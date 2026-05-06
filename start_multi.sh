#!/bin/bash

PROJECT_DIR="/home/dhruvil/GuniVox V3/GuniVox V3"

# Find a suitable terminal emulator
if command -v ptyxis &> /dev/null; then
    TERM_CMD="ptyxis -- "
elif command -v gnome-terminal &> /dev/null; then
    TERM_CMD="gnome-terminal -- "
else
    TERM_CMD="xterm -e "
fi

# 1. Start Python Backend in a new terminal
$TERM_CMD bash -c "cd '$PROJECT_DIR' && source .venv/bin/activate && uvicorn server:app --host 0.0.0.0 --port 8000 --reload; exec bash" &

# 2. Start React Frontend in a new terminal
$TERM_CMD bash -c "cd '$PROJECT_DIR' && npm run dev; exec bash" &

# 3. Start Cloudflare Tunnel if available
if command -v cloudflared &> /dev/null; then
    $TERM_CMD bash -c "cloudflared tunnel run gunivox; exec bash" &
fi
