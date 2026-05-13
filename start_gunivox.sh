#!/bin/bash
# ============================================================
#  GuniVox V3 — Multi-Terminal Startup Script
# ============================================================

PROJECT_DIR="/home/dhruvil/GuniVox V3/GuniVox V3"
cd "$PROJECT_DIR"

# 1. Cleanup
echo "🧹 Cleaning up..."
pkill -9 -f "uvicorn server:app" 2>/dev/null || true
pkill -9 -f "vite"               2>/dev/null || true
pkill -9 -f "cloudflared"        2>/dev/null || true
sleep 2

# 2. Greeting
mkdir -p static/audio
if [ ! -f "static/audio/greeting.wav" ]; then
    echo "🎙️ Generating greeting..."
    .venv/bin/python3 generate_greeting.py || true
fi

# 3. Terminal Launch Helper
# We use 'ptyxis' as it was found on the system.
# We use --new-window to ensure they are visible.
launch() {
    local cmd="$1"
    local title="$2"
    echo "🚀 Launching $title..."
    ptyxis --new-window -T "$title" -- bash -c "cd '$PROJECT_DIR'; $cmd; echo; echo 'Process exited. Press enter to close.'; read" &
    sleep 1
}

# 4. Start the 3 terminals
launch ".venv/bin/python3 -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload" "GuniVox BACKEND"
launch "npm run dev" "GuniVox FRONTEND"
launch "cloudflared tunnel run gunivox" "GuniVox TUNNEL"

echo ""
echo "✅ All 3 terminals have been launched!"
echo "You can now close this window or keep it for reference."
echo ""
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo "Public: https://api.gunivox.online"
echo ""
read -p "Press Enter to finish startup script..."
