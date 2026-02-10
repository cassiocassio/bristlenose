# Merge Plan: `navigation` → `main`

**Written:** 10 Feb 2026
**Branch:** `navigation` (3 commits ahead of main)
**Tests:** 757 passed, lint clean

---

## Pre-merge: finish Project tab (minimum)

The only blocker is the **Project tab** — it's the first thing users see when they open the report, and it currently says "Project summary coming soon." Give it something minimum viable (project name, session count, date range, participant list — whatever metadata is already available from the pipeline).

Analysis and Settings tabs can ship as placeholders — they're behind other tabs and users won't land on them by default. Improve them later on main.

- **Project tab** (line ~278 in `render_html.py`) — **must populate before merge**
- **Analysis tab** (line ~494) — placeholder is fine for now
- **Settings tab** (line ~500) — placeholder is fine for now

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

- **`analysis`** — touches `render_html.py`, `main.js`, `toolbar.html`. See `docs/merge-plan-analysis.md` for full resolution guide. Conflict is manageable:
  - `render_html.py`: analysis adds `"organisms/analysis.css"` to `_THEME_FILES` (new line, auto-merge), adds `analysis` parameter to `render_html()`, adds `_render_analysis_page()` and `_ANALYSIS_JS_FILES` (new functions at end of file). No structural conflict — analysis renders a **separate** `analysis.html` page, not inline content. The navigation Analysis tab placeholder stays as-is for now
  - `main.js`: navigation restructured boot to `_bootFns` array; analysis added `initAnalysis()` to the old sequential style. Resolution: add `['initAnalysis', initAnalysis]` to `_bootFns` array. But note: `initAnalysis()` runs on the analysis page (separate HTML file with its own `<script>` block), not the report page. On the report page it only wires the toolbar button — which navigation removes (codebook button pattern). Decision needed: keep analysis toolbar button, or make the Analysis tab link to `analysis.html`
  - `toolbar.html`: navigation removed codebook button; analysis added analysis button on the same line. Resolution: drop both (codebook is now a tab, analysis will be linked from the tab)
- `keyboard-navigation` — touches `focus.js` and `main.js`
- `export-sharing` — touches `render_html.py` and `main.js`
