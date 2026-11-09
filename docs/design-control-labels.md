# Control labels never truncate

**Owner rule, 9 Nov 2026, web and macOS, all 21 locales.** A button, tab,
segmented control, pop-up, toolbar pill, checkbox or clickable chip shows its
whole label. Not an ellipsis ("Show Det…"), not a clip by its container, not a
row pushed off the edge of a dialog. The fix is always the layout, never a
shorter translation: abbreviating a locale value to fit moves the defect into a
locale file.

**Why this needs writing down:** every review reads English, and English fits.
German, French, Polish, Russian and Catalan run longer (about 10% longer on
average across the locale files, and far more on single labels). The defect
that set the rule shipped in English anyway: the Mac failed pane showed "Retry"
beside "Show Det…" in a detail column with hundreds of points to spare.

## The cause, mostly: layout that did more than the job needed

The 9 Nov audit (Swift and web, followed by an Occam review of every site and
every fix) found that the clipping in **roomy main-content surfaces** was
self-inflicted, by layout written to solve some other problem:

1. Our own `HStack` inside a stock control's slot. `ContentUnavailableView`'s
   `actions:` slot handles one button correctly, but a plain `HStack` of two
   comes out equal-width and cut. That was the failed pane and BootView's
   failure pane. (Measured with an `NSHostingView` probe: the total width is
   the same either way; it is only divided equally.)
2. A hard-coded width on a control: `.frame(width: 240)` on the Settings folder
   pop-up in a 660 pt pane, which cut Russian "Last location used".
3. A hard-coded width on a column of labels: `width: 11rem` on the web Settings
   nav. (Its `overflow-y: auto` silently makes `overflow-x` auto too, so it
   scrolled sideways instead of growing.)

**Tight surfaces are different, and are allowed to be tight.** Popovers
(280–360 pt) and sheets (420 pt) are narrow on purpose, so prose wraps and the
surface stays compact. There, the fix is not more width; it is deciding what
gives way.

## The defaults

1. **Never write a width on a control or on the row that holds it.** Let the
   label size it. If the row needs to keep its shape, give it a floor (and, for
   user data, a ceiling): Swift `.frame(minWidth:maxWidth:)`, CSS
   `min-width`. Not `.frame(width:)` or `width:`.
2. **Fixed widths belong only to popovers and sheets**, where prose has to
   wrap. Inside them the text wraps and the buttons keep their width.
3. **A row that might not fit stacks.** On the Mac, `ViewThatFits { HStack;
   VStack }` with the default action first in the stack, as a stacked
   `NSAlert` reads (`ProviderProblemPill.swift`,
   `ContentView.swift` SpotlightConfirmSheet). On the web, `flex-wrap: wrap`.
   Never hyphenation or `overflow-wrap: anywhere`: they turn a cut label into
   a broken one.
4. **Only the researcher's own words may truncate**: a tag, file, folder,
   project or speaker name. Our words (any i18n string) never. On the web an
   element that truncates user content says so with
   `data-truncates="user-content"` (`TagRow.tsx` is the first); the e2e walk
   exempts that marker and nothing else.

## The patterns, per platform

**macOS (SwiftUI / AppKit)**

| Situation | Write |
|---|---|
| One button in a `ContentUnavailableView` `actions:` slot | The bare `Button`. It sizes to its label. |
| Two or more buttons in that slot | `HStack(spacing: 12) { … }.fixedSize(horizontal: true, vertical: false)` |
| A button beside wrapping text in a fixed-width popover or sheet | `.fixedSize(horizontal: true, vertical: false)` on the button; the text wraps |
| Buttons that may not fit even alone | `ViewThatFits(in: .horizontal) { HStack { … }; VStack(alignment: .trailing) { … } }` |
| A toolbar status pill's label | `.fixedSize(horizontal: true, vertical: false)`, not `.lineLimit(1)`: a toolbar item that will not shrink goes to the overflow menu (»), as it should |
| A pop-up whose title is user data | A floor and a ceiling, with the data's own `.lineLimit(1).truncationMode(.middle)` |

Always `.fixedSize(horizontal: true, vertical: false)`, never bare
`.fixedSize()`: fixing the height too breaks a `ViewThatFits(in: .vertical)`
height ladder (`ProjectDiagnosticPopover.swift` documents the trap).

**Web (CSS / TSX)**

| Situation | Write |
|---|---|
| A row of controls that can outgrow its box | `flex-wrap: wrap` on the row (`.tag-sidebar-actions`, `.feedback-sentiments`) |
| A column of nav labels | `min-width`, not `width`, so the column grows to its longest label |
| A control's own label | No `text-overflow: ellipsis`, no `nowrap` + `overflow: hidden`, no fixed `width` / `max-width` / `flex-basis` |
| A clickable chip holding user content that may ellipsize | Mark it `data-truncates="user-content"` |

## What was tried and rejected (9 Nov 2026)

- **A `ButtonRow` view plus a Swift source lint that demanded it.** The two
  existed mostly to justify each other, the lint enforced a rule ("use
  `ButtonRow`") rather than the outcome, and it could see 2 of ~20 sites.
  Stripped.
- **Letting each Feedback rating label wrap under its face** to keep the 1–5
  scale on one row. Measured, it fails: the German labels are single words
  ("Frustrierend", "Ausgezeichnet"), so the row still ran past the card. The
  row wraps instead; English stays on one row.
- **Breaking long words in the Settings nav** (`overflow-wrap: anywhere;
  hyphens: auto`). Replaced by `min-width`, the simpler rule. Note that the
  walk could not show this nav ever cutting a label at its viewport, so that
  change is a precaution, not a proven fix.

## How this is checked

- **Web, mechanically:** `e2e/tests/button-labels.spec.ts` walks every lens in
  en/de/fr/pl/ru, opens the Feedback dialog (+da) and the Settings dialog (+fi),
  and narrows the tag sidebar to its 200 px floor with the handle's own Home key
  (+ca). It fails on a label cut inside a control and on a control pushed past
  the box that clips it, and it carries two proof cases showing it can fail.
  It only sees what it opens: **add each new dialog, popover or menu to the
  walk.** Feedback missing from the footer fails the test rather than skipping
  it.
- **macOS: review only, for now.** `what-would-gruber-say`, `ux-critique` and
  `i18n-review` carry the rule as a blocking finding. There is no Swift outcome
  gate. If one is wanted, the shape is the 9 Nov probe turned into a test:
  render the panes in German and French and assert each button is at least as
  wide as its label's ideal width. Not a source lint.
