---
status: pending
last-trued: 2026-11-10
trued-against: HEAD@main on 2026-11-09
---

# Notification surfaces — which event goes where, and what the web toast becomes

> **Research and plan. Nothing here is built.** It answers one question: Bristlenose
> has five feedback surfaces that grew separately (the SPA toast, the SPA activity
> chip, the Mac's sidebar and toolbar indicators, the Mac's one notification
> banner, and the CLI's terminal lines). Which event belongs on which, and what does
> the toast that remains need to be?
>
> **The principle (owner, 9 Nov 2026):** where a Mac-native way exists, do not draw a
> toast; where we are in the web world (`bristlenose serve` in a browser, the HTML
> export) we need one. It is a per-message triage, not a "port toasts to Swift" job
> (the lean agreed on 27 Jul 2026, recorded in
> [`design-embedded-activity-routing.md`](design-embedded-activity-routing.md) §"Scope boundary").
>
> **The second principle (owner, 9 Nov 2026): attention picks the surface.** If Bristlenose
> is visible and in front, the researcher is looking, so the in-window surfaces
> (sidebar row, pill, chip, a toast where one is still needed) are enough and the system
> raises **no** notification. A system notification is for when they are *not* looking:
> the app is behind a stack of other windows, hidden or minimised, or the display is
> asleep or the screen locked. The shipped run banner already follows this to the letter
> (`RunBannerCoordinator.runDidEnd`: `guard !attention().isLooking`; "looking" is active
> app + a visible window + display awake + screen unlocked + login session active,
> `design-run-banner.md` §Fixes #1). So the rule is not new; this doc's job is to say
> that any *future* event wanting a banner goes through that same gate, and that nothing
> else may post one while the researcher is looking.
>
> **The third principle (owner, 9 Nov 2026): a toast is not the cheap way to tell the
> user something.** Progress on real data is designed *on the data*: a thumbnail that
> will be real in a minute shimmers where it will appear (the ghost → working → done
> vocabulary decided the same day, `design-motion.md` §4.7.2, `docs/mockups/loading-states.html`,
> not yet built), not narrated by "your thumbnails are loading". §3b states when a
> toast is the right surface.
>
> **Siblings.** [`design-embedded-activity-routing.md`](design-embedded-activity-routing.md)
> owns the *progress* half (the activity chip). This doc owns the *informational*
> half that doc named as "a yet-unwritten sibling", and ties the two together.
> [`design-run-banner.md`](design-run-banner.md) owns the one native notification.
> [`design-pipeline-diagnostic-popover.md`](design-pipeline-diagnostic-popover.md) owns the
> message-kind vocabulary and the "don't reach for a toast" rule on the Mac.

## 1. What exists today

| Surface | Where | Who draws it | Used for |
|---|---|---|---|
| **SPA toast** | `frontend/src/utils/toast.ts`, `components/Toast.tsx`, `theme/atoms/toast.css` (`.clipboard-toast`, `--bn-toast-z`) | the page, in the browser **and** inside the Mac's web view | 27 call sites (§2): confirmations, no-op explanations, failures |
| **SPA activity chip** | `components/ActivityChipStack.tsx`, `ActivityChip.tsx`, `contexts/ActivityStore.ts`, `theme/atoms/activity-chip.css` | the page, portalled to `document.body` | AutoCode, catch-up, clip export, screens export: progress, result, action, cancel. Survives lens switches (module-level store), and a reload (session storage, RE#38) |
| **Screen-reader line** | `utils/announce.ts`, `components/AnnounceRegion.tsx` | the page | `toast()` calls it for you; about 20 other callers use it alone |
| **Mac sidebar row** | `ProjectRowActivityIndicator.swift` (ring), `SidebarActivityRing.swift`, `ProjectSubtitle` / `SidebarSubtitleText` (status line) | the app | a pipeline run, a drag-import copy |
| **Mac toolbar pills** | `StatusPill.swift` shell; `OllamaDownloadPill`, `WhisperDownloadPill`, `ProviderProblemPill`, `AlphaExpiryPill` | the app | app-global tasks and a provider problem (fed by the web via the `llm-failure` bridge message) |
| **Mac toast** | `ToastView.swift`: `ToastStore` + `ToastOverlay` + `ToastSurface`, one store per window (R90, `tests/test_desktop_toast_scope.py`), VoiceOver announcement | the app | 4 call sites (below) |
| **Mac notification banner** | `RunBannerCoordinator.swift`, `RunBanner.swift` (`UNUserNotificationCenter`) | the system | **one event**: an analysis ended while the researcher was not looking (built 6 Nov 2026) |
| **CLI lines** | `bristlenose/pipeline.py` (`_print_stage`, `cli_prefix`), `bristlenose/timing.py` | the terminal | stage progress with the five-kind glyphs. Not a toast and not on the table: English by design |
| **Message kinds** | `bristlenose/ui_kinds.py` (source), `frontend/src/utils/messageKind.ts`, `desktop/.../MessageKind.swift` | all | five kinds and five glyphs, the whole vocabulary |

What is verified from source, not inferred:

- **The system notification centre carries exactly one event on the Mac.** The only `UNUserNotificationCenter` use is `RunBannerCoordinator.swift`; it posts only when the researcher is not looking (`attention().isLooking`), never for a run the researcher stopped, and carries only the project id in `userInfo`. There is no notification for a provider problem, a failed export or anything from the web layer. Alerts on the Mac are otherwise pills, sheets and `NSAlert`s.
- **The Mac's toast surface is alive, with 4 call sites, not "none" and not "~8".** `ContentView.swift:2657` and `:2878` (a drag-import copy failed: `copyToastText`), `ContentView.swift:1263` and `AlphaExpiryFlow.swift:58` (`FeedbackSheet` hands its "sent" message back through `onToast`; suppressed when `onSent` is wired, `FeedbackSheet.swift:417`). [`design-pipeline-diagnostic-popover.md`](design-pipeline-diagnostic-popover.md) says both things in different places ("no toasts left on the Mac" in an anti-pattern bullet, "~8 call sites" in its truing banner). The code says 4.
- **The Mac toast has no `kind` and no live action.** `ToastStore.show(_ message:, duration:)` is the whole API. The popover doc's surface table (`ToastStore.show(_, kind:)`, "leading SF Symbol") describes something that was never built. `ToastSurface`'s `action` parameter has no live caller (its own header says so).
- **The web view's toasts are the last toasts the Mac user sees on a web-origin event.** Nothing in `BridgeHandler.swift` shows a toast, alert or banner on the web's behalf. The bridge's messages are state mirrors (`quote-action-state`, `export-counts`, `llm-failure`, `project-action`, …), never "tell the user".

## 2. Inventory: every `toast(` call site

Counted with `rg 'toast\(' frontend/src` minus tests and `toast.ts`: **27 call expressions in 7 files** (a 28th hit, `api.ts:301`, is a comment). Eleven are in `exportActions.ts`, eight in `AppLayout.tsx`. Only 3 pass a `kind`. Durations: the default 2000 ms at 14 sites, 4000 at 4, 5000 at 1, 6000 at 8: chosen per caller, with no rule.

**Event kinds** (the classification this doc uses):

- **C — confirmation.** The user did it and can see it. Telling them adds nothing except, sometimes, a count.
- **N — no-op explanation.** The action did nothing; the toast says why.
- **F — failure of a user action.** The user needs to know it did not happen.
- **S — a write that did not land.** The background save failed; the page is otherwise silent about it.
- **R — refusal with a kind.** The server said no for a named reason.
- **J — a notice about a started job** that the job's own chip could carry.

| # | Site | Message (locale key) | ms | kind | Event | In the Mac app today |
|---|---|---|---|---|---|---|
| 1 | `AppLayout.tsx:637` | `toolbar.noQuotesSelected` | 2000 | — | N | Reachable only from the native menu (`copyAsCSV` bridge action). The menu item's enabled state is already mirrored (`quote-action-state`), so a correct disable makes this unreachable. **Verify.** |
| 2 | `AppLayout.tsx:643` | `toolbar.csvCopied` (count) | 2000 | — | C | Native menu action; the menu has no control to morph |
| 3 | `AppLayout.tsx:644` | `toolbar.csvFailed` | 2000 | — | F | as above |
| 4 | `AppLayout.tsx:706` | `export.screens.copied` (count) | 6000 | — | C | **A round trip:** web asks native to write the pasteboard (`screens-pasteboard-write`), native answers `menuAction("screensCopied")` (`BridgeHandler.swift:1621`), and the *web* draws the word. A native action's confirmation drawn by the page |
| 5 | `AppLayout.tsx:710` | `export.screens.copyFailed` | 6000 | — | F | same round trip, failure leg |
| 6–8 | `AppLayout.tsx:876, 882, 887` | `export.screens.copyFailed` ×3 | 6000 | — | F | three branches of one failure (newer export replaced it; no files; read failed). Same sentence, three sites |
| 9 | `exportActions.ts:97` | `export.noQuotesMatch` | 2000 | — | N | |
| 10 | `exportActions.ts:104` | `export.quotesCopied` (count) | 2000 | — | C | also calls `announce(msg)` the line after, which `toast()` has already done |
| 11 | `exportActions.ts:109` | `export.exportFailed` | 2000 | — | F | |
| 12 | `exportActions.ts:133` | `export.noQuotesMatch` | 2000 | — | N | |
| 13 | `exportActions.ts:165` | `export.clips.noClips` | 2000 | — | N | |
| 14 | `exportActions.ts:183` | PII warning · burn unavailable (joined) | 6000 | — | J | a warning about what the export contains, shown for 6 s, then gone |
| 15–17 | `exportActions.ts:188–190` | `export.clips.ffmpegMissing` / `.inProgress` / `.failed` | 2000 | — | F | |
| 18 | `exportActions.ts:203` | `export.screens.none` | 2000 | — | N | |
| 19 | `exportActions.ts:217` | `export.screens.inProgress` / `.failed` | 2000 | — | F | |
| 20 | `speakerPicking.ts:173` | `sessions.picker.nameTaken` | 5000 | — | N | Fires from the web picker only. The Mac draws its own picker (`__BRISTLENOSE_NATIVE_PERSON_PICKER__`), so in the app this is unreachable from the picker. **Verify** the other caller, `SessionsTable.tsx:440` |
| 21 | `revealExport.ts:67` | `export.revealFailed` | 6000 | — | F | "a reveal the native side refuses is not seen here" (its own comment) |
| 22 | `api.ts:326` | `sync.pageStale` | 6000 | — | S | a serve restart left the tab with a dead token |
| 23 | `api.ts:338` | `sync.saveFailed` / `.saveRefused` / `.runInProgress` / `.quoteGone` | 4000 | — | S | also reached from `CodebookV2.tsx:420` through `toastSaveFailed` |
| 24–26 | `CodebookV2.tsx:414, 426, 431` | `autocodeRefusal(...)` / `autocodeFailure(...)` | 4000 | **error / warning / info** | R | the only call sites that pass a `kind` (so the only ones that draw a glyph) |
| 27 | `FeedbackModal.tsx:150` | the feedback sent / failed message | 2000 | — | C | Fires from the **web** modal only. In the app the footer's "Send feedback" posts `open-feedback` and the native sheet answers (and, if `onSent` is not wired, native `toast.show`). A browser-only toast already, by an existing fork |

Counts by event kind, per call site: **C 4** (#2, 4, 10, 27), **N 6** (#1, 9, 12, 13, 18, 20), **F 11** (#3, 5, 6–8, 11, 15–17, 19, 21), **S 2** (#22, 23), **R 3** (#24–26), **J 1** (#14). 4 + 6 + 11 + 2 + 3 + 1 = 27. The count of call expressions is exact; the kind of a few (a 'no files' message could be N or F) is a reading.

Two defects the inventory turns up, both small:

1. **A failure can be erased by a confirmation.** `toast()` is "one at a time, new calls replace the current" (`toast.ts`). A `csvCopied` fired 1.5 s after a failed save replaces the failed save's message. The save-failure site's own comment relies on the replace rule to collapse a burst; it never considers a different message replacing it.
2. **Failures look like confirmations.** 11 of the 27 sites are failures and 24 pass no kind, so "Export failed" renders in the same plain inverted capsule as "Copied". The glyph vocabulary exists (`KIND_GLYPH`) and 3 sites use it.

## 2a. Why toasts became the answer (from git, 9 Nov 2026)

Read from the commit bodies of the first commit that added each message (`git log -S<key>`), not from memory. Twelve commit bodies were read in full; the feedback toast and the §J8.11 reasoning behind the taken-name refusal were **not** (their messages say little, and the picker design doc was not opened).

**The origin is a legitimate one.** The first toast is `showToast()` in `theme/js/csv-export.js`, v0.2.0, 30 Jan 2026: the feedback for *Copy as CSV* in a static report with no server ("No favourites to export", "N favourites copied as CSV", "Could not copy to clipboard", 2 s). A clipboard write has no subject on screen and no other voice, which is rule 2 of §3b. The class is still called `.clipboard-toast`. When the SPA arrived, `toast.ts` was written as the "drop-in replacement for the vanilla showToast()" (its own header).

**Then it was the cheapest seam, and each new failure reused it.** `toast(message)` is one import, callable from `api.ts`, a bridge handler or a util, with no component tree and no state to design. The pattern across the commits:

| Cluster | When | Why it became a toast, in the commit's own words |
|---|---|---|
| **Copy and export confirmations** (#2, 3, 9–12) | Jan–Mar 2026 | Inherited from the vanilla CSV copy. Mar 24 wired the strings into i18next, Mar 26 added the export dropdown with the same toasts. On 22 Jun, `exportActions.ts` was centralised so the SPA dropdown and the **macOS native menu "invoke identical logic"** (`9dbb3884c`, "native bridge parity"). That is why toasts appear in the Mac app at all: native menu commands are dispatched into the page, and the page draws the word |
| **Clip and screens start failures** (#13, 15–19) | 27 Mar, 17 Oct | The clip export first shipped with an "async progress toast" (`85cb1f4cf`), which became the activity chip; the toasts that stayed are the refusals at the start, a server status mapped straight to a message (`422` → ffmpeg missing, `409` → already running, by `msg.includes("422")`). Screens (`ab7696ceb`) copied the shape |
| **A background save failed** (#22, 23) | 25 Jul, 14 and 22 and 24 Oct | `b19c75add`: "A failed sync is otherwise invisible until reload silently reverts the user's change." One generic toast wired once in `firePut` "so every view-toggle consumer … is covered uniformly", and "an outage burst collapses to a single message". The motive was **silent-failure hunting**, and there is no per-item failure state on a quote, so the only global voice was a toast. Later commits made it say *why* (`aaf60677e`: it blamed the connection when the server was refusing a write during a run), name a re-run-removed quote (`4b3a1ef32`, RE#20 #21) and say a tab outlived its serve (`c17079640`, R87) |
| **Copy Screens round trip** (#4–8) | 17 Oct | `0fc4193f1`, from a three-way review: "Copy Screens said 'Copied' before anything was on the clipboard … and a refused copy was silent." The fix was honest copies: "the shell says copied or not". The only way for the shell's verdict to reach the researcher was back through the page, which draws toasts |
| **Show in folder failed** (#21) | 22 Oct | `f15a263d4` (RE#20 #44): the failure "caught into the console only — the chip had already closed, so nothing happened as far as the researcher could see". Reused the toast "as a failed screens copy already does". Precedent, not design |
| **Taken name refused** (#20) | 6 Oct | The people picker (§J8): pick, someone new and rename are "three acts, never guessed from a name"; a clash is "refused aloud". The commit says nothing of why aloud meant a toast and not inline validation (not investigated) |
| **AutoCode refusals** (#24–26) | 30 Aug | `ae050e567`: the panel was showing the server's `detail` string, which quoted framework ids and told the reader to run a shell command. Refusals got a name on the wire and a kind, and the code comment says why a toast: "A refusal is transient and about the click" |

**What the history says, as reasons:**

1. **The first toast was right, and the rest inherited the tool, not the reasoning.** Nobody decided "failures are toasts"; each failure was found silent and given the nearest working voice.
2. **A reliability phase turned silence into toasts.** `b19c75add`, `0fc4193f1`, `f15a263d4`, `aaf60677e`, `c17079640` are all "X was silent, now it says so" (R86, R87, RE#20). "A failed thing must be visible" is a standing rule here, and with no failure state on the data, a toast was the fastest way to obey it.
3. **There was no in-context vocabulary to reach for.** The ghost → working → done states were decided only on 9 Nov 2026 (`design-motion.md` §4.7.2). Before that, "something is happening or went wrong" outside a control had two forms: a toast or a chip.
4. **Native menu commands run in the page**, so the Mac app inherited the web's toasts for actions that, natively, would be silent.
5. **The Mac deliberately went the other way.** `5598bd39` (19 Aug 2026, "five toasts and a fuse removed") replaced native toasts with the drag's own refusal, a persistent "+3 unanalysed" row, a dimmed menu item and the poof effect, because "a post-hoc message [was] the only grammar available". The web side never got the same treatment, and the 27 Jul routing doc parked it as "a yet-unwritten sibling": this doc.
6. **Cost to add was near zero.** One import, one locale key. `sync.*` "had never had locale keys" until Oct (`aaf60677e`), and no one had to design anything to ship it.

## 3. The decision matrix

Four deployments. **Browser** is `bristlenose serve` opened in any browser. **Embedded** is the SPA in the Mac app's web view (`isEmbedded()`). **Export** is the offline HTML (`isExportMode()`). **CLI** is the terminal. "Today" is what ships; "Proposed" is this doc's recommendation. Cells marked **[owner]** are decisions that are the owner's (§7), with a default.

| Event | Browser | Embedded (Mac app) | Export | CLI |
|---|---|---|---|---|
| **C — confirmation** ("47 quotes copied") | Today: toast. Proposed: keep, short (2 s), count only if it carries information. A browser has no clipboard feedback of its own | Today: toast inside the web view. Proposed **[owner]**: no visual toast; VoiceOver still hears it through `announce()`. Finder, Notes and Mail say nothing on ⌘C. If the count matters, it is already on `export-counts` and the menu | Cannot fire: the export controls and keys are gated (§5) | n/a |
| **N — no-op** ("No quotes selected") | Toast, or better the control disabled with a reason | The menu item or control is disabled instead (`quote-action-state` exists for exactly this). Where the message is still reachable, keep the toast until each is proven unreachable | n/a | n/a |
| **F — failure of a user action** | Toast with the `error` glyph; **not** replaced by a later success (§8 phase 2) | **[owner]** Today: web toast in the web view. Interim proposal: keep, with the glyph and a longer hold. Principled end state: a native alert or the row/pill, which needs a new bridge message (`notify`) the app does not have. See §7 | Cannot fire | Existing `✗` lines |
| **S — a write that did not land** | Toast, collapsing a burst to one message. This is the one the browser cannot do without | Keep as a web toast. The page is the only party that knows; there is no native state to mirror. `sync.pageStale` should be rare (the app reloads on a serve change) | Cannot fire: writes are gated (`api.ts:257`) | n/a |
| **R — refusal with a kind** ("Add an API key in Settings first.") | Toast with its kind. Gains an **action** ("Open Settings" is the obvious one) | Same toast, with the action posting `open-settings` (a bridge message that already exists, `BridgeHandler.swift:1899`). Not a new surface; the toast gets the button it was missing | Cannot fire | n/a |
| **J — notice about a started job** (PII warning, burn unavailable) | Move into the job's chip: the chip already has a body and an action link | Same, in the docked chip | Cannot fire | n/a |
| **Progress / result of a background job** | Activity chip (floating) | Activity chip, **docked** under `isEmbedded()` (Strategy 1 in the routing doc; no Swift) | Cannot fire | Terminal progress lines |
| **A run ended while away** | n/a (a browser serve does not run the pipeline) | Native notification banner, only if the researcher is not looking (shipped) | n/a | The final summary line |
| **A run ended while looking** | n/a | Row subtitle and ring change. No toast, no banner | n/a | n/a |
| **A provider problem** | The chip's error text | Chip text **and** the native pill (`llm-failure` bridge → `ProviderProblemModel`). Two surfaces for one fact; the pill is the durable one | n/a | CLI error line |

### Where the SPA should stop drawing a toast when embedded

In order of confidence:

1. **The Copy Screens round trip (rows 4, 5).** The page asks native to write the pasteboard; native already knows whether it worked (`BridgeHandler.swift:1621–1640`) and then tells the page to say so. A native success needs no word (drop it) and a native failure should be drawn by the party that knew. Today the page draws both. Either route: the page stops (success) / native uses the existing `ToastStore` or an alert (failure).
2. **Confirmations of the obvious (rows 2, 10, 27).** Rows 2 and 10 are copies from a native menu command with no control at the site of action to morph. Row 27: the Mac already has a native sheet for feedback, so it is already forked by deployment.
3. **No-op explanations (rows 1, 9, 12, 13, 18, 20)** that are unreachable once the native menu item or control is correctly disabled. Needs a per-site check, not a blanket rule.
4. **The job notice (row 14)** belongs in the chip in every deployment.

What stays a toast in the Mac app: the failures and unseen states (F, S, R). That is the "keep-list" from the 27 Jul lean, and it is most of the volume (16 of 27). The honest position is that the Mac app cannot stop drawing *failure* toasts until the app has a way to show a web-origin failure natively (§7 decision 2).

### A duplicate that fires on two surfaces

No call site fires both a web toast and a native notification: the notification centre carries one event (the run end) and the web layer has no path to it. The real duplicates are one level down:

- **A provider problem** is told twice: the chip's error text and the native pill. This is intentional (different lifetimes) and the pill is fed by one bridge message, so it is not drift.
- **Feedback** is already forked correctly: native sheet and native toast in the app, web modal and web toast in a browser.
- **An announcement doubled:** `exportActions.ts:104` calls `toast()` (which calls `announce()`) and then `announce()` again with the same text. Harmless (the live region coalesces) and worth deleting.

## 3a. One system, not a mapping (owner, 9 Nov 2026)

The matrix above is not a 1:1 translation of each toast to a native notification. The researcher's experience is the **sum** of the web layer and whatever the host adds, and the two are designed together. Three consequences:

1. **The web layer is the floor, and it must be complete on its own.** Bristlenose also runs as the CLI plus `bristlenose serve` in a browser on macOS (Homebrew, pipx), on Linux (pip, Snap, Copr, Homebrew), and the CLI alone on Windows. There the web toast, the chip and the terminal lines are *all* the researcher gets: no sidebar ring, no pill, no banner. So every message a browser user needs must be a web message, and nothing may be removed from the web layer on the strength of a native surface that a Linux user does not have.
2. **The Mac app subtracts or adds only through the existing seam** (`isEmbedded()` and the bridge), never by editing the web layer for everyone. Suppressing a web message in the app is allowed **only when a named native surface carries the same information**. Phase 6 therefore needs a *pairing table* before it ships: each suppressed message, and what in the Mac app now tells the researcher (a disabled menu item, the row subtitle, the pill, the banner, or "nothing, because they did it and can see it"). A message with no named pairing stays.
3. **Attention has an analogue everywhere, and the rule is the same.** On the Mac it is `ResearcherAttention.isLooking`. In a browser it is the page's own state (`document.visibilityState`, `document.hasFocus()`); in a terminal the researcher is looking at it or not and the run's summary line is waiting when they return. A host that can raise a notification does so only when the researcher is not looking; a host that cannot loses nothing it had.

What each deployment has, for the "run ended while away" case (the only event with a banner today):

| Deployment | When looking | When away |
|---|---|---|
| Mac app | row subtitle and ring | system banner (shipped) |
| macOS or Linux CLI | terminal progress and the final summary line | the summary line, waiting in the terminal |
| `serve` in a browser | the report updates in place | nothing. A browser notification (the Notifications API) could do this, but it asks the user for permission and is a **new feature** with its own consent and wording (decision 9). Not recommended before launch |
| Windows CLI | terminal lines | the summary line |

The CLI's own terminal lines already share the five-kind glyph vocabulary with the web and the Mac (`ui_kinds.py`, `messageKind.ts`, `MessageKind.swift`; pinned by tests), and that shared vocabulary is the right amount of system: one set of kinds, each deployment drawing them natively. This doc does **not** propose a new shared event contract across Python, TypeScript and Swift (the Seams rule would then demand a fixture and parity tests). The `tone` argument in §6 is a web-side classification only; promote it to a shared contract if a third surface ever needs to read it.

## 3b. When a toast is the right thing

A toast is the right surface only when **every** one of these holds. Fail any one and the message belongs somewhere else (the right-hand column).

| # | Rule | If it fails, put it… |
|---|---|---|
| 1 | **It is a transient fact, not a state.** Test: if the researcher looked again in a minute, should it still be true? "Copied" is a fact. "Thumbnails still loading", "this save failed and is still unsaved", "this control can't be used" are states | **on the thing**: ghost, shimmer or marker on the data (§4.7.2), a disabled control with its reason, an item in the row subtitle |
| 2 | **There is no subject on screen to carry it.** The event happened off-screen or in the background (a clipboard write, a background save, a refused request from a closed menu) | at the subject, if there is one: a button morphing to a tick, inline validation in the field, the card that failed |
| 3 | **It is not progress.** Progress is *designed on the real data*: a thumbnail's ghost becomes working becomes the picture. A job with no on-screen subject (a clip export writing to disk) gets the chip; in the Mac app the row's ring and status line | the data, the chip, the ring |
| 4 | **It tells the user something they do not already know from having done the action.** "Copied" after pressing Copy fails; "Copied, but 2 clips had no video" passes | nowhere: delete it. Keep a count only if the count is the information |
| 5 | **No native or inline home is cheaper in this deployment.** In the Mac app a disabled menu item beats "No quotes selected"; in a browser a disabled button with a reason does too | the control, or the host (§3, §3a) |
| 6 | **Missing it is cheap, or it leaves a trace.** A low-stakes fact can fade after seconds. A failure that costs the researcher their work must not live *only* in a toast that auto-dismisses; it needs a longer hold and, where the data exists, a mark on the thing that failed | the thing, plus a held toast |
| 7 | **It asks for no decision**, except one single action that is a transient *control* (Undo, Open Settings). Anything needing a choice or a read is a sheet or an alert | a sheet or alert (`Dialog`, the Mac's `NSAlert`) |
| 8 | **One plain line, one of the five kinds, no narration.** No "loading…", no "please wait", no "run" (computer language); expected outcomes get plain words and no retry prompt | rewrite, or delete |

**What passes, in the 27 sites:** the background save failures (#22, #23: no subject on screen, a lost edit otherwise); failures of an off-screen write or request (#3, 5–8, 11, 15–17, 19, 21: a clipboard or file operation from a menu that has closed); and the three refusals, which should gain their action (#24–26). That is about **16** of 27, and most of them are failures, which is why the glyph and the hold (phases 2 and 3) matter more than the stacking.

**What fails, and where it goes:** the 4 confirmations (#2, 4, 10, 27: rule 4, and #4 also rule 5 because native knows), the 6 no-ops (rule 5: the disabled control, or inline validation for the taken name, #20), and the 1 job notice (#14: rule 3, it describes what the export will contain, so it belongs in the export dialog before it starts or in the job's own chip). That is about **11** of 27 as *triage candidates*, each a per-site owner call, none a blanket deletion.

**What no toast in the codebase does today:** none of the 27 narrates loading. The narration lives in the activity chip, and whether the chip's jobs should instead show on their subject is the next question (decision 10).

## 4. The Mac's own toast

`ToastView.swift` is a live surface with four callers and no `kind`. The Mac's rule is "don't reach for a toast" (`design-pipeline-diagnostic-popover.md` §Anti-patterns, 19 Aug 2026; rationale `design-analysis-lifecycle.md` §4.2). Two of the four callers (the drag-import copy failures) are failures with no better home found yet; the other two (feedback sent) are suppressed in the alpha-expiry flow. This doc does not recommend deleting `ToastView` or adding to it. It recommends **deciding after** §3's round-trip and failure decisions (§7), because if failures from the web are to be drawn natively, `ToastSurface` with its unused `action` parameter is the nearest shipped sibling, and if not it can go.

## 5. The export

`isExportMode()` is true when the embedded data is present. The offline report cannot write or ask a server, so by construction the failure and save classes cannot fire:

- `api.ts` returns early (`:257`) for writes; reads resolve from the embedded JSON (`:117`, `:128`).
- `ExportDropdown` returns `null` (`:224`); `useKeyboardShortcuts` returns early at four sites (`:195`, `:213`, `:246`, `:255`).
- The activity store skips (`ActivityStore.ts` imports `isExportMode`).

So the export needs the toast **component** (it ships in the single-file build whether used or not) but no toast **behaviour**. This is argued from the gates, not proven by a test. If the web toast grows, the cheapest guard is a test that mounts the export entry, sends every keyboard shortcut and asserts no `bn-toast` appears. Not written.

## 6. What the web toast becomes

### Borrow or build

Recommendation: **build in-house, copy Sonner's behaviours, add no dependency.** Reasons from this repo:

- **One speech path.** `toast()` already calls `announce()`, whose live region is portalled outside `#bn-app-root` so `useInert` does not silence it (`AnnounceRegion.tsx`). Sonner mounts its own `aria-live` region inside its `<Toaster/>`; adopting it means either two announcements for every toast or removing ours and re-proving the dialog case. This is the trap, and it is ours.
- **A detached root.** `toast()` is imperative, callable from `api.ts` and from a bridge handler, rendering into its own `createRoot` container (`toast.ts`). Sonner's model is a `<Toaster/>` in the tree plus a module-level `toast()`; it can work, but the test file's teardown contract (`_resetToast`, written because the detached root escapes testing-library) would need re-deriving.
- **Our look.** The capsule, the `.toast-glyph--{kind}` colours and `--bn-toast-z` (above a dialog, by design) are tokens. Sonner's default styling would be switched off to use ours, which leaves its stacking and gestures as the part worth having.
- **The single-file export** carries every dependency. Sonner's size is **not measured here**; if the owner wants the number, measure in a scratch directory, not in `frontend/` (`npm run size` / `scripts/check-bundle-budget.py` is the budget gate).
- The behaviours worth having are about 100 lines: a short queue, pause on hover and focus, a kind-aware duration, and an optional action.

### The seam

All 27 call sites go through `toast(message, duration?, kind?)`. **Keep that signature.** Additions are an optional fourth argument and defaults, so no call site must change:

```ts
toast(message, duration?, kind?, options?: { action?: { label: string; run: () => void }; id?: string })
```

- `id` replaces a message of the same id (what the save-failure site hand-rolls today).
- `action` is the Undo or "Open Settings" button; the Mac toast's unused `action` parameter is the nearest shipped sibling.
- Default duration by kind when the caller passes none: success/info short, warning/error longer. The 14 sites that pass nothing get a rule; the 13 that pass a number keep it until each is migrated.

### Behaviours to copy, and the ones not to

| Behaviour (Sonner) | Take it? | Why |
|---|---|---|
| Stack up to ~3 rather than replace | Yes | Fixes the "failure erased by a confirmation" defect |
| Pause on hover / focus | Yes | A 2 s toast cannot be read by a slower reader. Also helps keyboard users |
| Action button | Yes | Gives refusals their "Open Settings" |
| Priority: an error is not replaced by a success within its window | Yes | The smallest change, and a reliability fix, not polish |
| Promise toast (loading → success/error) | **No** | The activity chip is already the progress surface; a second one is the duplication this doc exists to remove |
| Swipe to dismiss | **No** | A desktop tool; the chip and toast are dismissed by their own control |
| Expand-on-hover stack animation | **No** | Visual delight; not asked, and the motion brief wants "causal, proportional, interruptible" (`design-motion.md`) |
| Auto-dismiss a **failure** | Careful | A failed save the researcher did not see is a lost edit. Longer hold or until dismissed; **[owner]** because "not needy UX" and "failed runs must be visible" pull in different directions |

Accessibility stays as is: `announce()` remains the single speech path, and a failure uses the same polite region (no `role="alert"` interruption) unless the owner decides otherwise.

### The embedded fork lives at the seam, not at 27 sites

The triage in §3 says some confirmations should draw nothing in the app. Do it once: classify at the call (a short `tone`, e.g. `"confirm"`) and let `toast()` skip the *visual* when `isEmbedded()` while still calling `announce()`. A suppressed message needs **no new strings**, so it costs none of the 21-locale changes that adding or rewording a key does. The per-site decision (which of the C and N rows to mark) is the owner's, not an engineer's.

## 7. Open decisions (the owner's)

1. **Embedded confirmations: delete, or keep?** "47 quotes copied" from a menu command: a native app says nothing on ⌘C, and the agreed filter is "does this tell the user something they do not already know?". If the count is wanted it belongs at the action (the menu). Default proposed: suppress the visual in the app, keep `announce()`.
2. **Embedded failures: web toast, or native?** Failures are 11 of 27 sites (16 with the save failures and refusals). Keeping them as web toasts in the web view is the interim and ships today. The principled answer needs a new web→native message (`notify`) and a native presenter (a sheet, an alert, or the existing `ToastSurface`); the web-origin failure then has a native home and the web toast is browser-only. This is new plumbing and **new UX**, so it sits behind the R114 gate (mockup, review, explicit approval).
3. **Sonner or in-house?** Recommendation is in-house (§6). Decide whether a measured bundle-size comparison is worth doing before closing it.
4. **Should an error toast outlast 2 s, and by how much?** (§6). Interacts with "not needy UX".
5. **Chip: dock it, or route it to native?** Strategy 1 (dock, no Swift) vs Strategy 2 (native slots), already open in the routing doc, where Strategy 1 is recommended for alpha. Unchanged by this doc.
6. **The Copy Screens round trip (rows 4, 5):** native success draws nothing (drop the word), native failure drawn by native. Needs a yes before the page stops saying it.
7. **`ToastView.swift`: keep, extend or retire?** Decide after 2 and 6.
10. **Which chip jobs have an on-screen subject, and should show *on it*?** A Screens export has the Screens lens's tiles; AutoCode has quotes and tags that are about to appear; a clip export writes to disk and has nothing on screen. Under the third principle the first two could show ghost → working → done where the result will appear, with the chip kept only for the subjectless job. That is the §4.7.2 vocabulary applied to a new place, it reopens the "status lives where its subject lives" question in the routing doc, and it is **new UX**, so it needs a mockup before anyone builds it. No recommendation beyond asking per job. Until §4.7.2 itself is built (a mockup, with the tapestry strip's working sweep built on 9 Nov but not yet judged live; the rest is not code), this stays a direction, not a phase.
9. **A browser or Linux "while away" notification?** `serve` in a browser could raise a Notifications-API notification when the tab is hidden and a run or job ends, by the same attention rule. It needs the user's permission, a consent line and wording in 21 locales, and it is a new capability with no native sibling to copy on the web side. Default: no, not before launch; revisit if browser and Linux researchers report missing a finished run. A Linux desktop notification from the CLI (a `notify-send`-style call) is a separate idea I have **not** checked for sandboxing under Snap, so it is not proposed.
8. **Should a web-origin job that finishes while the researcher is away raise the banner?** The attention rule (header) says a notification belongs exactly then, and today only a pipeline run does. An AutoCode, catch-up or clip/screens export that finishes (or fails) while Bristlenose is behind other windows leaves its result on a chip nobody is looking at, and a web toast that fires then is simply missed. Reusing the run banner's gate would need the page to tell the shell a job ended (a `job-ended` bridge message, shaped like `llm-failure`) and the coordinator to post for it. It is a new notification, so it needs the R114 gate and the "beta means almost no new features" exemption the run banner was given by name. Not in the plan below until decided.

## 8. Phased plan

Same shape as [`design-settings-ui.md`](design-settings-ui.md): each phase ships alone, with a status and anchors. Phases marked **beta-safe** are small, behaviour-preserving or fix a real defect; the rest wait for after launch (first App Store submission 24 Nov 2026, per the project's lifecycle) or for owner sign-off. Nothing here is started.

| # | Phase | Status | Beta | Size | Anchors |
|---|---|---|---|---|---|
| **0** | **True the docs.** Correct `design-pipeline-diagnostic-popover.md`: "~8 call sites" is 4; `ToastStore.show(_, kind:)` and `.toast--{kind}` do not exist; `AutoCodeToast.tsx` (named in its file map) was deleted. Point `design-embedded-activity-routing.md` §"Scope boundary" at this doc | pending | **yes** | doc only | `ToastView.swift`, `Toast.tsx`, `ActivityChipStack.tsx` header |
| **1** | **Delete dead CSS.** `theme/atoms/autocode-toast.css` (27 hard-coded colours) is imported by nothing: it is in neither `theme/index.css`'s atoms list nor `theme_assets.py`'s CSS list, no TSX or JS uses its classes, and the only reference is `scripts/audit-css.py`. Confirm with `scripts/audit-css.py` and the theme tests, then remove. (The chip's own `activity-chip.css` has 31 literals and is live; tokenising it is a separate, visual change) | pending | **yes** | tiny | `atoms/autocode-toast.css`, `scripts/audit-css.py`, `tests/test_theme_token_resolution.py` |
| **2** | **A failure is not erased by a confirmation**, and failures carry the `error` glyph. Priority rule in `toast()` (an error holds its window against a lower kind); pass `kind: "error"` at the 11 F sites; delete the doubled `announce` at `exportActions.ts:104` | pending | **yes** | small | `utils/toast.ts`, `Toast.tsx`, `Toast.test.tsx`, `exportActions.ts` |
| **3** | **Durations by kind.** A default by kind when the caller passes none; migrate the 13 hard-coded numbers one by one | pending | **yes** | small | `utils/toast.ts`, `messageKind.ts` |
| **4** | **Stack, pause on hover and focus, `id` replace.** Same `toast()` signature; `_resetToast` and the detached-root teardown keep their contract | pending | after launch | medium | `utils/toast.ts`, `Toast.tsx`, `atoms/toast.css`, `Toast.test.tsx` |
| **5** | **Action button**, first use: "Open Settings" on the `no_api_key`, `provider_ambiguous` and `provider_local` refusals, via the existing `open-settings` bridge message | pending | after launch | small | `CodebookV2.tsx:414`, `autocodeRefusal.ts`, `BridgeHandler.swift:1899` |
| **6** | **Embedded fork at the seam** (`tone: "confirm"` suppresses the visual under `isEmbedded()`, keeps `announce()`), applied to the sites the owner picks | pending, owner-gated (decision 1) | after launch | small | `utils/toast.ts`, `utils/embedded.ts` |
| **7** | **Move the job notice into the chip** (row 14) | pending | after launch | small | `exportActions.ts:183`, `ActivityChip.tsx` |
| **8** | **Dock the activity chip when embedded** (Strategy 1) | pending (owned by the routing doc) | after launch | small | `design-embedded-activity-routing.md` |
| **9** | **A native home for web-origin failures** (`notify` bridge message plus a presenter) | pending, owner-gated (decision 2), R114 gate | later | medium | `shims/bridge.ts`, `BridgeHandler.swift`, `ToastView.swift` |
| **10** | **Resolve `ToastView.swift`** (keep, extend or retire) after 6 and 9 | pending (decision 7) | later | small | `ToastView.swift`, `tests/test_desktop_toast_scope.py` |

### Verification each phase needs

- Phases 1–3: `.venv/bin/python -m pytest tests/`, `.venv/bin/ruff check .`, `cd frontend && npm test` and `npm run lint`. Phase 2 needs a vitest case that fires a failure and then a confirmation and asserts the failure is still shown (and that it fails without the change).
- Phases 4–7 add a human check no test covers: a browser serve and the Mac app, with a deliberate failure (stop the serve and edit a quote) while triggering a confirmation. QA command: `.venv/bin/bristlenose serve --dev <a project folder>`, then `http://localhost:8484/report/`. The Mac app needs its own build; nothing here changes Swift until phase 9.
- Anything that suppresses a visible message needs the R114 gate: a mockup, review, and explicit approval before it is built.

### What this plan deliberately leaves alone

The design system (tokens, atoms, the glyph vocabulary), the Dialog, the activity chip's polling and persistence, the run banner, the CLI's lines, and every native indicator on the sidebar and toolbar. It adds no dependency, no new glyph, no new string for the suppressed messages, and no new UX.
