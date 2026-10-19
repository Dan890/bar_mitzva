"""Extra reference readers → <aliyah>/refs_env.js (features only, the audio is not deployed)

Usage:
    python tools/build_refs.py binyamin "בנימין אפלבוים" ref16k.wav ref_whisper.json beeri-9a8bc7 beeri-9a8bc7/a2 beeri-9a8bc7/a3

The recording may hold several aliyot in a row (a full parsha reading, cut to the part needed):
the text of all the given aliyot is aligned to it at once, then every verse gets the same
pitch/energy features as original_env.js. The student's recording is scored against the
original and against every reference, and the closest one counts — so a reading that is right
but follows another (correct) reader's melody is not marked wrong.

ref16k.wav: 16 kHz mono PCM. ref_whisper.json: transcript cache, created on first run.
Verses that did not align well (< 60% of words recognised) are left out for that reader.
"""
import json
import os
import sys

from align import align_words, load_js, transcribe, DROP
from build_env import SR, frames, read_wav

MIN_MATCH = 0.6


def env_of(data, v):
    s0, s1 = v["start"], v["end"]
    r = frames(data[int(s0 * SR):int(s1 * SR)])
    if not r:
        return None
    fe, fp, fv, med = r
    return {
        "dur": round(s1 - s0, 2), "f0med": round(med, 1),
        "fp": [round(float(x), 2) for x in fp], "fv": [int(x) for x in fv],
        "fe": [round(float(x), 3) for x in fe],
        "words": [[round(w["s"] - s0, 2), round(w["e"] - s0, 2)] for w in v["words"]],
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rid, name, wav, cache, dirs = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:]
    per = [load_js(os.path.join(d, "data.js"), "window.VERSES") for d in dirs]
    verses = [v for vs in per for v in vs]
    if not os.path.exists(cache):
        plain = " ".join(DROP.sub("", w["t"]) for w in verses[0]["words"])
        json.dump(transcribe(wav, "ivrit-ai/whisper-large-v3-turbo-ct2", plain),
                  open(cache, "w", encoding="utf-8"), ensure_ascii=False)
    hyp = json.load(open(cache, encoding="utf-8"))
    data = read_wav(wav)

    tim, ratios = align_words(verses, hyp, len(data) / SR, tail=0.6)
    k = 0
    for d, vs in zip(dirs, per):
        envs = []
        for _ in vs:
            envs.append(env_of(data, tim[k]) if ratios[k] >= MIN_MATCH else None)
            k += 1
        path = os.path.join(d, "refs_env.js")
        refs = load_js(path, "window.REF_ENVS") if os.path.exists(path) else []
        refs = [r for r in refs if r["id"] != rid] + [{"id": rid, "name": name, "verses": envs}]
        with open(path, "w", encoding="utf-8") as f:
            f.write("// extra reference readers: per-verse features like original_env.js (tools/build_refs.py)\n")
            f.write("window.REF_ENVS = " + json.dumps(refs, ensure_ascii=False) + ";\n")
        print(f"{d}: {sum(e is not None for e in envs)}/{len(envs)} verses -> {path}")


if __name__ == "__main__":
    main()
