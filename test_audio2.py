import wave, io, struct

def detect_silence(wav_bytes):
    try:
        with wave.open(io.BytesIO(wav_bytes), 'rb') as w:
            frames = w.readframes(w.getnframes())
            width = w.getsampwidth()
            fmt = '<' + ('h' if width==2 else 'b') * (len(frames)//width)
            samples = struct.unpack(fmt, frames)
            max_amp = max(abs(s) for s in samples[::10])
            return max_amp < 1500  # Silence threshold
    except Exception as e:
        return False
