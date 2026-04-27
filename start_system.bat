@echo off
TITLE GuniVox V3 System Launcher
color 0A
echo.
echo ===================================================
echo   GuniVox V3 -- Starting All Services
echo ===================================================
echo.

REM --- 1. Python FastAPI Backend (via uvicorn) ---
echo [1/3] Launching Python Backend (uvicorn)...
start "GuniVox Backend" cmd /k "cd /d %~dp0 && call .venv\Scripts\activate && uvicorn server:app --host 0.0.0.0 --port 8000 --reload"

REM --- 2. Ngrok Tunnel ---
echo [2/3] Launching Ngrok Tunnel (port 8000)...
if exist "D:\ngrok.exe" (
    start "Ngrok Tunnel" cmd /k "D:\ngrok.exe http 8000"
) else (
    start "Ngrok Tunnel" cmd /k "ngrok http 8000"
)

REM --- 3. React Frontend (Vite dev server) ---
echo [3/3] Launching React Frontend (Vite)...
start "GuniVox Frontend" cmd /k "cd /d %~dp0 && npm run dev"

echo.
echo All services are starting up...
echo Waiting 7 seconds for servers to initialize...
timeout /t 7 /nobreak >nul
start http://localhost:3000

echo.
echo ===================================================
echo   GuniVox V3 is LIVE!
echo   Frontend  : http://localhost:3000
echo   Backend   : http://localhost:8000
echo   API Docs  : http://localhost:8000/docs
echo ===================================================
echo.
echo Keep the 3 terminal windows open to maintain service.
pause
