# Rules, section by section

Each rule says what to do and why, briefly. "Classical" means the book-typography
tradition Tschichold returned to and Bringhurst codified. "Screen" marks where
the web differs and the rule bends.

## 1. Characters

Use the right glyph, not the nearest key.

| Write | Not | Where |
|---|---|---|
| “ ” ‘ ’ | " ' | All prose. `build.py` curls Markdown via `smarty`. Hand-written HTML and Python strings in `build.py` (titles, leads) don't go through Markdown, so check them by hand. |
| ’ (apostrophe) | ' | It's, don't, the ’90s. An apostrophe at the start of a word points the same way as one in the middle (’90s, not ‘90s). |
| – (en dash) | - | Ranges: 4–6 GB, 2023–2026, pages 3–7, Monday–Friday. Not for "from 4 to 6". Write "from 4 to 6" or "4–6", never "from 4–6". |
| — or – (sentence dash) | - or -- | Whichever the house style records (see house-style.md), used the same way everywhere. |
| × | x | Multiplication and dimensions: 5×, 1920 × 1080. |
| − (minus) | - | Negative numbers and arithmetic in prose: −3 dB. |
| … | ... | Ellipsis. A menu item that opens a dialog ("Export…") takes the single character too, to match macOS. |
| ⌘ ⌥ ⇧ ⌃ | Cmd, Command-, Opt | Mac shortcuts, in the order macOS menus show them: ⌃⌥⇧⌘. One notation site-wide. |
| → | -> or > | Menu paths: File → Export. |
| ′ ″ | ' " | Feet and inches, minutes and seconds of arc. Rare in these docs, but don't let smarty curl them. |
| © ™ | (c) (tm) | Rare. Fine to leave in legal boilerplate if it's pasted from somewhere. |

Inside code (backticks, fences, `<code>`, `<pre>`, `<kbd>`) **nothing changes**.
Code is what the user types, so it must stay typeable.

## 2. Spaces

- **One space after a full stop.** The classical tradition and Penguin both use
  one. HTML collapses double spaces anyway, but they're noise in the source.
- **Non-breaking space** (`&nbsp;` in HTML; in Markdown, the literal U+00A0
  character) where a line break would strand a fragment:
  - between a number and its unit: 15&nbsp;GB, 5&nbsp;minutes, 16&nbsp;GB&nbsp;RAM
  - after short labels with a number: Step&nbsp;3, page&nbsp;7, macOS&nbsp;15
  - inside names that read as one: Apple&nbsp;Silicon (optional; use judgement)
- **No space** between a number and %, or around × in "5×" when it means "times".
  Use spaces around × in dimensions: 1920 × 1080.
- **Never** use spaces or `&nbsp;` for layout or indentation. That's CSS's job.

## 3. Emphasis

Classical rule: italic for emphasis, bold almost never in running text. Bold
is a signpost for scanning, not a raised voice.

- **Find out what bold means on this site and make it mean one thing.** Docs
  conventionally bold UI labels (click **Export**). If that's the meaning,
  bold must not *also* be used for stress, warnings or key ideas. Stress is
  italic; warnings are callouts.
- **Count it.** If a page has more bold than a reader can scan, none of it
  works. Report bold per page when it looks heavy.
- **Never combine** bold + italic, or underline for anything but links.
- **No ALL CAPS for emphasis.** Capitals are for acronyms, and for labels if the
  house style says so (the sidebar group headings are small caps-like labels,
  which is fine).

## 4. Headings

- **Sentence case**, consistently. Proper nouns and product feature names keep
  their capitals (Focus Mode, if that's the feature's name in the app UI).
  Check the app's own UI strings before "correcting" a feature name.
- **No full stop** at the end of a heading. A question mark is fine.
- **Don't stack headings.** A heading directly followed by another heading,
  with no text between, is a hierarchy problem. Fix it with a sentence of
  introduction, or by removing a level.
- **Don't skip levels** (h2 → h4).
- **Space above a heading > space below it**, so the heading belongs to what
  follows. Check this in the CSS, not just the Markdown.
- **Headings are balanced** (`text-wrap: balance` in site.css). A heading that
  wraps should break at a sense boundary. If balance gives a bad break, rewrite
  the heading shorter; don't force a `<br>`.

## 5. Lists

- **Parallel grammar.** Every item in a list has the same shape: all
  imperatives, all noun phrases, or all sentences.
- **Punctuation by shape.** Fragments take no full stop; full sentences take
  one each. Never mix within a list.
- **A list of one** isn't a list. Write a sentence.
- **Numbered** only when order matters (steps). Otherwise bullets.

## 6. Tables

Tschichold's later practice and Bringhurst agree: tables are for reading, not
for showing off the grid.

- **Horizontal rules only**, and few of them. No vertical rules, no boxes.
- **Numbers right-aligned** (or aligned on the decimal point) with **tabular
  figures**: `font-variant-numeric: tabular-nums`. Inter has them.
- **Text left-aligned.** Never centre a column of text.
- **Units in the header**, not repeated in every cell, when every row shares them.
- **Header text** is the same size as the body or one step smaller. Avoid
  shouting with all caps plus bold plus colour.

## 7. Measure and leading

The classical comfortable measure is 45–75 characters per line, about 66 the
ideal for continuous reading. Bringhurst gives the same range. On a screen at
docs sizes, aim for roughly 60–80.

- **Measure it.** As of 5 Oct 2026, `.page-inner` is `max-width:760px` with
  15px Inter: about 95–110 characters per line. **House style keeps this on
  purpose** (see house-style.md). Book measure is dogma on the web. The rule
  that matters is that prose **never runs full-width**: flag any prose
  container without a max-width. If the measure is ever revisited, size it in
  `em`, not `ch`. `1ch` is Inter's tabular zero (0.631em), while an average
  character is about 0.465em, so `65ch` holds about 88 characters.
- **Leading** (line-height) rises with measure. 1.5–1.6 suits ~70 characters.
  Headings get tighter leading (1.1–1.25) because they're short and large.
- **Fewer sizes.** Count the distinct font sizes on a docs page. A scale with
  more than about six steps in running content (not counting UI chrome) is a
  smell. Near-duplicates like 13px and 13.5px, or 15px and 15.5px, should merge
  unless there's a measured reason.

## 8. The end of the line

- **No widows or orphans.** `text-wrap: pretty` on paragraphs and list items,
  `balance` on headings, both already in site.css. Check the result in a
  browser at desktop and phone widths.
- **Ragged right, not justified.** Browsers hyphenate and justify poorly.
  Justified text without good hyphenation makes rivers, so keep the rag.
- **Hanging punctuation** (`hanging-punctuation: first last`, Safari only) is on
  site-wide and off for code and form fields. If a block contains *only* a
  bracketed or quoted token (like the home page's `[00:01]` timecodes), turn it
  off for that block, or the brackets hang out of the box.
- **Don't let a line break** split a number from its unit, a shortcut from its
  key, or ⌘ from its letter. Non-breaking spaces (§2), or `white-space: nowrap`
  on `kbd`.

## 9. Acronyms and small caps

The classical treatment sets runs of capitals (API, MCP, PII) in small caps or
letterspaces them slightly. **Inter 4.1 has no small caps.** The shipped file has
no `smcp` or `c2sc`, even though the Inter website lists `c2sc`. It also has no
oldstyle figures (`onum`). The browser's own `font-variant-caps` fallback
shrinks capitals and leaves them too light, so don't use it. **House style
allows a compensated fake instead** (see house-style.md): set capitals at about
0.8em, raise the weight (about +60 to +80 on the `wght` axis) and add
0.03–0.05em of tracking, then judge by eye against the lowercase beside it.
Use it sparingly, for runs of capitals in running text, never in headings or UI labels.

All-caps *labels* are different. They do want `font-feature-settings: "case"`
(this raises hyphens and brackets to cap height; `text-transform` doesn't switch
it on) and 0.04–0.08em of tracking.

To see what any font file really has, rather than what its website says:

```bash
uv run --with fonttools python3 -c "from fontTools.ttLib import TTFont; f=TTFont('assets/fonts/InterVariable-4.1.woff2'); print(sorted({r.FeatureTag for r in f['GSUB'].table.FeatureList.FeatureRecord})); print([a.axisTag for a in f['fvar'].axes])"
```

## 9a. Italics

The real Inter italic ships (5 Oct 2026), and `font-synthesis: small-caps` on
`html` forbids faked bold and italic. If a new font or weight is ever added,
ship its italic too. With synthesis off, a missing face shows up as upright
text instead of being quietly faked.

## 10. Screen mechanics (CSS this site already relies on)

| Concern | Property | Status |
|---|---|---|
| Widows in body | `text-wrap: pretty` | site.css, all `p, li, figcaption` |
| Even headings | `text-wrap: balance` | site.css, `h1`–`h4` |
| Centred short copy | `text-wrap: balance` | style.css, `.story p`, `.hero-subtitle` |
| Hanging quotes | `hanging-punctuation: first last` | site.css on `html`; off for code, inputs, `.more-tc` |
| Curly quotes | Markdown `smarty` | build.py; dashes and `<< >>` off on purpose |
| Tabular figures | `font-variant-numeric: tabular-nums` | site.css on `table` |
| Shortcuts | `<kbd>`, modifiers ⌃⌥⇧⌘ | build.py `kbd_shortcuts()`; site.css `kbd` |
| Number + unit | `&nbsp;` | build.py `nbsp_units()` for docs; by hand in content/*.html |

All of these degrade gracefully: a browser that doesn't know them wraps and
sets text as before. Don't add JavaScript typesetting to make up for a browser
that lacks a feature.
