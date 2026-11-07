# Reference docs — by area

Moved verbatim from the root `CLAUDE.md` on 5 Nov 2026 to cut what every session loads on every turn. The root keeps a short rule and a pointer here. Read the group for the area you are working in. The "must-read" groups and the sibling CLAUDE.md list stay in the root.

**Frontend / UI:**
- `bristlenose/theme/js/MODULES.md`, `bristlenose/theme/CSS-REFERENCE.md` — JS + CSS component reference
- `docs/design-sidebar-playground.md` — 6-column grid, overlay, drag-resize, minimap, dev playground
- `docs/design-responsive-layout.md` — quote grid, density, breakpoints
- `docs/design-react-migration.md` — active migration plan
- `docs/design-react-component-library.md` — 16 primitives
- `docs/design-minimap.md`, `docs/design-inspector-panel.md`, `docs/design-finding-weight.md`

**Pipeline / backend:**
- `docs/design-cloud-files.md` — **read before anything iCloud- or File-Provider-shaped.** The one statement of what can and cannot be known about cloud-backed files and what Bristlenose shows: a bounded read, an ordinary retryable failure, the existing can't-find pane; no wait label, no cloud glyph, no provider advice. Re-proposed five times before 22 Oct 2026; not reopened by a new framing
- `docs/design-analysis-lifecycle.md` — **the cross-cutting view of analyse / re-analyse / incremental**: one state machine, sequence diagrams, the affordance inventory, and the observed failure modes (four outcomes, not three). Read before adding or changing any analysis-triggering control
- `docs/design-pipeline-resilience.md` — manifest, event sourcing, resume, provenance
- `docs/design-screens.md` — **the plan for screens (proposal, 13 Oct 2026; one project, Mac first, OCR engine pluggable):** joins what was said, what was on the shared screen and which screen they were on. Read before touching OCR, screen text, the Screens lens, or quote↔screen joins; its two evidence records are `design-screen-text-search.md` and `design-screens-lens.md`. **Its §4 privacy line was corrected 17 Oct 2026: Bristlenose never sends screens anywhere on its own (never to the LLM); anything the researcher chooses — exports, their cloud tools, MCP — is open.** The exports (folder, clipboard, Miro board) are planned in `design-screens-export.md`
- `docs/design-project-identity.md` — **decided 13 Oct 2026, built 15–16 Oct (phases 2, 4, 5 and 6; phase 3 obviated): a study is its database plus a marker id (`study_marker.py`, with a visible `bristlenose-study.txt` beacon Locate… finds by Spotlight), a recording is a content fingerprint (`utils/fingerprint.py`, registry version 3), a path is a hint that heals.** §11a records where the build departed from the note and the known limits. Read before touching the project row match, `sessions.json` keys, `SourceFile.path`, the MCP project key, or the sidebar's drop and relocate code
- `docs/design-lifecycle-failure-modes.md` — **read before changing where a project's database, output or events live, or anything that runs across a stash, restore, crash, rename or move.** The register of lifecycle failure modes, each designed out with its proving test or open with its reason (its § The score has the count); `tests/test_lifecycle_scenarios.py` engineers them against the real server and stash code, with strict xfails for the open ones
- `docs/design-pipeline-diagnostic-popover.md` — **read before adding any new error / status / message that surfaces in the popover, the pill, the sidebar glyph, or any toast.** Five-kind `MessageKind` taxonomy (`bristlenose/ui_kinds.py`), length budgets, anti-patterns, flowchart for fitting new messages into the existing vocabulary instead of inventing new glyphs/colours
- `docs/design-platform-transcripts.md`, `docs/design-transcript-coverage.md`
- `docs/design-people.md` — **problem-first spec for person identity: jobs to be done, then UX, then data.** Read before touching names, speaker roles, or anything that renders a person. Owns the ranked sequence, the settled decision 1 (codes are globally-numbered slots, identity a layer above; renumbering falls out of renaming — supersedes §11c's (session,code)-rekey direction), the one still-open product call (decision 2: whose name survives an export), and §H's sequenced work packages
- `docs/design-speaker-splitting.md`, `docs/design-speaker-role-detection.md`
- `docs/design-speaker-editing.md`, `docs/design-transcript-editing.md`, `docs/design-transcript-speaker-editing-roadmap.md`
- `docs/design-multi-project.md` — scope rules (instance vs project tables)
- `docs/design-session-management.md`
- `docs/design-logging.md`

**Export:**
- `docs/design-export-html.md` (anonymisation), `docs/design-export-locale.md` (one language per deliverable — shipped in 0.28.0), `docs/design-export-quotes.md` (CSV/XLS), `docs/design-export-clips.md`, `docs/design-export-slides.md`, `docs/design-miro-bridge.md`, `docs/design-footer-feedback-react.md`

**Desktop:**
- `docs/archive/design-desktop-app.md`, `docs/design-desktop-security-audit.md`
- `docs/design-modularity.md` — **canonical cross-channel component strategy** (CLI + macOS, Background Assets, no-fork principle, trickle-to-full-capability)
- `docs/design-desktop-python-runtime.md` — Mac sidecar mechanics
- `docs/private/road-to-app-store.md` — current Apple-side gate sequence (Sprint 2 plan archived; see 100days.md for live plan)
- `docs/design-project-sidebar.md`, `docs/design-wkwebview-messaging.md`
- `docs/design-desktop-menu-actions.md`, `docs/design-desktop-settings.md`

**Assistant surfaces (MCP + chat lens):**
- `docs/design-mcp-server.md` — the endpoint, its four tools, §6a's sheet-era as-built record (superseded, kept as history)
- `docs/design-mcp-extension.md` — **the shipped Mac path**: handshake file (§3.1), proxy contract (§3.2, §5b's three states), Settings ▸ MCP Agents (§3.7), the Turn On/Off Agent Access verb swap (§3.6a), the exposure badge (§5a-bis), packaging + build gates (§4), and §5c's spike + live-install measurements
- `docs/design-chat-lens.md` — the in-app cited question box (same grounding core)
- `docs/design-mcp-native-proxy.md` — **read before touching agent access on macOS 27 or the ChatGPT channel.** Measured 29 Sep 2026: ChatGPT installs a local plugin in one click (`codex://plugins/<name>?marketplacePath=<marketplace.json>`), runs its tools in Work mode only, and does **not** supply Node; macOS 27 decides a container read by the *responsible* process, and a team-signed proxy launched as its own responsible process needs no grant — but that route is private SPI and was rejected for the App Store. What is built (on `main`, unreleased) is a sandboxed helper carrying the team app group, in `desktop/mcp-helper/`, gated by `desktop/scripts/check-mcp-helper.sh` (§6.9–§6.11)
- `docs/design-mcp-files-and-folders.md` — the System Settings ▸ Files & Folders route for the Node proxy on macOS 27 (shipped copy, all 21 locales); now the fallback for a build without the native helper, and the recovery sentence

**Analysis / research methodology:**
- `docs/design-research-methodology.md` — read before changing prompts or analysis logic
- `docs/academic-sources.html` — theoretical foundations
- `docs/design-signals-future.md`, `docs/design-quote-sequences.md`, `docs/design-dashboard-stats.md`, `docs/design-signal-elaboration.md`

**i18n:** `docs/design-i18n.md` — terminology table, implementation gotchas

**Codebook:** `docs/design-codebook-norman.md` (**read before rewording any framework tag** — the decision register, the evidence policy for data that cannot be cited, and the harness; a decision there is reopened by a witness quote that fails, never by a hunch), and its siblings `design-codebook-garrett.md`, `design-codebook-morville.md`, `design-codebook-nielsen-register.md`, `design-codebook-yablonski.md` — every authored codebook has a register, a golden fixture under `tests/fixtures/codebook-golden/`, and `tests/test_codebook_registers.py` gates them: a settled decision without a witness fails, a fixture tag that does not exist fails, and **a `not_this` that points at a tag in another codebook which does not exist fails** (every 22 Sep 2026 audit found such pointers; `docs/codebook-audits/` holds the audits). A tag or group that changes name carries `renamed_from:` so `codebook_sync` migrates installed rows, `docs/design-codebook-v2.md` (the navigator that ships), `docs/design-codebook-state-model.md` (what the enable/disable switch means — the canonical spec), `docs/design-codebook-library.md`, `docs/design-codebook-focus.md`, `docs/design-moderator-question-pill.md`, `docs/design-dynamic-codebook-builder.md`. The v1 island's decision log is history: `docs/archive/design-codebook-island.md`

**HTML report / dashboard / auth:**
- `docs/design-html-report.md`, `docs/design-dashboard-navigation.md`
- `docs/design-sentiment-charts.md`, `docs/design-badge-action-pill.md`
- `docs/design-react-islands.md`, `docs/design-autocode.md`

**Ops / release:**
- `docs/release.md`, `docs/file-map.md`, `CONTRIBUTING.md`, `INSTALL.md`, `SECURITY.md`
- **`docs/testing/README.md` — the testing & acceptance hub (start here for anything test/QA/acceptance).** Three-tier model (CI · Playwright · acceptance matrix · human walk), `docs/testing/coverage-inventory.md` (the single source of surfaces: 27 formats · 5 exports · 5 lenses · 5 providers), `docs/testing/acceptance-matrix.md` (mechanical tier, Phase-1 plan), `docs/testing/test-data-generation.md` (fixture recipe). Built already: `tests/test_no_fake_success_acceptance.py` (skips without fixtures) + `e2e/`. The by-hand walk lives in the private QA doc.
- `docs/design-ci.md`, `docs/archive/design-test-strategy.md`, `docs/design-playwright-testing.md`, `docs/design-test-philosophy.md`
- `docs/design-doctor-and-snap.md`, `docs/design-homebrew-packaging.md`, `docs/design-fedora-packaging.md` (Copr — **live since 28 Aug 2026**, see the status section; §7 holds the standing obligations, and the measured `ffmpeg-free` codec verdict)
- `docs/design-cli-improvements.md`, `docs/design-llm-call-telemetry.md`, `docs/design-performance.md`, `docs/design-website-performance.md` (the 7 Nov 2026 PageSpeed audit of bristlenose.app: the Substack embed is the blocking time, the PNG shots are the bytes; every fix is owed in the website repo)
- **The release chain has a board.** `.venv/bin/python scripts/release-board.py` draws `.release/<v>/board.html` from the files the train writes; `--serve` runs it live on loopback behind a per-run token; `release.sh run --board` starts one detached if none is serving and prints the link, and without the flag prints it only if one exists (the release never needs the board — §8 of the design doc has the five layers) — the feed is `desktop/scripts/sink.sh` teeing the `@bn` protocol into `.release/<v>/bn-events.log` (`docs/design-release-board.md`). Two rules that cost a day: the board reads and never derives (no data is a third state, and the driver writes its own boundary lines so an empty sink is *ran, no record*, not *did not run*), and `printf %q` + `shlex` is not a round-trip — values are normalised before quoting and the parser counts what it cannot read.
- **The release chain is executable, and it is documented in three places, not one.** [`scripts/README.md`](../scripts/README.md) is the index (what to type: `release.sh plan|run|verify`, the gates, the suites that prove the gates). [`desktop/scripts/REPORT-STYLE.md`](../desktop/scripts/REPORT-STYLE.md) Part 2 is the *rules* a script follows — where constants live (`scripts/project.conf`), why probes are tri-state, what each exit code means (`75` = acts done, verification pending), the testability seams, and the shell traps this codebase has already paid for. `docs/design-release-machine.md` is the architecture and `docs/release-premortem.md` replays six months of release incidents against the current scripts. `docs/design-release-principles.md` is the *why* under all three — the saga/pivot shape, the tri-state-oracle and TOCTOU rules, gates-as-a-population, and what to measure — each line anchored to the incident that paid for it. **Four places, then.** Read the principles before adding a gate or a retry; they are what stops the next one being born dead.
- `docs/design-decisions.md` (why)
- `docs/ROADMAP.md`
