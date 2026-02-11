# Merge Plan: `analysis` → `main`

> **Status:** Merged 11 Feb 2026. This plan is kept for historical reference.

**Written:** 10 Feb 2026
**Branch:** `analysis` (6 commits, fast-forward merged after rebase)
**Tests:** 894 passed (113 analysis-specific), lint clean
**Prerequisite:** Navigation branch merges first

---

## Merge order: navigation first, then analysis

Navigation merges first because:

1. **Larger structural change** — navigation wraps all report content in tab panels and restructures the boot sequence. Analysis adds a separate page without changing existing structure
2. **Navigation has an Analysis tab placeholder** — analysis can populate it (or link from it) after rebase
3. **Easier rebase direction** — analysis rebasing onto navigation means adapting one `initAnalysis` call and one toolbar button. The reverse would require navigation to understand and accommodate the analysis page architecture

---

## Conflict resolution guide

### 1. `bristlenose/stages/render_html.py` — LOW CONFLICT

**What analysis adds:**
- `"organisms/analysis.css"` in `_THEME_FILES` (line 75 on analysis, auto-merges — different position from navigation's `"organisms/global-nav.css"`)
- `analysis: object | None = None` parameter on `render_html()` (line 188)
- `_render_analysis_page()` call inside `render_html()` body (line 496–506)
- `_ANALYSIS_JS_FILES` list + `_load_analysis_js()` + `_get_analysis_js()` (lines 1030–1055)
- `_serialize_matrix()` + `_serialize_analysis()` (lines 1058–1117)
- `_render_analysis_page()` function (lines 1120–1184)

**What navigation changes:**
- Wraps report content in tab panels (lines ~267–580)
- Adds `"organisms/global-nav.css"` to `_THEME_FILES` and `"js/global-nav.js"` etc to `_JS_FILES`
- Adds Analysis tab placeholder (lines 493–497): "Analysis features coming soon"

**Resolution:**
- `_THEME_FILES` and `_JS_FILES` additions: both branches add different entries — git auto-merges
- Analysis's new functions at end of file: no conflict (new code appended)
- The `_render_analysis_page()` call inside `render_html()` body: insert after the tab panel content is written, before `</article>`. The analysis page is a **separate HTML file** — it doesn't go inside a tab panel
- Navigation's Analysis tab placeholder: **leave as-is for now** — future work to link it to `analysis.html` or embed content inline. See decision below

**Note:** Analysis does NOT add `analysis.js` to the main report's `_JS_FILES` — it uses a separate `_ANALYSIS_JS_FILES` for the standalone page. No conflict with the report JS bundle.

### 2. `bristlenose/theme/js/main.js` — SEMANTIC CONFLICT

**Analysis (current):** adds `initAnalysis();` at end of sequential boot calls
**Navigation:** restructures boot to `_bootFns` array with try/catch isolation

**Resolution after rebase:**
```javascript
// In the _bootFns array, add before initGlobalNav:
['initAnalysis', initAnalysis],
```

**However:** `initAnalysis()` on the report page only does one thing — wires the `#analysis-btn` toolbar button click handler to open `analysis.html` in a new window. If the toolbar button is removed (see below), `initAnalysis()` on the report page becomes a no-op (it checks `if (analysisBtn)` and exits). It's harmless but unnecessary. Consider:
- **Option A:** Keep `initAnalysis` in `_bootFns` — safe, no-op if button absent
- **Option B:** Remove it from `_bootFns` — the analysis page has its own `<script>` block that calls `initAnalysis()` directly. The report page doesn't need it if there's no toolbar button

### 3. `bristlenose/theme/templates/toolbar.html` — TEXTUAL CONFLICT

**Analysis:** added codebook button + analysis button (line 3–4)
**Navigation:** removed codebook button (codebook is now a tab)

**Resolution:** Drop both the codebook button and the analysis button. Navigation's tab bar replaces toolbar buttons for page-level navigation. The Analysis tab (currently placeholder) becomes the entry point for analysis features.

### 4. `bristlenose/pipeline.py` — NO CONFLICT

Analysis adds `_compute_analysis()` and three call sites. Navigation doesn't touch this file.

### 5. `bristlenose/output_paths.py` — NO CONFLICT

Analysis adds `analysis_file` property. Navigation doesn't touch this file.

### 6. `docs/BRANCHES.md` — TEXTUAL CONFLICT (trivial)

Both branches update this file. Take navigation's version, then re-add analysis section.

### 7. Other analysis-only files — NO CONFLICT

All new files, no overlap:
- `bristlenose/analysis/` (entire package)
- `bristlenose/theme/js/analysis.js`
- `bristlenose/theme/organisms/analysis.css`
- `bristlenose/theme/templates/analysis.html`
- `tests/test_analysis_*.py` (4 files)
- `docs/mockups/mockup-analysis.html`
- `docs/design-analysis-future.md`

---

## Decision: Analysis tab → analysis.html linking

After both branches merge, the report will have:
- An **Analysis tab** in the global nav (from navigation) — currently placeholder
- A standalone **analysis.html** page (from analysis) — fully functional

**Options:**

1. **Tab links to analysis page** — Analysis tab shows a brief summary + "Open full analysis →" button that opens `analysis.html`. Quick to implement, keeps analysis in its own window
2. **Tab embeds analysis content** — Analysis tab renders signal cards and heatmaps inline. Bigger change — needs to reconcile two rendering approaches (Python-injected JSON + IIFE on standalone page vs inline within report's JS bundle)
3. **Tab stays placeholder** — Ship as-is, improve later

**Recommended: Option 1** — minimal work, delivers value. The analysis page's JS (`initAnalysis()`) is designed for a standalone page with its own global `BRISTLENOSE_ANALYSIS`. Embedding inline would need significant refactoring.

Implementation for Option 1 (post-merge on main):
- Replace the "coming soon" placeholder in navigation's Analysis tab with:
  - "Open analysis page" link/button → `window.open('analysis.html', ...)`
  - Or: brief text explaining what the analysis page shows
- If `analysis.html` doesn't exist (no sentiment data), show "No analysis available — run with sentiment-enabled quotes to see signal concentration analysis"

---

## Rebase steps

```bash
# 1. Ensure navigation is merged to main first
cd /Users/cassio/Code/bristlenose

# 2. Rebase analysis onto updated main
cd "/Users/cassio/Code/bristlenose_branch analysis"
git fetch origin
git rebase main
```

Expected conflicts:
- `render_html.py` — resolve `_THEME_FILES`/`_JS_FILES` list additions (keep both), keep analysis functions
- `main.js` — add `['initAnalysis', initAnalysis]` to `_bootFns` array (or omit if toolbar button removed)
- `toolbar.html` — drop analysis button (tab replaces it)
- `docs/BRANCHES.md` — take main's version, re-add analysis entry

```bash
# 3. Run tests + lint post-rebase
.venv/bin/python -m pytest tests/
.venv/bin/ruff check .

# 4. Merge from main worktree
cd /Users/cassio/Code/bristlenose
git merge analysis

# 5. Post-merge: wire Analysis tab to analysis.html
# (small change on main, not part of the rebase)
```

---

## Post-merge updates

- `docs/BRANCHES.md` — move analysis to "Completed Branches"
- `CLAUDE.md` — note analysis page architecture in main docs (currently on branch-only CLAUDE.md)
- Wire Analysis tab placeholder → link to `analysis.html`
- Consider: should `initAnalysis` stay in `_bootFns`? (harmless no-op vs unnecessary call)

---

## Risk assessment

**Low risk.** The conflicts are well-understood:

- Analysis's core work (Python math, models, signals, tests) is entirely in new files — zero conflict
- `render_html.py` changes are additive (new functions appended, new parameter added)
- The only semantic conflict is `main.js` boot sequence — one line to adapt
- The toolbar button removal is a UX improvement (tab replaces button)
- 97 tests verify analysis pipeline end-to-end, including HTML rendering
