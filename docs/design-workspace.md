---
status: pending
last-trued: 2026-08-15
---

> **Pending / aspirational.** Forward-looking design (post-TestFlight multi-project + multi-window). The **serve/view family (A/B/C) is still open**; several *window-level* decisions were taken 15 Aug 2026 and are marked as such in §"Effectively decided vs genuinely open". The "What shipped" section names the A1/A2 increments already on the path (verified against shipped Swift); the rest is not built. Check `TODO.md` / `docs/ROADMAP.md` for status.

## Changelog

- _2026-08-17b_ — **Two more from the six-window run, both "harmless at N=1, total at N=2".** (1) **Going to the welcome screen put every window on Welcome.** `SidebarDeselectMonitor` uses `NSEvent.addLocalMonitorForEvents`, which is **app**-wide: each window installs one, each sees every click anywhere in the app, and each then called its *own* `deselect`. One click in one window's empty sidebar area deselected all six. Now scoped — the monitor compares `event.window` against its own host view's window. Worth noting the shape, since it is the second instance today: a per-window callback hung off an app-wide channel. The first was the menu-bar broadcasts. (2) **The ordinal's group key was the wrong key.** It was keyed on the *lens*, on the stated assumption that "different lenses already read differently, because the subtitle carries the per-lens count" — which is **false**, and the Window menu proved it: `countSubtitle` returns the session count for Project, for Sessions *and* for a window with no lens yet, so three windows drew `IKEA with uxfriends (1 Session · 18m)` and none of them was numbered, while a fourth carried a "2". Keyed on the rendered subtitle now, so the collision test is the thing the reader is actually looking at rather than a proxy for it. The run narration is deliberately excluded from the key — its stage and ETA change every second and would reshuffle numbers throughout a run.
- _2026-08-18_ — **First review of the multi-window work, and the child window is specified rather than assumed.** Seven agents plus a parsimony pass; 34 findings, log kept with the maintainer's private review notes. The headline confirms constraint 5 as shipped reality: `File ▸ New Window` opens a **full master** with a live project list, so two windows on two studies render one study's participant data under the other's name — and the blast radius crosses an outbound edge, since `Send to Miro` exports the wrong study's quotes to a board named for the right one. The restrictive child shape decided on 16 Aug was never built; the code shipped permissive, the one direction this section had ruled out ("loosening later is trivial and tightening after people rely on it is not"). **Three decisions close it without waiting on 3b:** a child holds a *lens, not a project* and reads its title from the serve, so it cannot drift; ⌥⌘N makes a child unless `hasMaster`; and **promotion is rejected** — it would exist only to paper over the single serve, would be deleted at 3b, and would change a window's shape because a different window closed. Switching the master takes the children with it: **accepted**, odd but manageable through beta, and the honest form of the Stage 3a constraint. Also corrected here: the "a master has two cues" reasoning, which is false — both cues come from one source. Separately measured by the review rather than reasoned: AppKit's automatic Window-menu path **does** render `Title (Subtitle)` (two throwaway binaries), so keying the duplicate group on the rendered subtitle is correct by construction, and `desktop/CLAUDE.md`'s 15.0 deployment target is stale against 26.1.
- _2026-08-17_ — **First real multi-window run: the felt feature works, and it found two bugs.** Four windows on one study, four different lenses, four independent sidebars and subtitles — which was structurally impossible before Stage 3a. Confirmed too that lens choices in one window don't disturb the others. **Bug 1, serious: opening a new window reset every other window to the Project dashboard, and so did going to the welcome screen.** One cause — selection is per window, the sidecar is not. Every arm of `applySelectionChange` that isn't "serve this project" called `serveManager.stop()` on everyone's behalf, and a new window hits that arm before it restores its project. The blast radius is total because killing the serve mints a new port on the next start and every window's web view is keyed on the port (`ServeSession.viewID`), so they all remount at `/report/`. Fixed at both ends: a window only stops the serve when no *other* window still shows a project (`WindowRoster.anyProjectShown(excluding:)`), and `switchProject` no-ops when it is already serving that exact path — which a second window asks for by definition. **Bug 2: the ordinal suffix numbered a window that was alone.** Windows transit the Project lens on open, so ⌥⌘N four times claims 1–4 there and the survivor keeps a number that refers to nothing. The gap rule is kept exactly where it was decided; a window left *alone* in its group now gives its number up, which also retires the "lone Study 2" case that had been accepted as odd.
- _2026-08-16i_ — **P3b: a project reopens where you were on the page, not just on the right lens.** New `anchor-change` message inbound and the existing retry-aware `window.scrollToAnchor` outbound. Anchors as decided: Quotes → group heading (sections *and* themes — both are `QuoteGroup`, and watching only themes would leave the Sections half always restoring to the top), Sessions → session, Analysis and Project → top; Codebook taken as its framework header. **Sessions is the case that shapes the design** — its position is a route, not an offset, so it restores by navigating and its value comes from `SessionsRouteMemory` rather than the scroll reporter; one stored field plus `LensAnchor`'s per-lens table beats two fields kept mutually exclusive by convention. The message **names its lens**, because `anchor-change` and `route-change` are independent and a bare nil can't distinguish "scrolled back to the top of Quotes" from "left Quotes" — without it, every lens switch would wipe a good remembered position (same guard, same reason, as `lensSubtitle`/`lensSubtitleTab`). Capture is debounced to scroll-settle and written only on change, which also dissolved the stress test's teardown-race worry: there is nothing left to grab at `onDisappear`. No validation that a stored anchor still exists — the content is mutable, so the check would be a lie by the time it mattered; it fails honestly at the top instead. **Stage 3a and P3 are now complete, and none of it has been seen on screen.**
- _2026-08-16h_ — **P3a: a project opens where you left it.** The lens half of the restore, and it turned out to need **no new bridge plumbing** — the lens is derivable from the `route-change` path that already flows, so the stress test's "bigger than copy `SessionsRouteMemory`" warning applies only to the anchor half. `LensMemory` holds the decision (unknown lens degrades to the dashboard rather than crashing or being honoured blindly; a never-opened project has no memory, which lands it on the dashboard without needing a rule); `Project.lastLens` persists it in `projects.json`, machine-local and deliberately not inside the researcher's project folder. Two guards share one piece of state: the restore must not re-fire on a run-completion reload's `isReady`, and the capture must not run before the restore or the SPA's initial dashboard landing overwrites the memory it is about to restore from. **P3b (the anchor) is specified but not started** — Quotes → theme heading, Sessions → session, Analysis → top; Codebook taken as its group heading by inference, one table entry to change. Twice while writing the back-compat test I hand-wrote a `projects.json` fixture and twice the format guess was wrong (the envelope's `version`, then `.prettyPrinted` + `.sortedKeys`) — it now round-trips through the real encoder and strips the key by parsing, which is the version that encodes no guess.
- _2026-08-16g_ — **Stage 3a is complete: the roster, the ordinals, and the Dock click.** Two decisions closed it. **Dim, not `mainWindow`** — with a panel frontmost the app dims its window commands rather than acting on the window behind, so `WindowRoster` is deliberately *not* a most-recently-key list, and the ⌘N-from-Settings papercut is **retired rather than fixed**: under the dim rule, "no window is in focus, so make one" is the coherent answer. **Keep the gap** — ordinals are lowest-free and nobody already open is ever renumbered, so closing the middle of three leaves "Study" and "Study 3" and the next window fills the 2. The consequence the decision hadn't pictured is now pinned by a test: close the *first* of two and the survivor sits alone as "Study 2" — odd-looking, and still better than a title that changes because something happened in another window. `applicationShouldHandleReopen` asks the roster rather than AppKit's `hasVisibleWindows`, which counts Settings and the Import window and would answer "yes" when there is nothing to come back to. Writing the roster's tests caught a real bug before it shipped — a welcome-screen window wasn't being counted, so a Dock click would have opened a second one. **Nothing in Stage 3a has been seen on screen**; that is the outstanding claim on all of it.
- _2026-08-16f_ — **`File ▸ New Window` (⌥⌘N) ships, and the dead item beside it is finally dimmed.** `Window ▸ Bristlenose` is gone: wrong menu (Apple's Window-menu command list has no new-window command) and wrong label (it called `openWindow(id:)` against a `WindowGroup`, which *spawns*). Seeding the key across the 21 locales turned up **`File ▸ Open in New Window` (⇧⌘O) already there and dead** — the item this session opened by asking whether it did anything. They are different commands, not duplicates: New Window opens another view of the project already showing; Open in New Window opens the *selected* project, the menu twin of a sidebar double-click. So it stays, `.disabled(true)`, until `WindowGroup(for:)` can carry a project value in Stage 3b — dimmed rather than deleted, because the command is wanted and because a menu is a promise about what the app can do. `applicationShouldHandleReopen` did **not** ride along: the coupling wasn't load-bearing (the menu bar outlives windows, so New Window is already the way back from empty), and it regroups with the **window roster** — now the named next unit, wanted by reopen, by the E4 ordinals, and by the ⌘N-from-Settings papercut. Its shape is a genuine choice, not plumbing: count vs titles vs approximating AppKit's `mainWindow`, which is the semantic `focusedSceneValue` doesn't give (it follows *key*).
- _2026-08-16e_ — **P2 core shipped: each window owns its own state.** `ContentView` holds its `BridgeHandler` as a `@StateObject` and publishes it as `focusedSceneValue(\.bridge, …)`; the menu bar reads the key window's, falling back to `BridgeHandler.unattached` — a never-attached instance whose all-default state dims exactly the items that need a window, so the no-window case needed no branch in ten menu structs. **Two windows on one project can now sit on different lenses**, which is the felt feature (tags beside quotes) and it needed no family call, no second sidecar and no serve rework. The reload fan-out came free: `scheduleReportReloadOnCompletion` already ran per `ContentView`, gated on that window's project. Three decisions taken: renderer crashes on a shared partition are **debounced** (`RendererRecovery`, 250 ms collect + 150 ms stagger, no crash-loop guard by design); a run is narrated by the **key window only** (`WindowSubtitle.body`, extracted as a pure decision so it is testable — five title bars counting one run to 100% is noise, and a background window's per-lens count is genuinely different information); and the **serve stays up** when the last window closes. That last one changed nothing directly but exposed the quit hook sitting on `ContentView`, where it never ran with no window open — moved into `ServeManager`'s own termination observer. Also closed a `TODO` that had been waiting for exactly this work: report chrome now follows `@Environment(\.controlActiveState)` rather than app-wide `NSWindow` key notifications. Still owed on 3a: the E4 ordinal suffix, `File ▸ New Window` ⌥⌘N, `applicationShouldHandleReopen`, and the window roster all three want.
- _2026-08-16d_ — **P1 shipped: the menu bar routes instead of broadcasting.** The taxonomy the stress test asked for is settled first (new §"P1's taxonomy") — four groups, two mechanisms, because window-targeted and selection-targeted share one routing rule and differ only in what the window does next. So the conversion is **one** focused value carrying a per-window command sink, not seventeen focused values. The predicted no-window failure doesn't arise: New Project is already two halves, and the app-global half (`projectIndex.addProject`) needs no window, so ⌘N stages the follow-through on the batons `pendingIconReveal`/`pendingRename` established and opens a window to drain them — the item is never dimmed. Three broadcasts that reached *inside* a window became per-window batons (the outline's rename, the toolbar's session switcher, the export popover's Miro row). 15 `Notification.Name` declarations deleted; 15 `ContentView` receivers collapsed into one `perform(_:)`. **The drift is now mechanically held**: `check-menu-routing.sh` (build-all step 1a-ter) fails on any post from `MenuCommands.swift` bar the two that open a dedicated `Window` scene, and on any retired name reappearing — the count went 16 → 19 in eighteen days precisely because nothing failed. Two things deliberately left: one papercut (⌘N with Settings frontmost opens a second window rather than raising the first — wants a window roster, which `applicationShouldHandleReopen` needs anyway, so both land in P2), and two app-level broadcasts outside the 19 that will need the same treatment (`showFeedbackSheet`, `undoableRemovalRestoredSelection`).
- _2026-08-16c_ — **The child-window shape, and the plan stress-tested.** New §"What a child window is": a spun-off window is same-project, own lens, **no project list** — masters get projects, children get lenses, which removes the failure mode (a secondary window switching the shared serve) while keeping the whole point (Quotes here, Codebook there). Ships restrictive (list hidden *and* switching inert) because loosening is trivial and tightening later isn't; pin-vs-hide is deliberately deferred since both answers ship the same first version. Claude Desktop recorded as the reference implementation, contributing two things the design had missed — a **scope chip** as an alternative to our subtitle, and a **pin (keep-on-top)**, which the five-transcripts case needs. One question left open: whether there are one or two child types (atomic transcript leaf vs lens window), since the naming inverts between them. Accepted for alpha: a child's title is its only cue, which promotes constraint 5 to a Stage 3a **acceptance criterion**. §"Implementation plan" gains the shortest-path note (tags-beside-quotes is P1+P2 and needs no family call) and a stress-test findings subsection. New constraint 8 (shared partition shares renderer failure); constraint 6 updated — wired in `b0dbabc9`, and it closes half of the second cache opt-out in `design-desktop-switch-performance.md`. Relaunch boot storm deferred as alpha-acceptable.
- _2026-08-16b_ — **Presumed Family A; the memory objection is measured.** A sidecar is **~140 MB and flat from 1 to 8 windows** (two sidecars — fronted + A2 parked slot — served eight windows), so A's penalty over B/C is ~140 MB *per additional project*, i.e. 140–280 MB at the expected 2–3. That was the argument holding the family call open, and it no longer carries. §"Effectively decided vs genuinely open" moves the call from *open* to **presumed A, decide late**, and constraint 7 is recorded as A's one genuinely new design problem, to be answered on paper before Stage 3b. New §"Implementation plan" sequences the work; its first two items are family-independent, so nothing waits on the formal call. Two caveats attached to the number: it came off a 3-session project (a floor, not a typical figure) and one Debug-build machine. Separately, `SharedConfigStore` landed (`b0dbabc9`) — constraint 6 is closed for messaging; its memory half is unverified because attributing WebKit helper processes to an app from outside it defeated five approaches.
- _2026-08-16_ — **The window axis is sized, and it isn't the project axis.** Observed usage is ~12 windows over ~2–3 projects (five transcripts side by side plus quotes/analysis on *one* study), so §"Problem definition" now splits the two and carries an "N is about" column. Three consequences recorded: the A/B/C call governs the *small* axis; N retained WebViews cost the same under every family, which largely defuses memory as a discriminator between them; and the load case is a whole 16 GB desk, not an app. §"Memory governance" replaces "a cap sized later" with a **stated budget** plus **live-if-visible / discarded-if-occluded**, whose ceiling is display area rather than user intent. The "what settles the family call" note is **revised**: the earlier "how many projects" survey asked the wrong question — the deciding number is the marginal cost of the Nth window on the *same* project, which is a one-day spike. Two new constraints: 6, cross-window BroadcastChannel is validated but unwired (`WebView.swift:87` mints a fresh partition per view, so two windows are mute today); 7, the MCP handshake assumes exactly one fronted serve, which B and C fit natively and A does not. Family A/B/C still open.
- _2026-08-15_ — **Window-level decisions taken; the big architectural call still open.** (1) New §"What a window opens onto": double-click opens *that project* — the Notes model, answering the open question this doc used to end on — and a window restores the **lens** plus an **anchor**, never a pixel offset and never search/filter, from `projects.json`. (2) New §"The command that opens a window": `Window ▸ Bristlenose` becomes `File ▸ New Window` (⌥⌘N), per the HIG's own menu-bar standards; records the missing `applicationShouldHandleReopen` this exposes. (3) Stage 3 split into **3a** (per-window `BridgeHandler`, same-project windows — needs no family call) and **3b** (per-window serve — blocked on A/B/C), because 3a is what actually buys "Quotes here, Analysis there" and is reachable today. (4) New constraint 5: with two windows open the title bar can name a project that isn't on screen — observed, not predicted by the blocker list. Family A/B/C unchanged and still open.

- _2026-07-28_ — **Stage 1 of window-scoping shipped** (see §"Window-scoping the menu commands" below): View ▸ Hide/Show Projects is now per-window via the app's first `focusedSceneValue` seam (`SidebarVisibilityFocus.swift`), replacing a `NotificationCenter` broadcast that toggled every open window. `BridgeHandler.sidebarVisible` and the `.toggleProjectsSidebar` notification are deleted. The remaining **16** menu broadcasts are unchanged and still fire in every window — the staged plan for them is the new section. Doc otherwise still aspirational.
- _2026-06-21_ — added front-matter (`status: pending`) + pending banner on the day the doc was created; confirmed the "What shipped" A1/A2 increments verify against shipped Swift (`ServeManager.swift` single `parked` slot, `generation` token reused; A1 cancel-on-switch modal gone). Currency fix: §"What shipped" called `warm-sidecar-pool` "pending merge" — it merged the same day (`78b2d40`). Body otherwise unaltered (aspirational by design).

# Workspace — genuine multi-project + multi-window (post-TF)

**Status:** Problem definition + option range. The end goal is fixed; the
**architecture is open** — the serve/view family (A/B/C) is the one big call and is
deliberately unmade here. What *has* been decided since is window-level and local:
what a window opens onto, what restores, and the command that creates one. Those are
marked in §"Effectively decided vs genuinely open"; everything else remains the
"promote to a design doc when post-TF planning starts" artefact that the planner's
Workspace item pointed at.

This supersedes the earlier one-line sketch's *assumption* (one serve process
serving N mounted projects) — see "What we now know" — but keeps its bones: the
reader/worker idea (now one option among several), CLI ≡ desktop parity, and the
"when + how, not whether" framing.

## End goal (fixed)

**Multi-project in the most genuine sense a user expects, and multi-window with
it.** The yardstick is every other real multi-thing app — a browser's tabs, an
IDE's windows, Finder, Music:

- Many projects open at once, visible, switchable.
- Switching between them is **instant** — like a browser tab or an app window, not
  a load. (Switch-back already feels *fast* post-A2; the bar is *instant*.)
- Multiple projects can be **doing things at once** — N analyses running in
  parallel, not one-at-a-time-with-the-rest-blocked.
- **Multi-window** — open projects in separate windows, side by side, compare,
  drag between.
- Each project's **state persists** across a switch (scroll, selection, view) —
  you left it where you left it.
- **No modal friction** — never "stop the current thing to look at another."

Multitasking has been a settled user expectation for decades (the 1989 OS/2 Warp
"juggling" ad is the canonical artefact). The cohort tells us about the *analysis*
surface (quote / theme / tag / signal quality); they do not tell us about
concurrency architecture — so this is a **when + how, not whether** question, owned
by engineering judgement, not cohort feedback.

## What shipped (the increments already on the path)

- **Phase A1 — view-freedom** (`background-runs-view-switch`): a run continues in
  the background while you switch to view another project; the cancel-on-switch
  modal is gone. Pipelines are independent `--no-serve` subprocesses with
  per-project WAL DBs.
- **Phase A2 — warm-sidecar pool** (`warm-sidecar-pool`, merged 21 Jun 2026): switching
  *back* to the previous project re-points to a parked, still-running sidecar
  instead of teardown+restart — kills the boot wait and the rapid-switch crash.
  **Single parked slot** (current + most-recent-previous), not an N-pool.

A1+A2 deliver *fast, crash-free* switching for the A↔B case. They do **not**
deliver the end goal: switching is fast-not-instant, only one prior project is
warm, runs are still effectively single-slot, and it's single-window.

## What we now know (constraints that reframe the architecture)

These are established facts (verified during A2), not assumptions:

1. **The serve sidecar is single-project-per-process.** `create_app(project_dir)`
   binds a per-project DB (`db_url_for_project`), startup importer, event watcher,
   and media routes at startup. A running sidecar **cannot** be re-pointed at
   another project. ⇒ The earlier "one serve process, N projects mounted" sketch
   is **not how the server works today** — it implies a real server
   re-architecture, not just a Swift change. This is the single biggest open call.
2. **Warm *server* ≠ warm *view*.** A2 keeps the Python server alive, but the
   WebView still cold-mounts the SPA on switch (required by the per-sidecar token +
   per-project isolation). Browser-back-*instant* needs the rendered **view**
   retained, not just the server. Full tier model + the WebKit-vs-Safari reasoning:
   `docs/design-desktop-switch-performance.md`.
3. **Memory is the governing cost.** Each warm sidecar is a Python process (~70–90
   MB) and each retained WebView is a live WebKit content process + a rendered
   heap. N of each, on the 8 GB Apple-Silicon floor, is real pressure — any
   "N live" model needs a small cap + eviction.
4. **The plumbing is settled and reusable:** `bind(0)` kernel-assigned ports, the
   sidecar's own parent-death watcher (self-terminate on host death), and the
   single `generation` ownership token. Any new model must keep these contracts.
5. **With two windows open, the title bar can name a project that isn't on screen.**
   Observed 15 Aug 2026: two windows titled `bn-eviction-test` and `project-ikea2`,
   both rendering the same content (38 quotes, 10 signals, identical sections).
   Selection is `@State` and therefore *already* per-window, so each title names its
   own sidebar pick — but the content comes from the single fronted sidecar, so at
   most one of those titles is true. This is blocker 2 below surfacing as a
   **truthfulness** failure rather than a convenience one, and the blocker list did
   not predict it. It sharpened the same day the window subtitle gained a folder
   disambiguator and live run state: the title is now more specific, and therefore
   more credible, on a window that may be showing something else entirely. The
   consequence for sequencing is that multi-window cannot ship half-done — a window
   that lies about which study it shows is worse than a window you can't open.
6. **Cross-window messaging is designed and validated, but not wired.**
   `docs/design-wkwebview-messaging.md` proved (28 Mar 2026) that BroadcastChannel
   works across `WKWebView`s sharing one `WKWebsiteDataStore` **instance**, and
   specifies a per-project keyed store: views within a project share the partition
   and can talk; views across projects stay isolated. That is exactly the shape the
   observed usage needs — "scroll the quotes window, jump to each quote in context"
   is same-project by construction. But `WebView.swift:87` still calls
   `.nonPersistent()` directly, which mints a **fresh partition per view**, so two
   windows would today be mute to each other. **Wired 16 Aug 2026** (`b0dbabc9`,
   `SharedConfigStore`) — keyed per *serve session*, not per project, because the
   server sets a cookie and cookies ignore port, so a partition outliving its
   sidecar would replay the old session's cookie at the next one. Sharing also
   closes half of the second cache opt-out catalogued in
   `design-desktop-switch-performance.md` §"WebKit ≠ Safari": the ephemeral store
   was previously fresh *per view*, so every window started with an empty resource
   cache; siblings now share one, and the first to load populates the bundle for
   the rest.
8. **A shared partition also shares renderer failure, and the recovery predates
   it.** `webViewWebContentProcessDidTerminate` (`WebView.swift:343`) calls
   `webView.reload()` — a clean recovery for one window. Now that siblings share a
   partition, *if* WebKit consolidates their content processes (the benefit we
   want, still unverified) then one renderer crash takes out every window on that
   project and each independently fires a full SPA mount against one sidecar. The
   consolidation is also a blast-radius increase, and the recovery path was written
   for N=1. Needs a coordinated or debounced reload before multi-window, not after.
7. **The MCP handshake assumes exactly one fronted serve.** `MCPHandshake` carries
   `{schema, port, token, instance_id, updated_at}` and — deliberately — **no
   `project` field**, because "tool payloads carry the project"; `syncHandshake()`
   guards on the *fronted* `state`. Multi-window across projects dissolves
   "fronted". This cuts by family: **B and C fit natively** (one port, one token,
   agent names the project — the shape the handshake was already designed for),
   while **A does not** (N ports and N tokens against a one-slot file). A's ways out
   are both costly: grow the handshake to N entries — a breaking change to the one
   contract Bristlenose has with software installed inside *another vendor's* app,
   where an already-installed proxy can skew against a newer host — or let agent
   exposure follow window focus, which is unacceptable on its own terms (the antenna
   badge means exposure; exposure that moves when you click a window is not
   something the researcher authorised). Recorded because it would otherwise be
   rediscovered halfway through implementing A.

## Problem definition

Today the desktop is **project navigation chrome**: a sidebar holds many projects,
exactly one is *fronted* (served + viewable), switching is a per-switch sidecar
lifecycle event, and only one pipeline runs at a time. The gap to the end goal has
four independent dimensions, each currently at "one":

| Dimension | Today | Genuine multi-project | N is about |
|---|---|---|---|
| **Viewable at once** | 1 fronted | N mounted, switch is instant | ~2–3 |
| **Warm (no re-load)** | 1 parked (A2) | all open projects | ~2–3 |
| **Running at once** | 1 (A1 backgrounds it) | N in parallel (capped) | 2 (policy) |
| **Windows** | 1 | N, side-by-side | **~12** |

The job is to lift each from "one" to "N" **without** regressing isolation
(per-project token + ephemeral store), the local-first contract, or 8 GB-floor
viability — and keeping CLI ≡ desktop parity (one codebase, packaging differences
only; `docs/design-modularity.md`).

### Windows and projects are different axes — sized 16 Aug 2026

The table above originally listed "Windows" alongside the project dimensions as
though they scaled together. They do not, and the difference is large enough to
change which decisions matter.

The observed shape (maintainer, 16 Aug 2026) is **many windows over few projects**:
*"quotes and codebook, or a couple of transcripts and analysis … all the transcripts
from 5 sessions tall and skinny side by side on a Studio Display, then scrolling the
main quotes window and jumping to each quote in context."* That is eight-plus windows
on **one** study. The project count is *"less than the number of mail viewers you
might open"* — two or three.

Three consequences, and the first is uncomfortable for how this doc is organised:

1. **The family call (A/B/C) governs the axis that is small.** N projects is ~2–3.
   The axis that is large — windows — is served by Stage 3a, which needs no family
   decision at all. The expensive, contested, least-reversible choice in this
   document is not the one gating the shape of use we actually expect.
2. **It largely defuses the memory argument between families.** N retained WebViews
   cost the same under A, B and C — every family needs a live view per window. The
   family changes only the *sidecar* count, and 3 sidecars vs 1 is on the order of
   180 MB. If the WebViews are the bill, the process model is a rounding error on
   the constraint this doc named as governing.
3. **The load case is a whole desk, not an app.** The target is a 16 GB machine with
   "50 other tabs and Excel and all the rest open" — Bristlenose is one citizen
   among several heavy ones, not the foreground tenant. See §"Memory governance"
   under the orthogonal decisions.

## Implementation options (undecided — the range, with trade-offs)

The central open question: **how do N projects become live + instantly
switchable?** Three families, each composable with the orthogonal decisions below.
None is chosen here.

### Family A — N single-project sidecars + N retained WebViews (extend A2)

Each project keeps its own `bristlenose serve` process (today's model) AND its own
retained, fully-rendered WebView; switching = show/hide the right window/view.
- **For:** no server re-architecture (builds straight on A2 + the warm pool);
  isolation is free (each sidecar already its own origin/token/store); a retained
  view never re-points, so the per-sidecar-token problem simply doesn't arise.
- **Against:** heaviest on memory (N processes + N WebViews); needs a view-pool
  manager outside SwiftUI's `.id`-recreation lifecycle + shared eviction with the
  sidecar pool; staleness handling (a parked view is frozen as-of-park).

### Family B — one multi-project serve + one/few WebViews (the original sketch)

Re-architect `create_app` to mount N projects (path-mapped `/report/{slug}/`,
per-project DB/importer/watcher behind one process); switching = URL change.
- **For:** process-light (one server); "switching is free" is just navigation;
  closest to the browser mental model.
- **Against:** significant server rework (single-project bindings → multi-tenant;
  the ~12 hard-coded `/api/projects/1/` frontend sites; media/event routing per
  project); **shared-fate risk** (one project's bug/wedge can take down all);
  contradicts today's single-project-per-process reality (constraint 1).

### Family C — hybrid reader/worker (the refined sketch)

One multi-project **reader** process (read-only over finished manifests, serving
all reports) + per-project **worker** subprocesses for runs (semaphore-capped).
- **For:** decouples *viewing many* (cheap, one reader) from *running many*
  (capped workers); manifest + events log stay the truth surface, no new IPC;
  maps cleanly to a CLI `bristlenose workspace add/serve/run` and a desktop
  `ServeManager`→`Workspace` rename.
- **Against:** still needs the reader to be multi-project (a chunk of Family B's
  server rework); two lifecycle models to maintain (reader vs workers); the
  reader is still a shared-fate component for *viewing*.

### Orthogonal decisions (compose with any family)

- **Instant switching → retain the rendered WebView (Tier 2).** Needed for the
  browser-back feel regardless of family (even Family B benefits from not
  re-mounting). The threshold-aware switch-progress treatment (instrument first,
  spinner only > ~1 s) is the near-term polish. Detail:
  `docs/design-desktop-switch-performance.md`.
- **Multi-window → Phase C.** `WindowGroup(for: Project.ID)` + a per-window serve
  registry + fixing the hard-coded `/api/projects/1/` frontend sites. Composes
  with A/B/C. Non-negotiable for the paid product (the free CLI+Safari path
  already delivers instant multi-window switching, so the paid app must match it).
- **Parallel runs → Phase B (cap-2 + queue).** `PipelineRunner` single-slot →
  2-slot, 3rd queues (policy already chosen: ruled out unbounded — GPU + provider
  rate-limit contention). Orthogonal to the serve/view model.
- **Memory governance — a stated budget, and liveness bounded by occlusion.**
  Whatever goes "N live" needs eviction, but a cap sized later is a knob; a budget
  is falsifiable. **State a figure Bristlenose holds itself to on a loaded 16 GB
  machine** (the load case is a whole desk — 50 browser tabs, Excel, Teams calls,
  mail — with Bristlenose as one citizen, not the foreground tenant), and treat
  exceeding it as a defect rather than a tuning opportunity.

  The mechanism that makes a dozen windows compatible with that budget is
  **live if visible, discarded if occluded** — Safari's background-tab discarding,
  applied to windows. It reads as though it fights "instant", but there is a natural
  bound underneath: **you cannot look at more windows than fit on your screen.**
  Tiled across a Studio Display all twelve are visible and all live — and that is a
  machine with headroom. On the 16 GB laptop you cannot *see* twelve windows, so the
  ones behind can be discarded without anyone noticing, and revealing one is a
  deliberate act that can afford a beat. This turns the ceiling into a function of
  **display area rather than user intent**, which is self-limiting in the right
  direction and is the only framing found so far under which "a dozen windows" and
  "good citizen next to Teams and Excel" are simultaneously true.

  Couples to §"What a window opens onto" — a discarded window restoring is the same
  problem as a window reopening, so the lens + anchor restore is the mechanism for
  both, and pixel offsets fail for both for the same reason.
- **Per-project view-state persistence** (scroll/selection/view) falls out of
  retained views (Family A / Tier 2) for free; Family B would need explicit
  state save/restore.

## Effectively decided vs genuinely open

- **Decided (direction):** instant switching = retained views (Tier 2);
  multi-window = Phase C, non-negotiable for paid; parallel-runs policy = cap-2 +
  queue; CLI ≡ desktop parity; keep `bind(0)` + parent-death-watcher + single
  `generation` token; isolation (per-project token + ephemeral store) is
  non-negotiable.
- **Decided 15 Aug 2026 (window-level, independent of the family call):**
  double-click opens *that project* in a new window (Notes model); a window restores
  the lens + an anchor and nothing else; `File ▸ New Window` (⌥⌘N) replaces
  `Window ▸ Bristlenose`; window title = project name, subtitle = count or live run
  state. All four sit in the two new sections below and none of them waits on A/B/C.
- **Presumed Family A, decide late (16 Aug 2026).** Not yet formally chosen, but
  no longer wide open: stop spending anything on keeping B or C alive, and don't
  wait on the call to proceed (the plan's first two items are family-independent).

  **What changed:** the family question was held open by an *unquantified* memory
  cost, and it is now quantified. A sidecar is **~140 MB and flat from 1 to 8
  windows** — measured 16 Aug 2026, two sidecars serving eight windows. Since
  every family needs one live WebView per window, sidecar count is the *only*
  thing A/B/C differ on, so A's whole penalty is ~140 MB per additional project:
  140–280 MB at the expected 2–3. On 16 GB that is not an argument, and it was the
  argument. Weigh it against A's zero server rework (B needs single-project →
  multi-tenant, the ~12 hardcoded `/api/projects/1/` frontend sites, and per-project
  media/event routing), A's reversibility (retained-WebView work survives a later
  move to B; B's surgery does not survive a move back), free isolation (each
  sidecar is already its own origin/token/store), and no shared fate.

  **Two caveats on the number.** It came off a **3-session** project, so it is a
  floor rather than a typical figure — re-measure against a real 40-session study
  before it enters a budget. And it is one reading, one machine, Debug build.

  **A's one genuinely new problem is constraint 7** (the MCP handshake). It is
  smaller than it looks — agent access is already per-project and opt-in, and the
  handshake already ships a deliberate v1 limitation — but it touches a contract
  with software installed inside another vendor's app, so it gets designed on
  paper before Stage 3b, not discovered mid-build.

  **What would reopen the call:** the sidecar figure landing far higher against a
  real study, or the expected project count turning out to be ~8–10 rather than
  2–3.

  **What settles it is a spike, not a survey** (revised 16 Aug 2026). The earlier
  framing — "pick it with real multi-project-machine data", i.e. how many projects a
  researcher keeps live — asked the wrong question: that number is ~2–3 and it is
  the *small* axis (see §"Windows and projects are different axes"). The number that
  actually decides is **the marginal cost of the Nth window on the same project,
  versus the Nth project.** Windows on one project share an origin, a port and a
  data store; windows on different projects cannot. Whether WebKit collapses
  same-origin views onto one content process is what makes a dozen windows either
  ~300 MB or ~2 GB, and it is a day's measurement rather than a cohort question.
  Run it before the family call, because it moves constraint 3 (memory as the
  governing cost) more than any argument in this section does.

  Weigh alongside it, in both directions: **for A** — it extends shipped, proven A2,
  and it is the reversible option (the retained-WebView work survives a later move
  to B, whereas B's single-project→multi-tenant surgery does not survive a move
  back); and its governing objection, memory on the 8 GB floor, is the one that
  erodes with time, since base Apple Silicon is already 16 GB and this ships
  post-TF. **Against A** — constraint 7, the MCP handshake, which B and C fit
  natively and A does not.

## Window-scoping the menu commands (the Notes-experience prerequisite)

Prompted by "double-click a project → new window, sidebar closed" (28 Jul 2026).
Assessed against shipped code; **Stage 1 is built**, Stages 2–3 are not.

**The finding that reframes it:** the sidebar wasn't shared state. `ContentView`
owns `columnVisibility` as `@State`, so it was always per-window — but the
*command* was a `NotificationCenter.default` broadcast every window received. Two
windows moved in lockstep. This is systemic: there were **17** `post` sites in
`MenuCommands.swift` and **zero** uses of `FocusedValue` anywhere in the app. With
two windows open, New Project fires twice and Rename prompts in both.

Three blockers sit under the Notes experience, all from every model being one
app-level `@StateObject` injected into `WindowGroup(id: "main")`:

1. **One `ServeManager`** — one sidecar, one port, one warm-park slot; and
   `create_app(project_dir)` is single-project-per-process (constraint 1 above).
   Two projects ⇒ two sidecars.
2. **One `BridgeHandler`, one `weak var webView`** — last WebView registered wins,
   so every `menuAction` drives the wrong window. Its ~28 `@Published` properties
   are global too, so `activeTab` is shared: **two windows cannot show different
   lenses.** This kills the "Quotes here, Sessions there" value even for two
   windows on the *same* project.
3. **`WindowGroup(id: "main")` carries no value**, so `openWindow(id:)` duplicates
   the same state rather than opening a project.

### Stages

- **Stage 1 — window-scoped sidebar. ✅ Shipped 28 Jul 2026.** `focusedSceneValue`
  publishes the key window's binding; the menu drives it directly and dims when no
  project window is frontmost. Scene-scoped (not view-scoped) so it survives focus
  moving into the WKWebView. Decision logic extracted to `SidebarToggle`
  (+ `SidebarToggleTests`) per the testable-helper convention.
- **Stage 2 — `@FocusedValue` for the remaining commands. ✅ Shipped 16 Aug 2026**
  (see P1 in §"Implementation plan"). The real keystone: it is
  what makes *any* multi-window behaviour correct, and Stage 3 would have to invent
  it anyway. Also fixes double-fire bugs that exist today the moment a user opens a
  second window. **The count is now 19, not the 16 recorded on 28 Jul 2026** —
  re-counted 15 Aug. That drift is itself the finding: new commands are still being
  written with the broadcast pattern, because it is the path of least resistance and
  nothing fails when you take it. The number grows until Stage 2 lands and makes
  `focusedSceneValue` the obvious idiom to copy.
- **Stage 3a — per-window `BridgeHandler` (same-project windows). ✅ Complete
  16 Aug 2026** (see P2 in §"Implementation plan"). Split out of
  Stage 3 on 15 Aug 2026 because it is the half that **actually delivers the felt
  feature** — "Quotes in this window, Analysis in that one" — and it needs **no
  family call**. One `BridgeHandler` per window, each owning its own `weak var
  webView` and its ~28 published properties; both windows point at the *same*
  sidecar, so there is no second Python process and no serve rework. Note that
  Stage 2 alone does **not** get you here: `@FocusedValue` routes the *command* to
  the right window, but the lens is shared because the *state* is shared. 3a is the
  one that fixes it.
- **Stage 3b — per-window serve + `WindowGroup(for:)` (cross-project windows).**
  Two projects visible at once ⇒ two sidecars (constraint 1). This is the part
  blocked on the family choice (A/B/C) above. "Sidebar closed by default" is ~2
  lines at the *end* of this stage (seed `columnVisibility = .detailOnly` when the
  window opens with a project value) — none of the cost is there.

**The open question this section used to end on is answered** (15 Aug 2026): double-
click means *new window on that project* (the Notes model). The "same project,
different lens" case is not the compromise it looked like — it is served by
`File ▸ New Window`, so both behaviours exist, and 3a delivers the cheaper one
first. See §"What a window opens onto".

## What a window opens onto (decided 15 Aug 2026)

Double-click on a project in the sidebar opens **that project** in a new window.

### It restores where you left, not the dashboard

The app already holds this position one level down. `SessionsRouteMemory` remembers
which session you were reading inside the Sessions lens, and its doc comment states
the principle: *"Visiting the grid RESETS the memory — 'the view the user left' is
the index in that case, not the transcript they saw an hour ago."* This decision is
the same rule one level up — project instead of session, lens instead of route.

The reason is an **asymmetry, not a preference.** A wrong restore costs one click:
you wanted the overview, you click Project. A wrong reset can be unrecoverable: you
wanted the quote you were part-way through tagging, and you are now hunting for a
position among 312 that you never consciously memorised. One is a click, the other
is a search.

Precedent: **Finder stores view state per folder** — view style, sort, scroll — and
restores it when you open that folder. A Bristlenose project *is* a folder and the
lens is the view style. That contract predates OS X.

The counter-case — the Project dashboard is the orientation surface, and a
researcher returning after three months wants the overview — mostly dissolves on
inspection: a project with **no** stored lens lands on the dashboard already, and
that is exactly the never-opened case. The genuinely awkward case is a months-old
memory, and the fix for it is **not** a time heuristic ("restore if closed
recently"). An invisible clock deciding where you land is an unlearnable rule — the
researcher cannot see it, so they cannot predict it. Either always or never. (Same
objection, and the same answer, as the conditional folder disambiguator in the
window-subtitle work.)

### What is restored, and what deliberately isn't

| | Restored | Why |
|---|---|---|
| **Lens** | Yes | Cheap, robust, and most of the felt value — Quotes vs the dashboard is the difference a researcher notices. |
| **Position** | As an **anchor**, never a pixel offset | The content is mutable: a re-analysis rewrites the quote set, hiding twenty quotes shifts everything. A stored offset into changed content lands *somewhere* and looks deliberate — confidently wrong, which is worse than landing at the top. A section anchor either resolves or falls back honestly. |
| **Search / filter** | No | A query restored days later shows 6 of 312 quotes with no visible cause. Mail clears search between openings for the same reason. (The tag filter keeps its own existing persistence rule; this decision doesn't touch it.) |

### Two mechanisms, different owners

- **Relaunch** — macOS state restoration, per window, restoring each window as it
  was. The OS owns this; we don't reimplement it.
- **Opening a project fresh** (double-click, `File ▸ New Window`) — the per-project
  last-lens memory, stored in `projects.json`, which already carries per-project
  desktop state (`icon`, `position`, `lastOpened`, `agentAccess`) and is
  machine-local. It does **not** go inside the researcher's project folder: this is
  window management, not study data, and it has no business travelling with the
  study to a client's Drive.

That split also settles two windows on one project: each restores itself on
relaunch; a *new* window on that project uses the per-project memory.

### Dependency

The lens lives in `BridgeHandler`, one app-level object today — so this rides
**Stage 3a** and cannot land before it. Once 3a exists it is nearly free, since each
window finally has somewhere to put its own lens. `SessionsRouteMemory` is the shape
to copy: a small value type carrying the decision, unit-testable, fed by the
`route-change` bridge messages that already flow.

## The command that opens a window (decided 15 Aug 2026, shipped 16 Aug)

`Window ▸ Bristlenose` becomes **`File ▸ New Window`, ⌥⌘N**.

Two things are wrong with it today. It is in the **wrong menu** — Apple's standard
Window-menu command list contains no new-window command at all, while
`File ▸ New <Item>` is defined as *"Creates a new document, file, or window."* And
its **label is the brand name** on an item that calls `openWindow(id: "main")`
against a `WindowGroup`, which *spawns* a window rather than reopening one: it is
already a New Window command wearing a reopen label, and it is how a second window
gets opened by accident today.

⌥⌘N rather than ⌘N because ⌘N is New Project. That is Mail's exact split — ⌘N makes
a new *thing* (a message), ⌥⌘N makes a new *window onto existing things*.

**Shipped 16 Aug 2026**, and it turned up a sibling the design hadn't accounted
for. `File ▸ Open in New Window` (⇧⌘O) already existed — the item whose deadness
opened this whole line of work — dispatching `menuAction("openInNewWindow")` to
an SPA handler that has never existed. The two are **different commands**, not
duplicates: New Window opens another view of the project already showing; Open
in New Window opens the *selected* project, which is the menu twin of
double-clicking a sidebar row. So the dead one stays, **dimmed**, until
`WindowGroup(for:)` can carry a project value — Stage 3b. Dimmed rather than
deleted because the command is designed and wanted, and because this codebase
already treats a menu as a promise about what the app can do: an item that
silently does nothing is worse than one that says it can't yet.

`applicationShouldHandleReopen` did **not** ship with it. The coupling turned out
not to be load-bearing — the menu bar survives having no windows, so
`File ▸ New Window` is still reachable from the empty state, which is what
`Window ▸ Bristlenose` was there to provide. It is grouped with the window roster
instead, below.

Rejected: *New Bristlenose Window* (Finder names itself only because its menu bar is
also the desktop's; for an ordinary app the app name is noise) and *New Project
Browser* (names the chrome rather than the content, and "browser" is a loaded Mac
term for NSBrowser's column view, which this is not).

**A gap the rename exposes.** There is no `applicationShouldHandleReopen` in the
app, so `Window ▸ Bristlenose` is currently the *only* way back after closing the
last window. Clicking the Dock icon should do that and today does nothing. That
handler has to land **with** the rename, not after it.

**Settled by the same HIG pass:** window-list entries are listed *"in alphabetical
order for easy scanning"* — a second, independent reason the
`Project view: <folder>: <project>: <lens>` title scheme was withdrawn, since a type
prefix sorts every window under one letter and destroys the scan. The shipped scheme
is title = project name, subtitle = count or live run state; the options weighed and
the edge cases are drawn in `docs/mockups/window-menu-naming.html`.

## What a child window is (decided 16 Aug 2026)

Spinning a window off a study gives a **child**: same project, its own lens, and
**no project list**. Masters get projects, children get lenses. One `ContentView`,
one flag on the sidebar outline — `ProjectSidebarOutline` already folds the five
lens rows into the same `NSOutlineView` as the project list, so this is a section
omitted, not a new window type.

**Why the cut is exactly there.** The project list switches which study is served,
and with one `ServeManager` a secondary window switching it yanks every other
window's content — constraint 5 again, but user-triggered and frequent. The lens
rail switches the view of the current study: per-window after Stage 3a, harmless,
and the entire point. Removing the first removes the failure mode; keeping the
second keeps the feature. Nothing is traded.

**Ship restrictive.** In a child the list is not shown *and* project-switching is
inert (`View ▸ Show Projects` dims). Not because the pin is certainly right, but
because loosening later is trivial and tightening after people rely on it is not.

**A child holds a lens, not a project (decided 18 Aug 2026).** Read
"masters get projects, children get lenses" literally: a child has no `selection`
of its own, and its title comes from *what is being served*, not from a per-window
pick. Three things follow, and the third is why this shape rather than the obvious
one.

- **A child cannot name a study it isn't showing.** The failure this whole
  section exists to prevent becomes unrepresentable rather than guarded — there
  is no second source to drift from. (The guard is still owed on the *master*,
  for the async gap while it switches.)
- **Switching the master takes the children with it.** Every window is showing
  the same study by construction, so the switch moves all of them coherently and
  every title stays true. **Accepted 18 Aug 2026** — a bit odd, manageable
  through beta, and better than any alternative available before 3b. The cost is
  real and worth stating: you cannot peek at another study while keeping
  transcripts open. That is the Stage 3a constraint surfaced honestly instead of
  hidden behind a window that lies, and removing it is exactly what 3b buys —
  which gives that stage a one-line headline.
- **Nothing here is built to be deleted at 3b.** "A child's project is the served
  one" is not thrown away when serves become per-window; it is *re-scoped*, the
  same sentence with a narrower subject. This is the argument against the obvious
  alternative — giving a child its own project and then **promoting** an orphaned
  child to a master. Promotion exists only to paper over "there is one serve", has
  no meaning once that is false, and makes a window change shape while you are
  looking at it because you closed a different one. Rejected.

**⌥⌘N makes a child unless there is no master (decided 18 Aug 2026).** The
condition is `hasMaster`, **not** "no windows open" — closing the master while
children remain is reachable, and under a window-count rule ⌥⌘N would mint
another child, leaving a screen of lens windows with no project list and no way
to get one short of relaunching. With `hasMaster` that state has a one-keystroke
exit using the command already in the researcher's fingers, which is what
replaces promotion. A welcome-screen window counts as a master (it carries the
list); Settings and the Import window do not, as the roster already has it. A new
child opens at the **lens of the window it was spun off from** — the gesture reads
as "duplicate this view, now re-point it".

**Deferred deliberately — pin vs hide-by-default-switchable.** Both answers ship
the same first version; they diverge only on what happens when someone tries to
get the list back, which is observable in use rather than predictable. The test:
spin off a Quotes window and go ten minutes without reaching for the project list.
If the hand goes there it is a hide, and the serve question reopens.

**Superseded 18 Aug 2026 — "a master has two cues" was wrong.** The reasoning
below held that a master is safer because a wrong title is contradicted by the
sidebar. It is not: in the shipped master the title *and* the sidebar highlight
both derive from the same per-window `selection`, while the content comes from the
shared serve — so they agree with each other and are wrong together. Two cues from
one source are one cue drawn twice, and the master is therefore the *more*
deceptive shape, because it looks corroborated. Under the decision above a child
reads its title from the serve and cannot drift at all. Original text kept:

> **Accepted for alpha — a child's title is its only cue.** A master has two, the
> sidebar selection and the title; strip the list and the title stands alone. Fine
at alpha, since the failure needs two windows *and* a stale title. But it promotes
constraint 5 from a nice-to-have to a **Stage 3a acceptance criterion**: in a
master a wrong title is contradicted by the sidebar, in a child there is nothing
to contradict it.

### Reference implementation — Claude Desktop

Its "open in new window" is this pattern shipping (observed 16 Aug 2026): the
child has **no sidebar at all** — traffic lights, title, pin, overflow menu — and
is fully live, its composer works, so a child is not a read-only viewer. Two
things worth taking:

- **A scope chip beside the title** (the project name next to the conversation
  name) is how it shows containment without a sidebar. An alternative to our
  title+subtitle and more compact under a long name — prototype it against the
  subtitle before Stage 3a fixes the shape.
- **A pin (keep-on-top)**, per-window and opt-in. Nothing here had noticed the
  need, and the five-transcripts-beside-a-scrolling-quotes-window case requires
  it, or the transcripts fall behind the master the moment you click it.
  `NSWindow.level = .floating`; selective, since five floating windows would fight
  each other and bury the master.

### Open — one child type or two?

Claude Desktop's child is a *pure leaf* with no navigation, which it can be
because a conversation is **atomic**, like a note. A study is not — it has five
lenses, so Bristlenose has one level more than the reference (project → lens →
session versus project → conversation). The analogy is exact for a transcript
window and silent about a lens window.

The naming inverts between them, which is the tell that they may be different
things: the reference puts the leaf in the title and the container in a chip.
"Ben — 12 Mar" with an `IKEA Study` chip reads well; "Quotes" with an `IKEA Study`
chip does not, because *Quotes* is a mode, not a name — for a lens window the
study **is** the identity. So possibly two types: an atomic transcript leaf (no
rail, participant in the title) and a lens window (study in the title, lens rail,
no project list). That is more surface than one type. Decide before Stage 3a,
not during.

## Implementation plan

Derived from the stages and decisions above, ordered by dependency. **The first
two items are family-independent** — they are what the observed usage (a dozen
windows over two or three studies) actually needs, and nothing in them changes if
the presumed-A call is later reversed.

### The shortest path to the felt feature

Tags beside quotes — two windows on **one** study, one on Codebook and one on
Quotes — is **P1 + P2 and nothing else.** No family call, no cross-project serve,
no retained views, no occlusion policy, no pin decision, no child-type decision.
All of those sit on the far side of it. When the rest of this plan looks long,
this is the part that isn't.

### Now — unblocked, and fixing live defects

**P1 · Stage 2 — `@FocusedValue` for the broadcast commands. ✅ Shipped 16 Aug
2026.** `MenuCommands.swift` held 19 `NotificationCenter.default.post` sites; each
fired in *every* open window, and a second window is reachable today, so these
were live defects rather than future ones. All 17 that reach a project window now
go through one `WindowCommandSink` published as a scene focused value
(`WindowCommandFocus.swift`) — 15 `ContentView` receivers collapse into one
`perform(_:)`. Three per-window batons replaced the broadcasts that reached
*inside* a window: the outline's `renameRequest`, the toolbar's
`sessionsSwitcherRequest`, and the export popover's `onMiro` closure. Fifteen
`Notification.Name` declarations are deleted.
*Done:* every menu command targets the frontmost project window and dims when
none is — except New Project and New Folder, which never dim (see the taxonomy
above). Held open by `desktop/scripts/check-menu-routing.sh`, wired into
`build-all.sh` step 1a-ter, which fails on a post from `MenuCommands.swift` or on
a retired name coming back. Seven tests in `WindowCommandTests`.

#### P1's taxonomy, settled 16 Aug 2026

The stress test said to settle this before the refactor. Read against the code,
the 19 sites are **four** groups, and the useful finding is that two of them share
one mechanism:

| Group | Sites | Routing | Dims when no window? |
|---|---|---|---|
| **1 · App-global with a window follow-through** | New Project, New Folder | Key window if there is one; otherwise perform the model half at app level and open a window to carry the rest | **Never** |
| **2 · Window-targeted** | AI & Privacy, Send to Miro, Send Feedback, Welcome, Switch Session, (DEBUG) diagnostic fixtures | Key window | Yes |
| **3 · Selection-targeted** | Rename ×2, Delete Folder, Move To ×2, Reveal Transcripts, Locate, Stop, Remove from Sidebar, Add Files | Key window, which reads its own selection | Yes |
| **4 · Already single-receiver by scene** | Import ▸ …, (DEBUG) Cloud Import fixtures | A dedicated `Window` scene receives them | n/a |

Groups 2 and 3 are **one seam**, not two: both mean "route to the key window",
and they differ only in what the window then does with it. So the conversion is
one focused value carrying a per-window command sink, not seventeen focused
values. Group 3's *dimming* still reads app-global `BridgeHandler` state until
P2 — P1 owns routing, not state.

Group 4 is the reason the count of real defects is 17, not 19. `openCloudImport`
is received by `CloudImportOpener`, which is attached to the main `WindowGroup`
and so does fire once per window — but it opens a `Window` scene, and
`openWindow(id:)` on one of those is idempotent, so the visible behaviour is
already correct. Left alone deliberately: the fix is to move the modifier off the
`WindowGroup`, which belongs with the cloud-import work, not here.

**The no-window path has an owner, and it is group 1's split.** `createNewProject()`
is already two halves — `projectIndex.addProject(…)`, which is app-global and needs
no window, and *select it + begin inline rename*, which is window state. So ⌘N with
no window open performs the first half at app level, sets the existing one-shot
batons (`pendingRename` — the idiom `pendingIconReveal` established), and opens a
window that consumes them on appear. The item is therefore **never dimmed**, and
the failure the stress test predicted — "no window open and the user cannot create
a project at all" — does not arise. Which window consumes the baton when several
are open is a P2 question, not a P1 one: with one window there is no ambiguity, and
P1 routes to the key window before the fallback is ever reached.

**P2 · Stage 3a — per-window `BridgeHandler`. ✅ Core shipped 16 Aug 2026.**
Depends on P1: routing commands to the right window is meaningless while the
state they act on is shared. `ContentView` now owns its `BridgeHandler` as a
`@StateObject` and publishes it as `focusedSceneValue(\.bridge, …)`; the menu bar
reads the key window's and falls back to `BridgeHandler.unattached`, whose
all-default state dims exactly the items that need a window — so the no-window
case needed no branch in ten menu structs. Both windows still point at the same
sidecar: no second Python process, no serve rework.

The reload fan-out turned out to need **no work**: `scheduleReportReloadOnCompletion`
already runs per `ContentView` and is gated on that window's `selectedProjectID`,
so making the handler per-window made it fan out by construction.

The three stress-test failure points were **decided 16 Aug 2026** and are
resolved:

| | Decision | How |
|---|---|---|
| **Renderer crash on a shared partition** (constraint 8) | Debounce | `RendererRecovery` collects the per-view terminations from one crash for 250 ms, then reloads the batch staggered 150 ms apart. Not coordinated: each view has to re-fetch its own page regardless, so an election buys nothing. |
| **Run narration at N windows** (E7 at a scale it wasn't argued at) | Key window only | `WindowSubtitle.body(narratesRun:isStopping:isRunning:)` — extracted as a pure decision so it is testable, per this file's own rule. Background windows show their per-lens count, which is genuinely different information per window. |
| **Last window closed** | Serve stays up | Already the behaviour, so no teardown was added — but it exposed that the quit hook lived on `ContentView`, i.e. never ran when the last window was closed. Moved into `ServeManager`'s own termination observer: the object that owns the process owns its shutdown. |

Also folded in: the `NSWindow.did{Become,Resign}Key` pair driving report chrome
carried a `TODO: filter by window object when multi-window ships`. They are
`@Environment(\.controlActiveState)` now — per-window by construction, no AppKit
plumbing, and it covers app-level deactivation too.

**Stage 3a is complete as of 16 Aug 2026.** The four items that were owed all
landed: the `File ▸ New Window` ⌥⌘N rename, the **E4 ordinal suffix**,
`applicationShouldHandleReopen`, and the `WindowRoster` the last two needed.

`WindowRoster` is deliberately small — ordinals per (study, lens) group, and "is
any project window open?". It is **not** a most-recently-key list, i.e. not an
approximation of AppKit's `mainWindow`. That was considered and declined
(16 Aug 2026): with a panel frontmost this app **dims** its window commands
rather than acting on the window behind, so there is no second window to resolve
and nothing to hold. That decision also **retires the ⌘N papercut** rather than
fixing it — under the dim rule, "no window is in focus, so make one" is the
coherent answer, not a bug.

Ordinals are **lowest-free, and nobody already open is ever renumbered**. Close
the second of three and you keep "Study" and "Study 3"; the next window opened
fills the 2, so the numbers stay small. The honest consequence, pinned by a test
so it doesn't read as a bug: close the *first* of two and the survivor stays
"Study 2" on its own. Odd-looking, and still better than a title that changes
because something happened in a different window.

Constraint 5 (a title naming a project that isn't on screen) is structurally gone
now that each window owns its own state — **but none of Stage 3a has been seen on
screen.** That is the one outstanding claim on all of it.

**P3 · Per-window restore — lens + anchor.** Depends on P2 (the lens has nowhere
to live until each window owns one). Per §"What a window opens onto"; copy
`SessionsRouteMemory`'s shape.

**P3a — the lens. ✅ Shipped 16 Aug 2026.** `LensMemory` decides, `Project.lastLens`
stores it in `projects.json`, and `ContentView` restores on the `isReady`
transition that marks a fresh open. Needed **no new bridge plumbing** — the lens
is already derivable from the `route-change` path this doc's stress test worried
about. The table below is explicit that the lens is "most of the felt value", and
this is that half.

Two guards, both load-bearing, both in one piece of state (`lensRestoredFor`):
the restore must not re-fire on the *next* `isReady`, because a run-completion
reload raises that flag again and would yank the researcher back from wherever
they had since navigated; and the *capture* must not run before the restore, or
the SPA's initial landing on the dashboard overwrites the memory with `project`
and the restore then dutifully honours it.

**P3b — the anchor. ✅ Shipped 16 Aug 2026.** The half that needed the bridge
work, and it got a new message in each direction: `anchor-change` inbound
(`useAnchorReporter` → `BridgeHandler.currentAnchor`) and `window.scrollToAnchor`
outbound, which already existed as a shim and is retry-aware, so it survives being
fired straight after a lens switch while the destination page is still mounting.

Anchors as decided: **Quotes → group heading** (sections *and* themes — both are
`QuoteGroup`, both render `<h3 id>`, and watching only themes would make the
Sections half of the lens always restore to the top), **Sessions → session**,
**Analysis and Project → top**. Codebook was not specified and is taken as its
framework section header, the direct sibling of a theme heading one lens over.

**Sessions is the shape that justifies the design.** Its position is a *route*,
not a scroll offset, so restoring it means navigating, and its value comes from
`SessionsRouteMemory` rather than from the SPA's scroll reporter. One stored field
interpreted by `LensAnchor`'s per-lens table, rather than two fields kept mutually
exclusive by convention.

Capture is debounced to scroll-settle and written only on change, and the message
**names its lens** — `anchor-change` and `route-change` are independent, so a bare
nil cannot distinguish "scrolled back to the top of Quotes" from "left Quotes",
and without the lens a switch away would wipe a good remembered position. Same
guard, and the same reason, as `lensSubtitle`/`lensSubtitleTab`.

Deliberately no validation that a stored anchor still exists: the content is
mutable, so the check would be a lie by the time it mattered. It fails honestly
instead — `scrollToAnchor` retries then gives up at the top, and a vanished
session lands on `TranscriptPage`'s error state with the switcher as the way out.

*Done when:* closing a window on Quotes at a given section and reopening the
project lands there, while search and filter do not come back.

### Alongside — measurements that gate the memory design

**M1 · Quiet-machine window cost.** Quit browsers, confirm `pgrep -f
WebKit.WebContent` reads near zero, launch, open N windows, count and measure.
No attribution needed once nothing else on the machine spawns WebKit. *Answers:*
whether occlusion-discarding is load-bearing or a refinement. Independent of
P1–P3; do it whenever convenient.

**M2 · Sidecar footprint against a real study.** Re-measure the ~140 MB against a
40-session project rather than the 3-session one it came from. *Answers:* whether
the presumed-A cost estimate survives, and gives the budget a real number.

### Design-before-build

**D1 · Agent access across N sidecars** (constraint 7). A's only new problem, and
the one that touches an external contract. Must be settled on paper before P4.

### Later — needs D1, M1, and the formal call

**P4 · Stage 3b** — per-window serve, cross-project windows. **P5 · Tier-2
retained views** — pairs with P4; shares the view-pool infrastructure.
**Phase B** — parallel runs, cap-2 + queue; orthogonal to all of the above and
can move earlier if run-throughput feedback demands it.

### Failure points found by stress-testing this plan (16 Aug 2026)

**P1 — the 19 sites are three categories, not one. ✅ Settled and shipped.** It
turned out to be four groups sharing two mechanisms — see "P1's taxonomy" above.
The predicted failure (New Project dimming with no window open, leaving the user
unable to create a project) does not arise: the command splits into an app-global
half and a window follow-through. The gate exists as
`desktop/scripts/check-menu-routing.sh`.

**P2 — the renderer-crash recovery was written for N=1. ✅ Debounced.**
Constraint 8. `RendererRecovery` — 250 ms collection window, 150 ms stagger.
Deliberately no crash-loop guard: a page that reliably kills the renderer
reload-loops at N=1 today, and that is a separate bug whose fix this would
only hide.

**P2 — the run-completion reload must fan out. ✅ Free, then decided.** The
reload half needed nothing: `scheduleReportReloadOnCompletion` already runs per
`ContentView`, gated on that window's `selectedProjectID`, so a per-window handler
fans it out by construction. The narration half was the real question, and it is
**key window only** — see the P2 table.

**P2 — nothing refcounts windows. ✅ Answered.** The serve question is
decided — **it stays up**, so closing the last window is not a teardown event and
needs no refcount for that. The partition follows: with the serve up, reopening
asks for the same `ServeSession` and should get the same partition back, so
releasing on window close would throw away sessionStorage for nothing;
`SharedConfigStore`'s supersede-sweep already handles the port changing. What is
still owed is a **roster of live project windows** — wanted by
`applicationShouldHandleReopen`, by the E4 ordinal suffix, and by the ⌘N papercut.
`WindowRoster` shipped later the same day and closed it.

**P3 — bigger than "copy `SessionsRouteMemory`". ✅ True, and it split.**
The **lens** half needed none of it — the lens is derivable from the
`route-change` path that already flows, so P3a shipped 16 Aug 2026 with no bridge
work at all. The warning stands for the **anchor** half: no anchor or scroll
message exists in either direction, so P3b needs new plumbing, capture before
teardown (by `onDisappear` the web view is gone), and restore after mount — the
existing retry-polling `scrollToAnchor` shim covers that last part. **✅ All of
it shipped 16 Aug 2026** — the teardown-race worry dissolved: capture is
continuous (debounced scroll-settle, written on change), so there is nothing to
grab at `onDisappear`.

**M1 — "quit browsers" is insufficient.** Xcode, Mail, Messages, Slack and Notion
all embed WebKit, and Xcode will be open because you are building. Enumerate and
quit, or state the floor.

**M2 — the number depends on state, not just study size.** Sidecar footprint grows
with what has been *loaded*, so the protocol must fix the state ("after opening
Quotes on the largest study") or successive readings are not comparable.

**E4 ordinals leave gaps. ✅ Decided, shipped, then refined on first contact.**
Close window 2 of 3 and you have "Study" and "Study 3"; the next window opened
fills the 2, so the numbers stay small. Renumbering was rejected for the reason
this doc rejects a time-based restore — a name that changes for reasons invisible
from the window itself is unlearnable.

**The first real run found the case the decision was never shown** (17 Aug 2026).
Every window passes *through* the Project lens as it opens, so ⌥⌘N four times
claims 1–4 there; move three to other lenses and the survivor keeps whatever it
grabbed in transit. The screen showed a window titled **"IKEA with uxfriends 4"**
alone on Project with no 1, 2 or 3 anywhere — a number disambiguating nothing,
which is the one thing an ordinal must never be.

Refined rather than reversed: **a window left alone in its group gives its number
up.** The gap rule is untouched where it was decided (close the middle of three
and 1 is still held, so nothing moves), and it also retires the "lone Study 2"
consequence that had been accepted as odd-but-tolerable. Stated as a rule: an
ordinal is shown only while it is telling the reader something.

**Deferred — the relaunch boot storm.** Eight restored windows each cold-mounting
against one booting sidecar. Alpha-acceptable (16 Aug 2026), and already partly
mitigated: siblings now share one ephemeral resource cache, so the first to load
populates the bundle for the rest, and occlusion-discarding covers the remainder
by mounting only the visible windows.

### Small, already decided, not blocked by any of the above

**The window roster. ✅ Shipped 16 Aug 2026** — `WindowRoster`, serving the two
consumers that survived: `applicationShouldHandleReopen` (which asks it rather
than AppKit's `hasVisibleWindows`, since that counts Settings and the Import
window too) and the E4 ordinals. The third — approximating AppKit's `mainWindow`
so a command could act on the window *behind* a frontmost panel — was **declined**
in favour of dimming, which is what the app already did. See the P2 section.

## Sequencing

Post-TF. A1 ✅ and A2 ✅ already removed the "stuck on one project" felt blocker,
so this is enhancement, not blocker-fix — but it is the **paid-product** bar (the
free CLI+Safari path sets it). The phases compose: Phase B (parallel runs) and the
serve/view family choice are independent; Phase C (multi-window) + Tier-2 (retained
views) are the instant-multi-window pair. Likely order once planning opens:
choose the family → Tier-2 retained views → Phase C multi-window → Phase B
parallel runs (or B earlier if run-throughput feedback demands it).

**Stages 2 and 3a are the exception to "post-TF".** Neither waits on the family
call, and Stage 2's bugs are **live today, not hypothetical**: a second window is
reachable right now via `Window ▸ Bristlenose`, and `MenuCommands.swift` currently
holds **19** `NotificationCenter.default.post` sites (up from the 17 counted on
28 Jul), every one of them a broadcast that fires in every open window. With two
windows open, New Project fires twice and Rename prompts in both. Constraint 5 —
a title bar naming a project that isn't on screen — is the same class of problem
and lands on 3a. The honest framing is that today's app is *single-window software
that can be made to open a second window*, and the cheapest way to stop that being
true is Stage 2 → Stage 3a, in that order, independent of everything else here.

## References

- `docs/design-desktop-switch-performance.md` — the switch-latency slice (tiers,
  WebKit≠Safari, the instant-switch path). This doc is the umbrella; that one is
  the latency sub-concern.
- `docs/mockups/window-menu-naming.html` — the window-title/Window-menu naming
  options and their edge cases, with the 15 Aug decisions marked on each. The
  source for §"The command that opens a window" and for what a restored window is
  called once it opens.
- `docs/design-modularity.md` — CLI ≡ desktop parity, what ships where.
- `desktop/CLAUDE.md` — warm-sidecar pool (A2) mechanics, the `generation` token,
  `bind(0)` + parent-death-watcher contracts.
