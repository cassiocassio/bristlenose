---
status: partial
last-trued: 2026-09-20
trued-against: HEAD@main on 2026-09-20 (835cde98)
---

> **Truing status:** Partial — the architecture is current (trued 2026-09-20);
> §"How it works" steps 1 and 7 named a control and a modal that 0.29.0 deleted
> and have been rewritten, and three counts were wrong. §"Gotchas" gained the
> retry-path qualification. Deeper runtime behaviour lives in
> `bristlenose/server/CLAUDE.md`, not here — see the ownership note below.

## Changelog

- _2026-09-20_ — the rationale hover tooltip on proposed badges is **parked**
  behind `featureFlags.proposalRationaleTooltip` (see § Parked). The
  `rationale` field is unchanged on the wire.
- _2026-09-20_ — trued up: corrected endpoint count 7 → 8 (the cancel route was
  never listed) and test count 96 → 148; rewrote the entry point (install *is*
  apply, not a separator button) and the review step (`ThresholdReviewModal`
  behind a Review door, not an auto-opened report modal); qualified the re-run
  guard and the "denied proposals are kept" claim, both false on the retry path;
  promoted the threshold slider from "stretch goal" to shipped. Anchors:
  `bristlenose/server/routes/autocode.py:330`, `:264-271`,
  `frontend/src/islands/CodebookV2.tsx:403-404`,
  `frontend/src/pages/CodebookV2Page.tsx:231`, commit "codebook v2 becomes the
  codebook lens: v1 deleted, the icon back, and the i18n graduated".
- _2026-04-16_ — initial draft (commit "refactor: offload CLAUDE.md reference
  material to dedicated docs").

# AutoCode — LLM-Assisted Tag Application

`autocode.py` is the engine module. `routes/autocode.py` has 8 API endpoints. Two
ORM tables: `AutoCodeJob` (job lifecycle) and `ProposedTag` (per-quote tag
proposals with confidence + rationale).

> **Ownership.** This doc is the orientation layer: the workflow, the endpoint
> table and the standing gotchas. The *runtime* half — `failure_kind`, the
> persisted `applied_lower_threshold` / `applied_upper_threshold` /
> `prompt_version`, `reconcile_orphaned_jobs`, the catch-up delta
> (`reapply_to_new_quotes` / `reapply_active_frameworks`), the strong-ref
> `_AUTOCODE_TASKS` set, and the write-only non-fatal per-batch progress rule —
> lives in `bristlenose/server/CLAUDE.md`. That file points here for the workflow
> and endpoints; this one points there for runtime. Don't mirror either half into
> the other: the 2026-09-20 pass found the endpoint count wrong in both places at
> once, which is what a duplicated number does.

## How it works

1. Researcher installs a codebook from the library. **Install *is* apply** — there
   is no separate "AutoCode" button:
   `importCodebookTemplate(id).then(() => startAutoCode(id))`
   (`frontend/src/islands/CodebookV2.tsx:403-404`). The framework separator that
   used to carry the control died with the v1 lens.
2. `POST /api/projects/{id}/autocode/{framework_id}` → starts background job via
   `asyncio.create_task()`
3. Engine loads all quotes + codebook discrimination prompts, batches into groups
   of 25 (`BATCH_SIZE = 25`, `autocode.py:38`)
4. Each batch → one LLM call with full taxonomy (all sub-tags with
   definition/apply_when/not_this)
5. LLM returns best-fit tag + confidence (0.0-1.0) + rationale per quote — no hard
   NO_FIT (`llm/prompts/autocode.md`: "Always return a tag name")
6. Results stored as `ProposedTag` rows (status: "pending")
7. Progress surfaces as an activity chip (`addJob("autocode:" + id)`,
   `CodebookV2.tsx:409`). Review is **pulled, not pushed**: a Review door on the
   codebook tile (`frontend/src/pages/CodebookV2Page.tsx:231`) opens
   `ThresholdReviewModal`. Nothing auto-opens on poll.

## API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/projects/{id}/autocode/{framework_id}` | Start job |
| GET | `/projects/{id}/autocode/{framework_id}/status` | Poll progress |
| POST | `/projects/{id}/autocode/{framework_id}/cancel` | Cancel a running job |
| GET | `/projects/{id}/autocode/{framework_id}/proposals` | List proposals (min_confidence filter) |
| POST | `/projects/{id}/autocode/proposals/{id}/accept` | Accept → creates QuoteTag |
| POST | `/projects/{id}/autocode/proposals/{id}/deny` | Deny → keeps for telemetry |
| POST | `/projects/{id}/autocode/{framework_id}/accept-all` | Bulk accept above threshold |
| POST | `/projects/{id}/autocode/{framework_id}/deny-all` | Bulk deny pending |

## Parked

- **Rationale hover tooltip — parked behind a feature flag, 20 Sep 2026.**
  Hovering a proposed badge floated in the LLM's rationale from below the
  badge (`.has-tooltip .tooltip`, `theme/molecules/autocode-report.css`), on
  the quote card (`Badge.tsx`, proposed variant), in `ProposalZoneList.tsx`
  and in the `AutoCodeReportModal.tsx` table. Withheld via
  `featureFlags.proposalRationaleTooltip` in
  `frontend/src/utils/featureFlags.ts`; the tests force the flag on to keep
  the behaviour specified and assert the shipped state separately. Two
  things have to be fixed before it flips, and only one is presentation:
  (1) the tooltip lands over the row below — the `+` add-tag control and the
  next card — and the slide-in motion reads as interruption; (2) the
  rationale text is the model's raw justification and frequently restates
  the tag ("this is a task-framing statement…") instead of saying what in
  the quote earned it. (2) is a prompt change in
  `bristlenose/llm/prompts/`, not a CSS one. Tracked in the 100-day
  inventory under § 3 Embarrassing / Should.

## Gotchas

- **Re-run guard**: Unique constraint on `(project_id, framework_id)` — one job per
  codebook per project. **Only pending/running (409 `ALREADY_RUNNING`) and
  completed (409 `ALREADY_APPLIED`) block.** A `cancelled` or `failed` job is
  deleted and re-run (`routes/autocode.py:264-271`).
- **Denied proposals are kept for telemetry — except on the retry path.** Deleting
  a dead job deletes *every* `ProposedTag` for it, denied rows included
  (`routes/autocode.py:265-267`). Any telemetry analysis must treat a re-run
  framework as having lost its prior decisions.
- **Cloud-only**: Prompt weight ~14K-17K tokens per call. Ollama excluded (4K
  context can't fit taxonomy + quotes) — 503 `PROVIDER_LOCAL`.
- **Background task**: First feature to call LLMs from serve mode. Uses
  `asyncio.create_task()` — job runs after endpoint returns. No Celery/Redis needed
- **Confidence filter**: Proposals endpoint accepts `min_confidence` query param
  (default 0.5). All assignments stored regardless, filtered at query time. The
  user-facing threshold control **shipped** — `ThresholdReviewModal.tsx` +
  `DualThresholdSlider.tsx` + `ConfidenceHistogram.tsx`; see
  `docs/design-autocode-threshold-review.md`.
- **LLMClient(settings)**: Takes only settings, creates its own tracker internally.
  Don't pass LLMUsageTracker as second arg

## Testing

148 tests across 5 files (`test_autocode_discrimination.py` 15,
`test_autocode_engine.py` 43, `test_autocode_models.py` 20,
`test_autocode_taxonomy.py` 24, `test_serve_autocode_api.py` 46). Live LLM eval
harness (`test_autocode_discrimination.py`) has 20 golden Garrett quotes — run with
`pytest -m slow` (~$0.01/run, ≥80% accuracy threshold).

## Related

- `docs/design-autocode-threshold-review.md` — the review modal this feeds
- `docs/design-codebook-state-model.md` — enable/disable semantics and the
  catch-up delta an enable fires
- `docs/design-dynamic-codebook-builder.md` — `TagPrompt` / `TagPromptDecision`,
  the researcher-side analogue of the framework taxonomy this engine consumes
