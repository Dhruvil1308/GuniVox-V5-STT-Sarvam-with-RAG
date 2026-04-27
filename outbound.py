from flask import Flask, request, Response, jsonify
import requests
import json
from datetime import datetime

app = Flask(__name__)

# ==========================================
# CONFIGURATION
# ==========================================
VOBIZ_AUTH_ID = 'MA_U0V5JKA1'
VOBIZ_AUTH_TOKEN = 'iU5tg4E4WfRO7XN6cdtm3dYccqanE4kybqSgDFu8NEHDbzGlzpXiGq4XCcdpFFXO'
VOBIZ_FROM_NUMBER = '+912271263960'
NGROK_URL = 'https://disliking-hulk-bauble.ngrok-free.dev'  # Update if ngrok restarts
# ==========================================


# 1. FRONTEND
@app.route('/', methods=['GET'])
def index():
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>GuniVox Outbound Agent</title>
      <style>
        body { font-family: sans-serif; display: flex; justify-content: center; align-items: center;
               height: 100vh; background: #f4f4f9; margin: 0; }
        .card { background: white; padding: 30px; border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; }
        input { padding: 10px; width: 200px; margin-right: 10px;
                border: 1px solid #ccc; border-radius: 4px; }
        button { padding: 10px 20px; background: #0056b3; color: white;
                 border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #004494; }
        #status { margin-top: 15px; font-weight: bold; color: #333; }
      </style>
    </head>
    <body>
      <div class="card">
        <h2>📞 Call via GuniVox</h2>
        <input type="text" id="phone" placeholder="+919876543210" />
        <button onclick="makeCall()">Call Me</button>
        <p id="status"></p>
      </div>
      <script>
        async function makeCall() {
          const phone = document.getElementById('phone').value;
          const statusEl = document.getElementById('status');
          if (!phone) { statusEl.innerText = 'Please enter a phone number.'; return; }
          statusEl.innerText = 'Initiating call...';
          try {
            const response = await fetch('/api/call', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ to: phone })
            });
            const result = await response.json();
            statusEl.innerText = result.message || result.error;
          } catch (err) {
            statusEl.innerText = 'Error connecting to server.';
          }
        }
      </script>
    </body>
    </html>
    '''


# 2. TRIGGER OUTBOUND CALL
@app.route('/api/call', methods=['POST'])
def make_call():
    data = request.get_json()
    to_number = data.get('to')

    if not to_number:
        return jsonify({'error': 'Phone number is required'}), 400

    url = f'https://api.vobiz.ai/api/v1/Account/{VOBIZ_AUTH_ID}/Call/'

    headers = {
        'X-Auth-ID': VOBIZ_AUTH_ID,
        'X-Auth-Token': VOBIZ_AUTH_TOKEN,
        'Content-Type': 'application/json'
    }

    payload = {
        'from': VOBIZ_FROM_NUMBER,
        'to': to_number,
        'answer_url': f'{NGROK_URL}/vobiz-answer',
        'answer_method': 'POST',
        'hangup_url': f'{NGROK_URL}/status',
        'hangup_method': 'POST'
    }

    print(f"\\n[{datetime.now()}] 📤 Sending call request to Vobiz...")
    print(f"   To: {to_number}")
    print(f"   Answer URL: {payload['answer_url']}")

    try:
        response = requests.post(url, headers=headers, json=payload)
        result = response.json()
        print(f"   Vobiz Response ({response.status_code}): {json.dumps(result, indent=2)}")

        if not response.ok:
            return jsonify({'error': result.get('message', 'Vobiz API error'), 'details': result}), response.status_code

        return jsonify({'message': f"✅ Call queued! UUID: {result.get('request_uuid')}", 'details': result})

    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return jsonify({'error': str(e)}), 500


# 3. VOBIZ ANSWER WEBHOOK — called when recipient picks up
@app.route('/vobiz-answer', methods=['GET', 'POST'])
def vobiz_answer():
    print(f"\\n[{datetime.now()}] 📞 /vobiz-answer HIT!")
    print(f"   Method: {request.method}")
    print(f"   Headers: {dict(request.headers)}")
    print(f"   Form data: {request.form.to_dict()}")
    print(f"   JSON: {request.get_json(silent=True)}")

    xml_response = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak voice="WOMAN" language="en-US">
        Hello! Welcome to GuniVox. How can I assist you today?
    </Speak>
</Response>'''

    return Response(xml_response, mimetype='text/xml')


# 4. VOBIZ STATUS/HANGUP WEBHOOK
@app.route('/status', methods=['GET', 'POST'])
def call_status():
    print(f"\\n[{datetime.now()}] 📴 /status HIT!")
    print(f"   Form data: {request.form.to_dict()}")
    print(f"   JSON: {request.get_json(silent=True)}")
    return jsonify({'received': True}), 200


# 5. CATCH-ALL — logs any unexpected Vobiz webhook hits
@app.route('/<path:path>', methods=['GET', 'POST'])
def catch_all(path):
    print(f"\\n[{datetime.now()}] ⚠️  UNEXPECTED HIT: /{path}")
    print(f"   Method: {request.method}")
    print(f"   Form: {request.form.to_dict()}")
    print(f"   JSON: {request.get_json(silent=True)}")
    return jsonify({'received': True}), 200


if __name__ == '__main__':
    print("✅ GuniVox Python server starting on http://localhost:3000")
    print(f"   Answer URL: {NGROK_URL}/vobiz-answer")
    print(f"   Status URL: {NGROK_URL}/status")
    app.run(host='0.0.0.0', port=3000, debug=True)

