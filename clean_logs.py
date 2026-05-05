import re

with open("server.py", "r", encoding="utf-8") as f:
    code = f.read()

# Remove specific emojis
emojis = ["✅", "❌", "⚡", "📞", "🗣️", "📥", "📤", "🔊", "✨", "💾", "💡", "🚀", "⚠️"]
for e in emojis:
    code = code.replace(e, "")
    code = code.replace(e + " ", "")

# Fix double spaces left by emoji removal
code = code.replace('logger.info("  Sarvam', 'logger.info("Sarvam')
code = code.replace('logger.warning("  SARVAM', 'logger.warning("SARVAM')

# Remove unnecessary logging in hot paths to optimize latency
lines = code.split("\n")
new_lines = []

for line in lines:
    stripped = line.strip()
    if stripped.startswith('logger.info("="*50)'):
        continue
    if 'logger.info(f"   Downloaded {len(audio_data)} bytes' in stripped:
        continue
    if 'logger.info("   Running Sarvam AI STT' in stripped:
        continue
    if 'logger.info(f"   Full Payload: {form_data}")' in stripped:
        continue
    if "logger.info(f\"TTS Cache hit for:" in stripped:
        continue
    if "logger.info(f\"Sarvam TTS done →" in stripped:
        continue
    if 'logger.info(f"   Call SID: {call_sid}")' in stripped:
        continue
    if 'logger.info(f"RAG: Translated query' in stripped:
        continue
    if 'logger.info(f"RAG: no relevant results' in stripped:
        continue
    if 'logger.info(f"RAG: {len(results)} hit(s)' in stripped:
        continue
    if 'print(" Default courses populated.")' in stripped:
        continue

    # Convert verbose TTS log to debug
    if 'logger.info(f"Sarvam TTS ({SARVAM_TTS_SPEAKER}) synthesizing' in line:
        line = line.replace('logger.info', 'logger.debug')

    # Convert the prompt build error to warning
    if 'logger.error(f"Prompt build error: {e}")' in line:
        pass
    
    new_lines.append(line)

with open("server.py", "w", encoding="utf-8") as f:
    f.write("\n".join(new_lines))

print("Cleanup script executed.")
