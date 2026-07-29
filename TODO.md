# Bristlenose — Where I Left Off

Last updated: 28 Jul 2026. _This file is a capture inbox + session context, not a changelog — `git log` + `CHANGELOG.md` are the unabridged record._

**28 Jul 2026 — Cloud/storage policy DECIDED + a live read bug found.** Nine storage models worked through (iCloud sync, auto-tiering, per-project keep-local, Cloud Archive, File Provider extension, proxy/transcode, LRU budget, archive-as-truth, do-nothing); policy landed at **`docs/design-project-storage.md`** with a yes/no/maybe/avoid table (paired with **`docs/design-cloud-import.md`** — see below). Answer: **BN manages nothing** — no tiering, syncing, transcoding, evicting or deleting; it reads whatever folder it's pointed at and stays useful when media is absent. **The actionable half is a real bug, not a feature:** uncoordinated reads of *dataless* (cloud-evicted) files can fail with **`EDEADLK` / errno 35** instead of materialising — affects iCloud, OneDrive/SharePoint, Google Drive, Dropbox, Box, i.e. the modal researcher setup — and BN does uncoordinated `open()` + ffmpeg subprocesses with 30 s timeouts (so a fetch reads as a corrupt file) + blind `copyItem` (the known force-quit hang). Fix list: `NSFileCoordinator`-wrapped reads Swift-side / materialise-then-read Python-side; free-space precheck before a run + legible `ENOSPC`; never blind-copy a dataless source; stay useful when source media is gone (dogfood walk not yet done); make "missing after analysis completed" **neutral, not a warning** — today it nags the researcher for the one act that frees their disk. Also corrected two long-standing planning figures: a study is **~26 GB, not 500 GB+** (99% of corpora are 720p platform recordings at ~1.3 GB/hr, not 4K local screen captures), and "they can re-fetch from Teams/Zoom" expires (Teams default 60–120 days). Contradicts the "macOS materialises on read — the CLI is right to do nothing" line in `docs/design-desktop-project-status.md`; that doc wants truing. Same session: tempered the local-first/privacy framing out of `CLAUDE.md` + `docs/ROADMAP.md` (it isn't the stance, and "nothing is uploaded" is false — the analysis *is* an outbound LLM call).

**29 Jul 2026 — cloud-eviction bug REPRODUCED end-to-end; fix list is small and exact.** Real project on Dropbox, three 307–649 MB screen recordings, Make online-only, Analyse → **run fails** with `ffprobe timed out after 30s probing <file>` (red ✗ on the row). Control case — same project, files made available offline → runs clean. Only variable is residency; nothing wrong with cloud paths, sandbox, or pipeline. **The message means the opposite of what happened** — researcher reads "my video is broken", truth is "my file was still downloading". Evidence + recipe now in `docs/design-project-storage.md` §3 "Reproduced end-to-end". **Fixes, all small:** (1) `is_dataless()` pre-check (`os.stat().st_flags & 0x40000000` — cross-provider, works today) before ffprobe/open in [audio.py:48](bristlenose/utils/audio.py:48) + [audio.py:141](bristlenose/utils/audio.py:141) (the second *raises* `AudioToolError` and kills the run; the first only warns); (2) on dataless → report **info** "Fetching from <provider>…", **no wall-clock cap** (measured: 90+ s after requesting the fetch, zero bytes had landed — no timeout value works); (3) same guard before `copyItem` Swift-side (the known force-quit hang); (4) soft hint only after several minutes ("still fetching — is Dropbox running?") since BN cannot distinguish a healthy fetch from a stalled one. **Two structural findings alongside:** `.inCloud` is *unreachable* — [ProjectAvailability.swift:141](desktop/Bristlenose/Bristlenose/ProjectAvailability.swift:141) short-circuits on `fileExists` of the **folder**, which is true even when every file inside is evicted, so the cloud glyph can never appear for evicted media (explains "I've never seen it"); and [ProjectFolderWatcher.swift:228](desktop/Bristlenose/Bristlenose/ProjectFolderWatcher.swift:228) *already* calls `isCloudEvicted` per file and throws the answer away with `continue` — one line turns it into `evictedFiles` and gives whole-vs-partial for free. **Also:** the provider classifier [ProjectIndex.swift:650](desktop/Bristlenose/Bristlenose/ProjectIndex.swift:650) is an allowlist of three — **Google Drive and Box fall through to `.local`**; should match `~/Library/CloudStorage/` structurally and take the first path component as the label. **Progress is not observable and that's permanent** — Dropbox swaps files in atomically (measured ~50% on Finder's pie with `st_blocks` still 0), `percentDownloaded` is deprecated, `globalProgress` is per-provider aggregate → indeterminate spinner is the honest shape, never a ring. Detection itself is fine: `SF_DATALESS` and `ubiquitousItemDownloadingStatus`/`ubiquitousItemIsDownloading` all work **cross-provider** (verified on Dropbox, not just iCloud). Minor: the app's "Show details" panel shows three import-machinery frames and **no exception type or message** — the one line that matters only appears in the per-project log; that alone made this hard to diagnose.

**28 Jul 2026 — cloud import designed (nothing built, post-TF).** `docs/design-cloud-import.md`. **BN holds captured originals, never references** — a Teams/Zoom link can vanish, so pull the bytes and own the retention clock. Doesn't need a server: a user-initiated fetch is OAuth **public client + PKCE** (`ASWebAuthenticationSession`, Keychain refresh token — the Miro shape). **Teams is unusually clean:** non-channel recordings land in the *organiser's own* OneDrive `/Recordings`, and the researcher schedules the interview — so `Files.Read` (delegated, own data, user-consentable) covers the modal case with **no admin consent**, and Graph metering ended 25 Aug 2025. Never reach for `Files.Read.All` / `Sites.Read.All` (admin-only since Aug 2025 = the procurement gate the ICP avoids); never `drive.readonly` on Google (restricted scope → CASA, $500–4,500/yr) — `drive.file` via Picker instead. **v1 = `Files.Read` only:** list `/Recordings`, parse title+date from the filename, single-select, download into the selected project, store `driveItem` id + account per session (dedupe + retry + provenance, and **already-imported state belongs in v1** — it does most of v1.1's reliability work). v1.1 = multi-select + per-row outcome (reuse `partial`) + resumable. v2 = `Calendars.Read` for surname/@domain/description search + attendee roster — **which could retire the pre-PII-redaction speaker-ID LLM call** that `SECURITY.md` currently has to disclose. Then Zoom (Unlisted app, review), then Google (sensitive-scope verification). Key mechanics: calendar is the index (Graph can't filter by attendee → pull a window, filter client-side, instant type-ahead); read `expirationDateTime` per file and sort soonest-expiring so the list is a triage queue ("expires in 11 days" — MS expiry emails are now a per-tenant setting, so researchers may not be warned); 30-day default window; join calendar↔recordings so the list only offers meetings that have something to fetch (also stops BN holding a general diary). **Priority is the video file; transcript/roster/brief are gravy — and never substitute the platform transcript for Whisper** (real-time ASR, weak diarisation). Manual drag-drop stays first-class forever: organiser-owns-it breaks for guests in a client's tenant, which is a real freelancer case.

**28 Jul 2026 — a11y: verify the WKWebView is not a keyboard trap (menu escape REMOVED).** View ▸ Move Focus to Projects (⌘0) is gone, along with its whole chain — `.focusProjects` notification, `ContentView.focusProjectsList`, `firstSidebarTableView`, `focusLog` (~2.2k chars across 4 files). It existed as a "§10.1 keyboard no-trap" escape, but **a menu item is not an accessibility affordance** — a keyboard user stuck in the web view will not discover the fourth row of the View menu, and WCAG 2.1.2 asks for "unmodified arrow or tab keys, **or other standard exit methods**", which means the platform's own (⌃F6 / ⇧⌃F6 pane cycling, ⌃F2 menu bar, Tab exiting at document end) — not a bespoke command. ⌘0 went to **Actual Size**, which is what every Mac app binds it to and what this file already documented as WebKit's own meaning. **The task this leaves:** with Full Keyboard Access on (⌃F1), Tab into the report and confirm ⌃F6 and Tab both escape the WKWebView back to the sidebar. If they don't, the fix is the window's **key-view loop** (`nextKeyView`, ensuring the sidebar `NSOutlineView` is reachable), not another unread menu row. Tell that the old item was papering over this: its implementation carried a "no sidebar table view (collapsed?) — focusing content view" fallback and warning logs, which is a workaround's shape, not a design's. Also now orphaned: `desktop.menu.view.moveFocusToProjects` across 20 locales.

**28 Jul 2026 — Check Health wired → native Health window.** New serve endpoint `GET /api/doctor` (bearer-authed, deliberately NOT auth-exempt — exposes env detail; runs `doctor.run_local_checks`, the local non-network subset) feeds a native `DoctorReportView` (`health` Window scene, `.commandsRemoved()`), opened from Diagnostics ▸ Check Health via `openWindow(id: "health")`. Committed: backend + view + BristlenoseApp scene + tests + two trued design docs (`99c95551`). **Two pieces left uncommitted, entangled with the in-progress menu-icons branch — land them there:** (a) the `openWindow` menu-wiring line in `MenuCommands.swift`; (b) the orphaned `desktop.menu.app.checkHealth` key removal across 20 locales + the `fix-the-menus.md` update. **Deferred follow-ups (noted in `docs/design-diagnostics-menu.md`):** an async pass to surface the network-bearing checks (API-key validation, reachability, Ollama probe) the endpoint currently skips; and native-only checks (Keychain access, sandbox entitlements, bundle integrity) this window is the future home for. Minor: the `fix` text is CLI-flavoured (`get_fix()`) — accepted for v1.

**26 Jul 2026 — dead-code / vestigial audit (catalogue only, nothing deleted).** Five parallel agents swept Python · frontend · theme · desktop · cross-cutting for deletable tails after the old-toast find. Highest-confidence, zero-risk deletion sweep queued: **(1) old-toast lineage** — `AutoCodeToast.tsx` + `AutoCodeReportModal.tsx` (both never mounted, superseded by ActivityChip / ThresholdReviewModal) + `atoms/autocode-toast.css` (never served) + 6 `autocode.report.*` locale keys ×20; **(2) frontend orphans** — `AboutDeveloper.tsx`, `useAppNavigate.ts`, `getColorTheme`, 4 dead `api.ts` fns; **(3) Python** — `output_paths.py` static-linking block (4 fns) + `_ensure_index_symlink`, zero-ref helpers in `text.py`/`timecodes.py`, unwired config `whisper_device`/`merge_speaker_gap_seconds`; **(4) repo cruft** — root PNGs (`overlay-mode*.png`, `push-*.png`), `interviews.png`, `bristlenose-todo-summary.md`, `scripts/populate-gh-project.py`, `scripts/compare-render.sh`; **(5) spike** — `scripts/spike_discussion_routing.py` + its 2 prompts (confirm the discussion-routing spike is abandoned first — new untracked files). **Two decisions, not mechanical:** desktop AppKit-vs-SwiftUI sidebar split (+ reconcile the `desktop/CLAUDE.md` contradiction: code defaults to SwiftUI, doc claims AppKit shipped); and the inert `focus-change`/`undo-state` bridge handlers (wire the missing JS emitters, or delete + the now-permanently-disabled desktop Quotes/Edit menu items). Docs half already trued this session (`0be5e712`). Also flagged but out of `--topic` scope: `CLAUDE.md:216` + `DEVELOPMENT.md:200` still call `design-react-migration.md` the "active migration plan" — it's complete; fix via `/true-the-docs --claude-pointers`.

**16 Jul 2026 — 🐟 stage-2.5 `.dmg` LIVE.** First notarised Developer-ID `.dmg` cut, shipped, and validated end-to-end: download from **bristlenose.app** → clean *"Apple checked it"* Gatekeeper (source=Notarized Developer ID) → launch → full analysis (IKEA project, 28 quotes / 3 themes). Signing spike solved + documented: a sandboxed app + Keychain-Sharing entitlement forces a provisioning profile, so forcing Developer ID at *archive* fails — the working flow is archive dev-signed → export Developer-ID with `-allowProvisioningUpdates` (Xcode auto-mints the profile, no portal). Mechanics in **`docs/design-dmg-build.md`**; `release.md` trued (bump-version.py flow + mandatory gates + desktop channels). Cert minted via Xcode ▸ Manage Certificates — **back it up as a `.p12`** (login-keychain password had diverged; the private key is the only unrecoverable piece). **Open follow-ups:** (a) website git commit is entangled with a concurrent docs-overhaul session — left for that session (CTA is live + on disk); (b) **atomic scp upload** (temp name → `mv`) so a future cut never serves a partial file mid-upload (a naive re-download hit "disk not readable"); (c) **unified release doc** + the critiqued **`cut-a-release --patch|--minor` skill** (map all 5 channels — PyPI · Homebrew · Snap · `.dmg` · TestFlight; the doc is the honest prerequisite).

**14 Jul 2026 — 🐟 TF-1 DELIVERED.** First TestFlight build accepted by App Store Connect: **0.20.0 (2068)**, 223 MB model-less `.pkg` (large-v3-turbo downloads on first transcribe), "ready for internal testing", now in Apple processing. Cleared ASC validation after three nested-signing fixes (app-sandbox on sidecar/ffmpeg/ffprobe; `org.python.python` framework re-sign; `LSApplicationCategoryType`). Build/signing already merged into **local main** (`ed5ef885`) — `testflight-prep` branch is spent. Local main is ~26 commits ahead of `origin/main`, **all unpushed**: pushing main publishes the App Store signing config (sandbox flip, ASC fixes, entitlements) to the public repo — a launch-narrative call, not a routine push. First tester (Paul) invited. **Next TF work is no longer "upload" — it's add remaining testers + run cohort-feedback calls.** Whisper delivery decided = Background Assets (essential tier); brief at `docs/private/handoffs/background-assets.md` for the parallel branch. PII/Presidio stays post-TF.

**11 Jul 2026 — v0.20.0 shipped (incremental builds).** Curation survives re-analysis (freeze marked quotes, membership-based section identity, star-anchored theme names, dismissible "New" badge); desktop loose-file intake + incremental add (drop / File→Add Files ⇧⌘A) + run recovery; native feedback sheet; sessions-journey deep-links; Shoal adaptive count. Bumped 0.19.0→0.20.0 (feature release = minor bump; convention now in CLAUDE.md). Live on PyPI + brew. **Desktop half reaches the cohort only with the next bundled-sidecar build — not yet done.**

**7 Jul 2026 — Acceptance-testing tier (Phase 1).** All test docs under `docs/testing/` (hub + `coverage-inventory.md`); built format-coverage + invariant harness + lens smoke (`bc5a036a`, folded into 0.20.0). Open: real Teams/Meet `.docx` parity fixture; firing local/cloud provider cells (`run_matrix.py --run-local` free / `--run-cloud` = keys+spend); `launchd` nightly wrapper (Phase 3).

**Launch plan:** `docs/private/100days.md` — triaged by topic + MoSCoW priority. That's the source of truth for what ships. This file is a public capture inbox + session context — antechamber for untriaged items only; promote to the plan doc once triaged.

---

## Next session focus

Sprint schedule (S1–S6) ended 30 Jun. **Internal TF is now LIVE — build 0.20.0 (2068) delivered 14 Jul** (#3 sandbox flip, #10 ASC record, #12 first upload all done; see the dated milestone above). Active focus shifts from "get to TF" to **run the cohort**: once Apple finishes processing, add the remaining 4 UXR friends' Apple IDs (Users & Access → Internal group) and schedule the walks-fix-walks cohort calls per `docs/private/100days.md` §cohort-call-protocol.

Immediate ladder: (1) **wait for Apple processing** → confirm build appears under TestFlight → Internal; (2) **add remaining testers + invite**; (3) **cohort calls** (Paul first / friendly-CTO track). In parallel, the **Background Assets branch** (whisper essential-tier delivery) can start slow off `docs/private/handoffs/background-assets.md`. Orthogonal small win: **Opus 4.8 P2** (price the Opus row, current-gen the picker `"Opus 4"→4.8`) — overdue since ~18 Jun, TF-non-blocking; verify the catalogue still says "Opus 4" first.

---

## Ideas (captured, not triaged)

- **Thinking-shimmer: native sidebar line needs an Xcode build-verify; help copy + tuner wiring pending.** 25 Jul 2026: the web half shipped + verified (`560a0cf4`) — activity chip label shimmers (`atoms/shimmer.css`, two-gate: `prefers-reduced-motion` + `data-analysis-animation`), spinner removed, CSS chip at 20% contrast, toggle bridged native→web. The native sidebar `.running` status-line shimmer (`SidebarShimmerText.swift` + `ProjectSidebarOutline` wiring, at 5%) **compiles clean** (verified via isolated `xcodebuild`, 25 Jul); the only remaining check is the **visual read** — does it shimmer and stay consistent light/dark on a running row — which needs a live run in the app. Follow-ups: (a) broaden the `showAnalysisAnimation` help copy (currently shoal-only) across the 20 locales once native lands; (b) the Debug▸Shimmer Tuner menu wiring (`MenuCommands`/`BristlenoseApp`/`ShimmerTunerView`) stays **uncommitted** — entangled with the Keycap Gallery debug window, commit with that batch. Spec: `docs/design-motion.md` §4.7.1.

- **Boot progress bar is silent to VoiceOver.** 25 Jul 2026: `BootView` progress phases were stripped to just the indeterminate bar (removed the "Bristlenose" wordmark / tagline / "Starting…" text that redundantly re-branded on every project switch in the embedded Mac context). With the visible text gone and no replacement label, the bare `ProgressView` announces nothing to VoiceOver — the app-wide convention is an explicit `.accessibilityLabel` (cf. `OllamaDownloadPill`/`StatusPill`). Deferred per the "bar UX comes later" steer; add a label (reuse the existing `desktop.boot.startingSidecar`/`loadingReport` strings) when the bar gets its next pass.

- **`configure azure` still punts endpoint+deployment to manual `.env`.** 21 Jul 2026: `configure <provider>` now file-persists the API *key* on a keyring-less box (`59e3770c`), and env-var reads accept the SDK-native names (`dd76725e`, incl. `AZURE_OPENAI_ENDPOINT`/`AZURE_OPENAI_DEPLOYMENT`). But `configure azure` only stores the key — it prints the endpoint/deployment as a "add these to .env yourself" hint (`cli.py` azure branch). To fully close the loop like the other providers, `configure azure` would prompt for endpoint+deployment and persist all three to the config `.env` (needs a generic "write arbitrary var" path on `FileCredentialStore`, or reuse the existing upsert). Low alpha priority (Azure is enterprise; `docs/design-cli-provider-selection.md`). The `ProviderSpec.config_fields` registry in `providers.py` already declares these fields — an interactive `configure` could iterate them generically instead of the current hardcoded per-provider branch.

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
| `docs/design-discussion-lens.md` | Discussion lens — project quotes onto the researcher's guide by territory; macOS-only. Design + routing spike; feature unbuilt |
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

