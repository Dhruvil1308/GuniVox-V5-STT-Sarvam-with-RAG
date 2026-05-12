import asyncio
import os
from dotenv import load_dotenv
import httpx

load_dotenv(".env.local")

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
INITIAL_GREETING = "Hi, હું અનન્યા, Ganpat University તરફથી AI Career Assistant બોલું છું. ઘણા વિદ્યાર્થીઓને 10મા, 12મા અથવા Graduation પછી યોગ્ય career પસંદ કરવામાં મુશ્કેલી પડે છે. વિદ્યાર્થીઓને યોગ્ય માર્ગદર્શન આપવા માટે અમે તમારા શહેરમાં FREE One-to-One Career Counselling Session આયોજન કરી રહ્યા છીએ. શું તમને આ counselling sessionમાં જોડાવું ગમશે?"

async def generate_greeting():
    url = "https://api.sarvam.ai/text-to-speech"
    payload = {
        "text": INITIAL_GREETING,
        "target_language_code": "gu-IN",
        "speaker": "anushka",
        "model": "bulbul:v2",
        "speech_sample_rate": 8000,
        "enable_punctuation": True,
        "pitch": 0,
        "pace": 1.0,
        "loudness": 1.5,
        "audio_format": "wav"
    }
    headers = {"api-subscription-key": SARVAM_API_KEY}
    
    print("Generating greeting via Sarvam AI...")
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            os.makedirs("static/audio", exist_ok=True)
            with open("static/audio/greeting.wav", "wb") as f:
                import base64
                data = response.json()
                f.write(base64.b64decode(data['audios'][0]))
            print("Successfully saved to static/audio/greeting.wav")
        else:
            print(f"Error: {response.status_code} - {response.text}")

if __name__ == "__main__":
    asyncio.run(generate_greeting())
