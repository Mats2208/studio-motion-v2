import json, sys
from faster_whisper import WhisperModel
src = sys.argv[1]; out = sys.argv[2]
m = WhisperModel("medium", device="cpu", compute_type="int8")
segs, info = m.transcribe(src, language="es", word_timestamps=True, vad_filter=False, beam_size=5)
words=[]
for s in segs:
    for w in s.words:
        words.append({"w": w.word.strip(), "start": round(w.start,3), "end": round(w.end,3), "p": round(w.probability,3)})
json.dump({"source": src, "duration": info.duration, "words": words}, open(out,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
for w in words: print(f"{w['start']:7.3f} {w['end']:7.3f} {w['p']:.2f} {w['w']}")
