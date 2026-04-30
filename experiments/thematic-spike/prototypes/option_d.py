"""Option D: iterative two-pass.

Pass 1 = the baseline. Pass 2 feeds the baseline result back in,
asks Claude to review it critically against the full corpus and
produce a refined theme set (merge weak, split overloaded, fix
mis-assignments, add missed patterns).

Closes the Braun & Clarke "review themes" loop the baseline skips.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import LLM, Quote, Stopwatch, Theme, ThemeSet, parse_json_block
from prompts import REVIEW_SYSTEM, REVIEW_USER

from prototypes.baseline import run as baseline_run


def run(corpus: list[Quote], llm: LLM | None = None) -> ThemeSet:
    sw = Stopwatch()
    llm = llm or LLM()

    # Pass 1: baseline
    first = baseline_run(corpus, llm=llm)
    first_pass_json = json.dumps(
        {
            "themes": [
                {
                    "label": t.label,
                    "description": t.description,
                    "quote_indices": t.quote_indices,
                }
                for t in first.themes
            ]
        },
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

    user = REVIEW_USER.replace("{first_pass_json}", first_pass_json).replace(
        "{quotes_json}", quotes_json
    )
    response = llm.call(REVIEW_SYSTEM, user, max_tokens=8000)
    parsed = parse_json_block(response)

    themes = [
        Theme(label=t["label"], description=t["description"], quote_indices=t["quote_indices"])
        for t in parsed.get("themes", [])
    ]

    return ThemeSet(
        prototype="d",
        label="D — Iterative two-pass (draft → review/refine)",
        themes=themes,
        meta={
            "n_quotes": len(corpus),
            "first_pass_themes": len(first.themes),
            "elapsed_s": sw.lap(),
            "notes": "Pass 1 = baseline single call. Pass 2 reviews pass-1 output "
            "against the full corpus and produces a revised theme set.",
            **llm.stats(),
        },
    )
