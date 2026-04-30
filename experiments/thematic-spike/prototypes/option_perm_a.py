"""Perm-A: baseline + explicit permission to leave quotes unassigned."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import LLM, Quote, Stopwatch, Theme, ThemeSet, parse_json_block
from prompts import BASELINE_SYSTEM, PERM_A_USER


def run(corpus: list[Quote], llm: LLM | None = None) -> ThemeSet:
    sw = Stopwatch()
    llm = llm or LLM()
    quotes_for_llm = [
        {
            "index": q.index,
            "participant": q.participant_id,
            "timecode": q.timecode,
            "topic_label": q.topic_label,
            "text": q.text,
        }
        for q in corpus
    ]
    quotes_json = json.dumps(quotes_for_llm, ensure_ascii=False, separators=(",", ":"))

    user = PERM_A_USER.replace("{quotes_json}", quotes_json)
    response = llm.call(BASELINE_SYSTEM, user, max_tokens=8000)

    parsed = parse_json_block(response)

    themes = [
        Theme(label=t["label"], description=t["description"], quote_indices=t["quote_indices"])
        for t in parsed.get("themes", [])
    ]
    unassigned = parsed.get("unassigned", []) or []

    return ThemeSet(
        prototype="perm_a",
        label="Perm-A — noise bucket permission",
        themes=themes,
        meta={
            "n_quotes": len(corpus),
            "n_unassigned": len(unassigned),
            "unassigned_indices": unassigned,
            "elapsed_s": sw.lap(),
            "notes": f"{len(unassigned)} quotes left unassigned",
            **llm.stats(),
        },
    )
