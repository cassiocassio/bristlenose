# Signals follows a hide

**Status: proposal, 30 Oct 2026. Nothing built.** Mockup: `docs/mockups/signals-follow-hide.html`.
Owner-agreed in principle on 30 Oct 2026 ("the plan is sound"). Revised the same day after two
independent reviews (the plan against the code, and the UX consequences). Decisions D1, D3, D5,
D6 and the "Show fewer" string were settled by the owner the same day; D2 is still open.

## The contract

A hidden quote is a researcher's judgement: true, but low quality, distracting or open to
misreading. It counts nowhere (owner, 22 Oct 2026; `speaker_slots.analysis_quotes`): not the
Quotes lens, not Screens, not Miro, not exports, not agents over MCP or the chat lens. It is
reversible, because it is a true thing that was said.

**The Signals lens is the one place that breaks it.** Since the Signals lens moved to a stored
snapshot (`/signals/snapshot`, migrations 023 and 024), a hide made after the snapshot was built
still shows on the card, in "Show all N", and in the HTML export, which embeds that snapshot.
A snapshot is rebuilt only after a completed run, a completed codebook apply, or a server start
that finds it missing or on an older payload version (`app.py`, `routes/autocode.py`).
The module docstring of `signal_snapshots.py` says hand curation does not touch it, and
`docs/design-signal-snapshot-lifecycle.md` promises a reader that returns the last complete
snapshot unchanged (Reader contract, invariant 2). This change reverses both for the quote list,
on purpose. The lifecycle doc's own event map (§5) already lists a hide as a refresh trigger, so
the doc disagrees with itself.

## What changes, and what does not

| Part of a card | After a hide | Why |
|---|---|---|
| The quotes listed, and "Show all N" | Follow the hide at once | Evidence a reader can see |
| The shown set (the four) | Refills from the remaining ranked quotes | `selectQuotes` runs over what is left |
| The contribution cells and "N voices" | Derived from the remaining quotes | Free to compute; what you can count must agree |
| Evidence assertions that cite a hidden quote | Dropped on read | Each carries `source_quote_id` |
| A card with no counted quote left | Dropped from the lens | "The reader only removes" (D3) |
| The server's card set and ranking | **Frozen** until the next run | Thresholds and ranking are a recalculation |
| Strength, concentration, effective voices, composite, confidence, flag | **Frozen as calculated** | A recalculation, deliberately not done here |
| The sentiment chip's label and flag | **Frozen** | Computed from the quotes at build time |
| Written headline and claim; the summary paragraph | **Frozen** | Costs an LLM call; may still paraphrase a hidden quote (D4) |
| Inspector heatmap cells that have a card: count, participants, intensities, and the row, column and grand totals | Follow the hide (D6) | A cell that says 6 must lead to a card that says "Show all 6" |
| Heatmap cells with no card, the "Based on N tags" banner, the participant universe | **Frozen** | No quote list in the payload to subtract from |

On screen two more things move that the server does not: the client folds near-duplicate cards
(`dedupeSignals`, similarity of their quote sets), and it runs over the remaining quotes, so a
hide can fold a card or unfold one. The contribution cells' shades are relative within a card, so
hiding one participant's quote can change another participant's shade.

No LLM call, no recalculation, no new route. The reader stays calculation-free: it only removes.

## The rule: an allow-list of counted quotes

The server keeps a snapshot quote only if its reference is in the set of references of the
quotes that count right now (`analysis_quotes`). Everything else is removed from the response.
What `analysis_quotes` follows, live and undoable in serve: a **hide**, a **speaker recode** that
takes a speaker out of the evidence, and a **moved paragraph**. A future **Delete** will follow it
too. A re-import that removes a session changes it as well, but serve has no route that removes a
session, and a rebuild normally follows; the allow-list matters there only when the rebuild is
skipped (incomplete narratives, or no cloud key).

**What it does not cover: a researcher's own edit.** Edits are stored as `QuoteEdit` rows and
Signals reads the original `Quote.text` (live and stored), so an edit changes no reference and the
card keeps showing the pre-edit text. That is an existing gap (D2), not something this change
introduces or fixes.

**One-way.** The filter only removes. A quote hidden before the snapshot was built is absent from
it, so unhiding that quote brings nothing back until the next rebuild. A quote hidden after the
build comes back at once on unhide.

**The join key** is `compute_quote_reference`, already in every snapshot quote as `quote_id`.
Its shape is frozen in payload v4: the signal path builds its record without a segment index or
an ordinal, so every stored reference is a hash with segment index -1 and ordinal 0, whatever the
database row holds. Two rows with the same participant, session, start and text share a
reference; hiding one leaves the other's twin in the snapshot (an accepted limit, rare).

## Plan, in slices (each its own commit, in this order)

1. **A row-to-reference function, in the frozen shape.** `quote_reference_for_row(quote)` builds
   the record with `segment_index=-1` and `ordinal=0` explicitly, and is documented as the
   payload-v4 shape, not as "the same record from a row". Use it from the signal path so the two
   cannot drift. **Do not unify it with `grounding.py`'s record**, which uses the row's real
   segment index and ordinal for the chat lens and MCP: unifying would empty every stored snapshot
   through the filter, or change every elaboration cache key and force a paid re-elaboration of
   every card in every project. **Pin it with a round trip on rows that carry a real segment
   index**, plus one row with ordinal 1: for each quote in each card of a built snapshot, the
   reference derived from its row equals the payload's `quote_id`. A fixture whose rows are all
   (-1, 0) would pass against the wrong builder, so it proves nothing. Mutation: building from the
   row's own segment index must make the pin fail.
2. **Server filter.** In `get_stored_signal_snapshot`, after `snapshot_payload`, apply a pure
   `filter_snapshot_to_counted(payload, counted_refs)` in `signal_snapshots.py`: per card, drop
   quotes not in the set (a quote whose `quote_id` is empty is dropped too); drop assertions whose
   `source_quote_id` is not in the set and re-number `ordinal`; rebuild `participants` from the
   remaining quotes, sorted as the build sorts them (string order); drop a card left with no
   quote; set `count`; and subtract each removed quote from the card's cell in the matching
   matrix (section or theme, by `source_type`): `count`, the participant's tally, one intensity,
   and the row, column and grand totals (D6). A card's quotes are the whole cell's quotes
   (`generic_detect.py`), so this is exact for `count`, participants, intensities and totals.
   `weighted_count` needs the quote's group weight, which the payload does not carry: check how
   the client uses it before deciding whether to leave it or carry the weight. It tolerates missing keys. Leave every other field alone. Record on the
   card, before filtering, whether it had assertions (see slice 4).
3. **The export.** The export calls the same handler, so slice 2 covers it. This slice is a test,
   in `tests/test_serve_hidden_counts_nowhere.py` (which today pins only the live routes): an
   export made after a hide contains neither the hidden quote's text nor an assertion citing it.
   `/signals/codebooks` and `/signals/sentiment` are computed live and are already correct.
4. **Client.** `selectQuotes`, "Show all N" and the contribution cells already read `signal.quotes`.
   - Rename the local `hiddenQuotes` (the quotes behind "Show all") to `collapsedQuotes`.
   - Rename the visible string behind the expanded toggle from "Hide" to "Show fewer": "Hide" now
     collides with the researcher's Hide on the same card. A 21-locale change (`signals.hide`).
   - When a card had assertions in the stored snapshot and all were filtered, keep the lead-only
     branch. Otherwise the card falls back to the full elaboration and shows a summary paragraph
     written with the hidden quote in view.
   - Guard `selectQuotes` against drawing one quote in two slots when few remain, with a test.
5. **Docs.** `docs/design-signal-snapshot-lifecycle.md` (the Reader contract, invariant 2, the §5
   row for a hide: a read-time filter now, a refresh still deferred), the `signal_snapshots.py`
   docstring, `bristlenose/server/CLAUDE.md`, and the forward plan. The CHANGELOG line is written
   at release.

## Tests that prove it (each shown able to fail)

- Hide a quote on a card after the build, read the snapshot: the quote and an assertion citing it
  are gone; unhide: both are back. Hidden before the build, then unhidden: not back (the one-way
  rule). The reader still makes no LLM call and no signal calculation (assert the elaboration and
  detection functions are not called).
- The slice 1 round trip, on rows with real segment indices and an ordinal.
- A recoded-out speaker and a moved paragraph are filtered too.
- All of a card's quotes hidden: the card is gone from the response.
- Hide the only cited quote: the claim shows, with no summary paragraph.
- Hide the 2 shown of 4 shown + 3 behind: the next 2 move up; the link reads the new total.
- Export after a hide omits it.
- Mutation: replace the allow-list with "keep everything" and watch each of the above fail.

## Decisions

Settled by the owner on 30 Oct 2026:

- **D1. Voices follow the hide; the concentration figure may be wrong.** The contribution cells
  and "N voices" light according to whether the participant is still represented in the
  remaining quotes. Concentration and effective voices stay as calculated; nobody recomputes them
  in their head, and the figure being off is acceptable. The remedy is the next run. (The strength
  can be carried by the quotes a researcher hid, since people hide the loud ones: known, accepted.)
- **D3. A card with no counted quote left is dropped.** If nothing visible supports a signal, the
  researcher does not want to see it. The design of any all-hidden state beyond dropping stays
  parked.
- **D5. The hidden-quotes counter and dropdown are page-level.** They sit on the same line as
  "Based on N accepted tags", ranged right, as the Screens lens ranges its counter, so they do
  not compete with the "Show all / Show fewer" link on any card. They list the hidden quotes of the
  section or theme the page shows (owner, 30 Oct), read live from the database: a quote hidden
  before the snapshot was built is listed even though it never reached a card. Not needed for the first slice of work; the placement is
  decided. Two things the build must settle when it is built: an unhide from here of a quote that
  was hidden before the snapshot was built cannot return to its card (the filter only removes), so
  it needs a refetch or a rebuild, or the counter will look broken exactly where the one-way rule
  shows; and an unhide made while Signals is open moves a quote in front of the researcher, so the
  Quotes lens's fly-down or the `.bn-handover` arrival applies.
- **D6. Heatmap cells follow the hide** by subtraction (slice 2), so clicking a 6 never lands on
  a card that says "Show all 7".
- **"Show fewer"** replaces "Hide" on the expanded toggle.
- **D7. The shipped cap is four shown quotes**, not three; the mockup draws four.

Still open:

- **D2. A researcher's edit.** Signals ignores `QuoteEdit` text today, live and stored. Should a
  card show a quote as edited? If so it is an overlay applied on read, and not part of the
  reference. Until decided, "redaction" is not delivered by this change for the quote list.
- **D4. The headline and summary paragraph** may describe a quote that has been hidden. Accepted
  for now. What is not accepted is a newly revealed paragraph (slice 4).

## Known small defects this leaves (recorded in the forward plan)

A hide made before the snapshot was built does not come back on unhide until the next rebuild
(the filter only removes); Signals ignores the researcher's quote edits; two identical rows share
one reference; heatmap cells with no card keep their old counts; contribution shades are relative,
so one hide can change another participant's cell; unhide does not rebuild the snapshot; the
client's folding of similar cards re-runs over the remaining quotes; and the chat lens and MCP
build their quote references differently from the Signals route, so MCP likely never serves a
cached headline.

## Later, not in this change

Live recalculation of strength, order and thresholds on every read, with lazy headlines;
recalculating on every hide (considered, not preferred: one LLM call per changed card, again on
unhide, not possible offline, cards jumping while curating); an exact join by database id; the
"+N hidden" control; a designed all-hidden state. All are recorded in the forward plan under
"Signals follows a hide".

## Human QA (what tests cannot cover)

Hide a quote in the Quotes lens, open Signals: it is gone from the card, and "Show all N" has
dropped by one. Unhide: it returns in its place. Hide every quote behind one card: the card goes
and its neighbours close up. Export the report and open it offline: the hidden quote is absent.
Press ⌘Z while on Signals after a hide made elsewhere: the open card is likely to stay unchanged
until you leave and return (not covered by tests; check). In the Mac app, hide while Signals is
open in a second window: that window is stale until ⌘R (accepted; no live push).
