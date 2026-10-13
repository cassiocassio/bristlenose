"""Does an observed screen sequence agree with what the pipeline inferred from speech, and do quotes land on screens?

    python3 experiments/screens-lens/flows.py <tag>=<private screen-text dir>/<tag>=<bristlenose-output dir> [...]

Per session, from visits.json + labels.json (hand page labels) and the run's intermediate files:

1. **Sequence.** Pages in order with consecutive repeats merged; how many steps, revisits, back-steps.
2. **Cross-session alignment by URL template.** The address bar's path with the locale prefix
   (/de/de, /gb/en) dropped and product slugs, ids and search terms masked. Text cannot align a German
   and an English session; the URL's structure can.
3. **Quotes on screens.** Each extracted quote's interval against the page intervals: is it said
   during the share, on which page (largest overlap), and how pure each report section
   (screen_clusters.json, the LLM's speech-derived screens) is against the page actually on screen.
4. **Speech-detected screen changes.** topic_boundaries.json `screen_change` boundaries against the
   observed page transitions: recall within ±30 s, and precision.

Aggregates and template paths only (public site structure); no quote text, no participant names.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

WINDOW = 30.0


def template(page: str | None, frag: str | None) -> str | None:
    if not page:
        return None
    p = re.sub(r"^[a-z0-9.-]+?\.(?:com|de|co\.uk)", "", page)
    p = re.sub(r"^/[a-z]{2}/[a-z]{2}(?=/|$)", "", p)          # locale prefix
    p = re.sub(r"/p/[^/]+", "/p/*", p)
    p = re.sub(r"/cat/[^/]+", "/cat/*", p)
    p = re.sub(r"/addon-app/.*", "/planner-app", p)
    p = re.sub(r"/se$", "/search", p)
    p = p or "/"
    return p + (("#" + re.sub(r"/[#\d]+$", "", frag)) if frag else "")


def main() -> None:
    graphs: dict[str, list[str]] = {}
    for arg in sys.argv[1:]:
        tag, st, out = arg.split("=")
        vs = json.loads((Path(st) / "screens" / "visits.json").read_text())
        lab = json.loads((Path(st) / "screens" / "labels.json").read_text())
        inter = Path(out) / ".bristlenose" / "intermediate"
        quotes = json.loads((inter / "extracted_quotes.json").read_text())
        clusters = json.loads((inter / "screen_clusters.json").read_text())
        bounds = json.loads((inter / "topic_boundaries.json").read_text())[0]["boundaries"]
        page = [lab["page"][str(v["v"])] for v in vs]
        ivs = [(v["t0"], v["t1"], p) for v, p in zip(vs, page)]
        share0, share1 = vs[0]["t0"], vs[-1]["t1"]

        seq = []
        for (a, b, p) in ivs:
            if seq and seq[-1][0] == p:
                seq[-1][2] = b
            else:
                seq.append([p, a, b])
        names = [s[0] for s in seq]
        revisits = sum(1 for k, n in enumerate(names) if n in names[:k])
        back = sum(1 for k in range(2, len(names)) if names[k] == names[k - 2])
        tmpl = []
        for v in vs:
            t = template(v["page"], v["frag"])
            if t and (not tmpl or tmpl[-1] != t):
                tmpl.append(t)
        graphs[tag] = tmpl

        def page_at(a: float, b: float) -> str | None:
            ov = Counter()
            for (x, y, p) in ivs:
                o = min(b, y) - max(a, x)
                if o > 0:
                    ov[p] += o
            return ov.most_common(1)[0][0] if ov else None

        in_share = [q for q in quotes if float(q["end_timecode"]) > share0 and float(q["start_timecode"]) < share1]
        on_page = [q for q in in_share if page_at(float(q["start_timecode"]), float(q["end_timecode"]))]
        purity, sec_rows = [], []
        for c in clusters:
            pages = [page_at(float(q["start_timecode"]), float(q["end_timecode"])) for q in c["quotes"]]
            pages = [p for p in pages if p]
            if pages:
                top, n = Counter(pages).most_common(1)[0]
                purity.append((n, len(pages)))
                sec_rows.append(f"{len(c['quotes'])} quotes → {len(set(pages))} page(s), top page holds {n}")
        quotes_per_page = Counter(page_at(float(q["start_timecode"]), float(q["end_timecode"])) for q in on_page)
        trans = [s[1] for s in seq[1:]]
        sc = [b["timecode_seconds"] for b in bounds if b["transition_type"] == "screen_change"]
        sc_in = [t for t in sc if share0 - WINDOW <= t <= share1]
        hit = sum(1 for t in trans if any(abs(t - s) <= WINDOW for s in sc_in))
        prec = sum(1 for s in sc_in if any(abs(t - s) <= WINDOW for t in trans))
        print(f"\n== {tag}")
        print(f"share {share0 / 60:.1f}–{share1 / 60:.1f} min; {len(vs)} visits; {len(set(page))} pages; "
              f"sequence {len(seq)} steps, {revisits} revisits, {back} back-steps (A→B→A)")
        print(f"template path: {' → '.join(tmpl)}")
        print(f"quotes: {len(quotes)} extracted, {len(in_share)} during the share, {len(on_page)} on a page; "
              f"pages with ≥1 quote: {len([p for p in quotes_per_page if p])}/{len(set(page))}; "
              f"per page {sorted(quotes_per_page.values(), reverse=True)}")
        print(f"report sections (speech-derived screens): {len(clusters)}; quotes on their section's top page: "
              f"{sum(n for n, _ in purity)}/{sum(t for _, t in purity)}")
        for r in sec_rows:
            print("   ", r)
        print(f"screen_change boundaries in share: {len(sc_in)}; observed page transitions: {len(trans)}; "
              f"transitions with a speech boundary within ±{WINDOW:.0f}s: {hit}; boundaries near a transition: {prec}")
    if len(graphs) > 1:
        sets = [set(g) for g in graphs.values()]
        common = set.intersection(*sets)
        edges = [Counter(zip(g, g[1:])) for g in graphs.values()]
        shared_edges = set.intersection(*[set(e) for e in edges])
        print(f"\ncross-session: templates {[len(s) for s in sets]}, shared {len(common)}: {sorted(common)}")
        print(f"edges {[len(e) for e in edges]}, shared {len(shared_edges)}: {sorted(shared_edges)}")


if __name__ == "__main__":
    main()
