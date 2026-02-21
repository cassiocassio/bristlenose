# Logging Architecture

> **Status**: Phase 1 (infrastructure) implemented; Phase 2 (tier 1 instrumentation) planned; tiers 2–3 backlogged
> **Implemented in**: v0.10.2, Feb 2026

## The problem

Bristlenose had a single logging knob: `-v` on the CLI, which toggled `logging.basicConfig` between `WARNING` and `DEBUG` on stderr. Everything went to the terminal and vanished when you scrolled past it. There was no persistent log file.

This meant:
- If an error happened in serve mode (no `-v` flag), you saw it flash by and it was gone
- If you needed to debug a past run, there was nothing to look at
- If a subtle issue (like the LLM returning a stringified JSON array instead of an actual list) happened intermittently, you'd never catch it unless you happened to be running verbose at the time

### Trigger

An `AutoCodeBatchResult` validation error in serve mode — the Anthropic SDK returned `assignments` as a JSON string instead of a parsed list. The `logger.error()` printed to the terminal, but the surrounding context (what the SDK actually returned, which model, which batch) was invisible because those were `logger.debug()` calls suppressed by the default `WARNING` level.

## Architecture

Two fully independent knobs:

| Knob | Controls | Default | Where output goes |
|------|----------|---------|-------------------|
| `-v` / `--verbose` | Terminal verbosity | `WARNING` | stderr |
| `BRISTLENOSE_LOG_LEVEL` | Log file verbosity | `INFO` | `.bristlenose/bristlenose.log` |

Changing one does not affect the other. You can have a quiet terminal with a debug-level log file, or a noisy terminal with an info-level log file, or any combination.

### Log file details

- **Location**: `<output_dir>/.bristlenose/bristlenose.log` — alongside the per-project SQLite DB
- **Rotation**: `RotatingFileHandler`, 5 MB max per file, 2 backups (`.log.1`, `.log.2`)
- **Max disk**: ~15 MB ceiling (5 MB x 3 files), then oldest is deleted
- **Compression**: None — 15 MB is negligible for a local tool
- **Format**: `2026-02-21 14:32:15 | INFO    | bristlenose.server.autocode | Job started...`
- **Encoding**: UTF-8

### Where logging is configured

| Entry point | When `setup_logging()` is called |
|-------------|----------------------------------|
| `Pipeline.run()` | After `output_dir.mkdir()`, before manifest load |
| `Pipeline.run_transcription_only()` | After `output_dir.mkdir()` |
| `Pipeline.run_analysis_only()` | After `output_dir.mkdir()` |
| `Pipeline.run_render_only()` | Before intermediate JSON load |
| `create_app()` (serve mode) | After project_dir resolution, before FastAPI init |

All paths call `setup_logging()` from `bristlenose/logging.py`. The call is idempotent — second calls clear and rebuild handlers.

### Serve mode specifics

`bristlenose serve` now accepts `-v` / `--verbose`, which controls:
1. The bristlenose log terminal handler (DEBUG vs WARNING)
2. The uvicorn log level (`info` vs `warning`)

In `--dev` mode, the verbose flag is stashed in `_BRISTLENOSE_VERBOSE` env var so uvicorn's factory reload can recover it.

## Key files

| File | Purpose |
|------|---------|
| `bristlenose/logging.py` | `setup_logging()`, `_parse_log_level()`, rotation config |
| `bristlenose/pipeline.py` | `Pipeline._configure_logging()` — deferred setup |
| `bristlenose/server/app.py` | `create_app(verbose=...)` — serve mode setup |
| `bristlenose/cli.py` | `-v` flag on `run`, `transcribe`, `analyze`, `render`, `serve` |
| `tests/test_logging.py` | 12 tests covering handlers, levels, independence, rotation |

## Existing logger coverage

27 modules use `logging.getLogger(__name__)`:

- **Pipeline**: `pipeline.py`
- **LLM**: `llm/client.py`
- **Stages**: all 12 stage files (`ingest`, `extract_audio`, `parse_subtitles`, `parse_docx`, `transcribe`, `identify_speakers`, `merge_transcript`, `pii_removal`, `topic_segmentation`, `quote_extraction`, `quote_clustering`, `thematic_grouping`)
- **Server**: `app.py`, `autocode.py`, `importer.py`, `routes/autocode.py`
- **Other**: `doctor.py`, `ollama.py`, `people.py`, `timing.py`, `render_html.py`, `render_output.py`, `utils/audio.py`, `utils/hardware.py`

## Instrumentation tiers

The logging infrastructure is in place. What's needed now is *using* it — adding `logger.info()` and `logger.debug()` calls at the right places so the log file captures useful diagnostic information.

### Tier 1 — diagnosing LLM issues (high value, immediate)

These would have helped diagnose the autocode double-serialization bug.

1. **LLM response shape logging** — log `block.input` key types in the Anthropic path, and parsed `data` key types in OpenAI/Azure/Gemini/Local paths. One DEBUG line per `analyze()` call showing whether each field is the expected type. Catches double-serialization, missing fields, unexpected nulls
2. **Token usage at INFO** — after every LLM call, log model name, input tokens, output tokens, total. Currently tracked in `LLMUsageTracker` but never logged — invisible in the log file
3. **AutoCode batch progress** — log batch number, quote count, token spend per batch. Currently only `logger.error()` on failure; success path is silent

### Tier 2 — diagnosing pipeline and data issues (medium value)

4. **Cache hit/miss decisions** — when `_is_stage_cached()` returns true/false, log which stage and why. Currently silent boolean
5. **Importer sync stats** — log per-entity counts (projects, sessions, quotes, clusters, themes) during serve-mode import. Currently only logged at the end as a single line
6. **Model name at INFO** — promote the `logger.debug("Calling Anthropic API: model=%s", ...)` lines in all five `_analyze_*` methods to INFO. Currently DEBUG-only, invisible at default log level

### Tier 3 — observability (nice to have)

7. **Concurrency queue depth** — when semaphore is created for quote extraction / topic segmentation / audio extraction, log the concurrency level and total tasks
8. **PII entity breakdown** — log how many entities of each type (person, location, email, etc.) were detected/redacted per session
9. **FFmpeg error detail** — when audio extraction fails, log the ffmpeg command and return code (currently exception-only)
10. **Keychain resolution** — log which credential store is active and which keys were found/missing during config load
11. **Manifest load/save** — when manifest is loaded, log schema version, previous run date, stage summary. When saved, log which stage changed status

## Tier 1 implementation plan

Three changes, all in existing files. ~20 lines total.

### 1a. LLM response shape logging (`bristlenose/llm/client.py`)

Add a DEBUG log line in each `_analyze_*` method, right before `response_model.model_validate()`, showing the types of the top-level fields in the parsed data. This catches double-serialization (string where list expected), missing fields, and unexpected nulls.

**Anthropic** (line ~259, inside the `for block` loop):

```python
logger.debug(
    "Anthropic tool input fields: %s",
    {k: type(v).__name__ for k, v in block.input.items()},
)
return response_model.model_validate(block.input)
```

**OpenAI / Azure / Gemini / Local** (before each `model_validate(data)` call):

```python
logger.debug(
    "LLM response fields: %s",
    {k: type(v).__name__ for k, v in data.items()} if isinstance(data, dict) else type(data).__name__,
)
return response_model.model_validate(data)
```

Five insertion points total (one per provider method). No behavior change.

**What it catches**: The autocode bug — you'd see `{'assignments': 'str'}` instead of `{'assignments': 'list'}` in the log file.

### 1b. Token usage at INFO (`bristlenose/llm/client.py`)

After each provider's token tracking block, add an INFO log with model name and token counts. Currently the tracker accumulates silently — the log file never sees individual call costs.

**Pattern** (same for all five providers, after `self.tracker.record(...)` call):

```python
logger.info(
    "LLM call: model=%s input_tokens=%d output_tokens=%d",
    self.settings.llm_model,  # or azure_deployment, local_model
    input_tokens,
    output_tokens,
)
```

Five insertion points. Uses the same token values already passed to `self.tracker.record()`.

**What it catches**: Unexpectedly large/small responses, cost tracking without running `-v`, and a timeline of when LLM calls happened in the log file.

### 1c. AutoCode batch progress (`bristlenose/server/autocode.py`)

**Job start** (line ~249, after `job.llm_model = settings.llm_model`):

```python
logger.info(
    "AutoCode job started: framework=%s quotes=%d batches=%d model=%s",
    framework_id, len(batch_items), len(batches), settings.llm_model,
)
```

**Per-batch completion** (line ~338, after `processed_count += len(batch)`):

```python
logger.info(
    "AutoCode batch done: %d/%d quotes, %d proposals",
    processed_count, job.total_quotes, len(proposals),
)
```

**Job completion** (after the `batch_results` gather loop, line ~372):

```python
logger.info(
    "AutoCode job finished: %d proposals from %d quotes (%d batch errors)",
    proposed_count, processed_count,
    sum(1 for r in batch_results if isinstance(r, BaseException)),
)
```

Three insertion points. All INFO level — visible in the log file by default.

**What it catches**: Progress visibility, batch failure rate, and a clear record of what the job did. The `Batch failed: %s` error on line 368 now has surrounding context.

### Test coverage

No new tests needed — these are log lines only, no behavior change. Existing tests continue to pass. The log lines are visible in test output when running with `-v` or when `BRISTLENOSE_LOG_LEVEL=DEBUG`.

### Risk

None. Additive-only changes (log lines). No control flow changes. No new dependencies.

## Non-goals

- **Structured logging (JSON lines)**: not needed for a local tool. Grep works fine
- **Log aggregation / shipping**: local-first tool, no remote logging
- **Per-request API logging middleware**: uvicorn already logs requests; we add domain-level logging where it matters
- **Compression**: 15 MB ceiling is fine; gzip would add complexity for negligible gain

## References

- Phase 4a in `docs/design-pipeline-resilience.md` describes a structured event log (`pipeline-events.jsonl`) for provenance tracking. That's a separate system — immutable, append-only, machine-readable. The log file here is for human debugging, not data integrity
- The resilience design's event log and the logging system serve different purposes: events are facts about data ("quote q001 was extracted by claude-sonnet-4"), logs are operational diagnostics ("LLM call took 3.2s, 1847 output tokens, response had 25 assignments")
