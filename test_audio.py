import re

def clean_stt(text):
    if '' in text: return ""
    clean = re.sub(r'[^a-zA-Z0-9\u0A80-\u0AFF\s]', '', text).strip()
    if len(clean) <= 1: return ""
    return text.strip()

print(clean_stt('આ હરલ ળાલ હાલે હાલલ હાલલલ'))
print(clean_stt('bumped o mimm<|lt|>'))
