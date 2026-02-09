# Active Feature Branches

This document tracks active feature branches to help multiple Claude sessions coordinate without conflicts.

**Updated:** 7 Feb 2026

---

## Worktree Convention

Each active feature branch gets its own **git worktree** — a full working copy in a separate directory. This lets multiple Claude sessions work on different features simultaneously without interfering.

**Directory pattern:** `/Users/cassio/Code/bristlenose_branch <name>`

| Directory | Branch | Purpose |
|-----------|--------|---------|
| `bristlenose/` | `main` | Main repo, releases, hotfixes |
| `bristlenose_branch CI/` | `CI` | CI improvements |

**Creating a new feature branch worktree:**

```bash
# From the main repo:
cd /Users/cassio/Code/bristlenose

# Create the branch (if it doesn't exist) and the worktree in one go:
git branch my-feature main
git worktree add "/Users/cassio/Code/bristlenose_branch my-feature" my-feature

# Or if the branch already exists:
git worktree add "/Users/cassio/Code/bristlenose_branch my-feature" my-feature
```

**Each worktree needs its own venv** to run tests:

```bash
cd "/Users/cassio/Code/bristlenose_branch my-feature"
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

**Listing worktrees:** `git worktree list` (from any worktree)

**Removing a worktree** (after merging to main):

```bash
git worktree remove "/Users/cassio/Code/bristlenose_branch my-feature"
git branch -d my-feature
```

**Rules:**
- `bristlenose/` always stays on `main` — never check out a feature branch there
- Each Claude session should confirm which worktree it's operating in at session start
- Commits made in any worktree are immediately visible to all others (shared `.git`)
- Don't run `git checkout` to switch branches inside a worktree — that defeats the point

---

## How to Use This File

When starting a new Claude session on a feature branch:
1. Check this file to see what other branches are active
2. Confirm you're in the right worktree directory
3. Note which files other branches are touching
4. Avoid editing those files unless necessary
5. Update this file when you create/complete a branch

When merging back to main:
1. Read the merge plan for your branch
2. Check for conflicts with other branches
3. Update this file to mark your branch as merged
4. Remove the worktree

---

## Active Branches

### `CI`

**Status:** Not started
**Started:** 7 Feb 2026
**Worktree:** `/Users/cassio/Code/bristlenose_branch CI/`

**Files this branch will touch:**
- `.github/workflows/` — CI workflow files
- Potentially `pyproject.toml`, `Makefile`, or similar build config

---

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

## Completed Branches (for reference)

### `transcript-annotations` — merged 9 Feb 2026

Transcript page annotations: quote highlighting with margin labels, tag badges, span bars for quote extent, citation toggle. Also: badge abstraction (`badge-utils.js`), delete circle restyle (white floating chip), design-system reference docs (`docs/design-system/`).

### `codebook` — merged 7 Feb 2026

Interactive codebook page with tag taxonomy management. Phases 1–3: OKLCH colour tokens, toolbar redesign, standalone `codebook.html` with drag-and-drop, inline editing, group CRUD, cross-window sync. Also: shared `escapeHtml()`, `showConfirmModal()`, `toggle()` in modal infrastructure.

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
