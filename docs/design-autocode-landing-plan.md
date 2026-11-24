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
| D41 | Phase 2 review (lead's call, owner away; D29): a PENDING proposal is sorted by the lines on Apply, as shipped (N175: an unhidden quote's proposal comes back to the review); Apply is on when a line moved or a pending row sits outside the tentative band. Threshold decisions keep D26. Phase 3 stores the accept line rounded UP to the grid, so the run's own cut leaves no pending row above it. **Owner to confirm.** |
| D42 | Closing the review after a row decision refreshes the lenses (as Apply does), so a tag removed in the dialog does not linger on cards (lead's call). |
| D43 | The review waits for the stored lines before drawing, within the 5 s status-read limit; a failed read shows "Failed to load proposals" with Apply off; Apply has the row writes' 30 s timeout (lead's call). |
| D44 | A row override carries the status the dialog showed and is refused if it changed since (D34's stale-window protection, extended); any refusal re-reads the row. The zone lists keep their shipped open/closed defaults (lead's call). |
| D45 | **Resequenced (lead's call, D29/D32):** per-batch live acceptance (D6) lands in Phase 4 with the playback that shows it, not in Phase 3: accepted tags appearing mid-run before Phase 4 would be the D32 regression again. Phase 3 is the end-of-run hybrid cut and the stopped-run settle. **Owner to confirm.** |
| D46 | The cut accepts at the stored line itself: the 30% rank rounded UP to the 0.05 grid, on every path (completed, stopped, resumed). Every accepted proposal is then at or above the stored line and every pending one below it, so a later re-cut can never invert the order (Phase 3 review, lead's call). An off-grid rank takes slightly under 30%. Ties at the line all go in, so a codebook answering one flat confidence has all of it accepted. **Owner to confirm the tie rule.** The cut commits in the same transaction as the run's outcome, so no reader sees a finished run without its cut. Old studies with no stored lines are not cut retroactively (D29). |
| D47 | **D6 refined: the live line never falls** (lead's call, owner to confirm). After each batch the line is the highest of every live line so far and the running estimate, kept on the job (`live_accept_line`, migration 028) so a resumed run continues from it. Measured: with three calls at once batches finish out of order, and D6 as written let an early dip lower the stored line; on the 109-proposal UXR run 200 random timings averaged 31% accepted and reached 47%. With the rule every timing matched the end-only cut (28%). **Owner to know:** with the 0.80 floor and a line that never falls, only proposals at 0.80 or above can turn green live. On the real trial runs that is about 16% of the run's final accepted tags (14 of 30 on the 109-proposal run); the rest turn green in the end-of-run top-up. **Known tail:** if a run's exact cut ends above the live acceptances (synthetic, well-fitting studies with an exact line of 0.85 to 1.0 and weaker early sessions), the never-taken-back reconcile lowers the stored line: p95 +26 points accepted. No real trial run does this: fewer than 1% of real proposals score above 0.80. A run that does logs one INFO line. |
| D48 | **Every end of a first apply settles** (D27 extended, lead's call, owner to confirm): a stop, a failure, an outcome that could not be saved, a crash found by the boot sweep, a missing codebook template. Each stores lines, tops up, excludes below 0.30 and tags the accepted, so no ended run holds accepted proposals without their tags or stored lines. A retry resumes at the stored lines. Signals is rebuilt after a stop or failure only when the settle made a tag (D31). |
| D49 | **Review is refused while a first apply codes or settles** (D17 enforced on the server): the re-cut, accept-all and deny-all answer 409 with "AutoCode is still coding this codebook. Review it when the run has finished."; the dialog shows its existing Apply failure. A single row's accept or deny stays allowed and pinned (D2); catch-ups are not refused (D20). |
| D50 | **Live floor 0.75 and a softer final wave** (owner, 23 Nov 2026). Until 25 proposals have landed the live line is not below 0.75 (was 0.80; D47's line still never falls). Measured on the real trial runs: 44% of a run's greens land live instead of 16%, with no overshoot on any real run (synthetic high-confidence studies: p95 +35 points, against +26). The end-of-run top-up plays strongest first over about 3 s. The owner tunes this empirically: if real studies regularly need the lines moved by hand, the defaults move. |
| D51 | **The Mac pop-up is hidden only where the sidebar shows AutoCode** (lead's call, owner to confirm). Phase 5a's lines (and the running count that already shipped) are drawn by the AppKit sidebar only, which is still behind the default-off `BristlenoseAppKitSidebar` flag (`BristlenoseFlags.swift`; cutover confirmed, not done). Phase 5b hides the AutoCode pop-ups (D38, D40) only when the Mac host says its sidebar shows them; the SwiftUI sidebar keeps the pop-up until the cutover, so no Mac user is left without progress. |
| D52 | **⌘. is held for a later review** (owner, 23 Nov 2026). Phase 5a's "Stop AutoCode" menu item stays as committed, with no ⌘.; ⌘. stops only a pipeline run and keeps toggling the sidebars on Quotes. The owner expects ⌘. on the Mac to stop whatever is happening without naming every kind of work, and finds "Stop AutoCode" too specific; nothing changes until that is designed (backlog, 100 days §8). |
| D53 | **A catch-up that fails or comes up short shows its pop-up in the Mac app** (lead's call after the Phase 5b review, owner to confirm). The Mac sidebar has no ended line for catch-ups, so hiding their pop-up in every ending (D40) left a rate-limited, failed or partial pass silent. A hidden AutoCode or catch-up job stays hidden while it runs and when it ends completed or stopped; a catch-up ending any other way is drawn with its shipped words; a first run stays hidden in every ending (D38). A job that ends unseen leaves the activity list. |
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

### Phase 3: Default cut at the end of the run (built 23 Nov 2026)

Live acceptance moved to Phase 4 (D45). As built (commits 8d21bde40, 87f25a343, c08dc98db, c23c438aa; restore branch autocode-landing/phase-3):

- **Every first apply ends with the hybrid cut** (D5, D46): the run's counted proposals are ranked; the line is the 30% rank's confidence rounded up to the grid, never below 0.70; pending proposals at or above it are accepted, those below 0.30 excluded, the rest stay pending; `decided_by="threshold"`, conditional on still pending, so a researcher's decision is never overwritten (D2). The cut runs inside the run's outcome save (worker thread, retries), in the same transaction as the outcome.
- **The house default** writes its done marker after the cut and keeps its retry rules; `accept_at_default_cutoff` is gone.
- **A stopped first apply** settles over what was coded (D27) but stays unfinished: no `completed_at`, no marker (D35); a resumed run ends at the stored lines. The status reports `ending`, and the web page refreshes the lenses once a stopped run has settled. A **failed** first apply is not settled (lead's call: D27 names a stop; its retry cuts the whole run).
- **Catch-ups** exclude below the stored lower line, 0.30 (D5).

### Phase 4: Live landing

**Reference:** `experiments/autocode-landing/` (the lab). Its handles map to product settings; retune there, then copy the values.

- **Server (4a, built 23 Nov 2026; restore branch autocode-landing/phase-4a):** batches of 5, 10, then 25 for a first apply (D24; catch-ups keep 25, a resume ramps again), in stored order, `Quote.id` (D25). Live acceptance per batch inside the batch's save, in a savepoint so it can never fail the save (D6, D47); it writes the proposal's status only, and the tags are made at the run's cut, so ordinary readers show nothing of a running job (D32). Every end settles (D48); Review refuses mid-run (D49). **The live read** for 4b: `GET …/autocode/{fw}/proposals?min_confidence=0&live=true[&since_id=N]` returns `{proposals, total, states, run}`. `states` lists (id, quote, tag, status, decided_by) for every row the read would list, so decisions on rows already held (live acceptances, the top-up) arrive through it; identity is (id, quote, tag) because SQLite reuses ids; `run.cursor` is the largest id in this answer's proposals; the page stops after the first read with `run.settled`, which waits for the cut and for any catch-up in flight.
- **One playback store on the page**, between the data and every view: quote cards, the tag sidebar, the Codebook lens and both histograms read from it, so no view shows a tag another hasn't played yet.
- **Pacing by queue size**, with gradual speed changes: start below a baseline call time, speed up freely, slow gently, cap flashes at about three a second, and play the rest out over 1 to 2 s when the server finishes. The baseline needs a home that outlives a study and the Mac app's quit: browser storage does not (`frontend/gotchas.md`), and each study has its own database; until an app-wide store exists, a built-in starting value per model (about 49 s for a batch of 25 on Sonnet 4.6, Phase 0b) and the run's own timings (review 10).
- **Landing:** accepted tags flash (`badge-accept-flash`) on the card, the sidebar row and the lens row; tentative tags appear quietly; the D8 pulse schedule.
- **Layout:** the tag row's height is reserved, so a landing tag never moves the page; filtered lists take matches live (D10), so check that WebKit keeps the reading position when content is added above it.
- **Edge cases:** a page opened mid-run shows what's already saved without flashing it; a reload works out the state again; a hidden window pauses and then catches up quickly; catch-up passes land the same way, with Review live (D20).
- **Decisions mid-run:** accepting or excluding a tentative tag on a quote card while the run lands is a researcher decision, pinned (D2).
- **The end of a run:** the top-up's few accepted tags flash as the last of the playback.
- **Histograms:** the scale only grows, in rounded steps; squares or bars are chosen once, from the quote count, at the start.
- **Status:** the Mac line counts what the server has (it is native and cannot see the page); the CLI pop-up waits for playback (D11).

**Measured live, 24 Nov 2026** (one first apply of UXR on a scratch copy of the Talismanic study, Claude Sonnet 4.6, 111 proposals, 49,622 tokens in and 10,903 out, about $0.31; probe in the lead's scratchpad, not committed). Calls of 12, 24, 40, 47, 44 and 37 s for batches of 5, 10, 25, 25, 25, 21; the first proposals on the live read at 12.8 s. Accepted live as the batches landed: 3, 11, 18, 24, then 26 after the end-of-run top-up, so 24 of the run's 26 greens landed live (the run's exact line, 0.75, equalled D50's floor). The live line held at 0.75 and never fell; stored lines 0.30 / 0.75; 26 accepted (23%: the 30% rank fell at 0.72, off the grid, so D46 takes a little under 30%), 85 pending, none excluded; 0 inversions; 26 AutoCode tags made at the cut, one per accepted proposal. Not checked live then: the page's playback, and the Mac app.

**The page's playback measured, 24 Nov 2026** (a second real first apply on the same scratch copy, about $0.31, watched by a Playwright probe in Chromium and WebKit at once, sampling the Quotes page every 100 ms beside the server's live read every second; the pages were opened 4 s into the run). Both browsers: the first tag on screen at about 16 s; at most 3 landings in any second; the page never showed more than the server held; it ended with exactly the server's 25 accepted and 85 tentative, with nothing leaving the page at the hand-over; the tentative pulse on; one pop-up (browser); no console errors. **A gap found, already there before this work:** the page reads the runs in flight once, when the report loads, so a run started after that by anything other than this page (another window, or the server's house-default apply after a pipeline run) gets neither a pop-up nor live landing until the page reloads. The Mac sidebar line still shows it (Phase 5a). Backlog, 100 days §2. Not checked: the Mac app.

### Phase 5: Progress surfaces

**5a built 23 Nov 2026** (commits 8544db603, 6328e0c9c, a71c14ff2; restore branch autocode-landing/phase-5a, which also holds Phase 6's first build because the two were built side by side). AppKit sidebar only (D51): running, Stopped, Out of credit, Provider key issue, Partial run and other failure lines; the ring's × and a "Stop AutoCode" menu item without ⌘. (D52); failures stay until the codebook is started again, "Stopped" clears when the study is opened; the line survives a reap; "Stopping…" at once; the busy hold counts its ceiling from the last progress. With two codebooks running, the newest-started run drives the line and Stop (lead's call). 
**5b built 24 Nov 2026** (commits 7c6b9315a, f995b6c7c; restore branch autocode-landing/phase-5b). The Mac host injects `window.__BRISTLENOSE_SIDEBAR_AUTOCODE__` from one tested script builder (`WebView.reportUserScripts`) when the AppKit sidebar flag is on; `hostShowsAutoCode()` reads it, and AutoCode and catch-up jobs carry `hidden` (D51, D53). The stack still polls and fires `postLLMFailure`, `onComplete` and `onSettled` for hidden jobs, so the playback hand-over and the lens refresh run unchanged. `tests/test_env_name_parity.py` now also checks every injected page global is read by the page.

**Mockup:** `docs/mockups/autocode-progress-states.html` (`279c0b0f2`), to be updated with D23's words.

- Mac sidebar lines for stopped, failed and partly failed AutoCode, in the pipeline run's words (D13, D23; `ProjectSubtitle.swift`, `SidebarSubtitleText.swift`, `ScreenReading.swift`), read from the jobs list Phase 1 widens. A line clears when the researcher opens the study or starts the codebook again.
- Then remove the pop-up inside the Mac app (`isEmbedded()`); the CLI web app keeps it.

### Phase 6: Tag sidebar overview

**Built 23–24 Nov 2026** (commits e21daee72, e32ef5fef, 9482a9add, fd90d527c, 06fff03ed, aca3a6aff; restore branch autocode-landing/phase-6). Route `GET/PATCH /api/projects/{id}/tag-overview` (server-only in the export), table `tag_overview_states`, migration 029, which seeds `auto_opened` for studies that already have a finished run so none opens by itself on upgrade. Ticks: the lower at 0.30, the upper at the live accept line during a first run, the stored lines after the cut. Bars only. The overview's writes are quiet; its read lives in a module store. New keys `tags.countTags_*`, `tags.summaryFromCodebooks_*`, `autocode.review.tally`; new tokens `--bn-colour-positive-text`, `--bn-colour-warning-text` in all 8 palettes. Bundle headroom after it: 0.6 kB of 222 kB.

**Mockup:** `docs/mockups/tag-sidebar-autocode-histogram.html` (`24e947017`, and the later update for "34 tags" and the researcher's own tags).

- The overview as D17, built on the existing `ConfidenceHistogram`; Review opens the existing `ThresholdReviewModal` for its codebook.
- **Remembered per study (D12):** a small table, a migration, a route, and its export classification (`tests/test_serve_export_coverage.py` fails until the route is classified; review 10).
- Hidden when its codebook's eye is closed; dimmed in solo mode with the rest of the summary line (not hidden; the Phase 6 audit default); absent from the HTML export (proposals are server-only there, `routes/export.py`).
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
