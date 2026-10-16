"""Minimal ElevenLabs client. The key comes from ELEVENLABS_API_KEY (or the file named by ELEVENLABS_KEY_FILE) at call time and is never printed,
logged or written into the project. Only api.elevenlabs.io receives it.

  python tools/eleven.py account
  python tools/eleven.py voices "<search>"            # shared library, female, Spanish
  python tools/eleven.py tts <voice_id> <out.mp3> "<text>" [stability style speed]   (+ <out>.json alignment)
  python tools/eleven.py sfx <out.mp3> <seconds> "<prompt>"
  python tools/eleven.py add <public_owner_id> <voice_id> "<name>"
"""
import base64, json, os, sys
from pathlib import Path
import urllib.request, urllib.error

KEY_FILE = Path(os.environ.get("ELEVENLABS_KEY_FILE", ""))   # or set ELEVENLABS_API_KEY directly
API = "https://api.elevenlabs.io"


def key():
    if os.environ.get("ELEVENLABS_API_KEY"):
        return os.environ["ELEVENLABS_API_KEY"]
    raw = KEY_FILE.read_text(encoding="utf-8", errors="ignore").strip()
    # the file may contain "label: value" — keep the token-looking part
    for tok in raw.replace("=", " ").replace(":", " ").split():
        if len(tok) >= 30:
            return tok
    raise SystemExit("no key found in key file")


def req(method, path, body=None, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(API + path, data=data, method=method,
                               headers={"xi-api-key": key(), "Content-Type": "application/json", "Accept": "*/*"})
    try:
        with urllib.request.urlopen(r, timeout=180) as resp:
            b = resp.read()
            return b if raw else json.loads(b)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code} {path}: {e.read()[:400].decode(errors='ignore')}")


def account():
    s = req("GET", "/v1/user/subscription")
    print(json.dumps({k: s.get(k) for k in ("tier", "character_count", "character_limit", "voice_limit",
                                             "voice_slots_used", "professional_voice_limit", "can_use_instant_voice_cloning",
                                             "next_character_count_reset_unix")}, indent=1))


def voices(search):
    q = urllib.parse.urlencode({"page_size": 60, "gender": "female", "language": "es", "search": search})
    d = req("GET", f"/v1/shared-voices?{q}")
    for v in d.get("voices", []):
        print(json.dumps({k: v.get(k) for k in ("public_owner_id", "voice_id", "name", "accent", "age", "descriptive",
                                                 "use_case", "locale", "cloned_by_count", "preview_url")}, ensure_ascii=False))


def tts(voice_id, out, text, stability=0.38, style=0.45, speed=1.0):
    body = {"text": text, "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": float(stability), "similarity_boost": 0.8, "style": float(style),
                               "use_speaker_boost": True, "speed": float(speed)}, "seed": 251016}
    d = req("POST", f"/v1/text-to-speech/{voice_id}/with-timestamps?output_format=mp3_44100_128", body)
    Path(out).write_bytes(base64.b64decode(d["audio_base64"]))
    Path(out).with_suffix(".json").write_text(json.dumps(d.get("alignment"), ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", out)


def sfx(out, seconds, prompt):
    b = req("POST", "/v1/sound-generation", {"text": prompt, "duration_seconds": float(seconds), "prompt_influence": 0.55}, raw=True)
    Path(out).write_bytes(b); print("wrote", out, len(b), "bytes")


def add(owner, voice_id, name):
    d = req("POST", f"/v1/voices/add/{owner}/{voice_id}", {"new_name": name})
    print(json.dumps(d))


if __name__ == "__main__":
    import urllib.parse
    cmd, *a = sys.argv[1:]
    {"account": account, "voices": voices, "tts": tts, "sfx": sfx, "add": add}[cmd](*a)
