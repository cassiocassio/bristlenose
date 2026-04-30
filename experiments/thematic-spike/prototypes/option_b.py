"""Option B: code-first, theme-second.

Per-quote code extraction (1 LLM call per quote → 1–3 short codes), then
embed and cluster the codes (much smaller corpus than quotes), then name
each code-cluster as a theme. Quotes inherit their codes' theme.

This is the QDA-tool consensus shape (NVivo / ATLAS.ti / Marvin /
Looppanel all converge on this).
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import LLM, Quote, Stopwatch, Theme, ThemeSet, embed, parse_json_block
from prompts import (
    CODE_EXTRACT_SYSTEM,
    CODE_EXTRACT_USER,
    NAME_CLUSTER_SYSTEM,
    NAME_CLUSTER_USER,
)
from sklearn.cluster import AgglomerativeClustering


def run(corpus: list[Quote], llm: LLM | None = None) -> ThemeSet:
    sw = Stopwatch()
    llm = llm or LLM()

    # Pass 1: per-quote code extraction
    quote_codes: list[list[str]] = []  # parallel to corpus
    for q in corpus:
        user = (
            CODE_EXTRACT_USER.replace("{participant_id}", q.participant_id)
            .replace("{topic_label}", q.topic_label)
            .replace("{text}", q.text)
        )
        try:
            response = llm.call(CODE_EXTRACT_SYSTEM, user, max_tokens=200)
            parsed = parse_json_block(response)
            codes = [c.strip().lower() for c in parsed.get("codes", []) if c.strip()]
        except Exception as e:
            print(f"  [b] code extraction failed for quote {q.index}: {e}")
            codes = []
        quote_codes.append(codes[:3])

    # Build a flat code list with provenance: (code, originating_quote_index)
    flat: list[tuple[str, int]] = []
    for qi, codes in enumerate(quote_codes):
        for c in codes:
            flat.append((c, qi))

    if not flat:
        return ThemeSet(
            prototype="b",
            label="B — Code-first, theme-second",
            themes=[],
            meta={"n_quotes": len(corpus), "elapsed_s": sw.lap(), **llm.stats()},
        )

    # Embed unique codes (dedup) and cluster them
    unique_codes: list[str] = []
    code_to_idx: dict[str, int] = {}
    for c, _qi in flat:
        if c not in code_to_idx:
            code_to_idx[c] = len(unique_codes)
            unique_codes.append(c)

    vectors = embed(unique_codes)

    # Aim for 6–12 code clusters
    n_clusters = min(max(6, len(unique_codes) // 6), 12)
    if n_clusters >= len(unique_codes):
        n_clusters = max(2, len(unique_codes) // 2)
    clusterer = AgglomerativeClustering(
        n_clusters=n_clusters,
        metric="cosine",
        linkage="average",
    )
    code_cluster = clusterer.fit_predict(vectors)

    # Map quote → code-cluster. The LLM lists codes in priority order
    # (most-defining first). Take the first code's cluster; this avoids
    # tie-breaker dominance where one cluster eats the corpus.
    quote_cluster: dict[int, int] = {}
    for qi, codes in enumerate(quote_codes):
        if not codes:
            continue
        first_code = codes[0]
        quote_cluster[qi] = int(code_cluster[code_to_idx[first_code]])

    # Group quotes by cluster
    cluster_quotes: dict[int, list[int]] = defaultdict(list)
    for qi, cl in quote_cluster.items():
        cluster_quotes[cl].append(qi)

    # Name each code-cluster
    themes: list[Theme] = []
    for cl in sorted(cluster_quotes.keys()):
        cl_codes = [unique_codes[i] for i, c in enumerate(code_cluster) if c == cl]
        member_qis = cluster_quotes[cl]
        sample = member_qis[:6]
        quotes_sample = "\n".join(
            f"- [{corpus[i].participant_id}] {corpus[i].text[:200]}" for i in sample
        )
        codes_list = ", ".join(cl_codes[:15])
        user = (
            NAME_CLUSTER_USER.replace("{codes_list}", codes_list)
            .replace("{quotes_sample}", quotes_sample)
        )
        response = llm.call(NAME_CLUSTER_SYSTEM, user, max_tokens=400)
        parsed = parse_json_block(response)
        themes.append(
            Theme(
                label=parsed.get("label", f"Code cluster {cl}"),
                description=parsed.get("description", ""),
                quote_indices=member_qis,
            )
        )

    return ThemeSet(
        prototype="b",
        label="B — Code-first, theme-second (QDA-tool shape)",
        themes=themes,
        meta={
            "n_quotes": len(corpus),
            "n_unique_codes": len(unique_codes),
            "n_code_clusters": n_clusters,
            "elapsed_s": sw.lap(),
            "notes": (
                f"{len(corpus)} per-quote code calls (~150 tok each), then embed "
                f"+ cluster {len(unique_codes)} unique codes into {n_clusters} "
                "groups, then 1 LLM naming call per group."
            ),
            **llm.stats(),
        },
    )
