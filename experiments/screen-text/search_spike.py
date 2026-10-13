"""Search a screen-text index the way the product would, and print result rows as the design doc sketches them.

    python3 experiments/screen-text/search_spike.py <index.json> <transcript.txt> "query" ["query" …]

Matching is the shipped rule (folded phrase from a word start, ``score.fold``). Sticky lines (chrome)
are not searched. A hit is a moment: one row per episode run, earliest first, carrying the on-screen
interval and the transcript paragraph being spoken at the run's start (the last segment starting at or
before it). Hits are grouped by the screen they appeared on (the index's text-diff moments), so
several matching lines on one screen are one row. Prints rows to stdout only: they carry participant
speech.
"""

from __future__ import annotations

import argparse
import bisect
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from score import fold  # noqa: E402

RETURN_S = 60.0
TC = re.compile(r"^\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]\s*\[([^\]]+)\]\s*(?:\([^)]*\)\s*)?(.*)$")


def secs(a: str, b: str, c: str | None) -> int:
    return int(a) * 3600 + int(b) * 60 + int(c) if c else int(a) * 60 + int(b)


def same_key(text: str) -> str:
    """The text for "is this the same line coming back?": folded, with a leading token of one or two
    characters dropped, because Vision reads a tab's favicon or a bullet as one (`b Enter postcode`,
    `23 Warenkorb - IKEA`). Only for grouping rows; the row still shows the text as read."""
    f = fold(text).split()
    while len(f) > 1 and len(f[0]) <= 2:
        f = f[1:]
    return " ".join(f)


def mmss(t: float) -> str:
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60:02d}:{t % 60:02d}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("index", type=Path)
    ap.add_argument("transcript", type=Path)
    ap.add_argument("queries", nargs="+")
    args = ap.parse_args()
    index = json.loads(args.index.read_text())
    segs = []
    for line in args.transcript.read_text(errors="replace").splitlines():
        if m := TC.match(line):
            segs.append((secs(*m.groups()[:3]), m.group(4), m.group(5)))
    eps = [(" " + fold(e["text"]) + " ", e) for e in index["episodes"] if not e["sticky"]]
    for q in args.queries:
        t0 = time.perf_counter()
        fq = " " + fold(q)
        rows = []
        for hay, e in eps:
            if fq in hay:
                for a, b in e["runs"]:
                    rows.append((a, b, e["text"]))
        rows.sort()
        # One row per screen a match APPEARED on: each run is keyed by the screen change (the index's
        # text-diff moments) at or before its start, and the matching lines that appear on one screen
        # share a row. Grouping by overlapping intervals instead chained eight minutes of different
        # screens into one row, measured; this keeps a row a place you can jump to.
        # And the same text coming back within RETURN_S rejoins its row: a form label that flickers
        # off under a popover listed six times otherwise, measured.
        by_screen: dict[float, list] = {}
        last_row: dict[str, list] = {}
        for a, b, text in rows:
            prev = last_row.get(same_key(text))
            if prev and a - prev[1] <= RETURN_S:
                prev[1] = max(prev[1], b)
                continue
            k = bisect.bisect_right(index["moments"], a) - 1
            key = index["moments"][k] if k >= 0 else a
            row = by_screen.setdefault(key, [a, b, text, []])
            row[0], row[1] = min(row[0], a), max(row[1], b)
            if text not in row[3]:
                row[3].append(text)
            last_row[same_key(text)] = row
        merged = sorted(by_screen.values())
        ms = (time.perf_counter() - t0) * 1000
        print(f'\n"{q}": {len(merged)} moments ({len(rows)} runs, {ms:.1f} ms over {len(eps)} episodes)')
        for a, b, text, texts in merged[:6]:
            said = [s for s in segs if s[0] <= a]
            s = said[-1] if said else None
            more = f"  (+{len(texts) - 1} more on screen)" if len(texts) > 1 else ""
            print(f"  {mmss(a)}–{mmss(b + index['every'])}  {text[:60]!r}{more}")
            if s:
                print(f"      {s[1]}, {mmss(s[0])}: {s[2][:90]!r}")


if __name__ == "__main__":
    main()
