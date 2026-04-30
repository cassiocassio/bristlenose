"""Option C: map-reduce.

Per-participant: extract candidate themes from that participant's quotes
alone (small calls). Reduce: merge candidate themes into corpus-level
themes (one call over a much smaller object — themes not quotes).
Re-assign each quote to the merged theme set.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import LLM, Quote, Stopwatch, Theme, ThemeSet, parse_json_block
from prompts import (
    MERGE_THEMES_SYSTEM,
    MERGE_THEMES_USER,
    PER_PARTICIPANT_SYSTEM,
    PER_PARTICIPANT_USER,
    REASSIGN_SYSTEM,
    REASSIGN_USER,
)


def run(corpus: list[Quote], llm: LLM | None = None) -> ThemeSet:
    sw = Stopwatch()
    llm = llm or LLM()

    # Group quotes by participant
    by_participant: dict[str, list[Quote]] = defaultdict(list)
    for q in corpus:
        by_participant[q.participant_id].append(q)

    # Pass 1: per-participant theme drafts
    candidates: list[dict] = []  # flat list of {participant, label, description}
    for pid, qs in sorted(by_participant.items()):
        if len(qs) < 2:
            # Skip participants with too few quotes; their quotes still get
            # reassigned in the final pass
            continue
        quotes_json = json.dumps(
            [
                {"index": q.index, "topic_label": q.topic_label, "text": q.text}
                for q in qs
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        user = (
            PER_PARTICIPANT_USER.replace("{participant_id}", pid)
            .replace("{quotes_json}", quotes_json)
        )
        try:
            response = llm.call(PER_PARTICIPANT_SYSTEM, user, max_tokens=2000)
            parsed = parse_json_block(response)
            for t in parsed.get("themes", []):
                candidates.append(
                    {
                        "participant": pid,
                        "label": t.get("label", ""),
                        "description": t.get("description", ""),
                    }
                )
        except Exception as e:
            print(f"  [c] per-participant pass failed for {pid}: {e}")

    if not candidates:
        return ThemeSet(
            prototype="c",
            label="C — Map-reduce (per-participant → merge → reassign)",
            themes=[],
            meta={"n_quotes": len(corpus), "elapsed_s": sw.lap(), **llm.stats()},
        )

    # Pass 2: merge candidates into corpus-level themes
    candidates_json = json.dumps(
        [
            {"index": i, "participant": c["participant"], "label": c["label"], "description": c["description"]}
            for i, c in enumerate(candidates)
        ],
        ensure_ascii=False,
        indent=2,
    )
    user = MERGE_THEMES_USER.replace("{candidates_json}", candidates_json)
    response = llm.call(MERGE_THEMES_SYSTEM, user, max_tokens=3000)
    merged = parse_json_block(response)
    merged_themes = merged.get("themes", [])

    if not merged_themes:
        return ThemeSet(
            prototype="c",
            label="C — Map-reduce (per-participant → merge → reassign)",
            themes=[],
            meta={"n_quotes": len(corpus), "elapsed_s": sw.lap(), **llm.stats()},
        )

    # Pass 3: reassign each quote to a merged theme
    themes_json = json.dumps(
        [
            {"index": i, "label": t["label"], "description": t.get("description", "")}
            for i, t in enumerate(merged_themes)
        ],
        ensure_ascii=False,
        indent=2,
    )
    quotes_json = json.dumps(
        [
            {
                "index": q.index,
                "participant": q.participant_id,
                "topic_label": q.topic_label,
                "text": q.text,
            }
            for q in corpus
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    user = REASSIGN_USER.replace("{themes_json}", themes_json).replace(
        "{quotes_json}", quotes_json
    )
    response = llm.call(REASSIGN_SYSTEM, user, max_tokens=4000)
    assignments_data = parse_json_block(response)

    theme_quotes: dict[int, list[int]] = defaultdict(list)
    for a in assignments_data.get("assignments", []):
        ti = a.get("theme_index", -1)
        qi = a.get("quote_index")
        if ti >= 0 and qi is not None:
            theme_quotes[ti].append(qi)

    themes: list[Theme] = []
    for ti, t in enumerate(merged_themes):
        themes.append(
            Theme(
                label=t.get("label", f"Theme {ti}"),
                description=t.get("description", ""),
                quote_indices=sorted(theme_quotes.get(ti, [])),
            )
        )

    return ThemeSet(
        prototype="c",
        label="C — Map-reduce (per-participant → merge → reassign)",
        themes=themes,
        meta={
            "n_quotes": len(corpus),
            "n_participants": len(by_participant),
            "n_candidate_themes": len(candidates),
            "elapsed_s": sw.lap(),
            "notes": "3-pass: per-participant theme drafts → corpus merge → reassign all quotes.",
            **llm.stats(),
        },
    )
