"""Align the recording to the verse text → <student>/timings.js

Usage:
    python tools/align.py beeri-9a8bc7 [--model ivrit-ai/whisper-large-v3-turbo-ct2]

Steps:
 1. faster-whisper transcribes media/_full16k.wav with word timestamps (cached in media/_whisper.json).
 2. Both the transcript and the verse text are reduced to bare consonants (no nikud/ta'amim,
    final letters folded, ו/י dropped so ktiv male/haser don't matter, השם → אדני),
    and aligned character by character.
 3. Every text word gets the time of its matched characters; unmatched words are
    interpolated by letter count. Verse = first word start → next verse start.

Prints a per-verse match ratio; low ratios are worth fixing in the site's "מצב סנכרון".
"""
import argparse
import difflib
import json
import os
import re
import sys


FINALS = str.maketrans("ךםןףץ", "כמנפצ")
DROP = re.compile(r"[^א-ת]")


def bare(word):
    w = DROP.sub("", word).translate(FINALS)
    w = w.replace("יהוה", "אדני")
    return w.replace("ו", "").replace("י", "")


def load_js(path, var):
    s = open(path, encoding="utf-8").read()
    s = s[s.index("=", s.index(var)) + 1:].strip().rstrip(";")
    return json.loads(s)


def transcribe(wav, model_name, prompt):
    from faster_whisper import WhisperModel
    import wave
    import numpy as np
    with wave.open(wav) as w:                              # 16 kHz mono PCM from prepare_audio.py
        audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segs, _ = model.transcribe(audio, language="he", word_timestamps=True, vad_filter=False,
                               beam_size=5, initial_prompt=prompt, condition_on_previous_text=False)
    out = []
    for seg in segs:
        for w in seg.words or []:
            out.append({"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)})
        print(f"  {seg.end:7.1f}s  {seg.text.strip()[:70]}")
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("student")
    ap.add_argument("--model", default="ivrit-ai/whisper-large-v3-turbo-ct2")
    ap.add_argument("--retranscribe", action="store_true")
    a = ap.parse_args()

    verses = load_js(os.path.join(a.student, "data.js"), "window.VERSES")
    wav = os.path.join(a.student, "media", "_full16k.wav")
    cache = os.path.join(a.student, "media", "_whisper.json")

    if a.retranscribe or not os.path.exists(cache):
        plain = " ".join(DROP.sub("", w["t"]) for w in verses[0]["words"])
        hyp = transcribe(wav, a.model, plain)
        json.dump(hyp, open(cache, "w", encoding="utf-8"), ensure_ascii=False)
    hyp = json.load(open(cache, encoding="utf-8"))

    # hypothesis chars with a time each (spread evenly across the whisper word)
    hc, ht = [], []
    for h in hyp:
        b = bare(h["w"])
        for i, ch in enumerate(b):
            hc.append(ch)
            ht.append(h["s"] + (h["e"] - h["s"]) * (i + 0.5) / len(b))
    # reference chars labelled by (verse, word)
    rc, rlab, words = [], [], []
    for vi, v in enumerate(verses):
        for wi, w in enumerate(v["words"]):
            words.append((vi, wi, max(1, w["n"])))
            for ch in bare(w["t"]) or "_":
                rc.append(ch)
                rlab.append(len(words) - 1)

    sm = difflib.SequenceMatcher(None, "".join(rc), "".join(hc), autojunk=False)
    hits = {}                                             # word index -> [times]
    for blk in sm.get_matching_blocks():
        if blk.size < 2:
            continue
        for k in range(blk.size):
            hits.setdefault(rlab[blk.a + k], []).append(ht[blk.b + k])

    # monotone start time per word; interpolate gaps by letter weight
    n = len(words)
    st = [None] * n
    last = -1.0
    for i in range(n):
        if i in hits:
            t = min(hits[i])
            if t > last:
                st[i] = t
                last = t
    known = [i for i in range(n) if st[i] is not None]
    if not known:
        raise SystemExit("no alignment found — check the recording/text match")
    import wave
    with wave.open(wav) as w:
        audio_end = w.getnframes() / w.getframerate()
    end_t = max(hits[known[-1]]) if known[-1] in hits else audio_end
    for i in range(known[0]):                               # leading gap
        st[i] = st[known[0]]
    for a_, b_ in zip(known, known[1:] + [None]):
        hi = b_ if b_ is not None else n
        t0 = st[a_]
        t1 = st[b_] if b_ is not None else end_t
        wsum = sum(words[k][2] for k in range(a_, hi))
        acc = 0
        for k in range(a_, hi):
            st[k] = t0 + (t1 - t0) * acc / wsum
            acc += words[k][2]

    out = []
    for vi, v in enumerate(verses):
        idx = [k for k in range(n) if words[k][0] == vi]
        nxt = idx[-1] + 1
        v_end = st[nxt] if nxt < n else min(audio_end, max(end_t, hyp[-1]["e"]) + 0.8)
        ws = []
        for j, k in enumerate(idx):
            e = st[idx[j + 1]] if j + 1 < len(idx) else v_end
            ws.append({"s": round(st[k], 2), "e": round(e, 2)})
        ratio = sum(1 for k in idx if k in hits) / len(idx)
        print(f"{v['ref']:>7}  {st[idx[0]]:7.2f}–{v_end:7.2f}  matched {ratio:4.0%}" + ("   ← לבדוק" if ratio < 0.6 else ""))
        out.append({"start": round(st[idx[0]], 2), "end": round(v_end, 2), "words": ws})

    path = os.path.join(a.student, "timings.js")
    with open(path, "w", encoding="utf-8") as f:
        f.write("// auto-generated word/verse timings (aligned from recording via tools/align.py)\n")
        f.write("window.TIMINGS = " + json.dumps({"version": 1, "source": "whisper+align", "verses": out}) + ";\n")
    print("->", path)


if __name__ == "__main__":
    main()
