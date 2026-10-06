"""Build a student's data.js (cantillated verses) from Sefaria.

Usage:
    python tools/build_data.py "Exodus 27:20-30:10" beeri-3f9a1c/data.js

Text: "Miqra according to the Masorah" (nikud + ta'amei hamikra).
Where the Masorah text carries a footnote with the reading of Ashkenazi/Sefardi
books, that reading is used (that is what the boy reads from).
"""
import json
import re
import sys
import urllib.parse
import urllib.request

VERSION = "hebrew|Miqra according to the Masorah"
LETTERS = re.compile(r"[א-ת]")
GEMATRIA = [(400, "ת"), (300, "ש"), (200, "ר"), (100, "ק"), (90, "צ"), (80, "פ"),
            (70, "ע"), (60, "ס"), (50, "נ"), (40, "מ"), (30, "ל"), (20, "כ"),
            (10, "י"), (9, "ט"), (8, "ח"), (7, "ז"), (6, "ו"), (5, "ה"), (4, "ד"),
            (3, "ג"), (2, "ב"), (1, "א")]


def heb_num(n):
    if n == 15:
        return "טו"
    if n == 16:
        return "טז"
    out = ""
    for v, ch in GEMATRIA:
        while n >= v:
            out += ch
            n -= v
    return out


def fetch(ref):
    url = ("https://www.sefaria.org/api/v3/texts/" + urllib.parse.quote(ref.replace(" ", "."))
           + "?version=" + urllib.parse.quote(VERSION))
    with urllib.request.urlopen(url) as r:
        d = json.load(r)
    return d


def clean(s):
    # footnote with the Ashkenazi/Sefardi reading replaces the preceding word
    s = re.sub(r"(\S+)<sup[^>]*>\*</sup><i class=\"footnote\">\(בספרי ספרד ואשכנז ([^)]+)\)</i>",
               r"\2", s)
    s = re.sub(r"<sup.*?</sup>|<i class=\"footnote\">.*?</i>", "", s)
    s = re.sub(r"\{[פס]\}|<br>", " ", s)            # petuchah / setumah markers
    s = re.sub(r"<[^>]+>", "", s)                   # remaining tags (kq-trivial, paseq <b>)
    s = s.replace("&thinsp;", "").replace("&nbsp;", " ")
    s = re.sub(r"\s*׀", " ׀", s)     # paseq sticks to the previous word
    return re.sub(r"\s+", " ", s).strip()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ref, out = sys.argv[1], sys.argv[2]
    d = fetch(ref)
    text = d["versions"][0]["text"]
    # sections: [[ch, v], ...] ; text is nested per chapter when range spans chapters
    m = re.match(r".*?(\d+):(\d+)", ref)
    ch, v = int(m.group(1)), int(m.group(2))
    chapters = text if text and isinstance(text[0], list) else [text]
    multi = len(chapters) > 1
    verses = []
    for ci, chap in enumerate(chapters):
        if ci > 0:
            ch, v = ch + 1, 1
        for s in chap:
            words = [{"t": w, "n": len(LETTERS.findall(w))} for w in clean(s).split(" ")]
            label = (heb_num(ch) + ":" + heb_num(v)) if multi else heb_num(v)
            verses.append({"ref": label, "words": words})
            v += 1
    with open(out, "w", encoding="utf-8") as f:
        f.write("// " + ref + " — cantillated (nikud + ta'amei hamikra), Miqra according to the Masorah\n")
        f.write("window.VERSES = " + json.dumps(verses, ensure_ascii=False) + ";\n")
    print(len(verses), "verses ->", out)


if __name__ == "__main__":
    main()
