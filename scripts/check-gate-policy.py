#!/usr/bin/env python3
"""Every soft gate must carry a disposition. No gate goes soft by default.

THE RULE

`continue-on-error` is how a check stops being a check. It is sometimes the
right call — an upstream CVE feed is news, not a defect — but a soft gate with
no stated end is how this repo lost three months of Swift test coverage:
docs/design-ci.md wrote "informational initially — promote to blocking once
stable" and no promotion ever came, because nothing was obliged to ask.

So every soft gate declares one of three dispositions in
docs/testing/soft-gates.json:

  ratchet      A number that may not rise. scripts/check-ratchet.py holds it.
               For debt too large to fix now and too easy to grow.
  expires      A date by which somebody must decide again. For things outside
               our control, where "fix it" is not the available action.
  conditional  Soft here, hard somewhere that matters. The macOS matrix is the
               model: informational on a push, blocking on a release tag.

This file fails when a soft gate has no disposition, when an `expires` date has
passed, when a `ratchet` names a metric that does not exist, or when the
registry describes a gate that no longer does.

WHAT IT CANNOT DO

It sees `continue-on-error` in workflow YAML. It does not see a gate made soft
some other way — a `|| true`, a piped exit status, an assertion written as
`cmd && ok`. Those have all been real here. Same limit as every mechanism in
this family: it catches what it models. docs/testing/gaps.md G7.

Usage:
  scripts/check-gate-policy.py            verify; exit 1 on any violation
  scripts/check-gate-policy.py --list     print the live soft gates and exit 0
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "docs/testing/soft-gates.json"
RATCHET = ROOT / "docs/testing/ratchet.json"
VALID = {"ratchet", "expires", "conditional"}


def live_soft_gates() -> dict[str, str]:
    """key -> the continue-on-error expression, for every soft gate in CI."""
    import yaml

    found: dict[str, str] = {}
    for f in sorted((ROOT / ".github/workflows").glob("*.yml")):
        wf = yaml.safe_load(f.read_text()) or {}
        for jid, job in (wf.get("jobs") or {}).items():
            if not isinstance(job, dict):
                continue
            if job.get("continue-on-error") is not None:
                found[f"{f.name}::{jid}"] = str(job["continue-on-error"])
            for st in job.get("steps") or []:
                if isinstance(st, dict) and st.get("continue-on-error") is not None:
                    name = st.get("name") or "(unnamed)"
                    found[f"{f.name}::{jid}::{name}"] = str(st["continue-on-error"])
    return found


def main() -> int:
    live = live_soft_gates()
    if "--list" in sys.argv:
        for k, v in sorted(live.items()):
            print(f"  {k}\n      continue-on-error: {v}")
        return 0

    reg = json.loads(REGISTRY.read_text()).get("gates", {})
    ratchets = json.loads(RATCHET.read_text()) if RATCHET.exists() else {}
    today = _dt.date.today()
    problems: list[str] = []

    for key in sorted(live):
        entry = reg.get(key)
        if entry is None:
            problems.append(
                f"UNDECLARED soft gate: {key}\n"
                f"    Add it to {REGISTRY.relative_to(ROOT)} with a disposition:\n"
                f"    ratchet (a number that may not rise) | expires (a date to decide again)\n"
                f"    | conditional (hard somewhere that matters). A gate does not go soft by default."
            )
            continue
        disp = entry.get("disposition")
        if disp not in VALID:
            problems.append(f"{key}: disposition {disp!r} is not one of {sorted(VALID)}")
        elif disp == "ratchet":
            metric = entry.get("ratchet")
            if metric not in ratchets:
                problems.append(
                    f"{key}: disposition is 'ratchet' but metric {metric!r} is not in "
                    f"{RATCHET.relative_to(ROOT)} — the ceiling it claims does not exist"
                )
        elif disp == "expires":
            raw = entry.get("expires")
            try:
                when = _dt.date.fromisoformat(str(raw))
            except (TypeError, ValueError):
                problems.append(f"{key}: expires {raw!r} is not an ISO date")
                continue
            if when <= today:
                problems.append(
                    f"REVIEW DUE: {key} expired {when}\n"
                    f"    {entry.get('why', '')}\n"
                    f"    Decide again: promote it, ratchet it, or set a new date and say why.\n"
                    f"    Bumping the date without a reason is the thing this exists to stop."
                )
        elif disp == "conditional" and not entry.get("hard_when"):
            problems.append(f"{key}: disposition 'conditional' must say hard_when")

    for key in sorted(set(reg) - set(live)):
        problems.append(
            f"STALE registry entry: {key} is declared but no longer a soft gate.\n"
            f"    Remove it — a registry describing gates that do not exist is how the docs got here."
        )

    if problems:
        print("GATE POLICY VIOLATIONS\n", file=sys.stderr)
        print("\n\n".join(problems), file=sys.stderr)
        return 1

    print(f"gate policy: {len(live)} soft gate(s), all declared")
    for key in sorted(live):
        e = reg[key]
        extra = e.get("expires") or e.get("ratchet") or e.get("hard_when", "")
        print(f"  {e['disposition']:<12} {key}  ({extra})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
