# Bristlenose — Product Roadmap

Everything planned, from trivial polish to multi-month features. Big-ticket items point to their design docs rather than duplicating content here.

**Current status:** v0.10.3, Feb 2026. Core pipeline complete and published (PyPI, Homebrew, Snap). Serve mode shipped; React migration in progress on `main`.

---

## Strategic milestones

Sequenced by dependency — each milestone unlocks the next.

### Milestone 1: Complete React component library

Build all 14 reusable primitives in 4 rounds, then compose them into page-level components (QuoteCard, SessionsRow, CodebookGroup, SignalCard, TranscriptSegment).

- **Round 1** (done): Badge, PersonBadge, TimecodeLink
- **Round 2** (done): EditableText, Toggle (+Modal, Toast as infra)
- **Round 3** (done): TagInput, Sparkline
- **Round 4** (done): Metric, Annotation, Counter, Thumbnail, JourneyChain

Design doc: `docs/design-react-component-library.md`

### Milestone 2: API replaces localStorage

Wire React components to the server data API (6 endpoints, 94 tests already exist). Remove localStorage as the source of truth for tags, edits, stars, hidden quotes, deleted badges.

Design docs: `docs/design-reactive-ui.md`, `bristlenose/server/CLAUDE.md`

### Milestone 3: Playwright E2E tests

Once the React DOM stabilises, add browser tests covering all 11 DB-mutating user actions. Convention: `data-testid="bn-{component}-{element}"` on every interactive element.

Design doc: `docs/design-test-strategy.md`

### Milestone 4: Multi-project support

Home screen showing all projects. Create new blank projects. Switch between projects without restarting the server. The DB schema already supports multiple projects (Project table with id/name/slug) — the API and CLI currently hardcode project ID 1.

**Needs design doc.** Key decisions: project file storage model (folder references vs central storage vs `.bristlenose` document package), home screen UX (full-page navigation vs sidebar), project metadata scope.

### Milestone 5: File import (drag-and-drop)

Drag video/audio/transcript files onto a drop target in the browser, or use a file picker. Files are linked into the project's input directory.

**Needs design doc.** Key decisions: copy vs symlink vs reference, folder drop vs file drop, browser file-path access limitations on localhost (may need server-side file dialog).

### Milestone 6: Settings UI

GUI equivalent of all `.env` / CLI configuration. Two scopes: app-wide defaults and per-project overrides. Settings page accessible from app chrome. 30+ settings across LLM provider, API keys, transcription, PII, pipeline, and theme categories.

**Needs design doc.** Key decisions: storage format (JSON file vs DB table), interaction between CLI flags and GUI settings, credential handling (keychain vs plaintext), first-run wizard in serve mode.

### Milestone 7: Run pipeline from GUI

"Analyse" button that runs the full pipeline as a background task. Progress view showing stages, timing, and estimated completion. Cancel button. Re-import into DB when complete.

**Needs design doc.** Key decisions: WebSocket vs SSE for progress streaming, background thread vs subprocess, per-session vs per-stage progress granularity, partial results during pipeline run.

The pipeline already emits `PipelineEvent` objects and the `TimingEstimator` produces time estimates — this is a wiring job, not new backend work.

### Milestone 8: Incremental re-run

Add 2 new interview recordings to an existing 6-session project, re-run the pipeline, preserve all researcher work (tags, stars, hidden, renames, text edits, deleted badges) on existing quotes.

Much of the infrastructure exists: quote stable key `(project_id, session_id, participant_id, start_timecode)` for dedup/upsert, `merge_people()` for people.yaml, `import_conflict` table in the schema (not yet populated). The hard part is selective re-clustering: do new quotes slot into existing clusters, or does everything re-cluster?

Design doc: `docs/design-serve-milestone-1.md` (merge strategy section)

### Milestone 9: Export & sharing

Standalone HTML export (works today via `bristlenose render`). Published reports with starred video clips on Cloudflare R2. Password protection, then Google/Microsoft SSO, then workspace URLs and view tracking.

Deferred until post-React — the React app can hydrate from either a server API or an embedded JSON blob, making export natural rather than a separate plumbing effort.

Design docs: `docs/design-export-sharing.md`, `docs/private/publish-and-sharing.md`, `docs/private/video-formats-and-transcoding.md`

### Milestone 10: macOS native app

Native Swift/SwiftUI shell (~650 lines) around a WKWebView showing the same HTML report. PyInstaller-frozen Python sidecar communicating via stdin/stdout JSON-RPC. AVFoundation replaces FFmpeg (5 MB vs 80 MB). mlx-whisper for Metal GPU transcription. Mac App Store distribution (sandbox works — corrected understanding). Annual subscription.

Design docs: `docs/private/desktop-app-exploration.md` (technical architecture, blockers, effort estimates), `docs/private/repo-app-biz-strategy.md` (repo structure, pricing, competitive landscape, App Store strategy)

---

## Feature backlog

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
| Sticky header decision | #15 | small |
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
| Relocate AI tag toggle (removed from toolbar, needs new home) | — | small |
| Deploy feedback endpoint to Dreamhost | — | small |
| User research panel opt-in (email field in feedback modal) | — | small |

Ref: `docs/design-dashboard-stats.md` for the full dashboard stats inventory and priorities.

### Report JavaScript

| Item | Issue | Effort |
|------|-------|--------|
| Add `'use strict'` to all modules | #7 | trivial |
| Extract shared `utils.js` for duplicated code | #8 | trivial |
| Extract magic numbers to config object | #9 | trivial |
| Drop `execCommand('copy')` fallback | #10 | trivial |
| Split `tags.js` into smaller modules | #22 | small |
| Explicit cross-module state management | #23 | small |
| Auto-suggest accessibility (ARIA) | #24 | small |
| JS tests (jsdom or Playwright) | #28 | medium |

### Analysis page

| Item | Effort |
|------|--------|
| Phase 4: two-pane layout, grid-as-selector | medium |
| Phase 5: LLM narration of signal cards | small |
| User-tag × group grid (new design needed) | medium |

Ref: `docs/design-analysis-future.md`

### Transcript page interactions

| Item | Effort |
|------|--------|
| User tags on transcript page | small |
| Tidy up extent bars | small |
| Expand/collapse sections and themes | medium |
| Pulldown menu on margin annotations | medium |
| Flag uncited quote for inclusion | medium–large |
| Drag-and-drop quote reordering | large |

### Pipeline & LLM

| Item | Issue | Effort |
|------|-------|--------|
| Moderator Phase 2: cross-session linking | #25 | medium |
| Speaker diarisation improvements | #26 | medium |
| Batch processing dashboard | #27 | medium |
| Custom prompts (user-defined tag categories) | — | medium |
| Pass transcript data to renderer (avoid redundant I/O) | — | small |

Ref: `docs/design-llm-providers.md`, `docs/design-research-methodology.md`

### Performance

| Item | Issue | Effort |
|------|-------|--------|
| Cache `system_profiler` results | #30 | trivial |
| Skip logo copy when unchanged | #31 | trivial |
| Temp WAV cleanup after transcription | #33 | small |
| Word timestamp pruning after merge stage | #35 | small |
| Pipeline stages 8→9 per-participant chaining | #32 | medium |
| LLM response cache | #34 | medium |

Ref: `docs/design-performance.md` for full audit, done items, and "not worth optimising" rationale.

### CLI

| Item | Issue | Effort |
|------|-------|--------|
| Britannification pass | #40 | trivial |
| `--prefetch-model` flag for Whisper | #41 | trivial |
| Shell completion (`--install-completion`) | — | trivial |

Ref: `docs/design-cli-improvements.md`

### Packaging & distribution

| Item | Issue | Effort |
|------|-------|--------|
| Homebrew formula: post_install for spaCy model | #42 | trivial |
| Snap store publishing | #45 | small |
| Platform detection refactor: shared `utils/system.py` | #43 | small |
| Windows installer (winget) | #44 | medium |

### Testing & CI

| Item | Effort |
|------|--------|
| Enable pytest coverage in CI | trivial |
| Multi-Python CI (3.10, 3.11, 3.12, 3.13) | trivial |
| Add macOS to main CI | small |
| Vitest + React Testing Library setup | small |
| ESLint + Prettier for frontend | small |
| Component tests for each React primitive | medium |
| A11y lint rules (`eslint-plugin-jsx-a11y`) | small |
| Playwright E2E tests (12 core + graceful degradation) | medium |
| Visual regression baselines (light + dark) | medium |
| Cross-browser Playwright (Chromium, Firefox, WebKit) | small |
| Bundle size budget tracking | small |
| axe-core accessibility assertions in E2E | small |
| Alembic setup (SQLite migration) | small |

Ref: `docs/design-test-strategy.md`

### Infrastructure & internal

| Item | Effort |
|------|--------|
| SVG icon set (replace × character glyphs) | small |
| Namespace localStorage keys by project slug | trivial |
| Tighten `postMessage` origin from `'*'` to same-origin | trivial |
| Inject `BRISTLENOSE_CODEBOOK_URL` as configurable global | trivial |
| People.yaml web UI (part of Moderator Phase 2) | medium |
| Miro bridge (near-term sharing story) | medium |

### Theme refactoring (pick up when working in these areas)

- Typography audit: 16 font-sizes → ~10, introduce `--bn-font-size-*` tokens
- Tag-count aggregation: 3 implementations → shared `countUserTags()`
- Shared user-tags data layer: extract `userTagStore`
- `isEditing()` guard deduplication: shared `EditGuard` class
- Inline edit commit pattern: shared `inlineEdit()` helper (~6 repetitions)
- Close button CSS base class: extract `.close-btn` atom
- Input focus CSS base class: extract `.bn-input` atom

---

## Dependency maintenance

### Quarterly review (next: May 2026, then Aug, Nov)

Run `pip list --outdated`. Bump floor pins only for security fixes, needed features, or 2+ major versions behind.

### Annual review (next: Feb 2027)

- Python EOL check (3.10 EOL Oct 2026)
- faster-whisper / ctranslate2 project health
- spaCy major version (3.x → 4.x)
- Pydantic major version
- Rebuild snap
- Review `pip-audit` CI output

### Risk register

| Dependency | Risk | Escape hatch |
|-----------|------|------------|
| faster-whisper / ctranslate2 | High | mlx-whisper (macOS), whisper.cpp bindings |
| spaCy + thinc + presidio | Medium | Pin spaCy 3.x indefinitely; contained to PII stage |
| anthropic / openai SDKs | Low | Floor pins, backward-compatible |
| Pydantic | Low | Stable at 2.x |
| Python | Low | Running 3.12; bump floor when 3.10 EOLs |

---

## Items needing design docs

These big-ticket features don't yet have dedicated design docs and need them before implementation begins:

| Feature | What to design |
|---------|---------------|
| **Multi-project support** | Project registry model, home screen UX, project file storage, API changes (remove hardcoded project ID 1) |
| **File import / drag-and-drop** | Upload vs path reference, folder support, browser file-path limitations, validation |
| **Settings UI** | Storage format, config priority chain (CLI vs GUI), credential handling, per-project vs app-wide scoping |
| **Run pipeline from GUI** | Progress streaming (WebSocket vs SSE), background execution model, cancel flow, re-import on completion |

These four features could share a single design doc (e.g. `docs/design-app-experience.md`) since they're tightly coupled — or be individual docs. The macOS native app, export/sharing, and incremental re-run already have design docs.

---

## Design doc index

| Document | Covers |
|----------|--------|
| `docs/design-reactive-ui.md` | Framework choice, risk assessment, migration audit, server options |
| `docs/design-react-component-library.md` | 14 primitives, 4-round build sequence, coverage matrix |
| `docs/design-serve-migration.md` | Serve architecture, island pattern, tech stack |
| `docs/design-serve-milestone-1.md` | Domain model, DB schema, importer, merge strategy |
| `docs/design-test-strategy.md` | Testing gaps, Playwright plan, `data-testid` convention |
| `docs/design-export-sharing.md` | Export phases 0–5, React dependency |
| `docs/design-analysis-future.md` | Two-pane layout, grid-as-selector, user-tag grid |
| `docs/design-dashboard-stats.md` | Unused pipeline data, dashboard improvement priorities |
| `docs/design-llm-providers.md` | Provider roadmap, Gemini, documentation |
| `docs/design-performance.md` | Performance audit, done/open/not-worth-it |
| `docs/design-cli-improvements.md` | CLI warts and fixes |
| `docs/design-html-report.md` | Report features, people file, transcript pages |
| `docs/design-research-methodology.md` | Quote selection, sentiment taxonomy, clustering rationale |
| `docs/design-doctor-and-snap.md` | Doctor command, snap packaging |
| `docs/design-platform-transcripts.md` | Platform transcript ingestion |
| `docs/design-transcript-coverage.md` | Transcript coverage feature |
| `docs/design-codebook.md` | Codebook editor |
| `docs/design-keychain.md` | Keychain credential storage |
| `docs/design-keyboard-navigation.md` | Keyboard shortcuts |
| `docs/design-test-data-generation.md` | Test data generation |
| **Private** | |
| `docs/private/desktop-app-exploration.md` | macOS native app: architecture, blockers, effort, pricing |
| `docs/private/repo-app-biz-strategy.md` | Repo structure, App Store, competitive landscape |
| `docs/private/publish-and-sharing.md` | Published reports with starred video clips |
| `docs/private/pricing-and-revenue.md` | Pricing model, revenue scenarios |
| `docs/private/video-formats-and-transcoding.md` | Codec compatibility, clip extraction |
