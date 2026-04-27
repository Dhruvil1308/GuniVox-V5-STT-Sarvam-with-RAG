# -*- coding: utf-8 -*-
"""
download_piper_voice.py
One-time setup: downloads a Piper TTS voice model into piper_voices/.

Run once before starting the server:
    python download_piper_voice.py

Available voices:
  en_US-lessac-medium  (recommended - best speed/quality)
  en_US-lessac-high    (better quality, same speed)
  en_US-amy-medium     (different female voice)

Change VOICE_NAME below to switch voice.
"""

import os
import sys
import requests

# Config
VOICE_NAME = "en_US-lessac-medium"
VOICES_DIR = os.path.join(os.path.dirname(__file__), "piper_voices")

# Piper HuggingFace URL structure:
# /resolve/main/{lang}/{lang_region}/{voice_name}/{quality}/{filename}
# Example: /en/en_US/lessac/medium/en_US-lessac-medium.onnx
BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"


def build_urls(voice_name):
    parts = voice_name.split("-")        # ['en_US', 'lessac', 'medium']
    lang_region = parts[0]              # en_US
    lang = lang_region.split("_")[0]   # en
    speaker = parts[1]                  # lessac
    quality = parts[2]                  # medium
    subpath = f"{lang}/{lang_region}/{speaker}/{quality}"
    onnx_url   = f"{BASE_URL}/{subpath}/{voice_name}.onnx"
    config_url = f"{BASE_URL}/{subpath}/{voice_name}.onnx.json"
    return onnx_url, config_url


def download(url, dest):
    if os.path.exists(dest):
        print(f"  [OK] Already exists: {os.path.basename(dest)}")
        return
    print(f"  [>>] Downloading {os.path.basename(dest)} ...")
    resp = requests.get(url, stream=True, timeout=180)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))
    downloaded = 0
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded * 100 // total
                print(f"\r     {pct}% ({downloaded // 1024} KB)", end="", flush=True)
    print(f"\r  [OK] Saved -> {os.path.basename(dest)}          ")


def main():
    print("=" * 60)
    print(f"  GuniVox -- Piper Voice Model Downloader")
    print(f"  Voice : {VOICE_NAME}")
    print(f"  Dir   : {VOICES_DIR}")
    print("=" * 60)

    os.makedirs(VOICES_DIR, exist_ok=True)

    onnx_url, config_url = build_urls(VOICE_NAME)
    onnx_path   = os.path.join(VOICES_DIR, f"{VOICE_NAME}.onnx")
    config_path = os.path.join(VOICES_DIR, f"{VOICE_NAME}.onnx.json")

    print(f"\n  ONNX URL  : {onnx_url}")
    print(f"  Config URL: {config_url}\n")

    try:
        download(onnx_url,   onnx_path)
        download(config_url, config_path)
    except requests.HTTPError as e:
        print(f"\n[ERR] HTTP Error: {e}")
        print("   Check VOICE_NAME at:")
        print("   https://huggingface.co/rhasspy/piper-voices/tree/main")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERR] Download failed: {e}")
        sys.exit(1)

    print()
    print("[DONE] Voice model ready!")
    print("   Start server: uvicorn server:app --host 0.0.0.0 --port 8000 --reload")


if __name__ == "__main__":
    main()
