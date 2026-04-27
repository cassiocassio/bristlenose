---
status: mixed
last-trued: 2026-04-27
trued-against: HEAD@cost-and-time-forecasts (efc051a) on 2026-04-27
---

# Phase 1 — LLM cost forecast (implementation plan)

> **Trued 2026-04-27 against `efc051a`.** Slice A (schema + writer + frontmatter) shipped. Slices B (hot-path wiring) and C (forecast replacement) remain planned. Provider-method line refs in §EDIT files item 9 refreshed against current `client.py`. Branch name corrected.

**Status:** Slice A shipped (2026-04-27, `efc051a`); Slices B + C planned.
**Parent design:** [design-llm-call-telemetry.md](design-llm-call-telemetry.md) — full design covering cost + time + UX + shoal across five phases. This doc is the file-by-file implementation plan for Phase 1 only.
**Scope:** narrow. Replace the hardcoded `_TOKENS_PER_SESSION` constant with a self-correcting cost forecast backed by per-call data capture. Time forecast is Phase 2.
**Branch:** `cost-and-time-forecasts`.

## Context

The pre-run cost forecast in [bristlenose/llm/pricing.py:51](../bristlenose/llm/pricing.py:51) is a single hardcoded constant `_TOKENS_PER_SESSION = (17_000, 10_000)`, set 12 Feb 2026 from a handful of FOSSDA-shaped runs and never recalibrated. It silently misleads any user whose workload deviates — different transcript lengths, models, prompts (after maintainer rewrites), languages. The constant has been wrong for two months and nobody noticed because it looked authoritative.

Phase 1 ships the data-capture instrumentation and replaces the constant with a self-correcting forecast. The MAAS lesson recorded in the parent design is the *why now*: retrospective instrumentation is never justifiable in any project big enough to need it. The window for getting the data layer right is short.

**Done criteria**: hardcoded constant gone; out-of-the-box forecast no worse than today; measurably better after ~5 runs.

## File-by-file plan

Implementation order is dependency-driven: data + helpers, then plumbing, then hot-path callers, then tests.

### NEW files

1. **`bristlenose/llm/telemetry.py`**
   - Pydantic `LLMCallEvent` model (OTel-aligned field names via `Field(alias=...)`).
   - `record_call(...)` writer using `events.py:266-276` primitives (`O_APPEND|O_NOFOLLOW|0o600`, single `os.write()` per row). **No per-call fsync** — statistical not forensic; fsync at run terminus only.
   - Module-level `ContextVar`s: `_run_id`, `_run_dir`, `_stage_id`, `_session_id`.
   - `@contextmanager` helpers `stage(name)` and `session(pid)`.
   - `set_run_context(run_id, run_dir) -> tokens` / `reset_run_context(tokens)` — token-pair helpers used by `run_lifecycle.py` (Slice B) for clean set/reset around the lifecycle's existing try/finally. Avoids leaking unbalanced ContextVar state.
   - `trim_to_cap(path, cap)` — atomic-rewrite trim used at run terminus. `trim_run_terminus(run_dir=None)` is a convenience wrapper that picks up the contextvar.
   - `iter_rows(run_dir)` — read-side helper for the forecast (Slice C) and tests; tolerates missing file and malformed rows.
   - 1000-row retention trim (configurable via `BRISTLENOSE_LLM_CALLS_RETAIN`).
   - `BRISTLENOSE_LLM_TELEMETRY=0` env-var kill switch.
   - **No-op contract:** `record_call` silently returns when telemetry is disabled, when no run is active (`_run_id` or `_run_dir` is `None`), or when `_stage_id` is `None`. Guarantees that telemetry never raises into the hot path even if Slice B integration regresses.

2. **`bristlenose/llm/cohort_normalise.py`** — `normalise_model(provider, response_model_string) -> tuple[family, major]`. One small per-provider function, table-driven, pure. No SDK imports.

3. **`bristlenose/llm/cohort-baselines.json`** — shipped table for default cloud cohorts. **Slice A ships empty** (`{"cohorts": []}`); the maintainer dogfoods FOSSDA between Slices B and C and derives medians by hand from the resulting JSONL rows. This sequencing is cleaner than parsing pre-A DEBUG-log lines. Final populated form covers Sonnet 4, GPT-4o, Gemini 2.5 Pro × cost-relevant stages × all prompts:
   ```json
   {
     "schema_version": 1,
     "generated_at": "<ISO timestamp>",
     "source": "FOSSDA n=N runs",
     "cohorts": [
       {
         "stage_id": "s09_quote_extraction",
         "prompt_id": "quote-extraction",
         "prompt_version": "0.1.0",
         "model_family": "claude-sonnet",
         "model_major": "4",
         "median_input_tokens": 14203,
         "median_output_tokens": 8910,
         "sample_count": 12
       }
     ]
   }
   ```
   Loaded once at module import (Slice C). Lookup is linear scan (≤ ~50 rows even at full coverage).

4. **`tests/test_llm_telemetry.py`** — schema round-trip with OTel aliases; file mode `0o600` and `O_NOFOLLOW`; retry-summing in `_analyze_local`; contextvar isolation across `asyncio.gather`; retention trim; missing-usage handling; kill-switch env var.

5. **`tests/test_cohort_normalise.py`** — table-driven: Anthropic, OpenAI, Azure (passthrough), Gemini, Ollama. Unknown providers raise.

6. **`tests/test_prompt_frontmatter.py`** — every `bristlenose/llm/prompts/*.md` parses to a `PromptTemplate` with non-empty `id` and `version`; `id` matches filename stem; `sha` stable across two calls.

### EDIT files

7. **`bristlenose/llm/prompts/*.md`** (8 files) — add YAML frontmatter `---\nid: <stem>\nversion: 0.1.0\n---\n` to each: `autocode.md`, `quote-clustering.md`, `quote-extraction.md`, `signal-elaboration.md`, `speaker-identification.md`, `speaker-splitting.md`, `thematic-grouping.md`, `topic-segmentation.md`. Initial version `0.1.0` everywhere; bump deliberately on future edits.

8. **`bristlenose/llm/prompts/__init__.py`** — extend the loader (lines 22–53) to parse frontmatter. Add `PromptTemplate(id, version, sha, system, user, path)` dataclass. New `get_prompt_template(name) -> PromptTemplate`. Keep `get_prompt(name) -> PromptPair` shim around the new loader for backward compatibility (~9 external call sites).

9. **`bristlenose/llm/client.py`** — `LLMClient.analyze()` (line 162) accepts new optional `prompt_template: PromptTemplate | None = None` argument. Each provider method (`_analyze_anthropic` line 220, `_analyze_openai` line 290, `_analyze_azure` line 359, `_analyze_google` line 432, `_analyze_local` line 502) calls `telemetry.record_call(...)` exactly once on terminal outcome, alongside the existing `tracker.record(...)`. Line refs verified at HEAD `efc051a`; re-confirm before applying Slice B edits.

   **`_analyze_local` retry summing**: accumulators outside the `for attempt` loop sum tokens + elapsed across attempts; one terminal `tracker.record` and one terminal `record_call` with `retry_count = attempts_used - 1`. Don't double-count.

10. **`bristlenose/run_lifecycle.py`** — at line 364 (after `new_run_id()`), set `_run_id` and `_run_dir` contextvars; reset in the `finally` clause that wraps the lifecycle (currently lines 394–452). Run-terminus retention trim runs in the same finally block before `_remove_pid_file`.

11. **`bristlenose/pipeline.py`** — wrap each LLM-issuing stage body with `with telemetry.stage("s10_quote_extraction"):` (analogous per stage: `s05b_identify_speakers`, `s08_topic_segmentation`, `s09_quote_extraction`, `s10_quote_clustering`, `s11_thematic_grouping`). Per-participant inner tasks add `with telemetry.session(participant_id):`. **Note (Slice B reality):** Stage 5b runs *before* participant codes are assigned, so its inner-task wrap binds `session_id` (e.g. `s1`) instead of `participant_id` (e.g. `p1`). Stages 8/9 bind `transcript.participant_id` as planned. Stages 10/11 are single cross-session calls — stage wrap only, no session binding. Update the two `estimate_pipeline_cost(...)` call sites at lines 652 and 1531 (imports at 650 and 1529) to pass `run_dir=self.output_dir / ".bristlenose"`.

12. **5 stage modules** (`bristlenose/stages/s05b_identify_speakers.py`, `s08_topic_segmentation.py`, `s09_quote_extraction.py`, `s10_quote_clustering.py`, `s11_thematic_grouping.py`) — switch `get_prompt(name)` calls to `get_prompt_template(name)` and pass into `client.analyze(..., prompt_template=tmpl)`.

13. **`bristlenose/llm/pricing.py`** — replace `_TOKENS_PER_SESSION` (line 51) and `estimate_pipeline_cost()` (lines 54–62). New body streams the run's JSONL via `_scan_local_jsonl(run_dir, family, major)` → median per cohort `(stage, prompt_id, version, family, major)` → sum across stages × n_sessions if local cohort N≥3; else fall back to `cohort-baselines.json` lookup; else return `None`. Keep `_LEGACY_TOKENS_PER_SESSION = (17_000, 10_000)` as a private kill-switch constant gated by `BRISTLENOSE_LLM_FORECAST=legacy`. Remove after one release.

14. **`tests/test_llm_usage.py`** lines 91–120 — replace `_TOKENS_PER_SESSION` assertions with: forecast returns shipped-baseline number when no JSONL exists; returns local-median number when ≥3 JSONL rows exist; returns `None` when neither baseline nor local rows match. Mock `run_dir` via `tmp_path`.

15. **`tests/test_llm_truncation.py`** — assert that on truncation the JSONL row has `outcome="truncated"` and reflects partial response tokens.

16. **`CLAUDE.md`** — add gotcha line: *"`<output_dir>/.bristlenose/llm-calls.jsonl` is a re-identification key (sibling to `pii_summary.txt`); never include in any export, support bundle, or shareable archive."*

## `LLMCallEvent` schema

```python
class LLMCallEvent(BaseModel):
    schema_version: int = 1
    ts: str                                              # ISO8601 UTC, required
    run_id: str                                          # required, from contextvar
    session_id: str | None = None                        # nullable for run-level calls
    stage: str                                           # required, contextvar
    gen_ai_system: str = Field(alias="gen_ai.system")    # provider, required
    gen_ai_operation_name: str = Field(default="chat", alias="gen_ai.operation.name")
    gen_ai_request_model: str = Field(alias="gen_ai.request.model")     # required
    gen_ai_response_model: str | None = Field(default=None, alias="gen_ai.response.model")
    model_family: str                                    # from cohort_normalise
    model_major: str                                     # from cohort_normalise
    prompt_id: str | None = None
    prompt_version: str | None = None
    prompt_path: str | None = None
    prompt_sha: str | None = None
    input_chars: int                                     # len(system) + len(user)
    input_tokens: int | None = Field(default=None, alias="gen_ai.usage.input_tokens")
    output_tokens: int | None = Field(default=None, alias="gen_ai.usage.output_tokens")
    cache_read_input_tokens: int | None = Field(default=None, alias="gen_ai.usage.cache_read_input_tokens")
    cache_creation_input_tokens: int | None = Field(default=None, alias="gen_ai.usage.cache_creation_input_tokens")
    elapsed_ms: int                                      # summed across retries
    retry_count: int = 0
    finish_reason: str | None = None
    outcome: Literal["ok", "truncated", "error", "cancelled"]
    usage_source: Literal["reported", "missing"] = "reported"
    price_table_version: str                             # from PRICE_TABLE_VERSION
    cost_usd_actual_estimate: float | None = None
    cost_usd_predicted: float | None = None
    # hardware_signature, estimated_*, estimate_source DEFERRED to Phase 2
    model_config = ConfigDict(populate_by_name=True)
```

## Slice strategy

Three independently mergeable slices. Each leaves `main` shippable.

- **Slice A — Schema + writer** (steps 1–6, 16, partial tests). Lands frontmatter, prompt-loader extension, `cohort_normalise`, `telemetry.py`, **empty** `cohort-baselines.json`, CLAUDE.md gotcha, schema/normalise/frontmatter tests. `record_call` is unused in production — exercised by tests only. Zero behaviour change.
- **Slice B — Wire telemetry into the hot path** (steps 9–12). `client.py`, stage modules, contextvars set in `run_lifecycle.py` and `pipeline.py`. After this lands, every real run produces JSONL rows. Forecast still uses the old constant.
- **Between B and C** — maintainer runs FOSSDA once on this branch, JSONL accumulates real rows, derive `cohort-baselines.json` medians from those rows (hand or quick script), commit populated JSON.
- **Slice C — Replace the forecast** (step 13 + remaining tests). Delete `_TOKENS_PER_SESSION`, swap `estimate_pipeline_cost` body. The user-visible change. Isolates the rollback decision.

## Decisions taken (resolved during plan review)

- **Initial baselines**: Slice A ships `{"cohorts": []}`. Real medians derived between Slices B and C from a maintainer FOSSDA run on this branch. Cleaner dogfood loop than parsing DEBUG log lines pre-Slice-A.
- **CLI provider-prompt strings** at `cli.py:384,387,393` (`~$1.50/study` etc) stay hardcoded. Out of Phase 1 scope; revisit with provider-chooser UX work.
- **`bristlenose forget <session_id>`** erasure CLI deferred to a separate GDPR-erasure design.
- **`PromptTemplate` legacy `get_prompt` shim** kept indefinitely. No deprecation warning.
- **`cohort_normalise` import** at module top (small, stdlib-only, no SDK reach).
- **Single growing JSONL** with 1000-row retention cap, accept residual atomicity risk (rows ~700B, well under PIPE_BUF 4KB on macOS).

## Verification plan

**Out-of-the-box no-worse than today** (Slice C):
- Manual: fresh project (no `.bristlenose/llm-calls.jsonl`), run `bristlenose run` against FOSSDA. Compare pre-run cost line to pre-Phase-1 main-branch line. Accept within ±20% on Sonnet 4 / GPT-4o / Gemini 2.5 Pro defaults.
- Automated: `tests/test_llm_usage.py` parameterised — `estimate_pipeline_cost("claude-sonnet-4-20250514", 10, run_dir=None)` returns within ±20% of `0.27 × 10`.

**Measurably better after 5 runs**:
- Scripted dogfood: run FOSSDA five consecutive times, capture pre-run estimate each time. By run 4, cohort lookup switches from shipped to local. Run-5 estimate within ±10% of trailing actual.
- Automated: `tests/test_llm_telemetry.py` simulates 5 fake JSONL rows, asserts forecast returns `per-stage median × n_sessions × per-token price`.

**Schema integrity**:
- Hand-grep one row from a real run: confirm OTel dotted aliases serialise (`"gen_ai.usage.input_tokens": 14203` not `"input_tokens": 14203`).
- `LLMCallEvent.model_validate` round-trips a written row.

**Trust boundary**:
- `tests/test_llm_telemetry.py`: stat the file → mode `0o600`; symlink-attack returns error.
- Grep `bristlenose/exporters/*` for `llm-calls.jsonl` → expect zero matches.

**End-to-end smoke**:
- `bristlenose run` against the 2-min smoke fixture using local Ollama — verify retry-summed row appears with `retry_count > 0` if retries fire, exactly one row per logical call.

## Rollback / kill switches

Three layers, cheapest first:

1. `BRISTLENOSE_LLM_TELEMETRY=0` — short-circuits `record_call()` to a no-op. Read path tolerates missing/empty JSONL (returns `None` → falls back to baselines).
2. `BRISTLENOSE_LLM_FORECAST=legacy` — `estimate_pipeline_cost` uses retained `_LEGACY_TOKENS_PER_SESSION = (17_000, 10_000)` regardless of JSONL/baselines. Six-month grace; remove in Phase 2 PR.
3. Git revert. Slice C is the only user-visible behaviour change; reverting just C leaves A+B intact (rows accumulate, forecast goes back to constant). Preserves the data-collection win even if forecast logic is buggy.

Document both env vars in [bristlenose/llm/CLAUDE.md](../bristlenose/llm/CLAUDE.md) and a one-liner in CLI `--help` epilogue.

## Reference files

- Parent design: [docs/design-llm-call-telemetry.md](design-llm-call-telemetry.md)
- Write primitives to mirror: [bristlenose/events.py:266-276](../bristlenose/events.py:266)
- Run lifecycle setter site: [bristlenose/run_lifecycle.py:364](../bristlenose/run_lifecycle.py:364)
- Existing prompt loader: [bristlenose/llm/prompts/__init__.py:22-85](../bristlenose/llm/prompts/__init__.py:22)
- LLM dispatch chokepoint: [bristlenose/llm/client.py:162-218](../bristlenose/llm/client.py:162)
- Local retry path to refactor: [bristlenose/llm/client.py:502-596](../bristlenose/llm/client.py:502)
- Existing forecast call sites: [bristlenose/pipeline.py:650](../bristlenose/pipeline.py:650), [bristlenose/pipeline.py:1531](../bristlenose/pipeline.py:1531)
- Existing `RunCost` shape: [bristlenose/cost.py:30-65](../bristlenose/cost.py:30)
- Convention guard: [bristlenose/llm/CLAUDE.md](../bristlenose/llm/CLAUDE.md) — lazy-import discipline applies; `cohort_normalise` is small enough for top-level.
