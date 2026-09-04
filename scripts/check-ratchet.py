#!/usr/bin/env python3
"""Numbers that are allowed to be non-zero but not allowed to rise.

WHY A FOURTH GATE COLOUR

The vocabulary was hard / soft / informational, and none of them fits mypy.
Hard is a lie — 238 errors is a project, not a commit. Soft is what it has been
since it was added, and 238 is the evidence of what soft-with-no-ceiling buys.
Informational is soft with better manners.

So: a ratchet. The number may stay where it is; it may fall; it may not rise.
That is the only shape that makes a long-standing debt safe to leave alone
without letting it grow while nobody is obliged to look.

WHAT IT IS NOT

It is not a plan to reach zero, and it must not pretend to be. Nothing here
schedules the work; it only stops the bill increasing. See
docs/testing/gaps.md G3/G4 for the reasoning and G7 for the honest limits of
this whole family of mechanism.

TIGHTENING

When a number falls, the ceiling should follow it down — otherwise the slack
just gets re-spent. `--tighten` rewrites the ceilings to the measured values,
and refuses to raise any of them: a ratchet that can be loosened by the tool
that reads it is not a ratchet. Raising a ceiling is a deliberate edit to the
JSON, made by a person, in a commit that has to say why.

A metric marked `authority: ci` cannot be tightened from here at all, so its
route is the `ratchet tighten` workflow — `gh workflow run ratchet-tighten.yml`
— which measures on a fresh CI install and commits the lowered ceiling. That is
not ceremony: the number moves with whatever mypy a fresh install resolves, and
a ceiling set from the dev Mac failed its first CI run for exactly that reason.

Tightening PRESERVES anything in the JSON that the code does not own — `note`
above all, which is where the argument for a number lives. Rebuilding the entry
from METRICS deleted it silently, and two of the five entries carry one.

Usage:
  scripts/check-ratchet.py             measure and compare; exit 1 if any rose
  scripts/check-ratchet.py --tighten   lower ceilings to current values
  scripts/check-ratchet.py --json      machine-readable, no verdict
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CEILINGS = ROOT / "docs/testing/ratchet.json"


def _grep_count(pattern: str, path: Path) -> int:
    """Count regex matches across a tree, counting each occurrence, not each line."""
    total = 0
    for f in sorted(path.rglob("*")):
        if f.is_file() and f.suffix in {".py", ".ts", ".tsx", ".md"}:
            total += len(re.findall(pattern, f.read_text(errors="ignore")))
    return total


def measure_mypy() -> int | None:
    exe = ROOT / ".venv/bin/mypy"
    cmd = [str(exe)] if exe.exists() else ["mypy"]
    try:
        out = subprocess.run(
            [*cmd, "bristlenose/", "--ignore-missing-imports"],
            cwd=ROOT, capture_output=True, text=True, timeout=600,
        ).stdout
    except Exception:
        return None
    m = re.search(r"Found (\d+) errors?", out)
    if m:
        return int(m.group(1))
    # "Success: no issues found" is a real zero, not a failure to measure.
    return 0 if "Success" in out else None


def measure_unproven_gates() -> int | None:
    """Gates whose red nobody has ever watched — scripts/check-gate-proofs.py.

    Held rather than demanded to zero: 17 of 21 were unproven when this landed,
    and a gate nobody can satisfy is one somebody switches off. Freezing the
    count means existing debt stays put while a NEW gate has to arrive with a
    proof or push this up and fail.
    """
    try:
        out = subprocess.run(
            [sys.executable, str(ROOT / "scripts/check-gate-proofs.py"), "--json"],
            cwd=ROOT, capture_output=True, text=True, timeout=120,
        )
        return len(json.loads(out.stdout)["unproven"])
    except Exception:
        return None


METRICS: dict[str, dict] = {
    "gates_without_proof": {
        "measure": measure_unproven_gates,
        "basis": "scripts/check-gate-proofs.py --json, length of `unproven`",
        "why": "gaps.md G8 — 'is it passing' and 'can it fail' are different questions, "
               "and mac-build.yml answered the first correctly for three months while "
               "being incapable of the second",
    },
    "mypy_errors": {
        "measure": measure_mypy,
        "basis": "mypy bristlenose/ --ignore-missing-imports, 'Found N errors'",
        "why": "gaps.md G3 — soft since it was added, which is how it reached 238",
        # ENVIRONMENT-DEPENDENT, so CI is the authority. pyproject pins `mypy>=1.13`
        # — a floor, not a version — so a fresh CI install resolves whatever is
        # newest while this Mac sits on 2.3.0. Identical source measured 238 here
        # and 239 there on 3 Sep 2026, which made the ceiling I set from a local
        # run fail its first real CI run. A count that moves with the toolchain is
        # not a property of the code.
        #
        # Enforced in CI; advisory locally, and --tighten will not lower it from a
        # local run. The better fix is pinning mypy exactly, but that is a
        # dependency-policy change (docs/design-platform-policy.md) and not this
        # script's to make.
        "authority": "ci",
    },
    "pytest_skip_sites": {
        # `@pytest.mark.skip` matches inside `skipif`, so count skipif separately
        # and require a non-word char after `skip`. Getting this wrong gave three
        # different totals in one session (25, 22, 3) before it was pinned.
        "measure": lambda: (
            _grep_count(r"@pytest\.mark\.skipif", ROOT / "tests")
            + _grep_count(r"@pytest\.mark\.skip(?![a-z])", ROOT / "tests")
            + _grep_count(r"pytest\.skip\(", ROOT / "tests")
        ),
        "basis": "skipif + bare skip + runtime pytest.skip() across tests/",
        "why": "a skip reads as a pass in every summary line — gaps.md G2",
    },
    "pytest_slow_marked": {
        "measure": lambda: _grep_count(r"@pytest\.mark\.slow", ROOT / "tests"),
        "basis": "@pytest.mark.slow across tests/",
        "why": "excluded from CI by -m 'not slow', so each one is CI coverage given up",
    },
    "e2e_allowlist_entries": {
        "measure": lambda: len(
            re.findall(r"^\| CI-A\d+ \|", (ROOT / "e2e/ALLOWLIST.md").read_text(), re.M)
        ),
        "basis": "table rows in e2e/ALLOWLIST.md (prose mentions of CI-A* do not count)",
        "why": "governed suppressions, but the register set 10 as the tooling threshold",
    },
}


def _provenance() -> dict[str, str]:
    """Where a ceiling's number came from — the first question asked when it fails.

    A ceiling with no provenance is why 238/239 cost a CI run to diagnose: the
    file recorded the number and nothing about the machine that produced it.
    """
    p = {
        "on": _dt.date.today().isoformat(),
        "by": "ci" if os.environ.get("CI") else "local",
    }
    server = os.environ.get("GITHUB_SERVER_URL")
    repo = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if server and repo and run_id:
        p["run"] = f"{server}/{repo}/actions/runs/{run_id}"
    return p


def _tighten_hint(k: str) -> str:
    """The instruction that actually works for this metric, not a generic one."""
    if METRICS[k].get("authority") == "ci":
        return "tighten it in CI: gh workflow run ratchet-tighten.yml"
    return "tighten it: scripts/check-ratchet.py --tighten"


def main() -> int:
    ceilings = json.loads(CEILINGS.read_text()) if CEILINGS.exists() else {}
    measured = {k: v["measure"]() for k, v in METRICS.items()}

    if "--json" in sys.argv:
        print(json.dumps({"measured": measured, "ceilings": ceilings}, indent=2, sort_keys=True))
        return 0

    in_ci = bool(os.environ.get("CI"))

    if "--tighten" in sys.argv:
        out = dict(ceilings)
        moved = []
        for k, now in measured.items():
            if now is None:
                continue
            if METRICS[k].get("authority") == "ci" and not in_ci:
                print(f"skipping {k}: CI is the authority for it; a local number would re-break the gate")
                continue
            was = ceilings.get(k, {}).get("ceiling")
            if was is None or now < was:
                # Start from what is ON DISK, not from METRICS. `note` exists
                # only in the JSON, so rebuilding the entry from the code
                # deleted it — no error, no diff anyone was going to read.
                # Measured 4 Sep 2026: tightening mypy_errors dropped the note
                # recording that its ceiling was set in CI and why, which is the
                # one fact the next person to see it fail will want.
                entry = dict(ceilings.get(k) or {})
                entry.update({j: v for j, v in METRICS[k].items() if j != "measure"})
                entry["ceiling"] = now
                entry["measured"] = _provenance()
                out[k] = entry
                moved.append(f"{k}: {was} -> {now}")
        CEILINGS.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
        print("\n".join(f"tightened {m}" for m in moved) or "nothing to tighten")
        return 0

    rose, slack, blind, loose = [], [], [], []
    for k, now in measured.items():
        ceil = (ceilings.get(k) or {}).get("ceiling")
        if now is None:
            blind.append(k)
        elif ceil is None:
            slack.append(f"  {k}: {now} (no ceiling set)")
        elif now > ceil:
            if METRICS[k].get("authority") == "ci" and not in_ci:
                slack.append(f"  {k}: {now} > ceiling {ceil} — ADVISORY here; CI is the authority")
            else:
                rose.append(f"  {k}: {now} > ceiling {ceil}  — {METRICS[k]['why']}")
        elif now < ceil:
            # Slack is reported the same whether or not CI owns the metric. The
            # advisory line below used to swallow this case for an authority:ci
            # metric and print the measurement alone, so a ceiling 91 above it
            # read exactly like a ceiling at it — which is how mypy_errors went
            # from 238 to 148 on 4 Sep 2026 and left the gate not gating, with
            # every local run looking fine.
            slack.append(f"  {k}: {now} < ceiling {ceil} — {ceil - now} of slack, {_tighten_hint(k)}")
            if in_ci and METRICS[k].get("authority") == "ci":
                loose.append((k, now, ceil))
        elif METRICS[k].get("authority") == "ci" and not in_ci:
            print(f"  {k}: {now} (at ceiling {ceil}; advisory locally — CI is the authority)")
        else:
            print(f"  {k}: {now} (at ceiling)")

    for b in blind:
        # Not measurable is not the same as fine. Say so rather than passing.
        print(f"  {b}: NOT MEASURED — tool missing; this metric is unguarded in this run")
    for s in slack:
        print(s)
    for k, now, ceil in loose:
        # A GitHub annotation, because the log line above is the one nobody
        # reads. This is the only notice this mechanism gets to give: the
        # ceiling cannot lower itself, and a stale one is a gate that passes
        # whatever happens.
        print(
            f"::notice file=docs/testing/ratchet.json::{k} is {now}, ceiling {ceil} — "
            f"{ceil - now} of headroom the ratchet is not holding. "
            f"Tighten from CI: gh workflow run ratchet-tighten.yml"
        )
    if rose:
        print("\nRATCHET EXCEEDED — these may not rise:", file=sys.stderr)
        print("\n".join(rose), file=sys.stderr)
        print("\nRaising a ceiling is a deliberate edit to docs/testing/ratchet.json,\n"
              "in a commit that says why. --tighten will not do it for you.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
