#!/usr/bin/env python3
"""Measure the transcript-source mix across Bristlenose project outputs.

Reads ONLY structural metadata from
    <output_dir>/.bristlenose/intermediate/session_segments.json
namely each segment's ``source`` field (written by s03/s04/s05: "srt", "vtt",
"docx", "mlx-whisper", "faster-whisper") plus session and segment counts.
It never reads, prints or aggregates transcript text, speaker labels or names.

The serve-mode SQLite DB is NOT a valid source for this: importer.py writes the
constant source="transcript" on every row.

Usage:
    python3 scripts/measure-transcript-sources.py ROOT [ROOT ...]

Reports both denominators. Sessions (= one recording) is the right unit for
attribution questions; segment counts are biased because a platform .vtt yields
far fewer, longer segments than Whisper does for the same recording.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

PLATFORM = {"srt", "vtt", "docx"}                          # arrived diarised
LOCAL_ASR = {"mlx-whisper", "faster-whisper", "whisper"}   # labels inferred
EXCLUDE_SUBSTR = ("Code-backups", "node_modules")


def find_session_segments(roots: list[Path]) -> list[Path]:
    out: list[Path] = []
    tail = os.path.join(".bristlenose", "intermediate")
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            if "node_modules" in dirnames:
                dirnames.remove("node_modules")
            if "session_segments.json" in filenames and dirpath.endswith(tail):
                p = Path(dirpath) / "session_segments.json"
                if not any(x in str(p) for x in EXCLUDE_SUBSTR):
                    out.append(p)
    return sorted(out)


def main() -> None:
    roots = [Path(a).expanduser() for a in sys.argv[1:]] or [Path.cwd()]
    files = find_session_segments(roots)

    seg_counts: Counter[str] = Counter()
    ses_bucket: Counter[str] = Counter()
    n_sessions = 0

    print(f"{'proj':<5} {'sessions':>8} {'segments':>9}  source distribution")
    for i, f in enumerate(files):
        label = chr(ord("A") + i) if i < 26 else f"P{i}"
        data = json.loads(f.read_text(encoding="utf-8"))
        c: Counter[str] = Counter()
        for _sid, segs in data.items():
            n_sessions += 1
            kinds = {s.get("source", "") for s in segs}
            ses_bucket[
                "platform" if kinds & PLATFORM
                else "local" if kinds & LOCAL_ASR
                else "empty"
            ] += 1
            for s in segs:
                c[s.get("source", "") or "(empty)"] += 1
        seg_counts.update(c)
        dist = ", ".join(f"{k}={v}" for k, v in sorted(c.items(), key=lambda kv: -kv[1]))
        print(f"{label:<5} {len(data):>8} {sum(c.values()):>9}  {dist}")

    tot = sum(seg_counts.values()) or 1
    plat = sum(v for k, v in seg_counts.items() if k in PLATFORM)
    loc = sum(v for k, v in seg_counts.items() if k in LOCAL_ASR)
    nz = ses_bucket["platform"] + ses_bucket["local"] or 1
    print(f"\nprojects={len(files)} sessions={n_sessions} segments={tot}")
    print("raw source strings:", dict(sorted(seg_counts.items(), key=lambda kv: -kv[1])))
    print(f"by segment:  platform={plat} ({plat / tot:.1%})  local={loc} ({loc / tot:.1%})"
          f"  other={tot - plat - loc}")
    print(f"by session:  platform={ses_bucket['platform']} ({ses_bucket['platform'] / nz:.1%})"
          f"  local={ses_bucket['local']} ({ses_bucket['local'] / nz:.1%})"
          f"  empty={ses_bucket['empty']}")


if __name__ == "__main__":
    main()
