import os
import requests

key = "AIzaSyBckN4uJqfMZ-1-PtBZAHUwc9fB1-njZsE"
url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={key}"

data = {
    "input": {"text": "Hello World"},
    "voice": {"languageCode": "en-US", "name": "en-US-Neural2-F"},
    "audioConfig": {"audioEncoding": "MP3"}
}

res = requests.post(url, json=data)
print(res.status_code)
print(res.text[:200])
