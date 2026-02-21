#!/usr/bin/env python3
"""Analyse quote proximity in real pipeline output to find run detection thresholds.

Usage:
    .venv/bin/python experiments/segment_proximity_analysis.py <output-dir>

Where <output-dir> is a bristlenose output directory containing
.bristlenose/intermediate/screen_clusters.json and theme_groups.json.

The script groups quotes by (session_id, participant_id) within each
section/theme, then measures both timecode gaps and segment_index gaps
between consecutive quotes. It prints a summary of how many "runs"
(sequences of 2+ quotes) are detected at various thresholds, with
example text.

This helps determine the right default thresholds for the run detection
algorithm described in docs/design-quote-sequences.md.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass
class QuoteInfo:
    """Minimal quote data for proximity analysis."""

    session_id: str
    participant_id: str
    start_timecode: float
    end_timecode: float
    segment_index: int
    text: str
    group_label: str  # section or theme label
    group_type: str  # "section" or "theme"


@dataclass
class Gap:
    """A gap between two consecutive quotes from the same participant."""

    timecode_gap: float  # seconds between end of q1 and start of q2
    ordinal_gap: int  # segment_index difference (-1 if either is unknown)
    q1_text: str
    q2_text: str
    group_label: str
    participant_id: str
    session_id: str


def load_quotes(output_dir: Path) -> list[QuoteInfo]:
    """Load all quotes from intermediate JSON files."""
    intermediate = output_dir / ".bristlenose" / "intermediate"
    quotes: list[QuoteInfo] = []

    clusters_file = intermediate / "screen_clusters.json"
    if clusters_file.exists():
        clusters = json.loads(clusters_file.read_text(encoding="utf-8"))
        for cluster in clusters:
            for q in cluster.get("quotes", []):
                quotes.append(QuoteInfo(
                    session_id=q.get("session_id", ""),
                    participant_id=q.get("participant_id", ""),
                    start_timecode=float(q.get("start_timecode", 0.0)),
                    end_timecode=float(q.get("end_timecode", 0.0)),
                    segment_index=int(q.get("segment_index", -1)),
                    text=q.get("text", ""),
                    group_label=cluster.get("screen_label", ""),
                    group_type="section",
                ))

    themes_file = intermediate / "theme_groups.json"
    if themes_file.exists():
        themes = json.loads(themes_file.read_text(encoding="utf-8"))
        for theme in themes:
            for q in theme.get("quotes", []):
                quotes.append(QuoteInfo(
                    session_id=q.get("session_id", ""),
                    participant_id=q.get("participant_id", ""),
                    start_timecode=float(q.get("start_timecode", 0.0)),
                    end_timecode=float(q.get("end_timecode", 0.0)),
                    segment_index=int(q.get("segment_index", -1)),
                    text=q.get("text", ""),
                    group_label=theme.get("theme_label", ""),
                    group_type="theme",
                ))

    return quotes


def compute_gaps(quotes: list[QuoteInfo]) -> list[Gap]:
    """Compute gaps between consecutive quotes within each group + participant."""
    # Group quotes by (group_label, group_type, session_id, participant_id)
    groups: dict[tuple[str, str, str, str], list[QuoteInfo]] = defaultdict(list)
    for q in quotes:
        key = (q.group_label, q.group_type, q.session_id, q.participant_id)
        groups[key].append(q)

    gaps: list[Gap] = []
    for key, group_quotes in groups.items():
        if len(group_quotes) < 2:
            continue

        # Sort by start_timecode (primary signal)
        sorted_qs = sorted(group_quotes, key=lambda q: q.start_timecode)

        for i in range(len(sorted_qs) - 1):
            q1, q2 = sorted_qs[i], sorted_qs[i + 1]
            tc_gap = q2.start_timecode - q1.end_timecode

            if q1.segment_index >= 0 and q2.segment_index >= 0:
                ord_gap = q2.segment_index - q1.segment_index
            else:
                ord_gap = -1

            gaps.append(Gap(
                timecode_gap=tc_gap,
                ordinal_gap=ord_gap,
                q1_text=q1.text[:80],
                q2_text=q2.text[:80],
                group_label=key[0],
                participant_id=q1.participant_id,
                session_id=q1.session_id,
            ))

    return gaps


def detect_runs(
    gaps: list[Gap],
    max_tc_gap: float | None = None,
    max_ord_gap: int | None = None,
) -> int:
    """Count how many gaps would be classified as 'within a run'."""
    count = 0
    for g in gaps:
        if max_tc_gap is not None and g.timecode_gap <= max_tc_gap:
            count += 1
        elif max_ord_gap is not None and g.ordinal_gap >= 0 and g.ordinal_gap <= max_ord_gap:
            count += 1
    return count


def print_report(quotes: list[QuoteInfo], gaps: list[Gap]) -> None:
    """Print the threshold analysis report."""
    has_timecodes = any(q.start_timecode > 0 for q in quotes)
    has_ordinals = any(q.segment_index >= 0 for q in quotes)

    print(f"\nTotal quotes: {len(quotes)}")
    print(f"Total consecutive pairs (same group + participant): {len(gaps)}")
    print(f"Has timecodes: {has_timecodes}")
    print(f"Has segment ordinals: {has_ordinals}")

    if not gaps:
        print("\nNo consecutive quote pairs found. Nothing to analyse.")
        return

    # Timecode analysis
    if has_timecodes:
        tc_gaps = sorted(g.timecode_gap for g in gaps)
        print("\n--- Timecode gap distribution ---")
        print(f"  Min:    {tc_gaps[0]:.1f}s")
        print(f"  Median: {tc_gaps[len(tc_gaps) // 2]:.1f}s")
        print(f"  Max:    {tc_gaps[-1]:.1f}s")

        print("\n  Threshold   Pairs within   % of pairs")
        print("  ---------   -------------  ----------")
        for threshold in [5, 10, 15, 20, 30, 45, 60, 90, 120]:
            n = sum(1 for g in tc_gaps if g <= threshold)
            pct = 100 * n / len(tc_gaps) if tc_gaps else 0
            print(f"  {threshold:>5}s       {n:>5}          {pct:>5.1f}%")

    # Ordinal analysis
    if has_ordinals:
        ord_gaps = sorted(g.ordinal_gap for g in gaps if g.ordinal_gap >= 0)
        if ord_gaps:
            print("\n--- Segment ordinal gap distribution ---")
            print(f"  Min:    {ord_gaps[0]}")
            print(f"  Median: {ord_gaps[len(ord_gaps) // 2]}")
            print(f"  Max:    {ord_gaps[-1]}")

            print("\n  Max gap   Pairs within   % of pairs")
            print("  -------   -------------  ----------")
            for max_gap in [1, 2, 3, 5, 10, 20]:
                n = sum(1 for g in ord_gaps if g <= max_gap)
                pct = 100 * n / len(ord_gaps) if ord_gaps else 0
                print(f"  {max_gap:>5}       {n:>5}          {pct:>5.1f}%")

    # Show examples of close pairs
    print("\n--- Example close pairs (timecode gap < 30s) ---")
    close = sorted(
        (g for g in gaps if g.timecode_gap <= 30),
        key=lambda g: g.timecode_gap,
    )
    for g in close[:10]:
        ord_str = f"ord={g.ordinal_gap}" if g.ordinal_gap >= 0 else "ord=?"
        print(f"\n  [{g.session_id}/{g.participant_id}] {g.group_label}")
        print(f"  gap: {g.timecode_gap:.1f}s  {ord_str}")
        print(f"  > {g.q1_text}")
        print(f"  > {g.q2_text}")


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <output-dir>")
        print("  output-dir: bristlenose output directory with .bristlenose/intermediate/")
        sys.exit(1)

    output_dir = Path(sys.argv[1])
    if not output_dir.is_dir():
        print(f"Error: {output_dir} is not a directory")
        sys.exit(1)

    intermediate = output_dir / ".bristlenose" / "intermediate"
    if not intermediate.is_dir():
        print(f"Error: {intermediate} not found. Run the pipeline first.")
        sys.exit(1)

    quotes = load_quotes(output_dir)
    if not quotes:
        print("No quotes found in intermediate JSON files.")
        sys.exit(1)

    gaps = compute_gaps(quotes)
    print_report(quotes, gaps)


if __name__ == "__main__":
    main()
