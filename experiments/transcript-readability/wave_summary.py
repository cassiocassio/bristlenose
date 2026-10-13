"""Summarise prompt trials per recording, for deciding which prompt ships.

Compares today's baseline (no prompt, nets on) with each prompted run on the
numbers that decided batch 1: sentence ends, longest unpunctuated run, words,
30-second blocks where speech vanished, inaudible gaps, prompt words per 100
words (a rise means the prompt is leaking into the text), and the language
Whisper detected (a wrong one hands the audio the wrong prompt).

    .venv/bin/python experiments/transcript-readability/wave_summary.py ROOT ID [ID ...]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BASELINES = ("none+net+inaudible", "none+net", "none")
PROMPTED = ("prompt+net+inaudible", "prompt-v2+net+inaudible")


def _words(text: str) -> list[str]:
    return [w for w in re.sub(r"[^\w\s']", " ", text.casefold()).split() if w]


def _blocks(segs: list[dict]) -> dict[int, float]:
    """Words per 30-second block, each segment's words spread over the time it
    covers. Giving them all to the block a segment starts in made prompted runs,
    which come back as fewer, longer segments, look as if they lost the blocks
    after (found in review, 13 Oct 2026)."""
    out: dict[int, float] = {}
    for s in segs:
        if s.get("inaudible"):
            continue
        n = len(s["text"].split())
        a, b = float(s["start"]), max(float(s["end"]), float(s["start"]) + 0.01)
        k = int(a // 30)
        while k * 30 < b:
            share = (min(b, (k + 1) * 30) - max(a, k * 30)) / (b - a)
            out[k] = out.get(k, 0.0) + n * share
            k += 1
    return out


def summarise(root: Path, sid: str) -> list[str]:
    trials = root / "trials"
    base = next((json.loads((trials / f"{sid}.{c}.json").read_text())
                 for c in BASELINES if (trials / f"{sid}.{c}.json").exists()), None)
    if base is None:
        return [f"{sid}: no baseline"]
    bb = _blocks(base["segments"])
    rows = [f"{sid:6} base  det={base['detected']:3} words={base['metrics']['words']:5} "
            f"sent={base['metrics']['sentences']:4} run={base['metrics']['longest_unpunctuated']:4}"]
    for cond in PROMPTED:
        path = trials / f"{sid}.{cond}.json"
        if not path.exists():
            continue
        r = json.loads(path.read_text())
        m = r["metrics"]
        nb = _blocks(r["segments"])
        lost = sum(1 for b, n in bb.items() if n >= 20 and nb.get(b, 0) < n / 4)
        gaps = [s for s in r["segments"] if s.get("inaudible")]
        pw = set(_words(r.get("prompt") or ""))
        def leak(segs: list[dict]) -> float:
            ws = [w for s in segs for w in _words(s["text"])]
            return 100 * sum(w in pw for w in ws) / max(1, len(ws))
        rows.append(
            f"{'':6} {'v1' if cond.startswith('prompt+') else 'v2':4}  det={r['detected']:3} "
            f"words={m['words']:5} sent={m['sentences']:4} run={m['longest_unpunctuated']:4} "
            f"lost={lost:2} gaps={len(gaps)}/{round(sum(s['end'] - s['start'] for s in gaps))}s "
            f"leak={leak(base['segments']):.1f}->{leak(r['segments']):.1f}"
        )
    return rows


if __name__ == "__main__":
    root = Path(sys.argv[1])
    for sid in sys.argv[2:]:
        print("\n".join(summarise(root, sid)))
