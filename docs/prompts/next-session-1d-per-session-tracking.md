# Next session prompt: Phase 1d — Per-session tracking for expensive stages

## Context

Phase 1c is done — the pipeline reads an existing manifest on startup and skips stages 8–11 when their intermediate JSON exists. But this is all-or-nothing: if quote extraction crashes after 7 of 10 sessions, the entire stage is marked `RUNNING` and all 10 sessions are re-processed on resume.

Phase 1d adds per-session granularity. The manifest tracks which sessions completed within a stage, so only the 3 remaining sessions need LLM calls.

## What to build

As described in `docs/design-pipeline-resilience.md` section 1d.

### 1. Add `SessionRecord` to `manifest.py`

```python
class SessionRecord(BaseModel):
    status: StageStatus
    session_id: str
    completed_at: str | None = None
    provider: str | None = None       # "anthropic", "google", etc.
    model: str | None = None          # "claude-sonnet-4-20250514", etc.
```

Add `sessions: dict[str, SessionRecord] | None = None` to `StageRecord`. Only used for per-session stages (topic segmentation, quote extraction).

### 2. Add `mark_session_complete()` helper to `manifest.py`

```python
def mark_session_complete(
    manifest: PipelineManifest,
    stage: str,
    session_id: str,
    provider: str | None = None,
    model: str | None = None,
) -> None:
```

### 3. Modify `pipeline.py` stages 8 and 9

**Topic segmentation** currently calls `segment_topics(clean_transcripts, ...)` which processes all transcripts at once. For per-session tracking:

1. Before calling `segment_topics`, check the previous manifest for completed sessions
2. Filter `clean_transcripts` to only include sessions not yet completed
3. Load cached topic maps from `topic_boundaries.json` for completed sessions
4. Call `segment_topics` only for remaining sessions
5. Merge cached + fresh topic maps
6. After each session completes, call `mark_session_complete()` on the manifest
7. Write the merged results to `topic_boundaries.json`

**Quote extraction** follows the same pattern with `extract_quotes()`.

**Key subtlety**: The current stage functions process sessions concurrently (bounded by `llm_concurrency`). The per-session tracking needs to wrap around the existing concurrency model, not replace it. The simplest approach: filter the input list, let the stage function handle concurrency as before, write session records after the batch completes.

### 4. Handle partial stages

When a stage has `sessions` with some `COMPLETE` and some `PENDING`/`FAILED`:
- Load cached results for completed sessions from intermediate JSON
- Filter the JSON to only include data for completed session_ids
- Run the stage function only for remaining sessions
- Merge and write the combined results
- Mark stage as `COMPLETE` only when all sessions are done; otherwise `PARTIAL`

### 5. Stage status derivation

```python
def _derive_stage_status(manifest: PipelineManifest, stage: str) -> StageStatus:
    """Derive overall stage status from session-level records."""
    record = manifest.stages.get(stage)
    if record is None or record.sessions is None:
        return record.status if record else StageStatus.PENDING
    statuses = {s.status for s in record.sessions.values()}
    if all(s == StageStatus.COMPLETE for s in statuses):
        return StageStatus.COMPLETE
    if any(s == StageStatus.COMPLETE for s in statuses):
        return StageStatus.PARTIAL
    return StageStatus.PENDING
```

## What the user sees

```
$ bristlenose run interviews/    # first run — credit exhaustion during quote extraction
 ✓ Ingested 10 sessions                    0.1s
 ✓ Transcribed 10 sessions                 4m 30s
 ✓ Segmented 87 topic boundaries           35s
 ⚠ Extracted 42 quotes (7/10 sessions)     2m 10s
   API credit balance too low

$ bristlenose run interviews/    # resumed
 ✓ Ingested 10 sessions                    0.1s
 ✓ Transcribed 10 sessions                 4m 30s
 ✓ Segmented 87 topic boundaries           (cached)
 ✓ Extracted 78 quotes (3 new sessions)    0m 45s
 ✓ Clustered 12 screens · Grouped 8 themes 15s
 ✓ Rendered report                          0.1s
```

## Files to change

- `bristlenose/manifest.py` — `SessionRecord` model, `mark_session_complete()`, `_derive_stage_status()`
- `bristlenose/pipeline.py` — stages 8 and 9 get per-session caching logic
- `tests/test_manifest.py` — test session-level tracking
- `tests/test_pipeline_resume.py` — test per-session resume

## Key constraints

- `segment_topics()` and `extract_quotes()` don't need to change — they already accept and return per-session data
- Provider/model is per-session, not per-stage — changing provider between runs doesn't invalidate completed sessions
- Intermediate JSON (`topic_boundaries.json`, `extracted_quotes.json`) stores all sessions' results merged — on resume, filter by session_id to identify what's cached
- Stages 10+11 (clustering/theming) are cross-session — they always re-run when the quote pool changes (but are still skippable at the stage level via Phase 1c when nothing changed)

## Risk

Medium. The merge of cached + fresh results must produce the same data shape as a full run. The filtering of intermediate JSON by session_id is new code. Test thoroughly with mixed cached/fresh scenarios.

## Size

Medium-large (~120 lines). Mostly in pipeline.py. The manifest model changes are small.
