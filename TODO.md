# Bristlenose — Where I Left Off

Last updated: 1 Mar 2026 (React migration complete, CI stabilised, export shipped)

## Next session reminder

- [ ] **Codebook autocomplete Stage 2: double-t quick-repeat** — double-tap `t` within 400ms applies last-used tag to focused/selected quotes. Design: `docs/design-codebook-autocomplete.md` Stage 2. Files: `useKeyboardShortcuts.ts` (double-tap detection), `QuotesContext.tsx` (tag mutation, `lastUsedTag` tracking), CSS flash animation. Bulk support: multi-selected quotes get the tag too. Stage 1 (grouped autocomplete) shipped in commits `fbba431`, `c27351a`, `9e21266`. Estimated: half session
- [ ] **QA: threshold review dialog on real data** — run AutoCode against real interview projects and evaluate how well the confidence histogram + dual slider helps researchers eliminate false positives. Qualitative assessment, not automated
- [ ] **Auto-serve after run** — after `bristlenose run` completes, launch serve mode and open browser automatically instead of printing the static HTML link. The React served version is the canonical experience; the static HTML report link is misleading. Consider: `--no-serve` flag to opt out, port selection, what happens if serve deps are missing (fall back to static link)
- [ ] **Export polish** — inline logo as base64 (currently shows "Bristlenose logo" text), fix footer "Bristlenoseversion" missing space, fix in-report navigation links (plain `<a href="/report/...">` don't work with hash router — need React Router `<Link>` or hash-aware hrefs)
- [ ] **Help modal styling** — renders but needs polish (no close button, layout rough)
- [ ] **Responsive quote grid** — CSS-only Phase 1. Design doc ready (`docs/design-responsive-layout.md`), mockup exists. Plan approved, not yet implemented
- [ ] **Skill stress test: remote-only branch** — test `/close-branch` when remote branch exists but local was deleted (someone pushed, you fetched). Exercises the "nothing local to delete, remote exists" path

---

## Task tracking

**GitHub Issues is the source of truth for actionable tasks:** https://github.com/cassiocassio/bristlenose/issues

This file contains: session reminders, feature groupings with context, items too small for issues, architecture notes, dependency maintenance, and completed work history.

### Priority order

1. **Export polish** — fix remaining rough edges from Step 10 export
2. **Help modal styling** — visual polish pass
4. **Responsive quote grid** — CSS-only Phase 1
5. **Extract design tokens for Figma** — pull colours, spacing, typography, radii from `bristlenose/theme/` into a structured format (JSON/CSS variables) importable as Figma variables. Enables Figma MCP round-trip workflow
4. **Moderator Phase 2** (#25) — cross-session linking
5. **Dark mode selection highlight** (#52) — visibility bug
6. **SVG icon set** — replace fragile character glyphs (no issue — small enough to just do)
7. **Miro bridge** — near-term sharing story. See `docs/private/design-miro-bridge.md`

---

## Feature roadmap by area

### Report UI

| Item | Issue | Effort |
|------|-------|--------|
| Dashboard: increase stats coverage | — | medium |
| Dark mode: selection highlight visibility | #52 | trivial |
| Logo: increase size from 80px to ~100px | #6 | trivial |
| Show day of week in session Start column | #11 | small |
| Reduce AI tag density (tune prompt or filter) | #12 | small |
| User-tags histogram: right-align bars | #13 | small |
| Clickable histogram bars → filtered view | #14 | small |
| Refactor render_html.py header/toolbar into template helpers | #16 | small |
| Theme management in browser (custom CSS themes) | #17 | small |
| Dark logo: proper albino bristlenose pleco | #18 | small |
| Lost quotes: surface unselected quotes for rescue | #19 | small |
| .docx export | #20 | small |
| Edit writeback to transcript files | #21 | small |
| Tag definitions page | #53 | small |
| Undo bulk tag (Cmd+Z for last tag action) | — | medium |
| Multi-page report (tabs or linked pages) | #51 | large |
| Project setup UI for new projects | #49 | large |
| Responsive quote grid layout | — | medium |
| Content density setting (Compact / Normal / Generous) | — | small |

### Content density setting

Three-way toggle (Compact / Normal / Generous) that scales content without touching chrome (nav, toolbar, logo). All spacing tokens are `rem`-based, so a single `font-size` change on `<article>` cascades to quote text, badges, timecodes, headings, and padding.

| Setting | `article` font-size | Use case |
|---------|---------------------|----------|
| Compact | 14px (0.875rem) | Dense scanning, big datasets, small screens |
| Normal | 16px (1rem) | Default — current look |
| Generous | 18px (1.125rem) | Screen-sharing, calls, accessibility, large monitors |

Implementation: add `--bn-content-scale` token (`0.875` / `1` / `1.125`), set `font-size: calc(var(--bn-content-scale) * 1rem)` on `<article>`. Toggle in toolbar or settings. Persist via preferences store. Interacts with responsive grid — Generous + wide screen = fewer but more readable columns.

### Responsive layout

Multi-column quote grid using CSS `auto-fill`. Card max-width `23rem` (368px) keeps ~5 words/line for fast scanning. Columns add automatically as viewport widens — no JS. Mockup: `docs/mockups/responsive-quote-grid.html`. Full design: `docs/design-responsive-layout.md`.

### Pipeline and analysis

| Item | Issue | Effort |
|------|-------|--------|
| Signal concentration: Phase 4 — two-pane layout, grid-as-selector | — | medium |
| Signal concentration: Phase 5 — LLM narration of signal cards | — | small |
| Signal concentration: user-tag × group grid (new design needed) | — | medium |
| Session enable/disable toggle (temporary exclusion from analysis) | — | medium |
| Delete/quarantine session from UI (`.bristlenose-ignore`) | — | medium |
| Re-run pipeline from serve mode (background, with progress) | — | large |
| Moderator Phase 2: cross-session linking | #25 | medium |
| Speaker diarisation improvements | #26 | medium |
| Batch processing dashboard | #27 | medium |
| Quote sequences: ordinal-based detection for non-timecoded transcripts | — | medium |
| Quote sequences: "verse numbering" for plain-text transcripts | — | medium |
| Quote sequences: per-project threshold configurability | — | small |

Session management design doc: `docs/design-session-management.md`

### CLI

| Item | Issue | Effort |
|------|-------|--------|
| Britannification pass | #40 | trivial |
| `--prefetch-model` flag for Whisper | #41 | trivial |
| Doctor: serve-mode checks + Vite auto-discovery | — | medium |

### Packaging

| Item | Issue | Effort |
|------|-------|--------|
| CI: automate `.dmg` build on push | — | medium |
| `.dmg` README: include "Open Anyway" instructions | — | trivial |
| Homebrew formula: post_install for spaCy model | #42 | trivial |
| Snap store publishing | #45 | small |
| Windows installer (winget) | #44 | medium |

### Desktop app (macOS)

| Item | Issue | Effort |
|------|-------|--------|
| Keychain: migrate from `security` CLI to native Security framework | — | small |
| ReadyView: replace `NSOpenPanel.runModal()` with SwiftUI `.fileImporter()` | — | trivial |
| ProcessRunner: replace `availableData` polling with `AsyncBytes` | — | small |
| `hasAnyAPIKey()` only checks Anthropic — rename or extend | — | trivial |

### Performance

See `docs/design-performance.md` for full audit, done items, and "not worth optimising" rationale.

| Item | Issue | Effort |
|------|-------|--------|
| Cache `system_profiler` results | #30 | trivial |
| Skip logo copy when unchanged | #31 | trivial |
| Pipeline stages 8→9 per-participant chaining | #32 | medium |
| Temp WAV cleanup after transcription | #33 | small |
| LLM response cache | #34 | medium |
| Word timestamp pruning after merge stage | #35 | small |

### Logging instrumentation

See `docs/design-logging.md` for architecture and full tier breakdown. Infrastructure (log file, two-knob system) is done.

| Item | Tier | Effort |
|------|------|--------|
| Cache hit/miss decisions in `_is_stage_cached()` | 2 | trivial |
| Importer per-entity sync stats | 2 | trivial |
| Promote model name from DEBUG to INFO in `_analyze_*` methods | 2 | trivial |
| Concurrency queue depth at semaphore creation | 3 | trivial |
| PII entity type breakdown per session | 3 | small |
| FFmpeg command and return code on failure | 3 | trivial |
| Keychain resolution: which store, which keys | 3 | trivial |
| Manifest load/save: schema version, stage summary | 3 | trivial |

### Internal refactoring

| Item | Issue | Effort |
|------|-------|--------|
| Platform detection refactor: shared `utils/system.py` | #43 | small |

### Testing & infrastructure

| Item | Effort |
|------|--------|
| Storybook / component playground for primitives | medium |
| Playwright E2E layer 4 (structural smoke tests) | medium |
| Playwright E2E write-action tests (11 actions: star, hide, edit, tag, etc.) | large |

---

## Items only tracked here (not in issues)

These are too small for issues or are internal-only concerns.

- [ ] **SVG icon set** — replace all character glyphs (delete circles, modal close, search clear) with SVG icons. Candidates: Lucide, Heroicons, Phosphor, Tabler. See `docs/design-system/icon-catalog.html`
- [ ] **Relocate AI tag toggle** — removed from toolbar (too crowded); needs a new home. Code commented out in `render_html.py` and `codebook.js`/`tags.js`
- [ ] **User research panel opt-in** — optional email field in feedback modal
- [ ] **Miro bridge** — Miro-shaped CSV export → API integration → layout engine. See `docs/private/design-miro-bridge.md`
- [ ] **Tag definitions page** — also tracked as #53
- [ ] **Custom prompts** — user-defined tag categories via `bristlenose.toml` or `prompts.toml`
- [ ] **Framework acronym prefixes on badges** — small-caps 2–3 letter author prefix (e.g. `JJG`, `DN`). CSS class exists, parked until visual pattern finalised
- [ ] **Drag-to-reorder codebook frameworks** — researchers drag framework `<details>` sections to prioritise. Persist order per project
- [ ] **Pass transcript data to renderer** — avoid redundant disk I/O in `render_html.py`
- [ ] **People.yaml web UI** — in-report UI to update unidentified participants. API endpoint exists, missing the HTML renderer and UX design. Part of Moderator Phase 2 (#25)
- [ ] **Post-analysis review panel** — non-modal, dismissable panel after pipeline completes in serve mode for name correction, token summary, coverage overview

### Investigations (no commitment)

- [ ] **Sentiment badges as a built-in codebook framework** — sentiments are conceptually just another codebook; refactoring would unify with thresholds, review dialog, accept/deny. Big but significant simplification
- [ ] **Tag namespace uniqueness + import merge strategy** — flat namespace, clash detection, provenance tracking (user-created vs framework vs AutoCode)
- [ ] **Tokenise acceptance flash as design system pattern** — generalise `badge-accept-flash` into reusable `.bn-confirm-flash` + `useFlash(key)` hook
- [ ] **Canonical tag → colour as first-class schema** — persist `colour_set`/`colour_index` on `TagDefinition` to survive reordering; eliminate client-side colour computation
- [ ] **Sidebar filter undo history stack** — multi-step undo for tag filter state changes in the Tag Sidebar (show-only clicks, tick toggles). See `docs/design-codebook-autocomplete.md` Decision 6b

### Transcript page interactions

Ideas from 9 Feb 2026 session, roughly in order of effort:

- [ ] User tags on transcript page (small)
- [ ] Tidy up extent bars (small)
- [ ] Expand/collapse sections and themes in main report (medium)
- [ ] Pulldown menu on margin annotations — move quote to different section/theme (medium)
- [ ] Flag uncited quote for inclusion (medium–large)
- [ ] Drag-and-drop quote reordering (large)

### Vanilla JS refactoring (frozen — static render path only)

These apply to the legacy vanilla JS in `bristlenose/theme/js/`. Per CLAUDE.md, vanilla JS is frozen (data-integrity fixes only, no feature work). Low priority.

- [ ] Typography and icon audit — 16 distinct font-sizes, consolidate to ~10
- [ ] Tag-count aggregation (3 implementations) → shared `countUserTags()`
- [ ] Shared user-tags data layer
- [ ] `isEditing()` guard deduplication
- [ ] Inline edit commit pattern (~6 repetitions) → shared helper
- [ ] Close button CSS base class → `.close-btn` atom
- [ ] Input focus CSS base class → `.bn-input` atom
- [ ] Checkbox atom — extract ghost checkbox style

### file:// → http:// migration prep

- [ ] Namespace localStorage keys by project slug (prevents multi-report collision)
- [ ] Tighten `postMessage` origin from `'*'` to same-origin

---

## Dependency maintenance

Bristlenose has ~30 direct + transitive deps across Python, ML, LLM SDKs, and NLP. CI runs `pip-audit` on every push (informational, non-blocking).

### Quarterly dep review (next: May 2026, then Aug 2026, Nov 2026)

- [ ] **May 2026** — Run `pip list --outdated`. Bump floor pins in `pyproject.toml` only if there's a security fix, a feature you need, or the floor is 2+ major versions behind
- [ ] **Aug 2026** — Same
- [ ] **Nov 2026** — Same

### Annual review (next: Feb 2027)

- [ ] **Feb 2027** — Full annual review:
  - Check Python EOL dates — Python 3.10 EOL is Oct 2026; if past EOL, bump `requires-python`, `target-version`, `python_version`
  - Check faster-whisper / ctranslate2 project health
  - Check spaCy major version
  - Check Pydantic major version
  - Rebuild snap; review `pip-audit` CI output

### Risk register

| Dependency | Risk | Escape hatch |
|---|---|---|
| faster-whisper / ctranslate2 | High — fragile chain, maintenance varies | `mlx-whisper` (macOS), `whisper.cpp` bindings |
| spaCy + thinc + presidio | Medium — spaCy 3.x pins thinc 8.x | Contained to PII stage; can pin 3.x indefinitely |
| anthropic / openai SDKs | Low — backward-compatible | Floor pins are fine |
| Pydantic | Low — stable at 2.x | Large migration but not urgent |
| Python itself | Low (now) — 3.10 EOL Oct 2026 | Bump floor at EOL |
| protobuf (transitive) | Low — CVE-2026-0994 (DoS); we don't parse untrusted protobuf | Resolves when patched |

---

## Key files to know

| File | What it does |
|------|-------------|
| `pyproject.toml` | Package metadata, deps, tool config (version is dynamic — from `__init__.py`) |
| `bristlenose/__init__.py` | **Single source of truth for version** (`__version__`) |
| `bristlenose/cli.py` | Typer CLI entry point |
| `bristlenose/config.py` | Pydantic settings (env vars, .env, bristlenose.toml) |
| `bristlenose/pipeline.py` | Pipeline orchestrator |
| `bristlenose/people.py` | People file: load, compute stats, merge, write, display name map |
| `bristlenose/stages/render_html.py` | HTML report renderer |
| `bristlenose/theme/` | Atomic CSS design system |
| `bristlenose/theme/js/` | Report JavaScript modules (frozen — static render path only) |
| `bristlenose/llm/prompts/` | LLM prompt templates |
| `bristlenose/doctor.py` | Doctor check logic |
| `frontend/` | Vite + React + TypeScript SPA |
| `.github/workflows/` | CI (ci.yml), release (release.yml), snap (snap.yml) |
| `snap/snapcraft.yaml` | Snap recipe |

## Key URLs

- **Repo:** https://github.com/cassiocassio/bristlenose
- **Issues:** https://github.com/cassiocassio/bristlenose/issues
- **PyPI:** https://pypi.org/project/bristlenose/
- **Homebrew tap:** https://github.com/cassiocassio/homebrew-bristlenose
- **CI runs:** https://github.com/cassiocassio/bristlenose/actions

---

## Doctor: serve-mode checks + Vite auto-discovery

See `docs/design-serve-doctor.md` for full design. Summary: 4 new doctor checks, Vite auto-discovery via `/__vite_ping`, replace hardcoded port in `app.py`.

---

## Design docs

| Document | Covers |
|----------|--------|
| `docs/design-reactive-ui.md` | Framework comparison, risk assessment (partially superseded by React migration) |
| `docs/design-react-migration.md` | **React migration plan** (Steps 1–10, all complete) |
| `docs/design-react-component-library.md` | 16-primitive component library (complete) |
| `docs/design-llm-providers.md` | Provider roadmap |
| `docs/design-performance.md` | Performance audit |
| `docs/design-export-sharing.md` | Export and sharing phases 0–5 |
| `docs/design-html-report.md` | HTML report, people file, transcript pages |
| `docs/design-responsive-layout.md` | Responsive layout, density setting, breakpoints |
| `docs/design-doctor-and-snap.md` | Doctor command, snap packaging |
| `docs/design-serve-doctor.md` | Serve-mode doctor checks, Vite auto-discovery |
| `docs/design-research-methodology.md` | Quote selection, sentiment taxonomy, clustering rationale |
| `docs/design-pipeline-resilience.md` | Manifest, event sourcing, resume, provenance |
| `docs/design-logging.md` | Persistent log file, two-knob system |
| `docs/design-test-strategy.md` | Gap audit, Playwright plan, `data-testid` convention |
| `docs/design-desktop-app.md` | macOS app, SwiftUI, PyInstaller sidecar |
| `docs/design-session-management.md` | Re-import, enable/disable, quarantine |
| `docs/design-codebook-island.md` | Migration audit, API design, drag-drop |
| `docs/design-signal-elaboration.md` | Interpretive names, pattern types |
| `docs/design-transcript-editing.md` | Section strike, text correction, prior art |
| `docs/design-sidebar.md` | Dual-sidebar layout (TOC left, Tags right) |

---

## Done (reverse chronological)

- [x] **Playwright E2E harness layers 1–3** (Mar 2026) — console error monitor, link crawler, network assertion. Chromium + WebKit. Auto-starts `bristlenose serve` against smoke-test fixture. CI integration. Design doc: `docs/design-playwright-testing.md`
- [x] **React migration Steps 1–10** (Mar 2026) — full SPA with React Router, PlayerContext, FocusContext, keyboard shortcuts, export, app shell. See `docs/design-react-migration.md`
- [x] **CI stabilisation** (Mar 2026) — frontend lint/typecheck/vitest in GitHub Actions
- [x] **Export (Step 10)** — self-contained HTML download, blob-URL'd JS chunks, hash router for file://, optional anonymisation
- [x] **About panel redesign** — sidebar layout with 5 sections
- [x] **Configuration reference panel** in Settings
- [x] **Morville Honeycomb codebook** added
- [x] **Context expansion** — hover-reveal chevrons on timecodes, progressive transcript disclosure in quote cards
- [x] **Split speaker badges** — two-tone pill (code left, name right), settings toggle
- [x] **16-primitive React component library** (4 build rounds, 182 Vitest tests)
- [x] **Serve mode** — FastAPI + SQLite + React SPA, 22-table schema, full CRUD
- [x] **AutoCode** — engine, 7 API endpoints, Norman/Garrett/Plato prompts, threshold review dialog, 96 tests
- [x] **Signal elaboration** — LLM-generated interpretive names, pattern classification, sparkbar charts
- [x] **Video thumbnails** — auto-extracted keyframes, heuristic placement
- [x] **Analysis page** — signal cards, heatmaps, codebook grids, drill-down
- [x] **Pipeline crash recovery** (Phase 1a–1d-ext) — manifest-based resume, per-session tracking
- [x] **Phase 1 codebook import** — picker, preview, import, remove with impact stats
- [x] **Desktop app scaffold** — SwiftUI macOS shell, 5-state launcher, bundled sidecar
- [x] **Time estimation** — Welford's online algorithm, progressive disclosure
- [x] **Logging** — persistent log file, two-knob system (terminal + file)
- [x] **Session-count guard** — prompt before processing >16 sessions
- [x] **Status command** — `bristlenose status <folder>` reads manifest
- [x] **All LLM providers** — Claude, ChatGPT, Azure OpenAI, Gemini, Ollama
- [x] **Keychain integration** — `bristlenose configure`, native credential storage
- [x] **Doctor command** — 7 checks, pre-flight gate, first-run auto-doctor
- [x] **Codebook + hidden quotes** — tag organisation, colour-coded badges, group CRUD
- [x] **Keyboard shortcuts + search + multi-select** — j/k, star, tag, bulk actions
- [x] **Full 12-stage pipeline** — ingest → render, concurrent LLM + FFmpeg
- [x] **HTML report** — CSS theme, timecodes, video player, dark mode, people file, transcripts
- [x] **Published** — PyPI, Homebrew tap, snap (CI builds), man page
- [x] **CLI** — Cargo-style output, file-level progress, `--llm` aliases, British aliases
