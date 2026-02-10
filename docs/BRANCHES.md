# Active Feature Branches

This document tracks active feature branches to help multiple Claude sessions coordinate without conflicts.

**Updated:** 11 Feb 2026

---

## Worktree Convention

Each active feature branch gets its own **git worktree** — a full working copy in a separate directory. This lets multiple Claude sessions work on different features simultaneously without interfering.

**Directory pattern:** `/Users/cassio/Code/bristlenose_branch <name>`

| Directory | Branch | Purpose |
|-----------|--------|---------|
| `bristlenose/` | `main` | Main repo, releases, hotfixes |
| `bristlenose_branch analysis/` | `analysis` | Analysis feature |

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
| `analysis` | `bristlenose_branch analysis/` | `origin/analysis` |

---

## Active Branches

### `analysis`

**Status:** Phases 1–3 complete with comprehensive test coverage (97 tests across 4 files)
**Started:** 10 Feb 2026
**Worktree:** `/Users/cassio/Code/bristlenose_branch analysis/`
**Remote:** `origin/analysis`
**Design doc:** `docs/private/signal-concentration.md`

**What it does:** Analysis page — signal cards ranked by composite score (concentration × agreement × intensity), section × sentiment and theme × sentiment heatmaps with adjusted standardised residuals, dark mode support. Full pipeline integration: Python math module computes metrics, renderer produces standalone `analysis.html` with injected JSON, client-side JS builds the UI.

**Phase 1 — Static mockup (`docs/mockups/mockup-analysis.html`):**
- Signal cards: two-column layout (identity left, metrics right), expandable quote list with timecodes, speaker links, per-quote intensity dots aligned under mean intensity dots
- Metrics panel: signal strength, concentration (bar, 0–8× absolute scale), agreement/N_eff (bar, 0–N scale), mean intensity (SVG half-fill dots)
- Confidence classification (Strong/Moderate/Emerging): computed but **hidden from UI** — misleading next to signal strength number. CSS + JS preserved with TODOs for future restoration
- Heatmap: section × sentiment and theme × sentiment tables with residual-driven cell colouring, click-to-highlight linking to signal cards
- Quotes: sorted by participant then timecode, hanging-indent quote-row layout (timecode → quote body → intensity dots), timecode links to player, speaker links to transcript pages

**Phase 2 — Python math module (`bristlenose/analysis/`):**
- `metrics.py` — 5 pure functions: `concentration_ratio`, `simpsons_neff`, `mean_intensity`, `composite_signal`, `adjusted_residual`
- `models.py` — plain dataclasses: `MatrixCell`, `Matrix`, `SignalQuote`, `Signal`, `AnalysisResult`
- `matrix.py` — `build_section_matrix()`, `build_theme_matrix()` from grouped quotes
- `signals.py` — `detect_signals()` with MIN_QUOTES_PER_CELL=2, DEFAULT_TOP_N=12, confidence classification

**Phase 3 — Pipeline integration + HTML rendering:**
- `pipeline.py` — `_compute_analysis()` glue function, lazy import, participant counting (sessions or quote fallback, moderator exclusion via `startswith("p")`)
- `render_html.py` — `_render_analysis_page()`, `_serialize_analysis()`, `_serialize_matrix()`, JSON injection into IIFE-wrapped `<script>`, toolbar "Analysis" button
- `analysis.html` template — 12-line skeleton with div containers, JS populates all content
- `analysis.js` (423 lines) — `renderSignalCards()`, `renderHeatmap()`, OKLCH colour interpolation, theme-responsive via MutationObserver, cell-click-to-card linking
- `analysis.css` (336 lines) — signal cards, heatmaps, `light-dark()` for theme, expansion animation

**Test coverage (97 tests across 4 files):**
- `test_analysis_metrics.py` (39 tests) — all 5 metrics with edge cases (zeros, empty, boundary)
- `test_analysis_matrix.py` (13 tests) — section/theme matrix building, None sentiment exclusion, ordering
- `test_analysis_signals.py` (14 tests) — signal detection, confidence classification, quote ordering, top-N
- `test_analysis_integration.py` (58 tests) — `_compute_analysis`, serialization round-trip, HTML render end-to-end, confidence boundaries, quote-lookup consistency, edge cases (pipe in labels, non-ASCII, zero participants, single participant, natural PID sorting)

**Files this branch touches:**
- `bristlenose/analysis/__init__.py` — **new** package
- `bristlenose/analysis/models.py` — **new** data structures
- `bristlenose/analysis/metrics.py` — **new** pure math functions
- `bristlenose/analysis/matrix.py` — **new** matrix builder
- `bristlenose/analysis/signals.py` — **new** signal detector
- `bristlenose/pipeline.py` — `_compute_analysis()` added, called from `run()`, `run_analysis_only()`, `run_render_only()`
- `bristlenose/stages/render_html.py` — `_render_analysis_page()`, serialization, analysis JS list, toolbar button
- `bristlenose/output_paths.py` — `analysis_file` property
- `bristlenose/theme/templates/analysis.html` — **new** template skeleton
- `bristlenose/theme/js/analysis.js` — **new** client-side rendering
- `bristlenose/theme/organisms/analysis.css` — **new** styles
- `docs/mockups/mockup-analysis.html` — **new** original prototype
- `tests/test_analysis_metrics.py` — **new**
- `tests/test_analysis_matrix.py` — **new**
- `tests/test_analysis_signals.py` — **new**
- `tests/test_analysis_integration.py` — **new**

**Potential conflicts with other branches:**
- `render_html.py` — always hot; adds `_render_analysis_page()` and serialization helpers
- `pipeline.py` — adds `_compute_analysis()` and calls from three pipeline methods
- `output_paths.py` — adds `analysis_file` property

**Next phases:** (see `docs/design-analysis-future.md` for full design thinking)
- **Explore first** — use on 2–3 real studies before adding interactivity
- Phase 4: two-pane layout — grids as interactive selectors (cell/row/column toggles) controlling signal cards in right pane
- Phase 5: LLM narration — natural-language insight summaries on signal cards
- User-tag × group grid — new design needed, different from sentiment grids
- Future: sentiment trajectory detection (Jensen-Shannon divergence), participant sparkline grid, embeddings for cross-boundary discovery

---

### `transcript-annotations`

**Status:** Phase 1–3 implemented, needs visual polish
**Started:** 9 Feb 2026
**Worktree:** `/Users/cassio/Code/bristlenose_branch transcript-annotations/`
**Remote:** `origin/transcript-annotations`

**What it does:** Annotated transcript pages — quote highlighting (inline `<mark>` using `verbatim_excerpt` from LLM), right-margin section/theme labels, sentiment + user tag badges, cross-window sync. Data pipeline working; visual design needs refinement.

**Files this branch touches:**
- `bristlenose/llm/structured.py` — `verbatim_excerpt` field on `ExtractedQuoteItem`
- `bristlenose/models.py` — `verbatim_excerpt` field on `ExtractedQuote`
- `bristlenose/stages/quote_extraction.py` — passes `verbatim_excerpt` through
- `bristlenose/stages/render_html.py` — highlight rendering, quote map data injection, margin JS init
- `bristlenose/theme/tokens.css` — `--bn-colour-cited-bg` token
- `bristlenose/theme/templates/transcript.css` — quoted/uncited segment styles
- `bristlenose/theme/js/transcript-annotations.js` — **new** margin annotation module
- `bristlenose/theme/molecules/transcript-annotations.css` — **new** margin layout
- `tests/test_transcript_annotations.py` — **new** 26 tests

**Potential conflicts with other branches:**
- `render_html.py` — always hot; `_render_transcript_page()` modified heavily
- `tokens.css` — new token added

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
