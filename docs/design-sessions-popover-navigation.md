# Sessions lens — native popover navigation

**Status:** decided, building · **Scope:** embedded (macOS) only · **Mockup:** [`docs/mockups/sessions-popover-navigation.html`](mockups/sessions-popover-navigation.html) · **Review log:** 49 findings, plan-review 14 Aug 2026

## What this is

A **quick session switcher** in the macOS app's titlebar. It replaces the session
dropdown in the transcript's sticky header. The web sessions sidebar is removed
from the embedded build in the same change, because switching sessions was the
only thing it was reached for and it was never the right shape for that.

The framing matters for every decision below: this is **not** a sidebar being
demoted into a menu. It is a dropdown moving to the titlebar and gaining the
information density it always wanted. The "full fat" view — sentiment maps, user
journeys, source files — stays one click away as **All Sessions**.

Nothing here touches the CLI SPA. In a browser, the sidebar, the rails and the
sticky-header dropdown all stay exactly as they are.

## The governing principle

This surface is native, reached from a native toolbar, sitting beside a native
source list. It should **live in that world honestly rather than rebuild the
webview's compromises and approximations inside Swift.** It is the tiebreaker
for anything that comes up during the build — and note which way it cuts: it
argues for the real control *and against* porting the CSS badge colours.

## What ships

1. **The sessions left sidebar is gone in embedded mode.** Browser keeps it.
2. **The toolbar's `list.bullet` button on the Sessions lens opens a native
   popover** instead of dispatching `toggleLeftPanel`. On Quotes, Codebook and
   Analysis it still toggles the web panel, unchanged.
3. **The sticky-header session dropdown is hidden in embedded mode** — the
   disclosure affordance only. The `Session N` label stays.
4. **The Sessions lens restores the view the user left**, rather than always
   landing on the index.

## Popover contents

```
┌─ All Sessions ────────────────────────┐   ← returns to the grid
│  All 12 sessions                      │
├───────────────────────────────────────┤   ← one separator
│ [p1]  Session 1   Yuki                │
│                   26m · 10 Feb, 09:12 │
│ [p2]  Session 2   Priya               │
│                   21m · 10 Feb, 10:05 │
│       Session 6                       │   ← multi-participant
│ [p6]              Beth                │
│ [p7]              Participant         │      (italic placeholder)
│ [p8]              Participant         │
│                   19m · 11 Feb, 09:00 │
└───────────────────────────────────────┘
```

Three columns: participant badge, a fixed muted `Session N` column, then the
name(s) at a constant x. Single and multi-participant rows are structurally the
same shape; the multi case simply has more name rows. **No `#N` session badge** —
`#N` is on its way out of the product, and reintroducing it here would entrench
it.

## Decisions

### Interaction — a chooser, not a sidebar

| | |
|---|---|
| Open | Click the toolbar button |
| Commit | **Single click** on a row → navigate and dismiss |
| Keyboard | Arrows move a **highlight only**; Return/Space commits |
| Escape | Dismiss, no change |
| Not built | Press-drag-release; double-click-to-open-a-window |

This is the question that actually decides whether a source-list table in a
popover is a Mac idiom — the control class doesn't, the behaviour does. Two
consequences follow and both are load-bearing:

**Never navigate from `tableViewSelectionDidChange`.** It is the seductive wrong
place: a keyboard or VoiceOver user arrowing to row 8 would fire seven
navigations and seven WKWebView loads. Commit from `tableView.action` and an
explicit `keyDown` for Return/Space.

**Press-drag-release is not available and is not being faked.** It is an
`NSMenu` affordance; `NSPopover` has no equivalent, and building it means custom
event monitoring across a window boundary. We can't switch container to get it
(`NSMenuItem.view` loses the automatic highlight drawing, which is the whole
reason for the real capsule). Click-to-open/click-to-choose is what Calendar's
calendars popover, Photos' Add To and Tower's branch switcher all do.

Also explicit, because none of it is guaranteed by the frameworks: make the
table first responder by hand (`makeFirstResponder` from `viewDidMoveToWindow`
— SwiftUI does not hand it over), select the current session and
`scrollRowToVisible` so the first arrow press moves relative to where the user
is, implement `cancelOperation(_:)` rather than trusting Escape to the responder
chain (Tab cycles *inside* a popover, so Escape is the only exit), and restore
focus to the toolbar button on dismiss.

### Multi-participant rows stack, badges aligned to names

Real studies carry them — three sessions in twelve in the Fishkeeping study, and
the second and third participants are *unnamed*, because the pipeline only names
the first speaker.

Badges align to the names rather than sitting at the top of the margin. The
rejected alternative puts the first badge level with the title, so `p6` reads as
a label for *Session 6* — reintroducing the number conflation that dropping `#N`
was meant to remove — and leaves the last name with no badge. It needs no
table-inside-a-table: two columns sharing a row pitch is one `NSGridView`.

**The unnamed placeholder is muted *italic*,** not muted alone. That is the
system's own documented rule (`person-badge.css`: *"role word shown as a
muted-italic placeholder (PowerPoint-title convention) to read as editable, not
as a real name"*). Without the italic it reads as three people, one of whom is
called Participant — and under Edo, where `--bn-colour-muted` is a saturated
blue, colour-only de-emphasis reads as a link.

### Colours come from the system, never from the CSS palette

**Do not port `--bn-colour-badge-bg` / `-text` into Swift.**
[`design-native-colour-alignment.md`](design-native-colour-alignment.md)
§Principles rule 2 is explicit that Apple publishes no canonical hex for these —
they're dynamic across light/dark, accent, Increase Contrast and desktop tint,
and they shift across releases — so the CSS palette *samples* them with Digital
Color Meter and re-samples at OS bumps. The doc names the bitrot-proof answer as
bridging the live `NSColor` **into** CSS. Porting a sampled hex the other way
runs that pipeline backwards: a dated, lossy snapshot of a value we have live
access to in the language we are writing.

- **Default palette:** system semantics only — `.secondaryLabelColor`,
  `.quaternaryLabelColor`, `.labelColor`. They track appearance, Increase
  Contrast **and** `backgroundStyle` for free.
- **Edo:** `SidebarPalette` gains badge cases whose Default branch returns the
  system semantic and whose Edo branch reads a colorset — generated by
  `scripts/export-palette-swiftui.py` from `palette-edo.css`, per
  [`design-theme-divergence.md`](design-theme-divergence.md) Layer III, not
  hand-authored.

This is what makes the badge respond to selection. AppKit sets
`backgroundStyle = .emphasized` on a selected source-list cell and stock cells
re-tint; a CALayer chip ported from CSS is the one element that doesn't know
it's selected, which is why the mockup shows a grey chip floating inside the
capsule in light and a punched hole in dark. It also retires the measured
contrast failures (accent title on capsule was 2.91–3.12:1 against a 4.5:1 bar)
— system label colours are correct by construction and free.

**Note for QA — ways the mockup is knowingly stale** (it is a throwaway review
artefact; the decisions moved past it and it was deliberately not re-rendered):

- It draws the *unemphasized* capsule (grey wash, accent text). In a popover the
  table **is** the key view, so the real render is
  `selectedContentBackgroundColor` — a solid accent capsule with white label
  text. Wrong in kind, not degree.
- Its top row still says "Sessions index"; the decided name is **All Sessions**.
- Its single-participant rows still show the rejected run-on title
  (`Session 6 · Beth`); the decided layout is the three-column one in this doc.
- Its subtitle duration is `formatCompactDuration`; the decision is
  `DurationFormat.human`.

### The active row is the real AppKit source-list capsule

Not an approximation. The capsule colour is *internal to `NSTableView` and
matches no public UI-element colour* (verified by sampling all of them), so a
SwiftUI row cannot draw it. Having the real capsule means using the real
control.

**It stays a popover — the popover is the container, the table is the content:**

- **Container:** SwiftUI `.popover(isPresented:arrowEdge:)` on the toolbar
  button, exactly as `ExportMenuButton` presents the share menu.
- **Content:** `NSViewRepresentable` wrapping `NSScrollView` + **`NSTableView`
  with `style = .sourceList` and `selectionHighlightStyle = .sourceList`**,
  reusing `SourceListSelectionRowView` so the unemphasized treatment cannot
  drift from the sidebar. That type is currently `private` — extracting it is
  part of the work, so this change is not purely additive.

Precedent: Calendar's calendars popover (the exact shape — a source-list-shaped
navigation list, in a popover, from a toolbar button, standing in for a
sidebar), Photos' Add To, Music's Add to Playlist. *(The earlier draft cited
Notes' folder picker and Xcode's navigator popovers; both were wrong — Notes'
is a sheet, and Xcode's are menus.)*

**Ruled out — `NSMenu` with `NSMenuItem.view`.** It looks like the more native
answer, but a custom view loses the menu's automatic highlight drawing, so the
selection has to be hand-drawn — defeating the entire reason for the capsule.

**The three costs this does *not* dissolve for free.** The earlier draft claimed
keyboard nav, type-select and scrolling come free with the control. Scrolling
does. The other two become explicit code, and are budgeted as one small,
testable `configureSourceListTable(_:)`:

- `rowSizeStyle = .custom`, or `heightOfRow` is **silently never called**.
- **`tableView(_:heightOfRow:)`** — note `heightOfRowByItem` is an
  `NSOutlineView` method; porting the sidebar's shape verbatim gives a delegate
  that is never consulted.
- `makeFirstResponder`, or arrows and type-select silently do nothing.
- `tableView(_:typeSelectStringFor:row:)` returning names + codes + title,
  **plus** `tableView(_:nextTypeSelectMatchFromRow:toRow:for:)` doing
  token-level prefix matching (`SessionsPopoverSpec.typeSelectMatches`, pure and
  tested). The default matcher is *anchored* prefix only, so without the second
  method just the leading name is reachable — "beth" jumps, "p6" silently does
  not. Contract wrinkle, pinned by test: the delegate's range is
  `[startRow, endRow)` **with wrap**, and equal bounds mean one full sweep, not
  an empty range.

### Row metrics

Reuse **`ProjectCellSpec.rowHeight(twoLine:)`**, not a new constant and not the
export popover's 42pt. Its 32pt single-line base is measured against Finder /
Notes / Mail, and its own comment records that *no native two-line source-list
reference exists* — which is exactly our problem, already solved once. Sharing
the spec means the popover and the sidebar cannot drift, which is the anti-drift
property the real control was chosen for. Row height is `f(participantCount)`,
not a binary — there are at least three heights (0, 1, and n extra name rows).

The badge column is sized for `pN`/`pNN` — the 99.9% case, single-digit most
common. Pin the **column**, not the chip; a 3-digit code widens it without
breaking. The index row's glyph is `Image(systemName: "square.grid.2x2")` — the
same symbol `ExportPopoverContent` already uses — not a drawn chip.

### Subtitle

`DurationFormat.human` + a Swift `formatFinderDate` mirror: `26m · 10 Feb 2026,
09:12`.

**Duration is `DurationFormat.human`** (`26m` under an hour, `1h 3m` over) — it
already exists and already ships in the window subtitle. Deliberately *not* the
grid's `formatDuration` (`26:31`, which reads as a timecode) nor the sidebar's
`formatCompactDuration` (`1h 03`, a bare number after a middle dot). The grid is
the odd one out and should follow later. Its `h`/`m` abbreviations are
knowingly unlocalised — the Python source hardcodes them so the two surfaces
stay in lockstep (`DurationFormat.swift:14-16`).

**Date is parity with the Sessions grid's Start column**, including the cases
where that reads `00:00`. The mirror must reproduce `formatFinderDate` exactly:

- `en* → en_GB`, then `DateFormatter.setLocalizedDateFormatFromTemplate`.
  Hardcoding `en_GB` breaks 19 locales (ja wants `2026年2月10日`); passing the raw
  locale breaks *English* parity (`Locale("en")` gives `Feb 10, 2026`).
- The `Hm` template, not `jm` — the web pins `hour12: false`, so this
  deliberately overrides the user's 12/24-hour setting.
- Today/Yesterday via `localizedString(from: DateComponents(day: 0))`. **Not**
  `ProjectRow.formatBareDate`'s `relative()`, which the implementer will reach
  for and which returns "6 hours ago" where the contract wants "Today".
- `nil` → em-dash, matching `format.ts:22`.

A third, Python implementation exists (`utils/markdown.py:462`) and already
disagrees on the separator ("Today at 16:59"). The popover adopts the **TS**
contract. No cross-language fixture — this is independent local rendering, not a
wire contract, so a mismatch is cosmetic; literal Swift cases suffice.

**The underlying value is wrong and is tracked as a must-fix** (planning board,
§2 Broken · Must). `session_date` is the file's birth time — when the recording
was *saved*, at the end of the session. The drift equals the session duration,
so an 11:00 interview running 58 minutes displays as 11:58, and researchers
cross-reference against the calendar invite. Parity means one fix lands on both
surfaces at once. Note two *different* wrongnesses under one column headed
Start: media sessions show a **drifted** time, transcript-only sessions a
**fabricated** midnight — and the fabricated one looks more plausible.

### Names

`SpeakerResponse.name` is `person.short_name or person.full_name`, and
`short_name` in real data is the **given name** ("Yuki", "Beth", "Nina"). So the
popover shows given names — matching `SessionsSidebar`, which it replaces, and
narrower than the mockup suggests. A switcher is not a directory.

### Route memory lives in Swift

`switchToTab` keeps one meaning — go to the tab root — and only the affordances
that want restore opt in. The earlier draft put it in the SPA on the premise
that it would also change the toolbar tab picker; **that picker no longer
exists** (relocated into the sidebar by `LensRail`), so the real callers are the
AppKit outline's lens rows, the `LensRail` fallback, and **View ▸ ⌘1–5** — which
the earlier draft never mentioned. `desktop/CLAUDE.md:236` still describes the
segmented picker and needs the same correction.

Web storage is not an option regardless: `.nonPersistent()` is minted fresh per
`makeNSView` and the `.id` forces a remount on every switch and warm re-point,
so `localStorage` is wiped constantly — and reaching for a persistent store to
"fix" that would be a genuine cross-project leak.

**The remembered id is cleared, not validated.** Session ids are positional; a
re-analysis that drops a session renumbers the rest, so remembered `s3` restores
*successfully* to a different participant's transcript. The review proposed
validate-and-clear; what shipped is **clear-only**, on the same
`analysing → ready` transition that drives the report reload — renumbering only
happens via a run, so clearing at the run boundary covers the wrong-participant
case, and validation at restore time had no fetched list at hand (the popover
model belongs to the toolbar button, not the lens rows). The benign 404 half
lands on `TranscriptPage`'s error state with the toolbar switcher as the way
out. Memory also clears on project switch (`BridgeHandler.reset()`).

Also: **All Sessions** must navigate to `/report/sessions/` explicitly, or the
restore will bounce it straight back to the remembered transcript.

## Data source

**Swift fetches `GET /api/projects/1/sessions`** (project id is always 1 in
serve mode) with a **narrow `Decodable`** — required keys are exactly
`session_id` (navigation and route memory depend on it) and `session_number`
(the row title), each a deliberate whole-payload-failure decision; optional:
`session_date`, `duration_seconds`, `speakers[].{speaker_code, name}`. `role`
is **not** decoded — the participant filter keys off the `p` code prefix,
matching the server's own convention (`sessions.py:176`, `:317`), so decoding
the role string would be a dead field against the narrowness principle. Swift's
`Decodable` fails the whole payload on one missing required key and the
bundled-sidecar-lag class is live and documented; a narrow struct also makes it
structurally impossible for `source_folder_uri` or `source_files[].path` —
absolute paths encoding username and often client name — to reach the view.

Rejected: **direct DB read** (duplicates the schema and inherits the
`immutable=1` WAL trap — the count-blank-after-run bug, `1e1d608`) and **bridge
push** (makes a native toolbar surface depend on the webview having posted, and
it's empty before first paint).

### The (port, token) pair is the project identity

The earlier draft said authToken staleness was "structurally fixed by the reset
in `start()`". **That covers only the mismatched-pair 401 that bit `MiroAPI`.**
The mode that matters here is the *matched-but-stale pair*: a parked sidecar
stays alive, listening and accepting its own token, and the endpoint has no
project identity beyond the port — so a stale pair returns **HTTP 200 with the
previous project's participant names**. `selectedProjectPath` is the wrong key:
it is set synchronously at `ContentView.swift:701` while `switchProject` runs on
a later turn, so an `.onChange` fires *inside* the window.

All three rules are enforced **inside `SessionsAPI.load(identity:)`**, not left
to caller discipline:

1. Identity is a `@MainActor` **provider closure**, not a value parameter —
   `load` reads it at request-build time, and there is no `(port, token)`
   argument a caller could snapshot early.
2. Identity keys on the **port**, mirroring `ContentView.swift:2306`.
3. After the network await, `load` reads the provider **again** and compares
   ports (`SessionsFetchIdentity.shouldPublish`); an overtaken fetch returns
   `nil` — discarded, never rendered — and this applies to failures too: an old
   fetch's connection-refused must not mark the *new* project unreachable any
   more than its 200 may show the old project's names.

Never send the request with a nil token — a missing-header 401 and a
wrong-token 401 return the same body, destroying the one diagnostic signal.

**Extend `desktop/CLAUDE.md` with this**, not just this doc: it is the second
native bearer consumer and there will be a third.

## States

Three UI states, not eight. **200-with-zero-sessions must never merge with
failure** — it is a correct answer, it is what a just-imported project looks
like, and rendering it as the same nothing as a 401 teaches distrust of an
accurate screen.

| State | Shows |
|---|---|
| Loaded | The list |
| Empty (200, `sessions: []`) | "No sessions yet" |
| Unreachable (401 / refused / 404 / decode) | "Couldn't load sessions" + Retry |

The eight underlying conditions stay distinct in `os.Logger` (status code + the
middleware's `detail` string is what identified the MiroAPI bug). **All
Sessions renders unconditionally** — it is a route change needing no fetch, so
it is the escape hatch when the list fails. Do **not** copy `MiroAPI.status()`;
its own doc-comment forbids widening it to a context where "no token" and
"couldn't tell" must differ.

The failure string is a localised static from the `MessageKind` vocabulary held
in the popover's own `@State` — never `error.localizedDescription`, and never
routed into `ServeManager.state` / `outputLines` / `os_log` (those feed the
diagnostic popover's tail and "Copy error details", which users paste into bug
reports). `redactKeys(in:)` is the wrong tool here — it matches provider API-key
shapes, not `token_urlsafe` bearers and not names.

**Re-fetch on popover open.** That closes the stale-after-a-run case *and* most
of the sidecar-boot window in one mechanism.

## Implementation

Three commits, so reverting the last alone restores the sidebar.

**Commit 1 — additive.** Nothing removed; the sidebar still works.
1. `configureSourceListTable(_:)` — `.sourceList` style + highlight,
   `rowSizeStyle = .custom`, first-responder handoff. Postconditions unit-tested.
2. `SessionsPopoverList` — `NSViewRepresentable` over `NSScrollView` +
   `NSTableView`; `tableView(_:heightOfRow:)` via `ProjectCellSpec`;
   `typeSelectStringFor`; `cancelOperation`.
3. Cell views: All Sessions, single-participant, multi-participant
   (`NSGridView`, badges aligned to names, italic placeholder).
4. `SpeakerBadgeCell` — system semantics on Default, `SidebarPalette` on Edo.
5. Session fetch + narrow `Decodable`, port-keyed, post-await guarded.
6. Swift `finderDate` mirror.
7. i18n: seed `sessions.speakerPlaceholder.{participant,moderator,observer}` in
   all 20 locales (**they exist only in `en` today** — the reuse is not free),
   plus `desktop.sessionsPopover.*` for the new strings. Swift keys carry their
   namespace: `common.sessions.speakerPlaceholder.participant`. The count string
   goes through `I18n.plural(_:count:)`, reusing the reviewed four-form twin at
   `desktop.connectAgent.sessions_*`. Glossary row for "All Sessions".

**Commit 2 — rewiring.** Still nothing removed, and — deliberately narrower
than first planned — **only the affordances that don't guard the sidebar**: the
⌘⌥L/View-menu repoint, `[`-key gating, `allSidebarsShowing` and `panel-state`
move to commit 3, because they are consequences *of* the removal. That way
reverting commit 3 alone restores both the sidebar and every path to it,
leaving a coherent fallback (popover on the toolbar, sidebar via ⌘⌥L). In the
commit-2 window ⌘⌥L still toggles a sidebar that still exists, so no menu row
lies.
8. Toolbar button presents the popover on `.sessions`
   (`SessionsSwitcherButton`) with its own accessible name
   (`desktop.toolbar.switchSession`, seeded ×20 — it used to resolve to
   "Sessions" *on the Sessions lens*). Listens for `.showSessionsSwitcher`
   so commit 3's menu twin is one `NotificationCenter.post`.
9. `navigateToSession` bridge wrapper — the completion-handler overload with an
   explicit nil, NOT the `try await … in: nil, in: .page` spelling that
   silently resolves to the same overload and leaves the `catch` dead.
10. Route memory, Swift-side (`SessionsRouteMemory`, pure + tested):
    lens-activation callers (`activateLens` — sidebar rows, `LensRail`, ⌘1–5)
    restore; `switchToTab` stays pure so All Sessions reaches the grid.

**Commit 3 — the removal. This is the revert target.**
11. `SessionsSidebar` out of the embedded layout — gate `showSidebar`/`active`,
    **not** the `leftPanel` prop: `{leftPanel ?? <TocSidebar/>}` means
    `undefined` renders the *Quotes* contents panel.
12. Sticky-header `Selector` disclosure gated on `isEmbedded()`, label kept.
13. ⌘⌥L / View ▸ row on `.sessions` → post `.showSessionsSwitcher`; `[` key
    gated off the sessions route; `allSidebarsShowing` and `panel-state` stop
    counting a panel that no longer exists.

**Accessibility** (throughout, not a phase): one composed `accessibilityLabel`
per row, from the **model** not the truncated text field, badge immediately
before its name — that adjacency is the only thing conveying the pairing
non-visually. Commas, not middots (VoiceOver pauses on commas, reads nothing for
a middot). Mark badge subviews `accessibilityHidden`. The house pattern is
`ProjectRow.swift:635-698`; the AppKit sidebar port dropped it (one
`setAccessibilityLabel` in 2064 lines) and this surface can't inherit that.

**Tests.** Assert the *outcome*, not the helper: build through the same factory,
`reloadData()`, and assert `table.rect(ofRow:).height` **differs** between a
single and a stacked row — under any non-`.custom` style both report the same
pinned height, so this is the assertion that fails on the real bug. A pure
`heightForRow(session:)` test passes in both the working and broken states.
Parameterise over participant count. Plus: the port-guard decision as a testable
helper, the route-memory helper, and the SPA gate asserted **both** ways (the
browser keeps its dropdown *and* embedded loses it) — reuse
`SidebarLayout.test.tsx`'s `vi.mock("../utils/embedded")` pattern rather than
toggling the global, since `isEmbedded()` memoises. Explicit manual-QA lines for
keyboard nav and the error state; neither is headlessly testable and both are
obvious to a human in one keypress.

**Docs to true in the same change:** `desktop/CLAUDE.md:236` (stale segmented
picker) and `:256` + `docs/design-sidebar.md` §"Desktop embedded mode" (both
assert the toolbar toggles are the only path to the web panels — false for
Sessions after this), `docs/glossary.md` (new user-facing name),
`docs/platform-text-map.md` (desktop-only string inventory).

## Known and accepted

- **`list.bullet` means two things** — a momentary chooser on Sessions, a
  stateful toggle on the other three lenses. The sin is the divergence in *kind*,
  not the glyph, and fixing the menu twin (commit 2) is most of the cure.
- **Hover highlight: YES — reversed 14 Aug 2026 on first live QA.** The plan
  originally accepted no-hover because source-list *tables* never hover
  (Finder, Mail). The reversal is the role argument, and it is the correct
  reading of the governing principle: **the container's idiom wins over the
  control's.** This surface behaves as a menu — transient, light-dismiss,
  click-commits — and Apple's own menus and popover choosers track the
  pointer; the table is an implementation detail chosen for the capsule. Nor
  is hover here a webview approximation: it is Apple menu vocabulary. The
  treatment is the popover *family's* wash (`labelColor` at 6%, matching
  `ExportPopoverRow` and the All Sessions row), deliberately not the menu's
  accent capsule — which would collide with the grey capsule marking the
  *current* session and fork the hover vocabulary inside one surface.
  Implemented as `SessionsPopoverHoverRowView`, a **subclass** of the shared
  row view, so the project sidebar (a genuine source list) stays hover-free
  and the capsule anti-drift guarantee is inherited.
- **The `?embedded` query param** makes `isEmbedded()` true in a browser, so the
  documented dev-QA URL yields a report with no switcher at all. Gate the
  removal on the injected global, or note it in the QA doc.
- **`#N` in the Sessions index** is on its way out but not in this change.
- **Only Sessions loses its left panel.** The Quotes TOC, tag sidebar, codebook
  and signals panels — their toolbar toggles, ⌘⌥L behaviour and `[`/`]` keys —
  are untouched on those lenses, in the app and in the browser. The same
  popover treatment *may* one day suit them, but that is a separate decision
  per lens (Sessions' panel was a switcher; the others navigate within a
  view), recorded 14 Aug 2026 as explicitly not-yet.

## Not doing

Cross-language date fixture (cosmetic, not a wire contract). Eight-state error
taxonomy (three UI states). Prefetch-before-open (the open-triggered fetch
covers it). Regenerating the mockup's 34-session tail with stacked rows, and
ARIA-ing the mockup into an executable a11y spec — both are work on a throwaway.
