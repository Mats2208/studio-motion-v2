"""Single source of truth for every time in the film.

Merges faster-whisper and ElevenLabs word timings, cuts the voice into six
phrases at the quietest 20 ms window of each pause, places them on the film
timeline and writes timeline.json (+ film/timeline.js for the composition).
"""
import json, math, difflib
from pathlib import Path
import numpy as np
import librosa

ROOT = Path(__file__).resolve().parents[1]
SR = 48000
FPS = 30
DURATION = 25.0
SCORE_TRIM = 0.056          # aligns the 120 BPM score grid to multiples of 0.5 s
PHRASE_WORDS = [5, 8, 6, 5, 6, 5]
EMPHASIS = {"idea": 0, "vida": 1, "movimiento": 2, "posibilidades": 3, "lugar": 4, "dimensiones": 5}
# Each phrase is placed so its anchor word's ACOUSTIC onset lands on a fixed film time. These are the
# moments the Blender shots were rendered for (B4 splits on "abren", B5 locks on "lugar", B7 rises on
# "dimensiones"), so any voice can be swapped in without re-rendering 3D.
ANCHORS = [("idea", 1.466), ("vida", 6.482), ("movimiento", 8.919), ("abren", 11.304), ("lugar", 15.023), ("dimensiones", 22.107)]
VOICE = json.loads((ROOT / "voice.json").read_text(encoding="utf-8"))   # {name, source, alignment, whisper}


def norm(w):
    return "".join(c for c in w.lower() if c.isalnum() or c in "áéíóúñ").replace("…", "")


def eleven_words(path):
    d = json.load(open(path, encoding="utf-8"))
    c, s0, s1 = d["characters"], d["character_start_times_seconds"], d["character_end_times_seconds"]
    out, cur, st, pe = [], "", None, None
    for ch, a, b in zip(c, s0, s1):
        if ch == " ":
            if cur: out.append({"w": cur, "start": st, "end": pe}); cur = ""
            continue
        if not cur: st = a
        cur += ch; pe = b
    if cur: out.append({"w": cur, "start": st, "end": pe})
    return out


def match_key(w):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", w.lower()) if c.isalnum() and unicodedata.category(c) != "Mn")


def merged_words():
    """ElevenLabs alignment is the canonical word list (it is the script); Whisper refines matching words."""
    el = eleven_words(ROOT / VOICE["alignment"] if not Path(VOICE["alignment"]).is_absolute() else VOICE["alignment"])
    wh = json.load(open(ROOT / VOICE["whisper"], encoding="utf-8"))["words"]
    assert len(el) == sum(PHRASE_WORDS), ("script word count", len(el))
    sm = difflib.SequenceMatcher(a=[match_key(w["w"]) for w in el], b=[match_key(w["w"]) for w in wh], autojunk=False)
    pair = {}
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            pair[blk.a + k] = wh[blk.b + k]
    out = []
    for i, b in enumerate(el):
        a = pair.get(i)
        ds = abs(a["start"] - b["start"]) if a else 9.0
        start = (a["start"] + b["start"]) / 2 if ds <= 0.08 else b["start"]
        end = (a["end"] + b["end"]) / 2 if a and abs(a["end"] - b["end"]) <= 0.08 else b["end"]
        out.append({"word": b["w"].strip(".,…"), "key": norm(b["w"]), "src_start": round(start, 3),
                    "src_end": round(end, 3), "whisper_eleven_delta_ms": round(ds * 1000) if a else None})
    return out


def acoustic_onset(y, t0, t1):
    """First 5 ms hop whose 15 ms RMS rises 12 dB above the quietest preceding hop (same rule as tools/onsets.py)."""
    hop, win = int(0.005 * SR), int(0.015 * SR)
    a, b = max(0, int(t0 * SR)), int(t1 * SR)
    d = np.array([20 * np.log10(np.sqrt((y[s:s + win] ** 2).mean()) + 1e-9) for s in range(a, b, hop)])
    lo = int(np.argmin(d[: max(2, len(d) // 2)]))
    j = next((k for k in range(lo, len(d)) if d[k] > d[lo] + 12), lo)
    return a / SR + j * 0.005 + 0.0075


def quietest(y, t0, t1, win=0.02):
    a, b = int(t0 * SR), int(t1 * SR)
    n = int(win * SR)
    best, best_t = 1e9, (t0 + t1) / 2
    for s in range(a, max(a + 1, b - n), n // 4):
        r = float(np.sqrt(np.mean(y[s:s + n] ** 2)))
        if r < best:
            best, best_t = r, (s + n / 2) / SR
    return best_t


def main():
    src = VOICE["source"]
    y, _ = librosa.load(src if Path(src).is_absolute() else ROOT / src, sr=SR, mono=True)
    src_len = len(y) / SR
    words = merged_words()
    phrases, i = [], 0
    for p, n in enumerate(PHRASE_WORDS):
        phrases.append(words[i:i + n]); i += n
    cuts = [0.0]
    for p in range(5):
        cuts.append(quietest(y, phrases[p][-1]["src_end"], phrases[p + 1][0]["src_start"]))
    cuts.append(src_len)
    # trim each phrase to its own speech (+100 ms before, +180 ms after) so silent tails never collide
    seg_in = [max(cuts[p], phrases[p][0]["src_start"] - 0.10) for p in range(6)]
    seg_out = [min(cuts[p + 1], phrases[p][-1]["src_end"] + 0.18) for p in range(6)]
    offsets = []
    for p, (key_, target) in enumerate(ANCHORS):
        w = next(x for x in phrases[p] if x["key"] == key_)
        on = acoustic_onset(y, w["src_start"] - 0.08, w["src_start"] + 0.2)
        offsets.append(round(target - on + VOICE.get("corrections", [0] * 6)[p], 3))
    tl_phr, tl_words = [], []
    for p, ws in enumerate(phrases):
        off = offsets[p]
        ph = {"index": p, "src_in": round(seg_in[p], 3), "src_out": round(seg_out[p], 3), "offset": off,
              "start": round(seg_in[p] + off, 3), "end": round(seg_out[p] + off, 3),
              "text": " ".join(w["word"] for w in ws)}
        tl_phr.append(ph)
        for w in ws:
            g = dict(w, phrase=p, start=round(w["src_start"] + off, 3), end=round(w["src_end"] + off, 3))
            g["frame"] = round(g["start"] * FPS)
            tl_words.append(g)
    for i, (a, b) in enumerate(zip(tl_phr, tl_phr[1:])):
        sa = phrases[i][-1]["src_end"] + a["offset"]          # real speech edges on the film timeline
        sb = phrases[i + 1][0]["src_start"] + b["offset"]
        assert sb - sa >= 0.10, ("speech overlap", a["text"], b["text"], round(sa, 3), round(sb, 3))
        if a["end"] > b["start"]:                              # only the silent margins touch: split the silence
            mid = round((sa + sb) / 2, 3)
            a["src_out"] = round(a["src_out"] - (a["end"] - mid), 3); a["end"] = mid
            b["src_in"] = round(b["src_in"] + (mid - b["start"]), 3); b["start"] = mid
    assert tl_phr[0]["start"] >= 0.0 and tl_phr[-1]["end"] <= DURATION - 0.4, "voice outside the film window"
    emph = {k: next(w for w in tl_words if w["key"] == k and w["phrase"] == p) for k, p in EMPHASIS.items()}
    beats = [round(k * 0.5, 3) for k in range(0, 50)]
    downbeats = [float(t) for t in range(1, 25, 2)]

    # S-curve stroke for act 3, 64 screen-space points (px). Blender unprojects the same points.
    stroke = []
    for k in range(64):
        t = k / 63
        x = 220 + 1480 * t
        yv = 600 - 150 * math.sin(2 * math.pi * (t - 0.08)) * (0.55 + 0.45 * t) + 26 * math.sin(5 * math.pi * t)
        stroke.append([round(x, 2), round(yv, 2)])

    acts = [
        {"id": "a1-idea", "start": 0.0, "end": 3.0},
        {"id": "a2-create", "start": 3.0, "end": 7.3},
        {"id": "a3-stroke", "start": 7.3, "end": 10.4},
        {"id": "a4-questions", "start": 10.4, "end": 13.4},
        {"id": "a5-pieces", "start": 13.4, "end": 16.0},
        {"id": "a6-montage", "start": 16.0, "end": 21.0},
        {"id": "a7-dimensions", "start": 21.0, "end": 23.0},
        {"id": "a8-lockup", "start": 23.0, "end": 25.0},
    ]
    shots = [
        {"id": "b1_cursor", "start": 1.5, "end": 3.1, "w": 1920, "h": 1080, "alpha": False},
        {"id": "b2_torus", "start": 3.0, "end": 7.3, "w": 1560, "h": 990, "alpha": False},
        {"id": "b3_ribbon", "start": 9.0, "end": 10.4, "w": 1920, "h": 1080, "alpha": False},
        {"id": "b4_question", "start": 10.4, "end": 12.1, "w": 1920, "h": 1080, "alpha": False},
        {"id": "b5_pieces", "start": 13.4, "end": 16.0, "w": 1920, "h": 1080, "alpha": False},
        {"id": "b6_wire", "start": 17.0, "end": 18.0, "w": 1920, "h": 1080, "alpha": False},
        {"id": "b7_dimensiones", "start": 22.0, "end": 23.0, "w": 1920, "h": 1080, "alpha": True},
        {"id": "b8_logo", "start": 23.0, "end": 25.0, "w": 1920, "h": 1080, "alpha": True},
    ]
    for s in shots:
        s["frames"] = round((s["end"] - s["start"]) * FPS)
    events = {
        "caret_blinks": [0.15, 0.65], "cursor_lunge": 2.5, "flash": 3.0,
        "swatch_clicks": [5.0, 5.5, 6.0], "play_click": 6.5, "viewport_zoom": 7.0,
        "stroke_start": emph["movimiento"]["start"] - 1.32, "stroke_end": emph["movimiento"]["start"],
        "lift": 9.0, "lens_wipe": 10.3, "split": 11.304,   # B4 is rendered splitting at 11.304 s
        "grid": round(min(12.0, emph["posibilidades"]["start"] - 0.05), 3),   # grid + plate arrive with the word
        "snaps": [13.75, 13.875, 14.0, 14.25, 14.5, 14.75, 15.0],
        "montage": [17.0, 18.0, 19.0, 20.0], "dimensiones": emph["dimensiones"]["start"], "lockup": 23.0,
    }
    tl = {"voice": VOICE["name"], "fps": FPS, "duration": DURATION, "frames": int(DURATION * FPS), "width": 1920, "height": 1080,
          "seed": 251016, "bpm": 120, "score_trim": SCORE_TRIM, "beats": beats, "downbeats": downbeats,
          "phrases": tl_phr, "words": tl_words,
          "emphasis": {k: {"start": v["start"], "end": v["end"], "frame": v["frame"]} for k, v in emph.items()},
          "acts": acts, "shots": shots, "events": events, "stroke_px": stroke,
          "palette": {"ink": "#0E0B16", "ink2": "#1B1530", "paper": "#F4F0EA", "white": "#FFFFFF",
                      "violet": "#6A3DF0", "lilac": "#B9A6FF", "coral": "#FF5B3A", "muted": "#8C8698",
                      "viewport": "#ECE7F5"}}
    (ROOT / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1), encoding="utf-8")
    (ROOT / "film/timeline.js").write_text("window.TL = " + json.dumps(tl, ensure_ascii=False) + ";\n", encoding="utf-8")
    for p in tl_phr:
        print(f"P{p['index']} src {p['src_in']:6.3f}-{p['src_out']:6.3f} -> {p['start']:6.3f}-{p['end']:6.3f}  {p['text']}")
    for k, v in emph.items():
        print(f"  {k:14s} {v['start']:6.3f}  frame {v['frame']}")
    print("max whisper/eleven start delta ms:", max(w["whisper_eleven_delta_ms"] or 0 for w in tl_words),
          "| unmatched:", [w["word"] for w in tl_words if w["whisper_eleven_delta_ms"] is None])


if __name__ == "__main__":
    main()
