# Bristlenose — Where I Left Off

Last updated: 21 Jun 2026 (**Warm-sidecar pool — instant, crash-free project switching (Phase A2)** on branch `warm-sidecar-pool`, implemented + core-GUI-QA-passed, pending merge after `project-status-line`. `switchProject` now *parks* the outgoing serve sidecar and re-points to it on switch-back instead of teardown+restart — rapid A↔B is an instant hand-off and the restart-race crash (`Server exited before becoming ready (code 1)`) dissolves. **Option B: a single parked slot, not a dict+LRU pool** — reviewed + rejected the LRU pool as over-engineering for the only-observed A↔B repro; reuses the single `generation` token (no second epoch — `ObjectIdentifier` identity-routing retired the old termination epoch capture). **CRITICAL review catch (3 agents):** the detail-pane WebView must be keyed `.id(project.id + port)`, not id alone, or a warm re-point reuses the previous sidecar's token → silent 401s/blank report. Reviewed via `/usual-suspects` (plan, 6 agents + William) + William (impl), both clean; full `BristlenoseTests` green (343). Post-QA: A2 keeps the *server* warm, not the rendered *view*, so it's "fast, not instant" — the switch-perf tiers + road to instant (Tier-2 retained WebViews = Phase C, non-negotiable for paid; the free CLI+Safari path already sets that bar) are catalogued in `docs/design-desktop-switch-performance.md`. Post-TF umbrella (genuine multi-project + multi-window — problem def + the undecided A/B/C serve-model options) promoted to `docs/design-workspace.md`; planner Workspace item refactored to point at it (objective + best-guesses, decision deferred to post-TF). Prior: 18 Jun 2026 (**Sidebar run-progress text + drag-create polish** on branch `progress-text-surfacing`, pending merge — the running-row subtitle now reads the live ladder ("Transcribing · 2 of 3 · <1 min left") via the pure `RunProgressSubtitle` composer (six-stage `timing.py ALL_STAGES` vocabulary — NOT `manifest.STAGE_ORDER` — localised in all 7 locales, drift-pinned test; degrades to "Analysing · <1 min left" then "Analysing…"); the row icon baseline-aligns to the title (`firstTextBaseline`); and a folder-drop now adopts the folder's own name with no inline rename ("+ New Project" still opens rename). GUI-verified live across the stage ladder; trued `docs/design-sidebar-activity-indicators.md` to shipped-0b. Also this session, review-driven (`silent-failure-hunter` caught it; 4 other agents + the plan missed it): **sidebar session-count refresh** (`1e1d608`) — the count went stale/`nil` after a run because the *serve importer* commits `sessions` into a WAL the desktop's sandbox-mandated `immutable=1` read can't see until checkpoint (the pipeline run never writes the count), and the watcher only rescans on source-file events; fixed two-part — importer PASSIVE-checkpoint (`_checkpoint_wal`) so immutable readers see the rows + a desktop completion ride-out rescan (`ContentView.scheduleCountRescan`); importer file-DB regression test + `CompletionRescanTests`; live-confirmed the failure mode (foo2 served, report knew 3 sessions, sidebar blank — stale bundled sidecar lacked the checkpoint). **Key gotcha surfaced:** `010910a`'s 0b ring was *latent* on desktop — the bundled sidecar (v0.15.14) predated the `run_progress` emit, so neither ring nor text appeared until the sidecar was rebuilt (`build-sidecar.sh`); see `desktop/CLAUDE.md`. Two follow-ups captured as handoffs: during-run **detail-pane** surface (deferred per "sidebar text only"), and **cached/skipped-stage progress emit** (upstream Python — cached runs emit only the initial estimate → "Analysing · <1 min left" throughout). Prior: 17 Jun 2026 (**Phase 0b determinate ETA progress ring** implemented on branch `determinate-progress` — Welford ETA surfaced via a new `run_progress` event → Swift determinate ring with monotonic + asymptote honesty rules (`010910a`); plus **report auto-reload on run completion** fixed on the same branch — the in-place detail WebView now reloads via `bridgeHandler.reloadWebView()`/`reloadFromOrigin` on the analysing→ready transition (the `.id`-bump approach was silently defeated by `updateNSView`'s same-URL guard), so the report renders without a manual project switch; GUI-verified, pending merge. Model-default 404 fix (chip `task_42398d4f`, now superseded): the retired default `claude-sonnet-4-20250514` (Anthropic killed it 15 Jun) was un-rotted **run-path-only** (`f159fec` on this branch — providers/config/pricing/Swift/tests → `claude-sonnet-4-6`/`claude-opus-4-8`); the durable SSOT + `doctor` liveness + monthly-EOL-watch layer is parked as `model-eol-resilience` (handoff + 100days card + memory `project_model_default_resilience`). Prior: 10 Jun 2026 (**CLI `--llm <provider>` provider-default-model fix shipped** on branch `llm-provider-default-model` — `_fill_provider_default_model` in `config.py` snaps `llm_model` to the resolved provider's `default_model` on the CLI when no model was chosen, fixing the cross-provider 404 (`--llm chatgpt` → Claude model → OpenAI 404 at s08). Value-based gate (not the `_src` dotenv-file label, which misses provider+key-in-`.env`-no-model); CLI-only; drift-pin test. Reviewed 3 rounds (code-review/bach/silent-failure/william). Prior: 9 Jun 2026 (**smart-split quote extraction shipped** on branch `chunked-quote-extraction` — `f8ea55a`, **merged to main**: reactive truncation→split for low-output-cap models, typed `TruncatedResponseError` + `OUTPUT_TRUNCATED` Cause (Swift-mirrored), cloud-client `max_retries=6` for 429 bursts; verified live on Claude (forced-cap A/B), full ikea2 pipeline, and real gpt-4o SDK; quote-exclusivity held. No version bump yet (release pending — wheel code touched). Earlier: 8 Jun 2026 (popover state catalog + display-kind taxonomy captured, docs-only `26203e8` — see Ideas › Pipeline popover state catalog. Earlier: desktop ChatGPT run fixed end-to-end + verified in the sandboxed app — see Ideas › Desktop provider-resolution. No version bump: wheel unchanged; fixes are desktop sidecar/entitlements + CLI flag default. Prior: 5 Jun 2026 — v0.15.13 release — pipeline-view v2 per-(provider, model) grain shipped to PyPI; desktop flow-B Ollama setup + consent-activation merged; CI hardened with job timeouts, SHA-pinned actions, and least-privilege tokens. 2978 tests passing, ruff clean. Also: **Cassandra** dependency pre-mortem agent + `/cassandra` skill shipped — `0bbb1ca`, **now public on origin/main** (`917565b`, pushed 5 Jun — no version bump: all `.claude/`/`docs/`/`.github/`, nothing in the wheel); see Ideas below.)

**Most recent ship: v0.15.13 (4 Jun 2026)** — `bristlenose pipeline` view gains per-(provider, model) grain (feature rung v2, schema 3→4); desktop model-first Ollama setup (flow B) with consent now activating the chosen provider; CI hardening (bounded jobs, pinned third-party actions, read-only default token scopes, six-class fragility map in `docs/design-ci.md`). See `CHANGELOG.md` for full bullet list.

**Launch plan:** `docs/private/100days.md` — triaged by topic + MoSCoW priority. That's the source of truth for what ships. This file is a public capture inbox + session context — antechamber for untriaged items only; promote to the plan doc once triaged.

---

## Next session focus

**S3 (12–23 May) is the active sprint.** Gate has shifted (7 May quality reset): Internal TF is gated on **walks-fix-walks** — 2–3 consecutive end-to-end walks across different scenarios producing zero new snags — not on a checklist. Mission Sandbox PASSED 4 May; Track B + S6 framing is superseded.

Pick up from `docs/private/100days.md` §Critical Path. Within-sprint candidates: D1 stage-contract audit (unblocked by A4 + B1); remaining sandbox exports (clips / CSV / slides / anonymised bundle); C-stream UX papercuts; continue walks 5–8 from §1. **Release-pipeline-to-PyPI is the surprise S3 risk** — six tags behind users; CI patch landing tonight.

Reference: `docs/private/handoffs/sandbox-walk-followup-fixes.md` (closeout), `docs/private/sandbox-inventory-beats-6-13.md` (16-finding inventory + status block).

---

## Ideas (captured, not triaged)

- **Detail-pane "can't show a report" states — design as a set** (18 Jun 2026) — Treat *all* the "I can't show you a report right now" detail-pane screens as one coherent family, designed together, not piecemeal (same spirit as the popover state catalog below, but for the detail pane). Today they're split across **two rendering systems with two visual languages**: the **Python serve status page** (`bristlenose/server/status_page.py:detect_status`) renders _No interviews to analyse yet_ / _Nothing to see here, yet_ / _Last run was cancelled_ / _Last run failed_; the **Swift native chrome** (`BootView.swift`) renders _starting sidecar_ / _loading report_ / _sidecar failed → installation corrupted + Retry_; and **`ProjectAvailability`** drives _can't-find volume (unmounted)_ + _cloud-evicted (iCloud)_. The **mid-first-analysis** case (run in flight, no report yet) currently falls through to "Nothing to see here, yet." — that's the during-run detail-pane handoff, now **demoted to Could / post-TF**: the sidebar ring + `RunProgressSubtitle` text already say "it's working," and a richer detail-pane progress surface is *not in the TF timescale*. Designing as a set surfaces the architectural call the during-run handoff already flagged — a boot/status surface is native chrome (per *data views → React SPA; native chrome → nav/status/boot*), so the set likely **consolidates the Python status-page states into native Swift surfaces** (one visual language, not two). **Design-first: enumerate + mock the whole family before any Swift.** Grounding: during-run spec at `docs/private/handoffs/progress-text-detail-pane.md` (folded into this set); state anchors are `status_page.py:detect_status` + `BootView.swift` + `ProjectAvailability`.

- **Pipeline popover state catalog + rolling-log direction** (8 Jun 2026, `26203e8`) — catalogued every desktop popover/status state with a surface-level **display-kind** taxonomy (codifies what already ships; designs nothing new) in `docs/design-pipeline-diagnostic-popover.md`. Surfaced a coverage finding: only the Ollama pill is live-invocable from `CommandMenu("Debug")`; the diagnostic popover is env-var + relaunch; everything else is real-condition-only. **Post-TF follow-up (deliberately undecided):** the `.running` popover flicks per-stage screens past unread on a fast run (the toast anti-pattern); the captured direction is an in-flight rolling-log / collapsing phase-itinerary reusing the settled MessageKind row vocabulary — see the doc's "Future direction" deferred appendix + the native-size mock `docs/mockups/pipeline-popover-rolling-log.html`. Implementation is a separate `/new-feature` pass that decides the appendix's open questions (accordion vs carousel, where legible phase names live, expansion policy). **Guardrail: reuse the settled icons/typography/MessageKind/diagnostic IA — do not relitigate.**

- **Desktop provider-resolution + diagnostic honesty** (5 Jun 2026) — handoff: `docs/private/handoffs/desktop-provider-resolution.md`. The desktop "Transcription failed" was a *ghost*: the run went out as **Claude with a Gemini model** (`gemini-2.5-flash` → Anthropic 404), mislabelled by an over-broad classifier. Four defects, none transcription: (1) `ConsentActivation.resolve` flips a deliberate provider choice → Anthropic when its cached verdict isn't `.online`; (2) `overlayPreferences` injects the global `llmModel`, not per-provider, so provider+model desync; (3) over-broad failure classifier (`(speech )?model` matches benign preflight); (4) swallowed cause ("Detailed cause not captured"). Start: `/new-feature desktop-provider-resolution …` (invocation in the handoff). The `gemini-provider` model-string fix (`gemini-2.0-flash`→`gemini-2.5-flash`) is itself **done + Tier-1 verified** (key validates, picker shows the model, persists across relaunch) — that branch's deliverable stands; this is the separate desktop bug it surfaced.
  **Update 8 Jun 2026 — desktop ChatGPT run now works END-TO-END, verified in the sandboxed app** (drag literal video-only folder → fresh GUI run → report on-screen: 14 quotes / 2 themes, run_completed). Five layered blockers found + fixed (`d9963e9`, `a6bd586`, `94892fd`): the decisive one was `run --llm` defaulting to "claude" and beating the desktop-injected `BRISTLENOSE_LLM_PROVIDER` env var (anthropic+gpt-4o 404); plus JIT entitlements (transcription SIGKILL), per-model gpt-4o max_tokens clamp, `freeze_support()` (`-B` crash), `.env` carve-out + orphan-guard, and a full provider/model resolution ledger. Trail: `docs/private/ikea-run-debug-log.md`; gotchas: `desktop/CLAUDE.md` § "Run / sidecar / signing gotchas". **Two follow-ups, do in this order:** (1) ~~**chunked quote extraction** — gpt-4o's 16384 output ceiling truncates quote extraction ~1/3 on dense transcripts → run fails; the real reliability fix (= `100days.md:674` smart-split).~~ ✅ **DONE 9 Jun 2026 (`f8ea55a`, branch `chunked-quote-extraction`, merged to main)** — smart-split shipped + verified; see 100days.md:674. ~~**New follow-up surfaced:** CLI `--llm chatgpt` (no `--model`/env) doesn't apply the provider's `default_model` → sends Claude's model to OpenAI → 404; coherence-snap in `config.py` is desktop-gated. Chip filed; own branch.~~ ✅ **DONE 10 Jun 2026 (branch `llm-provider-default-model`)** — `_fill_provider_default_model` snaps the model on the CLI too, gated on the model *value* (not the `_src` dotenv-file label); reviewed 3 rounds. (2) **Swift bare-model env tidy** — host can still inject a bare `llmModel` without a provider; the Python orphan-guard makes it harmless, so hygiene not a fix. Original-handoff defect (1) (`ConsentActivation.resolve` flips provider→Anthropic on non-`.online` cached verdict) was NOT re-touched — still open.
  **Update 8 Jun 2026 (cont.) — the resolution ledger is now legible across the Swift/Python seam.** Added `step=host-defaults` (Swift host emits which provider/model/key it injected — `key=present/absent/keyless` only, never the value) + `step=cli-args` (the `run`/`analyze` `--llm` forward-or-not decision), so the trace reads top-to-bottom: host-defaults → cli-args → Python `0-inputs … 4-final`. Python read-site is `load_settings` (the chokepoint, so autocode/analysis/run all carry it). Pinned Python-side (`tests/test_desktop_config_resolution.py`); Swift side has `BristlenoseTests` (build-compiles; runs via Xcode Cmd+U, not CI). Rationale + the queue-vs-env-var transport split: `docs/design-test-philosophy.md` §(b).

- **Real end-to-end install smoke — the "hello" test** (4 Jun 2026, ~2h) — when `bristlenose render` was removed, its 4 stale call-sites broke `Install & Smoke Test` for ~11 days (invisible because the CI monitor was watching the wrong workflow name — both fixed 4 Jun). The per-push install jobs were reduced to `--version` + `doctor` ("is it alive / are native deps present") — deterministic, zero-flake, but no real pipeline coverage. Deferred deeper test: generate a tiny ~2 s one-word video fixture (`say -o word.aiff "hello"` → ffmpeg to a small `.mp4`, commit it) and wire it into the **keyed, scheduled `full-run` job** for a true end-to-end transcribe→analyse→render. Deliberately **not** on every push, for two reasons we worked out: (a) full `run` needs an API key for the analysis stages, so it can only live in the keyed job; (b) a per-push Whisper-tiny *transcribe-only* is both flaky (model download + inference re-imports the exact CDN/download fragility class we removed on 4 Jun) **and** a non-representative slice — it skips the Claude analysis that is the actual product. Cheapest version: point `full-run` at the tiny video alongside the existing VTT fixtures, lenient transcript assertion. Optional bonus: de-`|| true` an `ffmpeg -version` check in the per-push jobs (deterministic native-dep gate). Context: `.github/workflows/install-test.yml`, `docs/design-ci.md` § Fragility classes.

- **Cassandra dependency pre-mortem — follow-ups** (4 Jun 2026) — the agent + `/cassandra` skill shipped (`0bbb1ca`); see `docs/design-dependency-premortem.md` + the ledger `docs/dependency-premortem-log.md` (Entry 1 = pre-mortem of the full outstanding bump wave; effectively *is* the overdue May-2026 quarterly dep review, minus the floor-pin bumps). Near-term: (a) Cassandra is now public (pushed 5 Jun 2026, `917565b`) — post the drafted friendly "inspired by you" issue on [`thoughtbot/dependabot-review-skill-thoughtbot`](https://github.com/thoughtbot/dependabot-review-skill-thoughtbot) pointing back to it; (b) the **lighthouse** major-ignore in `.github/dependabot.yml` still carries a stale "CI is on 20" rationale — CI is Node 24 and lighthouse 13 needs ≥22.19 (satisfied) — so either drop the ignore or correct the comment (a dep-policy call, deliberately left to you). Validate the prophecies: `/cassandra --score` can already mark **@playwright/test 1.60.0 (PR #110)** a real *hit* — it shipped and fixed the chromium-install hang. Longer-term: extract Cassandra into a standalone generalised OSS giveaway repo (~Sep 2026) — scheduled reminder set + memory `project_cassandra_standalone_extraction.md`; gated on scored ledger data + a v1.
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

- [x] **May 2026** — Run `pip list --outdated`. Bump floor pins in `pyproject.toml` only if there's a security fix, a feature you need, or the floor is 2+ major versions behind _(closed 8 Jun 2026 — Cassandra ledger Entry 1 effectively is this review minus floor-pin bumps; see TODO.md L27)_
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

