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

   **Measured 22 Sep 2026 — all four books, ten Amazon markets.** The two rows
   below that said "not covered" are now covered, and one of them turned out to
   be a yes. Method: search each market for the original English title (the
   stores index it), then confirm the hit is a translation rather than a
   same-titled local book — `4274214834` 「ユーザビリティエンジニアリング」 is by
   **樽本 徹也**, not Nielsen, and is exactly the false positive the next
   searcher will also find.

   **Amended the same day: it is nine, not six.** The eleven markets recorded
   below as "no Amazon market, unchecked rather than nil" were checked against
   national bookstores, and three of them had editions. The caution was right
   and the number was wrong — a nil from a search that cannot reach the market
   is not a nil.

   | shelf book | editions found | markets |
   |---|---|---|
   | **Norman**, *The Design of Everyday Things* | **nine** | de, es, fr, it, ja, pt-BR, **zh-Hant, ko, ru** |
   | **Braun & Clarke**, *Thematic Analysis* | **one** | pl — *Analiza tematyczna: Praktyczny przewodnik*, PWN, `8301238356` |
   | **Nielsen**, *Usability Engineering* | none | — |
   | **Lazarus**, *Emotion & Adaptation* | none | — |

   Per-edition, for cover capture:

   | market | ISBN/ASIN | title | max cover |
   |---|---|---|---|
   | de | `3800648091` | *The Design of Everyday Things: Psychologie und Design der alltäglichen Dinge* (Vahlen) | 441×700 |
   | es | `8412779916` | *El diseño de las cosas cotidianas* | 769×1200 |
   | fr | `B08NTXLNRZ` | *Le design des objets du quotidien* | 1600×2378 |
   | it | `8809986865` | *La caffettiera del masochista* (Giunti) | 1000×1514 |
   | ja | `4788514346` | 『誰のためのデザイン？ 増補・改訂版』(新曜社) | 683×1000 |
   | pt-BR | `6555324473` | *O design do dia a dia* | 1781×2560 |
   | pl | `8301238356` | *Analiza tematyczna: Praktyczny przewodnik* (PWN) | 776×1080 |

   **German is the finding that changes the rule's shape.** Vahlen keeps the
   **English main title** and adds a German subtitle, so "show the local
   edition's title" resolves for `de` to *the title already on the shelf* — a
   no-op for the title and a change only for the artwork. A per-book × per-
   language matrix was the right call: one switch would have got this wrong.

   **The eleven non-Amazon markets, checked 22 Sep 2026** against national
   stores. The prediction in the previous sentence of this paragraph — "Norman
   plausibly has ko/zh-Hant/ru/cs editions" — was three-quarters right:

   | locale | store | result |
   |---|---|---|
   | zh-Hant | 博客來 books.com.tw | **設計的心理學：人性化的產品設計如何改變世界 (3版)**, `0010643797`, 唐納‧諾曼. The same store also stocks Yablonski's *Laws of UX* 2nd ed — a second shipped codebook readable in Chinese |
   | ko | YES24 | **도널드 노먼의 디자인과 인간 심리**, 학지사, 2016, tr. 박창호 |
   | ru | Litres | **Дизайн привычных вещей**, tr. Б. Л. Глушак — listed but *нет в продаже* |
   | cs | Kosmas | no match for Donald Norman |
   | uk | Yakaboo | **UNCHECKED** — Cloudflare-blocked from here. Not a nil |
   | pt-PT | Wook | search path redirects; likely carries the Brazilian edition |
   | ca | La Central (Barcelona) | **nil, measured 22 Sep 2026.** Nine Norman titles, not one in Catalan — *El diseño de las cosas cotidianas* (Capitán Swing), *El ordenador invisible* (Paidós), the English original. `disseny de les coses` returns nothing. Catalan readers are served by the Spanish edition |
   | da, fi, nb, sv | Saxo, Adlibris, Ark | nil — each store's own language facet reads English for every hit |
   | nl, tr | Amazon | nil — English editions only |

   **All 21 locales are now accounted for**: eleven carry a local edition
   (ten Norman plus Braun & Clarke in Polish), nine are measured nil, and `en`
   is the source. There is no "unchecked" row left.

   | shelf book | what the earlier research said |
   |---|---|
   | **Norman**, *The Design of Everyday Things* | translated into 20+ languages; the one title with genuine international traction (#5,251 in Japan, 155 ratings). Its codebook is the one the existing decision says to translate |
   | **Nielsen**, *Usability Engineering* | **no French translation exists**; #532,405 in Japan on 4 ratings. The existing decision is that Nielsen stays English |

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


## Review status

The plan below was written, then reviewed against the code, and revised. The
review changed it materially rather than endorsing it, so treat the current
text as second-draft: three rows of §2's key table were wrong in ways that
change the English, §3's escaping model was one sink where there are three plus
a layer inside the JS, §6 understated clipping as overflow when it is silent
truncation that the auto-fit structurally cannot correct, §8's order had the
people-time last and a red gate first, and §8a — the defect where **no
illustration reloads on a language change** — was missed entirely by the first
draft. Two class-A defects that already exist in English surfaced on the way.

## The plan

### 0. What makes this different from the prose pass

The prose pass translated *our sentences about the product*. This pass
translates *the product being shown*, plus *a researcher's data*, plus *other
companies' software*. Those are three different jobs with three different
correctness rules, and conflating them is the main risk:

| class | example | rule | source of truth |
|---|---|---|---|
| **A · our own UI, copied** | `Signal`, `Concentration`, `Agreement`, `Intensity`, `Participant`, `Satisfaction`, `n hidden`, `Extract Video Clips…` | **word for word with what we ship** — never re-translated | the existing locale keys |
| **B · third-party UI, imitated** | Claude Code's `Thinking…` / `⎿ Found 6 quotes`, Zoom/Teams/Meet exports, a Miro sticky | match what *that* product ships in *that* locale, or stay English where it ships English | evidence per product per locale |
| **C · research data, invented** | five participant quotes, two theme titles, codes, word clouds, sample filenames, the chat answer | **written** per locale as plausible utterances, not translated | a native speaker with the research brief |

Class A is the one with a mechanical answer and the one most likely to be got
wrong by a well-meaning translator, because a string like `Signal` looks
translatable. If an illustration shows our own UI and the word differs from the
lens beside it, the illustration stops being documentation and becomes a
contradiction.

### 1. The surface, split by technology

Both halves need doing; they need different mechanisms.

**Nine webview illustrations** — HTML + JS built as Swift string templates in
`WelcomeIllustrationHTML` (`WelcomeIllustrations.swift:795+`): `emergentThemes`,
`quote`, `signal`, `autocode`, `manualTags`, `tag`, `starHide`, `agentChat`,
`miro`. These already interpolate Swift values (`var PACE=\(WelcomeTempo…)`), so
the seam exists — but it is **string interpolation into HTML and JS**, which is
an escaping surface, not a formatting one. See §3.

**Four native SwiftUI illustrations**: `SentimentFanView` (7 sentiment names),
`BookShelfView` (4 titles + covers), `IngestIllustrationView` (5 filenames — its
surtitles are already localised), `ClipsIllustrationView` (already localised).
These take ordinary `i18n.t` calls, exactly like the prose pass.

### 2. Class A — the word-for-word rule, mechanised

**Do not add new keys for anything we already ship.** But the mapping is not
the obvious one, and three of the five rows a first draft of this plan proposed
were wrong in ways that change the English:

| illustration string | the key that actually ships it | note |
|---|---|---|
| `Signal` | `common:signals.signalLabel` | matches |
| `Concentration` | `common:signals.concLabel` = **`"Conc."`** | the lens abbreviates; the illustration spells it out |
| `Agreement` | `common:signals.agreeLabel` = **`"Agree."`** | same |
| `Intensity` | `common:signals.intensityLabel` | matches; but see the defect below |
| `Participant` (speaker badge) | **`enums:speakerRole.participant`** — *not* `dashboard.colParticipants`, which is a plural table header | |
| the seven sentiment names | `enums:sentiment.*` | settled taxonomy; **capitalised**, while the fan and the signal card draw them lowercase |
| `n hidden` | `common:tags.countHidden` = `"{{count}} hidden"` | **no `_one`/`_other` stems in any locale** — call `t(key, ["count": …])`, never `plural()`, which would miss and render the raw key |
| `Extract Video Clips…` | `desktop:menu.quotes.extractClips` | already wired |

**Two decisions fall out of that table, and they are decisions, not bookkeeping.**

1. **Does word-for-word mean the illustration says `Conc.`?** The abbreviations
   exist because the *lens* is space-constrained and the illustration is not. Two
   defensible readings: the rule does its job and the example matches the app;
   or word-for-word means *the same key*, and a teaching surface may take the
   `*Title` sibling where space allows. The second is a real weakening and has
   to be taken deliberately rather than discovered.
2. **Sentiment casing.** `enums:sentiment.*` is capitalised; `SentimentFanView`
   and the signal card draw lowercase. Adopting the keys changes both surfaces.

**Two class-A defects already existed in English** — found while building this
table, and **fixed 21 Sep 2026** rather than carried into the pass. The intensity
tooltip said `(0–3)`; intensity is 1–3 (`models.py`: *1=mild, 2=moderate,
3=strong*, and the quote-extraction prompt says the same), so the shipped string
was right and the picture was wrong. The Miro sticky said `2 quote(s)`, which
`tests/test_miro_board.py::test_header_count_is_singular_or_plural_never_parenthesised`
exists specifically to stop the exporter producing — the illustration was
depicting the one output the product is tested never to emit. The source mockup
carried the same intensity error twice and was corrected with it, since that is
where a future port would pick it up again.

Both were literal strings, not keys. They become key lookups in this pass; the
fix was to make the English true first, so the pass is not translating a
falsehood into twenty languages.

**The gate: extend the existing test, do not build a sibling.**
`tests/test_welcome_locale_keys.py` already scans `WelcomeIllustrations.swift`
and already enforces both directions by enrolling call sites rather than a list.
The tempting alternative — "fail on any literal equal to a shipped string" —
was measured against the real corpus and is the wrong instrument: **eleven
literals collide today** (`Signal`, `Intensity`, `Participant`, `Settings`,
`Satisfaction`, `Moderator`, `Hide`, `Tip`, `AI`, `Quotes`, `Sessions`), and the
dangerous one is `Settings`, which in the illustration is the *name of a section
of the study under test* — class C. The gate would fire and the fix it names
would be actively wrong. It would also pass **vacuously** once the literals are
gone. So: pin the key at the call site (allow-list, enrol-by-existing, no false
positives), plus a separate **English-only** duplicate-value report, which
collapses 21 locales to one list a human can actually read.

### 3. The interpolation seam — three sinks, and a second layer inside the JS

A first draft said "one helper that JSON-encodes and escapes `<` `>` `&`". That
is right for exactly one destination and wrong for the other two:

| sink | example | what it needs |
|---|---|---|
| JS string literal | `var T=[{t:"…"}]` | JSON encoding **and** `<` `>` `&`, so `</script>` cannot close the block |
| HTML text node | `<span class="metric-label">Signal</span>` | HTML escaping only — JSON encoding would inject literal `"` |
| HTML attribute | `title="Concentration ratio — …"` | HTML escaping **plus** `"` |

And there is a second layer the draft missed entirely: `cardHTML`, `tagCard` and
`fullCard` interpolate values into **`innerHTML` inside the JS**. Fixing only the
Swift→template boundary leaves that open.

**So the shape to build is not three helpers but one seam:** pass a single JSON
blob at the top of the script and have the JS assign through `textContent`. One
escape site, one sink, no HTML-injection surface across ~57 strings, and the
`innerHTML` layer disappears with it. Note two porting details: Swift's
`JSONEncoder` has no `ensure_ascii` equivalent and emits literal non-ASCII
(fine, the page is UTF-8), and the apostrophe worry from the draft does not
bite — these are double-quoted literals. The real breakers are `"`, `\`, a
newline, and `</script>`.

**Also: the seam does not exist everywhere the draft claimed.** Five templates
already interpolate Swift values, but `miro` and `agentChat` hold their
user-visible text as **static HTML in the body** — precisely the two with the
most hand-set content. Those need new interpolation points, not a substitution.

### 4. Class C — the part that is authored, not translated

Two of these are re-authoring jobs that a translation brief cannot cover.

**The quote illustration is a disfluency animation.** Its token list marks each
word keep-or-trim and strikes the filler through: *"So, um, The checkout, like,
was honestly, the—the confusing, you know? I couldn't actually figure out where
to pay."* The fillers are English fillers. Japanese needs えーと／あの, German
*ähm/also*, French *euh/ben*, and the repair-repetition (*the—the*) has a
different shape in each language. A translator handed this string will
translate the *sentence* and destroy the *demonstration*. Brief it as: write a
natural disfluent utterance in your language, then mark which tokens a tidy-up
would remove.

**The brief must ask for a token array, not a sentence.** Two specifics a
translator will otherwise get wrong: the spacing and punctuation are *inside*
the tokens (`{t:"So, "}`, `{t:", like,"}`, `{t:" the—the"}`), so what the
animation needs is a list whose `join("")` is the sentence — French needs its
space before `?`, Japanese has no inter-word spaces at all. And the trim tokens
are capped at `20ch` in the resting state, so a long German or Finnish repair
is clipped with no error.

**The search word clouds** (`"where do I start?" / confusing / too many steps /
I gave up` and the positive set) are corpus samples, not UI. They need to read
like things a participant in that language would actually say.

The five sample quotes, two theme titles and the codes are the same job, one
step easier. The sample **filenames** carry a personal name and a date order —
but see §9's question 3: if the study is one fictional study told in twenty
languages, most of that list shrinks or disappears.

### 5. Class B — imitating other people's software honestly

The principle: **we are showing the user something they will recognise.** So
each imitated surface is set to whatever that product actually does in that
locale, and where we cannot establish it, we leave English rather than invent
a translation that product does not ship.

- **Claude Code's terminal** (`Thinking…`, `⎿ Found 6 quotes`,
  `bristlenose · search_quotes`, `(MCP)(query: "checkout")`). Claude Code's CLI
  is English-only today. **Leave it English in every locale** — a translated
  `Thinking…` would depict software that does not exist. Worth one check before
  the pass, since this could change.
- **Zoom / Teams / Meet** appear only as the words "Word exports from Zoom,
  Teams or Meet" in an already-localised surtitle, and as the *filename shape*
  `Discovery call - Transcript.docx`. Those products **do** localise their export
  filenames, so the realistic per-locale filename is the one that product
  generates there. This is a small, checkable detail with a big realism payoff.
- **Miro** sticky notes carry our quote text, not Miro chrome. Product name never
  translates.

### 5a. The fourth class — our own UI that is English-only by design

The three-class table above is not quite complete, and the gap is sharp. The
Miro sticky's `2 quote(s)` comes from `count_noun(n, "quote")`, and the house
convention is that CLI count strings are **English-only in alpha**. So a
*correctly translated* Miro sticky would depict a board Bristlenose has never
produced — which is exactly the argument §5 makes for not translating Claude
Code, turned on ourselves. The same question covers the `SECTION` / `THEME`
surtitles and the `p1` / `p3` speaker codes, which are generated and never
translated.

Three options, and only the third resolves cleanly: translate it and depict
software that does not exist; leave it English inside an otherwise-German
illustration and accept it reads as an oversight; or treat the illustration as
a forcing function and localise the Miro export itself. The third is out of
this pass's scope, so one of the first two must be **written down here** before
a reviewer files it as a bug.

### 5b. Accessibility — the same argument, unfinished

Every illustration is `.accessibilityHidden(true)`, deliberately, as decorative
chrome. But the premise of this whole pass is that these worked examples *are*
the documentation for twenty locales. If that is true, a VoiceOver user gets no
documentation in any language, and translating the illustrations does not
change that by one word. Either that is an accepted boundary and it is stated
as one, or it is the second half of the same argument and belongs in this plan.

### 6. Geometry — it clips silently, and `fit()` cannot save it

Worse than the draft said. The webviews are fixed-size, have neither
`ViewThatFits` nor `WelcomeClauseFit`, and every template sets
`overflow:hidden` — so a label that does not fit **vanishes**, with no
scrollbar and no error. The signal card is a hard `440px` wide and its `fit()`
scales from `offsetWidth`, which stays 440 whatever the content is, so the
auto-fit **structurally cannot compensate** for a longer German metric label;
several inner rows are `white-space:nowrap` besides.

Two consequences. Where a class-A label genuinely does not fit, the fix is a
**layout change, not a copy change** — word-for-word is the rule. And for the
signal card specifically the honest fix is to measure `scrollWidth`.

**This needs an instrument, not a resolution.** 21 locales × 9 webviews is 189
renders and nobody is going to eyeball them by hand. The cheapest instrument
already half exists: the mockups these were ported from live in
`docs/mockups/welcome-*-animations.html` and are auto-discovered by
`serve --dev`, so a locale-parameterised mockup page shows every locale in a
browser. That belongs early in the sequence, not after the content lands.

### 7. Book covers need pixels, not just titles

Settled above: a cover shows the local edition's title only where that edition
exists. The consequence is that **a translated title needs translated artwork**
— the covers are images of specific editions, and the title is drawn as part of
the design. So the work per (book × language) is: confirm the edition exists,
then capture its cover. The bookstore links for that are in the appendix.

Two costs the first draft did not name. `BookShelfView` falls back to a
**typographic placeholder that draws the title as text** whenever the cover
image is missing — dormant today because all four assets exist, but a per-locale
asset scheme means most (book × language) pairs will miss and fall back, and
`bookCard` has no locale in scope to choose an asset with. And up to 4 × 21
cover images is an unbudgeted addition to the app bundle. The titles also live
as literals in a static array, so they need the same key treatment as everything
else.

Prioritisation, **measured 22 Sep 2026** (the per-market table is in §"Open
questions for the pass" item 1): **Norman has six editions**, Braun & Clarke has
**one** (Polish), and Nielsen and Lazarus have none in any Amazon market. So the
work is seven (book × language) covers, not the 4 × 21 this section budgeted
for — which retires the bundle-size concern below rather than answering it.
Four of the seven are under the shipping spec (~1000×1500) at the best
resolution Amazon serves; **accepted for v1, 22 Sep 2026**. The open half is
not resolution but permission: these are publisher artwork, and the images
Amazon serves come with Amazon's own terms attached.

### 8. Sequencing — people-time first, gate after the seam

The first draft put the gate first and the authoring brief fourth. That is
backwards on both counts: the plan's own text says class C is "the long pole and
it is people-time", and a gate written before the seam exists would be red from
day one, which is how an `xfail` gets added and a gate stops meaning anything.

1. **Class C brief out** — the authoring work runs in parallel with all the code
   below, and it is the critical path. Settle §9's one-study question first,
   because it decides how big the brief is.
2. **The locale-parameterised mockup page**, so there is a way to *see* 21 × 9
   before anything is plumbed.
3. **The JSON-blob seam plus locale-aware reload** (§3 and the reload defect
   below), proven on one webview end to end, reviewed.
4. **The gate**, whose shape depends on what the seam looks like.
5. **Class A everywhere** — mechanical once the seam exists, and the immediate
   coherence win.
6. **Class B evidence** per product, one check each.
7. **Covers** — Norman first.
8. **Longest-locale layout pass** across the nine, using the instrument from 2.

### 8a. The defect that will otherwise be found last

**A language change does not reload any of the nine webviews.** The HTML is
handed to `loadHTMLString` once; the update path is empty; and the only reload
trigger is SwiftUI recreating the view when its `.id` changes, which today keys
on colour scheme, palette and stillness — not locale. None of the nine structs
even takes `I18n`, so they do not re-render when it publishes.

Net effect if this is not fixed first: a user switches to German, the prose
around the illustrations changes, and **all nine illustrations stay in English**
until they happen to toggle dark mode. It would ship silently and no gate we own
would see it. Each struct needs the environment object and the locale in its
`.id`, and that is a named step, not an implementation detail.

### 9. Open questions

1. **One study or twenty?** The coherent answer is one fictional study told in
   each language — same participants, same findings, spoken locally. It is also
   much less work. But the plan above still commissions per-locale filenames,
   participant names and date orders, which is the *other* answer. Reconcile
   this **before** any brief goes out; it changes the size of the ask by roughly
   a third.
2. **Does word-for-word mean `Conc.`?** (§2, decision 1.) A rule or a carve-out,
   taken deliberately.
3. **Sentiment casing** — the keys are capitalised, two surfaces draw lowercase.
4. **The English-only class** (§5a) — translate and lie, leave and look sloppy,
   or localise the Miro export. Pick, and write it here.
5. **Accessibility** (§5b) — accepted boundary, or the other half of the job?
6. **Is the webview the right vehicle at all?** They were built as webviews to
   reuse mockup CSS and stay in sync with the report's styling, which was right
   for chrome fidelity. It now buys: a bespoke escaping seam, a locale-reload
   dance, silent clipping, a font stack with **no CJK coverage** (Inter / Open
   Sans / Helvetica / Arial — ja, ko and zh-Hant fall through to a browser
   default, destroying the recognition the illustration exists for), and
   hand-set `<br>` line breaks that every translation invalidates. A native
   SwiftUI rebuild of the two most text-heavy — `miro` and `agentChat`, both
   essentially static text compositions — would get `ViewThatFits`, real
   `i18n.t`, VoiceOver and no escaping at all. The counter is real: it forks the
   mockup→illustration pipeline and loses CSS resync. Worth asking before ~57
   strings go through the harder path.
7. **Does Claude Code's CLI ever ship localised?** If it does, §5 flips.
8. **`zh-Hant-HK` takes none of the ~57 new keys** unless the value genuinely
   differs in Hong Kong — an ordinary key there pins the value and breaks the
   inheritance chain. Stated here because it is the rule most easily forgotten
   at scale.

## Open terminology calls from the 21 Sep review (prose pass, not illustrations)

Applied: it `Abbreviazioni`→`Scorciatoie` (the bare noun means *abbreviations*);
es restored `libro de códigos` (the QDA term had been truncated to `libro`);
fr `une étiquette par verbatim`→`des étiquettes sur chaque verbatim` (the
singular changed what AutoCode does); fr `tips.configuration.link`
`Réglages`→`Configuration` (it collided with the Settings pane on the same
screen); pl swept the block from *tag/tagowanie* to *etykieta*, because the
`desktop` namespace it lives in already says *etykieta* in the menu the user
opens next; `ru` added to the `_divergent_studyTools` marker, which named five
locales when six drop the qualifier.

Deliberately **not** applied, each needing a decision rather than an edit:

- **ca `tips.configuration.link`** has the same Settings collision as fr, but
  `Configuració` *is* Apple-ca for Settings, so the docs page needs a different
  word and a native picks it.
- **zh-Hant import/export asymmetry** — the block uses Apple-TW `輸出` for export
  and `匯入` for import. `glossary.csv` says `輸入`. This is inside the pending
  Taiwan ratification (`docs/i18n-language-decisions.md` § zh-Hant), so it waits
  for that pass rather than being settled here.
- **pt-BR/pt-PT star vocabulary** — `Destacar e ocultar` uses *destacar* for
  star while the same block uses *em destaque* for featured. Pre-existing across
  the locale, inherited not introduced, but the welcome pane is where a new
  researcher meets both.
- **sv dashes** — the block uses the en dash throughout (19 occurrences), which
  is correct Swedish typography but flips the house form against sv's own corpus
  (62 em, 28 en). A deliberate call, one way or the other.
- **zh-Hant `ingestRows`** keeps ` — ` where ja took §6a's label colon. Chinese
  would take fullwidth `：`. Consistency call, not a re-derivation of §6a.

## Appendix — bookstore links for cover capture

Search links per market, for confirming an edition exists and capturing its
cover. **Start with Norman**: the research in `design-i18n.md` says it is the
only one of the four with broad translation, so it is where the effort pays.
Nielsen has no French edition at all and ranks near zero everywhere; Braun &
Clarke and Lazarus are unverified in every market, so treat a nil result there
as information rather than a failed search.

Each link searches the **original English title** — that is what finds a
translated edition on most of these stores, because they index the original.
Where a store returns nothing, search the author name alone before concluding
no edition exists.

### Germany (`de`)

| book | Amazon.de | Thalia |
|---|---|---|
| Norman | [search](https://www.amazon.de/s?k=The+Design+of+Everyday+Things) | [search](https://www.thalia.de/suche?sq=The+Design+of+Everyday+Things) |
| Nielsen | [search](https://www.amazon.de/s?k=Usability+Engineering) | [search](https://www.thalia.de/suche?sq=Usability+Engineering) |
| Braun & Clarke | [search](https://www.amazon.de/s?k=Thematic+Analysis+A+Practical+Guide) | [search](https://www.thalia.de/suche?sq=Thematic+Analysis+A+Practical+Guide) |
| Lazarus | [search](https://www.amazon.de/s?k=Emotion+and+Adaptation) | [search](https://www.thalia.de/suche?sq=Emotion+and+Adaptation) |

### France (`fr`)

| book | Amazon.fr | Fnac |
|---|---|---|
| Norman | [search](https://www.amazon.fr/s?k=The+Design+of+Everyday+Things) | [search](https://www.fnac.com/SearchResult/ResultList.aspx?Search=The+Design+of+Everyday+Things) |
| Nielsen | [search](https://www.amazon.fr/s?k=Usability+Engineering) | [search](https://www.fnac.com/SearchResult/ResultList.aspx?Search=Usability+Engineering) |
| Braun & Clarke | [search](https://www.amazon.fr/s?k=Thematic+Analysis+A+Practical+Guide) | [search](https://www.fnac.com/SearchResult/ResultList.aspx?Search=Thematic+Analysis+A+Practical+Guide) |
| Lazarus | [search](https://www.amazon.fr/s?k=Emotion+and+Adaptation) | [search](https://www.fnac.com/SearchResult/ResultList.aspx?Search=Emotion+and+Adaptation) |

### Spain (`es`)

| book | Amazon.es | Casa del Libro |
|---|---|---|
| Norman | [search](https://www.amazon.es/s?k=The+Design+of+Everyday+Things) | [search](https://www.casadellibro.com/busqueda-generica?busqueda=The+Design+of+Everyday+Things) |
| Nielsen | [search](https://www.amazon.es/s?k=Usability+Engineering) | [search](https://www.casadellibro.com/busqueda-generica?busqueda=Usability+Engineering) |
| Braun & Clarke | [search](https://www.amazon.es/s?k=Thematic+Analysis+A+Practical+Guide) | [search](https://www.casadellibro.com/busqueda-generica?busqueda=Thematic+Analysis+A+Practical+Guide) |
| Lazarus | [search](https://www.amazon.es/s?k=Emotion+and+Adaptation) | [search](https://www.casadellibro.com/busqueda-generica?busqueda=Emotion+and+Adaptation) |

### Catalonia (`ca`)

| book | La Central | Amazon.es |
|---|---|---|
| Norman | [search](https://www.lacentral.com/web/cercador?q=The+Design+of+Everyday+Things) | [search](https://www.amazon.es/s?k=The+Design+of+Everyday+Things) |
| Nielsen | [search](https://www.lacentral.com/web/cercador?q=Usability+Engineering) | [search](https://www.amazon.es/s?k=Usability+Engineering) |
| Braun & Clarke | [search](https://www.lacentral.com/web/cercador?q=Thematic+Analysis+A+Practical+Guide) | [search](https://www.amazon.es/s?k=Thematic+Analysis+A+Practical+Guide) |
| Lazarus | [search](https://www.lacentral.com/web/cercador?q=Emotion+and+Adaptation) | [search](https://www.amazon.es/s?k=Emotion+and+Adaptation) |

### Italy (`it`)

| book | Amazon.it | IBS |
|---|---|---|
| Norman | [search](https://www.amazon.it/s?k=The+Design+of+Everyday+Things) | [search](https://www.ibs.it/search/?ts=as&query=The+Design+of+Everyday+Things) |
| Nielsen | [search](https://www.amazon.it/s?k=Usability+Engineering) | [search](https://www.ibs.it/search/?ts=as&query=Usability+Engineering) |
| Braun & Clarke | [search](https://www.amazon.it/s?k=Thematic+Analysis+A+Practical+Guide) | [search](https://www.ibs.it/search/?ts=as&query=Thematic+Analysis+A+Practical+Guide) |
| Lazarus | [search](https://www.amazon.it/s?k=Emotion+and+Adaptation) | [search](https://www.ibs.it/search/?ts=as&query=Emotion+and+Adaptation) |

### Netherlands (`nl`)

| book | Bol.com | Amazon.nl |
|---|---|---|
| Norman | [search](https://www.bol.com/nl/nl/s/?searchtext=The+Design+of+Everyday+Things) | [search](https://www.amazon.nl/s?k=The+Design+of+Everyday+Things) |
| Nielsen | [search](https://www.bol.com/nl/nl/s/?searchtext=Usability+Engineering) | [search](https://www.amazon.nl/s?k=Usability+Engineering) |
| Braun & Clarke | [search](https://www.bol.com/nl/nl/s/?searchtext=Thematic+Analysis+A+Practical+Guide) | [search](https://www.amazon.nl/s?k=Thematic+Analysis+A+Practical+Guide) |
| Lazarus | [search](https://www.bol.com/nl/nl/s/?searchtext=Emotion+and+Adaptation) | [search](https://www.amazon.nl/s?k=Emotion+and+Adaptation) |

### Poland (`pl`)

| book | Empik | Amazon.pl |
|---|---|---|
| Norman | [search](https://www.empik.com/szukaj/produkt?q=The+Design+of+Everyday+Things) | [search](https://www.amazon.pl/s?k=The+Design+of+Everyday+Things) |
| Nielsen | [search](https://www.empik.com/szukaj/produkt?q=Usability+Engineering) | [search](https://www.amazon.pl/s?k=Usability+Engineering) |
| Braun & Clarke | [search](https://www.empik.com/szukaj/produkt?q=Thematic+Analysis+A+Practical+Guide) | [search](https://www.amazon.pl/s?k=Thematic+Analysis+A+Practical+Guide) |
| Lazarus | [search](https://www.empik.com/szukaj/produkt?q=Emotion+and+Adaptation) | [search](https://www.amazon.pl/s?k=Emotion+and+Adaptation) |

### Brazil (`pt-BR`)

| book | Amazon.com.br | Livraria Cultura |
|---|---|---|
| Norman | [search](https://www.amazon.com.br/s?k=The+Design+of+Everyday+Things) | [search](https://www.livrariacultura.com.br/busca?q=The+Design+of+Everyday+Things) |
| Nielsen | [search](https://www.amazon.com.br/s?k=Usability+Engineering) | [search](https://www.livrariacultura.com.br/busca?q=Usability+Engineering) |
| Braun & Clarke | [search](https://www.amazon.com.br/s?k=Thematic+Analysis+A+Practical+Guide) | [search](https://www.livrariacultura.com.br/busca?q=Thematic+Analysis+A+Practical+Guide) |
| Lazarus | [search](https://www.amazon.com.br/s?k=Emotion+and+Adaptation) | [search](https://www.livrariacultura.com.br/busca?q=Emotion+and+Adaptation) |

### Portugal (`pt-PT`)

| book | Wook | Bertrand |
|---|---|---|
| Norman | [search](https://www.wook.pt/pesquisa/The%20Design%20of%20Everyday%20Things) | [search](https://www.bertrand.pt/pesquisa/The%20Design%20of%20Everyday%20Things) |
| Nielsen | [search](https://www.wook.pt/pesquisa/Usability%20Engineering) | [search](https://www.bertrand.pt/pesquisa/Usability%20Engineering) |
| Braun & Clarke | [search](https://www.wook.pt/pesquisa/Thematic%20Analysis%20A%20Practical%20Guide) | [search](https://www.bertrand.pt/pesquisa/Thematic%20Analysis%20A%20Practical%20Guide) |
| Lazarus | [search](https://www.wook.pt/pesquisa/Emotion%20and%20Adaptation) | [search](https://www.bertrand.pt/pesquisa/Emotion%20and%20Adaptation) |

### Sweden (`sv`)

| book | Adlibris | Bokus |
|---|---|---|
| Norman | [search](https://www.adlibris.com/se/sok?q=The+Design+of+Everyday+Things) | [search](https://www.bokus.com/cgi-bin/product_search.cgi?search_word=The+Design+of+Everyday+Things) |
| Nielsen | [search](https://www.adlibris.com/se/sok?q=Usability+Engineering) | [search](https://www.bokus.com/cgi-bin/product_search.cgi?search_word=Usability+Engineering) |
| Braun & Clarke | [search](https://www.adlibris.com/se/sok?q=Thematic+Analysis+A+Practical+Guide) | [search](https://www.bokus.com/cgi-bin/product_search.cgi?search_word=Thematic+Analysis+A+Practical+Guide) |
| Lazarus | [search](https://www.adlibris.com/se/sok?q=Emotion+and+Adaptation) | [search](https://www.bokus.com/cgi-bin/product_search.cgi?search_word=Emotion+and+Adaptation) |

### Norway (`nb`)

| book | Ark | Adlibris |
|---|---|---|
| Norman | [search](https://www.ark.no/search?text=The+Design+of+Everyday+Things) | [search](https://www.adlibris.com/no/sok?q=The+Design+of+Everyday+Things) |
| Nielsen | [search](https://www.ark.no/search?text=Usability+Engineering) | [search](https://www.adlibris.com/no/sok?q=Usability+Engineering) |
| Braun & Clarke | [search](https://www.ark.no/search?text=Thematic+Analysis+A+Practical+Guide) | [search](https://www.adlibris.com/no/sok?q=Thematic+Analysis+A+Practical+Guide) |
| Lazarus | [search](https://www.ark.no/search?text=Emotion+and+Adaptation) | [search](https://www.adlibris.com/no/sok?q=Emotion+and+Adaptation) |

### Denmark (`da`)

| book | Saxo | Williams Dam |
|---|---|---|
| Norman | [search](https://www.saxo.com/dk/products/search?query=The+Design+of+Everyday+Things) | [search](https://www.williamdam.dk/search?q=The+Design+of+Everyday+Things) |
| Nielsen | [search](https://www.saxo.com/dk/products/search?query=Usability+Engineering) | [search](https://www.williamdam.dk/search?q=Usability+Engineering) |
| Braun & Clarke | [search](https://www.saxo.com/dk/products/search?query=Thematic+Analysis+A+Practical+Guide) | [search](https://www.williamdam.dk/search?q=Thematic+Analysis+A+Practical+Guide) |
| Lazarus | [search](https://www.saxo.com/dk/products/search?query=Emotion+and+Adaptation) | [search](https://www.williamdam.dk/search?q=Emotion+and+Adaptation) |

### Finland (`fi`)

| book | Suomalainen | Adlibris |
|---|---|---|
| Norman | [search](https://www.suomalainen.com/search?q=The+Design+of+Everyday+Things) | [search](https://www.adlibris.com/fi/haku?q=The+Design+of+Everyday+Things) |
| Nielsen | [search](https://www.suomalainen.com/search?q=Usability+Engineering) | [search](https://www.adlibris.com/fi/haku?q=Usability+Engineering) |
| Braun & Clarke | [search](https://www.suomalainen.com/search?q=Thematic+Analysis+A+Practical+Guide) | [search](https://www.adlibris.com/fi/haku?q=Thematic+Analysis+A+Practical+Guide) |
| Lazarus | [search](https://www.suomalainen.com/search?q=Emotion+and+Adaptation) | [search](https://www.adlibris.com/fi/haku?q=Emotion+and+Adaptation) |

### Czechia (`cs`)

| book | Kosmas | Databáze knih |
|---|---|---|
| Norman | [search](https://www.kosmas.cz/hledani/?q=The+Design+of+Everyday+Things) | [search](https://www.databazeknih.cz/search?q=The+Design+of+Everyday+Things) |
| Nielsen | [search](https://www.kosmas.cz/hledani/?q=Usability+Engineering) | [search](https://www.databazeknih.cz/search?q=Usability+Engineering) |
| Braun & Clarke | [search](https://www.kosmas.cz/hledani/?q=Thematic+Analysis+A+Practical+Guide) | [search](https://www.databazeknih.cz/search?q=Thematic+Analysis+A+Practical+Guide) |
| Lazarus | [search](https://www.kosmas.cz/hledani/?q=Emotion+and+Adaptation) | [search](https://www.databazeknih.cz/search?q=Emotion+and+Adaptation) |

### Russia (`ru`)

| book | Labirint | Chitai-gorod |
|---|---|---|
| Norman | [search](https://www.labirint.ru/search/The%20Design%20of%20Everyday%20Things/) | [search](https://www.chitai-gorod.ru/search?phrase=The+Design+of+Everyday+Things) |
| Nielsen | [search](https://www.labirint.ru/search/Usability%20Engineering/) | [search](https://www.chitai-gorod.ru/search?phrase=Usability+Engineering) |
| Braun & Clarke | [search](https://www.labirint.ru/search/Thematic%20Analysis%20A%20Practical%20Guide/) | [search](https://www.chitai-gorod.ru/search?phrase=Thematic+Analysis+A+Practical+Guide) |
| Lazarus | [search](https://www.labirint.ru/search/Emotion%20and%20Adaptation/) | [search](https://www.chitai-gorod.ru/search?phrase=Emotion+and+Adaptation) |

### Ukraine (`uk`)

| book | Yakaboo |
|---|---|
| Norman | [search](https://www.yakaboo.ua/ua/search/?query=The+Design+of+Everyday+Things) |
| Nielsen | [search](https://www.yakaboo.ua/ua/search/?query=Usability+Engineering) |
| Braun & Clarke | [search](https://www.yakaboo.ua/ua/search/?query=Thematic+Analysis+A+Practical+Guide) |
| Lazarus | [search](https://www.yakaboo.ua/ua/search/?query=Emotion+and+Adaptation) |

### Turkey (`tr`)

| book | Kitapyurdu | Idefix |
|---|---|---|
| Norman | [search](https://www.kitapyurdu.com/index.php?route=product/search&filter_name=The+Design+of+Everyday+Things) | [search](https://www.idefix.com/search?Q=The+Design+of+Everyday+Things) |
| Nielsen | [search](https://www.kitapyurdu.com/index.php?route=product/search&filter_name=Usability+Engineering) | [search](https://www.idefix.com/search?Q=Usability+Engineering) |
| Braun & Clarke | [search](https://www.kitapyurdu.com/index.php?route=product/search&filter_name=Thematic+Analysis+A+Practical+Guide) | [search](https://www.idefix.com/search?Q=Thematic+Analysis+A+Practical+Guide) |
| Lazarus | [search](https://www.kitapyurdu.com/index.php?route=product/search&filter_name=Emotion+and+Adaptation) | [search](https://www.idefix.com/search?Q=Emotion+and+Adaptation) |

### Japan (`ja`)

| book | Amazon.co.jp | honto |
|---|---|---|
| Norman | [search](https://www.amazon.co.jp/s?k=The+Design+of+Everyday+Things) | [search](https://honto.jp/netstore/search.html?k=The+Design+of+Everyday+Things) |
| Nielsen | [search](https://www.amazon.co.jp/s?k=Usability+Engineering) | [search](https://honto.jp/netstore/search.html?k=Usability+Engineering) |
| Braun & Clarke | [search](https://www.amazon.co.jp/s?k=Thematic+Analysis+A+Practical+Guide) | [search](https://honto.jp/netstore/search.html?k=Thematic+Analysis+A+Practical+Guide) |
| Lazarus | [search](https://www.amazon.co.jp/s?k=Emotion+and+Adaptation) | [search](https://honto.jp/netstore/search.html?k=Emotion+and+Adaptation) |

### Korea (`ko`)

| book | Kyobo | Yes24 |
|---|---|---|
| Norman | [search](https://search.kyobobook.co.kr/search?keyword=The+Design+of+Everyday+Things) | [search](https://www.yes24.com/product/search?query=The+Design+of+Everyday+Things) |
| Nielsen | [search](https://search.kyobobook.co.kr/search?keyword=Usability+Engineering) | [search](https://www.yes24.com/product/search?query=Usability+Engineering) |
| Braun & Clarke | [search](https://search.kyobobook.co.kr/search?keyword=Thematic+Analysis+A+Practical+Guide) | [search](https://www.yes24.com/product/search?query=Thematic+Analysis+A+Practical+Guide) |
| Lazarus | [search](https://search.kyobobook.co.kr/search?keyword=Emotion+and+Adaptation) | [search](https://www.yes24.com/product/search?query=Emotion+and+Adaptation) |

### Taiwan (`zh-Hant`)

| book | 博客來 books.com.tw |
|---|---|
| Norman | [search](https://search.books.com.tw/search/query/key/The%20Design%20of%20Everyday%20Things) |
| Nielsen | [search](https://search.books.com.tw/search/query/key/Usability%20Engineering) |
| Braun & Clarke | [search](https://search.books.com.tw/search/query/key/Thematic%20Analysis%20A%20Practical%20Guide) |
| Lazarus | [search](https://search.books.com.tw/search/query/key/Emotion%20and%20Adaptation) |

### Hong Kong (`zh-Hant-HK`)

| book | 博客來 books.com.tw | Eslite |
|---|---|---|
| Norman | [search](https://search.books.com.tw/search/query/key/The%20Design%20of%20Everyday%20Things) | [search](https://www.eslite.com/Search?keyword=The+Design+of+Everyday+Things) |
| Nielsen | [search](https://search.books.com.tw/search/query/key/Usability%20Engineering) | [search](https://www.eslite.com/Search?keyword=Usability+Engineering) |
| Braun & Clarke | [search](https://search.books.com.tw/search/query/key/Thematic%20Analysis%20A%20Practical%20Guide) | [search](https://www.eslite.com/Search?keyword=Thematic+Analysis+A+Practical+Guide) |
| Lazarus | [search](https://search.books.com.tw/search/query/key/Emotion%20and%20Adaptation) | [search](https://www.eslite.com/Search?keyword=Emotion+and+Adaptation) |

### Author-only fallback

| author | Amazon (any market — swap the TLD) |
|---|---|
| Norman | `https://www.amazon.<tld>/s?k=Don+Norman` |
| Nielsen | `https://www.amazon.<tld>/s?k=Jakob+Nielsen` |
| Braun & Clarke | `https://www.amazon.<tld>/s?k=Braun+Clarke` |
| Lazarus | `https://www.amazon.<tld>/s?k=Richard+Lazarus` |

Swap `<tld>` for `de`, `fr`, `es`, `it`, `nl`, `pl`, `co.jp`, `com.br`.

---

## Answers to the two open calls, from the Swift-strings session (21 Sep 2026)

This session asked the Swift English-strings audit session for a call on §"Open
questions for the pass" items (a) and (b), plus the fourth-class item left open
in the taxonomy. Its answers, kept whole so the reasoning travels with them.
**It had not read the nine webview templates** — its Welcome work was the native
sentiment fan and nothing else — so these are judgements about the *rules*, not
about the templates, and nothing here duplicates this doc's own analysis.

**(a) The illustration should NOT say "Conc." Give it its own key.**

An abbreviation is an English orthographic convention, not a word. "Conc."
abbreviates "Concentration" in English; the Polish, Finnish or Japanese term may
not abbreviate at all, or abbreviate at a different cut. Word-for-word here does
not preserve our copy — it exports an English convention into twenty languages
that do not share it, and asks a Japanese translator to shorten 集中度 to match a
column width that exists in a different surface.

There is settled precedent for calling this a **fork** rather than drift:
`docs/i18n-defects.md` Decision 3, closed 21 Sep 2026. Three of twenty-three
mirrored CLI/SPA strings diverge, every one of them a technical name in the
terminal against a plain name in the SPA, and the conclusion recorded there is
that *"keep both in sync" is the wrong instruction and no equality check should
be written*. Same structure: the lens abbreviates under a column width, the
illustration spells out under a teaching job. Put the reason in a comment at the
site so a later sweep cannot "fix" the two into each other.

**(b) Per-locale data — and the plan's own inconsistency is the tell.**

Commissioning per-locale participant names and filenames *is* the decision;
"one study told in every language" with localised names is the worst available
cell, because a study whose metadata is Japanese and whose quotes are English
reads as a tool that was translated rather than one that fits. §8's disfluency
token array forces the answer regardless — a translated sentence destroys the
demonstration, so one class-C item must be written per locale already, and one
is enough to settle the taxonomy.

Scope it as the repo scopes everything else here: machine-written sample data
pending native review has the same standing as the ten machine-seeded locales
that already ship. "Needs a native writer" must not become "never".

**The fourth class (our own English-by-design surfaces) — close it English.**

The Miro sticky's count comes from `count_noun`, and a translated sticky depicts
a board Bristlenose has never produced. That is the same defect as a translated
"Thinking…", decided the same way, by the rule this doc already applies to
third-party UI: depict what actually ships. `docs/design-i18n.md` §"Which
surfaces are targets" now states CLI-English as permanent rather than interim,
and carries a second row (the icon picker) for a surface that is English
*because of what it does for the reader*. This fourth class is not an exception
to the taxonomy — it is the taxonomy working.

**On §5, whether the native fit approach transfers.** The rule does, the
arithmetic does not. `fitScale(in:)` / `rowWidth(_:)` on the sentiment fan
compute widths from a known chip set only because SwiftUI would not measure the
text; the constants are tuned to that set and port to nothing. What generalises
is *measure the content, not the container* — which is exactly this doc's
`offsetWidth`-on-a-hard-440px finding, and a webview can measure real laid-out
text at render time, a capability the native side lacks. The webview half is the
stronger one.

Its added warning: `overflow:hidden` + `white-space:nowrap` is worse than
truncation, because the label does not shorten, it disappears. One gate that
renders each template at the tightest supported width in the longest locale and
asserts nothing has zero measured height would catch the class; absence is the
failure mode, and absence is what screenshot review does not catch.

**On §9, the literal-scanning gate.** Independently confirmed the same day, from
the other side. A `.failed("…")` literal scanner built for the pipeline-failure
work fired on `DoctorReportView`'s unrelated `.failed(String)` enum — System
Health, English by decision. The fix was to anchor on something structurally
unique to the call meant (`category:` as the second argument), never on the
text. Same instrument, same failure, same repair shape; this doc's "Settings"
example is that trap one layer meaner, because there the fix the gate names is
actively wrong.

**On §1.** Ship it first and alone. Nine illustrations that never reload on a
locale change make every other item here invisible when it lands — the whole
content pass would go in and nothing would appear to change. It is small,
verifiable by eye, and it is the difference between the rest of the work being
testable and not.
