"""Sequential GPU render queue (one Blender job at a time).

enqueue:  python tools/render_queue.py add <scene> [final|preview]   (snapshots the current .blend)
worker:   python tools/render_queue.py work                          (runs until queue empty for 30 min)
"""
import json, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
Q = ROOT / "renders/queue.json"
BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"


def load():
    return json.loads(Q.read_text()) if Q.exists() else []


def save(q):
    Q.parent.mkdir(parents=True, exist_ok=True)
    Q.write_text(json.dumps(q, indent=1))


def add(scene, mode="final"):
    snap = ROOT / f"blender/snap_{scene}.blend"
    shutil.copy2(ROOT / "blender/studio-motion-v2.blend", snap)
    q = load()
    q.append({"scene": scene, "mode": mode, "blend": str(snap), "status": "queued", "t_add": time.time()})
    save(q)
    print("queued", scene, mode)


def work():
    idle = 0
    while idle < 1800:
        q = load()
        job = next((j for j in q if j["status"] == "queued"), None)
        if not job:
            time.sleep(5); idle += 5; continue
        idle = 0
        job["status"] = "running"; job["t_start"] = time.time(); save(q)
        log = ROOT / f"logs/{job['scene']}_{job['mode']}.log"
        with open(log, "w", encoding="utf-8") as fh:
            rc = subprocess.call([BLENDER, "-b", job["blend"], "--python", str(ROOT / "blender/render_shot.py"),
                                  "--", job["scene"], job["mode"]], stdout=fh, stderr=subprocess.STDOUT)
        q = load()
        for j in q:
            if j["scene"] == job["scene"] and j["status"] == "running":
                j["status"] = "done" if rc == 0 else f"failed:{rc}"
                j["seconds"] = round(time.time() - job["t_start"], 1)
        save(q)
        print(job["scene"], job["mode"], "rc", rc, flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "add":
        add(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "final")
    else:
        work()
