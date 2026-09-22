---
status: archived-reference
last-trued: 2026-09-21
trued-against: HEAD@main on 2026-09-21
---

# Phase 1 — LLM cost forecast (implementation plan)

> **Truing status:** Partial — Phase 1 is shipped in full as of 2026-04-28; this doc is preserved as the implementation-record of how it landed. Slice A (`efc051a`), Slice B (`b140650`, `5ba52c7`), Slice C (`4401e41`) are all merged on main via `98df507`; branch closed in `23d56af`. The §File-by-file plan and §Verification plan are retained verbatim as the historical plan against which slices were executed — read them as past, not future, work. The "FOSSDA dogfood between B and C" sequencing in §Decisions taken did **not** happen as planned, and the consequence ran for five months: `cohort-baselines.json` stayed the empty Slice A placeholder until 2026-09-21, so **the forecast this doc plans never once fired for a user**. See the 2026-09-21 changelog entry and the FOSSDA-pivot note in §Decisions taken.

## Changelog

- _2026-09-21_ — **the deferred step was finally taken, and it was not the only thing missing.** `cohort-baselines.json` is populated (15 rows: `claude-sonnet/4`, `gpt-4o/4`, and a pooled `*` cohort) by the new [`scripts/regenerate-cohort-baselines.py`](../scripts/regenerate-cohort-baselines.py), which is the script §Implementation of the parent design reserved a name for. Populating it alone would **not** have been enough — three further defects each independently returned `None`: (1) `_LOCAL_N_THRESHOLD` was applied to per-run stages `s10`/`s11`, which issue exactly one call per run, and an under-sampled bucket vetoed the *whole* forecast, so a single-run project could never use its own data; (2) baseline lookup was exact-match on `(family, major)`, so `claude-sonnet-5` found nothing while `claude-sonnet-4` rows sat in the same file, and three of the four cloud defaults normalise to a family with no rows at all; (3) `cost_usd_actual_estimate` / `cost_usd_predicted` were declared on `LLMCallEvent` in Slice A and written by nothing, so no row in any `llm-calls.jsonl` carried a cost. All four fixed. Backtested against 12 complete runs in the maintainer corpus: median forecast/actual ratio **0.95×**, 11 of 12 within 2×; the outlier is FOSSDA at 0.26× (long-form oral history, sessions far above the corpus median), which its own local history corrects to 0.78× on a second run. See §Decisions taken.
- _2026-04-28_ — trued up: status flipped to archived-reference, doc reframed as historical implementation plan rather than forward-looking work. Slices B/C confirmed shipped (commits `b140650`, `5ba52c7`, `4401e41`); merged via `98df507`; branch closed `23d56af`. Kill switch `BRISTLENOSE_LLM_FORECAST=legacy` confirmed wired at `bristlenose/llm/pricing.py:224`. FOSSDA pivot called out in §Decisions taken: maintainer dogfood deferred post-merge, baselines remain empty placeholder. Stage-5b session_id observation promoted from parenthetical "Slice B reality" note to documented invariant. Anchors: `bristlenose/llm/pricing.py:8-12` (module docstring describes shipped behaviour), `bristlenose/llm/pricing.py:66` (`_LEGACY_TOKENS_PER_SESSION`), `bristlenose/llm/pricing.py:204-247` (`estimate_pipeline_cost` data-driven body).
- _2026-04-27_ — trued up against `efc051a`: Slice A shipped; provider-method line refs in §EDIT files item 9 refreshed; branch name corrected.
- _2026-04-25_ — initial draft.

**Status:** All three slices shipped (Slice A `efc051a`, Slice B `b140650` + `5ba52c7`, Slice C `4401e41`); merged via `98df507`; branch `cost-and-time-forecasts` closed (`23d56af`).
**Parent design:** [design-llm-call-telemetry.md](design-llm-call-telemetry.md) — full design covering cost + time + UX + shoal across five phases. This doc is the file-by-file implementation plan for Phase 1 only.
**Sibling:** [design-llm-pricing-fetch.md](design-llm-pricing-fetch.md) — keeps the rate sheet itself current between releases (separate followup PR after slice C; not yet implemented as of 2026-04-28).
**Scope:** narrow. Replace the hardcoded `_TOKENS_PER_SESSION` constant with a self-correcting cost forecast backed by per-call data capture. Time forecast is Phase 2.
**Branch:** `cost-and-time-forecasts` — merged via `98df507`, closed in `23d56af`.

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

> **Shipped — preserved as record.** All three slices landed on main. Section retained verbatim below to capture the planned sequencing; commit anchors added inline.

Three independently mergeable slices. Each leaves `main` shippable.

- **Slice A — Schema + writer** (steps 1–6, 16, partial tests). Lands frontmatter, prompt-loader extension, `cohort_normalise`, `telemetry.py`, **empty** `cohort-baselines.json`, CLAUDE.md gotcha, schema/normalise/frontmatter tests. `record_call` is unused in production — exercised by tests only. Zero behaviour change. **Shipped `efc051a` (2026-04-27).**
- **Slice B — Wire telemetry into the hot path** (steps 9–12). `client.py`, stage modules, contextvars set in `run_lifecycle.py` and `pipeline.py`. After this lands, every real run produces JSONL rows. Forecast still uses the old constant. **Shipped `b140650` (hot-path) + `5ba52c7` (serve-mode autocode + elaboration binding).**
- **Between B and C** — maintainer runs FOSSDA once on this branch, JSONL accumulates real rows, derive `cohort-baselines.json` medians from those rows (hand or quick script), commit populated JSON. **Did not happen as planned — see §Decisions taken pivot note.**
- **Slice C — Replace the forecast** (step 13 + remaining tests). Delete `_TOKENS_PER_SESSION`, swap `estimate_pipeline_cost` body. The user-visible change. Isolates the rollback decision. **Shipped `4401e41` with `_LEGACY_TOKENS_PER_SESSION` retained as kill-switch (not deleted, gated by `BRISTLENOSE_LLM_FORECAST=legacy`).**

## Decisions taken (resolved during plan review)

> **Pivot from plan — 2026-04-28, closed 2026-09-21.** The "FOSSDA dogfood between Slices B and C, derive medians, commit populated JSON" step did **not** happen as planned. Slice C shipped (`4401e41`) with `cohort-baselines.json` still as the empty Slice A placeholder, deferring the populate step to "a separate manual step" tracked out of band. It was not taken for five months.
>
> **What the deferral actually cost, measured 2026-09-21.** The plan reads as though an empty baselines file degrades the forecast to "local data only". It does not — it disables the feature outright, for everyone, permanently. A new user has no local rows by definition, so step 3 of the resolution order was the only step that could ever answer them, and it was empty. Worse, step 2 could not rescue a *returning* user either: the threshold vetoed the whole forecast on `s10`/`s11`, which have one sample per run by construction. Every documented path returned `None`.
>
> **And the tests could not see it.** `tests/test_llm_usage.py` passed throughout, because every fixture stubbed `_load_baselines` with synthetic cohorts and used one or two stages — never the real file, never the per-session + per-run mix a real log has. One test, `test_returns_none_when_no_data_anywhere`, asserted `cost is None` while reading the *real* baselines: it was pinning the defect, and would have gone red the moment anyone fixed it. This is the degenerate-fixture trap in the root `CLAUDE.md` — *a fixture whose values are the degenerate case can disable the very code path under test.* The regression tests added on 2026-09-21 read the shipped file and a genuinely empty `run_dir`, and each was proved red against the pre-fix tree before being kept.
>
> **Standing obligation.** Prompts and baselines move together — a release that bumps a `prompt_version` should re-run `scripts/regenerate-cohort-baselines.py`, since the medians are calibrated against the wording. Nothing gates this yet; the parent design's §Implementation proposes a CI check that fails when `prompts.lock` and `cohort-baselines.json` drift.

- **Initial baselines**: Slice A ships `{"cohorts": []}`. Real medians were planned to be derived between Slices B and C from a maintainer FOSSDA run on this branch. Cleaner dogfood loop than parsing DEBUG log lines pre-Slice-A. *(See pivot note above — sequencing did not hold; the file stayed empty, and therefore the forecast stayed dead, from 2026-04-28 to 2026-09-21.)*
- **Pooled `("*", "*")` cohort** *(added 2026-09-21, not in the original plan)*: the plan assumed lookup by exact `(family, major)`. That cannot serve a model nobody has run — and at time of writing that includes `claude-sonnet-5` and three of the four cloud providers' current defaults, because `gpt-5.6-terra` normalises to `("gpt-5.6-terra", "0")` and `gemini-3.8-flash` to `("gemini-flash", "3")`. Lookup now widens: exact → same family, nearest major → pooled `*`. The justification is that input tokens are a function of the transcript and the prompt schema, not of the model; output tokens vary by verbosity, which the measured spread between `claude-sonnet/4` and `gpt-4o/4` bears out at under 2× per stage. Honest-but-approximate beats a blank where the user is deciding whether to spend their own money.
- **CLI provider-prompt strings** at `cli.py:384,387,393` (`~$1.50/study` etc) stay hardcoded. Out of Phase 1 scope; revisit with provider-chooser UX work.
- **`bristlenose forget <session_id>`** erasure CLI deferred to a separate GDPR-erasure design.
- **`PromptTemplate` legacy `get_prompt` shim** kept indefinitely. No deprecation warning.
- **`cohort_normalise` import** at module top (small, stdlib-only, no SDK reach).
- **Single growing JSONL** with 1000-row retention cap, accept residual atomicity risk (rows ~700B, well under PIPE_BUF 4KB on macOS).

## Verification plan

> **Shipped — preserved as record.** Verification was executed during slice merges; this section retained as the original verification design. Test files referenced (`tests/test_llm_usage.py`, `tests/test_llm_telemetry.py`) all exist and pass on main as of 2026-04-28.

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

Three layers, cheapest first. **All three wired and shipped as of 2026-04-28**:

1. `BRISTLENOSE_LLM_TELEMETRY=0` — short-circuits `record_call()` to a no-op. Read path tolerates missing/empty JSONL (returns `None` → falls back to baselines).
2. `BRISTLENOSE_LLM_FORECAST=legacy` — `estimate_pipeline_cost` uses retained `_LEGACY_TOKENS_PER_SESSION = (17_000, 10_000)` regardless of JSONL/baselines. Wired at [`bristlenose/llm/pricing.py:224`](../bristlenose/llm/pricing.py:224); six-month grace; remove in Phase 2 PR.
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
