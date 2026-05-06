#!/bin/bash
echo "Starting GuniVox V3 System"

# Trap CTRL+C to kill all background processes
trap "trap - SIGTERM && kill -- -$$" SIGINT SIGTERM EXIT

# 1. Start Python backend
echo "[1/3] Launching Python Backend (uvicorn)..."
source .venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# 2. Start cloudflared tunnel
echo "[2/3] Checking for cloudflared..."
if command -v cloudflared &> /dev/null; then
    echo "Launching Cloudflare Tunnel (gunivox)..."
    cloudflared tunnel run gunivox &
else
    echo "cloudflared not found. Skipping tunnel."
fi

# 3. Start React Frontend
echo "[3/3] Launching React Frontend (Vite)..."
npm run dev &
FRONTEND_PID=$!

echo ""
echo "==================================================="
echo "  GuniVox V3 is LIVE!"
echo "  Backend   : http://localhost:8000"
echo "  API Docs  : http://localhost:8000/docs"
echo "  Frontend  : usually http://localhost:5173"
echo "==================================================="
echo "Press Ctrl+C to stop all services."
echo ""

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
