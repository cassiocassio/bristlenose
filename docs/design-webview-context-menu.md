---
status: built 24 Oct 2026 on main, unreleased (§10 as built); §9.3 still the owner's call
last-trued: 2026-10-24
trued-against: HEAD@main 002b6ee1d, macOS 27.0 (26A428), Swift 6.4
---

# The report's right-click menu: what WebKit offers, where it goes, what to offer instead

The report runs in `BristlenoseWebView` (`desktop/Bristlenose/Bristlenose/WebView.swift`). At
the time of this audit it overrode only `performKeyEquivalent`, so every right-click got WebKit's
default menu. _Since 21 Oct 2026 (`576f7287`) `willOpenMenu` exists and swaps WebKit's Reload for
Reload Report through a pure helper, `ReportContextMenu.apply`; the link and image items below are
unchanged, and that helper is where this proposal's edits would go._ This audit maps that menu across every lens and page, and proposes
what the app should offer instead.

**Mockup:** [`docs/mockups/webview-context-menu-proposal.html`](mockups/webview-context-menu-proposal.html)
shows today against proposed in each context, plus the window each one opens.

**§9 supersedes §4.1's menus** (24 Oct 2026: the owner's rules, a Gruber/HIG review, and the
owner's decisions). §§1–8 stay as the measured record.

**The owner's position, which the proposal follows.** People coming from Safari expect *Open Link
in New Window* to open a new window. Bristlenose offers it only where it can open the right
Bristlenose window reliably: the right project, the right lens and the right place within it (a
session's transcript at the moment, a section, a quote). Where it can't, it offers nothing.

## How each row was established

| Mark | Meaning |
|---|---|
| **P** | Measured in a standalone WKWebView probe (`experiments/webview-context-menu/probe.swift`, macOS 27.0). It uses the same public delegates the app implements, with synthetic right-clicks and each item fired after the menu closed. |
| **C** | Code reading, file:line given. Not tried in the app. |
| **H** | A hand check is still owed in a Debug build (§7). |

**Not tried in the app.** The Debug app was in use by a concurrent session (the Screens lens's
own right-click work), so I did not drive it. Every in-app row is therefore **P** for what WebKit
does plus **C** for what `WebView.swift` then does with it.

## 1. What WebKit puts in the menu (P)

Raw `NSMenuItem.identifier` values, read in `willOpenMenu`:

| Target | Items, in order |
|---|---|
| `<a href>` (internal or external) | `WKMenuItemIdentifierOpenLink` Open Link · `…OpenLinkInNewWindow` Open Link in New Window · `…DownloadLinkedFile` Download Linked File · `…CopyLink` Copy Link · separator · `…ShareMenu` Share… |
| `<img>` (http or `data:`) | `…OpenImageInNewWindow` · `…DownloadImage` · `…CopyImage` · `…CopySubject` Copy Subject · `…RevealImage` Look Up · separator · Share… |
| Text or background, no selection | `…GoBack` Back (only with history) · `…Reload` · separator |
| `<button>`, span, div | Back · Reload · separator · Share… |

Two things not probed:

- **Text with a selection.** Real right-click selects the word, and WebKit then adds Look Up, Translate, Search With…, Copy, Share, Speech and Services.
- **`<video>`.** The media menu: Open/Download/Copy Video, Show Controls, Full Screen, Picture in Picture.

Inspect Element is added when `isInspectable` is on (`WebView.swift:208`, the Diagnostics preference).

**The identifiers are SPI.** The macOS 27 SDK exports the `_WKMenuItemIdentifier…` symbols in
`WebKit.tbd`, but no public header declares them. Matching on the raw strings works today. It is an
undocumented contract (§5, risk 1).

## 2. Where each item goes in the app

| Item | Route | Result in Bristlenose |
|---|---|---|
| **Open Link in New Window**, same-serve URL | `createWebViewWith` with the link URL, `targetFrame` nil (P) → `isAllowedServeURL` passes → the **popout player** path (`WebView.swift:771-858`) (C) | **Closes any open player.** Opens a 720×480 window titled *Video Player* holding a bare embedded SPA: no toolbar, sidebar or lens rail. `PopoutOwners` registers it as a player, so the Video menu's bare keys (Space, ←, →) attach while it is key. It shares the report's `navigation` message handler (`desktop/CLAUDE.md`: the popout inherits the parent's `userContentController`). `handleMessage` does not check which web view posted (`BridgeHandler.swift:876`), so this SPA's `ready` / `route-change` / `panel-state` posts update the **main window's** `BridgeHandler`. That can move its lens capsule and Back state to the popout's route. (C, H) |
| **Open Link in New Window**, external URL | `createWebViewWith` (P) → `openExternal` (C) | Opens the default browser or Mail. |
| **Open Image in New Window**, same-serve image (session thumbnails) | `createWebViewWith` with the image URL (P) | The player-window path above, showing a bare JPEG and closing any playing clip. (C) |
| **Open Image in New Window**, `data:` image (Screens stills) | `createWebViewWith` with the `data:` URL (P) → `openExternal` refuses the scheme (`WebView.swift:420-427`) | Nothing happens; a warning is logged. (C) |
| **Open Link**, internal | Main-frame navigation, `navType` 0 (P) → allowed (C) | A full document reload of the SPA at that route: boot surface, `documentState` → `.loading`, then `ready` again. It gets there, at the cost of a reload, and in-page state goes. |
| **Open Link**, `#t=…` timecode | A fragment change on the current document (C) | Nothing visible. Nothing handles `#t=`. |
| **Download Linked File / Download Image** | No `decidePolicyFor`, no `didBecome download`, no `decideDestination`, and no file in ~/Downloads (P) | Silent no-op in the probe, with the same public delegate set as the app. (H for the app) |
| **Copy Link / Share…**, internal | Copies or shares `http://127.0.0.1:<port>/report/…` (C) | A loopback URL that dies when the serve restarts (`bind(0)`) and means nothing to anyone else (`desktop/CLAUDE.md` § Port allocation). |
| **Copy Image** | Pasteboard | Works. |
| **Copy Subject / Look Up** on an image | Visual Look Up | Runs on participants' recordings and screens. Whether it contacts Apple's servers was not measured. |
| **Back / Forward / Reload** | WebKit history / reload | Same as the toolbar's ◀ ▶, plus a reload in place. |

**The same hijack is reachable with a LEFT click, no menu needed.** These go through
`createWebViewWith`:

- Codebook threshold-review timecodes are `target="_blank"` links to `/report/sessions/{sid}#t-{sec}` (`ProposalZoneList.tsx:125`).
- The Dashboard featured quote with no media uses ⌘-click → `window.open(sessionURL)` (`Dashboard.tsx:392`).

Each opens a report page in the player window (C, H). §4 fixes this along with the menu.

## 3. Every lens and target

The right-click target is decided by the DOM: an `<a href>` gets link items, an `<img>` gets image
items, anything else gets the page menu. "Place" is where the **left-click** goes, which is not
always the href, and the proposal keys on the place.

**Proposal key:**

- **SEED**: a new Bristlenose window opened at the place. WebKit's own item stays where it is, with its own localised title, retargeted to our action.
- **NONE**: remove the item.
- **KEEP**: leave WebKit's item.

### Project dashboard (`islands/Dashboard.tsx`)

| Target | Tag · href | Left-click goes to | WebKit offers / does today | Mac user expects | Proposal |
|---|---|---|---|---|---|
| Stat cards, pair halves (`:103`, `:130`, `:145`) | a · `/report/{lens}/`, `/report/quotes/#themes` | That lens (and anchor) | Link menu · New Window → player window | That lens in a new window | **SEED** lens (+ anchor). WindowSeed has the lens today, not the anchor. |
| Section/theme nav (`:512`) | a · `#{anchor}`, relative, so it resolves to `/report/#…` | **Quotes** lens at the anchor | Link menu · New Window → player window, at the Project root | Quotes at that section | **SEED** Quotes + anchor. The href is wrong for this, so take the place from the component (§4.2). |
| Session filename (`:280`), coverage timecodes (`:544`), featured timecode | a · `#t=0` / `#t={sec}` | Plays the clip in the player | Link menu · New Window → player window showing the dashboard | The recording at that moment | **SEED** session transcript at the moment, or **NONE** for v1 (§4.3). |
| Session `#N` (`:305`) | a · `/report/sessions/{sid}` | That transcript (by a full reload) | Link menu · New Window → player window | That transcript in a new window | **SEED** session |
| Featured speaker (`:432`) | a · `/report/sessions/{sid}#t-{sid}-{sec}` | Transcript, but the anchor format doesn't parse (`TranscriptPage.tsx:557` matches `t-(\d+)$`), so it lands at the top | as above | Transcript at the quote | **SEED** session + seconds (from the component, not the href) |
| Featured quote card (`:400`) | div role=button | Plays (or the transcript if there's no media) | Page menu | — | KEEP the page menu |

### Sessions grid and tapestry (`islands/SessionsTable.tsx`, `components/SessionTapestry.tsx`)

| Target | Tag · href | Left-click | Today | Expects | Proposal |
|---|---|---|---|---|---|
| `#N` (`:955`) | a · `/report/sessions/{sid}` | Transcript (full reload) | Link menu → player window | Transcript in a new window | **SEED** session |
| Journey labels (`JourneyChain.tsx:133`) | a · `/report/sessions/{sid}#t-{sec}` | Transcript at the moment (router) | as above | Transcript at that moment | **SEED** session + seconds |
| Filename (`:905`) | a · `#t=0` | Plays | Link menu → player window with the grid | Recording | as for dashboard timecodes |
| Thumbnail (`Thumbnail.tsx:34`) | img · `/report/assets/thumbnails/{sid}.jpg` (unauthenticated) | Opens the player | Image menu · New Window → **player window shows the JPEG and the playing clip closes** · Download does nothing | Copy Image; perhaps the session | **NONE** for Open/Download Image; KEEP Copy Image. Optionally SEED session (the place is known). |
| Tapestry flags, track, quote marks (`SessionTapestry.tsx:464-664`) | SVG / button | Transcript at the moment (router) | Page menu | — | KEEP. No link items to replace (see §4.5 for a possible addition). |
| Scene strip, hover frame | SVG image / img, `pointer-events:none` | — | Never a target | — | — |
| Speaker badges (`:1020`), tapestry toggle | button | Picker / expand | Page menu | — | KEEP |
| Interviews header (`:587`) | a role=button · `#` | Reveal / copy path | Link menu · New Window → player window showing the grid | Not a link | **NONE** for all link items: `href="#"` is not a place. |

### Session transcript (`islands/TranscriptPage.tsx`)

| Target | Tag · href | Left-click | Today | Expects | Proposal |
|---|---|---|---|---|---|
| Timecode (`:835` → `TimecodeLink.tsx:34`) | a · `#t={sec}` (relative, no session) | Plays | Link menu → player window showing the transcript at the top | This transcript at this moment | **SEED** session + seconds (both known on this page) |
| Words (`:891`), paragraphs | span, in a contenteditable host when paragraph editing is on | Caret | Text/editing menu (Look Up, Translate, Copy, Search With…) | Mac text services | **KEEP** (§4.6) |
| Margin label and gutter mark (`islands/transcript/GutterEntry.tsx`; `Annotation.tsx` retired 17 Oct 2026) | a · `/report/quotes/?reveal={dom_id}#{anchor}` | Opens the Quotes lens at the quote's group, the quote brought into view (`docs/design-transcript-gutter.md`) | Link menu | That quote's group | **SEED** the same address. Screens and Discussion marks beside it carry `/report/screens/?screen=…&session=…` and `/report/discussion/?item=…&turn=…` |
| Speaker badge (`:854`) | button | Picker | Page menu | — | KEEP |

### Quotes lens

| Target | Tag · href | Left-click | Today | Expects | Proposal |
|---|---|---|---|---|---|
| Timecode (`QuoteCard.tsx:687`) | a · `#t={sec}` | Plays | Link menu → player window showing the Quotes root | The transcript at the quote | **SEED** session + seconds |
| Speaker badge (`QuoteCard.tsx:742` → `PersonBadge.tsx:30`) | a · `/report/sessions/{sid}#t-{sec}` | Transcript at the moment (full reload) | as above | The same, in a new window | **SEED** session + seconds |
| TOC sections/themes/sessions (`TocSidebar.tsx:244-280`) | a · `#section-…`, `#theme-…`, `#session-quotes-{sid}` | Scroll | Link menu → player window | That section in a new window | **SEED** Quotes + anchor |
| Hidden-quotes counter (`Counter.tsx:82`, `:113`) | a role=button · `#` | — | Link menu | Not a link | **NONE** (link items) |
| Card body, badges | div / span / button | Focus / edit | Page or text menu | — | KEEP |

### Codebooks lens

| Target | Tag · href | Left-click | Today | Expects | Proposal |
|---|---|---|---|---|---|
| Navigator rows (`CodebookV2Sidebar.tsx:166`) | a · `#` | Selects the codebook | Link menu → player window | That codebook in a new window | **NONE** for v1. The codebook is not addressable by route; `LensAnchor` scrolls to `codebook-fw-…` ids, so SEED Codebook + that id is possible later. |
| Author links (`CodebookV2Page.tsx:292`) | a · external `https://`, `mailto:` | Browser / Mail | Link menu; New Window → browser | Safari's behaviour | **KEEP** all link items, minus the Download item, which does nothing |
| Threshold-review timecodes (`ProposalZoneList.tsx:125`) | a target=_blank · `/report/sessions/{sid}#t-{sec}` | **A left click opens the player window** (§2) | as above | Transcript at the moment in a new window | **SEED** session + seconds, for both the left click and the menu |
| Tag bar / rows (`CodebookAuthoring.tsx:88`, `:242`) | span / div, draggable | Select / drag | Page menu | — | KEEP |

### Signals lens (`islands/SignalsPage.tsx`)

| Target | Tag · href | Left-click | Today | Expects | Proposal |
|---|---|---|---|---|---|
| Location heading (`:1027`) | a · `#section-…`, relative, so it resolves to the **Signals** page | **Quotes** lens at the section | Link menu → player window showing Signals | Quotes at that section | **SEED** Quotes + anchor, from the component, because the href points at the wrong lens |
| Expanded quote timecode (`:741`) | a · `/report/sessions/{sid}#t-{sec}` | Transcript (full reload) | as above | The same in a new window | **SEED** session + seconds |
| Signal card, heatmap cells, sidebar entries | div / td / a without href | Focus / scroll | Page menu | — | KEEP. A signal has no addressable place. |

### Discussion lens (`islands/discussion/DiscussionLens.tsx`)

There are no links and no images. Timecodes are spans (`:610`, `:634`), so they get the page menu. **KEEP.**
(§4.5 covers adding an item later.)

### Screens lens and the Screens navigator (`islands/screens/ScreensLens.tsx`)

| Target | Tag · src | Today | Expects | Proposal |
|---|---|---|---|---|
| Board screengrab (`:2095`) | img · `data:image/jpeg` | Image menu. **Open Image in New Window does nothing** (the `data:` scheme is refused). Download does nothing (P). Copy Image works. | Copy Image | **NONE** for Open/Download Image; KEEP Copy Image. Leave room for Tidy at the top (the concurrent session's `context-items`). |
| Navigator thumbnails (`:968`) | img · `data:` | as above | as above | as above. A screen has no route, and `LensAnchor` restores Screens to the top, so there is no SEED for a screen until a screen is addressable. |

I did not read the Screens files beyond these lines. A concurrent session owns them.

### Popout player (`bristlenose/theme/templates/player.html`)

| Target | Today | Proposal |
|---|---|---|
| `<video>`, src `/media/…` (unauthenticated) | WebKit's media menu (not probed). **Open Video in New Window does nothing**: the popout web view has no `uiDelegate` (`WebView.swift:799-800` sets only `navigationDelegate`), so `createWebViewWith` is never asked (C). Download Video goes through the same silent path as Download Linked File (H). Copy Video Address gives a loopback `/media/` URL. | **NONE** for Open/Download/Copy Video; **KEEP** Full Screen, Picture in Picture and Show Controls. |

### Surfaces in the web view that aren't lenses

| Surface | Target | Proposal |
|---|---|---|
| Miro export panel (`MiroExportPanel.tsx:291`, `:407`) | External links (docs, the board) | **KEEP**, minus Download |
| Status page (`server/status_page.py:292`) | Help link, `target=_blank`, external | **KEEP**, minus Download. It is server-rendered, so a bridge script would have to be added to it before it could send a place. It has no internal links, so it doesn't need one. |
| Header, NavBar, Footer, the web Settings modal | Hidden in embedded mode | — |
| Native Settings, sidebar, toolbar | Native, not the web view | — |

## 4. Proposal

### 4.1 What the menu offers

| Target kind | Open Link in New Window | Open Link | Download Linked File | Copy Link / Share… | Image items | Page items |
|---|---|---|---|---|---|---|
| Internal link whose place is known | **SEED** (WebKit's item and title, our action) | **NONE**. The left click does it without a reload. | **NONE** | **NONE**: a loopback URL that dies on the next restart | — | KEEP |
| Internal link, place unknown or `href="#"` | **NONE** | **NONE** | **NONE** | **NONE** | — | KEEP |
| External link (`https`, `mailto`) | **KEEP** (opens the browser, which is what Safari users expect from a non-report link) | KEEP | **NONE** (does nothing) | KEEP | — | KEEP |
| Image (thumbnail, screengrab) | — | — | — | — | **KEEP Copy Image**. **NONE** for Open Image in New Window and Download Image. Copy Subject / Look Up: **owner's call** (participant imagery; network use unmeasured). | KEEP |
| Player `<video>` | — | — | — | — | **NONE** for Open/Download/Copy Video. KEEP Full Screen, PiP and Controls. | KEEP |
| Text, background, buttons | — | — | — | — | — | **KEEP** Back/Forward/Reload, the text services and Inspect Element |

These choices meet the expectation for three reasons:

- *Open Link in New Window* survives only where it does what Safari does: the same page, in a new window, with full chrome. Everywhere else it is absent rather than surprising.
- Every **NONE** removes an item that today does nothing, does the wrong thing (the player hijack), or hands out a URL that stops working.
- The items that work (Copy Image, the text services, Back) stay.

Reload stays because it is the in-place escape hatch when a report wedges. Whether it reads as a "web page" tell is a separate question for another day.

### 4.2 The place comes from the component, not the href

Two links point their href at the wrong lens: Signals' location headings and the Dashboard's
section nav both carry a relative `#section-…` while their left click goes to Quotes. Timecode
hrefs carry no session at all. A seed built from the href would open the wrong window. So the
element whose left click goes to a place declares that place, for example
`data-bn-place='{"lens":"sessions","session":"s3","seconds":120}'`, written by the same component
that writes the click handler. Then the two cannot drift.

An `<a href>` with no `data-bn-place` gets **NONE**: no new-window item, never a guess. This
follows *exact key over clever heuristic*.

### 4.3 What WindowSeed needs

Today `WindowSeed` is `{token, project, lens}` (`WindowSeed.swift`). That is enough for a lens
root, which is what the sidebar's lens-row *Open in New Window* already does
(`ContentView.swift:2918`). It cannot express a session, a moment, a section or a quote.

Proposed: one optional field, `place`, a small typed enum mapped through the existing `LensAnchor`
apply paths:

| Case | Apply after `ready` (where `seed.lens` is applied, `ContentView.swift:1089-1103`) |
|---|---|
| `.anchor(lens, id)` (Quotes `theme-…`, `section-…`, `session-quotes-…`, `q-…`; Codebook `codebook-fw-…`) | `activateLens` + `scrollToAnchor`, as `restoreAnchor` does for `lastAnchor` |
| `.session(id, seconds?)` | Navigate to `/report/sessions/{id}#t-{seconds}` through the router, so `TranscriptPage`'s tolerant `#t-N` resolver (`TranscriptPage.tsx:552-561`) finds the nearest segment. `navigateToSession(sid, anchorId)` goes through `scrollToAnchor`, which has no tolerance. |

Three constraints:

- **Decoding stays tolerant.** The custom `init(from:)` already defaults missing fields; an old seed decodes with `place = nil`.
- **The place is consumed once.** A seed is a restoration value. A place left in it would put a restored window back at the link target rather than where the researcher left it. Clear it after it is applied, as `seed.lens` is cleared on a project change (`ContentView.swift:1407-1411`).
- **Always `fresh(project:lens:place:)`.** Never `revealing`. The point is another window alongside the current one, as on the lens row.

**Timecodes, the one real choice.** In Safari a timecode link would open a page, while in
Bristlenose its left click *plays*. Seeding "the transcript at that moment" is a reasonable meaning
for *Open in New Window*. Offering nothing on timecodes is also defensible. The recommendation is
SEED, with this flagged for the owner.

### 4.4 Narrow `createWebViewWith` to the player, whatever happens to the menu

`createWebViewWith` should open the popout only for the player page
(`/report/assets/bristlenose-player.html`) and nothing else from the serve. Any other same-serve
URL becomes a seeded new window when a place can be derived from the route (`/report/sessions/{sid}`
and `#t-N` are exact), and is refused otherwise.

This fixes the left-click hijacks in §2 (threshold review, the featured-quote ⌘-click) **and** is
the safety net if menu editing ever stops matching (§5, risk 1). It is the single most valuable
change in this audit.

The popout also needs its own messages kept out of the report's `BridgeHandler`: drop
`navigation` posts whose `message.webView` is not the report web view. Today
`userContentController(_:didReceive:)` accepts any 127.0.0.1 frame.

### 4.5 Not in scope, named so it can be declined

Some targets have a place but are not links: Discussion timecodes, tapestry marks, the featured
quote card. WebKit offers them no link items, so nothing breaks. The bridge could *add* an *Open
in New Window* item for them. That is a new affordance rather than a correction, so it is left for
the owner.

### 4.6 Text services stay

Look Up, Translate, Search With…, Speech and Services on selected transcript text are the Mac's,
and every Mac app offers them. They are user-initiated, so removing them would be the
non-native choice. Search With… does send the selected words to a search engine. That is the
researcher's own explicit act, as it is in Mail. Noted, not changed.

## 5. Mechanism and its risks

**Mechanism.**

1. **Web side.** One capture-phase `contextmenu` listener for the whole SPA, embedded mode only, installed beside the navigation shims. It resolves `e.target.closest('[data-bn-place]')` and posts one message per right-click, `{type: "context-target", seq, place | null}`. It does not call `preventDefault`, so WebKit still opens its menu.
2. **Native side.** `BristlenoseWebView.willOpenMenu(_:with:)`. It takes the pending target if it arrived for this right-click (`seq` newer than the last menu and received within a short bound, say 250 ms). Then it edits the menu by identifier per §4.1. For SEED it keeps WebKit's *Open Link in New Window* item (its position and its WebKit-localised title) and sets its `target`/`action` to ours. Our action calls `openWindow(id: "main", value: .fresh(project:, lens:, place:))`, through a closure the window's `ContentView` hands the web view, since `openWindow` is a scene affordance.
3. **No target → the safe answer.** If no current target is pending, remove *Open Link in New Window* rather than leave WebKit's. The safe failure is a missing item, never the player hijack.

**This is the hook Reload Report already uses** (`ReportContextMenu.apply`, 21 Oct 2026), and the one the Screens session planned for Tidy. The Screens lens is adding
`postContextItems` (`frontend/src/shims/bridge.ts:356-366`, uncommitted at the time of this
audit), and `docs/design-screens.md` names `BristlenoseWebView.willOpenMenu` for Tidy. There must
be **one** `willOpenMenu` and preferably **one** message per right-click, carrying both the
page's items and the place. Otherwise native has to merge two posts whose relative order is also
unproven. Fold this into theirs; don't add a second override.

**Risks.**

1. **The identifiers are SPI** (§1). Raw values such as `WKMenuItemIdentifierOpenLinkInNewWindow` are stable in practice, but nothing promises them. If WebKit renames them, the edit silently matches nothing and the default menu returns. The narrowing in §4.4 means the dangerous item then opens a proper window or nothing, never the player. **Pin the identifiers with a test**: a probe-shaped test that opens the menu on an `<a href>` and asserts the identifier set. It fails loudly on an OS update.
2. **Message ordering is measured, not promised.** In 30 of 30 probe right-clicks (10, then 20 with the app's own `Task { @MainActor }` hop) the bridge post and its main-actor task ran **before** `willOpenMenu`. The margin was 7.9–71 ms, on an idle machine. Under load it is unproven. Both messages plausibly travel on WebKit's one web-process → UI-process connection, which would order them, but that is inference. The `seq` + staleness bound + remove-by-default design (step 3) makes a late or missing post cost a missing item, not a wrong window. The Screens Tidy item rides the same assumption, and its failure is the same harmless one.
3. **The Coordinator's `Task` hop.** `didReceive` defers to `Task { @MainActor }` (`WebView.swift:338`). The probe showed this costs about 0.1 ms. Storing the context target synchronously in `didReceive`, which is already on the main thread, removes the hop entirely.
4. **First-menu warm-up.** In the probe, the first right-click's post arrived but no menu opened within 0.4 s. A menu opened about 2.3 s after that click, and the second click produced no post. That reads as a cold web process whose late menu absorbed the second click. It is my interpretation, not a measured cause, but either way a test must warm up before asserting.
5. **Retargeting a WebKit item.** Changing `target`/`action` on WebKit's `NSMenuItem` keeps its localisation for free (the app declares 22 `.lproj`, `desktop/CLAUDE.md`). It does rely on WebKit not re-reading the item after `willOpenMenu`. If that ever bites, insert our own item titled with `desktop.menu.file.openInNewWindow` ("Open in New Window", already in 21 locales) at the same index.
6. **`openWindow` from AppKit.** The action fires in the web view, outside SwiftUI. The `ContentView` that owns the web view must hand it a closure that captures `openWindow` and the current project id, so the menu can never open a window on another project.

## 6. Findings that are bugs today, independent of the menu

1. **A left click on a threshold-review timecode opens the transcript in the player window and closes any playing clip** (`ProposalZoneList.tsx:125` `target="_blank"` → `createWebViewWith`). C, H. Fixed by §4.4.
2. **A report page in the popout writes into the main window's bridge state** (`BridgeHandler.handleMessage` has no sender check). C, H. Fixed by §4.4's sender filter.
3. **The Dashboard featured-speaker link lands at the top of the transcript.** Its anchor `#t-{sid}-{sec}` doesn't match `t-(\d+)$` (`Dashboard.tsx:389`, `:434`; `TranscriptPage.tsx:557`). C.
4. ~~**The transcript margin label (`#q-{id}`) goes nowhere on a left click** (`Annotation.tsx:35`). C.~~ Fixed 17 Oct 2026: the label and a new gutter mark lead into the Quotes lens (`docs/design-transcript-gutter.md`).
5. **Download Linked File / Download Image / Download Video are silent no-ops** (P in the probe; H in the app).

## 7. Hand checks owed (Debug build, about 5 minutes)

1. In Quotes, right-click a speaker badge and choose **Open Link in New Window**. Expected today: a *Video Player* window holding the transcript with no chrome, and the main window's lens capsule possibly moving to Sessions (finding 2).
2. Play a clip, then right-click a Sessions thumbnail and choose **Open Image in New Window**. Expected: the clip's window is replaced by the JPEG.
3. In Codebooks, open a threshold review and **left-click** a timecode (finding 1).
4. Right-click any internal link and choose **Download Linked File**. Expected: nothing; confirm there is no save panel.
5. In the player, right-click the video and choose **Open Video in New Window**. Expected: nothing.

## 8. The probe

`experiments/webview-context-menu/probe.swift` is a standalone AppKit program with no Bristlenose
code. It does three things:

- Serves a page from a loopback socket: an internal link, an http image, a `data:` image, text, an external link and a button.
- Sends synthetic `rightMouseDown`s and logs `willOpenMenu`'s items and the bridge post with timestamps.
- Fires each chosen item after the menu closes, then logs which delegate calls followed.

Build with `swiftc -O probe.swift -o probe`. It runs for about 20 s with a small window on screen.
The ordering figures in §5 come from a variant that adds the app's `Task { @MainActor }` hop in
the message handler and loops twenty right-clicks over the link, both images and the text.

## 9. Revised menus (24 Oct 2026)

### 9.1 The owner's rules

1. **The first item is the single-click action**, as Finder's first item on a folder is Open. Then
   extensions: the same in a new window, then other useful actions.
2. **Labels say exactly what happens** ("Open Transcript in New Window", not WebKit's "Open Link in
   New Window").
3. **A fragment offers both the transcript and the recording.** From a fragment seen elsewhere the
   most useful click is the transcript in context (read before and after); the second is the
   transcript parked in a new window while the analysis goes on; the third is the recording,
   from anywhere.
4. **The dashboard's featured quotes play on a click** (three high-value quotes, likely bound for a
   deck). On the transcript page the timecode plays and the timeline scrolls the page.
5. **v1 is one player per window** (it syncs to that window's scrolling transcript); several
   windows can each have their own. Measured from code 24 Oct 2026; not yet tried by hand.

### 9.2 Decisions

| # | Decision | By |
|---|---|---|
| D1 | A new window opens where the click goes; from a target whose click plays, it opens the transcript at the moment **and starts playing** in that window's player | owner |
| D2 | Copy Subject and Look Up stay on participants' images for now | owner |
| D3 | An emptied link menu falls back to Reload Report (it is never empty, since 21 Oct) | owner |
| D4 | Verbs: **Show in X** locates the clicked thing inside X; **Open X** opens X itself; the new-window item names its destination only when it isn't the clicked thing (Notes: "Show in Note" / "Open Note in New Window"; Music: "Open in New Window" / "Open Now Playing in New Window") | review, accepted |
| D5 | Plain **Play**, not "Play from 12:34" (Music, Photos, QuickTime; the moment is under the pointer, and a recording may be audio only) | review, accepted |
| D6 | **Reload Report only on page, text and `href="#"` menus**, not on link, image or video menus (Safari puts Reload only on the page background; View ▸ Reload Report covers the rest). Changes `ReportContextMenu.apply`, which today appends it everywhere | review; owner: "go with Safari" |
| D7 | External links: **Open Link · Copy Link — Share…**. No "in New Window" (the click already goes to the browser; the item would open the page in a Bristlenose window) and no Download | review, accepted |
| D8 | Player video: **Play/Pause · Mute — Enter Full Screen · Enter Picture in Picture — Hide Controls**, matching WebKit's and QuickTime's names | review, accepted |
| D9 | Menu bar agrees with the context menus (HIG: every context item is in the menu bar): Quotes ▸ **Show in Transcript** (was "Reveal in Transcript", a fossil by the glossary), with an Option-alternate **Open Transcript in New Window**; Video ▸ **Enter Full Screen / Exit Full Screen** (was "Fullscreen"). Values change, keys stay, 21 locales | review, accepted |
| D10 | **A blue timecode plays; a speaker badge opens the transcript.** "Time looks like video player UI, take me into that moment"; the badge is "that person and their whole conversation", at that moment. The quote-card timecode keeps playing, and its menu leads with Play | owner |
| D11 | Speaker badges get their own menu | owner |
| D12 | The quote card gets a menu of its own (§9.5) | owner |
| — | The review recommended making every bracketed timecode play, Signals and Codebooks included. **Reopened by D10** (§9.3) | owner, under discussion |

### 9.3 Open: the blue timecodes that don't play

D10 settles the quote card (§9.4 rows follow it). Two blue, bracketed timecodes look the same and
do not play: the **Signals expanded-quote timecode** (a plain link to the transcript, which
reloads the report) and the **Codebooks threshold-review timecode** (a new-window link, today the
player-window hijack). The review's recommendation, that they play too, now follows from D10.
If they do, their speaker badges need the transcript link a quote card's badge already has
(Signals' `PersonBadge` has no `href`; threshold review shows a plain code), or the transcript is
reachable there only by right-click. Diagnostics' "Listen at 12:34" buttons (Diagnostics on) read
as playing and open the transcript; same question, lower stakes.

### 9.4 Menus per target

"—" is a separator. The first item is the single-click action.

| Target | Click | Menu |
|---|---|---|
| Blue timecode that plays: quote card (Quotes, Discussion, Screens), dashboard featured and coverage, Screens version time | Play | **Play** — Show in Transcript · Open Transcript in New Window (the new window plays, D1) |
| Speaker badge on a quote card; Discussion moderator badge | Show in Transcript | **Show in Transcript** · Open Transcript in New Window (no Play on a person; the card's timecode is beside it) |
| Signals expanded-quote timecode; Codebooks threshold-review timecode | Show in Transcript today (§9.3: Play if they follow D10) | as the blue-timecode row if they play; else **Show in Transcript** · Open Transcript in New Window — Play. Drop threshold review's `target=_blank` either way |
| Sessions journey label | Show in Transcript | **Show in Transcript** · Open Transcript in New Window — Play |
| Paragraph timecode on the transcript page | Play | **Play** — Open Transcript in New Window (plays, D1) |
| Sessions `#N` | Open Transcript | **Open Transcript** · Open Transcript in New Window — Play |
| Sessions filename; dashboard session filename | Play | **Play** — Open Transcript · Open Transcript in New Window |
| Sessions thumbnail | Play | **Play** — Open Transcript · Open Transcript in New Window — Copy Image · Share… (D2 keeps Copy Subject and Look Up on images generally; the review would drop them here, where they are WebKit's leftovers) |
| Signals location heading; dashboard section nav; stat card naming a section | Show in Quotes | **Show in Quotes** · Open Quotes in New Window |
| Stat card naming a lens | Open | **Open** · Open in New Window (`menu.file.openInNewWindow`) |
| Quotes contents entry | Go to Section | **Go to Section** · Open Quotes in New Window |
| Screens screengrab | — | Copy Image · Copy Subject · Look Up — Share… |
| External link | Open Link | **Open Link** · Copy Link — Share… (D7) |
| `href="#"` actions; non-links; text; background | — | WebKit's page or text menu — Reload Report |
| Player video | Play/Pause | D8 |

### 9.5 Raised, not in scope

- **A menu on the quote card itself** (right-click the body, not a link): Star, Hide, Add Tag…, Copy
  Quote, Show in Transcript, the commands the Quotes menu already holds. The review's biggest gap
  (Mail's message menu); a new target, so the owner's call.
- **Copy Link stays out** until there is a link that survives a restart; a bare "12:34" on the
  clipboard names no session, so no Copy Timecode either.
- **Two players opened from two windows land on top of each other** (one saved frame,
  `"BristlenosePlayer"`), and the report listens on one shared BroadcastChannel name, which would
  cross-talk between windows if the player's fallback ever fired.

## 10. As built (24 Oct 2026)

On `main`, unreleased: `cdfd0b596` (only the player page opens the player window; the bridge drops
posts from any web view but the report's), `6e800f460` (the page declares each link's place,
`frontend/src/utils/contextPlace.ts`), `9325894ae` (`WindowSeed.place`), `05c40c315`
(`ReportContextMenu.swift`, the §9.4 menus), `08c7da805` (strings, Quotes ▸ Show in Transcript
and Open Transcript in New Window), then review fixes `699284ad8`…`002b6ee1d`. Where the build
departs from §9:

- **Threshold review's timecode opens the transcript in a new window** on a left click, in the
  app (a new tab in a browser), because a same-window visit would unmount the review dialog. Its
  menu leads with Open Transcript in New Window and offers no Show in Transcript (rule 9.1.1). §9.3
  (whether it should play instead) is still open.
- **The quote card's menu** is Star/Unstar · Hide · Add Tag… — Copy Quote — Show in Transcript ·
  Open Transcript in New Window, then WebKit's Back and Reload Report. Star's label follows the one
  rule Star acts by (`starActionIsUnstar` over the selection the card sits in) and counts ("Star 3
  Quotes"). Only a right-click on the card body moves focus; a link in the card gets the link's
  menu and leaves the selection alone. Selected text gets WebKit's text menu, no card items.
- **The place is never read from the href.** Each component declares it beside its click handler
  (`data-bn-place`, written in the Mac app only). The wire is pinned on both sides by
  `tests/fixtures/context-target-contract.json`.
- **The page numbers right-clicks per document**; the app resets its count when a new document
  loads (`ContextTargetSlot.newDocument`). Without that, every menu after ⌘R or a run's reload
  lacked our items.
- **A new window's place waits for the report itself** (`documentState == .spa`), not the first
  `isReady` the boot nets can fabricate (`WindowSeed.placeArrival`).
- **Not built:** Video ▸ Enter/Exit Full Screen (D9's second half; the player window's full-screen
  state is readable, so it can be done); the Screens version time offers Play only (its files were
  another session's); Copy Link stays out (§9.5).
- **Hand checks owed** (no test reaches WebKit's real menu): each §9.4 row; a new window from a
  playing timecode actually opens its player (it plays after an await, outside the gesture); two
  windows, two players; modifier-clicks on journey labels and stat cards (refused popouts); a
  right-click just after load on a busy page (250 ms window; the log says why when a target is not
  used); each macOS beta (the removal list is a denylist).

