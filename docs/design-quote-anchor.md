# Quote anchor — a coordinate system between quotes and transcripts

**Status:** proposal, 3 Nov 2026. No code. It **extends** [design-transcript-editing.md](design-transcript-editing.md) decision 3 ("the keystone is a persisted word-range anchor") and step 1 of its order of work ("one word-range type, and one edit record"); it does not replace them. Where this note and that one disagree, that one is the spec until the owner says otherwise.

**Scope (3 Nov 2026, owner).** Transcript-side editing (corrections, strikes and their undo) is **not before the 24 Nov 2026 submission**: the editing design already marks it GA-gating, about 2027, and its undo rules (decisions 17 and 26) make it large. Line breaks are **presentation**, stored apart from the words (§8). §15 sets the order of work; §3.3 and §4.3 are reserved for the later editing work and are not part of the first phase. The v1 setting, a single "Break long paragraphs" switch computed when the quote is drawn, with nothing stored, is specified in [design-display-preferences.md](design-display-preferences.md); this note is the path beyond it.

**Why now.** Automatic line breaks need to know where words were cut out of a quote and how long the speaker paused there (the line-break lab and display-preferences thread of 3 Nov 2026; there is no design note for it yet). Today a quote carries `text`, `verbatim_excerpt`, two timecodes and a loose `segment_index`. The gutter re-derives "which transcript words is this quote?" in the browser on every page view and finds 76% of them (`docs/design-transcript-gutter.md`, measured 17 Oct 2026 on 918 quotes). The rest is a guess. Line breaks, the edit feature, the gutter and incremental analysis all want the same thing, so we build it once.

## 1. The model: the transcript is a reference genome

The owner's suggestion (3 Nov 2026) was DNA: exons kept, introns spliced out, and tidying inside a kept exon. It maps closely enough to borrow whole standards, which is the house rule (prior art over invention).

| Biology | Bristlenose | Standard to copy |
|---|---|---|
| Reference genome, immutable | The **base**: a session's words after redaction, as the pipeline wrote them | reference assembly |
| Position on the reference | **Base word index**, 0-based, half-open `[start, end)`, per session | BED / SAM coordinates |
| A transcript's gene annotation | The quote's **anchor**: session, `[start, end)`, and an alignment string | GFF3 / GTF |
| Exon (kept) | A run of base words the quote uses | `=` in an alignment |
| Intron (spliced out) | **N gap**: a large run of base words left out between kept runs | `N` (skipped region) |
| RNA editing inside an exon | **Tidy**: filler removed (`D`), words reworded (`X`), words inserted (`I`, our `[clarifying]`) | `D`, `X`, `I` |
| Alignment string | **Extended CIGAR**, e.g. `12=1D5=1X3=N40=` | SAM extended CIGAR |
| A variant call with its REF allele | A **transcript edit**: kind, range, the base words it was made against, the new words | VCF, REF check |
| The personal genome | The **view**: base with edits applied | `bcftools consensus` |
| Liftover after a new assembly | **Rebase** after a re-transcription | chain files |

Two kinds of cut, because the ethics differ:

- **D (tidy gap).** Short, inside a used run. Today's extraction policy produces only these: filler removed and replaced with `...` ([quote-extraction.md:28](../bristlenose/llm/prompts/quote-extraction.md)). The two-kind split is the one research-writing guidance already makes: Lingard (2019) separates an ellipsis inside a sentence (words removed within it) from one after a full stop (at least one whole sentence dropped), and advises removing only what does not bear on the meaning.
- **N (splice gap).** Long, between two used runs. Substantive material was left out and two statements now touch that did not touch in the recording. **This is the cut that could change a meaning**, and it is where a researcher cropping the middle of a quote lands. Whether the pipeline ever produces one is unmeasured (§9).

**Where the analogy breaks, so we don't over-reach.** Overlapping speech is two strands read in parallel; we use one merged order and say so. Biology has no cut made by a person with intent, so the human-authored side (corrections, strikes, notes) comes from our own edit design, not from genomics. And "transcript" collides with the biological word, so in this note the interview text is the **base** and a quote is a **mature transcript**.

## 2. Invariants

1. **I1. The base is immutable.** Edits are overlays. Revert deletes an edit row; nothing rewrites the base (design-transcript-editing decision 4).
2. **I2. Anchors live in base coordinates.** A transcript edit never moves an anchor, because the edit changes the view and the anchor addresses the base. This single choice removes the shifting-positions class of bug that decision 11 already identified.
3. **I3. Refuse, never guess.** An anchor or edit that cannot be resolved is a state we show (`unresolved`, `refused`), never one we repair with a heuristic. The existing replay already works this way (`TranscriptLayoutEdit.verify`).
4. **I4. The tokenisation is persisted, not recomputed.** Base indices must mean the same thing on every platform and Python/ICU version. We split once at import and store the result.
5. **I5. Every ellipsis is accounted for.** In a quote's pipeline text, the k-th `...` corresponds to the k-th gap (`D` or `N`). A gap with no ellipsis is reported as **silent**; an ellipsis with no gap is reported as **orphaned**. Neither is repaired.
6. **I6. A quote's text is its own copy.** The anchor says where the text came from. It is not a projection of the base, because tidying rewords.
7. **I7. One write path.** A correction reaches `Quote.text`, `verbatim_excerpt` and the researcher's edit together, through one function (design-transcript-editing step 1, "three copies").
8. **I8. Raw stays raw.** The transcript never shows a quote's line breaks or tidying.

## 3. Schema

Names are illustrative. All tables are project-scoped through their parent (`Session`, `Quote`), as the multi-project rules require.

### 3.1 The base

No new table for the words themselves; they stay in `TranscriptSegment` (`text`, `words_json`). Two additions:

```
TranscriptSegment
  + base_start   INTEGER   -- ordinal of the segment's first base word, per session
  + base_count   INTEGER   -- words in this segment (0 for an inaudible gap)
  + tok_json     TEXT      -- persisted tokenisation when there is no words_json (see I4)
  + timing       TEXT      -- 'exact' (Whisper words) | 'interpolated' | 'none'

Session
  + base_hash    TEXT      -- hash of the normalised base word sequence
```

The base is the **post-redaction** word sequence, because quotes are extracted after redaction. Redaction clears word timings (`s07_pii_removal.py:593`, `clean_seg.words = []`), so a redacted session has token positions but `timing = 'interpolated'` at best, never `exact`. Redaction tokens (`[NAME]`) are base words flagged non-editable.

Layout edits (split, join, move) change paragraph boundaries and never the base word sequence, so every anchor survives them untouched.

### 3.2 The anchor

```
quote_anchors            -- one row per quote
  quote_id     FK UNIQUE
  session_id   FK
  base_start   INTEGER     -- first base word the quote covers
  base_end     INTEGER     -- exclusive
  ops          TEXT        -- extended CIGAR over [base_start, base_end)
  base_hash    TEXT        -- hash of those base words, normalised (the REF check)
  prefix       TEXT        -- the 3 base words before the range, normalised (context, see 4.3)
  suffix       TEXT        -- the 3 base words after the range, normalised
  method       TEXT        -- 'excerpt_exact' | 'excerpt_aligned' | 'timecode_only'
  status       TEXT        -- resolved | approximate | ambiguous | unresolved | stale
  derived_at   DATETIME
```

`ops` carries everything the older sketch spread across a span table and a gap table. Walk it and you have the kept runs, the gaps and their base ranges; sum word times over a gap and you have the pause that line-break placement wants. One short string, diffable, splittable at any base position (which is what a split of a quote needs).

### 3.3 The edit journal (reserved; not built before 24 Nov 2026)

One table generalises `TranscriptLayoutEdit`:

```
transcript_edits
  id, session_id
  kind         -- correct | strike | split | join | move | note
  base_start, base_end          -- the range, in base coordinates
  ref_hash     TEXT             -- hash of the base words the edit was made against (VCF's REF)
  payload      TEXT (JSON)      -- replacement words | target speaker | note text
  created_at
  UNIQUE (session_id, kind, base_start, base_end, ref_hash)   -- idempotent replay
```

Plus the file mirror the pipeline reads, `.bristlenose/transcript-edits.json` (design-transcript-editing step 1), written from the DB with an atomic rename. **The database is the source of truth; the file is derived and rebuilt at serve start if missing**, the same write-ahead rule as the manifest ("never a lie: may be behind, never ahead").

This is deliberately **not an event-sourced history stack**. Decision 4 says one saved edit over an immutable original, and removal deletes the row. The rows are the journal; the view is a fold over them.

### 3.4 Line breaks: a presentation overlay (first phase)

```
quote_breaks             -- one row per quote that has breaks; absent means none
  quote_id     FK UNIQUE
  breaks       TEXT (JSON) -- [[after_word_index, level], ...]; level 1 = phrase, 2 = thought
  source       TEXT        -- 'auto' | 'researcher'
  verify       TEXT        -- short hash of the quote's resolved wording the breaks were made against
  created_at   DATETIME
```

`after_word_index` counts words in the quote's **own** resolved wording (the pipeline's text, or the researcher's edit if there is one), tokenised by one shared function. It needs no anchor and no transcript. This is the `TranscriptLayoutEdit` pattern (a position plus a `verify`): when the wording changes and `verify` no longer matches, `auto` breaks are recomputed and `researcher` breaks are dropped without a message. Nothing about it pins a quote or mints a durable id, and no `\n` enters `Quote.text`.

## 4. Algorithms

### 4.1 Locating a quote (extraction to anchor)

Runs in the importer from data already in the database, so it needs **no pipeline change and backfills existing projects without a re-run**.

1. **Window.** Base words by the quote's participant whose time falls in `[start − δ, end + δ]` (or the segment named by `segment_index`).
2. **Normalise** both sides (NFKC, casefold, strip punctuation; CJK by the persisted tokens).
3. **Locate** the `verbatim_excerpt`: exact subsequence first (`excerpt_exact`); otherwise a local alignment (Smith-Waterman on tokens) accepted above a coverage threshold θ (`excerpt_aligned`, status `approximate`).
4. **Align the quote text to that span** to assign operations: matches `=`, rewordings `X`, bracketed `[clarifying]` runs `I`, removed runs `D` (short) or `N` (long, above a length threshold), each ellipsis token claiming the next gap.
5. **Check I5** and record silent or orphaned gaps.
6. **Fallback** when step 3 fails: `timecode_only`, `status = unresolved`, the window kept. The gutter then does what it does today. We never pretend.

Cost is O(n·m) inside a small window. A typical quote is tens of words.

### 4.2 Re-matching on re-extraction

The importer today matches a re-cut quote to a row by start second, then by words at 0.6 (`importer.py` `_match_quotes_to_rows`, `_CLOSE_ENOUGH`). With anchors, match first by **overlap of `[base_start, base_end)`** (Jaccard, same participant); fall back to the word ratio only when the overlap is empty. Overlap is deterministic and does not drift with the model's rewording, which is the failure the 0.6 threshold papers over. A curated quote the model omits keeps its row and its anchor: `orphaned` from the analysis, still addressable on the transcript.

### 4.3 Rebase (liftover)

If `Session.base_hash` changes (a re-transcription), every anchor and edit in the session is `stale`. Align old base to new base (Myers diff on normalised words). An anchor maps if both ends map and at least 90% of its words align (θ to be measured); otherwise it stays `unresolved`. The stored `prefix` and `suffix` do two jobs, borrowed from Hypothesis's anchoring: they rank candidates when the excerpt occurs more than once (§4.1 step 3), and they let a rebase search near the old position for the same surroundings before it aligns the whole session. An edit whose `ref_hash` does not match the mapped range is **refused** and listed (design-transcript-editing: "an edit whose words changed is refused"). Re-analyse is the begin-again action and discards both (decision 12), so rebase matters only for ordinary Analyse paths.

### 4.4 The view

`view(session) = fold(base, edits)` in base-coordinate order, producing the displayed words and two partial maps (`base to view`, `view to base`). Corrections replace a base range; strikes mark it; notes insert zero-width markers. Corrected words share the replaced words' time span, divided by length (decision 18). The view is **derived on read and cached by `(base_hash, max(edit.id))`**; it is never a stored second copy of the words.

## 5. State engine

An anchor is in exactly one state:

| State | Meaning | Shown as |
|---|---|---|
| `resolved` | Exact excerpt match in base | solid keyline |
| `approximate` | Aligned with tidying between anchors | dashed keyline (exists today) |
| `ambiguous` | Two or more equal candidates | timecode window, no keyline; never silently chosen |
| `unresolved` | No match | timecode window only |
| `stale` | `base_hash` changed under it | as unresolved, until rebased |

Orthogonal **flags**, computed from overlaps and never stored as truth: `struck_overlap` (a strike touches a kept run), `gap_changed` (a correction landed inside a `D`/`N` gap), `text_diverged` (the researcher's edit changed the ellipsis count), `silent_gaps` (n), `orphaned_ellipses` (n).

Events and what each does:

| Event | Anchor | Flags |
|---|---|---|
| Base imported / base_hash changes | recompute; `stale` then rebase | clear |
| Quote extracted / re-extracted | create or re-match (§4.2) | recompute |
| Correction (kept run) | unchanged | none; text patched by the one write path |
| Correction (inside a gap) | unchanged | `gap_changed` |
| Strike | unchanged | `struck_overlap` if it touches a kept run |
| Split / join / move | unchanged (base-coordinate) | none |
| Researcher edits the quote | unchanged | `text_diverged` if ellipsis count changed |
| Remove an edit | unchanged | recompute |

## 6. Data flow and journalling

```
pipeline ──► intermediate JSON (segments, words, quotes) ──► importer (idempotent upsert)
                                                               │
                         ┌─────────────────────────────────────┤
                         ▼                                     ▼
                  base: segments + persisted tokens     quote_anchors (derived, §4.1)
                         │                                     │
researcher edit ──► transcript_edits (DB, write-ahead) ──► .bristlenose/transcript-edits.json
                         │                                     │
                         └──────────► view = fold(base, edits) ┘
                                              │
              gutter · quote cards · line-break placement · exports · MCP / chat
```

- **Replay is idempotent.** The unique key makes a replay of the same edit a no-op; the importer replays the whole journal in base-coordinate order on every import, in one transaction.
- **A write is one row.** Concurrent PATCHes from the SPA, the importer replay and a Mac serve restart cannot interleave inside a row. The importer already refuses registry writes while a run is in progress (`refusal.analysis_running()`); the journal write follows the same rule.
- **A stale client cannot corrupt.** Every edit request carries `ref_hash`; the server verifies it against the base and answers 409 `edit_refused` with a reason, never an English string the client prints.
- **Crash recovery.** A crash mid-replay rolls back the transaction; the file mirror is rebuilt from the DB; the cached view is keyed on `(base_hash, max(edit.id))`, so a half-applied state cannot be read as current.
- **Journalling for the researcher** is the Bin and Put Back (decision 17): any edit removable in any order. Because all ranges are base coordinates, almost nothing depends on anything else; the one exception is below.

## 7. Stress tests

Each row is a scenario, what the model does, the invariant that decides it, and where the proof lives (a new test unless it names an existing one).

| # | Scenario | Outcome | Rule |
|---|---|---|---|
| 1 | Researcher corrects a word in the transcript, same length ("bee bee sea" to "BBC" counts as 3 to 1, see 2) | Anchor unchanged; quote text patched by the one write path | I2, I7 |
| 2 | Correction changes the word count | Anchor unchanged (base coordinates); `base to view` map shifts; corrected words share the replaced span's time | I2, decision 18 |
| 3 | A correction lands inside an excised **gap**, and turns filler into content ("um" becomes "no") | Anchor unchanged; `gap_changed` raised; the quote is re-analysed per decision 26. The excision is no longer pure filler | I5 |
| 4 | Researcher edits the quote text (small tidy) | Anchor unchanged (it describes the pipeline text); `text_diverged` only if the ellipsis count changed | I6 |
| 5 | Researcher **deletes a chunk from the middle** of a quote | The edit narrows nothing in the base; a derived alignment of the new text shows an `N` with **no ellipsis**: `silent_gaps`. Open decision: nudge to insert `…`, insert it, or allow it (§10) | I5 |
| 6 | Researcher crops the start or end of a quote | Derived alignment narrows the gutter highlight; stored anchor still covers the original, so Revert is exact | I1, I6 |
| 7 | Researcher adds words to the quote | `I` run; bracketed is fine; **unbracketed speech-looking words** are the one thing to prevent | decision "the one thing to prevent" |
| 8 | Researcher **strikes** a chunk of transcript inside a quote's kept run | `struck_overlap`; the quote is excluded whole until cropped clear (the proposal in design-transcript-editing § Open) | decision 13 |
| 9 | Strike lies wholly inside a gap | Nothing to do; the struck words were already excised | I2 |
| 10 | Strike spans two quotes, or a quote's boundary | Each quote flagged by its own overlap; the strike is one Bin row (decision 19) | I2 |
| 11 | Researcher hides or bins a quote | Anchor and gutter mark persist, greyed; no cascade | existing `QuoteState` |
| 12 | Split a paragraph the quote spans | **Anchor unchanged** (today: position plus six words breaks). A split of the quote itself cuts the `ops` at the base position: two anchors, `ops` partitioned | I2; CIGAR is splittable |
| 13 | Join paragraphs; move one to another speaker | Anchor unchanged; a moved paragraph's quote leaves evidence through the existing filter | existing `speaker_slots` |
| 14 | Analyse with new files; the model re-cuts a quote differently, or omits it | Re-match by span overlap (§4.2); an omitted curated quote keeps its row and anchor, `orphaned` | I3 |
| 15 | Re-transcription changes the base | `stale`; rebase by word diff; below θ stays `unresolved`; edits with a mismatched `ref_hash` are **refused and listed** | I3 |
| 16 | Re-analyse | Discards edits and anchors (decision 12); both regenerate | decision 12 |
| 17 | Redacted session: no word timings | Base is tokens, `timing = 'interpolated'`; anchors work; **pause features are unavailable**, not faked | I4; assert only what we know |
| 18 | A phrase repeats ("I mean" three times) | Candidates ranked by time within the model's window; a tie is `ambiguous`, never silently picked | I3 |
| 19 | Text with no spaces (CJK) | Tokenised once at import by a segmenter and **persisted**; render never re-tokenises | I4 |
| 20 | Two correction edits on overlapping ranges | The second is refused until the first is removed (one saved edit per range, decision 4) | decision 4 |
| 21 | A correction inside a strike | Refused: struck text is not editable. A strike over an existing correction is allowed; the correction goes dormant and returns on Put Back | decision 17 |
| 22 | Remove an edit out of order | Free, because ranges are base coordinates. **One exception:** an edit whose range is expressed against another edit's replacement words (a correction of a correction) supersedes it and is not a separate row | decision 17 |
| 23 | Serve restarts mid-replay, or a stale tab edits after a base change | Transaction rolls back; the mirror is rebuilt; the stale edit gets 409 `edit_refused` | §6 |
| 24 | Copy or move a study | Anchors are database-relative; no path enters them | project identity |
| 25 | A segment with nothing heard (inaudible) | `base_count = 0`; anchors may span it; split and join refuse it (existing) | existing inaudible net |
| 26 | Offline HTML export and MCP / chat | The projection plus anchors (indices and hashes only) are embedded; route classified `EMBED_PATH_TEMPLATES` or the coverage test fails | `test_serve_export_coverage.py` |
| 27 | Clip export across a correction | Times outside the correction are real word times; inside, interpolated (decision 18) | decision 18 |

## 8. What it means for line breaks

- **Gap kind and length are features the placement lab can read**: a `D` is filler (a pause inside a thought, no break), an `N` is a seam between two used runs (a strong candidate). The owner's earlier point that excision gaps carry significance becomes a toggle on measured data, not an assumption.
- **Ellipsis fidelity is enforced by I5**, not by a prompt instruction.
- **Breaks are presentation, not wording** (owner, 3 Nov 2026: trimming at the Quotes stage is for presentation and to clear the researcher's head; fixing the transcript is a correction to the source, a different kind of edit with different undo). So they are stored **apart from the words**, in the overlay of §3.4, never as `\n` in `Quote.text` or in a `QuoteEdit`. This reverses the earlier recommendation in this note, which stored breaks as characters.
- **Why the overlay beats characters in the text:**
  1. *No pin, no "edited" mark.* A `QuoteEdit` pins a quote against re-extraction and mints a durable id; adding line breaks must not do that.
  2. *No clash with decision #30.* A change in spacing only is already "no edit". The card separates the breaks from the words on commit: words unchanged, so no text edit; breaks recorded in the overlay. (I saw #30 on `EditableText` and in the transcript-edit steps, not on the quote path; confirm before building.)
  3. *Nothing downstream sees a `\n`.* Search, chat and MCP grounding, the AutoCode and signal prompts, the gutter's matcher and CSV never receive one, which retires assumption 9 of §14. Each export adds breaks in its own way from the overlay: a soft break in a Miro sticky, a newline in a cell.
  4. *It is the house pattern* (`TranscriptLayoutEdit`: a position and a `verify`).
- **Two sources, one shape.** `auto` rows come from placement rules; `researcher` rows come from a hand edit, and win over `auto` until the wording changes. Revert of a quote edit removes the researcher's text edit and leaves the breaks alone; a separate control clears the researcher's breaks.
- **Placement inputs by phase.** The first phase uses text alone: sentence ends, `...` runs, and line length. Timing (gap duration, `D` versus `N`) needs the anchor and comes with it (§15). Breaks are whitespace, so they never touch `ops`.
- **Every surface that draws a quote asks one primitive**, `QuoteText`, which takes the resolved wording and the overlay and decides how to draw them (a half-line gap for level 2, a line break for level 1, nothing when the preference is off). The Quotes card, the Screens card (same card), Discussion, Signals evidence and the Dashboard migrate one at a time (§15).

## 9. Measure first

1. **Coverage.** Run §4.1 over the 918 quotes in the 10 local projects the gutter note measured. Target: beat 76%. Report `resolved`, `approximate`, `ambiguous`, `unresolved` separately.
2. **Do `N` gaps occur?** Count `N` ops in real quotes. If there are none, the pipeline only ever produces `D`, and `N` exists only for researcher crops.
3. **Silent gaps.** Count `D` ops with no ellipsis: how often does the model drop words without marking it?
4. **Pause signal.** For `D` and `N` gaps with exact timing, plot gap duration against where a researcher put breaks (the IKEA quote is one example; the lab collects more).

## 10. Open decisions for the owner

1. **A researcher cuts the middle out of a quote and writes no ellipsis** (row 5). Nudge, insert, or allow?
2. **Two kinds of omission, one mark?** `...` today means "filler removed". A cut of substance is the editorial convention `[...]`. Do `D` and `N` show differently?
3. ~~Line breaks: characters in the text, or an overlay?~~ **Settled 3 Nov 2026 (owner's presentation-versus-source cut): an overlay, §3.4 and §8.** Still open inside it: how a hand-typed break in the card is separated from the words on commit, and whether the overlay is also shown in the Signals evidence bullet, where a half-line gap may not fit.
4. **θ for rebase and for an aligned excerpt** (§4.1, §4.3), and the `D`/`N` length threshold, are measured, not guessed (§9).
5. **Does a quote the model omits keep its row** when it is curated? (§4.2 assumes yes; the importer's stale-quote rule decides.)

## 11. Verified and not verified

**Read in this session:** `models.py` `ExtractedQuote`; `server/models.py` `TranscriptSegment`, `TranscriptLayoutEdit`, `Quote`, `QuoteEdit`; design-transcript-editing decisions 3, 4, 6, 9, 11, 12, 13, 17, 18, 19, 26 and its keystone section; `design-transcript-gutter.md` (the 76% figure); the extraction prompt's ellipsis rule; `s07_pii_removal.py:593`; `server/CLAUDE.md`.

**Not read, and therefore not claimed:** how the importer deletes or keeps a curated quote the model omits; how `words_json` maps to merged segments in every path; whether any real quote has a non-adjacent span; whether the Python segmenter choice for CJK is available in the sidecar. Each is a first-hour check before any code.

## 12. Prior art (searched 3 Nov 2026)

`design-transcript-editing.md` § Prior art already surveys Descript, Trint, Otter, Dovetail, Rev, Grain and Reduct; this adds what bears on **tracing evidence back to the raw**. Source quality is uneven and noted.

| Source | What it says | What we take |
|---|---|---|
| [CASRAI: CAQDAS workflows](https://casrai.org/guides/caqdas-workflows) and NVivo, ATLAS.ti, MAXQDA reviews (secondary and vendor-comparison pages; **weak evidence**, verify in the vendors' manuals) | Each coded segment stays linked to its exact place in the source; the audit trail comes mainly from memos, not from the link | The link is table stakes. What is rare is a link that survives an edit |
| NVivo guides ([Toronto](https://mdl.library.utoronto.ca/technology/tutorials/introduction-nvivo-14-mac)) | Source files open **read-only**; editing is a deliberate mode | Supports I1: the base is protected, editing is an explicit act |
| [Magnolia release note](https://github.com/caledavis/Magnolia/releases/tag/v1.6.2) | Editing a coded line used to **shift the codes, quotes and memos**, then was fixed | Offsets drift on edit in real QDA software. **No source found for how NVivo or ATLAS.ti behave**; this is worth testing by hand on a trial copy |
| [Descript help](https://help.descript.com/getting-started/edit-like-a-doc) and [feedback](https://descript.canny.io/feature-requests/p/replace-transcript-function-not-syncing-properly-timing-issues) | Edits are non-destructive and deletions are hidden, not erased; word-level alignment means a delete cuts only that word's audio; **Replace Transcript changed word timings** even for spelling fixes | Supports I1 and decision 18 (corrections keep the replaced span's timing). Rewriting words must not rewrite times |
| [Hypothesis, "Fuzzy Anchoring"](https://web.hypothes.is/blog/fuzzy-anchoring/) (2013; the current client may differ) and the W3C Web Annotation selectors | Store position **and** the quoted text with prefix and suffix; search near the stored position first, then fuzzily; a quote can match more than once, a position cannot | `ref_hash` plus `prefix` and `suffix` (§3.2); candidate ranking and `ambiguous` (§4.1). Added to the schema from this finding |
| [TEI stand-off](https://wiki.tei-c.org/index.php/Stand-off_markup), [STAM](https://annotation.github.io/stam), [brat](https://github.com/nlplab/brat/wiki/Annotation-Data-Format) | Text stays unmodified; annotations point into it, zero-based; brat supports discontinuous annotations. The ACE pilot docs warn that "immutable" sources are often not in practice | Our base-plus-overlay design is the mainstream pattern. Discontinuous annotations are our multi-run quote. The ACE warning is why §4.3 exists |
| [Lingard, "Beyond the default colon" (2019)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6904374/) | Keep quotes verbatim; an ellipsis inside a sentence differs from one after a full stop (a whole sentence dropped); cut only what does not bear on the meaning; put added words in square brackets | The `D` and `N` split (§1). Insertions in brackets (the one thing to prevent) |
| [Koji checklist](https://www.koji.so/visuals/editing-interview-quotes-checklist), [CASRAI conventions](https://casrai.org/guides/transcription-conventions-qualitative-research), [Scribendi](https://www.scribendi.com/academy/articles/interview_quotes.en.html) (practitioner guides, not standards) | Edit a copy, never the analysed transcript; cleaned quotes should trace to a master transcript; **state whether quotes are verbatim, lightly cleaned or translated**; do not stitch answers from different places | Supports "go back to the raw". Suggests a study-level **fidelity statement** the anchor can generate (§13) |
| [OHMS](https://cni.org/topics/digital-humanities/in-sync), [Transana](https://www.transana.com/learn/screencasts/transcription-time-codes/) | Index entries and clips tie to timecodes; word-level search jumps to the moment | Timecode-only linking is the field's norm and is what we already do. Nothing found beyond it |
| [Jerome's *per cola et commata*](https://www.britannica.com/topic/per-cola-et-commata) (4th century; see also [his preface to Isaiah](https://www.fourthcentury.com/?p=10916)) | Text set out in sense-units, each on its own line, to show a reader where to pause and breathe when reading aloud; classical units *comma*, *colon* and *periodus*; placed by an editor's judgement of sense | The breathing-marks overlay is this layout, generated. A line between phrases, a larger gap between thoughts. Detail and a paragraph-length benchmark: [research-paragraph-length-benchmark.md](research-paragraph-length-benchmark.md) |

**Not found:** a published standard for quote-to-timecode provenance in UX or qualitative work. **Not searched:** W3C PROV-O, UIMA's stand-off model, and how Dovetail, Condens and similar repositories store a quote's source range. **From memory, not re-checked this session:** Peritext (Litt et al., 2021), SAM/CIGAR, GFF3, VCF, UCSC chain files.

## 13. What better data could unlock

The mockup drives the requirements; the structure also opens things the old data could not. Each is a candidate for the mockup, with the data it needs.

| Candidate | Needs | Not possible today because |
|---|---|---|
| **Peek at a cut:** hover an ellipsis to see the words it replaced; click to land on them in the transcript | gap ranges (`ops`) | an ellipsis is only characters |
| **Two ellipsis marks** for filler versus a sentence dropped (Lingard) | `D` versus `N` | no distinction is recorded |
| **Play it as cut, or as spoken**: skip the excised runs, or hear what was left out | kept and gap runs with exact times | clips cut one start-to-end range |
| **Fidelity line per quote and per study**: "31 words kept, 6 cut, 2 added"; a methods-ready statement | counts from `ops` | nothing counts |
| **Coverage track**: a strip beside each session showing which stretches are used as evidence, with tags and sentiment on parallel tracks (a genome-browser view) | anchors in one coordinate system | quotes cannot be placed word-exactly |
| **Exact context expansion** (the parked feature): extend a quote by a sentence in either direction | base range | it matches text in the browser |
| **Edit that shows its reach**: correct a word and see exactly which quotes it touches | overlap of edit and anchor | highlight desyncs after an edit |
| **Overlap and duplicate detection** between quotes | overlapping base ranges | no shared coordinates |

## 14. Assumptions and what this note relies on

Everything here that I did not establish myself, by origin, so a wrong one can be found.

**A. Prior decisions relied on (documents; the owner's own rulings)**

| Relied on | Where | Age and risk |
|---|---|---|
| The keystone is a persisted word-range anchor (decision 3); one word-range type and one edit record (order-of-work step 1) | design-transcript-editing | Written 26 Jul 2026, amended 24 Oct. The 24 Oct amendment says its payoff for incremental analysis shrank; **this note adds a new reason (line breaks), which is a scheduling call, not a given** |
| One saved edit over an immutable original; revert deletes the row (4); any edit removable in any order (17); Re-analyse keeps nothing (12); edits keyed on time plus words (11); corrected words share the replaced span's time (18) | same | Decisions, current |
| Corrections flow both ways, editorial edits stay with the quote (6); newer transcript edit wins in the reworded case (26, 2 Nov); the effect of an edit is judged by re-analysis (13) | same | **Revised twice in 10 days.** Row 3 and 4 of §7 lean on these and could move again |
| Strike keyed on session, time range and words; excluded whole until cropped clear (decisions 9, 19; § Open) | same | The "excluded whole" part is a **proposal**, not a decision |
| 76% of quotes are found by the gutter's matcher; the rest are not | design-transcript-gutter | Measured 17 Oct 2026, 918 quotes, 10 local projects. Re-measure |
| Importer matches re-cut quotes by start second then words at 0.6; ordinals are never re-ranked | `server/CLAUDE.md` | Read from the doc, not from `importer.py` |
| Refuse, never guess; an edit that no longer matches is skipped and logged | `TranscriptLayoutEdit` docstring (read) | Code read |
| The extraction policy replaces filler with `...` | `quote-extraction.md` (read) | Verified |
| Redaction clears word timings | `s07_pii_removal.py:593` (read) | Verified; the July doc cited line 193, so line numbers rot |
| Re-analyse is the nuclear option; the report is a file the researcher owns; Mac prefs must be mirrored, not `localStorage` | root `CLAUDE.md`, `frontend/CLAUDE.md` | Current |
| Beta means almost no new features | the maintainer's memory notes, **not a repo document** | I treated it as binding; you have since called this feature a big win |

**B. Things you told me in this conversation that I built on**

Ellipses mark excised material and are an ethics matter (not hesitations); the raw is always one click away; automatic placement is needed while there are hundreds of quotes; line breaks "really make things nice"; a lab with sliders and a visual-preferences control (focus, density, line breaks); a native control and a browser control; the work is attacked from both the data end and the UX end.

**C. Assumptions I made and have not verified**

1. The quote card's edit path (`useCropEdit`, hybrid mode) is where typed breaks are lost. **I read only `EditableText`.** The three causes I listed are hypotheses with no reproduction.
2. Decision #30 (a spacing-only edit is no edit) applies to quote edits. I saw it on `EditableText` and in the transcript-edit steps, not on the quote path.
3. An edited quote is pinned and minted a durable id. I took this from the July doc (citing `importer.py:2667`), which I did not read.
4. Anchors can be computed in the importer from data already in the database, with no pipeline change. This fails for a session with no word timings.
5. `verbatim_excerpt` is usually present and usually an exact substring. The gutter note says it is not found for 24%, which I read as "the model tidied it".
6. The pipeline produces only `D` gaps. Inferred from the prompt; unmeasured.
7. The base is the post-redaction sequence. Inferred from quote extraction running after redaction.
8. Whisper word times are good enough to measure a pause. **Word-level timestamps are known to be approximate**; I have not measured it here.
9. ~~`\n` in quote text breaks nothing downstream.~~ **Retired 3 Nov 2026:** breaks no longer enter the text (§8). What replaces it is untested: each export must add the breaks from the overlay itself. The Miro export splits a sticky's text on `\n` (`miro_export.py:324`), which is all I saw of how it handles them.
10. A persisted tokenisation for CJK is available in the sidecar. Unchecked.
11. A density preference does not already exist. Unchecked; the Mac has a typography setting.
12. The census of where quote text is drawn (about 7 SPA surfaces, about 30 Python files) came from text searches, not from reading each one.
13. All thresholds (θ, the 90% rebase floor, the `D`/`N` length cut, the 3-word context) are placeholders to be measured.

**D. Things I said that turned out wrong, so they are not relied on**

That ellipses were hesitations (corrected by you); that the pause rule should discount excision gaps (you suspect they are always significant; now a lab toggle); that a break-only edit would be cancelled by decision #30 (a hypothesis only).

## 15. Phasing (3 Nov 2026)

Which of these lands before the 24 Nov 2026 submission is the owner's call; each phase is complete without the next. The "beta means almost no new features" rule comes from the maintainer's notes, and the owner has called this work a big win, so it is listed here as a choice and not assumed.

| Phase | What | Needs | Not needed | Proves |
|---|---|---|---|---|
| **0. Reproduce** | A failing test: type a shift-return in the quote card, commit, read it back. Find which of the three suspects is real (`textContent` on commit, `white-space` on display, decision #30). Read `useCropEdit` and the hybrid mode first | the card | anchors, transcript, overlay | what is actually lost today |
| **1. Overlay and primitive** | `quote_breaks` (§3.4); `QuoteText` draws it on the Quotes card first; the card separates a typed break from the words on commit; an on/off preference; the half-line gap as one token | the resolved wording; one shared tokeniser | anchors, transcript edits, timing | that line breaks read better with hundreds of quotes on screen (the mockup drives this) |
| **2. Placement from text** | `auto` rows from sentence ends, `...` runs and line length; none for short quotes; measured against hand-broken quotes in the lab | phase 1; the lab (`experiments/line-break-lab/`) | anchors, timing, the model | how far text alone gets |
| **3. Every surface** | Migrate Screens, Discussion, Signals evidence and the Dashboard onto `QuoteText`, one at a time, each with its existing tests; settle which show the researcher's edit (§8; Signals today shows the pipeline's wording) | phase 1 | anchors | wording parity across surfaces. Touches the cache key Signals cards use (decision 21), so check the cost first |
| **4. Exports** | Miro, FigJam, slides, CSV and XLS add breaks from the overlay; test the chat and MCP surfaces for none | phases 1 and 3 | anchors | the same quote reads the same everywhere |
| **5. Derived anchors** | §4.1 in the importer, read-only, no edit feature; spike first (§9); backfills existing projects without a re-run | the base coordinates, persisted tokenisation, prefix and suffix (§3.1, §3.2) | `transcript_edits`, the journal, rebase | coverage over 76%; whether `N` gaps occur; how many cuts are silent |
| **6. What anchors unlock** | Timing-based placement (`D` and `N`, pauses); peek at a cut; two ellipsis marks; fidelity line; coverage track; exact context expansion (§13) | phase 5 | transcript edits | each only if the mockup shows it earns its keep |
| **7. Transcript editing** | Corrections, strikes, undo, rebase (§3.3, §4.3), the resolver and corrections as an overlay | phase 5; decisions 17 and 26 | | **after 24 Nov**; GA-gating, about 2027 |

**What phases 0 to 4 leave alone:** the pipeline, the database tables for quotes and edits, the transcript page, and every existing edit rule. Phase 1 adds one table and one primitive.

**What keeps phase 7 open:** from phase 5, anchors address the base by index with a persisted tokenisation, a `ref_hash`, and context words. None of that needs the edit feature, and all of it is needed by it.

**Derived** means computed from data already stored, deterministic, and rebuildable at any import. It is a cache of provenance, not researcher state, so it can be recomputed, improved, or thrown away without losing anyone's work.
