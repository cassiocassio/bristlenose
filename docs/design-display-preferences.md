# Display preferences: how the Quotes lens looks

**Status:** control surface built 3 Nov 2026 (web and Mac, uncommitted; see TODO.md). Density is continuous (0 to 1, Normal at 0.5; a slider on the Mac, three named stops on the web); its end values and the Break default are still to decide. Mac popover: icon rows for Layout, a slider for Density, plain left-tick rows for Break and Focus Mode (owner, 3 Nov 2026). Variants considered: `mockups/display-popover-variants.html`. Proposal from a long design session with the owner. A **mockup** with real Talismanic quotes exists: [mockups/quotes-display-options.html](mockups/quotes-display-options.html) (the right-hand panel there is a lab, not product). Whether any of this lands before the 24 Nov 2026 submission is the owner's call.

**Build split (3 Nov 2026, owner):** the line-break display **algorithm** (`frontend/src/utils/breakParagraphs.ts`, the lab, the research) stays with the Quote formatting session; the **Display control** (popover, store, CSS, `QuoteCard` integration, the Mac popover) is built by a separate session from a private handoff. The nine `toolbar.display*` strings are already in all 21 locales. Compact / Normal / Spacious may ship roughed in for the Sunday 8 Nov 2026 release; Break long paragraphs ships off until the owner decides its default.

**Supersedes:** the "Content density setting (separate feature)" section of [design-responsive-layout.md](design-responsive-layout.md) (compact / normal / generous, `data-density` on `<html>`, vanilla `density.js`). It was never built, it scoped to `<html>` (which moves the chrome), and it was written for the frozen JS.

## 1. Why

A researcher using the Quotes lens said the screen is **"overwhelming to read, very intense"**, and one user (Bettina) found the masonry grid difficult. The owner's aim: **make it easier to parse**. There are three parsing jobs, each with its own lever:

| Job | The question | Lever |
|---|---|---|
| Parse the words | where do the phrases and thoughts fall? | breaks inside a quote |
| Parse the card | who said it, where, what is it tagged? | hierarchy and quietness (Focus Mode already does this) |
| Parse the screen | which quote do I read next? | layout, density, fewer things at once |

On the 109 Talismanic quotes the median quote is **57 words** (8 to 147), and 33 of them are over 70 words: long walls of text, drawn in a grid of cards about 5 words wide. That is a measured cause of the intensity; it is not the only one.

## 2. The cluster: four independent settings

| Setting | Axis | Values | Status |
|---|---|---|---|
| **Layout** | arrangement | Columns (today's grid, masonry in WebKit) · Single column | new |
| **Density** | space | Compact · Normal · Spacious | new |
| **Break long paragraphs** (working name) | rhythm | on · off | new; the v1 spec is §4 |
| **Focus Mode** | attention | on · off | **shipped** (`z`, toolbar button, Mac View menu) |

They are independent and each has a quick toggle. The control is one **Display** button on the toolbar that opens a popover. In the Mac app the web toolbar is not rendered (`Toolbar.tsx` returns `null` when embedded), so the Mac gets a native toolbar item and a native popover; the browser gets the web one. Both read one shared contract (§6).

**Scope rule.** Density and Layout apply to **quote content only**: the cards and the lens area. The header, navigation, toolbar, contents list and sidebars never change size. That is what separates this from zoom, which scales everything.

## 3. Layout and Density

**Layout.** Columns is `responsive-grid.css` untouched: `auto-fill` columns of `--bn-quote-max-width` (23rem), upgraded to `display: grid-lanes` masonry where supported (the Mac's WKWebView always; other browsers show a rectangular grid). Single column holds the whole group (heading, hidden-quotes control, description, cards) to **`--bn-max-width` (52rem)**, the width Discussion already uses, so there is one reading width in the product, not two (decided 3 Nov 2026; an earlier 44rem token was dropped). Full width was weighed and not chosen. Single column also makes keyboard order trivial: in masonry, DOM order and visual position diverge (`spatialNav.ts`). An explicit setting wins over any automatic behaviour. It is left-aligned and leaves the right of a wide window empty, as Discussion does.

**Density.** A small set of tokens scoped to the lens root, not `<html>`: card padding, body text size, leading, the gap between cards (`--bn-grid-gap`). Values used in the mockup are **a starting point, not decisions**: Compact is a 0.7rem gap, 0.45rem vertical padding, text at 0.94 of body, leading 1.4; Spacious is a 1.9rem gap, 1.15rem padding, text at 1.08, leading 1.75. Open: whether Compact may shrink text at all, or only the space around it (Gmail's density, as I recall, changes spacing and not text size); a legibility floor on text size either way.

## 4. Break long paragraphs: the v1 spec

**What it is.** One switch. On: a quote longer than a natural block is shown as **blocks separated by a half-line gap**, and the lines wrap on their own inside each block. Off: the quote as it is today. Nothing else: no line-level breaks, no slider, no per-quote control. The slider, the placement choices and the two-level mode live in the lab (the mockup's right-hand panel) and stay there until a result earns a place in the product. These are parameters to keep tuning, not to bake.

**The placement** is a length-balanced choice of break sites, the line-breaking problem Knuth and Plass solved for TeX:
- **Candidate sites** (after a word): a sentence end, a cut (`...`), the point before *because / but / so / and / which / though / although / whereas*. Each site has a small cost (sentence end cheapest, then cut, then conjunction).
- **Objective:** choose the sites so each block's length sits near the target, with a penalty for each break, a cap for over-long blocks and a soft penalty for blocks under five words. Solved by dynamic programming over the sites; a quote under about a thought stays whole.
- **Target:** about **35 words** (the median length of a paragraph of speech across a tabloid, a US paper and a broadsheet is 23 to 42 words; see [research-paragraph-length-benchmark.md](research-paragraph-length-benchmark.md)). The final number is the owner's, and a constant.
- **Rules that never bend:** the words are never changed (breaks are whitespace only); a `...` stays with the phrase it ends and is never alone on a line; a block never ends on a small word (the, a, of, to, and…); a leading `...` stays with the words after it.

**Computed when the quote is drawn, from its text.** No stored breaks, no table, no migration, no pipeline change, no word timings, no anchor. The same text always gives the same blocks, so editing a quote re-places its breaks and reverting restores them. This is the point of the single checkbox: it needs none of the machinery in [design-quote-anchor.md](design-quote-anchor.md) §3.4, which becomes necessary only for hand-placed breaks and timing evidence.

**Measured on the 109 Talismanic quotes** (a script over the placement function, target 34, thoughts only): 1.7 blocks per quote; 51 quotes left whole (the short ones); **all 33 quotes over 70 words broken**; no block of 5 words or fewer. At the tabloid target (28) it is 2.0 blocks per quote; at the broadsheet target (49) 1.3, with 29 of the 33 long quotes broken. These are structural counts, not judgements of how it reads.

**Where it applies in v1.** The quote card (`QuoteCard.tsx`), which the Quotes, Screens and Discussion lenses all draw. Signals evidence (`QuoteBlock` in `SignalsPage.tsx`, no quote marks, as that card draws none) and the Uncategorised floor (`UncategorisedFloor.tsx`, marks inside the first and last block) call `breakIntoBlocks` themselves, since 4 Nov 2026, and follow the same setting; each has a vitest that fails with the wiring removed. The Dashboard's featured quotes, the Signals hover tooltip, the hidden-quotes previews and tables stay unbroken on purpose (excerpts, glanced at). The owner's direction (4 Nov 2026) is that Break moves out of this popover into Settings and applies everywhere quotes are read; Density and Layout stay Quotes-only (100days §8). The exports (Miro, CSV, slides) still show quotes unbroken; using the function in Python means a second copy, which needs an entry in [design-shared-formats.md](design-shared-formats.md) and a contract fixture.

**Tests to expect** (properties, not examples): the blocks joined with spaces equal the original text up to whitespace; no block is only `...`; the result is deterministic; short quotes are one block; no block ends on a small word; and a golden set of a few quotes with expected blocks. A property-based test is a good fit.

**Not this.** The researcher's own hand-typed line breaks are a separate bug: a break typed in the edit box is lost on commit (`EditableText` reads `textContent`; the display collapses `\n`; decision #30 may cancel a spacing-only edit; the quote card edits through `useCropEdit`, which has not been read). It needs its own reproduction first.

## 5. What the mockup showed, and what it did not

Seen rendered (Chromium) on 19 real quotes in two sections: single column with breaks reads clearly better than the 5-word cards on the long quotes; "every cut and sentence" at the far end fragments badly (the extreme the owner predicted); a break at every cut alone inflates the participant with many cuts by 51% in a single column and does nothing for the fluent speaker (15 of 20 long p2 quotes stay whole), so cuts are too sparse to be the only sites.

**Not verified:** WebKit and the Mac app (masonry, scroll, native chrome); a blind comparison against today's screen; the Mac popover; any value of any constant as a reading judgement; Signals, the Dashboard and Screens drawing quotes through the same rules.

## 6. The shared contract and persistence

One contract, rendered natively on each surface. The three KEYS sit in `tests/fixtures/report-prefs-contract.json`, asserted from Python, vitest and Swift, as zoom and the quote grouping already are; the allowed VALUES and defaults live in `DisplayPrefsStore.ts` and `DisplayPrefs.swift` (the fixture lists keys only). **A preference that must survive a quit goes through `storePref` (`utils/nativePrefs.ts`) and the mirrored-key list** (`MIRRORED_PREF_KEYS`, `BridgeHandler.reportPrefKeys`): the Mac app's web views do not keep `localStorage` across a quit. Applied before first paint, as `applySavedZoom` is. Keys as built: `bn-display-layout` (`columns` | `single`), `bn-display-density` (a number 0 to 1, two decimals, Normal 0.5; the first build's words `compact`/`normal`/`spacious` still load), `bn-display-breaks` (`on` | `off`). Focus Mode is deliberately not persisted today (`FocusModeStore` boots off); whether it should be is open.

**Differs from the Export popover it sits beside, and both differences are decided (owner, 3 Nov 2026):**
1. **The display settings persist.** The Export popover's Anonymise switch is deliberately **not** persisted (the popover is recreated each open, so a researcher never ships an unexpectedly anonymised export). Display settings are the opposite: they go through the mirrored-prefs mechanism so a reader keeps their layout. In the Mac build that means the popover's state is read from the persisted value on every open, never from a `@State` default.
2. **The popover stays open while the reader tries settings** ("try before you buy"), and does not dismiss on a choice as an action row does. Escape and a click outside close it.

## 7. The controls

**Browser.** A **Display** toolbar button with an "Aa" glyph and a caret, beside Focus Mode, opening the Export menu's classes and grammar (a muted group label over indented rows with a tick). Nothing new in CSS for the menu.

**Mac.** A native toolbar item opening a popover that follows `ExportPopoverContent` in `ContentView.swift`: **icon rows** for Layout (the chosen row's icon an accent disc, as the system's Energy Mode popover); a **slider** for Density with a small A and a big A at its ends and Compact, Normal and Spacious written underneath; plain **tick rows** (tick on the left, no icon) for Break and Focus Mode; hairline separators. (Built that way 3 Nov 2026; the earlier segmented pickers and switch rows were dropped.) Focus Mode and, as the Mac idiom for display toggles, the View menu carry the same settings. The Mac build is its own piece of work; see the handoff in the maintainer's private notes.

| Where | Control |
|---|---|
| Layout | icon rows: columns · single column |
| Density | slider, continuous, words underneath |
| Break long paragraphs | tick row |
| Focus Mode | tick row (shipped) |

## 8. Glyphs

Names verified to exist (Lucide 1.49.0 in `frontend/node_modules`; the macOS symbol list for the SF side; every SF symbol here dates from macOS 13 or earlier, so safe at the app's floor of 15). Looked up, not seen rendered.

| Job | Lucide | SF Symbol | Note |
|---|---|---|---|
| Display button | `a-large-small` ("Aa") | `textformat.size` | The convention for a reading-appearance button. Apple ships per-script variants (`.ja`, `.ko` and others); Lucide has the Latin one only. Rejected: `sliders-horizontal` (reads as filter or settings). |
| Single column | `rectangle-vertical` | `rectangle.portrait` | |
| Columns | `columns-2` | `rectangle.split.2x1` | |
| Break long paragraphs (if an icon is wanted) | `pilcrow` | `paragraph` | Alternative `rows-2` ↔ `rectangle.grid.1x2`. |
| Density: Compact / Normal / Spacious | `a-arrow-down` / `a-large-small` / `a-arrow-up` | `textformat.size.smaller` / `textformat.size.larger` at the slider's ends | **Chosen by the owner, 3 Nov 2026:** people read density as text size, so a small A and a big A; on the web rows Normal echoes the Display button's own mark. The Mac slider uses only the two end symbols and has no mark for Normal. The earlier `fold-vertical`/`unfold-vertical` and `rows-4/3/2` candidates were dropped. |

Housekeeping when built: a concept in `Icon.tsx`, a row in the Lucide and SF table of [design-icon-system.md](design-icon-system.md), and `tests/test_no_improvised_icons.py` stays green.

## 9. Strings (owner-written, none shipped)

New keys, each in 21 locales (and Swift): **Display, Layout, Columns, Single column, Density, Compact, Normal, Spacious, Break long paragraphs**, plus a hint under the switch if one is wanted. Reused: `toolbar.focusMode` ("Focus Mode"), `toolbar.allQuotes`. "Break long paragraphs" is a working name: a quote is not always a paragraph, "Break up long quotes" may be truer, and either needs the glossary check (`docs/glossary.md`). Copy rule: say only what would be news; a hint only where the title is not self-evident.

## 10. Decisions for the owner

1. **Which of the four ship before 24 Nov 2026**, if any. Break long paragraphs is the smallest and needs no new storage; Layout is one rule; Density is a token set and a design pass.
2. **The default state** of Break long paragraphs. A lean toward on for the Quotes lens, given the "overwhelming" feedback; not decided.
3. **The label.**
4. **Compact and text size**, and the single column's width and alignment.
5. **Whether Focus Mode persists**, and whether it joins the Display popover as a duplicate of its toolbar button.
6. **The Mac control's home:** toolbar popover only, or also View-menu items.

## 11. After v1

The lab holds what is not for the product yet: a second level (phrase breaks) and its placement; a strength threshold ("more or fewer"); the researcher's own hand-placed breaks as an overlay (§3.4 of the anchor note: no pin, no "edited" mark, nothing downstream sees a `\n`); timing evidence (pauses, the difference between a short cut of filler and a long gap), which needs the persisted quote-to-transcript anchor; and a model's groupings of segments as the semantic arbiter. The classical precedent is Jerome's *per cola et commata*, sense-lines set out to show a reader where to breathe ([research-paragraph-length-benchmark.md](research-paragraph-length-benchmark.md) §3a). Everything after v1 builds on the same overlay and does not change what v1 stores, which is nothing.

## 12. Assumptions and what was not checked

- The Talismanic test data is the study used on the public About page, with the participants' agreement (the owner, 3 Nov 2026). Shown by participant code.
- The mockup was checked in Chromium only. The Mac app's WKWebView, masonry and native popover are unverified.
- Density values, the 44rem measure and the 35-word target are starting points.
- The card family (`QuoteCard` via `quoteCardHost`) is assumed to cover the Quotes, Screens and Discussion lenses; Screens and Discussion were not opened to confirm.
- Where focus mode's control lives on the Mac (the View menu entry exists in `desktop.json`) was not traced.
- The "Aa" convention is from memory of Apple Books, Safari and similar readers, not searched.
- No readability literature was searched beyond the benchmark note's classical sources.

## References

[mockups/quotes-display-options.html](mockups/quotes-display-options.html) · [research-paragraph-length-benchmark.md](research-paragraph-length-benchmark.md) · [design-quote-anchor.md](design-quote-anchor.md) · [design-responsive-layout.md](design-responsive-layout.md) · [design-icon-system.md](design-icon-system.md) · [design-feature-flags.md](design-feature-flags.md) · `frontend/src/contexts/FocusModeStore.ts` · `frontend/src/utils/nativePrefs.ts` · `bristlenose/theme/organisms/responsive-grid.css` · `desktop/Bristlenose/Bristlenose/ContentView.swift` (`ExportPopoverContent`)
