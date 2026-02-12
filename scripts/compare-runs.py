#!/usr/bin/env python3
"""Compare two bristlenose pipeline runs (e.g. Sonnet vs Gemini Flash).

Usage:
    python scripts/compare-runs.py path/to/run-a path/to/run-b

Each path should be an output directory containing .bristlenose/intermediate/.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def _load_json(output_dir: Path, filename: str) -> list[dict] | None:
    """Load an intermediate JSON file, trying both directory layouts."""
    for subdir in [".bristlenose/intermediate", "intermediate"]:
        path = output_dir / subdir / filename
        if path.exists():
            return json.loads(path.read_text())
    return None


def _quote_key(q: dict) -> str:
    """Identity key for a quote: session + timecode range."""
    return f"{q['session_id']}@{q['start_timecode']:.1f}-{q['end_timecode']:.1f}"


def compare_quotes(a_quotes: list[dict], b_quotes: list[dict], a_name: str, b_name: str) -> None:
    """Compare extracted quotes between two runs."""
    print(f"\n{'='*60}")
    print("QUOTES")
    print(f"{'='*60}")
    print(f"  {a_name}: {len(a_quotes)} quotes")
    print(f"  {b_name}: {len(b_quotes)} quotes")

    # Index by session_id for per-participant comparison
    a_by_session: dict[str, list[dict]] = {}
    b_by_session: dict[str, list[dict]] = {}
    for q in a_quotes:
        a_by_session.setdefault(q["session_id"], []).append(q)
    for q in b_quotes:
        b_by_session.setdefault(q["session_id"], []).append(q)

    all_sessions = sorted(set(a_by_session) | set(b_by_session))
    print("\n  Per session:")
    for sid in all_sessions:
        a_count = len(a_by_session.get(sid, []))
        b_count = len(b_by_session.get(sid, []))
        delta = b_count - a_count
        marker = f" ({'+' if delta > 0 else ''}{delta})" if delta != 0 else ""
        print(f"    {sid}: {a_count} vs {b_count}{marker}")

    # Quote type distribution
    a_types = Counter(q["quote_type"] for q in a_quotes)
    b_types = Counter(q["quote_type"] for q in b_quotes)
    print("\n  Quote types:")
    for qt in sorted(set(a_types) | set(b_types)):
        print(f"    {qt}: {a_types.get(qt, 0)} vs {b_types.get(qt, 0)}")

    # Sentiment distribution
    a_sent = Counter(q.get("sentiment") or "(none)" for q in a_quotes)
    b_sent = Counter(q.get("sentiment") or "(none)" for q in b_quotes)
    print("\n  Sentiments:")
    for s in sorted(set(a_sent) | set(b_sent)):
        print(f"    {s}: {a_sent.get(s, 0)} vs {b_sent.get(s, 0)}")

    # Intensity distribution
    a_int = Counter(q.get("intensity", 1) for q in a_quotes)
    b_int = Counter(q.get("intensity", 1) for q in b_quotes)
    print("\n  Intensity:")
    for i in sorted(set(a_int) | set(b_int)):
        print(f"    {i}: {a_int.get(i, 0)} vs {b_int.get(i, 0)}")

    # Timecode overlap — find quotes that cover the same moment
    a_keys = {_quote_key(q) for q in a_quotes}
    b_keys = {_quote_key(q) for q in b_quotes}
    overlap = a_keys & b_keys
    only_a = a_keys - b_keys
    only_b = b_keys - a_keys
    print("\n  Timecode overlap (same session + start/end):")
    print(f"    Both: {len(overlap)}")
    print(f"    Only {a_name}: {len(only_a)}")
    print(f"    Only {b_name}: {len(only_b)}")

    # Average quote length
    a_avg = sum(len(q["text"].split()) for q in a_quotes) / max(len(a_quotes), 1)
    b_avg = sum(len(q["text"].split()) for q in b_quotes) / max(len(b_quotes), 1)
    print(f"\n  Avg quote length: {a_avg:.0f} words vs {b_avg:.0f} words")


def compare_clusters(a_clusters: list[dict], b_clusters: list[dict],
                     a_name: str, b_name: str) -> None:
    """Compare screen clusters between two runs."""
    print(f"\n{'='*60}")
    print("SCREEN CLUSTERS")
    print(f"{'='*60}")
    print(f"  {a_name}: {len(a_clusters)} screens")
    print(f"  {b_name}: {len(b_clusters)} screens")

    print(f"\n  {a_name} screens:")
    for c in sorted(a_clusters, key=lambda x: x.get("display_order", 0)):
        n = len(c.get("quotes", []))
        print(f"    {c['screen_label']} ({n} quotes)")

    print(f"\n  {b_name} screens:")
    for c in sorted(b_clusters, key=lambda x: x.get("display_order", 0)):
        n = len(c.get("quotes", []))
        print(f"    {c['screen_label']} ({n} quotes)")

    # Label overlap
    a_labels = {c["screen_label"].lower() for c in a_clusters}
    b_labels = {c["screen_label"].lower() for c in b_clusters}
    shared = a_labels & b_labels
    if shared:
        print(f"\n  Shared labels (case-insensitive): {len(shared)}")
        for label in sorted(shared):
            print(f"    {label}")


def compare_themes(a_themes: list[dict], b_themes: list[dict],
                   a_name: str, b_name: str) -> None:
    """Compare theme groups between two runs."""
    print(f"\n{'='*60}")
    print("THEMES")
    print(f"{'='*60}")
    print(f"  {a_name}: {len(a_themes)} themes")
    print(f"  {b_name}: {len(b_themes)} themes")

    print(f"\n  {a_name} themes:")
    for t in a_themes:
        n = len(t.get("quotes", []))
        print(f"    {t['theme_label']} ({n} quotes)")

    print(f"\n  {b_name} themes:")
    for t in b_themes:
        n = len(t.get("quotes", []))
        print(f"    {t['theme_label']} ({n} quotes)")


def compare_topics(a_topics: list[dict], b_topics: list[dict],
                   a_name: str, b_name: str) -> None:
    """Compare topic segmentation between two runs."""
    print(f"\n{'='*60}")
    print("TOPIC SEGMENTATION")
    print(f"{'='*60}")
    a_total = sum(len(t.get("boundaries", [])) for t in a_topics)
    b_total = sum(len(t.get("boundaries", [])) for t in b_topics)
    print(f"  {a_name}: {a_total} boundaries across {len(a_topics)} sessions")
    print(f"  {b_name}: {b_total} boundaries across {len(b_topics)} sessions")

    # Transition type distribution
    a_types = Counter(
        b["transition_type"] for t in a_topics for b in t.get("boundaries", [])
    )
    b_types = Counter(
        b["transition_type"] for t in b_topics for b in t.get("boundaries", [])
    )
    print("\n  Transition types:")
    for tt in sorted(set(a_types) | set(b_types)):
        print(f"    {tt}: {a_types.get(tt, 0)} vs {b_types.get(tt, 0)}")


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <output-dir-a> <output-dir-b>")
        sys.exit(1)

    dir_a = Path(sys.argv[1])
    dir_b = Path(sys.argv[2])

    if not dir_a.exists():
        print(f"Not found: {dir_a}")
        sys.exit(1)
    if not dir_b.exists():
        print(f"Not found: {dir_b}")
        sys.exit(1)

    a_name = dir_a.name
    b_name = dir_b.name

    print(f"Comparing: {a_name} vs {b_name}")

    # Load all intermediate files
    files = {
        "quotes": "extracted_quotes.json",
        "clusters": "screen_clusters.json",
        "themes": "theme_groups.json",
        "topics": "topic_boundaries.json",
    }

    for label, filename in files.items():
        a_data = _load_json(dir_a, filename)
        b_data = _load_json(dir_b, filename)
        if a_data is None:
            print(f"\n  {filename} not found in {a_name}")
        if b_data is None:
            print(f"\n  {filename} not found in {b_name}")
        if a_data is None or b_data is None:
            continue

        if label == "quotes":
            compare_quotes(a_data, b_data, a_name, b_name)
        elif label == "clusters":
            compare_clusters(a_data, b_data, a_name, b_name)
        elif label == "themes":
            compare_themes(a_data, b_data, a_name, b_name)
        elif label == "topics":
            compare_topics(a_data, b_data, a_name, b_name)

    print()


if __name__ == "__main__":
    main()
