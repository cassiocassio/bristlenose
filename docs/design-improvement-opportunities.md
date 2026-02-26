# Improvement Opportunities

A reflective audit of Bristlenose's architecture, design system, frontend, testing, and developer experience — conducted Feb 2026 against v0.10.3. Organised by area, each item tagged with effort and priority.

## Architecture

### Strengths

- **Clean module boundaries.** Stages are loosely coupled pure functions; the server has its own ORM independent of pipeline models; the LLM client abstracts 5 providers behind one interface.
- **Immutable data contracts.** Pydantic models enforce structure at every stage boundary — no stringly-typed handoffs.
- **Crash recovery shipped.** Manifest-based resume (Phase 1a–1d-ext) with atomic writes, per-session tracking, and a `status` command. Production-grade for a local tool.

### What could improve

| # | Item | Why it matters | Effort | Priority |
|---|------|---------------|--------|----------|
| A1 | **Break up `render_html.py`** (1,245 lines) | God object that knows about data models, people files, coverage, thumbnails, CSS/JS concatenation, and file I/O. Hard to test or change in isolation. Extract into `html_builder`, `asset_bundler`, `video_mapper`. | M | Medium |
| A2 | **Consolidate timecode functions** | `format_timecode()` / `parse_timecode()` are identical in `models.py` and `utils/timecodes.py`. Remove from `models.py`, import from utils. | S | High |
| A3 | **Centralise magic numbers** | `_MAX_SESSIONS_NO_CONFIRM = 16`, `_MAX_WARN_LEN = 74`, `_MAX_SLUG_LENGTH = 50` scattered across files. Move to a `constants.py` or fold into `BristlenoseSettings`. | S | Low |
| A4 | **Standardise error handling** | No custom exception hierarchy — stages use `ValueError`, `RuntimeError`, bare `Exception` interchangeably. Some stages raise, others accumulate. Define `BristlenoseError` base + `LLMError`, `StageError`, `ConfigError`. | M | Medium |
| A5 | **Make stage dependencies explicit** | Stage execution order is implicit (enforced only by call sequence in `pipeline.py`). A lightweight `requires` metadata on each stage function would make the DAG visible and enable future parallel scheduling. | M | Low |
| A6 | **Shared transcript parser** | `pipeline.py:load_transcripts_from_dir()` and `server/importer.py:_parse_transcript_file()` implement similar logic. Extract to `utils/transcript_parser.py`. | S | Medium |

## Design System & Frontend

### Strengths

- **Textbook atomic CSS.** 98 CSS files in a clean tokens → atoms → molecules → organisms → templates hierarchy. 6,317 lines, well-factored.
- **Modern colour system.** OKLCH pentadic palette with `light-dark()` for dark mode — no class toggling, no duplication.
- **Complete primitive library.** 16/16 React primitives shipped with consistent API (controlled components, `data-testid`, className passthrough).
- **Zero CSS duplication between render paths.** Both static HTML and serve mode share the same CSS — only JS diverges.

### What could improve

| # | Item | Why it matters | Effort | Priority |
|---|------|---------------|--------|----------|
| D1 | **Implement responsive quote grid** | Designed (mockup exists, `auto-fill` CSS Grid, cards at 23rem) but not shipped. Single biggest UX win — MacBook gets 3 columns, Studio Display gets 5. ~1 hour of CSS. | S | High |
| D2 | **Tokenise remaining hardcoded values** | ~30 values still inline: danger/success colours use fallbacks instead of `light-dark()`, animation durations scattered, no responsive breakpoint tokens. | S | Medium |
| D3 | **Add focus trap to modals** | Modals exist (threshold review, report) but Tab key escapes them. Quick a11y fix with `focus-trap-react` or a 20-line hook. | S | Medium |
| D4 | **Add skip-to-content link** | No landmark navigation. A single hidden-until-focused `<a>` at the top of the page. 5 minutes. | XS | Medium |
| D5 | **Finish vanilla JS → React migration** | 8,152 lines of frozen vanilla JS serve the static render path. Steps 5–10 of the React migration plan remain. Each step retires a vanilla module and its maintenance burden. | L | Medium |
| D6 | **Bundle size monitoring** | No size budget or tracking. Not critical for a local tool today, but prevents regressions as islands grow. `vite-plugin-bundle-analyzer` or `size-limit`. | S | Low |

## Testing

### Strengths

- **1,837 Python tests** with a 1:1 test-to-source LOC ratio. All pipeline stages, API endpoints, edge cases (international names, provider horror scenarios), and crash recovery are covered.
- **587 Vitest tests** for React primitives and islands, 100% pass rate.
- **Resilience tests are thorough.** `test_pipeline_resume.py` is 858 lines covering mid-stage failures, manifest corruption, and session-level resume.

### What could improve

| # | Item | Why it matters | Effort | Priority |
|---|------|---------------|--------|----------|
| T1 | **Add Python version matrix to CI** | `pyproject.toml` claims `>=3.10` but CI only tests 3.12. Breakages on 3.10/3.11/3.13 go undetected until user reports. | XS | High |
| T2 | **Fix 58 frontend lint errors** | `npm run lint` fails. Primary culprit: `react-hooks/immutability` violations in `TranscriptAnnotations.tsx`. Blocks any frontend CI gate. | S | High |
| T3 | **Add `npm run lint` + `npm run typecheck` to CI** | Frontend has no quality gate in CI. TypeScript errors and lint failures can ship. | XS | High |
| T4 | **Enable pytest coverage reporting** | `pytest-cov` is installed but not wired up. Add `--cov=bristlenose --cov-report=term` to CI for visibility into gaps. | XS | Medium |
| T5 | **Set up Playwright E2E tests** | No browser automation tests despite the test strategy doc specifying 12 initial scenarios. Serve mode React islands + vanilla JS shell interactions are only tested manually. | M | High |
| T6 | **Add automated a11y tests** | Good semantic HTML but no `jest-axe` or `axe-core` in the test suite. Catches regressions that visual inspection misses. | S | Medium |
| T7 | **Add `npm audit` to CI** | Frontend dependency vulnerabilities are unchecked. Add as `continue-on-error` (like `pip-audit`). | XS | Low |

## Logging & Observability

### Strengths

- **Two-knob logging system shipped.** `-v` for terminal, `BRISTLENOSE_LOG_LEVEL` for file. Per-project rotating log files (5 MB, 2 backups). Noisy third-party loggers suppressed.
- **Status command.** `bristlenose status <folder>` reads the manifest and prints project state without re-running anything.

### What could improve

| # | Item | Why it matters | Effort | Priority |
|---|------|---------------|--------|----------|
| O1 | **Ship Tier 1 logging instrumentation** | Specified in `design-logging.md` but not implemented: LLM response shape (catches double-serialisation bugs), token usage at INFO (post-mortem cost analysis), AutoCode batch progress. ~20 lines per PR. | S | High |
| O2 | **Add serve-mode request logging middleware** | No logging of API method/path/status/duration. Debugging serve-mode issues requires terminal access and reproduction. FastAPI middleware, ~15 lines. | S | Medium |
| O3 | **Add LLM call correlation IDs** | Log lines from the same LLM request can't be correlated. Pass a `request_id` through `LLMClient.call()` and include in all log lines for that call. | S | Low |

## Developer Experience

### Strengths

- **Excellent documentation.** 37 design docs, 4 subsystem CLAUDE.md files, academic citations in the resilience doc. Every major feature has a design rationale.
- **Zero stale TODOs in code.** No `TODO`, `FIXME`, or `HACK` comments — all tracked in `TODO.md`.
- **Fast local iteration.** `npm run dev` proxies to FastAPI with hot reload; `pytest` runs in <30s; `ruff check --fix` auto-corrects most lint.

### What could improve

| # | Item | Why it matters | Effort | Priority |
|---|------|---------------|--------|----------|
| X1 | **Write `docs/howto-add-pipeline-stage.md`** | No guide for the most common extension point. Developers must reverse-engineer from existing stages. Include annotated template, manifest wiring checklist, decision tree (per-session? LLM? cacheable?). | S | Medium |
| X2 | **Set up Dependabot** | No automated dependency update PRs. A `.github/dependabot.yml` takes 30 minutes and catches stale transitive deps. | XS | Low |
| X3 | **Add Alembic for SQLite migrations** | No schema migration tooling. First schema change to the 22-table serve-mode DB will be high-risk without it. Ship before the change is needed, not during. | M | Medium |
| X4 | **Add Storybook or equivalent** | 16 React primitives exist but aren't browsable in a catalogue. Aids visual QA and onboarding. | M | Low |

## Priority summary

**Do now** (< 1 day each, high impact):
- T1: Python version matrix in CI
- T2: Fix frontend lint errors
- T3: Frontend lint + typecheck in CI
- O1: Tier 1 logging instrumentation
- A2: Consolidate timecode functions

**Do soon** (1–3 days each, meaningful improvement):
- D1: Responsive quote grid
- T5: Playwright E2E setup
- A6: Shared transcript parser
- X1: Pipeline stage howto guide

**Do when relevant** (medium effort, unlock future work):
- A1: Break up `render_html.py`
- A4: Exception hierarchy
- X3: Alembic migrations
- D5: Continue React migration (Steps 5–10)

**Backlog** (nice to have, low urgency):
- A3: Centralise magic numbers
- A5: Explicit stage DAG
- D6: Bundle size monitoring
- X4: Storybook
