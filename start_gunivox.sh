#!/bin/bash
# ============================================================
#  GuniVox V3 — Perfect Startup Script
#  Handles: process cleanup, cache clearing, greeting
#  generation, backend, frontend, and cloudflared tunnel.
# ============================================================

set -e

PROJECT_DIR="/home/dhruvil/GuniVox V3/GuniVox V3"
cd "$PROJECT_DIR"

VENV="$PROJECT_DIR/.venv/bin"
PYTHON="$VENV/python3"
PIP="$VENV/pip"

# ─────────────────────────────────────────────────────────────
# 0. CLEAN UP STALE PROCESSES & FREE PORT 8000
# ─────────────────────────────────────────────────────────────
echo "🧹 Cleaning up any stale processes..."

# Kill by name
pkill -9 -f "uvicorn server:app" 2>/dev/null || true
pkill -9 -f "vite"               2>/dev/null || true
pkill -9 -f "npm run dev"        2>/dev/null || true

# Kill anything still holding port 8000
PORT_PID=$(lsof -ti :8000 2>/dev/null) || true
if [ -n "$PORT_PID" ]; then
    echo "   ⚠️  Port 8000 held by PID(s): $PORT_PID — force-killing..."
    echo "$PORT_PID" | xargs kill -9 2>/dev/null || true
fi

# Also kill anything holding port 3000 (Vite)
PORT3_PID=$(lsof -ti :3000 2>/dev/null) || true
if [ -n "$PORT3_PID" ]; then
    echo "   ⚠️  Port 3000 held by PID(s): $PORT3_PID — force-killing..."
    echo "$PORT3_PID" | xargs kill -9 2>/dev/null || true
fi

# Clear Python bytecode cache so edits are always loaded fresh
find "$PROJECT_DIR" -type d -name "__pycache__" \
    ! -path "*/.venv/*" ! -path "*/node_modules/*" \
    -exec rm -rf {} + 2>/dev/null || true

# Wait until port 8000 is actually free (up to 10 seconds)
echo "   Waiting for port 8000 to be free..."
for i in $(seq 1 10); do
    if ! lsof -ti :8000 &>/dev/null; then
        echo "✅ Port 8000 is free."
        break
    fi
    sleep 1
done

# Final check — abort if port is still busy
if lsof -ti :8000 &>/dev/null; then
    echo "❌ ERROR: Port 8000 is still in use after 10 seconds. Cannot start."
    echo "   Run:  sudo lsof -i :8000   to see what's blocking it."
    exit 1
fi

# ─────────────────────────────────────────────────────────────
# 1. (RE-)GENERATE STATIC GREETING — instant voice on pickup
# ─────────────────────────────────────────────────────────────
GREETING_FILE="$PROJECT_DIR/static/audio/greeting.wav"
mkdir -p "$PROJECT_DIR/static/audio"

if [ ! -f "$GREETING_FILE" ]; then
    echo "🎙️  Generating static greeting audio..."
    "$PYTHON" "$PROJECT_DIR/generate_greeting.py" && \
        echo "✅ Greeting generated: static/audio/greeting.wav" || \
        echo "⚠️  Greeting generation failed — will use live TTS fallback"
else
    echo "✅ Greeting audio already exists (static/audio/greeting.wav)"
fi

# ─────────────────────────────────────────────────────────────
# 2. FIND TERMINAL EMULATOR
# ─────────────────────────────────────────────────────────────
if command -v ptyxis &>/dev/null; then
    open_tab() { ptyxis --new-window -- bash -c "$1; exec bash" & }
elif command -v gnome-terminal &>/dev/null; then
    open_tab() { gnome-terminal --title="$2" -- bash -c "$1; exec bash" & }
elif command -v xterm &>/dev/null; then
    open_tab() { xterm -title "$2" -e bash -c "$1; exec bash" & }
else
    # Fallback: run everything in background
    open_tab() { bash -c "$1" &> "/tmp/gunivox_$2.log" & }
fi

# ─────────────────────────────────────────────────────────────
# 3. START BACKEND (FastAPI / uvicorn)
# ─────────────────────────────────────────────────────────────
echo "🚀 Starting Python backend..."
BACKEND_CMD="cd '$PROJECT_DIR' && source .venv/bin/activate && \
    uvicorn server:app --host 0.0.0.0 --port 8000 --reload"
open_tab "$BACKEND_CMD" "GuniVox Backend"

# Wait for backend to be ready (up to 30 seconds)
echo "⏳ Waiting for backend to start..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/api/llm/health &>/dev/null; then
        echo "✅ Backend is UP (${i}s)"
        break
    fi
    sleep 1
done

# ─────────────────────────────────────────────────────────────
# 4. START REACT FRONTEND (Vite)
# ─────────────────────────────────────────────────────────────
echo "🖥️  Starting React frontend..."
FRONTEND_CMD="cd '$PROJECT_DIR' && npm run dev"
open_tab "$FRONTEND_CMD" "GuniVox Frontend"

# ─────────────────────────────────────────────────────────────
# 5. START CLOUDFLARE TUNNEL (if installed)
# ─────────────────────────────────────────────────────────────
if command -v cloudflared &>/dev/null; then
    echo "🌐 Starting Cloudflare Tunnel..."
    TUNNEL_CMD="cloudflared tunnel run gunivox"
    open_tab "$TUNNEL_CMD" "GuniVox Tunnel"
else
    echo "⚠️  cloudflared not found — skipping tunnel."
fi

# ─────────────────────────────────────────────────────────────
# DONE
# ─────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║         🎉 GuniVox V3 is LIVE!                  ║"
echo "║                                                  ║"
echo "║  Backend   →  http://localhost:8000              ║"
echo "║  API Docs  →  http://localhost:8000/docs         ║"
echo "║  Frontend  →  http://localhost:3000              ║"
echo "║  Public    →  https://api.gunivox.online         ║"
echo "╚══════════════════════════════════════════════════╝"
