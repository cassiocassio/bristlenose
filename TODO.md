# Bristlenose — Where I Left Off

Last updated: 19 May 2026 (`pipeline-diagnostic-popover-swift` Swift half shipped on branch — Mac diagnostic popover surfaces partial / abandoned runs with per-bucket SF Symbol failures, dominant-category pill, plaintext-portable Copy, debug fixture harness. Trued spec doc + review log, four review passes, all 45 findings closed/parked/ignored. Build clean, 2754 tests passing, ruff clean. Twelve forward-looking plan files under founder-private handoffs for next iterations — Plan A (terminus per-stage summaries), Live progress Phases 1+2, pill visibility discussion, schema-v6 rides, verbose mode stretch. **Pre-existing leak found:** `bristlenose/cli.py:857` prints "Pipeline failed." — user-facing convention is "Analysis" not "Pipeline" (now documented in `docs/design-pipeline-diagnostic-popover.md` §"User-facing vocabulary"). Worth a small sweep when convenient.)

**Most recent ship: v0.15.10 (17 May 2026)** — C1 codebook plumbing (`--codebook=<slug>` + `bristlenose codebooks` subcommand) and smoke-fixture `RunCompletedEvent` so e2e perf-gate stops timing out on `#bn-app-root`. **Caveat:** PyPI is still at 0.15.3 as of 19 May — seven tag pushes since 10 May haven't reached users; `ci/perf-gate` failed on every release workflow run in that span. CI fix in flight, release attempt expected tonight (19 May). v0.15.8/9 carry the substantive work — honesty everywhere (A3 + A4 + B1), multi-project Phases 0–3, sidebar honesty wave 2, HIG corpus, Keychain biometric ACL, folder watcher, AppleDouble skip. See `CHANGELOG.md` for full bullet list.

**Launch plan:** `docs/private/100days.md` — triaged by topic + MoSCoW priority. That's the source of truth for what ships. This file is a public capture inbox + session context + done history.

---

## Next session focus

**S3 (12–23 May) is the active sprint.** Gate has shifted (7 May quality reset): Internal TF is gated on **walks-fix-walks** — 2–3 consecutive end-to-end walks across different scenarios producing zero new snags — not on a checklist. Mission Sandbox PASSED 4 May; Track B + S6 framing is superseded.

Pick up from `docs/private/100days.md` §Critical Path. Within-sprint candidates: D1 stage-contract audit (unblocked by A4 + B1); remaining sandbox exports (clips / CSV / slides / anonymised bundle); C-stream UX papercuts; continue walks 5–8 from §1. **Release-pipeline-to-PyPI is the surprise S3 risk** — six tags behind users; CI patch landing tonight.

Open follow-ups not in any active branch (surface separately, not alpha blockers):
- **Sidebar drag-and-drop polish chips** (14 May 2026, gruber pass on commit `fce69e4`) — two small UX/correctness items deferred after the `.dropDestination` refactor. The bullets are mechanically linked — fixing (2) closes (1) cleanly: (1) **Folder row should accept Finder URL drops directly** — currently a Finder folder dropped onto a `FolderRow` bubbles up to the List's URL drop and creates a top-level project, ignoring the folder under the cursor (verified in code 19 May 2026: `ContentView.swift:1508` accepts `String.self` only). Either consume silently or, better, create the project *inside* the folder (requires threading `intoFolder: UUID?` through `processDroppedURLs` / `addProject`; current signature at `ProjectIndex.swift:329` has no `intoFolder` param). Gap V1 design doc explicitly left open — `design-sidebar-drop-behaviour.md` types `sidebarFolder(folderID)` as a target but its action table has no row for Finder content × sidebar folder. Real UX bug — visible. (2) **Replace String-typed internal-project payload with a custom `Transferable` newtype** — `.draggable(project.id.uuidString)` (`ContentView.swift:1568`) + `.dropDestination(for: String.self)` (`ContentView.swift:1508`) works but is type-weak; a `ProjectDragID: Codable, Transferable` with a custom UTType (`app.bristlenose.project-id`) would be the idiomatic version and would also close the snag in (1) by making the folder row's two drop types non-overlapping. _Drop-affordance VoiceOver moved to 100days §14 beta-Must (S6) 19 May 2026._

Reference: `docs/private/handoffs/sandbox-walk-followup-fixes.md` (closeout), `docs/private/sandbox-inventory-beats-6-13.md` (16-finding inventory + status block).

### A3 cli-honest-output follow-ups (parked, see review log)

Status: A3 landed on `main` 14 May 2026 as commits `dc71073` (code+tests+Swift), `607202d` (user-facing docs), `04dcdd6` (design-doc sweep). Review log: `docs/private/reviews/cli-improvements.md` — 30 findings, 15 resolved / 7 parked / 8 ignored.

Parked items most likely to resurface during cohort calls (in priority order):
- **Failure-banner copy in manual.md** (Finding 22) — new banners aren't documented anywhere user-readable. Manual.html is the natural Google landing for "bristlenose claude api key invalid". 3–5 bullet "When things go wrong" section. Pairs with Finding 25 (doctor positioning) and Finding 24 (run/serve mental-model one-liner).
- **AUTH suffix edge cases** (Finding 14) — `(no key set)` / `(key too short)` alternate diagnostic when key is missing/typo'd. Surfaces if a tester hits "rejected" with no suffix and asks why.
- **Abandon-path verbosity** (Finding 7, parked Chesterton) — surface partial-run stats on mid-run DISK / MISSING_BINARY via a `--verbose` flag on `run` if cohort asks.

### cli-just-works follow-ups (deferred from cli-just-works branch — see Decisions block at `.claude/plans/cli-just-works.md`)

- **No-account-yet flow** — numbered URL → getpass → optional Keychain persist → re-enter validation. Existing `_maybe_prompt_for_provider` covers the simpler "missing-key → prompt" case; full-numbered flow defers to a follow-up branch. Spec lives in the Decisions block.
- **`pipeline-events.jsonl` `Cause` entries on preflight aborts** (finding 12 in design doc) — currently aborts go through `typer.Exit(2)` with the recovery message; threading the event writer through the preflight modules is its own small refactor.
- **Verify quarterly-drift cron `trig_01BtVXKG5hBnhPF4bGwR78CR` is armed** against current `billing_hints.py` URLs/minimums. Verification task, not code.
- **Translation review** for `bristlenose/locales/{es,fr,de,ko,ja}/preflight.json` — currently English mirrors. Picks up the parked product-polish text rewrites (Findings 12, 13, 14, 45, 49 in the review log) at the same time so translators see the final English shape once, not twice.

---

## Desktop app security (must-fix before any distribution)

From security review of desktop app plan (22 Mar 2026). All findings are in the serve-side and process management layer, not the Swift bridge code (which is clean).

- [x] **Localhost auth token** — bearer token middleware, per-session `secrets.token_urlsafe(32)`, validated on `/api/*` + `/media/*`. Injected into HTML (`json.dumps`) + WKUserScript (regex-validated). Design: `docs/design-localhost-auth.md`
- [x] **Media endpoint filtering** — extension allowlist + path-traversal guard on `/media/` route. Also requires auth token
- [x] **CORS middleware** — `CORSMiddleware(allow_origins=[])` blocks all cross-origin requests
- [x] **Don't bundle API key in binary** — verified clean: no hardcoded keys in Swift source, Keychain-only storage, user enters via Settings
- [x] **Skip zombie cleanup when dev port override is set** — `killOrphanedServeProcesses()` now skips when the external-server env var is active, so the terminal dev server isn't killed on Xcode launch. (Env var renamed from `BRISTLENOSE_DEV_PORT` to `BRISTLENOSE_DEV_EXTERNAL_PORT` in Track C C1.)
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
- [→] **i18n: Settings second-pane sweep + menu-bar audit** — folded 8 May 2026 into `docs/private/100days.md` §2 Should as a single [Beta-must] entry covering all three (LLM detail pane / Transcription pane / menu-bar audit). Full file:line context preserved in 100days entry. Removed from TODO.md per "antechamber not duplicate" rule.

Remaining desktop bugs and i18n items tracked in `docs/private/100days.md` §2, §7, §8.

## Desktop app — multi-project sidebar Phase 1 (26 Mar 2026)

- [x] **ProjectIndex model** — `projects.json` in `~/Library/Application Support/Bristlenose/`. CRUD with unique name enforcement (appends " 2", " 3"). New projects insert at top
- [x] **ProjectRow with inline rename** — `doc.text` icon, slow-double-click rename (0.3–1.0s), `simultaneousGesture` so List selection isn't swallowed. Commit on Return, cancel on Escape
- [x] **Sidebar layout** — "Projects" section header, `+ New Project…` row at top of list, `folder.badge.plus` button in sidebar title bar (disabled, Phase 3 placeholder). Selection by UUID (not value type) survives project mutations
- [x] **Project menu rewired** — Show in Finder (native `NSWorkspace`), Rename/Delete via notifications. Re-Analyse/Archive disabled (future). File > New Project (Cmd+N) posts notification
- [x] **BridgeHandler.selectedProjectPath** — published property for menu disable guards, reset on project switch

- [x] **Phase 3: Folders** — `FolderRow.swift`, `Folder` model with CRUD, `folderId` on Project, `SidebarSelection` enum, `DisclosureGroup` collapse, "Move to" submenu, adaptive Project menu, File > New Folder (⇧⌘N), `folder.badge.plus` enabled, collapsed state persistence, locale keys in all 6 languages

Remaining multi-project work tracked in `.claude/plans/tf-multi-project.md` (Phase 0 + Phase 1 shipped 14 May 2026; Phase 2 sidecar-restart switch (#1/#2/#3) shipped 14 May 2026 on `multi-project-switch`; Phase 2 #11 drag-onto-existing shipped 15 May 2026 on `multi-project-drag-onto`; Phase 2 #14 folder watcher still open; Phase 3 cloud-evicted post-cohort). Original 5-phase plan in `docs/design-project-sidebar.md` is superseded for TF scope.

## CI hardening — sprint 2 step 0 (18 Apr 2026, ci-cleanup branch)

- [x] **Flip e2e gate to blocking** — removed `continue-on-error: true` from `.github/workflows/ci.yml`. First CI run post-flip passed green (19m44s). The three P3 regressions parked during v0.14.5 release-unblock are cleared: autocode status 404 allowlisted (REST-correct), codebook route 404 allowlisted as deferred-fix (root cause S3), `_BRISTLENOSE_AUTH_TOKEN=test-token` wired into the main e2e workflow
- [x] **`e2e/ALLOWLIST.md` register** — every deliberate e2e-spec suppression now has a categorised entry + `// ci-allowlist: CI-A<N>` code marker. 3 categories: infra / by-design / deferred-fix. 4 current entries. Prevents silent accretion. Validator + staleness gate deferred to v2 (tracked §11)
- [x] **SECURITY.md auth-token honesty update** — prior text claimed the token was random-at-startup and memory-only unconditionally; reality is `_BRISTLENOSE_AUTH_TOKEN` in env overrides (for CI fixtures + uvicorn reload). Spec now matches code; doctor check warns on accidental env bleed. The proper gate (behind `BRISTLENOSE_DEV_MODE=test`) is a design problem deferred with a full plan (reminder 16 May 2026)
- [x] **Fix: Analysis "Show all N quotes" toggle** — was an `<a>` without `href` (surfaced only when e2e gate became blocking). Converted to `<button type="button">` with minimal CSS reset
- [x] **Fix: `playwright.config.ts` shell-quoting** — unquoted `${BRISTLENOSE}` / `${FIXTURE_DIR}` interpolation broke worktrees with spaces in the name. Pre-existing; surfaced during ci-cleanup verification

## CI hardening — sprint 1 (15–16 Apr 2026)

- [x] **pytest coverage in CI** — `--cov` flags on pytest, coverage XML uploaded as artifact, `[tool.coverage]` config in `pyproject.toml`. Baseline: 73% (11,116 statements). No `fail_under` yet — informational
- [x] **macOS CI matrix** — `ubuntu-latest` + `macos-latest` (informational, `continue-on-error`). Catches platform-specific bugs without blocking merges
- [x] **GZip middleware** — `GZipMiddleware(minimum_size=500)` on FastAPI app. Media routes set `Content-Encoding: identity` to prevent re-compression of video/audio
- [x] **Frontend bundle size gate** — `size-limit` (300 kB gzipped JS), `npm run size` / `npm run size:why`, runs in CI after frontend build
- [x] **Alembic migration strategy** — replaces manual `_migrate_schema()` with programmatic Alembic (no `alembic.ini`). Per-project SQLite, `render_as_batch=True` for SQLite compat, detect-and-stamp for existing DBs. Baseline revision 001 (no-op). 9 migration tests. Unblocks Person UUID migration (S3)
- [x] **Multi-Python CI** — test matrix expanded to 3.10, 3.11, 3.12, 3.13 × 2 OS (8 cells). `fail-fast: false`, macOS informational
- [x] **Split lint from test jobs** — `lint` (ruff, mypy, man page, pip-audit, SBOM) runs once on ubuntu/3.12. `test` matrix `needs: lint` — universal failures skip all 8 test jobs
- [x] **pip cache on test runners** — `cache: pip` on `setup-python` saves 30-60s per job
- [x] **Single coverage artifact** — only ubuntu/3.12 uploads coverage XML (was 8 redundant uploads)
- [x] **CI architecture doc** — `docs/design-ci.md`: goals, philosophy, job structure, matrix strategy, coverage gaps audit, desktop-build plan

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

## Re-evaluate security-review agent calibration (29 Apr 2026)

AI makes it cheap to enumerate every "could go wrong" — that doesn't mean every finding is worth acting on. During Beat 3 QA setup, security-review returned 11 findings against a single QA doc; piping them verbatim (rotate test keys, dedicated $5-cap key, Logger privacy spot-check, quit Zoom/iCloud before Wi-Fi off, wipe keychain via shell) added theatre without proportional risk reduction for a dev Mac with $20-cap + no-auto-renew keys. User pushback ("if they get my mac and cut my thumb off they can have the keychain — what do i care about $20 in a log") was the right calibration check.

Agent-side fixes to evaluate:
- Have the agent lead each finding with realistic impact + cost-of-mitigation, not adversarial scenario. Proportionality as burden of proof.
- Self-classify findings as "ship blocker" / "code-quality nice" / "threat-model dependent" instead of flat severity.
- Inject the user's threat model (single-user dev Mac, capped keys, security-literate ex-Canonical) so the agent weighs against actual consequence.

Caller-side discipline already captured in `feedback_proportionate_security.md` and the index entry in `MEMORY.md` — don't pipe agent output verbatim, mediate.

Bigger question: same calibration likely applies to other adversarial-by-design agents (a11y-review, perf-review). Worth tuning the suite prompts together.

---

## Ideas (captured, not triaged)

- **Collab with [`llmfit`](https://github.com/AlexsJones/llmfit)** for "what local model should this hardware run?" (3 May 2026) — currently `OllamaCatalog.fits()` is a hand-rolled approximation: bundled curated list + memory thresholds + "recommended for this Mac" hint. `llmfit`'s whole job is that question. Two scopes: (a) reuse llmfit as a dependency to power the model picker (replace the curated list + hint logic), (b) closer collab — contribute Bristlenose's actual analysis-task profiles (long-context theme clustering, structured quote extraction) so llmfit's "fit" metric incorporates analysis quality, not just "will it load." Reach out to AlexsJones once we have a story to tell (post-alpha, when we have real user-machine data on what actually works for analysis runs vs just chat). Captured during sandbox-debug walk.

- **Post-TestFlight: adopt `mise` / `uv` / `just` per `docs/design-dev-environment.md`** (6 May 2026) — Phase 0 (skill-level desktop-binary symlinks) **landed 6 May 2026**; Phases 1–4 are post-cohort-feedback only. Don't open as a branch during the alpha sprint. The doc is the parking lot. One open chip flagged in the doc's "Codesigning vs symlinks" section: change `rsync -a` → `rsync -aL` in the xcodeproj `Copy Sidecar Resources` script so `models/` ships as real bytes, not a dangling symlink. Verify production sidecar path first — may be redundant.
- **Doctor "(bundled)" annotation on FFmpeg path** (2 May 2026, parked from `bundled-binary-helper` review) — `bristlenose doctor` reports the resolved ffmpeg path even when it's bundle-relative inside the .app. Honest diagnostic vs add a `(bundled)` suffix so TestFlight users aren't surprised by absolute paths inside their `.app`. Product call. Park until alpha tester feedback says it's confusing. Reference: `bristlenose/doctor.py:check_ffmpeg`
- **Merge `bundled*Environment(for:)` Swift helpers when a third lands** (2 May 2026, parked from `bundled-binary-helper` review) — `BristlenoseShared.sslEnvironment(for:)` and `bundledBinaryEnvironment(for:)` are called back-to-back at every spawn site (`PipelineRunner.swift`, `ServeManager.swift`). At three helpers the two for-loops become real boilerplate; consolidate into a single `bundledSidecarEnvironment(for:)` then. Rule of Three — wait for it
- **Bridge the 1.5 GB Whisper-model first-run download with something to do** (3 May 2026) — Mac Background-Assets path (and any equivalent on other channels) will start fetching the model after first launch, but on a slow connection that's many minutes of dead air before the user can transcribe. Don't let the app feel inert. Options to explore: a bundled sample project (real audio + canned transcripts/quotes) the user can poke around in to learn the UI; a guided tour of the report surfaces; "what's downloading and why" progress affordance that's visible but not modal; pre-flight prompts during onboarding ("import existing transcripts" path is fully usable without the model). Goal: buy minutes of valid product experience while the engine lands. Surfaces near `docs/design-desktop-python-runtime.md` Background Assets work.
- **Feedback pipeline → Bristlenose (internal dogfooding)** (17 Apr 2026) — IMAP fetch from feedback@bristlenose.app (DreamHost) → deterministic PII/header strip (Presidio + salted anon IDs for sender stability) → redacted `.md` archive in gitignored dir → monthly batch ingest into a private Bristlenose project to cluster themes for roadmap input. Read-only, never used as demo data, never shipped. Consent-safe because it stays internal. Caveats: emails are many short sessions (not few long ones) — may need a batch mode or synthetic "session per month"; no moderator questions so question-pill logic doesn't apply.
- **Incremental analysis methodology (post-TF reanalysis)** (13 May 2026) — design doc captured at `docs/design-incremental-analysis.md`. No implementation. Surface when a TestFlight tester adds new interviews to a project that's already been analysed and wants the delta, not a full re-run. Cost question: which pipeline stages can re-use cached output and which must re-run when the corpus changes.
- **ASR backend strategy** (11 May 2026) — design doc captured at `docs/design-asr-backend-strategy.md`. Articulates the mlx-only-on-Apple-Silicon vs faster-whisper-on-x86 split, platform-transcripts (Teams Premium / Zoom paid) as optimisation. Phase 1 marked shipped at capture time; later phases not scheduled.
- **Native-vs-web surfaces** (12 May 2026) — design note captured at `docs/design-native-vs-web-surfaces.md` (alongside `reset-app-state.sh`). Categorises which surfaces should be native Mac vs WKWebView; informs future port-of-UI decisions. No implementation queue.
- **Foundation Models corpus + multi-stage LLM routing scaffolding** (19 May 2026) — pre-WWDC plumbing across three in-flight feature branches (`foundation-models-corpus`, `pipeline-view-v1`, `pipeline-view-v1-5`) and three trued design docs (`design-modularity.md`, `design-pluggable-llm-routing.md`, `design-stage-backends.md` — reconciled together at `e9b77e9`). Plumbing now, FM-provider code / spike branches / premium-tier-shape commitment hold until WWDC + post-cohort. Strategy memory: `project_apple_ai_durable_plumbing_thesis.md`. **Canonical entry:** `100days.md` § "Captured for triage" — that's the source of truth; this is the antechamber pointer so the work doesn't disappear from sitreps and `/sync-board`.
- **CLI-UX codebook (cli-ux.yaml) + analysis-register companion + asciinema session-matching design note** (11 May 2026) — captured as two phases. Phase 1 already on disk: `bristlenose/server/codebook/cli-ux.yaml` (6 groups, 35 tags, audience-aware preamble) + `docs/design-cli-analysis-register.md` (register rules for emitting reports that land with API designers / DX engineers / OSS maintainers, not classical UXRs — codebook-aware prompt variants in `bristlenose/llm/prompts/`, headline blocks, bug-stub emission). Phase 2 deferred: `docs/design-cli-session-matching.md` covers asciinema + paste-log ingestion, 90% case is remote Teams/Meet/Zoom call with participant emailing terminal artifact afterwards, primary privacy control is the disposable-VM + revoked-keys research protocol, redaction is defence-in-depth. Don't start Phase 2 until Phase 1 has produced reports the audience finds useful. Cheapest move when scheduled: `cli-register` variants of `extract_quotes` + `generate_themes` prompts, sandpit-sized week, no new pipeline stages or DB changes.

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
| `docs/archive/design-reactive-ui.md` | Framework comparison, risk assessment (partially superseded by React migration) |
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
| `docs/design-speaker-splitting.md` | LLM splitting for single-speaker transcripts |
| `docs/design-speaker-role-detection.md` | Generalised role detection (oral history, journalism, etc.) |
| `docs/design-speaker-editing.md` | Four transcript editing operations (name, reassign, split, merge) |
| `docs/design-transcript-speaker-editing-roadmap.md` | 11-layer work breakdown for transcript + speaker editing |
| `docs/design-sidebar.md` | Dual-sidebar layout (TOC left, Tags right) |
| `docs/design-windows-ci.md` | Windows CI strategy, compatibility audit, phased plan |

---

## Done (reverse chronological)

- [x] **FOSSDA pipeline throughput baseline** (Apr 2026) — manual measurement procedure for per-stage wall-clock times, LLM latency, peak RSS, peak mid-run temp WAV against 10 FOSSDA interviews. Added `logger.info("llm_request | ...")` in `LLMClient.analyze()` so request-latency median/p95 is derivable from `bristlenose.log`. Ran two usual-suspects passes; fixes covered thermal stabilisation, ANSI-strip, hardware-key capture, Welford vs elapsed clarification. See `docs/design-perf-fossda-baseline.md`
- [x] **CLAUDE.md refactor** (Apr 2026) — offloaded reference material (lookup tables, feature specs, action catalogues) from 5 CLAUDE.md files into 8 new docs + 3 existing docs. Total CLAUDE.md down 1,995→1,527 lines (-23%). New docs: `design-desktop-menu-actions`, `design-desktop-settings`, `design-sentiment-charts`, `design-badge-action-pill`, `design-dashboard-navigation`, `design-react-islands`, `design-autocode`, `design-react-migration-status`. Gotchas/conventions/patterns preserved; reference lookups moved with one-liner pointers
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
- [x] **Pipeline resilience Phase 2c** (Apr 2026) — input change detection via source file metadata hashing (size+mtime), upstream content_hash propagation, cascade invalidation. 12 new tests
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
