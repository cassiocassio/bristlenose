# Native interaction audit — shedding the web feel

_Status: research + audit capture, native-experiment branch (Jul 2026). Presentation/interaction only — engine and on-device-intelligence are out of scope for this branch. This doc is the spec input for the native "Design Lens" build; it does not itself change code._

The `native-experiment` spike asks how much of Bristlenose can stop being a WKWebView-hosted React SPA and become genuine native macOS, lens by lens, with the Python engine unchanged and the React SPA retained for non-Mac platforms. This doc captures the **interaction-behaviour** half of that question — the idioms that make a Mac user "smell something off" — as distinct from the visual element mapping (see the native-anatomy specimen and `design-native-colour-alignment.md`).

Two inputs, both Jul 2026:
- **Canon** — a fact-checked deep-research pass over the Mac-native discourse (Gruber, Siracusa/ATP, Simmons, Hansmeyer, Apple HIG, WebKit engineering). Claims tagged with verification confidence below.
- **Real-app audit** — a `what-would-gruber-say` pass over the actual CSS/JS and native shell, with file evidence.

## TL;DR

- **The native shell is already good.** Unified toolbar with correct zones, ~89-item menu bar with contextual dimming, the `NSOutlineView` source-list migration, seam-aligned paint, Find/undo/Cmd-E/Cmd-J bridged. The web-feel leaks are almost all _inside the WKWebView_, in the five report lenses.
- **They cluster around two things:** hover-reveal affordances and absent direct-manipulation idioms (context menus, single-click-select/double-click-open, drag-out).
- **Two priorities:**
  1. **Retire the hover vocabulary** in the report (underline-on-hover, blue hover-tint rows, opacity-fade action buttons) → selection-driven states. **Pure CSS/React, no shell work.** Closes the seam against the native `NSOutlineView` sitting one pixel away.
  2. **Ship right-click context menus** on quotes/sessions/badges — the single loudest tell. **But see the macOS-WKWebView constraint (§5)** — this is not the clean `WKUIDelegate` call it is on iOS.
- **Already correct, keep:** the app opts into `color-scheme: light dark` (`tokens.css:231`), so it inherits system light/dark, native form-control rendering, and named system colours for free — the highest-leverage web fix, already banked. Native scrollbars are un-overridden. Modifier-click new-tab guards and reduce-motion guards are present.

## 1. The principle (from the canon)

Native feel is **behavioural harmony with macOS conventions, not implementation language.** Gruber's "Mac-Assed Mac Apps" framing is explicit that an app can be native _code_ and still not a Mac app — his example is Slack. `[verified 3-0: daringfireball.net/2020/11/sketch_mac_app_mac_apps; audacious.blog/2020/tuned-for-the-mac]`

Corollary for us: writing the lens in SwiftUI does not by itself buy native feel; adopting the idioms does. And SwiftUI is not a free pass to correctness — the canon repeatedly flags it as not-yet-ready for load-bearing surfaces:
- Gruber, "SwiftUI only makes it easy to develop bad apps" (Jun 2026); >5 years in, still no API to detect an open context menu, blocking the standard focus ring around a right-click target outside `List`. `[sourced, unverified]`
- Apple's own SwiftUI Journal app: delete-word-then-undo doesn't restore the word — basic text editing unreliable. `[sourced, unverified]`
- Brent Simmons pulled SwiftUI out of NetNewsWire (2019) back to AppKit — "the future, but emphasis on future." `[sourced, unverified]`

This is the external backing for the project's existing **"99% SwiftUI; drop to AppKit where the native result is structurally unreachable"** rule (`design-desktop-sidebar-appkit.md`). The market won't enforce native craft — it's a self-imposed standard.

## 2. Three-way taxonomy (the checkable canon)

Each item tagged **native-do / web-drop / electron-avoid** and by reachability: **[web]** fixable inside the WKWebView (CSS/JS), **[shell]** needs the native shell.

| # | Idiom | Tag | Reach | Source / confidence |
|---|-------|-----|-------|---------------------|
| 1 | Menu bar lists **all** commands; dim-not-hide unavailable ones | native-do | shell | HIG, verified 3-0 |
| 2 | Windows resize/hide/move/full-screen | native-do | shell | HIG, verified 3-0 |
| 3 | Adopt user **accent colour** + **system fonts**; never hard-code system colour values (use `NSColor`/`Color`) | native-do / web-drop | shell (chrome) + web (CSS system colors) | HIG, verified 3-0 |
| 4 | `color-scheme: light dark` on root → auto light/dark, native form controls, scrollbars, system colours. WebKit does **not** auto-darken — opt-in is mandatory | native-do | web | WebKit blog, verified 3-0. **Already done: `tokens.css:231`** |
| 5 | Default **arrow** cursor on buttons/controls; pointing-hand reserved for **links** | web-drop | web | Apple "Pointers in macOS", verified 3-0 |
| 6 | macOS density: system font is 13**pt**; the CSS 16px default reads oversized | web-drop / native-do | web | verified 3-0, **caveat:** points≠pixels — 13pt ≈ 17.3 CSS px, not literal `13px` |
| 7 | Settings as native panes (System-Settings grid), not JSON/text config | native-do / web-drop | shell (web can still avoid JSON-config) | MacStories Nova review, verified 3-0 |
| 8 | Document **proxy icon** in the title bar, shown by default (not hover-hidden) | native-do | shell | Gruber, verified 3-0 |
| 9 | Electron's cross-platform uniformity is itself the defect — "equally wrong everywhere" | electron-avoid | n/a | Gruber, _sourced, unverified (infra error, not refuted)_ |

**Refuted, excluded:** "native editors reuse the standard Mac file-browser sidebar" (vote 1-2). Nova ships its own sidebar; reimplementing a sidebar is not disqualifying.

## 3. Bristlenose real-app audit (ranked tells, with evidence)

Inside the WKWebView, ranked by how loudly each breaks native feel. Fix location tagged.

1. **No right-click context menus anywhere in the report** — `onContextMenu` appears **zero times** in `frontend/src/`. Right-click a quote/session/timecode → the default WKWebView browser menu (Reload, Inspect Element), because `WebView.swift` has no context-menu intercept. The verbs already exist (Star, Hide, Tag, Copy, Open) and the `bridgeHandler.menuAction()` return-path is built. **[shell — see §5 constraint]** _Loudest tell._
2. **Hover-reveal action buttons** — `atoms/toggle.css:35` (`.hide-btn opacity:0→1` on `.quote-card:hover`), `molecules/name-edit.css:21` (`.name-pencil`), `molecules/editable-text.css:70` (crop handle). Invisible until pointed at; unreachable by keyboard/VoiceOver; no trackpad-tap analogue. Note the inconsistency: `.star-btn` is always visible, hide/pencil/crop fade. **[web]** _Contested — see §6._
3. **Blue underline-on-hover navigation** — `organisms/toc.css:36`, `atoms/timecode.css:18`, `organisms/blockquote.css:60`. Reads as hyperlinks; native source-list rows show **selection**, not underline. Already queued in `design-native-colour-alignment.md` §Deferred ("neutral hover"). Loud because it sits beside the native `NSOutlineView`. **[web]**
4. **Hover-tint on list rows** — `--bn-colour-hover` at `sidebar.css:773` (`.session-entry`), `:917` (`.signal-entry`), `:455` (`.toc-link`). macOS source lists don't tint on hover; rows react to selection/click, not pointer presence. **[web]**
5. **Single-click navigation, no select/open split** — `SessionsSidebar.tsx:181`, `TimecodeLink.tsx:23` navigate on plain single-click; `onDoubleClick`/`dblclick` = **zero hits** in `frontend/src/` and `theme/js/`. The Finder idiom is single-click selects, double-click opens. `QuoteCard.tsx:361` **already** does Finder-style single-select with Cmd/Shift — the model exists, just isn't on navigational rows. **[web]** (double-click-to-open-in-**window** touches the shell)
6. **CSS-drawn checkboxes** — `atoms/checkbox.css` (`-webkit-appearance:none` + hand-drawn tick). The native checkbox animates, respects Increase Contrast + system accent. **[web]**
7. **Custom animated tooltips** — `Tooltip.tsx` + `atoms/tooltip.css` (300ms float-down). Label-only cases should use native help tags (`.help()`); reserve custom for genuinely rich content. **[web]** _Lowest rank; partly a sane existing convention._

**Correctly handled (credit):** scrollbars un-overridden (native overlay), modifier-click new-tab guards present (`QuoteCard.tsx:301` etc.), reduce-motion guards on animated states (`timecode.css:46`), `color-scheme` opt-in (`tokens.css:231`).

## 4. Missing Mac idioms (absence a Mac user feels)

All **[shell]** unless noted.

- **Rich context menus** — §3.1 / §5. Highest priority.
- **Single-click-select / double-click-open** on navigational rows — model exists in `QuoteCard`; propagate to sessions. Double-click-opens-in-new-window is the Notes pattern (`File ▸ Open in New Window` exists at `MenuCommands.swift:282` but no double-click gesture bound). **[web + shell]**
- **Drag-from-inactive-window / drag-out** — no `draggingSession`/`NSDraggingSource` in Swift, no HTML5 `draggable` drag-out. Drag a quote to Keynote, a thumbnail to Finder. Includes the click-through-drag subtlety (start a drag from a background window without focusing first).
- **Full Keyboard Access** — good single-key review shortcuts + `:focus-visible` rings, but the hover-reveal affordances (§3.2) are an FKA hazard by construction, and Tab-traversal across the native↔web seam is flagged open in `design-desktop-sidebar-appkit.md` §6. **[web + shell]**
- **Proxy icon** — no `representedURL`/`isDocumentEdited`. Projects _are_ folders on disk (real `file://` path; the sidebar has "Show in Finder"), so a proxy icon is semantically honest. `window.representedURL = projectFolderURL`.
- **Window state restoration** — `@AppStorage` carries last project + settings, but no `@SceneStorage`/`NSWindowRestoration`; window frame, active lens, and scroll position don't restore across relaunch. **Doc-vs-reality gap:** `macos-ux-checklist.md:23` claims `@SceneStorage` "✓ scoped" but it isn't implemented (and `desktop/CLAUDE.md` notes `@SceneStorage` doesn't survive relaunch for debug-signed apps, which is why `@AppStorage` carries selection). Update the checklist.
- **Quick Look (Space)** on session/clip files — `macos-ux-checklist.md:28` marks it nice-to-have; not built.

## 5. The context-menu question (a grey-area specimen)

The real-app audit calls context menus the highest-value native investment. The nuance, sharpened: **the question is not whether we can have a custom right-click menu — we can, easily — it's whether that menu is *native-rendered* or *web-rendered*.** Two independent things:

1. **Suppress-and-replace (web route) — fully available, proven.** Intercept the `contextmenu` event, `preventDefault()` the browser's default menu, render your own menu in the web layer. This is exactly what Miro and Figma do inside their WKWebView/canvas surfaces. A *custom* context menu on quotes/sessions/badges is never in doubt and needs no shell work — it's `onContextMenu` in React. The only cost: a web-rendered menu lacks native `NSMenu` vibrancy/animation/styling, so it reads _slightly_ web-feel.
2. **Native `NSMenu` (shell route) — the constrained one.** Making the right-click surface a genuine AppKit menu. macOS WKWebView exposes **no documented public delegate** for this, unlike iOS's `webView(_:contextMenuConfigurationForElement:)`. `[sourced: mjtsai.com 2022, unverified — infra error, not refuted]` The workaround is to **subclass `WKWebView`** and override AppKit's `willOpenMenu(_:with:)` / `menu(for:)` to build the `NSMenu`, reading a `data-*` id the web layer stamps on the right-clicked element (web→native hit-test handshake). Real, but not a clean API.

So the priority is **not** "can we ship context menus" (yes — web route, today) but **"is the native menu worth the subclass fight?"** That makes it a clean **grey-area / holding-the-tide** entry for the published audit: the pragmatic web menu ships now and is Miro-proven; the native `NSMenu` is the mac-assed path with no public API and a hit-test handshake to build. **Verify the subclass route before committing to native rendering** — it decides whether "native context menus" is a shell afternoon or a fight. Shipping the web menu first is a legitimate interim, not a failure.

Other **unverified-but-plausible** WKWebView defects to re-verify before relying on them (all `craft.do` "Thinking Outside of the WKWebView", infra-errored during verification):
- Two-click focus (first click focuses the web view, second focuses the field) — Craft added a hover gesture to pre-focus.
- Loss of native scroll deceleration/momentum after a trackpad drag.
- Standard Cmd shortcuts (e.g. Cmd+scroll zoom) not passing through by default.

## 6. Open decision — hover-reveal vs always-visible

**Do the quote card's star/hide/edit-pencil/crop affordances stay hover-revealed, or move to always-visible / selection-driven?** Recorded as open, not resolved.

- **The field is split.** Reeder/NetNewsWire hover-reveal for a calm list; **Mail/Finder tie affordances to _selection_, not hover.** The Mac-canonical trigger is selection, not hover.
- **HIG is silent** on hover-reveal specifically, but its context-menu rule ("always make context-menu items available in the main interface too") points at not hiding the only path to a verb.
- **The project has a standing lean toward restraint** — `feedback_absence_is_information` ("render chrome only for exceptions") and the documented Notion-convention note in `theme/CLAUDE.md` (pencils hide during edit). A reviewer shouldn't overturn that unasked.
- **The parsimonious path that breaks no rule:** show actions on the **selected** row (Mail model), always mirror in the right-click menu, keep hover as an _additional_ nicety — never the only reveal. Reuses `QuoteCard`'s existing selection model; passes FKA (selection is keyboard-reachable, hover isn't).

_Decision owner: user. Default if unspecified: keep current hover behaviour (honours the standing lean) but add the context-menu mirror so no verb is hover-only._

## 7. Prioritised actions

**Now — pure web layer, no shell, closes the seam (all [web]):**
1. Retire underline-on-hover (§3.3), hover-tint rows (§3.4) → neutral selection states. Cashes `design-native-colour-alignment.md` §Deferred.
2. Remove `cursor:pointer` from non-link controls (canon §2.5).
3. Drop the CSS checkbox override (§3.6) → native control.
4. Propagate `QuoteCard` single-select + add `onDoubleClick` to sessions/timecodes (§3.5).
5. Swap label-only custom tooltips for native `title`/`.help()` (§3.7).

**Native shell — higher value, more work:**
6. Context menus on quotes/sessions/badges — **verify §5 route 1 first.**
7. Proxy icon (`representedURL`), real `@SceneStorage` frame+lens+scroll restoration, double-click-open-in-window, drag-out, FKA seam traversal.

**Housekeeping:**
8. Correct `macos-ux-checklist.md:23` (`@SceneStorage` claimed done, isn't).

## Provenance

- Canon: fact-checked deep-research, Jul 2026. Primary sources — Apple macOS HIG, WebKit engineering blog, Apple API docs, Daring Fireball (a requested anchor). Confidence tags inline; 15 claims confirmed 3-0, 1 refuted, 9 unverified due to verifier infrastructure errors (plausible, source-attributed, flagged as such — several are the most decision-useful hybrid-specific items, esp. §5).
- Real-app audit: `what-would-gruber-say`, Jul 2026, grounded in `bristlenose/theme/` CSS, `frontend/src/`, `desktop/Bristlenose/`, held against `macos-ux-checklist.md`, `design-native-colour-alignment.md`, `design-desktop-sidebar-appkit.md`.
- Related: `design-native-vs-web-surfaces.md` (which surfaces go native), `design-native-colour-alignment.md` (seam alignment), `design-native-typography-grid.md` (type), the native-anatomy specimen (visual element A/B mapping).
