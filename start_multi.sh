#!/bin/bash

PROJECT_DIR="/home/dhruvil/GuniVox V3/GuniVox V3"

# 1. Start Python Backend in a new terminal
ptyxis -T "GuniVox Backend" -- bash -c "cd '$PROJECT_DIR' && source .venv/bin/activate && uvicorn server:app --host 0.0.0.0 --port 8000 --reload; exec bash" &

# 2. Start React Frontend in a new terminal
ptyxis -T "GuniVox Frontend" -- bash -c "cd '$PROJECT_DIR' && npm run dev; exec bash" &

# 3. Start Ngrok if available
if command -v ngrok &> /dev/null; then
    ptyxis -T "Ngrok" -- bash -c "ngrok http 8000; exec bash" &
fi
