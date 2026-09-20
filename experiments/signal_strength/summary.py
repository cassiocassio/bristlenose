"""The headline numbers quoted in docs/design-signal-strength.md.

Kept beside the harness so the note can be re-measured with one command
rather than re-argued.
"""
from __future__ import annotations

from collections import defaultdict

from metric import voices

from bristlenose.signals.metrics import adjusted_residual


def _matrix_totals(corpus: list[dict]):
    tot: dict = defaultdict(lambda: defaultdict(int))
    cols: dict = defaultdict(set)
    for c in corpus:
        key = (c["project"], c["framework"], c["axis"])
        tot[key]["grand"] += c["k"]
        tot[key][("row", c["location"])] += c["k"]
        tot[key][("col", c["group"])] += c["k"]
        cols[key].add(c["group"])
    return tot, cols


def _r_rule(cards: list[dict], metric: str):
    """Walk strongest first; keep a card only if it brings a new quote."""
    seen: set[int] = set()
    kept: list[dict] = []
    hidden: list[dict] = []
    for c in sorted(cards, key=lambda c: (-c[metric], -c["k"])):
        q = set(c["quote_ids"])
        (kept if q - seen else hidden).append(c)
        seen |= q
    return kept, hidden


def summarise(corpus: list[dict], floor: int = 2) -> None:
    cards = [c for c in corpus if c["k"] >= floor]
    projects = {c["project"] for c in corpus}
    print(f"\n=== corpus: {len(projects)} projects, {len(corpus)} "
          f"(location x group) pairs, {len(cards)} cards at k>={floor} ===")

    tot, cols = _matrix_totals(corpus)

    # 2a -- why concentration reads exactly 1.00
    # Classify by the mechanical cause in the ratio's own terms.  A lift is
    # exactly 1 when the cell's column or row carries the whole matrix.
    reasons: dict[str, int] = defaultdict(int)
    for c in cards:
        if abs(c["conc"] - 1.0) > 1e-9:
            continue
        key = (c["project"], c["framework"], c["axis"])
        t = tot[key]
        if t[("col", c["group"])] == t["grand"]:
            reasons["framework declares one column" if c["n_cols_declared"] == 1
                    else "the only column with any data"] += 1
        elif t[("row", c["location"])] == t["grand"]:
            reasons["row carries the whole matrix"] += 1
        else:
            reasons["coincidence"] += 1
    print(f"\n2a  concentration == 1.00 exactly: {sum(reasons.values())} "
          f"of {len(cards)} cards")
    for name, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"        {name:28s} {n}")
    sent = [c for c in cards if c["framework"].startswith("sentiment")]
    print(f"    sentiment-side cards {len(sent)}; distinct concentration values "
          f"{sorted({round(c['conc'], 6) for c in sent})[:6]}")

    # 2c -- adjusted_residual on the framework's own matrix
    zs = set()
    for c in [c for c in cards if c["framework"] == "sentiment"]:
        t = tot[(c["project"], c["framework"], c["axis"])]
        zs.add(round(adjusted_residual(c["k"], t[("row", c["location"])],
                                       t[("col", c["group"])], t["grand"]), 6))
    print(f"\n2c  adjusted_residual over the one-column cards: "
          f"{sorted(zs) if zs else '(none in this label set)'}")

    # 2d -- breadth overstatement
    over = [c for c in cards if c["n_eff"] > c["n_part"] + 1e-9]
    full = [c for c in cards
            if c["n_eff"] / c["P"] >= 0.999 and c["n_part"] < c["P"]]
    gt1 = [c for c in cards if c["n_eff"] / c["P"] > 1 + 1e-9]
    print(f"\n2d  n_eff exceeds the people who spoke : {len(over)} of "
          f"{len(cards)} ({len(over) / len(cards):.0%})")
    print(f"    breadth reads 1.00 on fewer people : {len(full)}")
    print(f"    breadth exceeds 1.00               : {len(gt1)}")
    if over:
        w = max(over, key=lambda c: c["n_eff"] - c["n_part"])
        print(f"    worst: people {w['part_counts']} ({w['n_part']} spoke) "
              f"n_eff={w['n_eff']:.2f} -> Hill {voices(w['part_counts']):.2f}, "
              f"P={w['P']}   [{w['project']}]")

    # 2e -- the composite has no ceiling
    print(f"\n2e  composite range {min(c['composite'] for c in cards):.2f} … "
          f"{max(c['composite'] for c in cards):.2f}  "
          f"(cards above 1.0: {sum(1 for c in cards if c['composite'] > 1)})")

    # 3 -- the degeneracy is gone
    ss = sorted(c["S"] for c in cards if c["kind"] == "sentiment")
    so = sorted(c["S"] for c in cards if c["kind"] == "codebook")
    for nm, v in (("sentiment side", ss), ("codebook side", so)):
        if v:
            print(f"\n3   surprise, {nm} : {min(v):.3f} … {max(v):.3f}"
                  f"  median {v[len(v) // 2]:.3f}  n={len(v)}")
    hs = [c["H"] for c in cards if c["kind"] == "sentiment"]
    hc = [c["H"] for c in cards if c["kind"] == "codebook"]
    if hs and hc:
        import statistics as _s
        print(f"    heat, sentiment median {_s.median(hs):.3f} vs codebook "
              f"{_s.median(hc):.3f}  gap {_s.median(hs) - _s.median(hc):+.3f}")
    print(f"    nothing to be surprised by (n_c == K_all): "
          f"{sum(1 for c in cards if c['n_c'] == c['K_all'])} cards")

    # 3 -- the floor, per project
    print("\n3   survivors of surprise >= 0.5, per project")
    per: dict = defaultdict(list)
    for c in cards:
        per[c["project"]].append(c)
    for proj, cs in sorted(per.items()):
        print(f"        {proj[:26]:26s} {len(cs):3d} cards  "
              f"{sum(1 for c in cs if c['S'] >= 0.5):3d} kept")

    # 7 -- absence
    ab = [c for c in corpus if c["S"] < 0.05]
    print(f"\n7   surprise < 0.05 over all {len(corpus)} pairs: {len(ab)} "
          f"— of which empty (k == 0): {sum(1 for c in ab if c['k'] == 0)}")
    for c in sorted((c for c in ab if c["k"] == 0), key=lambda c: c["S"]):
        print(f"        S={c['S']:.4f}  0 of {c['K_r']:3d} here, expected "
              f"{c['K_r'] * c['n_c'] / c['K_all']:4.1f}   "
              f"{c['group'][:26]} @ {c['location'][:30]}")

    # 8 -- the de-duplication rule
    print("\n8   de-duplication rule, run unguarded")
    byloc: dict = defaultdict(list)
    for c in cards:
        byloc[(c["project"], c["axis"], c["location"])].append(c)
    for metric in ("composite", "strength"):
        hid = hid_s = 0
        for cs in byloc.values():
            _, hidden = _r_rule(cs, metric)
            hid += len(hidden)
            hid_s += sum(1 for c in hidden if c["kind"] == "sentiment")
        print(f"        by {metric:10s}: {len(byloc)} locations, {len(cards)} "
              f"cards, {hid} hidden — the Sentiment card {hid_s} times")
    uniq = mixed = sup = sub = 0
    for cs in byloc.values():
        s_ = [c for c in cs if c["kind"] == "sentiment"]
        o_ = [c for c in cs if c["kind"] == "codebook"]
        if not s_ or not o_:
            continue
        mixed += 1
        sq = set(s_[0]["quote_ids"])
        cov: set[int] = set()
        for c in o_:
            oq = set(c["quote_ids"])
            cov |= oq
            if oq < sq:
                sup += 1
            elif sq < oq:
                sub += 1
        if sq - cov:
            uniq += 1
    print(f"        Sentiment cards bringing a quote no codebook card carries: "
          f"{uniq} of {mixed}")
    print(f"        codebook cell strictly inside the sentiment cell: {sup}; "
          f"the reverse: {sub}")

    # 10 -- floor independence
    print("\n10  floor independence")
    for f in (1, 2, 3):
        sel = sorted((c for c in corpus if c["k"] >= f),
                     key=lambda c: -c["strength"])
        v = sorted(c["strength"] for c in sel)
        print(f"        k>={f}: {len(sel):4d} cells  strength "
              f"{min(v):5.1f}…{max(v):5.1f}  median {v[len(v) // 2]:5.1f}   "
              f"single-quote cells in the top ten: "
              f"{sum(1 for c in sel[:10] if c['k'] == 1)}")
