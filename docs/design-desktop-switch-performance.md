# Desktop project-switch performance — tiers, gains, and the road to instant

**Status:** A2 (warm-sidecar pool) shipped 19 Jun 2026. This doc catalogues the
switch-performance model it established, what it bought, and the optimisations
that remain — so the "why isn't it *instant*?" question has a durable answer and
the future work is captured rather than re-derived.

Context: multi-project Phase A2 (after A1 `background-runs-view-switch`). Sibling
phases: B (cap-2 concurrent execution), C (multi-window). See
`desktop/CLAUDE.md` → "Warm-sidecar pool (Phase A2)" for the mechanism.

## The three timing tiers

Switching the selected project has three speeds, depending on what's already warm:

| Tier | When | What's reused | What still happens | Feel |
|---|---|---|---|---|
| **0 — Cold** | first visit; a 3rd distinct project; a project whose warm slot was evicted | nothing | sidecar spawn → `bind(0)` → import project DB → readiness; **then** WebView mount → SPA boot → `/api` fetch → render | "normal speed" (seconds) |
| **1 — Warm sidecar** *(A2, shipped)* | switching **back** to the immediately-previous project | the **server process** (no boot, no re-import) | WebView **re-mounts**: fresh `WKWebView`, cold SPA boot, `/api` fetch, render | "fast, but not instant" |
| **2 — Warm WebView** *(future, not built)* | — | the **rendered view** too | swap which retained WebView is visible | instant (browser-back feel) |

The QA observation maps exactly: cold the first time (Tier 0), fast-but-not-instant
on switch-back (Tier 1). The expectation of "instant, like hitting Back in a
browser" is **Tier 2** — a different mechanism than A2 built.

## Was "instant like browser-back" a reasonable expectation?

Yes as a desire — it's a learned, native expectation (browser back/forward, app
tab-switch). But it requires keeping the **rendered view** alive, which A2
deliberately did not do. Browser "Back" is instant because the browser keeps the
prior page's DOM + JS heap + scroll state in memory and re-displays it — no
re-fetch, no re-render, no re-mount. A2 keeps the **server** warm, not the
**view**. Warm server ≠ warm view. (This exact gap was flagged in the A2 review:
"warm sidecar ≠ warm WebView.")

## What A2 actually bought (the gains)

- **Killed the dominant cost.** The expensive part of a switch was always the
  *sidecar boot* (Python process spawn + project DB import + uvicorn bind +
  readiness) — seconds. A2 removes that on switch-back. The residual (Tier 1)
  cost is only the client-side SPA re-init, which is sub-second.
- **Dissolved the crash.** Rapid A↔B switching used to race a teardown against a
  boot and could kill the sidecar (`Server exited before becoming ready`). The
  warm path does **no teardown on the hot path**, so the race is gone for warm
  hits. (Cold starts retain the existing, A1-guarded boot supersession.)
- **No regression to correctness or isolation.** Each switch still gets the right
  per-sidecar auth token (the `.id` + port re-mount) and a fresh isolated data
  store (security rule 4). The speed-up didn't trade these away.

## Why Tier 1 isn't instant — where the remaining time goes

On a warm re-point the sidecar is already up, but the detail-pane WebView is
**re-mounted** (`ContentView` keys it `.id("\(project.id)-\(port)")`, so a port
change forces a fresh `makeNSView`). A fresh WebView pays, in order:

1. `WKWebView` instantiation + a WebKit content process.
2. Load `/report/` HTML from the warm server.
3. Download + parse + compile the JS bundle. The data store is
   `.nonPersistent()` **per project** (`WebView.swift:53`), so each mount starts
   with an empty cache and reloads the bundle (localhost, so I/O is fast; parse +
   compile is not free).
4. React mounts the component tree.
5. `/api/*` data fetch (fast — warm DB on localhost).
6. Render the active tab's content (quote grid / sessions) — **scales with
   project size**.

Plus a deliberate spinner: `applySelectionChange` calls `bridgeHandler.reset()`,
so `BootView(.loadingReport)` shows until the SPA posts `ready` (or the 2 s
`didFinish` fallback). So part of the "not instant" is a *visible spinner* during
a re-init that is itself quick — see optimisation 1.

**Why the re-mount is non-negotiable in the A2 design:** two reasons we cannot
just keep one WebView and change its URL — (a) the auth token is injected at
`makeNSView` time, so talking to a *different* sidecar (different port + token)
requires a re-mount to re-inject (skipping this was the original silent-401 bug);
(b) per-project data-store isolation (security rule 4) wants a fresh
`.nonPersistent()` store per project. Tier 1 accepts the re-mount; Tier 2 changes
the model so a re-mount isn't needed at all.

## Future optimisations (cheap → expensive)

### 1. Kill the spinner flash on a warm re-point — *perception, LOW cost*

Don't make it faster; make it *feel* like a content swap instead of a mini-load.
On a warm re-point we know the server is up and the SPA will paint quickly, so
suppress (or ~250 ms-grace) the `BootView(.loadingReport)` overlay — the user
sees the previous frame held a beat longer, then the new content paints in, with
no spinner. **Complexity:** low — thread a "this switch was warm" flag to the
detail pane. **Risk:** hides a genuinely slow paint; the grace window mitigates.
This is the best feel-per-effort win and the natural next step. (Deferred from A2
as gruber's "Option 1".)

### 2. Shared static-bundle cache / process pool — *MEDIUM cost, marginal gain*

The JS/CSS bundle is **identical across projects** (same SPA); only the data
differs. Today each project's `.nonPersistent()` store re-loads the bundle. A
shared `WKProcessPool` + a cache partition for the *immutable bundle* (kept
separate from per-project data, which stays isolated) would cut parse/compile.
**Complexity:** medium — WKWebView doesn't cleanly separate "shared immutable
assets" from "isolated per-origin data," and security rule 4 wants per-project
isolation. **Gain:** modest on localhost (the cost is more in React mount +
render than asset download). Probably not worth it on its own.

### 3. Retain the WebView per warm project (true Tier 2 / browser-back) — *HIGH cost*

Keep N live `WKWebView`s (one per parked project), each fully rendered and bound
to its own sidecar/token/store; swap which is **visible** (ZStack opacity, or
add/remove from superview) instead of re-mounting. Switch-back becomes instant.
Complexities:

- **Memory.** Each retained WebView is a live WebKit content process + a rendered
  React heap. With N warm *sidecars* also resident, you hold N servers + N
  clients. On the 8 GB-Apple-Silicon floor that's real pressure — the retained-
  view count needs the same small cap + LRU as the sidecar pool, ideally a
  *shared* eviction policy so the two pools evict in lockstep.
- **SwiftUI lifecycle fight.** SwiftUI's `.id`-driven recreation is the opposite
  of view retention. WKWebViews would be managed *outside* SwiftUI's normal
  teardown (a view-pool manager, sibling to `ServeManager`) and presented — a
  meaningful rework of the detail pane + `WebView.swift`. Upside: a retained
  WebView never re-points to a different sidecar (each stays bound to its own),
  so the token problem the `.id`+port fix solves simply doesn't arise — cleaner
  in principle, harder to wire in SwiftUI.
- **Staleness.** A retained view shows the project as it was when parked. If a
  background run completed (or any data changed) while parked, the view is stale
  on re-show and needs a targeted refresh — a problem the always-fresh re-mount
  doesn't have today. Couples to the existing "report auto-reload after a run
  finishes" machinery.
- **Pairs with Phase C.** Multi-window already implies multiple live WebViews, so
  the retention infrastructure is shared. Tier 2 is most natural **with or after
  Phase C**, not before.

### 4. (Adjacent, frontend lane) Cheaper SPA cold-mount

Code-split, defer non-critical tabs, cache rendered state in `sessionStorage`.
Helps Tier 0 **and** Tier 1, independent of the desktop shell. Mostly a
`frontend/` concern; noted here for completeness, owned elsewhere.

## Recommendation / sequencing

- **Now / cheap:** optimisation 1 (kill the spinner flash) is the obvious
  feel-win whenever switch polish gets attention — low risk, no architecture
  change. It does not block TF.
- **The destination:** optimisation 3 (retained WebViews) is what delivers the
  browser-back feel the expectation is reaching for — but it is **Phase-C-scale**
  (memory tradeoff on entry-tier Macs, SwiftUI-lifecycle rework, staleness
  handling) and should ride with Phase C (multi-window), which needs the same
  infrastructure. Not now.
- **A2 as shipped is the right TF line:** it removes the multi-second boot and
  the crash. "Fast but not instant" is a correct, honest place to ship from;
  instant is a later, larger tier, not a bug in A2.
