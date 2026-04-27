#!/usr/bin/env bash
# build.sh — Render Build Script for GuniVox V3
# This runs during Render's build phase.

set -o errexit  # Exit on error

echo "=== GuniVox V3 Build ==="

# 1. Install system dependencies for Piper TTS (espeak-ng)
echo ">>> Installing system dependencies..."
apt-get update -qq && apt-get install -y -qq espeak-ng libespeak-ng1 > /dev/null 2>&1 || true

# 2. Install Python dependencies
echo ">>> Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# 3. Download Piper TTS voice model
echo ">>> Downloading Piper voice model..."
python download_piper_voice.py

# 4. Create required directories
mkdir -p static/audio
mkdir -p piper_voices

echo "=== Build complete ==="
