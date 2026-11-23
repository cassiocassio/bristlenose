---
status: proposed
last-trued: 2026-11-23
---

# AutoCode landing: build plan

What a researcher sees after AutoCode, and while it runs. Planned with the owner on 23 Nov 2026,
from a design session that started at the threshold review dialog and the finding that a first
report is far too intense. This doc is the phased plan and the decisions behind it; the
interaction detail lives in the mockups and the lab listed at the end.

**Owner, 23 Nov 2026: build all of it now**, in the beta, as a deliberate exception to the
reliability phase. The R114 UX gate still holds: each phase with new UX starts from an approved
mockup (noted per phase).

## The problems

1. **The review dialog is a one-way ratchet.** It loads only proposals still pending
   (`ThresholdReviewModal.tsx:87`) and the server refuses to change a decided proposal
   (`routes/autocode.py:753`, `:801`). After one Apply you can only narrow what is left; an
   exclusion cannot be undone in the app, though the row is kept. `design-autocode-threshold-review.md`
   §re-entry says overrides work; they do not.
2. **The first experience is too intense.** Researchers land in a full report.
3. **Nothing arrives until the run ends.** Proposals are saved in one transaction after every batch
   has answered (`autocode.py:483`, `:519`), so a run shows a spinner and then everything at once,
   and a run cut off at 90% loses all of it.
4. **The Mac sidebar has no line for a stopped or failed AutoCode.** The line exists only while a
   first apply runs; failure reaches the researcher only through the web pop-up.

## Decisions (owner, 23 Nov 2026)

| # | Decision |
|---|---|
| D1 | The review dialog shows the whole run, and its lines can be moved again later. |
| D2 | A decision a researcher makes on a tag is pinned, whenever it is made: in the review dialog, on a quote card later, or on a tentative tag while the run is still landing. No re-cut and no end-of-run top-up overrides it: the meaning of a quote, as a person reads it, is a much stronger signal than the arithmetic of a cut-off. Needs a record of how each decision was made. |
| D3 | No warning when raising the accept line removes tags: re-cutting again brings them back. |
| D4 | A threshold exclusion is not a rejection in the telemetry; only a researcher's own is (`docs/methodology/tag-rejections-are-great.md`: a rejection is a judgement a person makes). |
| D5 | Default cut after a run, then the researcher judges the result: **the hybrid**. Accept the most confident 30% of the run's proposals, never below 0.70; exclude below 0.30 (closed with Phase 0a, below). |
| D6 | Tags are accepted **live, batch by batch, on the server**, against a running estimate of the 30% cut: as each batch is saved the cut is re-estimated from every proposal so far (never below 0.70, and not below 0.80 until 25 proposals have landed). When the run ends the exact cut is known and a small top-up accepts what the estimate missed. An accepted tag is never taken back. The page only plays back what the server decided. |
| D7 | Live landing: tags land on the quote cards, the tag sidebar and the Codebook lens as batches arrive; accepted tags flash, tentative ones appear quietly; the histograms grow. |
| D8 | Tentative tags pulse during a run and for one minute after, then calm to a still dashed outline over 30 s. No pulse under reduced motion. |
| D9 | The researcher stays where they are when AutoCode starts. |
| D10 | A filtered Quotes list takes new matches live, in place. |
| D11 | The CLI pop-up says done only after the last tag has landed on screen. |
| D12 | The tag sidebar overview opens by itself once, after a first run; open/closed and merged/split are remembered per study, on the server. |
| D13 | The Mac line for a stopped or failed AutoCode reuses the pipeline run's words. |
| D14 | Two paid test runs before building (well under £1): batch size 5 against 25, and shuffled against stored quote order. |
| D15 | Sentiment is listed in the Sessions grid's order everywhere: frustration, confusion, doubt, surprise, confidence, delight, satisfaction. |
| D16 | The Mac keeps a study's server alive for as long as AutoCode works, however long. Refined after review (finding 11): held while the run makes progress; a run whose counters stop moving still meets a ceiling, so a stuck job cannot keep a server alive for ever. |
| D17 | Tag sidebar overview, as drawn in the mockup: one codebook reads "34 tags \| Review"; several read "96 tags from **3 codebooks**", the count a link that splits one merged chart into one per codebook; the merged chart has no ticks and no Review; each split chart has its own cut and Review; zone colours; tally in chart order with coloured numbers; Review present but inactive during a run. The line counts only reviewable codebooks: never Sentiment, never the researcher's own tags. |
| D18 | The green shared by Satisfaction and Accepted stays: context tells them apart. |
| D19 | Split view during a run: the finished charts hold their scale; everything rescales once, smoothly, when the run ends. |
| D20 | Catch-up passes land with the same playback, and Review stays live while they run. |
| D21 | When several codebooks run at once, Signals is rebuilt once, when the last one finishes. |
| D22 | Before any run, the top line counts every tag except Sentiment. |
| D23 | The Mac line's words: stopped → "Stopped" (no glyph); out of credit → "Out of credit" and key rejected → "Provider key issue" (error glyph); finished with some batches failed → "Partial run" (warning glyph). |
| D24 | A run sends batches of 5, then 10, then 25 (Phase 0b): first tags in about 12 s instead of about 49 s, for about $0.06 more a run. |
| D25 | Quotes go to the model in stored order, never shuffled (Phase 0c): mixing sessions changes the answers more than the model's own run-to-run noise. |
| D26 | A re-cut moves only proposals whose zone changes against the stored lines: Apply with the lines unmoved changes nothing, whatever the live acceptance did (review finding 2). |
| D27 | A first run stopped partway settles its cut at once: the exact cut over what was coded, and the top-up. Resuming continues with the same lines. |
| D28 | ~~The HTML export carries accepted tags only.~~ **Reversed (owner, 23 Nov, after the regression audit):** the export carries tentative tags as it shipped (dashed tags, the pale bar segments, their confidence-weighted part in Signals), from finished runs only, never from a run still coding or stopped. |

### Decisions after the regression audit (owner, 23 Nov 2026)

Two read-only audits checked Phase 1 as built and Phases 2–7 as planned against shipped behaviour. Phase 1 had broken three things; the plan would have broken more. Rulings:

| # | Decision |
|---|---|
| D29 | **No regressions to shipped behaviour.** A phase that changes what is shipped and tested needs a decision here naming it; anything else is a regression and is fixed before the phase lands. |
| D30 | Undo of "remove tag" restores the tag and its proposal: a tag put back by Undo leaves no researcher exclusion behind (Phase 1 regression, fixed). |
| D31 | Signals is rebuilt only when tags changed: when the last of several concurrent runs ends, after a stopped or failed first run that left accepted tags, and after a re-cut that moved something. Never after a catch-up pass, never after an Apply that moved nothing (Phase 1 regression, fixed). |
| D32 | Until Phase 4's playback exists, proposals of a run still coding, stopped or failed are not shown anywhere (quote cards, tentative counts, Signals), exactly as shipped. Phase 4 turns them on for the live page only. |
| D33 | `hide_parameters=True` stays on every database engine: no SQL error anywhere logs bound values (participant text). |
| D34 | Phase 2: the server keeps refusing an ordinary accept or deny on an already-decided proposal ("reviewed elsewhere", 409, which both clients handle); the dialog's row override sends an explicit override. |
| D35 | Phase 3: a stopped first run settles its cut (D27) but stays unfinished: no `completed_at`, and the house default's done marker is not written, so its remaining quotes are still coded. |
| D36 | Phase 7: sentiments are reordered on screen only (tag sidebar, Codebook lens), by name; `sentiment.yaml`, colour slots and Signals' columns are untouched. |
| D37 | Phase 2's dialog title loses its sparkle icon. |
| D39 | **Phase 2's dialog is approved as drawn** in `docs/mockups/autocode-review-dialog.html` (owner, 23 Nov 2026): the whole run, the pin on a person's decision (Lucide Pin, label "Your decision" in 21 locales), counters showing Apply's outcome, decided rows listed with their ✗ and ✓ (an explicit override, D34), Apply only after a line moves, the whole run when nothing is pending, and no sparkle in the title. The subtitle keeps its shipped words. |
| D40 | Mac app only: catch-up passes also report through the sidebar status line ("AutoCode · N of M" over the pass's own quotes, from the status's catch-up counts), and their pop-up is designed out of the app too; the CLI web app keeps it. The Mac side follows a running catch-up as well as a first apply (today `AutoCodeProgress.parse` skips jobs with `completed_at`). The catch-up's lens refresh and credit/key signal keep running without the pop-up (owner, 23 Nov 2026). Every other job's pop-up (clip and screens exports, Copy Screens) is untouched: the pop-up is one shared component, and D38/D40 hide it for AutoCode only. |
| D38 | Mac app only: the first-run AutoCode pop-up is designed out. The sidebar line is where progress lives, in every lens. Stop is the progress ring's hover × (the pattern copy and run already use, with its keyboard route); the long failure sentence is in the popover the line's glyph opens, an AutoCode variant, not the pipeline's Diagnostics; View Report is the tag sidebar overview's link (Phase 6), so Phase 5 lands with or after Phase 6. The pop-up's unseen work keeps running without it: telling the app about credit and key failures (`postLLMFailure`), and refreshing the lenses when coding ends. Every other pop-up stays in the app (catch-up passes, clip and screens exports, Copy Screens). The CLI web app keeps the AutoCode pop-up unchanged. |

Mockups: `docs/mockups/autocode-review-dialog.html` (Phase 2, approved, D39), `docs/mockups/autocode-mac-popup.html` (D38 is its option B, with Stop on the ring rather than the menu drawn there).

### Still open from the interface audit (defaults preserve shipped behaviour)

- **Phase 4:** the pulse schedule (D8) also obeys the app's "Show analysis animation" setting and leaves the review dialog's tentative counter alone [default]; a researcher's own accept flash is never delayed or capped by playback [default]; the review dialog's histogram keeps today's behaviour, and grow-only scales apply to the sidebar overview only [default]; catch-up passes keep batches of 25 [default]; reserving the tag row's height applies only while a run lands [default]; live landing never fires `bn:tags-changed` per batch, and the store lets a researcher's own changes through at once, keeping `initFromQuotes`' rules; in export mode the store passes the embedded data straight through.
- **Phase 6:** under search or Used, the summary line keeps today's live match count [default]; in the export, the line keeps D22's wording with no overview [default]; solo mode dims the line as today (it is not hidden); the search box still appears above 8 tags counted over all tags; add a test pinning the summary line before changing it.
- **Phase 5:** where the new lines rank against Signals, run usage and deltas; a line must survive the server being reaped (today `pollAutoCode` clears it), and clears when the researcher starts the codebook again.

Already shipped in this session: the count column and sentiment bar colours in the tag sidebar
and Codebook lens (`ee2472c52`).

## Closed questions

All six questions left open on 23 Nov were closed the same day against
`docs/mockups/autocode-open-questions.html` (decisions D5, D6, D19 to D23 above).

### Phase 0a result: the default cut (measured 23 Nov 2026)

Every AutoCode run in the trial studies, 15 runs, under three rules (share of proposals accepted):

| Runs | Fixed (≥ 0.70) | Percentages (top 30%) | Hybrid (top 30%, never < 0.70) |
|---|---|---|---|
| UXR, 8 runs | 0 to 53%, most near 50% | 31 to 41% | 0 to 40%, most 31 to 35% |
| Poorly fitting codebooks (Norman, Nielsen, Yablonski, CLI UX), 7 runs | 0 to 3%, excluding up to 100% | 31 to **100%** | 0 to 3%, excluding up to 100% |

Percentages are ruled out: three poorly fitting runs have every proposal at 0.10, so "the strongest
30%" accepts all of them. Fixed lines accept half of a typical UXR run, which is the overwhelm.
The hybrid takes about a third of a codebook that fits and almost nothing from one that does not.

Live acceptance (D6), simulated on the same runs: on runs of 37 to 159 proposals the running
estimate lands within a few tags of the exact cut (+2 to −7), with flashes throughout the run;
the end-of-run top-up adds 1 to 7 tags. A run of 25 or fewer is one batch, so it lands at once
whatever the rule. Stored and shuffled order give similar totals.

## Phases

```
0 Measure (done) ─► 1 Server foundations ─► 2 Re-cuttable review ─► 3 Default cut, accepted live
                            │                        │                       │
                            └────────────────────────┴──► 4 Live landing ◄───┘
                                                             │        │
                                              5 Progress ◄───┘        └──► 6 Sidebar overview
```

### Phase 0: Measure (done 23 Nov 2026)

- ~~**0a. Confidence spreads.**~~ Result above (§ Closed questions).
- ~~**0b. First-batch size.**~~ Two calls each on Talismanic, one at a time, Claude Sonnet 4.6: 5 quotes 12.2 s ($0.03 a call), 10 quotes 20.3 s ($0.04), 25 quotes 49.3 s ($0.06). About 3 s fixed, then about 1.9 s a quote: call time is about 94% per quote (the lab had assumed 75%). A full batch of 25 takes about 49 s; the 29.8 s median in the logs mixed in smaller catch-up passes. Settles D24.
- ~~**0c. Shuffle.**~~ 50 quotes (a block from session 1, a block from session 3), coded in stored order twice and shuffled once. Stored against stored again (the model's own noise): the same tag for 35 of 50, confidence moving 0.04 on average where the tag held. Stored against shuffled: the same tag for 30 or 31 of 50, confidence moving 0.09 to 0.10. One run each, so modest evidence, but it points one way. Settles D25. Also worth knowing beyond this plan: the same 50 quotes in the same order got a different tag for 15 of them on a second run.

Spent: $0.65. Harness: `experiments/autocode-landing/paired_runs.py`.

### Review

A Fable review of this plan (23 Nov 2026, the `code-review` agent on Claude Fable 5.2) found
eleven problems with the build as first written; each is folded into the phases below and marked
"(review n)". It confirmed the problem statements, the double full stop, the Mac words already in
the locales, the export classifications, and one proposal per quote surviving per-batch saving.

### Phase 1: Server foundations

No visible change, except the fixes. Live acceptance waits for Phase 3, so nothing is accepted
automatically before the dialog can undo it (review 4).

- **Save each batch as it finishes**, its proposals and its entries in the register of sent quotes in one transaction. The save reads before it writes, which `bristlenose/server/gotchas.md` § AutoCode says fails at once on a locked database, so a failure rolls back and retries in a fresh session; when retries run out the batch is held in memory and saved with the end of the run, never dropped (review 5). `proposed_count` follows each save, so the boot-time orphan sweep keeps what a crash left.
- **Catch-up passes too**: `_reapply_to_new_quotes` saves per batch and reads the lines when it saves, not when it starts, so a re-cut made during a pass applies to its quotes (review 8).
- **Record how each decision was made**: a new column on `ProposedTag`: threshold, researcher, or unknown. Accept-all, deny-all and the apply steps write "threshold"; the per-row accept and deny write "researcher". Rows from before the migration get "unknown", which is pinned like a researcher's decision but never counted as a rejection (review 7). Migration test beside `tests/test_migration_025_autocode_sent_quotes.py`.
- **A tag removed on a quote card is a researcher's exclusion**: `patch_tags` / `put_tags` mark the tag's proposal excluded by the researcher, so no re-cut brings it back (review 1).
- ~~**Tentative tags show during a first run**: `/quotes` returns pending proposals for a first apply still coding or stopped, not only for jobs with `completed_at` (review 6).~~ Reverted by D32: every reader of tentative tags (quote cards, the Codebook lens's tentative counts, Signals) sees only applied jobs' proposals (`autocode.of_applied_jobs`) until Phase 4.
- ~~**Export: accepted tags only** (D28): the embedded `/quotes` leaves pending proposals out.~~ Reverted with D28: the export carries finished runs' tentative tags, as shipped.
- **Telemetry:** the rejection emitter, when it is built, counts only researcher exclusions; nothing counts rejections today (D4, review 10).
- **Read what's new**: a cursor on the proposals route ("proposals since id N"), and the counts by confidence on the status read, so the sidebar needs no extra request.
- **The jobs list includes stopped and failed runs** until they are acknowledged, so the Mac can draw their lines (Phase 5; review 10).
- **The Mac's busy hold** follows D16 as refined: held while the counters move, with a ceiling on no progress (`busy.py`, `ServeReaping.swift`; review 11).
- **Signals** is rebuilt once when the last of several concurrent runs ends (D21), after a stopped run that has accepted tags, and after a re-cut that moved something (review 9); never after a catch-up pass (D31). Owner, 23 Nov: right; let the study settle before spending tokens on Signals' write-ups.
- **Fix:** the failure pop-up's double full stop ("…out of credit.."): `activity.failed` adds a full stop after an `autocodeFailure` sentence that already ends with one.

Tests: a batch's proposals and register entries commit together; a writer holding the lock does not lose a batch; a crash between batches loses only batches in flight and the sweep keeps the counts; provenance from each path, and "unknown" after the migration; a tag removed on a card survives a re-cut; ~~`/quotes` shows a running first apply's tentative tags; the export carries no pending proposals~~ (now: a first apply not finished shows no tentative tags anywhere, and the export carries a finished run's, D32/D28); an Undo of a removed tag puts its proposal back (D30).

### Phase 2: Re-cuttable review

**Mockup approved (D39):** `docs/mockups/autocode-review-dialog.html`. Build to it exactly.

**Built 23 Nov 2026** (server `6200b97d5`, `1b8b6efaf`; the dialog in the commit after them):

- The dialog loads every proposal of the run: the histogram shows accepted, tentative and excluded; the counters and zone lists show where Apply would leave each one (`frontend/src/utils/recut.ts`, the client's copy of the server's `recut_target`).
- Apply is `POST …/autocode/{fw}/recut`: it moves only threshold decisions and pending proposals (D2), and only those whose zone changes against the stored lines (D26); researcher and unknown decisions carry a pin ("Your decision") and stay put. No warning on removing tags (D3). It stores the snapped lines and asks for a Signals rebuild only when something moved (D31). Apply is off until a line moves from the stored lines. A run no lines were ever stored on gets a plain cut: only pending proposals are sorted, offered while anything is pending.
- A re-cut deletes only tags whose source is AutoCode, never a tag the researcher added by hand that the proposal happened to match (review 1).
- Accepted and Excluded list decided rows with their ✗ and ✓. On a decided row they send `{"override": true}` (D34); the ordinary accept and deny still refuse a decided proposal with 409. An overridden deny removes only an AutoCode-made tag.
- The title loses its sparkle icon: "AutoCode Review — <codebook>" (D37). The `ai` icon concept now has no caller.
- `design-autocode-threshold-review.md` trued (§re-entry, the counters, Apply).

Tests: `tests/test_autocode_recut.py` (Apply with the lines unmoved changes nothing; only zone changes move; pinned decisions never move; a hand-added tag survives; a never-cut run's plain cut; the override routes and the 409 kept for ordinary calls; Signals only when something moved) and `ThresholdReviewModal.test.tsx` § "the whole run, re-cuttable".

### Phase 3: Default cut, accepted live

- **Accept live** per D6: the running estimate of the hybrid cut on each saved batch, the cautious start, and the top-up when the run ends. The top-up and every live acceptance update only proposals still pending (the conditional-update pattern at `autocode.py:1347`), so a researcher's decision made mid-run is never overwritten (D2, review 5).
- **The end of every first apply** runs the hybrid's own step: the exact cut, the top-up, and excluding below 0.30. It replaces `accept_at_default_cutoff` as the house default's `after_apply` (which accepts everything at 0.70, the flood this plan removes) and keeps its write of the house default's `completed` marker (review 3; pin in `tests/test_autocode_house_default.py`).
- **The stored lines** are the exact cut snapped to the 0.05 grid the dialog and the catch-ups use; D26 keeps a later re-cut honest whatever the live acceptance did (review 2).
- **A stopped first apply** settles at once (D27).
- The researcher stays where they are (D9).

Test: a researcher's exclusion between a batch and the top-up stays excluded.

### Phase 4: Live landing

**Reference:** `experiments/autocode-landing/` (the lab). Its handles map to product settings; retune there, then copy the values.

- **Server:** batches of 5, 10, then 25 (D24), in stored order (D25).
- **One playback store on the page**, between the data and every view: quote cards, the tag sidebar, the Codebook lens and both histograms read from it, so no view shows a tag another hasn't played yet.
- **Pacing by queue size**, with gradual speed changes: start below a baseline call time, speed up freely, slow gently, cap flashes at about three a second, and play the rest out over 1 to 2 s when the server finishes. The baseline needs a home that outlives a study and the Mac app's quit: browser storage does not (`frontend/gotchas.md`), and each study has its own database; until an app-wide store exists, a built-in starting value per model (about 49 s for a batch of 25 on Sonnet 4.6, Phase 0b) and the run's own timings (review 10).
- **Landing:** accepted tags flash (`badge-accept-flash`) on the card, the sidebar row and the lens row; tentative tags appear quietly; the D8 pulse schedule.
- **Layout:** the tag row's height is reserved, so a landing tag never moves the page; filtered lists take matches live (D10), so check that WebKit keeps the reading position when content is added above it.
- **Edge cases:** a page opened mid-run shows what's already saved without flashing it; a reload works out the state again; a hidden window pauses and then catches up quickly; catch-up passes land the same way, with Review live (D20).
- **Decisions mid-run:** accepting or excluding a tentative tag on a quote card while the run lands is a researcher decision, pinned (D2).
- **The end of a run:** the top-up's few accepted tags flash as the last of the playback.
- **Histograms:** the scale only grows, in rounded steps; squares or bars are chosen once, from the quote count, at the start.
- **Status:** the Mac line counts what the server has (it is native and cannot see the page); the CLI pop-up waits for playback (D11).

### Phase 5: Progress surfaces

**Mockup:** `docs/mockups/autocode-progress-states.html` (`279c0b0f2`), to be updated with D23's words.

- Mac sidebar lines for stopped, failed and partly failed AutoCode, in the pipeline run's words (D13, D23; `ProjectSubtitle.swift`, `SidebarSubtitleText.swift`, `ScreenReading.swift`), read from the jobs list Phase 1 widens. A line clears when the researcher opens the study or starts the codebook again.
- Then remove the pop-up inside the Mac app (`isEmbedded()`); the CLI web app keeps it.

### Phase 6: Tag sidebar overview

**Mockup:** `docs/mockups/tag-sidebar-autocode-histogram.html` (`24e947017`, and the later update for "34 tags" and the researcher's own tags).

- The overview as D17, built on the existing `ConfidenceHistogram`; Review opens the existing `ThresholdReviewModal` for its codebook.
- **Remembered per study (D12):** a small table, a migration, a route, and its export classification (`tests/test_serve_export_coverage.py` fails until the route is classified; review 10).
- Hidden when its codebook's eye is closed; hidden in solo mode with the rest of the summary line; absent from the HTML export (proposals are server-only there, `routes/export.py`).
- Grows live from the Phase 4 store; in the split view the finished charts hold their scale until the run ends (D19).
- Before any run, the top line counts every tag except Sentiment (D22).
- New tokens for status text: the bar greens and ambers fall under 4.5:1 as small text in light mode (orange 2.2:1, green 3.3:1); the mockup's #b45309 and #15803d reach about 4.8:1 on the sidebar tint.
- Depends on Phase 2, so Review opens a dialog over the same whole run the small chart shows.

### Phase 7: Small follow-on

- Sentiment in the Sessions grid's order in the tag sidebar and the Codebook lens (D15).

## Strings (21 locales each)

- The summary line with the codebook count as a link inside it (a key that carries the markup, since word order varies).
- Singular and plural forms for "{{count}} tags" (`tags.countTags` has none) and for the codebook count.
- The tally with its counts as placeholders ("Excluded 3 · Tentative 55 · Accepted 51").
- Reused as they are: `codebook.reviewProposals` (Review), the zone words, the pipeline run's pill words (D13).

## Not in this plan

In the 100-days backlog: splitting the tag sidebar into AutoTags and Manual modes (§4), and a
150-hour study stress test (§15).

## Before Phase 1

Reviewed by Fable on 23 Nov 2026 (§ Review). A `/usual-suspects` pass is still worth running on
Phase 1's diff, which touches the database, the sidecar's lifecycle and three surfaces.

## References

- Lab: `experiments/autocode-landing/` (`279c0b0f2`): a real run's proposals and 52 logged call times (median 29.8 s, but mixing in small catch-up passes; a full batch of 25 takes about 49 s, Phase 0b). Its Lines handle lacks D6's running estimate, and its call-size share defaults to 75% where 0b measured about 94%; fix both before tuning Phase 4.
- Paired runs: `experiments/autocode-landing/paired_runs.py` (Phase 0b and 0c).
- Open questions, closed: `docs/mockups/autocode-open-questions.html` (Phase 0a's data in section 1).
- States: `docs/mockups/autocode-progress-states.html`.
- Sidebar overview: `docs/mockups/tag-sidebar-autocode-histogram.html`.
- The dialog as built: `docs/design-autocode-threshold-review.md`.
- Engine: `docs/design-autocode.md`; catch-up passes: `bristlenose/server/gotchas.md` § AutoCode.
