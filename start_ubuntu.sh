#!/bin/bash
echo "Starting GuniVox V3 System"

# Trap CTRL+C to kill all background processes
trap "trap - SIGTERM && kill -- -$$" SIGINT SIGTERM EXIT

# 1. Start Python backend
echo "[1/3] Launching Python Backend (uvicorn)..."
source .venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# 2. Start ngrok if available (optional)
echo "[2/3] Checking for ngrok..."
if command -v ngrok &> /dev/null; then
    echo "Launching Ngrok Tunnel (port 8000)..."
    ngrok http 8000 &
else
    echo "ngrok not found. Skipping ngrok tunnel."
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
