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
| D4 | **Each typed word matches on its own**, in any order, as the start of a word. A **"quoted"** term matches as an exact phrase. | A behaviour change to shipped search (today: one contiguous substring). |
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
   Greek final `ς` is `σ`. Curly and straight apostrophes are equal.
   Whitespace runs are one space, and invisible characters (soft hyphen,
   zero-width space) are ignored.
   **Accents are folded only where they are optional:** Latin, Greek,
   Cyrillic, Arabic and Hebrew. In Japanese, Thai and Hindi a combining mark
   changes the word (`パン` is bread, `ハン` is not), so it is kept, and a match
   may not end just before one (`ハ` does not find `パ`).
2. **Terms.** The query splits on spaces into words. Text inside double quotes
   (straight, curly, « », 「 」) is one phrase term. An unclosed quote runs to
   the end. Apostrophes at the edge of a word are dropped, so smart single
   quotes (‘than the’) act as the plain words.
3. **Word-initial.** A term matches only at the start of a word (`st` finds
   *Storey*, not *best*). Exception: a term in Chinese, Japanese or Thai script
   matches anywhere, because those scripts don't space words.
4. **All terms, any field.** A quote matches when **every** term matches in
   **some** searchable field. The fields are:
   - the quote text (the edited text if there is one);
   - the speaker name;
   - tag names;
   - the sentiment.

   So *tom delivery* finds Tom's quote about delivery.
5. **Activation.** Free text filters from **2 characters**, or 1 Chinese or
   Japanese character (today: 3; decided 3 Oct 2026). Characters are counted
   after folding, so a letter written with a separate accent counts once.
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
| Person | **Mentions** | its text contains one of the person's names as a phrase (§3). Disabled in the menu when the person has no name, only a code. |
| Person | **Not** | its `participant_id` is not the code |
| Tag | **Tagged** (default) | it carries the tag (store edits included) |
| Tag | **Text contains** | its text contains the tag name as a phrase |
| Tag | **Not tagged** | it does not carry the tag |

- **A token is the real badge inside a light container**: the meaning word
  (*said by*, *mentions*, *not*, *tagged*, *contains*, *not tagged*), then the
  badge exactly as it appears on a quote card, then a ▾ disclosure. Only the
  container and the word are new; the badge is not restyled (§7a).
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
| typing | recompute rows; highlight row 1 (free text) | open when there are rows |
| ↓ / ↑ | move the highlight (wraps) | open the menu |
| ↩ | apply the highlighted row. A free-text row commits the query now (no debounce wait); a person or tag row becomes a token and **clears the typed text** | commit the query |
| Esc | close the menu | today's cascade: clear text, then collapse. The ⓧ button clears text **and** tokens |
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

- **Tokens render as native chips inside the capsule, before the text field.**
  Each chip is a SwiftUI `Menu` offering the meanings plus Remove.
- **The suggestions menu is native**: a SwiftUI popover anchored under the
  capsule, with SF Symbols glyphs and a trailing count. ↑/↓/↩/Esc go to the
  popover while the field has focus.
- **The SPA stays the source of truth.** Native sends keystrokes (as today) and
  user choices; the SPA recognises, applies, and posts back state.

Bridge contract (additions to `frontend/src/shims/bridge.ts` and `BridgeHandler.swift`):

| Direction | Message | Payload |
|---|---|---|
| native → web | `setSearchQuery` (exists) | `{text}` |
| web → native | `search-suggestions` | `{query, rows: [{id, kind, label, typed: [[start,end]], count}]}`: labels are **already localised** by the SPA |
| native → web | `applySearchSuggestion` | `{id}` |
| web → native | `quotes-filter` (exists, grows) | `{searchQuery, viewMode, tokens: [{kind, label, mode, modes: [{id, label, enabled}]}]}` |
| native → web | `setSearchTokenMode` | `{index, mode}` |
| native → web | `removeSearchToken` | `{index}` |

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
   the split `PersonBadge` for a person. It reads `getComputedStyle` from it
   and sends the resolved values with each row and each token:

   ```ts
   interface BadgeStyle {
     bg: string;
     fg: string;
     border: string | null;
     fontFamily: "mono" | "body";
     sizePx: number;
     weight: number;
     padX: number;
     padY: number;
     radius: number;
   }
   // person rows and tokens carry { code: BadgeStyle, name: BadgeStyle | null }
   ```

2. Swift paints exactly those values:
   - `Font.system(size:weight:design:)`, with `.monospaced` for mono. That
     resolves to SF Mono, which is what `--bn-font-mono` resolves to in
     WKWebView.
   - The numeric weight mapped to the nearest `Font.Weight`.
   - Points taken 1:1 from pixels, which is how the webview renders them.
3. **The styles are re-sent when anything that changes them changes**: the
   palette, the appearance (light or dark), the display mode (code only, or
   code and name), and any tag's colour. They are keyed by tag name and
   speaker code, so a recolour in the codebook repaints the native chip
   immediately.

**Tests.**

- A vitest asserts that the probe reads the same values the rendered badge
  has, so the probe can't drift from `Badge`.
- A Swift snapshot test renders a chip from a fixture `BadgeStyle` and
  compares it against a PNG of the web badge at the same scale, within a small
  tolerance. It's cheap, and it catches a wrong weight mapping or padding.
- Human QA puts the native token beside the same badge on a quote card, in
  both palettes and both schemes, and checks it with Digital Color Meter.

## 8. i18n

New keys in `common.json`, in all 21 full locales (not `zh-Hant-HK`):

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
| **P1 Matcher** | `searchMatch.ts`, contract fixture, `highlight.tsx` and `filter.ts` switched to it | vitest green; every shipped search behaviour still covered, the D4 change asserted. **Matcher and fixture done 3 Oct 2026** (53 matching cases, 15 activation cases); the switch-over of `filter.ts` and `highlight.tsx` is still to do |
| **P2 Tokens** | token types + predicates; `searchTokens` in QuotesStore with add/remove/set-mode actions; **one** `filterStateOf(store)` replacing the six hand-built `FilterState`s (Toolbar, QuoteSections, QuoteThemes, ExportDropdown, LensSubtitleSync, `getVisibleQuotes`); highlight of mentions/contains | exports and subtitle counts honour tokens (asserted) |
| **P3 Recognisers** | `searchSuggest.ts`, pure; people from `getPeople()` (embedded in the export) | unit tests. **Done 3 Oct 2026**, headless: rule tests on a hand-built project, invariants and an independently written matcher over the seeded synthetic project (`searchSynthetic.ts`), and a 10,000-quote scale test (2–8 ms a keystroke warm, 17 ms cold, on an M-series Mac) |
| **P4 Browser UI** | combobox, rows, chips, meaning menus; CSS in `bristlenose/theme/molecules/search.css`; locale keys ×21 | vitest; `check-locales.py --strict`; browser QA |
| **P5 Mac** | bridge messages; `BadgeStyle` probe in the SPA; native badge views painted from it; native chips and popover with lens SF Symbols; Swift tests incl. the badge snapshot (§7a) | `desktop/scripts/test-swift.sh`; `.app` QA side by side with the card badge, both palettes and schemes |
| **P6 Docs** | true `design-html-report.md`'s search section and `platform-text-map.md`; set this doc's status to shipped | — |

## 12. Open questions

1. ~~**Activation at 2 characters rather than 3.**~~ Decided 3 Oct 2026: 2.
2. **The ⓧ button clears tokens as well as text.** Or should it clear text
   only, with tokens removed one at a time, as in Mail?
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
