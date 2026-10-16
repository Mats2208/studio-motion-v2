"""Acoustic onset of every word, measured on the placed voice track (film/assets/audio/voice-only.wav).

Search window per word (ElevenLabs only when the two disagree by > 300 ms): [min(ElevenLabs, Whisper-on-mix) - 80 ms, max(...) + 80 ms]. Onset = first
5 ms hop whose 15 ms RMS rises 12 dB above the quietest hop that precedes it inside the window.
Visual cues anchor to `onset`; timeline.json and film/timeline.js are rewritten in place.
"""
import json
from pathlib import Path
import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
tl = json.loads((ROOT / "timeline.json").read_text(encoding="utf-8"))
mix_words = json.loads((ROOT / "analysis/words-mix.json").read_text(encoding="utf-8"))["words"]
v, sr = sf.read(ROOT / "film/assets/audio/voice-only.wav")
v = v.mean(1)
hop, win = int(0.005 * sr), int(0.015 * sr)


def onset(t0, t1):
    a, b = int(t0 * sr), int(t1 * sr)
    d = np.array([20 * np.log10(np.sqrt((v[s:s + win] ** 2).mean()) + 1e-9) for s in range(a, b, hop)])
    lo = int(np.argmin(d[: max(2, len(d) // 2)]))
    j = next((k for k in range(lo, len(d)) if d[k] > d[lo] + 12), None)
    return None if j is None else round(t0 + j * 0.005 + 0.0075, 3)


import difflib
import unicodedata
norm = lambda w: "".join(c for c in unicodedata.normalize("NFD", w.lower()) if c.isalnum() and unicodedata.category(c) != "Mn")
sm = difflib.SequenceMatcher(a=[norm(w["key"]) for w in tl["words"]], b=[norm(m["w"]) for m in mix_words], autojunk=False)
pair = {blk.a + k: mix_words[blk.b + k] for blk in sm.get_matching_blocks() for k in range(blk.size)}
for i, w in enumerate(tl["words"]):
    m = pair.get(i, {"start": w["start"]})
    lo, hi = min(w["start"], m["start"]), max(w["start"], m["start"])
    if hi - lo > 0.3:            # sources disagree badly (music masking): trust ElevenLabs
        lo = hi = w["start"]
    o = onset(lo - 0.08, hi + 0.12)
    w["onset"] = o if o is not None else w["start"]
    w["onset_frame"] = round(w["onset"] * tl["fps"])
for k, e in tl["emphasis"].items():
    w = next(x for x in tl["words"] if x["key"] == k and abs(x["start"] - e["start"]) < 1e-3)
    e["onset"], e["onset_frame"] = w["onset"], w["onset_frame"]
    print(f"{k:14s} onset {e['onset']:.3f} (frame {e['onset_frame']})")
(ROOT / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1), encoding="utf-8")
(ROOT / "film/timeline.js").write_text("window.TL = " + json.dumps(tl, ensure_ascii=False) + ";\n", encoding="utf-8")
print("words:", " ".join(f"{w['word']}@{w['onset']}" for w in tl["words"]))
