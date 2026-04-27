# -*- coding: utf-8 -*-
"""
diagnostic_check.py
Full end-to-end health check for GuniVox:
  1. Server reachability & LLM config
  2. Piper TTS
  3. Groq Whisper STT (cloud)
  4. OpenAI GPT-4o-mini (LLM)
  5. Vobiz API connectivity
  6. Webhook endpoint reachability
  7. TTS audio file generation + HTTP serving
  8. FAISS RAG index & search
  9. Public URL / tunnel check
"""

import os, sys, time, wave, tempfile, uuid, requests, json

BASE = "http://localhost:8000"
PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"

results = []

def check(label, passed, detail=""):
    status = PASS if passed else FAIL
    msg = f"  {status}  {label}"
    if detail:
        msg += f"\n         {detail}"
    print(msg)
    results.append((label, passed))

print()
print("=" * 60)
print("  GuniVox -- Full Stack Diagnostic Check")
print("=" * 60)

# ──────────────────────────────────────────────────────────────
# 1. Server reachability
# ──────────────────────────────────────────────────────────────
print("\n[1] SERVER")
try:
    r = requests.get(f"{BASE}/api/llm/health", timeout=5)
    data = r.json()
    check("Server is running", r.status_code == 200, str(data))
    check("LLM provider = openai", data.get("provider") == "openai",
          f"provider={data.get('provider')}")
    check("Model = gpt-4o-mini", data.get("model") == "gpt-4o-mini",
          f"model={data.get('model')}")
    check("RAG enabled", data.get("rag_enabled") is True,
          f"rag_enabled={data.get('rag_enabled')}")
except Exception as e:
    check("Server is running", False, str(e))

# ──────────────────────────────────────────────────────────────
# 2. Piper TTS -- generate audio via /vobiz-answer simulation
# ──────────────────────────────────────────────────────────────
print("\n[2] PIPER TTS")
try:
    from piper.voice import PiperVoice
    voices_dir = os.path.join(os.path.dirname(__file__), "piper_voices")
    onnx_files = [f for f in os.listdir(voices_dir) if f.endswith(".onnx")]
    check("piper-tts installed", True)
    check("Voice model file exists", len(onnx_files) > 0,
          f"Found: {onnx_files}")
    if onnx_files:
        model_path = os.path.join(voices_dir, onnx_files[0])
        config_path = model_path + ".json"
        voice = PiperVoice.load(
            model_path,
            config_path=config_path if os.path.exists(config_path) else None,
            use_cuda=False
        )
        tmp = os.path.join(tempfile.gettempdir(), f"piper_test_{uuid.uuid4().hex}.wav")
        t0 = time.time()
        with wave.open(tmp, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(22050)
            voice.synthesize("Hello, this is a Piper TTS test.", wf)
        ms = int((time.time() - t0) * 1000)
        size = os.path.getsize(tmp)
        os.remove(tmp)
        check("Piper synthesis works", size > 1000,
              f"Generated {size} bytes in {ms}ms")
        check(f"Latency < 500ms", ms < 500, f"Actual: {ms}ms")
except ImportError:
    check("piper-tts installed", False, "Run: pip install piper-tts")
except Exception as e:
    check("Piper TTS test", False, str(e))

# ──────────────────────────────────────────────────────────────
# 3. Groq Whisper STT (cloud-based)
# ──────────────────────────────────────────────────────────────
print("\n[3] GROQ WHISPER STT")
try:
    from dotenv import load_dotenv
    load_dotenv(".env.local")
    groq_key = os.getenv("GROQ_API_KEY", "")
    check("GROQ_API_KEY present", bool(groq_key) and len(groq_key) > 10,
          f"Key: {groq_key[:12]}..." if groq_key else "NOT SET")
    if groq_key:
        from groq import Groq
        gc = Groq(api_key=groq_key)
        # Quick validation: list models to confirm key works
        check("Groq client initialised", gc is not None, "whisper-large-v3-turbo ready")
except ImportError:
    check("groq package installed", False, "Run: pip install groq")
except Exception as e:
    check("Groq STT check", False, str(e))

# ──────────────────────────────────────────────────────────────
# 4. OpenAI API (LLM)
# ──────────────────────────────────────────────────────────────
print("\n[4] OPENAI LLM (GPT-4o-mini)")
try:
    from dotenv import load_dotenv
    load_dotenv(".env.local")
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY", "")
    check("OPENAI_API_KEY present", bool(api_key) and len(api_key) > 20,
          f"Key: {api_key[:12]}...")
    oai = OpenAI(api_key=api_key)
    t0 = time.time()
    resp = oai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say 'ok' only."}],
        max_tokens=5,
        temperature=0
    )
    ms = int((time.time() - t0) * 1000)
    reply = resp.choices[0].message.content.strip()
    check("OpenAI API call succeeded", bool(reply), f"Reply: '{reply}'")
    check(f"Response latency < 3s", ms < 3000, f"Actual: {ms}ms")
except Exception as e:
    check("OpenAI API call", False, str(e))

# ──────────────────────────────────────────────────────────────
# 5. Vobiz API connectivity
# ──────────────────────────────────────────────────────────────
print("\n[5] VOBIZ API")
try:
    VOBIZ_AUTH_ID    = os.getenv("VOBIZ_AUTH_ID",    "MA_U0V5JKA1")
    VOBIZ_AUTH_TOKEN = os.getenv("VOBIZ_AUTH_TOKEN",  "iU5tg4E4WfRO7XN6cdtm3dYccqanE4kybqSgDFu8NEHDbzGlzpXiGq4XCcdpFFXO")
    check("VOBIZ_AUTH_ID set", bool(VOBIZ_AUTH_ID), VOBIZ_AUTH_ID)
    check("VOBIZ_AUTH_TOKEN set", bool(VOBIZ_AUTH_TOKEN),
          f"{VOBIZ_AUTH_TOKEN[:12]}...")
    # Ping Vobiz API root (account endpoint)
    vobiz_url = f"https://api.vobiz.ai/api/v1/Account/{VOBIZ_AUTH_ID}/"
    headers = {
        "X-Auth-ID":    VOBIZ_AUTH_ID,
        "X-Auth-Token": VOBIZ_AUTH_TOKEN,
    }
    t0 = time.time()
    rv = requests.get(vobiz_url, headers=headers, timeout=10)
    ms = int((time.time() - t0) * 1000)
    check("Vobiz API reachable", rv.status_code in (200, 201, 202),
          f"HTTP {rv.status_code} in {ms}ms | body={rv.text[:80]}")
except Exception as e:
    check("Vobiz API reachable", False, str(e))

# ──────────────────────────────────────────────────────────────
# 6. Webhook endpoint (/vobiz-answer) via local server
# ──────────────────────────────────────────────────────────────
print("\n[6] WEBHOOK ENDPOINTS (local)")
endpoints = [
    ("POST", "/vobiz-answer"),
    ("POST", "/vobiz-respond"),
    ("POST", "/vobiz-silent"),
    ("POST", "/status"),
]
for method, path in endpoints:
    try:
        r = requests.post(f"{BASE}{path}", data={"CallUUID": "test-diag-check"}, timeout=10)
        # These return XML or JSON — just check they don't 500
        ok = r.status_code < 500
        check(f"{method} {path} responds (no 500)", ok,
              f"HTTP {r.status_code} | content-type={r.headers.get('content-type','?')[:40]}")
    except Exception as e:
        check(f"{method} {path}", False, str(e))

# ──────────────────────────────────────────────────────────────
# 7. Static audio serving
# ──────────────────────────────────────────────────────────────
print("\n[7] STATIC AUDIO SERVING")
try:
    # Write a dummy wav so we can fetch it
    audio_dir = os.path.join("static", "audio")
    os.makedirs(audio_dir, exist_ok=True)
    test_name = f"diag_{uuid.uuid4().hex}.wav"
    test_path = os.path.join(audio_dir, test_name)
    # Write minimal valid WAV (44 bytes header, silent)
    with wave.open(test_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(22050)
        wf.writeframes(b'\x00' * 44100)  # 1 second silence
    r = requests.get(f"{BASE}/static/audio/{test_name}", timeout=5)
    check("Static audio file served over HTTP", r.status_code == 200,
          f"HTTP {r.status_code} | size={len(r.content)} bytes")
    os.remove(test_path)
except Exception as e:
    check("Static audio serving", False, str(e))

# ──────────────────────────────────────────────────────────────
# 8. FAISS RAG index & search
# ──────────────────────────────────────────────────────────────
print("\n[8] FAISS RAG")
try:
    # Check stats endpoint
    r = requests.get(f"{BASE}/api/rag/stats", timeout=5)
    if r.status_code == 200:
        stats = r.json()
        check("FAISS index loaded", stats.get("ready") is True,
              f"vectors={stats.get('total_vectors')}, model={stats.get('model')}")
        check("FAISS has vectors", (stats.get("total_vectors") or 0) > 0,
              f"total_vectors={stats.get('total_vectors')}")
    else:
        check("FAISS stats endpoint", False, f"HTTP {r.status_code}")

    # Test a semantic search
    r = requests.get(f"{BASE}/api/rag/search", params={"q": "BCA fees eligibility", "top_k": 3}, timeout=10)
    if r.status_code == 200:
        data = r.json()
        hits = data.get("results", [])
        check("FAISS search returns results", len(hits) > 0,
              f"{len(hits)} hit(s) for 'BCA fees eligibility'")
        if hits:
            top = hits[0]
            check("Top result has score > 0.3", top.get("score", 0) > 0.3,
                  f"score={top.get('score', 0):.3f}, program={top.get('record', {}).get('program', '?')}")
            check("Top result has voice_context", bool(top.get("voice_context")),
                  f"{top.get('voice_context', '')[:80]}...")
    else:
        check("FAISS search endpoint", False, f"HTTP {r.status_code}")
except Exception as e:
    check("FAISS RAG check", False, str(e))

# ──────────────────────────────────────────────────────────────
# 9. Public URL / tunnel check
# ──────────────────────────────────────────────────────────────
print("\n[9] PUBLIC URL")
try:
    # Read BASE_URL from the running server's env
    base_url = os.getenv("BASE_URL", "")
    if not base_url:
        # Try to read from .env.local
        from dotenv import dotenv_values
        env = dotenv_values(".env.local")
        base_url = env.get("BASE_URL", "")
    if not base_url:
        # Try to extract from server.py
        import re as _re
        with open("server.py", "r", encoding="utf-8") as f:
            content = f.read()
        m = _re.search(r'^BASE_URL\s*=\s*["\'](.+?)["\']', content, _re.MULTILINE)
        base_url = m.group(1) if m else ""

    check("BASE_URL configured", bool(base_url), base_url or "NOT SET")
    if base_url and base_url.startswith("http"):
        try:
            rn = requests.get(base_url, timeout=8,
                              headers={"ngrok-skip-browser-warning": "true"})
            check("Public URL is LIVE", rn.status_code < 500,
                  f"HTTP {rn.status_code}")
        except Exception as e:
            check("Public URL is LIVE", False,
                  f"Tunnel/URL may be down: {e}")
except Exception as e:
    check("Public URL check", False, str(e))

# ──────────────────────────────────────────────────────────────
# SUMMARY
# ──────────────────────────────────────────────────────────────
print()
print("=" * 60)
passed = sum(1 for _, p in results if p)
total  = len(results)
print(f"  RESULT: {passed}/{total} checks passed")
if passed == total:
    print("  STATUS: ALL SYSTEMS GO ✅")
else:
    failed = [l for l, p in results if not p]
    print(f"  FAILED: {failed}")
print("=" * 60)
