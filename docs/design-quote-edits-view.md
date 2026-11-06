# Quote Edits: seeing how the raw transcript became each quote

**Status:** step 1 built 6 Nov 2026 and **parked**: the View menu item and its state exist behind
`BristlenoseFlags.quoteEdits`; nothing in the transcript draws the view yet. A decisions log, not a spec for
step 2. Mockup of the proposed transcript treatment: [mockups/transcript-quote-extent.html](mockups/transcript-quote-extent.html).

## The idea

A cleaned quote is the model's tidying of a stretch of speech: filler removed, false starts merged, detours cut,
the gaps marked with "…". The transcript page already draws a keyline round the stretch a quote came from, and
lifts it to white on hover (`design-transcript-gutter.md`, "Hover"). **Quote Edits** is an off-by-default view
that explains exactly how the raw words became the quote: the keyline marks the extent the model considered, the
words that made it into the quote keep the normal ink, and the words inside the extent that were cut sit back in
the same knocked-back ink as text that never became a quote. It is for the curious and for checking a quote
against what was said; it is harder to read than the plain transcript, so it is not the default.

## Decided (owner, 4–6 Nov 2026)

- **Name: "Show Quote Edits" / "Hide Quote Edits"**, a View menu Show/Hide swap like Show Session Timeline.
  "Edits" says what happened to the words. "Origins" and "history" imply we can trace where an opinion came
  from, which we cannot; "cuts" is ambiguous (video cuts, clip export); "trims" collides with the crop controls.
  It does overlap the researcher's own quote edits, which context settles.
- **Off by default, not remembered across launches** (the opposite of Focus Mode and the Display settings),
  **no keyboard shortcut**, and **cleared on leaving the transcript** so the tick and the root class never
  outlive the page they describe. Moving from one transcript to another is not leaving: it stays on, so a
  researcher can check quotes across sessions (pinned by a test; reverse it by keying the clear on the session).
- **No new click targets on the transcript text.** The caret is reserved for editing, including adding a line
  break, so the view cannot use a click on the words. Hover is fine: it commits nothing.
- **Step 1 is the menu item only.** Not built: any visual treatment, the Option peek, a Quotes-lens variant, the
  server data below.

## What step 1 is

`QuoteEditsStore` (web, module state, off at boot, class `bn-quote-edits` on the root, nothing styles it);
`quote-edits-state {available, on}` mirrored to the Mac like `timeline-state`; `BridgeHandler.quoteEditsAvailable`
and `quoteEditsOn`, reset on a project switch; View ▸ Show / Hide Quote Edits after Timeline Detail, dimmed off
the transcript and reading "Show" when dimmed (`PanelToggle.labelKey`). Parked behind `BristlenoseFlags.quoteEdits`
(a `UserDefaults` key, off everywhere: `defaults write app.bristlenose BristlenoseQuoteEdits -bool YES`), not
`#if DEBUG`, which `design-feature-flags.md` says is not for parking a user feature.

`available` is the route match (`/report/sessions/:sessionId`), not the page's own state as the Session Timeline's
is. It is true while the transcript is still loading and for an unknown session id. Harmless while nothing is drawn;
step 2 should decide whether `TranscriptPage` owns it.

## Where step 2 starts

1. **A per-word used/cut record per quote.** The server sends none today: `quoteExtents.ts` finds the extent by
   matching the quote's `verbatim_excerpt`, and says nothing about which words inside it the cleaned text kept.
   The persisted word anchor is the keystone in `design-transcript-editing.md`. About 3.5% of quotes cannot be
   located and keep today's dashed keyline; they have no reliable split.
2. **Roles.** On (or while peeking), every quote in view gets its keyline and its grey cuts and no white; the quote
   under the pointer also lifts its used words to white. With the view off, the shipped hover is unchanged.
3. **Peek: hold Option.** Shows the same view for every quote in view, and does nothing if the view is already
   on. It starts after a short hold and ends when any other key goes down, so Option+Arrow and Option-typed
   characters do not flash it once the text is editable. Instant, no animation.
4. **Scope of the class.** `bn-quote-edits` is on the document root; step 2's CSS scopes to the transcript.
5. **Quotes lens.** No keyline or raw words there, so it needs its own treatment or none.
