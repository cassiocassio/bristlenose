"""Render compare.html: 6 columns side by side + overlap matrix + grain table."""
from __future__ import annotations

import html
import json
import statistics
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import Quote, ThemeSet, embed, load_corpus, load_themes
from scoreboard import SCOREBOARD_CSS, render_scoreboard_html, score_project

PROTOTYPE_ORDER = ["s10", "s11", "baseline", "a", "b", "c", "d", "e", "perm_a", "perm_b", "perm_c", "h", "m"]


def render(corpus: list[Quote], theme_sets: list[ThemeSet], out_path: Path, project: str | None = None) -> None:
    quote_lookup = {q.index: q for q in corpus}

    # Order theme sets per PROTOTYPE_ORDER
    by_proto = {ts.prototype: ts for ts in theme_sets}
    ordered = [by_proto[p] for p in PROTOTYPE_ORDER if p in by_proto]

    # Per-theme participant + quote counts
    def theme_stats(t, ts):
        participants = sorted({quote_lookup[i].participant_id for i in t.quote_indices if i in quote_lookup})
        return participants, len(t.quote_indices)

    # Build the column HTML
    cols_html: list[str] = []
    for ts in ordered:
        meta = ts.meta
        # Header
        header = f"""<div class="col-header">
  <h2>{html.escape(ts.label)}</h2>
  <div class="meta">
    <div>{len(ts.themes)} themes · {meta.get('elapsed_s', '?')}s · {meta.get('calls', '?')} calls</div>
    <div>{meta.get('input_tokens', 0):,} in · {meta.get('output_tokens', 0):,} out · ${meta.get('cost_usd', 0):.3f}</div>
    <div class="notes">{html.escape(meta.get('notes', ''))}</div>
  </div>
</div>"""

        cards: list[str] = []
        for t in ts.themes:
            participants, qcount = theme_stats(t, ts)
            quote_lis = []
            for i in t.quote_indices[:50]:
                q = quote_lookup.get(i)
                if not q:
                    continue
                quote_lis.append(
                    f'<li><span class="pid">[{html.escape(q.participant_id)} {html.escape(q.timecode)}]</span> '
                    f'{html.escape(q.text[:300])}{"…" if len(q.text) > 300 else ""}</li>'
                )
            extra = f"<li class='more'>… and {len(t.quote_indices) - 50} more</li>" if len(t.quote_indices) > 50 else ""
            cards.append(f"""<div class="theme">
  <h3>{html.escape(t.label)}</h3>
  <div class="theme-meta">{qcount} quotes · {len(participants)} participants ({", ".join(html.escape(p) for p in participants)})</div>
  <div class="theme-desc">{html.escape(t.description)}</div>
  <details><summary>Show quotes</summary><ul>{"".join(quote_lis)}{extra}</ul></details>
</div>""")
        cols_html.append(f'<div class="col">{header}{"".join(cards)}</div>')

    # Overlap matrix: cosine similarity between theme-label sets
    matrix_html = render_overlap_matrix(ordered)

    # Grain metrics
    grain_html = render_grain(ordered, len(corpus))

    # Cost summary
    total_cost = sum(ts.meta.get("cost_usd", 0) for ts in ordered)
    total_calls = sum(ts.meta.get("calls", 0) for ts in ordered)
    cost_summary = f"<div class='cost'>Total: <b>${total_cost:.3f}</b> across {total_calls} LLM calls · {len(corpus)} quotes</div>"

    # Quality scoreboard (architecture-agnostic measurement)
    if project:
        score_rows = score_project(project, out_path.parent)
        scoreboard_html = render_scoreboard_html(score_rows)
    else:
        scoreboard_html = "<p>No project specified — scoreboard skipped.</p>"

    out = TEMPLATE.replace("{COST_SUMMARY}", cost_summary).replace(
        "{COLUMNS}", "".join(cols_html)
    ).replace("{MATRIX}", matrix_html).replace("{GRAIN}", grain_html).replace(
        "{SCOREBOARD}", scoreboard_html
    ).replace("{SCOREBOARD_CSS}", SCOREBOARD_CSS).replace(
        "{N_QUOTES}", str(len(corpus))
    )
    out_path.write_text(out)


def render_overlap_matrix(ordered: list[ThemeSet]) -> str:
    """Cosine-sim of mean theme-label embedding per prototype."""
    if len(ordered) < 2:
        return "<p>Not enough prototypes for overlap matrix.</p>"
    proto_names = [ts.prototype for ts in ordered]
    proto_labels = [ts.label.split(" — ")[0] for ts in ordered]

    # Per prototype: take mean embedding of all theme labels
    means = []
    for ts in ordered:
        if not ts.themes:
            means.append(np.zeros(384))
            continue
        labels = [t.label for t in ts.themes]
        vecs = embed(labels)
        means.append(vecs.mean(axis=0))
    means_arr = np.stack(means)
    # Already normalised, but mean isn't — renormalise
    norms = np.linalg.norm(means_arr, axis=1, keepdims=True)
    norms[norms == 0] = 1
    means_arr = means_arr / norms
    sim = means_arr @ means_arr.T

    # Render as HTML table
    rows = ["<tr><th></th>" + "".join(f"<th>{html.escape(l)}</th>" for l in proto_labels) + "</tr>"]
    for i, label in enumerate(proto_labels):
        cells = [f"<th>{html.escape(label)}</th>"]
        for j in range(len(proto_labels)):
            v = sim[i, j]
            shade = int(255 - (v * 200))  # higher sim = darker
            cells.append(
                f'<td style="background:rgb({shade},{shade},255);">{v:.2f}</td>'
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f'<table class="matrix">{"".join(rows)}</table>'


def render_grain(ordered: list[ThemeSet], n_quotes: int) -> str:
    rows = ["<tr><th>Prototype</th><th>Themes</th><th>Mean q/theme</th><th>Max</th><th>Min</th><th>Coverage</th><th>Cost</th></tr>"]
    for ts in ordered:
        sizes = [len(t.quote_indices) for t in ts.themes] or [0]
        covered = len({i for t in ts.themes for i in t.quote_indices})
        rows.append(
            f"<tr><td>{html.escape(ts.label.split(' — ')[0])}</td>"
            f"<td>{len(ts.themes)}</td>"
            f"<td>{statistics.mean(sizes):.1f}</td>"
            f"<td>{max(sizes)}</td>"
            f"<td>{min(sizes)}</td>"
            f"<td>{covered}/{n_quotes} ({100 * covered / n_quotes:.0f}%)</td>"
            f"<td>${ts.meta.get('cost_usd', 0):.3f}</td></tr>"
        )
    return f'<table class="grain">{"".join(rows)}</table>'


TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8">
<title>Thematic Analysis Spike</title>
<style>
  body { font-family: -apple-system, system-ui, sans-serif; margin: 0; padding: 16px; background: #f4f4f4; }
  h1 { margin-top: 0; }
  .cost { background: #fffbe6; padding: 8px 12px; border-left: 4px solid #f0c000; margin: 12px 0; }
  .columns { display: grid; grid-template-columns: repeat(13, minmax(280px, 1fr)); gap: 12px; overflow-x: auto; }
  .col { background: white; padding: 12px; border-radius: 6px; min-width: 280px; }
  .col-header { border-bottom: 2px solid #333; padding-bottom: 8px; margin-bottom: 12px; }
  .col-header h2 { font-size: 13px; margin: 0 0 4px 0; }
  .col-header .meta { font-size: 10px; color: #666; }
  .col-header .meta .notes { margin-top: 4px; font-style: italic; }
  .theme { border: 1px solid #ddd; border-radius: 4px; padding: 8px; margin-bottom: 8px; background: #fafafa; }
  .theme h3 { font-size: 13px; margin: 0 0 4px 0; }
  .theme-meta { font-size: 10px; color: #888; margin-bottom: 4px; }
  .theme-desc { font-size: 11px; line-height: 1.4; margin-bottom: 6px; }
  .theme details { font-size: 10px; }
  .theme details summary { cursor: pointer; color: #4a6; }
  .theme ul { padding-left: 16px; margin: 6px 0; }
  .theme li { margin-bottom: 4px; }
  .pid { color: #888; font-family: monospace; font-size: 9px; }
  .more { color: #888; font-style: italic; }
  table.matrix, table.grain { border-collapse: collapse; margin: 16px 0; background: white; }
  table.matrix td, table.matrix th, table.grain td, table.grain th { border: 1px solid #ccc; padding: 4px 8px; text-align: center; font-size: 11px; }
  table.grain td:first-child, table.grain th:first-child { text-align: left; }
  h2.section { margin-top: 32px; }
  {SCOREBOARD_CSS}
</style></head>
<body>
<h1>Thematic Analysis Spike — {N_QUOTES} quotes</h1>
{COST_SUMMARY}
<div class="columns">{COLUMNS}</div>

<h2 class="section">Overlap matrix</h2>
<p>Cosine similarity between mean theme-label embeddings. Higher = more agreement on theme content. Self-similarity always 1.0.</p>
{MATRIX}

<h2 class="section">Quality scoreboard</h2>
<p>
Architecture-agnostic measurement of the existing prototype outputs. <b>Green</b> = healthy on this dimension, <b>red</b> = warning. Coverage of 100% is a warning (likely padding); 60–90% is healthy. Brief-restating: theme labels matching the project's brief vocabulary (approximate regex). Tightness: mean within-cluster cosine distance (lower = tighter). Multi-p %: % of themes with ≥3 participants (cross-participant signal).
</p>
{SCOREBOARD}

<h2 class="section">Grain &amp; coverage (legacy summary)</h2>
<p>Older summary kept for cross-reference.</p>
{GRAIN}

</body></html>"""


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("project", choices=["fossda", "ikea"])
    args = ap.parse_args()
    out_dir = Path(__file__).parent / "output" / args.project
    corpus = load_corpus(out_dir / "corpus.json")
    theme_sets = []
    for p in PROTOTYPE_ORDER:
        path = out_dir / f"themes_{p}.json"
        if path.exists():
            theme_sets.append(load_themes(path))
    render(corpus, theme_sets, out_dir / "compare.html")
    print(f"Wrote {out_dir / 'compare.html'}")
