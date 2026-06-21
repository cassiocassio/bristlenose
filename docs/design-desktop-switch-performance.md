---
status: current
last-trued: 2026-06-21
trued-against: HEAD@main on 2026-06-21
---

## Changelog

- _2026-06-21_ — trued up, no material changes. Every load-bearing claim verified against shipped Swift: the Tier 0/1 cold-vs-warm split (`ServeManager.switchProject`), the single warm slot (`ServeManager.parked`, `ParkedSidecar.swift`), `.id("\(project.id)-\(port)")` WebView keying (`ContentView.swift`), `.nonPersistent()` per-project store (`WebView.swift`), `Cache-Control: no-store` (`app.py`). Tier 2 + the four future optimisations are correctly fenced as not-built. Added front-matter.

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

## WebKit ≠ Safari: which cache benefits we forfeit, and why

A reasonable expectation: "we embed WebKit, Safari is WebKit, so we should get
Safari's instant Back." *A browser is more than a rendering engine* — and that
"more" is exactly the part we don't inherit. Three layers to separate:

- **The engine** — WebCore (layout/DOM) + JavaScriptCore. We get this.
- **The framework** — WebKit2's multi-process model + networking + caching APIs,
  surfaced through `WKWebView`. We get this too: a crashed web-content process
  can't take the app down, and `WKWebView` *does* support an HTTP resource cache
  and a back-forward page cache. So yes — we get more than a rendering engine.
- **The browser app** — Safari adds history/session restore, tab *snapshots* for
  instant visual switch, tuned cache eviction, persistent partitioned storage,
  profiles. **None of that is in the `WKWebView` embedding surface.** It's Safari,
  the application, built on top of WebKit.

Then two of *our own* decisions opt out of the WebKit-level caching we'd
otherwise get:

1. **We recreate the `WKWebView` on every switch** (`.id` re-mount). WebKit's
   back-forward page cache — the thing that makes Safari's *Back* instant — lives
   on a **single web view's own session history** (`backForwardList`). It restores
   a page you navigated *away from within that instance*. A brand-new instance has
   an empty history and an empty page cache: nothing to restore. Safari's instant
   Back is *intra-instance* back/forward; our switch is a *cross-instance* swap, so
   the page cache never even applies.
2. **We use `.nonPersistent()`, fresh per project** (security rule 4). That's an
   ephemeral store — no persistent HTTP cache, wiped with the instance — so even
   the ordinary resource cache (bundle, assets) starts empty every mount. A
   deliberate isolation choice, but it forecloses the cheap caching too.

The one path that *would* use Safari's actual page cache — keep one `WKWebView`
and navigate between projects via back/forward — is ruled out by our security
model: each project's page needs *its* sidecar's token injected (can't, without a
re-mount) and its own isolated store (can't, in a shared instance). So we can't
borrow WebKit's automatic "keep the page around"; we'd have to do it manually.

**That manual version is Tier 2.** Retaining a live `WKWebView` per project and
swapping visibility is, in effect, us re-implementing the slice of "a browser"
that isn't the rendering engine — the session/tab/cache-continuity layer. The gap
between `WKWebView` and Safari *is* the Tier-2 work. We weren't handed it for free
because our token + isolation model is stricter than a browser's (every project is
its own origin with its own credential), and stricter isolation is precisely what
defeats shared-session caching.

## Future optimisations (cheap → expensive)

### 1. Fix the warm-switch progress treatment — *perception; design problem, not a one-liner*

⚠️ **This is NOT "kill the spinner."** Naively removing the overlay is wrong,
because the right treatment depends on how long the warm re-point actually takes,
and that's **report-size-dependent** — small reports are under the line, big ones
are over it.

**Grounded in the response-time literature** (checked 21 Jun 2026, not eyeballed).
The established constants — Miller 1968, popularised by Nielsen 1993; Doherty &
Thadani, IBM 1982 — are **100 ms / 400 ms / 1 s / 10 s**, not a single 250 ms line:

- **< ~100 ms** — feels instantaneous (Miller/Nielsen). Show nothing, ever.
- **~100 ms – ~1 s** — Doherty "in-flow" band (sub-400 ms is where productivity
  peaks). A loading indicator here is the **flicker bug** — it appears and
  vanishes before the eye resolves it ("what flashed?"). Suppress it; hold the
  prior frame and let content paint in. *(This is the maintainer's "≤250 ms feels
  janky" instinct, correctly generalised up to ~1 s — and 250–500 ms is exactly
  the practitioner "delay-before-showing-a-spinner" band.)*
- **> ~1 s** — flow of thought starts to break (Nielsen). Now the *absence* of
  feedback feels broken → you DO want an affordance — but **probably not the
  current full detail-pane `BootView(.loadingReport)` flash**. Something lighter,
  to be designed (designer's call — do not prescribe here).
- **> ~10 s** — determinate / percent-done; the user will multitask.

**The two practitioner numbers don't survive scrutiny as stated — the real model
is three feedback channels:**

1. **Instant action-ack (< ~100 ms) — non-negotiable, and NOT the spinner's job.**
   The click must register *immediately*: selection highlights, cursor/active
   state, prior frame stays put. "Click → nothing for 250 ms" is **not** the
   delay convention working — it's a *missing ack*, and it reads as "is my network
   down?" because nothing answered the click. (A browser never goes dead on a link
   click: the tab spinner / stop-button chrome flips instantly, *before* the page
   paints. That's the ack channel, separate from render.) Get this right and the
   "delay-before-spinner" window stops feeling broken — something already replied.
2. **No heavy indicator at all for sub-~1 s ops.** Hold the prior frame, let
   content swap in. The ~250–500 ms "delay-before-showing" number is *only* the
   guard that stops a spinner ever appearing for these — not a dead zone.
3. **A designed, *fading* affordance only for genuinely long ops (> ~1 s).**

**Reject the "≥ 1 s minimum-display" rule as usually stated** — "show a page, then
hold it back for a second" is as daft as it sounds. It only bites in one narrow
window (the op finishes just *after* the spinner appeared), and there it trades a
~40 ms flicker for ~950 ms of *deliberately withheld, already-ready content* —
quadrupling perceived latency to dodge a blink. Bad deal. The blink has two better
fixes: (a) don't show the indicator for sub-threshold ops at all (channel 2), and
(b) if one is up, **fade it out** as content arrives — continuity without
hostage-taking. **Never hold ready content to satisfy a minimum.** (The "1 s" was
likely a misapplied borrow of Nielsen's 1 s-flow limit — which argues *against*
showing anything sub-1 s, not for parking a spinner there.) So the current single
treatment (always show the boot overlay) is wrong at *both* ends — it flickers
under ~1 s and is too heavy, and potentially content-withholding, over it.

**Prerequisite — instrument first.** Before designing, measure the actual Tier-1
re-point→`ready` time across a range of report sizes (small / medium / large), so
we know *which* reports stay under ~1 s (suppress any indicator) versus cross it
(need the designed treatment) — and how far the big ones go. Don't design against
a guessed threshold. (The probe + state transitions already log; add timing around
the `.starting`→`.running`→SPA-`ready` span for the warm path.)

**Then design** (designer-owned): the sub-threshold "show nothing" path is cheap
(a "this switch was warm" flag gates the overlay); the over-threshold affordance
is a real little UX problem — what, where, how light — open for design, NOT the
current flash. **Complexity:** low to *build* once designed; the design is the
work. This is the best feel-per-effort near-term win, and it does not block TF.
(Originated as gruber's deferred "Option 1"; sharpened by the 250 ms-threshold
point, 21 Jun 2026.)

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
  Phase C**, not before. This doc is the switch-*latency* slice; the broader
  multi-project + multi-window architecture and its open options (the family A/B/C
  serve-model call) live in the umbrella doc `docs/design-workspace.md`.

### 4. (Adjacent, frontend lane) Cheaper SPA cold-mount

Code-split, defer non-critical tabs, cache rendered state in `sessionStorage`.
Helps Tier 0 **and** Tier 1, independent of the desktop shell. Mostly a
`frontend/` concern; noted here for completeness, owned elsewhere.

## The benchmark: the free CLI path already delivers Tier 2 today

The decisive product framing (maintainer, 21 Jun 2026): **a CLI user who runs
`bristlenose serve` per project and opens each in its own Safari window/tab gets
all of Tier 2 — instant switching — for free, right now.** Real Safari is the
whole browser: persistent partitioned cache, back-forward page cache, tab
snapshots, session continuity. Switching tabs is instant because the rendered
pages stay alive. So on this axis **the free CLI+Safari workaround currently
beats the desktop app** (which is at Tier 1).

That sets a floor, not an aspiration: **the paid desktop product must at least
match what the free path already does.** Slowness isn't noticed only by people who
understand the cache machinery — the response-time thresholds above are *human
perception*, not technical sophistication, so every user feels the lag equally.
If anything the non-technical researcher (our actual user) is *less* forgiving,
not more: they have no engineering mental model to excuse it with — they just see
that the paid app is slower than the free one. So this isn't about a niche
audience; it's that a paid product slower than its own free workaround fails all
its users. That's why Tier 2 / multi-window is not a someday-nice-to-have — it's
the bar the free path has already set.

## Recommendation / sequencing

- **Near-term (careful, designer-owned):** optimisation 1 — but as a *measured,
  threshold-aware* fix, not a spinner-removal. Instrument the warm-switch timing
  first, then design the sub-/over-250 ms treatments. Low build cost once
  designed; does not block TF.
- **The destination — non-negotiable for the paid product:** optimisation 3
  (retained WebViews = Tier 2) delivers the browser-back feel, and it **rides
  Phase C (multi-window)**, which the maintainer has called non-negotiable for the
  paid product (21 Jun 2026). The two share all the infrastructure (multiple live
  WebViews + a view-pool manager + shared eviction with the sidecar pool). Phase C
  is where the paid product matches the CLI+Safari benchmark above. It is
  **Phase-C-scale** (memory on the 8 GB floor, SwiftUI-lifecycle rework, staleness
  handling) — not now, but committed.
- **A2 as shipped is the right TF line:** it removes the multi-second boot and the
  crash. "Fast but not instant" is a correct, honest place to ship *alpha/TF*
  from. It is **not** the bar for the paid product — that bar is Tier 2, set by
  the free CLI+Safari path. Instant is a later, larger tier, not a bug in A2.
