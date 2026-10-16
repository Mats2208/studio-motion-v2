"""Encode every finished Blender PNG sequence into a clip the composition can place,
export the grid-tile stills, and write film/snaps.js. Opaque shots -> H.264 CRF 12 yuv420p;
alpha shots -> VP9 yuva420p WebM (HyperFrames extracts alpha sources as PNG)."""
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TL = json.loads((ROOT / "timeline.json").read_text(encoding="utf-8"))
OUT = ROOT / "film/assets/renders"
OUT.mkdir(parents=True, exist_ok=True)
STILLS = {"b1_cursor": 34, "b2_torus": 110, "b3_ribbon": 30, "b4_question": 30, "b5_pieces": 1, "b6_wire": 30}


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[-2000:]); sys.exit(1)


only = set(sys.argv[1:])
for s in TL["shots"]:
    sid = s["id"]
    if only and sid not in only:
        continue
    src = ROOT / "renders" / sid
    n = len(list(src.glob("f_*.png")))
    if n != s["frames"]:
        print(f"skip {sid}: {n}/{s['frames']} frames"); continue
    pat = str(src / "f_%04d.png")
    if s["alpha"]:
        dst = OUT / f"{sid}.webm"
        run(["ffmpeg", "-y", "-v", "error", "-framerate", "30", "-start_number", "1", "-i", pat, "-c:v", "libvpx-vp9",
             "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "16", "-row-mt", "1", "-auto-alt-ref", "0", str(dst)])
    else:
        dst = OUT / f"{sid}.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-framerate", "30", "-start_number", "1", "-i", pat, "-c:v", "libx264",
             "-preset", "slow", "-crf", "12", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dst)])
    if sid in STILLS:
        run(["ffmpeg", "-y", "-v", "error", "-i", str(src / f"f_{STILLS[sid]:04d}.png"), "-vf", "scale=768:-2",
             "-q:v", "3", str(OUT / f"{sid}_still.jpg")])
    print("encoded", sid, n, "frames ->", dst.name)

snaps = ROOT / "renders/b5_snaps.json"
if snaps.exists():
    (ROOT / "film/snaps.js").write_text("window.SNAPS = " + snaps.read_text() + ";\n")
