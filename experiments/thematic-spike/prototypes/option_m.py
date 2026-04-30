"""Option M: BERTopic-style pure-math pipeline. No LLM at all.

embed (sentence-transformers) → reduce (UMAP) → cluster (HDBSCAN) → name (c-TF-IDF).

The point: does the LLM contribute value over plain math? Determinism +
zero cost are the wins. HDBSCAN's noise bucket (-1) is preserved as
quotes-not-in-any-theme — the math equivalent of researchers culling
filler.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import LLM, Quote, Stopwatch, Theme, ThemeSet, embed

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "of", "to", "in",
    "on", "at", "for", "with", "by", "from", "as", "is", "it", "its", "this",
    "that", "these", "those", "be", "been", "being", "are", "was", "were",
    "i", "you", "he", "she", "we", "they", "me", "him", "her", "us", "them",
    "my", "your", "his", "their", "our", "what", "which", "who", "when",
    "where", "why", "how", "all", "any", "some", "no", "not", "so", "than",
    "too", "very", "can", "just", "do", "does", "did", "have", "has", "had",
    "will", "would", "could", "should", "may", "might", "must", "shall",
    "yeah", "yes", "um", "uh", "like", "really", "kind", "sort", "thing",
    "things", "know", "think", "get", "got", "going", "go", "come", "came",
    "said", "say", "says", "saying", "well", "okay", "ok", "right", "mean",
    "lot", "bit", "actually", "probably", "maybe", "guess", "want", "need",
    "use", "used", "using", "make", "makes", "made", "see", "saw", "look",
    "looking", "way", "back", "still", "even", "much", "more", "most",
    "also", "only", "own", "over", "out", "up", "down", "into", "about",
    "there", "here", "now", "one", "two", "first", "last", "good", "great",
    "people", "person", "time", "day", "year", "years",
}


def _tokenize(text: str) -> list[str]:
    return [
        w for w in re.findall(r"[a-z][a-z'-]+", text.lower())
        if len(w) >= 3 and w not in _STOPWORDS
    ]


def _ctfidf_label(
    cluster_texts: list[str],
    other_clusters_texts: list[list[str]],
    top_k: int = 5,
) -> str:
    """Top-k discriminative words: this cluster's TF / mean(other clusters' TF)."""
    cluster_tokens = [tok for t in cluster_texts for tok in _tokenize(t)]
    if not cluster_tokens:
        return "(unlabelled)"
    cluster_tf: dict[str, float] = {}
    for w in cluster_tokens:
        cluster_tf[w] = cluster_tf.get(w, 0) + 1
    n_self = len(cluster_tokens)
    cluster_tf = {w: c / n_self for w, c in cluster_tf.items()}

    other_tf: dict[str, float] = {}
    n_others = max(1, len(other_clusters_texts))
    for ot in other_clusters_texts:
        ot_tokens = [tok for t in ot for tok in _tokenize(t)]
        if not ot_tokens:
            continue
        n_o = len(ot_tokens)
        for w in ot_tokens:
            other_tf[w] = other_tf.get(w, 0) + (1 / n_o) / n_others

    scores = {
        w: tf / (other_tf.get(w, 0) + 0.001)
        for w, tf in cluster_tf.items()
    }
    top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return " ".join(w for w, _ in top) if top else "(unlabelled)"


def run(corpus: list[Quote], llm: LLM | None = None) -> ThemeSet:
    sw = Stopwatch()

    texts = [f"[{q.topic_label}] {q.text}" for q in corpus]
    vectors = embed(texts)

    import umap
    import hdbscan

    n = len(corpus)
    n_neighbors = max(2, min(15, n - 1))
    n_components = min(5, max(2, n - 2))
    reducer = umap.UMAP(
        n_neighbors=n_neighbors,
        n_components=n_components,
        metric="cosine",
        random_state=42,
    )
    reduced = reducer.fit_transform(vectors)

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=2,
        metric="euclidean",
        cluster_selection_method="eom",
    )
    labels = clusterer.fit_predict(reduced)

    cluster_ids = sorted({int(lab) for lab in labels if lab != -1})
    noise_count = int(np.sum(labels == -1))

    cluster_texts: dict[int, list[str]] = {}
    cluster_members: dict[int, list[int]] = {}
    for i, lab in enumerate(labels):
        lab = int(lab)
        if lab == -1:
            continue
        cluster_texts.setdefault(lab, []).append(corpus[i].text)
        cluster_members.setdefault(lab, []).append(i)

    themes: list[Theme] = []
    for cid in cluster_ids:
        others = [cluster_texts[other] for other in cluster_ids if other != cid]
        label = _ctfidf_label(cluster_texts[cid], others, top_k=5)
        themes.append(
            Theme(
                label=label,
                description="BERTopic-derived; researcher should rename.",
                quote_indices=cluster_members[cid],
            )
        )

    # Largest first
    themes.sort(key=lambda t: -len(t.quote_indices))

    noise_pct = round(100 * noise_count / max(1, n), 1)
    return ThemeSet(
        prototype="m",
        label="M — BERTopic (math only, no LLM)",
        themes=themes,
        meta={
            "n_quotes": n,
            "n_clusters": len(cluster_ids),
            "noise_count": noise_count,
            "noise_pct": noise_pct,
            "elapsed_s": sw.lap(),
            "cost_usd": 0.0,
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "notes": (
                "Pure math: sentence-transformers + UMAP + HDBSCAN + c-TF-IDF. "
                "No LLM. Deterministic given seed. "
                f"Noise quotes (not in any theme): {noise_count}/{n} ({noise_pct}%)."
            ),
        },
    )
