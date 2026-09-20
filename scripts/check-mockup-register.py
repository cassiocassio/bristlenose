#!/usr/bin/env python3
"""Every mockup carries a lifecycle entry, and every entry names a real file.

`docs/mockups/` holds ~165 standalone HTML mockups. Without a marker there is no
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
import subprocess
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


def _tracked_mockups() -> set[str]:
    """Mockup filenames git knows about.

    Falls back to the filesystem outside a checkout (a release tarball, say),
    where `git` is not available and every file present is by definition part
    of what shipped.
    """
    try:
        out = subprocess.run(
            ["git", "ls-files", "--", "docs/mockups/*.html"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return {p.name for p in MOCKUPS.glob("*.html")}
    return {Path(line).name for line in out.splitlines() if line.strip()}


def _ignored_mockups(names: set[str]) -> set[str]:
    """Which of these names `.gitignore` deliberately excludes.

    `git check-ignore --no-index` answers for a path that does not exist, which
    is the whole point: in CI an ignored mockup is never checked out, so
    "is it on disk" cannot distinguish *deliberately absent* from *deleted*.
    """
    if not names:
        return set()
    rel = [f"docs/mockups/{n}" for n in sorted(names)]
    try:
        out = subprocess.run(
            ["git", "check-ignore", "--no-index", *rel],
            cwd=ROOT, capture_output=True, text=True,
        ).stdout
    except OSError:
        return set()
    return {Path(line).name for line in out.splitlines() if line.strip()}


def main() -> int:
    if not REGISTER.exists():
        print(f"error: register not found at {REGISTER.relative_to(ROOT)}")
        return 1

    # What the REPOSITORY holds, not what this working copy happens to have.
    #
    # A mockup carrying verbatim participant speech is gitignored rather than
    # committed — the repo is public, and `experiments/signal_valence/README.md`
    # says of its harvest "do not copy it anywhere shareable". Those mockups
    # still have a lifecycle worth recording, and STATUS.md is where it goes,
    # so a row naming one is correct and must not read as an orphan.
    #
    # Globbing the filesystem made the answer depend on who was asking: seven
    # such rows validated on the machine that built them and failed in CI,
    # where the files are simply not checked out. Asking git makes it the same
    # question everywhere.
    tracked = _tracked_mockups()
    present = {q.name for q in MOCKUPS.glob("*.html")}

    # Corpus = tracked, PLUS any gitignored mockup that is actually here.
    #
    # The first version of this fix used `tracked` alone. That closed the orphan
    # direction and opened a blind spot in the other one: an ignored file was
    # never *required* to have a row, so the gate printed "all 155 registered"
    # with 166 on disk and four unrowed — one of them the artefact
    # design-signal-card.md calls the review artefact. A gate that cannot see a
    # whole class of file is worse than no gate, because it reports success.
    #
    # A gitignored mockup is deliberate, not accidental: the quote-bearing ones
    # cannot go in a public repo but still have a lifecycle, which is exactly why
    # STATUS.md carries rows for them. An untracked-and-NOT-ignored file is work
    # in flight — someone's WIP this minute — and failing on it would make the
    # gate everyone's problem the moment anyone drafts a mockup.
    #
    # Known limit, and it is unavoidable: CI never checks out an ignored file, so
    # `present - tracked` is empty there and CI cannot catch a missing row for
    # one. That direction is only checkable on a machine that holds them.
    on_disk = tracked | _ignored_mockups(present - tracked)

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
    # A row for a deliberately-ignored mockup is not an orphan. Asked as "is
    # this name ignored BY RULE", not "is it here" — the first pass at this
    # compared against the local filesystem, which is exactly the machine
    # dependence the change was removing: in CI those files are never checked
    # out, so the set was empty and all seven rows failed again.
    ignored = _ignored_mockups(registered.keys() - on_disk)
    orphans = sorted(registered.keys() - on_disk - ignored)
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
