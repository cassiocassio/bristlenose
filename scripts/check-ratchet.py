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

Usage:
  scripts/check-ratchet.py             measure and compare; exit 1 if any rose
  scripts/check-ratchet.py --tighten   lower ceilings to current values
  scripts/check-ratchet.py --json      machine-readable, no verdict
"""
from __future__ import annotations

import json
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


METRICS: dict[str, dict] = {
    "mypy_errors": {
        "measure": measure_mypy,
        "basis": "mypy bristlenose/ --ignore-missing-imports, 'Found N errors'",
        "why": "gaps.md G3 — soft since it was added, which is how it reached 238",
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


def main() -> int:
    ceilings = json.loads(CEILINGS.read_text()) if CEILINGS.exists() else {}
    measured = {k: v["measure"]() for k, v in METRICS.items()}

    if "--json" in sys.argv:
        print(json.dumps({"measured": measured, "ceilings": ceilings}, indent=2, sort_keys=True))
        return 0

    if "--tighten" in sys.argv:
        out = dict(ceilings)
        moved = []
        for k, now in measured.items():
            if now is None:
                continue
            was = ceilings.get(k, {}).get("ceiling")
            if was is None or now < was:
                out[k] = {**METRICS[k], "ceiling": now, "basis": METRICS[k]["basis"],
                          "why": METRICS[k]["why"]}
                out[k].pop("measure", None)
                moved.append(f"{k}: {was} -> {now}")
        CEILINGS.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
        print("\n".join(f"tightened {m}" for m in moved) or "nothing to tighten")
        return 0

    rose, slack, blind = [], [], []
    for k, now in measured.items():
        ceil = (ceilings.get(k) or {}).get("ceiling")
        if now is None:
            blind.append(k)
        elif ceil is None:
            slack.append(f"  {k}: {now} (no ceiling set)")
        elif now > ceil:
            rose.append(f"  {k}: {now} > ceiling {ceil}  — {METRICS[k]['why']}")
        elif now < ceil:
            slack.append(f"  {k}: {now} < ceiling {ceil} — tighten it: scripts/check-ratchet.py --tighten")
        else:
            print(f"  {k}: {now} (at ceiling)")

    for b in blind:
        # Not measurable is not the same as fine. Say so rather than passing.
        print(f"  {b}: NOT MEASURED — tool missing; this metric is unguarded in this run")
    for s in slack:
        print(s)
    if rose:
        print("\nRATCHET EXCEEDED — these may not rise:", file=sys.stderr)
        print("\n".join(rose), file=sys.stderr)
        print("\nRaising a ceiling is a deliberate edit to docs/testing/ratchet.json,\n"
              "in a commit that says why. --tighten will not do it for you.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
