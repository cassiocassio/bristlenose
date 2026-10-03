---
status: parked
updated: 3 Oct 2026
---

# Quotes filter menu

A future toolbar button on the Quotes lens: a menu of curation filters the
researcher composes, Mail-style. Decided in conversation on 3 Oct 2026 from
Photos' filter menu as the reference. **Nothing here is built, and nothing
here changes today's toolbar**: Star stays as its own toggle
(`design-desktop-nav-toolbar-rearrangement.md` §4.3, rev 3 unchanged).

## 1. Decisions

- **Tags are out.** Tag filtering is the Tags inspector, settled UX and its own
  body of work. Sentiment and intensity are badges in that same world, so they
  are out too.
- **Mail's model, not Photos'.** Photos' menu is a radio, one scope at a time.
  Ours compose, so the rows are checkboxes that AND, the button tints while any
  is on, and the lens subtitle names the active filters. The subtitle already
  does this for Starred (`quotesSubtitle`: "Starred quotes · 12"); a filter
  extends that line, it does not add chrome.
- **One filter state, several doors.** The menu, the Star toggle, the View menu
  and later the search field's curation recogniser (`design-search.md` §4,
  the *starred / hidden / edited* row) all write the same predicate, the single
  `filterStateOf(store)` that search's P2 introduces. A facet chosen by typing
  ticks the same row the menu ticks; it does not become a chip. Chips are for
  entities (a person, a tag). The field holds what you typed, the menu holds how
  you narrowed.
- **A row appears only when it can say something.** No AutoCode proposals, no
  *Needs review* row; nothing hidden, no *Show hidden* row. Photos does this
  with *Captured by Me*.
- Glyph `line.3.horizontal.decrease`, in the actions capsule after Export.
  Never a hand-rolled More menu; the system overflow handles narrow windows as
  §4.3 already says.

## 2. Rows

| Row | Predicate (state the SPA already holds) | Status |
|---|---|---|
| **Needs review** | the quote has a pending AutoCode proposal: `store.proposedTags[domId]` non-empty | plan, §3 |
| **Edited by me** | `store.edits[domId]` set | yes |
| **Show hidden** | `store.hidden[domId]` | candidate, §4 |

All three are client-side predicates over the quotes store. No server change,
no new route. The offline export carries no proposals and is read-only, so
*Needs review* never appears there and *Edited by me* is a plain read.

## 3. Needs review — the plan

**What it is.** The AutoCode review queue as a view of the Quotes lens. Today
proposed badges sit on cards scattered through sections and themes and the
researcher scrolls for them. The filter collects them.

- **Predicate.** `proposedTags[domId]?.length > 0`, evaluated inside the one
  `filterStateOf(store)` (search P2). Build that refactor first; it replaces
  the six hand-built `FilterState`s and is where every row of this menu lives.
- **Subtitle.** "Needs review · 23", the Starred branch of `quotesSubtitle`
  generalised to a list of active filters joined by the interpunct.
- **Leaving the view.** Accepting or denying a quote's last proposal makes it
  stop matching. It must not vanish under the pointer: a card keeps its place
  until the filter is next changed or the lens is re-entered. One rule for
  every row, and the same answer §4 needs. Check what Starred does today when a
  quote is unstarred inside the starred view, and align.
- **Menu.** SwiftUI `Menu` of `Toggle`s on the Mac; a popover menu of
  checkboxes in the browser. View ▸ Filter ▸ mirrors it, and *All Quotes /
  Starred Quotes Only* fold into that submenu at the same time. No keyboard
  shortcut; shortcuts are earned.
- **Bridge.** `quotes-filter` (web → native) grows a `filters` field listing
  the active row ids; native → web gains `setQuoteFilter {id, on}`. Swift mirror
  plus a round-trip fixture, per the wire-contract gotcha in `CLAUDE.md`.
- **i18n.** Row labels and the subtitle noun in all 21 full locales, not
  `zh-Hant-HK`.
- **Tests.** The predicate in `filter.test.ts`; the subtitle string; the bridge
  round-trip; a vitest that the row is absent when there are no proposals.

Build order: P2 predicate refactor → menu with *Needs review* and *Edited by
me* → *Show hidden* once §4 is decided.

## 4. Show hidden — the open UX

The predicate is one line. The UX is not, which is why this row waits.

"I hid that somewhere and have no idea" is a real job, and today the only way
back is the bulk restore (`unhideQuotes`). Three questions before it is drawn:

1. **Hidden only, or everything including hidden?** The job is finding the one
   you hid, which argues for hidden only.
2. **Unhide per card, then what?** The card needs an Unhide control, and after
   it the quote no longer matches. Same rule as §3: it keeps its place until
   the filter changes, so a run of unhides does not reflow the list each time.
3. **How is a hidden card marked** so it is never mistaken for a live one? Mail
   draws Show Deleted messages in place, muted. The `.bn-hidden` defence in
   depth (`design-html-report.md`) must stay: a hidden quote in this view is
   still hidden to every export and count.

## 5. Considered and rejected, 3 Oct 2026

| Row | Why not |
|---|---|
| Sentiment, Strong only | live in the tag world, out by decision |
| Has video | the clips folder *is* that list, once exported |
| Unprompted (no moderator question) | not useful enough for a row |
| Kept by me (pinned) | redundant with Starred and Edited, since any touch pins |
| New since last analysis | not useful enough; needs a previous-run stamp nothing stores |
| Persona / role | not useful enough for a row |
| Screen-specific vs general | that is Sections versus Themes, navigation not filter |
| Badge removed, moved by me, quote length, session date or language | audit trivia |
| Session, participant, timecode, section, theme | many-valued; search recognisers, not menu rows |

## 6. Relation to search

`design-search.md` plans a *curation state* recogniser whose rows are exactly
these facets, and §5 there says tokens "never change the sidebar's state". This
doc adds a door onto the same state, nothing more: D1–D8 stand. The one shape
question the two share is the leaving-the-view rule in §3, which belongs in
the predicate and so should be settled before search's P2.
