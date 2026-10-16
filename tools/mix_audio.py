"""Pre-mix the whole soundtrack: placed voice phrases, trimmed score with voice-keyed ducking,
event-aligned effects (each effect's transient peak is aligned to its event time), synthesized
accents, loudness normalisation to -14 LUFS and a look-ahead limiter to -1 dBTP.
Writes film/assets/audio/mix.wav and analysis/mix_report.json.
"""
import json, math
from pathlib import Path
import numpy as np
import soundfile as sf
import librosa, pyloudnorm
from scipy.signal import butter, sosfilt, resample_poly

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "film/assets/audio/src"          # score + effects from the earlier production (ElevenLabs)
TL = json.loads((ROOT / "timeline.json").read_text(encoding="utf-8"))
VOICE = json.loads((ROOT / "voice.json").read_text(encoding="utf-8"))
SFX2 = ROOT / "film/assets/audio/sfx2"
SR = 48000
N = int(TL["duration"] * SR)
rng = np.random.default_rng(TL["seed"])
db = lambda x: 10 ** (x / 20)


def place(bus, x, t, gain_db=0.0, align_peak=False):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    off = int(np.argmax(np.abs(x).sum(1))) if align_peak else 0
    s = int(round(t * SR)) - off
    a, b = max(s, 0), min(s + len(x), N)
    if b > a:
        bus[a:b] += x[a - s:b - s] * db(gain_db)


def sfx(name, rate=1.0):
    x, sr = sf.read(SRC / f"{name}.wav")
    assert sr == SR
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    if rate != 1.0:
        up, down = 100, int(round(100 * rate))
        x = np.stack([resample_poly(x[:, c], up, down) for c in range(2)], 1)
    return x / (np.abs(x).max() + 1e-9) * db(-6)          # every effect normalised to -6 dBFS peak


def sfx2(name):
    """ElevenLabs effects generated for V2 (warm, no bells), normalised to -6 dBFS peak."""
    x, _ = librosa.load(SFX2 / f"{name}.mp3", sr=SR, mono=False)
    x = np.stack([x, x], 1) if x.ndim == 1 else x.T
    return x / (np.abs(x).max() + 1e-9) * db(-6)


def env(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(t / max(a, 1e-4), 1.0) * np.exp(-np.maximum(t - a, 0) / d)


def tick(freq=3200, dur=0.004):
    n = int(0.06 * SR); t = np.arange(n) / SR
    return np.sin(2 * np.pi * freq * t) * env(n, 0.0005, dur)


def sub_hit(f0=110, f1=45, drop=0.12, dur=0.7):
    n = int(dur * SR); t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / (drop / 3))
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.tanh(1.6 * np.sin(ph)) * env(n, 0.003, dur / 4)


def bell(freqs=(1568, 2093, 3136, 4186), dur=1.6):
    n = int(dur * SR); t = np.arange(n) / SR
    y = sum(np.sin(2 * np.pi * f * t) * np.exp(-t / (dur / (1 + k))) / (1 + k) for k, f in enumerate(freqs))
    return y * env(n, 0.004, 10.0)


def noise_swell(dur, lo=300, hi=6000, curve=2.0):
    n = int(dur * SR)
    w = rng.standard_normal(n)
    out = np.zeros(n); seg = 2400
    for i in range(0, n, seg):
        p = i / n
        fc = lo * (hi / lo) ** p
        sos = butter(2, [max(fc * 0.6, 40), min(fc * 1.6, 20000)], btype="band", fs=SR, output="sos")
        out[i:i + seg] = sosfilt(sos, w[i:i + seg + 0])[:len(out[i:i + seg])]
    return out * (np.linspace(0, 1, n) ** curve)


def main():
    # ---------------- voice
    vsrc = VOICE["source"]
    vo_src, _ = librosa.load(vsrc if Path(vsrc).is_absolute() else ROOT / vsrc, sr=SR, mono=True)
    hp = butter(2, 90, btype="high", fs=SR, output="sos")
    vo = np.zeros(N)
    for p in TL["phrases"]:
        seg = vo_src[int(p["src_in"] * SR):int(p["src_out"] * SR)].copy()
        f = int(0.012 * SR); seg[:f] *= np.linspace(0, 1, f); seg[-f:] *= np.linspace(1, 0, f)
        s = int(round(p["start"] * SR))
        vo[s:s + len(seg)] += seg[:N - s]
    vo = sosfilt(hp, vo)
    vo_st = np.stack([vo, vo], 1)

    # ---------------- music, trimmed onto the 0.5 s grid, ducked by the voice
    mus, _ = librosa.load(SRC / "score.wav", sr=SR, mono=False)
    mus = mus.T[int(TL["score_trim"] * SR):]
    music = np.zeros((N, 2)); music[:len(mus)] = mus[:N]
    win = int(0.01 * SR)
    rms = np.sqrt(np.convolve(vo ** 2, np.ones(win) / win, mode="same"))
    gate = (20 * np.log10(rms + 1e-9) > -45).astype(float)
    a_att, a_rel = math.exp(-1 / (0.06 * SR)), math.exp(-1 / (0.28 * SR))
    g = np.zeros(N); y = 0.0
    for i in range(N):
        c = a_att if gate[i] > y else a_rel
        y = c * y + (1 - c) * gate[i]; g[i] = y
    duck = 1 - (1 - db(-9)) * g
    music *= duck[:, None]

    # ---------------- effects
    fx = np.zeros((N, 2))
    E = TL["events"]
    for t in E["caret_blinks"]:
        place(fx, tick(), t, -20)
    place(fx, sfx("notification"), TL["emphasis"]["idea"]["start"] + 0.04, -12, align_peak=True)
    place(fx, sfx("airy-whoosh"), 2.74, -8, align_peak=True)
    place(fx, noise_swell(0.4, 600, 9000, 2.5), 2.68, -24)
    for t in E["swatch_clicks"]:
        place(fx, sfx("publish-click", 1.15), t, -9, align_peak=True)
    place(fx, sfx("publish-click"), E["play_click"], -5, align_peak=True)
    place(fx, sfx("airy-whoosh", 1.35), 6.72, -15, align_peak=True)
    m = sfx("marker"); m = m[: int(1.55 * SR)]; m[-int(0.12 * SR):] *= np.linspace(1, 0, int(0.12 * SR))[:, None]
    place(fx, m, E["stroke_start"] + 0.05, -15)
    place(fx, noise_swell(1.0, 200, 8000, 3.0), 8.0, -17)
    place(fx, sub_hit(), 9.0, -5)
    place(fx, sfx("paper-lift"), 9.12, -11, align_peak=True)
    place(fx, sfx("airy-whoosh", 0.85), 10.32, -7, align_peak=True)
    place(fx, sfx("folder-open"), E["split"] + 0.02, -8, align_peak=True)
    place(fx, sub_hit(90, 40, 0.1, 0.5), E["split"], -13)
    # V2: the bright C6-G6-C7 bell and the 12-tick spray read as shrill; a warm generated reveal replaces them
    place(fx, sfx2("grid-reveal"), E["grid"] - 0.25, -9)
    snap = sfx2("snap-soft")
    for k, t in enumerate(E["snaps"]):
        last = k == len(E["snaps"]) - 1
        place(fx, snap, t, -6 if last else -13, align_peak=True)
    place(fx, sub_hit(70, 40, 0.08, 0.45), E["snaps"][-1], -13)
    place(fx, sfx("airy-whoosh", 0.8), 16.02, -14, align_peak=True)
    place(fx, tick(1800, 0.006), 16.5, -16)
    for t in E["montage"]:
        place(fx, sub_hit(120, 55, 0.05, 0.25), t, -12)
        place(fx, sfx("publish-click", 1.0), t, -13, align_peak=True)
        place(fx, tick(2600, 0.004), t + 0.5, -19)
    place(fx, noise_swell(0.6, 400, 7000, 2.0), 20.42, -24)
    place(fx, sfx("airy-whoosh", 0.9), E["dimensiones"] + 0.05, -10, align_peak=True)
    place(fx, sfx("umbrella-open"), E["dimensiones"] + 0.12, -14, align_peak=True)
    place(fx, sfx2("logo-pad"), E["lockup"] - 0.05, -8)
    place(fx, sfx2("logo-sting"), E["lockup"] - 0.05, -12)

    mix = vo_st * db(0) + music * db(-3) + fx * db(0)
    # global tail fade so the score resolves at 25.000 s
    a, b = int(23.9 * SR), N
    curve = 0.5 * (1 + np.cos(np.linspace(0, np.pi, b - a)))       # V2: 1.1 s cosine fade, no hard stop
    mix[a:b] *= curve[:, None]

    meter = pyloudnorm.Meter(SR)
    lufs0 = meter.integrated_loudness(mix)

    def limit(x, ceil_db=-1.5):   # -1.5 leaves room for AAC overshoot under the -1.0 dBTP spec
        """Look-ahead limiter on a 4x oversampled peak estimate (true-peak proxy)."""
        ceil = db(ceil_db)
        over = np.abs(resample_poly(x, 4, 1, axis=0)).max(1).reshape(-1, 4).max(1)[:N]
        need = np.minimum(1.0, ceil / np.maximum(over, 1e-9))
        la = int(0.005 * SR)
        gmin = np.array([need[max(0, i - la):i + la].min() for i in range(0, N, 48)])
        gl = np.interp(np.arange(N), np.arange(0, N, 48), gmin)
        rel = math.exp(-1 / (0.08 * SR)); g = np.empty(N); y = 1.0
        for i in range(N):
            y = gl[i] if gl[i] < y else rel * y + (1 - rel) * gl[i]; g[i] = y
        return x * g[:, None], g

    # gain -> limit, repeated; the limiter is always the LAST stage so the ceiling holds
    gain_db, gs = 0.0, np.ones(N)
    base = mix * db(-14.0 - lufs0)
    for _ in range(5):
        mix, gs = limit(base * db(gain_db))
        err = -14.0 - meter.integrated_loudness(mix)
        if abs(err) <= 0.15:
            break
        gain_db += err
    out = ROOT / "film/assets/audio/mix.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(out, mix.astype(np.float32), SR, subtype="PCM_24")
    sf.write(ROOT / "film/assets/audio/voice-only.wav", vo_st.astype(np.float32) * 0.9, SR, subtype="PCM_24")
    # waveform peaks for the "Sonido" card (64 bars over the whole film)
    mono = np.abs(mix).mean(1)
    bars = [float(mono[i * N // 64:(i + 1) * N // 64].max()) for i in range(64)]
    mx = max(bars)
    (ROOT / "film/peaks.js").write_text("window.PEAKS = " + json.dumps([round(b / mx, 3) for b in bars]) + ";\n")
    rep = {"lufs_before_norm": round(lufs0, 2), "lufs_final_estimate": round(meter.integrated_loudness(mix), 2),
           "limiter_min_gain_db": round(20 * np.log10(gs.min()), 2)}
    (ROOT / "analysis/mix_report.json").write_text(json.dumps(rep, indent=1))
    print(rep)


if __name__ == "__main__":
    main()
