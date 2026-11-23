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
| D2 | A new cut moves only decisions a threshold made; the researcher's own accepts and excludes stay pinned. Needs a record of how each decision was made. |
| D3 | No warning when raising the accept line removes tags: re-cutting again brings them back. |
| D4 | A threshold exclusion is not a rejection in the telemetry; only a researcher's own is (`docs/methodology/tag-rejections-are-great.md`: a rejection is a judgement a person makes). |
| D5 | Default cut after a run, then the researcher judges the result. Fixed lines or percentages: **measure first** (Phase 0). |
| D6 | When the server accepts: **follow the measurement**. Fixed lines win: accept batch by batch, as the catch-up passes already do. Percentages win: accept once at the end. |
| D7 | Live landing: tags land on the quote cards, the tag sidebar and the Codebook lens as batches arrive; accepted tags flash, tentative ones appear quietly; the histograms grow. |
| D8 | Tentative tags pulse during a run and for one minute after, then calm to a still dashed outline over 30 s. No pulse under reduced motion. |
| D9 | The researcher stays where they are when AutoCode starts. |
| D10 | A filtered Quotes list takes new matches live, in place. |
| D11 | The CLI pop-up says done only after the last tag has landed on screen. |
| D12 | The tag sidebar overview opens by itself once, after a first run; open/closed and merged/split are remembered per study, on the server. |
| D13 | The Mac line for a stopped or failed AutoCode reuses the pipeline run's words. |
| D14 | Two paid test runs before building (well under £1): batch size 5 against 25, and shuffled against stored quote order. |
| D15 | Sentiment is listed in the Sessions grid's order everywhere: frustration, confusion, doubt, surprise, confidence, delight, satisfaction. |
| D16 | The Mac keeps a study's server alive for as long as AutoCode works, however long. |
| D17 | Tag sidebar overview, as drawn in the mockup: one codebook reads "34 tags \| Review"; several read "96 tags from **3 codebooks**", the count a link that splits one merged chart into one per codebook; the merged chart has no ticks and no Review; each split chart has its own cut and Review; zone colours; tally in chart order with coloured numbers; Review present but inactive during a run. The line counts only reviewable codebooks: never Sentiment, never the researcher's own tags. |
| D18 | The green shared by Satisfaction and Accepted stays: context tells them apart. |

Already shipped in this session: the count column and sentiment bar colours in the tag sidebar
and Codebook lens (`ee2472c52`).

## Open (suggested default in brackets)

- **Split view during a run:** the still charts shrink as the running one grows, or hold their scale until the run ends [hold, rescale once at the end].
- **Catch-up passes:** land with the same playback; Review live or inactive while one runs [same playback, Review live].
- **Two codebooks at once:** rebuild Signals once, when the last finishes [yes].
- **Before any run:** does the top line's count include Sentiment [no, as the overview's rule].
- **D13's mapping**, to confirm in the states mockup: stopped → "Stopped"; out of credit → "Out of credit"; key rejected → "Provider key issue"; some batches failed → "Run had failures".
- **After Phase 0:** fixed lines or percentages, and the X% / Z% if percentages.

## Phases

```
0 Measure ──┬──► 1 Server foundations ──► 2 Re-cuttable review ──► 3 Default cut
            │            │                        │
            └────────────┴──► 4 Live landing ─────┴──► 6 Sidebar overview
                                   │
                                   └──► 5 Progress surfaces
```

### Phase 0: Measure (no product change)

- **0a. Confidence spreads.** Across the trial runs' databases, what 0.70 / 0.30 accept and exclude, set against percentile cuts. Free; no LLM calls. Settles D5, and so D6.
- **0b. First-batch size.** One paired run on Talismanic: batches of 5 against 25, time to the first answer. Settles whether the first batches are 5, 10, then 25.
- **0c. Shuffle.** One paired run: shuffled against stored order, compared quote by quote. Settles whether quotes are shuffled into batches (which makes every partial histogram a fair sample).

Write the results into this doc. Cost of 0b and 0c together: well under £1.

### Phase 1: Server foundations

No visible change, except the fixes.

- **Save each batch as it finishes**, its proposals and its entries in the register of sent quotes in one transaction, with a retry when the database is locked. A stopped or failed run keeps its saved batches, and the cut is applied to them.
- **Accept** per D6.
- **Record how each decision was made**: a new column on `ProposedTag` (threshold or researcher), with a migration. Accept-all, deny-all and the catch-up's apply write "threshold"; the per-row accept and deny write "researcher".
- **Telemetry** counts only researcher exclusions as rejections (D4).
- **Read what's new**: a cursor on the proposals route ("proposals since id N"), and the counts by confidence on the status read, so the sidebar needs no extra request.
- **The Mac holds the server** while AutoCode works, with no 30-minute cap (D16; `busy.py`, `ServeReaping`).
- **Fix:** the failure pop-up's double full stop ("…out of credit.."): `activity.failed` adds a full stop after an `autocodeFailure` sentence that already ends with one.
- **Signals** is rebuilt once when the last of several concurrent runs ends (open item).

Tests: the shared register and proposals commit together; a crash between batches loses only batches still in flight; provenance written by each path; a stopped run's cut.

### Phase 2: Re-cuttable review

**Mockup owed:** the dialog over a whole run, with dispositions shown and hand decisions pinned. Owner approval before building.

- The dialog loads every proposal of the run: the histogram shows accepted, tentative and excluded; the zone lists show where each one sits now.
- Moving a line moves only threshold decisions (D2); hand decisions carry a mark and stay put.
- A re-cut route applies the lines over the whole run, skipping researcher decisions. No warning on removing tags (D3).
- True `design-autocode-threshold-review.md`: §re-entry claims overrides that do not exist.

### Phase 3: Default cut

- Every first apply ends with the default cut: accept the strong band, leave the middle tentative, exclude the weak. This generalises today's house default (`autocode_house_default.py`, which accepts only and never excludes, because an exclusion could not be undone; Phase 2 removes that reason).
- Lines or percentages per Phase 0.
- The researcher stays where they are (D9).

### Phase 4: Live landing

**Reference:** `experiments/autocode-landing/` (the lab). Its handles map to product settings; retune there, then copy the values.

- **Server:** first batches of 5 and 10 if 0b says so; shuffled quotes if 0c says so.
- **One playback store on the page**, between the data and every view: quote cards, the tag sidebar, the Codebook lens and both histograms read from it, so no view shows a tag another hasn't played yet.
- **Pacing by queue size**, with gradual speed changes: start below a per-model baseline (a running average of call times, kept app-wide; durations only, never the call log itself), speed up freely, slow gently, cap flashes at about three a second, and play the rest out over 1 to 2 s when the server finishes.
- **Landing:** accepted tags flash (`badge-accept-flash`) on the card, the sidebar row and the lens row; tentative tags appear quietly; the D8 pulse schedule.
- **Layout:** the tag row's height is reserved, so a landing tag never moves the page; filtered lists take matches live (D10), so check that WebKit keeps the reading position when content is added above it.
- **Edge cases:** a page opened mid-run shows what's already saved without flashing it; a reload works out the state again; a hidden window pauses and then catches up quickly; catch-up passes land the same way (open item).
- **Histograms:** the scale only grows, in rounded steps; squares or bars are chosen once, from the quote count, at the start.
- **Status:** the Mac line counts what the server has (it is native and cannot see the page); the CLI pop-up waits for playback (D11).

### Phase 5: Progress surfaces

**Mockup:** `docs/mockups/autocode-progress-states.html` (`279c0b0f2`), to be updated with D13's words.

- Mac sidebar lines for stopped, failed and partly failed AutoCode, in the pipeline run's words (D13; `ProjectSubtitle.swift`, `SidebarSubtitleText.swift`, `ScreenReading.swift`).
- Then remove the pop-up inside the Mac app (`isEmbedded()`); the CLI web app keeps it.

### Phase 6: Tag sidebar overview

**Mockup:** `docs/mockups/tag-sidebar-autocode-histogram.html` (`24e947017`, and the later update for "34 tags" and the researcher's own tags).

- The overview as D17, built on the existing `ConfidenceHistogram`; Review opens the existing `ThresholdReviewModal` for its codebook.
- Hidden when its codebook's eye is closed; hidden in solo mode with the rest of the summary line; absent from the HTML export (proposals are server-only there, `routes/export.py`).
- Grows live from the Phase 4 store; the split view's scale during a run per the open item.
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

Run `/usual-suspects` over this plan: it touches the database, the sidecar's lifecycle, the
telemetry and three surfaces, and a plan is cheaper to correct than a branch.

## References

- Lab: `experiments/autocode-landing/` (`279c0b0f2`): a real run's proposals and 52 logged call times (median 29.8 s; 1 in 10 at 50 s or more).
- States: `docs/mockups/autocode-progress-states.html`.
- Sidebar overview: `docs/mockups/tag-sidebar-autocode-histogram.html`.
- The dialog as built: `docs/design-autocode-threshold-review.md`.
- Engine: `docs/design-autocode.md`; catch-up passes: `bristlenose/server/gotchas.md` § AutoCode.
