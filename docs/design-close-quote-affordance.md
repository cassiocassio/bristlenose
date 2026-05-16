# Close-quote affordance — glyph + language pass

> **SUPERSEDED by `docs/design-quote-triage.md` (15 May 2026).** This doc captured the first pass of Simon's session; the consolidated doc absorbs its content alongside the triage-workflow framing, the keyboard / selection / focus reality check, and the corrected stance on "maybe" + signal-sort. Read the triage doc; this one is kept for review-log continuity.

_Captured 15 May 2026 from session with Simon. Scope: icons, position, language. No data-model change, no new interactions, no animation rework._

## Problem

The eye glyph on quotes (hide affordance) isn't reading the way it should:

1. **Wrong vocabulary.** Eye-icon visibility toggles belong to design tools — Figma, Photoshop, layer panels. Researchers aren't toggling canvas-layer visibility; they're deciding whether a quote earns a place in the analysis. The metaphor pulls the wrong mental model into a research surface.
2. **Mixed metaphor with tags.** The same eye appears on tags, where it does something different: toggling a tag's eye **filters out every quote carrying that tag** — a bulk visibility operation across the corpus. So one glyph runs two jobs with two scopes (one quote vs many-via-tag) and two semantics (direct set-aside vs filter-by-attribute). Whichever side the user learns first miscalibrates the other.

## Direction

Three changes, all surface-level:

### 1. Swap glyph and verb on the quote side: close (bare ×, tab-style)

Replace the per-quote eye with a **bare ×** at the card's trailing edge. Verb becomes **close**, not hide.

**Mental model: a closeable window-let — closer to a browser tab than a window.** The quote is *closeable* and *reopenable*, but it isn't a window and the glyph shouldn't pretend to be one:
- not a Mac window — no red-dot apparatus, no traffic-light treatment
- not a chrome verb either — closing happens in-content, the surrounding view stays put
- not a cancellation — the quote is set aside, not retracted from a flow
- **closer to closing a browser tab** than closing a window: small quiet × at the edge, can have many, reopenable later, the content isn't lost
- bare × (not cross-in-circle) avoids invoking SF `xmark.circle.fill` (the chip-clear / search-clear idiom) and stays in the content-region register
- circle treatment on hover/focus only is acceptable — quiet at rest, target grows when meant

This framing also explains why "close" is the right verb here even on a Mac: tab-close uses the same word on every platform and nobody confuses it with window-close. The verb earns its place because the *thing* is clearly tab-like.

### 2. Mirror the verb in the closed-quotes section: open / open all

The reveal control in the closed-quotes section becomes **Open** (single) or **Open all** (bulk). Close/open is a clean verb pair running both ways; reinforces reversibility; sidesteps the awkwardness of "unhide" / "restore" / "un-dismiss".

### 3. Reposition hidden-tags affordance to the bottom of the section/theme

Currently the hidden-tags affordance sits near the top, competing with the section/theme title. Move it to the **bottom of the section block** so it reads as housekeeping — an afterthought, not a primary anchor. Hidden tags are a power-user control; they shouldn't share visual weight with the title.

## What we keep

- **The existing close/reveal animations.** They're working; this is a glyph + verb swap, not an interaction rethink.
- **The eye glyph itself — reserved exclusively for hide/show (visibility) behaviour.** That's the tag-side operation: a tag's eye toggles visibility of the set of quotes carrying that tag. That genuinely *is* a visibility toggle across the corpus, which is what the eye actually means. The eye doesn't disappear; it stops doing double duty.

## Resulting semantic split

| Surface | Glyph | Verb | Scope |
|---|---|---|---|
| Quote | bare × (tab-style) | close / open | one quote |
| Tag | eye | hide / show | every quote under that tag |

One glyph per semantic. No collision.

## Open questions

1. **Tag-side eye — is "hide every quote under this tag" actually the operation people are reaching for?** Or do they want a *filter* (additive, composable across tags) rather than a *hide* (subtractive, per-tag)? If it's really a filter, the right glyph might be a funnel, not an eye. Defer the call until we watch a cohort tester use it.
2. **Closed-quotes section: still a discrete section, or surfaced inline as collapsed cards?** The window metaphor suggests cards could "minimise in place" — but that's an interaction-model change and out of scope here. Park.
3. **Keyboard equivalents.** Two bindings to decide:
   - **Plain Delete / Backspace** on a focused quote → close. Memory rule already reserves plain Delete for in-quote ops (Cmd+Delete is project-delete in sidebar). Likely a decision, not a question.
   - **⌘W on a focused quote → close.** This is the tab-framing's escalation from the original plan: under the tab metaphor, ⌘W is the in-fluent keyboard reflex for "close this tab," so wiring it to close the focused quote is coherent rather than a collision. Open question: scope to non-editable focus targets only (so ⌘W in an edit field doesn't fire), and decide whether it should fall through to the window if no quote is focused.
4. **VoiceOver labels.** "Close quote" / "Open quote" / "Open all closed quotes" — confirm these read well aloud and don't get confused with window-close announcements.
5. **Localisation.** Close/open is short and clean in English. Verify the verb pair survives translation in the six locales — particularly Japanese (閉じる / 開く is fine) and German (Schließen / Öffnen). Check there's no clash with existing close/open verbs used elsewhere (modals, menus). **Locale-key renames required** (i18n-review): `announce.hidden` → `announce.closed`, `announce.restored` → `announce.opened`, `keyboard.shortcuts.hideQuotes` → `keyboard.shortcuts.closeQuotes`. Six locales × three keys. Internal data-model identifiers (`.bn-hidden`, `bristlenose-hidden` localStorage key, `hideQuote()` etc.) stay as `hidden` — user-facing vs internal split is deliberate; document in `docs/design-html-report.md`.
6. **Placement: top-left, top-right, or trailing-edge of the card?** Worth exploration:
   - **Top-left** = Mac window-close convention (red dot lives here). Mac-correct but on a card, the position is borrowed without inheriting window semantics.
   - **Top-right** = Windows + web/iOS modals. Web-fluent; matches researcher muscle memory from non-Mac surfaces.
   - **Tab-trailing-edge** = the framing's natural home: tab × sits at the tab's trailing edge, which on a card is closer to top-right.
   - **Bicameral pairing with star:** top-left × + top-right star reads as polarity-by-side (left = subtractive, right = additive). Real perceptual structure, but breaks under RTL locales (not shipped) and depends on what else lives on the card. Worth a sketch at the 500px breakpoint before committing.
7. **Archive remains a viable alternative.** Gruber's Mac-precedent read names Archive (Mail / NetNewsWire / Reeder pattern) as the dominant Mac idiom for "remove from view but keep in dataset". The tab-framing softens but doesn't fully eliminate the Close-as-chrome-verb concern. Tone difference: **Archive is deliberate, Close is casual** — for a quote a researcher is setting aside mid-skim, casual is probably right, but worth holding Archive as a fallback if cohort testing surfaces friction with Close.

## Focus model

After **Close**: focus moves to the next sibling quote in the same section, falling back to the previous sibling, then to the section heading (made focusable via `tabindex="-1"`).

After **Open** (from the closed-quotes section): focus lands on the now-visible quote in its origin section, scrolled into view; the live-region announcement names the destination section so the scroll jump isn't disorienting.

After **Open all**: focus stays on the trigger (which then disappears or disables). Don't fling focus across the document.

A single polite `role="status"` live region (scoped to the report root, reused across close / open / open-all and existing star/hide-tag if not already) announces operation + remaining count + destination context.

## Accessibility specifics

- Accessible names are object-scoped: `aria-label="Close quote"`, `aria-label="Open quote"`, `aria-label="Open all closed quotes"` — never bare verbs.
- Inline SVG carries `aria-hidden="true"`; the parent `<button>` provides the name. No `role="img"` or `<title>` inside the SVG.
- Touch target ≥ 24×24 (WCAG 2.5.8 AA), solved by button padding — don't shrink the × to match the eye glyph's pixel footprint.
- Visual register: not red, not traffic-light-sized, not in a title bar. Content-region close glyph only.
- DOM order matches visual order for the hidden-tags move (WCAG 1.3.2). Move in JSX, not via CSS `order:` / `grid-row:`. Don't render the affordance at all when zero hidden tags.
- Surface: React SPA only. The static render path (`bristlenose/stages/s12_render/`) is a sealed byproduct and keeps the existing glyph.

## Out of scope

- Data-model changes (closed-quote storage stays as is)
- Animation rework
- Restructuring the closed-quotes section
- Tag-side glyph/verb decision (deferred to cohort observation)
- Multi-select close/open gestures
