<div align="center">

# ⚡ GuniVox V3

### Ganpat University — AI-Powered Voice Admission Counselor

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Twilio](https://img.shields.io/badge/Twilio-Voice_API-F22F46?style=for-the-badge&logo=twilio&logoColor=white)](https://twilio.com)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com)

**GuniVox** is an intelligent outbound voice assistant that automates admission counseling calls for **Ganpat University**. It uses **Twilio** for telephony, **OpenAI GPT-4o-mini** for conversational AI, and a modern **React + Vite** dashboard for real-time call management and analytics.

---

[Features](#-features) · [Architecture](#-architecture) · [Installation](#-installation--setup) · [How to Run](#-how-to-run) · [Configuration](#%EF%B8%8F-configuration) · [API Reference](#-api-reference) · [Project Structure](#-project-structure) · [Tech Stack](#-tech-stack)

</div>

---

## 🌟 Features

| Category | Feature |
|---|---|
| **🤖 AI Voice Agent** | Human-like female Indian AI counselor with warm, friendly tone |
| **📞 Outbound Dialer** | One-click outbound calls via Twilio Voice API from the dashboard |
| **🗣️ Multilingual** | Automatic language detection — English (en-IN), Gujarati (gu-IN), Hindi (hi-IN) |
| **📊 Live Analytics** | Real-time call stats, positive lead tracking, and searchable call history |
| **📝 Live Transcription** | Real-time speech-to-text transcription displayed during active calls |
| **🎓 Course Management** | Full CRUD interface for managing university courses and fees |
| **🧠 Smart Lead Extraction** | AI-powered post-call analysis extracts name, interest, and lead status |
| **📥 Excel Export** | One-click export of all call logs with transcripts to `.xlsx` |
| **🔍 Search & Filter** | Search call history by phone number/name, filter by date range |
| **🔐 Authentication** | Login-protected admin dashboard |

---

## 🏛 Architecture

```
┌──────────────────────┐        ┌──────────────────────┐
│   React Frontend     │  HTTP  │   FastAPI Backend     │
│   (Vite + TS)        │◄──────►│   (Python)            │
│   Port: 3000         │        │   Port: 8000          │
└──────────────────────┘        └──────┬───────────────┘
                                       │
                        ┌──────────────┼──────────────┐
                        │              │              │
                   ┌────▼────┐  ┌──────▼─────┐  ┌────▼────┐
                   │ Twilio  │  │  OpenAI    │  │ SQLite  │
                   │ Voice   │  │  GPT-4o    │  │   DB    │
                   │ API     │  │  mini      │  │         │
                   └─────────┘  └────────────┘  └─────────┘
                        │
                   ┌────▼────┐
                   │  Ngrok  │
                   │ Tunnel  │
                   └─────────┘
```

### How It Works

1. **Admin initiates a call** from the React dashboard by entering a phone number.
2. **Backend triggers Twilio** to place an outbound call to the target number.
3. **Twilio hits the `/voice` webhook** (via Ngrok tunnel) to get the initial greeting TwiML.
4. **User speaks → Twilio transcribes** speech and POSTs it to the `/respond` endpoint.
5. **OpenAI generates a contextual response** using the system prompt + course database.
6. **Response is spoken back** to the user via Twilio's text-to-speech (Google Neural2 voices).
7. **Metadata (name, interest, lead status)** is extracted in real-time from each AI response.
8. **When the call ends**, a full transcript analysis runs to ensure all metadata is captured.
9. **Dashboard updates in real-time** with call status, transcript, and analytics.

---

## 📦 Installation & Setup

### Prerequisites — What You Need to Install First

Before setting up GuniVox, make sure the following software is installed on your machine:

| # | Software | Download Link | Why It's Needed |
|---|---|---|---|
| 1 | **Python 3.10+** | [python.org/downloads](https://www.python.org/downloads/) | Runs the FastAPI backend server |
| 2 | **Node.js 18+** (includes npm) | [nodejs.org](https://nodejs.org/) | Runs the React frontend dev server |
| 3 | **Ngrok** | [ngrok.com/download](https://ngrok.com/download) | Creates a public tunnel so Twilio can reach your local server |
| 4 | **Git** (optional) | [git-scm.com](https://git-scm.com/) | To clone the repository |

> **💡 Tip:** After installing Python and Node.js, verify they work by running:
> ```bash
> python --version    # Should show Python 3.10+
> node --version      # Should show v18+
> npm --version       # Should show 9+
> ```

### External Accounts Required

You also need accounts on these platforms (free tiers available):

| Service | Sign Up | What You Need From It |
|---|---|---|
| **Twilio** | [twilio.com/try-twilio](https://www.twilio.com/try-twilio) | Account SID, Auth Token, and a Phone Number |
| **OpenAI** | [platform.openai.com](https://platform.openai.com/) | API Key for GPT-4o-mini |

---

### Step 1 — Clone the Repository

```bash
git clone https://github.com/<your-username>/GuniVox_V3.git
cd GuniVox_V3
```

Or download the ZIP from GitHub and extract it.

### Step 2 — Create Python Virtual Environment

```bash
# Create virtual environment
python -m venv .venv
```

### Step 3 — Install Python Dependencies

```bash
# Activate the virtual environment (Windows)
.venv\Scripts\activate

# Install all backend libraries
pip install -r requirements.txt
```

This installs the following Python libraries:

| Library | Purpose |
|---|---|
| `fastapi` | Backend web framework (REST API) |
| `uvicorn` | ASGI server to run FastAPI |
| `twilio` | Twilio Voice API SDK for making/managing calls |
| `openai` | OpenAI SDK for GPT-4o-mini AI responses |
| `python-dotenv` | Loads environment variables from `.env.local` |
| `openpyxl` | Generates Excel (`.xlsx`) reports from call data |
| `pydantic` | Data validation for API request/response models |
| `python-multipart` | Handles form data from Twilio webhooks |
| `requests` | HTTP client for external API calls |

### Step 4 — Install Frontend Dependencies

```bash
npm install
```

This installs the following Node.js packages (defined in `package.json`):

| Package | Purpose |
|---|---|
| `react` & `react-dom` | React 19 UI framework |
| `axios` | HTTP client for calling the backend API |
| `framer-motion` | Smooth animations and transitions |
| `lucide-react` | Modern icon library |
| `tailwind-merge` & `clsx` | Tailwind CSS utility helpers |
| `@vitejs/plugin-react` | Vite plugin for React + JSX support |
| `typescript` | TypeScript compiler |
| `vite` | Frontend build tool & dev server |

### Step 5 — Configure Environment Variables

Create a file named `.env.local` in the project root directory and add your API keys:

```env
# LLM Provider Selection: openai | gemini | ollama
AI_PROVIDER=ollama

# Ollama Configuration (used when AI_PROVIDER=ollama)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=jatas-qwen-rag:latest
OLLAMA_TIMEOUT_SECONDS=45

# Optional RAG Controls
ENABLE_RAG=true
RAG_TOP_K=3

# OpenAI Configuration
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o-mini

# Twilio Configuration
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_CALLER_ID=+1xxxxxxxxxx

# Ngrok (optional — system auto-detects if Ngrok is running locally)
NGROK_URL=https://your-subdomain.ngrok-free.dev

# Gemini API (optional — used by frontend data layer)
GEMINI_API_KEY=your-gemini-api-key
```

**Where to find these values:**

| Variable | Where to Get It |
|---|---|
| `OPENAI_API_KEY` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `TWILIO_ACCOUNT_SID` | [Twilio Console](https://console.twilio.com/) → Dashboard |
| `TWILIO_AUTH_TOKEN` | [Twilio Console](https://console.twilio.com/) → Dashboard |
| `TWILIO_CALLER_ID` | [Twilio Console](https://console.twilio.com/) → Phone Numbers → Active Numbers |

> **⚠️ Important:** The `.env.local` file is git-ignored by default. **Never commit API keys to version control.**

### Step 6 — Set Up Ngrok

Place `ngrok.exe` either in `D:\ngrok.exe` or add it to your system PATH. The `start_system.bat` checks for `D:\ngrok.exe` first, then falls back to the system PATH.

Sign up at [ngrok.com](https://ngrok.com) and authenticate:

```bash
ngrok config add-authtoken <your-ngrok-auth-token>
```

---

## 🟢 How to Run

### Option A — One-Click Start (Recommended for Windows)

The project includes a **`start_system.bat`** script that automatically launches **all three services** (Backend + Ngrok + Frontend) in separate terminal windows with a single double-click.

**Just double-click `start_system.bat`** — or run it from the command line:

```bash
start_system.bat
```

#### What `start_system.bat` Does

The batch file performs the following steps automatically:

```batch
@echo off
TITLE GuniVox System Launcher
echo ===================================================
echo   Starting GuniVox V3 System...
echo ===================================================

echo [1/3] Launching Python Backend...
start "GuniVox Backend" cmd /k "call .venv\Scripts\activate && pip install -r requirements.txt --quiet && python server.py"

echo [2/3] Launching Ngrok Tunnel...
if exist "D:\ngrok.exe" (
    start "Ngrok Tunnel" cmd /k "D:\ngrok.exe http 8000"
) else (
    start "Ngrok Tunnel" cmd /k "ngrok http 8000"
)

echo [3/3] Launching React Frontend...
start "GuniVox Frontend" cmd /k "npm run dev"

echo.
echo All servers are starting!
echo Please wait a moment for the frontend to load...
echo.
timeout /t 5
start http://localhost:3000

echo System is Live! You can close this window if you want,
echo but keep the other 3 terminal windows open.
pause
```

**Step-by-step breakdown:**

| Step | What Happens |
|---|---|
| **[1/3] Backend** | Activates the Python virtual environment (`.venv`), installs/updates dependencies from `requirements.txt`, and starts the FastAPI server on **port 8000** |
| **[2/3] Ngrok** | Opens a secure tunnel to expose `localhost:8000` to the internet. Checks for `D:\ngrok.exe` first, otherwise uses the system PATH. This gives Twilio a public URL to send webhooks to |
| **[3/3] Frontend** | Runs `npm run dev` to start the Vite React dev server on **port 3000** |
| **Auto-open** | After a 5-second wait, your default browser opens `http://localhost:3000` automatically |

**After running, you will see 3 new terminal windows:**

```
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  GuniVox Backend │  │  Ngrok Tunnel    │  │  GuniVox Frontend│
│  (Python/FastAPI)│  │  (Public URL)    │  │  (React/Vite)    │
│  Port: 8000      │  │  → localhost:8000│  │  Port: 3000      │
└──────────────────┘  └──────────────────┘  └──────────────────┘
      ⚠️ Keep all 3 terminal windows open while using the system!
```

---

### Option B — Manual Start (Any OS)

If you are on macOS/Linux or prefer to start each service manually, open **three separate terminals**:

**Terminal 1 — Python Backend:**
```bash
# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies (first time only)
pip install -r requirements.txt

# Start the server
python server.py
# ✅ Backend running at http://localhost:8000
```

**Terminal 2 — Ngrok Tunnel:**
```bash
ngrok http 8000
# ✅ Copy the HTTPS URL shown (e.g., https://xxxx-xxxx.ngrok-free.dev)
# The backend auto-detects this URL at runtime
```

**Terminal 3 — React Frontend:**
```bash
npm run dev
# ✅ Frontend running at http://localhost:3000
```

---

### Step 7 — Open the Dashboard

Navigate to **http://localhost:3000** in your browser (auto-opens if using `start_system.bat`).

**Default Login Credentials:**

| Field | Value |
|---|---|
| Username | `Admin` |
| Password | `Guni@2026` |

After logging in, you'll see three main sections:

| Tab | Description |
|---|---|
| **🔊 Smart Dialer** | Enter a phone number and initiate AI-powered outbound calls with live waveform visualization and real-time transcription |
| **📊 Analytics Hub** | View call statistics, positive lead counts, searchable call history table, and export data to Excel |
| **🎓 Courses** | Add, edit, or delete university courses — changes are immediately reflected in the AI's knowledge |

---

## ⚙️ Configuration

### System Prompt (`prompt_config.py`)

The AI personality and behavior is fully customizable in `prompt_config.py`. The system prompt defines:

- **AI persona** — A warm, friendly female Indian admission counselor named "GuniVox"
- **Conversation flow** — 6-phase outbound call protocol (Intro → Name → Guidance → Email → Confirm → Exit)
- **Response format** — Structured output: `LANG: [code] | TEXT: [spoken text] | NAME: [name] | INTEREST: [course] | STATUS: [status]`
- **University database** — Official course catalog, fees, eligibility, and contact info
- **Multilingual support** — Auto-detection and switching between English, Gujarati, and Hindi
- **Conciseness rules** — Max 1-2 lines per response (optimized for phone conversations)

### Course Database

Courses can be managed in two ways:

1. **Dashboard UI** → Navigate to the "Courses" tab to add, edit, or delete courses via the web interface.
2. **Database** → Courses are stored in `gunivox.db` (SQLite) and automatically seeded with defaults on first run.

The AI dynamically fetches courses from the database at the start of each call, so changes are reflected immediately.

### Ollama + Local SLM Inference

You can run GuniVox fully on your local Ollama model for outbound-call responses.

1. Start Ollama locally and pull your model:
```bash
ollama pull jatas-qwen-rag:latest
ollama run jatas-qwen-rag:latest
```
2. Set `.env.local` values:
```env
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=jatas-qwen-rag:latest
```
3. Restart `server.py`.
4. Verify connectivity:
       - `GET /api/llm/health`

If `model_available` is `true`, all live outbound call inference in `/vobiz-respond` will use your local Ollama model.

### Lightweight RAG Support

The backend includes a simple lexical retrieval layer (`rag_documents` table in SQLite). On each user turn, top matched snippets are injected as system context before model inference.

Useful endpoints:

- `POST /api/rag/documents` → Add knowledge
- `GET /api/rag/search?q=...&top_k=3` → Test retrieval quality

Example add request:

```json
{
      "title": "BCA Scholarships 2026",
      "content": "Merit students above 85% get 20% tuition waiver for first year.",
      "source": "admissions-policy"
}
```

### Default Courses (Auto-Seeded)

| Course | Fees (per year) |
|---|---|
| BCA (Bachelor of Computer Applications) | ₹70,000 |
| MCA (Master of Computer Applications) | ₹1,40,000 |
| BSc IT (Data Science / Cyber Security) | ₹75,000 – ₹85,000 |
| MSc IT | ₹75,000 – ₹1,00,000 |

### Voice Configuration

| Setting | Value | Location |
|---|---|---|
| Default Voice | `Google.en-IN-Neural2-D` | `server.py` |
| Gujarati Voice | `Google.gu-IN-Standard-A` | `server.py` |
| Speech Input | `speech` with auto timeout | `server.py` |
| Speech Hints | Common keywords for faster recognition | `server.py` |

---

## 📡 API Reference

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/login` | Authenticate with username & password |

**Request Body:**
```json
{ "username": "Admin", "password": "Guni@2026" }
```

---

### Call Management

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/call` | Initiate an outbound call |
| `POST` | `/api/end_call/{call_sid}` | End an active call |
| `GET` | `/api/call/{call_sid}` | Get live call status & transcript |

**Initiate Call — Request:**
```json
{ "phone_number": "+919876543210" }
```

**Initiate Call — Response:**
```json
{ "success": true, "call_sid": "CAxxxxxxxx", "status": "initiated" }
```

---

### Analytics & Logs

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/stats` | Get call statistics (total calls, positive leads) |
| `GET` | `/api/calls` | List all call logs (with optional search & date filter) |
| `GET` | `/api/download` | Download call logs as Excel file |
| `POST` | `/api/calls/{id}/reanalyze` | Re-analyze a call transcript for missing metadata |

### LLM & RAG Utilities

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/llm/health` | Check active provider status and Ollama model availability |
| `POST` | `/api/rag/documents` | Insert a RAG document into SQLite |
| `GET` | `/api/rag/search` | Test retrieval results for a query |

**Query Parameters (for `/api/calls` and `/api/stats`):**

| Param | Type | Description |
|---|---|---|
| `q` | string | Search by phone number or user name |
| `start_date` | string | Filter from date (YYYY-MM-DD) |
| `end_date` | string | Filter to date (YYYY-MM-DD) |

---

### Course Management

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/courses` | List all courses |
| `POST` | `/api/courses` | Add a new course |
| `PUT` | `/api/courses/{id}` | Update an existing course |
| `DELETE` | `/api/courses/{id}` | Delete a course |

**Course Schema:**
```json
{
  "name": "BCA",
  "description": "Bachelor of Computer Applications",
  "fees": "70,000/yr",
  "brochure_url": "https://example.com/brochure.pdf"
}
```

---

### Twilio Webhooks (Internal)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/voice` | Initial call greeting (TwiML) — called by Twilio |
| `POST` | `/respond` | Handle user speech input & return AI response — called by Twilio |
| `POST` | `/status` | Receive call status updates from Twilio |

> These endpoints are called by Twilio via the Ngrok tunnel, not by the frontend.

---

## 📁 Project Structure

```
GuniVox_V3/
│
├── server.py               # FastAPI backend — API routes, Twilio webhooks, OpenAI integration
├── prompt_config.py         # AI system prompt & university knowledge base
├── outbound.py              # Standalone outbound call utility (for testing)
├── requirements.txt         # Python dependencies
├── gunivox.db               # SQLite database (auto-generated on first run)
├── leads.xlsx               # Exported call logs (auto-generated on download)
│
├── App.tsx                  # Main React app — Login, Dialer, Analytics, Courses views
├── index.tsx                # React entry point (renders <App /> into DOM)
├── index.html               # HTML shell with Tailwind CDN & import maps
├── index.css                # Global styles (Tailwind directives + custom scrollbar)
├── types.ts                 # TypeScript interfaces (Course, University, Helpdesk, Transcription)
├── data.ts                  # Static data — course catalog, university profile, helpdesk contacts
│
├── components/
│   ├── VoiceAgent.tsx       # Voice agent UI component
│   └── InfoDisplay.tsx      # Information display component
│
├── services/
│   └── audioUtils.ts        # Audio utility functions
│
├── vite.config.ts           # Vite configuration (port 3000, environment variables, aliases)
├── tsconfig.json            # TypeScript compiler configuration
├── package.json             # Node.js dependencies & npm scripts
├── metadata.json            # Project metadata (name, description, permissions)
│
├── start_system.bat         # ⚡ Windows one-click launcher (starts ALL 3 services)
├── .env.local               # Environment variables — API keys (git-ignored, must create manually)
└── .gitignore               # Git ignore rules
```

---

## 🛠 Tech Stack

### Backend (Python)

| Library | Version | Purpose |
|---|---|---|
| **FastAPI** | Latest | High-performance async web framework for building APIs |
| **Uvicorn** | Latest | Lightning-fast ASGI server to run FastAPI |
| **Twilio** | Latest | Twilio SDK — making outbound calls, handling voice webhooks |
| **OpenAI** | Latest | OpenAI SDK — GPT-4o-mini for conversational AI responses |
| **python-dotenv** | Latest | Loads API keys and config from `.env.local` file |
| **openpyxl** | Latest | Generates Excel (`.xlsx`) files for call data export |
| **Pydantic** | Latest | Request/response data validation and serialization |
| **python-multipart** | Latest | Parses form data from Twilio webhook POST requests |
| **requests** | Latest | HTTP client for external API communication |

### Frontend (TypeScript/React)

| Package | Version | Purpose |
|---|---|---|
| **React** | 19 | Component-based UI framework |
| **React DOM** | 19 | React renderer for web browsers |
| **Vite** | 6+ | Fast build tool and development server |
| **TypeScript** | 5.8 | Static type checking for JavaScript |
| **Axios** | Latest | Promise-based HTTP client for API calls |
| **Framer Motion** | 12+ | Production-ready animation library |
| **Lucide React** | Latest | Beautiful, consistent icon set |
| **Tailwind CSS** | CDN | Utility-first CSS framework for styling |
| **tailwind-merge** | Latest | Merges Tailwind classes without conflicts |
| **clsx** | Latest | Conditional CSS class utility |

### Infrastructure

| Tool | Purpose |
|---|---|
| **Ngrok** | Secure HTTPS tunnel — exposes localhost:8000 to the internet for Twilio webhooks |
| **SQLite** | Lightweight file-based database — no separate database server needed |
| **Google Neural2 Voices** | High-quality text-to-speech voices (Indian English & Gujarati) |

---

## 📊 Database Schema

The database (`gunivox.db`) is **automatically created** on first run. No manual setup needed.

### `calls` Table

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER | Primary key (auto-increment) |
| `call_sid` | TEXT | Twilio Call SID (unique identifier) |
| `phone_number` | TEXT | Target phone number |
| `status` | TEXT | Call status — `initiated`, `ringing`, `answered`, `completed`, `busy`, `no-answer`, `failed` |
| `started_at` | TEXT | ISO timestamp of when the call was initiated |
| `end_reason` | TEXT | How the call ended (`user_initiated`, etc.) |
| `user_name` | TEXT | Caller's name (extracted by AI) |
| `interest` | TEXT | Course interest (extracted by AI) |
| `lead_status` | TEXT | `Positive` / `Negative` / `Pending` |
| `follow_up` | TEXT | Follow-up notes |
| `transcript` | TEXT | Full conversation transcript (stored as JSON) |

### `courses` Table

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER | Primary key (auto-increment) |
| `name` | TEXT | Course name (e.g., "BCA", "MCA") |
| `description` | TEXT | Course description and eligibility |
| `fees` | TEXT | Fee structure (e.g., "70,000/yr") |
| `brochure_url` | TEXT | Link to brochure PDF (optional) |

---

## 🔄 Call Flow Diagram

```
┌─────────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Dashboard  │────►│  /api/   │────►│  Twilio  │────►│  Phone   │
│  (React)    │     │  call    │     │  API     │     │  (User)  │
└─────────────┘     └──────────┘     └────┬─────┘     └──────────┘
                                          │
                                    ┌─────▼─────┐
                                    │  /voice   │  ◄── Greeting TwiML
                                    └─────┬─────┘
                                          │
                                    ┌─────▼─────┐
                                    │ /respond  │  ◄── Speech → AI → Speech (loop)
                                    └─────┬─────┘
                                          │
                                    ┌─────▼─────┐
                                    │  /status  │  ◄── Call ended → Analyze transcript
                                    └───────────┘
```

---

## 🧪 Testing with Standalone Outbound Script

For quick testing without the dashboard, use `outbound.py`:

```bash
# Activate virtual environment
.venv\Scripts\activate

# Edit TARGET_NUMBER and TWIML_URL in outbound.py
# Then run:
python outbound.py
```

This directly places a Twilio call without needing the React frontend.

---

## 📋 Available Commands

| Command | Description |
|---|---|
| `start_system.bat` | **⚡ One-click launch** — starts Backend + Ngrok + Frontend automatically |
| `python server.py` | Start only the FastAPI backend server (port 8000) |
| `npm run dev` | Start only the React frontend dev server (port 3000) |
| `ngrok http 8000` | Start only the Ngrok tunnel |
| `npm run build` | Build the React frontend for production |
| `npm run preview` | Preview the production build locally |
| `python outbound.py` | Test outbound calling directly without the dashboard |

---

## ⚠️ Important Notes

1. **Ngrok must be running** before making calls — Twilio needs a public HTTPS URL to send webhooks to your local server.
2. **Twilio trial accounts** can only call verified phone numbers. Upgrade your Twilio account for unrestricted calling.
3. **The SQLite database** (`gunivox.db`) is auto-created on first run with 4 default courses (BCA, MCA, BSc IT, MSc IT).
4. **Keep all 3 terminal windows open** while using the system. Closing any terminal will stop that service.
5. **CORS is set to allow all origins** (`*`) for development. Restrict this in production.
6. **Login credentials** are hardcoded for demo purposes (`Admin` / `Guni@2026`). Implement proper authentication for production use.
7. **The `.env.local` file is git-ignored.** You must create it manually with your own API keys.

---

## 🔧 Troubleshooting

| Problem | Solution |
|---|---|
| `ModuleNotFoundError` when running `server.py` | Make sure the virtual environment is activated: `.venv\Scripts\activate` |
| `npm: command not found` | Install Node.js from [nodejs.org](https://nodejs.org/) |
| "Could not find Ngrok URL" error | Make sure Ngrok is running (`ngrok http 8000`) before making calls |
| Twilio "Cannot make call" error | Verify your Twilio credentials in `.env.local` and check that the phone number is verified (trial accounts) |
| Frontend shows blank page | Check the browser console for errors, and ensure `npm install` completed successfully |
| Port 8000 already in use | Kill the existing process or change the port in `server.py` |

---

## 📄 License

This project is developed for **Ganpat University** admission counseling purposes.

---

<div align="center">
  <p><strong>Built with ❤️ for Ganpat University</strong></p>
  <p><sub>GuniVox V3 — Intelligent Voice Assistant for Admissions</sub></p>
</div>
#   G u n i V o x - T e s t i n g - G r o q  
 