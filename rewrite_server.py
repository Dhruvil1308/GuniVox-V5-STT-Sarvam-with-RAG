import os

content = '''import os
import logging
import json
import re
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
import requests
from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import Response, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from openpyxl import Workbook

# Import our configuration
from prompt_config import SYSTEM_PROMPT

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment
load_dotenv(".env.local")

# Configure OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Configure Vobiz
VOBIZ_AUTH_ID = os.getenv("VOBIZ_AUTH_ID", 'MA_U0V5JKA1')
VOBIZ_AUTH_TOKEN = os.getenv("VOBIZ_AUTH_TOKEN", 'iU5tg4E4WfRO7XN6cdtm3dYccqanE4kybqSgDFu8NEHDbzGlzpXiGq4XCcdpFFXO')
VOBIZ_FROM_NUMBER = os.getenv("VOBIZ_FROM_NUMBER", '+912271263960')
NGROK_URL = 'https://disliking-hulk-bauble.ngrok-free.dev'

app = FastAPI()

# Enable CORS for Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for dev, restrict in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATABASE SETUP (SQLite) ---
DB_FILE = "gunivox.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_sid TEXT UNIQUE,
            phone_number TEXT,
            status TEXT,
            started_at TEXT,
            end_reason TEXT,
            user_name TEXT,
            interest TEXT,
            lead_status TEXT,
            follow_up TEXT,
            transcript TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            fees TEXT,
            brochure_url TEXT
        )
    """)
    conn.commit()
    conn.close()
    
    populate_default_courses()

def populate_default_courses():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM courses")
    if c.fetchone()[0] == 0:
        defaults = [
            ("BCA", "Bachelor of Computer Applications. 10+2 English required.", "70,000/yr", None),
            ("MCA", "Master of Computer Applications. Needs BCA/BE/BSc.", "1,40,000/yr", None),
            ("BSc IT", "Bachelor of Science in IT (Data Science/Cyber Security).", "75,000 - 85,000/yr", None),
            ("MSc IT", "Master of Science in IT.", "75,000 - 1,00,000/yr", None)
        ]
        c.executemany("INSERT INTO courses (name, description, fees, brochure_url) VALUES (?, ?, ?, ?)", defaults)
        conn.commit()
        print("✅ Default courses populated.")
    conn.close()

init_db()

# Simple in-memory chat history (Call SID -> Message List)
sessions: Dict[str, List[Dict[str, str]]] = {}

# --- HELPER FUNCTIONS ---

def save_call_log(call_sid: str, data: dict):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT id FROM calls WHERE call_sid = ?", (call_sid,))
    exists = c.fetchone()
    
    if not exists:
         c.execute("""
            INSERT INTO calls (call_sid, phone_number, status, started_at)
            VALUES (?, ?, ?, ?)
         """, (call_sid, data.get('phone_number'), 'initiated', datetime.now().isoformat()))
    else:
        fields = []
        values = []
        for key, val in data.items():
            if key in ['status', 'end_reason', 'user_name', 'interest', 'lead_status', 'follow_up', 'transcript']:
                fields.append(f"{key} = ?")
                values.append(val)
        
        if fields:
            values.append(call_sid)
            sql = f"UPDATE calls SET {', '.join(fields)} WHERE call_sid = ?"
            c.execute(sql, values)
            
    conn.commit()
    conn.close()

def export_db_to_excel(start_date: Optional[str] = None, end_date: Optional[str] = None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    query = "SELECT * FROM calls"
    params = []
    
    if start_date and end_date:
        query += " WHERE started_at BETWEEN ? AND ?"
        params.extend([f"{start_date}T00:00:00", f"{end_date}T23:59:59"])
    
    query += " ORDER BY id DESC"
    
    c.execute(query, params)
    rows = c.fetchall()
    columns = [description[0] for description in c.description]
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Call Logs"
    ws.append(columns)
    for row in rows:
        ws.append(row)
    
    filename = "leads.xlsx"
    wb.save(filename)
    return filename

# --- API MODELS ---
class LoginRequest(BaseModel):
    username: str
    password: str

class CallRequest(BaseModel):
    phone_number: str

class Course(BaseModel):
    name: str
    description: str
    fees: str
    brochure_url: Optional[str] = None

# --- API ENDPOINTS ---

@app.post("/api/login") 
async def login(creds: LoginRequest):
    if creds.username == "Admin" and creds.password == "Guni@2026":
        return {"token": "fake-jwt-token-for-demo", "user": "Admin"}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/api/call")
async def trigger_call(req: CallRequest):
    logger.info(f"🔗 Using Ngrok URL: {NGROK_URL}")
    url = f"https://api.vobiz.ai/api/v1/Account/{VOBIZ_AUTH_ID}/Call/"
    headers = {
        "X-Auth-ID": VOBIZ_AUTH_ID,
        "X-Auth-Token": VOBIZ_AUTH_TOKEN,
        "Content-Type": "application/json"
    }
    payload = {
        "from": VOBIZ_FROM_NUMBER,
        "to": req.phone_number,
        "answer_url": f"{NGROK_URL}/vobiz-answer",
        "answer_method": "POST",
        "hangup_url": f"{NGROK_URL}/status",
        "hangup_method": "POST"
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        result = response.json()
        
        if not response.ok:
            logger.error(f"Vobiz Error: {result}")
            raise HTTPException(status_code=response.status_code, detail=result.get("message", "Vobiz API error"))
            
        call_uuid = result.get("request_uuid")
        if not call_uuid:
            call_uuid = "unknown_" + datetime.now().strftime("%Y%m%d%H%M%S")

        save_call_log(call_uuid, {"phone_number": req.phone_number})
        
        return {"success": True, "call_sid": call_uuid, "status": "queued", "details": result}
    except Exception as e:
        logger.error(f"Call failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/end_call/{call_sid}")
async def end_call(call_sid: str):
    try:
        url = f"https://api.vobiz.ai/api/v1/Account/{VOBIZ_AUTH_ID}/Call/{call_sid}/"
        headers = {
            "X-Auth-ID": VOBIZ_AUTH_ID,
            "X-Auth-Token": VOBIZ_AUTH_TOKEN
        }
        res = requests.delete(url, headers=headers)
        save_call_log(call_sid, {"status": "completed", "end_reason": "user_initiated"})
        return {"success": True, "status": "completed"}
    except Exception as e:
        logger.error(f"Failed to end call {call_sid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# VOBIZ ANSWER WEBHOOK
@app.api_route("/vobiz-answer", methods=["GET", "POST"])
async def vobiz_answer(request: Request):
    print(f"\\n[{datetime.now()}] 📞 /vobiz-answer HIT!")
    print(f"   Method: {request.method}")
    print(f"   Headers: {dict(request.headers)}")
    form_data = await request.form()
    print(f"   Form data: {dict(form_data)}")
    
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak voice="WOMAN" language="en-US">
        Hello! Welcome to GuniVox. How can I assist you today?
    </Speak>
</Response>"""

    return Response(content=xml_response, media_type="text/xml")

# VOBIZ STATUS WEBHOOK
@app.api_route("/status", methods=["GET", "POST"])
async def call_status(request: Request):
    print(f"\\n[{datetime.now()}] 📴 /status HIT!")
    form_data = await request.form()
    print(f"   Form data: {dict(form_data)}")
    
    data_dict = dict(form_data)
    if not data_dict:
        try:
            data_dict = await request.json()
        except:
            pass
            
    call_sid = data_dict.get("request_uuid") or data_dict.get("CallUUID") or data_dict.get("CallSid")
    status = data_dict.get("status") or data_dict.get("CallStatus") or "unknown"
    
    if call_sid:
        save_call_log(call_sid, {"status": status})
        
    return JSONResponse(content={"received": True})

@app.api_route("/{path:path}", methods=["GET", "POST"])
async def catch_all(request: Request, path: str):
    # Only map if not an /api route so we don't clobber them
    if path.startswith("api/"):
        raise HTTPException(status_code=404)
        
    print(f"\\n[{datetime.now()}] ⚠️  UNEXPECTED HIT: /{path}")
    print(f"   Method: {request.method}")
    form_data = await request.form()
    print(f"   Form: {dict(form_data)}")
    return JSONResponse(content={"received": True})

# --- ALL EXISTING API ENDPOINTS RETAINED ---

@app.get("/api/stats")
async def get_stats(start_date: Optional[str] = None, end_date: Optional[str] = None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    query_total = "SELECT COUNT(*) FROM calls"
    query_positive = "SELECT COUNT(*) FROM calls WHERE lead_status='Positive'"
    params = []
    
    if start_date and end_date:
        range_cond = " WHERE started_at BETWEEN ? AND ?"
        query_total += range_cond
        query_positive += " AND started_at BETWEEN ? AND ?"
        params.extend([f"{start_date}T00:00:00", f"{end_date}T23:59:59"])
        
    c.execute(query_total, params)
    total = c.fetchone()[0]
    
    if start_date and end_date:
        c.execute(query_positive, params)
    else:
        c.execute(query_positive)
    positive = c.fetchone()[0]
    
    c.execute("SELECT * FROM calls ORDER BY id DESC LIMIT 5")
    recent_calls = []
    columns = [desc[0] for desc in c.description]
    for row in c.fetchall():
        recent_calls.append(dict(zip(columns, row)))

    conn.close()
    return {"total_calls": total, "positive_leads": positive, "recent_calls": recent_calls}

@app.get("/api/calls")
async def get_calls(q: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    query = "SELECT * FROM calls"
    params = []
    conditions = []
    
    if q:
        conditions.append("(phone_number LIKE ? OR user_name LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    
    if start_date and end_date:
        conditions.append("started_at BETWEEN ? AND ?")
        params.extend([f"{start_date}T00:00:00", f"{end_date}T23:59:59"])
        
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY id DESC"
    
    c.execute(query, params)
    calls = []
    columns = [desc[0] for desc in c.description]
    for row in c.fetchall():
        calls.append(dict(zip(columns, row)))
    
    conn.close()
    return calls

@app.get("/api/courses")
async def get_courses():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM courses")
    courses = []
    columns = [desc[0] for desc in c.description]
    for row in c.fetchall():
        courses.append(dict(zip(columns, row)))
    conn.close()
    return courses

@app.post("/api/courses")
async def add_course(course: Course):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO courses (name, description, fees, brochure_url) VALUES (?, ?, ?, ?)",
              (course.name, course.description, course.fees, course.brochure_url))
    conn.commit()
    course_id = c.lastrowid
    conn.close()
    return {**course.dict(), "id": course_id}

@app.put("/api/courses/{course_id}")
async def update_course(course_id: int, course: Course):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE courses SET name=?, description=?, fees=?, brochure_url=? WHERE id=?",
              (course.name, course.description, course.fees, course.brochure_url, course_id))
    conn.commit()
    conn.close()
    return {"success": True}

@app.delete("/api/courses/{course_id}")
async def delete_course(course_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM courses WHERE id=?", (course_id,))
    conn.commit()
    conn.close()
    return {"success": True}

@app.get("/api/download")
async def download_excel(start_date: Optional[str] = None, end_date: Optional[str] = None):
    filepath = export_db_to_excel(start_date, end_date)
    return FileResponse(path=filepath, filename="GuniVox_Leads.xlsx", media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.get("/api/call/{call_sid}")
async def get_call_status_ep(call_sid: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT status, transcript FROM calls WHERE call_sid = ?", (call_sid,))
    row = c.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Call not found")

    status, transcript_json = row
    transcript = json.loads(transcript_json) if transcript_json else []
    
    if call_sid in sessions:
        transcript = [msg for msg in sessions[call_sid] if msg['role'] != 'system']

    return {"call_sid": call_sid, "status": status, "transcript": transcript}

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 GuniVox Backend (Vobiz Edition) Running...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''

with open("server.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Rewrote server.py successfully.")
