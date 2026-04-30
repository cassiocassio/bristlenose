# AutoCode Threshold Review Dialog — Design Document

## Context

The Plato stress test (280 philosophical quotes tagged with a 26-tag scholarly codebook) revealed a key UX problem with AutoCode: the system always proposes a tag for every quote, even when the content is irrelevant. "What is your suit, Euthyphro?" gets tagged "myth and analogy" at 0.10 confidence. Without threshold controls, researchers see weak matches and lose trust — the same problem Dovetail's auto-tagging has.

> **Same disease, different cure.** This is the AutoCode-side analogue of the noise-bucket failure mode the thematic-analysis spike found in s11 (see `experiments/thematic-spike/FINDINGS.md` *"Universal failures"* — 100% coverage = padding). In s11 the cure is a prompt-level permission to leave quotes unassigned; in AutoCode the cure is a UI-level confidence threshold. Both are honesty mechanisms — the system saying "I'm not sure" instead of forcing every quote into a bucket.

The current `AutoCodeReportModal` shows a flat triage table of all proposals above a hardcoded 0.5 confidence threshold. The researcher can accept all or deny individual rows. There's no way to see the confidence distribution, set thresholds, or distinguish strong matches from weak ones.

**Goal:** Replace the flat triage table with a confidence-aware review dialog that lets the researcher set two thresholds (accept above / exclude below), see the distribution, and review proposals in three zones.

## UX design

### Layout (top to bottom)

```
┌──────────────────────────────────────────────────────────────┐
│  ✦ AutoCode Review — {frameworkTitle}                  [×]   │
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
- **Shows only pending proposals** — already-accepted/denied proposals are excluded from the histogram
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

Three inline chips below the histogram. Update in real-time as sliders move. Counts only pending proposals.

The **Tentative** counter uses the same pulsating dashed-border treatment as the `badge-proposed` variant in the quotes screen. This visual link teaches the researcher: "these are the same badges you'll see on your quotes." The Exclude and Accept counters use solid borders (grey and green respectively).

### Proposal lists

Three collapsible sections:

| Zone | Default state | Per-row actions | Ordering |
|------|--------------|-----------------|----------|
| **Accepted** (above upper) | Collapsed | Deny button (override) | Confidence desc |
| **Tentative** (between thresholds) | **Expanded** | Accept + Deny buttons | Confidence desc |
| **Excluded** (below lower) | Collapsed | Accept button (rescue) | Confidence desc |

Each row shows: timecode (linked to transcript), speaker badge, quote text, tag badge (with rationale tooltip), **confidence score** (two decimals, monospace), action buttons.

Rows are grouped by session ID with session headers, same as the current triage table.

### Footer

| Button | Behaviour |
|--------|-----------|
| **Close** | Close without API calls. No changes committed |
| **Apply thresholds** | 1. Accept-all with `min_confidence=upper`, 2. Deny-below with `max_confidence=lower`, 3. Refresh codebook, close |

The tentative zone proposals stay as `pending` — not committed by Apply. They appear on quotes as pulsating proposed badges. The researcher can re-open the dialog to review them later.

## State model

### Per-row actions call the API immediately

When the researcher clicks Accept or Deny on an individual row, the API is called right away (matching current `AutoCodeReportModal` behaviour). This means:
- Per-row decisions persist even if the dialog is closed without Apply
- The local proposals array is updated optimistically (fade-out animation, then remove from list)
- The histogram does NOT change on per-row actions (it's a fixed reference for the distribution shape)
- Only the zone counters update

### Slider changes are purely visual

Moving sliders recomputes zone assignments client-side. No API calls until Apply. The proposals list re-sorts based on the new thresholds.

### Apply thresholds commits bulk actions

"Apply thresholds" makes two API calls:
1. `POST accept-all` with `{"min_confidence": upperThreshold}` — accepts all pending above upper
2. `POST deny-all` with `{"max_confidence": lowerThreshold}` — denies all pending below lower

Proposals between the thresholds remain pending (tentative).

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

| Component | Change |
|-----------|--------|
| `CodebookPanel.tsx` | Swap `AutoCodeReportModal` for `ThresholdReviewModal`. Keep proposed count badge as re-entry point |
| `AutoCodeToast.tsx` | `onOpenReport` now opens `ThresholdReviewModal` |
| `AutoCodeReportModal.tsx` | Deprecated — kept on disk, no longer imported |

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

Register in `_THEME_FILES` list in `render/theme_assets.py`.

## Re-entry flow

The dialog can be re-opened any time from the proposed count badge on the ✦ AutoCode button in the codebook panel. On re-entry:

- Fresh API fetch: proposals with updated statuses (previous accept/deny reflected)
- Histogram shows only remaining `pending` proposals
- Subtitle shows "N of M proposals remaining (X accepted, Y excluded)"
- Slider thresholds reset to defaults (not persisted)
- If zero pending: disabled state, "All proposals reviewed"

### Always-visible entry point

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
| Zero pending (re-entry after full review) | Empty histogram, all zones empty, Apply disabled |
| Network error during Apply | Individual per-row overrides already committed. Bulk calls are idempotent — retry is safe. Show error, stay open |
| Lower = upper (single threshold) | Tentative zone collapses to one 0.05 bin. Valid configuration |

## Open questions

1. **Framework-specific slider defaults?** Garrett (broad categories) might warrant 0.50/0.70; Norman (specific principles) 0.55/0.75; Plato (26 scholarly tags) 0.60/0.80. Start with universal defaults, consider persisting last-used thresholds per framework later.

2. **Should the histogram animate on slider drag?** Bar recolouring on every 0.05 step creates visual feedback but might feel janky with many bins. Recommendation: CSS transitions on bar colour (0.1s ease) — cheap and smooth.

3. **Should excluded proposals show rationale?** The LLM's rationale for a 0.10 confidence match is often "this quote has no philosophical content" — which is useful feedback that the system is working correctly. Keep the rationale tooltip on all rows regardless of zone.

## Implementation sequence

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
