#!/usr/bin/env bash
# build.sh — Render Build Script for GuniVox V3
# This runs during Render's build phase.

set -o errexit  # Exit on error

echo "=== GuniVox V3 Build ==="

# 1. Install Python dependencies
echo ">>> Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# 2. Create required directories
mkdir -p static/audio

# 3. Build the React frontend
echo ">>> Installing Node.js dependencies..."
npm install

echo ">>> Building React frontend..."
npm run build

echo "=== Build complete ==="
