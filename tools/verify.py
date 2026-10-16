"""Evidence for the DONE WHEN list: format, loudness, freezes, black frames, word-to-picture sync
and a contact sheet. Writes analysis/verification.json and review/contact-sheet.jpg."""
import json, re, subprocess, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TL = json.loads((ROOT / "timeline.json").read_text(encoding="utf-8"))
MP4 = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "film/renders/studio-motion-v2.mp4"
FPS = TL["fps"]


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def probe():
    r = sh(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt,nb_frames,channels,sample_rate:format=duration", "-of", "json", str(MP4)])
    return json.loads(r.stdout)


def frame(f, w=960, h=540, rgb=False):
    vf = "select=eq(n\,%d),scale=%d:%d" % (f, w, h)
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(MP4), "-vf", vf, "-vframes", "1", "-f", "rawvideo",
                        "-pix_fmt", "rgb24" if rgb else "gray", "-"], capture_output=True)
    a = np.frombuffer(r.stdout, np.uint8)
    return (a.reshape(h, w, 3) if rgb else a.reshape(h, w)).astype(float)


# screen regions (1920x1080) where each emphasised word appears
REGIONS = {"idea": (980, 440, 1300, 640), "vida": (560, 64, 1100, 200), "movimiento": (130, 200, 900, 360),
           "posibilidades": (900, 470, 1500, 610), "lugar": (110, 290, 600, 470), "dimensiones": (300, 520, 1640, 760)}


# the emphasised word's own colour (coral on ink, text-coral on light, violet 3D render)
WORD_RGB = {"idea": (255, 91, 58), "vida": (214, 58, 26), "movimiento": (214, 58, 26), "posibilidades": (214, 58, 26),
            "lugar": (214, 58, 26), "dimensiones": (110, 70, 240)}


def sync():
    """First frame where pixels of the word's own colour appear in its region (count > 40 px at 960x540)."""
    out = {}
    for k, (x0, y0, x1, y1) in REGIONS.items():
        on = TL["emphasis"][k]["onset_frame"]
        box = (slice(y0 // 2, y1 // 2), slice(x0 // 2, x1 // 2))
        target = np.array(WORD_RGB[k], float)
        tol = 70 if k == "dimensiones" else 55
        diffs = []
        for f in range(on - 6, on + 7):
            px = frame(f, rgb=True)[box]
            diffs.append(int((np.linalg.norm(px - target, axis=2) < tol).sum()))
        first = next((i for i, d in enumerate(diffs) if d > 40), None)
        lag = None if first is None else first - 6
        out[k] = {"onset_frame": on, "first_visual_change_frame": None if first is None else on - 6 + first,
                  "lag_frames": lag, "ok": lag is not None and -2 <= lag <= 2, "diffs": [round(d, 1) for d in diffs]}
    return out


def main():
    rep = {"file": str(MP4)}
    p = probe(); rep["probe"] = p
    v = next(s for s in p["streams"] if s["codec_type"] == "video"); a = next(s for s in p["streams"] if s["codec_type"] == "audio")
    dur = float(p["format"]["duration"])
    rep["format_ok"] = (v["width"], v["height"]) == (1920, 1080) and v["r_frame_rate"] == "30/1" and v["codec_name"] == "h264" \
        and v["pix_fmt"] == "yuv420p" and a["codec_name"] == "aac" and int(a["channels"]) == 2 and abs(dur - 25.0) <= 1 / FPS + 0.03
    nf = sh(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(MP4)]).stdout.strip()
    rep["frames"] = int(nf)
    eb = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", str(MP4), "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    rep["lufs"] = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", eb)[-1]); rep["true_peak_dbfs"] = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", eb)[-1])
    fz = sh(["ffmpeg", "-hide_banner", "-i", str(MP4), "-vf", "freezedetect=n=0.001:d=1", "-an", "-f", "null", "-"]).stderr
    rep["freezes"] = re.findall(r"freeze_start: ([\d.]+)", fz)
    bd = sh(["ffmpeg", "-hide_banner", "-i", str(MP4), "-vf", "blackdetect=d=0.1:pic_th=0.98:pix_th=0.03", "-an", "-f", "null", "-"]).stderr
    rep["black_segments"] = re.findall(r"black_start:([\d.]+)", bd)
    rep["sync"] = sync()
    rep["done_when"] = {
        "format_25s_1080p30_h264_aac": rep["format_ok"] and rep["frames"] == 750,
        "loudness_-14±0.5_LUFS": abs(rep["lufs"] + 14) <= 0.5,
        "true_peak_<=-1dBTP": rep["true_peak_dbfs"] <= -1.0,
        "no_freeze_>=1s": not rep["freezes"],
        "no_pure_black_frames_(luma<3%)": not rep["black_segments"],
        "emphasis_sync_within_2_frames": all(s["ok"] for s in rep["sync"].values()),
    }
    # contact sheet: one frame per second + act midpoints
    times = sorted(set([i + 0.5 for i in range(25)] + [round((a["start"] + a["end"]) / 2, 2) for a in TL["acts"]]))
    sel = "+".join(f"eq(n\\,{round(t * FPS)})" for t in times)
    (ROOT / "review").mkdir(exist_ok=True)
    cols = 6; rows = -(-len(times) // cols)
    sh(["ffmpeg", "-y", "-v", "error", "-i", str(MP4), "-vf", f"select='{sel}',scale=480:-1,drawtext=text='%{{pts\\:hms}}':x=8:y=8:fontsize=18:fontcolor=white:box=1:boxcolor=black@0.5,tile={cols}x{rows}",
        "-vsync", "vfr", "-frames:v", "1", str(ROOT / "review/contact-sheet.jpg")])
    (ROOT / "analysis/verification.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(rep["done_when"], indent=1)); print("frames", rep["frames"], "LUFS", rep["lufs"], "TP", rep["true_peak_dbfs"], "freezes", rep["freezes"], "black", rep["black_segments"])
    for k, s in rep["sync"].items(): print(f"  {k:14s} onset f{s['onset_frame']} first change f{s['first_visual_change_frame']} lag {s['lag_frames']}")


if __name__ == "__main__":
    main()
