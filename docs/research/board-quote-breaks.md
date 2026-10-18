# Where a long quote breaks on a board, in 21 languages

**Status, 18 Oct 2026: built.** A quote over `SPLIT_AT` (325, measured as displayed width) goes
on a Miro or FigJam board as two or three stickies. `board_layout.split_quote` scores every place
it could break and trades that against an even split. The rules for each spoken language are data,
in `bristlenose/data/break_rules.json`, each entry citing its sources. This page is the research
behind that file and the measurements that checked it.

## What was wrong

The owner's board (18 Oct 2026) broke a quote at "people businesses are… / …appreciating" and
"back in the… / …day". Whisper had dropped punctuation for that stretch of the session, so the old
splitter, which looked only for punctuation in a narrow window, fell back to the word nearest the
middle. It also rendered a speaker trailing off ("that...") as "that..…", 120 times across the
trial runs, and split Japanese mid-word, because it knew no Japanese punctuation and needed spaces.

## How a break is scored

| Kind | Worth | Notes |
|---|---|---|
| Sentence end (`.?!` and `。！？`, inside any closing quote) | 10 | French spaced marks and « » stay with their sentence |
| Elision the extraction made (" ... ") | 9 | becomes the part's "…" |
| Clause mark, or a speaker trailing off ("but...") | 6 | trailing off was a sentence end before; it isn't |
| Comma (and `、，`) | 4 | |
| Bare gap: the speaker's pause | up to 12 | 8 a second, capped at 1.5 s; only where there is no mark and not inside a phrase |
| Bare gap: the language's word rules | −4 to +3 | `leads`, `no_start`, `opens`, `closes`, `ends_well` |
| Imbalance | 30 × Σ((part − even)/even)² | no part under 45% of even |

Japanese and Chinese have no spaces, so their bare breaks are the phrase ends **BudouX** finds
(Google's segmenter, the one Chrome uses for CSS `word-break: auto-phrase`; a dependency since
18 Oct 2026): a Japanese bunsetsu, a Chinese word. The language's rules score each
(`_phrase_worth`): a clause-final particle reads well, a modifier (の, 的) badly. A Japanese
bunsetsu carries its particle at its end, so endings are matched; BudouX gives a Chinese particle
its own token, and Chinese words end in the same characters (覺得 "feel"), so a Chinese particle
counts only as a whole token, except 的. Kinsoku (JLREQ, clreq) removes any break before a closing
mark or small kana, or after an opening one. A pause inside a phrase, after an article or before a
bound word, is hesitation and earns nothing.

## Measured

*First measurement, whole corpus, before tuning; the tuned, held-out numbers are in the next section.*

`experiments/quote-breaks/lang_eval.py` takes the real Whisper transcripts from the style-prompt
research (`docs/design-whisper-style-prompts.md`; 19 languages, 2–4 recordings each) and the
punctuated fossda sessions for English. It **strips their punctuation**, splits quote-sized runs,
and counts how often a break lands where the punctuation was: a sentence end, or any mark. The
gold is Whisper's own punctuation, so it is a proxy, but the same proxy for every language.

| | Breaks | No pauses: on a sentence | No pauses: on any mark | With pauses: on any mark |
|---|---|---|---|---|
| English, word rules as first built | 816 | 23% | 46% | 69% |
| English, plus *and/or/but* as leads (now) | 816 | 26% | 51% | 72% |
| Other languages, English rules only (before) | 53–215 each | 0–17% | 15–30% | 38–84% |
| Other languages, their own rules (now) | 53–215 each | 8–36% | 35–77% | 57–88% |

Per language, now (no pauses / with pauses, on any mark): ca 52/75, cs 72/84, da 63/83, de 57/67,
es 69/85, fi 63/74, fr 62/80, it 43/57, ko 35/79, nb 47/81, nl 45/69, pl 77/88, pt-AO 52/61,
pt-BR 44/68, pt-PT 45/79, ru 57/72, sv 55/81, tr 46/70, uk 62/70. **Not yet as good as English
everywhere.** Without pauses 12 of these 19 match or beat English's 51%; Korean (35), Italian (43),
Brazilian and European Portuguese (44, 45), Dutch (45), Turkish (46) and Norwegian (47) do not.
With pauses 12 of 19 match or beat its 72%; Italian (57) is furthest behind, then Angolan
Portuguese (61, a 23-break corpus), German (67), Brazilian Portuguese (68), Dutch (69), Turkish
and Ukrainian (70). Apart from English *and/or/but*, chosen on this harness, the lists are the authorities'
and untuned, so these numbers are the honest starting point; tuning would need a held-out half.
Japanese had only 12 breaks in its corpus (33%), too few to read;
the splits read correctly by eye ("…思ったのですが / ただ英語を…").

Across the trial runs' 322 long English quotes, no part now ends on an article, a preposition or a
pronoun (5 did), and none shows "..…" (120 did).

## Tuned on a held-out half (18 Oct 2026)

Each language's recordings, sorted, were split alternately into a **tuning half** and a
**held-out half** before anything was looked at (`lang_eval.py --half tune|held`; the three
Portuguese variants pooled as `pt`). Changes were found on the tuning half only, from the words
either side of each break that missed a mark (`--why LANG`), and made by category, never one word
to fit one miss. The held-out half was then scored, and scored once more after the last change,
which came from a rule a unit test pins rather than from held-out data.

- **"That" words.** Romance *che/que*, Dutch *dat*, Scandinavian *at/att/som* no longer earn an
  opener bonus, as English *that* never did: those languages put no comma before them, so a break
  there splits a noun from the clause that defines it. Kept where the authority requires the comma
  (German *dass*, Duden D 118; Czech *že*; Polish *że*; Russian *что*; Ukrainian *що*; Finnish
  *että*): removing them there cost 7–10 points, because with the comma gone the word is the cue
  to where it stood.
- **Finnish *sitten*, *nyt*** open no clause: spoken Finnish puts them inside or at the end of one
  (*lähdetään sitten*). Tuning half 61% → 70%.
- **Weights** (grid on the tuning half, every language at once): balance 40 → 30, pause 6 → 8 a
  second. The lead penalty made no difference between 3 and 6. Balance 25 scored a point higher
  again and was not taken, to stay near the English boards the owner judged.
- **A pause inside a phrase earns nothing**, so a pause after "a" stays a hesitation at the
  higher pause weight.
- **Tried and dropped:** Turkish *yani*, *işte* as clause enders (41% → 38% on the tuning half).

Held-out half, before → after (on any mark; breaks in brackets — under ~40 a single break moves a
number several points):

| | No pauses | With pauses |
|---|---|---|
| English (479) | 52 → 55% | 74 → 78% |
| Catalan (69) | 48 → 48% | 71 → 67% |
| Czech (69) | 72 → 74% | 84 → 90% |
| Danish (49) | 63 → 63% | 86 → 90% |
| German (60) | 47 → 50% | 58 → 62% |
| Spanish (90) | 66 → 69% | 82 → 86% |
| Finnish (47) | 68 → 70% | 85 → 87% |
| French (43) | 63 → 67% | 84 → 86% |
| Italian (41) | 41 → 49% | 68 → 71% |
| Korean (22) | 50 → 55% | 82 → 82% |
| Norwegian (10) | 10 → 30% | 80 → 80% |
| Dutch (47) | 40 → 51% | 60 → 68% |
| Polish (33) | 73 → 73% | 82 → 82% |
| Portuguese (25) | 44 → 44% | 68 → 76% |
| Russian (45) | 53 → 56% | 60 → 62% |
| Swedish (38) | 47 → 45% | 76 → 76% |
| Turkish (42) | 57 → 57% | 64 → 71% |
| Ukrainian (17) | 59 → 59% | 65 → 76% |

Everything held or improved but three: Swedish without pauses (one break), and Catalan with pauses
(71 → 67%), where the pause-inside-a-phrase rule took back what the weights gave (72% before it;
the same rule cost German and Dutch 2–3 points there while gaining on the tuning half). It is kept
because it is the subtitlers' rule and a test pins it; the likely cost is words that are both a
lead and a clause end (German *das* as a demonstrative, *ich weiß das*), which the lists cannot
tell apart.

**Against English** (held-out half). Without pauses, Czech, Danish, Spanish, Finnish, French,
Korean, Polish, Russian, Turkish and Ukrainian match or beat English's 55%; Catalan, German,
Italian, Dutch, Portuguese and Swedish are 4–11 points below; Norwegian's 10 breaks are too few to
read. With pauses, Czech, Danish, Spanish, Finnish, French, Korean, Norwegian and Polish beat
English's 78%; Portuguese, Swedish and Ukrainian are 2 points below, Italian and Turkish 7, Dutch
10, Catalan 11, German and Russian 16.
On the 322 long English quotes of the trial runs, 22 now break elsewhere than on the boards the
owner judged; across all of them the median part sits one point further from even.

## Decisions

- **A full-width character counts as two** (`text_width`, UAX #11), for the split length and for
  the sticky's size, so a Japanese sticky holds the same ink as an English one at the same size of
  type. A Japanese quote splits at about 162 characters. Netflix's line lengths imply about 100
  (ja) and 125 (zh, ko) for the same amount of *speech*; that is the alternative if equal speech
  matters more than equal ink.
- **English "and", "or", "but" may not end a part** (Netflix: break before a conjunction). It moved
  English from 46% to 51% (no pauses) and 69% to 72% (with pauses); widening the set to *so,
  because, if, when, that* added nothing.
- **Japanese が after a predicate is "but"**, a clause end: *ですが ますが だが たが ですけど* score
  as a clause (6), not as the subject particle (3).
- **BudouX is a dependency** (owner, 18 Oct 2026): `budoux>=0.9` in core, collected into the
  sidecar with its models and licence (`collect_all`), in THIRD-PARTY-BINARIES.md, ACKNOWLEDGEMENTS.md
  and the Windows lock. On this corpus it gave the same Japanese breaks as the kana-to-kanji rule it
  replaced; for Chinese it is what finds a word end at all.
- **Simplified Chinese** uses the Traditional rules with their characters converted; **pt-BR and
  pt-PT** share one list, because Whisper reports only `pt`; **Norwegian** `no`/`nn` uses `nb`.
- With no language stored (a platform or docx transcript), the script decides: kana is Japanese,
  Han Chinese (Traditional or Simplified by its characters), Hangul Korean, anything else English.

## The research

Compiled 18 Oct 2026 from the authorities below, starting from the ones this repo already cites
(`docs/design-whisper-style-prompts.md`, `docs/design-i18n.md`).


Research for the board splitter in `bristlenose/board_layout.py` (`BreakRules`: `leads`, `opens`, `opens2`), 18 Oct 2026. Labels: **VERIFIED** means I read the source page or PDF myself; **REPORTED** means a search summary or a secondary source, not read in full. Quotes are under 15 words; everything else is paraphrase.

## The finding that matters most: one rule, shared by every language

Netflix's *General Requirements* apply to every language's guide, and each language guide adds only shape and length. The rule (VERIFIED, [General Requirements §4](https://partnerhelp.netflixstudios.com/hc/en-us/articles/215758617-Timed-Text-Style-Guide-General-Requirements)):

- break **after punctuation**, **before conjunctions**, **before prepositions**;
- never separate a noun from its article or adjective, a first name from a last name, a verb from its subject pronoun, a prepositional verb from its preposition, or a verb from its auxiliary, reflexive pronoun or negation.

That is the shape `_LEADS`/`_OPENS` already encode. So for most languages the work is the word lists, not new logic. Three extensions are needed, and the JSON carries them as extra keys:

1. **`no_start`: words that must not *begin* a part.** English has none, but enclitics do: Polish *się*, Czech *se/si/jsem/by*, Russian and Ukrainian *же/ли/бы*, Turkish *mı/mi* and *de/da*, German *sich*, Chinese 的/了/嗎. The rule is the same Netflix one ("verb from reflexive pronoun or negation"), seen from the other side. To implement it, subtract `_LEAD_PENALTY` when `_word(after)` is in `no_start`.
2. **Conjunctions belong in `leads` as well as `opens`.** Catalan (VERIFIED, Blanquerna) and Polish (VERIFIED, SDH rules) say outright that a line must not end on a conjunction. The Danish and Swedish guides say to break *before* *og/och/men*. Today English *and/but* are only openers, so a cut just after "and" costs nothing. The lists below put the coordinating conjunctions in both, meaning break before them and never after. This changes behaviour; it is a recommendation, not a measured result.
3. **Japanese and Chinese need positional rules.** The splitter's `_CJK_BREAK` finds only punctuation. The JSON adds `kinsoku_no_start`, `kinsoku_no_end`, `break_after`, `no_break_after`, and for Korean and Turkish `break_after_suffixes`.

## Summary table

| Lang | Authority for breaks (Netflix guide links are in the JSON) | Status | Chars/line |
|---|---|---|---|
| ca | [Blanquerna-URL *Criteris de subtitulació* §11.3](https://cms.blanquerna.edu/sites/default/files/2026-04/criteris-de-subtitulacio_versio_novembre.docx.pdf) | VERIFIED | 36; Netflix 42 |
| cs | [ÚJČ *Internetová jazyková příručka*](https://prirucka.ujc.cas.cz/?id=880) (ČSN 01 6910) | VERIFIED | 42 |
| da | [*Guidelines for Subtitling in Denmark* v5](https://undertekstning.dk/download/guidelines_subtitling_uk_v5_november_2025/) | VERIFIED | 38–40 |
| de | Netflix de I.12 + [General Requirements](https://partnerhelp.netflixstudios.com/hc/en-us/articles/215758617-Timed-Text-Style-Guide-General-Requirements); ARD/ZDF *Untertitel-Standards* | VERIFIED; ARD REPORTED | 42; ARD 37 |
| es | Netflix es §12 + General; UNE 153010, ATRAE | VERIFIED; UNE REPORTED | 42 |
| fi | [SKTL *Käännöstekstitysten laatusuositukset* 2020 §2.1.1](https://www.av-kaantajat.fi/gallery/laatusuositukset%20taitettu%20ei%20allek.pdf) | VERIFIED | 42 |
| fr | [ATAA *French Subtitling Standards*](https://www.ataa.fr/documents/NORMES_SOUS-TITRAGE_FRANCAIS_ANGLAIS_EN-TETE.pdf) | VERIFIED | 40–42 |
| it | Netflix it I.12 + General; Perego 2008 | VERIFIED; Perego REPORTED | 42 |
| ja | [W3C JLREQ §3.1.7–8](https://www.w3.org/TR/jlreq/) (JIS X 4051); Netflix ja | VERIFIED; JIS REPORTED | 13 |
| ko | [W3C KLREQ §7.1](https://www.w3.org/TR/klreq/); Netflix ko I.11 | VERIFIED | 16 |
| nb | Netflix nb §12 + General (NAViO guide: dead link) | VERIFIED | 42 |
| nl | [Auteursbond *Guidelines for subtitling*](https://auteursbond.nl/wp-content/uploads/2024/04/Dutch-Guidelines-for-subtitling-EN.pdf) | VERIFIED | ~42 |
| pl | [ZPE *sieroty*](https://zpe.gov.pl/a/przeczytaj/DG2whzY8q); [Künstler & Butkiewicz 2019](https://kulturabezbarier.org/wp-content/uploads/2019/12/Napisy-dla-nieslyszacych_zasady-tworzenia_2019.pdf) | VERIFIED | 40 |
| pt-BR | Netflix pt-BR I.11 (restates General in full) | VERIFIED | 42 |
| pt-PT | Netflix pt-PT §12 + General | VERIFIED | 42 |
| ru | Мильчин, *Справочник издателя и автора*, via a [federal instruction](https://www.consultant.ru/document/cons_doc_LAW_467791/cf5f8027a72140a623acc35927d2e92069f82edb/) | instruction VERIFIED; Мильчин REPORTED | 42 |
| sv | [Medietextarna 2020 §1.7](https://www.medietextarna.se/wp-content/uploads/2020/11/Guidelines-for-subtitling-in-Sweden-2020.pdf); [Finland-Swedish 2020 §2.1.1](https://www.av-kaantajat.fi/gallery/riktlinjer%20f%C3%B6r%20svensk%20undertextning%20i%20finland%202.pdf) | VERIFIED | 35–40 |
| tr | Netflix tr I.12, the richest language-specific set; nothing from TDK | VERIFIED | 42 |
| uk | Netflix uk §12 (its own list) | VERIFIED | 42 |
| zh-Hant | [W3C clreq §6.1](https://www.w3.org/TR/clreq/); Netflix zh-Hant | VERIFIED | 16 |

Every Netflix language guide (VERIFIED) also says: at most two lines, one line if it fits, and a bottom-heavy pyramid, without stranding one or two words on the top line. The Dutch guide prefers lines of about equal length. That matters to us only as support for `BALANCE_WEIGHT`: no authority wants a tiny fragment.

## Implementation notes from reading the code

*Built since: a no-break space is never a gap; Turkish *İ* and Russian *ё* fold before lookup, and list words are folded the same way when loaded. Not built: Turkish *I*→*ı*, since no list word begins with *ı*.*

- **French spaced punctuation is already handled** in the working tree (VERIFIED in `_breaks`): there is no break before a token without letters, such as `?`, `;` or `»`, and none after a standalone `«`, `¿` or `¡`.
- **A no-break space is a break today.** Python's `\s` matches U+00A0 and U+202F (checked), and `_breaks` splits on `\s+`. A no-break space exists precisely to forbid a break: French uses it before `; : ! ?` and inside « », and ÚJČ and the Russian instruction use it between a number and its unit or % and between initials and surname. Suggest `[^\S   ]+` for the gap pattern. The French rule then holds even without the punctuation-token special case.
- **Turkish casing:** `str.casefold()` turns `İçin` into `i̇çin` (i plus U+0307) and `I` into `i`, so a capitalised Turkish word misses every list (checked). For `tr`, map `İ→i` and `I→ı` before `casefold`.
- **Russian ё:** Whisper and writers alternate *всё/все* and *ещё/еще*. Fold `ё→е` before lookup (the lists are written with е, except *моё*, which should be folded too).
- **Catalan l·l:** `_word` strips `·`, so *col·lecció* becomes *collecció*. No function word contains it, but list words must never include the middle dot.
- **Elision and hyphens:** French, Italian and Catalan elided articles (*l'*, *d'*, *qu'*) are glued to the next word, so they can never end a part. `_word` drops hyphens, so *c'est-à-dire* is stored as `c'estàdire`, and Portuguese enclitics (*disse-lhe*) stay one token.
- **Particle verbs:** German *an/auf/aus*, Dutch *op/aan/uit* and the Scandinavian particles are prepositions in `leads`, but can also end a clause ("ich rufe dich morgen *an*"). The Finland-Swedish guide (VERIFIED) breaks *after* a preposition that belongs to its verb (*varit med om | många…*). That penalty is a known cost, softened because a clause end usually has a comma, and the comma branch adds no lead penalty.

## Per language

### Catalan (ca)
**Rule.** Never separate a determiner from its noun, an adjective from its noun, compound tenses, verbal periphrases or fixed phrases. A line may end neither on a preposition nor on a conjunction (VERIFIED, Blanquerna §11.3). Netflix defers to the General rules.
**LEADS.** Articles, including personal *en/na*, contractions (*al, del, pel*), possessives (which follow an article, *el meu*), demonstratives, prepositions, subject and clitic pronouns, *no*, *haver* auxiliaries, the periphrastic past *vaig/va/van* (Catalan-specific and frequent), copulas, intensifiers, and *i o però que*. **OPENS.** *però, perquè, doncs, aleshores, llavors* 3; the rest, weighted, in the JSON.
**Ambiguous.** *es* (reflexive) and *és* ("is") are distinct, *si* and *sí* likewise. *en* is an article, a preposition and a pronoun, but every reading is a lead. *cap* means "none" or "towards" (*cap a*).

### Czech (cs)
**Rule.** A line must not end on the non-syllabic prepositions *k, s, v, z*, the syllabic *o, u*, or the conjunctions *a, i*. Also never split a number from its unit, %, abbreviation or noun, initials or a title from a surname, day from month, or *tzv.* from its word (VERIFIED, ÚJČ, applying ČSN 01 6910).
**LEADS.** The one-letter set and their vocalised forms (*ke, se, ve, ze*), other prepositions, demonstratives, possessives, pronouns, intensifiers. **NO_START.** The second-position clitics *se, si, jsem, jsi, jsme, jste, bych, bys, by…*. **OPENS.** *ale, protože, takže* 3; the rest, weighted, in the JSON.
**Ambiguous.** *se* is both the preposition "with" and the reflexive; it is in both lists, so it never borders a cut. *to* is a demonstrative and also "it", as in *to je*. *tak* means "so", and is also an intensifier.

### Danish (da)
**Rule.** Break before collocations and before *og, eller, men, fordi, at*, placed with care rather than wherever the line fills (VERIFIED, Danish Guidelines §Line break). Two lines of 38–40 characters.
**LEADS.** Articles, possessives, demonstratives, prepositions, subject pronouns, modals and auxiliaries, *ikke*, intensifiers. **OPENS.** *men, så, fordi* 3; the rest, weighted, in the JSON.
**Ambiguous.** *for* is "because" and "for"; *så* is "so/then" and an intensifier; casefolded *I* ("you", plural) collides with the preposition *i*, but both are leads.

### German (de)
**Rule.** Line breaks keep grammatical or semantic units intact, with no short words stranded on the top line (VERIFIED, Netflix de I.12), plus the General list. Duden requires a comma before every subordinate clause (VERIFIED earlier in the repo, D 118), so *weil/dass/wenn* breaks usually arrive by the comma branch.
**LEADS.** The full inflected article and possessive paradigms. Most of German's length is inflection: German needs ~100 forms where English needs 40. Also *in/im/am/zum/zur…*, subject pronouns, auxiliaries and modals, *nicht*, *sich*, intensifiers. **NO_START.** *sich*. **OPENS.** *aber, weil, denn, also, sondern* 3; the rest, weighted, in the JSON.
**Ambiguous.** *der/die/das* are articles, relatives and demonstratives; *sie* is "she", "they" or "you"; *sein* is "his" or "to be"; *ihr* is "her" or "you". *nicht* often closes a clause (*ich weiß es nicht*). Separable particles: see the implementation notes.

### Spanish (es)
**Rule.** Lines break by syntactic unit as in the General Requirements. Do not force a pyramid if syntax suffers (VERIFIED, Netflix es §12, with a worked example). UNE 153010 and ATRAE (REPORTED) list the same pairs: article + noun phrase, preposition + noun phrase, verb forms, pronoun + verb.
**LEADS.** Articles and *al/del*, possessives, demonstratives, prepositions, subject pronouns, proclitics (*me te se nos os le les lo la*), *no*, *haber* auxiliaries, copulas, intensifiers, *y o pero que*. **OPENS.** *pero, porque, entonces* 3; the rest, weighted, in the JSON.
**Ambiguous.** *a* is a preposition and also marks a personal object (both leads). *la/lo* are articles and clitics. *si* ("if") and *sí* ("yes") differ by the accent mark, as do *tu/tú* and *el/él*. *más* means "more" and often ends a clause. `¿ ¡` are stripped by `_word`, and a standalone mark is already skipped.

### Finnish (fi)
**Rule.** Words that belong together stay on one line: the parts of the verb, noun phrases and the parts of a name. The most natural break is a clause boundary (VERIFIED, SKTL §2.1.1). Finnish has no articles and mostly postpositions, so prepositions do not apply. The equivalent rule is **don't split the verb chain**: the negation verb from its main verb (*en | tiedä*), the auxiliary *olla* from its participle (*olen | käynyt*), or a genitive or demonstrative from its noun.
**LEADS.** Demonstratives (*tämä, tuo, se, nämä, nuo, ne*), genitive pronouns, including spoken *mun/sun*, subject pronouns including *mä/sä*, the whole negation verb *ei/en/et/emme/ette/eivät*, *olla* forms, intensifiers. **OPENS.** *mutta, koska, joten* 3; the rest, weighted, in the JSON.
**Ambiguous.** Spoken *et* is "that" (for *että*) and also "you don't". *niin* is "so", but also an intensifier (*niin hyvä*). *se* is "it" and a determiner-like "the". *on* is a copula ("is") or an auxiliary.

### French (fr)
**Rule.** Do not separate a subject from its verb, or a preposition from its infinitive. Avoid ending a line on a relative pronoun, and don't hyphenate (VERIFIED, ATAA). The Imprimerie nationale rules on no-break spaces before `; : ! ?` (repo, VERIFIED earlier) make those marks part of the preceding word.
**LEADS.** Articles and *du/au/aux*, possessives, demonstratives, prepositions, the subject clitics *je tu il elle on nous vous ils elles* (the strongest bond), object clitics *me te se*, *ne*, *y*, *être/avoir* forms, intensifiers, the relatives *qui que dont où*, and *et ou mais*. **OPENS.** *mais, donc, parce (que), alors, c'est-à-dire* 3; the rest, weighted, in the JSON.
**Ambiguous.** *si* is "if" and also an intensifier; *après* is a preposition and spoken "then"; *a* is the verb "has", *à* the preposition; *plus*. ATAA prefers straight quotes in French subtitles, but transcripts may carry « » and the code handles both.

### Italian (it)
**Rule.** The General list, a bottom-heavy pyramid, and no one or two words alone on the top line (VERIFIED, Netflix it I.12). Perego (2008, REPORTED) found Italian viewers tolerant of syntactically odd breaks, which supports keeping the penalty modest.
**LEADS.** Articles, the articulated prepositions (*del, nella, sul…*), possessives, demonstratives, prepositions, pronouns and clitics (*mi ti si ci vi ne*), *non*, auxiliaries and copulas, intensifiers, *e o ma che*. **OPENS.** *ma, però, perché, quindi, allora, cioè* 3; the rest, weighted, in the JSON.
**Ambiguous.** *e* ("and") versus *è* ("is") versus the filler *eh* (KIParla; noted in the repo). Whisper sometimes writes *e'* for *è*, so fold that before lookup. *ci* is a pronoun and also the locative "there".

### Norwegian Bokmål (nb)
**Rule.** The General list plus pyramid shape. Two lines may be used for readability even when one would fit (VERIFIED, Netflix nb). NAViO's guidelines URL is dead. A 2013 *Folia Scandinavica* article (REPORTED) says Scandinavian norms are converging, so the Danish and Swedish rules are good proxies.
**Lists.** As Danish, with the Bokmål forms *ei, mi, di, si, våre, dere, ble, nå, veldig, svært*; pair *selv om*. Nynorsk (`nn`) maps to these lists already (`break_rules`), which mostly works. Nynorsk forms (*eg, ikkje, kva, når*) would need their own entries.

### Dutch (nl)
**Rule.** Break between two lines at a logical point, with lines roughly equal in length. Example: *I said that I didn't feel | one bit like it* (VERIFIED, Auteursbond; also Netflix nl).
**LEADS.** *de het een 'n*, possessives, demonstratives, prepositions, subject pronouns, auxiliaries and modals, *niet, geen*, intensifiers, *te*. **OPENS.** *maar, dus, want, omdat* 3; the rest, weighted, in the JSON.
**Ambiguous.** *die/dat* are demonstratives and also relatives or conjunctions (kept as leads, opener weight 1 only). *zijn* means "his" and "to be"; *hun* "their" and "them"; *te* "too" and the infinitive marker. Separable particles.

### Polish (pl)
**Rule.** One-letter words (*a, i, o, u, w, z*) must not stay at a line end (VERIFIED, ZPE). Don't split a first name from a surname, a modifier from its head, or a preposition from its noun. Don't separate *nie* or *się* from the verb, and don't leave conjunctions at a line end (VERIFIED, Künstler & Butkiewicz §4). PWN reportedly treats the one-letter rule as an editorial convention rather than a spelling rule (REPORTED).
**LEADS.** The one-letter set plus *we, ze*, prepositions, demonstratives, possessives, pronouns, *nie*, *się*, the future auxiliary *będę/będzie*, intensifiers. **NO_START.** *się, by*. **OPENS.** *ale, bo, więc, czyli* 3; the rest, weighted, in the JSON.
**Ambiguous.** *jak* means "how", "as" or "when"; *to* is a demonstrative and also a copula-like "is"; *ze* ("with") is not *że* ("that"); *jego/jej/ich* are also object pronouns. Polish *no* ("well") is spelled like English *no*, but the lists are per language, so no clash.

### Portuguese (pt-BR, pt-PT)
**Rule.** Netflix pt-BR restates the General rules in full and gives an example. *Eu queria falar com | vocês* is wrong; *Eu queria falar | com vocês* is right (VERIFIED). pt-PT defers to the General rules.
**LEADS (shared).** Articles and contractions (*do, na, ao, à, pelo, num*), possessives, demonstrative determiners (*este, esse, aquele*), but not the pronouns *isto, isso, aquilo*, which end phrases (*é isso*). Also prepositions including Brazilian *pra/pro*, subject pronouns, proclitics, *não*, *ter* and *ser/estar* forms, the periphrastic future *vou/vai/vão*, intensifiers, *e ou mas que*. **OPENS.** *mas, porque, então* 3; the rest, weighted, in the JSON.
**Ambiguous.** *a* is an article, a preposition and a pronoun; *e* ("and") versus *é* ("is") versus the filler *eh*; *bem* is an intensifier or "well"; *mais*. pt-PT enclisis is hyphenated (*disse-lhe*), so it stays one token.

### Russian (ru)
**Rule.** One-letter prepositions and conjunctions must not end a line, even mid-sentence, and one- to three-letter ones not when they open a sentence. Initials stay with the surname and numbers with their units (VERIFIED, the instruction restating Мильчин; Мильчин itself REPORTED). The negation *не* stays with its word.
**LEADS.** *в к с у о и а я* and the vocalised *во ко со об*, other prepositions, demonstratives, possessives, pronouns, *не ни*, the future auxiliary *буду/будет*, intensifiers. **NO_START.** The enclitics *же ж ли ль бы б*. **OPENS.** *но, потому (что), поэтому, так что, то есть* 3; the rest, weighted, in the JSON.
**Ambiguous.** *это* means "this" and also "it is"; *так* "so" and "thus"; *его/её/их* are possessives and also objects (left out of leads); *вот* and *ну* are discourse openers but also occur mid-clause.

### Swedish (sv)
**Rule.** Keep semantic units together. Break before a subordinate clause (*att, som, för att, eftersom*) or a conjunction (*och, men, eller*), and then aim for a shorter top line (VERIFIED, Medietextarna §1.7). Never split mid-phrase or mid-clause. Keep the tighter-bound words of a subject or object together. Break *after* a preposition that is part of its verb (VERIFIED, Finland-Swedish §2.1.1, with examples).
**LEADS.** Articles, possessives, demonstratives, prepositions (with the particle-verb caveat), subject pronouns, auxiliaries and modals, *inte*, intensifiers. **OPENS.** *men, så, eftersom* 3; the rest, weighted, in the JSON.
**Ambiguous.** *om* is "if" and "about"; *för* is "because" and "for"; *så* "so" and an intensifier; *det/de* articles and pronouns. Under V2 order (*sen gick jag*) a subject pronoun can follow its verb, which makes its lead penalty a mild false positive.

### Turkish (tr)
**Rule (VERIFIED, Netflix tr I.12, with examples).** No lone short word on either line. Break after converbs (*-ıp, -arak*), keeping compound verbs whole, and before conjunctions. Break after adverbs and postpositions (*göre, önce, için, dek*), after the optative, and after punctuation. Never separate a noun from its article (*bir*) or adjective, or a verb from its auxiliary (*rahatsız | oluyor* is wrong).
**Equivalent rule.** Turkish is agglutinative and postpositional, so the English "never end on a preposition" becomes **never start on a postposition, question particle or light verb**. **NO_START.** *mı/mi/mu/mü* and their personal forms, the clitics *de/da*, *değil*, the postpositions *için, gibi, kadar, göre, dek, rağmen, beri*, and the *etmek/olmak* forms. **BREAK_AFTER.** Those postpositions, plus *ki*; the suffixes *-ıp/-ip/-up/-üp, -arak/-erek, -ınca…, -ken* (a suffix match on the word before the gap, score as a phrase, 2–4). **LEADS.** *bir, bu, şu, her, hiç, bazı, birkaç, hangi, aynı, çok, en, pek*, the genitive pronouns *benim…*, *böyle/şöyle/öyle*. **OPENS.** *ama, fakat, ancak, çünkü, yani* 3; the rest, weighted, in the JSON.
**Ambiguous.** *o* is "that" (a determiner) and also "he/she/it" (left out). *sonra/önce* are postpositions but also clause-initial "then". Netflix lists *daha* among the words to break after, so it is not a lead. The casing bug is described in the implementation notes.

### Ukrainian (uk)
**Rule.** Netflix uk gives its own list (VERIFIED): break after punctuation and before conjunctions and prepositions. Don't separate an adjective from its noun, a name from a surname, a subject pronoun from its predicate, or a verb from its auxiliary, reflexive or negation. Segmentation outranks the pyramid. University typesetting guides (REPORTED) forbid one-letter prepositions and conjunctions at a line end.
**LEADS.** *в у з із зі і й а о*, prepositions, demonstratives, possessives, pronouns, *не ні*, the future auxiliary *буду/буде*, intensifiers. **NO_START.** *же ж би б*. **OPENS.** *але, бо, тому (що), отже, тобто* 3; the rest, weighted, in the JSON.
**Ambiguous.** *в/у* and *і/й* alternate for euphony, so both forms are listed. Apostrophes: Ukrainian *ʼ* (U+02BC) counts as a letter for `\w`, while *'* (U+0027) is kept by `_word`. No list word contains one.

## Japanese, Chinese and Korean

**Japanese (ja).** *Kinsoku* (VERIFIED, JLREQ §3.1.7–3.1.8, after JIS X 4051). A line must not **start** on closing brackets, hyphens and 〜, ？！, ・：；, 。．, 、，, iteration marks (々ゝ…), ー or small kana. It must not **end** on an opening bracket. The full strings are in the JSON, with full-width （）［］｛｝ added to JLREQ's code points. JLREQ notes that many books relax the rule for 々, ー and small kana.

*Where to break.* No subtitle authority names particles. Captioning research takes **bunsetsu boundaries** as the candidate breaks, scored by clause boundary, dependency, pause and length (Murata et al., Nagoya 2009, REPORTED). Without a parser, a proxy is the step from hiragana to kanji or katakana, since a bunsetsu usually ends in a particle. Weight it by the particle:
- **clause particles** *から ので けど けれど(も) のに ながら し たら ても*: score as a clause (6);
- **case and topic particles** *は が を に で と も へ や より まで*: score as a phrase (2–4);
- **never** after *の* or adnominal *な* (that cuts a modifier from its noun), inside a hiragana run, or before a kinsoku character.

Netflix ja (VERIFIED) writes spaces for 。、 in subtitles. Whisper keeps 。、.

**Traditional Chinese (zh-Hant).** clreq's recommended **basic** level (VERIFIED, §6.1.1): no line starts on 、，。：；！？, a closing quote or bracket, a connector or an interpunct (·‧). No line ends on an opening quote or bracket. *——* and *……* are unbreakable, as is a number with its %, ° or currency sign (§6.1.2). clreq says Taiwan and Hong Kong have no positioning standard, but most publications follow these rules. Netflix zh-Hant (VERIFIED) puts no 、，or period at a line end.
*Words* (from grammars; no guide lists them): enclitic particles (的 了 著 過 嗎 呢 吧 們 地 得…) must not **start** a part. Never break right **after** 的 地 得 之. Sentence-final 吧 呢 嗎 啊 啦 are natural break-afters. Openers lead with *但是 可是 所以 因為 因此 不過* at weight 3. Ambiguity: the same characters begin words (了解, 得到, 的確), so a one-character `no_start` match costs a few false positives.

**Korean (ko).** KLREQ (VERIFIED, §7.1) breaks Hangul by **character or by eojeol** (the space-separated word), at the author's choice. Subtitles break by eojeol, so the space-gap model applies directly. Netflix ko (VERIFIED) also allows two lines when a line holds 3 or more punctuation marks, or to set a quoted sentence on its own line. KLREQ kinsoku: no line starts on a closing bracket, a hyphen, ？！, a middle dot, a period or a comma; none ends on an opening bracket.
- **LEADS:** prenominal determiners (이 그 저 이런 그런 어떤 무슨 몇 모든 한 두 첫 다른…), possessive 제/내, the negators 안/못, intensifiers.
- **NO_START:** dependent nouns, spaced but bound to their modifier (*할 수 있다*, *갈 거야*): 수 거 것 줄 데 때문에 뿐 만큼 중 정도 적, with their particle forms.
- **BREAK_AFTER (suffix):** connective endings (-는데 -지만 -니까 -어서/-아서 -면서 -다가 -려고), scored as a clause. The one-syllable -고 -서 -면 also end nouns (학교, 교과서), so score them 1.
- **OPENS:** led by 그런데/근데 하지만 그래서 그러니까 왜냐하면 at weight 3.

### Characters per line, and a split length for full-width scripts

| | Netflix chars/line (VERIFIED) | Reading speed, adult (VERIFIED) |
|---|---|---|
| English | 42 | 20 cps |
| Latin/Cyrillic languages above | 42 | 17–20 cps |
| Japanese | 13 full-width (11 vertical); half-width counts 0.5 | 4 cps |
| Traditional Chinese | 16 (18 in SDH) | 9 cps |
| Korean | 16; Latin, space and punctuation count 0.5 | 12 cps |

`text_width` counts a full-width character as 2. So `SPLIT_AT = 325` splits a CJK quote at about 162 characters: same ink, same sticky. By Netflix's line lengths, one full-width character carries about 42/16 = 2.6 Latin characters of reading in zh and ko, and 42/13 = 3.2 in ja. If a part should hold the same amount of *speech* rather than the same width, the thresholds become about **125 characters for zh-Hant and ko** and **100 for ja**, that is a width multiplier of 2.6 or 3.2 instead of 2. The sticky would then show a shorter, sparser block. Which to prefer is a product call: equal ink fills the note evenly, equal speech gives a reader the same amount to take in. Korean also has spaces, which `text_width` counts as 1, close to Netflix's 0.5.

## Sources not reached, and what was used instead
- RAI's Italian norms (host refused), ATRAE's Spanish guide (PDF over 10 MB), and the NAViO and ERC guide pages (404 or homepage) were not read. Netflix and the General Requirements cover each of these languages.
- Мильчин's text was not found online; the Russian rule comes from a federal records instruction that restates it.
- No Japanese subtitle guide that I found names particles. The particle list is grammar plus the bunsetsu research above, not a quoted rule.
