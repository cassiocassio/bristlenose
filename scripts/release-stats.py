#!/usr/bin/env python3
"""release-stats.py — what the release ledgers already know, made readable.

Every run under `.release/` records each step's attempts and outcomes, and each
failed attempt leaves a log. The data to answer "how often does this class
recur?" has been there since 0.28.0 — but answering it on 23 Sep 2026 meant
hand-writing a throwaway script and re-reading 25 logs, which is how a failure
class reaches its fifth occurrence before anyone counts it.

Read-only. Classifies through `verdict_failure_class` in release.sh, so there is
ONE taxonomy: the driver stamps it into the ledger at failure time, and this
re-derives it for runs that predate the stamp. A second copy here would drift
from the one that ships, and the drift would be invisible.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_CLASSIFY = 'RELEASE_LIB=1 . "$0" 2>/dev/null; verdict_failure_class "$1"'


def classify(log: Path) -> str:
    """Ask release.sh, so the taxonomy has exactly one definition."""
    out = subprocess.run(
        ["bash", "-c", _CLASSIFY, str(ROOT / "scripts" / "release.sh"), str(log)],
        capture_output=True, text=True,
    )
    return out.stdout.strip() or "unknown"


def _attempts(events: Path) -> tuple[int, list[tuple[str, str]]]:
    """(attempts, [(step, attempt)]) for the failures in one run's ledger."""
    tries, fails, last = 0, [], {}
    for line in events.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue           # a torn line is not a step outcome
        step, status, detail = e.get("step"), e.get("status"), e.get("detail") or ""
        if status == "running":
            if m := re.search(r"attempt (\d+)", detail):
                last[step] = m.group(1)
                tries += 1
        elif status == "fail":
            fails.append((step, last.get(step, "?")))
    return tries, fails


def main(argv: list[str]) -> int:
    runs = sorted(p for p in (ROOT / ".release").glob("*/events.jsonl"))
    if not runs:
        print("no runs under .release/ yet")
        return 0

    classes: Counter[str] = Counter()
    per_class_runs: dict[str, set[str]] = {}
    total_tries = total_fails = clean = 0

    print(f"  {'release':<9} {'tries':>5} {'failures':>9}  classes")
    for events in runs:
        version = events.parent.name
        tries, fails = _attempts(events)
        total_tries += tries
        total_fails += len(fails)
        if not fails:
            clean += 1
        here: Counter[str] = Counter()
        for step, attempt in fails:
            cls = classify(events.parent / "logs" / f"{step}.{attempt}.log")
            classes[cls] += 1
            here[cls] += 1
            per_class_runs.setdefault(cls, set()).add(version)
        shown = " ".join(f"{c}×{n}" if n > 1 else c for c, n in here.most_common())
        print(f"  {version:<9} {tries:>5} {len(fails):>9}  {shown or '—'}")

    print(f"\n  {len(runs)} runs · {total_tries} attempts · {total_fails} failures"
          f" · {clean} clean ({100 * clean // max(len(runs), 1)}%)")

    print("\n  failure class          count   releases   recurring?")
    for cls, n in classes.most_common():
        seen = len(per_class_runs[cls])
        # Recurrence across RELEASES is the signal, not raw count: three
        # failures in one run is one bad night, three across three runs is a
        # class that will happen again.
        flag = "← recurring" if seen > 1 else ""
        print(f"  {cls:<22} {n:>5}   {seen:>8}   {flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
