---
status: partial
last-trued: 2026-11-23
trued-against: HEAD@main on 2026-11-23 (Phase 2 of docs/design-autocode-landing-plan.md)
---

> **Truing status:** Partial — **this shipped.** The design half (§UX design,
> §Histogram, §Zones, §Backend) is an accurate as-built description of live code
> and needs no reading-down. The *build-plan* half — §Component architecture,
> §Always-visible entry point, §Implementation sequence, §Verification,
> §Files to modify — is written in the future tense for finished work and names
> two files that no longer exist. Those sections carry inline banners; read them
> as a record of how it was built, not as work outstanding. Trued 2026-09-20.

## Changelog

- _2026-11-23_ — Phase 2 of `docs/design-autocode-landing-plan.md` (decisions D1–D3,
  D26, D34, D37, D39; design `docs/mockups/autocode-review-dialog.html`): the dialog
  loads the whole run, pins a person's decision, counts Apply's outcome, lists decided
  rows with their ✗ / ✓ as an explicit override, offers Apply only once a line has
  moved, and Apply is one re-cut call. §Re-entry claimed overrides that did not exist
  (the server refused a decided proposal with 409); it now describes what is built.
  The sections below are trued to it; the sparkle left the title.
  Review fixes the same day (D41–D44): Apply decides pending proposals by the lines,
  as shipped; Close after a row decision refreshes the page's tags; the lines' read
  and Apply are bounded; an override names the status it expects.
- _2026-09-20_ — trued up: marked the doc shipped, which it had never said. A cold
  reader hit §Context describing the modal as unbuilt and a **Goal:** for something
  five months live, and would reasonably have triaged the whole doc as pending.
  Banner-marked the build-plan sections; corrected `CodebookPanel.tsx` and
  `AutoCodeToast.tsx` (both deleted) to the live call sites; corrected the
  `AutoCodeReportModal` "deprecated, kept on disk" row, which understates it — the
  component has no production caller at all but is still barrel-exported with 12
  live tests; recorded that §"Always-visible entry point" shipped with *different*
  gating than proposed; recorded the durable side-effect of Apply thresholds that
  the doc never mentioned. Anchors: `frontend/src/islands/CodebookV2.tsx:68,837`,
  `frontend/src/pages/CodebookV2Page.tsx:115-117,229-235`,
  `bristlenose/server/routes/autocode.py:566-568,648-650`,
  `frontend/src/components/index.ts:4`, commit "codebook v2 becomes the codebook
  lens: v1 deleted, the icon back, and the i18n graduated".
- _2026-04-30_ — initial draft.

# AutoCode Threshold Review Dialog — Design Document

## Context

The Plato stress test (280 philosophical quotes tagged with a 26-tag scholarly codebook) revealed a key UX problem with AutoCode: the system always proposes a tag for every quote, even when the content is irrelevant. "What is your suit, Euthyphro?" gets tagged "myth and analogy" at 0.10 confidence. Without threshold controls, researchers see weak matches and lose trust — the same problem Dovetail's auto-tagging has.

> **Same disease, different cure.** This is the AutoCode-side analogue of the noise-bucket failure mode the thematic-analysis spike found in s11 (see `experiments/thematic-spike/FINDINGS.md` *"Universal failures"* — 100% coverage = padding). In s11 the cure is a prompt-level permission to leave quotes unassigned; in AutoCode the cure is a UI-level confidence threshold. Both are honesty mechanisms — the system saying "I'm not sure" instead of forcing every quote into a bucket.

The current `AutoCodeReportModal` shows a flat triage table of all proposals above a hardcoded 0.5 confidence threshold. The researcher can accept all or deny individual rows. There's no way to see the confidence distribution, set thresholds, or distinguish strong matches from weak ones.

**Goal:** Replace the flat triage table with a confidence-aware review dialog that lets the researcher set two thresholds (accept above / exclude below), see the distribution, and review proposals in three zones.

> **Shipped — the two paragraphs above are the pre-build statement of the problem,
> kept for context.** `ThresholdReviewModal` is live and is what the Review door
> opens (`frontend/src/islands/CodebookV2.tsx:68,837`). `AutoCodeReportModal` is no
> longer the current anything: nothing in production renders it. The decision to
> keep this review a *modal* rather than fold it into the lens was ratified
> separately — `docs/design-codebook-v2.md` Q15, closed by the user 30 Aug 2026.

## UX design

### Layout (top to bottom)

```
┌──────────────────────────────────────────────────────────────┐
│  AutoCode Review — {frameworkTitle}                    [×]   │
│  180 of 280 proposals remaining (60 accepted, 40 excluded)   │
│  Drag the thresholds to control how many auto-tags are       │
│  applied as tentative or accepted.                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  CONFIDENCE HISTOGRAM (20 bins, 0.05 width)                  │
│                                                              │
│  ▪▪                                                          │
│  ▪▪      ▪▪                              ▪▪▪▪               │
│  ▪▪  ▪▪  ▪▪                          ▪▪▪▪▪▪▪▪  ▪▪           │
│  ▪▪  ▪▪  ▪▪  ▪▪          ▪▪  ▪▪  ▪▪▪▪▪▪▪▪▪▪▪▪  ▪▪  ▪▪     │
│  ├──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┤      │
│  0.0              0.25             0.5             0.75  1.0  │
│       ◄── grey ──►|◄──── amber ────►|◄──── green ────►       │
│                   ▲                  ▲                        │
│                 lower              upper                      │
│                                                              │
│  ┌────────────┐  ┌╌╌╌╌╌╌╌╌╌╌╌╌┐  ┌────────────┐            │
│  │ Exclude 39 │  ┊ Tentative 40┊  │ Accept 101 │            │
│  └────────────┘  └╌╌╌╌╌╌╌╌╌╌╌╌┘  └────────────┘            │
│                   ↑ pulsating                                │
│                     dashed border                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ▶ Accepted (101)                   — collapsed by default   │
│  ▼ Tentative (40)                   — expanded by default    │
│    ┌─────────────────────────────────────────────────┐       │
│    │ s1 — Euthyphro                                  │       │
│    │ 0:45  [p1]  "And what is piety..."  piety  0.62 │ ✓ ✕  │
│    │ 2:30  [p1]  "Remember that I..."    forms  0.55 │ ✓ ✕  │
│    │ s3 — Crito                                      │       │
│    │ 1:15  [p1]  "But suppose I ask..." elenchus 0.48│ ✓ ✕  │
│    └─────────────────────────────────────────────────┘       │
│  ▶ Excluded (39)                    — collapsed by default   │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                                  [Close]  [Apply thresholds] │
└──────────────────────────────────────────────────────────────┘
```

### Histogram

- **20 bins** of width 0.05: [0.00, 0.05), [0.05, 0.10), ..., [0.95, 1.00]
- Max height ~120px (histogram area), scaled relative to the tallest bin
- X-axis labels at 0.0, 0.2, 0.4, 0.6, 0.8, 1.0
- **Shows the whole run** — pending, accepted and excluded proposals alike, as they stood when the dialog opened (Phase 2, D1); bars stay coloured by position against the sliders, and a pinned decision is counted in its bar but not drawn differently there
- Split bins (where a threshold falls mid-bin): the bar is visually divided at the threshold point

#### Unit-square mode vs continuous bars

When the proposal count is small enough, each bar is composed of **individual squares** — one per proposal — stacked vertically. Each square is coloured with **the tag's codebook colour** (via `getTagBg(colour_set, colour_index)`), giving the researcher immediate visual feedback about which tags dominate each confidence band. This makes the histogram informative rather than just decorative.

**Threshold for switching:** The histogram area has a fixed aspect ratio of roughly 4:1 to 5:1 (width:height). Given the bin width (1/20th of the track) and the available height, compute the maximum number of squares that fit vertically: `maxStack = floor(histogramHeight / squareSize)`. If the tallest bin count exceeds `maxStack`, fall back to **continuous bars** coloured by zone (green/amber/grey) — no individual squares.

**Square sizing:** Each square is a fixed `squareSize × squareSize` cell (computed from bin width: `squareSize = binWidth` so squares fill the bin column exactly). A 1px gap between squares gives visual separation.

**Fallback continuous bars:** When the tallest bin is too tall for unit squares, bars are solid-filled and coloured by their zone: green (above upper threshold), amber (between thresholds), grey (below lower threshold). This is the safe default for large datasets (500+ proposals).

### Dual threshold slider

- Two thumb handles on a shared horizontal track, aligned to the histogram x-axis
- Step granularity: 0.05 (matches histogram bins)
- Minimum gap between handles: 0.05
- Track colouring: grey (0→lower), amber (lower→upper), green (upper→1.0)
- Each handle shows its value as a label (e.g. "0.30", "0.70")
- **Defaults:** lower = 0.30, upper = 0.70
- Arrow keys on focused handle: move by 0.05 step

### Zone counters

Three inline chips below the histogram. Update in real-time as sliders move. They count **where Apply would leave each proposal over the whole run** (Phase 2): a pinned decision where it sits; a pending proposal where the sliders put it, since Apply decides it (D41, as shipped: a quote unhidden after the last Apply brings its proposal back, N175); a threshold decision where its status puts it unless the sliders put it in a different zone from the stored lines (D26). Same words, same place. The rule is `outcomeZone` in `frontend/src/utils/recut.ts`, the client's copy of the server's `recut_target`; both read the cases in `tests/fixtures/recut-contract.json` (`tests/test_recut_contract.py`, `recut.test.ts`).

The **Tentative** counter uses the same pulsating dashed-border treatment as the `badge-proposed` variant in the quotes screen. This visual link teaches the researcher: "these are the same badges you'll see on your quotes." The Exclude and Accept counters use solid borders (grey and green respectively).

### Proposal lists

Three collapsible sections:

| Zone | Default state | Per-row actions | Ordering |
|------|--------------|-----------------|----------|
| **Accepted** (where Apply leaves it accepted) | Collapsed | Deny button (override) | Confidence desc |
| **Tentative** (where Apply leaves it pending) | **Expanded** | Accept + Deny buttons | Confidence desc |
| **Excluded** (where Apply leaves it excluded) | Collapsed | Accept button (rescue) | Confidence desc |

Each row shows: timecode (linked to transcript), speaker badge, quote text, tag badge (with rationale tooltip), **confidence score** (two decimals, tabular figures), action buttons.

**Pinned rows (Phase 2, D2).** A decision a person made (`decided_by` "researcher", here or on a quote card) or one made before who decided was recorded ("unknown") carries Lucide *Pin* (`Icon` concept `pinned`) after its confidence, muted (`.threshold-pin` in `molecules/threshold-review.css`), with the label "Your decision" (`autocode.review.yourDecision`) as its tooltip and accessible name. Pinned rows never move with the sliders.

**Decided rows are listed (Phase 2, D39).** Accepted and Excluded list proposals already decided, not only pending ones the sliders would move there, so ✗ on an accepted row excludes it and ✓ on an excluded row accepts it. On a decided row the button sends the explicit override (D34); either way the row becomes the researcher's pinned decision.

Rows are grouped by session ID with session headers, same as the current triage table.

### Footer

| Button | Behaviour |
|--------|-----------|
| **Close** | Close without API calls. No changes committed |
| **Apply thresholds** | 1. Accept-all with `min_confidence=upper`, 2. Deny-below with `max_confidence=lower`, 3. Refresh codebook, close |

The tentative zone proposals stay as `pending` — not committed by Apply. They appear on quotes as pulsating proposed badges. The researcher can re-open the dialog to review them later.

## State model

### Per-row actions call the API immediately

When the researcher clicks Accept or Deny on an individual row, the API is called right away. This means:
- Per-row decisions persist even if the dialog is closed without Apply
- The row fades out (200 ms) and comes back in the zone the decision put it in, pinned (Phase 2; it used to leave the dialog)
- A pending row sends an ordinary accept or deny. A decided row sends `{"override": true, "expected_status": <the status it was shown in>}` (D34, D44); decided differently since (on a quote card), the server refuses it with the same 409
- A 409 (`proposal_accepted` / `proposal_denied`) means the row was decided elsewhere: the dialog reads the run again and draws that row as the server holds it (D44), saying so when it went the other way from the click (N33)
- Closing after a row call that saved tells the caller (`onClose(changed)`), which raises `codebook-changed` and `bn:tags-changed` as Apply does, so quote cards and the tag sidebar drop a tag an override removed (D42)
- A failure toasts and puts the row back as it was (R5); a 404 removes it
- The histogram does NOT change on per-row actions (it's a fixed reference for the distribution shape)
- The zone counters and the subtitle's counts update

### Slider changes are purely visual

Moving sliders recomputes zone assignments client-side. No API calls until Apply. The proposals list re-sorts based on the new thresholds.

### Apply thresholds re-cuts the run

> **Since Phase 2 (23 Nov 2026) Apply is one call**, `POST …/autocode/{fw}/recut` with
> `{"lower", "upper"}` on the 0.05 grid (`recutProposals` in `utils/api.ts`). It moves
> only threshold decisions and pending proposals, and only those whose zone under the
> stored lines differs from their zone under the new ones (D26), so it is offered only
> once a line has moved from the stored lines, or while a pending proposal sits outside
> the tentative band (D41: Apply decides pending proposals by the lines, as shipped).
> A threshold decision moves only on a zone change. A researcher's or an "unknown" decision
> never moves (D2); a proposal moved out of Accepted loses its tag only when AutoCode
> made it; no warning on removing tags (D3). A run no lines were ever stored on gets a
> plain cut (only pending proposals sorted), offered while anything is pending. Since
> Phase 3 (23 Nov 2026) a first apply stores the end-of-run hybrid cut's lines with its
> outcome, and accepts at the stored accept line (rounded up to the grid), so the dialog
> opens on them with every row in its zone and Apply off (D41, D46). Since Phase 4a (23 Nov
> 2026) the run also accepts live as each batch is saved (`autocode.accept_live`, D6: the
> hybrid's line over the proposals so far, held at 0.80 until 25 have landed, never falling
> during the run, kept on the job as `live_accept_line`). Every end of a first apply settles
> (completion, a Stop, a failure, an outcome that could not be saved, an orphan the boot
> sweep finds; D27 extended): it stores a line no higher than the grid line at or below
> the lowest live acceptance, so every threshold acceptance sits at or above the stored
> line and every pending row on a quote that counts below it, and a run takes at least the
> exact cut. Live acceptance makes no tag: the settle makes the tags of every threshold
> acceptance, so a run still coding shows only on the live read (`GET …/proposals?live=true`,
> D32), and no ended run shows an acceptance without its tag. While a first apply codes or
> settles, Apply (`recut`), accept-all and deny-all are refused with 409 (D17) and the
> dialog shows `applyFailed`; a single row's accept or deny stays allowed (D2). A re-cut counts, and
> rebuilds Signals for, only rows whose status changes. The
> lines are stored, and Signals is rebuilt only when something moved (D31). The call
> fails after the per-row writes' time limit and shows `applyFailed` (D43). Tests:
> `tests/test_autocode_recut.py`, `ThresholdReviewModal.test.tsx`.
>
> The two-call description below is how it was built in April; accept-all and deny-all
> remain as routes.

"Apply thresholds" made two API calls:
1. `POST accept-all` with `{"min_confidence": upperThreshold}` — accepts all pending above upper
2. `POST deny-all` with `{"max_confidence": lowerThreshold}` — denies all pending below lower

Proposals between the thresholds remain pending (tentative).

> **It also has a durable side-effect this section never mentioned.** Both bulk
> calls persist the cutoff onto the job — `job.applied_upper_threshold`
> (`bristlenose/server/routes/autocode.py:566-568`) and
> `job.applied_lower_threshold` (`:648-650`), alongside `prompt_version`. Those
> stored values feed the catch-up re-apply, so "Apply thresholds" is not a
> one-shot triage action: it sets the boundary that later quotes are judged against
> when the framework re-codes. See `docs/design-codebook-state-model.md` §8.

## API changes

### Backend: add `max_confidence` to BulkActionRequest

**File:** `bristlenose/server/routes/autocode.py`

```python
class BulkActionRequest(BaseModel):
    group_id: int | None = None
    min_confidence: float = 0.5
    max_confidence: float | None = None  # NEW
```

In `deny_all_proposals()`: when `max_confidence` is provided, filter `ProposedTag.confidence < body.max_confidence` instead of `>= min_confidence`. This gives "deny everything below X" semantics.

> **Phase 2 added two things** (23 Nov 2026): `POST …/autocode/{fw}/recut` (§Apply
> thresholds re-cuts the run), and a body `{"override": true}` on the per-row
> `…/proposals/{id}/accept` and `/deny`, which only the dialog's buttons on a decided row
> send, with `expected_status` (required with it). Without it a decided proposal is
> still refused with 409 (`_already_reviewed`), which the quote cards rely on for a
> stale window or a double click (D34); with it, a proposal whose status is no longer
> the expected one is refused the same way (D44).

No new endpoints needed. The frontend fetches all proposals with `min_confidence=0.0` and computes histogram bins client-side. A distribution endpoint is an optimisation for later if datasets grow beyond 500+ proposals.

### Frontend API helpers

**File:** `frontend/src/utils/api.ts`

- Update `denyAllProposals(frameworkId, maxConfidence?)` to send `{"max_confidence": X}` in the body

## Component architecture

### New components

| Component | File | ~Lines | Responsibility |
|-----------|------|--------|---------------|
| `ThresholdReviewModal` | `components/ThresholdReviewModal.tsx` | ~200 | Top-level modal: fetches all proposals, manages slider state, renders sub-components, handles Apply |
| `ConfidenceHistogram` | `components/ConfidenceHistogram.tsx` | ~120 | Pure presentational: 20 bins, unit-square mode (tag-coloured) or continuous bars (zone-coloured), auto-selects based on tallest bin vs available height |
| `DualThresholdSlider` | `components/DualThresholdSlider.tsx` | ~120 | Two-handle custom slider with zone-coloured track. Emits `onLowerChange`/`onUpperChange` |
| `ProposalZoneList` | `components/ProposalZoneList.tsx` | ~100 | Collapsible list for one zone. Session headers + triage rows with zone-specific action buttons |

### Modified components

> **As-built, 20 Sep 2026 — two of these three files are gone.** The table below is
> the plan as written; the right-hand column is where each change actually landed.

| Component (as planned) | Change | Where it landed |
|-----------|--------|---|
| `CodebookPanel.tsx` | Swap `AutoCodeReportModal` for `ThresholdReviewModal`. Keep proposed count badge as re-entry point | **File deleted** in 0.29.0. The swap lives at `frontend/src/islands/CodebookV2.tsx:68,837`; re-entry is the Review door, not a count badge |
| `AutoCodeToast.tsx` | `onOpenReport` now opens `ThresholdReviewModal` | **File deleted** ("autocode: delete the unmounted toast, port the coverage nothing else had"). Progress is the activity chip stack — `addJob("autocode:" + id)`, `CodebookV2.tsx:409` |
| `AutoCodeReportModal.tsx` | Deprecated — kept on disk, no longer imported | **File deleted** 17 Oct 2026, with its barrel export, tests and 7 `autocode.report.*` locale keys. Its two parked-tooltip tests were the only witness to the tooltip on a proposal row and were ported to `ThresholdReviewModal.test.tsx` |

### CSS

**File:** `bristlenose/theme/molecules/threshold-review.css` (~100 lines)

- `.threshold-histogram` — grid container for 20 bar bins
- `.threshold-histogram-bar` — individual bar (continuous mode, zone-coloured)
- `.threshold-histogram-square` — individual unit square (tag-coloured, used when count is low enough)
- `.threshold-slider-track` — horizontal track with zone backgrounds
- `.threshold-slider-thumb` — draggable handle with value label
- `.threshold-zone-counter` — inline chip with count
- `.threshold-zone-counter--tentative` — pulsating dashed border, reuses `@keyframes bn-proposed-pulse` from `badge.css`
- `.threshold-zone-list` — collapsible section with chevron toggle
- `.threshold-confidence` — monospace confidence score in table rows

Register in `_THEME_FILES` list in `bristlenose/stages/s12_render/theme_assets.py`
(done — `:75`). The §Files to modify table had this path right; this line did not.

## Re-entry flow

> **As built since Phase 2 (23 Nov 2026).** This section used to say a reopened dialog
> showed only pending proposals and that a decided one could be overridden; the second
> was not true (the server refused it with 409) and the first was the one-way ratchet
> the landing plan removes. What is built:

The dialog is re-opened from the codebook page's Review door (see below). On re-entry:

- Fresh API fetch of the whole run and of the job's stored lines, together; nothing is drawn until both answer, and a status read that fails or passes its time limit (`STATUS_READ_TIMEOUT_MS`) shows `loadFailed` with Apply off (D43)
- The histogram, counters and zone lists cover every proposal; decided rows are listed in their zones, a person's decisions pinned
- Subtitle keeps its shipped words: "N of M proposals remaining (X accepted, Y excluded)"
- The sliders start at the stored lines (snapped), or the defaults when none were stored; Apply is off until it would change something (a line moved, or a pending proposal the lines decide)
- With nothing pending the whole run still shows, so a finished run can be re-cut and any decision overridden per row

### Always-visible entry point

> **Shipped, with different gating than proposed (as-built 20 Sep 2026).** The
> affordance is a **Review door** on the codebook tile, gated at
> `frontend/src/pages/CodebookV2Page.tsx:115-117` on
> `!readOnly && !b.floor && b.id !== "sentiment" && b.installed && tagCount > 0` —
> note it keys on the codebook being *installed and non-empty*, not on
> `proposedCount > 0` **nor** on `acStatus === "completed"`, so neither branch
> proposed below is what decides it. The treatment is a `bn-btn-secondary` labelled
> `codebook.reviewProposals` beside a reach sentence (`:229-235`), not a count badge
> or a `✓ done` badge. `CodebookPanel.tsx:906` is a dead anchor — the file is gone —
> and the CSS landed as `.pg-review-row` / `.pg-review-meta` in the v2 lens
> stylesheet, not in `codebook-panel.css`. The section below is the original
> proposal, kept because its *reasoning* about re-entry is why the door exists.

The proposed count badge currently renders only when `proposedCount > 0` (`CodebookPanel.tsx:906`). This means once the researcher accepts/denies all proposals — or bulk-applies thresholds — the entry point vanishes. But revisiting threshold boundaries is natural: the researcher forms an idea from the histogram and the dense list, then spends time with the actual quotes, then wants to come back and adjust.

**Design:** When autocode has been run for a framework (job status is `completed`), always show a re-entry affordance on the ✦ AutoCode button, even when pending count is zero:

- **Pending > 0:** Show the current count badge (e.g. `42`), clicking opens the review modal — unchanged
- **Pending = 0, but autocode was run:** Show a "Review" text link or a `✓ done` badge in the same position. Clicking opens the modal in its zero-pending state: empty histogram, "All proposals reviewed" subtitle, but the three zone lists still show the final dispositions (accepted/denied breakdown). The researcher can override individual decisions (accept a previously denied proposal, deny a previously accepted one) without re-running the job
- **Autocode never run:** No badge, no link — unchanged

This requires the frontend to know whether autocode has been run for a framework. The `proposedCount` fetch already implies this (it comes from a completed job). An alternative: check `acStatus === "completed"` which is already tracked per-framework in `CodebookPanel` state.

**Files to modify:**
- `frontend/src/islands/CodebookPanel.tsx` — conditional rendering at line 906: replace `proposedCount > 0` with `acStatus === "completed"`, show count when > 0, show "Review" when = 0
- `bristlenose/theme/organisms/codebook-panel.css` — style for the zero-pending "Review" affordance (muted, non-pulsating)
- `frontend/src/components/ThresholdReviewModal.tsx` — the zero-pending path already works per the spec above; no changes needed

## Edge cases

| Case | Behaviour |
|------|-----------|
| All high confidence | All bars green, tentative+excluded zones empty. Apply accepts all |
| All low confidence | All bars grey, accepted+tentative zones empty. Researcher can lower upper threshold or close |
| Very few proposals (<10) | Histogram is sparse but readable. Still useful for showing confidence range |
| Zero pending (re-entry after full review) | The whole run shows, decided rows in their zones; Apply off until a line moves (Phase 2) |
| Network error during Apply | Individual per-row overrides already committed. Bulk calls are idempotent — retry is safe. Show error, stay open |
| Lower = upper (single threshold) | Tentative zone collapses to one 0.05 bin. Valid configuration |

## Open questions

1. **Framework-specific slider defaults?** Garrett (broad categories) might warrant 0.50/0.70; Norman (specific principles) 0.55/0.75; Plato (26 scholarly tags) 0.60/0.80. Start with universal defaults, consider persisting last-used thresholds per framework later.

2. **Should the histogram animate on slider drag?** Bar recolouring on every 0.05 step creates visual feedback but might feel janky with many bins. Recommendation: CSS transitions on bar colour (0.1s ease) — cheap and smooth.

3. **Should excluded proposals show rationale?** The LLM's rationale for a 0.10 confidence match is often "this quote has no philosophical content" — which is useful feedback that the system is working correctly. Keep the rationale tooltip on all rows regardless of zone.

## Implementation sequence

> **Done — this section and the two after it (§Verification, §Files to modify) are
> future-tense instructions for completed work.** Every "Create" row exists on disk.
> Kept as the build record; not a to-do list. Two rows have moved since: the two
> deleted files noted at §Component architecture, and the CSS path at §CSS.

1. **Backend** (~30 lines): Add `max_confidence` to `BulkActionRequest`, update `deny_all_proposals` filter logic
2. **Frontend types + API** (~15 lines): Update `denyAllProposals` helper signature
3. **CSS** (~100 lines): `molecules/threshold-review.css`
4. **Components** (~500 lines total): `ConfidenceHistogram`, `DualThresholdSlider`, `ProposalZoneList`, `ThresholdReviewModal`
5. **Integration** (~20 lines): Swap modal in `CodebookPanel.tsx`
6. **Tests**: Backend (deny-below), component tests (Vitest + RTL)

## Verification

1. `pytest tests/test_serve_autocode_api.py` — new deny-below tests pass
2. `npm run test` in `frontend/` — new component tests pass
3. Manual: start serve mode, import framework, run autocode, open review dialog, drag sliders, verify histogram recolours and counts update, apply thresholds, verify proposals accepted/denied correctly, re-open dialog and see remaining proposals

## Files to modify

| File | Change |
|------|--------|
| `bristlenose/server/routes/autocode.py` | Add `max_confidence` to `BulkActionRequest`, update `deny_all_proposals` |
| `frontend/src/utils/api.ts` | Update `denyAllProposals` signature |
| `frontend/src/utils/types.ts` | No changes needed (existing types sufficient) |
| `frontend/src/components/ThresholdReviewModal.tsx` | **Create** |
| `frontend/src/components/ConfidenceHistogram.tsx` | **Create** |
| `frontend/src/components/DualThresholdSlider.tsx` | **Create** |
| `frontend/src/components/ProposalZoneList.tsx` | **Create** |
| `frontend/src/islands/CodebookPanel.tsx` | Swap modal, keep re-entry badge |
| `bristlenose/theme/molecules/threshold-review.css` | **Create** |
| `bristlenose/stages/s12_render/theme_assets.py` | Register CSS in `_THEME_FILES` |
| `tests/test_serve_autocode_api.py` | Add deny-below tests |
