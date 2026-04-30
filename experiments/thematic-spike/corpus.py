"""Build a frozen corpus.json for each project from existing trial-run output.

Reads `extracted_quotes.json` from a project's
`bristlenose-output/.bristlenose/intermediate/` directory and produces a
sampled, indexed list of Quote objects saved as corpus.json.

Per the spike design (see ../../doing-trial-runs… plan): we ignore the
SCREEN_SPECIFIC vs GENERAL_CONTEXT split and pool all quotes. Real
themes hide on both sides of that boundary in UX corpora.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from lib import Quote, save_corpus

# Project name -> trial-run directory name
PROJECTS = {
    "fossda": "fossda-opensource",
    "ikea": "project-ikea",
}

REPO = Path(__file__).resolve().parents[2]


def load_raw_quotes(project: str) -> list[dict]:
    proj_dir = PROJECTS[project]
    path = (
        REPO
        / "trial-runs"
        / proj_dir
        / "bristlenose-output"
        / ".bristlenose"
        / "intermediate"
        / "extracted_quotes.json"
    )
    with open(path) as f:
        return json.load(f)


def build_corpus(project: str, n: int | None, seed: int = 42) -> list[Quote]:
    """Pool all quotes (ignore SS/GC split). Optionally random-sample n with seed.

    If n is None or n >= total, returns the whole pool in original order.
    Otherwise returns a random sample, then re-sorts to original order so
    indexes match transcript reading order.
    """
    raw = load_raw_quotes(project)
    # Pool everything
    pool: list[dict] = []
    for q in raw:
        pool.append(q)

    if n is None or n >= len(pool):
        chosen = list(range(len(pool)))
    else:
        rng = random.Random(seed)
        chosen = sorted(rng.sample(range(len(pool)), n))

    corpus: list[Quote] = []
    for i, src_idx in enumerate(chosen):
        q = pool[src_idx]
        # `start_timecode` is float seconds; render as MM:SS
        secs = float(q.get("start_timecode", 0.0))
        mm, ss = divmod(int(secs), 60)
        hh, mm = divmod(mm, 60)
        timecode = f"{hh:02d}:{mm:02d}:{ss:02d}" if hh else f"{mm:02d}:{ss:02d}"
        corpus.append(
            Quote(
                index=i,
                participant_id=q.get("participant_id", "?"),
                timecode=timecode,
                topic_label=q.get("topic_label", "")[:80],
                text=q.get("text", "").strip(),
                quote_type=q.get("quote_type", "?"),
            )
        )
    return corpus


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("project", choices=list(PROJECTS.keys()))
    ap.add_argument("-n", type=int, default=None, help="sample size (default: all)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    corpus = build_corpus(args.project, args.n, args.seed)
    out = Path(__file__).parent / "output" / args.project / "corpus.json"
    save_corpus(corpus, out)
    print(f"Wrote {len(corpus)} quotes to {out}")


if __name__ == "__main__":
    main()
