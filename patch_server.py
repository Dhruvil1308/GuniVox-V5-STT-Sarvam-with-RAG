#!/usr/bin/env python3
"""
Patches server.py to add warm transfer functionality.
Reads server.py, inserts the transfer code block, and writes back.
"""
import os

FILE = "/home/dhruvil/GuniVox V3/GuniVox V3/server.py"

with open(FILE, "r", encoding="utf-8") as f:
    content = f.read()

# ── 1. Add TRANSFER constants after VOBIZ_FROM_NUMBER line ────────────────
OLD_CONST = 'VOBIZ_FROM_NUMBER = os.getenv("VOBIZ_FROM_NUMBER", "")\nBASE_URL          = os.getenv("BASE_URL", "").rstrip("/")'
NEW_CONST = '''VOBIZ_FROM_NUMBER = os.getenv("VOBIZ_FROM_NUMBER", "")
TRANSFER_NUMBER   = os.getenv("TRANSFER_NUMBER", "")
CONNECTING_MUSIC  = os.getenv("CONNECTING_MUSIC", "goodvibes.mp3")
BASE_URL          = os.getenv("BASE_URL", "").rstrip("/")'''

if OLD_CONST in content:
    content = content.replace(OLD_CONST, NEW_CONST, 1)
    print("✅ Added TRANSFER_NUMBER and CONNECTING_MUSIC constants")
else:
    print("⚠️  Could not find VOBIZ_FROM_NUMBER constant block — check manually")

# ── 2. Insert warm transfer functions after handle_silence_logic ───────────
ANCHOR = '''# ─────────────────────────────────────────
# ⚡ OPT-6: Download recording — 1 retry × 150 ms (was 2 × 500 ms)
# ─────────────────────────────────────────'''

WARM_TRANSFER_CODE = '''
# ═══════════════════════════════════════════════════════════════════════════
# WARM TRANSFER — Music redirect loop + VoBiz Transfer API push
# ═══════════════════════════════════════════════════════════════════════════
#
# FULL FLOW:
#   1. Agent detects [TRANSFER] in LLM response → transfer_xml() called
#   2. User hears "connecting you" TTS, then immediately redirected to /hold-loop
#   3. /hold-loop plays hold music on loop (no dead air, no full-file blocking)
#   4. Background task dials counsellor after 3s (TTS is ~3s, so user is in loop by then)
#   5. Counsellor answers → /counsellor-answer:
#        a. Counsellor enters Conference room (VoBiz creates the room here)
#        b. VoBiz Transfer REST API pushes user: /hold-loop → /join-conference
#        c. User enters the same Conference room → MERGED ✅
#   6. Counsellor no-answer → /counsellor-hangup → rescues user with fallback
#
# WHY redirect loop instead of Conference Member Play API:
#   - VoBiz only creates a conference room WHEN a participant enters via XML.
#     Calling the Conference Member Play REST API before that returns 404.
#   - <Play> before <Conference> blocks sequentially (plays full 3+ min file first).
#   - Redirect loop: user loops through music XML; VoBiz Transfer API can interrupt
#     at ANY moment to push them into the conference. Zero dead air. ✅
# ═══════════════════════════════════════════════════════════════════════════

async def transfer_xml(request: Request, speak_text: str, call_sid: str, lang: str = "gu-IN") -> str:
    """
    Step 1 of warm transfer (user side):
      1. Plays "connecting you" TTS to the user
      2. Redirects user to /hold-loop (music plays in a loop here)
      3. Dials counsellor in background after 3s
    """
    BASE_URL = get_base_url(request)
    conf_room = f"gvx_{call_sid[-12:]}"
    sessions[f"__conf__{call_sid}"] = conf_room

    audio_url = await generate_tts_audio(speak_text, BASE_URL, lang)

    # Dial counsellor in background after 3s
    asyncio.create_task(_dial_counsellor_background(call_sid, BASE_URL))

    logger.info(f"📞 WARM TRANSFER | room={conf_room} | call_sid={call_sid}")

    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Play>{audio_url}</Play>"
        f'<Redirect method="POST">{BASE_URL}/hold-loop?call_sid={call_sid}</Redirect>'
        "</Response>"
    )


async def _dial_counsellor_background(call_sid: str, base_url: str):
    """
    Background task: waits 3s then dials counsellor.
    3s gives user time to finish TTS and enter /hold-loop first.
    """
    await asyncio.sleep(3.0)
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            _executor,
            lambda: _dial_counsellor_sync(call_sid, base_url)
        )
        logger.info(f"🤝 Counsellor dial initiated: {result.get('request_uuid', '?')}")
    except Exception as e:
        logger.error(f"❌ Counsellor dial failed for call_sid={call_sid}: {e}")
        asyncio.create_task(_rescue_user_from_hold_loop(call_sid, base_url))


def _dial_counsellor_sync(call_sid: str, base_url: str) -> dict:
    """Fires outbound VoBiz REST call to the counsellor number."""
    url = f"https://api.vobiz.ai/api/v1/Account/{VOBIZ_AUTH_ID}/Call/"
    headers = {
        "X-Auth-ID":    VOBIZ_AUTH_ID,
        "X-Auth-Token": VOBIZ_AUTH_TOKEN,
        "Content-Type": "application/json",
    }
    payload = {
        "from":          VOBIZ_FROM_NUMBER,
        "to":            TRANSFER_NUMBER,
        "answer_url":    f"{base_url}/counsellor-answer?call_sid={call_sid}",
        "answer_method": "POST",
        "hangup_url":    f"{base_url}/counsellor-hangup?call_sid={call_sid}",
        "hangup_method": "POST",
    }
    resp = http_session.post(url, headers=headers, json=payload, timeout=HTTP_TIMEOUT_SECONDS)
    result = resp.json()
    if not resp.ok:
        raise RuntimeError(f"VoBiz dial error {resp.status_code}: {result}")
    sessions[f"__counsellor__{call_sid}"] = result.get("request_uuid", "")
    return result


async def _push_user_to_conference(call_sid: str, base_url: str, delay: float = 1.5):
    """
    Uses VoBiz Call Transfer REST API to interrupt user's /hold-loop and
    redirect them to /join-conference where they get Conference XML.
    delay gives the counsellor time to enter the conference room first.
    """
    await asyncio.sleep(delay)
    join_url = f"{base_url}/join-conference?call_sid={call_sid}"
    api_url  = f"https://api.vobiz.ai/api/v1/Account/{VOBIZ_AUTH_ID}/Call/{call_sid}/"
    headers  = {
        "X-Auth-ID":    VOBIZ_AUTH_ID,
        "X-Auth-Token": VOBIZ_AUTH_TOKEN,
        "Content-Type": "application/json",
    }
    payload  = {"legs": "aleg", "aleg_url": join_url, "aleg_method": "POST"}

    def _do():
        r = http_session.post(api_url, headers=headers, json=payload, timeout=HTTP_TIMEOUT_SECONDS)
        logger.info(f"🔀 User pushed to conference | call_sid={call_sid} | {r.status_code}: {r.text[:200]}")

    await asyncio.get_running_loop().run_in_executor(_executor, _do)


async def _rescue_user_from_hold_loop(call_sid: str, base_url: str):
    """Rescue user from /hold-loop with a fallback message when counsellor can't be reached."""
    await asyncio.sleep(1.0)
    try:
        fallback_text = "\\u0aae\\u0abe\\u0aab \\u0a95\\u0ab0\\u0ab6\\u0acb, \\u0a85\\u0aae\\u0abe\\u0ab0\\u0ac0 \\u0a9f\\u0ac0\\u0aae \\u0a89\\u0aaa\\u0ab2\\u0acd\\u0aac\\u0acd\\u0aa7 \\u0aa8\\u0aa5\\u0ac0. \\u0a85\\u0aae\\u0ac7 \\u0a9f\\u0ac2\\u0a82\\u0a95 \\u0ab8\\u0aae\\u0aaf\\u0aae\\u0abe\\u0a82 \\u0a95\\u0ac9\\u0ab2 \\u0a95\\u0ab0\\u0ac0\\u0ab6\\u0ac1\\u0a82. \\u0aa7\\u0aa8\\u0acd\\u0aaf\\u0ab5\\u0abe\\u0aa6."
        audio_url    = await generate_tts_audio(fallback_text, base_url, lang="gu-IN")
        fallback_url = f"{base_url}/user-fallback?audio_url={requests.utils.quote(audio_url)}"
        api_url  = f"https://api.vobiz.ai/api/v1/Account/{VOBIZ_AUTH_ID}/Call/{call_sid}/"
        headers  = {
            "X-Auth-ID":    VOBIZ_AUTH_ID,
            "X-Auth-Token": VOBIZ_AUTH_TOKEN,
            "Content-Type": "application/json",
        }
        payload  = {"legs": "aleg", "aleg_url": fallback_url, "aleg_method": "POST"}

        def _do():
            r = http_session.post(api_url, headers=headers, json=payload, timeout=HTTP_TIMEOUT_SECONDS)
            logger.info(f"   Rescue (hold-loop) → {r.status_code}: {r.text[:200]}")

        await asyncio.get_running_loop().run_in_executor(_executor, _do)
    except Exception as e:
        logger.error(f"❌ _rescue_user_from_hold_loop failed: {e}")
    finally:
        sessions.pop(f"__conf__{call_sid}", None)
        sessions.pop(f"__counsellor__{call_sid}", None)


'''

if ANCHOR in content:
    content = content.replace(ANCHOR, WARM_TRANSFER_CODE + ANCHOR, 1)
    print("✅ Inserted warm transfer helper functions")
else:
    print("⚠️  Could not find anchor for warm transfer insertion")

# ── 3. Add [TRANSFER] detection in vobiz_respond ──────────────────────────
OLD_RESPOND = '''    should_hangup = "[HANGUP]" in text or "HANGUP" in ai_data.get("text", "")
    text          = text.replace("[HANGUP]", "").strip()

    # ── TTS (⚡ OPT-4 async + OPT-5 cache) ───────────────────────────────────
    if should_hangup:
        xml = await hangup_xml(request, text, lang=lang)
    else:
        xml = await gather_xml(request, text, action_path="vobiz-respond", lang=lang)

    return Response(content=xml, media_type="text/xml", headers=get_cloudflare_headers())'''

NEW_RESPOND = '''    should_hangup   = "[HANGUP]"   in text or "HANGUP"   in ai_data.get("text", "")
    should_transfer = "[TRANSFER]" in text or "TRANSFER" in ai_data.get("text", "")
    text = text.replace("[HANGUP]", "").replace("[TRANSFER]", "").strip()

    # ── TTS (⚡ OPT-4 async + OPT-5 cache) ───────────────────────────────────
    if should_transfer:
        xml = await transfer_xml(request, text, call_sid, lang=lang)
    elif should_hangup:
        xml = await hangup_xml(request, text, lang=lang)
    else:
        xml = await gather_xml(request, text, action_path="vobiz-respond", lang=lang)

    return Response(content=xml, media_type="text/xml", headers=get_cloudflare_headers())'''

if OLD_RESPOND in content:
    content = content.replace(OLD_RESPOND, NEW_RESPOND, 1)
    print("✅ Added [TRANSFER] detection in vobiz_respond")
else:
    print("⚠️  Could not find vobiz_respond response block — check manually")

# ── 4. Add warm transfer endpoints before the API endpoints section ────────
ENDPOINT_ANCHOR = '# ─────────────────────────────────────────\n# API ENDPOINTS (all unchanged from original)\n# ─────────────────────────────────────────'

WARM_ENDPOINTS = '''
# ═══════════════════════════════════════════════════════════════════════════
# WARM TRANSFER WEBHOOK ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.api_route("/hold-loop", methods=["GET", "POST"])
async def hold_loop(request: Request):
    """
    Plays hold music in a loop while user waits for counsellor.
    User stays here until /counsellor-answer fires the VoBiz Transfer API
    which immediately redirects this call to /join-conference.
    """
    try:
        form_data = dict(await request.form())
    except Exception:
        form_data = {}

    call_sid = (
        request.query_params.get("call_sid")
        or form_data.get("CallUUID")
        or form_data.get("call_sid")
        or ""
    )
    BASE_URL       = get_base_url(request)
    hold_music_url = f"{BASE_URL}/static/audio/{CONNECTING_MUSIC}"

    logger.info(f"🔄 /hold-loop | call_sid={call_sid}")

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Play>{hold_music_url}</Play>"
        f'<Redirect method="POST">{BASE_URL}/hold-loop?call_sid={call_sid}</Redirect>'
        "</Response>"
    )
    return Response(content=xml, media_type="text/xml", headers=get_cloudflare_headers())


@app.api_route("/join-conference", methods=["GET", "POST"])
async def join_conference(request: Request):
    """
    Called when VoBiz Transfer API redirects the user from /hold-loop.
    Returns Conference XML so the user joins the room where counsellor is waiting.
    """
    try:
        form_data = dict(await request.form())
    except Exception:
        form_data = {}

    call_sid  = (
        request.query_params.get("call_sid")
        or form_data.get("CallUUID")
        or form_data.get("call_sid")
        or ""
    )
    conf_room = sessions.get(f"__conf__{call_sid}", f"gvx_{call_sid[-12:]}")

    logger.info(f"✅ /join-conference | call_sid={call_sid} | room={conf_room}")

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Conference>{conf_room}</Conference>"
        "<Hangup/>"
        "</Response>"
    )
    return Response(content=xml, media_type="text/xml", headers=get_cloudflare_headers())


@app.api_route("/counsellor-answer", methods=["GET", "POST"])
async def counsellor_answer(request: Request):
    """
    Called by VoBiz when counsellor picks up.
    1. Counsellor enters Conference room (VoBiz creates the room at this point)
    2. After a 1.5s delay, Transfer API pushes user from /hold-loop into the same room
    Both are then merged in the conference. ✅
    """
    try:
        form_data = dict(await request.form())
    except Exception:
        form_data = {}

    call_sid  = request.query_params.get("call_sid", "")
    conf_room = sessions.get(f"__conf__{call_sid}", f"gvx_{call_sid[-12:]}")
    BASE_URL  = get_base_url(request)

    logger.info(f"🤝 Counsellor answered | room={conf_room} | call_sid={call_sid} | data={form_data}")

    # Brief the counsellor
    briefing     = "Hello, this is GuniVox AI. A prospective student is waiting for career counselling. Connecting you now."
    briefing_url = await generate_tts_audio(briefing, BASE_URL, lang="en-IN")

    # Push user from /hold-loop into conference (with 1.5s delay so counsellor enters first)
    asyncio.create_task(_push_user_to_conference(call_sid, BASE_URL, delay=1.5))

    # Counsellor enters Conference room now (this creates the room on VoBiz)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Play>{briefing_url}</Play>"
        f"<Conference>{conf_room}</Conference>"
        "<Hangup/>"
        "</Response>"
    )
    return Response(content=xml, media_type="text/xml", headers=get_cloudflare_headers())


@app.api_route("/counsellor-hangup", methods=["GET", "POST"])
async def counsellor_hangup(request: Request):
    """
    Called by VoBiz when counsellor call ends (no-answer, busy, or completed).
    If counsellor never answered: rescue user from /hold-loop with fallback.
    If they answered and finished normally: log it and clean up.
    """
    try:
        form_data = dict(await request.form())
    except Exception:
        form_data = {}

    call_sid    = request.query_params.get("call_sid", "")
    BASE_URL    = get_base_url(request)
    hangup_cause = (
        form_data.get("HangupCauseName")
        or form_data.get("CallStatus")
        or form_data.get("status")
        or "unknown"
    )

    logger.info(f"📋 /counsellor-hangup | cause={hangup_cause} | call_sid={call_sid}")

    normal_causes = {"normal_clearing", "completed", "in-progress", "normal hangup"}
    if hangup_cause.lower() in normal_causes:
        logger.info(f"✅ Transfer completed normally")
        sessions.pop(f"__conf__{call_sid}", None)
        sessions.pop(f"__counsellor__{call_sid}", None)
    else:
        logger.warning(f"⚠️  Counsellor did not answer (cause={hangup_cause}) — rescuing user")
        asyncio.create_task(_rescue_user_from_hold_loop(call_sid, BASE_URL))

    return JSONResponse(content={"received": True})


@app.api_route("/user-fallback", methods=["GET", "POST"])
async def user_fallback(request: Request):
    """Plays fallback audio and hangs up the user's call."""
    audio_url = request.query_params.get("audio_url", "")
    logger.info(f"📢 /user-fallback | audio_url={audio_url[:80]}")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Play>{audio_url}</Play>"
        "<Hangup/>"
        "</Response>"
    )
    return Response(content=xml, media_type="text/xml", headers=get_cloudflare_headers())


'''

if ENDPOINT_ANCHOR in content:
    content = content.replace(ENDPOINT_ANCHOR, WARM_ENDPOINTS + ENDPOINT_ANCHOR, 1)
    print("✅ Inserted warm transfer webhook endpoints")
else:
    print("⚠️  Could not find API ENDPOINTS anchor")

with open(FILE, "w", encoding="utf-8") as f:
    f.write(content)

print("\n✅ server.py patched successfully.")
