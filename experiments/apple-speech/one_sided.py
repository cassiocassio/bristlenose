"""Dump both engines' words in every one-sided stretch, for reading by hand.

A one-sided stretch (analyse.py) is >= 8 s where one engine has >= 1 word a second
and the other almost none: speech one engine dropped, or text the other invented.
Reading them is how each is classified. The dump holds participants' speech, so
it is written under trial-runs/ (gitignored) and never quoted in public files.

    .venv/bin/python experiments/apple-speech/one_sided.py [speech|dictation]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from run_apple import OUT  # noqa: E402


def words_in(words, a, b):
    return " ".join(w["text"].strip() for w in words if a <= w["start"] < b)


def main(engine: str) -> int:
    rows = json.loads((OUT / f"results-{engine}.json").read_text())
    out = []
    for sid, row in rows.items():
        if "only_whisper_spans" not in row:
            continue
        a = json.loads((OUT / "apple" / f"{sid}.{engine}.json").read_text())
        w = json.loads((OUT / "whisper" / f"{sid}.whisper.json").read_text())
        for who, spans in (("WHISPER ONLY", row["only_whisper_spans"]),
                           ("APPLE ONLY", row["only_apple_spans"])):
            for s, e in spans:
                out.append(f"## {sid} {who} {s // 60}:{s % 60:02d}-{e // 60}:{e % 60:02d} ({e - s} s)")
                out.append("  W: " + words_in(w["words"], s - 2, e + 2))
                out.append("  A: " + words_in(a["words"], s - 2, e + 2))
                conf = [x["conf"] for x in w["words"] if s <= x["start"] < e]
                if conf:
                    out.append(f"  W mean confidence {sum(conf) / len(conf):.2f}")
    path = OUT / f"one-sided-{engine}.txt"
    path.write_text("\n".join(out), encoding="utf-8")
    print(path, len([x for x in out if x.startswith('##')]), "stretches")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "speech"))
