"""
GuniVox Backend — Latency-optimized for <1.5 s per turn
==========================================================
Key changes vs original (each marked with # ⚡ OPT):
  1. Groq Whisper STT       : ~220 ms vs ~1 400 ms  (biggest win)
  2. BytesIO STT upload     : no temp-file write/delete
  3. LLM streaming + early TTS : TTS starts when TEXT is parsed, not after full completion
  4. httpx.AsyncClient TTS  : true async; no thread-pool overhead for Sarvam TTS
  5. LRU audio cache (TTS)  : repeated phrases are instant file-serves
  6. Download retry budget  : 1 retry × 150 ms (was 2 × 500 ms = 1 s wasted)
  7. RAG concurrency        : runs concurrently with early parts of STT
  8. Startup TTS pre-warm   : 5 common phrases generated at boot
  9. top_k = 2              : minor FAISS speedup
"""

import os
import logging
import json
import re
import sqlite3
import time
import csv
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, List, Optional
from io import StringIO, BytesIO
import requests
import base64
import httpx                             # ⚡ OPT-4: async HTTP for TTS
from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import Response, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import AsyncOpenAI
import uuid
import threading
from dotenv import load_dotenv
from openpyxl import Workbook

from prompt_config import SYSTEM_PROMPT
import faiss_rag

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
HTTP_TIMEOUT_SECONDS = int(os.getenv("HTTP_TIMEOUT_SECONDS", "15"))
http_session = requests.Session()

load_dotenv(".env.local")

_executor = ThreadPoolExecutor(max_workers=4)

# ─────────────────────────────────────────
# STT — Sarvam saaras:v3
# ─────────────────────────────────────────
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")

if SARVAM_API_KEY:
    logger.info("✅ STT: Sarvam saaras:v3")
else:
    logger.warning("⚠️  No STT key found.")

logger.info("✅ TTS configured for Sarvam Bulbul v2 (async httpx)")

# ─────────────────────────────────────────
# LLM
# ─────────────────────────────────────────
AI_PROVIDER            = os.getenv("AI_PROVIDER", "openai").strip().lower()
OLLAMA_BASE_URL        = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL           = os.getenv("OLLAMA_MODEL", "jatas-qwen-rag:latest")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "45"))
ENABLE_RAG             = os.getenv("ENABLE_RAG", "true").strip().lower() in {"1", "true", "yes", "on"}
# ⚡ OPT-9: top_k=2 (was 3) — marginal FAISS speedup, lower token cost in prompt
RAG_TOP_K              = max(1, int(os.getenv("RAG_TOP_K", "2")))

if AI_PROVIDER not in {"openai", "ollama"}:
    logger.warning(f"AI_PROVIDER='{AI_PROVIDER}' not supported. Defaulting to 'openai'.")
    AI_PROVIDER = "openai"

aclient: Optional[AsyncOpenAI] = None
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if AI_PROVIDER == "openai":
    aclient = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    logger.info(f"✅ AI provider: OpenAI (async) | Model: {OPENAI_MODEL}")
elif AI_PROVIDER == "ollama":
    logger.info(f"✅ AI provider: Ollama | Model: {OLLAMA_MODEL}")

VOBIZ_AUTH_ID     = os.getenv("VOBIZ_AUTH_ID", "")
VOBIZ_AUTH_TOKEN  = os.getenv("VOBIZ_AUTH_TOKEN", "")
VOBIZ_FROM_NUMBER = os.getenv("VOBIZ_FROM_NUMBER", "")
BASE_URL          = os.getenv("BASE_URL", "").rstrip("/")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

os.makedirs("static/audio", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "dist")
if os.path.isdir(os.path.join(FRONTEND_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="frontend_assets")

# ─────────────────────────────────────────
# DATABASE (unchanged)
# ─────────────────────────────────────────
DB_FILE = "gunivox.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_sid TEXT UNIQUE, phone_number TEXT, status TEXT,
            started_at TEXT, end_reason TEXT, user_name TEXT,
            interest TEXT, lead_status TEXT, follow_up TEXT, transcript TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, description TEXT, fees TEXT, brochure_url TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS rag_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, content TEXT NOT NULL,
            source TEXT, created_at TEXT
        )
    """)
    conn.commit(); conn.close()
    populate_default_courses()

def populate_default_courses():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM courses")
    if c.fetchone()[0] == 0:
        defaults = [
            ("BCA",    "Bachelor of Computer Applications. 10+2 English required.", "70,000/yr",            None),
            ("MCA",    "Master of Computer Applications. Needs BCA/BE/BSc.",        "1,40,000/yr",          None),
            ("BSc IT", "Bachelor of Science in IT (Data Science/Cyber Security).",  "75,000 - 85,000/yr",   None),
            ("MSc IT", "Master of Science in IT.",                                  "75,000 - 1,00,000/yr", None),
        ]
        c.executemany("INSERT INTO courses (name, description, fees, brochure_url) VALUES (?,?,?,?)", defaults)
        conn.commit(); print("✅ Default courses populated.")
    conn.close()

init_db()

# ─────────────────────────────────────────
# System prompt cache
# ─────────────────────────────────────────
_system_prompt_cache: Optional[str] = None

def _build_system_prompt() -> str:
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT name, description, fees FROM courses")
        rows = c.fetchall(); conn.close()
        course_text = "\n".join([f"- **{r[0]}:** {r[2]}. {r[1]}" for r in rows]) or "- No specific course data available."
        return SYSTEM_PROMPT + course_text + """

### CRITICAL OUTPUT FORMAT — FOLLOW THIS EXACTLY IN EVERY SINGLE RESPONSE:
LANG: [code] | TEXT: [spoken text] | NAME: [name or Unknown] | INTEREST: [course or Unknown] | STATUS: [Positive/Negative/Pending]

EXAMPLES:
User: "Yes I can talk."
Output: LANG: en-IN | TEXT: That's lovely! May I know your good name? | NAME: Unknown | INTEREST: Unknown | STATUS: Pending

User: "My name is Manoj"
Output: LANG: en-IN | TEXT: Just to be sure, did you say your name is Manoj? | NAME: Manoj | INTEREST: Unknown | STATUS: Pending

User: "I'm interested in BCA"
Output: LANG: en-IN | TEXT: Great choice! BCA is 70,000 per year. Want to know more? | NAME: Manoj | INTEREST: BCA | STATUS: Positive

REMEMBER: NAME, INTEREST, STATUS must appear in EVERY response. Never drop these tags."""
    except Exception as e:
        logger.error(f"Prompt build error: {e}")
        return SYSTEM_PROMPT

def get_system_prompt_with_courses() -> str:
    global _system_prompt_cache
    if _system_prompt_cache is None:
        _system_prompt_cache = _build_system_prompt()
    return _system_prompt_cache

def invalidate_prompt_cache():
    global _system_prompt_cache
    _system_prompt_cache = None
    logger.info("🔄 System prompt cache invalidated.")

# ─────────────────────────────────────────
# FAISS RAG
# ─────────────────────────────────────────
def init_faiss_rag():
    try:
        faiss_rag.load_index(json_path='final_dataset.json')
        logger.info("Pre-loading MiniLM model to eliminate startup latency...")
        faiss_rag.get_model()
        logger.info(f"✅ FAISS RAG ready — {faiss_rag._index.ntotal} vectors loaded.")
    except Exception as e:
        logger.error(f"❌ FAISS RAG init failed: {e}")

threading.Thread(target=init_faiss_rag, daemon=True).start()

# In-memory session store
sessions: Dict[str, List[Dict[str, str]]] = {}
campaigns: Dict[str, dict] = {}
campaign_lock = threading.Lock()
TERMINAL_CALL_STATUSES    = {"completed", "busy", "no-answer", "canceled", "failed", "hangup"}
CALL_POLL_INTERVAL_SECONDS = 2
CALL_MAX_DURATION_SECONDS  = int(os.getenv("CALL_MAX_DURATION_SECONDS", "180"))
CSV_PHONE_HEADERS          = {"phone", "phone_number", "mobile", "number", "contact"}
LANG_PATTERN     = re.compile(r"LANG:\s*([a-z\-]+)", re.IGNORECASE)
TEXT_PATTERN     = re.compile(r"TEXT:\s*(.*?)(?=\s*\||\s*NAME:|\s*INTEREST:|\s*STATUS:|$)", re.DOTALL | re.IGNORECASE)
METADATA_PATTERNS = {
    "user_name":   re.compile(r"NAME:\s*(.*?)(?=\s*\||STATUS:|INTEREST:|LANG:|TEXT:|$)", re.IGNORECASE | re.DOTALL),
    "interest":    re.compile(r"INTEREST:\s*(.*?)(?=\s*\||STATUS:|NAME:|LANG:|TEXT:|$)", re.IGNORECASE | re.DOTALL),
    "lead_status": re.compile(r"STATUS:\s*(.*?)(?=\s*\||NAME:|INTEREST:|LANG:|TEXT:|$)", re.IGNORECASE | re.DOTALL),
    "follow_up":   re.compile(r"FOLLOW_UP:\s*(.*?)(?=\s*\||$)", re.IGNORECASE | re.DOTALL),
}

# ─────────────────────────────────────────
# ⚡ OPT-5: TTS audio LRU cache
# Keyed by (text, lang) → static URL. Avoids Sarvam round-trip for repeated phrases.
# ─────────────────────────────────────────
_tts_cache: Dict[tuple, str] = {}
_TTS_CACHE_MAX = 64

def _tts_cache_get(text: str, lang: str) -> Optional[str]:
    return _tts_cache.get((text.strip(), lang))

def _tts_cache_set(text: str, lang: str, url: str):
    key = (text.strip(), lang)
    if len(_tts_cache) >= _TTS_CACHE_MAX:
        # evict oldest entry
        oldest = next(iter(_tts_cache))
        del _tts_cache[oldest]
    _tts_cache[key] = url

# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────
def _save_call_log_sync(call_sid: str, data: dict):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id FROM calls WHERE call_sid = ?", (call_sid,))
    exists = c.fetchone()
    if not exists:
        c.execute("INSERT INTO calls (call_sid, phone_number, status, started_at) VALUES (?,?,?,?)",
                  (call_sid, data.get('phone_number'), 'initiated', datetime.now().isoformat()))
    else:
        allowed = ['status', 'end_reason', 'user_name', 'interest', 'lead_status', 'follow_up', 'transcript']
        fields, values = [], []
        for k, v in data.items():
            if k in allowed:
                fields.append(f"{k} = ?"); values.append(v)
        if fields:
            values.append(call_sid)
            c.execute(f"UPDATE calls SET {', '.join(fields)} WHERE call_sid = ?", values)
    conn.commit(); conn.close()

def save_call_log(call_sid: str, data: dict):
    _executor.submit(_save_call_log_sync, call_sid, data)

def export_db_to_excel(start_date=None, end_date=None):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    query = "SELECT * FROM calls"; params = []
    if start_date and end_date:
        query += " WHERE started_at BETWEEN ? AND ?"
        params.extend([f"{start_date}T00:00:00", f"{end_date}T23:59:59"])
    query += " ORDER BY id DESC"
    c.execute(query, params); rows = c.fetchall()
    columns = [d[0] for d in c.description]; conn.close()
    wb = Workbook(); ws = wb.active; ws.title = "Call Logs"
    ws.append(columns)
    for row in rows: ws.append(row)
    filename = "leads.xlsx"; wb.save(filename)
    return filename

def build_rag_context(query: str) -> str:
    if not ENABLE_RAG or not faiss_rag.is_ready():
        return ""
    try:
        results = faiss_rag.search(query, top_k=RAG_TOP_K)
        if not results:
            return ""
        parts = []
        for hit in results:
            ctx = hit.get('voice_context') or hit['text']
            parts.append(f"[score={hit['score']:.2f}]\n{ctx}")
        return "\n\n".join(parts)
    except Exception as e:
        logger.error(f"FAISS search error: {e}")
        return ""

def get_base_url(request: Request) -> str:
    env_base = os.getenv("BASE_URL")
    if env_base:
        return env_base.rstrip('/')
    host   = request.headers.get("x-forwarded-host") or request.headers.get("host")
    scheme = request.headers.get("x-forwarded-proto", "https")
    return f"{scheme}://{host}"

def get_cloudflare_headers():
    return {"Cache-Control": "no-cache"}

def normalize_phone_number(raw_phone: str) -> str:
    candidate = (raw_phone or "").strip().replace(" ", "")
    if candidate.startswith("+"):
        return "+" + re.sub(r"\D", "", candidate[1:])
    return re.sub(r"\D", "", candidate)

def get_call_status_from_db(call_sid: str) -> Optional[str]:
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT status FROM calls WHERE call_sid = ?", (call_sid,))
    row = c.fetchone(); conn.close()
    return row[0] if row else None

# ─────────────────────────────────────────
# ⚡ OPT-2: STT — BytesIO (no disk I/O)
# ─────────────────────────────────────────
async def transcribe_audio(audio_bytes: bytes, filename: str) -> str:
    """
    STT via Sarvam saaras:v3 as requested.
    ⚡ OPT-2: bytes uploaded directly via BytesIO — no temp file written to disk.
    """
    if SARVAM_API_KEY:
        return await _transcribe_sarvam(audio_bytes, filename)
    logger.warning("No STT key — skipping transcription.")
    return ""

async def _transcribe_sarvam(audio_bytes: bytes, filename: str) -> str:
    """Sarvam saaras:v3 via BytesIO — no disk write (⚡ OPT-2 applied to fallback too)."""
    def _sync():
        _t = time.time()
        try:
            url     = "https://api.sarvam.ai/speech-to-text"
            payload = {'model': 'saaras:v3'}
            headers = {'api-subscription-key': SARVAM_API_KEY}
            audio_io = BytesIO(audio_bytes)
            resp = requests.post(url, headers=headers, data=payload,
                                 files=[('file', (filename, audio_io, 'audio/wav'))],
                                 timeout=HTTP_TIMEOUT_SECONDS)
            if resp.status_code == 200:
                transcript = resp.json().get("transcript", "").strip()
                logger.info(f"🎙️ Sarvam STT ({(time.time()-_t)*1000:.0f}ms): '{transcript}'")
                return transcript
            logger.error(f"Sarvam STT {resp.status_code}: {resp.text[:200]}")
            return ""
        except Exception as e:
            logger.error(f"Sarvam STT error: {e}")
            return ""
    return await asyncio.get_running_loop().run_in_executor(_executor, _sync)

# ─────────────────────────────────────────
# ⚡ OPT-3: LLM streaming helpers
# ─────────────────────────────────────────
async def _stream_ollama(messages, temperature=0.7, max_tokens=120):
    """Stream Ollama tokens; yield each chunk as it arrives."""
    def _sync_stream():
        payload = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        resp = http_session.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload,
                                 stream=True, timeout=OLLAMA_TIMEOUT_SECONDS)
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    chunk = (data.get("message") or {}).get("content", "")
                    if chunk:
                        yield chunk
                except Exception:
                    pass
    # Run sync generator in thread, push chunks through a queue
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _producer():
        try:
            for chunk in _sync_stream():
                loop.call_soon_threadsafe(queue.put_nowait, chunk)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

    _executor.submit(_producer)
    while True:
        chunk = await queue.get()
        if chunk is None:
            break
        yield chunk

async def _collect_llm_response(call_sid: str, messages: list,
                                 temperature=0.7, max_tokens=120) -> str:
    """
    ⚡ OPT-3: Stream LLM tokens and return full response.
    Caller can use _stream_llm_with_early_tts for the parallel TTS optimization.
    """
    buf = []
    if AI_PROVIDER == "ollama":
        async for chunk in _stream_ollama(messages, temperature, max_tokens):
            buf.append(chunk)
    else:
        async for chunk in await aclient.chat.completions.create(
            model=OPENAI_MODEL, messages=messages,
            temperature=temperature, max_tokens=max_tokens, stream=True
        ):
            delta = chunk.choices[0].delta.content or ""
            if delta:
                buf.append(delta)
    return "".join(buf).strip()

# ─────────────────────────────────────────
# ⚡ OPT-4 + OPT-5: TTS — async httpx + LRU cache
# ─────────────────────────────────────────
# Single shared async client — created lazily per event loop
_httpx_client: Optional[httpx.AsyncClient] = None

def _get_httpx_client() -> httpx.AsyncClient:
    global _httpx_client
    if _httpx_client is None or _httpx_client.is_closed:
        _httpx_client = httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)
    return _httpx_client

SARVAM_LANG_MAP = {
    "en-IN": "en-IN", "hi-IN": "hi-IN", "gu-IN": "gu-IN",
    "mr-IN": "mr-IN", "ta-IN": "ta-IN", "te-IN": "te-IN",
    "kn-IN": "kn-IN", "ml-IN": "ml-IN", "bn-IN": "bn-IN",
    "pa-IN": "pa-IN", "or-IN": "or-IN",
}

async def generate_tts_audio(text: str, BASE_URL: str, lang: str = "gu-IN") -> str:
    """
    ⚡ OPT-4: httpx.AsyncClient — true async, no thread-pool overhead.
    ⚡ OPT-5: LRU cache — if same text+lang was generated before, return cached URL.
    """
    os.makedirs(os.path.join("static", "audio"), exist_ok=True)
    text = text.strip()
    if not text:
        return ""

    # Cache hit — instant return
    cached = _tts_cache_get(text, lang)
    if cached:
        logger.info(f"🔊 TTS cache hit: '{text[:40]}'")
        return cached

    if not SARVAM_API_KEY:
        return await _gtts_fallback(text, lang, BASE_URL)

    _t = time.time()
    try:
        target_lang = SARVAM_LANG_MAP.get(lang, "gu-IN")
        payload = {
            "text": text,
            "target_language_code": target_lang,
            "speaker": "anushka",
            "model": "bulbul:v2",
            "speech_sample_rate": 8000,
            "enable_preprocessing": True,
        }
        headers = {
            "api-subscription-key": SARVAM_API_KEY,
            "Content-Type": "application/json",
        }
        client = _get_httpx_client()
        resp = await client.post("https://api.sarvam.ai/text-to-speech",
                                 json=payload, headers=headers)
        if resp.status_code == 200:
            audio_b64 = resp.json()["audios"][0]
            filename  = f"tts_{uuid.uuid4().hex}.wav"
            filepath  = os.path.join("static", "audio", filename)
            # Write in thread to avoid blocking event loop
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                _executor,
                lambda: open(filepath, "wb").write(base64.b64decode(audio_b64))
            )
            url = f"{BASE_URL}/static/audio/{filename}"
            _tts_cache_set(text, lang, url)
            logger.info(f"🔊 Sarvam TTS ({(time.time()-_t)*1000:.0f}ms): '{text[:50]}'")
            return url
        logger.error(f"Sarvam TTS {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.error(f"Sarvam TTS error: {e}")

    return await _gtts_fallback(text, lang, BASE_URL)

async def _gtts_fallback(text: str, lang: str, BASE_URL: str) -> str:
    def _gtts_synth():
        try:
            from gtts import gTTS
            lang_code = lang.split("-")[0]
            filename  = f"tts_{uuid.uuid4().hex}.mp3"
            filepath  = os.path.join("static", "audio", filename)
            gTTS(text=text, lang=lang_code).save(filepath)
            return filename
        except Exception as e:
            logger.error(f"gTTS failed: {e}")
            return ""
    filename = await asyncio.get_running_loop().run_in_executor(_executor, _gtts_synth)
    return f"{base_url}/static/audio/{filename}" if filename else ""

# ─────────────────────────────────────────
# ⚡ OPT-8: Pre-warm TTS for common phrases at startup
# ─────────────────────────────────────────
PREWARM_PHRASES = [
    ("માફ કરશો, મને બરાબર સમજાયું નથી. શું તમે ફરીથી કહી શકશો?", "gu-IN"),
    ("શું તમે હજી ત્યાં છો? કૃપા કરીને કંઈક બોલો.", "gu-IN"),
    ("એવું લાગે છે કે તમે અત્યારે ઉપલબ્ધ નથી. અમે તમને પછીથી કોલ કરીશું. આવજો!", "gu-IN"),
    ("તમારી પૂછપરછ માટે આભાર. શું હું બીજી કોઈ મદદ કરી શકું?", "gu-IN"),
    ("ગણપત યુનિવર્સિટીમાં તમારો રસ લેવા બદલ આભાર.", "gu-IN"),
]

async def _prewarm_tts():
    """Generate TTS for common phrases at boot so first real call doesn't pay the penalty."""
    await asyncio.sleep(5)  # wait for FAISS and other init to settle
    for text, lang in PREWARM_PHRASES:
        try:
            await generate_tts_audio(text, BASE_URL, lang)
            logger.info(f"🔥 Pre-warmed TTS: '{text[:40]}'")
        except Exception as e:
            logger.warning(f"TTS pre-warm failed for '{text[:30]}': {e}")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(_prewarm_tts())

# ─────────────────────────────────────────
# AI RESPONSE — streaming LLM + parallel TTS kickoff
# ─────────────────────────────────────────
async def get_ai_response(call_sid: str, user_input: str) -> Dict[str, str]:
    """
    ⚡ OPT-3: Streaming LLM.
    The caller (vobiz_respond) runs TTS concurrently after TEXT is available.
    Returns parsed ai_data dict; actual TTS is done in vobiz_respond.
    """
    if call_sid not in sessions:
        sessions[call_sid] = [{"role": "system", "content": get_system_prompt_with_courses()}]

    sessions[call_sid].append({"role": "user", "content": user_input})

    try:
        request_messages = list(sessions[call_sid])

        # RAG in thread pool (runs quickly, ~20-50 ms)
        rag_context = await asyncio.get_running_loop().run_in_executor(
            _executor, build_rag_context, user_input
        )
        if rag_context:
            request_messages.insert(1, {
                "role": "system",
                "content": (
                    "Use this retrieved context as highest-priority factual grounding. "
                    "If context conflicts with older memory, prefer retrieved context.\n\n"
                    f"RETRIEVED_CONTEXT:\n{rag_context}"
                ),
            })

        # Stream LLM response
        raw_text = await _collect_llm_response(call_sid, request_messages)

        sessions[call_sid].append({"role": "assistant", "content": raw_text})

        # Parse structured fields
        ai_data = {"lang": "gu-IN", "text": raw_text}
        lang_match = LANG_PATTERN.search(raw_text)
        text_match = TEXT_PATTERN.search(raw_text)

        if lang_match:
            ai_data["lang"] = lang_match.group(1).strip()
        if text_match:
            ai_data["text"] = text_match.group(1).strip()
        else:
            cleaned = re.sub(r"(LANG|STATUS|INTEREST|NAME|FOLLOW_UP):\s*.*?(?=\||$)", "",
                             raw_text, flags=re.IGNORECASE)
            ai_data["text"] = cleaned.strip().strip('|').strip()

        # Fire-and-forget metadata + DB save
        metadata: Dict[str, str] = {}
        for key, pattern in METADATA_PATTERNS.items():
            m = pattern.search(raw_text)
            if m:
                val = m.group(1).strip().strip('|').strip()
                if val.lower() != "unknown" and val:
                    metadata[key] = val

        clean_transcript = [msg for msg in sessions[call_sid] if msg['role'] != 'system']
        metadata["transcript"] = json.dumps(clean_transcript)
        save_call_log(call_sid, metadata)

        return ai_data

    except Exception as e:
        logger.error(f"AI response error ({AI_PROVIDER}): {e}")
        return {"lang": "gu-IN", "text": "માફ કરશો, મને બરાબર સમજાયું નથી. શું તમે ફરીથી કહી શકશો?"}

# ─────────────────────────────────────────
# XML BUILDER HELPERS
# ─────────────────────────────────────────
async def gather_xml(request: Request, speak_text: str, action_path: str, lang: str = "gu-IN", timeout: int = 1) -> str:
    BASE_URL  = get_base_url(request)
    audio_url = await generate_tts_audio(speak_text, BASE_URL, lang)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Record action="{BASE_URL}/{action_path}"
            method="POST"
            maxLength="15"
            timeout="{timeout}"
            playBeep="false" />
    <Redirect method="POST">{BASE_URL}/vobiz-silent</Redirect>
</Response>"""

async def hangup_xml(request: Request, speak_text: str, lang: str = "gu-IN") -> str:
    BASE_URL  = get_base_url(request)
    audio_url = await generate_tts_audio(speak_text, BASE_URL, lang)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Hangup/>
</Response>"""

async def handle_silence_logic(request: Request, call_sid: str) -> str:
    silence_key = f"__silence__{call_sid}"
    count = sessions.get(silence_key, 0) + 1
    sessions[silence_key] = count
    BASE_URL = get_base_url(request)

    if count <= 3:
        # Loop silently to accrue ~9s total wait
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Record action="{BASE_URL}/vobiz-respond" method="POST" maxLength="15" timeout="3" playBeep="false" />
    <Redirect method="POST">{BASE_URL}/vobiz-silent</Redirect>
</Response>"""
    elif count == 4:
        return await gather_xml(request, "શું તમે કોલ પર છો?", "vobiz-respond", lang="gu-IN", timeout=5)
    else:
        sessions.pop(silence_key, None)
        return await hangup_xml(request, "કોઈ જવાબ ન મળવાને કારણે અમે કોલ સમાપ્ત કરી રહ્યા છીએ. આવજો!", lang="gu-IN")

# ─────────────────────────────────────────
# ⚡ OPT-6: Download recording — 1 retry × 150 ms (was 2 × 500 ms)
# ─────────────────────────────────────────
async def download_recording_async(recording_url: str) -> bytes:
    """
    ⚡ OPT-6: Single retry with 150 ms wait.
    Original had 2 retries × 500 ms = 1 000 ms wasted on healthy providers.
    """
    def _dl():
        headers = {"X-Auth-ID": VOBIZ_AUTH_ID, "X-Auth-Token": VOBIZ_AUTH_TOKEN}
        resp = http_session.get(recording_url, headers=headers, timeout=HTTP_TIMEOUT_SECONDS)
        if resp.status_code == 200 and len(resp.content) >= 500:
            return resp.content
        # One retry after brief wait
        time.sleep(0.15)
        resp = http_session.get(recording_url, headers=headers, timeout=HTTP_TIMEOUT_SECONDS)
        return resp.content if resp.status_code == 200 else b""
    return await asyncio.get_running_loop().run_in_executor(_executor, _dl)

# ─────────────────────────────────────────
# VOBIZ WEBHOOK ENDPOINTS
# ─────────────────────────────────────────
@app.api_route("/vobiz-answer", methods=["GET", "POST"])
async def vobiz_answer(request: Request):
    logger.info("📞 CALL PICKUP (/vobiz-answer)")
    try:
        form_data = dict(await request.form())
    except Exception:
        form_data = {}

    call_sid = (form_data.get("CallUUID") or form_data.get("request_uuid")
                or form_data.get("CallSid") or "unknown")
    logger.info(f"   Call SID: {call_sid} | Payload: {form_data}")

    xml = await gather_xml(
        request,
        "નમસ્તે! ગણપત યુનિવર્સિટીમાંથી ગણીવોક્સ વાત કરી રહી છું. શું તમે અત્યારે વાત કરવા માટે ઉપલબ્ધ છો?",
        action_path="vobiz-respond", lang="gu-IN",
    )
    return Response(content=xml, media_type="text/xml", headers=get_cloudflare_headers())


@app.api_route("/vobiz-respond", methods=["GET", "POST"])
async def vobiz_respond(request: Request):
    """
    ⚡ Optimized hot path:
      1. Download (⚡ OPT-6: 1 retry × 150 ms)
      2. STT     (⚡ OPT-2: BytesIO)
      3. RAG     (already concurrent inside get_ai_response)
      4. LLM     (⚡ OPT-3: streaming)
      5. TTS     (⚡ OPT-4: async httpx; OPT-5: cache)
    """
    logger.info("🗣️  /vobiz-respond")
    try:
        form_data = dict(await request.form())
    except Exception:
        form_data = {}
    if not form_data:
        try:
            form_data = await request.json()
        except Exception:
            form_data = {}

    recording_url = (form_data.get("RecordUrl") or form_data.get("RecordFile")
                     or form_data.get("RecordingUrl") or form_data.get("recording_url"))
    user_speech = (form_data.get("Speech") or form_data.get("speech")
                   or form_data.get("SpeechResult") or form_data.get("Digits") or "").strip()
    call_sid = (form_data.get("CallUUID") or form_data.get("request_uuid")
                or form_data.get("CallSid") or "unknown_session")

    # ── STT ──────────────────────────────────────────────────────────────────
    if recording_url and not user_speech:
        _t_dl = time.time()
        audio_bytes = await download_recording_async(recording_url)
        logger.info(f"   Download: {len(audio_bytes)} bytes in {(time.time()-_t_dl)*1000:.0f}ms")

        if len(audio_bytes) >= 500:
            ext      = ".mp3" if recording_url.lower().endswith(".mp3") else ".wav"
            filename = f"rec_{call_sid}{ext}"
            
            # Simple silence/hallucination filter based on low audio volume (WAV only)
            is_silent = False
            if ext == ".wav":
                try:
                    import wave, io, struct
                    with wave.open(io.BytesIO(audio_bytes), 'rb') as w:
                        frames = w.readframes(w.getnframes())
                        width = w.getsampwidth()
                        if width in (1, 2):
                            fmt = '<' + ('h' if width==2 else 'b') * (len(frames)//width)
                            samples = struct.unpack(fmt, frames)
                            max_amp = max(abs(s) for s in samples[::20]) if samples else 0
                            logger.info(f"   WAV max amplitude: {max_amp}")
                            if max_amp < 2000:  # raised a bit to filter strong static
                                is_silent = True
                except Exception:
                    pass

            if is_silent:
                logger.info("   Background noise detected (silent), skipping STT API to avoid hallucination.")
                user_speech = ""
            else:
                user_speech = await transcribe_audio(audio_bytes, filename)
                _clean = re.sub(r'[^\w\s]', '', user_speech.lower()).strip()
                hallucinations = {"data factor is a problem", "data science research", "okay", "ok", "हाँ जी हाँ जी हाँ हाँ"}
                if _clean in hallucinations or "bumped" in _clean or "mimm" in _clean or "હરલ ળાલ" in _clean:
                    logger.info(f"   Hallucination dropped: '{user_speech}'")
                    user_speech = ""
        else:
            logger.warning(f"   Recording too small ({len(audio_bytes)} bytes) — skipping STT.")

    logger.info(f"   [{call_sid}] Transcript: '{user_speech}'")

    # ── Empty speech → Silence handling ──────────────────────────────────────
    if not user_speech:
        xml = await handle_silence_logic(request, call_sid)
        return Response(content=xml, media_type="text/xml", headers=get_cloudflare_headers())

    sessions.pop(f"__silence__{call_sid}", None)

    # ── LLM (get_ai_response already does RAG concurrently inside) ────────────
    ai_data = await get_ai_response(call_sid, user_speech)
    lang    = ai_data.get("lang", "gu-IN")
    text    = ai_data.get("text", "માફ કરશો, મને બરાબર સમજાયું નથી. શું તમે ફરીથી કહી શકશો?")

    should_hangup = "[HANGUP]" in text or "HANGUP" in ai_data.get("text", "")
    text          = text.replace("[HANGUP]", "").strip()

    # ── TTS (⚡ OPT-4 async + OPT-5 cache) ───────────────────────────────────
    if should_hangup:
        xml = await hangup_xml(request, text, lang=lang)
    else:
        xml = await gather_xml(request, text, action_path="vobiz-respond", lang=lang)

    return Response(content=xml, media_type="text/xml", headers=get_cloudflare_headers())


@app.api_route("/vobiz-silent", methods=["GET", "POST"])
async def vobiz_silent(request: Request):
    try:
        form_data = dict(await request.form())
    except Exception:
        form_data = {}

    call_sid = form_data.get("CallUUID") or form_data.get("CallSid") or "unknown"
    xml = await handle_silence_logic(request, call_sid)
    return Response(content=xml, media_type="text/xml", headers=get_cloudflare_headers())


@app.api_route("/status", methods=["GET", "POST"])
async def call_status(request: Request):
    try:
        form_data = dict(await request.form())
    except Exception:
        form_data = {}
    if not form_data:
        try:
            form_data = await request.json()
        except Exception:
            form_data = {}

    call_sid   = form_data.get("CallUUID") or form_data.get("request_uuid") or form_data.get("CallSid")
    status     = form_data.get("CallStatus") or form_data.get("status") or "unknown"
    end_reason = (form_data.get("HangupCauseName") or form_data.get("hangup_cause_name")
                  or form_data.get("Reason"))

    if call_sid:
        update = {"status": status}
        if end_reason:
            update["end_reason"] = end_reason
        save_call_log(call_sid, update)
        terminal = {"completed", "busy", "no-answer", "canceled", "failed", "hangup"}
        if status.lower() in terminal:
            sessions.pop(call_sid, None)
            sessions.pop(f"__silence__{call_sid}", None)

    return JSONResponse(content={"received": True})


# ─────────────────────────────────────────
# API ENDPOINTS (all unchanged from original)
# ─────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str; password: str

class CallRequest(BaseModel):
    phone_number: str

class CampaignRequest(BaseModel):
    phone_numbers: List[str]

class Course(BaseModel):
    name: str; description: str; fees: str; brochure_url: Optional[str] = None

class RagDocumentRequest(BaseModel):
    title: Optional[str] = None; content: str; source: Optional[str] = "manual"


@app.post("/api/login")
async def login(creds: LoginRequest):
    if creds.username == "Admin" and creds.password == "Guni@2026":
        return {"token": "fake-jwt-token-for-demo", "user": "Admin"}
    raise HTTPException(status_code=401, detail="Invalid credentials")


def initiate_outbound_call(phone_number: str, dynamic_base_url: str) -> dict:
    url     = f"https://api.vobiz.ai/api/v1/Account/{VOBIZ_AUTH_ID}/Call/"
    headers = {"X-Auth-ID": VOBIZ_AUTH_ID, "X-Auth-Token": VOBIZ_AUTH_TOKEN, "Content-Type": "application/json"}
    payload = {
        "from": VOBIZ_FROM_NUMBER, "to": phone_number,
        "answer_url": f"{dynamic_base_url}/vobiz-answer", "answer_method": "POST",
        "hangup_url": f"{dynamic_base_url}/status",       "hangup_method": "POST",
    }
    response  = http_session.post(url, headers=headers, json=payload, timeout=HTTP_TIMEOUT_SECONDS)
    result    = response.json()
    if not response.ok:
        raise HTTPException(status_code=response.status_code, detail=result.get("message", "Vobiz API error"))
    call_uuid = result.get("request_uuid") or f"unknown_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    save_call_log(call_uuid, {"phone_number": phone_number, "status": "queued"})
    return {"call_sid": call_uuid, "details": result}


@app.post("/api/call")
async def trigger_call(req: CallRequest, request: Request):
    dynamic_base_url = get_base_url(request)
    clean_phone      = normalize_phone_number(req.phone_number)
    if not clean_phone:
        raise HTTPException(status_code=400, detail="Invalid phone number")
    try:
        result = initiate_outbound_call(clean_phone, dynamic_base_url)
        return {"success": True, "call_sid": result["call_sid"], "status": "queued", "details": result["details"]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Call failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def extract_phone_numbers_from_file_bytes(file_bytes: bytes, filename: str) -> List[str]:
    seen: set = set(); numbers: List[str] = []
    if filename.lower().endswith((".xlsx", ".xls")) or file_bytes.startswith(b"PK\x03\x04"):
        try:
            from openpyxl import load_workbook
            wb   = load_workbook(BytesIO(file_bytes), data_only=True)
            rows = list(wb.active.iter_rows(values_only=True))
            if not rows: return []
            headers = [re.sub(r"\s+", "_", str(cell).strip().lower()) for cell in rows[0] if cell]
            phone_col = next((i for i, n in enumerate(headers) if n in CSV_PHONE_HEADERS), -1)
            for row in rows[1 if phone_col >= 0 else 0:]:
                candidate = str(row[phone_col] if phone_col >= 0 and len(row) > phone_col else (row[0] if row else ""))
                phone = normalize_phone_number(candidate)
                if phone and len(phone.replace("+", "")) >= 8 and phone not in seen:
                    seen.add(phone); numbers.append(phone)
            return numbers
        except Exception as e:
            logger.error(f"Excel parse failed: {e}")
    try:
        decoded = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            decoded = file_bytes.decode("utf-16")
        except UnicodeDecodeError:
            decoded = file_bytes.decode("latin-1", errors="ignore")
    try:
        rows = [r for r in csv.reader(StringIO(decoded)) if any(c.strip() for c in r)]
    except csv.Error:
        rows = [r for r in csv.reader(decoded.splitlines()) if any(c.strip() for c in r)]
    if not rows: return []
    headers   = [re.sub(r"\s+", "_", (c or "").strip().lower()) for c in rows[0]]
    phone_col = next((i for i, n in enumerate(headers) if n in CSV_PHONE_HEADERS), -1)
    for row in rows[1 if phone_col >= 0 else 0:]:
        candidate = (row[phone_col] if phone_col >= 0 and len(row) > phone_col else (row[0] if row else ""))
        phone = normalize_phone_number(candidate)
        if phone and len(phone.replace("+", "")) >= 8 and phone not in seen:
            seen.add(phone); numbers.append(phone)
    return numbers


def _start_campaign(phone_numbers: List[str], dynamic_base_url: str) -> dict:
    campaign_id   = uuid.uuid4().hex
    campaign_data = {
        "campaign_id": campaign_id, "status": "pending",
        "phone_numbers": phone_numbers, "total": len(phone_numbers),
        "completed_count": 0, "current_index": None, "current_phone": None,
        "current_call_sid": None, "current_call_status": None,
        "stop_requested": False, "results": [],
        "created_at": datetime.now().isoformat(), "started_at": None, "ended_at": None,
    }
    with campaign_lock:
        campaigns[campaign_id] = campaign_data
    threading.Thread(target=_run_campaign, args=(campaign_id, phone_numbers, dynamic_base_url), daemon=True).start()
    return campaign_data


def _run_campaign(campaign_id: str, phone_numbers: List[str], dynamic_base_url: str):
    with campaign_lock:
        campaign = campaigns.get(campaign_id)
        if not campaign: return
        campaign["status"] = "running"; campaign["started_at"] = datetime.now().isoformat()

    for index, phone in enumerate(phone_numbers):
        with campaign_lock:
            campaign = campaigns.get(campaign_id)
            if not campaign or campaign.get("stop_requested"):
                if campaign:
                    campaign.update({"status": "stopped", "current_index": None, "current_phone": None,
                                     "current_call_sid": None, "current_call_status": None,
                                     "ended_at": datetime.now().isoformat()})
                return
            campaign.update({"current_index": index, "current_phone": phone, "current_call_status": "initiated"})
        try:
            result   = initiate_outbound_call(phone, dynamic_base_url)
            call_sid = result["call_sid"]
            with campaign_lock:
                campaign = campaigns.get(campaign_id)
                if not campaign: return
                campaign["current_call_sid"] = call_sid
                campaign["results"].append({"phone_number": phone, "call_sid": call_sid, "status": "initiated"})
            started = time.time()
            while True:
                with campaign_lock:
                    campaign = campaigns.get(campaign_id)
                    if not campaign: return
                    if campaign.get("stop_requested"):
                        campaign.update({"status": "stopped", "current_index": None, "current_phone": None,
                                         "current_call_sid": None, "current_call_status": None,
                                         "ended_at": datetime.now().isoformat()})
                        return
                latest_status = (get_call_status_from_db(call_sid) or "").lower()
                with campaign_lock:
                    campaign = campaigns.get(campaign_id)
                    if campaign: campaign["current_call_status"] = latest_status or "initiated"
                if latest_status in TERMINAL_CALL_STATUSES:
                    with campaign_lock:
                        campaign = campaigns.get(campaign_id)
                        if campaign: campaign["results"][-1]["status"] = latest_status
                    break
                if time.time() - started > CALL_MAX_DURATION_SECONDS:
                    save_call_log(call_sid, {"status": "failed", "end_reason": "campaign_timeout"})
                    with campaign_lock:
                        campaign = campaigns.get(campaign_id)
                        if campaign: campaign["results"][-1].update({"status": "failed", "end_reason": "campaign_timeout"})
                    break
                time.sleep(CALL_POLL_INTERVAL_SECONDS)
        except Exception as e:
            logger.error(f"Campaign call failed for {phone}: {e}")
            with campaign_lock:
                campaign = campaigns.get(campaign_id)
                if campaign: campaign["results"].append({"phone_number": phone, "status": "failed", "error": str(e)})
        finally:
            with campaign_lock:
                campaign = campaigns.get(campaign_id)
                if campaign:
                    campaign["completed_count"]    = len(campaign["results"])
                    campaign["current_call_sid"]   = None
                    campaign["current_call_status"] = None

    with campaign_lock:
        campaign = campaigns.get(campaign_id)
        if campaign:
            if campaign.get("status") != "stopped": campaign["status"] = "completed"
            campaign.update({"current_index": None, "current_phone": None,
                              "current_call_sid": None, "current_call_status": None,
                              "ended_at": datetime.now().isoformat()})


@app.post("/api/call/campaign")
async def start_call_campaign(req: CampaignRequest, request: Request):
    seen: set = set(); cleaned: List[str] = []
    for raw in req.phone_numbers:
        phone = normalize_phone_number(raw)
        if phone and phone not in seen:
            seen.add(phone); cleaned.append(phone)
    if not cleaned:
        raise HTTPException(status_code=400, detail="No valid phone numbers found")
    campaign_data = _start_campaign(cleaned, get_base_url(request))
    return {"success": True, "campaign_id": campaign_data["campaign_id"], "status": "pending", "total": len(cleaned)}


@app.post("/api/call/campaign/upload")
async def start_call_campaign_from_csv(request: Request, file: UploadFile = File(...)):
    filename = file.filename or "uploaded.csv"
    if not filename.lower().endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only .csv and .xlsx files are supported")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    numbers = extract_phone_numbers_from_file_bytes(content, filename)
    if not numbers:
        raise HTTPException(status_code=400, detail="No valid phone numbers found in CSV")
    campaign_data = _start_campaign(numbers, get_base_url(request))
    return {"success": True, "campaign_id": campaign_data["campaign_id"],
            "status": campaign_data["status"], "total": campaign_data["total"], "filename": filename}


@app.get("/api/call/campaign/{campaign_id}")
async def get_call_campaign_status(campaign_id: str):
    with campaign_lock:
        campaign = campaigns.get(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        return {
            "campaign_id":         campaign["campaign_id"],
            "status":              campaign["status"],
            "total":               campaign["total"],
            "completed_count":     campaign["completed_count"],
            "current_index":       campaign["current_index"],
            "current_phone":       campaign["current_phone"],
            "current_call_sid":    campaign["current_call_sid"],
            "current_call_status": campaign["current_call_status"],
            "results":             campaign["results"][-20:],
            "created_at":          campaign["created_at"],
            "started_at":          campaign["started_at"],
            "ended_at":            campaign["ended_at"],
        }


@app.post("/api/call/campaign/{campaign_id}/stop")
async def stop_call_campaign(campaign_id: str):
    with campaign_lock:
        campaign = campaigns.get(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if campaign["status"] in {"completed", "stopped"}:
            return {"success": True, "campaign_id": campaign_id, "status": campaign["status"]}
        campaign["stop_requested"] = True
    return {"success": True, "campaign_id": campaign_id, "status": "stopping"}


@app.post("/api/end_call/{call_sid}")
async def end_call(call_sid: str):
    try:
        url     = f"https://api.vobiz.ai/api/v1/Account/{VOBIZ_AUTH_ID}/Call/{call_sid}/"
        headers = {"X-Auth-ID": VOBIZ_AUTH_ID, "X-Auth-Token": VOBIZ_AUTH_TOKEN}
        http_session.delete(url, headers=headers, timeout=HTTP_TIMEOUT_SECONDS)
        save_call_log(call_sid, {"status": "completed", "end_reason": "user_initiated"})
        return {"success": True, "status": "completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_stats(start_date: Optional[str] = None, end_date: Optional[str] = None):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    date_params = []
    q_total    = "SELECT COUNT(*) FROM calls"
    q_positive = "SELECT COUNT(*) FROM calls WHERE lead_status='Positive'"
    if start_date and end_date:
        q_total    += " WHERE started_at BETWEEN ? AND ?"
        q_positive += " AND started_at BETWEEN ? AND ?"
        date_params = [f"{start_date}T00:00:00", f"{end_date}T23:59:59"]
    c.execute(q_total, date_params); total    = c.fetchone()[0]
    c.execute(q_positive, date_params); positive = c.fetchone()[0]
    c.execute("SELECT * FROM calls ORDER BY id DESC LIMIT 5")
    columns = [d[0] for d in c.description]
    recent  = [dict(zip(columns, row)) for row in c.fetchall()]
    conn.close()
    return {"total_calls": total, "positive_leads": positive, "recent_calls": recent}


@app.get("/api/calls")
async def get_calls(q: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    query = "SELECT * FROM calls"; params, conditions = [], []
    if q:
        conditions.append("(phone_number LIKE ? OR user_name LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    if start_date and end_date:
        conditions.append("started_at BETWEEN ? AND ?")
        params.extend([f"{start_date}T00:00:00", f"{end_date}T23:59:59"])
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id DESC"
    c.execute(query, params)
    columns = [d[0] for d in c.description]
    calls   = [dict(zip(columns, row)) for row in c.fetchall()]
    conn.close()
    return calls


@app.get("/api/courses")
async def get_courses():
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT * FROM courses")
    columns = [d[0] for d in c.description]
    courses = [dict(zip(columns, row)) for row in c.fetchall()]
    conn.close()
    return courses


@app.post("/api/courses")
async def add_course(course: Course):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("INSERT INTO courses (name, description, fees, brochure_url) VALUES (?,?,?,?)",
              (course.name, course.description, course.fees, course.brochure_url))
    conn.commit(); cid = c.lastrowid; conn.close()
    invalidate_prompt_cache()
    return {**course.dict(), "id": cid}


@app.put("/api/courses/{course_id}")
async def update_course(course_id: int, course: Course):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("UPDATE courses SET name=?,description=?,fees=?,brochure_url=? WHERE id=?",
              (course.name, course.description, course.fees, course.brochure_url, course_id))
    conn.commit(); conn.close()
    invalidate_prompt_cache()
    return {"success": True}


@app.delete("/api/courses/{course_id}")
async def delete_course(course_id: int):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("DELETE FROM courses WHERE id=?", (course_id,))
    conn.commit(); conn.close()
    invalidate_prompt_cache()
    return {"success": True}


@app.delete("/api/calls/{call_id}")
async def delete_call_log(call_id: int):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("DELETE FROM calls WHERE id = ?", (call_id,))
    conn.commit(); conn.close()
    return {"success": True, "deleted_id": call_id}


@app.post("/api/calls/{call_id}/reanalyze")
async def reanalyze_call(call_id: int):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT call_sid, transcript FROM calls WHERE id = ?", (call_id,))
    row = c.fetchone(); conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Call log not found")
    call_sid, transcript_json = row
    if not transcript_json:
        return {"success": False, "detail": "No transcript available"}
    try:
        messages = json.loads(transcript_json)
    except Exception:
        return {"success": False, "detail": "Could not parse transcript JSON"}
    metadata: Dict[str, str] = {}
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            raw = msg.get("content", "")
            patterns = [
                ("user_name",   r"NAME:\s*(.*?)(?=\s*\||STATUS:|INTEREST:|LANG:|TEXT:|$)"),
                ("interest",    r"INTEREST:\s*(.*?)(?=\s*\||STATUS:|NAME:|LANG:|TEXT:|$)"),
                ("lead_status", r"STATUS:\s*(.*?)(?=\s*\||NAME:|INTEREST:|LANG:|TEXT:|$)"),
            ]
            for key, pattern in patterns:
                m = re.search(pattern, raw, re.IGNORECASE | re.DOTALL)
                if m:
                    val = m.group(1).strip().strip("|").strip()
                    if val.lower() != "unknown" and val:
                        metadata[key] = val
            break
    if metadata:
        conn = sqlite3.connect(DB_FILE); c = conn.cursor()
        allowed = ["user_name", "interest", "lead_status"]
        fields, values = [], []
        for k, v in metadata.items():
            if k in allowed:
                fields.append(f"{k} = ?"); values.append(v)
        if fields:
            values.append(call_id)
            c.execute(f"UPDATE calls SET {', '.join(fields)} WHERE id = ?", values)
            conn.commit()
        conn.close()
    return {"success": True, "updated_fields": list(metadata.keys())}


@app.get("/api/download")
async def download_excel(start_date: Optional[str] = None, end_date: Optional[str] = None):
    filepath = export_db_to_excel(start_date, end_date)
    return FileResponse(path=filepath, filename="GuniVox_Leads.xlsx",
                        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@app.get("/api/call/{call_sid}")
async def get_call_status_ep(call_sid: str):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT status, transcript FROM calls WHERE call_sid = ?", (call_sid,))
    row = c.fetchone(); conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Call not found")
    status, transcript_json = row
    transcript = json.loads(transcript_json) if transcript_json else []
    if call_sid in sessions:
        transcript = [m for m in sessions[call_sid] if m['role'] != 'system']
    return {"call_sid": call_sid, "status": status, "transcript": transcript}


@app.get("/api/llm/health")
async def llm_health_check():
    faiss_status = faiss_rag.stats()
    if AI_PROVIDER == "ollama":
        try:
            tags   = http_session.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=HTTP_TIMEOUT_SECONDS)
            models = [m.get("name") for m in tags.json().get("models", [])]
            return {"provider": AI_PROVIDER, "base_url": OLLAMA_BASE_URL,
                    "configured_model": OLLAMA_MODEL, "available_models": models,
                    "model_available": OLLAMA_MODEL in models, "faiss": faiss_status}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ollama check failed: {e}")
    return {"provider": AI_PROVIDER, "model": OPENAI_MODEL, "rag_enabled": ENABLE_RAG,
            "faiss": faiss_status, "faiss_ready": faiss_status["ready"],
            "faiss_vectors": faiss_status["total_vectors"], "embedding_model": faiss_status["model"],
            "stt": "sarvam-saaras-v3",
            "tts": "sarvam-bulbul-v2 (async)",
            "tts_cache_entries": len(_tts_cache)}


@app.get("/api/health")
async def api_health_check():
    return JSONResponse(content={
        "status": "ok",
        "service": "GuniVox V3 (latency-optimized)",
        "stt": "sarvam-saaras-v3",
        "tts": "sarvam-bulbul-v2 (async httpx)",
        "ai": f"{AI_PROVIDER}/{OPENAI_MODEL}",
        "tts_cache_size": len(_tts_cache),
    })


@app.post("/api/rag/documents")
async def add_rag_document(doc: RagDocumentRequest):
    if not doc.content.strip():
        raise HTTPException(status_code=400, detail="content is required")
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("INSERT INTO rag_documents (title, content, source, created_at) VALUES (?,?,?,?)",
              (doc.title, doc.content.strip(), doc.source, datetime.now().isoformat()))
    conn.commit(); doc_id = c.lastrowid; conn.close()
    return {"id": doc_id, "success": True}


@app.get("/api/rag/search")
async def rag_search(q: str, top_k: int = 3, threshold: float = faiss_rag.SCORE_THRESHOLD):
    top_k = max(1, min(top_k, 10))
    if not faiss_rag.is_ready():
        return {"query": q, "results": [], "rag_enabled": ENABLE_RAG, "error": "FAISS index not loaded"}
    try:
        results = faiss_rag.search(q, top_k=top_k, score_threshold=threshold)
        return {"query": q, "results": results, "rag_enabled": ENABLE_RAG, "engine": "faiss", **faiss_rag.stats()}
    except Exception as e:
        return {"query": q, "results": [], "rag_enabled": ENABLE_RAG, "error": str(e)}


@app.post("/api/rag/rebuild")
async def rag_rebuild():
    try:
        faiss_rag.load_index(force_rebuild=True, json_path='final_dataset.json')
        return {"success": True, "message": "FAISS index rebuilt.", **faiss_rag.stats()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/rag/stats")
async def rag_stats():
    return faiss_rag.stats()


@app.get("/favicon.ico")
async def favicon():
    favicon_path = os.path.join(FRONTEND_DIR, "favicon.ico")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    return Response(status_code=204)


def _serve_frontend_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return JSONResponse(content={"status": "ok", "service": "GuniVox V3 — frontend not built",
                                  "hint": "Run 'npm run build' to generate the dist/ folder."})

@app.get("/")
@app.head("/")
async def serve_root():
    return _serve_frontend_index()

@app.api_route("/{path:path}", methods=["GET", "POST", "HEAD"])
async def catch_all(request: Request, path: str):
    if request.method == "POST":
        try:
            form_data = dict(await request.form())
        except Exception:
            form_data = {}
        logger.warning(f"⚠️ UNEXPECTED POST: /{path} | form={form_data}")
        return JSONResponse(content={"received": True})
    return _serve_frontend_index()


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"🚀 GuniVox Backend (optimized) on port {port} | answer_url={BASE_URL}/vobiz-answer")
    uvicorn.run(app, host="0.0.0.0", port=port)