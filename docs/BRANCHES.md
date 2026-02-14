# Active Feature Branches

This document tracks active feature branches to help multiple Claude sessions coordinate without conflicts.

**Updated:** 13 Feb 2026

---

## Worktree Convention

Each active feature branch gets its own **git worktree** — a full working copy in a separate directory. This lets multiple Claude sessions work on different features simultaneously without interfering.

**Directory pattern:** `/Users/cassio/Code/bristlenose_branch <name>`

| Directory | Branch | Purpose |
|-----------|--------|---------|
| `bristlenose/` | `main` | Main repo, releases, hotfixes |
| `bristlenose_branch symbology/` | `symbology` | § ¶ ❋ Unicode prefix symbols for sections, quotes, themes |
| `bristlenose_branch serve/` | `serve` | FastAPI + React + SQLite served version |

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

**Important:** Always `cd` to the main repo *before* removing a worktree. If a Claude session or terminal has its CWD inside the worktree directory, removing it will break that shell — every subsequent command fails with "path does not exist" and the session is unrecoverable.

```bash
# 1. Switch to main repo FIRST (never remove a worktree from inside it)
cd /Users/cassio/Code/bristlenose

# 2. Remove the worktree and branch
git worktree remove "/Users/cassio/Code/bristlenose_branch my-feature"
git branch -d my-feature

# 3. If the directory was already deleted (rm -rf or Finder):
git worktree prune          # cleans stale worktree refs
git branch -d my-feature    # delete the branch

# 4. If also on remote:
git push origin --delete my-feature
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

## Backup Strategy

Feature branches are pushed to GitHub for backup without triggering releases (only `main` triggers releases). Use `git push origin <branch-name>` to back up.

| Branch | Local worktree | GitHub remote |
|--------|---------------|---------------|
| `main` | `bristlenose/` | `origin/main` (push via `origin/main:wip` until release time) |
| `symbology` | `bristlenose_branch symbology/` | `origin/symbology` |
| `serve` | `bristlenose_branch serve/` | (local only) |

---

## Active Branches

### `symbology` — started 12 Feb 2026

**Worktree:** `/Users/cassio/Code/bristlenose_branch symbology`

**Goal:** Add consistent Unicode prefix symbols (§ Section, ¶ Quote, ❋ Theme) across all user-facing surfaces — navigation, headings, dashboards, analysis, tooltips, and text output.

**Files likely to touch:**
- `bristlenose/stages/render_html.py` — dashboard stats, pane headings, template params
- `bristlenose/stages/render_output.py` — markdown heading call sites
- `bristlenose/theme/templates/toc.html` — TOC headings
- `bristlenose/theme/templates/global_nav.html` — tab labels
- `bristlenose/theme/templates/analysis.html` — analysis page headings
- `bristlenose/theme/js/analysis.js` — signal cards, heatmap headers
- `bristlenose/theme/js/transcript-annotations.js` — margin label tooltips
- `bristlenose/theme/js/codebook.js` — quote count tooltips

### `serve` — started 13 Feb 2026

**Worktree:** `/Users/cassio/Code/bristlenose_branch serve`

**Goal:** Add `bristlenose serve` command — FastAPI server + React frontend + SQLite database. Islands migration pattern: serve the existing HTML report over HTTP, then replace vanilla JS components with React islands one at a time.

**Current status:** Milestones 0 and 1 complete. The sessions table is now a React island backed by a real API reading from SQLite. 72 new tests, full suite (1050) passing.

**Files added/modified:**
- `bristlenose/server/models.py` — full 22-table domain schema (was single Project table)
- `bristlenose/server/importer.py` — pipeline output → SQLite importer
- `bristlenose/server/routes/sessions.py` — sessions API endpoint
- `bristlenose/server/app.py` — sessions router, DB dependency injection, auto-import on startup
- `bristlenose/server/db.py` — StaticPool for in-memory testing, all-models init
- `bristlenose/stages/render_html.py` — `serve_mode` flag for React mount point
- `frontend/src/islands/SessionsTable.tsx` — React sessions table component
- `frontend/src/main.tsx` — mount SessionsTable into `#bn-sessions-table-root`
- `docs/design-serve-milestone-1.md` — full design doc with domain model, decisions, status
- `docs/CHANGELOG-serve.md` — development log with design rationale
- `tests/test_serve_models.py` — 38 schema tests
- `tests/test_serve_importer.py` — 17 import tests
- `tests/test_serve_sessions_api.py` — 17 API tests

**Design docs:** `docs/design-serve-migration.md`, `docs/design-serve-milestone-1.md`

---

## Completed Branches (for reference)

### `project-dashboard` — merged 13 Feb 2026

At-a-glance project dashboard redesign. Clickable stats, featured quotes, session rows, cross-tab navigation. Compact layout with paired stats, slim session table, linked sections/themes. Non-scrolling single-viewport design for the Project tab.

### `analysis` — merged 11 Feb 2026

Analysis page with signal cards ranked by composite score (concentration × agreement × intensity), section × sentiment and theme × sentiment heatmaps with adjusted standardised residuals, dark mode support. Full pipeline integration: Python math module (`bristlenose/analysis/`), standalone `analysis.html` with injected JSON, client-side JS rendering. 97 tests across 4 files. Future phases in `docs/design-analysis-future.md`.


### `codebook-tag-filter` — merged 11 Feb 2026

Tag filter dropdown uses codebook colours and hierarchy. Tags grouped into tinted sections matching codebook page. Badge-styled labels via `createReadOnlyBadge()` in `badge-utils.js`. Search matches both tag names and group names.

### `navigation` — merged 11 Feb 2026

Global tab bar navigation for the HTML report. 7 tabs (Project, Sessions, Quotes, Codebook, Analysis, Settings, About). Sessions tab with grid → inline transcript drill-down. Project tab dashboard with stats, featured quotes, sections/themes tables, sentiment chart. Speaker cross-navigation from quote cards to session timecodes. Full ARIA/accessibility. `global-nav.js`, `global-nav.css`, `global_nav.html`, `session_table.html` added; `render_html.py` extended with ~800 lines; `main.js` boot refactored to `_bootFns` array.

### `jinja2-migration` — merged 9 Feb 2026

Phase 1 Jinja2 template extraction: footer, document shell, report header, quote card. Adds `jinja2>=3.1` dependency, comparison script (`scripts/compare-render.sh`), 12 parity tests. `render_html.py` reduced by ~170 lines. Output byte-identical. Phase 2+ (toolbar, sentiment chart, coverage, player) tracked in `docs/jinja2-migration-plan.md`.

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
