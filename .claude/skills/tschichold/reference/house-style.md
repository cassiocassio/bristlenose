# House style

Decisions are law. Don't relitigate them; apply them. Open questions get
asked (with a recommendation) the first time a fix depends on them. Record the
answer here with the date, and move it to Decided.

## Decided

- **Curly quotes and apostrophes in all prose.** Docs are curled at build time by
  Markdown `smarty` (build.py `_MD_CFG`). Hand-written HTML is curled in the
  source. Code is never curled. *(5 Oct 2026)*
- **Widows:** `text-wrap: pretty` on body, `balance` on headings and on centred
  short copy. *(5 Oct 2026)*
- **Hanging punctuation on**, off for code, form fields and single-token chips
  such as `.more-tc`. *(5 Oct 2026)*
- **Ranges take an en dash:** 4–6, 2023–2026. *(already the docs' majority usage:
  about 20 en-dash ranges against a handful of hyphens.)*
- **Small caps may be faked**, because the variable weight axis can compensate.
  Inter 4.1 has no real small caps. A shrunken capital is too light, so a
  small-caps run is set as capitals at a smaller size, with the weight raised
  and a little tracking added until its colour matches the lowercase. Real
  italics are a different matter: never fake them. *(5 Oct 2026)*
- **Tabular figures in tables** (`font-variant-numeric: tabular-nums` on
  `table`, site.css). Body text keeps Inter's default proportional figures.
  Timecodes are set in mono, which is tabular anyway. *(5 Oct 2026)*
- **A number and its unit never split across a line.** `build.py` `nbsp_units()`
  inserts a no-break space at build time ("15&nbsp;GB", "30&nbsp;days") in
  prose, never in code. Hand-written HTML takes `&nbsp;` in the source. Extend
  `_UNIT_RE` when a new unit turns up. *(5 Oct 2026)*
- **Real italic ships** (`InterVariable-Italic-4.1.woff2`, from the same
  official 4.1 release as the roman). `font-synthesis: small-caps` on `html`
  means the browser may never fake bold or italic. *(5 Oct 2026)*
- **Shortcuts are `<kbd>`**, in Inter, one quiet box per shortcut, never split.
  Authors keep writing backticks. `build.py` `kbd_shortcuts()` converts any
  modifier glyphs + key, a lone arrow or a lone modifier, and puts the
  modifiers in menu order ⌃⌥⇧⌘ (`⌘⌥N` → `⌥⌘N`). On keyboard-shortcuts.md only,
  bare keys (`j`, `Escape`) convert too. Elsewhere, write `<kbd>t</kbd>` by
  hand for a bare key in prose. *(5 Oct 2026)*
- **One space after a full stop.**
- **Measure: keep the current cap.** The docs column stays at `.page-inner
  { max-width: 760px }`, about 95–110 characters (14–15 words) per line. That's
  above the book range on purpose. Nine words a line suits a novel, but it's
  dogma for reference docs read on screen. The real rule is that **text never
  runs full-width**: every prose column has a max-width, so a maximised window
  never stretches the line. Don't propose narrowing it unless asked; do flag
  any new layout where prose has no max-width. *(5 Oct 2026)*

## Open questions

Each one gives what the docs do now and a recommendation.

1. **Double or single quotes?** The docs use double (“ ”). British book
   tradition, including Penguin under Tschichold, uses single (‘ ’) with double
   for quotes inside quotes. *Recommendation:* keep double. They're the
   site's habit and the norm for software docs. Smarty curls whichever is typed,
   so switching later is a source-wide find-and-replace.
2. **Sentence dash: spaced em ( — ) or spaced en ( – )?** The docs have about 338
   spaced em dashes and no spaced en dashes. British usage favours the spaced en
   dash; American usage favours the closed-up em dash. *Recommendation:* keep the
   spaced em dash. It's consistent across the docs, and spaced em is a common
   web compromise. Do flag it if the dash count on a page is high: dashes are
   doing the work of commas, colons and brackets.
3. **Shortcut notation.** The docs mix ⌘F style (most) with Command-L (a few).
   *Recommendation:* glyphs everywhere (⌘L, ⇧⌘E). That's macOS menu order and
   the majority usage. Write the key letter in capitals, as the menus do.
4. **What bold means.** About 357 bold runs across 36 pages. *Recommendation:*
   bold = a UI label the reader will see on screen (a button, menu item or
   field). Anything else bold becomes italic, a callout, or plain.


## Parked (remind the user)

- **Dark-mode weight compensation.** Light text on dark reads heavier. The idea:
  lower `--w-normal`/`--w-emph`/`--w-strong` slightly under
  `prefers-color-scheme: dark` and judge by eye. Inter has no `GRAD` axis, so
  this reflows text a little. The user wants time to look at it properly.
  Raise it at the start of the next typography session. *(parked 5 Oct 2026)*
- **App and docs.** The Mac app and the web report (main bristlenose repo) have
  their own type and need their own context: tabular timecodes there too, for
  example. This skill is scoped to the website; the app would need its own
  version. *(raised 5 Oct 2026)*

