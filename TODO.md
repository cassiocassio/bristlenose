# Bristlenose — Where I Left Off

Last updated: 11 Jul 2026. _This file is a capture inbox + session context, not a changelog — `git log` + `CHANGELOG.md` are the unabridged record._

**11 Jul 2026 — v0.20.0 shipped (incremental builds).** Curation survives re-analysis (freeze marked quotes, membership-based section identity, star-anchored theme names, dismissible "New" badge); desktop loose-file intake + incremental add (drop / File→Add Files ⇧⌘A) + run recovery; native feedback sheet; sessions-journey deep-links; Shoal adaptive count. Bumped 0.19.0→0.20.0 (feature release = minor bump; convention now in CLAUDE.md). Live on PyPI + brew. **Desktop half reaches the cohort only with the next bundled-sidecar build — not yet done.**

**7 Jul 2026 — Acceptance-testing tier (Phase 1).** All test docs under `docs/testing/` (hub + `coverage-inventory.md`); built format-coverage + invariant harness + lens smoke (`bc5a036a`, folded into 0.20.0). Open: real Teams/Meet `.docx` parity fixture; firing local/cloud provider cells (`run_matrix.py --run-local` free / `--run-cloud` = keys+spend); `launchd` nightly wrapper (Phase 3).

**Launch plan:** `docs/private/100days.md` — triaged by topic + MoSCoW priority. That's the source of truth for what ships. This file is a public capture inbox + session context — antechamber for untriaged items only; promote to the plan doc once triaged.

---

## Next session focus

Sprint schedule (S1–S6) ended 30 Jun; active focus is the **Critical Path to Internal TF** in `docs/private/100days.md` §Critical Path. Internal TF is gated on the **walks-fix-walks** quality bar — 2–3 consecutive end-to-end walks across different scenarios producing zero new snags — plus a mechanical TF-branch upload (#3 sandbox flip re-apply, #10 ASC record, #12 first upload).

Immediate ladder: (1) **build + sign the bundled sidecar** so 0.20.0's desktop features (incremental add, loose-file intake, feedback sheet) reach the cohort — nothing to walk without it; (2) **walks-fix-walks** on that build; (3) mechanical TF upload. Orthogonal small win: **Opus 4.8 P2** (price the Opus row, current-gen the picker `"Opus 4"→4.8`) — overdue since ~18 Jun, TF-non-blocking; verify the catalogue still says "Opus 4" first.

---

## Ideas (captured, not triaged)

- **Focus mode (distraction-free reading)** — promoted to `docs/private/100days.md` §"Captured for triage" (spiked, unbuilt, Phase 0 next). Antechamber pointer; canonical entry is the plan doc.
- **Tag overload (same-meaning tag overlap)** — promoted to `docs/private/100days.md` §"Captured for triage" (design captured, `docs/design-tag-overload.md`). Antechamber pointer; canonical entry is the plan doc.

- **Colour palette picker + Edo v1** — ✅ shipped 0.19.0. Edo-polish follow-ups (muted-text AA-fail at 4.20:1, `--palette`/`BRISTLENOSE_PALETTE` env rename [chunk ②], provisional palette-string native review, surface-harmony pass) live in `docs/private/100days.md` §"Iterate Edo post-TestFlight".

- **Tag-sidebar count zero-suppression** — diagnosed 2 Jul: the post-AutoCode "wall of zeros" is correct data (accepted count) but reads as broken; proposals live only in the micro-bars. Design agreed = three-state count (bold accepted / muted tentative digit / clean blank) + suppress `TOTAL 0` rows. Sandbox committed (`docs/mockups/mockup-tag-count-zero-suppression.html`, `eea527fa`); implementation brief at `docs/private/handoffs/tag-count-zero-suppression.md`. **Gated on** the user picking the tentative-digit style (`6`/`6⁺`/`+6`/`·6`) in the sandbox. Trunk work, not a worktree.

- **Native colour/shape alignment (Tier-1)** — ✅ shipped 0.19.0 (Apple system-blue accent, grey nav-selection capsule, 6px radii, single shared palette). Deferred items (dynamic user-accent + live-`NSColor` selection bridge, link-blue split, neutral hover-vocab, dark `--bn-focus-shadow`) parked in `docs/design-native-colour-alignment.md`.

- **Localisation — 20 locales shipped** (0.16–0.19: cs/it/pt-BR/pt-PT/zh-Hant/zh-Hant-HK + pl/ru/uk/da/sv/nb/tr/nl/fi, joining en/es/ja/fr/de/ko). Machine-seeded community previews; **native review is the content gate** (per-language reviewer briefs + contested terms in gitignored branch notes; Weblate is user-owned). Open engineering follow-up: **`no`→`nb` auto-detection** not wired — 3 ingress points (i18next detector, `i18n.py`, Swift `Locale`); a bare-`no` system won't auto-select nb (manual pick works).

- **Native Quotes toolbar (search + starred) + per-lens search reminder** (27 Jun 2026, planned-not-built) — design + mockup done this session, no code. Plan: in the desktop app, make Quotes-lens **search** and the **starred filter** native toolbar controls and stop rendering their SPA equivalents when `isEmbedded()`; **remove the tags dropdown** from the SPA toolbar entirely (web + embedded) since the tags **sidebar** (`toggleRightPanel`) replaces it — retire `filterByTag` from the View menu + `AppLayout.tsx`. Chosen affordances: search = **expanding search button** (`NSSearchToolbarItem`, Safari/Mail pattern, maps to Cmd+F/`find`); starred = **single star toggle** (`allQuotes`⇄`starredQuotesOnly`). New bridge surface: native→web action `setSearchQuery {text}`; web→native message `quotes-filter {searchQuery, viewMode}` (same push pattern as `export-counts`/`lens-subtitle`); `BridgeHandler.quoteViewMode` for the star state + View-menu checkmarks. **Echo loop is mostly defused because the embedded SPA renders NO web search input** (`SearchBox` gated on `!isEmbedded()`) — the native field is the sole text source of truth, so `store.searchQuery` is a pure downstream filter param, not a second editable box. Native→web typing is one-way (no guard needed); web→native sync only fires for a few discrete native-initiated resets (`allQuotes` clear, `useSelectionForFind`/Cmd+E selection, find-pasteboard) — covered by a value-equality skip + don't-clobber-while-field-is-editing. Note `focusSearchInput()` (queries `.search-input`) no-ops in embedded mode → Cmd+F/Cmd+E focus is handled natively by the expanding toolbar item; only the `setSearchQuery` *filtering* path runs on the web side. Filtered count already rides the native subtitle (`postLensSubtitle`). Files: `Toolbar.tsx`, `AppLayout.tsx`, `shims/bridge.ts`, `ContentView.swift`, `BridgeHandler.swift`, `MenuCommands.swift`. **THE REMINDER (this is the captured bit):** Sessions / Codebook / Analysis have **no working search today** — the toolbar magnifier `find` calls `focusSearchInput()` which finds only the Quotes `.search-input`, so it **silently no-ops on those 3 lenses** (and Edit ▸ Find is a dead menu item there too). They each need real per-lens search one day: **Sessions** → transcript search (`TranscriptPage`), **Codebook** → filter codes (`CodebookPanel`), **Analysis** → filter signals (`AnalysisPage`). Interim UX decision (mine + user, 27 Jun): keep a **disabled** search button on those lenses (not morphed-away) to reserve the toolbar slot / set expectation / serve as the visible reminder — a deliberate, documented **exception** to the `desktop/CLAUDE.md` "toolbars morph, no greyed-out graveyard" rule (justified: search is conceptually universal, unlike the contextual toggles that rule was written for; a stable disabled slot is more native than a button that pops in/out). Disabled state needs a self-explaining tooltip ("Search in sessions — coming soon"-style) and matching menu dimming; add the CLAUDE.md exception line so nobody re-morphs it. Pre-build: run the `NSSearchToolbarItem` + star-toggle + disabled-state approach past `what-would-gruber-say` / `swiftui-pro`.

- **Export-menu follow-ups** (22 Jun 2026, branch `claude/cli-export-audit-9uuhn7`) — deferred from the export-popover review. (1) **Web SPA dropdown parity**: `ExportDropdown.tsx` should gain the anonymise toggle + CSV/XLSX format choice + All/Selected/Starred scope the macOS popover has — shared `utils/exportActions.ts` (`saveQuotesSpreadsheet(format)`, `copyQuotesToClipboard(anonymise)`, `getVisibleQuotes`) already supports it, so mostly wiring; today the web copy ships participant names with no anonymise affordance (privacy gap). (2) **Clips scoping**: user wants Extract Video Clips to honour scope (All/Selected/Starred) — blocked on the clips endpoint (`routes/clips_export.py start_clip_extraction`) taking only `anonymise`, no `quote_ids`; needs a backend param + a scope disclosure on the clips row. Spreadsheet stays "everything visible" (no scope) by decision. (3) **CLDR plurals** for the `copyScope*` labels — currently parenthetical "All ({{count}})" to dodge singular/plural; proper `i18n.pluralCategory` `_one`/`_other` across 7 `desktop.json` would read "All 1 quote / All 34 quotes". (4) **Anonymise in the menu bar** + retire the legacy `copyAsCSV` item (Quotes menu now has canonical Copy Quotes ▸ / Save as Spreadsheet ▸ / Extract Clips; anonymise-in-menu needs a shared persisted-flag decision since the popover's is per-open transient). (5) **Spreadsheet download robustness**: anchor-download fails silently on 404/401/500 and in Vite `--dev`/offline (no cookie/server) — blob-fetch-then-anchor with `res.ok`+toast, guard rows to serve-mode. (6) `extractVideoClips` error classification uses `msg.includes("422")` — fragile; thread typed `ApiError {status}` through `api.ts`. Review log: `docs/private/reviews/export-menu-parity.md`. **Per-lens export decisions (22 Jun):** Project/dashboard = **Export Report only**; Analysis = **Export Report only for now** (signal cards ride the self-contained HTML — no separate analysis export yet); Sessions = **"Reveal Transcripts in Finder"** — **built 22 Jun** in the export popover's Sessions lens (`revealTranscripts()` in `ExportPopoverContent`, native `NSWorkspace.selectFile` rooted at the transcripts dir; **menu-bar parity for it is a fast-follow** — popover-only today). The lean local-first primary (reuses the `revealInFinder` pattern; point at `transcripts-cooked/` if present — i.e. `--redact-pii` ran — else `transcripts-raw/`; user-facing label says "transcripts", NOT "cooked" which internally means PII-redacted), with a bespoke **Export Anonymised Transcripts** deferred (the display-name Anonymise toggle is a *different layer* from PII redaction, so an anonymised bundle isn't on disk and must be generated; also needed for cross-platform parity since Finder is macOS-only); Codebook = Export Report now, **Export Codebook (YAML, re-importable)** the one genuine new-artefact export worth doing eventually; Quotes = shipped set. **Organising principle:** for any lens whose artefact already lives in the output folder (transcripts, report HTML, clips, people.yaml, codebook), "Show in Finder" is the local-first default; a bespoke "Export…" only earns its place when it produces something NOT already on disk (anonymised / reformatted / re-bundled). **TF scope (22 Jun):** quotes (copy / CSV / XLSX) + transcripts + videos (clips) is "more than enough for a working researcher" — that's the TF export MVP. Of that set, only **Show Transcripts in Finder** is unbuilt (quotes/CSV/XLSX/clips shipped). Analysis/Codebook bespoke exports + anonymised-transcript bundle + the **HTML report improvement** itself are all explicitly **future work, post-TF**.

- **Detail-pane "can't show a report" states — design as a set** (18 Jun 2026) — Treat *all* the "I can't show you a report right now" detail-pane screens as one coherent family, designed together, not piecemeal (same spirit as the popover state catalog below, but for the detail pane). Today they're split across **two rendering systems with two visual languages**: the **Python serve status page** (`bristlenose/server/status_page.py:detect_status`) renders _No interviews to analyse yet_ / _Nothing to see here, yet_ / _Last run was cancelled_ / _Last run failed_; the **Swift native chrome** (`BootView.swift`) renders _starting sidecar_ / _loading report_ / _sidecar failed → installation corrupted + Retry_; and **`ProjectAvailability`** drives _can't-find volume (unmounted)_ + _cloud-evicted (iCloud)_. The **mid-first-analysis** case (run in flight, no report yet) currently falls through to "Nothing to see here, yet." — that's the during-run detail-pane handoff, now **demoted to Could / post-TF**: the sidebar ring + `RunProgressSubtitle` text already say "it's working," and a richer detail-pane progress surface is *not in the TF timescale*. Designing as a set surfaces the architectural call the during-run handoff already flagged — a boot/status surface is native chrome (per *data views → React SPA; native chrome → nav/status/boot*), so the set likely **consolidates the Python status-page states into native Swift surfaces** (one visual language, not two). **Design-first: enumerate + mock the whole family before any Swift.** Grounding: during-run spec at `docs/private/handoffs/progress-text-detail-pane.md` (folded into this set); state anchors are `status_page.py:detect_status` + `BootView.swift` + `ProjectAvailability`.

- **Pipeline popover state catalog + rolling-log direction** (8 Jun 2026, `26203e8`) — catalogued every desktop popover/status state with a surface-level **display-kind** taxonomy (codifies what already ships; designs nothing new) in `docs/design-pipeline-diagnostic-popover.md`. Surfaced a coverage finding: only the Ollama pill is live-invocable from `CommandMenu("Debug")`; the diagnostic popover is env-var + relaunch; everything else is real-condition-only. **Post-TF follow-up (deliberately undecided):** the `.running` popover flicks per-stage screens past unread on a fast run (the toast anti-pattern); the captured direction is an in-flight rolling-log / collapsing phase-itinerary reusing the settled MessageKind row vocabulary — see the doc's "Future direction" deferred appendix + the native-size mock `docs/mockups/pipeline-popover-rolling-log.html`. Implementation is a separate `/new-feature` pass that decides the appendix's open questions (accordion vs carousel, where legible phase names live, expansion policy). **Guardrail: reuse the settled icons/typography/MessageKind/diagnostic IA — do not relitigate.**

- **Desktop provider-resolution — one open item** — the ChatGPT end-to-end run and the CLI provider-default-model fixes shipped + verified (8–10 Jun). Still open: `ConsentActivation.resolve` flips a deliberate provider choice → Anthropic when its cached verdict isn't `.online` (`docs/private/handoffs/desktop-provider-resolution.md` defect 1). The Swift bare-model env tidy is hygiene, not a fix.

- **Real end-to-end install smoke — the "hello" test** (4 Jun 2026, ~2h) — when `bristlenose render` was removed, its 4 stale call-sites broke `Install & Smoke Test` for ~11 days (invisible because the CI monitor was watching the wrong workflow name — both fixed 4 Jun). The per-push install jobs were reduced to `--version` + `doctor` ("is it alive / are native deps present") — deterministic, zero-flake, but no real pipeline coverage. Deferred deeper test: generate a tiny ~2 s one-word video fixture (`say -o word.aiff "hello"` → ffmpeg to a small `.mp4`, commit it) and wire it into the **keyed, scheduled `full-run` job** for a true end-to-end transcribe→analyse→render. Deliberately **not** on every push, for two reasons we worked out: (a) full `run` needs an API key for the analysis stages, so it can only live in the keyed job; (b) a per-push Whisper-tiny *transcribe-only* is both flaky (model download + inference re-imports the exact CDN/download fragility class we removed on 4 Jun) **and** a non-representative slice — it skips the Claude analysis that is the actual product. Cheapest version: point `full-run` at the tiny video alongside the existing VTT fixtures, lenient transcript assertion. Optional bonus: de-`|| true` an `ffmpeg -version` check in the per-push jobs (deterministic native-dep gate). Context: `.github/workflows/install-test.yml`, `docs/design-ci.md` § Fragility classes.

- **Cassandra dependency pre-mortem — follow-ups** (4 Jun 2026) — the agent + `/cassandra` skill shipped (`0bbb1ca`); see `docs/design-dependency-premortem.md` + the ledger `docs/dependency-premortem-log.md` (Entry 1 = pre-mortem of the full outstanding bump wave; effectively *is* the overdue May-2026 quarterly dep review, minus the floor-pin bumps). Near-term: (a) Cassandra is now public (pushed 5 Jun 2026, `917565b`) — post the drafted friendly "inspired by you" issue on [`thoughtbot/dependabot-review-skill-thoughtbot`](https://github.com/thoughtbot/dependabot-review-skill-thoughtbot) pointing back to it; (b) the **lighthouse** major-ignore in `.github/dependabot.yml` still carries a stale "CI is on 20" rationale — CI is Node 24 and lighthouse 13 needs ≥22.19 (satisfied) — so either drop the ignore or correct the comment (a dep-policy call, deliberately left to you). Validate the prophecies: `/cassandra --score` can already mark **@playwright/test 1.60.0 (PR #110)** a real *hit* — it shipped and fixed the chromium-install hang. Longer-term: extract Cassandra into a standalone generalised OSS giveaway repo (~Sep 2026) — scheduled reminder set + memory `project_cassandra_standalone_extraction.md`; gated on scored ledger data + a v1.
- **Collab with [`llmfit`](https://github.com/AlexsJones/llmfit)** for "what local model should this hardware run?" (3 May 2026) — currently `OllamaCatalog.fits()` is a hand-rolled approximation: bundled curated list + memory thresholds + "recommended for this Mac" hint. `llmfit`'s whole job is that question. Two scopes: (a) reuse llmfit as a dependency to power the model picker (replace the curated list + hint logic), (b) closer collab — contribute Bristlenose's actual analysis-task profiles (long-context theme clustering, structured quote extraction) so llmfit's "fit" metric incorporates analysis quality, not just "will it load." Reach out to AlexsJones once we have a story to tell (post-alpha, when we have real user-machine data on what actually works for analysis runs vs just chat). Captured during sandbox-debug walk.

- **Post-TestFlight: adopt `mise` / `uv` / `just` per `docs/design-dev-environment.md`** (6 May 2026) — Phase 0 (skill-level desktop-binary symlinks) **landed 6 May 2026**; Phases 1–4 are post-cohort-feedback only. Don't open as a branch during the alpha sprint. The doc is the parking lot. One open chip flagged in the doc's "Codesigning vs symlinks" section: change `rsync -a` → `rsync -aL` in the xcodeproj `Copy Sidecar Resources` script so `models/` ships as real bytes, not a dangling symlink. Verify production sidecar path first — may be redundant.
- **Doctor "(bundled)" annotation on FFmpeg path** (2 May 2026, parked from `bundled-binary-helper` review) — `bristlenose doctor` reports the resolved ffmpeg path even when it's bundle-relative inside the .app. Honest diagnostic vs add a `(bundled)` suffix so TestFlight users aren't surprised by absolute paths inside their `.app`. Product call. Park until alpha tester feedback says it's confusing. Reference: `bristlenose/doctor.py:check_ffmpeg`
- **Merge `bundled*Environment(for:)` Swift helpers when a third lands** (2 May 2026, parked from `bundled-binary-helper` review) — `BristlenoseShared.sslEnvironment(for:)` and `bundledBinaryEnvironment(for:)` are called back-to-back at every spawn site (`PipelineRunner.swift`, `ServeManager.swift`). At three helpers the two for-loops become real boilerplate; consolidate into a single `bundledSidecarEnvironment(for:)` then. Rule of Three — wait for it
- **Bridge the 1.5 GB Whisper-model first-run download with something to do** (3 May 2026) — Mac Background-Assets path (and any equivalent on other channels) will start fetching the model after first launch, but on a slow connection that's many minutes of dead air before the user can transcribe. Don't let the app feel inert. Options to explore: a bundled sample project (real audio + canned transcripts/quotes) the user can poke around in to learn the UI; a guided tour of the report surfaces; "what's downloading and why" progress affordance that's visible but not modal; pre-flight prompts during onboarding ("import existing transcripts" path is fully usable without the model). Goal: buy minutes of valid product experience while the engine lands. Surfaces near `docs/design-desktop-python-runtime.md` Background Assets work.
- **Feedback pipeline → Bristlenose (internal dogfooding)** (17 Apr 2026) — IMAP fetch from feedback@bristlenose.app (DreamHost) → deterministic PII/header strip (Presidio + salted anon IDs for sender stability) → redacted `.md` archive in gitignored dir → monthly batch ingest into a private Bristlenose project to cluster themes for roadmap input. Read-only, never used as demo data, never shipped. Consent-safe because it stays internal. Caveats: emails are many short sessions (not few long ones) — may need a batch mode or synthetic "session per month"; no moderator questions so question-pill logic doesn't apply.
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

- [x] **May 2026** — Run `pip list --outdated`. Bump floor pins in `pyproject.toml` only if there's a security fix, a feature you need, or the floor is 2+ major versions behind _(prophecy 8 Jun 2026 via Cassandra Entries 1+2; execution 9 Jun 2026: security wave `5c96058` (presidio + cryptography 44→48, cleared 3 OSVs, floor bumped) + graduated-holds wave `e3c0a87` (starlette 1.x pair + WTForms 3.2 pair, dependabot config updated). Cassandra tally 4/4/0. Wave-3 greens deferred — see `docs/private/handoffs/dep-wave-3-greens.md`.)_
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

