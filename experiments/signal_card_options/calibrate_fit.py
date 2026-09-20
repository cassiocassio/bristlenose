"""Fit the label thresholds to the judgements. Reproduces build_calibrate's
sampling exactly, attaches the answers, and looks for where they separate."""
import collections, json, pathlib

HERE = pathlib.Path(__file__).resolve().parent
VAL = {"frustration": "neg", "confusion": "neg", "doubt": "neg", "surprise": "neu",
       "satisfaction": "pos", "delight": "pos", "confidence": "pos"}
ANS = ("A C C C C C B A A C C A A A A C A A B A A A A A A A A")  # 1..27 (14 revised C→A)

C = [c for c in json.load(open(HERE / "cards.json")) if c["group"] == "Sentiment"]
rows = []
for c in C:
    qs = [q for q in c["quotes"] if q["sentiment"] in VAL]
    if len(qs) < 2:
        continue
    wv, wl = collections.Counter(), collections.Counter()
    for q in qs:
        w = q["intensity"] or 1
        wv[q["sentiment"]] += w
        wl[VAL[q["sentiment"]]] += w
    tot = sum(wv.values()); top, tw = wv.most_common(1)[0]
    pos, neg, neu = wl.get("pos", 0), wl.get("neg", 0), wl.get("neu", 0)
    d = pos + neg
    rows.append(dict(c=c, wv=wv, n=len(qs), top=top, vshare=tw / tot,
                     pos=pos, neg=neg, neu=neu, nvals=len(wv),
                     lshare=(max(pos, neg) / d if d else 1.0),
                     lean=("Positive" if pos > neg else "Negative") if d else
                          ("Positive" if pos else "Negative" if neg else "-"),
                     clash=bool(pos and neg)))
band = lambda r: min(int(r["lshare"] * 10) * 10, 90)
picked, seen = [], collections.Counter()
for r in sorted([r for r in rows if r["clash"]], key=lambda r: r["lshare"]):
    if seen[band(r)] < 6:
        picked.append(r); seen[band(r)] += 1
anchors = sorted([r for r in rows if not r["clash"]], key=lambda r: -r["vshare"])
picked += anchors[:3] + anchors[len(anchors)//2:len(anchors)//2 + 2]
picked.sort(key=lambda r: r["lshare"])

ans = ANS.split()
assert len(ans) == len(picked), f"{len(ans)} answers vs {len(picked)} cases"
for r, a in zip(picked, ans):
    r["ans"] = a

print("%-3s %-4s %-7s %-7s %-5s %-4s %-22s %s" % (
    "#", "ans", "value%", "dir%", "vals", "clash", "top value", "location"))
for i, r in enumerate(picked, 1):
    print("%-3d %-4s %6.0f%% %6.0f%% %-5d %-5s %-22s %s" % (
        i, r["ans"], r["vshare"]*100, r["lshare"]*100, r["nvals"],
        "y" if r["clash"] else "-", f'{r["top"]} ({r["lean"]})', r["c"]["location"][:34]))

print("\n── separation ──")
for lab in "ABC":
    g = [r for r in picked if r["ans"] == lab]
    if not g: continue
    v = sorted(r["vshare"] for r in g); d = sorted(r["lshare"] for r in g)
    print("  %s  n=%-3d value%%  %3.0f–%3.0f   direction%%  %3.0f–%3.0f   vals %d–%d" % (
        lab, len(g), v[0]*100, v[-1]*100, d[0]*100, d[-1]*100,
        min(r["nvals"] for r in g), max(r["nvals"] for r in g)))

print("\n── does LEAN predict it better than dominance? ──")
t = collections.Counter((r["lean"], r["ans"]) for r in picked)
print("            A    B    C")
for lean in ("Positive", "Negative"):
    print("  %-9s %3d  %3d  %3d" % (lean, t[(lean,"A")], t[(lean,"B")], t[(lean,"C")]))
cl = [r for r in picked if r["clash"]]
print("\n  clashing cases only (n=%d):" % len(cl))
t2 = collections.Counter((r["lean"], r["ans"]) for r in cl)
for lean in ("Positive", "Negative"):
    n = sum(t2[(lean,a)] for a in "ABC")
    print("    %-9s n=%-3d A=%d  B=%d  C=%d   → %.0f%% named a feeling" % (
        lean, n, t2[(lean,"A")], t2[(lean,"B")], t2[(lean,"C")],
        100*t2[(lean,"A")]/n if n else 0))

print("\n── the positive vocabulary is near-synonymous; the negative is not ──")
for lean in ("Positive", "Negative"):
    vals = collections.Counter()
    for r in cl:
        if r["lean"] == lean:
            for v in r["wv"]:
                if VAL[v] == ("pos" if lean=="Positive" else "neg"): vals[v] += 1
    print("  %-9s %s" % (lean, dict(vals)))

print("\n── the negative cases, in your order ──")
for i, r in enumerate(picked, 1):
    if r["lean"] != "Negative" or not r["clash"]: continue
    negs = {v: w for v, w in r["wv"].items() if VAL[v] == "neg"}
    print("  %-3d %s  %-34s  neg: %-38s  pos: %s" % (
        i, r["ans"], r["c"]["location"][:34],
        ", ".join(f"{k} {v}" for k, v in sorted(negs.items(), key=lambda x: -x[1])),
        ", ".join(f"{k} {v}" for k, v in r["wv"].items() if VAL[k] == "pos")))
print("\n  distinct NEGATIVE values present, by answer:")
for a in "ABC":
    g = [r for r in picked if r["ans"] == a and r["lean"] == "Negative" and r["clash"]]
    if g:
        n = [len({v for v in r["wv"] if VAL[v] == "neg"}) for r in g]
        print("    %s  n=%-2d  distinct negative values: %s  (mean %.1f)" % (
            a, len(g), sorted(n), sum(n)/len(n)))

print("\n── 13 vs 14, raw ──")
for i in (13, 14):
    r = picked[i-1]
    print("  case %d  (%s)  %s" % (i, r["ans"], r["c"]["location"]))
    for q in sorted(r["qs"] if "qs" in r else r["c"]["quotes"], key=lambda q: (q["pid"], q["t"])):
        if q["sentiment"] in VAL:
            print("     %-4s %-12s i=%d  %s" % (q["pid"], q["sentiment"], q["intensity"],
                                                 q["text"][:74]))
    print()

print("── is the MINORITY's forcefulness the separator? ──")
print("%-3s %-4s %-8s %-9s %-9s %s" % ("#","ans","minority","min max-i","min mean-i","majority"))
for i, r in enumerate(picked, 1):
    if not r["clash"]: continue
    qs = [q for q in r["c"]["quotes"] if q["sentiment"] in VAL]
    maj = "pos" if r["pos"] > r["neg"] else "neg"
    mino = [q for q in qs if VAL[q["sentiment"]] not in (maj, "neu")]
    if not mino: continue
    mx = max(q["intensity"] or 1 for q in mino)
    mn = sum(q["intensity"] or 1 for q in mino)/len(mino)
    print("%-3d %-4s %-8s %-9d %-9.1f %s" % (
        i, r["ans"], f"{len(mino)}q {'pos' if maj=='neg' else 'neg'}", mx, mn,
        f"{r['pos'] if maj=='pos' else r['neg']}w"))

print("\n── is it WHO holds the feelings? ──")
print("%-3s %-4s %-12s %-26s %s" % ("#","ans","structure","who","location"))
tab = collections.Counter()
for i, r in enumerate(picked, 1):
    if not r["clash"]: continue
    qs = [q for q in r["c"]["quotes"] if q["sentiment"] in VAL]
    P = {q["pid"] for q in qs if VAL[q["sentiment"]] == "pos"}
    N = {q["pid"] for q in qs if VAL[q["sentiment"]] == "neg"}
    if P - N and N - P:      s = "POLARISED"     # different people, opposed
    elif P & N:              s = "ambivalent"    # someone holds both
    else:                    s = "?"
    tab[(s, r["ans"])] += 1
    print("%-3d %-4s %-12s %-26s %s" % (
        i, r["ans"], s, f"+{sorted(P)} −{sorted(N)}"[:26], r["c"]["location"][:30]))
print("\n              A    B    C")
for s in ("ambivalent", "POLARISED"):
    n = sum(tab[(s,a)] for a in "ABC")
    print("  %-11s %3d  %3d  %3d    (n=%d)" % (s, tab[(s,"A")], tab[(s,"B")], tab[(s,"C")], n))

print("\n" + "="*78)
for i in (1, 2, 6, 13, 14, 16):
    r = picked[i-1]
    qs = sorted([q for q in r["c"]["quotes"] if q["sentiment"] in VAL],
                key=lambda q: (q["pid"], q["t"]))
    w = " · ".join(f"{v} {n}" for v, n in r["wv"].most_common())
    print("\nCASE %d — you said %s      %s · %s" % (
        i, r["ans"], r["c"]["project"], r["c"]["location"]))
    print("   weight: %s    (pos %d / neg %d)" % (w, r["pos"], r["neg"]))
    for q in qs:
        print("   %-4s %-12s i=%d  %s" % (q["pid"], q["sentiment"], q["intensity"], q["text"]))
