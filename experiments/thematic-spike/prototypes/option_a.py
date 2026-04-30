"""Option A: embed → agglomerative cluster → LLM-name per cluster.

BERTopic-style. Sentence-transformers embeddings (free, local), sklearn
agglomerative clustering with cosine distance, one cheap LLM call per
cluster to name it. Deterministic given a fixed embedding model.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import LLM, Quote, Stopwatch, Theme, ThemeSet, embed, parse_json_block
from prompts import NAME_CLUSTER_SYSTEM, NAME_CLUSTER_USER
from sklearn.cluster import AgglomerativeClustering


def run(corpus: list[Quote], llm: LLM | None = None) -> ThemeSet:
    sw = Stopwatch()
    llm = llm or LLM()

    # Embed quote text + topic label (richer signal than text alone)
    texts = [f"[{q.topic_label}] {q.text}" for q in corpus]
    vectors = embed(texts)

    # Cluster — pick a k that gives roughly 5–12 themes
    n_clusters = min(max(5, len(corpus) // 10), 12)
    clusterer = AgglomerativeClustering(
        n_clusters=n_clusters,
        metric="cosine",
        linkage="average",
    )
    labels = clusterer.fit_predict(vectors)

    # Name each cluster
    themes: list[Theme] = []
    for cluster_id in sorted(set(labels)):
        member_indices = [i for i, lab in enumerate(labels) if lab == cluster_id]
        # Sample up to 6 quotes for the LLM; show codes are derived from quotes
        sample = member_indices[:6]
        quotes_sample = "\n".join(
            f"- [{corpus[i].participant_id}] {corpus[i].text[:200]}" for i in sample
        )
        codes_list = ", ".join(corpus[i].topic_label for i in sample)

        user = (
            NAME_CLUSTER_USER.replace("{codes_list}", codes_list)
            .replace("{quotes_sample}", quotes_sample)
        )
        response = llm.call(NAME_CLUSTER_SYSTEM, user, max_tokens=400)
        parsed = parse_json_block(response)
        themes.append(
            Theme(
                label=parsed.get("label", f"Cluster {cluster_id}"),
                description=parsed.get("description", ""),
                quote_indices=member_indices,
            )
        )

    return ThemeSet(
        prototype="a",
        label="A — Embed + cluster + LLM-name (BERTopic-style)",
        themes=themes,
        meta={
            "n_quotes": len(corpus),
            "n_clusters": n_clusters,
            "elapsed_s": sw.lap(),
            "notes": "Embeddings: sentence-transformers all-MiniLM-L6-v2 (free, local). "
            "Clustering: sklearn AgglomerativeClustering, cosine, average-linkage. "
            "LLM only for naming (1 call per cluster).",
            **llm.stats(),
        },
    )
