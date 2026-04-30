"""Import existing production s10 (screen_clusters) output as a spike column.

Reads `screen_clusters.json` from a project's intermediate dir, matches
quotes back to the spike's corpus by (participant_id, start_timecode, text),
and saves as themes_s10.json in the project's spike output dir.

This lets us see what the *production* pipeline already produces alongside
the experimental prototypes — a real-world baseline rather than yet another
LLM variation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from corpus import PROJECTS
from lib import Quote, Theme, ThemeSet, load_corpus, save_themes

REPO = Path(__file__).resolve().parents[2]


def import_s10(project: str) -> ThemeSet:
    """Load existing s10 output and convert to ThemeSet shape."""
    proj_dir = PROJECTS[project]
    s10_path = (
        REPO / "trial-runs" / proj_dir / "bristlenose-output"
        / ".bristlenose" / "intermediate" / "screen_clusters.json"
    )
    if not s10_path.exists():
        raise FileNotFoundError(f"No s10 output at {s10_path}")

    spike_corpus_path = Path(__file__).parent / "output" / project / "corpus.json"
    corpus = load_corpus(spike_corpus_path)

    # Build a lookup: (participant_id, rounded_start_timecode, text_prefix) → index
    def _key(q_pid: str, q_start: float, q_text: str) -> tuple[str, int, str]:
        return (q_pid, int(round(q_start)), q_text.strip()[:60])

    corpus_lookup: dict[tuple[str, int, str], int] = {}
    for q in corpus:
        # corpus stores timecode as MM:SS string; reconstruct seconds
        parts = q.timecode.split(":")
        if len(parts) == 2:
            secs = int(parts[0]) * 60 + int(parts[1])
        else:
            secs = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        corpus_lookup[_key(q.participant_id, secs, q.text)] = q.index

    # Convert each screen cluster to a Theme
    s10_clusters = json.loads(s10_path.read_text())
    themes: list[Theme] = []
    matched = 0
    unmatched_examples: list[str] = []

    for cluster in s10_clusters:
        quote_indices: list[int] = []
        for q in cluster.get("quotes", []):
            key = _key(q["participant_id"], q["start_timecode"], q["text"])
            idx = corpus_lookup.get(key)
            if idx is not None:
                quote_indices.append(idx)
                matched += 1
            else:
                if len(unmatched_examples) < 3:
                    unmatched_examples.append(
                        f"{q['participant_id']} @ {q['start_timecode']}: {q['text'][:50]}"
                    )

        if quote_indices:
            themes.append(
                Theme(
                    label=cluster.get("screen_label", "(no label)"),
                    description=cluster.get("description", ""),
                    quote_indices=sorted(quote_indices),
                )
            )

    total_s10_quotes = sum(len(c.get("quotes", [])) for c in s10_clusters)
    print(f"  Matched {matched} / {total_s10_quotes} s10 quotes to corpus indices")
    if unmatched_examples:
        print(f"  Unmatched examples: {unmatched_examples}")

    return ThemeSet(
        prototype="s10",
        label="S10 — Production screen clusters (existing pipeline)",
        themes=themes,
        meta={
            "n_quotes": len(corpus),
            "n_clusters": len(themes),
            "matched_quotes": matched,
            "total_s10_quotes": total_s10_quotes,
            "elapsed_s": 0.0,
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "notes": (
                "Imported from existing pipeline output (s10_quote_clustering). "
                "Only SCREEN_SPECIFIC quotes are included; GENERAL_CONTEXT quotes "
                "live in s11 themes (not imported here). Coverage will be ~80% on "
                "ikea because GC quotes are excluded by design."
            ),
        },
    )


def import_s11(project: str) -> ThemeSet:
    """Load existing s11 (theme_groups) output and convert to ThemeSet shape."""
    proj_dir = PROJECTS[project]
    s11_path = (
        REPO / "trial-runs" / proj_dir / "bristlenose-output"
        / ".bristlenose" / "intermediate" / "theme_groups.json"
    )
    if not s11_path.exists():
        raise FileNotFoundError(f"No s11 output at {s11_path}")

    spike_corpus_path = Path(__file__).parent / "output" / project / "corpus.json"
    corpus = load_corpus(spike_corpus_path)

    def _key(q_pid: str, q_start: float, q_text: str) -> tuple[str, int, str]:
        return (q_pid, int(round(q_start)), q_text.strip()[:60])

    corpus_lookup: dict[tuple[str, int, str], int] = {}
    for q in corpus:
        parts = q.timecode.split(":")
        if len(parts) == 2:
            secs = int(parts[0]) * 60 + int(parts[1])
        else:
            secs = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        corpus_lookup[_key(q.participant_id, secs, q.text)] = q.index

    s11_groups = json.loads(s11_path.read_text())
    themes: list[Theme] = []
    matched = 0
    total = 0
    for grp in s11_groups:
        quote_indices: list[int] = []
        for q in grp.get("quotes", []):
            total += 1
            key = _key(q["participant_id"], q["start_timecode"], q["text"])
            idx = corpus_lookup.get(key)
            if idx is not None:
                quote_indices.append(idx)
                matched += 1
        if quote_indices:
            themes.append(
                Theme(
                    label=grp.get("theme_label", "(no label)"),
                    description=grp.get("description", ""),
                    quote_indices=sorted(quote_indices),
                )
            )

    print(f"  Matched {matched} / {total} s11 quotes to corpus indices")
    return ThemeSet(
        prototype="s11",
        label="S11 — Production thematic groups (existing pipeline)",
        themes=themes,
        meta={
            "n_quotes": len(corpus),
            "n_themes": len(themes),
            "matched_quotes": matched,
            "total_s11_quotes": total,
            "elapsed_s": 0.0,
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "notes": (
                "Imported from existing pipeline output (s11_thematic_grouping). "
                "Only GENERAL_CONTEXT quotes are included; SCREEN_SPECIFIC quotes "
                "are in s10 (imported separately). Coverage will be partial because "
                "the spike's corpus pools both types."
            ),
        },
    )


def main() -> None:
    for project in PROJECTS.keys():
        print(f"\n=== {project} ===")
        out_dir = Path(__file__).parent / "output" / project
        for label, importer in [("s10", import_s10), ("s11", import_s11)]:
            try:
                ts = importer(project)
            except FileNotFoundError as exc:
                print(f"  {label} skipped: {exc}")
                continue
            save_themes(ts, out_dir)
            print(f"  {label}: saved {len(ts.themes)} clusters to themes_{label}.json")


if __name__ == "__main__":
    main()
