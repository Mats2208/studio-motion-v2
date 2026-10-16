"""One command per voice: timeline -> mix -> acoustic onsets -> HyperFrames render -> verification.
  python tools/build_voice.py <name> <voice.mp3> <alignment.json>
Writes film/renders/studio-motion-v2-<name>.mp4 and analysis/verification-<name>.json."""
import json, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
name, src, align = sys.argv[1:4]
py = sys.executable


def run(*cmd, cwd=ROOT):
    env = dict(__import__("os").environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    r = subprocess.run(list(cmd), cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", shell=(cmd[0] == "npx"))
    if r.returncode:
        print(r.stdout[-1500:], r.stderr[-1500:]); sys.exit(f"failed: {cmd[:3]}")
    return r.stdout


wsrc = f"analysis/words-{name}.json"
if not (ROOT / wsrc).exists():
    run(py, "analysis/whisper_words.py", src, wsrc)
ANCH = [("idea", 1.466, 0), ("vida", 6.482, 0), ("movimiento", 8.919, 0), ("abren", 11.304, 0), ("lugar", 15.023, 0), ("dimensiones", 22.107, 1)]
corr = [0.0] * 6
for it in range(3):     # place -> measure the placed voice -> correct each phrase by its anchor error
    (ROOT / "voice.json").write_text(json.dumps({"name": name, "source": src, "alignment": align, "whisper": wsrc,
                                                 "corrections": corr}, indent=1), encoding="utf-8")
    print(run(py, "tools/build_timeline.py")[-700:])
    print(run(py, "tools/mix_audio.py")[-200:])
    run(py, "analysis/whisper_words.py", "film/assets/audio/mix.wav", "analysis/words-mix.json")
    run(py, "tools/onsets.py")
    tl = json.loads((ROOT / "timeline.json").read_text(encoding="utf-8"))
    errs = []
    for p, (k, target, _) in enumerate(ANCH):
        w = next(x for x in tl["words"] if x["key"] == k and x["phrase"] == p)
        errs.append(round(w["onset"] - target, 3))
    print("iteration", it, "anchor errors (s):", errs)
    if max(abs(e) for e in errs) <= 1 / 30:
        break
    corr = [round(c - e, 3) for c, e in zip(corr, errs)]
out = f"renders/studio-motion-v2-{name}.mp4"
tmp = out.replace(".mp4", "-picture.mp4")
run("npx", "hyperframes@0.8.164", "render", "--quality", "delivery", "--output", tmp, cwd=ROOT / "film")
# mux the measured master exactly (the renderer re-levels some mixes): copy picture, AAC 256 kb/s 48 kHz
run("ffmpeg", "-y", "-v", "error", "-i", str(ROOT / "film" / tmp), "-i", str(ROOT / "film/assets/audio/mix.wav"),
    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2",
    "-shortest", "-movflags", "+faststart", str(ROOT / "film" / out))
(ROOT / "film" / tmp).unlink()
v = run(py, "tools/verify.py", str(ROOT / "film" / out))
shutil.copy(ROOT / "analysis/verification.json", ROOT / f"analysis/verification-{name}.json")
shutil.copy(ROOT / "timeline.json", ROOT / f"analysis/timeline-{name}.json")
print(v[-1400:])
