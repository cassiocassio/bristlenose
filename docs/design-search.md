---
status: proposed
updated: 28 Sep 2026
---

# Search: suggestions, recognisers and tokens

The toolbar search field grows from a substring filter into a field that
**offers** what it recognises as you type (a person, a tag) and turns a chosen
suggestion into a **token** whose meaning can be changed from a menu. This doc
specifies the first slice, ideas 01–03 of `docs/mockups/search-ideas.html`, in
the Quotes lens. The frame-by-frame flow is `docs/mockups/search-flow.html`.

Background research: `docs/research/federated-search.md` (notes in `docs/research/federated-search-notes/`). Per-lens and
global proposals: `docs/mockups/toolbar-search.html`.

## 1. Decisions

Settled by the maintainer on 28 Sep 2026. Build on them, don't reopen them.

| # | Decision | Consequence for this slice |
|---|---|---|
| D1 | The long-term engine is **SQLite FTS5 + Python**, shared by CLI, SPA and MCP. Core Spotlight is rejected. | Not built here. The matching rules below are pinned by a fixture so that core can be held to the same answers. |
| D2 | The **first slice is TypeScript**, over data the SPA already holds. | No server work, no network call per keystroke. Works in serve mode, in the Mac app and in the offline HTML export. |
| D3 | On the Mac, the **suggestions menu is native**, fed by the SPA. | The SPA computes suggestions and posts them over the bridge; SwiftUI draws them. One recogniser, drawn natively per surface. |
| D4 | **Words typed together match together**, in order, from the start of a word: `want to go` finds *I want to go home*, never *want*, *to* and *go* scattered. A **"quoted"** term matches as exact text anywhere. *Revised 3 Oct 2026; it was "each typed word matches on its own, in any order". It is a quote engine: several typed words are something somebody said.* | People and tags are tokens (D6), so a query need not cross fields to find "Tom" and "delivery"; `tom "delivery"` still does. |
| D5 | First recognisers: **phrase, word, participant code (speaker badge), participant name, tag**. | Sentiment, timecode, date, section, signal, session: later. |
| D6 | **Tokens have a meaning menu** from the start: person = *said by / mentions / not*; tag = *tagged / text contains / not tagged*. | |
| D7 | The **"Ask the report"** question row comes **later**. | Not in this slice. |
| D8 | **⌥⌘F returns to search** when project-wide search ships (Mail: ⌘F current lens, ⌥⌘F project). | Not in this slice; ⌘F keeps focusing the field. |

## 2. Scope of slice 1

**In:** the Quotes lens, on both surfaces (browser SPA, Mac app).

- Suggestions menu under the field (idea 01): a free-text row, then people, then tags.
- Recognisers for badge, name and tag (idea 02).
- Person and tag tokens with meaning menus (idea 03).
- Per-word and quoted-phrase matching (D4), with highlights to match.

**Out, and where it goes:**

| Not in slice 1 | Where it goes |
|---|---|
| Results pseudo-lens, ⌘↩, scope bar | Idea 04 |
| Search-and-code | Idea 05 |
| Transcript Find with ⌘G | Idea 06, a separate track that needs none of this |
| Recents and saved searches | Ideas 11 and 15 |
| Sessions, Codebook and Signals lens search | Idea 14 |
| Folder scope | Idea 10 |
| Server search, MCP reuse | D1 |
| Curation filters as a menu (needs review, edited, hidden) | `design-quotes-filter-menu.md`, a door onto the same P2 predicate |

## 3. Matching rules (the contract)

One module, `frontend/src/utils/searchMatch.ts`, used by the filter, the
highlights and every recogniser. Pinned by
`tests/fixtures/search-match-contract.json` (asserted by vitest now; the Python
core asserts the same file when it lands).

1. **Folding.** Case, diacritics and compatibility forms fold: `Jose` finds
   `José`, `е` finds `ё`, `ＡＢＣ` finds `abc`, `strasse` finds `Straße`, and
   Greek final `ς` is `σ`. Latin letters with no Unicode decomposition fold
   by lodash's `deburr` table: `soren` finds `Søren`, `lodz` finds `Łódź`,
   `oeuvre` finds `œuvre`. Curly and straight apostrophes are equal.
   Whitespace runs are one space, and invisible characters (soft hyphen,
   zero-width space, emoji skin tones) are ignored. **Punctuation is
   whitespace** on both sides, so `yes it was` finds *Yes, it was* and
   `well known` finds *well-known*; transcripts are full of commas. An
   apostrophe at the edge of a word drops on both sides (*students’ work*,
   *‘than the’*); one inside a word stays (*don't*).
   **Accents are folded only where they are optional:** Latin, Greek,
   Cyrillic, Arabic and Hebrew. In Japanese, Thai and Hindi a combining mark
   changes the word (`パン` is bread, `ハン` is not), so it is kept, and a match
   may not end just before one (`ハ` does not find `パ`).
2. **Terms.** The words typed between quotes are one run, matched in order
   from the start of a word; the last word may still be being typed
   (`than the sh` finds *than the shelf*). Text inside double quotes
   (straight, curly, « », 「 」) is one phrase term, matched as **exact text,
   anywhere**: `"boarding was"` finds *onboarding was*. Quoting is how to
   search for a fragment, and it is what ⌘E (Use Selection for Find) sends, so
   a selection always finds the quote it came from. An unclosed quote runs to
   the end. Apostrophes at the edges of a run are dropped, so smart single
   quotes (‘than the’) act as the plain words. Each run and each phrase may
   match a different field (quote text, speaker, tag names, sentiment).
3. **Word-initial.** A word matches only at the start of a word (`st` finds
   *Storey*, not *best*). Exceptions: a quoted phrase (rule 2), and a term in
   Chinese, Japanese or Thai script, which matches anywhere because those
   scripts don't space words.
4. **All terms, any field.** A quote matches when **every** term matches in
   **some** searchable field. The fields are:
   - the quote text (the edited text if there is one);
   - the speaker name;
   - tag names;
   - the sentiment.

   So *tom delivery* finds Tom's quote about delivery.
5. **Activation.** Free text filters from **2 characters**, or 1 Chinese or
   Japanese character (today: 3; decided 3 Oct 2026). Characters are counted
   in the parsed terms, after folding: quote marks and edge apostrophes don't
   count (`''` and `'s` are not searches), and a letter written with a
   separate accent counts once.
   Recognisers run from **1 character**.
6. **Highlights** mark every matching occurrence of every term, on the original
   (unfolded) text.

Known limits, accepted:

- Turkish dotless *ı* does not fold to *i*.
- German *ü* does not match *ue*.
- Korean particles (*서울에서*) match by prefix only (*서울* finds it; *에서* does not).
  Within a syllable a prefix does match, as the keyboard composes it (*서우* finds *서울*).
- An apostrophe is a word boundary, so *brien* finds *O'Brien* and *re* marks *they're*.
- No typo tolerance until the Python core lands.

## 4. Recognisers

Each recogniser reads the raw query and **offers** rows. It never applies
anything by itself (research: users pick a suggestion in about a quarter of
searches, so free text must stay the default action).

| Row | Candidates | Recognised when | Count shown | Cap |
|---|---|---|---|---|
| **Free text** | the query itself | query is active (§3.5) | quotes that would be visible | always first |
| **Person** | every speaker code in the project's people list or on any quote; names from the people list (full and short) | every query word matches the start of the code or of a name word (*p3*, *pri*, *shah*) | quotes that person said, under the current tokens | 3 |
| **Tag** | every tag name on any quote (store edits included) | every query word matches the start of a word in the tag name | quotes carrying that tag, under the current tokens | 3 |

Ordering within a group: exact match first (*p3* typed, *p3* offered), then by
count, then by name. **A row whose count is 0 is not offered**, except the
free-text row. **A candidate already present as a token is not offered.**
Moderators (*m1*) appear only when they have quotes; speaker role is detected
by code prefix, never by the stored role (`frontend/CLAUDE.md`).

**Row anatomy.** There are two kinds of row, and the count is always right-aligned.

- **Rows that point at a lens** (free text now; transcripts, sections and
  signals later) take that lens's own glyph. It's an SF Symbol on the Mac, the
  same one the lens uses in the app (`LensItem.swift`): Quotes `text.quote`,
  Sessions `person.2`, Codebooks `tag`, Signals `square.grid.3x3`, Project
  `target`, transcripts `doc.text`. The label follows Photos: **typed letters
  in primary text, the rest in secondary**.
- **Rows that name a thing that has a badge** (people and tags) show **the
  badge itself**, exactly as it looks on a quote card, and no glyph. The badge
  is the recognition. A person row is the split speaker badge `p3 | Priya`; a
  tag row is the tag's coloured `.badge`. Typed-letter emphasis is not drawn
  inside a badge, because that would make it differ from the badge on the card.
  The free-text row above it already shows what was typed.

In the browser the lens glyphs are our own SVGs drawn to match. SF Symbols
may not be shipped in a web page, and the SPA has no lens icons today.

## 5. Tokens

```ts
type PersonMode = "said" | "mentions" | "not";
type TagMode = "tagged" | "contains" | "not";
type SearchToken =
  | { kind: "person"; code: string; names: string[]; mode: PersonMode }
  | { kind: "tag"; name: string; mode: TagMode };
```

| Token | Meaning | A quote passes when |
|---|---|---|
| Person | **Said by** (default) | its `participant_id` is the code |
| Person | **Mentions** | its text contains one of the person's names as **whole words**: *Tom* finds *Tom said* and *Tom's*, never *Tomorrow*. Korean may be followed directly by a particle (*김민지가*); Chinese and Japanese match anywhere. Disabled in the menu when the person has no name, only a code. |
| Person | **Not** | its `participant_id` is not the code |
| Tag | **Tagged** (default) | it carries the tag (store edits included) |
| Tag | **Text contains** | its text contains the tag name as whole words (*price*, not *pricey*) |
| Tag | **Not tagged** | it does not carry the tag |

- **A token is the real badge inside a light container**: the meaning word
  (*said by*, *mentions*, *not*, *tagged*, *contains*, *not tagged*), then the
  badge exactly as it appears on a quote card, then a ▾ disclosure. Only the
  container and the word are new; the badge is not restyled (§7a).
- **Text means what the card shows**: the researcher's edit if there is one,
  including one made this session (QuotesStore `edits`), for typed words,
  *mentions* and *text contains* alike.
- **A token is addressed by its person or tag, never its position**, so a
  meaning menu left open on one token can't act on another after the list
  changes under it.
- Tokens and free text combine with **AND**. Tokens sit before the free text,
  as in Mail.
- Tokens apply **on top of** hidden, starred and the tag sidebar. They never
  change the sidebar's state; the two are independent filters.
- Highlights: *mentions* and *text contains* tokens also highlight their
  phrase, so a hit that doesn't contain the typed word still shows why it
  matched.
- **Lifetime.** Tokens last for the session, like the query. They are not
  restored after a relaunch (`LensMemory.swift:25`) and do not follow a lens
  switch in slice 1.

## 6. Interaction (browser)

The field keeps today's collapsible behaviour. When focused and holding
recognised text, a menu opens under it.

| Input | Menu open | Menu closed |
|---|---|---|
| typing | recompute rows; keep the highlighted row while it is still offered (rows are addressed by id), else row 1 (free text) | open when there are rows. Only an edit opens it: text the store or a lens switch puts back does not |
| ↓ / ↑ | move the highlight (wraps) | open the menu |
| ↩ | apply the highlighted row. A free-text row commits the query now (no debounce wait); a person or tag row becomes a token and **clears the typed text** | commit the query |
| Esc | close the menu | empty the field, text **and** tokens, as ⓧ does and as Mail's field does (decided 3 Oct 2026, §12 Q2); on the Mac it also collapses the field |
| ⌫ in an empty input | — | first press selects the last token, second removes it |
| click a token | — | opens its meaning menu (radio items + Remove) |
| blur | close the menu | — |

Accessibility: WAI-ARIA combobox. The input carries `role="combobox"`,
`aria-expanded` and `aria-activedescendant`; the menu is a `listbox` with
labelled groups; token menus are `menu` with `menuitemradio`. There is one
polite live-region announcement per settled query, of the form
*"23 quotes · 2 suggestions"*, not one per row.

## 7. Mac

The field is the native capsule (`QuotesToolbarControls.swift`). The web
toolbar stays hidden in embedded mode.

- **Tokens render as native chips inside the field, before the text.** A chip
  is a button that opens a real `NSMenu` of the meanings (the chosen one
  ticked, *mentions* dimmed for a code-only person) and Remove. Not a SwiftUI
  `Menu`: on macOS it flattens its label to a title and cannot draw the
  coloured badge. (`SearchFieldViews.swift`, built 3 Oct 2026.)
- **The suggestions list is native**: a borderless child window under the
  field that never becomes key, so the caret stays in the field while it is
  open. That is the pattern of Apple's *CustomMenus* sample and of Safari's
  address bar; a popover was the first plan and would take key status from
  the field mid-typing. Rows carry the Quotes lens's SF Symbol for the free
  text and the badge itself for people and tags, with the count right-aligned;
  the highlight is the system selection. ↑/↓ move it (wrapping), ↩ chooses,
  Esc closes the list and then empties the field, a click chooses, and ⌫ in
  an empty field selects the last token and then removes it.
- **The SPA stays the source of truth.** Native sends keystrokes (as today) and
  user choices; the SPA recognises, applies, and posts back state.

Bridge contract (additions to `frontend/src/shims/bridge.ts` and `BridgeHandler.swift`):

| Direction | Message | Payload |
|---|---|---|
| native → web | `setSearchQuery` (exists) | `{text}` |
| web → native | `search-suggestions` | `{query, rows: [{id, kind, label, typed: [[start,end]], count, code?}]}`: labels are **already localised** by the SPA; `id` is stable for the subject (`text`, `person:<code>`, `tag:<folded name>`), so a stale click still applies what was clicked; `typed` offsets are UTF-16; person rows carry their `code` |
| native → web | `applySearchSuggestion` | `{id}` |
| web → native | `quotes-filter` (exists, grows) | `{searchQuery, viewMode, tokens: [{kind, subject, styleKey, label, removeLabel, mode, modes: [{id, label, word, enabled}]}]}`: `styleKey` is the speaker code or the **folded** tag name, so Swift never reimplements `fold`; `word` is what the chip shows for that meaning (*said by*) and `removeLabel` the menu's last item |
| web → native | `search-badge-styles` | `{tags: {<folded name>: BadgeStyle}, people: {<code>: {code: BadgeStyle, name: BadgeStyle \| null}}}`, keyed as `styleKey` and a row id's suffix; colours as display-P3 components (§7a) |
| native → web | `setSearchTokenMode` | `{subject, mode}`: `subject` is `{kind: "person", code}` or `{kind: "tag", name}`, never a position (§5) |
| native → web | `removeSearchToken` | `{subject}` |

Because the SPA sends labels, the native side adds **no** locale keys for rows
or meanings. The Swift parity rule applies: every new field gets its Swift
mirror and a round-trip test (`CLAUDE.md`, the wire-contract gotcha).

### 7a. Visual parity: badges look the same on both sides of the seam

**Rule.** A tag or speaker badge drawn natively (in a suggestion row or a token
chip) is indistinguishable from the same badge on a quote card in the web view.
That means the same colours, font, size, weight, padding, radius and border, in
light, dark, the default palette and Edo. This is the seam-alignment
discipline in `docs/design-native-colour-alignment.md` §Principles, applied to
the badge.

**Mechanism: the SPA sends resolved styles; Swift holds no palette copy.** The
tag colours are CSS variables chosen by colour set and index
(`utils/colours.ts` `getTagBg`), per palette and per scheme. A Swift table of
hex values would be a second copy that drifts. (The Welcome screen's sentiment
chips are that kind of copy, hand-kept in `WelcomeIllustrations.swift`.) So:

1. The SPA renders a hidden probe of the real component: a `Badge` for a tag,
   the split `PersonBadge` for a person, inside the app root so the palette
   and display attributes apply. It reads `getComputedStyle` from it and sends
   the resolved values as their own message, `search-badge-styles`, keyed the
   way rows and tokens already name their subjects (`utils/badgeStyle.ts`):

   ```ts
   interface P3Colour { r: number; g: number; b: number; a: number } // 0…1
   interface BadgeStyle {
     bg: P3Colour | null;            // null: no fill
     fg: P3Colour;
     border: { colour: P3Colour; widthPx: number } | null;
     fontFamily: "mono" | "body";
     sizePx: number;
     weight: number;
     padX: number;                   // left
     padY: number;                   // top
     padRight: number;               // a name half is padded on one side only
     padBottom: number;
     lineHeightPx: number | null;    // null: the CSS left it `normal`
     radius: number;
   }
   // { tags: {<folded name>: BadgeStyle},
   //   people: {<code>: { code: BadgeStyle, name: BadgeStyle | null }} }
   ```

   Colours go as display-P3 components, read back from a 1×1 P3 canvas, so
   Swift builds `Color(.displayP3, …)` without parsing CSS. Each message
   replaces the last and carries only the badges the menu and chips show.

2. Swift paints exactly those values:
   - `Font.system(size:weight:design:)`, with `.monospaced` for mono. That
     resolves to SF Mono, which is what `--bn-font-mono` resolves to in
     WKWebView.
   - The numeric weight mapped to the nearest `Font.Weight`.
   - Points taken 1:1 from pixels, which is how the webview renders them.
3. **The styles are re-sent when anything that changes them changes**: the
   palette, the appearance (light or dark), the display mode (code only, or
   code and name), and any tag's colour. The SPA caches each measurement by
   appearance (`data-theme`, `data-color-theme`, `data-person-display`, and
   the system scheme) and by the tag's colour set and index, so it measures
   only what is new and a recolour in the codebook re-measures that tag.
4. **Swift drops what it cannot read** (`SearchBridge.swift`
   `SearchBadgeStyles`): an entry missing a field is left out, a font family
   it does not know is drawn in the body font, and a malformed name half
   draws the code alone. A badge with no style is drawn plainly rather than
   guessed at. An SPA that sends no `padRight`/`padBottom` means "as left and
   top" (added 3 Oct 2026, when the name half drew 1.6 px short on the right
   and 0.5 px short in height without them).

**Tests.**

- A vitest asserts that the probe reads the same values the rendered badge
  has, so the probe can't drift from `Badge`.
- A Swift snapshot test renders a chip from a fixture `BadgeStyle` and
  compares it against a PNG of the web badge at the same scale, within a small
  tolerance. It's cheap, and it catches a wrong weight mapping or padding.
- Human QA puts the native token beside the same badge on a quote card, in
  both palettes and both schemes, and checks it with Digital Color Meter.

## 8. i18n

New keys in `common.json`, in all 21 full locales (not `zh-Hant-HK`). **Seeded 4 Oct 2026** for the keys the Mac menu and chips read (`textRow`, the six menu labels, the six chip words, `remove`), with English pinned in `en-value-pins.json`; `people`, `tags` and `announce` wait for the browser UI that reads them. In pl, ru, uk, cs, fi and tr the person labels take a colon form (*Mówi: Priya*) so a name is never inflected wrongly:

| Key | English |
|---|---|
| `search.suggest.textRow` | Quotes containing “{{query}}” |
| `search.suggest.people` | People (group label, screen readers) |
| `search.suggest.tags` | Tags (group label, screen readers) |
| `search.token.person.said` | Said by {{name}} |
| `search.token.person.mentions` | Mentions {{name}} |
| `search.token.person.not` | Not {{name}} |
| `search.token.tag.tagged` | Tagged “{{tag}}” |
| `search.token.tag.contains` | Text contains “{{tag}}” |
| `search.token.tag.not` | Not tagged “{{tag}}” |
| `search.token.remove` | Remove |
| `search.token.person.saidWord` | said by (the chip's word, lower case) |
| `search.token.person.mentionsWord` | mentions |
| `search.token.person.notWord` | not |
| `search.token.tag.taggedWord` | tagged |
| `search.token.tag.containsWord` | contains |
| `search.token.tag.notWord` | not tagged |
| `search.announce` | {{count}} quotes (CLDR plurals) |

Each locale uses its own quotation marks; don't copy the English `“ ”`.
`search.placeholder` changes from *Filter quotes…* to *Search quotes, people,
tags*. That is a 21-file reword (the i18n gotcha on rewording `en`), and
vitest must be re-run for any test quoting it.

## 9. Privacy

- Slice 1 makes no network call. The query never leaves the page, so it can't
  reach a server log. (The Python core must send queries in a POST body: under
  `-v` the access log prints query strings, and so would print a participant's
  name.)
- Names are searched **inside the project only**. Folder scope (idea 10) shows
  speaker codes only (`design-multi-project.md` §3c Finding 5).

## 10. Tests

| Layer | What it pins |
|---|---|
| `search-match-contract.json` + vitest | every rule in §3, including the known limits (so the Python core can't "fix" one silently) |
| `searchSuggest.test.ts` | the recognisers: exact-first ordering, the cap, zero-count rows hidden, tokened items excluded |
| `filter.test.ts` | each of the six token meanings; AND with text; token independence from the tag sidebar |
| `SearchBox.test.tsx` | the §6 table row by row, plus the ARIA attributes |
| bridge contract fixture + Swift round-trip | `search-suggestions` and `quotes-filter.tokens` decode, including an unknown future `kind` (ignored, not fatal) |
| human QA | the menu's feel in the browser; native chips and popover in the `.app` |

## 11. Build plan

Each phase ends green and committed.

| Phase | Work | Exit check |
|---|---|---|
| **P1 Matcher** | `searchMatch.ts`, contract fixture, `highlight.tsx` and `filter.ts` switched to it | vitest green; every shipped search behaviour still covered, the D4 change asserted. **Done 3 Oct 2026**: matcher and fixture (53 matching cases, 15 activation cases), then the Quotes filter, highlights, the "N matching" label, the search box and ⌘E (sends its selection as a quoted phrase) switched to it. A test pins that the search menu's count equals the list a researcher gets on ↩, with hidden, starred and store tag edits in play |
| **P2 Tokens** | token types + predicates; `searchTokens` in QuotesStore with add/remove/set-mode actions; **one** `filterStateOf(store)` replacing the six hand-built `FilterState`s (Toolbar, QuoteSections, QuoteThemes, ExportDropdown, LensSubtitleSync, `getVisibleQuotes`); highlight of mentions/contains | exports and subtitle counts honour tokens (asserted). **Done 3 Oct 2026**, headless (no way to add a token from the screen until P4): `utils/searchTokens.ts`; `filterStateOf` is referentially stable, so it sits in dependency lists as itself and a new filter (a token, a filter-menu row) is added once; the quote cards take parsed `highlight` terms instead of the raw query. Asserted: the web Export menu's scope, the native counts (`getVisibleQuotes`), the window subtitle and the "N matching" label all narrow with tokens; said-by/not and tagged/not-tagged partition a synthetic project exactly; mentions and contains agree with an independently written whole-word check |
| **P3 Recognisers** | `searchSuggest.ts`, pure; people from `getPeople()` (embedded in the export) | unit tests. **Done 3 Oct 2026**, headless: rule tests on a hand-built project, invariants and an independently written matcher over the seeded synthetic project (`searchSynthetic.ts`), and a 10,000-quote scale test (2–8 ms a keystroke warm, 17 ms cold, on an M-series Mac) |
| **P4 Browser UI** | **Built 4 Oct 2026** (`SearchBox.tsx` with `combo`, `searchKeys.ts`, CSS in `molecules/search.css`): the same rows, chips, meaning menus and keys as the Mac, from the same `searchSuggestionsFor` and `searchBridge` labels; a WAI-ARIA combobox (`aria-activedescendant`, options never focused), people and tags as labelled groups. With tokens the field shrinks and wraps its chips rather than spilling out of the column (the toolbar right-aligns). **Remaining:** the placeholder reword (§8) and the one-per-settled-query live announcement (§6) | vitest; `check-locales.py --strict`; browser QA |
| **P5 Mac** | **Native menu and chips built 3 Oct 2026** (`SearchFieldViews.swift`, wired in `QuotesToolbarControls.swift`); wording approved and the §8 keys seeded in 21 locales on 4 Oct 2026. **Plumbing done 3 Oct 2026**, headless: the menu, tokens and badge styles cross the bridge in both directions, pinned on both sides by `tests/fixtures/search-bridge-contract.json`; the `BadgeStyle` probe and its per-appearance cache in the SPA; Swift decodes and holds all three on `BridgeHandler`. **Remaining:** the badge snapshot test against a web PNG (§7a); VoiceOver for the list (it is a non-key window, so the field would need to announce the highlighted row) | `desktop/scripts/test-swift.sh`; `.app` QA side by side with the card badge, both palettes and schemes |
| **P6 Docs** | true `design-html-report.md`'s search section and `platform-text-map.md`; set this doc's status to shipped | — |

## 12. Open questions

1. ~~**Activation at 2 characters rather than 3.**~~ Decided 3 Oct 2026: 2.
2. ~~**The ⓧ button clears tokens as well as text.**~~ Decided 3 Oct 2026:
   ⓧ and Esc both empty the whole field, text and tokens, as Mail's does.
   Backspacing the text away is not a clear: tokens go one at a time.
   (`clearSearch` in QuotesContext; `SearchBox`'s `onClear`.)
3. **Mentions.** Names only, from the people list. Nicknames and "the
   moderator" are not recognised.
4. **No typed-letter emphasis inside badges** (§4). The badge is drawn exactly
   as on the card, and the free-text row shows what was typed. Alternative: a
   faint underline under the typed letters inside the badge, at the cost of
   exact parity.
5. **Tags with the same name in two codebooks are one suggestion.** The tag
   token filters by name (§5), so this is consistent today. It would
   over-count if a token ever filtered by codebook and name.
6. **The order of tied suggestions follows the runtime's collation.** The
   SPA computes the order once and both the browser and the native menu draw
   it, so the two surfaces agree. Pass the UI locale explicitly if the order
   must not depend on the machine.
7. **Short names that are ordinary words** (*Will*, *Grace*, *Mark*, *May*). Typed text is now a run (D4), so `will smith` finds the name and `will` still finds *William* from the start of the word. The open part is the *mentions* token:
   *mentions* matches them as whole words, so "I will" counts as mentioning
   Will. The highlight shows why each quote matched. The alternative, using
   only the full name when the short name is a dictionary word, would miss
   "Will said".
8. ~~**Tokens and a refetch.**~~ Decided 3 Oct 2026: the researcher never
   asks for a refetch. It comes from a run finishing, an AutoCode catch-up
   finishing in the background, or an AutoCode report being applied, so it
   keeps what they were looking at: the query, tokens, starred-only and the tag
   filter (`initFromQuotes(…, replace)`). It used to clear all four.
9. **Speaker codes are tokens.** Decided 3 Oct 2026: a code typed as a word
   and followed by a space (`p3 `, `M1 `) becomes a *said by* token; the space
   is what tells `m1` from the start of `m11`. Codes in a quoted phrase stay
   text, and only codes of people with a quote that is not hidden count
   (`takeCodeTokens`). Parked behind a flag for a day while nothing drew a
   token; **shipped 4 Oct 2026** once both fields drew chips, and the flag
   deleted.
   **Still open:** moderator codes are per session, so a *said by m1* token
   matches every session's first moderator. Participant codes are
   project-wide and unaffected.
10. **Who closes the native menu on the free-text row.** Choosing it leaves
    the query as typed (the contract's `commit-text`), so no new
    `search-suggestions` arrives to empty the menu. The native side should
    close it on that choice; the SPA cannot tell it to.
11. **Accepted 3 Oct 2026. Badge styles are keyed by folded tag name**, so two tags whose names
    differ only by case or accents share one style, as they share one
    suggestion (Q5). If they sit in codebooks with different colours, the
    native chip takes whichever was measured last.
12. ~~**Letters with a stroke do not fold.**~~ Decided 3 Oct 2026: nobody
    should have to type an accent. Latin letters that Unicode gives no
    decomposition (ø ł đ æ œ þ ı) fold by lodash's `deburr` table, an
    off-the-shelf one rather than ours, applied to Latin-1 and Latin
    Extended-A letters only, so it never reaches a script whose marks are kept.
    *Søren*, *Łódź*, *Đorđe*, *œuvre* and *kırmızı* are match cases in the
    contract now. German *ü* still does not match *ue* (typing *u* does).
13. ~~**The tag sidebar's search box did not fold.**~~ Decided 3 Oct 2026:
    one fold for everything. It uses `searchMatch.ts` now, so it folds accents
    and matches a word from its start, as toolbar search does.
