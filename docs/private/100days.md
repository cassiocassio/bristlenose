# Bristlenose — 100-Day Launch Inventory

**Launch: 30 June 2026 · Mac App Store · Beta · $TBD/month**

Gathered from: TODO.md, ROADMAP.md, 37 GitHub issues, 20+ design docs, 6 CLAUDE.md files, 5 active branches, source code TODOs.

MoSCoW within each category. **100-day goal: complete every Must.**

**Icebox** sits below Could in sections that have entries. These are ideas with merit that we're deliberately not pursuing in the 100-day window — parked, not deleted. On the GitHub Projects board, Icebox is a column to the right of Done.

### Sprint schedule

Items tagged `[S1]`–`[S6]` are assigned to a sprint. Untagged items are unassigned. Synced to the [GitHub Projects board](https://github.com/cassiocassio/bristlenose-delivery) via `/sync-board`.

| Tag | Dates | Theme |
|-----|-------|-------|
| ~~[S1]~~ | ~~14–25 Apr~~ | ~~Start the clocks~~ ✅ **Done 17 Apr 2026** (8 days early; succession plan deferred beyond 100days) |
| [S2] | 28 Apr–9 May | Road to alpha — A/B interleave sandbox + MVP flow, CI cleanup first |
| [S3] | 12–23 May | Multi-project |
| [S4] | 26 May–6 Jun | First-run + export |
| [S5] | 8–19 Jun | Visual design + a11y |
| [S6] | 22–30 Jun | Launch prep + public legal |

**Sprint 2 re-scope v3 (17 Apr 2026).** Alpha path decided: **internal TestFlight, not `.dmg`.** Sandbox work is unavoidable (StoreKit needs it), and a `.dmg` path would be throwaway code. Doing it now gets us a modern sandbox-aware codebase from the start. Rejected items: Developer ID cert, `.dmg` build pipeline, Gatekeeper README (all struck in §11 Operations). See `docs/private/road-to-alpha.md` for the full 14-checkpoint path.

**Sprint 2 cadence — A/B/C interleave (updated 29 Apr 2026).** Three parallel tracks per `docs/private/sprint2-tracks.md`. **Track C ✅ closed 28 Apr** (C2 signing, C3 Keychain-in-sandbox, C4 Privacy Manifest, C5 supply chain — `Bristlenose.pkg` App-Store-Connect-ready). **Track B happy path ✅ shipped 26 Apr** via `port-v01-ingestion` (commit `e781ebe` → v0.15.0 — broader than predicted: ingestion + multi-project core + lifecycle); first-run polish remaining on `first-run` worktree (started 29 Apr). **Track A in progress** on `sandbox-debug` worktree (started 29 Apr). Tracks converge at first TestFlight upload (#12). Cross-channel component strategy in `docs/design-modularity.md` — what's bundled, what's Background Assets, what's CLI-only, no-fork principle. Alternate sandbox/signing steps with MVP flow / UI quality steps. Each step unblocks the other: sandbox work surfaces UI regressions (folder bookmarks, temp paths); UI work exercises the sandboxed paths. Order:

1. ~~**Clean up CI** — re-enable the E2E gate (3 parked P3 regressions), land the perf regression gate. Unblocks everything else.~~ _Done 18 Apr 2026 (ci-cleanup branch): gate flipped, 3 regressions cleared (autocode 404 allowlisted, codebook 404 allowlisted as deferred-fix to S3, auth-token wired). Plus `e2e/ALLOWLIST.md` register, Analysis page button fix, SECURITY.md honesty update, `bristlenose doctor` env-bleed check. CI passed first try post-flip (19m44s). Option B auth-token gate deferred with design plan + reminder 16 May. Python floor bump to 3.12 tracked §11 Should + reminder 9 May._
2. **A/B/A/B through S2:**
   - A: sandbox step (one entitlement + related code migration at a time)
   - B: MVP flow step (one beat of §1a below at a time)
   - Repeat. Ship nothing to friends until MVP 1-hour flow is green AND sandboxed build runs end-to-end.
3. **First TestFlight upload** lands when both tracks are green. May slip into S3 — that's fine, deadline is MVP quality, not calendar.

**Real QA = IKEA study + CLI handholding on video calls with UXR friends.** TestFlight is the delivery mechanism; video-call UXR sessions are the feedback loop.

Performance: stress sweep shows clean linear scaling to 3000 quotes — virtualisation deferred to Icebox. AI disclosure dialog: already shipped (`AIConsentView.swift`). Solicitor contact: still May (external TestFlight and public legal paperwork are S6+, not alpha-blocking).

---

## 1. Missing — essential feature gaps ("it's not done without it")

### Must
- [S1-S5] **IKEA codebook validation dataset** — 5 moderated IKEA interviews with UXR friends (favours, not schedulable). ~1/week over S1–S5. Tests whether sentiment categories, UXR codebook (moderator questions, friction, sentiment), and thematic grouping produce useful results on real research data. Also provides marketing screenshots and speed demo video. (design-real-data-testing.md)
- **~~Desktop app v0.1~~** — SwiftUI shell, PyInstaller sidecar, folder picker, pipeline runner, "Open Report" button. ~365–435 MB bundle. (design-desktop-app.md)
- ~~**Export: standalone HTML from serve mode** — `POST /api/projects/{id}/export`, self-contained HTML. Shipped v0.11.2. (design-export-sharing.md)~~
- [S4] **Export: research package (zip)** — zip with report.html + transcripts/ (.txt with inline timecodes) + clips/ (optional, FFmpeg). Human-readable filenames (`p1 03m45 Sarah onboarding was confusing.mp4`). Anonymisation across all surfaces. Replaces 3 hours of Final Cut Pro work. Stages 1–3 of export roadmap. (design-export-sharing.md)
- [S3] **Multi-project support** — home screen, project list, create/switch without restart. Milestone 4 in ROADMAP. Design docs: `docs/design-project-sidebar.md` (5-phase plan), `docs/design-multi-project.md` (infra/DB/architecture). Phase 1 prompt: `docs/private/prompts/phase1-project-sidebar.md`
- **~~File import (drag-and-drop)~~** — add recordings to project from GUI. Milestone 5. Needs design doc
- [S3] **Duplicate folder drop warning** — when dropping a folder that matches an existing project's path, show dismissable warning with "Duplicate of \<project\>" — allow it (user may tag/analyse differently) but flag the likely mistake
- [S3] **Slow-double-click rename in sidebar** — Finder-style slow double-click to inline rename. `simultaneousGesture(TapGesture())` and `onTapGesture` both break List selection on macOS 26. Needs NSEvent monitor approach or AppKit subclass. Rename still works via right-click and Project menu
- [S3] **Multi-select projects (Shift/Cmd click)** — change `List(selection:)` from `UUID?` to `Set<UUID>`. Detail pane shows "3 projects selected". Enables bulk delete via right-click, and drag-to-folder in Phase 3. Prerequisite for drag-to-reorder
- [S3] **Drag-to-reorder projects in sidebar** — persisted via `position` integer in project index. Needs multi-select first. Phase 3 in design doc
- [S3] **Drop-on-existing-project row** — add interviews to existing project via drag. Data model ready (`addFiles`). Needs `DropDelegate` hit-testing on List (per-row `.onDrop` breaks selection on macOS 26)
- [S3] **UTType validation on drop** — filter dropped files to accepted media types (audio, video, subtitle, docx, txt). Currently accepts any file
- [S3] **Empty state drag target** — `ContentUnavailableView` as `.onDrop` target when project list is empty
- **~~Run pipeline from GUI~~** — "Analyse" button, background task, progress streaming. Milestone 7. Needs design doc
- **~~Settings UI~~** — provider selection, API key entry, redaction toggle, model choice. Milestone 6. Needs design doc. Currently CLI-only config is a hard block for App Store users
- [S4] **App Store subscription infrastructure** — StoreKit 2, receipt validation, entitlement check. Not yet designed
- **~~Auto-serve after run~~** — pipeline finishes → auto-launch serve + open browser. (TODO.md immediate)
- **Subprocess lifecycle / orphan management** — make orphan handling invisible to the user. PID-file-based scan-and-reconcile at app init for both `bristlenose run` and `bristlenose serve`; sandbox-clean (`proc_pidinfo` / `proc_pidpath` instead of `lsof`/`pgrep`). Replaces today's serve-only `lsof`-based cleanup. Required before sandbox flips on for TestFlight. Surfaced during port-v01-ingestion QA. Design: `docs/design-subprocess-lifecycle.md`. Estimated ~2 days. _(24 Apr 2026: Stop-is-a-lie + stale-pill alpha blockers shipped — 4 commits 896c074..da5cc45. Owned- and orphan-path cancel both ack instantly via `isStopping`; orphan-path SIGINT→SIGTERM→SIGKILL escalation; orphan-attach popover tails `bristlenose.log`. Sandbox-clean probes + `stopAll()` still TODO.)_
- ~~[S2] **Alpha telemetry — Phase 1 plumbing**~~ — `/api/health` advertises `telemetry: {enabled, url}`; dev-only `POST/GET/DELETE /api/dev/telemetry` stub with Pydantic validation, 500-event batch cap, PID-scoped JSONL; `website/telemetry.php` + moved `website/feedback.php` with `hash_equals`, placeholder-token guardrail, CSV cell-safety helper. Reviewed (3 agents, 8 mechanical findings fixed, 8 design-questions parked). Done 26 Apr 2026 (alpha-telemetry branch, 6 commits). PHP files NOT yet deployed to bristlenose.app — `/deploy-website` only when Phase 2 starts so the URL the health endpoint advertises actually resolves
- **Alpha telemetry — Phases 2–4 (deferred to post-TestFlight)** — TestFlight tester feedback path is video-call + UX observation, not instrumented data; alpha telemetry can wait without losing the testers (they don't notice it's missing). Deferred 26 Apr 2026 to keep the TestFlight runway clear of feature-creep. Pick up after first TestFlight cohort reports back. Open work: (2) Python — `TelemetryEvent` SQLite table + Alembic migration, `POST /api/telemetry/events`, background batched shipper, `bristlenose/llm/prompt_version.py` + `prompts/versions.jsonl` sidecar. (3) React — emission hook on suggest/accept/reject/edit, 2 s debounce collapse rule, `edited` as flag not offset. (4) Swift — Sheet 2 telemetry opt-in (verbatim from spec §First-launch sheets), Keychain UUID helper, sidecar env-var injection (`BRISTLENOSE_RESEARCHER_ID`), Settings → Privacy screen. Four architectural questions + eight parked `/usual-suspects` findings — full context in `docs/private/alpha-telemetry-next-session-prompt.md`. Methodology spec stays on main as the plan; absence of in-alpha data means the first Substack piece pushes to second cohort, not first

### Should
- **Desktop toast infrastructure** — SwiftUI toast overlay (auto-dismiss, fade). Needed for "Added N interviews to project", archive undo, and future feedback. Reference: `frontend/src/components/Toast.tsx`
- **Add interview flow (serve mode)** — dashboard/sessions list "Add interviews" button → file picker → re-process. CLI route: `bristlenose add <files> <project-folder>`. Both need toast confirmation
- **Session enable/disable toggle** — exclude sessions without re-running pipeline. Option A (`is_disabled` bool). (design-session-management.md)
- **~~Incremental re-run~~** — add new recordings, preserve researcher work. Milestone 8. Quote stable key already in place
- ~~**Left-hand nav content for all tabs** — signal cards, speaker badges, codebook titles, sessions list, analysis views in left sidebar~~
- **~~Standard modal with nav for Settings and About~~** — consistent modal pattern, consider unifying help + about
- **New title bar design** — current title bar needs refresh
- **Post-analysis review panel** — non-modal, dismissable panel after pipeline completes: name correction, token summary, coverage overview

### Could
- **Batch processing dashboard** — queue multiple projects (#27)
- **Custom prompts** — user-defined tag categories / analysis instructions
- **`.well-known/apple-app-site-association`** — Universal Links so `bristlenose.app/...` URLs open in the desktop app. Needs bundle ID + team ID from Apple Developer account

### Won't (100 days)
- **Windows app** — winget installer (#44), Windows credential store
- **In-app report viewing (WKWebView)** — defer to v0.2 desktop
- **Multi-page report** — tabs or linked pages (#51). Large effort, defer post-launch
- **Project setup UI for new projects** (#49) — large effort, defer post-launch
- **.docx export** — Word document output for sharing with stakeholders (#20)
- **Published reports** — Cloudflare R2 hosted sharing. Phase 2–3 of export
- **Person linking** — cross-project identity via `person_links` table in instance DB (same/not_same link types, transitivity, canonical person display). Folder-scoped only — no cross-folder linking (security review CRITICAL). Requires instance DB, UUID migration, encryption. (design-multi-project.md §2, §3c)
- **Cross-project search** — folder-scoped quote/tag/participant search across project DBs. FTS5 per-project, no central index. Speaker codes by default, not display names. (design-multi-project.md §3b, §3c Finding 5)
- **Project archive/restore** — active→archived→reopened lifecycle. Schema fields (`archived`, `previous_folder_id`) included from start. Flat archive section, folder-level archive, un-archive with folder restore. (design-multi-project.md §3a)

### Icebox (100 days)
- **Miro bridge** — Miro-shaped CSV export → API integration → layout engine. CSV export works as stopgap. Killer feature - Resuresct for move out of beta! See `docs/private/design-miro-bridge.md`
- **Spring-loaded folders during drag** — open folder on hover during drag. SwiftUI List doesn't support natively; needs timer or NSEvent monitor. Low priority — "Move to" submenu covers the use case
- **iPad companion (read-mostly thin client)** — post-alpha. Mac runs the pipeline as today; iPad syncs quotes/stars/tags/hidden state from a per-subscriber cloud workspace. "Workbench → reading chair" — sofa skim of the 15% of quotes that matter, star-favourite pass on iPad, edits flow back. Text+audio-proxy sync is small; video originals stay on the Mac (or optional 480p HLS proxy). Subscription funds the relay rather than GPU time. Pairs with the broader cloud-tier framing: differentiator is "you pick the LLM, you can leave anytime with a self-contained HTML", not "bytes never leave the device". Discussion 30 Apr 2026.

---

## 1a. MVP 1-hour human session flow (S2 focus)

The canonical end-to-end beats a first-time user must complete successfully in the Mac app before we ship to anyone. Each beat that doesn't work in the current build becomes an S2 item.

1. **First-time open** — app launches, window shows a welcoming empty state
2. **AI disclosure sheet** — shown, acknowledged, dismissed (shipped: `AIConsentView.swift`)
3. **Set up Claude API key** — Settings → paste key → saved to Keychain → validated
4. **New project** — create a project (folder picker or named project)
5. **Drop interview folder** — drag-and-drop a folder of recordings/subtitles onto the project
6. **Process** — pipeline runs, progress visible, completes without crashing
7. **Display** — report opens, quotes render, transcripts navigable
8. **Add a codebook** — import or create a codebook, apply to project, quotes re-tagged
9. **Investigate signals** — dashboard signal cards clickable, lead to relevant quotes
10. **Use stars and filtering** — star quotes, filter by tag/star/sentiment, filters stick
11. **Export credible report** — standalone HTML export, opens in browser, looks shareable
12. **Export video clips** — FFmpeg stream-copy produces human-named clips from starred quotes
13. **Export CSV** — quotes export opens in Excel, columns sensible, no broken characters; Miro paste works

**S2 exit criterion:** Martin can run this flow on a laptop with no API keys pre-configured and no cached state, from new, in under an hour, and produce a report he'd send to a UXR friend without apologising. Everything below §2 Broken that blocks any step above gets promoted into S2 implicitly.

> **Beat status as of 29 Apr 2026** — beats 1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13 reachable end-to-end via `port-v01-ingestion` (26 Apr). **Still open:** beat 3 — Settings + Keychain shipped (`LLMSettingsView.swift`, `KeychainHelper.swift`) but no live API roundtrip validation; beat 3b implicit — Ollama detection rich on Python side (`bristlenose/ollama.py`) but Swift UI doesn't surface install method / auto-start / model picker. Both gaps are scoped on the `first-run` worktree.

---

## 2. Broken — doesn't work as designed

### Must
- **~~Dark mode selection highlight~~** — invisible in dark mode (#52)
- [S5] **Dark logo** — placeholder inverted image, needs proper albino bristlenose pleco (#18, logo.css HACK)
- **~~Circular dependency in production build~~** — fixed in 0.13.6 but regression-prone (SidebarStore import cycle)
- [S3] **Import FK constraint** — fixed in 0.13.4 (ProposedTag cleanup) but needs E2E coverage to prevent regression
- [S3] **Native toolbar tab i18n not reactive** — changing language in Settings doesn't update toolbar labels until app restart. `I18n` `@StateObject` doesn't trigger segmented control re-render


### Should
- **Create canonical design doc for first-run flow** — Beat 3/3a/3b shipped `AIConsentView.swift` (~240 lines), `OllamaSetupSheet.swift` (~330 lines), and the `ContentView` welcome detail-pane (`4772c3a`) but none of the existing design docs (`design-desktop-app.md`, `design-multi-project.md`, `design-project-sidebar.md`, `design-desktop-settings.md`, `design-keychain.md`) is the canonical home for the first-run flow as a single thing. New `docs/design-first-run-flow.md` should cover: consent gate (`ContentView.swift:267-272, 343-346`), consent re-access (Bristlenose menu > AI & Privacy…), `AIConsentView.currentVersion` policy, consent-log audit (`UserDefaults` `consentLog`), `OllamaSetupSheet` state machine (idle/installingOllama/waitingForDaemon/downloadingModel/finishing/failed), HTTP-only daemon probe, ordering invariant (consent BEFORE prefs notification), welcome detail-pane home view. Surfaced by 30 Apr 2026 truing pass.
- **Translation catch-up pass — first-run desktop screens** — `LLMSettingsView.swift` and `OllamaSetupSheet.swift` ship with ~30 hardcoded English strings on the first-run path (Beat 3 + 3b, 30 Apr 2026, `first-run` branch). Plan: machine-translate as good-enough first pass before alpha (subsumes Finding 39 from settings-ui review log) + glossary discussion for any new vocabulary (status labels, install copy, error catalogue). Same pass cleans up unused `chrome.noProjectSelected` / `chrome.selectProject` keys in 6 locales. Ja-locale gap is the longest pole: `ja/desktop.json` has ~53% empty values pre-existing, including `aiConsent.useOllama` + `aiConsent.ollamaCallout` which collapse the alt-AI path to invisible for Japanese users. If not done in time for alpha: pull ja from the locale picker.
- **AIConsent sheet rewrite for clarity + simplicity** — alpha→beta polish window. Current sheet has 6 sections + 2 buttons; "Researcher responsibility" copy at the bottom probably never read. Plan: fold into a Learn more disclosure, shrink to disclosure + decision. (Finding 50 from settings-ui review log, 30 Apr 2026.)
- **Local model reliability** — ~85% vs ~99% cloud. Investigate parse failure patterns (llm/CLAUDE.md)
- **Speaker diarisation** — cross-session moderator linking not working (#25, #26) — single-session detection improved (LLM splitting, generalised heuristic, format-agnostic prompt, Apr 2026). Cross-session linking remains. See `docs/design-transcript-speaker-editing-roadmap.md` Layer 11
- **Badge × character** — platform-inconsistent rendering, replace with SVG (badge.css TODO)

### Could
- **Edit writeback to transcript files** (#21) — edits only persist in DB, not source files
- **Word timestamp pruning** — unused data accumulates after merge stage (#35)
- **E2E regressions parked during v0.14.5 release unblock (17 Apr 2026)** — set `continue-on-error: true` on the e2e CI job to ship v0.14.5. Cleared on `ci-cleanup` branch (18 Apr 2026) via targeted allowlists + CI env-var wiring; e2e gate flipped back to blocking. One item deferred to S3 (root-cause fix, not the allowlist).
  - [S3] [CI-A4] **Unknown subresource 404 on `/report/codebook/`** — Playwright console spec catches a 404 but `msg.text()` truncates the URL. Local `curl` of the page + all listed assets all return 200; some runtime subresource fails. Need to run the e2e locally with trace viewer and check Network tab to identify. Likely a route-chunk prefetch, a missing thumbnail in the smoke fixture, or a font. User impact: cosmetic (devtools only). **Allowlisted in `e2e/tests/console.spec.ts` during `ci-cleanup` branch (18 Apr 2026) — see `e2e/ALLOWLIST.md` CI-A4; root-cause fix deferred to S3 when we're back in the frontend.**
  - ~~**"Show all N quotes →" links on Analysis page have no href/click handler**~~ — resolved (18 Apr 2026) during `ci-cleanup` branch. Surfaced a 4th hidden regression that was sailing past the `continue-on-error` gate. Fixed at the source: converted the `<a>`-with-no-href to a proper `<button type="button">` in `AnalysisPage.tsx` with minimal CSS reset in `analysis.css`. `test.fixme` placeholder in `e2e/tests/links.spec.ts` removed. Previously reported as "only reproducible with project-ikea"; turns out the smoke fixture also produces signal cards with these links.
  - ~~**Autocode status endpoint 404 is noisy**~~ — resolved (18 Apr 2026): kept REST semantics (404 = no job for this framework), allowlisted in `e2e/tests/network.spec.ts` with a pointer to `CodebookPanel.tsx:609`'s null-tolerant consumer. Frontend already treats 404 as idle.
  - ~~**perf-gate.spec.ts server identity guard: `_BRISTLENOSE_AUTH_TOKEN` env var not wired into CI**~~ — resolved (18 Apr 2026): `_BRISTLENOSE_AUTH_TOKEN: test-token` added to the main e2e job's `env:` block. Server already honours the env var at `app.py:96` (no code change needed on this branch; the env-override is tracked as a future hardening task — see §6 Risk Should).
  - See session transcript "fix release pipeline + main CI, step by step" (17 Apr 2026 wrap-up) for full investigation notes, curl proofs, and file:line pointers.

---

## 3. Embarrassing — too ugly to ship

### Must
- [S5] **Typography audit** — 16 font-sizes → ~10 with proper tokens (ROADMAP theme refactoring)
- [S5] **SVG icon set** — replace character glyphs (delete circles, modal close, search clear) with proper icons. Candidates: Lucide, Heroicons, Phosphor, Tabler. See `docs/design-system/icon-catalog.html`
- [S5] **Visual redesign: FT.com-level typographic legibility** — larger margins, fainter keylines, edo colours, more white space. FT.com as benchmark for large volumes of intense type with enough space to parse and scan
- [S5] **Colour themes** — named themes (e.g. "edo") as appearance switch. Beyond custom CSS — curated, designed themes. Needs design doc first: `docs/design-themes-and-schemes.md` — establish nomenclature (Theme = structure (font/spacing), Colour scheme = palette), file organisation, selection mechanism (CSS class? data attribute?), how Edo fits. Also investigate `--bn-selection-bg-inactive` dark value (#262626) too close to page bg (#111111)
- [S5] **Grid, spacing, type, colours audit** — holistic visual fit-and-finish pass
- [S3] **Tag density** — AI generates too many tags, overwhelming (#12)
- - **~~Logo size~~** — 80px feels tiny, increase to ~100px (#6)
- **~~Responsive quote grid~~** — Phase 1 CSS-only, design ready, not implemented (design-responsive-layout.md)
- ~~**Help modal polish**~~ — platform-aware shortcuts, typography tokens, entrance animation, dark kbd. Shipped 0.13.3
- **~~"Made with Bristlenose" branding footer~~** — Phase 5 of export, quick win (design-export-sharing.md)
- [S5] **Export polish** — minimum viable: delete things that should not be in an export, tidy up rough edges


### Should

- ~~**Histogram bar alignment** — right-align user-tags bars (#13)~~
- **~~Day of week in session Start column~~** (#11)
- **~~Right-hand sidebar animations~~** — match left-hand sidebar push/slide animations
- **Desktop home view — full design** — "no project selected" is an accidental engineering state, not designed UX. Designer's question: *what do you see on arrival?* Candidates: last project (already restored via `@AppStorage("selectedProjectID")`), help for first-timers, summary of recent work, new Bristlenose features, latest models, codebooks from the community. Today (30 Apr 2026, `first-run` branch, `ContentView.swift` detail else-branch) ships a static "Welcome to Bristlenose" placeholder — minimum plumbing only. Post-alpha: full design pass + window position/size restoration across launches (the project ID is restored; the window frame is the gap). Also: prune the now-unused `chrome.noProjectSelected` / `chrome.selectProject` locale keys (6 files) once the home view is finalised.


### Could
- **Symbology** — consistent Unicode prefixes (§ ¶ ❋) across navigation. Active branch
- **Close button CSS** — extract `.close-btn` atom (theme refactoring)
- **Content density setting** — Compact (14px) / Normal (16px) / Generous (18px) toggle. `--bn-content-scale` token (`0.875` / `1` / `1.125`), `font-size: calc(var(--bn-content-scale) * 1rem)` on `<article>`, cascades to all `rem`-based spacing. Toggle in toolbar or settings, persist via preferences store. Interacts with responsive grid — Generous + wide screen = fewer but more readable columns


### Icebox
- **Animated logo** — living-fish branch: breathing, gill pulsing, fin movement. Statement piece. Parked — oneday

---

## 4. Value — insights & time-saving ("why they'll use us")

### Must
- [S5] **QA: threshold review dialog on real data** — run AutoCode against real projects, evaluate confidence histogram + dual slider UX
- **~~Signal elaboration~~** — interpretive names + one-sentence summaries on signal cards. Designed (design-signal-elaboration.md)
- ~~**Codebook-aware tagging** — shipped in 0.13.0, verify it works end-to-end on real data~~
- ~~**Quick-repeat tag shortcut** (`r` key) — shipped, verify discoverability~~
- ~~**Bulk actions** — shipped in 0.13.3, verify on real multi-session projects~~


### Should
- **Analysis Phase 4** — two-pane layout, grid-as-selector. Medium effort (design-analysis-future.md)
- **~~Clickable histogram bars~~** → filtered view (#14)
- **~~Lost quotes rescue~~** — surface unselected quotes (#19)
- **Moderator question pill** — hover-triggered context (design-moderator-question-pill.md)
- **~~Quote sequences~~** — consecutive quote detection, ordinal-based for non-timecoded transcripts, verse numbering for plain-text, per-project threshold (design-quote-sequences.md)
- **~~Sidebar tag assign~~** — hover hint matching "add tag" visual language + toast undo ("Applied 'Trust' to 3 quotes — Undo")
- **Dashboard stats coverage** — increase the number of pipeline metrics surfaced on dashboard
- **PII summary dashboard widget** — surface pii_summary.txt findings (entity counts, flagged items needing review) in the serve-mode dashboard instead of expecting users to find and read a hidden text file
- **Drag-and-drop tags to quotes** — drag tag badge onto quote card to apply
- **s09 SS/GC classifier — navigational-vocabulary cue spike** — 30 Apr 2026 A/B against the s10 *clustering* prompt confirmed s10 cannot move coverage (it only ever sees pre-classified `SCREEN_SPECIFIC` quotes — adding cues there only re-partitions the existing pool, and on ikea regressed clean 8-section flow into 12 product-themed clusters). The right place for the cue ("here", "back", "on this page", "after I clicked", "the search bar at the top", etc.) is `bristlenose/llm/prompts/quote-extraction.md` (the SS/GC binary). Higher-risk than the s10 attempt — shifts quote counts between sections and themes — so needs its own A/B against ikea + fossda baselines and probably a methodology-doc note. See SS/GC docstring on `bristlenose/stages/s10_quote_clustering.py` and `experiments/thematic-spike/output/{ikea,fossda}/themes_s10_{before,after}.json` for the dead-end attempt

### Could
- **~~Analysis Phase 5~~** — LLM narration of signal cards
- **User-tag × group grid** — new heatmap view
- **Tag definitions page** (#53)
- **Transcript page user tags** — tag directly from transcript view
- **~~Framework acronym prefixes on badges~~** — small-caps 2–3 letter author prefix (e.g. `JJG`, `DN`)
- **Drag-to-reorder codebook frameworks** — researchers drag framework sections to prioritise, persist per project
- **People.yaml web UI** — in-report UI to update unidentified participants. API endpoint exists, missing UX design. Part of Moderator Phase 2 (#25)
- **Relocate AI tag toggle** — removed from toolbar (too crowded); needs a new home. Code commented out in `render/report.py` and `codebook.js`/`tags.js`
- **Delete/quarantine session from UI** — `.bristlenose-ignore` file (safe, reversible). (design-session-management.md)
- **Re-run pipeline from serve mode** — `POST /api/projects/{id}/rerun`, background task with progress streaming
- **~~User research panel opt-in~~** — optional email field in feedback modal
- **Pass transcript data to renderer** — avoid redundant disk I/O
- **Thematic analysis — wider survey & options** — post-alpha question worth carrying. s11 is one big inductive Claude call over the whole `GENERAL_CONTEXT` pool (47k tokens / 284 quotes on fossda); hits a context-window cliff around 1.5–2k quotes, no stability check, no separation between grouping and naming. Survey of academia + QDA-tool practice (Braun & Clarke iteratively, NVivo / ATLAS.ti / Marvin / Looppanel converge on code-first, BERTopic-style embed+cluster+name as local-first option) parked in `~/.claude/plans/doing-trial-runs-of-replicated-dolphin.md`. Cheapest first move: a 1-day **stability spike** — run s11 5× on fossda, embed theme labels, measure pairwise overlap. Surface at first non-fossda corpus / alpha-cohort retrospective. Apr 2026 spike-within-spike: added Option M (pure-math BERTopic — sentence-transformers + UMAP + HDBSCAN + c-TF-IDF, no LLM) to `experiments/thematic-spike/`. On fossda (n=100) it produced 16 clusters with 14% honest noise (vs 100% padding from LLM prototypes), concrete labels (sendmail, crochet/yarn, audacity), and zero cost; on the smaller ikea corpus (n=67) it under-segmented (3 clusters, 100% coverage). Suggestive — not conclusive — that the LLM may not be contributing distinguishable thematic value over BERTopic on richer corpora

---

## 5. Blocking — prevents adoption or causes abandonment

### Must
- [S4] **First-run experience** — new user opens app, has no project, no API key, no recordings. What happens? Design doc complete (`launch-docs/design-first-run-experience.md` in delivery repo): coach-in-context, no wizards/sheets, trial IS the onboarding. Needs implementation
- ~~**API key entry in GUI** — currently requires terminal. Absolute blocker for App Store users~~
- ~~**Error messaging**~~ — pipeline failures show actionable messages ("check API credits or logs", "run bristlenose doctor"), red ✗ / yellow ⚠ per stage. Shipped 0.13.3
- [S4] **`bristlenose doctor` in GUI** — dependency health checks visible in app, not just CLI
- ~~**Homebrew formula: spaCy model** — post_install step (#42). Without it, first run fails~~
- **Cohort baselines for all three frontier providers** — Phase 1 cost-forecast shipped (98df507) with empty `cohort-baselines.json`; populate from FOSSDA dogfood against Claude Sonnet 4 + GPT-4o + Gemini 2.5 Pro so non-Claude users get a pre-run cost estimate too. One run per provider into separate output dirs, merge medians into a single baseline file with `source: "FOSSDA n=3 vendors"`

### Should
- **Time estimate warning** — warn before long transcription jobs (#39)
- **Provider documentation** — which provider to choose, cost comparison (#38)
- **Whisper prefetch flag** — `--prefetch-model` to avoid surprise downloads (#41)

### Could
- **Shell completion** — `--install-completion` for power users
- **Snap Store publishing** (#45) — Linux adoption path. `snapcraft register bristlenose`, request classic confinement, add `SNAPCRAFT_STORE_CREDENTIALS` to GitHub secrets. See `docs/design-doctor-and-snap.md`
- ~~**Cancel button** — cancel running pipeline (desktop app stretch goal)~~ — shipped 24 Apr 2026 (toolbar pill Stop, owned + orphan paths, signal escalation, instant ack)

---

## 6. Risk — could get us into trouble

### Must
- ~~**Desktop security: localhost auth token**~~ — bearer token middleware, per-session `secrets.token_urlsafe(32)`, injected into HTML + WKUserScript. Design plan: `docs/design-localhost-auth.md`
- ~~**Desktop security: media endpoint filtering**~~ — extension allowlist + path-traversal guard on `/media/` route
- ~~**Desktop security: CORS middleware**~~ — `CORSMiddleware` with `allow_origins=[]` (same-origin only)
- ~~**Desktop security: verify zombie cleanup targets**~~ — added Vite :5173 to orphan port scan
- ~~**Desktop security: migrate Keychain to Security framework**~~ — native `SecItemAdd`/`SecItemCopyMatching`/`SecItemDelete` replaces `/usr/bin/security` CLI. Add-then-update pattern (atomic), `kSecAttrAccessibleWhenUnlocked`, DEBUG error logging. Plan: `.claude/plans/cuddly-orbiting-yao.md`. Python side (`credentials_macos.py`) still uses CLI — needs separate migration before sandbox
- ~~**Desktop security: minimal child process environment**~~ — stripped to PATH, HOME, TMPDIR, locale, VIRTUAL_ENV + BRISTLENOSE_* overlay
- ~~**Desktop security: port-restrict navigation policy**~~ — shipped in `WebView.swift` (`decidePolicyFor` restricts to `127.0.0.1` + `about:`)
- **~~Rotate API key~~** — was visible in terminal (TODO.md immediate)
- [S6] **Privacy policy** — required for external TestFlight + App Store submission. Not needed for internal-only alpha. Local-first model simplifies this but document must exist. Draft v1 complete (`launch-docs/privacy-policy.md` in delivery repo), needs solicitor review (May)
- [S6] **Terms of service** — subscription terms, refund policy, data handling. Draft v0.9.1 complete (`launch-docs/terms-of-service.md` in delivery repo), needs solicitor review (May)
- [S2] **App Store review compliance (TestFlight subset)** — umbrella for: Apple Distribution cert ✅, sandbox + entitlements (Track A pending), PyInstaller sidecar signing ✅, Privacy Manifest reason-code audit ✅ (C4, 28 Apr 2026), Hardened Runtime ✅. All tracked as individual items. Full review hardening for external testers / submission lives in S6. **C3 (Apr 2026) shipped Keychain → env-var injection + bundle integrity gates** (`check-bundle-manifest.sh` source→spec + `bristlenose doctor --self-test` spec→bundle, both wired into `build-all.sh`). Discovered 3 datas-coverage bugs during smoke test, resolved.
- [S5] **PII redaction audit** — verify Presidio catches names/emails in transcripts before shipping to paying users. Per `docs/design-modularity.md`: PII moves to `[pii]` pip extra (CLI) and tier-2 Background Assets pack (macOS, public beta) — out of base install. Alpha bundles it inline to avoid the asset-pack Python-packages-as-data problem; public beta deferred-downloads it.
- ~~**Security scanning** — npm audit, pip-audit, CodeQL before public release (design-test-strategy.md)~~
- ~~[S1] **Alembic/migration strategy** — DB schema changes without data loss. Currently no migration framework~~
- ~~**AI data disclosure dialog** — Apple Guideline 5.1.2(i). Shipped: `desktop/Bristlenose/Bristlenose/AIConsentView.swift` (first-run sheet, consent version policy, re-accessible via menu)~~
- ~~[S2] **Privacy Manifest (`PrivacyInfo.xcprivacy`)** — required for App Store since mid-2024. Host shipped 19 Apr 2026; sidecar shipped 28 Apr 2026 as Track C C4 (`765b111`..`f6c3170`). Two manifests cover the whole bundle (host at `Contents/Resources/`, sidecar at `Contents/Resources/bristlenose-sidecar/`). Symbol-sweep triage rejected per-package sub-manifests as gold-plating; build-all.sh step [f] enforces presence + plutil-lint on every release archive. See `docs/design-desktop-python-runtime.md` §"Privacy manifest coverage (C4)".~~

### Should
- ~~**Vulnerability disclosure page** — `security.txt` (RFC 9116) at `bristlenose.app/.well-known/security.txt`. PR #85~~
- **AGPL + App Store legal opinion** — CLA enables dual-licensing, but untested. Brief written opinion needed (~£200–500). Lawyers: see `docs/private/licensing-and-legal.md`
- **GDPR/data processor statement** — even though local-first, API calls send data to LLM providers
- **Crash reporting** — know when the app breaks in the field. Sentry or similar
- **Windows credential store** — env var fallback is insecure (SECURITY.md gap)
- ~~**PostMessage origin tightening**~~ — React path uses `window.location.origin` (PlayerContext.tsx). Vanilla JS path deprecated — just remove
- **localStorage namespace by project** — review what's still in localStorage and why (most state moved to SQLite). Collision risk may be moot
- **WKWebView Content Security Policy** — inject CSP via WKUserScript restricting script sources and connection targets. (design-desktop-security-audit.md)
- **Clean SecurityChecklist.swift** — remove resolved items #1, #3, ~~#5~~, #7, ~~#8~~; keep genuine blocker #2. (#5 + #8 done 26 Apr 2026 on `sidecar-signing` — `proc_pidpath` PID verification, port-restricted nav). (design-desktop-security-audit.md)
- **Wrap dev paths in `#if DEBUG`** — `ContentView.swift`, `ServeManager`, `I18n` leak developer directory structure into release binary. (design-desktop-security-audit.md)
- **Bundled fallback API key risk** — extractable from PyInstaller binary. Cap spending, use dedicated key, document accepted risk. (design-desktop-security-audit.md)
- **DASVS Level 1 audit** — AFINE's Desktop Application Security Verification Standard (Nov 2025), purpose-built for desktop apps. 12 domains, 150+ requirements. ([github.com/afine-com/DASVS](https://github.com/afine-com/DASVS))
- **PII detection warning before LLM send** — consider adding a PII detection warning before sending transcripts to LLM — strengthens privacy-by-design story. Non-blocking, nice-to-have. Review feasibility and UX implications
- **`safe_filename()` `..` removal hardening** — single-pass `replace("..", "")` can reassemble traversal from `"..../"`. Fixed with `while` loop in v0.14.2 clip extraction work, but needs systematic security review pass across all filename utilities
- **Pre-beta: re-audit LLM-provider API-key formats and extend log redactor** — C3 shipped a runtime redactor covering Anthropic (`sk-ant-`), OpenAI (`sk-proj-` / historical `sk-`), and Google (`AIza`). Azure was skipped (32-char hex false-positives on UUIDs/SHAs). Before beta: verify current formats haven't changed, add Azure with context-sensitive matching, confirm redactor hits across all providers with real test keys. Code site: `ServeManager.handleLine()`
- [S3] **Person UUID migration** — change Person.id from auto-increment integer to UUID before any person_links rows exist. Currently `Mapped[int]` in `server/models.py`. Design doc: "cost of adding UUIDs now is near-zero; retrofitting requires a migration touching every row." Depends on Alembic. (design-multi-project.md §2, §3c Finding 7)
- **Project index metadata exposure** — `projects.json` is a client roster (project names, folder/client names, paths, timestamps). Propagates via cloud sync, MDM, dotfile managers. Document sensitivity in SECURITY.md; desktop path in `~/Library/Application Support/` not `~/.config/`. (design-multi-project.md §3c, Finding 3)
- **Gate `_BRISTLENOSE_AUTH_TOKEN` env override behind `BRISTLENOSE_DEV_MODE=test`** — deferred from `ci-cleanup` branch (18 Apr 2026). Today `app.py:96` honours the env var unconditionally. SECURITY.md updated in v0.14.6 to describe the actual behaviour and `bristlenose doctor` warns when the env var is set, but the real gate was deferred: the writeback at `app.py:97` exists for `uvicorn --reload` session continuity, and a clean gate needs a "this PID wrote the env var" semantic so local dev doesn't lose its session on every code save. Also touches `scripts/perf-stress.sh` (currently pins the token without a flag). Open question surfaced by ci-cleanup review: is the gate genuine hardening or cosmetic given both env vars sit at the same attacker privilege level? Worth resolving before coding
- **Release-artifact scan for `BRISTLENOSE_DEV_MODE` string** — once the gate above lands, grep PyInstaller/Snap/Homebrew/`.app` artifacts to verify the dev-mode flag isn't baked into a user-distributable binary. Pre-empts enterprise reviewer question about dev-flag leakage

### Could
- **Export anonymisation** — checkbox to strip names/display-names from exported HTML
- **Rate limiting** — if server ever exposed beyond localhost
- ~~**pip-audit in CI**~~ — shipped in ci.yml. Also: `pip-licenses --format=json --with-urls` for licence compliance (verify AGPL-3.0 compatibility of all deps) — licence check still TODO

### Won't (100 days)
- **Instance DB encryption** — cross-project instance DB will contain person_links (cross-client identity). Two independent security reviews rated unencrypted storage CRITICAL. Options: SQLCipher or Keychain-derived key. Required before person linking ships. (design-multi-project.md §3c, Finding 2)
- **`bristlenose forget` — GDPR erasure across instance DB** — when person_links exist, deleting the project folder no longer erases all identity state. Needs CLI command: purge Person rows + person_links + transitive chains + audit receipt. (design-multi-project.md §3c, Finding 4)
- **Export isolation integration test** — CI-gated test: load 2 projects, verify Project A export contains zero data from Project B (Person rows, codebook groups, tags). (design-multi-project.md §3c, Finding 10)

---

## 7. Halo — gets us noticed, makes a statement

### Must
- [S6] **Local-first story** — "nothing leaves your laptop" messaging. Core differentiator. Needs landing page copy
- ~~**One-command install** — `brew install bristlenose` already works. Showcase this~~

### Should
- **Public-domain interview screenshots for marketing** — Veterans History Project (US govt, public domain) and NASA astronaut interviews for website, App Store listing, blog posts. Real interview content, freely usable. (design-real-data-testing.md)
- **Living logo** — animated bristlenose pleco (living-fish branch). Memorable, delightful
- **Dark mode** — already implemented, polish the rough edges
- **Speed demo** — "folder in, report out in 5 minutes" video/GIF for landing page
- **~~Keyboard-first UX~~** — shortcuts already deep (`[`, `]`, `\`, `r`, `s`, `?`). Showcase in marketing
- **Open source (AGPL)** — trust signal for researchers. Emphasise in positioning
- **Microinteractions** — bounces/slides for opens/closes, flashes of acceptance, staggered fly-up for bulk hide (150ms per card like vanilla JS version)

### Could
- **Video clip export story** — "folder in, clips out" — the 3-hour Final Cut Pro task done in seconds. Demo-able, visceral, differentiator vs Dovetail
- **Ollama integration** — "free, no account required" local LLM story
- **CLI text-only mode** — `bristlenose run/analyze/render --text` emits the full analysis (themes, signals, sections, codebook-tagged quotes, sentiment, friction) as plain markdown to stdout. Full ingestion (audio, video, Zoom/Teams, voice memos). Second product surface for the **AI-first early-adopter crowd** running local models on Linux/Pi/homelab — not the traditional NVivo/Atlas.ti ethnographer. Pairs with Ollama for a fully-local audio→markdown pipeline (no cloud in the loop, not even for analysis) — strongest privacy story we can tell. Pairs with the snap for Linux distribution. Design: `docs/design-cli-text-mode.md`. Time-box v0.1 to a weekend when the slot opens
- ~~**Multi-language**~~ — 5 locales shipped (en, es, fr, de, ko) in 0.14.1. Infrastructure + 4 languages exceeds target
- **i18n: help.signals/codebook/contributing translations** — EN keys exist (~63), ES/FR/DE/KO locales missing all of them
- **i18n: AboutSection full extraction** — ~15 paragraphs hardcoded English, needs `useTranslation` wiring + keys in all 5 locales
- **i18n: DeveloperSection & DesignSection** — dev-facing help panels, ~20 paragraphs hardcoded. Debatable whether to translate
- **i18n: SettingsModal CONFIG_DATA labels** — ~70 config reference labels hardcoded English. Nav chrome already wired
- **i18n: translation quality fixes** — ko participant term inconsistency (참여자 vs 참가자); de/ko missing `nav.codebookShort`. Machine translation QA checklist in `docs/design-i18n.md` Step 6
- **i18n: cross-check each new language against Apple glossary** — Spanish done (23 Mar 2026, all match). fr, de, ko still need cross-check for standard menu items (Edit > Find, View > Zoom, File > Print). See `docs/design-i18n.md`
- **i18n: fr common.json "citations" audit** — `sentItem3` in desktop.json fixed to "verbatim" (26 Mar). common.json still uses "citations" in export/copy contexts (copyQuotes, quotesCopied). These are UI action labels not the research concept — probably fine, but worth a native speaker review
- **i18n: localOllama staleness** — `help.privacy.localOllama` says "quality is lower than cloud models in 2026" — time-dependent claim that will go stale
- **Weblate attribution on bristlenose.app** — Libre plan condition (approval landed 29 Apr 2026). README link already present; website mention outstanding. Pull content from the Community menu of the Weblate project (badge + short blurb), drop into footer or about section of `website/index.html`

---

## 8. Quality of life — enhancements that bring joy

### Must
- ~~**Keyboard shortcuts help modal** — shipped but needs polish. Platform-aware ⌘/Ctrl~~

### Should
- ~~**Sidebar drag-to-push** — active branch (drag-push), replaces overlay mode~~
- **~~Responsive signal cards~~** — active branch (responsive-signal-cards)
- **Undo bulk tag** — Cmd+Z for last tag action (ROADMAP)
- **Sticky header** — decision pending (#15)
- **Density setting** — compact/comfortable/spacious for quote grid
- **Show/Hide panel label flip (desktop menu)** — wire SidebarStore/InspectorStore open state → bridge → Swift menu labels. Hide translations already exist in en/es/ko. ~30 min, fully scoped
- **Desktop UX review findings (22 Mar 2026)** — v0.1→v1 transition story (What's New sheet), pipeline progress (Stage 4 of 12), bare-key shortcuts in menu bar, "Remove" not "Delete" for projects, disambiguate three sidebars (Project Sidebar / Sections Panel / Tags Panel), archive undo toast, sidebar `.searchable()`, simplify drop zone flow, toolbar fixed min-width, window state restoration, dark mode re-sync KVO, embedded font token, cursor reset scope. Full checklist in session notes
- **Desktop Mac-nativeness (22 Mar 2026)** — P0: 13pt font injection (loudest web-view tell). P1: shared find pasteboard (Cmd+E/G), selection dimming on inactive window, temperature slider locale, Cocoa keybindings in contenteditable, Services menu testing, scroll feel testing (150+ quotes), serve startup progress line. P2: option-drag copies, undo/redo hiding deviation, disabled "+" button, View menu Enter Full Screen
- **Transcript page: tidy up extent bars** — small effort
- **Transcript page: flag uncited quote for inclusion** — medium-large effort

### Could
- **Theme management in browser** — custom CSS themes (#17)
- **Transcript expand/collapse** — collapsible sections and themes
- **Drag-and-drop quote reordering** — large effort
- **Transcript pulldown menu** — margin annotations (ROADMAP)
- **Measure-aware leading** — line-height interpolation based on column width across 23rem–52rem range (Bringhurst §2.1.2). Current `--bn-text-*-lh` tokens are fixed per size. Mockup: `docs/mockups/measure-aware-leading.html`. Playground already has slider
- **Britannification pass** (#40) — CLI text consistency
- **Input focus CSS `.bn-input` atom** — extract shared input styling
- **Checkbox atom** — extract ghost checkbox style
- **Titlebar project icon** — show the chosen SF Symbol icon next to the project name in the macOS title bar. SwiftUI `.navigationTitle` doesn't support inline images and toolbar items always get a lozenge. Needs AppKit-level NSWindow manipulation or a future SwiftUI API

### Icebox
- **Highlighter feature** — active branch, scope TBD. Parked

---

## 9. Technical debt — foundations for the future

### Must
- [S4] **Playwright E2E layers 4–5** — layers 1–3 done, need layers 4–5 for DB-mutating actions and visual regression. Beta blocker: 3 thin specs is not enough coverage for a shipped product (design-playwright-testing.md)
- [S1] ~~**Pipeline resilience Phase 2c** — input change detection: source file metadata hashing (size+mtime), upstream content_hash propagation, cascade invalidation, PII flag tracking. Done 15 Apr 2026~~
- [S1] ~~**Pipeline resilience Phase 2b** — verify content hashes on load (done 25 Mar 2026)~~
- ~~**PyPI `Development Status` classifier** — currently unset in pyproject.toml. Must be `Development Status :: 4 - Beta` before launch. Signals maturity to pip users~~
- ~~**Frontend CI**~~ — Vitest + ESLint + TypeScript typecheck gated in CI since 0.12.0. ESLint step informational (84 pre-existing errors). Prettier not yet added
- ~~[S1] **pytest coverage in CI** — trivial to enable, currently blind to dead code~~
- [S6] **Frontend test coverage for clip export** — extend ActivityChipStack + ExportDropdown tests for clips job type (added during clip extraction work, 27 Mar 2026)
- ~~[S1] **Multi-Python CI** — test 3.10, 3.11, 3.12, 3.13. Done 15 Apr 2026~~
- ~~[S4] **Swift test harness** — XCTest target + ~42 Swift Testing tests across 5 files (Tab, I18n, LLMProvider, KeychainHelper, ProjectIndex). Done 26 Apr 2026: `BristlenoseTests` target wired up via Xcode wizard; suite-level `@MainActor` added to fix Swift 6 actor-isolation errors on the pre-existing tests; EventLogReaderTests added alongside (Phase 1f Slice 4). 90 tests passing via `xcodebuild test`.~~
- **`BristlenoseTests` fixture re-include** — `Fixtures/{en,es}/*.json` (8 files) currently excluded from the BristlenoseTests target via `PBXFileSystemSynchronizedBuildFileExceptionSet` membershipExceptions because the auto-sync flattens them into `Resources/<name>.json` and they collide. `I18nTests` doesn't currently exercise its fixture-loading fallback path so tests still pass without them, but if/when that path is exercised they need re-including. The right fix is Xcode-side: in the project navigator, right-click `Fixtures` under `BristlenoseTests` → File Inspector → convert from group to folder reference (preserves `en/` and `es/` subdirs at copy time). Then remove the 8 entries from the membershipExceptions list in `Bristlenose.xcodeproj/project.pbxproj`. Trivial — surface when the test starts failing or when adding a new locale fixture. (debt added 26 Apr 2026, Slice 4 follow-up)
- **Desktop UX iteration** — full backlog in `docs/private/desktop-ux-iteration.md` (captured 26 Apr 2026 from `port-v01-ingestion` QA). Ten themed sections: activity pill placement (blocker — invisible at default widths), failure-surface deduplication, Resume/Retry/Re-analyse… verb wiring (Slice 4 carry-over), local Stop affordances + truthful state, CLI-rich progress surfacing, Settings/dev-mode rough edges, UnsupportedSubsetView, gruber polish, sidebar polish + incremental re-analysis, i18n debts. Suggested 5-pass grouping. User flagged "needs to happen sooner rather than later" — pairs naturally with [S5] (visual design + a11y) or splits as its own sprint between alpha and public beta.

### Should
- ~~**Alembic setup** — DB migration framework before any schema change~~
- **Real-data stress test corpus** — acquire NASA transcripts (~50 .txt), StoryCorps audio (~30 .mp3), SpinTX Spanish (~20 .mp4+.srt), IWM British (~10 .mp3), Korean War Legacy (~10 .mp4). ~125 sessions, ~100h, 3 languages. Exercise transcription quality, thematic analysis depth, scale rendering, i18n analysis. (design-real-data-testing.md)
- **Visual regression baselines** — Playwright screenshots, light + dark
- **Cross-browser Playwright** — Chromium + Firefox + WebKit
- ~~**Bundle size budget**~~ — moved to §15 Performance as a Must
- **Platform detection refactor** — shared `utils/system.py` (#43)
- **Skip logo copy when unchanged** (#31)
- **Temp WAV cleanup** (#33)
- **Pipeline concurrent chaining** (#32) — always-on semantic splitting for quote extraction. Related: **smart-split-on-truncation fallback** (deferred S3+, not S2). 17 Apr 2026: `llm_max_tokens` default raised 32768 → 64000 (Anthropic hard-caps Claude Sonnet 4 at 64000 decimal; portable ceiling across Claude/Gemini 65K/GPT-5 128K). FOSSDA baseline hit truncation on one dense session at the old 32K default. Smart-split sketch: on `max_tokens` truncation, fall back to splitting that one session on natural breaks (stage-8 topic segments, moderator Q pivots, long silences); reprocess truncated session only; monologue fallback is mechanical halves/thirds with explicit warning. Different from per-participant chaining: chaining is always-on semantic; smart-split is rare-path recovery
- **LLM response cache** (#34)
- **Logging tiers 2–3** — cache hit/miss decisions, concurrency queue depth, PII entity breakdown, FFmpeg command/return code, keychain resolution, manifest load/save (6 items, all trivial–small)
- **Promote pip-audit + npm audit to blocking** — target v0.15.0 (trivial)
- **i18n: pseudo-localisation QA** — add `i18next-pseudo` to catch remaining hardcoded strings. See `docs/design-i18n.md`
- [S3] **Hardcoded project ID audit** — ~12 locations hardcode project ID `1` (`app.py`, `export.py`, `api.ts`, `PlayerContext.tsx`, `ExportDialog.tsx`, `useProjectId.ts`, `main.tsx`, `index.html`). Two are bugs now (bypass `apiBase()`). Parameterise before multi-project. (design-multi-project.md §4)

### Could
- **a11y lint rules** — eslint-plugin-jsx-a11y
- **axe-core in E2E** — automated accessibility assertions
- **Component Storybook** — visual component catalogue
- **Typography token consolidation** — 16 sizes → ~10
- **Tag-count dedup** — 3 implementations → shared `countUserTags()`
- **`isEditing()` guard dedup** — shared `EditGuard` class
- **Inline edit commit pattern** — shared `inlineEdit()` helper
- **Shared user-tags data layer** — vanilla JS dedup (frozen path, low priority)
- **Configurable codebook URL** — `BRISTLENOSE_CODEBOOK_URL` as injected global instead of hardcoded (trivial, from old ROADMAP)
- **Dev HUD: end-to-end traceability panel** — debug overlay showing provenance at every layer (git branch/SHA/dirty, Python version/source, render timestamp, theme CSS path/mtime/hash, serve mode/port, frontend Vite hash/router mode, bridge state, API health). Toggle with keyboard shortcut. Data from git CLI at startup, `/api/health`, `/api/dev/info`, CSS inspection
- **Primary Python version helper** — extract `scripts/primary-python-version.sh` so `new-feature` skill, `bump-version.py`, and future tooling all read from one parser instead of grep'ing `release.yml` individually. Trigger: do this the next time we bump the CI python-version (currently 3.12) — bundles the bump and the DRY refactor into one piece of thinking

### Won't (100 days)
- **JS module cleanup** (#7, #8, #9, #10, #22, #23) — vanilla JS is frozen/deprecated
- **`'use strict'` in all modules** (#7) — frozen path
- **Explicit cross-module state management** (#23) — React replaced this

---

## 10. Documentation — guides, help, onboarding

### Must
- [S6] **App Store description** — short + long description, keywords, screenshots
- [S6] **Video walkthrough** — 2-minute "here's what Bristlenose does" screencast
- [S4] **In-app onboarding** — merged into first-run experience (§5). Trial IS the onboarding — no separate wizard. Post-trial, contextual tooltips only for features the trial didn't cover
- [S4] **Provider setup guide** — which LLM provider, how to get API key, cost expectations
- [S6] **README polish** — landing page README for GitHub (currently dev-focused)
- [S6] **Hero image of report on GitHub README** — screenshot showing a real report, above the fold

### Should
- **FAQ / troubleshooting** — common issues (FFmpeg, API keys, large files)
- **INSTALL.md desktop section** — "Download, drag to Applications, done"
- **Changelog for users** — user-facing changelog (not dev changelog)
- **How-to-get-API-key screenshots** — step-by-step visual guide for Claude, ChatGPT, Gemini console

### Could
- **Research methodology guide** — how Bristlenose analyses data, for researchers who want to understand
- **Academic citation** — BibTeX entry for papers
- **API documentation** — for power users who want to script against serve mode
- **Glossary heading case** — `docs/glossary.md` H1 uses title case, violating its own sentence-case rule. Trivial fix
- **Help text bulleted lists** — `help.privacy.missesBody`, `catchesBody`, `cannotBody` are dense paragraphs listing many categories. Bulleted lists would be more scannable and translatable
- **`ct()` candidate: actionReview** — `help.privacy.actionReview` references `pii_summary.txt` filename. Desktop users can't navigate to hidden files. Wrap in `ct()` or rewrite for desktop ("check the audit log in your project folder")
- **`dt()` design: single-call vs double-lookup** — current: `i18n.exists()` then `t()`. Alternative: `t(desktopKey, { defaultValue: t(key) })`. Revisit if forked key count grows past ~10
- **PII/anonymisation enforcement level** — glossary draws a hard line. Decide whether docs-review agent enforces at blocker or info level
- **CLAUDE.md "5 languages" stale** — current status line says 5 but 6 exist (ja added). Update when next editing current status
- **Vale linter setup** — `docs/glossary.md` terminology table can feed Vale substitution rules. See docs-review agent plan for implementation steps

---

## 11. Operations — CI/CD, release, monitoring

### Must
- [S2] **CI: desktop-build job** — `xcodebuild build` + `xcodebuild test` on macOS runner, `CODE_SIGNING_ALLOWED=NO`, informational initially. Catches Swift compilation errors and Swift Testing regressions on every push. Prerequisite for the full build pipeline below. Plan: `docs/design-ci.md` §Coverage gaps
- [S2] **TestFlight upload pipeline** — Xcode archive → App Store Connect upload (notarytool). Manual first (local `xcodebuild -exportArchive` + `xcrun notarytool submit`). Automate in S6. Only runs when MVP flow is green + sandbox is clean
- ~~**Desktop app build pipeline (.dmg path)** — won't do (17 Apr 2026). App Store is the sole distribution channel. See `docs/private/road-to-alpha.md` Decision section~~
- [S2] **App Store Connect setup** — app record, TestFlight internal beta group (≤100 testers, no Beta App Review), Privacy Nutrition Labels. Pricing + external tester config deferred to S6
- ~~[S2] **Apple Distribution certificate + provisioning profile**~~ ✅ **Done 19 Apr 2026 (Track C C2).** Cert + profile installed; notarytool keychain profile `bristlenose-notary` set up. Portal artefacts in `~/Code/Apple Developer/`
- **Developer ID certificate** — **deferred, not rejected (28 Apr 2026 reframe).** Trigger to revisit: ~10k paying users, OR first enterprise MDM ask. Sparkle update flow + notarytool submit are preserved as future-state in `design-desktop-python-runtime.md` §"Deferred — Developer ID flow"
- ~~[S1] **CI: add macOS runner** — currently Linux-only (informational, 15 Apr 2026)~~
- ~~**.dmg README** — won't do (17 Apr 2026). App Store path only~~
- ~~[S2] **PyInstaller sidecar signing**~~ ✅ **Done end-to-end 28 Apr 2026 (Track C C2 + post-C3 hardening).** Parallel `wait -n` job pool, SHA256 sign-manifest, full pipeline in `desktop/scripts/build-all.sh`. SECURITY #5/#8 unblocker landed 26 Apr (`823f9be..38808fe`); end-to-end run clean 28 Apr (`1ee30eb`) — adds Mac Installer Distribution cert + `installerSigningCertificate` in ExportOptions, falls back to `.app` from xcarchive when `method=app-store` exports only `.pkg`, skips notarytool/stapler/spctl on the App-Store path (`notarytool` only accepts Developer ID; App Store Connect validates server-side), uses `pkgutil --check-signature` instead. Empty-ents retest ran 28 Apr — RED (`8cfd2ee`): Python.framework's nested `_CodeSignature/` seal is the binding reason DLV stays. Lsof zombie-cleanup also libproc-only now (`5471b35`). C3 bundle-integrity gates resolved BUG-3/4/5
- ~~[S1] **Build number auto-increment** — `CFBundleVersion = 1` blocks Sparkle and App Store update logic. Set up CI auto-increment. Done: `bump-version.py` unifies desktop+CLI, auto-increments build number~~
- ~~[S1] **Domain & email infrastructure** — register `bristlenose.app`, configure SPF/DKIM/DMARC, Substack custom domain (`blog.bristlenose.app`), deploy site, set up email on DreamHost (`hello@`, `support@`, `security@`). Full plan: `docs/private/infrastructure-and-identity.md`~~
- [S6] **Supply chain hardening** — GitHub 2FA with hardware key, branch protection on main, PyPI hardware key + project-scoped token, register PyPI typosquats. Full checklist: `docs/private/infrastructure-and-identity.md`. Deferred from S1: low threat until commercial launch (see `docs/private/supply-chain-deferral.md`)

(Succession plan moved to §Post 100 days — deferred 17 Apr 2026.)

### Should
- [S6] **Rate-limit trial-key endpoint** — add rate limiting (1 req/min/IP) + server-side receipt validation to the trial-key endpoint, even for the 20-user beta. Blocks v1.0 subscription launch, not alpha (trial-key endpoint doesn't exist yet). See `trial-and-pricing-architecture.md` Part 2
- ~~[S1] **Anthropic billing alerts** — set up billing alerts at $5 and $10 thresholds for the trial API key account~~
- **Desktop app polish** — ReadyView: SwiftUI `.fileImporter()` (replace `NSOpenPanel.runModal()`). ProcessRunner: `AsyncBytes` instead of `availableData` polling. `hasAnyAPIKey()`: extend beyond Anthropic-only (or rename). Settings shortcut ⌘, : show in Help shortcuts conditionally (desktop only, browser intercepts). (Keychain migration moved to §6 Risk Must)
- **Doctor serve-mode checks** — Vite auto-discovery via `/__vite_ping`, replace hardcoded port (design-serve-doctor.md)
- **Extract design tokens for Figma** — colours, spacing, typography, radii → JSON/CSS variables
- **Crash reporting** — Sentry or Apple's built-in crash reporting
- **Update mechanism** — Sparkle framework or App Store auto-update
- **CI snap smoke test** — verify Snap package installs cleanly (TODO.md)
- **TestFlight beta** — pre-launch testing with real users
- **Windows CI** — pytest on `windows-latest` runner
- ~~**AV false-positive testing** — test signed `.dmg` against common macOS antivirus. PyInstaller bundles frequently flagged.~~ _Won't do (18 Apr 2026) — App Store path only, no `.dmg`. Notarised App Store builds don't hit the AV heuristics that unsigned `.dmg`s do._ (design-desktop-security-audit.md)
- **OS version compatibility testing** — set up macOS 15 Sequoia VM (UTM, Virtualization.framework) and test full app on the deployment target. Dev machine runs macOS 26 Tahoe — need VM coverage for macOS 15 (floor). Run BroadcastChannel spike, full app smoke test, WKWebView security policy, `.nonPersistent()` behaviour
- **Semgrep CI integration** — Swift security rules (experimental) + Python security rules (mature). (design-desktop-security-audit.md)
- **Objective-See QA** — run KnockKnock + LuLu during pre-release QA to verify system footprint
- **Move feedback endpoint to bristlenose.app** — currently on cassiocassio.co.uk. Update `DEFAULT_FEEDBACK_URL` in Python + TS, `From:` header in `feedback.php` to `support@bristlenose.app`, redeploy to bristlenose.app web root. Tidy-up, not a blocker — current endpoint works
- **CI allowlist validator + staleness gate** — `scripts/check-ci-allowlists.py`: parse `// ci-allowlist: CI-A<N>` markers in `e2e/tests/*.spec.ts`, parse the register at `e2e/ALLOWLIST.md`, fail CI if either side has an ID the other doesn't. Also flag any `deferred-fix` entry with `added:` > 90 days unless renewed. Plus a regex-shape lint (reject unanchored `.*` / `.+` in suppression patterns — mitigates regex-widening review finding). Trigger: ~10th register entry or before first external contributor, whichever is sooner. See `e2e/ALLOWLIST.md` "Future v2" section for full deferred scope
- **Bump Python floor to `>=3.12` — drop 3.10 and 3.11 from the CI matrix.** 3.10 EOLs upstream Oct 2026; beta realistically lands ~Jan 2027, so the floor has to ratchet before then. 3.11 is a transitional release (not the default on any LTS), covered by the 3.10-and-3.12 bracket today — dropping both at once is one ratchet instead of two. 3.12 matches Ubuntu 24.04 LTS + current Homebrew + macOS 15 Python. Touches: `pyproject.toml` (`requires-python`, classifiers, mypy `python_version`), `.github/workflows/ci.yml` matrix, `README.md`, `INSTALL.md`, `CLAUDE.md`, grep for any `sys.version_info` / `# Python 3.10` conditionals. User-visible: minor version bump to v0.15.0 with CHANGELOG note. Users on Ubuntu 22.04 with system Python 3.10 would need `apt install python3.12` (universe), snap, or the desktop app — acceptable given audience skew (researchers on brew / modern Linux) and that we ship two other distribution paths. Saves ~10 min wall-clock per CI run. ~1–2 hours of focused work. Branch name: `python-floor-3.12`. Reminder scheduled for 9 May 2026.

### Could
- **Analytics** — privacy-respecting usage analytics (opt-in only)
- **Weekly install smoke tests** — automated pip/pipx/brew verification
- **Perf history charts** — render `e2e/.perf-history.jsonl` as a chart over time (DOM counts, API latency, export size). Currently view-only via `scripts/perf-history.sh` (tabular). Options: Observable notebook, tiny matplotlib script, or a React page in the dev-only About panel. Source data: one JSON line per perf-gate run, gitignored (local-only). When we want cross-machine history, upload `.perf-history.jsonl` as a CI artifact and stitch runs together

---

## 12. Legal/Compliance — gates to App Store

### Must
- ~~[S1] **Apple Developer Program** — $99/year, individual enrollment (Martin Storey, Team ID `Z56GZVA2QB`). Bundle ID: `app.bristlenose`. Activated 16 Apr 2026, expires 16 Apr 2027. Transition to Ltd organisation enrollment if/when revenue justifies it (team transfer preserves app listing, reviews, URL). Full plan: `docs/private/infrastructure-and-identity.md`~~
- [S6] **Privacy policy URL** — required for external TestFlight + App Store submission. Not needed for internal alpha. Host at `bristlenose.research/privacy`. Draft complete, needs solicitor review (May) then hosting
- [S6] **Terms of service** — subscription terms. v0.9.1 drafted, needs solicitor review (May)
- [S2] **App sandbox compliance** — entitlements for file access, network (LLM API calls). Required for App Store Connect upload (including TestFlight)
- [S2] **Export compliance** — HTTPS only, no custom encryption = simplified declaration
- [S6] **Age rating** — likely 4+ (no objectionable content). App Store Connect only, not needed for internal TestFlight
- [S6] **EULA** — standard Apple EULA or custom
- **Privacy Manifest (`PrivacyInfo.xcprivacy`)** — canonical entry in §6 Risk
- **AI data transparency per Apple 5.1.2(i)** — canonical entry in §6 Risk ("AI data disclosure dialog")

### Should
- [S6] **Draft DPA for relay mode** — accept processor status under GDPR Article 4(2). Short, 2-page, honest DPA. Needed before v1.0 subscription launch, not for alpha. See `trial-and-pricing-architecture.md` Part 2
- [S6] **Execute DPAs with LLM providers** — execute DPAs with Anthropic/OpenAI/Google for the relay API accounts (sub-processor agreements). Needed before v1.0, not for alpha
- **GDPR statement** — data processing description (local-first, API calls to LLM providers)
- **Accessibility statement** — VoiceOver compatibility, keyboard navigation
- **Open source license display** — AGPL notice in app + dependency licenses

### Could
- **Cookie/tracking transparency** — App Tracking Transparency framework (likely N/A for local-first)

---

## 13. Go-to-market — revenue enablement

### Must
- **~~Pricing decision~~** — $/month, what's included, free tier?
- [S6] **Blog at substack** — minimal posts and place for people to gather and chat. cross posts from linkedin
- [S6] **Launch Blog post** — "why we built Bristlenose" story 3 minute read
- ~~[S6] **Public-facing website 1** — brochure landing page at bristlenose.app. Deployed 15 Apr 2026 via rsync to DreamHost. Still needs: video, speed demo GIF, comparison section, App Store download link~~
- ~~[S6] **Public-facing website 2** — manual page at bristlenose.app/manual.html. Deployed 15 Apr 2026~~
- ~~[S6] **Landing page + domain** — `bristlenose.app` registered (DreamHost), DNS configured, site deployed. Deploy skill: `/deploy-website`. Shell alias: `deploy-website`~~
- [S6] **App Store screenshots** — 3-5 screenshots at required resolutions
- [S6] **App Store preview video** — 15-30 second demo (optional but high impact)

### Should
- **Product Hunt launch** — prepared assets, description, maker comment
- **Demo dataset** — sample project that ships with app or is downloadable, so new users see a real report immediately
- **Twitter/LinkedIn announcement** — launch thread with GIF/video
- **HN Show post** — "Show HN: Local-first user research analysis"
- **UX research community outreach** — ResearchOps Slack, UXPA, mixed methods communities


### Could

- **Academic outreach** — HCI conferences, PhD students
- **Referral/word-of-mouth** — "share with a colleague" in-app prompt

### Won’t
- **Comparison page** — vs Dovetail, vs EnjoyHQ, vs manual spreadsheet

---

## 14. Accessibility — inclusive by default

### Must
- [S5] **Systematic accessibility review via ux-review skill** — run the `ux-review` agent on every new feature before merge and retroactively on all existing interactive surfaces (modals, sidebar, tag input, toolbar, quote cards, analysis page). The skill checks WCAG 2.1 AA, keyboard navigation, ARIA roles, focus management, screen reader support, and reduced motion. Make this a gated step in the feature workflow, not an afterthought
- [S5] **Non-focusable interactive elements (span onClick → button)** — Add Tag (+) on QuoteCard, Badge delete, Badge accept/deny actions, Counter unhide are all bare `<span onClick>` — invisible to keyboard users and screen readers. Convert to `<button>` with `aria-label`. (a11y audit, critical)
- [S5] **TagInput: implement WAI-ARIA combobox pattern** — missing `role="combobox"`, `aria-expanded`, `aria-autocomplete="list"`, `aria-controls`, `aria-activedescendant`. Suggestion list needs `role="listbox"`, items need `role="option"`. (a11y audit, critical)
- [S5] **Modal atom accessibility upgrade** — `role="dialog"`, `aria-modal`, focus trap, focus restore as a shared hook/wrapper. Retrofit to all 6 modals (HelpModal, ExportDialog, FeedbackModal, AutoCodeReportModal, ThresholdReviewModal, SettingsModal). HelpModal is the worst — no dialog role, no focus trap, no focus return. SettingsModal's ModalNav pattern is the reference implementation. (a11y audit, major)
- [S5] **NavBar: remove incorrect role="tablist"** — router links are not ARIA tabs; no matching `role="tabpanel"` exists. Semantic `<nav>` with links is correct. (a11y audit, major)
- [S5] **Missing aria-labels on inputs** — SearchBox ("Filter quotes"), TagInput ("Add tag"), TagSidebar search ("Search tags"), TagFilterDropdown search ("Search tags"). Placeholder text is not a label. (a11y audit, major)
- [S5] **ViewSwitcher dropdown keyboard navigation** — menu items have no `tabindex`, no Arrow key navigation, no Enter/Space to select, no Escape to close. (a11y audit, major)
- [S5] **Icon contrast failures** — `--bn-colour-icon-idle` (#c9ccd1 on white = 1.8:1) and `--bn-colour-starred` (#999 on white = 2.8:1) fail WCAG 1.4.11 non-text contrast (3:1 required). Dark mode `--bn-colour-icon-idle` (#595959 on #111 = 2.4:1) also fails. (a11y audit, major)
- [S5] **No `<main>` landmark** — QuotesTab renders in a bare fragment. Wrap `<Outlet>` in AppLayout's center column with `<main>`. (a11y audit, major)
- [S6] **Keyboard navigation audit** — verify all interactive elements reachable via Tab
- [S6] **VoiceOver testing** — basic screen reader pass on report and desktop app
- [S6] **Colour contrast** — WCAG AA on all text (light + dark mode)
- [S5] **Focus indicators** — visible focus rings on all interactive elements

### Should
- **Toast announcements** — toast container (e.g. "3 quotes copied as CSV") needs `role="status"` or `aria-live="polite"` for screen reader announcements. (a11y audit, major)
- **ARIA attributes** — proper roles on custom widgets (sidebar, tag input, dropdowns) (#24)
- **Reduced motion** — `prefers-reduced-motion` respected (partially shipped in 0.13.0)
- **eslint-plugin-jsx-a11y** — lint-time a11y checks
- **axe-core in Playwright** — automated a11y assertions in E2E
- **aria-live regions** — announcements for async operations (tag applied, quote hidden, key validated, export complete)
- **Desktop a11y: focus management** — on project switch (`webView.becomeFirstResponder()` on "ready" bridge message) and on tab switch (Cmd+1-5: focus first meaningful heading after React Router navigation). Currently focus lands in undefined location
- **Desktop a11y: drag handle ARIA** — add `role="separator"` with `aria-orientation="vertical"` and `aria-valuenow`/`valuemin`/`valuemax` to sidebar resize handles
- **Desktop a11y: Dynamic Type scaling curve** — define native→web font-size mapping (system `preferredContentSizeCategory` → CSS `font-size` on `<html>`). Observe changes via `NSApp` and re-inject
- **Desktop a11y: minor fixes** — segmented picker label ("Report section" not "Tab"), verify `<h1>` in embedded mode, bare-key vs VoiceOver Quick Nav documentation, settings slider accessible values, API key toggle state traits

### Could
- **High contrast mode** — Windows high contrast / forced-colors support

---

## 15. Performance — "never let it get slower"

Safari's performance team made WebKit fast by never allowing it to become slower — every commit runs benchmarks, regressions are rejected before they land. The report SPA is the core product surface inside both the macOS app and the CLI. It needs the same discipline. Full design doc: `spa-performance.md`.

**The plan: profile first, then fix by impact, then gate in CI.**

### Must
- [S1] **Profile against FOSSDA dataset** — run Lighthouse, Playwright DOM count, Xcode Instruments Animation Hitches, and manual scroll testing against FOSSDA interviews (~10 sessions). Record baselines for TTI, FCP, LCP, CLS, DOM node count, bundle size, static export file size. You can't prioritise what you haven't measured. This is step 0. FOSSDA downloaded, unblocked now
- ~~[S1] **Bundle size CI gate** — `size-limit` + `@size-limit/file`, 305 KB gzip limit. CI enforces in `frontend-lint-type-test` job. Current ~300 KB. 100 KB target needs route-level code splitting (separate task)~~
- ~~[S1] **`GZipMiddleware` in FastAPI** — one line. ~70% reduction in served HTML/CSS/JS. Free win for WKWebView and browser~~
- ~~[S1] **`content-visibility: auto` on quote card containers** — CSS only, works everywhere including file://. Browser skips layout/paint for off-screen cards. Supported since Safari 17.4. Essential for static export path where JS virtualisation isn't possible~~
- [Icebox] **`@tanstack/virtual` in serve mode** — deferred 17 Apr 2026. Stress sweep (see git log: `stress sweep findings: clean linear scaling to n=3000`) shows clean linear scaling up to 3000 synthetic quotes, well above the 1,500-quote 15h-study ceiling. Not a blocker for alpha or launch. Re-open if real-world use surfaces pathological cases
- ~~[S1] **Move `<script>` to end of `<body>`** — script block is already at end of `<body>` (after all `<article>` content, before `</body>`). No `<head>` scripts exist. Done~~
- [S2] **Performance regression gate in CI** — Playwright spec in existing E2E suite measuring DOM node count, API latency, export file size against smoke-test fixture. Doubling rule (fail at 2x baseline). Measured baselines: quotes page 549 nodes, export 1.6 MB. Design doc reviewed, ready to implement. See `docs/design-perf-regression-gate.md`
- ~~[S1] **`perf-review` agent** — Claude Code agent (`.claude/agents/perf-review.md`) that reviews PRs for performance regressions: new deps without size justification, unvirtualised large lists, missing `passive: true`, blocking resource additions. Catches the obvious stuff before CI catches the rest~~

### Should
- **`contain: layout style`** on sidebar panels and modals — tells browser it can skip these during layout
- **Debounce search input** at 150ms if not already done
- **`passive: true`** on all scroll/touch event listeners
- **Route-based code splitting** — `React.lazy()` per tab (quotes, transcripts, codebook, analysis, settings). Vite handles this natively
- **`React.memo` on repeated components** — QuoteCard, SessionRow, TagBadge. Rule: every component rendered > 50 times in a list must be memoised
- **Dynamic `import()` for Three.js fish** — ~168 KB gzip must never be in the critical path
- **Lighthouse CI** — run on every PR once serve mode is stable. Warn < 90, fail < 70
- **Minify CSS/JS in static export** — Python build step, reduces inline code by ~40-60%
- **WKWebView: disable `dataDetectorTypes`** — prevents unwanted layout work on quote cards
- **WKWebView: inject critical CSS via `WKUserScript` at `.atDocumentStart`** — eliminates flash-of-unstyled-content on cold loads
- **Replace `setInterval` player polling** with `BroadcastChannel` or `beforeunload` — timer runs even when player is closed
- **Profile in WKWebView specifically** — Xcode Instruments before each desktop release. JavaScriptCore has different optimisation behaviour to V8
- **WKWebView stress-test confirmation pass (post-launch-fast)** — the synthetic stress harness (`scripts/perf-stress.sh`) is Chromium-only today; fine for proving virtualisation works, but desktop ships primarily via WKWebView (JavaScriptCore). Add a WebKit project to `e2e/playwright.stress.config.ts` or a separate `run-in-wkwebview.swift` that loads the served report in a real WKWebView, runs the same DOM/paint assertions, and writes to `stress-results-wkwebview.json`. Compare deltas vs Chromium. Blocks signing off any virtualisation-adjacent perf claim for the desktop build

### Could
- **`@tanstack/virtual`** for quote lists > 100 items — only if `content-visibility` is insufficient (measure first)
- **PurgeCSS** — strip unused CSS from the 4,366-line design system per page
- **`<link rel="modulepreload">`** for anticipated next routes
- **API pagination** — 50 quotes per page for large datasets
- **Static export CSS splitting** — critical (above-fold) inline, deferred (print, modals) loaded via `requestIdleCallback`

### Won't (100 days)
- **Service workers** — local-first app doesn't need offline cache. Revisit at SaaS tier
- **SSR / static generation** — local server, not CDN. React hydration is fine
- **Optimise the vanilla JS frozen path** — deprecated, don't invest

---

## Active feature branches

| Branch | Started | Description | Merge target |
|--------|---------|-------------|-------------|
| `symbology` | 12 Feb | Unicode prefix symbols (§ ¶ ❋) across UI | main |
| `highlighter` | 13 Feb | Highlighter feature (scope TBD) — **Icebox** | main |
| `living-fish` | 26 Feb | Animated bristlenose logo — **Icebox** | main |

---

## GitHub issues to close as obsolete

- **#29** — Reactive UI architecture (superseded by React migration, complete)
- **#16** — Refactor render_html.py (done in 0.13.2)
- **#7, #8, #9, #10, #22, #23** — Vanilla JS improvements (frozen/deprecated path)

---

## Items needing design docs before implementation

1. ~~Multi-project support (Milestone 4)~~ — design docs complete: `docs/design-multi-project.md`, `docs/design-project-sidebar.md`
2. File import / drag-and-drop (Milestone 5)
3. Settings UI (Milestone 6)
4. Run pipeline from GUI (Milestone 7)
5. First-run experience / onboarding
6. App Store subscription infrastructure
7. Pricing model

---

## Dependency maintenance due in window

- **Quarterly review: May 2026** — `pip list --outdated`, bump for security/features
- **Python 3.10 EOL: Oct 2026** — decide minimum version before launch
- **faster-whisper/ctranslate2 health check** — HIGH risk dependency, monitor

---

## Post 100 days

Items deliberately deferred past the 100-day window. Reasons vary: dependence on Apple's 2026 release cycle (WWDC 8 June, macOS 27 developer beta shortly after, public release September), hardware not yet available, or commercial-stage prerequisites that the alpha doesn't yet meet.

- **Succession plan** — bus-factor doc (every account/credential/recovery path), password manager emergency access for one trusted person. (infrastructure-and-identity.md) — draft complete (`docs/private/succession-plan.md`), Apple Developer renewal date filled in (2027-04-16, Team ID `Z56GZVA2QB`); still needs: password manager emergency access config, successor briefing. **Deferred beyond 100days (17 Apr 2026):** no income, no commercial asset yet — inheritable asset is Martin shipping, not a repo. Revisit when Ltd is set up or there's paying customers.

- **Per-stage pluggable backends — stage A/B benchmark** — full plan in [`docs/design-stage-backends.md`](../design-stage-backends.md). s10 `quote_extraction` dominates both wall time (47.6%) and LLM cost (92.5%) on real runs; on Teams/Zoom inputs (s05 skipped) it becomes ~90% of runtime. The spike is designed as a re-runnable benchmark, not a one-shot. Sequencing: Phase A (cloud + Ollama harness, cheap, can run any time) → Phase B (MLX arm, Python-native, no Swift; most valuable against M5 / macOS 27 stack) → Phase C (Apple FM Swift shim, wait for post-WWDC FM announcements — chasing today's 4k-context 3B before the next OS ships risks throwing away work). Target: first full benchmark snapshot at macOS 27 developer beta (July 2026), re-run at GA (September 2026), re-run again before Jan 2027 launch copy is finalised. Apple ML Research's Nov 2025 M5 benchmarks (3.3–4× TTFT over M4, 14B dense at <10s TTFT, 30B MoE at <3s) are the reason this is worth planning for, not dismissing.

---

## Investigations (no commitment — explore if time allows)

These are speculative ideas worth thinking about but without a delivery commitment:

- **Sentiment badges as built-in codebook framework** — sentiments are conceptually just another codebook; unifying would simplify thresholds, review dialog, accept/deny. Big but significant
- **Tag namespace uniqueness + import merge strategy** — flat namespace, clash detection, provenance tracking (user vs framework vs AutoCode)
- **Canonical tag → colour as first-class schema** — persist `colour_set`/`colour_index` on `TagDefinition` to survive reordering; eliminate client-side colour computation
- **Sidebar filter undo history stack** — multi-step undo for tag filter state changes (show-only clicks, tick toggles). See `docs/design-codebook-autocomplete.md` Decision 6b
- **Measure-aware leading** — line-height should increase with wider columns (Bringhurst §2.1.2). Explore interpolating across 23rem–52rem range. Playground has a slider already
- **Tokenise acceptance flash as design system pattern** — generalise `badge-accept-flash` into reusable `.bn-confirm-flash` + `useFlash(key)` hook

---

*Updated 17 Apr 2026 (four passes). Fourth pass: alpha path decided — internal TestFlight, not `.dmg`. Reasoning: StoreKit needs sandbox anyway, doing it now means a modern codebase from the start. Rejected `.dmg` path items (Developer ID cert, .dmg build pipeline, Gatekeeper README) struck in §11. TestFlight upload pipeline + App Store Connect setup + App Store review compliance umbrella moved back to S2. S2 cadence: CI cleanup first, then A/B interleave sandbox/signing ↔ MVP flow steps. First upload when both tracks green (may slip to S3 — MVP quality is the deadline, not calendar). Full path in `docs/private/road-to-alpha.md`. Third pass: Mac app MVP 1-hour flow is the real gate. Added §1a MVP flow checklist. Virtualisation → Icebox (stress sweep shows clean scaling to n=3000). AI disclosure dialog marked shipped (AIConsentView.swift). Real QA path = IKEA study + CLI handholding on video calls with UXR friends. Second pass: Sprint 2 re-scoped to "Perf + TestFlight alpha pipeline": perf items first (virtualisation, regression gate), then internal TestFlight path (App Store Connect record, Apple Distribution cert, sandbox, Privacy Manifest, Export compliance, sidecar signing, AI disclosure lightweight). Second pass deduplicated Privacy Manifest + AI disclosure (kept §6 Risk as canonical, §12 Legal points there); split signing into Apple Distribution (S2, TestFlight path) vs Developer ID (S6, .dmg path); moved .dmg build pipeline, .dmg README, DPAs, and trial-key rate-limit to S6 (v1.0-blocking, not alpha-blocking). Solicitor contact: May. Previous: 15 Apr 2026. Reconciled with delivery repo copy: added §15 Performance (WebKit philosophy, profiling-first roadmap, perf-review agent, CI gates), sprint legend, iPad session outputs (privacy policy draft, ToS v0.9.1, privacy manifest, first-run experience design, new items L5/L6/I6/I7/R6), bundle size → §15 promotion. Previous: 25 Mar 2026 — domain architecture, security audit additions, shipped-item strikethrough. Original: 16 Mar 2026.*
