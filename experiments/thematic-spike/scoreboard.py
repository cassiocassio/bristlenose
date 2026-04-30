"""Quality scoreboard over the 6 prototype outputs per project.

Metrics computed (no new LLM calls — all derived from existing JSON
plus local embeddings):

- grain_per_100      : themes per 100 quotes (gives shape; high → mini-clusters, low → chapters)
- coverage_pct       : % of quotes assigned to any theme (60–85% is healthy, 100% suspect)
- mean_qpt           : mean quotes per theme
- max_theme_size     : largest theme (dominance flag)
- thin_single_part_themes        : 1 participant AND ≤2 quotes (LLM grasping at straws)
- substantial_single_part_themes : 1 participant AND ≥3 quotes (possible deviant-case insight)
- multi_part_pct     : % of themes with ≥3 participants (cross-participant signal)
- mean_parts_per_theme
- brief_restate_n    : count of theme labels matching brief vocabulary (approximate)
- brief_restate_pct
- mean_within_dist   : mean pairwise cosine distance within clusters (lower = tighter)
- max_within_dist    : worst cluster cohesion

Brief-restating is a hand-curated per-corpus regex against the project's
brief vocabulary (study topic, interview-guide phrases, obvious meta-frames).
It catches the obvious cases. An LLM judge would be more reliable but costs
~$0.02/output; left as a future addition.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import Quote, ThemeSet, embed, load_corpus, load_themes

# ---------- Brief-restating vocab per corpus -----------------------------

# Hand-curated. Match is case-insensitive, word-boundary.
BRIEF_VOCAB: dict[str, list[str]] = {
    "fossda": [
        # Study topic
        "open source", "open-source", "opensource", "fossda",
        # Interview-guide chapters
        "pioneer", "pioneering", "career", "early career", "early life",
        "biography", "biographical", "life and work", "formative",
        # Obvious meta-frames
        "technology", "tech as", "technical journey", "contribution",
        "developer", "movement", "oral history",
    ],
    "ikea": [
        # Study topic (mixed corpus: shopping + healthcare warm-up)
        "ikea", "shopping", "shop ", "checkout", "check out",
        # Interview-guide / task vocabulary
        "navigation", "navigate", "navigating", "interface", "search",
        "search functionality", "page", "site", "website", "product page",
        "category", "categories", "browse", "browsing", "homepage",
        "think aloud", "think-aloud",
        # Surgery side of corpus
        "surgery", "surgical", "operation", "appointment", "hospital",
        "patient experience", "care navigation", "healthcare",
    ],
}


# ---------- Metric helpers -----------------------------------------------


@dataclass
class ScoreRow:
    prototype: str
    label: str
    n_themes: int
    grain_per_100: float
    coverage_pct: float
    mean_qpt: float
    max_theme_size: int
    thin_single_part_themes: int
    substantial_single_part_themes: int
    multi_part_pct: float
    mean_parts_per_theme: float
    brief_restate_n: int
    brief_restate_pct: float
    mean_within_dist: float
    max_within_dist: float
    cost_usd: float
    elapsed_s: float
    notes: list[str]  # human-readable verdicts per metric


def is_brief_restating(label: str, vocab: list[str]) -> bool:
    s = label.lower()
    for v in vocab:
        if re.search(r"\b" + re.escape(v.lower()) + r"\b", s):
            return True
    return False


def cluster_internal_distances(quote_vectors: np.ndarray, indices: list[int]) -> float:
    """Mean pairwise cosine distance within a cluster (1 - cosine similarity)."""
    if len(indices) < 2:
        return 0.0
    vecs = quote_vectors[indices]
    sim = vecs @ vecs.T  # already normalised
    n = len(indices)
    # Sum upper triangle (excluding diagonal)
    iu = np.triu_indices(n, k=1)
    mean_sim = sim[iu].mean()
    return float(1.0 - mean_sim)


def score(corpus: list[Quote], ts: ThemeSet, vocab: list[str], quote_vectors: np.ndarray) -> ScoreRow:
    n = len(corpus)
    n_themes = len(ts.themes)

    # Coverage
    covered = {i for t in ts.themes for i in t.quote_indices if 0 <= i < n}
    coverage_pct = round(100.0 * len(covered) / n, 1) if n else 0.0

    # Grain
    grain_per_100 = round(100.0 * n_themes / n, 1) if n else 0.0

    # Sizes
    sizes = [len(t.quote_indices) for t in ts.themes] or [0]
    mean_qpt = round(statistics.mean(sizes), 1)
    max_theme_size = max(sizes)

    # Participants per theme
    parts_per_theme: list[int] = []
    thin_single_part = 0
    substantial_single_part = 0
    multi_part_count = 0  # ≥3 participants
    for t in ts.themes:
        ps = {corpus[i].participant_id for i in t.quote_indices if 0 <= i < n}
        parts_per_theme.append(len(ps))
        n_quotes = len([i for i in t.quote_indices if 0 <= i < n])
        if len(ps) == 1:
            if n_quotes <= 2:
                thin_single_part += 1
            else:
                substantial_single_part += 1
        if len(ps) >= 3:
            multi_part_count += 1
    mean_parts = round(statistics.mean(parts_per_theme), 1) if parts_per_theme else 0.0
    multi_part_pct = round(100.0 * multi_part_count / n_themes, 1) if n_themes else 0.0

    # Brief-restating
    brief_n = sum(1 for t in ts.themes if is_brief_restating(t.label, vocab))
    brief_pct = round(100.0 * brief_n / n_themes, 1) if n_themes else 0.0

    # Within-cluster cohesion
    dists = []
    for t in ts.themes:
        valid = [i for i in t.quote_indices if 0 <= i < n]
        d = cluster_internal_distances(quote_vectors, valid)
        if len(valid) >= 2:
            dists.append(d)
    mean_within = round(statistics.mean(dists), 3) if dists else 0.0
    max_within = round(max(dists), 3) if dists else 0.0

    notes: list[str] = []
    if coverage_pct >= 99.5:
        notes.append("⚠ 100% coverage — likely padding")
    elif coverage_pct < 50:
        notes.append("⚠ <50% coverage — under-clustering or many quotes left out")
    if max_theme_size >= n * 0.4:
        notes.append(f"⚠ dominant cluster ({max_theme_size}/{n} = {round(100*max_theme_size/n)}%)")
    if n_themes and thin_single_part >= n_themes / 2:
        notes.append(f"⚠ ≥half themes are thin single-participant ({thin_single_part}/{n_themes})")
    if substantial_single_part:
        notes.append(
            f"substantial single-p: {substantial_single_part}/{n_themes} "
            "(check for deviant-case insight vs long rant)"
        )
    if brief_pct >= 25:
        notes.append(f"⚠ brief-restating: {brief_n}/{n_themes} themes")
    if multi_part_pct >= 60:
        notes.append(f"✓ strong cross-participant ({multi_part_pct}%)")
    if mean_within > 0 and mean_within < 0.35:
        notes.append(f"✓ tight clusters (mean dist {mean_within})")
    elif mean_within > 0.55:
        notes.append(f"⚠ loose clusters (mean dist {mean_within})")

    return ScoreRow(
        prototype=ts.prototype,
        label=ts.label,
        n_themes=n_themes,
        grain_per_100=grain_per_100,
        coverage_pct=coverage_pct,
        mean_qpt=mean_qpt,
        max_theme_size=max_theme_size,
        thin_single_part_themes=thin_single_part,
        substantial_single_part_themes=substantial_single_part,
        multi_part_pct=multi_part_pct,
        mean_parts_per_theme=mean_parts,
        brief_restate_n=brief_n,
        brief_restate_pct=brief_pct,
        mean_within_dist=mean_within,
        max_within_dist=max_within,
        cost_usd=ts.meta.get("cost_usd", 0.0),
        elapsed_s=ts.meta.get("elapsed_s", 0.0),
        notes=notes,
    )


def score_project(project: str, output_dir: Path) -> list[ScoreRow]:
    corpus = load_corpus(output_dir / "corpus.json")
    vocab = BRIEF_VOCAB.get(project, [])
    # Embed all quotes once
    texts = [f"[{q.topic_label}] {q.text}" for q in corpus]
    vectors = embed(texts)

    rows: list[ScoreRow] = []
    for proto in ["baseline", "a", "b", "c", "d", "e", "perm_a", "perm_b", "perm_c", "h", "m"]:
        path = output_dir / f"themes_{proto}.json"
        if not path.exists():
            continue
        ts = load_themes(path)
        rows.append(score(corpus, ts, vocab, vectors))
    return rows


def render_scoreboard_html(rows: list[ScoreRow]) -> str:
    """Render a single HTML <section> with a scoreboard table + per-prototype notes."""
    headers = [
        ("Prototype", "label_short"),
        ("Themes", "n_themes"),
        ("Per 100q", "grain_per_100"),
        ("Coverage %", "coverage_pct"),
        ("Mean q/theme", "mean_qpt"),
        ("Max theme", "max_theme_size"),
        ("Thin 1-p", "thin_single_part_themes"),
        ("Substantial 1-p", "substantial_single_part_themes"),
        ("Multi-p %", "multi_part_pct"),
        ("Mean parts/theme", "mean_parts_per_theme"),
        ("Brief-restate", "brief_restate_n"),
        ("Tightness (mean dist)", "mean_within_dist"),
        ("Worst dist", "max_within_dist"),
        ("Cost $", "cost_usd"),
        ("Time s", "elapsed_s"),
    ]
    out = ['<table class="scoreboard"><thead><tr>']
    for h, _ in headers:
        out.append(f"<th>{h}</th>")
    out.append("</tr></thead><tbody>")
    for r in rows:
        d = asdict(r)
        d["label_short"] = r.label.split(" — ")[0]
        out.append("<tr>")
        for _, key in headers:
            v = d[key]
            cls = ""
            # Highlights (architecture-agnostic, criterion-based)
            if key == "coverage_pct":
                if v >= 99.5:
                    cls = "warn"
                elif v < 50:
                    cls = "warn"
                elif 60 <= v <= 90:
                    cls = "good"
            elif key == "brief_restate_n":
                if v == 0:
                    cls = "good"
                elif d["brief_restate_pct"] >= 25:
                    cls = "warn"
            elif key == "multi_part_pct":
                if v >= 60:
                    cls = "good"
                elif v < 30:
                    cls = "warn"
            elif key == "thin_single_part_themes":
                if v == 0:
                    cls = "good"
                elif r.n_themes and v >= r.n_themes / 2:
                    cls = "warn"
            elif key == "mean_within_dist":
                if v != 0 and v < 0.35:
                    cls = "good"
                elif v > 0.55:
                    cls = "warn"
            elif key == "max_theme_size":
                # Dominant-cluster flag: if max > 40% of grand-mean theme-corpus
                # we don't have the corpus-size here; user can read it from the
                # context. Fall back to a simple absolute threshold.
                if v >= 40:
                    cls = "warn"
            out.append(f'<td class="{cls}">{v}</td>')
        out.append("</tr>")
    out.append("</tbody></table>")

    # Notes section
    out.append('<div class="score-notes">')
    for r in rows:
        if not r.notes:
            continue
        out.append(f'<div class="proto-notes"><b>{r.label.split(" — ")[0]}:</b> ')
        out.append(" · ".join(r.notes))
        out.append("</div>")
    out.append("</div>")
    return "".join(out)


SCOREBOARD_CSS = """
table.scoreboard { border-collapse: collapse; background: white; font-size: 11px; margin: 12px 0; }
table.scoreboard th, table.scoreboard td { border: 1px solid #ccc; padding: 4px 6px; text-align: right; }
table.scoreboard th { background: #f0f0f0; text-align: center; }
table.scoreboard td:first-child { text-align: left; font-weight: bold; }
table.scoreboard td.good { background: #e0f5e0; }
table.scoreboard td.warn { background: #ffe5e0; }
.score-notes { font-size: 12px; margin: 12px 0; }
.proto-notes { margin-bottom: 4px; }
"""


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("project", choices=["fossda", "ikea"])
    args = ap.parse_args()
    out_dir = Path(__file__).parent / "output" / args.project
    rows = score_project(args.project, out_dir)
    for r in rows:
        print(f"\n=== {r.prototype} ({r.label}) ===")
        for f in [
            "n_themes",
            "coverage_pct",
            "thin_single_part_themes",
            "substantial_single_part_themes",
            "multi_part_pct",
            "brief_restate_n",
            "mean_within_dist",
            "max_theme_size",
        ]:
            print(f"  {f}: {getattr(r, f)}")
        if r.notes:
            print("  notes:", " · ".join(r.notes))
