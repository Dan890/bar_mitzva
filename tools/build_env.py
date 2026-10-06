"""Per-verse pitch/energy features of the reference recording → <student>/original_env.js

Usage:
    python tools/build_env.py beeri-9a8bc7

Mirrors computeUserFrames() in app/app.js (YIN, 1024 window, 40 ms hop, 16 kHz) so the
student's recording is compared against features computed the same way.
Needs media/_full16k.wav (prepare_audio.py) and timings.js (align.py / sync mode export).
"""
import json
import os
import sys
import wave

import numpy as np

SR, WIN, THRESH = 16000, 1024, 0.15
HOP = round(SR * 0.04)
TAU_MIN, TAU_MAX = SR // 400, min(SR // 80, WIN - 1)
NEED = WIN + TAU_MAX


def load_js(path, var):
    s = open(path, encoding="utf-8").read()
    s = s[s.index("=", s.index(var)) + 1:].strip().rstrip(";")
    return json.loads(s)


def read_wav(path):
    with wave.open(path) as w:
        assert w.getframerate() == SR and w.getnchannels() == 1 and w.getsampwidth() == 2
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768


def frames(data):
    starts = np.arange(0, len(data) - NEED + 1, HOP)
    if not len(starts):
        return None
    X = np.stack([data[s:s + NEED] for s in starts])
    A = X[:, :WIN]
    fe = np.sqrt((A ** 2).mean(axis=1))
    nfft = 1 << (NEED + WIN).bit_length()
    R = np.fft.irfft(np.conj(np.fft.rfft(A, nfft)) * np.fft.rfft(X, nfft), nfft)[:, :TAU_MAX + 1]
    c = np.concatenate([np.zeros((len(X), 1)), np.cumsum(X ** 2, axis=1)], axis=1)
    taus = np.arange(TAU_MAX + 1)
    E0 = c[:, WIN:WIN + 1]
    Et = c[:, WIN + taus] - c[:, taus]
    d = E0 + Et - 2 * R
    d[:, 0] = 0
    run = np.cumsum(d[:, 1:], axis=1)
    dp = np.ones_like(d)
    dp[:, 1:] = np.where(run > 0, d[:, 1:] * taus[1:] / np.where(run > 0, run, 1), 1)

    f0s, fv = [], []
    for row in dp:
        best = -1
        below = np.nonzero(row[TAU_MIN:TAU_MAX] < THRESH)[0]
        if len(below):
            tau = TAU_MIN + below[0]
            while tau + 1 <= TAU_MAX and row[tau + 1] < row[tau]:
                tau += 1
            best = tau
        else:
            best = TAU_MIN + int(np.argmin(row[TAU_MIN:TAU_MAX + 1]))
        shift = 0.0
        if 1 < best < TAU_MAX:
            a, b, cc = row[best - 1], row[best], row[best + 1]
            den = a + cc - 2 * b
            shift = 0.5 * (a - cc) / den if den else 0.0
        per = best + shift
        f0 = SR / per if per > 0 else 0
        f0s.append(f0)
        fv.append(1 if (row[best] < THRESH and 80 <= f0 <= 400) else 0)
    f0s, fv = np.array(f0s), np.array(fv)
    fe = fe / (fe.max() or 1)
    voiced = f0s[fv == 1]
    med = float(np.median(voiced)) if len(voiced) >= 5 else 0.0
    if len(voiced) >= 5:
        fp = np.where(fv == 1, 12 * np.log2(np.maximum(f0s, 1e-9) / med), np.nan)
        idx = np.arange(len(fp))
        ok = ~np.isnan(fp)
        fp = np.interp(idx, idx[ok], fp[ok])              # same as interpNaN (flat ends)
    else:
        fp = np.zeros(len(f0s))
    return fe, fp, fv, med


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    student = sys.argv[1]
    data = read_wav(os.path.join(student, "media", "_full16k.wav"))
    tim = load_js(os.path.join(student, "timings.js"), "window.TIMINGS")
    out = []
    for v in tim["verses"]:
        s0, s1 = v["start"], v["end"]
        seg = data[int(s0 * SR):int(s1 * SR)]
        r = frames(seg)
        fe, fp, fv, med = r if r else (np.zeros(0), np.zeros(0), np.zeros(0, int), 0.0)
        out.append({
            "dur": round(s1 - s0, 2), "f0med": round(med, 1),
            "fp": [round(float(x), 2) for x in fp], "fv": [int(x) for x in fv],
            "fe": [round(float(x), 3) for x in fe],
            "words": [[round(w["s"] - s0, 2), round(w["e"] - s0, 2)] for w in v["words"]],
        })
    path = os.path.join(student, "original_env.js")
    with open(path, "w", encoding="utf-8") as f:
        f.write("// original: per-frame features (40ms) + per-word spans, for DTW alignment & scoring\n")
        f.write("window.ORIG_ENV = " + json.dumps({"version": 3, "points": 64, "hop": 0.04, "verses": out}) + ";\n")
    print(len(out), "verses ->", path)


if __name__ == "__main__":
    main()
