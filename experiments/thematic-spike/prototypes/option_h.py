"""Option H: bottom-up mini-clusters (KJ-method shape).

Single LLM call asks for 20-40 small tight clusters of 3-8 quotes each,
flags one best quote per cluster, allows 15-25% unassigned, and bans
brief-restating labels via a corpus-specific banlist.

The researcher does the chapter-grouping themselves later. H produces
the bottom layer only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import LLM, Quote, Stopwatch, Theme, ThemeSet, parse_json_block
from prompts import MINICLUSTER_SYSTEM, MINICLUSTER_USER
from scoreboard import BRIEF_VOCAB


def _format_banlist(words: list[str]) -> str:
    if not words:
        return "(no banlist supplied)"
    return ", ".join(f'"{w}"' for w in words)


def run(corpus: list[Quote], llm: LLM | None = None, project: str | None = None) -> ThemeSet:
    sw = Stopwatch()
    llm = llm or LLM()

    banlist_words = BRIEF_VOCAB.get(project or "", [])
    banlist_str = _format_banlist(banlist_words)

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

    user = (
        MINICLUSTER_USER
        .replace("{n_quotes}", str(len(corpus)))
        .replace("{corpus_banlist}", banlist_str)
        .replace("{quotes_json}", quotes_json)
    )
    response = llm.call(MINICLUSTER_SYSTEM, user, max_tokens=16000)
    parsed = parse_json_block(response)

    clusters = parsed.get("clusters", []) or []
    unassigned = parsed.get("unassigned", []) or []

    themes: list[Theme] = []
    best_quotes: dict[int, int] = {}
    for idx, c in enumerate(clusters):
        qis = c.get("quote_indices", []) or []
        bq = c.get("best_quote_index")
        desc = ""
        if bq is not None:
            best_quotes[idx] = bq
            # Surface the best-quote anchor in description so render.py shows it
            quote = next((q for q in corpus if q.index == bq), None)
            if quote is not None:
                desc = f"Best quote: [{quote.participant_id} {quote.timecode}]"
        themes.append(
            Theme(
                label=c.get("label", "").strip(),
                description=desc,
                quote_indices=qis,
            )
        )

    n = len(corpus)
    return ThemeSet(
        prototype="h",
        label="H — Bottom-up mini-clusters (KJ-method shape)",
        themes=themes,
        meta={
            "n_quotes": n,
            "n_clusters": len(themes),
            "unassigned_count": len(unassigned),
            "unassigned_pct": round(100.0 * len(unassigned) / n, 1) if n else 0.0,
            "unassigned_indices": unassigned,
            "best_quotes": best_quotes,
            "project": project,
            "banlist_size": len(banlist_words),
            "elapsed_s": sw.lap(),
            "notes": (
                f"{len(themes)} mini-clusters, "
                f"{len(unassigned)} unassigned "
                f"({round(100.0 * len(unassigned) / n, 1) if n else 0.0}%)"
            ),
            **llm.stats(),
        },
    )
