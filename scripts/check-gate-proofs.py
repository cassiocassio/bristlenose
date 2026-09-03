#!/usr/bin/env python3
"""For every gate: has anyone ever seen it go red?

THE QUESTION NOTHING ELSE ASKS

"Is it passing" and "can it fail" are different questions, and only the first is
ever asked. `mac-build.yml` answered the first correctly every day from 20 May to
2 Sep 2026 while being structurally incapable of failing — green on runs carrying
16 compile errors, and `v0.29.0` shipped on nine channels with the Swift suite
red underneath it.

A gate whose red nobody has seen is not passing. It is unproven.

HOW A PROOF IS ESTABLISHED, cheapest first

  automated   A paired self-test exists — `test-<name>` or `test-check-<name>`
              beside the gate. It re-proves the failure path on every run, so it
              never goes stale. This is the one to aim for.
  declared    Something the naming convention cannot see: an inline self-test, a
              pytest, or a human who watched it go red on a date. Manual entries
              carry `observed` and AGE — a proof from two years ago is a claim
              about a script that has since been rewritten.
  unproven    Nobody has ever watched this fail.

WHY THIS DOES NOT DEMAND ZERO

18 of 21 gates were unproven when this was written. A gate demanding all of them
be proven today would be unmeetable, and an unmeetable gate is one somebody
switches off — which this repo has paid for. So the count is held by the ratchet
(`gates_without_proof`) instead: existing debt is frozen, and a NEW gate has to
arrive with a proof or push the number up and fail.

ITS OWN LIMIT

The automated bucket is derived from a naming convention, so a gate proven some
other way looks unproven until someone declares it. And nothing here verifies
that a paired `test-*` actually exercises the failure path rather than merely
existing. Both are gaps.md G7: it catches what it models.

Usage:
  scripts/check-gate-proofs.py           report the three buckets
  scripts/check-gate-proofs.py --json    machine-readable (the ratchet reads this)
  scripts/check-gate-proofs.py --stale N flag declared proofs older than N days
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTER = ROOT / "docs/testing/gate-proofs.json"
DIRS = ("scripts", "desktop/scripts")


def discover() -> tuple[dict[str, str], set[str]]:
    gates: dict[str, str] = {}
    tests: set[str] = set()
    for d in DIRS:
        for f in sorted((ROOT / d).glob("*")):
            if not f.is_file() or f.suffix not in {".sh", ".py"}:
                continue
            if f.stem.startswith("check-"):
                gates[f.stem] = f"{d}/{f.name}"
            elif f.stem.startswith("test-"):
                tests.add(f.stem)
    return gates, tests


def paired_test(stem: str, tests: set[str]) -> str | None:
    base = stem[len("check-"):]
    for cand in (f"test-{stem}", f"test-{base}"):
        if cand in tests:
            return cand
    return None


def classify() -> dict:
    gates, tests = discover()
    reg = json.loads(REGISTER.read_text()) if REGISTER.exists() else {}
    declared = reg.get("declared", {})
    for extra, meta in (reg.get("extra_gates") or {}).items():
        gates.setdefault(extra, meta.get("path", "?"))

    excluded = reg.get("excluded", {})
    out = {"automated": {}, "declared": {}, "unproven": [], "excluded": {}}
    for stem, path in sorted(gates.items()):
        if stem in excluded:
            # Not every `check-*` is a gate. check-python-band.py is a
            # measurement run at the quarterly tooling review; it has no red to
            # observe. Excluding it is honest; excluding a real gate to get the
            # count down is not, which is why exclusions carry a reason and are
            # printed in the report rather than hidden.
            out["excluded"][stem] = {"path": path, **excluded[stem]}
            continue
        t = paired_test(stem, tests)
        if t:
            out["automated"][stem] = {"path": path, "proof": t}
        elif stem in declared:
            out["declared"][stem] = {"path": path, **declared[stem]}
        else:
            out["unproven"].append(stem)
    return out


def main() -> int:
    res = classify()
    if "--json" in sys.argv:
        print(json.dumps(res, indent=2, sort_keys=True))
        return 0

    stale_days = None
    if "--stale" in sys.argv:
        stale_days = int(sys.argv[sys.argv.index("--stale") + 1])

    print(f"automated ({len(res['automated'])}) — a paired self-test re-proves the red every run")
    for k, v in res["automated"].items():
        print(f"    {k:36} <- {v['proof']}")

    print(f"\ndeclared ({len(res['declared'])}) — proven another way; manual entries age")
    today = _dt.date.today()
    stale = []
    for k, v in res["declared"].items():
        obs = v.get("observed", "")
        age = ""
        if obs:
            try:
                d = (today - _dt.date.fromisoformat(obs)).days
                age = f"{d}d ago"
                if stale_days and d > stale_days:
                    stale.append(f"{k} ({age})")
            except ValueError:
                age = "unparseable date"
        print(f"    {k:36} {v.get('how','?')[:44]}  {age}")

    if res["excluded"]:
        print(f"\nexcluded ({len(res['excluded'])}) — check-* but not a gate; no red to observe")
        for k, v in res["excluded"].items():
            print(f"    {k:36} {v.get('why','?')[:60]}")

    print(f"\nunproven ({len(res['unproven'])}) — nobody has watched these fail")
    for k in res["unproven"]:
        print(f"    {k}")
    print("\nHeld by the ratchet metric `gates_without_proof`, not demanded to zero.")
    print("A new gate must arrive with a proof or push that number up and fail.")

    if stale:
        print("\nSTALE PROOFS — re-observe or automate:", file=sys.stderr)
        for s in stale:
            print(f"  {s}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
