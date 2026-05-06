import wave, io, struct
def max_amplitude(wav_bytes):
    try:
        with wave.open(io.BytesIO(wav_bytes), 'rb') as w:
            frames = w.readframes(w.getnframes())
            width = w.getsampwidth()
            fmt = '<' + ('h' if width==2 else 'b') * (len(frames)//width)
            samples = struct.unpack(fmt, frames)
            return max(abs(s) for s in samples[::10])
    except Exception as e:
        return -1
print("Ready")
