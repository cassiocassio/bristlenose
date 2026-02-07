# Active Feature Branches

This document tracks active feature branches to help multiple Claude sessions coordinate without conflicts.

**Updated:** 7 Feb 2026

---

## How to Use This File

When starting a new Claude session on a feature branch:
1. Check this file to see what other branches are active
2. Note which files they're touching
3. Avoid editing those files unless necessary
4. Update this file when you create/complete a branch

When merging back to main:
1. Read the merge plan for your branch
2. Check for conflicts with other branches
3. Update this file to mark your branch as merged

---

## Active Branches

### `export-sharing`

**Status:** Design complete, implementation not started
**Started:** 5 Feb 2026
**Design doc:** `docs/design-export-sharing.md`
**Merge plan:** `docs/merge-plan-export-sharing.md`

**Files this branch will touch:**
- `bristlenose/theme/js/` — new `export.js` module
- `bristlenose/theme/molecules/` — new `export-dialog.css`
- `bristlenose/theme/organisms/` — new `made-with.css` (branding footer)
- `bristlenose/stages/render_html.py` — export button, footer CTA, state embedding
- `bristlenose/cli.py` — `bristlenose package` command (Phase 4 only)
- `bristlenose/config.py` — `--include-media`, `--portable` flags
- `docs/design-export-sharing.md` — design doc (already created)

**Safe for other branches to edit:**
- `bristlenose/llm/` — no overlap
- `bristlenose/stages/` (except `render_html.py`) — no overlap
- `bristlenose/theme/js/` existing modules — minimal overlap (may add hook in `main.js`)

---

### `keyboard-navigation`

**Status:** In progress (help overlay work stashed)
**Started:** Earlier session
**Design doc:** `docs/design-keyboard-navigation.md`
**Stash:** `keyboard-navigation - help overlay in progress`

**Files this branch touches:**
- `bristlenose/theme/js/focus.js` — focus system
- `bristlenose/theme/js/main.js` — boot sequence
- `bristlenose/theme/molecules/help-overlay.css` — new file
- `bristlenose/stages/render_html.py` — keyboard shortcut hints in UI
- `docs/design-keyboard-navigation.md` — design doc

**Potential conflicts with `export-sharing`:**
- `render_html.py` — both branches modify this file
- `main.js` — both branches add new init calls

**Resolution strategy:** Keyboard navigation merges first (more complete). Export-sharing rebases on main after keyboard merge.

---

### `codebook`

**Status:** Phase 2 UX prototyping (standalone mockup complete, iterating)
**Started:** 7 Feb 2026
**Worktree:** `/Users/cassio/Code/bristlenose_branch codebook/`
**Plan:** `~/.claude/plans/immutable-chasing-patterson.md`
**Phase 1 commit:** `1c66628` (colour tokens, AI tag toggle, badge styling — on main)

**What this branch does:**
Codebook panel for organising user tags into colour-coded groups. Researchers drag tags between groups, merge duplicates, and assign semantic colours. Six phases: Visual Foundation (done) → Data Model + Panel → Tag Operations → Filter & Histogram Integration → File Persistence → Import/Export + Polish.

**Files this branch will touch:**
- `bristlenose/theme/js/codebook.js` — existing Phase 1 data model, expanding with panel UI
- `bristlenose/theme/js/tags.js` — tag CRUD hooks for codebook integration
- `bristlenose/theme/js/histogram.js` — codebook colour awareness
- `bristlenose/theme/js/main.js` — boot sequence (new `initCodebook()` call)
- `bristlenose/theme/molecules/` — new `codebook-panel.css`
- `bristlenose/theme/organisms/` — possible new `codebook-layout.css`
- `bristlenose/stages/render_html.py` — codebook panel HTML, JS file list
- `mockup-codebook-panel.html` — standalone UX prototype (temporary)

**Safe for other branches to edit:**
- `bristlenose/llm/` — no overlap
- `bristlenose/stages/` (except `render_html.py`) — no overlap
- `bristlenose/theme/js/` modules other than `codebook.js`, `tags.js`, `histogram.js` — minimal overlap

**Potential conflicts:**
- `render_html.py` — shared with export-sharing and keyboard-navigation
- `main.js` — shared with all UI feature branches
- `tags.js` — shared if tag-related fixes land on main

---

## Completed Branches (for reference)

_None yet — add branches here after they're merged to main._

---

## Coordination Notes for Claude Sessions

### Reading this file

Before making changes, run:
```bash
git fetch origin
cat docs/BRANCHES.md
```

### Conflict-prone files

These files are frequently edited by multiple features. Take extra care:

| File | Why it's hot |
|------|-------------|
| `bristlenose/stages/render_html.py` | All UI features touch this |
| `bristlenose/theme/js/main.js` | Boot sequence for all JS modules |
| `bristlenose/cli.py` | All new commands land here |
| `TODO.md` | Everyone updates it |
| `CLAUDE.md` | Everyone updates it |

### Safe editing patterns

1. **New files are safe** — if your feature adds a new module (`export.js`, `help-overlay.css`), no conflict risk
2. **Append-only changes are safe** — adding a new function to an existing file rarely conflicts
3. **Structural changes are risky** — refactoring existing code will conflict with parallel work

### When you encounter a conflict

1. Don't resolve it yourself — note it in the merge plan
2. Ask the user which version to keep
3. Or wait for the other branch to merge first, then rebase

### Communication pattern

If you need to signal something to a future Claude session:
1. Add a note to this file under your branch
2. Or create a `docs/notes-{branch-name}.md` for longer notes
3. Reference it in `CLAUDE.md` under "Reference docs"
