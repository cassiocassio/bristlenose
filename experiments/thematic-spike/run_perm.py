"""Driver for the three permission-variant prototypes.

Reuses the cached corpus.json from prior run_all.py runs (no re-sampling).
Runs perm_a, perm_b, perm_c against fossda + ikea, saves themes_*.json,
then re-renders compare.html for each.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import LLM, load_corpus, load_themes, save_themes
from prototypes import option_perm_a, option_perm_b, option_perm_c
from render import PROTOTYPE_ORDER, render

PROTOS = [
    ("perm_a", option_perm_a.run),
    ("perm_b", option_perm_b.run),
    ("perm_c", option_perm_c.run),
]


def main() -> None:
    grand = 0.0
    for project in ["fossda", "ikea"]:
        out_dir = Path(__file__).parent / "output" / project
        corpus = load_corpus(out_dir / "corpus.json")
        print(f"\n=== {project.upper()} — {len(corpus)} quotes ===")
        for name, runner in PROTOS:
            print(f"  [{name}] running...", flush=True)
            llm = LLM()
            try:
                ts = runner(corpus, llm=llm)
                save_themes(ts, out_dir)
                cost = ts.meta.get("cost_usd", 0)
                grand += cost
                print(
                    f"  [{name}] {len(ts.themes)} themes · "
                    f"{ts.meta.get('elapsed_s', '?')}s · ${cost:.3f}"
                )
            except Exception as exc:
                print(f"  [{name}] FAILED: {exc}")
                traceback.print_exc()

        # Re-render with whatever theme JSONs are present
        theme_sets = []
        for p in PROTOTYPE_ORDER:
            path = out_dir / f"themes_{p}.json"
            if path.exists():
                theme_sets.append(load_themes(path))
        render(corpus, theme_sets, out_dir / "compare.html", project=project)
        print(f"  rendered → file://{out_dir / 'compare.html'}")
    print(f"\nGrand total cost: ${grand:.3f}")


if __name__ == "__main__":
    main()
