"""Option E: self-consistency.

Run baseline 5 times at temp 1.0; reconcile via a final LLM call that
flags themes as stable (≥3 runs), tentative (2 runs), or single-run.

Tests an empirical question we don't have an answer to: how stable is
the baseline across re-runs? The reconciler's stability flag is the
researcher-facing artefact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import LLM, Quote, Stopwatch, Theme, ThemeSet, parse_json_block
from prompts import RECONCILE_SYSTEM, RECONCILE_USER

from prototypes.baseline import run as baseline_run

N_RUNS = 5


def run(corpus: list[Quote], llm: LLM | None = None) -> ThemeSet:
    sw = Stopwatch()
    llm = llm or LLM()

    # 5 independent baseline runs
    runs: list[ThemeSet] = []
    for i in range(N_RUNS):
        try:
            r = baseline_run(corpus, llm=llm)
            runs.append(r)
            print(f"  [e] run {i + 1}/{N_RUNS}: {len(r.themes)} themes")
        except Exception as exc:
            print(f"  [e] run {i + 1}/{N_RUNS} failed: {exc}")

    if not runs:
        return ThemeSet(
            prototype="e",
            label="E — Self-consistency (5× baseline)",
            themes=[],
            meta={"n_quotes": len(corpus), "elapsed_s": sw.lap(), **llm.stats()},
        )

    # Reconcile
    runs_json = json.dumps(
        [
            {
                "run": i,
                "themes": [
                    {
                        "label": t.label,
                        "description": t.description,
                        "quote_indices": t.quote_indices,
                    }
                    for t in r.themes
                ],
            }
            for i, r in enumerate(runs)
        ],
        ensure_ascii=False,
        indent=2,
    )

    user = RECONCILE_USER.replace("{n_runs}", str(N_RUNS)).replace(
        "{runs_json}", runs_json
    )
    response = llm.call(RECONCILE_SYSTEM, user, max_tokens=6000)
    parsed = parse_json_block(response)

    themes = []
    stability_meta: list[dict] = []
    for t in parsed.get("themes", []):
        # Stuff stability into the description so it shows up in compare.html
        stab = t.get("stability", "?")
        appears = t.get("appears_in_runs", 0)
        desc = f"[{stab.upper()}, {appears}/{N_RUNS} runs] {t.get('description', '')}"
        themes.append(
            Theme(
                label=t["label"],
                description=desc,
                quote_indices=t.get("quote_indices", []),
            )
        )
        stability_meta.append({"label": t["label"], "stability": stab, "appears_in_runs": appears})

    return ThemeSet(
        prototype="e",
        label=f"E — Self-consistency ({N_RUNS}× baseline + reconcile)",
        themes=themes,
        meta={
            "n_quotes": len(corpus),
            "n_runs": N_RUNS,
            "themes_per_run": [len(r.themes) for r in runs],
            "stability_summary": stability_meta,
            "elapsed_s": sw.lap(),
            "notes": (
                f"Baseline run {N_RUNS} times at temp 1.0 + 1 reconcile call. "
                "The stability flag (stable / tentative / single-run) is the "
                "researcher-facing artefact; raw run themes saved in meta."
            ),
            **llm.stats(),
        },
    )
