# Bristlenose — Where I Left Off

Last updated: 15 Apr 2026

**Launch plan:** `docs/private/100days.md` — triaged by topic + MoSCoW priority. That's the source of truth for what ships. This file is a public capture inbox + session context + done history.

---

## Desktop app security (must-fix before any distribution)

From security review of desktop app plan (22 Mar 2026). All findings are in the serve-side and process management layer, not the Swift bridge code (which is clean).

- [x] **Localhost auth token** — bearer token middleware, per-session `secrets.token_urlsafe(32)`, validated on `/api/*` + `/media/*`. Injected into HTML (`json.dumps`) + WKUserScript (regex-validated). Design: `docs/design-localhost-auth.md`
- [x] **Media endpoint filtering** — extension allowlist + path-traversal guard on `/media/` route. Also requires auth token
- [x] **CORS middleware** — `CORSMiddleware(allow_origins=[])` blocks all cross-origin requests
- [x] **Don't bundle API key in binary** — verified clean: no hardcoded keys in Swift source, Keychain-only storage, user enters via Settings
- [x] **Skip zombie cleanup when BRISTLENOSE_DEV_PORT is set** — `killOrphanedServeProcesses()` now skips when dev port override is active, so the terminal dev server isn't killed on Xcode launch
- [x] **Minimal child process environment** — stripped to PATH, HOME, TMPDIR, USER, SHELL, locale, VIRTUAL_ENV + BRISTLENOSE_* overlay in `ServeManager.overlayPreferences()`

Remaining security items tracked in `docs/private/100days.md` §6 Risk.

## Desktop app — shipped this session

- [x] **Video player popout (WKUIDelegate)** — `window.open()` now creates a native NSWindow with WKWebView for player.html. Dynamic title (`s1 — Bristlenose`), `setFrameAutosaveName` for position persistence, single-popout guard, `webViewDidClose` cleanup
- [x] **12 video menu actions wired** — playPause, skip±5/±30, speed up/down/normal, volume up/down/mute, PiP, fullscreen. `sendCommand` on PlayerContext → `bristlenose-command` postMessage → player.html
- [x] **Bridge player state** — `getState()` reports live `hasPlayer`/`playerPlaying` for Video menu dimming. `postPlayerState` notifies Swift on open/close/play/pause
- [x] **Security hardening** — origin validation on postMessage (both directions), payload namespacing, float rounding on speed/volume steps, no-video guard
- [x] **BroadcastChannel fallback** — defence-in-depth for glow sync if `window.opener` is nil in WKWebView popouts
- [x] **a11y announce** — `announce("Playing pid")` on seekTo for VoiceOver

## Desktop app — bugs found

- [x] **Native toolbar tabs don't navigate** — fixed: stale `navigate` closure in `installNavigationShims`. Module-level refs instead of direct closure capture. Also added `makeFirstResponder(webView)` after tab switch for keyboard focus
- [x] **i18n: extract ~200 hardcoded frontend strings** — done (24 Mar 2026). ~30 components wired with `useTranslation()`. Sentiment badges translate via `enums.json`. `format.ts` uses `Intl.DateTimeFormat`. `<html lang>` tracks locale. Screen reader `announce()` calls use `i18n.t()`. Keys in all 5 locale files (en/es/fr/de/ko)
- [x] **i18n: help prose + shortcuts (Batch 11)** — HelpSection and ShortcutsSection wired to `t()` with `help.guide.*` and `help.shortcuts.*` keys (24 Mar 2026). SignalsSection, CodebookSection, ContributingSection also wired (24 Mar). AboutSection, DeveloperSection, DesignSection remain hardcoded English — deferred as "Could" in 100days.md
- [x] **i18n: Weblate setup** — connect `hosted.weblate.org` to repo for community translation. Free Libre plan. See `docs/design-i18n.md`

Remaining desktop bugs and i18n items tracked in `docs/private/100days.md` §2, §7, §8.

## Desktop app — multi-project sidebar Phase 1 (26 Mar 2026)

- [x] **ProjectIndex model** — `projects.json` in `~/Library/Application Support/Bristlenose/`. CRUD with unique name enforcement (appends " 2", " 3"). New projects insert at top
- [x] **ProjectRow with inline rename** — `doc.text` icon, slow-double-click rename (0.3–1.0s), `simultaneousGesture` so List selection isn't swallowed. Commit on Return, cancel on Escape
- [x] **Sidebar layout** — "Projects" section header, `+ New Project…` row at top of list, `folder.badge.plus` button in sidebar title bar (disabled, Phase 3 placeholder). Selection by UUID (not value type) survives project mutations
- [x] **Project menu rewired** — Show in Finder (native `NSWorkspace`), Rename/Delete via notifications. Re-Analyse/Archive disabled (future). File > New Project (Cmd+N) posts notification
- [x] **BridgeHandler.selectedProjectPath** — published property for menu disable guards, reset on project switch

- [x] **Phase 3: Folders** — `FolderRow.swift`, `Folder` model with CRUD, `folderId` on Project, `SidebarSelection` enum, `DisclosureGroup` collapse, "Move to" submenu, adaptive Project menu, File > New Folder (⇧⌘N), `folder.badge.plus` enabled, collapsed state persistence, locale keys in all 6 languages

Remaining multi-project phases tracked in `docs/design-project-sidebar.md` (Phases 4–5: bookmarks/availability, archive/bin).

## CI hardening — sprint 1 (15 Apr 2026)

- [x] **pytest coverage in CI** — `--cov` flags on pytest, coverage XML uploaded as artifact, `[tool.coverage]` config in `pyproject.toml`. Baseline: 73% (11,116 statements). No `fail_under` yet — informational
- [x] **macOS CI matrix** — `ubuntu-latest` + `macos-latest` (informational, `continue-on-error`). Catches platform-specific bugs without blocking merges
- [x] **GZip middleware** — `GZipMiddleware(minimum_size=500)` on FastAPI app. Media routes set `Content-Encoding: identity` to prevent re-compression of video/audio
- [x] **Frontend bundle size gate** — `size-limit` (300 kB gzipped JS), `npm run size` / `npm run size:why`, runs in CI after frontend build

## PII redaction audit (26 Mar 2026)

- [x] **Bug: Word objects not cleared after redaction** — `model_copy()` replaced `seg.text` but `seg.words` still contained original PII. Fixed in `s07_pii_removal.py`
- [x] **Bug: `pii_summary.txt` was a re-identification key in shareable output** — moved to `.bristlenose/` hidden directory with CONFIDENTIAL header
- [x] **Bug: `__repr__` leaked original PII into logs** — now shows `<N chars>` instead
- [x] **Bug: `UK_NHS` in entity map but not in `_DEFAULT_ENTITIES`** — one-line fix
- [x] **Config: `pii_score_threshold`** — configurable via `BRISTLENOSE_PII_SCORE_THRESHOLD` (0.0–1.0, default 0.7). Wired into `_redact_text()`
- [x] **Runtime warnings for dead config fields** — `pii_llm_pass` and `pii_custom_names` warn when set but not implemented
- [x] **Horror-show test transcript** — fictional adversarial interview with 70+ planted PII items across 8 categories. `tests/fixtures/pii_horror_transcript.txt` + `pii_horror_expected.yaml`
- [x] **PII audit test suite** — `tests/test_pii_audit.py` — 12 CI-safe tests + 70 parametrised Presidio detection tests (`@pytest.mark.slow`)
- [x] **Privacy help section** — new "Privacy" section in HelpModal (between Codebook and About). 3 subsections: where data goes, PII redaction limits, what to do. Links to published audit artifacts on GitHub. All 5 locales
- [x] **SECURITY.md overhaul** — PII section expanded with catches/misses/cannot-detect subsections, speaker ID timing, audit trail location
- [x] **PII audit artifacts** — `docs/pii-audit/` with README, redacted transcript, and summary log. Linked from help panel

Remaining PII work tracked in `docs/private/100days.md` §4 Value (PII dashboard widget) and §6 Risk.

---

## Task tracking

**GitHub Issues is the source of truth for actionable tasks:** https://github.com/cassiocassio/bristlenose/issues

**Launch plan:** `docs/private/100days.md` — triaged by topic and MoSCoW priority.

This file contains: session reminders, done history, dependency maintenance, and reference tables.

---

## Dependency maintenance

Bristlenose has ~30 direct + transitive deps across Python, ML, LLM SDKs, and NLP. CI runs `pip-audit` + `npm audit` on every push (informational, non-blocking). Dependabot opens weekly PRs for both ecosystems. CodeQL SAST runs on push + weekly. See `SECURITY.md` for remediation SLA.

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
| `bristlenose/stages/s12_render/` | HTML report renderer package |
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

## Design docs

| Document | Covers |
|----------|--------|
| `docs/design-reactive-ui.md` | Framework comparison, risk assessment (partially superseded by React migration) |
| `docs/design-react-migration.md` | **React migration plan** (Steps 1–10, all complete) |
| `docs/design-react-component-library.md` | 16-primitive component library (complete) |
| `docs/design-llm-providers.md` | Provider roadmap |
| `docs/design-performance.md` | Performance audit |
| `docs/design-export-sharing.md` | Export and sharing phases 0–5 (**superseded** — see 4 feature docs below) |
| `docs/design-export-slides.md` | Export dropdown (scope→format), per-quote copy icon, PowerPoint quote slides |
| `docs/design-export-quotes.md` | CSV + XLS spreadsheet export (11-column table) |
| `docs/design-export-clips.md` | Video clip extraction via FFmpeg |
| `docs/design-export-html.md` | Self-contained HTML export + cross-cutting export concerns |
| `docs/design-miro-bridge.md` | Miro API integration (OAuth, board creation, layout — post-beta) |
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
| `docs/design-windows-ci.md` | Windows CI strategy, compatibility audit, phased plan |

---

## Done (reverse chronological)

- [x] **Platform text forking** (Mar 2026) — `dt()`/`ct()` helpers in `platformTranslation.ts` for CLI vs desktop help text. Desktop namespace loaded conditionally in i18next. 4 keys forked (privacy PII, contributing, config reference). Desktop variants in all 6 locales. Terminology glossary (`docs/glossary.md`) and platform text map (`docs/platform-text-map.md`) as foundation docs for future docs-review agent. SECURITY.md desktop callout added.
- [x] **Export security + design docs** (Mar 2026) — XSS fix (`ensure_ascii=True`), `safe_filename()` utility (21 tests), path stripping from exports, anonymise label clarity (5 locales). Split `design-export-sharing.md` monolith into 4 focused design docs: HTML, quotes, clips, Miro. Cross-cutting concerns (anonymisation matrix, shared infrastructure, audit logging) documented in `design-export-html.md`
- [x] **Pipeline resilience Phase 2b** (Mar 2026) — verify content hashes on load, manifest invalidation on mismatch, lazy LLM client init
- [x] **Frontend deps bump** (Mar 2026) — Vite 8, TypeScript 6, ESLint 10, Vitest 4
- [x] **Bearer token auth** (Mar 2026) — localhost bearer token for serve mode API access control
- [x] **Export: video clip extraction** (Mar 2026) — FFmpeg stream-copy clips from starred + featured quotes. Human-readable filenames, adjacent merge, async progress toast, `clips_manifest.json` audit trail. `ClipBackend` Protocol for future AVFoundation backend. 64 new tests. Also fixed: `safe_filename()` `..` reassembly, `/media/` auth exemption, `PlayerContext`/`Minimap` raw fetch 401s
- [x] **Security scanning** (Mar 2026) — npm audit, CodeQL, Dependabot, gitleaks, SBOM
- [x] **Unified i18n architecture** (Mar 2026) — single source of truth (`bristlenose/locales/`), desktop `I18n.swift`, bridge locale sync, startup flash prevention, Weblate plan, Apple glossary cross-check process. See `docs/design-i18n.md`
- [x] **Help modal** (Mar 2026) — 3 phases: platform-aware shortcuts, typography tokens, entrance animation, custom tooltips with keyboard shortcut badges
- [x] **Bulk actions on multi-selection** (Mar 2026) — star, hide, tag respect click + shift+click range selection
- [x] **Sidebar push animation** (Mar 2026) — drag-open pushes content; keyboard shortcuts and click trigger push animation
- [x] **CI hardening sprint 1** (Apr 2026) — pytest coverage (73% baseline), macOS CI matrix, GZip middleware, bundle size gate
- [x] **Pipeline error/warning display** (Mar 2026) — red ✗ for failed stages, yellow ⚠ for partial success
- [x] **Render refactor** (Mar 2026) — `render_html.py` broken into `bristlenose/stages/s12_render/` package (8 submodules). Static render formally deprecated
- [x] **Numeric stage prefixes** (Mar 2026) — `bristlenose/stages/*.py` → `s01_ingest.py` … `s12_render/`
- [x] **Sidebar architecture** (Mar 2026) — 6-column grid, TOC + tag sidebars, rail drag-to-open, minimap, scroll spy, eye toggle, keyboard shortcuts
- [x] **Heading anchor scroll fix** (Mar 2026) — `scroll-margin-top` for section headings in React SPA
- [x] **Tag provenance** (Mar 2026) — `QuoteTag.source` column: `"human"` vs `"autocode"`, preserved across bulk replace
- [x] **Playwright E2E harness layers 1–3** (Mar 2026) — console error monitor, link crawler, network assertion. Chromium + WebKit
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
