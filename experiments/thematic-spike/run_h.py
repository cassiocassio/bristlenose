"""One-shot driver for option_h on both corpora."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lib import LLM, load_corpus, save_themes
from prototypes import option_h


def main() -> None:
    for proj in ["fossda", "ikea"]:
        out_dir = HERE / "output" / proj
        corpus = load_corpus(out_dir / "corpus.json")
        llm = LLM()
        ts = option_h.run(corpus, llm=llm, project=proj)
        save_themes(ts, out_dir)
        sizes = [len(t.quote_indices) for t in ts.themes]
        smin = min(sizes) if sizes else 0
        smax = max(sizes) if sizes else 0
        smean = (sum(sizes) / len(sizes)) if sizes else 0.0
        print(
            f"{proj}: {len(ts.themes)} mini-clusters, "
            f"sizes min={smin} mean={smean:.1f} max={smax}, "
            f"{ts.meta.get('unassigned_count', 0)} unassigned "
            f"({ts.meta.get('unassigned_pct', 0.0)}%), "
            f"${ts.meta['cost_usd']:.3f}, "
            f"{ts.meta['elapsed_s']:.1f}s"
        )


if __name__ == "__main__":
    main()
