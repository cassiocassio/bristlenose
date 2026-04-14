---
name: sync-board
description: Bidirectional sync between 100days.md and GitHub Projects board — strikethrough Done items, create new cards, backfill Sprint tags
disable-model-invocation: false
user-invocable: true
allowed-tools: Bash, Read, Edit
---

Sync the 100-day launch inventory (`docs/private/100days.md`) with the GitHub Projects board (Bristlenose Roadmap).

Two modes, selected by argument `$0`:

- **`/sync-board`** (no argument) — bidirectional sync: board→doc strikethrough + doc→board new cards + doc→board sprint backfill
- **`/sync-board mark-done "Item 1" "Item 2" ...`** — move specific items to Done on the board and strike through in the doc. Use when you've verified items are complete by reading the code

## Mode: default (bidirectional)

Run the unified sync script:

```bash
cd /Users/cassio/Code/bristlenose
python3 scripts/sync_100days.py
```

Review the dry-run output with the user. If changes look correct, apply:

```bash
python3 scripts/sync_100days.py --apply
```

Report what changed in each direction:
- Board → doc: items struck through or un-struck
- Doc → board: new cards created (with Kind, Priority, Sprint fields)
- Doc → board: Sprint field backfilled on existing cards

## Mode: mark-done (code-verified → board + doc)

The remaining arguments after `mark-done` are item titles (or substrings). Run:

```bash
cd /Users/cassio/Code/bristlenose
python3 scripts/sync_100days.py mark-done "Item title 1" "Item title 2"
```

Review the dry-run output. If correct, apply:

```bash
python3 scripts/sync_100days.py mark-done --apply "Item title 1" "Item title 2"
```

Report what was moved to Done and what was struck through. Items already Done on the board are skipped (but still struck through in the doc if not already).

## Notes

- The board is at: https://github.com/users/cassiocassio/projects/1
- Project ID: `PVT_kwHOAEYXlM4BORbY`
- Status field ID: `PVTSSF_lAHOAEYXlM4BORbYzg9Becg`
- 100days.md is in `docs/private/` (gitignored — contains names and value judgements)
- Sprint tags in 100days.md use the format `[S1]`–`[S6]` before the bold title
- Item matching uses normalized title text (lowercase, no punctuation) for fuzzy matching
- The unified script is `scripts/sync_100days.py` (tests: `tests/test_sync_100days.py`)
- Old single-direction scripts (`sync-100days-status.py`, `sync-100days-new.py`, `sync-100days-mark-done.py`) are deprecated — do not use
