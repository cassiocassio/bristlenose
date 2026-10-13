"""Can a phrase someone SAID be tied to a piece of text that was ON SCREEN at that moment, at a place?

    python3 experiments/screen-text/anchor_spike.py <index.json> <transcript.txt> <quotes.json> <session_id> [--show]

The enabler for three surfaces in docs/design-screens.md: blue highlights on transcript phrases the
participant read off the screen, quotes pinned to the screen element they are about (the annotated
screen), and "what was on screen" context for a quote. Uses the screen-text index from
pipeline_spike.py (episodes: text, box, on-screen runs; chrome flagged sticky) and the session's raw
transcript and extracted quotes.

For each transcript segment (a paragraph, from its timecode to the next) and each quote, the
candidate screen lines are the non-sticky episodes on screen within ±4 s. A **match** is either a run
of 2+ consecutive words shared by the spoken text and one screen line, containing at least one
content word (4+ letters, not a stopword), or a single **distinctive** word: 6+ letters, not a
stopword, appearing in at most 3 distinct screen lines of the whole session. Both sides are folded
as search folds them. A matched screen line carries a box, so a match is also an anchor.

Prints aggregates. --show prints the matches themselves to stdout (participant speech and screen
text: private, never paste into tracked files).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from score import fold  # noqa: E402

TC = re.compile(r"^\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]\s*\[([^\]]+)\]\s*(?:\([^)]*\)\s*)?(.*)$")
WINDOW = 4.0
STOP = set("""a an and are as at be but by for from has have i if in into is it its just like me my no not of on
or our so that the their them then there they this to was we what when where which who will with you your
yeah okay ok um uh oh well right yes really think know want would could should can just also very there here
der die das und ist ein eine nicht mit für auf zu den dem des sie ich wir oder""".split())


def secs(a: str, b: str, c: str | None) -> int:
    return int(a) * 3600 + int(b) * 60 + int(c) if c else int(a) * 60 + int(b)


def tc_to_s(tc) -> float:
    if isinstance(tc, (int, float)):
        return float(tc)
    parts = [float(p) for p in str(tc).split(":")]
    return sum(p * 60 ** i for i, p in enumerate(reversed(parts)))


def content(tok: str) -> bool:
    return len(tok) >= 4 and tok not in STOP and not tok.isdigit()


def matches(spoken: str, lines: list[dict], rare: set[str]) -> list[tuple[str, dict]]:
    s = fold(spoken).split()
    out = []
    for ln in lines:
        t = fold(ln["text"]).split()
        best = ""
        # longest common contiguous run of tokens
        for i in range(len(s)):
            for j in range(len(t)):
                k = 0
                while i + k < len(s) and j + k < len(t) and s[i + k] == t[j + k]:
                    k += 1
                if k >= 2 and any(content(x) for x in s[i:i + k]) and k > len(best.split()):
                    best = " ".join(s[i:i + k])
        if not best:
            hit = [w for w in set(s) & set(t) if len(w) >= 6 and w not in STOP and w in rare]
            if hit:
                best = max(hit, key=len)
        if best:
            out.append((best, ln))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("index", type=Path)
    ap.add_argument("transcript", type=Path)
    ap.add_argument("quotes", type=Path)
    ap.add_argument("session")
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()
    index = json.loads(args.index.read_text())
    eps = [e for e in index["episodes"] if not e["sticky"]]
    share_start = min((r[0] for e in eps for r in e["runs"]), default=0)
    line_freq: Counter[str] = Counter()
    for e in eps:
        for w in set(fold(e["text"]).split()):
            line_freq[w] += 1
    rare = {w for w, c in line_freq.items() if c <= 3}

    def on_screen(a: float, b: float) -> list[dict]:
        return [e for e in eps if any(r[0] <= b + WINDOW and r[1] + index["every"] >= a - WINDOW for r in e["runs"])]

    segs = []
    for line in args.transcript.read_text(errors="replace").splitlines():
        if m := TC.match(line):
            segs.append([secs(*m.groups()[:3]), m.group(4), m.group(5)])
    for i, sg in enumerate(segs):
        sg.append(segs[i + 1][0] if i + 1 < len(segs) else sg[0] + 30)

    def report(label: str, items: list[tuple[float, float, str, str]]) -> None:
        during = [x for x in items if x[1] >= share_start]
        hits, phrase_hits, kinds = 0, 0, Counter()
        for a, b, who, text in during:
            ms = matches(text, on_screen(a, b), rare)
            if ms:
                hits += 1
                if any(len(p.split()) >= 2 for p, _ in ms):
                    phrase_hits += 1
                kinds.update("phrase" if len(p.split()) >= 2 else "word" for p, _ in ms)
                if args.show:
                    print(f"  [{label} {int(a)}s {who}] {text[:90]!r}")
                    for p, ln in ms[:4]:
                        print(f"      ↔ {p!r:30}  in {ln['text'][:60]!r}  box={[round(x, 2) for x in ln['box']]}")
        n = len(during)
        print(f"{label}: {n} during the share; {hits} ({100 * hits / max(n, 1):.0f}%) match on-screen text, "
              f"{phrase_hits} ({100 * phrase_hits / max(n, 1):.0f}%) by a 2+ word phrase; matches {dict(kinds)}")

    seg_items = [(a, b, who, text) for a, who, text, b in segs if who[:1] == "p"]
    report("participant segments", seg_items)
    qs = [q for q in json.loads(args.quotes.read_text()) if q.get("session_id") == args.session]
    q_items = [(tc_to_s(q["start_timecode"]), tc_to_s(q["end_timecode"]), q.get("participant_id", ""),
                q.get("verbatim_excerpt") or q["text"]) for q in qs]
    report("quotes", q_items)
    print(f"(share starts at {share_start:.0f}s; {len(eps)} non-sticky screen lines; {len(rare)} rare words)")


if __name__ == "__main__":
    main()
