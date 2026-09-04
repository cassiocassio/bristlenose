#!/usr/bin/env python3
"""Every mockup carries a lifecycle entry, and every entry names a real file.

`docs/mockups/` holds 150 standalone HTML mockups. Without a marker there is no
way to tell a design of record from one describing a flow that was replaced,
except by reading the code — which defeats having them, and is how a rejected
idea gets proposed again a year later by whoever found the picture. The register
(`docs/mockups/STATUS.md`) carries a dated lifecycle per file; the states and
their meaning are in `docs/mockups/README.md`.

The whole corpus was classified on 3–4 Sep 2026. This gate exists so that stays
true: a mockup added tomorrow is otherwise the start of the next backlog, and
nothing else in the repo would notice.

Checks:
1. Every ``docs/mockups/*.html`` has a row in the register.
2. Every register row names a file that exists (catches renames and deletions,
   which leave a row pointing at nothing).
3. Every row's lifecycle cell names at least one known state. A row that exists
   but says nothing is not an entry, it is a placeholder — and it would satisfy
   check 1 while telling a reader nothing.

Deliberately NOT checked: whether a state is *correct*. That is a judgement
against the code and no script can make it. This gate enforces that somebody
was asked the question, not that they answered it well.

Hard by default, per the repo's gate policy (`docs/testing/soft-gates.json`):
the check is deterministic, sub-second, and the fix is one line in a Markdown
table, so there is nothing to ratchet or defer.

Exit 0: every mockup is registered.
Exit 1: a mockup is missing, a row is an orphan, or a row names no state.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOCKUPS = ROOT / "docs" / "mockups"
REGISTER = MOCKUPS / "STATUS.md"

# Mirrors the table in docs/mockups/README.md § Lifecycle. `unreviewed` is
# accepted so the register can carry an honest "nobody has checked this" rather
# than forcing a guess — it is the absence of a claim, not a claim of currency.
STATES = ("PROPOSED", "IMPLEMENTED", "SUPERSEDED", "ABANDONED", "PARKED", "SANDPIT")

# A register row: | `name.html` | date | lifecycle |
ROW = re.compile(r"^\|\s*`([^`]+\.html)`\s*\|([^|]*)\|(.*)\|\s*$")


def main() -> int:
    if not REGISTER.exists():
        print(f"error: register not found at {REGISTER.relative_to(ROOT)}")
        return 1

    on_disk = {p.name for p in MOCKUPS.glob("*.html")}

    registered: dict[str, str] = {}
    duplicates: list[str] = []
    for line in REGISTER.read_text().splitlines():
        m = ROW.match(line)
        if not m:
            continue
        name, _date, lifecycle = m.group(1), m.group(2), m.group(3)
        if name in registered:
            duplicates.append(name)
        registered[name] = lifecycle

    missing = sorted(on_disk - registered.keys())
    orphans = sorted(registered.keys() - on_disk)
    silent = sorted(
        n for n, tl in registered.items()
        if "unreviewed" not in tl and not any(s in tl for s in STATES)
    )

    if not (missing or orphans or silent or duplicates):
        print(f"✓ all {len(on_disk)} mockups registered")
        return 0

    if missing:
        print(f"\n{len(missing)} mockup(s) missing from the register:")
        for n in missing:
            print(f"  {n}")
        print(
            "\n  Add a row to docs/mockups/STATUS.md with a dated lifecycle, e.g.\n"
            "    | `your-mockup.html` | 4 Sep 2026 | PROPOSED 4 Sep 2026 — what it is |\n"
            "  States and their meaning: docs/mockups/README.md § Lifecycle.\n"
            "  `*unreviewed*` is a valid entry — say nothing rather than guess."
        )
    if orphans:
        print(f"\n{len(orphans)} register row(s) name a file that does not exist:")
        for n in orphans:
            print(f"  {n}")
        print("\n  Renamed or deleted? Update or remove the row.")
    if silent:
        print(f"\n{len(silent)} row(s) name no lifecycle state:")
        for n in silent:
            print(f"  {n}  →  {registered[n].strip()[:60]!r}")
        print(f"\n  Use one of: {', '.join(STATES)} — or *unreviewed*.")
    if duplicates:
        print(f"\n{len(duplicates)} mockup(s) appear twice in the register:")
        for n in sorted(set(duplicates)):
            print(f"  {n}")

    return 1


if __name__ == "__main__":
    sys.exit(main())
