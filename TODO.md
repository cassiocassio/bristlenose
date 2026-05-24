# Bristlenose — Where I Left Off

Last updated: 19 May 2026 (`pipeline-diagnostic-popover-swift` Swift half shipped on branch — Mac diagnostic popover surfaces partial / abandoned runs with per-bucket SF Symbol failures, dominant-category pill, plaintext-portable Copy, debug fixture harness. Trued spec doc + review log, four review passes, all 45 findings closed/parked/ignored. Build clean, 2754 tests passing, ruff clean. Twelve forward-looking plan files under founder-private handoffs for next iterations — Plan A (terminus per-stage summaries), Live progress Phases 1+2, pill visibility discussion, schema-v6 rides, verbose mode stretch. **Pre-existing leak found:** `bristlenose/cli.py:857` prints "Pipeline failed." — user-facing convention is "Analysis" not "Pipeline" (now documented in `docs/design-pipeline-diagnostic-popover.md` §"User-facing vocabulary"). Worth a small sweep when convenient.)

**Most recent ship: v0.15.10 (17 May 2026)** — C1 codebook plumbing (`--codebook=<slug>` + `bristlenose codebooks` subcommand) and smoke-fixture `RunCompletedEvent` so e2e perf-gate stops timing out on `#bn-app-root`. **Caveat:** PyPI is still at 0.15.3 as of 19 May — seven tag pushes since 10 May haven't reached users; `ci/perf-gate` failed on every release workflow run in that span. CI fix in flight, release attempt expected tonight (19 May). v0.15.8/9 carry the substantive work — honesty everywhere (A3 + A4 + B1), multi-project Phases 0–3, sidebar honesty wave 2, HIG corpus, Keychain biometric ACL, folder watcher, AppleDouble skip. See `CHANGELOG.md` for full bullet list.

**Launch plan:** `docs/private/100days.md` — triaged by topic + MoSCoW priority. That's the source of truth for what ships. This file is a public capture inbox + session context — antechamber for untriaged items only; promote to the plan doc once triaged.

---

## Next session focus

**S3 (12–23 May) is the active sprint.** Gate has shifted (7 May quality reset): Internal TF is gated on **walks-fix-walks** — 2–3 consecutive end-to-end walks across different scenarios producing zero new snags — not on a checklist. Mission Sandbox PASSED 4 May; Track B + S6 framing is superseded.

Pick up from `docs/private/100days.md` §Critical Path. Within-sprint candidates: D1 stage-contract audit (unblocked by A4 + B1); remaining sandbox exports (clips / CSV / slides / anonymised bundle); C-stream UX papercuts; continue walks 5–8 from §1. **Release-pipeline-to-PyPI is the surprise S3 risk** — six tags behind users; CI patch landing tonight.

Reference: `docs/private/handoffs/sandbox-walk-followup-fixes.md` (closeout), `docs/private/sandbox-inventory-beats-6-13.md` (16-finding inventory + status block).

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
- **Optional bottom status bar** (23 May 2026) — design exploration + macOS convention research captured at `docs/design-status-bar.md`. Move the pipeline status pill out of the toolbar into an optionally-visible bottom strip; full surface inventory + tiered shortlist + the visibility-policy gating decision. Post-TF (competes with titlebar redesign + the unified failure popover). **Canonical entry:** launch plan § "Captured for triage" — this is the antechamber pointer. Next step before Swift: re-run HIG research from the Mac for verbatim citations, then mock.
- **CLI-UX codebook (cli-ux.yaml) + analysis-register companion + asciinema session-matching design note** (11 May 2026) — captured as two phases. Phase 1 already on disk: `bristlenose/server/codebook/cli-ux.yaml` (6 groups, 35 tags, audience-aware preamble) + `docs/design-cli-analysis-register.md` (register rules for emitting reports that land with API designers / DX engineers / OSS maintainers, not classical UXRs — codebook-aware prompt variants in `bristlenose/llm/prompts/`, headline blocks, bug-stub emission). Phase 2 deferred: `docs/design-cli-session-matching.md` covers asciinema + paste-log ingestion, 90% case is remote Teams/Meet/Zoom call with participant emailing terminal artifact afterwards, primary privacy control is the disposable-VM + revoked-keys research protocol, redaction is defence-in-depth. Don't start Phase 2 until Phase 1 has produced reports the audience finds useful. Cheapest move when scheduled: `cli-register` variants of `extract_quotes` + `generate_themes` prompts, sandpit-sized week, no new pipeline stages or DB changes.

---

## Task tracking

**GitHub Issues is the source of truth for actionable tasks:** https://github.com/cassiocassio/bristlenose/issues

**Launch plan:** `docs/private/100days.md` — triaged by topic and MoSCoW priority.

This file contains: session reminders, untriaged captures, dependency maintenance, and reference tables.

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

