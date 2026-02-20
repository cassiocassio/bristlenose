# Session management — re-runs, filtering, and selective analysis

## Status

**Implemented (v0.10.2):** Re-import on every serve startup.
**Future:** Session enable/disable toggle, live analysis recalculation.

## Problem statement

Users add and remove interview videos between pipeline runs. A bad interview gets deleted; a new participant gets recorded. When `bristlenose run` re-runs the pipeline, the intermediate JSON files reflect the new state — but if the SQLite database still has quotes from the deleted session, the React islands show stale data.

Separately, researchers want to **temporarily exclude sessions** from analysis without deleting them. "Show me the signal cards without the three angry participants" is a valid analytical question that changes interpretation.

These are two different problems with related solutions.

## What we've built (re-import)

### The fix

The importer (`bristlenose/server/importer.py`) now **always re-imports** on every `bristlenose serve` startup. Previously, it set `project.imported_at` on first import and skipped all subsequent imports.

### How stale data is detected

Every entity touched during import gets a `last_imported_at` timestamp set to the current import time (`now`). After all upserts complete, a cleanup pass finds entities with `last_imported_at < now` (or null) — these are from a previous pipeline run and no longer exist in the intermediate JSON.

### What gets cleaned up

| Entity | Detection | Action |
|--------|-----------|--------|
| **Quotes** | `last_imported_at < now` | Delete researcher state (QuoteState, QuoteTag, QuoteEdit, DeletedBadge), join rows (ClusterQuote, ThemeQuote), then the quote itself |
| **Screen clusters** | `last_imported_at < now` and `created_by = "pipeline"` | Delete join rows, then the cluster. Researcher-created clusters are never touched |
| **Theme groups** | `last_imported_at < now` and `created_by = "pipeline"` | Delete join rows, then the theme. Researcher-created themes are never touched |
| **Sessions** | `session_id` not in current pipeline output | Delete child rows (SourceFile, TranscriptSegment, TopicBoundary, SessionSpeaker), orphaned Person rows, then the session |

### What's preserved

Researcher state on **surviving quotes** is fully preserved:

- **Starred/hidden** (QuoteState) — the star you put on a quote from session 1 survives when session 4 is removed
- **Tags** (QuoteTag) — all user-applied codebook tags stay
- **Text edits** (QuoteEdit) — corrected transcription text stays
- **Deleted badges** (DeletedBadge) — sentiment badges the researcher dismissed stay
- **Heading edits** (HeadingEdit) — renamed section/theme titles are project-scoped, not quote-scoped, so they always survive

### Test coverage

29 tests in `tests/test_serve_importer.py` cover:

- Basic import (13 tests)
- Idempotent re-import without duplicates (2 tests)
- Session removal cleans quotes and joins (2 tests)
- Researcher state survives re-import (5 tests: starred, hidden, tags, edits, badges)
- Researcher state cleaned for removed quotes (1 test)
- New session addition (2 tests)
- Stale cluster/theme removal (2 tests)
- Missing file handling (2 tests)

---

## Future: session enable/disable toggle

### The idea

A toggle per session in the Sessions tab (or a multi-select) that temporarily excludes sessions from all analysis views. The data stays in SQLite — it's just filtered out of API responses.

### Use cases

1. **Outlier exclusion**: "These three participants were all angry about the same unrelated billing issue. What does the data look like without them?"
2. **Cohort comparison**: "Show me only the enterprise users" (sessions 1, 4, 7) vs "Show me only the SMB users" (sessions 2, 3, 5, 6).
3. **Progressive analysis**: Start with all sessions, then narrow down to the most interesting subset.
4. **Bad interview quarantine**: The interview went badly but hasn't been deleted yet — hide it from analysis without re-running the pipeline.

### Design options

#### Option A: Per-session `is_disabled` flag

Add `is_disabled: bool` to the `sessions` table. API endpoints filter on `is_disabled = False` by default. A toggle in the Sessions tab flips the flag.

**Pros**: Simple, fast, persists across restarts.
**Cons**: Binary — can't do "show me sessions 1+2" vs "show me sessions 3+4" without toggling back and forth.

#### Option B: Named session sets

A new table `session_sets` with a name and a many-to-many join to sessions. The user creates sets ("Enterprise users", "SMB users", "All") and switches between them. API endpoints accept a `session_set_id` parameter.

**Pros**: Multiple views without toggling. Supports cohort comparison.
**Cons**: More complex UI. Users might not need this level of sophistication.

#### Option C: URL parameter filtering

No persistence — the current view is encoded in the URL hash or query params (`?sessions=s1,s2,s4`). The Sessions tab has checkboxes.

**Pros**: Shareable, bookmarkable, no schema change.
**Cons**: Lost on page reload unless saved to URL. Doesn't persist across serve restarts.

### Recommended approach

**Start with Option A** (simple toggle), graduate to Option B if users ask for cohort comparison.

### What changes downstream

When sessions are disabled, every API endpoint that returns quotes needs to filter them:

| Endpoint | Change |
|----------|--------|
| `GET /api/projects/{id}/quotes` | Exclude quotes where `session_id` matches a disabled session |
| `GET /api/projects/{id}/dashboard` | Recompute stats excluding disabled sessions |
| `GET /api/projects/{id}/sessions` | Show disabled sessions (greyed out) but mark them |
| `GET /api/projects/{id}/codebook` | Tag counts exclude disabled sessions |
| Analysis page | Signal cards, heatmaps, histograms all recompute |

The analysis page is the most impactful — signal concentration completely changes when you remove sessions. This is the "aha moment" that makes session filtering powerful.

### Impact on analysis

The analysis module (`bristlenose/analysis/`) computes metrics from grouped quotes. With session filtering:

- **Signal cards**: A signal that was "strong" across 5 sessions might become "moderate" across 3. Or a buried signal might surface when noisy sessions are removed.
- **Heatmap**: The sentiment-by-section matrix changes shape (fewer rows or different cell values).
- **Tag histograms**: Tag distribution shifts when sessions are excluded.

This is exactly the researcher's workflow: "I thought the main finding was frustration with onboarding, but when I exclude the three participants who had billing complaints, the real signal is confusion about the dashboard layout."

### Implementation sketch

1. Add `is_disabled` column to `sessions` table
2. Add `PATCH /api/projects/{id}/sessions/{sid}/toggle` endpoint
3. Add a helper `_active_session_ids(db, project_id)` that returns session IDs where `is_disabled = False`
4. Thread that filter through all quote-returning endpoints
5. Add toggle UI to Sessions table (checkbox or switch per row)
6. Recompute analysis on the fly (analysis is pure computation, no LLM calls — fast enough to recalculate client-side or server-side on each request)

---

## Future: delete session from UI

### The idea

A "Delete session" action in the Sessions tab that removes the session and re-runs the pipeline without it. More destructive than disable — the interview video and transcript are excluded from future runs.

### Why this is harder

Deleting a session means:

1. Removing the source file from the input directory (or marking it for exclusion)
2. Re-running the pipeline (transcription, quote extraction, clustering, theming)
3. Re-importing the new results

This is a full pipeline re-run, which takes minutes. The UI needs to show progress and handle the async nature of the operation.

### Possible approaches

1. **`.bristlenose-ignore` file**: A file in the input directory listing files to skip. The pipeline reads this during ingest and skips matching files. No file deletion needed — the original recordings stay on disk.
2. **Move to quarantine**: Move the file to a `bristlenose-output/.quarantine/` directory. Reversible.
3. **Actual deletion**: Delete the file. Irreversible.

### Recommended approach

**`.bristlenose-ignore`** — safest, reversible, works with the existing pipeline. The UI adds a line to the ignore file, then triggers a background pipeline re-run.

---

## Related: re-run pipeline from serve mode

Both "delete session" and "add new recording" require re-running the pipeline from within serve mode. Today, the pipeline runs from the CLI only. A future API endpoint could trigger a background pipeline run:

```
POST /api/projects/{id}/rerun
```

This spawns the pipeline in a background thread, streams progress events to the frontend via SSE or polling, and re-imports when done. The desktop app already has pipeline execution (via the sidecar) — the serve mode version would be similar but triggered from the UI.

---

## Files

| File | What |
|------|------|
| `bristlenose/server/importer.py` | Re-import logic, stale cleanup |
| `tests/test_serve_importer.py` | 29 tests covering all re-import scenarios |
| `bristlenose/server/models.py` | Domain schema (Quote.last_imported_at, ScreenCluster.last_imported_at, etc.) |
| `docs/design-session-management.md` | This document |
