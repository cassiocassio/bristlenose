"""Driver: build corpus → run all 6 prototypes → render compare.html.

Usage:
  python run_all.py fossda     # 100-quote sample, seed=42
  python run_all.py ikea       # all quotes
  python run_all.py            # both
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from corpus import build_corpus
from lib import LLM, save_corpus, save_themes
from prototypes import baseline, option_a, option_b, option_c, option_d, option_e
from render import render

CONFIGS = {
    "fossda": {"n": 100, "seed": 42},
    "ikea": {"n": None, "seed": 42},  # all 67 quotes
}

PROTOTYPES = [
    ("baseline", baseline.run),
    ("a", option_a.run),
    ("b", option_b.run),
    ("c", option_c.run),
    ("d", option_d.run),
    ("e", option_e.run),
]


def run_project(project: str, only: list[str] | None = None) -> None:
    print(f"\n=== {project.upper()} ===")
    cfg = CONFIGS[project]
    out_dir = Path(__file__).parent / "output" / project
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build corpus
    corpus = build_corpus(project, cfg["n"], cfg["seed"])
    save_corpus(corpus, out_dir / "corpus.json")
    print(f"Corpus: {len(corpus)} quotes (sampled with seed={cfg['seed']})")

    # Run prototypes
    theme_sets = []
    grand_cost = 0.0
    for name, runner in PROTOTYPES:
        if only and name not in only:
            # Try loading prior result
            prior_path = out_dir / f"themes_{name}.json"
            if prior_path.exists():
                from lib import load_themes

                theme_sets.append(load_themes(prior_path))
                print(f"  [{name}] skipped (using cached)")
            continue
        print(f"  [{name}] running...", flush=True)
        llm = LLM()
        try:
            ts = runner(corpus, llm=llm)
            save_themes(ts, out_dir)
            theme_sets.append(ts)
            cost = ts.meta.get("cost_usd", 0)
            grand_cost += cost
            print(
                f"  [{name}] {len(ts.themes)} themes · "
                f"{ts.meta.get('elapsed_s', '?')}s · ${cost:.3f}"
            )
        except Exception as exc:
            print(f"  [{name}] FAILED: {exc}")
            traceback.print_exc()

    # Render
    render(corpus, theme_sets, out_dir / "compare.html", project=project)
    print(f"\nTotal cost for {project}: ${grand_cost:.3f}")
    print(f"Open: file://{out_dir / 'compare.html'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("projects", nargs="*", choices=["fossda", "ikea"], default=None)
    ap.add_argument(
        "--only",
        nargs="*",
        choices=["baseline", "a", "b", "c", "d", "e"],
        help="Only run these prototypes (others are reloaded from disk if present)",
    )
    args = ap.parse_args()
    projects = args.projects or list(CONFIGS.keys())
    for p in projects:
        run_project(p, only=args.only)


if __name__ == "__main__":
    main()
