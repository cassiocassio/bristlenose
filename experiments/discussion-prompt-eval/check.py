"""Mechanical checks and agreement for every arm in an eval folder.

    .venv/bin/python experiments/discussion-prompt-eval/check.py EVAL_DIR [--ref claude-v100]

Writes EVAL_DIR/metrics.json and prints a summary. Checks per arm × study:
first-attempt schema validity, out-of-set values per field (and the kind/role
swaps by name), coverage (each turn once, no unknown ids), item/section ids
that exist and fit `kind`, `terse` length and presence, cluster-name variants,
attempts and salvage, and agreement with the reference arm per field (percent
and Cohen's kappa over all sent turns, a missing label counted as "∅").
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

from bristlenose.discussion.models import SessionLabelsOut
from bristlenose.llm.structured import salvage_items

KINDS = {"planned", "adlib", "new", "instruction", "chat"}
ROLES = {"opening", "core", "closing"}
MISSING = "∅"


def kappa(a: list[str], b: list[str]) -> float | None:
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb.get(k, 0) for k in ca) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def norm_cluster(s: str) -> str:
    s = re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()
    return " ".join(w[:-1] if w.endswith("s") and len(w) > 3 else w for w in s.split())


def raw_labels(raw: object) -> list[dict]:
    if isinstance(raw, dict) and isinstance(raw.get("labels"), list):
        return [x for x in raw["labels"] if isinstance(x, dict)]
    return []


def attempt_stats(raw: object) -> dict[str, int]:
    labs = raw_labels(raw)
    kinds = [x.get("kind") for x in labs]
    roles = [x.get("role", "core") for x in labs]
    return {
        "labels": len(labs),
        "kind_out_of_set": sum(k not in KINDS for k in kinds),
        "role_in_kind": sum(k in ROLES for k in kinds),           # the measured confusion
        "role_out_of_set": sum(r not in ROLES for r in roles),
        "kind_in_role": sum(r in KINDS for r in roles),
        "role_missing": sum("role" not in x for x in labs),
    }


def replay_kept(raw: object, *, coerce: bool) -> int:
    """Labels the last resort keeps from *raw* (0 when it refuses the reply)."""
    if not isinstance(raw, dict):
        return 0
    data = copy.deepcopy(raw)
    if coerce:
        for x in raw_labels(data):
            for f in ("item_id", "section_id", "cluster", "terse"):
                if f in x and x[f] is None:
                    x[f] = ""
    try:
        return len(SessionLabelsOut.model_validate(data).labels)
    except ValidationError:
        got = salvage_items(data, SessionLabelsOut)
        return 0 if got is None else len(got.result.labels)


def label_map(labels: list[dict]) -> dict[str, dict]:
    return {lb["turn_id"]: lb for lb in labels}


def target(lb: dict | None) -> str:
    if lb is None:
        return MISSING
    k = lb["kind"]
    return lb.get("item_id") or MISSING if k == "planned" else (
        lb.get("section_id") or MISSING if k == "adlib" else k)


def session_checks(rec: dict, turns: list[dict], spine: list[dict]) -> dict:
    sent = [t["id"] for t in turns]
    items = {it["id"] for s in spine for it in s["items"]}
    sections = {s["id"] for s in spine}
    raws = rec.get("raw") or []
    attempts = rec.get("attempts", 0)
    parse_errors = len(rec.get("parse_errors") or [])
    if not attempts and "Expecting value" in str(rec.get("error")):
        # recorded before the recorder logged unparseable replies: 3 of them
        attempts = parse_errors = 3
    out: dict[str, object] = {"n": len(sent), "attempts": attempts, "parse_errors": parse_errors,
                              "failed": bool(rec.get("error")), "dropped": rec.get("dropped") or 0}
    first = raws[0] if raws else None
    try:
        SessionLabelsOut.model_validate(first)
        out["first_valid"] = True
    except (ValidationError, TypeError):
        out["first_valid"] = False
    out["per_attempt"] = [attempt_stats(r) for r in raws]
    # Replay the last reply through the product's own last resort, as is and
    # with JSON nulls in the string fields read as "" (a code-side lever, not
    # in the product): how many labels would the stage have kept?
    last = raws[-1] if raws else None
    out["replay_kept"] = replay_kept(last, coerce=False)
    out["replay_kept_nulls_as_empty"] = replay_kept(last, coerce=True)
    # what the stage got (after any retry, repair or salvage)
    labs = rec.get("labels") or []
    ids = Counter(lb["turn_id"] for lb in labs)
    out["unknown_ids"] = sum(1 for i in ids if i not in set(sent))
    out["duplicates"] = sum(c - 1 for c in ids.values() if c > 1)
    out["unlabelled"] = sum(1 for i in sent if i not in ids)
    bad_fit = 0
    for lb in labs:
        k = lb["kind"]
        if k == "planned" and lb.get("item_id") not in items:
            bad_fit += 1
        elif k == "adlib" and lb.get("section_id") not in sections:
            bad_fit += 1
        elif k == "new" and not lb.get("cluster", "").strip():
            bad_fit += 1
    out["bad_fit"] = bad_fit
    # terse on the accepted raw reply (the model clips at 30, so read before it)
    acc = raw_labels(raws[-1]) if raws else []
    unp = [x for x in acc if x.get("kind") in ("adlib", "new")]
    other = [x for x in acc if x.get("kind") in KINDS - {"adlib", "new"}]
    out["terse_over_24"] = sum(len(str(x.get("terse", ""))) > 24 for x in unp)
    out["terse_missing"] = sum(not str(x.get("terse", "")).strip() for x in unp)
    out["terse_on_other"] = sum(bool(str(x.get("terse", "")).strip()) for x in other)
    out["unplanned"] = len(unp)
    clusters = [lb.get("cluster", "").strip() for lb in labs if lb["kind"] == "new" and lb.get("cluster")]
    names = set(clusters)
    normed = {norm_cluster(c) for c in names}
    out["clusters"] = len(names)
    out["cluster_variants"] = len(names) - len(normed)  # same name spelled two ways
    out["kind_dist"] = dict(Counter(lb["kind"] for lb in labs))
    out["role_dist"] = dict(Counter(lb.get("role", "core") for lb in labs))
    return out


def agree(ref: dict, arm: dict, sent: list[str]) -> dict[str, list[str]]:
    r, a = label_map(ref.get("labels") or []), label_map(arm.get("labels") or [])
    cols: dict[str, list[str]] = {"kind_ref": [], "kind": [], "role_ref": [], "role": [],
                                  "target_ref": [], "target": []}
    for t in sent:
        rl, al = r.get(t), a.get(t)
        cols["kind_ref"].append(rl["kind"] if rl else MISSING)
        cols["kind"].append(al["kind"] if al else MISSING)
        cols["role_ref"].append(rl.get("role", "core") if rl else MISSING)
        cols["role"].append(al.get("role", "core") if al else MISSING)
        cols["target_ref"].append(target(rl))
        cols["target"].append(target(al))
    return cols


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("eval_dir")
    ap.add_argument("--ref", default="claude-v100")
    args = ap.parse_args()
    ev = Path(args.eval_dir)
    inputs = {p.stem.removeprefix("inputs-"): json.loads(p.read_text(encoding="utf-8"))
              for p in ev.glob("inputs-*.json") if p.stem != "inputs-manifest"}
    arms = {p.stem.removeprefix("arm-"): json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(ev.glob("arm-*.json"))}
    ref = arms.get(args.ref)
    metrics: dict[str, dict] = {}
    for an, arm in arms.items():
        m: dict[str, dict] = {"_meta": {k: arm[k] for k in ("prompt", "llm", "model")}}
        for sn, sess in arm["studies"].items():
            inp = inputs[sn]
            rows = {}
            pooled: dict[str, list[str]] = {}
            for sid, rec in sess.items():
                turns = inp["sessions"][sid]
                rows[sid] = session_checks(rec, turns, inp["spine"])
                if ref and sid in ref["studies"].get(sn, {}):
                    for k, v in agree(ref["studies"][sn][sid], rec, [t["id"] for t in turns]).items():
                        pooled.setdefault(k, []).extend(v)
                if "gold" in inp:
                    g = inp["gold"]
                    lm = label_map(rec.get("labels") or [])
                    for t in turns:
                        if t["id"] in g:
                            pooled.setdefault("kind_gold", []).append(g[t["id"]]["kind"])
                            pooled.setdefault("kind_vs_gold", []).append(
                                lm[t["id"]]["kind"] if t["id"] in lm else MISSING)
            s: dict[str, object] = {"sessions": rows}
            if pooled.get("kind_ref"):
                for f in ("kind", "role", "target"):
                    a, b = pooled[f + "_ref"], pooled[f]
                    s[f"{f}_pct"] = round(100 * sum(x == y for x, y in zip(a, b, strict=True)) / len(a), 1)
                    k = kappa(a, b)
                    s[f"{f}_kappa"] = None if k is None else round(k, 3)
            if pooled.get("kind_gold"):
                a, b = pooled["kind_gold"], pooled["kind_vs_gold"]
                s["kind_gold_pct"] = round(100 * sum(x == y for x, y in zip(a, b, strict=True)) / len(a), 1)
                s["kind_gold_kappa"] = round(kappa(a, b) or 0, 3)
            m[sn] = s
        metrics[an] = m
    (ev / "metrics.json").write_text(json.dumps(metrics, indent=1), encoding="utf-8")

    # summary
    for an, m in metrics.items():
        meta = m["_meta"]
        print(f"\n== {an}  ({meta['llm']} {meta['model']}, prompt {meta['prompt']})")
        for sn, s in m.items():
            if sn == "_meta":
                continue
            rs = s["sessions"].values()
            tot = lambda k, rs=rs: sum(r[k] for r in rs)  # noqa: E731
            pa = [a for r in rs for a in r["per_attempt"]]
            print(f"  {sn:20s} sess={len(rs)} turns={tot('n')} failed={tot('failed')} "
                  f"first_valid={sum(r['first_valid'] for r in rs)}/{len(rs)} "
                  f"attempts={tot('attempts')} dropped={tot('dropped')} unlabelled={tot('unlabelled')} "
                  f"unknown={tot('unknown_ids')} dup={tot('duplicates')} badfit={tot('bad_fit')} "
                  f"role_in_kind(all attempts)={sum(a['role_in_kind'] for a in pa)} "
                  f"kind_oos={sum(a['kind_out_of_set'] for a in pa)} role_oos={sum(a['role_out_of_set'] for a in pa)} "
                  f"terse>24={tot('terse_over_24')}/{tot('unplanned')} terse_missing={tot('terse_missing')} "
                  f"terse_on_other={tot('terse_on_other')} clusters={tot('clusters')} variants={tot('cluster_variants')}")
            if "kind_pct" in s:
                print(f"  {'':20s} vs ref: kind {s['kind_pct']}% κ={s['kind_kappa']} | role {s['role_pct']}% "
                      f"κ={s['role_kappa']} | target {s['target_pct']}% κ={s['target_kappa']}")
            if "kind_gold_pct" in s:
                print(f"  {'':20s} vs gold: kind {s['kind_gold_pct']}% κ={s['kind_gold_kappa']}")


if __name__ == "__main__":
    main()
