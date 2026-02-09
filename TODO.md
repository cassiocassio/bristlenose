# Bristlenose — Where I Left Off

Last updated: 9 Feb 2026 (issue tracker consolidation + TODO restructure)

## Next session reminder

- [ ] **Deploy feedback endpoint to Dreamhost** — `server/feedback.php` is written and ready. See `server/README.md` for full deployment steps. Then flip `BRISTLENOSE_FEEDBACK` to `true` in `render_html.py` and set the URL. Also: split "Report a bug" link out of the feature flag so it's always visible

---

## Task tracking

**GitHub Issues is the source of truth for actionable tasks:** https://github.com/cassiocassio/bristlenose/issues

This file contains: session reminders, feature groupings with context, items too small for issues, architecture notes, dependency maintenance, and completed work history.

### Priority order

1. **Moderator Phase 2** (#25) — cross-session linking
2. **Dark mode selection highlight** (#52) — visibility bug
3. **SVG icon set** — replace fragile × character glyphs (no issue — small enough to just do)
4. Export & sharing — design doc at `docs/design-export-sharing.md`
5. **Reactive UI architecture** (#29) — design doc at `docs/design-reactive-ui.md`

---

## Feature roadmap by area

### Report UI

| Item | Issue | Effort |
|------|-------|--------|
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
| Multi-page report (tabs or linked pages) | #51 | large |
| Project setup UI for new projects | #49 | large |

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

### Pipeline and analysis

| Item | Issue | Effort |
|------|-------|--------|
| Moderator Phase 2: cross-session linking | #25 | medium |
| Speaker diarisation improvements | #26 | medium |
| Batch processing dashboard | #27 | medium |

### CLI

| Item | Issue | Effort |
|------|-------|--------|
| Time estimate warning for long jobs | #39 | trivial |
| Britannification pass | #40 | trivial |
| `--prefetch-model` flag for Whisper | #41 | trivial |

### Packaging

| Item | Issue | Effort |
|------|-------|--------|
| Homebrew formula: post_install for spaCy model | #42 | trivial |
| Snap store publishing | #45 | small |
| Windows installer (winget) | #44 | medium |

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

### Internal refactoring

| Item | Issue | Effort |
|------|-------|--------|
| Platform detection refactor: shared `utils/system.py` | #43 | small |

### Reactive UI migration

See `docs/design-reactive-ui.md` for framework comparison, risk assessment, and migration plan.

Tracked as issue #29 (large effort).

---

## Items only tracked here (not in issues)

These are too small for issues or are internal-only concerns.

- [ ] **SVG icon set** — replace all × character glyphs (delete circles, modal close, search clear) with SVG icons. Candidates: Lucide, Heroicons, Phosphor, Tabler. See `docs/design-system/icon-catalog.html` for current inventory
- [ ] **Relocate AI tag toggle** — removed from toolbar (too crowded with Codebook button); needs a new home. Code commented out in `render_html.py` and `codebook.js`/`tags.js`
- [ ] **Feedback endpoint** — deploy `server/feedback.php` to Dreamhost. See `server/README.md`
- [ ] **User research panel opt-in** — optional email field in feedback modal
- [ ] **Export and sharing Phases 0–5** — see `docs/design-export-sharing.md`
- [ ] **Tag definitions page** — also tracked as #53
- [ ] **Custom prompts** — user-defined tag categories via `bristlenose.toml` or `prompts.toml`
- [ ] **Pass transcript data to renderer** — avoid redundant disk I/O in `render_html.py`

### Theme refactoring opportunities

Low-priority improvements to pick up when working in these areas — not blockers.

- [ ] **Tag-count aggregation (3 implementations)** — `histogram.js`, `tag-filter.js`, `codebook.js` each count user tags independently. Shared `countUserTags()` would eliminate duplication
- [ ] **Shared user-tags data layer** — `tags.js` owns the map; `codebook.js` reads storage directly. Extract shared `userTagStore` if write access needed from codebook
- [ ] **isEditing() guard deduplication** — `editing.js` + `names.js` have separate booleans. Shared `EditGuard` class when a third editing context is added
- [ ] **Inline edit commit pattern** — `codebook.js`, `editing.js`, `names.js` repeat: create input, focus, wire blur/Enter/Escape with committed flag. Shared `inlineEdit()` helper (~6 repetitions)
- [ ] **Close button CSS base class** — `.bn-modal-close`, `.group-close`, `.histogram-bar-delete`, `.badge-delete` share the same pattern. Extract `.close-btn` atom
- [ ] **Input focus CSS base class** — `.group-title-input`, `.tag-add-input`, `.search-input` share: inherit font, border, radius, accent focus. Extract `.bn-input` atom

### file:// → http:// migration prep (cheap, prevents debt)

These can be done now, independently of the reactive UI migration.

- [ ] Namespace localStorage keys by project slug (prevents multi-report collision)
- [ ] Tighten `postMessage` origin from `'*'` to same-origin
- [ ] Inject `BRISTLENOSE_CODEBOOK_URL` as configurable global (like `BRISTLENOSE_PLAYER_URL`)

---

## Dependency maintenance

Bristlenose has ~30 direct + transitive deps across Python, ML, LLM SDKs, and NLP. CI runs `pip-audit` on every push (informational, non-blocking).

### Quarterly dep review (next: May 2026, then Aug 2026, Nov 2026)

- [ ] **May 2026** — Run `pip list --outdated` in the venv. Bump floor pins in `pyproject.toml` only if there's a security fix, a feature you need, or the floor is 2+ major versions behind. Run tests, commit
- [ ] **Aug 2026** — Same as above
- [ ] **Nov 2026** — Same as above

### Annual review (next: Feb 2027)

- [ ] **Feb 2027** — Full annual review:
  - Check Python EOL dates — Python 3.10 EOL is Oct 2026; if past EOL, bump `requires-python`, `target-version` (ruff), `python_version` (mypy)
  - Check faster-whisper / ctranslate2 project health — is ctranslate2 still maintained? If dormant, evaluate `whisper.cpp` bindings or `mlx-whisper` as default
  - Check spaCy major version — if spaCy 4.x is out, plan coordinated upgrade of spacy + thinc + models (only affects PII/presidio)
  - Check Pydantic major version — if Pydantic 3.x is out, assess migration scope
  - Rebuild snap to pick up fresh transitive deps
  - Review `pip-audit` CI output for any persistent unfixed CVEs; decide if workarounds needed

### Risk register

| Dependency | Risk | Why | Escape hatch |
|---|---|---|---|
| faster-whisper / ctranslate2 | High | Fragile chain, ctranslate2 ties to specific torch versions, maintenance activity varies | `mlx-whisper` (macOS), `whisper.cpp` Python bindings |
| spaCy + thinc + presidio | Medium | spaCy 3.x pins thinc 8.x; a spaCy 4.x release forces coordinated upgrade | Contained to PII stage only; can pin spaCy 3.x indefinitely |
| anthropic / openai SDKs | Low | Bump weekly, backward-compatible within major versions | Floor pins are fine; no action needed |
| Pydantic | Low | Stable at 2.x; no 3.x imminent | Would be a large migration but not urgent |
| Python itself | Low (now) | 3.10 EOL Oct 2026; running 3.12 | Bump floor when 3.10 reaches EOL |
| protobuf (transitive) | Low | CVE-2026-0994 (DoS via nested Any); no fix version yet; we don't parse untrusted protobuf | Resolves when patched version ships |

---

## Key files to know

| File | What it does |
|------|-------------|
| `pyproject.toml` | Package metadata, deps, tool config (version is dynamic — read from `__init__.py`) |
| `bristlenose/__init__.py` | **Single source of truth for version** (`__version__`); the only file to edit when releasing |
| `bristlenose/cli.py` | Typer CLI entry point (`run`, `transcribe`, `analyze`, `render`, `doctor`) |
| `bristlenose/config.py` | Pydantic settings (env vars, .env, bristlenose.toml) |
| `bristlenose/pipeline.py` | Pipeline orchestrator (full run, transcribe-only, analyze-only, render-only) |
| `bristlenose/people.py` | People file: load, compute stats, merge, write, display name map |
| `bristlenose/stages/render_html.py` | HTML report renderer — loads CSS + JS from theme/, all interactive features |
| `bristlenose/theme/` | Atomic CSS design system (tokens, atoms, molecules, organisms, templates) |
| `bristlenose/theme/js/` | Report JavaScript modules — concatenated at render time |
| `bristlenose/llm/prompts.py` | LLM prompt templates |
| `bristlenose/utils/hardware.py` | GPU/CPU auto-detection |
| `bristlenose/doctor.py` | Doctor check logic (pure, no UI) — 7 checks, `run_all()`, `run_preflight()` |
| `bristlenose/doctor_fixes.py` | Install-method-aware fix instructions |
| `.github/workflows/ci.yml` | CI: ruff, mypy, pytest on push/PR |
| `.github/workflows/release.yml` | Release pipeline: build → PyPI → GitHub Release → Homebrew dispatch |
| `.github/workflows/snap.yml` | Snap build & publish |
| `snap/snapcraft.yaml` | Snap recipe: classic confinement, core24, Python plugin |
| `CONTRIBUTING.md` | CLA, code style, design system docs, full release process |

## Key URLs

- **Repo:** https://github.com/cassiocassio/bristlenose
- **Issues:** https://github.com/cassiocassio/bristlenose/issues
- **PyPI:** https://pypi.org/project/bristlenose/
- **Homebrew tap repo:** https://github.com/cassiocassio/homebrew-bristlenose
- **CI runs:** https://github.com/cassiocassio/bristlenose/actions
- **Tap workflow runs:** https://github.com/cassiocassio/homebrew-bristlenose/actions
- **PyPI trusted publisher settings:** https://pypi.org/manage/project/bristlenose/settings/publishing/
- **Repo secrets:** https://github.com/cassiocassio/bristlenose/settings/secrets/actions

---

## Design docs

| Document | Covers |
|----------|--------|
| `docs/design-reactive-ui.md` | Framework comparison, risk assessment, migration audit, server options |
| `docs/design-llm-providers.md` | Provider roadmap, phase status, Gemini/docs next steps |
| `docs/design-performance.md` | Performance audit, done/open/not-worth-optimising |
| `docs/design-export-sharing.md` | Export and sharing phases 0–5 |
| `docs/design-cli-improvements.md` | CLI warts, fixes, LLM provider implementation records |
| `docs/design-html-report.md` | HTML report, people file, transcript pages |
| `docs/design-doctor-and-snap.md` | Doctor command, snap packaging |
| `docs/design-research-methodology.md` | Quote selection, sentiment taxonomy, clustering rationale |
| `docs/design-platform-transcripts.md` | Platform transcript ingestion |
| `docs/design-transcript-coverage.md` | Transcript coverage feature |
| `docs/design-codebook.md` | Codebook editor |
| `docs/design-keychain.md` | Keychain credential storage |
| `docs/design-keyboard-navigation.md` | Keyboard shortcuts |

---

## Done

### CI/CD automation

All done. `.github/workflows/ci.yml` (ruff + pytest hard gates, mypy informational), `.github/workflows/release.yml` (build → PyPI trusted publishing → GitHub Release → Homebrew tap dispatch), `.github/workflows/snap.yml`.

### Secrets management

All done. GitHub token (Keychain via `gh auth`), PyPI (Trusted Publishing/OIDC), `HOMEBREW_TAP_TOKEN` (classic PAT, GitHub Actions secret), Bristlenose API keys (`bristlenose configure`, keychain → env var → .env fallback).

### CLI improvements (Feb 2026)

- [x] `analyse` alias (British English convenience)
- [x] `transcribe` is now primary (renamed from `transcribe-only`)
- [x] `render` argument fix (auto-detects output dir)
- [x] Command reordering (workflow order in help)
- [x] `--llm claude/chatgpt` aliases
- [x] File-level progress ("Transcribing... 2/5 files")

Backward compat policy: don't worry until v1.0.0.

### LLM providers (Phases 1–4)

- [x] Phase 1: Ollama — interactive first-run, auto-install, auto-start, model auto-pull, retry logic, doctor integration
- [x] Phase 2: Azure OpenAI — registry, credentials, doctor validation
- [x] Phase 3: Keychain integration — `bristlenose configure`, native CLI tools, credential fallback chain
- [x] Phase 4: Gemini (#37) — budget option (~$0.20/study), native JSON schema, schema flattening, doctor integration, provider docs (#38)

### Features (reverse chronological)

- [x] **Hidden quotes + Codebook** — hide with `h` key, per-subsection badge with dropdown previews; standalone codebook page with drag-drop tag organisation, colour-coded badges, group CRUD; toolbar redesign
- [x] **Multi-select** — Finder-like selection (plain click, Cmd+click toggle, Shift+click range), bulk star/tag
- [x] **Keyboard shortcuts** — j/k navigation, s to star, t to tag, / to search, ? for help overlay
- [x] **Search-as-you-type** — collapsible search in toolbar, filters quotes by text/speaker/tags
- [x] **Tag taxonomy redesign** — 7 research-backed sentiments replacing 14 overlapping categories
- [x] **Multi-participant sessions** — session_id decoupling, global participant numbering, sessions table
- [x] **Moderator identification Phase 1** — per-session speaker codes, `.segment-moderator` CSS
- [x] **LLM name/role extraction** — extends Stage 5b, `SpeakerInfo` dataclass, auto-populate
- [x] **Editable names in report** — pencil icon, localStorage, YAML export, reconciliation
- [x] **Editable section/theme headings** — inline editing with ToC sync
- [x] **Platform-aware session grouping** — Teams/Zoom/Meet normalisation, 37 tests
- [x] **CLI output overhaul** — Cargo-style checkmarks, per-stage timing, LLM cost estimate
- [x] **Per-participant transcript pages** — deep-linked timecodes, speaker name resolution
- [x] **Dark mode** — CSS `light-dark()`, OS preference, config override, print forced light
- [x] **People file** — `people.yaml` with merge strategy, display names, 21 tests
- [x] **Concurrent LLM + FFmpeg** — `asyncio.Semaphore` + `asyncio.gather()`, VideoToolbox decode
- [x] **View-switcher + Copy CSV** — borderless dropdown, adaptive export button
- [x] **Timecode two-tone typography** — blue digits, muted brackets, hanging-indent layout
- [x] **Header redesign** — logo top-left, logotype, right-aligned meta
- [x] **Analysis ToC column** — Sentiment, Tags, Friction, Journeys in own nav
- [x] Full 12-stage pipeline (ingest → render)
- [x] HTML report with CSS theme, clickable timecodes, popout video player
- [x] Sentiment histogram, friction points, user journeys
- [x] Favourite quotes (star, reorder, FLIP animation, CSV export)
- [x] Inline quote editing (contenteditable, localStorage persistence)
- [x] Tag system (AI badges + user tags, auto-suggest, CSV export)
- [x] Atomic design system (`bristlenose/theme/`)
- [x] JavaScript extraction (17 modules, concatenated at render time)
- [x] `bristlenose render` command
- [x] Apple Silicon GPU acceleration (MLX)
- [x] PII redaction (Presidio, default off)
- [x] Cross-platform support (macOS, Linux, Windows)
- [x] Published to PyPI, GitHub, Homebrew tap
- [x] Snap packaging (classic confinement, CI builds)
- [x] Man page (self-installs, CI version check)
- [x] `bristlenose doctor` (7 checks, pre-flight gate, first-run auto-doctor)
- [x] Markdown style template (`utils/markdown.py`)
- [x] Short name suggestion heuristic
- [x] Participant table redesign (Finder-style dates)

### Implementation notes

#### Name extraction and editable names

Extends Stage 5b (no extra LLM call). LLM extraction → metadata harvesting → auto-populate empty fields → short name suggestion → browser editing (localStorage + YAML clipboard export). Human edits always win.

Key files: `identify_speakers.py`, `people.py`, `names.js`. Data flow: pipeline → auto-populate → write people.yaml → bake into HTML → browser edits → export YAML → paste → re-render → reconcile.

#### Moderator identification (Phase 1)

Per-session speaker codes (`[m1]`/`[p1]`/`[o1]`). Stage 5b heuristic + LLM → `assign_speaker_codes()` → transcript write → parser → people.yaml → transcript pages with `.segment-moderator` CSS.

Key decisions: `m` prefix (not `r`); moderator text muted; per-session codes (Phase 2 links them). Tests: `tests/test_moderator_identification.py` (21 tests).

Phase 2 design (issue #25): `same_as` field, auto-linking signals, web UI, aggregated stats.
