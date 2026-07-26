---
status: pending
last-trued: 2026-07-26
trued-against: HEAD@main on 2026-07-26
---

# Embedded activity routing — web-origin jobs onto native surfaces

> **Draft, unbuilt.** Design for what happens to web-origin background activity
> (AutoCode, catch-up re-apply, clip export) when the SPA runs embedded in the
> macOS WKWebView. Today it renders as a floating web "activity chip" inside the
> web view. This doc weighs two strategies — **dock the existing web chip** vs
> **push status to native surfaces** — and lands on a recommendation.
> Sibling to [`design-sidebar-activity-indicators.md`](design-sidebar-activity-indicators.md),
> which owns the *native-origin* run/copy indicators already on the sidebar row.
>
> **Reviewed 2026-07-26** (design-doc-review + code-review agents). Their findings
> reshaped the recommendation — see the changelog note at the end.

## Problem

Bristlenose has **two unrelated plumbing systems** for background activity:

- **Native-origin** (pipeline run, drag-import copy): sidecar →
  `pipeline-events.jsonl` on disk → `EventLogReader` (file tail) →
  `PipelineRunner`/`PipelineLiveData` → the **native sidebar row**
  (`ProjectRowActivityIndicator` determinate ring + `SidebarShimmerText` status
  line). App-global native activity (Ollama download, out-of-credit, alpha-expiry)
  → a **native toolbar pill**.
- **Web-origin** (AutoCode, catch-up re-apply, clip export): started from inside
  the SPA, status polled by React over HTTP, rendered as the floating web
  **activity chip** (`ActivityChipStack`, `createPortal` to `document.body`) — which
  in the desktop app floats *inside* the WKWebView content.

Inside the app this reads as two visual languages in two places: a pipeline run
gets a first-class native sidebar indicator; an AutoCode run gets a web chip
floating over the content. **Native has zero awareness of web-origin activity
today** (no `case "activity"` in `BridgeHandler`, no observer in any `.swift`).

Organizing principle (from the sibling doc): **status lives where its subject
lives.** All three web-origin activities are *project* activities, so embedded
they arguably belong on the active project's sidebar — as a run does. Whether
that's worth the plumbing is the question this doc answers.

## The three web-origin activities (all project-scoped)

| Activity | Trigger | Poll | Poll key |
|---|---|---|---|
| **AutoCode** | ✦ button, `CodebookPanel` | `GET /api/projects/{pid}/autocode/{framework_id}/status` (2 s) | `frameworkId` |
| **Catch-up re-apply** | codebook re-enable, `CodebookPanel` | same autocode endpoint | `frameworkId` |
| **Clip export** | export dialog, `exportActions` | `GET /api/projects/{pid}/export/clips/status` (2 s) | *(none — per-project singleton)* |

`ActivityJobEntry` (`contexts/ActivityStore.ts`) today is
`{ type: "autocode" | "clips" | "catchup", frameworkId, frameworkTitle, total? }`
— **no `scope` field.** All three render through the same `ActivityChip`. Any
routing design that says "AutoCode and clips" and forgets **catch-up** silently
drops a third of the surface — it is the same chip today.

There is **no web-origin *global* activity.** The global bucket is filled entirely
by native-origin app tasks that are already toolbar pills. So the original "route
to a toolbar pill for global activity" branch has no web producer to feed it — it
is a forward-looking `scope: "global"` seam only.

## The core obstacle: native has no free slot during a run

The original instinct — "put the run on the ring, put web activity on the
subtitle status line" — **does not survive a concurrent run.** The native sidebar
row has exactly two activity slots and a *run owns both*:

- **Ring** (`ProjectRowActivityIndicator`) — reserved for `.running`/`.copying`.
- **Subtitle line** (`ProjectSubtitle.resolve` → `SidebarSubtitleText`) — a
  **single-winner precedence chain**; `.running` already owns it as the live stage
  ladder ("Transcribing · 7 of 8 · 2m left").

AutoCode is *not* guaranteed mutually exclusive with a run (incremental analysis
can be mid-run when you start AutoCode; clip export is fully independent). So in
exactly the concurrent case, **both native slots are the run's and web activity
has nowhere to render.** The "status line, not ring" resolution only works when no
run is live — the easy case.

This is the pivotal finding. It means **pushing to native surfaces is not a free
win** — it forces a real decision (queue web activity behind the run? compose a
second line? accept invisibility mid-run?) that the floating chip never had,
because the chip is its own surface.

## Two strategies

### Strategy 1 — Dock the web chip (recommended for alpha)

Keep the entire self-contained web chip — its polling, dismissal, action link,
multi-job summary/expand, completion, i18n label — and in embedded mode **change
only its placement**: dock it (non-floating, positioned to sit with the native
chrome, e.g. bottom-trailing above the status bar, respecting `--bn-toolbar-inset`)
instead of floating over content.

- **Sidesteps every native-side gap below:** no dismissal-owner problem, no
  cross-project-switch re-tracking, no glyph-ownership split, no
  subtitle-precedence collision. The chip already solves all of that.
- **Smallest change:** a CSS/position fork under `isEmbedded()`, no bridge
  message, no Swift, no Python.
- **Cost:** it's still a web surface — two visual languages persist, just tidier.
  It doesn't achieve "status lives where its subject lives"; it achieves "status
  is no longer floating in the wrong spot."
- **Honest framing:** the ~80% of the value (stop the chip floating awkwardly over
  native content) for ~10% of the effort.

### Strategy 2 — Push status to native surfaces (the "full native" end state)

Route web-origin activity into the native sidebar/toolbar. This is the
principled end state and the right target *if* the subtitle-collision decision
lands on "web activity gets a native slot." It reopens several plumbing problems
the chip had already solved (below). Best sequenced *after* alpha, and only once
the collision decision is made.

## The enabling refactor (needed for Strategy 2; optional for Strategy 1)

Today the poll loop is welded to the renderer: `ActivityChipStack.tsx` owns the
2 s `setInterval` (`:138`), `normaliseAutoCode` (`:68`), `pollFn` dispatch
(`:116`), terminal-job skip (`:141`), once-only `onComplete` via a `completeFired`
ref (`:151`), and `createPortal` (`:226`). Critically, `onComplete` fires real
side-effects — `codebook-changed` / `bn:tags-changed` that make new tags appear
(`AppLayout.tsx:598`).

To fork rendering you must hoist polling to a headless hook — and **mount it
unconditionally**, not inside either render fork, or the non-mounted mode loses
polling *and* those completion side-effects:

```
ActivityStore (+ scope)                     ┌─▶ (browser) ActivityChipStack (floating)
      │                                      │
useActivityJobs() ──▶ useActivityPolling()  ─┼─▶ (embedded, Strategy 1) ActivityChip (docked)
   mounted ONCE in AppShell, surface-agnostic│
   writes live status into the store         └─▶ (embedded, Strategy 2) useBridgeActivitySync
   (preserves terminal-skip, onComplete-once)      posts snapshots to native
```

Strategy 1 needs the hoist far less (the chip keeps its own loop); it's mainly a
Strategy-2 prerequisite. Add `scope` to `ActivityJobEntry` either way — cheap,
and the routing key.

## Strategy 2 transport options (web → native)

### Option A — Bridge push (web polls, native renders)

Web keeps its HTTP poll; embedded, `useBridgeActivitySync` posts
`{ type: "activity", jobs: [...] }` over the existing `navigation`
`WKScriptMessageHandler`. Native renders on the scoped surface.

- **Established idiom:** `postLensSubtitle`/`postExportCounts`/`postQuotesFilter`
  are all "web computes, native renders." Native never re-implements the poll.
- **Least code of Strategy 2:** one `BridgeMessage` variant, one `handleMessage`
  case. Python unchanged.
- **Lifecycle reality (corrected):** the earlier draft claimed "the sidecar
  respawns on project switch, so the job is lost regardless." Under the
  **warm-sidecar pool (A2)** that's wrong — the sidecar is *parked*, and the
  AutoCode/clip task keeps running server-side. What dies is the **client's**
  tracking: the WKWebView remounts (keyed on project id + port) and the
  module-level `ActivityStore` starts empty. So on switch-*back* to a project whose
  AutoCode is still running, Option A shows **nothing** while work silently
  continues — worse than "lost." Mitigation: **re-hydrate on mount** — the SPA
  queries a status/list endpoint on load and repopulates `ActivityStore`, so both
  switch-back and browser-refresh recover. That's a separate "activity
  persistence" concern (needs a list endpoint) worth pulling in if Strategy 2 ships.

### Option B — Native polls the sidecar HTTP directly

Native gets a `URLSession` poller against the status endpoints — **precedent
exists**: `MiroAPI` already calls `http://127.0.0.1:{port}/api/projects/{id}/…`
from native, reading `ServeManager.authToken` + port. Independent of the WKWebView
lifecycle (fixes the switch-back gap natively).

- **Cost:** duplicates poll + normalisation + i18n label in Swift (the
  `pipeline_view/cli.py` mirror-divergence trap). The DTO/poll must carry
  `frameworkId` (autocode/catchup poll by it; clips is a per-project singleton
  with no id) — an `id`-only contract can't reconstruct the autocode URL.

### Option C — Event-log / file (jsonl the way runs do)

Python emits a job-event stream; native tails it via `EventLogReader`. Most
consistent with runs, survives everything, heaviest (new Python schema + reader).
The right end state if these jobs ever go long-lived/cross-project (Phase 3's
unified "Background" model).

## Native-side gaps Strategy 2 must solve (the chip already had)

1. **Subtitle-precedence collision during a run** (the core obstacle above) —
   **decision required.** Options: queue web activity behind the run (surfaces when
   the run ends); a composed/second subtitle line; or accept mid-run invisibility.
2. **No dismissal owner.** Browser dismisses the completed chip via `onDismiss` →
   `removeJob`. Embedded with no chip, nothing calls `removeJob`; the job lingers
   and `useBridgeActivitySync` keeps posting it. **Fix:** the terminal snapshot
   auto-removes after posting a final "completed" frame (so native can show the
   action briefly, then clear), and the native action posts a `project-action`
   that also clears.
3. **Project attribution is cross-namespace — do *not* send `projectId`.** The SPA
   only knows the **server DB id** (`useProjectId()` → `"1"` by default); native
   rows key on `ProjectIndex` UUIDs. A web-sent id won't match. **Fix:** native
   attributes the activity to the **fronted** project (the one whose sidecar/WebView
   is active), exactly as it already does for the fronted run. Drop `scope.projectId`;
   keep `scope: "project" | "global"` for the seam.
4. **Glyph/label ownership.** Baking `✦` + a composed string into the web payload
   bypasses the native `MessageKind` glyph authority (`design-pipeline-diagnostic-popover.md`)
   and the native subtitle composer. **Fix:** send **structured fields** (type,
   status, count/total, fraction, a `messageKind` for failures) and let native
   compose the string + choose the glyph. AutoCode *can* fail (`error_message`), so
   the DTO needs a failure kind that maps to `MessageKind`.
5. **Correct native target file.** The shipped sidebar is the AppKit
   `ProjectSidebarOutline.swift` / `SidebarSubtitleText.swift` path; the SwiftUI
   `ProjectRow.swift` is being flag-deleted. Wire the status line into the AppKit
   cell, and note `SubtitleVariant` is an exhaustive `switch` (no `default`) — a new
   web-activity case forces edits at every match site (compile-time completeness,
   but more surface than "extend the shimmer line").

## Proposed `ActivityDTO` (Strategy 2)

```ts
// web → native, over the existing `navigation` handler
{ type: "activity",
  jobs: [{
    id: string,                 // "autocode:garrett" | "clips"
    scope: "project" | "global",// no projectId — native attributes to fronted project
    kind: "autocode" | "catchup" | "clips",
    frameworkId?: string,       // present for autocode/catchup (Option B re-poll)
    status: "running" | "completed" | "failed" | "cancelled",
    processed?: number, total?: number, fraction?: number,
    messageKind?: "error" | "warning",   // failure → native glyph via MessageKind
    action?: "view-report" | "reveal-clips"
  }] }
```

Native composes all display text/glyphs from these fields; web sends no rendered
string and no glyph.

## Recommendation

1. **Ship Strategy 1 (dock the chip) for alpha.** It removes the actual pain (a web
   chip floating over native content) at a fraction of the cost and reopens none of
   the native-side gaps. Add `scope` to `ActivityJobEntry` while here (cheap seam).
2. **Treat Strategy 2 as post-alpha**, gated on the maintainer's decision to the
   **subtitle-collision** question (gap 1) — that decision determines whether
   Strategy 2 is even coherent. If yes: Option A + **re-hydrate on mount**, with the
   structured DTO (gap 4), fronted-project attribution (gap 3), and terminal
   auto-remove (gap 2).
3. **Do not build the global→toolbar branch** (no producer). Keep the `scope:
   "global"` seam. Note the toolbar is not uniform — `OllamaDownloadPill` is a
   bespoke capsule, only `OutOfCredit`/`AlphaExpiry` share `StatusPill` — so a
   future global route picks one, it isn't a drop-in.
4. **Defer Options B/C** unless activity must outlive the web view (B fixes
   switch-back natively via the `MiroAPI` precedent) or go cross-project/long-lived
   (C).

## Open decisions (need maintainer sign-off)

1. **Strategy 1 vs 2 for alpha.** Recommendation: 1 now, 2 post-alpha.
2. **Subtitle-collision (Strategy 2 only, but it's the gate):** during a live run,
   does web activity queue behind the run, get a second line, or stay invisible?
3. **Activity persistence / re-hydrate on mount** — in scope for this doc or a
   separate concern? (Fixes switch-back *and* browser-refresh-loses-chip.)
4. **Catch-up + AutoCode + clips concurrent on one project** — up to three chips
   today (summary/expand handles it); on a native single subtitle line, last-writer
   or a count?

## Implementation plan

**Phase 0 — enabling seam (safe, ship anytime, no behaviour change)**
- Add `scope: "project" | "global"` to `ActivityJobEntry`; stamp `"project"` at the
  three `addJob` sites (`CodebookPanel` ×2, `exportActions` ×1).
- Tests: `ActivityStore` carries scope; existing chip tests unchanged.

**Phase 1 — Strategy 1 (dock the chip) — the alpha deliverable**
- CSS: an `.activity-chip-stack.embedded` docked position (respect
  `--bn-toolbar-inset`; bottom-trailing, above the native status bar).
- `AppLayout`: pass `embedded` to the stack; no logic fork beyond a class.
- Verify in the **bundled `.app`** (WKWebView, not a browser): AutoCode + a clip
  export + a catch-up all dock correctly; multi-job summary/expand still works;
  reduced-motion + "Show animation while analysing" still gate the shimmer.
- Tests: Vitest asserts the `embedded` class + position; no regression to chip
  behaviour.

**Phase 2 — Strategy 2 groundwork (only after decision 1+2)**
- Hoist polling into `useActivityPolling`, mounted once in `AppShell`; store holds
  live status. Both renderers read from the store.
- Vitest: polling drives the store; terminal-skip + `onComplete`-once preserved;
  the completion side-effects (`codebook-changed`, `bn:tags-changed`) still fire.

**Phase 3 — Strategy 2 native push (Option A + re-hydrate)**
- `bridge.ts`: `postActivity(jobs)` + `{type:"activity"}` in `BridgeMessage`;
  diff-guard on job-array value equality (like `quotes-filter`).
- `useBridgeActivitySync` (embedded only): post on change; auto-remove terminal
  jobs after the final frame.
- Re-hydrate: SPA queries a status/list endpoint on mount → repopulate store.
- `BridgeHandler`: `case "activity"` → decode `[ActivityDTO]` → publish into a
  per-project `ActivityLiveData` attributed to the **fronted** project.
- AppKit `ProjectSidebarOutline`/`SidebarSubtitleText`: render web activity per the
  agreed collision rule; native composes string + glyph from structured fields.
- Action round-trip: native "View Report"/"Reveal" → `menuAction`/`project-action`
  back into the SPA (both wired).
- Tests: Vitest (post shape, no post when `!isEmbedded()`); XCTest (`BridgeHandler`
  decodes + publishes; unknown scope ignored, not crashed); manual `.app` walk.

## Acceptance / verification

- The real acceptance is the **bundled `.app` WKWebView**, not a browser — Strategy
  1's whole point is the native context (per `feedback_visual_is_the_product`).
- Phase 1: chip docks, doesn't float over content, all three activity types + the
  multi-job case behave; browser/serve keeps the floating chip unchanged.
- Phase 3: sidebar line reflects progress, web chip suppressed, "View Report" works
  from native, switch-away-and-back still shows a running job (re-hydrate).

## References

- [`design-sidebar-activity-indicators.md`](design-sidebar-activity-indicators.md) —
  native surfaces + vocabulary; Phase 3 = global toolbar pill; `ProjectSubtitle`
  single-winner precedence; motion=healthy / colour=attention.
- [`design-pipeline-diagnostic-popover.md`](design-pipeline-diagnostic-popover.md) —
  `MessageKind` glyph authority; failed-AutoCode must fit it.
- [`design-wkwebview-messaging.md`](design-wkwebview-messaging.md) — the bridge
  contract `postActivity` extends.
- Web: `contexts/ActivityStore.ts`, `components/ActivityChipStack.tsx`,
  `components/ActivityChip.tsx`, `layouts/AppLayout.tsx` (`chipJobs`), `shims/bridge.ts`,
  `utils/embedded.ts`.
- Native: `BridgeHandler.swift`, `ProjectSidebarOutline.swift`, `SidebarSubtitleText.swift`,
  `ProjectRowActivityIndicator.swift`, `ServeManager.swift` + `MiroAPI.swift` (native→sidecar
  HTTP precedent).
- Server: `routes/autocode.py`, `routes/clips_export.py`.

## Review changelog

- **2026-07-26** — first draft claimed "status line, not ring" resolved the
  collision (wrong — subtitle is also single-winner, run owns it), proposed sending
  `projectId` (cross-namespace), and forgot `catchup` (a third web activity).
  design-doc-review + code-review corrected these; the recommendation shifted from
  "Option A now" to "dock the chip now (Strategy 1), native-push post-alpha behind
  the collision decision." Also corrected: `OllamaDownloadPill` is not `StatusPill`;
  endpoint paths carry `/api` + `framework_id`; DTO must carry `frameworkId`; native
  target is the AppKit cell, not `ProjectRow`.
