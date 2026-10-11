"""Aggregate judge outputs into per-arm recall. Run from benchmark/.
Inputs: scores/judge-*.json (labels R*), scores/arm-mapping.json, optional
scores/judge-rep.json + rep-mapping.json (labels X*). Pass --exclude T1,S1 for
the sensitivity view, and --scores <dir> where the score files live (they are
kept outside the public tree; default ./scores)."""
import json, sys
pts = {"HIT": 1, "PARTIAL": 0.5, "MISS": 0}
scores = sys.argv[sys.argv.index("--scores") + 1] if "--scores" in sys.argv else "scores"
ex = set(sys.argv[sys.argv.index("--exclude") + 1].split(",")) if "--exclude" in sys.argv else set()
inv = {v: k for k, v in json.load(open(f"{scores}/arm-mapping.json")).items()}
J: dict = {}
for f in ("judge-py", "judge-ts", "judge-swift-a", "judge-swift-b"):
    for r, cases in json.load(open(f"{scores}/{f}.json")).items():
        J.setdefault(inv[r], {}).update(cases)
try:
    rm = json.load(open(f"{scores}/rep-mapping.json"))  # file label -> X*
    rinv = {v: k.replace("rep-", "").replace("-swift", "") + "r2" for k, v in rm.items()}
    for r, cases in json.load(open(f"{scores}/judge-rep.json")).items():
        J[rinv[r]] = cases
except FileNotFoundError:
    pass
for arm in sorted(J):
    c = {k: v for k, v in J[arm].items() if k not in ex}
    print(f"{arm:6s} cases={len(c):2d} recall={sum(pts[v['recall']] for v in c.values()):4.1f}")
