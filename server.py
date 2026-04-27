import os
import logging
import json
import re
import sqlite3
import wave
import struct
from datetime import datetime
from typing import Dict, List, Optional
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI
from groq import Groq
import uuid
import threading
from dotenv import load_dotenv
from openpyxl import Workbook
from xml.sax.saxutils import escape

from prompt_config import SYSTEM_PROMPT
import faiss_rag

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv(".env.local")

# --- Groq Whisper STT Initialization ---
# Uses Groq's ultra-fast LPU hardware to run Whisper Large-v3 Turbo
# Supports 100+ languages including English, Hindi, Gujarati
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
groq_client = None

def init_groq_stt():
    global groq_client
    if not GROQ_API_KEY:
        logger.warning("⚠️  GROQ_API_KEY not set — STT will not work!")
        return
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
        logger.info("✅ Groq Whisper STT ready (whisper-large-v3-turbo, cloud).")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Groq client: {e}")

init_groq_stt()

# --- Piper TTS Initialization ---
# Piper is a fast local ONNX-based TTS engine (~80-200ms synthesis)
# Voice model files are stored in piper_voices/ directory.
# Run download_piper_voice.py once to download the voice model.
piper_voice = None
PIPER_VOICES_DIR = os.path.join(os.path.dirname(__file__), "piper_voices")

def load_piper_tts():
    global piper_voice
    try:
        from piper.voice import PiperVoice
        # Find any .onnx model file in the voices directory
        onnx_files = [
            f for f in os.listdir(PIPER_VOICES_DIR)
            if f.endswith(".onnx")
        ] if os.path.isdir(PIPER_VOICES_DIR) else []

        if not onnx_files:
            logger.warning(
                "⚠️  No Piper voice model found in piper_voices/. "
                "Run: python download_piper_voice.py"
            )
            return

        model_path = os.path.join(PIPER_VOICES_DIR, onnx_files[0])
        config_path = model_path + ".json"
        if not os.path.exists(config_path):
            # Try without .json extension — piper auto-discovers it
            config_path = None

        logger.info(f"⏳ Loading Piper TTS voice: {onnx_files[0]} ...")
        piper_voice = PiperVoice.load(model_path, config_path=config_path, use_cuda=False)
        logger.info("✅ Piper TTS ready — ultra-low-latency synthesis enabled.")
    except ImportError:
        logger.error("❌ piper-tts package not installed. Run: pip install piper-tts")
    except Exception as e:
        logger.error(f"❌ Failed to load Piper TTS: {e}")

threading.Thread(target=load_piper_tts, daemon=True).start()

# ─────────────────────────────────────────
# LLM PROVIDER — Locked to OpenAI GPT-4o-mini for lowest latency
# Gemini is removed. Ollama remains available as an opt-in fallback.
# ─────────────────────────────────────────
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai").strip().lower()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "jatas-qwen-rag:latest")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "45"))
ENABLE_RAG = os.getenv("ENABLE_RAG", "true").strip().lower() in {"1", "true", "yes", "on"}
RAG_TOP_K = max(1, int(os.getenv("RAG_TOP_K", "3")))

# Force OpenAI if an unsupported/Gemini provider is set
if AI_PROVIDER not in {"openai", "ollama"}:
    logger.warning(f"AI_PROVIDER='{AI_PROVIDER}' is not supported. Defaulting to 'openai'.")
    AI_PROVIDER = "openai"

client: Optional[OpenAI] = None
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if AI_PROVIDER == "openai":
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    logger.info(f"✅ AI provider: OpenAI | Model: {OPENAI_MODEL}")
elif AI_PROVIDER == "ollama":
    logger.info(f"✅ AI provider: Ollama | Model: {OLLAMA_MODEL} | URL: {OLLAMA_BASE_URL}")

VOBIZ_AUTH_ID    = os.getenv("VOBIZ_AUTH_ID",    'MA_U0V5JKA1')
VOBIZ_AUTH_TOKEN = os.getenv("VOBIZ_AUTH_TOKEN",  'iU5tg4E4WfRO7XN6cdtm3dYccqanE4kybqSgDFu8NEHDbzGlzpXiGq4XCcdpFFXO')
VOBIZ_FROM_NUMBER = os.getenv("VOBIZ_FROM_NUMBER", '+912271263960')
# Public base URL — set via env var on Render (e.g. https://gunivox.onrender.com)
# Falls back to ngrok URL for local development
BASE_URL = os.getenv("BASE_URL", "https://disliking-hulk-bauble.ngrok-free.dev").rstrip("/")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for TTS audio
os.makedirs("static/audio", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount built React frontend assets (JS/CSS chunks)
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "dist")
if os.path.isdir(os.path.join(FRONTEND_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="frontend_assets")

# ─────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────
DB_FILE = "gunivox.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_sid TEXT UNIQUE,
            phone_number TEXT,
            status TEXT,
            started_at TEXT,
            end_reason TEXT,
            user_name TEXT,
            interest TEXT,
            lead_status TEXT,
            follow_up TEXT,
            transcript TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            fees TEXT,
            brochure_url TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS rag_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT NOT NULL,
            source TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()
    populate_default_courses()

def populate_default_courses():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM courses")
    if c.fetchone()[0] == 0:
        defaults = [
            ("BCA",    "Bachelor of Computer Applications. 10+2 English required.", "70,000/yr",              None),
            ("MCA",    "Master of Computer Applications. Needs BCA/BE/BSc.",        "1,40,000/yr",            None),
            ("BSc IT", "Bachelor of Science in IT (Data Science/Cyber Security).",  "75,000 - 85,000/yr",     None),
            ("MSc IT", "Master of Science in IT.",                                  "75,000 - 1,00,000/yr",   None),
        ]
        c.executemany("INSERT INTO courses (name, description, fees, brochure_url) VALUES (?,?,?,?)", defaults)
        conn.commit()
        print("✅ Default courses populated.")
    conn.close()

init_db()

# ─────────────────────────────────────────
# FAISS RAG INITIALIZATION
# ─────────────────────────────────────────
def init_faiss_rag():
    """Load (or build) the FAISS vector index from final_dataset.json on startup."""
    try:
        faiss_rag.load_index(json_path='final_dataset.json')
        logger.info(f"✅ FAISS RAG ready — {faiss_rag._index.ntotal} vectors loaded.")
    except Exception as e:
        logger.error(f"❌ FAISS RAG init failed: {e}")

# Load FAISS in a background thread to avoid blocking server startup
threading.Thread(target=init_faiss_rag, daemon=True).start()

# In-memory session store: call_sid → message list
sessions: Dict[str, List[Dict[str, str]]] = {}

# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────
def save_call_log(call_sid: str, data: dict):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id FROM calls WHERE call_sid = ?", (call_sid,))
    exists = c.fetchone()
    if not exists:
        c.execute(
            "INSERT INTO calls (call_sid, phone_number, status, started_at) VALUES (?,?,?,?)",
            (call_sid, data.get('phone_number'), 'initiated', datetime.now().isoformat())
        )
    else:
        allowed = ['status','end_reason','user_name','interest','lead_status','follow_up','transcript']
        fields, values = [], []
        for k, v in data.items():
            if k in allowed:
                fields.append(f"{k} = ?")
                values.append(v)
        if fields:
            values.append(call_sid)
            c.execute(f"UPDATE calls SET {', '.join(fields)} WHERE call_sid = ?", values)
    conn.commit()
    conn.close()

def export_db_to_excel(start_date: Optional[str] = None, end_date: Optional[str] = None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    query = "SELECT * FROM calls"
    params = []
    if start_date and end_date:
        query += " WHERE started_at BETWEEN ? AND ?"
        params.extend([f"{start_date}T00:00:00", f"{end_date}T23:59:59"])
    query += " ORDER BY id DESC"
    c.execute(query, params)
    rows = c.fetchall()
    columns = [d[0] for d in c.description]
    conn.close()
    wb = Workbook()
    ws = wb.active
    ws.title = "Call Logs"
    ws.append(columns)
    for row in rows:
        ws.append(row)
    filename = "leads.xlsx"
    wb.save(filename)
    return filename

def get_system_prompt_with_courses():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT name, description, fees FROM courses")
        rows = c.fetchall()
        conn.close()
        course_text = "\n".join([f"- **{r[0]}:** {r[2]}. {r[1]}" for r in rows])
        if not course_text:
            course_text = "- No specific course data available."
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


def build_rag_context(query: str) -> str:
    """
    Use FAISS vector search to retrieve semantically relevant programme info.
    Returns a compact, phone-call-friendly context string injected into the LLM.
    """
    if not ENABLE_RAG:
        return ""

    if not faiss_rag.is_ready():
        logger.warning("FAISS index not ready — skipping RAG retrieval.")
        return ""

    try:
        results = faiss_rag.search(query, top_k=RAG_TOP_K)
        if not results:
            logger.info(f"RAG: no relevant results for query='{query[:60]}'")
            return ""

        parts = []
        for hit in results:
            score = hit['score']
            ctx   = hit.get('voice_context') or hit['text']
            parts.append(f"[score={score:.2f}]\n{ctx}")

        context_str = "\n\n".join(parts)
        logger.info(f"RAG: {len(results)} hit(s) for query='{query[:60]}'")
        return context_str
    except Exception as e:
        logger.error(f"FAISS search error: {e}")
        return ""


def call_ollama_chat(messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 250) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json=payload,
        timeout=OLLAMA_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    body = response.json()
    return (body.get("message") or {}).get("content", "").strip()


def get_ai_response(call_sid: str, user_input: str) -> Dict[str, str]:
    if call_sid not in sessions:
        sessions[call_sid] = [{"role": "system", "content": get_system_prompt_with_courses()}]

    sessions[call_sid].append({"role": "user", "content": user_input})

    try:
        request_messages = list(sessions[call_sid])
        rag_context = build_rag_context(user_input)
        if rag_context:
            request_messages.insert(
                1,
                {
                    "role": "system",
                    "content": (
                        "Use this retrieved context as highest-priority factual grounding. "
                        "If context conflicts with older memory, prefer retrieved context. "
                        "If missing, continue normally.\n\n"
                        f"RETRIEVED_CONTEXT:\n{rag_context}"
                    ),
                },
            )

        if AI_PROVIDER == "ollama":
            raw_text = call_ollama_chat(request_messages, temperature=0.7, max_tokens=120)
        else:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=request_messages,
                temperature=0.7,
                max_tokens=120,  # Reduced for faster voice responses
            )
            raw_text = response.choices[0].message.content.strip()

        sessions[call_sid].append({"role": "assistant", "content": raw_text})

        ai_data = {"lang": "en-IN", "text": raw_text}

        lang_match = re.search(r"LANG:\s*([a-z\-]+)", raw_text, re.IGNORECASE)
        text_match = re.search(r"TEXT:\s*(.*?)(?=\s*\||\s*NAME:|\s*INTEREST:|\s*STATUS:|$)", raw_text, re.DOTALL | re.IGNORECASE)

        if lang_match:
            ai_data["lang"] = lang_match.group(1).strip()
        if text_match:
            ai_data["text"] = text_match.group(1).strip()
        else:
            cleaned = re.sub(r"(LANG|STATUS|INTEREST|NAME|FOLLOW_UP):\s*.*?(?=\||$)", "", raw_text, flags=re.IGNORECASE)
            ai_data["text"] = cleaned.strip().strip('|').strip()

        metadata = {}
        patterns = [
            ("user_name",   r"NAME:\s*(.*?)(?=\s*\||STATUS:|INTEREST:|LANG:|TEXT:|$)"),
            ("interest",    r"INTEREST:\s*(.*?)(?=\s*\||STATUS:|NAME:|LANG:|TEXT:|$)"),
            ("lead_status", r"STATUS:\s*(.*?)(?=\s*\||NAME:|INTEREST:|LANG:|TEXT:|$)"),
            ("follow_up",   r"FOLLOW_UP:\s*(.*?)(?=\s*\||$)"),
        ]
        for key, pattern in patterns:
            m = re.search(pattern, raw_text, re.IGNORECASE | re.DOTALL)
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
        return {"lang": "en-IN", "text": "I'm sorry, I didn't quite catch that. Could you please repeat?"}

# ─────────────────────────────────────────
# XML BUILDER HELPERS
# ─────────────────────────────────────────
def get_base_url(request: Request) -> str:
    """Safely extract the public base URL from the incoming request headers or env var."""
    env_base = os.getenv("BASE_URL")
    if env_base:
        return env_base.rstrip('/')
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    scheme = request.headers.get("x-forwarded-proto", "https")
    return f"{scheme}://{host}"

def generate_tts_audio(text: str, base_url: str, lang: str = "en-IN") -> str:
    """
    Generates TTS using Piper (ultra-fast local ONNX, ~80-200ms) for English.
    Falls back to gTTS for non-English languages (hi, gu, etc.).
    Returns the public URL to the audio file.
    """
    os.makedirs(os.path.join("static", "audio"), exist_ok=True)
    is_english = lang.lower().startswith("en")

    # ── Piper TTS (English, ultra-fast) ───────────────────────────────────────
    if piper_voice is not None and is_english:
        try:
            filename = f"tts_{uuid.uuid4().hex}.wav"
            filepath = os.path.join("static", "audio", filename)
            logger.info(f"🔊 Piper TTS synthesizing ({lang}): '{text[:60]}'")
            with wave.open(filepath, "wb") as wav_file:
                piper_voice.synthesize_wav(text, wav_file)
            logger.info(f"✅ Piper TTS done → {filename}")
            return f"{base_url}/static/audio/{filename}"
        except Exception as e:
            logger.error(f"Piper TTS failed: {e} — falling back to gTTS")

    # ── gTTS fallback (non-English OR Piper unavailable) ──────────────────────
    try:
        from gtts import gTTS
        lang_code = lang.split("-")[0]   # en-IN → en, hi-IN → hi
        filename = f"tts_{uuid.uuid4().hex}.mp3"
        filepath = os.path.join("static", "audio", filename)
        logger.info(f"🔊 gTTS synthesizing ({lang_code}): '{text[:60]}'")
        tts = gTTS(text=text, lang=lang_code)
        tts.save(filepath)
        logger.info(f"✅ gTTS done → {filename}")
        return f"{base_url}/static/audio/{filename}"
    except Exception as e:
        logger.error(f"gTTS also failed: {e}")
        # Return empty string — caller will still send XML but Play tag will be empty
        return ""

def get_ngrok_headers():
    """Return headers required to bypass ngrok browser warning."""
    return {"ngrok-skip-browser-warning": "true"}

def gather_xml(request: Request, speak_text: str, action_path: str, lang: str = "en-IN") -> str:
    """
    Returns a valid Vobiz <Record> block with <Play> nested inside for local Whisper/TTS.
    We play the AI's audio, then record the user.
    """
    base_url = get_base_url(request)
    audio_url = generate_tts_audio(speak_text, base_url, lang)
    
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Record action="{base_url}/{action_path}" 
            method="POST" 
            maxLength="15" 
            timeout="3" 
            playBeep="false" />
    <Redirect method="POST">{base_url}/vobiz-silent</Redirect>
</Response>"""

def hangup_xml(request: Request, speak_text: str, lang: str = "en-IN") -> str:
    base_url = get_base_url(request)
    audio_url = generate_tts_audio(speak_text, base_url, lang)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
    <Hangup/>
</Response>"""

# ─────────────────────────────────────────
# VOBIZ WEBHOOK ENDPOINTS
# ─────────────────────────────────────────

@app.api_route("/vobiz-answer", methods=["GET", "POST"])
async def vobiz_answer(request: Request):
    """Called by Vobiz the moment the callee picks up."""
    logger.info("="*50)
    logger.info("📞 CALL PICKUP EVENT DETECTED (/vobiz-answer)")
    try:
        form_data = dict(await request.form())
    except Exception as e:
        logger.error(f"Failed to parse form data on answer: {e}")
        form_data = {}

    call_sid = (
        form_data.get("CallUUID")
        or form_data.get("request_uuid")
        or form_data.get("CallSid")
        or "unknown"
    )
    logger.info(f"   Call SID: {call_sid}")
    logger.info(f"   Full Payload: {form_data}")
    logger.info("="*50)

    xml = gather_xml(
        request,
        "Hello! This is GuniVox calling from Ganpat University. Are you available for a quick talk?",
        action_path="vobiz-respond"
    )
    logger.info(f"   Generated XML response for call {call_sid}:\n{xml}")
    return Response(content=xml, media_type="text/xml", headers=get_ngrok_headers())

@app.api_route("/vobiz-respond", methods=["GET", "POST"])
async def vobiz_respond(request: Request):
    """Called by Vobiz after Gather captures speech."""
    logger.info("="*50)
    logger.info("🗣️ SPEECH GATHERED EVENT DETECTED (/vobiz-respond)")
    try:
        form_data = dict(await request.form())
    except Exception as e:
        logger.error(f"Failed to parse form data on respond: {e}")
        form_data = {}
    if not form_data:
        try:
            form_data = await request.json()
        except Exception:
            form_data = {}

    # ✅ Vobiz sends transcribed speech in the 'Speech' field (if Gather is used)
    # But since we use Record, it will send 'RecordingUrl'
    recording_url = form_data.get("RecordUrl") or form_data.get("RecordFile") or form_data.get("RecordingUrl") or form_data.get("recording_url")
    user_speech = (
        form_data.get("Speech")
        or form_data.get("speech")
        or form_data.get("SpeechResult")
        or form_data.get("Digits")
        or ""
    ).strip()

    if recording_url and groq_client:
        # Download the audio file (Vobiz media API requires auth headers)
        try:
            import time as _time
            logger.info(f"   Downloading recording from {recording_url}...")
            dl_headers = {
                "X-Auth-ID": VOBIZ_AUTH_ID,
                "X-Auth-Token": VOBIZ_AUTH_TOKEN,
            }
            audio_response = requests.get(recording_url, headers=dl_headers, timeout=10)
            audio_data = audio_response.content
            logger.info(f"   Downloaded {len(audio_data)} bytes (status={audio_response.status_code})")
            
            if audio_response.status_code != 200 or len(audio_data) < 500:
                logger.error(f"   Recording download failed or too small — status={audio_response.status_code}, body={audio_data[:200]}")
                user_speech = ""
            else:
                # Save to temp file for Groq API
                ext = ".mp3" if recording_url.lower().endswith(".mp3") else ".wav"
                temp_filename = f"temp_{uuid.uuid4().hex}{ext}"
                with open(temp_filename, "wb") as f:
                    f.write(audio_data)
                    
                # Run Groq Whisper STT (Large-v3 Turbo on Groq LPU)
                _stt_start = _time.time()
                logger.info("   Running Groq Whisper STT (large-v3-turbo)...")
                with open(temp_filename, "rb") as audio_file:
                    transcription = groq_client.audio.transcriptions.create(
                        file=(temp_filename, audio_file.read()),
                        model="whisper-large-v3-turbo",
                    )
                user_speech = transcription.text.strip()
                _stt_elapsed = (_time.time() - _stt_start) * 1000
                logger.info(f"   Groq STT result ({_stt_elapsed:.0f}ms): '{user_speech}'")
                
                # Cleanup temp file
                os.remove(temp_filename)
        except Exception as e:
            logger.error(f"Failed to process audio with Groq STT: {e}")
            user_speech = ""
    elif recording_url and not groq_client:
        logger.warning("Groq STT client not initialized! Check GROQ_API_KEY.")
        user_speech = ""

    call_sid = (
        form_data.get("CallUUID")
        or form_data.get("request_uuid")
        or form_data.get("CallSid")
        or "unknown_session"
    )

    logger.info(f"   Call SID: {call_sid}")
    logger.info(f"   Transcribed Speech: '{user_speech}'")
    logger.info(f"   Full Payload: {form_data}")
    logger.info("="*50)

    if not user_speech:
        # No speech detected — ask again
        xml = gather_xml(
            request,
            "I didn't quite catch that. Could you please repeat?",
            action_path="vobiz-respond"
        )
        return Response(content=xml, media_type="text/xml", headers=get_ngrok_headers())

    # Get AI response
    ai_data = get_ai_response(call_sid, user_speech)
    lang     = ai_data.get("lang", "en-IN")
    text     = ai_data.get("text", "I'm sorry, could you repeat that?")
    should_hangup = "[HANGUP]" in ai_data.get("text", "") or "HANGUP" in ai_data.get("text", "")
    text = text.replace("[HANGUP]", "").strip()

    if should_hangup:
        xml = hangup_xml(request, text, lang=lang)
    else:
        xml = gather_xml(request, text, action_path="vobiz-respond", lang=lang)

    return Response(content=xml, media_type="text/xml", headers=get_ngrok_headers())


@app.api_route("/vobiz-silent", methods=["GET", "POST"])
async def vobiz_silent(request: Request):
    """
    Fallback: Gather timed out with no speech at all.
    Ask once more; if still silent → hangup.
    """
    try:
        form_data = dict(await request.form())
    except Exception:
        form_data = {}

    logger.info(f"🔇 /vobiz-silent | data={form_data}")

    # Count silence hits per call to avoid infinite loop
    call_sid = form_data.get("CallUUID") or form_data.get("CallSid") or "unknown"
    silence_key = f"__silence__{call_sid}"
    count = sessions.get(silence_key, 0) + 1
    sessions[silence_key] = count

    if count >= 2:
        # Two consecutive silences → hang up politely
        sessions.pop(silence_key, None)
        xml = hangup_xml(request, "It seems you're not available right now. We'll call you later. Goodbye!")
    else:
        xml = gather_xml(
            request,
            "Are you still there? Please say something and I'll be happy to help.",
            action_path="vobiz-respond"
        )

    return Response(content=xml, media_type="text/xml", headers=get_ngrok_headers())


@app.api_route("/status", methods=["GET", "POST"])
async def call_status(request: Request):
    """Hangup/status webhook from Vobiz."""
    try:
        form_data = dict(await request.form())
    except Exception:
        form_data = {}
    if not form_data:
        try:
            form_data = await request.json()
        except Exception:
            form_data = {}

    logger.info(f"📴 /status | data={form_data}")

    call_sid = form_data.get("CallUUID") or form_data.get("request_uuid") or form_data.get("CallSid")
    status   = form_data.get("CallStatus") or form_data.get("status") or "unknown"
    end_reason = form_data.get("HangupCauseName") or form_data.get("hangup_cause_name") or form_data.get("Reason")

    if call_sid:
        update = {"status": status}
        if end_reason:
            update["end_reason"] = end_reason
        save_call_log(call_sid, update)

        terminal = {"completed","busy","no-answer","canceled","failed","hangup"}
        if status.lower() in terminal:
            sessions.pop(call_sid, None)
            sessions.pop(f"__silence__{call_sid}", None)

    return JSONResponse(content={"received": True})


# ─────────────────────────────────────────
# API ENDPOINTS (unchanged from original)
# ─────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class CallRequest(BaseModel):
    phone_number: str

class Course(BaseModel):
    name: str
    description: str
    fees: str
    brochure_url: Optional[str] = None


class RagDocumentRequest(BaseModel):
    title: Optional[str] = None
    content: str
    source: Optional[str] = "manual"

@app.post("/api/login")
async def login(creds: LoginRequest):
    if creds.username == "Admin" and creds.password == "Guni@2026":
        return {"token": "fake-jwt-token-for-demo", "user": "Admin"}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/api/call")
async def trigger_call(req: CallRequest, request: Request):
    # Derive the public base URL dynamically from the incoming request so
    # Vobiz callback URLs always point to the correct live server (Render, ngrok, etc.)
    dynamic_base_url = get_base_url(request)
    url = f"https://api.vobiz.ai/api/v1/Account/{VOBIZ_AUTH_ID}/Call/"
    headers = {
        "X-Auth-ID": VOBIZ_AUTH_ID,
        "X-Auth-Token": VOBIZ_AUTH_TOKEN,
        "Content-Type": "application/json"
    }
    payload = {
        "from": VOBIZ_FROM_NUMBER,
        "to": req.phone_number,
        "answer_url": f"{dynamic_base_url}/vobiz-answer",
        "answer_method": "POST",
        "hangup_url": f"{dynamic_base_url}/status",
        "hangup_method": "POST"
    }
    logger.info(f"📤 Initiating call to {req.phone_number} | answer_url={payload['answer_url']}")
    try:
        response = requests.post(url, headers=headers, json=payload)
        result = response.json()
        if not response.ok:
            raise HTTPException(status_code=response.status_code, detail=result.get("message", "Vobiz API error"))
        call_uuid = result.get("request_uuid") or f"unknown_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        save_call_log(call_uuid, {"phone_number": req.phone_number})
        return {"success": True, "call_sid": call_uuid, "status": "queued", "details": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Call failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/end_call/{call_sid}")
async def end_call(call_sid: str):
    try:
        url = f"https://api.vobiz.ai/api/v1/Account/{VOBIZ_AUTH_ID}/Call/{call_sid}/"
        headers = {"X-Auth-ID": VOBIZ_AUTH_ID, "X-Auth-Token": VOBIZ_AUTH_TOKEN}
        requests.delete(url, headers=headers)
        save_call_log(call_sid, {"status": "completed", "end_reason": "user_initiated"})
        return {"success": True, "status": "completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_stats(start_date: Optional[str] = None, end_date: Optional[str] = None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    date_params = []
    q_total    = "SELECT COUNT(*) FROM calls"
    q_positive = "SELECT COUNT(*) FROM calls WHERE lead_status='Positive'"
    if start_date and end_date:
        q_total    += " WHERE started_at BETWEEN ? AND ?"
        q_positive += " AND started_at BETWEEN ? AND ?"
        date_params = [f"{start_date}T00:00:00", f"{end_date}T23:59:59"]
    c.execute(q_total, date_params)
    total = c.fetchone()[0]
    c.execute(q_positive, date_params)
    positive = c.fetchone()[0]
    c.execute("SELECT * FROM calls ORDER BY id DESC LIMIT 5")
    columns = [d[0] for d in c.description]
    recent = [dict(zip(columns, row)) for row in c.fetchall()]
    conn.close()
    return {"total_calls": total, "positive_leads": positive, "recent_calls": recent}

@app.get("/api/calls")
async def get_calls(q: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    query = "SELECT * FROM calls"
    params, conditions = [], []
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
    calls = [dict(zip(columns, row)) for row in c.fetchall()]
    conn.close()
    return calls

@app.get("/api/courses")
async def get_courses():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM courses")
    columns = [d[0] for d in c.description]
    courses = [dict(zip(columns, row)) for row in c.fetchall()]
    conn.close()
    return courses


@app.get("/api/llm/health")
async def llm_health_check():
    faiss_status = faiss_rag.stats()

    if AI_PROVIDER == "ollama":
        try:
            tags = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
            tags.raise_for_status()
            models = [m.get("name") for m in tags.json().get("models", [])]
            return {
                "provider": AI_PROVIDER,
                "base_url": OLLAMA_BASE_URL,
                "configured_model": OLLAMA_MODEL,
                "available_models": models,
                "model_available": OLLAMA_MODEL in models,
                "faiss": faiss_status,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ollama check failed: {e}")

    return {
        "provider": AI_PROVIDER,
        "model": OPENAI_MODEL,
        "rag_enabled": ENABLE_RAG,
        "faiss": faiss_status,
        # legacy flat keys for diagnostic_check.py compatibility
        "faiss_ready": faiss_status["ready"],
        "faiss_vectors": faiss_status["total_vectors"],
        "embedding_model": faiss_status["model"],
    }


@app.post("/api/rag/documents")
async def add_rag_document(doc: RagDocumentRequest):
    if not doc.content.strip():
        raise HTTPException(status_code=400, detail="content is required")

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO rag_documents (title, content, source, created_at) VALUES (?,?,?,?)",
        (doc.title, doc.content.strip(), doc.source, datetime.now().isoformat()),
    )
    conn.commit()
    doc_id = c.lastrowid
    conn.close()
    return {"id": doc_id, "success": True}


@app.get("/api/rag/search")
async def rag_search(q: str, top_k: int = 3, threshold: float = faiss_rag.SCORE_THRESHOLD):
    """Search the FAISS vector index for semantically similar programme records."""
    top_k = max(1, min(top_k, 10))
    if not faiss_rag.is_ready():
        return {"query": q, "results": [], "rag_enabled": ENABLE_RAG, "error": "FAISS index not loaded"}
    try:
        results = faiss_rag.search(q, top_k=top_k, score_threshold=threshold)
        return {
            "query": q,
            "results": results,
            "rag_enabled": ENABLE_RAG,
            "engine": "faiss",
            **faiss_rag.stats(),
        }
    except Exception as e:
        logger.error(f"FAISS search API error: {e}")
        return {"query": q, "results": [], "rag_enabled": ENABLE_RAG, "error": str(e)}


@app.post("/api/rag/rebuild")
async def rag_rebuild():
    """Force-rebuild the FAISS index from the latest final_dataset.json."""
    try:
        faiss_rag.load_index(force_rebuild=True, json_path='final_dataset.json')
        return {
            "success": True,
            "message": "FAISS index rebuilt successfully.",
            **faiss_rag.stats(),
        }
    except Exception as e:
        logger.error(f"FAISS rebuild error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/rag/stats")
async def rag_stats():
    """Return FAISS index statistics."""
    return faiss_rag.stats()

@app.post("/api/courses")
async def add_course(course: Course):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO courses (name, description, fees, brochure_url) VALUES (?,?,?,?)",
              (course.name, course.description, course.fees, course.brochure_url))
    conn.commit()
    cid = c.lastrowid
    conn.close()
    return {**course.dict(), "id": cid}

@app.put("/api/courses/{course_id}")
async def update_course(course_id: int, course: Course):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE courses SET name=?,description=?,fees=?,brochure_url=? WHERE id=?",
              (course.name, course.description, course.fees, course.brochure_url, course_id))
    conn.commit()
    conn.close()
    return {"success": True}

@app.delete("/api/courses/{course_id}")
async def delete_course(course_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM courses WHERE id=?", (course_id,))
    conn.commit()
    conn.close()
    return {"success": True}

@app.delete("/api/calls/{call_id}")
async def delete_call_log(call_id: int):
    """Delete a single call log record by its integer primary key."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM calls WHERE id = ?", (call_id,))
    conn.commit()
    conn.close()
    return {"success": True, "deleted_id": call_id}


@app.post("/api/calls/{call_id}/reanalyze")
async def reanalyze_call(call_id: int):
    """
    Re-parse the stored transcript for a given call and refresh
    the lead metadata fields (user_name, interest, lead_status).
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT call_sid, transcript FROM calls WHERE id = ?", (call_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Call log not found")

    call_sid, transcript_json = row
    if not transcript_json:
        return {"success": False, "detail": "No transcript available to reanalyze"}

    try:
        messages = json.loads(transcript_json)
    except Exception:
        return {"success": False, "detail": "Could not parse transcript JSON"}

    # Re-extract metadata from the last assistant message in the transcript
    metadata = {}
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
            break  # only use the last assistant message

    if metadata:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        allowed = ["user_name", "interest", "lead_status"]
        fields, values = [], []
        for k, v in metadata.items():
            if k in allowed:
                fields.append(f"{k} = ?")
                values.append(v)
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
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT status, transcript FROM calls WHERE call_sid = ?", (call_sid,))
    row = c.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Call not found")
    status, transcript_json = row
    transcript = json.loads(transcript_json) if transcript_json else []
    if call_sid in sessions:
        transcript = [m for m in sessions[call_sid] if m['role'] != 'system']
    return {"call_sid": call_sid, "status": status, "transcript": transcript}

# ─────────────────────────────────────────
# HEALTH CHECK & UTILITY ROUTES
# ─────────────────────────────────────────
@app.get("/api/health")
async def api_health_check():
    """API health check endpoint."""
    return JSONResponse(content={
        "status": "ok",
        "service": "GuniVox V3",
        "stt": "groq-whisper-large-v3-turbo",
        "tts": "piper" if piper_voice else "gtts",
        "ai": f"{AI_PROVIDER}/{OPENAI_MODEL}"
    })

@app.get("/favicon.ico")
async def favicon():
    """Serve favicon from dist/ if it exists, otherwise 204."""
    favicon_path = os.path.join(FRONTEND_DIR, "favicon.ico")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    return Response(status_code=204)


def _serve_frontend_index():
    """Return the React app's index.html if the dist/ build exists."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    # Fallback JSON if frontend hasn't been built yet
    return JSONResponse(content={
        "status": "ok",
        "service": "GuniVox V3 — frontend not built",
        "hint": "Run 'npm run build' to generate the dist/ folder."
    })


@app.get("/")
@app.head("/")
async def serve_root():
    """Serve the React frontend at root. Also satisfies Render's health probe (returns 200)."""
    return _serve_frontend_index()


# Catch-all: serve frontend for browser routes, log unexpected webhook hits
@app.api_route("/{path:path}", methods=["GET", "POST", "HEAD"])
async def catch_all(request: Request, path: str):
    # POST requests to unknown paths are likely Vobiz webhook mis-hits
    if request.method == "POST":
        try:
            form_data = dict(await request.form())
        except Exception:
            form_data = {}
        logger.warning(f"⚠️ UNEXPECTED HIT: /{path} | method={request.method} | form={form_data}")
        return JSONResponse(content={"received": True})

    # GET/HEAD on non-API paths → serve the React SPA (client-side routing)
    return _serve_frontend_index()

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"🚀 GuniVox Backend running on port {port} | answer_url={BASE_URL}/vobiz-answer")
    uvicorn.run(app, host="0.0.0.0", port=port)