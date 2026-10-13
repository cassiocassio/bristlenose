"""Which signal says two visits are the same screen? Score each against hand labels.

    python3 experiments/screens-lens/identity.py <private screen-text dir>/<tag> [...]

Inputs (private, from visits.py and a hand pass over its contact sheets): screens/visits.json and
screens/labels.json, which gives every visit a **page** (what a sitemap node would be: the home page,
a category, the cart, the planner) and a **state** (the page plus any dialog, panel or drop-down
over it: "cart + postcode dialog"). Labels were written by looking at the frames, not at the signals.

Two questions, over every pair of visits in a session:
- **page**: are these two visits the same page?
- **state**: given they are the same page, are they the same state?

Signals: address-bar URL (path + #route, query dropped); its template (product slugs and ids masked);
line-set Jaccard; token-set Jaccard; token overlap (|A∩B| / min); TF-IDF cosine over tokens, IDF from
the session's visits, so navigation that is on every page weighs nothing; the tallest line (heading)
equal; dHash similarity (1 − min Hamming / 64 over the first, middle and last frames).

Reports, per signal: ROC AUC, and the best F1 over thresholds with its precision and recall. Then a
clustering check: average-linkage agglomeration at the best threshold, the number of clusters it makes
against the number of labels, and the adjusted Rand index. Aggregates only.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path


def auc(pos: list[float], neg: list[float]) -> float:
    if not pos or not neg:
        return float("nan")
    allv = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    # rank-sum with ties averaged
    ranks, i = {}, 0
    rsum = 0.0
    while i < len(allv):
        j = i
        while j < len(allv) and allv[j][0] == allv[i][0]:
            j += 1
        r = (i + j + 1) / 2
        rsum += r * sum(1 for k in range(i, j) if allv[k][1])
        i = j
    n1, n0 = len(pos), len(neg)
    return (rsum - n1 * (n1 + 1) / 2) / (n1 * n0)


def best_f1(pairs: list[tuple[float, bool]]) -> tuple[float, float, float, float]:
    best = (0.0, 0.0, 0.0, 0.0)
    for th in sorted({s for s, _ in pairs}):
        tp = sum(1 for s, y in pairs if s >= th and y)
        fp = sum(1 for s, y in pairs if s >= th and not y)
        fn = sum(1 for s, y in pairs if s < th and y)
        if tp == 0:
            continue
        p, r = tp / (tp + fp), tp / (tp + fn)
        f = 2 * p * r / (p + r)
        if f > best[0]:
            best = (f, p, r, th)
    return best


def ari(a: list[str], b: list[int]) -> float:
    n = len(a)
    c = Counter(zip(a, b))
    comb = lambda k: k * (k - 1) / 2  # noqa: E731
    sij = sum(comb(v) for v in c.values())
    sa = sum(comb(v) for v in Counter(a).values())
    sb = sum(comb(v) for v in Counter(b).values())
    exp = sa * sb / comb(n)
    mx = (sa + sb) / 2
    return (sij - exp) / (mx - exp) if mx != exp else 1.0


def cluster(n: int, sim, th: float) -> list[int]:
    groups = [[i] for i in range(n)]
    while True:
        best, bi, bj = -1.0, -1, -1
        for i, j in combinations(range(len(groups)), 2):
            s = sum(sim(a, b) for a in groups[i] for b in groups[j]) / (len(groups[i]) * len(groups[j]))
            if s > best:
                best, bi, bj = s, i, j
        if best < th:
            break
        groups[bi] += groups.pop(bj)
    out = [0] * n
    for g, members in enumerate(groups):
        for m in members:
            out[m] = g
    return out


def main() -> None:
    for root in map(Path, sys.argv[1:]):
        vs = json.loads((root / "screens" / "visits.json").read_text())
        lab = json.loads((root / "screens" / "labels.json").read_text())
        page = [lab["page"][str(v["v"])] for v in vs]
        state = [lab["state"][str(v["v"])] for v in vs]
        df = Counter(t for v in vs for t in set(v["tokens"]))
        N = len(vs)
        vecs = []
        for v in vs:
            w = {t: math.log(N / df[t]) for t in v["tokens"]}
            norm = math.sqrt(sum(x * x for x in w.values())) or 1
            vecs.append({t: x / norm for t, x in w.items()})

        def jac(a, b):
            a, b = set(a), set(b)
            return len(a & b) / len(a | b) if a | b else 0.0

        def url_key(v):
            return (v["page"], v["frag"]) if v["page"] else None

        def tmpl_key(v):
            return (v["template"], v["frag"]) if v["template"] else None

        sigs = {
            "url (path + #route)": lambda a, b: 0.5 if not (url_key(a) and url_key(b)) else float(url_key(a) == url_key(b)),
            "url template": lambda a, b: 0.5 if not (tmpl_key(a) and tmpl_key(b)) else float(tmpl_key(a) == tmpl_key(b)),
            "line-set Jaccard": lambda a, b: jac(a["lines"], b["lines"]),
            "token Jaccard": lambda a, b: jac(a["tokens"], b["tokens"]),
            "token overlap": lambda a, b: (len(set(a["tokens"]) & set(b["tokens"])) / min(len(a["tokens"]), len(b["tokens"])))
            if a["tokens"] and b["tokens"] else 0.0,
            "TF-IDF cosine": lambda a, b: sum(x * vecs[b["v"]].get(t, 0) for t, x in vecs[a["v"]].items()),
            "heading equal": lambda a, b: float(bool(a["head"]) and a["head"] == b["head"]),
            "dHash": lambda a, b: 1 - min(bin(x ^ y).count("1") for x in a["dhash"] for y in b["dhash"]) / 64,
        }
        sigs["url, else TF-IDF"] = lambda a, b: (sigs["url (path + #route)"](a, b) if url_key(a) and url_key(b)
                                                  else sigs["TF-IDF cosine"](a, b))
        print(f"\n== {root.name}: {N} visits, {len(set(page))} pages, {len(set(state))} states (hand labels)")
        for level, truth in (("page", page), ("state within a page", state)):
            print(f"-- {level}")
            print(f"  {'signal':24} {'AUC':>5} {'F1':>5} {'P':>5} {'R':>5} {'th':>5}  clusters  ARI")
            for name, f in sigs.items():
                pairs = []
                for i, j in combinations(range(N), 2):
                    if level != "page" and page[i] != page[j]:
                        continue
                    pairs.append((f(vs[i], vs[j]), truth[i] == truth[j]))
                a = auc([s for s, y in pairs if y], [s for s, y in pairs if not y])
                f1, p, r, th = best_f1(pairs)
                if level == "page":
                    cl = cluster(N, lambda x, y: f(vs[x], vs[y]), th)
                    extra = f"{len(set(cl)):>8}  {ari(truth, cl):.2f}"
                else:
                    extra = ""
                print(f"  {name:24} {a:5.2f} {f1:5.2f} {p:5.2f} {r:5.2f} {th:5.2f}  {extra}")


if __name__ == "__main__":
    main()
