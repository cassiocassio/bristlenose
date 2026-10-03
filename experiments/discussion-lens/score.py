#!/usr/bin/env python3
"""Score Discussion-lens spike runs against a gold answer key, and against each other.

    .venv/bin/python experiments/discussion-lens/score.py \
        --gold experiments/discussion-lens/synthetic/gold.json \
        experiments/discussion-lens/runs/synthetic/run-*.json

Gold format: synthetic/make_corpus.py's gold.json (per-turn kind/item/section,
per-quote section). Pairwise co-membership F1 is label-free — it asks only
"are these two turns (quotes) in the same section (item) in both?" — so it
scores emergent sections whose names the model chose.

Exit criteria (plan §7, Phase 1a), checked and printed:
  unplanned share within ±5 points of gold; quote section agreement ≥ QUOTE_MIN;
  structure stable across runs (pairwise section agreement ≥ STABLE_MIN).
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
from collections import Counter
from pathlib import Path

UNPLANNED_TOL = 5.0      # points
QUOTE_MIN = 0.80         # final quote → section accuracy
STABLE_MIN = 0.90        # pairwise agreement between runs on asked-turn sections
EXCLUDE = ("new:recipes",)  # the planted tangent: there is no single right section for it


def words(s: str) -> set[str]:
    return set(re.findall(r"[a-z']+", s.lower())) - {"the", "a", "you", "do", "how", "what", "of", "to", "it", "is", "your", "and"}


def jaccard(a: str, b: str) -> float:
    x, y = words(a), words(b)
    return len(x & y) / max(len(x | y), 1)


def spine_map(run: dict, gold: dict) -> dict[str, str]:
    """pred spine item id → gold item id, by text; and pred section id → gold section id."""
    gold_items = {iid: txt for sec in gold["spine"].values() for iid, txt in sec["items"].items()}
    out = {}
    for s in run["spine"]:
        for it in s["items"]:
            best = max(gold_items, key=lambda g: jaccard(it["text"], gold_items[g]), default=None)
            if best and jaccard(it["text"], gold_items[best]) >= 0.3:
                out[it["id"]] = best
        votes = Counter(out[it["id"]].split(".")[0] for it in s["items"] if it["id"] in out)
        if votes:
            out[s["id"]] = votes.most_common(1)[0][0]
    return out


def collapse(kind: str) -> str:
    return {"planned": "planned", "adlib": "unplanned", "new": "unplanned"}.get(kind, "not a question")


def pair_f1(pred: dict[str, str], gold: dict[str, str]) -> float:
    keys = sorted(set(pred) & set(gold))
    tp = fp = fn = 0
    for a, b in itertools.combinations(keys, 2):
        p, g = pred[a] == pred[b], gold[a] == gold[b]
        tp += p and g
        fp += p and not g
        fn += g and not p
    return 2 * tp / max(2 * tp + fp + fn, 1)


def pair_agreement(x: dict[str, str], y: dict[str, str]) -> float:
    keys = sorted(set(x) & set(y))
    pairs = list(itertools.combinations(keys, 2))
    return sum((x[a] == x[b]) == (y[a] == y[b]) for a, b in pairs) / max(len(pairs), 1)


def turn_sections(run: dict) -> dict[str, str]:
    item_sec = {it["id"]: s["id"] for s in run["sections"] for it in s["items"]}
    return {t["id"]: item_sec.get(t["item"], "standalone") for t in run["turns"] if t["item"]}


def score(run: dict, gold: dict) -> dict:
    m = spine_map(run, gold)
    gt = gold["turns"]
    pred_turn = {t["id"]: t for t in run["turns"]}
    r: dict = {}

    # 1. turn kinds
    ok = sum(collapse(pred_turn[tid]["kind"]) == collapse(g["kind"]) for tid, g in gt.items() if tid in pred_turn)
    r["turn kind accuracy"] = ok / len(gt)
    conf = Counter((collapse(g["kind"]), collapse(pred_turn[tid]["kind"])) for tid, g in gt.items()
                   if tid in pred_turn and collapse(pred_turn[tid]["kind"]) != collapse(g["kind"]))
    r["turn kind errors"] = {f"{a} → {b}": n for (a, b), n in conf.items()}

    # 2. planned items
    planned = [(tid, g) for tid, g in gt.items() if g["kind"] == "planned"]
    r["planned item accuracy"] = sum(m.get(pred_turn[tid]["item"] or "") == g["item"]
                                     for tid, g in planned) / max(len(planned), 1)

    # 3. unplanned share
    def share(kinds: list[str]) -> float:
        asked = [k for k in kinds if collapse(k) != "not a question"]
        return 100 * sum(collapse(k) == "unplanned" for k in asked) / max(len(asked), 1)
    r["unplanned share gold"] = share([g["kind"] for g in gt.values()])
    r["unplanned share pred"] = share([pred_turn[t]["kind"] for t in gt if t in pred_turn])

    # 4. never-asked planned items survive, marked planned
    asked_gold_items = {g.get("item") for g in gt.values()}
    never = [iid for sec in gold["spine"].values() if sec["kind"] != "instruction"
             for iid in sec["items"] if iid not in asked_gold_items]
    inv = {g: p for p, g in m.items() if "." in p}
    src = {it["id"]: it["source"] for s in run["sections"] for it in s["items"]}
    r["never-asked kept"] = f"{sum(src.get(inv.get(i, ''), '') == 'planned' for i in never)}/{len(never)} ({', '.join(never)})"

    # 5. promotion
    ts = turn_sections(run)
    emergent = {s["id"]: s["title"] for s in run["sections"] if s["origin"] == "emergent"}
    def home(cluster: str) -> Counter:
        return Counter(ts.get(tid, "—") for tid, g in gt.items() if g.get("section") == cluster)
    b, rc = home("new:budget"), home("new:recipes")
    r["budget promoted"] = bool(b) and b.most_common(1)[0][0] in emergent and b.most_common(1)[0][1] >= 0.75 * sum(b.values())
    r["recipes not promoted"] = not any(k in emergent for k in rc)
    r["recipes landed in"] = dict(rc)
    r["emergent sections"] = list(emergent.values())

    # 6. turn → section, turn → item (pairwise, label-free)
    asked_gold = {tid: g for tid, g in gt.items() if collapse(g["kind"]) != "not a question"}
    gsec = {t: g["section"] for t, g in asked_gold.items() if g["section"] not in EXCLUDE}
    r["turn section F1"] = pair_f1({t: ts.get(t, "none") for t in gsec}, gsec)
    gitem = {t: g["item"] for t, g in asked_gold.items()}
    pitem = {t: (pred_turn[t]["item"] or f"none:{t}") for t in gitem if t in pred_turn}
    r["item merge F1"] = pair_f1(pitem, gitem)

    # 7. quotes → section: final, anchor-only, topic-only
    sec_to_gold = {}
    for sid in {s["id"] for s in run["sections"]}:
        votes = Counter(asked_gold[t]["section"] for t, s in ts.items() if s == sid and t in asked_gold)
        sec_to_gold[sid] = m.get(sid) or (votes.most_common(1)[0][0] if votes else sid)
    gq = {(q["session_id"], round(q["start"], 2)): q["section"] for q in gold["quotes"]}
    for field, name in (("section", "quote section (final)"), ("anchor_section", "quote section (anchor only)"),
                        ("topic_section", "quote section (topic only)")):
        hits = n = 0
        for q in run["quotes"]:
            g = gq.get((q["session"], round(q["sec"], 2)))
            if g is None or g in EXCLUDE:
                continue
            n += 1
            hits += sec_to_gold.get(q[field] or "", "∅") == g
        r[name] = hits / max(n, 1)
    r["quote routing"] = dict(Counter(q["how"] for q in run["quotes"]))
    r["cost usd"] = run["cost"]["usd"]
    r["calls"] = run["cost"]["calls"]
    return r


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", required=True)
    ap.add_argument("runs", nargs="+")
    a = ap.parse_args()
    gold = json.loads(Path(a.gold).read_text(encoding="utf-8"))
    runs = [json.loads(Path(p).read_text(encoding="utf-8")) for p in a.runs]
    scores = [score(r, gold) for r in runs]
    keys = list(scores[0])
    width = max(len(k) for k in keys)
    print(f"{'':{width}}  " + "  ".join(f"run {i + 1}" for i in range(len(runs))))
    for k in keys:
        vals = [s[k] for s in scores]
        cell = (lambda v: f"{v:.2f}" if isinstance(v, float) else str(v))
        print(f"{k:{width}}  " + "  ·  ".join(cell(v) for v in vals))
    if len(runs) > 1:
        print()
        sec_pairs = [pair_agreement(turn_sections(x), turn_sections(y)) for x, y in itertools.combinations(runs, 2)]
        item_pairs = [pair_agreement({t["id"]: t["item"] or "" for t in x["turns"] if t["item"]},
                                     {t["id"]: t["item"] or "" for t in y["turns"] if t["item"]})
                      for x, y in itertools.combinations(runs, 2)]
        sigs = [" | ".join(s["title"] for s in r["sections"] if s["kind"] != "instruction") for r in runs]
        print(f"stability: section agreement between runs {min(sec_pairs):.3f}–{max(sec_pairs):.3f} · "
              f"item agreement {min(item_pairs):.3f}–{max(item_pairs):.3f}")
        print(f"           {len(set(sigs))} distinct section signature(s)")
        for s in sorted(set(sigs)):
            print(f"             · {s}")
    print("\nPhase 1a exit criteria (synthetic):")
    mean = lambda k: sum(s[k] for s in scores) / len(scores)  # noqa: E731
    diff = max(abs(s["unplanned share pred"] - s["unplanned share gold"]) for s in scores)
    checks = [(f"unplanned share within ±{UNPLANNED_TOL:g} points (worst {diff:.1f})", diff <= UNPLANNED_TOL),
              (f"quote section accuracy ≥ {QUOTE_MIN} (mean {mean('quote section (final)'):.2f})",
               mean("quote section (final)") >= QUOTE_MIN),
              ("recurring topic promoted, one-session tangent not, every run",
               all(s["budget promoted"] and s["recipes not promoted"] for s in scores))]
    if len(runs) > 1:
        checks.append((f"stable across runs: section agreement ≥ {STABLE_MIN} (min {min(sec_pairs):.3f})",
                       min(sec_pairs) >= STABLE_MIN))
    for text, ok in checks:
        print(f"  {'✓' if ok else '✗'} {text}")
    total = sum((s["cost usd"] or 0) for s in scores)
    print(f"\ncost: ${total:.4f} over {len(runs)} run(s), {sum(s['calls'] for s in scores)} calls")


if __name__ == "__main__":
    main()
