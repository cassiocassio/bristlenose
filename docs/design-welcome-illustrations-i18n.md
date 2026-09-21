---
status: current
last-trued: 2026-09-21
---

# Welcome illustrations — the i18n second pass

**Why this is the higher-value half.** The docs site is English and will stay
English. For a researcher in any of the twenty non-English locales, the Welcome
illustrations and the power of their worked examples are the entire product
documentation they will ever read in their own language. The prose pass
(21 Sep 2026) localised the *captions*; these are the *examples*, and they are
still English. Plan this as the second half of one piece of work, not as polish.

Two things make it cheaper than it looks: the chrome labels already have keys
(`common:signals.*`, `enums:sentiment.*` — the settled taxonomy, never
re-translate it), and the sample quotes are **research data**, so they need
writing per locale as plausible utterances rather than translating.

## Inventory

Extracted from `WelcomeIllustrations.swift` on 21 Sep 2026 (~80 distinct
strings). Grouped by view; `[html]` = inside a webview template, `[q]` = a sample quote
that needs writing per locale as plausible research data.

## SentimentFanView — 7 sentiment names
frustration · confusion · doubt · surprise · satisfaction · delight · confidence
→ keys exist: `enums:sentiment.*` (settled taxonomy; use them, never re-translate).

## BookShelfView — 4 book titles (drawn on placeholder covers)
The Design of Everyday Things · Usability Engineering · Thematic Analysis · Emotion & Adaptation
→ published translations exist for Norman (de/fr/ja/es/it/pt/zh…) — decide per locale whether
  the cover shows the local edition's title. Author names stay.

## IngestIllustrationView — 5 surtitles (in this pack) + 5 sample filenames
usability-test-03.mp4 · interview-with-anna.m4a · usability-test-03.vtt ·
Discovery call - Transcript.docx · 2026-01-15 14.30 Usability study
→ filenames are research data; a local name (anna → per-locale) and a local date order matter.

## ClipsIllustrationView — 2 (in this pack via `menu.quotes.extractClips` + `clipsIllustration.subtitle`)

## WelcomeIllustrationHTML (the five tool webviews + signal + quote) — ~57
Chrome: Signal · Concentration · Agreement · Intensity · Participant · Satisfaction ·
"n hidden" · Onboarding · Search results · Checkout · Settings · SECTION · THEME ·
"Thinking…" · "⎿ Found 6 quotes" · "bristlenose · search_quotes" · "2 quote(s)"
→ chrome has keys in `common:signals.*`, `common:*`; the MCP transcript lines are what
  Claude Code prints and could stay English as a faithful screenshot — decide.
Tooltips: Composite signal strength · Concentration ratio — how overrepresented vs study
average · Agreement — effective number of voices (Simpson's diversity) · Mean emotional
intensity (0–3)
Codes/tags: visible options · platform convention · mental model · Intuitive · How to begin unclear
Themes: "A/B homepage trial — Reactions to the two homepage variants we tested." ·
"Switching costs — Barriers for a participant already using a rival tool."
Sample quotes (5): "In the end, browsing rather than searching works. Yeah, it did." ·
"Is it normal it’s called a shopping bag? On another site it’d feel weird — you’re used to
a cart." · "I knew straight away where to click — it matched what I expected." ·
"Browsing beat searching — it just worked." · "Honestly, I skimmed straight past this bit."
Word clouds: “where do I start?” / confusing / too many steps / I gave up ·
“found it fast” / really clear / one tap / obvious
Chat answer: "Checkout is the clearest friction point — six quotes, nearly all frustration:
“I couldn’t figure out where to pay.”"
Quote illustration fragments: “I’ve got these… that I can go to but… that’s probably… quite
busy.” · “The obvious thing to pick here is … and tableware.”


## Already done in the prose pass — do not redo

`BookShelfView.line` (4), `IngestIllustrationView.surtitle` (5), the clips
menu row (title from `desktop.menu.quotes.extractClips`, subtitle from
`welcome.home.clipsIllustration.subtitle`) and the shelf's "Learn more →"
(`welcome.home.learnMore`) are wired and translated in all 21 locales.

## Open questions for the pass

1. **Book covers — DECIDED, and the research already exists.** A cover shows the
   local edition's title **only where that edition exists**; otherwise it keeps
   the English title. A translated title for a book with no translation is a
   false claim the reader can act on — they go looking for it and find nothing —
   and reverting to English is cheap. So this is a per-book × per-language
   matrix, not one switch.

   `docs/design-i18n.md` § "Third-party codebooks" already did this work
   (Amazon sales-rank data, Mar 2026) and settles two of the four shelf books:

   | shelf book | what the research says |
   |---|---|
   | **Norman**, *The Design of Everyday Things* | translated into 20+ languages; the one title with genuine international traction (#5,251 in Japan, 155 ratings). Its codebook is the one the existing decision says to translate |
   | **Nielsen**, *Usability Engineering* | **no French translation exists**; #532,405 in Japan on 4 ratings. The existing decision is that Nielsen stays English |
   | **Braun & Clarke**, *Thematic Analysis* | not covered — check per language before assuming |
   | **Lazarus**, *Emotion & Adaptation* | not covered — check per language before assuming |

   Two constraints that fall out. The **covers are images of the English
   editions** (typographic placeholders today), so a translated title drawn over
   an English cover is incoherent — title and artwork move together or not at
   all. And **author names never change**, in any language.

   Note this is only the *title*. The caption beneath it is our own prose about
   the book, and it is already translated in all 21 locales — that was never
   the question.
2. **The MCP terminal transcript** (`Thinking…`, `⎿ Found 6 quotes`,
   `bristlenose · search_quotes`) — Claude Code prints these in English. A
   faithful screenshot argues for leaving them; a teaching surface argues for
   translating. Decide once, record here.
3. **Sample filenames** — `interview-with-anna.m4a` and the date-ordered
   folder name (`2026-01-15 14.30 Usability study`) carry a personal name and
   a date order that read as foreign in most locales.
4. **Geometry** — these strings sit in fixed-width webviews tuned around the
   English. The same translate-to-length discipline applies, and the webviews
   cannot use `WelcomeClauseFit`.
