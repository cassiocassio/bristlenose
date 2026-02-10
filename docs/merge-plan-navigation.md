# Merge Plan: `navigation` → `main`

**Written:** 10 Feb 2026
**Branch:** `navigation` (3 commits ahead of main)
**Tests:** 757 passed, lint clean

---

## Pre-merge: finish placeholder tabs

Before merging, populate or remove the placeholder content in these tabs:

- **Project tab** (line ~278 in `render_html.py`) — currently "Project summary coming soon"
- **Analysis tab** (line ~494) — currently "Analysis features coming soon"
- **Settings tab** (line ~500) — currently "Report settings coming soon"

Decide for each: populate with real content, or ship as-is with placeholder text.

---

## Merge steps

1. **Rebase onto main:**
   ```bash
   cd "/Users/cassio/Code/bristlenose_branch navigation"
   git fetch origin
   git rebase main
   ```
   Expected conflict: `docs/BRANCHES.md` only (analysis branch entry removed on navigation, updated on main). Trivial to resolve.

2. **Run tests + lint post-rebase:**
   ```bash
   .venv/bin/python -m pytest tests/
   .venv/bin/ruff check .
   ```

3. **Merge from main worktree:**
   ```bash
   cd /Users/cassio/Code/bristlenose
   git merge navigation
   ```
   Fast-forward if rebased. Use `--no-ff` if you want a merge commit in the history.

4. **Post-merge updates:**
   - `docs/BRANCHES.md` — move navigation to "Completed Branches" section
   - `docs/BRANCHES.md` — remove navigation from worktree table and backup table
   - `CLAUDE.md` — remove navigation from worktree table, note tab architecture in HTML report features section

5. **Clean up branch:**
   ```bash
   cd /Users/cassio/Code/bristlenose
   # Use /close-branch skill, or manually:
   git worktree remove "/Users/cassio/Code/bristlenose_branch navigation"
   git branch -d navigation
   git push origin --delete navigation
   ```

6. **Push** when ready (after 9pm on weekdays).

---

## Risk assessment

**Low risk.** The branch is self-contained:

- **New files** (no conflict possible): `global-nav.js`, `global-nav.css`, `global_nav.html`, `test_navigation.py`
- **Modified files:** `render_html.py` is the big one (309 lines added) but changes are additive — existing content is wrapped in tab panels, not restructured
- **Only shared-file conflict:** `docs/BRANCHES.md` (documentation, trivial)
- **No model/pipeline/CLI changes** — purely a rendering-layer feature

---

## What merges after this

Other branches that touch `render_html.py` or `main.js` should rebase onto main after this merge lands, since navigation wraps all report content in tab panels. Specifically:

- `keyboard-navigation` — touches `focus.js` and `main.js`
- `export-sharing` — touches `render_html.py` and `main.js`
