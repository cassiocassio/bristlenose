# AutoCode — LLM-Assisted Tag Application

`autocode.py` is the engine module. `routes/autocode.py` has 7 API endpoints. Two new ORM tables: `AutoCodeJob` (job lifecycle) and `ProposedTag` (per-quote tag proposals with confidence + rationale). Working context lives in `bristlenose/server/CLAUDE.md`.

## How it works

1. Researcher clicks "✦ AutoCode quotes" on a framework separator (e.g. Garrett)
2. `POST /api/projects/{id}/autocode/{framework_id}` → starts background job via `asyncio.create_task()`
3. Engine loads all quotes + codebook discrimination prompts, batches into groups of 25
4. Each batch → one LLM call with full taxonomy (all sub-tags with definition/apply_when/not_this)
5. LLM returns best-fit tag + confidence (0.0-1.0) + rationale per quote — no hard NO_FIT
6. Results stored as `ProposedTag` rows (status: "pending")
7. Frontend polls `/status`, then opens report modal with proposals

## API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/projects/{id}/autocode/{framework_id}` | Start job |
| GET | `/projects/{id}/autocode/{framework_id}/status` | Poll progress |
| GET | `/projects/{id}/autocode/{framework_id}/proposals` | List proposals (min_confidence filter) |
| POST | `/projects/{id}/autocode/proposals/{id}/accept` | Accept → creates QuoteTag |
| POST | `/projects/{id}/autocode/proposals/{id}/deny` | Deny → keeps for telemetry |
| POST | `/projects/{id}/autocode/{framework_id}/accept-all` | Bulk accept above threshold |
| POST | `/projects/{id}/autocode/{framework_id}/deny-all` | Bulk deny pending |

## Gotchas

- **Re-run guard**: Unique constraint on `(project_id, framework_id)` — one job per codebook per project. Denied proposals stay for telemetry, not deleted
- **Cloud-only**: Prompt weight ~14K-17K tokens per call. Ollama excluded (4K context can't fit taxonomy + quotes)
- **Background task**: First feature to call LLMs from serve mode. Uses `asyncio.create_task()` — job runs after endpoint returns. No Celery/Redis needed
- **Confidence filter**: Proposals endpoint accepts `min_confidence` query param (default 0.5). All assignments stored regardless, filtered at query time. Stretch goal: user-facing threshold slider
- **LLMClient(settings)**: Takes only settings, creates its own tracker internally. Don't pass LLMUsageTracker as second arg

## Testing

96 tests across 5 files. Live LLM eval harness (`test_autocode_discrimination.py`) has 20 golden Garrett quotes — run with `pytest -m slow` (~$0.01/run, ≥80% accuracy threshold).
