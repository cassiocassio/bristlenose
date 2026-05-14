# Bristlenose — 100-Day Launch Inventory

**Goal: ship Bristlenose Beta in the App Store — paid, funded relay, by-researchers-for-researchers — to a self-funding indie audience. Day-job-quit at 2000 customers.**

**Original aspiration: 30 June 2026 Beta launch.** At material risk per 8 May 2026 reframe — relay-infrastructure work spans the summer, realistic Beta launch is fall 2026, with stage 2.5 (`.dmg` from bristlenose.app) carrying the public face in the meantime. The honest psychological endpoint of "100 days" is **stage 5: ready to ask 1000+ strangers on LinkedIn for their attention** — not stage 2 (Internal TF). The countdown is to that moment.

Gathered from: TODO.md, ROADMAP.md, 37 GitHub issues, 20+ design docs, 6 CLAUDE.md files, 5 active branches, source code TODOs.

MoSCoW within each category. **100-day goal: complete every Must.**

**Icebox** sits below Could in sections that have entries. These are ideas with merit that we're deliberately not pursuing in the 100-day window — parked, not deleted. On the GitHub Projects board, Icebox is a column to the right of Done.

### Sprint schedule

Items tagged `[S1]`–`[S6]` are assigned to a sprint. Untagged items are unassigned. Synced to the [GitHub Projects board](https://github.com/cassiocassio/bristlenose-delivery) via `/sync-board`.

| Tag | Dates | Theme |
|-----|-------|-------|
| ~~[S1]~~ | ~~14–25 Apr~~ | ~~Start the clocks~~ ✅ **Done 17 Apr 2026** (8 days early; succession plan deferred beyond 100days) |
| ~~[S2]~~ | ~~28 Apr–9 May~~ | ~~Road to alpha — A/B interleave sandbox + MVP flow~~ ✅ **Declared done 7 May 2026** — see Lifecycle stages + 7 May quality reset above. Tracks A + B + C MVP all landed; Mission Sandbox PASSED 4 May; quality-reset reframed next gate as walks-fix-walks |
| [S3] | 12–23 May | Walks-fix-walks gate + Internal TF prerequisites — fold of road-to-testflight blockers (fake-success audit, pipeline silent-skip, SPA refresh, export silent-fail, ErrorBoundary, Keychain ACL, titlebar). Multi-project Phase 1 carries over from original plan |
| [S4] | 26 May–6 Jun | Critical-path completion + Internal TF cohort calls + start of relay-infra summer (Friendly-CTO Sunday §0 → relay endpoint scaffolding) |
| [S5] | 8–19 Jun | Visual + a11y, Mac craft, Beta-prep continued; relay infra ongoing |
| [S6] | 22–30 Jun | App Store admin (form-filling, screenshots, copy), Beta App Review pre-flight (External TF gate), DPA execution |

> **Beta launch (stage 5) is not 30 June 2026 — at material risk per 8 May reframe.** Realistic fall 2026, with stage 2.5 (`.dmg` from bristlenose.app) carrying the public face through summer. Friendly-CTO Sunday work-stream runs in parallel on relay-infra architecture. GA targets 2027+. See Lifecycle stages above.

**Sprint 2 re-scope v3 (17 Apr 2026).** Alpha path decided: **internal TestFlight, not `.dmg`.** Sandbox work is unavoidable (StoreKit needs it), and a `.dmg` path would be throwaway code. Doing it now gets us a modern sandbox-aware codebase from the start. Rejected items: Developer ID cert, `.dmg` build pipeline, Gatekeeper README (all struck in §11 Operations). See `docs/private/road-to-app-store.md` for the full 14-checkpoint path.

**Sprint 2 cadence — A/B/C interleave (updated 29 Apr 2026).** Three parallel tracks per `docs/private/sprint2-tracks.md`. **Track C ✅ closed 28 Apr** (C2 signing, C3 Keychain-in-sandbox, C4 Privacy Manifest, C5 supply chain — `Bristlenose.pkg` App-Store-Connect-ready). **Track B happy path ✅ shipped 26 Apr** via `port-v01-ingestion` (commit `e781ebe` → v0.15.0 — broader than predicted: ingestion + multi-project core + lifecycle); first-run polish remaining on `first-run` worktree (started 29 Apr). **Track A in progress** on `sandbox-debug` worktree (started 29 Apr). Tracks converge at first TestFlight upload (#12). Cross-channel component strategy in `docs/design-modularity.md` — what's bundled, what's Background Assets, what's CLI-only, no-fork principle. Alternate sandbox/signing steps with MVP flow / UI quality steps. Each step unblocks the other: sandbox work surfaces UI regressions (folder bookmarks, temp paths); UI work exercises the sandboxed paths. Order:

1. ~~**Clean up CI** — re-enable the E2E gate (3 parked P3 regressions), land the perf regression gate. Unblocks everything else.~~ _Done 18 Apr 2026 (ci-cleanup branch): gate flipped, 3 regressions cleared (autocode 404 allowlisted, codebook 404 allowlisted as deferred-fix to S3, auth-token wired). Plus `e2e/ALLOWLIST.md` register, Analysis page button fix, SECURITY.md honesty update, `bristlenose doctor` env-bleed check. CI passed first try post-flip (19m44s). Option B auth-token gate deferred with design plan + reminder 16 May. Python floor bump to 3.12 tracked §11 Should + reminder 9 May._
2. **A/B/A/B through S2:**
   - A: sandbox step (one entitlement + related code migration at a time)
   - B: MVP flow step (one beat of §1a below at a time)
   - Repeat. Ship nothing to friends until MVP 1-hour flow is green AND sandboxed build runs end-to-end.
3. **First TestFlight upload** lands when both tracks are green. May slip into S3 — that's fine, deadline is MVP quality, not calendar.

**Real QA = IKEA study + CLI handholding on video calls with UXR friends.** TestFlight is the delivery mechanism; video-call UXR sessions are the feedback loop.

### 4 May 2026 alpha-scope review

Reviewed S2–S4 Musts plus four S5 visual-design Musts row-by-row in `docs/private/musts-review.md` (canonical record + rationale per item). Lever applied throughout: **alpha cohort is ≤20 testers on 1:1 video calls** — anything that exists to make the product self-explanatory to strangers is beta-grade. Net effect: ~5–7 working days of S2–S4 scope removed, plus icon set + FT-grade visual polish moved out of S5.

**Demoted out of alpha-Must (now Should / Could / Won't 100 days):**
- §1 — **Export research package zip** (was [S4]) → beta. Standalone-HTML export already ships; clip extraction already ships; the zip wrapper + anonymisation pass is the value-add and that's beta-grade.
- §1 — **App Store subscription infra** (was [S4]) → v1.0 work. Alpha learns whether the product is worth paying for *before* we design the price.
- §1 — **Slow-double-click rename in sidebar** (was [S3]) → Should. Right-click + Project menu cover it for alpha.
- §1 — **Drag-to-reorder projects** (was [S3]) → Could. Three projects in alpha don't need reorder; persisted ordering wants a `position` int + migration that's not earned.
- §2 — **Import FK constraint regression coverage** (was [S3]) → Should, S6, piggyback on Playwright layers 4–5 fixtures.
- §2 — **Native toolbar tab i18n not reactive** (was [S3]) → Could. Alpha is English-only with English-speaking testers.
- §3 — **Tag density tuning** (was [S3]) → post-alpha. Tuning before alpha is guessing; IKEA + cohort feedback will point at specific cuts.
- §3 — **SVG icon set** (was [S5]) → beta-Must. Char glyphs read "indie web app" — App Store screenshots will punish that, alpha 1:1 calls won't.
- §3 — **FT.com-grade visual redesign** (was [S5]) → post-beta. Most ambitious item in S5; FT.com is the *direction*, not the alpha gate.
- §15 — **Performance regression gate in CI** (was [S2]) → Should, S6/post-alpha. Bundle-size gate already exists; stress sweep proved n=3000 scales.

**Scoped down but still alpha-Must:**
- §1 — **Multi-project support** [S3]: Phase 1 only (list, create, switch, persistent selection). Defer instance DB, person linking, cross-project search, archive lifecycle to beta. **XL → M.**
- §3 — **Colour themes (Edo)** [S5]: Edo only, **no theme-switcher UI** for alpha. **L → M.**
- §5 — **First-run experience** [S4]: existing `WelcomeView` + `BootView` + Beat 3 + Beat 3b is enough for guided 1:1; full coach-in-context to beta. **M → S.**
- §5 — **`bristlenose doctor` in GUI** [S4]: scrolling-text panel wrapping doctor stdout, not health-traffic-light UI. **S → XS.**
- §10 — **Provider setup guide** [S4]: Claude-only README plain text. **S → XS.**
- §11 — **TestFlight upload pipeline** [S2]: manual-only for first iteration; automation deferred to S6. **M → S.**
- §11 — **App Store Connect setup** [S2]: engineering work mostly done (cert, profile, bundle ID); what's left is form-filling. **S → XS.**

**Decision logged:** alpha messaging is "**known to work with Claude — please try anything else you have and let us know**." Settings UI exposes every provider; README documents Claude only; non-Claude failures are signal not regression. Free coverage from testers who already have OpenAI/Gemini/Azure/Ollama keys vs. spinning up accounts ourselves. Post-alpha: own accounts everywhere + systematic test matrix. Memory: `project_alpha_provider_strategy.md`.

**Round 2 (4 May 2026, same-evening continuation)** — completed S5 a11y/value/risk + untagged tail. Lever applied: visual design is Martin's fast lane; sandbox/Apple plumbing is the slow lane (memory: `user_visual_design_velocity.md`). Don't frame visual-design Musts as alpha risk.

**Round 2 demotions to beta-Must (a11y backlog where the audience isn't in the alpha cohort):**
- §14 — **Systematic a11y review via ux-review skill** [S5] → beta-Must. Wire the agent as a *gate on new features* now (cheap); defer the retroactive sweep.
- §14 — **TagInput ARIA combobox** [S5] → beta-Must. Hidden SR semantics.
- §14 — **Modal atom a11y upgrade** [S5] → beta-Must. M-sized shared-hook + focus-trap work.
- §14 — **Missing aria-labels on inputs** [S5] → beta-Must. Pure SR affordance.
- §14 — **ViewSwitcher dropdown keyboard nav** [S5] → beta-Must. Power-user kbd nav.
- §14 — **Focus indicators (systematic token)** [S5] → beta-Must. Pairs with #34 (alpha-Must) — `<button>`s need *some* focus treatment, but the systematic token can wait.
- §3 — **Export polish** [S5] → beta-Must, rides with #17 zip export. Whatever cleanup is needed for the standalone-HTML path moves with whichever beta milestone resurrects #17.

**Round 2 keeps alpha-Must (cheap, screenshot-visible, or fast-lane work):**
- §3 — **Grid/spacing/type/colours audit** [S5]: complements #24 + #27, fast lane.
- §3 — **Serif voice-of-user quote treatment** [S5]: typographic differentiator, rides alongside #24.
- §14 — **Non-focusable interactive elements (span→button)** [S5]: cheap, mechanical, screenshot-visible focus rings.
- §14 — **NavBar: remove `role="tablist"`** [S5]: trivial XS, factually wrong markup.
- §14 — **Icon contrast failures** [S5]: pure token edit, visible to everyone not just SR users.
- §14 — **No `<main>` landmark** [S5]: one-line wrapper.
- §1 — **Subprocess lifecycle / orphan management** (untagged): required before sandbox flips on, partially shipped 24 Apr + 26 Apr.

**Round 2 reframes (still alpha-Must, but recharacterised):**
- §4 — **QA: threshold review dialog on real data** [S5]: happens *during* alpha not before. IKEA + cohort IS the real data.
- §6 — **PII redaction audit** [S5]: scope to spot-check Presidio on IKEA + FOSSDA for alpha; full `[pii]` extra split + Background Assets pack is beta-Must. Alpha cohort = consensual UXR friends, not paying customers handling third-party data.
- §9 — **Desktop UX iteration backlog** (untagged): pairs with S5 visual pass; same kind of work, same fast lane.

**Round 2 status-quo (already deferred, no change):** §1 Alpha telemetry Phases 2–4, §6/§11 Developer ID cert, §15 Bundle slimming pass.

**Round 2 opportunistic (no sprint slot):** §9 `BristlenoseTests` fixture re-include — surface when test fails or new locale added.

**Still not reviewed:** all of S6 (#43–#62). Deferred deliberately — form-filling, copy, legal, and screenshots, none of which have scope decisions that benefit from being made now.



Performance: stress sweep shows clean linear scaling to 3000 quotes — virtualisation deferred to Icebox. AI disclosure dialog: already shipped (`AIConsentView.swift`). Solicitor contact: still May (external TestFlight and public legal paperwork are S6+, not alpha-blocking).

## Lifecycle stages (locked 8 May 2026)

The six stages in sequence. Each stage does one job. Stage-prerequisite context on Musts in the numbered sections below indicates which stage a Must gates. Canonical reference: `project_lifecycle_stages.md` memory.

| # | Internal name | Public | Audience | Channel | Money |
|---|---|---|---|---|---|
| 1 | Solo | — | Martin | Local build | — |
| 2 | Internal TF | (private) | 5–10 watched UXR friends | TestFlight invite | Free |
| 2.5 | `.dmg` from bristlenose.app | Public download | 10–50 friends-of-friends | Direct download | Free, BYOK |
| 4 | External TF gate | (Apple only) | Apple reviewers | App Store Connect submission | Free, no testers |
| 5 | Beta in store | `Bristlenose Beta` | ≤50–100 paying purchasers | App Store | $5 + funded relay |
| 6 | GA | `Bristlenose` | Open | App Store | Subscription / packs |

"Alpha" is internal-planning-only, never user-facing. "Beta" = paid-in-store with funded relay. "GA" = subscription. Sparkle integration plan: `docs/private/sparkle-plan.md`.

## Critical Path to Internal TF (active focus, 8 May 2026)

_View only — links to canonical entries by title in numbered sections below. Sprint tags on canonical entries drive `/sync-board`. Each completed lifecycle stage shifts the active focus._

### Now
~~**Pipeline silently skips stages 2–11 on raw video**~~ ✅ **Done — verified 12 May 2026** — eliminated in current main by v0.15.4's `prepend_bundled_to_path()` + v0.15.5's preflight block. Both original repros were on a 0.15.3 sidecar pre-dating both fixes; the smoking gun (`mlx_whisper`'s bare `"ffmpeg"` shellout failing under sandbox PATH) was sitting in `bristlenose.log`. Re-run on `foo` with stripped PATH confirmed preflight aborts cleanly with no fake-success state. Two small leaks for follow-up: exit code 0 on preflight failure (should be 2); `--clean` scope leaves stale empty `sessions/` / `transcripts-raw/` dirs. Canonical: §1 line 340. End-to-end verification with fresh sandboxed-sidecar build still pending.

### Next
~~**React SPA misses pipeline-completion signal**~~ ✅ **Done 10 May 2026** — canonical §2 line 341.

### Then
~~**Filesystem export silent fail under sandbox**~~ ✅ **HTML report path done 10 May 2026** — canonical §2 line 342. Other export surfaces (clips / CSV / slides / anonymised bundle) still need the same `NSSavePanel` routing; promote into the new ladder if they're the next gate.

### Promote next (12 May 2026)
_The Now/Next/Then ladder is fully cleared. Pick the new Now from in-flight cluster work or open surfaces. Candidates:_
- ~~**A4 stage-cache honesty**~~ ✅ **Done 12 May 2026** (`0381a06` / `9d2cd2e`) — abandon-check now fires BEFORE `mark_stage_complete`; s08 abandon-check added; s10+s11 flipped soft→hard with `StageFailure` emitted at the LLM call site before fallback runs; `mark_stage_complete` refuses to record `content_hash` for empty content; privacy contract on `cause.message` (class name + provider + stage, never `str(exc)`); Whisper-zero-segments treated as success; `topics` bucket added to `PipelineSummary`, contract fixture bumped to v5; 470 lines of new tests across `test_pipeline_abandon.py` / `test_manifest.py` / `test_run_lifecycle.py`. Open follow-ups (small, defer or fold into D1): #17 duplicate-quote-rows dedup on re-run; #1 HF Hub unauthenticated warning mid-spinner; explicit `bristlenose analyze` smoke repro (Pass 3 acceptance gap).
- **D1 stage-contract audit** (S1, meta-plan systemic follow-up, now unblocked) — audits all 12 stages for the silent-empty failure class and introduces a `StageGuard` contract preventing recurrence. Gated on A4 + B1 having shipped first (both ✅, May 12 + 14) so the worked pattern exists before generalising. Plan: `docs/private/plans/2026-05-meta-plan.md` §D1; coherence doc: `docs/private/plans/2026-05-cluster-coherence.md`.
- ~~**B1 long-audio quality**~~ ✅ **Done 14 May 2026** — Whisper hallucination + untranscribed gaps + diarization-collapse. Pre-implementation diagnostic against preserved IKEA artefacts showed only one of three bugs reproducing as described: role-inversion did NOT reproduce (current run correctly assigns m1=moderator, p1=participant); `pct_words` 0/100 is by-design (m-codes intentionally excluded from denominator); mid-stream "diarization decay" is real but architectural (LLM splitter forward-propagates last label from 5–8 min sample window past the window). Shipped: regression-pin unit tests for heuristic + `pct_words` (defends against silent flip on future refactors); design-doc clarification + INFO log surfacing the propagation limit; Whisper parameter tuning (`condition_on_previous_text=False`, `no_speech_threshold=0.85`, `compression_ratio_threshold=1.8`) for mlx-whisper; `collapse_adjacent_repeats()` post-processor catching Whisper looping ("thanks thanks thanks", "facebook facebook") while preserving natural interjection doubling ("No. No. No.", "yeah yeah"). 5 files, ~155 lines. Review log: `docs/private/reviews/b1-long-audio-quality.md` (29 findings).
- **Remaining export surfaces under sandbox** — clips / CSV / slides / anonymised bundle (route via `WKDownload` + `NSSavePanel` like the HTML path)
- **C-stream UX papercuts** (S3, post-A-stream) — 14 items from 9 May IKEA call
- **tf-multi-project Phase 2** (S3, gate for cohort calls 2+) — sidecar-restart switch (#1), drag-onto-existing (#11), folder watcher (#14). Multiple facets stack — none replaces the others: (a) **Sequencing** — has to land before cohort call 2 so the next few sessions can exercise multi-project gestures. (b) **Credibility** — spruce sidebar signals "serious tool, give it serious feedback"; half-working sidebar reads "not ready, why are you showing me this" and the doubt bleeds into how URs assess the rest of the app. (c) **Feel credible AND work** — both at once, the UR doesn't separate them; a sidebar that *looks* fine and then loses scroll on switch / shows wrong project's data for 200ms / flashes-and-stalls on drop grows the tyre-kicking conversation more than a visibly-rough one would. Polish without function is worse than absent. (d) **Substance of the call** is research-craft — are quotes/tags/signals useful and usable in real UR work? (e) **Tyre-kicking is inevitable side-conversation** — Phase 2's job is making the obvious tyre-kicks brief so the substantive conversation gets the airtime. Martin could functionally coax URs through CLI+brew, but that setup *is* a long tyre-kicking conversation. Call 1 with Simon (friendly-CTO) was acceptably spent on brew/A-stream because CTOs read "early build" as context and tyre-kicking *is* their substantive conversation; working URs aren't calibrated that way and shouldn't have to be. Phase 0 + Phase 1 shipped 14 May 2026 (schema lock, `ProjectAvailability`, undo-toast Remove, Locate flow); Phase 2 is the gate for cohort call 2. Live plan: `.claude/plans/tf-multi-project.md`. Canonical entry: §1 line 246.

### Internal TF gate criteria
- Walks-fix-walks gate: 2–3 consecutive walks across different scenarios produce zero new snags
- Research-craft surface engageable: 60-minute walk where attention doesn't bounce sideways
- 5–10 trusted UXR friends recruited as ASC users with Apple IDs collected
- App Store Connect app record minimally complete (no listing copy / screenshots needed for Internal TF)
- First TestFlight upload succeeds and appears in TF Internal

### After Internal TF
Active focus shifts to stage 2.5 (`.dmg` from bristlenose.app). Sparkle integration plan: `docs/private/sparkle-plan.md`. Friendly-CTO Sunday §0 first.

### Lateral wins shipped 6–14 May 2026 (not in any plan doc at start of window)

Out-of-order discoveries and infrastructure work that landed alongside the planned A-stream + B1. Captured here so reverse-audit and sitreps see them; not load-bearing tracker entries.

- **CLI "just works" preflight block** (v0.15.5, 11 May) — api-key + whisper + ffmpeg preflights, HF progress-bar suppression, `count_noun`/inflect plurals, 6-locale `preflight.*` i18n namespace, lazy-fetch `en_core_web_sm`. Broader than A2's original scope. Design doc: `docs/design-cli-just-works.md`.
- **Pipeline diagnostic popover infrastructure** (7 May) — `design-pipeline-diagnostic-popover.md` + `MessageKind` taxonomy + structured per-stage failure summaries + cross-branch contract fixture (v1 → v5). Branches: `pipeline-summary-events`, `pipeline-diagnostic-pill`, `cli-message-kinds`. Foundation under A4 and the desktop failure pill.
- **Generic failure-surface** (v0.15.6, 11 May, `488952d`) — server-rendered status page for incomplete/failed/cancelled runs. Catches "navigate to a report mid-run" case.
- **SPA trust-UX** (10 May, `7136890` + `9e173e2`) — auto-refetch on pipeline completion + manual refresh button + refetch overlay + post-zero-quotes empty-state copy. Wasn't on any plan doc.
- **Sandbox export — HTML path** (10 May, `4f1b8c4`) — `WKDownload` + `NSSavePanel` routing. Other export surfaces (clips/CSV/slides/anonymised bundle) still pending.
- **Session-handoff sentinels** (14 May, `0054fea` + `07506dc`) — `/end-session` sign-off sentinel + `/close-branch` drift check. Workflow tooling, now load-bearing.
- **CI hygiene** (13 May) — `.tool-versions` node + python pin (`3bc1796`), no-red-CI-merges policy in CONTRIBUTING (`c9d1c81`), release-pipeline unblock (v0.15.7, `040c520`).
- **Workflow / agent ecosystem** (14 May) — James Bach reviewer agent + test philosophy doc (`958cca5`), `/new-feature --print-launch-url` + Step 14 hand-off (`2a737f8`), true-the-docs v2 with `--claude-pointers` mode (`2d3a019`).
- **Sandbox fixes** (7 May) — `prepend_bundled_to_path()` for mlx_whisper bare-name shellout (`d3ed409`), serve-importer re-import on `run_completed` (`02daeee`), `reset-app-state.sh` helper (12 May, `824422d`).
- **Captured design docs** (now in `TODO.md` Ideas): `design-incremental-analysis.md` (13 May), `design-asr-backend-strategy.md` (11 May), `design-native-vs-web-surfaces.md` (12 May), `design-cli-analysis-register.md` + cli-ux.yaml codebook (11 May).

## 7 May 2026 quality reset

Mission Sandbox passed 4 May. The two weeks before that were sandbox plumbing — entitlements, codesigning, sidecar trim, Keychain under sandbox, first-run beats, log-tail trust. None of it required operating the app as a user. The 7 May UX walk was the first end-to-end session in two weeks, and the snagging list isn't last-mile polish — it's a class of bug: **fake success feedback**. Exports that don't export. Pipelines that report "Analysed" without producing transcripts. SPA that shows empty state on a completed run. AutoCode buttons firing on groups they can't produce work for. The user's mental model of "did this work?" can't currently be trusted anywhere in the app.

**The new gate:** operate the app end-to-end as a user; nothing surprises you in a session. Not a list of items — a property of the product. Drop a folder, get a report, browse it, export it, close it, re-open it, change provider, run again — no surprises, no fake-success states, no crashes, no raw keys, no broken affordances. Then the cohort question re-opens.

**Why we don't share yet.** Five seasoned UXR friends' evenings are the most valuable signal source we have. We save them for what they're actually good at — study design, methodology critique, edge cases in real research workflow, cross-cohort patterns. We don't burn them on "the export button doesn't export" or "the toolbar is ugly" — we already know all of that, we'd waste their time finding it, and first impressions don't reset. The conversation worth having is on the research-craft surface (tags / codebook / AutoCode threshold review / signals / quote ergonomics). None of it lands if the first ten minutes are spent finding out the basic-affordance surface is broken.

**Duration measured in walks, not weeks.** Could be 2 weeks. Could be 6. The metric isn't elapsed time — it's walks-without-new-snags. When 2–3 consecutive walks across different scenarios produce nothing new, the cohort conversation re-opens, and likely starts smaller than five-at-once anyway.

## Three positioning differentiators (in priority order)

1. **By researchers, for researchers** — THE pitch. Headline. Listing copy. Welcome view. LinkedIn framing. The competitive frame against Dovetail/Marvin: those tools are built for *making research consumable by non-researchers* (PMs, stakeholders); Bristlenose is for **the analysis pass itself** — the deep listen, the coding, the pattern emergence. Product-decision test: does this feature help the researcher do the listening, or help someone who wasn't in the room consume the listening? First is core; second is incidental and probably off-roadmap. Pulled toward the second = Dovetail-drift = lose the audience the product is for.
2. **Native Mac craft** — secret weapon, never headlined. Pxlnv / Daring Fireball / Hypercritical / The Sweet Setup readers detect it without being told. Few percent of any population, disproportionately the recommender-class. *Craft, not slogan*: signals through what doesn't go wrong (toolbar feels right, sidebar feels Photos-like, Tahoe glass-bar lands, NSWindow popouts have proper titlebars). Telegraphing it ("natively built for Mac!") undermines the effect — the audience that cares doesn't need telling and the audience that doesn't care won't notice the claim.
3. **Local-first** — footnote / virtue-flag. Becomes headline candidate when M6+ silicon makes local-model analysis quality-competitive (2027+). Until then, mention where it matters internally, never as the lead.

Layered signal: deep audience (researcher) recognises the deep alignment. Very-deep audience (researcher + Mac-craft) recognises both. Neither layer telegraphed.

## Customer profile (ICP) and negative roadmap

**The customer is the buyer, the user, and the toolchain decision-maker — same person.** Own credit card. No procurement gate. No IT compliance review. No enterprise contract signed two reorgs ago. Once a studio gets big enough, standardisation kicks in — Dovetail because someone signed the contract, Photoshop layers because that's what the team uses. **Bristlenose customers are the people who would suffer working there.**

Concrete profile: freelancers, indie consultants, head-of-research-at-tiny-shop, senior researchers with leverage over their own toolchain even in larger orgs. Personality trait: routinely BYOD their Mac into Windows-default offices, refuse Outlook for Mail.app, keep personal Adobe / Things / HEY subs despite their org's standardisation, would rather buy their own tool than use the locked-down approved one. Mac-craft-aware *and* freelancer-mindset *and* taste-driven *and* willing-to-pay. Reads Daring Fireball, Pxlnv, Six Colors, The Sweet Setup, ATP listener-class. Mastodon over LinkedIn. Substack subscriptions to people they respect. **Concrete demographic exemplar: The Sweet Setup interview subjects + readership.**

**App Store distribution itself filters the audience.** Enterprise IT blocks App Store on managed Macs as standard policy; procurement won't approve $5 personal purchases. People for whom App Store works are by definition not behind the procurement wall. No work needed to exclude the wrong audience; distribution does it.

**Negative roadmap (deliberate not-build categories — fail the ICP lens):**
- Enterprise SSO / SAML
- SOC2 compliance
- Audit logging for compliance officers
- Admin consoles
- Multi-seat licensing
- Bulk procurement / volume licensing
- DPA / vendor-onboarding paperwork at scale
- Stakeholder-export-as-headline (export zip ships, but not as the pitch)

All real work that real B2B SaaS companies do; none serves this customer profile. Rejecting as a category frees roadmap and stays consistent with positioning.

## 2000-customer day-job-quit target

**Target: 2000 paying customers globally** — Martin's day-job-quit threshold (stated 8 May 2026).

Sizing: global UXR community ~250k–400k practitioners; addressable niche after ICP filters (individual-purchaser autonomy × Mac × willing-to-pay × App-Store-accessible) ~50k–80k. **2000 = ~3–4% capture of addressable niche** = ~0.6% of broad UXR community. Squarely in indie-Mac-app-business territory: Things, Bear, Drafts, Reeder, iA Writer all operate at 50k–500k paying users with sustainable economics.

Time horizon: realistically year 2–4 from Beta launch. Daring Fireball / Sweet Setup / ATP-Charlie editorial boost compresses by 6–18 months if it lands. Higher per-customer willingness-to-pay than note-taking apps (professional tool-ROI, $15–20/month plausible vs $3–5/month). Higher recommender-density inside niche (UXRs talk to UXRs at conferences, on Mastodon, in Slack — dense peer-graph, higher viral coefficient than diffuse general-Mac audiences).

**Cheap signal Beta surfaces:** conversion from "tried for $5 with funded preview" to "kept paying after trial credit ran out." **>15% conversion → 2000 is on track.** **<5% conversion → product needs more iteration before betting day job.**

2000 is *enough to quit*, not *the ceiling*. Same machinery that gets to 2000 keeps working past it. Day-job-quit number is the reasonable-bet threshold; upside above is real and not capped.

**Lens for scope decisions:** does this contribute to or distract from the path to 2000 paying individual-purchaser customers? Enterprise features fail the lens. Stakeholder-export features fail the lens. Mac-craft polish, codebook framework richness, peer-recommendation channels, editorial-venue craft — all serve the lens.

## Two-mode data architecture and two gates

**Two-mode data architecture:**
- **Pre-Beta (CLI, Internal TF, `.dmg`):** transcripts go directly from user's Mac to Anthropic on **user's** key. Bristlenose never touches them. Local-first technically true.
- **Beta funded preview window (≤$4 of relay credits per user):** transcripts route through **Bristlenose's relay on Martin's key**. Bristlenose is data controller in transit. **DPA with Anthropic required before any traffic flows.**
- **Post-credit-exhaustion BYOK fallback:** restores pre-Beta direct path. Two-mode messaging in privacy policy.

**Two gates, two bars:**
- **Internal TF gate (cohort):** NO surprises. Every minute of 5-hour cohort time protected. "Could you have spent this hour talking about codebooks / signals / quotes rather than apologising?"
- **Beta gate (paid public, original-warning-label):** warning-label-tolerable rough edges allowed *if* the warning is visible. "Would someone reading 'Beta — things will break' be surprised by THIS specific issue?" The original-Beta meaning of the word is reclaimed; "things will break" is the social contract.

## Editorial channel discipline

Marketing channels are peer-recommendation + editorial coverage from craft venues — Daring Fireball linklog, Pxlnv, Six Colors, The Sweet Setup app reviews, ATP "Charlie" segment, Mastodon, indie Substacks. *Not* LinkedIn ads, *not* "5 ways to improve your research workflow" content marketing. One Beta tester who recommends to one peer >> 1000 LinkedIn impressions to PMs.

**Don't pitch craft venues until there's a polished thing to point at.** They don't review unfinished things and reviewing too early burns the chance permanently. One-shot per outlet. Premature pitch = relationship gone.

**External TF reframed as a GATE not a STAGE.** Submit a build → Beta App Review (24–48h, Apple verdict) → either passes or bounces. No tester recruitment, no 90-day rebuild cadence, no feedback channel work. Apple-review reconnaissance only. Internal TF can grow 5 → 20 → 50 → up to 100 testers within its own ceiling without crossing into External TF territory.

---

## 1. Missing — essential feature gaps ("it's not done without it")

### Must
- [S1-S5] **IKEA codebook validation dataset** — 5 moderated IKEA interviews with UXR friends (favours, not schedulable). ~1/week over S1–S5. Tests whether sentiment categories, UXR codebook (moderator questions, friction, sentiment), and thematic grouping produce useful results on real research data. Also provides marketing screenshots and speed demo video. (design-real-data-testing.md). **Locked 8 May 2026:** target is 2–3 × ~10 min videos, all using the same IKEA prompt set (described in Cohort call protocol below) so they're combinable with the cohort member's own session into one project. These pre-recorded videos are the dropbox-shareable input for cohort calls. **Marketing use (locked 8 May 2026):** the IKEA cohort projects double as bristlenose.app + App Store screenshot source — real users talking about a real project, not synthetic demo data. Constraints when selecting quotes/screenshots: (a) no libel of IKEA — pick quotes about UX of checkout / store layout / flatpack assembly, not "IKEA wronged me" specifics; (b) anonymise participants — fake names + either blurred faces or explicit written permission per participant; (c) consent gradient applies — verbal consent on the call covers research use; marketing use requires a separate explicit-consent step (see `docs/methodology/consent-gradient.md`). Worth scripting the consent-conversation prompt before the first cohort call so it's not improvised on the day.
- **Cohort call protocol — five-part IKEA structure with dogfooded analysis** — [stage-2-prereq] Locked 8 May 2026 (resolves T5/TD13 product-shape question). Each Internal TF cohort call runs as a single ~5-hour session with one UXR friend, structured in five acts (acts 1–4 live on the call, act 5 post-call):
   1. **Live IKEA interview (~10–15 min, recorded).** Martin moderates, cohort member is the participant. Same prompt set every time so transcripts compose with the pre-recorded set: *"describe this checkout process"*; *"can you find a new bookcase that would fit in your living room"*; *"tell me how you feel at the end of an IKEA store visit"*; *"describe what happened the last time you self-assembled a piece of flatpack furniture."* Recorded video saved as the call's primary artefact. **Whisper 1.5 GB download runs in the background during this interview** — the ~10–15 min foreground IKEA conversation hides the model-fetch wait. **First-impression-on-call constraint:** the cohort member must NOT open the app before the call — first-impression of `WelcomeView` / `BootView` is precious user-research data we want to capture live. Pre-call homework is therefore TestFlight install only (binary download via TF), not "open and explore." This forces Whisper-during-interview unless the model is bundled out-of-box (see TD13 decision below).
   2. **First-run walk.** Cohort member opens Bristlenose for the first time, walks through `WelcomeView` / `BootView` / API key setup / new project. **Recorded.** This is the fresh-eyes first-impression session — the moment that doesn't happen twice. Their reactions, where they hesitate, what they expected vs what they see — all data the cohort calls exist to capture.
   3. **Process real content.** Cohort member uploads the 2–3 pre-recorded IKEA videos (from the dropbox link, sent in advance) plus the live interview just recorded. Pipeline runs end-to-end on real data while they watch. They — as researchers — read the moderator-question intent in the prompts, so the resulting analysis surface (themes, autotags, signals) is calibrated to known intent.
   4. **Explore Bristlenose together (~1 hour, recorded).** Martin guides the cohort member through the analysed report with **~5 prepared directing questions** pointing at general areas of the product (codebook structure / AutoCode threshold review / signal cards / quote ergonomics / themes — exact set TBD pre-call). Open conversation, not a script: the questions are seed points; the cohort member's reactions, hesitations, comparisons-to-their-own-tools and "wait, what does this do?" moments are the data. **This is the research-craft conversation the whole call exists to enable — see top-of-doc 7 May 2026 quality reset block for why we don't burn this time on bug-reporting.** Does Bristlenose's analysis match what they'd code by hand? Where does it diverge? Is this a tool they'd use? **Recorded** (this is the longer of the two recordings — IKEA interview is ~10–15 min, this is ~1 hour).
   5. **Post-call: dogfood Bristlenose on the call recording itself.** Martin runs Bristlenose on the recorded act-4 explore-together session (and act 2's first-run-walk recording) to extract product-improvement signal. The cohort member's quotes about Bristlenose ARE the research data; Bristlenose ANALYSES that data the way a researcher would analyse any user-research interview. Closes the loop: the product is its own feedback-extraction tool. Each cohort call generates both methodology validation (act 1's IKEA → does Bristlenose work on real research data?) AND product feedback (acts 2 + 4 → what did this researcher say about Bristlenose itself?). Cumulative across the cohort: 5–10 product-feedback projects, each analysed by the tool whose feedback they contain. Most honest dogfooding the project will ever do.

   **Pre-call package** (artefacts to prepare before any call): (a) Dropbox link with 2–3 × ~10 min pre-recorded IKEA interview videos; (b) TestFlight Internal install instructions (Apple ID collection step + invite link); (c) the four-prompt IKEA brief so they know what to expect of the live interview. **TestFlight Internal is the install channel** — `Bristlenose Beta` listing copy / External TF / Beta App Review etc. all out of scope for cohort calls.

   **Cohort recruitment status (8 May 2026):** **4 candidates already pre-warmed** via a WhatsApp chat and pub conversations explaining the project. **2 of the 4 have already tried the CLI version**, so they have a working mental model of Bristlenose's product shape — their act-2 first-impression captures "GUI version of the CLI thing I tried" rather than fresh-fresh first impression (different signal, still useful — calibrates against their CLI memory). Recruitment trigger is **"real thing in TestFlight"** — Martin pings the WhatsApp chat to schedule once a TF build clears the walks-fix-walks gate. Need 1 more (or 2) to reach 5-cohort floor; ceiling at ~10 within Internal TF. The friendly-CTO is one of the 4. **Implication:** there is no separate "cohort identification" project-management item — that work happened over months of pub conversations and is done. The only remaining recruitment step is the WhatsApp message at gate-clear, which takes minutes.

   **Friendly-CTO call may go first via CLI, ahead of TestFlight (8 May 2026):** the CTO is CLI-comfortable and would happily run the CLI version. The Mac-app first-impression constraint that gates the other cohort calls behind walks-fix-walks **doesn't apply to him** — his first-impression already happened, his feedback is technical/methodological, and the CLI is functionally complete in a way the Mac app is not. This means the CTO call can run *before* the walks gate clears; it doubles as the conversation starter for the broader cohort moment and gives him product context before the subsequent technical Sundays (Sparkle / relay-infra / sidecar swap / bundle-ID migration). Protocol adapts: act 2 (first-run walk) becomes a CLI walkthrough rather than `WelcomeView` first-impression; act 4 (explore together) becomes "look at the rendered HTML report and discuss themes/autotags/signals from a CLI-run analysis." Other 3+ cohort members stay gated on Mac app + walks-fix-walks because their first-impression IS the GUI moment.

   **Cohort composition decision (locked 8 May 2026):** Friendly-CTO is **one of the 5–10** cohort members, not a separate work-stream. He knows user research; running his cohort call as a particularly early one (probably the first or second) gives the product-shape conversation before the tech deep-dives, and lets him form an intuition for the tool he'll later be making architecture calls about. **Sequencing implication:** previously I was framing "schedule friendly-CTO Sunday" and "recruit cohort" as parallel project-management items. They're not — they're the same conversation, in the right order. Subsequent friendly-CTO Sundays (Sparkle architecture, relay-infra, sidecar swap, bundle-ID migration — see `docs/private/sparkle-plan.md` agenda) come AFTER his cohort call so the technical conversation has product context.

   **Resolves the deferred T5 / TD13 question:** the alpha cohort *is* doing raw video analysis (live English IKEA interview + pre-recorded English IKEA interviews), so AutoCode-non-English failure modes (T5) are NOT alpha-blockers — they stay [Beta-must]. Whisper-1.5 GB download timing (TD13) is solved by background-during-foreground-interview rather than by bundling the model out-of-box; the bundle-Whisper-OOB path stays available as a Beta-must call if cohort feedback surfaces friction.

   **Ship criteria:** pre-call package assembled and tested on Martin's own machine end-to-end; one full dry-run of all three acts done solo before the first cohort call; cohort calls don't begin until walks-fix-walks gate clears (see Critical Path / quality reset).
- **~~Desktop app v0.1~~** — SwiftUI shell, PyInstaller sidecar, folder picker, pipeline runner, "Open Report" button. ~365–435 MB bundle. (design-desktop-app.md)
- ~~**Export: standalone HTML from serve mode** — `POST /api/projects/{id}/export`, self-contained HTML. Shipped v0.11.2. (design-export-sharing.md)~~
- ~~[S4]~~ **Export: research package (zip)** — _Demoted to beta 4 May 2026 — see review block above. Standalone-HTML + clip export already ship; zip wrapper + anonymisation pass is beta-grade._ zip with report.html + transcripts/ (.txt with inline timecodes) + clips/ (optional, FFmpeg). Human-readable filenames (`p1 03m45 Sarah onboarding was confusing.mp4`). Anonymisation across all surfaces. Replaces 3 hours of Final Cut Pro work. Stages 1–3 of export roadmap. (design-export-sharing.md)
- [S3] **Multi-project support** — home screen, project list, create + switch projects. Milestone 4 in ROADMAP. Live plan: `.claude/plans/tf-multi-project.md` (supersedes the 5-phase `design-project-sidebar.md` and `design-multi-project.md` infra plan for TF scope). _Scoped 4 May 2026: Phase 1 only (list, create, switch, persistent selection). Instance DB, person linking, cross-project search, archive lifecycle deferred to beta. XL → M._ **Phase 0 + Phase 1 shipped 14 May 2026** (`206b522` schema lock + `ProjectAvailability` enum; `256e8d0` undo-toast Remove + Locate flow with Spotlight one-shot). **Phase 2 #1/#2/#3 shipped 14 May 2026** (`baf1896` merge of `multi-project-switch`) — sidebar-clicking another project tears down + respawns sidecar with HIG-correct in-flight-run confirm sheet (`ServeManager.switchProject(to:)` + escalating `shutdown(timeout:)`); `Cache-Control: no-store` middleware on `/api/projects/*`; `ProjectBookmarkLease` foundation. **Phase 2 #11 drag-onto-existing shipped 14 May 2026** in the same branch — drag-onto-project adds files via `addFiles`, project-onto-project rejected via non-modal toast, drop hit-test refactored to native per-row `.dropDestination`. **Phase 2 #14 NSFilePresenter folder watcher** remains open. **Phase 3 still open**: #10 cloud-evicted project single state.
- **~~File import (drag-and-drop)~~** — add recordings to project from GUI. Milestone 5. Needs design doc
- ~~[S3]~~ **Duplicate folder drop warning** — _Superseded 14 May 2026 by `.claude/plans/tf-multi-project.md` #11: dropping a folder that's already a project selects the existing project with a 0.4s row flash, no warning dialog. Photos/Music precedent — silent recognition beats interruption._ Original plan was a dismissable "Duplicate of \<project\>" warning.
- ~~[S3]~~ **Slow-double-click rename in sidebar** — _Demoted to Should 4 May 2026 — right-click + Project menu cover it for alpha._ Finder-style slow double-click to inline rename. `simultaneousGesture(TapGesture())` and `onTapGesture` both break List selection on macOS 26. Needs NSEvent monitor approach or AppKit subclass. Rename still works via right-click and Project menu
- [S3] **Multi-select projects (Shift/Cmd click)** — change `List(selection:)` from `UUID?` to `Set<UUID>`. Detail pane shows "3 projects selected". Enables bulk delete via right-click, and drag-to-folder in Phase 3. Prerequisite for drag-to-reorder
- ~~[S3]~~ **Drag-to-reorder projects in sidebar** — _Demoted to Could 4 May 2026 — three projects in alpha don't need reorder; revisit when cohort hits 5+ each._ persisted via `position` integer in project index. Needs multi-select first. Phase 3 in design doc
- [S3] **Drop-on-existing-project row** — add interviews to existing project via drag. Data model ready (`addFiles`). Needs `DropDelegate` hit-testing on List (per-row `.onDrop` breaks selection on macOS 26). Tracked as #11 in `.claude/plans/tf-multi-project.md`
- [S3] **UTType validation on drop** — filter dropped files to accepted media types (audio, video, subtitle, docx, txt). Currently accepts any file
- [S3] **Empty state drag target** — `ContentUnavailableView` as `.onDrop` target when project list is empty
- **~~Run pipeline from GUI~~** — "Analyse" button, background task, progress streaming. Milestone 7. Needs design doc
- **~~Settings UI~~** — provider selection, API key entry, redaction toggle, model choice. Milestone 6. Needs design doc. Currently CLI-only config is a hard block for App Store users
- ~~[S4]~~ **App Store subscription infrastructure** — _Demoted to v1.0 4 May 2026 — alpha is BYOK-only; learn whether the product is worth paying for before designing the price._ StoreKit 2, receipt validation, entitlement check. Not yet designed
- **~~Auto-serve after run~~** — pipeline finishes → auto-launch serve + open browser. (TODO.md immediate)
- **Subprocess lifecycle / orphan management** — make orphan handling invisible to the user. PID-file-based scan-and-reconcile at app init for both `bristlenose run` and `bristlenose serve`; sandbox-clean (`proc_pidinfo` / `proc_pidpath` instead of `lsof`/`pgrep`). Replaces today's serve-only `lsof`-based cleanup. Required before sandbox flips on for TestFlight. Surfaced during port-v01-ingestion QA. Design: `docs/design-subprocess-lifecycle.md`. Estimated ~2 days. _(24 Apr 2026: Stop-is-a-lie + stale-pill alpha blockers shipped — 4 commits 896c074..da5cc45. Owned- and orphan-path cancel both ack instantly via `isStopping`; orphan-path SIGINT→SIGTERM→SIGKILL escalation; orphan-attach popover tails `bristlenose.log`. Sandbox-clean probes + `stopAll()` still TODO.)_
- ~~[S2] **Alpha telemetry — Phase 1 plumbing**~~ — `/api/health` advertises `telemetry: {enabled, url}`; dev-only `POST/GET/DELETE /api/dev/telemetry` stub with Pydantic validation, 500-event batch cap, PID-scoped JSONL; `website/telemetry.php` + moved `website/feedback.php` with `hash_equals`, placeholder-token guardrail, CSV cell-safety helper. Reviewed (3 agents, 8 mechanical findings fixed, 8 design-questions parked). Done 26 Apr 2026 (alpha-telemetry branch, 6 commits). PHP files NOT yet deployed to bristlenose.app — run the `deploy-website` shell alias only when Phase 2 starts so the URL the health endpoint advertises actually resolves
- **Alpha telemetry — Phases 2–4 (deferred to post-TestFlight)** — TestFlight tester feedback path is video-call + UX observation, not instrumented data; alpha telemetry can wait without losing the testers (they don't notice it's missing). Deferred 26 Apr 2026 to keep the TestFlight runway clear of feature-creep. Pick up after first TestFlight cohort reports back. Open work: (2) Python — `TelemetryEvent` SQLite table + Alembic migration, `POST /api/telemetry/events`, background batched shipper, `bristlenose/llm/prompt_version.py` + `prompts/versions.jsonl` sidecar. (3) React — emission hook on suggest/accept/reject/edit, 2 s debounce collapse rule, `edited` as flag not offset. (4) Swift — Sheet 2 telemetry opt-in (verbatim from spec §First-launch sheets), Keychain UUID helper, sidecar env-var injection (`BRISTLENOSE_RESEARCHER_ID`), Settings → Privacy screen. Four architectural questions + eight parked `/usual-suspects` findings — full context in `docs/private/alpha-telemetry-next-session-prompt.md`. Methodology spec stays on main as the plan; absence of in-alpha data means the first Substack piece pushes to second cohort, not first
- **Trial-expired handoff UX** — [Beta-must, stage-5-prereq] most consequential Beta surface. When a Beta tester's funded preview budget (~$4 of relay credits) is exhausted, the path back to BYOK must be obvious and non-punitive. Surfaces: in-app banner ("preview budget exhausted, BYOK to continue"), Settings → LLM provider key entry pre-routed, copy that doesn't read as paywall. Pairs with two-mode data architecture and the funded-relay endpoint. Friendly-CTO Sunday relevant. **Ship criteria:** running out of preview credits never produces a silent failure or confusing error; BYOK switch is one click + paste; the user understands what just happened and what to do next
- **In-app feedback channel — low-friction "tell me anything" path** — [Beta-must, stage-5-prereq] Beta gate is "warning-label-tolerable rough edges allowed *if* the warning is visible"; the inverse is testers must have a frictionless channel to *tell us* when something surprises them. Existing feedback endpoint (`feedback.php`) is the plumbing; what's missing is the in-app surface that makes "tell me anything" the easiest path. Reference: existing `Toast.tsx` + `FeedbackModal.tsx` (frontend); desktop equivalent. **Ship criteria:** every screen has a one-keypress / one-click way to send freeform feedback; submission persists (not lost on app close); confirmation toast; works without a server roundtrip if relay is down

### Should
- **i18n marketing demo dataset (es + ja)** — sample VTT transcripts seeded 5 May 2026: `trial-runs/demo-escuela-gastronomica/` (es-MX, Mexican culinary school — María + Carlos) and `trial-runs/demo-sapporo-guide/` (ja-JP, Sapporo local-business guide app — Yuki + Tanaka). Two participants per project so quotes/themes/tags show cross-participant signal in App Store and bristlenose.app screenshots. Companion to IKEA codebook validation dataset (which covers English). Native review by es and ja UX-designer friends owed before screenshots ship — same loop as locale strings; raw machine-feel will read to a native UXR researcher's ear. Files explicitly marked demo content (`NOTE` blocks in VTT) so nobody mistakes for real research. Re-uses the multilingual UI Bristlenose already ships; no code changes required
- **Desktop toast infrastructure** — SwiftUI toast overlay (auto-dismiss, fade). Needed for "Added N interviews to project", archive undo, and future feedback. Reference: `frontend/src/components/Toast.tsx`
- **Add interview flow (serve mode)** — dashboard/sessions list "Add interviews" button → file picker → re-process. CLI route: `bristlenose add <files> <project-folder>`. Both need toast confirmation
- **Session enable/disable toggle** — exclude sessions without re-running pipeline. Option A (`is_disabled` bool). (design-session-management.md)
- **~~Incremental re-run~~** — add new recordings, preserve researcher work. Milestone 8. Quote stable key already in place
- ~~**Left-hand nav content for all tabs** — signal cards, speaker badges, codebook titles, sessions list, analysis views in left sidebar~~
- **~~Standard modal with nav for Settings and About~~** — consistent modal pattern, consider unifying help + about
- **New title bar design** — current title bar needs refresh
- **Post-analysis review panel** — non-modal, dismissable panel after pipeline completes: name correction, token summary, coverage overview
- **Project name input cap** — [Beta-must] folded from 7 May walk (T13). Project name (and folder, tag, codebook group) accepts 299+ characters with no input cap. Display truncation IS working (sidebar shows `jandslkfbnalkjsdbflk…`), but no validation at input — long names persist underneath. Risks: export filenames via `slugify()` already cap at 50, so collisions possible when long names share a prefix; whole-name shows up in modals/breadcrumbs/headers without consistent truncation. Sensible caps: project 80, folder 60, tag 40, codebook group 60. Apply across all user-named fields
- **AutoCode silent-zero on non-English** — [Beta-must] folded from 7 May walk (T5). On Spanish VTT, running AutoCode appears to execute (progress UI fires) but no tags land on any quote. Reruns ("still there") show tags still absent. Likely cause: AutoCode prompt is English-only, so the LLM either returns nothing applicable or returns proposals that don't match Spanish quote text. Same fake-success-feedback family. **Ship criteria:** non-English content either produces tags OR shows an honest "0 proposals returned for this codebook on this content (try a different codebook, or report)" state — not a clean-looking success
- **Whisper 1.5GB download — bridge with sample/tour** — [Beta-must] folded from 7 May walk (TD13). First-run UX has a long opaque wait while Whisper model downloads. Bridge with a guided tour or sample report so the wait isn't dead time. Pairs with the demo dataset Should items above

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
- **Markdown report as the CLI deliverable** — post-100-days. Reframe `--static` from "vestigial deprecated thing" to "the markdown deliverable for terminal users" (engineers, devrel, OSS-research folk who want emailable / greppable / diffable / pipeable text). Plays to static-render strengths instead of competing with the React SPA. Needs a real design pass on what a *good* markdown research report looks like — capture, park, revisit. Revisit trigger: 2+ cohort members say "I just wanted a text file I could grep / share / paste". Full capture: `docs/design-cli-improvements.md` §Future direction.
- **iPad companion (read-mostly thin client)** — post-alpha. Mac runs the pipeline as today; iPad syncs quotes/stars/tags/hidden state from a per-subscriber cloud workspace. "Workbench → reading chair" — sofa skim of the 15% of quotes that matter, star-favourite pass on iPad, edits flow back. Text+audio-proxy sync is small; video originals stay on the Mac (or optional 480p HLS proxy). Subscription funds the relay rather than GPU time. Pairs with the broader cloud-tier framing: differentiator is "you pick the LLM, you can leave anytime with a self-contained HTML", not "bytes never leave the device". Discussion 30 Apr 2026.

---

## 1a. MVP 1-hour human session flow (S2 focus)

The canonical end-to-end beats a first-time user must complete successfully in the Mac app before we ship to anyone. Each beat that doesn't work in the current build becomes an S2 item.

1. **First-time open** — app launches, window shows a welcoming empty state (shipped 1 May 2026: `WelcomeView.swift` + `BootView.swift`, commit `816ab65` on `first-run`)
2. **AI disclosure sheet** — shown, acknowledged, dismissed (shipped: `AIConsentView.swift`)
3. **Set up Claude API key** — Settings → paste key → saved to Keychain → validated (shipped: Beat 3)
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
- **Brand-new projects render unstyled in the desktop app** — fixed 1 May 2026 (commit `9e6224b`, `bristlenose/server/app.py` `_mount_prod_report`). A project that has never run the pipeline has no `<output_dir>/assets/bristlenose-theme.css`, so the SPA's `<link rel="stylesheet" href="/report/assets/bristlenose-theme.css">` 404'd and the entire UI rendered as raw HTML inside the WKWebView. Fix mirrors the dev-mode pattern: register a typed CSS route that prefers per-project rendered CSS if it exists and falls back to `_load_default_css()` otherwise. Smoke-tested on an empty project — endpoint now returns 200 + 262 KB of theme CSS instead of 404. Without this, Beat 7 ("Display — report opens, quotes render") was visibly broken on first contact for every brand-new project.
- **~~Dark mode selection highlight~~** — invisible in dark mode (#52)
- [S5] **Dark logo** — placeholder inverted image, needs proper albino bristlenose pleco (#18, logo.css HACK)
- **~~Circular dependency in production build~~** — fixed in 0.13.6 but regression-prone (SidebarStore import cycle)
- ~~[S3]~~ **Import FK constraint** — _Demoted to Should 4 May 2026, S6 with Playwright layers 4–5._ fixed in 0.13.4 (ProposedTag cleanup) but needs E2E coverage to prevent regression
- ~~[S3]~~ **Native toolbar tab i18n not reactive** — _Demoted to Could 4 May 2026 — alpha is English-only with English-speaking testers._ changing language in Settings doesn't update toolbar labels until app restart. `I18n` `@StateObject` doesn't trigger segmented control re-render
- ~~[S3] **Pipeline silently skips stages 2–11 on raw video**~~ ✅ **Done — verified 12 May 2026** — not a dispatcher-level skip; stages 2–11 were running but producing empty output because `mlx_whisper.audio.load_audio` shells out to bare `"ffmpeg"`, and the sandboxed sidecar's restricted PATH didn't include Homebrew's. Eliminated in current main by two layered fixes: (a) v0.15.4's `prepend_bundled_to_path()` in `bristlenose/__init__.py` prepends the bundled ffmpeg path at import time, so the bare-name shellout resolves under sandbox; (b) v0.15.5's preflight block catches missing ffmpeg loudly before stage 2 runs — no `.bristlenose/` written, no fake-success events, no fake "Analysed" pill. Both original repros (`trial-runs/bar` 2026-05-07, `trial-runs/foo` 2026-05-10) were on a 0.15.3 sidecar pre-dating both fixes; their `bristlenose.log` files contain the smoking-gun `Transcription failed: [Errno 2] No such file or directory: 'ffmpeg'` line. Verified 12 May 2026 by CLI re-run on `foo` with `env PATH=/usr/bin:/bin .venv/bin/bristlenose run`: preflight aborted cleanly with "FFmpeg not found / brew install ffmpeg" and no fake-success state persisted (broken-state snapshots at `/tmp/foo-snapshots-2026-05-12/`). Two small follow-ups: (i) preflight returns exit code 0 instead of 2 (man page documents 2); (ii) `run --clean` scope is `.bristlenose/` only — stale empty `sessions/` / `transcripts-raw/` dirs from prior fake-success runs are not removed. End-to-end verification with a fresh sandboxed-sidecar build still pending
- ~~[S3] **React SPA misses pipeline-completion signal**~~ ✅ **Done 10 May 2026** — both halves shipped in v0.15.4: correctness slice (`spa-pipeline-completion-refetch`) added `/api/projects/{id}/last-run` + `LastRunStore` polling + race-safe import-then-publish for auto-refetch within ~3 s; trust-UX layer (`pipeline-completion-trust-ux`) added NavBar refresh button (hidden when no run, serve-mode only — desktop's OS chrome owns refresh), accessible refetch overlay (`inert` + opacity 0.7), inline post-zero-quotes message, cross-island contract test. Pre-pipeline / no-sessions / failed-run surfaces moved out of SPA scope into the `generic-failure-surface` follow-up. Desktop manual-refresh affordance deferred to a follow-up branch (auto-poll alone carries the signal post-cohort feedback)
- ~~[S3] **Filesystem export silent fail under sandbox**~~ ✅ **HTML report path done 10 May 2026** — `sandbox-export-savepanel` merged in v0.15.4: Export downloads now route via `WKDownload` + `NSSavePanel`, six locale `desktop.json` files updated for save-dialog strings. Other export surfaces (video clips, CSV file, slides, anonymised bundle) still need the same routing — track in follow-up if/when they hit. Privacy-default consistency check ("Remove participant names" inconsistency between projects) still open
- [S3] **Clipboard CSV silent fail** — [stage-2-prereq] 🔴 folded from 7 May walk. Different bug, same family as filesystem export. Click Copy as CSV → toast fires (with raw i18n key, see separate item) → clipboard is empty. Different root cause: clipboard access in sandboxed app via WKWebView needs `WKWebViewConfiguration` allowing `JavaScriptCanAccessClipboard` (or `navigator.clipboard.writeText` permission), and the app entitlement for clipboard. Fire-and-forget success toast happens regardless of whether write landed. **Ship criteria:** clipboard write actually lands; success toast waits on confirmation, not button click; failure path shows honest error. Investigate `navigator.clipboard.writeText()` vs fallback `document.execCommand("copy")`, WKWebView config, entitlement
- [S3] **Route-level ErrorBoundary + Analysis crash** — [stage-2-prereq] 🔴 folded from 7 May walk. Analysis tab crashes with React error #300 on Spanish VTT project; stack trace in `components-BzJXEGiq.js`. Companion finding (higher priority): no `ErrorBoundary` / `errorElement` on React Router routes, so users see the developer-facing default ("Hey developer 👋…") with a minified stack trace. **Ship criteria:** route-level ErrorBoundary on every React Router route, rendering "Something went wrong on this tab. [Reload] [Report]" — covers the Analysis crash AND every future crash with one fix. Investigate the specific data-shape / conditional hook / undefined value that triggers #300 (likely sparse / non-English data) and fix in parallel. Per [React Router docs on errorElement](https://reactrouter.com/en/main/route/error-element)
- [S3] **Fake-success-feedback audit (one read of the codebase)** — [stage-2-prereq] 🔴 folded from 7 May quality reset. The recurring class-not-instance: filesystem export, clipboard CSV, AutoCode silent-zero, post-pipeline empty state all signal "done / complete / success / exported / applied" while the artifact doesn't exist. **Ship criteria:** one targeted grep + audit pass over every UI surface that signals success — verify the artifact exists, the data is correct, the failure path is honest. Likely surfaces 3–5 cousins not yet hit. Treat as one investigation, not seven separate fixes. Quality-reset framing: the user's mental model of "did this work?" must be trustable everywhere
- [S3] **Keychain ACL prompt at launch + Settings open** — [stage-2-prereq] 🟡 folded from 7 May walk. App eagerly fetches `Bristlenose Anthropic API Key` before showing any UI; macOS surfaces "Bristlenose wants to use your confidential information…" with zero context. Same pattern fires opening Settings — LLM Settings rows eagerly read all provider keys. Fix shape: (a) defer launch read entirely (only fetch when an LLM call needs the key, with in-app pre-prompt context); (b) Settings opens with zero Keychain calls (Appearance / Language fully usable); (c) LLM Settings only fetches when user clicks into that pane, framed inside the UI; (d) on Deny, panes still render in usable "key not loaded — click to authenticate" state. Status surface: non-blocking microbanner ("API keys stored in Keychain — click to authenticate") rather than blocking modal
- [S3] **i18n locales not reaching host bundle under sandbox** — [stage-2-prereq] 🟡 folded from 7 May walk and A1c sandbox findings. Welcome view + AIConsent leak raw keys when host i18n locales aren't bundled at `Resources/locales/`. Pre-existing build-system bug surfaced under sandbox. **Ship criteria:** locale JSON files reach the bundled `.app` Resources dir for every release build; gate in `build-all.sh`
- [S3] **i18n key leak `toolbar.quotesExported`** — [stage-2-prereq] 🟡 folded from 7 May walk. After Copy as CSV, success toast shows raw key instead of translated string. Either missing entry in `bristlenose/locales/en.json`, call before i18n init, or hard-coded key bypassing `t()`. **Ship criteria:** all 6 locales have the entry; toolbar toast helper enforces `t()` use
- [S3] **OllamaSetupSheet silent happy-path** — [stage-2-prereq] 🟡 folded from 7 May walk (TD6). When daemon + model already present, setup sheet flips through with no signal. **Ship criteria:** explicit "ready" state with confirmation before dismiss
- [S3] **Ollama setup quality + perf expectations copy** — [stage-2-prereq] 🟡 folded from 7 May walk (TD4). Honest-affordance copy: "slower & less precise than cloud" so cohort testers don't conclude the product itself is broken when the local backend underperforms
- [S3] **Titlebar redesign — drop project lozenge + centred app name; promote project + Photos-style subtitle** — [stage-2-prereq] 🟡 folded from 7 May walk. macOS app name lives in the menu bar, not the titlebar; project lozenge reads as an interactive control. Fix: drop centred app name AND lozenge styling; promote project name to centred bold with muted subtitle ("3 sessions · April 2026"). References: Xcode, Notes, Mail, Photos. Sessions = human-meaningful unit; date = at-a-glance recency. Pairs with the existing "**New title bar design**" entry in §1 Should — this folds the specific design call
- [S3] **Nav arrows leftmost edge** — [stage-2-prereq] 🟡 folded from 7 May walk. Back/forward arrows should sit immediately to the right of the sidebar toggle (Safari / Finder / Mail convention). Currently floating in middle of titlebar between project lozenge and centred title. Layout: `[sidebar panel | sidebar-toggle][< back][> forward] … rest of toolbar`
- [S3] **Toolbar overflow priority — back/forward last to collapse** — [stage-2-prereq] 🟡 folded from 7 May walk. At narrow widths the overflow ≫ menu absorbs back/forward alongside Export/Tags/Search. Back/forward are core navigation; should be among the *last* to collapse, not first
- [S3] **Sidebar drag-drop into folder** — [stage-2-prereq] 🟡 folded from 7 May walk. Right-click → "Move to…" works; data path is there. Wire the drag-and-drop affordance to the same handler. Small
- [S3] **Sidebar row-height jump on new project** — [stage-2-prereq] 🟡 folded from 7 May walk. Existing analysed projects show subtitle ("Analysed 8 hr ago"); newly-created render with no subtitle (shorter row), then become taller once a value lands. Reserve subtitle row height from the start (placeholder line / dash / "Empty / Not analysed yet") so row height is stable
- [S3] **"Analysed in 0 sec" preposition + sub-minute formatting** — [stage-2-prereq] 🟡 folded from 7 May walk (T28). Two bugs in one string: preposition ("in" reads future-tense — should be "Analysed 0 sec ago" / "just now") and sub-minute rounding ("0 sec" should round to "just now"). Same relative-time formatter as `Analysed 8 hr ago`; needs `< 1 min` branch + correct preposition
- [S3] **AutoCode button disabled on Sentiment group** — [stage-2-prereq] 🟡 folded from 7 May walk (T15). Sentiment is auto-applied during analysis pipeline by default — every quote already has its sentiment tag by the time the user reaches the Codebook page. The "+ AutoCode quotes" button on Sentiment can never produce work; clicking gives "0 of 0 proposals remaining / No proposals to review". Disable (not hide) the button on any group whose tags are pipeline-auto-applied; tooltip explaining why ("Sentiment is auto-coded during analysis"). Surface via flag on codebook group definition (e.g. `auto_applied_in_pipeline: true`)
- [S3] **Codebook first-arrival imbalance** — [stage-2-prereq] 🟡 folded from 7 May walk (T23). When only Sentiment is populated, Uncategorised + New-group placeholders dominate the top row at full width; "Emotional & Cognitive Signals" supergroup heading sits alone with a single child at ~1/3 width. "Drag tags between groups… drop to merge" instruction assumes ≥2 populated groups. Either collapse the supergroup band when it has only one child, OR ship default sibling groups (Cognitive Load, Mental Models, etc.) so layout is balanced from the start
- [S3] **Dashboard sessions table — full row clickable** — [stage-2-prereq] 🟡 folded from 7 May walk (T17). Hover highlights whole row in pale blue, implying it's clickable, but only the `#3` session-ID column actually opens the session. Affordance lies. Make whole row clickable (matches hover, aligns with Mail / Finder list patterns); keep `#3` as the existing target. Don't shrink hover; expand hit area
- [S3] **VTT speaker names in body parens** — [stage-2-prereq] 🟡 folded from 7 May walk (T18). VTT-sourced transcripts show speaker names inline in parentheses in quote body (`(Carlos) Me cambié a esta…`), even though participant badge already carries the same identity (`p2`). Lift names out of body text into the badge (e.g. `p2 Carlos`), matching non-VTT rendering. Fix lives in VTT parser stage — strip leading `(Name) ` from segment text and attach to speaker label metadata
- [S3] **Project dashboard width inconsistent** — [stage-2-prereq] 🟡 folded from 7 May walk (T25). Project dashboard is the only tab that doesn't use full window width — Sessions / Quotes / Codebook / Analysis all do. Cap or align Project page to match
- [S3] **Pipeline diagnostic popover (Swift) — Branch 2 of design-pipeline-diagnostic-popover.md** — current popover is ropey; spec is locked and Python half is shipped, so this is unblocked self-contained Swift work. Implement the two new pill states (`.completedPartial`, `.failedWithDiagnostic`) and the popover view consuming `PipelineSummary` from fixture v4. Surface area: `PipelineActivityItem.swift` (popover body + `formatDiagnosticPlaintext`), pill-label derivation per `dominantCategory()` precedence (AUTH > MISSING_BINARY > QUOTA > NETWORK > UNKNOWN), DisclosureGroup hierarchy (≤2 inline, ≥3 collapsible), overflow placeholder detection (`session_id == nil && message.hasPrefix("... and ")`), Copy/Email plaintext (Xcode "Copy Issue" pattern, no JSON). Locale strings: `desktop.pipeline.diagnostic.pill.<category>` + popover chrome across all 6 locales (machine-fill + native-friend review per usual playbook); plural rules for "and N more" (`_one`/`_other` en/es/fr/de, `_other`-only ko/ja). QA harness: debug-only fixture-injection so partial / failed states are reproducible without breaking a real run. Anti-patterns checklist in spec — do not mint new glyphs, do not link to half-broken results, do not add disabled placeholders. _Estimated 1–2 days Swift + 1 hour locale review. Marked alpha-blocking on the "tell us what failed" axis the spec leads with (primary user is the alpha tester whose run produced a partial result)._ References: `docs/design-pipeline-diagnostic-popover.md`, `bristlenose/ui_kinds.py`, `desktop/Bristlenose/Bristlenose/MessageKind.swift`, `tests/fixtures/pipeline-summary-contract.json`
- [S3] **brew first-run + IKEA-call cluster** — [stage-2-prereq] 🔴 surfaced 9 May 2026 from friendly-CTO's brew install + IKEA dogfood call. 35 numbered findings decomposed into 8 chunks (revised 10 May after coherence review + deeper-dig surfaced a systemic stage-contract pattern): A1 brew formula `[serve]` + man page (tap commit, S0); A2 doctor `check_serve_deps()` + anaconda warn + README (S2); A3 CLI honest output — pipeline-errored summary, no static-render surface, plurals, hide `--static`/`render` (S2); A4 stage-cache honesty (S0) — failed/empty stages don't cache; rerun-dedup #17; HF warning; six concrete fixes including the call-order bug at `pipeline.py:1308` where `mark_stage_complete` runs BEFORE the abandon-check; B1 long-audio quality (S0/S1) — Whisper hallucination #14, gaps #15, diarization-collapse #16; C1 CLI codebook plumbing (S2, reframed 11 May from "auto-run default codebook" — CLI gets `--codebook=<slug>` flag + `bristlenose codebooks` subcommand; no auto-run, no first-run greeting); C2 14 UX papercuts #18-#34 (S3, split-if-bloats); D1 stage-contract audit (S1, systemic — audit of 12 pipeline stages showed only 3 use structured failure-surfacing infrastructure; A4 + B1#16 are instances of the same silent-empty bug class; D1 generalises the cure via a `StageGuard` contract preventing future regressions); E1 codebook-picker-desktop (S3, capture-only stub — pre-flight "what's this about?" picker + signal-card interpretations in the desktop app; absorbs the headline first-impression product moment that C1 used to carry; gated on UXR-friend conversations about defaults + variants, which the cohort calls themselves are the input pipeline for — not something to design before them). Plan + handoffs at `docs/private/plans/2026-05-meta-plan.md`, coherence doc at `docs/private/plans/2026-05-cluster-coherence.md`, per-branch handoffs at `docs/private/handoffs/[A1-D1]-*.md`, review log at `docs/private/reviews/2026-05-cluster-coherence.md`. Status: ~~A1 shipped 11 May 2026~~ on tap at `697424e` (`[serve]` extras) + `26e3a39` (A1.1 man-page install moved to `def install` so brew auto-links; man page lands in Cellar via pip's wheel-data scheme but brew's link phase runs *between* `install` and `post_install`, so post_install installs miss auto-linking — surfaced during clean-shell verify); ~~A2 shipped 12 May 2026~~ on `a2-install-doctor-checks` (`check_serve_deps()` hard error in `run_all()`, brew/pipx/pip-aware fix message with zsh-glob-safe quoted brackets, README Python 3.10+ + anaconda caveat; Fix 3 anaconda runtime check dropped as unreachable under `requires-python = ">=3.10"`; latent Rich-markup-eating bug fixed at three print sites silently dropping `[serve]`); ~~A3 shipped 14 May 2026~~ direct on `main` as commits `dc71073` + `607202d` + `04dcdd6` — preflight gates `serve_deps` for run/serve/analyze; `PipelineAbandonedError` → researcher banner mapping `Cause.category` to copy (QUOTA, API_REQUEST split from QUOTA, AUTH with provider+suffix, NETWORK, API_SERVER, DISK, MISSING_*); `--static` deleted; `render` replaced with hidden Typer catch-all stub; `--no-serve` restored as hidden flag after doc-sweep caught the desktop sidecar regression; `_QUOTA_RE` split into QUOTA + API_REQUEST; `_AUTH_RE` extended to cover real Anthropic/OpenAI SDK 401 strings + tightened to drop bare-word false positives; 30-finding review log at `docs/private/reviews/cli-improvements.md`; ~~A4 shipped 12 May 2026~~ as merge `9d2cd2e`; B1 skeleton pending pre-flight; C1 rewritten 11 May to CLI plumbing scope; C2 skeleton pending pre-flight; D1 full handoff written, depends on A4+B1 shipping first; E1 stub — post-cohort. Coherence doc Pass 2 (11 May) landed 12 NEW findings; clean technical contracts locked; Contracts 5 + 6 superseded by C1 reframe. Per the friendly-CTO's onboarding-first lens — gate-level (A-stream + B1) before polish (C-stream); D1 trails as systemic; E1 sits outside this cluster's ship window. Execution order is A1 tonight, then A4+B1+A2 in parallel, then A3+C1+C2 sequenced after A4, then D1 after A4+B1. **As of 14 May 2026:** A1 ✅, A2 ✅, A3 ✅, A4 ✅, B1 ✅. Remaining: C1, C2, D1. Cross-references: overlaps with §2 fake-success-feedback audit and §2 Pipeline diagnostic popover (Swift) entries — different bugs, same family


### Should
- **Create canonical design doc for first-run flow** — Beat 3/3a/3b shipped `AIConsentView.swift` (~240 lines), `OllamaSetupSheet.swift` (~330 lines), and the welcome detail-pane (now `WelcomeView.swift` and `BootView.swift`, commit `816ab65` on `first-run`, superseding the `4772c3a` placeholder) but none of the existing design docs (`design-desktop-app.md`, `design-multi-project.md`, `design-project-sidebar.md`, `design-desktop-settings.md`, `design-keychain.md`) is the canonical home for the first-run flow as a single thing. New `docs/design-first-run-flow.md` should cover: consent gate (`ContentView.swift:267-272, 343-346`), consent re-access (Bristlenose menu > AI & Privacy…), `AIConsentView.currentVersion` policy, consent-log audit (`UserDefaults` `consentLog`), `OllamaSetupSheet` state machine (idle/installingOllama/waitingForDaemon/downloadingModel/finishing/failed), HTTP-only daemon probe, ordering invariant (consent BEFORE prefs notification), `BootView` unified boot/loading/failed surface, `WelcomeView` two-variant pattern (`.firstRun` + `.noSelection`), tagline canonical form ("Sensemaking for User Research" — no article, no period), `I18n.findLocalesDirectory()` worktree-aware `#filePath` derivation. Surfaced by 30 Apr 2026 truing pass; scope expanded 1 May 2026.
- **Translation catch-up pass — first-run desktop screens** — _LLMSettingsView + OllamaSetupSheet hardcoded-string extraction + 6-locale machine-fill done 5 May 2026 via `i18n-llm-settings` (merge `c023f7d`); native review for es/fr/de/ko/ja and the boot/welcome blocks still owed; ja broader gap remains._ `LLMSettingsView.swift` and `OllamaSetupSheet.swift` ship with ~30 hardcoded English strings on the first-run path (Beat 3 + 3b, 30 Apr 2026, `first-run` branch). Plan: machine-translate as good-enough first pass before alpha (subsumes Finding 39 from settings-ui review log) + glossary discussion for any new vocabulary (status labels, install copy, error catalogue). Scope now also covers the new `boot.*` and `welcome.*` blocks added to all 6 `desktop.json` files on 1 May 2026 (commit `816ab65`) — each ~7 + ~13 keys, English drafts present in all 6 locales, native review still owed for es/fr/de/ko/ja. The `chrome.noProjectSelected` / `chrome.selectProject` keys are no longer dead code — `WelcomeView.noSelection` resurrects them — so the previous "clean up unused keys" sub-clause is obsolete. Ja-locale gap is the longest pole: `ja/desktop.json` has ~53% empty values pre-existing, including `aiConsent.useOllama` + `aiConsent.ollamaCallout` which collapse the alt-AI path to invisible for Japanese users. If not done in time for alpha: pull ja from the locale picker.
- **AIConsent sheet rewrite for clarity + simplicity** — alpha→beta polish window. Current sheet has 6 sections + 2 buttons; "Researcher responsibility" copy at the bottom probably never read. Plan: fold into a Learn more disclosure, shrink to disclosure + decision. (Finding 50 from settings-ui review log, 30 Apr 2026.)
- **Continue road-to-testflight walks (sections 5–8)** — [S3] folded from `road-to-testflight.md` 8 May 2026 before that doc was deleted. The 7 May walk covered sections 0–4; sections 5–8 are unstarted walk plans, each their own ~30 min walk. (5) **Non-Claude provider failure as signal** — pick ChatGPT, run a stage that fails, verify message reads as expected not alarming; user can recover (switch back to Claude) without restarting; no stack traces leaking; README still documents Claude only. (6) **i18n drift, focus Japanese** — switch UI to `ja`, walk the whole app: any English fallthrough? date formatting natural? Japanese pixel-overflow? Settings labels / modal text / error messages / popover all translated? sentiment tags read naturally not transliterated? Then spot-check one screen each in es/fr/de/ko. (7) **Export HTML** — open project in serve mode, click Export HTML in toolbar, open exported file off `file://`, verify hash router resolves quote/session deep links, anonymisation toggle redacts cleanly with no PII in source, filename uses `safe_filename()` (preserves spaces/case for Finder), no `</script>` breakout in embedded JSON (view-source check). (8) **Provider switching second pass after a real session** — run analysis on Claude, switch to ChatGPT and re-render; back to Claude; to Ollama with no model installed. Note any state drift between LLM Settings, Keychain, sidecar, and consent log at each switch. Each section produces its own snagging list folded into §2 the same way 7 May's did. **Ship criteria:** each section walked at least once with no new 🔴 surprises; outputs filed back into §2 Broken or struck if already addressed
- **i18n: Settings second-pane sweep + menu-bar audit** — [Beta-must] folded from TODO.md 8 May 2026 (TD1/TD2/TD3 from road-to-testflight triage). Three concrete sweeps not covered by the Translation catch-up pass entry above: (1) **LLMSettingsView detail pane** — `desktop/Bristlenose/Bristlenose/LLMProvider.swift` ships hardcoded English in `activationToggleLabel:106`, `ProviderStatus.label:222`, `statusLabel(for:):96` Ollama branch, `description:86` Ollama line, `ProviderLinks.consoleLabel:137,145,153,167`. Plus `temperatureLabel` in ja/ko `desktop.json` is literal `"Temperature"` (loanword bug). Fix shape: introduce `desktop.llmSettings.activate.{generic,ollama}`, `desktop.llmSettings.status.{online,notSetUp,invalid,unavailable,checking,local}`, `desktop.providers.ollama.description` keys; thread `i18n` into LLMProvider helpers (currently pure value type). (2) **Transcription pane** — `desktop/Bristlenose/Bristlenose/TranscriptionSettingsView.swift` is fully hardcoded: `"Backend"`/`"Model"` Picker labels:12,23, `"Auto"` option:13, `"Auto detects the best engine for your Mac."` hint:17, `(recommended)` parenthetical:24. Add `desktop.transcriptionSettings.{backendLabel,modelLabel,backendAuto,backendHint,modelRecommendedSuffix}` keys. Bundle with the LLMSettings sweep. (3) **Menu-bar audit** — discriminate OS-defaults (Edit menu Cut/Copy/Paste, File Close/Page Setup/Print — those localise from system language and are not our bugs) from our literals (e.g. `BuildInfoSheet.swift:44` `Button("Close")`). Sweep `desktop/Bristlenose/Bristlenose/*.swift` for `Text("...")` / `Button("...")` / `Picker("...")` / `Section("...")` / `Label("...")` with English literals. `CommandMenu` titles are exempt by design (can't use runtime strings). All three sweeps targeting Beta cohort whose UI language is non-English; alpha cohort is English-only so this stays alpha→beta polish.
- **Tagline strategy: "Sensemaking" word, glossary entry, namespace** — parked from 1 May 2026 usual-suspects pass on `first-run` (i18n-review findings #1+#2+#4). Three coupled questions to settle with native speakers, not by speculation: (a) does "Sensemaking" survive translation as a brand differentiator, or do non-English markets need a loanword (es: "Sensemaking", de: "Sensemaking" or "Sinnstiftung", ja/ko: katakana/한글 transliteration following the `design-i18n.md` Don Norman precedent, fr: "Sensemaking" or "donner du sens à"); (b) `boot.tagline` is currently scoped to `desktop.json` but the same string will appear on bristlenose.app, README, App Store metadata — promote to `common.brand.tagline` before Weblate locks current renderings; (c) "Sensemaking" is not in `docs/glossary.md` core-concepts table — every translator (human or machine) routes to "analysis"/"análisis"/"Analyse" by default, exactly the commodity word the tagline earns the right not to be (memory: `feedback_always_be_deleting_words`). **Alpha is English-only**, so the locale renderings don't block alpha. Defer until native speakers are reviewing translations together (e.g. the broader "Translation catch-up pass" item above). Surface again at: alpha-cohort feedback checkpoint, OR website launch, OR App Store submission — whichever lands first.
- **Other parked items from 1 May usual-suspects pass** (5 agents on commits 816ab65 + 9e6224b) — 31 LOW/MEDIUM findings beyond the 5 HIGHs that were fixed inline. Top product-shape questions to come back to: (i) the WelcomeView 3-step rail is card-grade visual prominence with brochure-grade content — demote to one-line footnote OR rewrite as Otter/MacWhisper-differentiator copy that says what Bristlenose is for; (ii) New Project / Drop card affordance asymmetry (both look like buttons, only one is) — either merge gestures into one card or split into distinct *intents* not gestures; (iii) the dashed-rectangle drop target reads as web vocabulary (Dropzone.js) — Mac idiom is whole-window drop with subtle vibrancy highlight; needs zoom-out to MacWhisper / Pixelmator Pro / Tower; (iv) failure-mode `lineLimit(3)` truncates 5+ line sidecar stacks — relax or move full message into the Show Details ScrollView; (v) drop card has no a11y label / keyboard equivalent (HIG requires keyboard alternative for drag-drop). Plus a long tail of niggles (SF Symbol choices, 0.5pt hairline strokes, `.linear` vs `.circular` ProgressView, `.borderedProminent` too loud for empty state, German "und" vs "&", Korean register, "Mac" vs "laptop" inconsistency across locales). **Don't open these on the alpha critical path.** Most are alpha→beta polish.
- **Silero VAD pre-filter for mlx-whisper** — [S3] post-cohort gate. Two band-aids landed in B1 on 2026-05-14: (i) parameter tuning (`condition_on_previous_text=False`, `no_speech_threshold=0.85`, `compression_ratio_threshold=1.8`) breaks the autoregressive loop and drops over-compressed segments; (ii) `collapse_adjacent_repeats()` post-processor in `bristlenose/stages/s05_transcribe.py` collapses adjacent identical n-gram runs (length 1–8) with asymmetric thresholds — content-word and phrase-level repeats collapse at any adjacent occurrence ("thanks thanks", "Thank you. Thank you.", "facebook facebook"), while pure interjection runs are protected up to 6+ ("No. No. No." Thatcher-style, "yeah yeah", "very very good"). English-only reduplicable set; revisit for non-English cohorts. Verify after the first 2–3 cohort runs: are hallucinations still visible? If yes: integrate Silero VAD (~2 MB ONNX, well-regarded, used by `faster-whisper` already via `vad_filter=True` on the Linux/CPU path) as a pre-pass before calling `mlx_whisper.transcribe()` — extract speech regions only, feed those to the model. The mlx-whisper path is what every alpha cohort tester hits (macOS Apple Silicon), so this is the gap. Competitor differentiator context: Otter / Teams / Zoom / Dovetail / Marvin don't see this class of bug because their commercial ASR has VAD front-ends. If band-aids suffice: won't-fix.
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
- ~~[S5]~~ **SVG icon set** — _Demoted to beta-Must 4 May 2026 — char glyphs read "indie web app"; App Store screenshots will punish that, alpha 1:1 calls won't._ replace character glyphs (delete circles, modal close, search clear) with proper icons. Candidates: Lucide, Heroicons, Phosphor, Tabler. See `docs/design-system/icon-catalog.html`
- ~~[S5]~~ **Visual redesign: FT.com-level typographic legibility** — _Demoted to post-beta 4 May 2026 — most ambitious S5 item; FT.com is the direction not the alpha gate._ larger margins, fainter keylines, edo colours, more white space. FT.com as benchmark for large volumes of intense type with enough space to parse and scan
- [S5] **Colour themes** — named themes (e.g. "edo") as appearance switch. Beyond custom CSS — curated, designed themes. Needs design doc first: `docs/design-themes-and-schemes.md` — establish nomenclature (Theme = structure (font/spacing), Colour scheme = palette), file organisation, selection mechanism (CSS class? data attribute?), how Edo fits. Also investigate `--bn-selection-bg-inactive` dark value (#262626) too close to page bg (#111111). _Scoped 4 May 2026: Edo only, no theme-switcher UI for alpha. L → M._
- [S5] **Grid, spacing, type, colours audit** — holistic visual fit-and-finish pass
- [S5] **Serif voice-of-user quote treatment** — explore Sentinel (or comparable transitional/slab serif) for the verbatim quote text on the Mac version. Quotes are the *content*; everything else is chrome. A typographic distinction makes the participant voice unmistakable on the page. Gated on the typography audit landing first (so the serif sits inside a reconciled scale, not on top of one). Part of the design lockdown that gates the [S6] Hicks logo commission
- [S3] **Tag density** — AI generates too many tags, overwhelming (#12). _Scoped 4 May 2026: tuning deferred to post-alpha — tuning before alpha is guessing; IKEA + cohort feedback will point at specific cuts._
- - **~~Logo size~~** — 80px feels tiny, increase to ~100px (#6)
- **~~Responsive quote grid~~** — Phase 1 CSS-only, design ready, not implemented (design-responsive-layout.md)
- ~~**Help modal polish**~~ — platform-aware shortcuts, typography tokens, entrance animation, dark kbd. Shipped 0.13.3
- **~~"Made with Bristlenose" branding footer~~** — Phase 5 of export, quick win (design-export-sharing.md)
- ~~[S5]~~ **Export polish** — _Demoted to beta-Must 4 May 2026, rides with #17 zip export deferral._ minimum viable: delete things that should not be in an export, tidy up rough edges
- **Tahoe glass-bar styling** — [Beta-must] folded from 7 May walk (T19). Modernise toolbar/titlebar to follow the Tahoe pattern (and broader iOS/iPadOS direction): content slides edge-to-edge *underneath* floating glass-blur icon pills, rather than sitting in a discrete bar that crowds the content area. Forward-looking — also gracefully handles the toolbar overflow case better than a dense bar collapsing into ≫ menus. Worth aligning toolbar redesign with this rather than fixing the current bar in isolation. Pairs with the [S3] titlebar redesign in §2 — [S3] is the affordance fix (drop lozenge / promote project name); this is the visual-language modernisation
- **Structural sidebar reorg (Photos-style) — sketch first** — [Beta-must] folded from 7 May walk (T21). Move Project / Sessions / Quotes / Codebook / Analysis from the top toolbar into the left sidebar, Photos-style. Top of sidebar: tab items as primary nav (like `Library` / `Collections`); then a tiny grey-caps `Projects` section header (like `Pinned` / `Albums`); then the project list. Frees the titlebar for content + a few genuine controls; lets users *think about their content* rather than navigate around chrome. Dissolves several other titlebar problems (overflow ≫ menu, nav-arrow positioning, lozenge clutter, app-name-vs-project-name confusion). **Big snag, not a niggle — sketch before committing.** Mac sidebar conventions span "sidebar = nav + mode" (Photos / Things / Music / Finder / Claude Code) vs "sidebar = nav only, mode in toolbar" (Mail). Bristlenose's choice depends on whether tabs feel more like *mode* (case for sidebar) or *view on a project* (case for toolbar). Sectioning + visual differentiation carries the load (Finder / Notes / Reminders precedents). **Decision locked 8 May 2026:** Martin has a good feeling about it; next step is the sketch, not the implementation. Sketch path is hand-drawn (paper / iPad / Apple Notes) → upload image to Claude Code session with pixel dimensions + typography spec → discuss + iterate before writing any Swift. **Figma MCP setup is an alternative path but not a blocker** — the hand-sketch route is unblocked now. Filed separately as §11 Could "Figma MCP setup for design review pipeline" so the option is captured without gating this work. Sketch can land any time before the implementation slot — even before walks-fix-walks clears, since it's design exploration not code.


### Should

- ~~**Histogram bar alignment** — right-align user-tags bars (#13)~~
- **~~Day of week in session Start column~~** (#11)
- **~~Right-hand sidebar animations~~** — match left-hand sidebar push/slide animations
- **Desktop home view — recents / discovery expansion** — "no project selected" was an accidental engineering state; minimum-viable home view shipped 1 May 2026 (`WelcomeView.swift`, commit `816ab65` on `first-run`) with two variants (`.firstRun` icon + subtitle + New Project + drop target + 3-step rail + AI privacy link; `.noSelection` icon + "pick a project" + New Project CTA). Post-alpha expansion candidates remain: last project (already restored via `@AppStorage("selectedProjectID")`), summary of recent work, new Bristlenose features, latest models, codebooks from the community, window position/size restoration across launches (the project ID is restored; the window frame is the gap). The `chrome.noProjectSelected` / `chrome.selectProject` locale keys are no longer dead — `WelcomeView.noSelection` uses them — so the previous "prune unused keys" sub-clause is obsolete.


### Could
- **Symbology** — consistent Unicode prefixes (§ ¶ ❋) across navigation. Active branch
- **Close button CSS** — extract `.close-btn` atom (theme refactoring)
- **Content density setting** — Compact (14px) / Normal (16px) / Generous (18px) toggle. `--bn-content-scale` token (`0.875` / `1` / `1.125`), `font-size: calc(var(--bn-content-scale) * 1rem)` on `<article>`, cascades to all `rem`-based spacing. Toggle in toolbar or settings, persist via preferences store. Interacts with responsive grid — Generous + wide screen = fewer but more readable columns
- **Browse codebooks horizontal → vertical grid** — folded from 7 May walk (T22). _Demoted from Must to Could 8 May 2026 — "not a big one but a nice to have"._ Browse codebooks modal uses horizontal scrolling for framework cards. Made sense at 2–3; with the catalogue grown (Emotional & Cognitive Signals, Bristlenose UXR Codebook, Elements of UX, plus more off-screen) horizontal swipe-through hides options users can't predict are there. Switch to vertical grid (2–3 cards per row, scroll down) so the full catalogue is visible at a glance


### Icebox
- **Animated logo** — living-fish branch: breathing, gill pulsing, fin movement. Statement piece. Parked — oneday

---

## 4. Value — insights & time-saving ("why they'll use us")

### Must
- [S5] **QA: threshold review dialog on real data** — run AutoCode against real projects, evaluate confidence histogram + dual slider UX. _Reframed 4 May 2026: this is a continuous activity *during* alpha, not a pre-alpha gate. IKEA + cohort feedback IS the real data._
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

---

## 5. Blocking — prevents adoption or causes abandonment

### Must
- [S4] **First-run experience** — new user opens app, has no project, no API key, no recordings. What happens? Design doc complete (`launch-docs/design-first-run-experience.md` in delivery repo): coach-in-context, no wizards/sheets, trial IS the onboarding. Needs implementation. _Scoped 4 May 2026: existing `WelcomeView` + `BootView` + Beat 3 + Beat 3b is enough for guided 1:1 alpha calls. Full coach-in-context implementation deferred to beta. M → S. Confirm Beat 3 API roundtrip validation lands._
- ~~**API key entry in GUI** — currently requires terminal. Absolute blocker for App Store users~~
- ~~**Error messaging**~~ — pipeline failures show actionable messages ("check API credits or logs", "run bristlenose doctor"), red ✗ / yellow ⚠ per stage. Shipped 0.13.3
- [S4] **`bristlenose doctor` in GUI** — dependency health checks visible in app, not just CLI. _Scoped 4 May 2026: scrolling-text panel wrapping doctor stdout for alpha, not health-traffic-light UI. S → XS._
- ~~[S2] **Migrate `PipelineRunner` to `SidecarMode.resolve()`**~~ — done 2 May 2026 via PR #96 (`0e0157e`). `findBristlenoseBinary()` deleted; `PipelineRunner.spawn()` uses the same `SidecarMode.resolve(...)` path `ServeManager` does; bundled sidecar accepts `run` as a third subcommand gated on `_BRISTLENOSE_HOSTED_BY_DESKTOP=1`. Beats 6→13 now reachable under sandbox-on Debug — handoff prompt at `bristlenose_branch sandbox-debug/docs/private/prompts/track-a-beats-7-13-walkthrough.md` for the next session
- ~~**Homebrew formula: spaCy model** — post_install step (#42). Without it, first run fails~~

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
- [S6] **Privacy policy** — required for External TF + App Store submission. **Internal TF (stage 2) does NOT need a finalised privacy policy** — 5–10 watched friends in a private cohort, no commercial relationship, no money changing hands. **Gated on relay architecture, not on calendar.** The substantive privacy text is the Beta-stage data-sharing surface: how Claude API keys are handled in the relay, what flows through Bristlenose's servers in the funded-preview window, sub-processor relationships, retention. None of that text can exist yet because the relay architecture doesn't exist yet. Lock-in order: data-sharing architecture decided (Friendly-CTO Sundays + summer relay-infra work) → revise draft → running-friend tech lawyer first-read at running pace → commercial solicitor instructed when there's substantive prose to formalise. Draft v1 at `docs/private/launch-docs/privacy-policy.md` is placeholder shape and will be substantially rewritten. **Project-management state: parked, not pending. No near-term action.**
- [S6] **Terms of service** — same gating as Privacy policy above. Beta-stage commercial-risk surface (Claude API keys / relay data flow / refund policy / sub-processor agreements) is what needs commercial-solicitor money, and that surface doesn't exist yet because the relay architecture doesn't exist yet. Internal TF doesn't need this; Beta isn't close. Draft v0.9.1 at `docs/private/launch-docs/terms-of-service.md` is placeholder. **Don't spend lawyer money on the current draft — it describes a product that isn't being built.**
- [S2] **App Store review compliance (TestFlight subset)** — umbrella for: Apple Distribution cert ✅, sandbox + entitlements (Track A: A1 spike done 29 Apr 2026 — minimal entitlement set predicted; **A blocked on C1** because venv-based dev sidecar can't run under sandbox; resume as A1c once C1 lands), PyInstaller sidecar signing ✅, Privacy Manifest reason-code audit ✅ (C4, 28 Apr 2026), Hardened Runtime ✅. All tracked as individual items. Full review hardening for external testers / submission lives in S6. **C3 (Apr 2026) shipped Keychain → env-var injection + bundle integrity gates** (`check-bundle-manifest.sh` source→spec + `bristlenose doctor --self-test` spec→bundle, both wired into `build-all.sh`). Discovered 3 datas-coverage bugs during smoke test, resolved. **A1 spike output (29 Apr 2026):** `docs/private/sandbox-violations-A1.md` — predicted minimal entitlement set: host = `app-sandbox` + `network.client` + `files.user-selected.read-write`; sidecar = `cs.disable-library-validation` + `inherit`. SSB confirmed working with user-selected-files. **A1c smoke (30 Apr 2026):** `docs/private/sandbox-violations-A1c.md` — bundled sidecar present + spawning correctly. Confirmed: `files.user-selected.read-write` clears A1's bookmark deny ✅. Need to add: `network.server` (sidecar bind 9131 denied at kernel level — every report-rendering beat blocked). New non-sandbox findings: (1) `PipelineRunner.spawn()` PipelineRunner.swift:888 still calls stale `findBristlenoseBinary()` with `TODO(track-c-c1)` comment — C1 missed this code path, blocks all drop-and-run flows; (2) host i18n locales not bundled at `Resources/locales/` — pre-existing build-system bug, not sandbox; (3) `proc_listpids` denied (zombie cleanup non-functional under sandbox); (4) `iokit-open-user-client AppleNVMeEANUC` denied (silent). Two follow-up tasks chipped on main (cohort-baselines.json bundle datas, locales Copy Bundle Resources). Narrow-branch ordering: PipelineRunner migration → network.server entitlement → A1c-prime to surface Python-side surface (Whisper/FFmpeg/AppSupport/Ollama). **A2 ✅ shipped 1 May 2026** on `track-a-a2-network-server` worktree: `ENABLE_INCOMING_NETWORK_CONNECTIONS = YES` for the host Debug config grants `com.apple.security.network.server`, sidecar `bind()` succeeds, app reaches welcome view; A1c row 1 resolved. Side-effect: `desktop/scripts/reset-sandbox-state.sh` dev helper for libsecinit/secinitd EXC_BREAKPOINT recovery between iterations. Three design docs trued (desktop-python-runtime, desktop-security-audit, road-to-alpha) and `docs/private/sandbox-violations-A1c.md` appended with A2 verification block. Branch unpushed (4 working commits + 1 truing commit).
- [S5] **PII redaction audit** — verify Presidio catches names/emails in transcripts before shipping to paying users. Per `docs/design-modularity.md`: PII moves to `[pii]` pip extra (CLI) and tier-2 Background Assets pack (macOS, public beta) — out of base install. Alpha bundles it inline to avoid the asset-pack Python-packages-as-data problem; public beta deferred-downloads it. _Scoped 4 May 2026: spot-check Presidio on IKEA + FOSSDA for alpha; full audit + `[pii]` extra split + Background Assets pack is beta-Must. Alpha cohort = consensual UXR friends, not paying customers handling third-party data._
- **DPA executed with Anthropic** — [Beta-must, stage-5-prereq] _Promoted from §12 Should "[S6] Execute DPAs with LLM providers" 8 May 2026 per quality-reset folding._ Beta funded-preview routes user transcripts through Bristlenose's relay on Martin's Anthropic key, making Bristlenose data controller in transit. DPA must be signed before *any* relay traffic flows. Friendly-CTO Sunday topic. Solicitor review required. Sequencing: solicitor review → DPA signed → relay endpoint deployed → first Beta cohort. Cannot ship Beta without this
- **StoreKit receipt validation (server-side)** — [Beta-must, stage-5-prereq] _Promoted from §6 Should "[S6] Rate-limit trial-key endpoint" 8 May 2026._ Beta funded preview is gated by App Store purchase; relay endpoint validates the StoreKit receipt server-side before issuing per-user budget tokens. Without this, the funded relay is a free-for-all. Friendly-CTO Sunday relevant. Pairs with the funded-relay endpoint + budget-ledger work in §11. **Ship criteria:** every relay request carries a verified receipt token; replay attacks blocked; receipt revocation propagates to budget invalidation
- **Cost modelling defended numerically** — [Beta-must, stage-5-prereq] Per-user economics: ~$2/interview Claude cost on typical 30–60 min sessions × N interviews per Beta tester × ≤$4 funded-preview cap. Apple takes 15% (Small Business Program). $5 Beta price point is psychological, not revenue-generating — at price - 15% Apple - $4 relay the margin is roughly zero. Need numbers defended before pricing copy ships: average interview cost across the test corpus (FOSSDA / IKEA / demo-escuela / demo-sapporo), typical session count per cohort tester, kill-switch threshold for the global spend cap. Friendly-CTO Sunday topic. Output: a single numbers page reviewable by a battle-tested engineer before relay traffic flows
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
- **One-time `security-review` sweep of the threat-model surface** — ~30–50 files: PII redaction, telemetry, export pipeline, Keychain, sandbox entry points, auth middleware, media endpoint. Goal: every file in the threat model has been adversarially read at least once. Why: `/usual-suspects` only ever covered files touched by reviewed branches (~10% of the tree); the rest is implicitly trusted. One afternoon buys a defensible "every security-critical file has had one adversarial pass" claim. Not 100% review — risk-weighted. Floor stays ruff/mypy/pytest/e2e + defence-in-depth (sandbox, signing, leak-scan hooks)
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
- **Interim placeholder logo + neutral Edo-themed chrome — fine for TestFlight + quiet beta** — App Store listing, public website (`~/Code/bristlenose-website/`), favicon, in-app mark all run on a placeholder through internal TestFlight (closes late summer) AND the subsequent quiet, unpublicised, no-subscriptions initial public beta. Edo theme + considered type carries the visual identity in the placeholder window; the placeholder is honestly a placeholder. Don't burn weeks polishing an interim mark — its only job is "not embarrassing while we wait for Hicks." The durability bar (real mark you commit to for years) only kicks in at the LinkedIn-push moment below
- [post-100-days] **Hicks brief package — own discrete work, not a side-effect of S5** — assembling the package (reconciled type scale documented as a system, design-system writeup so the language is *explicit* not just lived in CSS, 1-page proposition site rewritten for the design lockdown, bounded brief with deliverables + dimensions + due date) is its own chunk of work that doesn't fall out of S5 for free. The S5 design work *uses* the new system in code; this item *writes the system down* so a designer can read and inherit it. Without this, the gate-cleared moment still has nothing to send. Schedule explicitly when the LinkedIn-push moment is in sight, don't assume it's absorbed by anything earlier
- [Jun 2026 — early summer] **Hicks logo commission — friendly low-pressure ask to an old collaborator** — Jon Hicks ([hicks.design](https://hicks.design) — Firefox, MailChimp, Skype) for the Bristlenose mark. Warm intro, not cold: prior Canonical web icon-set client from user's Canonical years. Budget covers mark only (Mac app icon 1024px masked-squircle, web/header lockup, favicon 16/32/180) — not full identity, so the surrounding work has to do that lift. **Ideal ask shape:** early summer 2026, asking him to fit a small piece of work into the next ~6 months at his own pacing. That generous landing window (≈Jun→Dec 2026) is the right tone for an old collaborator — no deadline pressure, slots into his calendar, respects his other commitments. **Public posture in the meantime:** internal TestFlight + soft-launch public beta (fewer than ~100 users, no LinkedIn push) continue with the placeholder mark. Real mark goes live whenever his work lands inside the 6-month window; LinkedIn push waits until after that. That ordering means the logo arrives *before* the audience-growth event, so it's "something not to change for the next few years" by the time anyone sees it at scale. **Gated on all four landing first** (so the brief he reads describes a coherent visual world): typography audit reconciled (#3 Must), Edo colour theme landed and tuned (#3 Must), serif voice-of-user quote treatment explored (Sentinel or alternative) Mac-side (#3 S5), grid/spacing/colours fit-and-finish at "indie Mac app you'd screenshot" level (#3 Must). Realistic calendar: substantial design lockdown by ~end May / early Jun so the brief package can be assembled in early Jun. **Package to send him:** reconciled type scale + design-system writeup + 1-page proposition site + bounded brief. **Why gated:** Hicks picks projects; he's not auditioning, the work is. Returning-client warmth + relaxed timeline help him say yes, but neither lowers the design bar. Do not pitch before the gate clears — wasting his time forecloses the relationship. See private memory `project_hicks_logo_ask.md`. **Gated on all four landing first:** typography audit reconciled (#3 Must), Edo colour theme landed and tuned (#3 Must), serif voice-of-user quote treatment explored (Sentinel or alternative) Mac-side (#3 S5), grid/spacing/colours fit-and-finish at "indie Mac app you'd screenshot" level (#3 Must). **Package to send him:** reconciled type scale + design-system writeup + 1-page proposition site + bounded brief. **Why gated:** Hicks picks projects; he's not auditioning, the work is. Returning-client warmth helps him open the email — it does not lower the design bar. Do not pitch before the gate clears — wasting his time forecloses the relationship. See private memory `project_hicks_logo_ask.md`.
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
- **i18n: Settings → LLM provider Ollama description tone-tighten** — _parked from i18n plan-review pass 5 May 2026 (William finding F9, ux-critique probe 4)._ "Free, runs locally. No API key needed." reads salesy compared to the rest of Settings copy ("Backend", "Auto detects the best engine for your Mac."). Cleaner: "Runs locally. No API key required." — drops the marketing word, keeps the two researcher-relevant facts. Six-locale fill cost — defer to a copy-only branch where translators see the whole sweep at once
- **i18n: Settings → LLM activation-toggle copy parity** — _parked from i18n plan-review pass 5 May 2026 (William finding F10, ux-critique probe 2)._ Generic "Use this provider" reads thinner than the Ollama row's "Use the local Ollama model" — the existing comment in `LLMProvider.swift:101-104` already complains about this. Per-provider rich copy ("Use Claude for analysis", "Use ChatGPT for analysis", "Use Gemini for analysis", "Use Azure OpenAI for analysis", "Use the local Ollama model") would remove the asymmetry. ~30 strings × 6 locales — copy-only branch when convenient
- **i18n: frontend BCP 47 lookup audit** — _parked from `locale-system-delegation` plan review 5 May 2026._ The desktop branch will switch to `Bundle.preferredLocalizations` for canonical BCP 47 lookup. The frontend (`frontend/src/i18n/LocaleStore.ts`) likely uses `navigator.language` with naive prefix-strip — same `zh-Hant` / `zh-Hans` / `pt-BR` / `pt-PT` trap. 5-minute audit during the desktop branch; if real, file a sibling branch. Don't couple to alpha
- **i18n: web Settings modal "Reset to system default" affordance** — _parked from `locale-system-delegation` plan review 5 May 2026._ The desktop side delegates locale to System Settings → Apps → Bristlenose, where macOS's "System Default" option clears the per-app override for free. The web Settings modal has no equivalent — once a user picks a language, they have no in-UI way to revert to "follow `navigator.language`." Trivial to add: an "Auto / System default" option at the top of the language dropdown that calls `localStorage.removeItem("bristlenose-language")` and re-reads `navigator.language`. Not blocking alpha

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
- **QA: pinch-to-zoom + ⌘+/⌘− across sidebar layouts** — verify the 6-column quotes-page grid (`toc-rail | toc-sidebar | center | minimap | tag-sidebar | tag-rail`) survives 3–4 native browser zoom steps without minimap or tag-sidebar collapsing wrongly. Trackpad pinch and Magic Mouse ⌘+/⌘− should both be safe (we have zero `wheel` listeners, so synthesised pinch falls through to browser zoom). Five-minute manual check in serve mode at `/report/quotes/`; only writes a follow-up if the grid actually shatters. Captures a Magic Mouse user's primary zoom path
- **Visible sidebar toggle buttons in React toolbar** — Mac-native affordance for the three rails (TOC sections / tag sidebar / project sidebar). Today they're keyboard-only (`[`, `]`, `\`, `⌘.`) which is fine for power users but invisible to first-timers. Real Mac apps (Mail, Notes, Xcode, Finder) all expose sidebar toggles as toolbar buttons with the `sidebar.left` / `sidebar.right` SF Symbol; click toggles, the keyboard shortcut is the power-user path. Pairs with the existing "Show/Hide panel label flip" item above (Mac menu bar half) — this is the React-side complement. **Don't add new keyboard shortcuts** — ⌘B collides with bold in every editable surface, ⌘0 collides with browser/Figma reset-zoom. Our existing plain `\` and `⌘.` already match Figma/Sketch/Miro muscle memory (the audience-weighted cluster that matters for researcher-designers), so the gap is discoverability, not chord choice

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
- **Choose Icon as flyout menu** — context-menu "Choose Icon" currently opens an attached popover (100 SF Symbols in a grid). Mouse-up dismissal on the menu item feels mediocre next to a true submenu flyout. Options: (a) trim palette to ~15 inline icons in a submenu and lose the long tail; (b) Finder tag-colour hybrid — top 12 inline + "All Icons…" opens the full popover; (c) inline `Menu` with custom grid view (fights NSMenu's text-list shape). Ellipsis already trimmed from the menu label; full UX treatment deferred

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
- [S3] **Adaptive `llm_concurrency` from response headers** — today `llm_concurrency` is a static config knob (default 3, `bristlenose/config.py`). Tier 1 Anthropic users on long transcripts can hit 429 (Sonnet 4: 50 RPM, 40K input TPM); higher tiers leave headroom unused. Auto-tune from the rate-limit headers every LLM response carries — no probe call, no separate "ask my tier" endpoint exists at any provider (concurrency isn't a thing they limit on; RPM/TPM is). **Outline:** (1) Wrap the LLM client to capture `anthropic-ratelimit-{requests,tokens,input-tokens,output-tokens}-{limit,remaining,reset}` (Anthropic) and `x-ratelimit-{limit,remaining}-{requests,tokens}` (OpenAI) on every response. Gemini fallback: hardcoded per-tier table (no consistent header support). Azure: per-deployment quota in headers, same shape as OpenAI. (2) Token-bucket throttle in front of the existing `asyncio.Semaphore` — bucket sized from observed limits, refilled per `*-reset`. Semaphore width derived from `safe_concurrency = (RPM × avg_request_seconds / 60) × 0.8` after first 3-5 calls give a latency baseline. (3) On 429, halve bucket + exponential backoff; recover toward observed ceiling. (4) Surface chosen concurrency in `bristlenose.log` (INFO line per stage) and in `doctor` output. (5) Keep `llm_concurrency` config as a hard ceiling override — auto-tune never exceeds it. **Cost:** ~1 day Anthropic + OpenAI; +0.5 day Gemini fallback table; +0.5 day tests + doctor surface. **Won't fix:** the within-pipeline parallelism is already as parallel as rate limits allow at concurrency=3 for typical projects; the win is for power users on Tier 2+ with 20+ interview projects who currently leave headroom on the floor. Pairs with future `bristlenose doctor` "your tier supports up to N concurrent" surface. Sprint placement: S3 (12–23 May 2026 multi-project window) as a side-quest — same config layer, different feature.
- **Logging tiers 2–3** — cache hit/miss decisions, concurrency queue depth, PII entity breakdown, FFmpeg command/return code, keychain resolution, manifest load/save (6 items, all trivial–small)
- **Promote pip-audit + npm audit to blocking** — target v0.15.0 (trivial)
- **i18n: pseudo-localisation QA** — add `i18next-pseudo` to catch remaining hardcoded strings. See `docs/design-i18n.md`
- [S3] **Hardcoded project ID audit** — ~12 locations hardcode project ID `1` (`app.py`, `export.py`, `api.ts`, `PlayerContext.tsx`, `ExportDialog.tsx`, `useProjectId.ts`, `main.tsx`, `index.html`). Two are bugs now (bypass `apiBase()`). Parameterise before multi-project. (design-multi-project.md §4)
- **Regression test: lazy Whisper model load** — pin the double-gate at `pipeline.py:2026-2035` and `s05_transcribe.py:58-65` so the ~1.5GB model is never fetched when every session has an existing transcript (Teams `.docx` / Zoom `.vtt`). Mock `WhisperModel` (faster-whisper) and `mlx_whisper.transcribe`, run pipeline against a fixture where all sessions have `has_existing_transcript=True`, assert neither backend was called. Load-bearing for desktop first-run UX — a future "warm up backend on app launch" optimisation would silently defeat the gate without this test. See `docs/design-asr-backend-strategy.md`.

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
- **Sidecar lifecycle: PID-file in App Group container as a follow-up to A6.** A6 (1 May 2026) shipped parent-death detection via `os.getppid()` polling — sidecar self-terminates within ~2s of host death. Cheaper alternative considered but not implemented: sidecar writes `~/Library/Containers/app.bristlenose/Data/Library/Application Support/Bristlenose/sidecar-<port>.json` (`{pid, port, started_at}`) on bind, atexit-unlinks on clean exit; host reads file on launch, `kill(pid, SIGINT)` if alive. Zero polling, zero kqueue, faster detection (~ms not seconds). Adopt if alpha cohort reports lingering orphans (would be visible in `sidecar_exit reason=...` log lines — search for unexpected `parent_death` clusters). Background prior art in `feedback_review_scope_creep.md`.
- **Sidecar lifecycle: host-side crash-loop detection + auto-respawn.** A6 ships "sidecar dies → host's WKWebView shows 'Server error · Retry'." For public beta: host detects sidecar exit, auto-respawns with backoff, surfaces a more specific error after N consecutive failures. For alpha we want *visibility* (the structured `sidecar_exit` log line), not auto-recovery — so we can act on cohort feedback. Trigger: first alpha tester report of "the app keeps crashing" → revisit.
- **PipelineRunner Shape B migration** — `bristlenose run` becomes a serve-mode HTTP endpoint. Today the bundled sidecar accepts `serve` (long-running) AND `run` (one-shot pipeline) as two subprocess paths, gated by the `_BRISTLENOSE_HOSTED_BY_DESKTOP=1` env-var handshake (Shape A — landed PR #96, May 2026). Shape B collapses this: serve-mode FastAPI gains `POST /api/projects/:id/pipeline/run` + SSE progress, `PipelineRunner.swift` becomes a thin HTTP client (deletes ~200 lines of process supervision), env-var gate disappears, sidecar `_PASSTHROUGH_COMMANDS` shrinks to `{"doctor"}`. Side-effect: enables concurrent project runs (today FIFO at the `Process()` slot — within-project multi-interview concurrency is already solved via `asyncio.Semaphore`, see `bristlenose/llm/CLAUDE.md:56`). Concurrent runs is _not a pricing/sales gating feature_ — nobody pays $14/mo because they can run 3 projects at once. Cost estimate: 1–2 days. Grep anchor `TODO(shape-b)` in `desktop/sidecar_entry.py` is the real surfacing mechanism — do it when iPad companion or cloud-tier scoping starts and wants the HTTP-on-serve shape, not before.

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
- [S4] **Provider setup guide** — which LLM provider, how to get API key, cost expectations. _Scoped 4 May 2026: Claude-only README plain text for alpha. Settings UI keeps all providers visible — alpha messaging is "known to work with Claude, please try anything else you have and let us know." Free coverage for non-Claude paths from testers who already have those keys. S → XS. See `project_alpha_provider_strategy.md`._
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
- [S3] **CI: desktop-build job** — `xcodebuild build` + `xcodebuild test` on macOS runner, `CODE_SIGNING_ALLOWED=NO`, informational initially. Catches Swift compilation errors and Swift Testing regressions on every push. Prerequisite for the full build pipeline below. Plan: `docs/design-ci.md` §Coverage gaps
- [S3] **TestFlight upload pipeline** — Xcode archive → App Store Connect upload (notarytool). Manual first (local `xcodebuild -exportArchive` + `xcrun notarytool submit`). Automate in S6. Only runs when MVP flow is green + sandbox is clean. _Scoped 4 May 2026: manual-only for first iteration; automation deferred to S6. M → S._ _Re-tagged S2→S3 8 May 2026 — S2 declared done; this slipped per quality-reset walks-gate._
- ~~**Desktop app build pipeline (.dmg path)** — won't do (17 Apr 2026). App Store is the sole distribution channel. See `docs/private/road-to-app-store.md` Decision section~~
- [S6] **App Store Connect setup** — app record, TestFlight internal beta group (≤100 testers, no Beta App Review), Privacy Nutrition Labels. Pricing + external tester config deferred to S6. _Scoped 4 May 2026: engineering work mostly done (cert, profile, bundle ID); what's left is form-filling. S → XS._
- ~~[S2] **Apple Distribution certificate + provisioning profile**~~ ✅ **Done 19 Apr 2026 (Track C C2).** Cert + profile installed; notarytool keychain profile `bristlenose-notary` set up. Portal artefacts in `~/Code/Apple Developer/`
- **Developer ID certificate** — **deferred, not rejected (28 Apr 2026 reframe).** Trigger to revisit: ~10k paying users, OR first enterprise MDM ask. Sparkle update flow + notarytool submit are preserved as future-state in `design-desktop-python-runtime.md` §"Deferred — Developer ID flow"
- ~~[S1] **CI: add macOS runner** — currently Linux-only (informational, 15 Apr 2026)~~
- ~~**.dmg README** — won't do (17 Apr 2026). App Store path only~~
- ~~[S2] **PyInstaller sidecar signing**~~ ✅ **Done end-to-end 28 Apr 2026 (Track C C2 + post-C3 hardening).** Parallel `wait -n` job pool, SHA256 sign-manifest, full pipeline in `desktop/scripts/build-all.sh`. SECURITY #5/#8 unblocker landed 26 Apr (`823f9be..38808fe`); end-to-end run clean 28 Apr (`1ee30eb`) — adds Mac Installer Distribution cert + `installerSigningCertificate` in ExportOptions, falls back to `.app` from xcarchive when `method=app-store` exports only `.pkg`, skips notarytool/stapler/spctl on the App-Store path (`notarytool` only accepts Developer ID; App Store Connect validates server-side), uses `pkgutil --check-signature` instead. Empty-ents retest ran 28 Apr — RED (`8cfd2ee`): Python.framework's nested `_CodeSignature/` seal is the binding reason DLV stays. Lsof zombie-cleanup also libproc-only now (`5471b35`). C3 bundle-integrity gates resolved BUG-3/4/5
- ~~[S1] **Build number auto-increment** — `CFBundleVersion = 1` blocks Sparkle and App Store update logic. Set up CI auto-increment. Done: `bump-version.py` unifies desktop+CLI, auto-increments build number~~
- ~~[S1] **Domain & email infrastructure** — register `bristlenose.app`, configure SPF/DKIM/DMARC, Substack custom domain (`blog.bristlenose.app`), deploy site, set up email on DreamHost (`hello@`, `support@`, `security@`). Full plan: `docs/private/infrastructure-and-identity.md`~~
- [S6] **Supply chain hardening** — GitHub 2FA with hardware key, ~~branch protection on main~~ (✅ 13 May 2026), PyPI hardware key + project-scoped token, register PyPI typosquats. Full checklist: `docs/private/infrastructure-and-identity.md`. Deferred from S1: low threat until commercial launch (see `docs/private/supply-chain-deferral.md`)
- **Funded relay endpoint and budget ledger** — Server-side proxy to Anthropic on Bristlenose's key for Beta funded-preview. Per-user budget cap (~$4 per receipt), global spend cap with auto-degrade-to-BYOK kill switch. Stage-5 prerequisite (Beta in store launch). Friendly-CTO Sunday topic. Cost: $5 - 15% Apple - $4 relay = ~zero margin (price is psychological, not revenue). See `project_lifecycle_stages.md`, `project_2000_customers_target.md`.
- **Crash telemetry baseline** — Lightweight crash reporting for Beta cohort. Was deferred phase 2-4 of alpha-telemetry; promoted to Beta-must per 7 May quality reset. Stage-5 prerequisite. Server-side (Sentry-class or first-party); opt-in disclosed in privacy policy.

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
- **Figma MCP setup for design review pipeline** — captured 8 May 2026 from T21 sketch-method discussion. If/when paper sketches outgrow Claude-Code-image-upload as a review medium, set up the Figma MCP integration so design files are inspectable directly in agent sessions. Not a blocker for any current work — hand-sketch + image-upload + dimensions/typography spec is the baseline. Surface this when (a) ≥3 sketches accumulate, OR (b) a design needs multi-state interaction modelling that paper can't carry. Until then, paper wins on speed
- **Weekly install smoke tests** — automated pip/pipx/brew verification
- **Perf history charts** — render `e2e/.perf-history.jsonl` as a chart over time (DOM counts, API latency, export size). Currently view-only via `scripts/perf-history.sh` (tabular). Options: Observable notebook, tiny matplotlib script, or a React page in the dev-only About panel. Source data: one JSON line per perf-gate run, gitignored (local-only). When we want cross-machine history, upload `.perf-history.jsonl` as a CI artifact and stitch runs together

---

## 12. Legal/Compliance — gates to App Store

### Must
- ~~[S1] **Apple Developer Program** — $99/year, individual enrollment (Martin Storey, Team ID `Z56GZVA2QB`). Bundle ID: `app.bristlenose`. Activated 16 Apr 2026, expires 16 Apr 2027. Transition to Ltd organisation enrollment if/when revenue justifies it (team transfer preserves app listing, reviews, URL). Full plan: `docs/private/infrastructure-and-identity.md`~~
- [S6] **Privacy policy URL** — required for external TestFlight + App Store submission. Not needed for internal alpha. Host at `bristlenose.research/privacy`. Draft complete, needs solicitor review (May) then hosting
- [S6] **Terms of service** — see canonical entry in §6 Risk Must. Gated on relay architecture, not on calendar. Internal TF doesn't need this; Beta does, and Beta isn't close.
- ~~[S2] **App sandbox compliance**~~ ✅ Mission Sandbox PASSED 4 May 2026 — entitlements for file access, network (LLM API calls). Required for App Store Connect upload (including TestFlight)
- [S6] **Export compliance** — HTTPS only, no custom encryption = simplified declaration
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
- **`Bristlenose Beta` listing copy in original-Beta-warning-label voice** — [Beta-must, stage-5-prereq] Beta gate is "warning-label-tolerable rough edges allowed *if* the warning is visible." App Store listing copy reclaims the original meaning of "Beta": this is software under active development, things will break, your feedback shapes what ships. *Not* the modern marketing-Beta where "beta" is just lower-case "1.0". Listing description, What's New, screenshot captions, support page all carry the warning-label voice. The honest framing earns more trust than the sanitised one with this customer profile. **Ship criteria:** listing reads as "we're being straight with you about where this is" not "we're slightly hedging the launch"; the word "Beta" appears in the public app name (`Bristlenose Beta`) and drops to `Bristlenose` only at GA

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
- [S5] **Systematic accessibility review via ux-review skill** — run the `ux-review` agent on every new feature before merge and retroactively on all existing interactive surfaces (modals, sidebar, tag input, toolbar, quote cards, analysis page). The skill checks WCAG 2.1 AA, keyboard navigation, ARIA roles, focus management, screen reader support, and reduced motion. Make this a gated step in the feature workflow, not an afterthought. _Scoped 4 May 2026: wire the agent as a gate on **new** features for alpha (cheap); the retroactive sweep across existing surfaces is beta-Must. Alpha cohort doesn't include screen-reader users._
- [S5] **Non-focusable interactive elements (span onClick → button)** — Add Tag (+) on QuoteCard, Badge delete, Badge accept/deny actions, Counter unhide are all bare `<span onClick>` — invisible to keyboard users and screen readers. Convert to `<button>` with `aria-label`. (a11y audit, critical)
- ~~[S5]~~ **TagInput: implement WAI-ARIA combobox pattern** — _Demoted to beta-Must 4 May 2026 — hidden SR semantics invisible to alpha cohort._ missing `role="combobox"`, `aria-expanded`, `aria-autocomplete="list"`, `aria-controls`, `aria-activedescendant`. Suggestion list needs `role="listbox"`, items need `role="option"`. (a11y audit, critical)
- ~~[S5]~~ **Modal atom accessibility upgrade** — _Demoted to beta-Must 4 May 2026 — M-sized shared-hook + focus-trap work, beta._ `role="dialog"`, `aria-modal`, focus trap, focus restore as a shared hook/wrapper. Retrofit to all 6 modals (HelpModal, ExportDialog, FeedbackModal, AutoCodeReportModal, ThresholdReviewModal, SettingsModal). HelpModal is the worst — no dialog role, no focus trap, no focus return. SettingsModal's ModalNav pattern is the reference implementation. (a11y audit, major)
- [S5] **NavBar: remove incorrect role="tablist"** — router links are not ARIA tabs; no matching `role="tabpanel"` exists. Semantic `<nav>` with links is correct. (a11y audit, major)
- ~~[S5]~~ **Missing aria-labels on inputs** — _Demoted to beta-Must 4 May 2026 — pure SR affordance, invisible to alpha cohort._ SearchBox ("Filter quotes"), TagInput ("Add tag"), TagSidebar search ("Search tags"), TagFilterDropdown search ("Search tags"). Placeholder text is not a label. (a11y audit, major)
- ~~[S5]~~ **ViewSwitcher dropdown keyboard navigation** — _Demoted to beta-Must 4 May 2026 — power-user kbd nav; alpha cohort uses mouse on calls._ menu items have no `tabindex`, no Arrow key navigation, no Enter/Space to select, no Escape to close. (a11y audit, major)
- [S5] **Icon contrast failures** — `--bn-colour-icon-idle` (#c9ccd1 on white = 1.8:1) and `--bn-colour-starred` (#999 on white = 2.8:1) fail WCAG 1.4.11 non-text contrast (3:1 required). Dark mode `--bn-colour-icon-idle` (#595959 on #111 = 2.4:1) also fails. (a11y audit, major)
- [S5] **No `<main>` landmark** — QuotesTab renders in a bare fragment. Wrap `<Outlet>` in AppLayout's center column with `<main>`. (a11y audit, major)
- [S6] **Keyboard navigation audit** — verify all interactive elements reachable via Tab
- [S6] **VoiceOver testing** — basic screen reader pass on report and desktop app
- [S6] **Colour contrast** — WCAG AA on all text (light + dark mode)
- ~~[S5]~~ **Focus indicators** — _Demoted to beta-Must 4 May 2026 — systematic token + sweep is more than it looks. Pairs with span→button (#34 alpha-Must) — `<button>`s need *some* focus treatment, but the systematic token can wait._ visible focus rings on all interactive elements

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
- ~~[S1] **Bundle size CI gate** — `size-limit` + `@size-limit/file`, 305 KB gzip limit. CI enforces in `frontend-lint-type-test` job. Current ~300 KB. 100 KB target needs route-level code splitting (separate task)~~ **Reframed 2 May 2026.** Old metric (sum of every `*.js` in `assets/`) overcounted by ~110 kB by including 40+ lazy locale chunks that never load on first paint, plus dev-only entries. New metric is **"Live SPA, English (gzipped)"** — same glob, but excludes `visual-diff-*`, `ResponsivePlayground-*`, `Playground*`, `devicePresets-*`, `HelloIsland-*`, and the 8 locale-namespace patterns (`common-*`, `settings-*`, `desktop-*`, `enums-*`, `cli-*`, `doctor-*`, `pipeline-*`, `server-*`). Limit set to **210 kB** (current 204.42 kB, 5.58 kB headroom). Honest measurement of regressions for code that actually loads on first paint; lazy locales no longer eat budget so adding the 7th locale won't blow the gate. Side-finding logged: i18n's dynamic-import template at `frontend/src/i18n/index.ts:46` captures all 8 JSON namespaces from `bristlenose/locales/${locale}/${ns}.json` even though only 4 are loaded at runtime — ~10 kB gz of dead chunks (cli/doctor/pipeline/server) that should be narrowed in the bundle slimming pass. Full analysis at `docs/private/bundle-size-analysis-2026-05-02.md`.
- **Bundle slimming pass (post-TestFlight optimisation)** — analysis done 2 May 2026 (`docs/private/bundle-size-analysis-2026-05-02.md`). Real targets: (1) `components-*.js` at 107 kB gz holds 37 components + 14 islands collapsed into one chunk because `main.tsx`'s legacy-island dynamic imports lose to `pages/*Tab.tsx` static imports — the 7 `INEFFECTIVE_DYNAMIC_IMPORT` warnings document this. **Single biggest lever:** delete legacy island mode in `main.tsx` together with the static render (both already on the deletion path), then route-level code-splitting actually works. Projected first-paint saving 30–50 kB gz. (2) Narrow i18n's dynamic-import template to the 4 namespaces actually loaded (~10 kB gz of dead chunks deleted at build time). (3) Confirm `visual-diff` is meant to ship to production assets, or move it to a dev-only entry. Don't chase i18n core (18.6 kB gz, load-bearing). **When:** post-TestFlight beta polish window. **Why deferred:** "we just need to get something that works into the hands of 5 people in May." 204 kB gz is fine for the alpha cohort on residential broadband.
- ~~[S1] **`GZipMiddleware` in FastAPI** — one line. ~70% reduction in served HTML/CSS/JS. Free win for WKWebView and browser~~
- ~~[S1] **`content-visibility: auto` on quote card containers** — CSS only, works everywhere including file://. Browser skips layout/paint for off-screen cards. Supported since Safari 17.4. Essential for static export path where JS virtualisation isn't possible~~
- [Icebox] **`@tanstack/virtual` in serve mode** — deferred 17 Apr 2026. Stress sweep (see git log: `stress sweep findings: clean linear scaling to n=3000`) shows clean linear scaling up to 3000 synthetic quotes, well above the 1,500-quote 15h-study ceiling. Not a blocker for alpha or launch. Re-open if real-world use surfaces pathological cases
- ~~[S1] **Move `<script>` to end of `<body>`** — script block is already at end of `<body>` (after all `<article>` content, before `</body>`). No `<head>` scripts exist. Done~~
- ~~[S2]~~ **Performance regression gate in CI** — _Demoted to Should 4 May 2026, S6/post-alpha — bundle-size gate already exists; stress sweep proved n=3000 scales; alpha cohort on 1:1 calls will surface perf regressions directly._ Playwright spec in existing E2E suite measuring DOM node count, API latency, export file size against smoke-test fixture. Doubling rule (fail at 2x baseline). Measured baselines: quotes page 549 nodes, export 1.6 MB. Design doc reviewed, ready to implement. See `docs/design-perf-regression-gate.md`
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
- **~15 May 2026 — revisit platform-policy Open Questions** — `docs/design-platform-policy.md` "Open questions / known gaps". Triage: auto-merge workflow + `pip-audit`/`npm audit`/`ignore-scripts` gates, tiered security SLA matrix (Tier 1 72h / Tier 2 7d / Tier 3 quarterly), ESLint stack `groups` vs four `ignore`s, WWDC ritual calendar hook (annual auto-filed issue), `pbxproj` dual-target comment. Decide: do now / defer to next quarterly tooling review / fold into WWDC-2026 prep window (early June).
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
- **Xcode Cloud for archive → notarise → TestFlight upload** — Apple-silicon macOS VMs (M-series, ~M1-class, free tier 25h/mo). Won't help Python/Playwright/PyInstaller, but could automate the Organizer dance once the app stabilises. Post-TestFlight quality-of-life, not alpha-blocking. Revisit after first cohort lands

---

*Updated 17 Apr 2026 (four passes). Fourth pass: alpha path decided — internal TestFlight, not `.dmg`. Reasoning: StoreKit needs sandbox anyway, doing it now means a modern codebase from the start. Rejected `.dmg` path items (Developer ID cert, .dmg build pipeline, Gatekeeper README) struck in §11. TestFlight upload pipeline + App Store Connect setup + App Store review compliance umbrella moved back to S2. S2 cadence: CI cleanup first, then A/B interleave sandbox/signing ↔ MVP flow steps. First upload when both tracks green (may slip to S3 — MVP quality is the deadline, not calendar). Full path in `docs/private/road-to-app-store.md`. Third pass: Mac app MVP 1-hour flow is the real gate. Added §1a MVP flow checklist. Virtualisation → Icebox (stress sweep shows clean scaling to n=3000). AI disclosure dialog marked shipped (AIConsentView.swift). Real QA path = IKEA study + CLI handholding on video calls with UXR friends. Second pass: Sprint 2 re-scoped to "Perf + TestFlight alpha pipeline": perf items first (virtualisation, regression gate), then internal TestFlight path (App Store Connect record, Apple Distribution cert, sandbox, Privacy Manifest, Export compliance, sidecar signing, AI disclosure lightweight). Second pass deduplicated Privacy Manifest + AI disclosure (kept §6 Risk as canonical, §12 Legal points there); split signing into Apple Distribution (S2, TestFlight path) vs Developer ID (S6, .dmg path); moved .dmg build pipeline, .dmg README, DPAs, and trial-key rate-limit to S6 (v1.0-blocking, not alpha-blocking). Solicitor contact: May. Previous: 15 Apr 2026. Reconciled with delivery repo copy: added §15 Performance (WebKit philosophy, profiling-first roadmap, perf-review agent, CI gates), sprint legend, iPad session outputs (privacy policy draft, ToS v0.9.1, privacy manifest, first-run experience design, new items L5/L6/I6/I7/R6), bundle size → §15 promotion. Previous: 25 Mar 2026 — domain architecture, security audit additions, shipped-item strikethrough. Original: 16 Mar 2026.*
