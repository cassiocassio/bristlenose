---
name: sync-board
description: Sync 100days.md strikethrough with GitHub Projects board — strike through Done items, create cards for new entries, or mark specific items as Done
disable-model-invocation: false
user-invocable: true
allowed-tools: Bash, Read, Edit
---

Sync the 100-day launch inventory (`docs/private/100days.md`) with the GitHub Projects board (Bristlenose Roadmap).

Three modes, selected by argument `$0`:

- **`/sync-board done`** (or no argument) — board → doc: strike through Done items in the markdown
- **`/sync-board new`** — doc → board: create cards for items in the doc that don't exist on the board
- **`/sync-board mark-done "Item 1" "Item 2" ...`** — move specific items to Done on the board and strike through in the doc. Use when you've verified items are complete by reading the code

If no argument is given, default to `done`.

## Mode: done (board → doc)

Run the sync script:

```bash
cd /Users/cassio/Code/bristlenose
python3 scripts/sync-100days-status.py
```

Review the dry-run output with the user. If changes look correct, apply:

```bash
python3 scripts/sync-100days-status.py --apply
```

Report what was struck through (and what was un-struck, if any items moved back from Done).

## Mode: new (doc → board)

Run the reverse sync script:

```bash
cd /Users/cassio/Code/bristlenose
python3 scripts/sync-100days-new.py
```

Review the dry-run output with the user. If the new cards look correct, apply:

```bash
python3 scripts/sync-100days-new.py --apply
```

Report how many cards were created and in which Kind categories.

## Mode: mark-done (code-verified → board + doc)

The remaining arguments after `mark-done` are item titles (or substrings). Run the mark-done script:

```bash
cd /Users/cassio/Code/bristlenose
python3 scripts/sync-100days-mark-done.py "Item title 1" "Item title 2"
```

Review the dry-run output with the user — it shows which cards will move to Done and which lines will get strikethrough. If correct, apply:

```bash
python3 scripts/sync-100days-mark-done.py --apply "Item title 1" "Item title 2"
```

Report what was moved to Done and what was struck through. Items already Done on the board are skipped (but still struck through in the doc if not already).

## Notes

- The board is at: https://github.com/users/cassiocassio/projects/1
- Project ID: `PVT_kwHOAEYXlM4BORbY`
- Status field ID: `PVTSSF_lAHOAEYXlM4BORbYzg9Becg`
- 100days.md is in `docs/private/` (gitignored — contains names and value judgements)
- Item matching uses normalized title text (lowercase, no punctuation) for fuzzy matching
- The scripts are in `scripts/sync-100days-status.py`, `scripts/sync-100days-new.py`, and `scripts/sync-100days-mark-done.py`
