# LLM call telemetry & self-correcting cost estimates

**Status:** Draft (Apr 2026)
**Owner:** Martin
**Related:** `docs/design-pipeline-resilience.md` (events log), `docs/design-perf-fossda-baseline.md` (latency log line), `bristlenose/llm/pricing.py` (current forecast), `bristlenose/cost.py` (post-run accounting), `docs/methodology/tag-rejections-are-great.md` (downstream consumer)

## Problem

Users care about two things: **no nasty wait-time surprises** and **no nasty cost surprises**. Time is at least co-primary with cost, often more important — for many alpha/beta users the tokens are billed to an employer or a corporate account, but their own time and the laptop's availability are costs they pay regardless.

The decision a user makes when starting a run is qualitative, not pence-precise:

- **~3 minutes** — wait at the desk, watch it.
- **~10 minutes** — make a coffee, come back.
- **~30–60 minutes** — go and do something else, check in over lunch.
- **~hours** — set it off, plan around it. *Leave the lid open if it's a Mac.*

Those four buckets correspond to qualitatively different plans for the next bit of the day. A user who thinks "coffee break" should not find out it was "back after lunch." Order-of-magnitude accuracy is enough; the user is choosing between buckets, not optimising minutes.

Cost has the same shape: the user is asking "is this $1, $10, or $100?" not "is this $4.32 or $4.57?". So both axes round generously, and both surface together so the user can trade off:

- Cloud: `~3 min, ~$4.50`
- Local: `~25 min, no $ cost`

The typical 2026 trade direction is *cloud is faster, local is cheaper-but-slower* — Anthropic's H100s out-pace a MacBook M2 for most stages today. By 2027–2028 a smaller cohort of users on serious Apple Silicon investment (M5 Pro, M6) will see the trade flip on the short-context-structured stages — local faster *and* free. The forecast doesn't bake either direction in; it reports what was measured. Both numbers, every time, let the user pick.

The pre-run cost forecast in [bristlenose/llm/pricing.py:51](../bristlenose/llm/pricing.py:51) is a single hardcoded constant `(17_000 input, 10_000 output)` per session. It's been wrong since 12 Feb 2026 and nobody noticed because it looked authoritative. The forecast doesn't update when prompts are rewritten, when models change, when hardware changes, when transcript length shifts — yet it speaks with the same confident voice every time.

What we actually want:

1. **Day one usable.** A user installing Bristlenose for the first time gets a forecast in the right order of magnitude.
2. **Silently improves.** As the user accumulates runs on their own machine, against their own data, the forecast quietly converges on their reality. They don't have to look at the machinery.
3. **Honest when we don't know.** For users on niche hardware/models the maintainer couldn't pre-calibrate against, the forecast says "unknown" rather than guessing.

Almost all prompt evolution in Bristlenose is driven by **quality** — better tags, sharper themes. Cost-tracking is incidental, present only to spare users from billing shock. The forecast is "no surprises" infrastructure, not a cost-optimisation tool.

```python
_TOKENS_PER_SESSION: tuple[int, int] = (17_000, 10_000)
```

Set once on 12 Feb 2026 (commit `df6c8c2`), eyeballed from a handful of FOSSDA-shaped runs, never recalibrated. The comment claims "based on ~30–60 min interview transcripts with Sonnet-class models" but no calibration script, dataset, or measurement log was committed. Today the constant silently lies whenever any of these wobble:

- transcript length outside the 30–60 min band
- model swap (Haiku terser, Opus more verbose, local models wildly variable)
- prompt rewrite (every edit to `bristlenose/llm/prompts/*.md` shifts input tokens, nothing notices)
- non-English transcript (CJK languages tokenise at ~1.5 chars/token vs ~4 for English)
- retry path firing (3× exponential backoff for local model JSON failures)
- single-session vs 20-session run (clustering/theming amortise non-linearly)

Meanwhile the *real* token counts come back on every provider response. Today they get summed into a run-level total in the events log and then thrown away. The forecast and the actuals never meet.

## The brief: out-of-the-box App Store experience

Before the rest of this doc — the brief is narrow on purpose. Everything else here is documented for completeness, not on the alpha path.

**The App Store user, first install, default Claude config, sees this and only this:**

```
Pre-run:  Estimated ~30 min, ~$5.
Mid-run:  [progress bar] ~12 min remaining — clustering quotes
Post-run: Done in 38 min. ~$5.40.
```

That's the entire UX promise for the alpha. The user never sees `RoughFirstGuess` vs `Settled` as labels — they see numbers that get more accurate over time, silently. The data layer behind those numbers is rich; the surface is one line per UX moment.

**Load-bearing for the brief** (must land):

- Per-call JSONL data capture — the instrumentation, per the MAAS lesson; window closes if we defer
- Shipped baselines for default Claude cohorts — the day-one number
- P75 padding + hold-the-number rule — the trust contract
- Cone-of-uncertainty countdown — the tightening display
- Step-count fallback — the honest spine when time data is thin on this user's machine
- Post-run reconciliation line — the calibration moment

**Documented but deferred** (not on alpha path):

- The `Anchored` comparative state — only matters when configs change, which an App Store user doesn't do
- Comparative narratives ("you've previously run with Sonnet…")
- Per-stage backend trade-off UX — genuinely future, downstream of [design-stage-backends.md](design-stage-backends.md)
- The full disclosure-triangle CLI overlay layout (a default-only strip is enough for alpha)
- The watchable-countdown last-minute ritual — Phase 3 polish, not alpha-blocking
- Shoal revival — Phase 4
- `--verbose` mode and elaborate CLI narratives — App Store users don't see them
- Multi-project / multi-window layout

This split matters because the doc has accreted forward-looking material in the course of being written. A reader scoping "what's actually in alpha?" should land here first.

## Goal

Capture per-call token usage and per-stage wall-time in a structured, append-only log. Use it to serve **three distinct UX moments**, all from the same data layer:

1. **Pre-run forecast** ("should I press Run?") — decision phase. Both axes (cost + time) at low precision. User is choosing between "wait at desk", "coffee break", "after lunch", "overnight, leave the lid open."
2. **In-run progress** ("how much longer?") — monitoring phase. Time-remaining countdown, with precision tightening as the remainder shrinks. Honest about what we don't know — falls back to step-count-only when time data is thin.
3. **Post-run review** — what did it actually take. Calibration for next time, in both axes.

These three moments have different emotional textures and different precision needs. The data layer is shared; the presentation differs.

The shared data layer must:

1. **Day-one usable.** Ships with baselines good enough to set adequate expectations on both axes — maintainer sets the rough first-time guess; system refines silently with use.
2. **Silently converge.** Local runs tighten the forecast on this user's machine, with this user's prompts, against this user's data. No knobs to turn, no dashboards to consult.
3. **Honest about uncertainty.** Fewer significant figures when data is thin. Step-count fallback when time is wholly unknown. Surface "we don't know" rather than fabricate.
4. **Both axes, surfaced together at decision time.** A user choosing between cloud and local sees `~3 min, ~$4.50` next to `~25 min, no $ cost`.
5. **Coarse, not precise — and the coarseness rule differs by moment.** Pre-run cost rounds to 1–2 sig figs. Pre-run time rounds to lunch/coffee buckets. In-run countdown tightens as it nears zero (different precision near 3 hours vs near 30 seconds — see §Time display below).

Non-goals (deliberately out of scope):

- Live dashboards, real-time aggregation, anomaly detection
- OTLP export to external observability platforms
- Cross-machine telemetry phoning home — this stays local-first
- Streaming chunk-level capture
- Prompt-diffing UI
- Penny-precise cost reporting — we are deliberately rounding

## Prior art

The space is well-mapped; we should align with conventions, not invent.

**Schema convention: OpenTelemetry GenAI semantic conventions.** Field names like `gen_ai.usage.input_tokens`, `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.system`, `gen_ai.operation.name`. Even with no OTLP export, naming our JSONL columns this way means Phoenix, Langfuse, OpenLLMetry, or any future consumer can ingest the file for free. Spec: <https://opentelemetry.io/docs/specs/semconv/gen-ai/>.

**Closest spiritual match: Simon Willison's `llm` tool.** SQLite-backed, append-only, local-first, queryable. The `responses` table holds prompt, response, model, and usage as JSON. <https://llm.datasette.io>. We won't adopt the schema wholesale (ours is more structured), but the *posture* — local file, post-hoc rollups, no live aggregator — is exactly right.

**Cost tables to steal:** LiteLLM's `model_prices_and_context_window_backup.json` (MIT, copy-pasteable, covers all 5 of our providers): <https://github.com/BerriAI/litellm/blob/main/litellm/model_prices_and_context_window_backup.json>. Worth comparing against our `PRICING` dict periodically.

**Token-prediction libraries:**
- `tiktoken` (OpenAI/Azure GPT family): exact, free, offline. <https://github.com/openai/tiktoken>
- `anthropic.messages.count_tokens()`: exact, requires API call (cheap but online).
- Gemini: `model.count_tokens()` in `google-generativeai`, online only.
- Ollama: per-model, llama.cpp tokenizers — variable.
- char/4 fallback: ~8–12% off for English prose, blows up to 30%+ on code/JSON/CJK.

**Heavyweight competitors we are NOT adopting:**
- Langfuse, Helicone — proxy/SaaS shape, wrong fit for local-first.
- LangSmith, W&B Weave — closed SaaS, phone-home.
- OpenLLMetry — closest drop-in but pulls full OTel SDK; too heavy for now.
- Arize Phoenix — local-first OSS option, SQLite backend; revisit if we ever want a UI.

**Waiting psychology and progress-bar UX** — the in-run countdown design draws from a small but coherent literature:

- **Maister, "The Psychology of Waiting Lines"** (Harvard, 1985). Eight principles. Most relevant here: #1 *unoccupied time feels longer than occupied* (justifies the Typographic Shoal — see §In-run UX); #4 *uncertain waits feel longer than known, finite waits* (justifies showing *something* even at low confidence); #5 *unexplained waits feel longer than explained* (justifies the human-readable stage label alongside the number). <http://davidmaister.com/articles/the-psychology-of-waiting-lines/>
- **Myers, "The Importance of Percent-Done Progress Indicators"** (CHI '85). The empirical foundation. 86% of users preferred percent-done indicators; "users will tolerate longer delays if a progress indicator is shown." <https://www.cs.cmu.edu/~bam/papers/chi85percent.pdf>
- **Nielsen's 10-second rule** (1993). Anything over ~10 s needs a percent-done indicator with a finite estimate. The minutes-to-hours regime is open territory beyond Nielsen — this design is part of that. <https://www.nngroup.com/articles/response-times-3-important-limits/>
- **Harrison et al., "Rethinking the Progress Bar"** (UIST 2007) and **"Faster Progress Bars"** (CHI 2010). The structural finding: **users hate upward revisions more than slow-but-monotone bars**. Recommendation: pad initial estimates, never revise upward visibly. If you must communicate uncertainty, use a range, not a moving point estimate. Bars that accelerate near the end feel faster; bars that decelerate feel "stuck." <https://www.chrisharrison.net/projects/progressbars/ProgBarHarrison.pdf>
- **Apple HIG — Progress indicators**: "When possible, switch from an indeterminate to a determinate indicator so that people can gauge progress." <https://developer.apple.com/design/human-interface-guidelines/progress-indicators>
- **Microsoft Fluent — Progress controls**: step indicators ("N of M") are the recommended pattern when "the operation has a known number of stages but the duration of each stage is variable or unknown." <https://learn.microsoft.com/en-us/windows/apps/design/controls/progress-controls>
- **Boehm/McConnell, "Cone of uncertainty"** (Boehm 1981; McConnell *Software Estimation*, 2006). The underlying concept for *adaptive-precision estimates* — uncertainty narrows as work progresses. There's no canonical name in HCI for "precision tightens as the remainder shrinks"; cone-of-uncertainty is the closest defensible term.
- **`tqdm` and Databricks Jobs UI** — the convergent ML/data-job pattern: per-stage discrete status (queued/running/done) + elapsed per stage, ETAs only within stages where iter rate is measurable. Aggregate cross-stage ETAs generally avoided as untrustworthy.

**Public writing on self-correcting forecasts** (mostly anecdotal, no published maths):
- Replit Agent retro: initial estimate 5× off, fixed by per-tool cohorting. <https://blog.replit.com/agent-3>
- Cursor "Shadow Workspace": per-feature token budgets recalibrated weekly from logs. <https://www.cursor.com/blog/shadow-workspace>
- Vercel AI SDK telemetry guide: explicit residual tracking via OTel spans. <https://sdk.vercel.ai/docs/ai-sdk-core/telemetry>

**Genuine gap in the literature:** no public examples of "this prompt got 18% more expensive after the rewrite" as a first-class workflow. Worth writing about once it works.

## Design

### Trust boundary

**This file is a re-identification key.** Same handling discipline as `pii_summary.txt`:

- Lives in `<output_dir>/.bristlenose/` (hidden), never the shareable output root.
- MUST NOT appear in HTML export, ZIP export, the Miro bridge, the slides export, the support bundle, or any "share with stakeholder" feature.
- Even though no original PII strings are recorded, the combination of `session_id` + timestamp + `input_chars` + `elapsed_ms` + `hardware_signature` is enough to reconstruct "participant X was interviewed on date Y and analysed by model Z on machine W." Treat it as such.
- `hardware_signature` is coarse by deliberate design — chip family + memory tier, never UUIDs or serial numbers. But it's still a re-identification dimension and inherits the same handling rules.
- A parallel gotcha line in root `CLAUDE.md` (sibling to the existing `pii_summary.txt` line) lands with the implementation, not after.
- Future opt-in alpha-telemetry upload boundary redaction rules (Phase 2+, see `docs/private/road-to-alpha.md` §13b):

| Field | Action at upload boundary |
|---|---|
| `session_id` | drop or salt-hash |
| `input_chars` | round to nearest power of 2 |
| `elapsed_ms` | round to nearest 100 ms |
| `prompt_template_path` | drop (redundant with `_sha`) |
| `hardware_signature` | already coarse (`darwin-arm64-M2-24GB`); safe to upload |
| token counts, model, stage, outcome, prompt sha | safe to upload |

### One JSONL row per terminal LLM outcome

Path: `<output_dir>/.bristlenose/llm-calls.jsonl`. Sibling to `pipeline-events.jsonl`.

**File-write primitives** (match `bristlenose/events.py:266-276` exactly, do not loosen):

- `os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)`
- One `os.write()` per row, never `pathlib.Path.open("a")` or buffered streams.
- POSIX guarantees `O_APPEND` assigns offsets atomically; for regular files single `write()` calls below 4 KiB are atomic in practice on APFS/ext4 but are not POSIX-guaranteed. Our rows are ~700 bytes — safe in practice. To be defence-in-depth, use a **per-run file** (`llm-calls-<run_id>.jsonl`) so there is no cross-run write contention; merge or scan as a glob at forecast time.
- **fsync discipline:** do **not** fsync per call from the asyncio event loop (blocks all coroutines 1–5 ms × 50 calls). Two acceptable patterns: (a) `await asyncio.to_thread(os.fsync, fd)` on every call, (b) drop per-call fsync entirely and fsync only at run terminus — the data is statistical, not forensic. Recommend (b): losing the last few rows on crash is fine; the run-level total in `pipeline-events.jsonl` is still durable.

**Implementation note:** the schema below is shown as JSON for readability. The actual implementation defines a `LLMCallEvent(BaseModel)` in Pydantic, mirroring `RunStartedEvent` etc. in [bristlenose/events.py:152](../bristlenose/events.py:152). OTel dotted field names round-trip via `Field(alias=...)`. `price_table_version` reuses the existing `PRICE_TABLE_VERSION` constant from [bristlenose/llm/pricing.py:13](../bristlenose/llm/pricing.py:13), never hardcoded.

Schema, OTel-aligned where possible:

```json
{
  "ts": "2026-04-27T19:30:00Z",
  "run_id": "run_2026-04-27T19-29-50_abc123",
  "session_id": "interview-04",
  "stage": "s10_quote_extraction",
  "gen_ai.system": "anthropic",
  "gen_ai.operation.name": "chat",
  "gen_ai.request.model": "claude-sonnet-4-20250514",
  "gen_ai.response.model": "claude-sonnet-4-20250514",
  "prompt_id": "extract_quotes",
  "prompt_version": "0.4.2",
  "prompt_path": "bristlenose/llm/prompts/extract_quotes.md",
  "prompt_sha": "a1b2c3d4e5f6...",
  "input_chars": 58213,
  "gen_ai.usage.input_tokens": 14203,
  "gen_ai.usage.output_tokens": 8910,
  "gen_ai.usage.cache_read_input_tokens": 0,
  "gen_ai.usage.cache_creation_input_tokens": 0,
  "elapsed_ms": 4203,
  "estimated_input_tokens": 17000,
  "estimated_output_tokens": 10000,
  "estimate_source": "hardcoded_constant",
  "retry_count": 0,
  "finish_reason": "end_turn",
  "outcome": "ok",
  "usage_source": "reported",
  "hardware_signature": "darwin-arm64-M2-24GB",
  "price_table_version": "<from PRICE_TABLE_VERSION constant>",
  "cost_usd_actual_estimate": 0.176,
  "cost_usd_predicted": 0.201
}
```

Field rationale:

- **`gen_ai.response.model` separately from `.request.model`** — model aliases drift (`claude-3-5-sonnet-latest` resolves to different snapshots over time). Always log what the provider actually used.
- **`prompt_id` + `prompt_version`** — primary cohort key. ID is stable across file moves; version is human-bumped semver from the prompt's YAML frontmatter. Drives "did v0.5 cost more than v0.4?" analysis.
- **`prompt_sha`** — sha256 of the .md template file at dispatch time. Integrity backstop only — a unit test catches "edited but didn't bump version." Never the cohort key. Hashing the rendered prompt would leak PII and fragment cohorts uselessly; the template hash sidesteps both.
- **`prompt_path`** — debug field. Path may move; `prompt_id` is the stable name.
- **`input_chars`** — raw character count of the rendered prompt. Cheap, language-agnostic, useful for binning when we don't have a tokenizer.
- **Cache token fields** — Anthropic prompt caching and OpenAI's automatic prefix caching both report cache reads separately. Counting them as full-price input inflates forecasts 2–5×. Must split.
- **`estimate_source`** — `"hardcoded_constant"` initially, `"cohort_median"` once the lookup is wired. Lets us measure the lift.
- **`retry_count`** — log only on terminal outcome (success or final failure). Don't double-count retries; that bug bit Langfuse and OpenLLMetry in 2024.
- **`outcome`** — `"ok" | "truncated" | "error" | "cancelled"`. Truncated calls (max_tokens hit) belong in the dataset; they're real spend.
- **`run_id`** — the **same** value `bristlenose/run_lifecycle.py` mints for `pipeline-events.jsonl`. Reused, never independently generated. Lets analysts JOIN the two logs.
- **`usage_source`** — `"reported" | "missing"`. Phase 1 only emits `"reported"` (Anthropic/OpenAI/Azure/Gemini SDKs all surface usage reliably). For Ollama, when the response field is missing or zero, write the row with `usage_source: "missing"` and null token counts. Cohort lookup skips null-token rows. Computed-from-tokenizer fallback (`usage_source: "computed"`) is **deferred** — out of scope for v1.

### Where the write happens

The chokepoint is `LLMClient.analyze()` in [bristlenose/llm/client.py](../bristlenose/llm/client.py). All 5 providers go through it. **But the chokepoint does not currently know `run_id`, `output_dir`, `stage`, or `prompt_template_id`** — every caller (stages 5b, 8, 9, 10, 11) would have to be touched to thread context through. This is wider than "single new helper module" suggests. Two patterns to choose from:

- **Pattern A — `contextvars`.** The pipeline runner sets a module-level `contextvars.ContextVar` for the run + stage at the start of each stage. `LLMClient.analyze()` reads it. asyncio-safe (each task gets its own copy). Per-call `prompt_template_id` still passed as an arg. **Recommended** — minimises call-site churn, matches how `bristlenose/timing.py` already threads stage info.
- **Pattern B — explicit `CallContext` arg.** New required `context: CallContext` arg on `analyze()`. Touches every call site (~6 files). More explicit, more typing.

The `prompt_template_id` problem is separate and worth its own decision (see Open question §"Prompt-template handle").

Today it emits a free-text log line:

```
llm_request | provider=anthropic | model=claude-sonnet-4-20250514 | elapsed_ms=4203 | schema=QuoteList
```

Promote this from a log string to a structured JSONL writer. The log line stays for human reading; the JSONL is the structured datum. Single new helper module: `bristlenose/llm/telemetry.py` with one function `record_call(...)` that appends a row.

Streaming note: the OTel GenAI spec is explicit that for `stream=True`, the span ends on the final chunk and usage attributes are set then. We don't currently stream, but if we ever do, the rule is "log on terminal outcome, never per chunk."

### Architecture: configuration determines cohort, two axes per estimate

The forecast is a pure function from **configuration** to **estimate**. Configuration is the tuple of dimensions that uniquely identifies a stable cost-and-time regime — same configuration, past predicts future; different configuration, fresh dataset.

Each estimate has **two axes**:

- **`usd`** — dollars. Hardware-independent: tokens × price-per-token. Cloud has cost; local has no `$` cost (electricity is below the noise floor of "should I bother").
- **`wall_seconds`** — duration. Hardware-dependent for local backends. Network-and-provider-dependent for cloud.

The cohort key differs slightly between the two axes — see *Two cohorts, one config* below. Everything else (normalisation, sample thresholds, display rounding) is the same.

#### The five dimensions

```
Config = (stage_id, prompt_id, prompt_version, model_family, model_major)
```

That tuple is the **cohort key**. Two LLM calls with the same key are interchangeable for cost prediction. Calls with different keys are not. Why these five and not others:

- **`stage_id`** — different work. Quote extraction is output-heavy; theming is one big synthesis call.
- **`prompt_id` + `prompt_version`** — each prompt version is its own dataset. A one-character edit can blow the estimate.
- **`model_family` + `model_major`** — the level at which structural cost differences live. Sonnet ≠ Haiku ≠ different vendor. Sonnet 4 ≠ Sonnet 3.5. But Sonnet 4 at one snapshot ≈ Sonnet 4 at another snapshot — provider-side snapshot dates within a major version don't materially change verbosity for a fixed prompt. The user's typical case ("ran 3 interviews, then 7 more next week — same prompts, same major versions") works because snapshot drift drops out of the key.

Dimensions explicitly **not** in the cost cohort key:

- **Snapshot date.** Recorded in the row (forensics) but ignored for cohorting. The "snapshot churn" pain — every cloud release would otherwise blank every cohort — disappears.
- **Hardware.** Token counts come from the model's tokenizer, not the GPU. Same `llama3.2:3b` on M2 vs M5 vs Linux/CUDA produces identical token counts. (Wall time is a different story — see below.)
- **Transcript length, language.** Captured in the per-call sample distribution within a stage cohort. The median across a stage's calls handles it without an extra dimension.
- **Machine, OS minor, time of day.** Not load-bearing for cost.

#### Two cohorts, one config

Wall time depends on hardware where cost does not. So the wall-time forecast uses a slightly extended cohort key:

```
CostCohortKey = (stage_id, prompt_id, prompt_version, model_family, model_major)
TimeCohortKey = CostCohortKey + (hardware_signature)
```

`hardware_signature` is set to a constant `"cloud"` for cloud calls (Anthropic/OpenAI/Azure/Gemini hardware is opaque and stable to us — one cohort across all users). For local calls (Ollama, MLX, Apple FM), it's a coarse machine descriptor:

| Platform | Signature example |
|---|---|
| Apple Silicon | `darwin-arm64-M2-24GB` |
| Apple Silicon (M5) | `darwin-arm64-M5-64GB` |
| Linux + NVIDIA | `linux-x86_64-RTX4090-24GB` |
| Linux CPU-only | `linux-x86_64-cpu-32threads-64GB` |
| Intel Mac | `darwin-x86_64-cpu-16threads-32GB` |

Coarse on purpose — chip family and memory tier (rounded to the nearest published RAM size). Never a UUID, serial number, or anything else that survives a reinstall. The signature is a re-identification dimension and inherits the existing Trust Boundary classification — it lives in `.bristlenose/` and never appears in any export.

A user with one machine sees a single time cohort per local backend. A user who runs Bristlenose on both a laptop and a desktop sees two — both contribute their own times, and switching machines triggers a fresh time-cohort while the cost cohort stays settled.

#### Normalisation: provider response → (family, major)

The string a provider returns in its response varies wildly. A normalisation function maps each provider's response to a normalised `(family, major)` tuple:

| Provider | Response example | Family | Major |
|---|---|---|---|
| Anthropic | `claude-sonnet-4-20250514` | `claude-sonnet` | `4` |
| OpenAI | `gpt-4o-2024-11-20` | `gpt-4o` | `(date dropped, family is the major axis)` |
| Azure | `prod-sonnet-eastus-v1` | deployment name (user-defined) | deployment name |
| Gemini | `gemini-2.5-pro-preview-05-06` | `gemini-pro` | `2.5` |
| Apple FM | `apple-fm@macOS-26.1.2` | `apple-fm` | `26` (OS major) |
| MLX | `mlx-qwen-14b-bf16` | `mlx-qwen` | `14b-bf16` (size+quant) |
| Ollama | `llama3.2:3b` | `llama` | `3.2:3b` (size matters) |

We **never** record the alias the user sent (`claude-3-5-sonnet-latest`, `gpt-4o`). Aliases drift silently and would silently poison cohorts. We record what the response actually returned.

Normalisation lives in `bristlenose/llm/cohort_normalise.py` — one tested function per provider, called once per row at write time. The full original response string is also kept in the row for forensics.

#### The estimate

```python
@dataclass(frozen=True)
class Axis:
    value: float | None      # None = no data on this axis
    precision: int           # significant figures: 1 or 2
    basis: str               # "local" | "shipped" | "none"
    sample_count: int

@dataclass(frozen=True)
class Estimate:
    usd: Axis                # cost axis (CostCohortKey)
    wall_seconds: Axis       # time axis (TimeCohortKey)
```

The two axes are computed independently against their own cohort keys, then bundled. They can resolve to different bases — common case: a user on a settled cloud cohort gets `basis="local"` for `usd` *and* `wall_seconds` (both are settled, both have data, hardware doesn't matter for cloud). A user who just switched from cloud to a local Llama gets `basis="shipped"` for `usd` (we have a baseline) and `basis="none"` for `wall_seconds` until run 2 (no shipped time baseline for their specific machine).

Algorithm per stage, per axis:

1. Stream `.bristlenose/llm-calls.jsonl` and `pipeline-events.jsonl`, filter by the relevant cohort key.
2. If any local rows match: median × (price for cost / 1.0 for time). `precision = 2 if N ≥ 3 else 1`. `basis = "local"`.
3. Else if `shipped_baselines` covers the key for that axis: baseline × scale. `precision = 1`. `basis = "shipped"`.
4. Else: `value = None`. `basis = "none"`.

There is no separate `settled` / `rough` / `unknown` state. Each axis carries its own confidence as `precision` + `sample_count` + `basis`. "No estimate on this axis" is just `value is None`.

#### Wall time spans non-LLM stages too

A pipeline run is more than LLM calls. Transcribe is ~47% of FOSSDA wall time despite making zero LLM calls (it's local Whisper, or SpeechAnalyzer on macOS 26+, see [design-stage-backends.md](design-stage-backends.md)). For the wall-time forecast to answer the user's "coffee or after lunch?" question — and to drive a meaningful time-remaining progress bar — it must span the whole pipeline, not just the LLM stages.

- **Cost forecast** is LLM-only. Non-LLM stages contribute zero `$`.
- **Wall-time forecast** spans every stage with a non-trivial duration. Source: per-stage `started_at`/`completed_at` timestamps already in `pipeline-events.jsonl` and the manifest. We don't need new instrumentation for this — `scripts/perf-breakdown.py` already does the bucketing; we lift its logic into the forecast path.

Cohort key for non-LLM stages: `(stage_id, prompt_id="", prompt_version="", "n/a", "n/a", hardware_signature)`. The empty prompt fields are the convention for non-LLM stages so the same lookup works uniformly.

#### Post-run reconciliation: the calibration moment

When the run completes, the user sees one final line that closes the loop on the pre-run estimate. This is where trust is built or broken — the user organised their day around `~45 min, ~$5`, and now the actuals come in.

Default rule: **within tolerance, just the facts. Notable miss, either direction, append a learning-tense postfix.**

```
Within ~10% on both axes:
  Done in 38 min. ~$5.40.

Notable time miss (either direction):
  Done in 53 min, ~$5.40 — adjusting future estimates.
  Done in 25 min, ~$5.40 — adjusting future estimates.

Notable cost miss:
  Done in 38 min, ~$8.20 — adjusting future estimates.
```

Why "adjusting future estimates" rather than "8 min over" or "60% over":

- **Frames the miss as the system working, not failing.** The JSONL exists precisely so estimates self-correct. The postfix makes that visible at the moment it earns its keep — first time the user sees it, they realise the tool actually does what it claims about silent improvement.
- **Direction-neutral.** Over and under both trigger the same phrase. Without symmetry, over-runs feel apologetic and under-runs feel undeclared — its own subtle trust problem.
- **Future-tense focus.** "8 min over" anchors on the deviation; "adjusting future estimates" anchors on what comes next. The user is more interested in tomorrow's run than in this one being slightly off.
- **Honest if and only if we are adjusting.** The cohort lookup using local rows means a notable run does shift the median. The postfix only fires when the run row is going to materially change the next forecast — which is exactly when it's true.

**Threshold for "notable":** the same ~10% gate used elsewhere in the design (loudness threshold, cohort-fallback decision). Cost can use a slightly looser threshold than time (the user planned around the time number; they didn't plan around the cost number to the same degree). Worth tuning empirically.

**Verbose mode** (`--verbose`, disclosure-overlay) shows the full reconciliation regardless: `Done in 53 min (estimated ~45 min). Cost ~$5.40 (estimated ~$5). Adjusting future estimates.` — the engineer-curious user gets the whole story; the App Store user gets the calibrated headline.

#### Step count is the honest fallback when time is unknown

Per Microsoft's step-indicator guidance and the `tqdm` / Databricks Jobs UI convention: when time is genuinely unknown — first run with a niche local model, hardware we've never seen, etc. — show **`step 8 of 12: clustering quotes`** instead of fabricating a number. This is not a fallback to apologise for; it is the primary mode when data is thin, and it has two virtues over a fake-precise time estimate:

- **It can never revise upward.** "8 of 12" is monotone by construction. Harrison's failure mode is impossible.
- **It still answers Maister #4** (uncertain waits feel longer than known) — the user knows the operation is finite, knows where they are in it, and knows it's progressing.

A run starts in step-count mode and progressively earns time precision as data accumulates:

```
First run on this hardware:
  Step 1 of 12: ingesting files...
  Step 5 of 12: identifying speakers... (cohort thin — no time estimate yet)

Second run (now have one data point):
  Step 5 of 12: identifying speakers — ~15 min remaining (rough)

Settled (≥3 runs):
  Step 5 of 12: identifying speakers — 12 min remaining
```

The step count never goes away; it lives alongside the time estimate when both are available, and stands alone when only it is.

#### Same data, two consumers: pre-run forecast and progress bar

The wall-time data has two consumers that have historically been separate:

1. **Pre-run forecast** (this design): "before I press Run, how long will it take?"
2. **Progress bar** (existing [bristlenose/timing.py](../bristlenose/timing.py)): "how much longer is this run going to take?"

Both want the same thing — per-stage time estimates keyed by `(stage_id, ..., hardware_signature)`. `timing.py` already implements Welford's online-variance over a hardware-keyed history; this design folds that work into the same `Estimate` shape rather than duplicating. After this lands, `timing.py` becomes the progress-bar consumer of the per-stage `Estimate` objects produced by the same lookup the pre-run forecast uses.

**Avoiding jumpy progress bars** (Harrison's failure mode). The naive approach — read a budget per stage, show linear progress within, jump-cut at boundaries — produces upward revisions when a stage overruns. Mitigations:

- **Cumulative budget, not per-stage.** The bar shows time remaining across the whole pipeline. Stage transitions don't reset progress; they're just where the slope can change.
- **The displayed number holds.** Set at run start to P75 of the cohort, it doesn't budge until the run completes or until we have to explicitly say "this is taking longer than the original ~45 min estimate." See §Time display for the rationale — the user organised their plan around the number; we don't move it under their feet, in either direction.
- **Stages are implementation detail.** User-facing display reads `"~12 minutes remaining — merging transcripts"`, not `"stage 5b: 30s left of 30s estimated."` The label is human (Maister #5: explained > unexplained); the time is the cumulative remainder.
- **Same hardware signature, same cohort.** A user on M2 sees their M2 history; on a borrowed M5 they see whatever M5 data exists (likely shipped baseline → first-run actuals → tightening).
- **Step count always available alongside.** When time is settled: `"Step 8 of 12: ~12 min remaining"`. When time is thin: `"Step 8 of 12: clustering quotes"`. The step count is the always-honest spine.

#### Aggregating across stages

A run is N stages × M sessions. Per-stage estimates are computed independently per axis, then summed within axis:

```
for axis in ("usd", "wall_seconds"):
    known   = [e[axis] for e in per_stage if e[axis].value is not None]
    unknown = [e for e in per_stage if e[axis].value is None]
    total   = sum(a.value for a in known) × n_sessions
    precision = min(a.precision for a in known)  # weakest known stage
```

The two axes report independently. It's normal for one axis to be settled and the other unknown — e.g. user just swapped s10 from Sonnet to Apple FM: cost axis stays settled (we know what s10-on-Apple-FM costs: nothing), time axis goes unknown (we've never seen this user's hardware run Apple FM).

Display surfaces both axes side-by-side and flags any stage that's unknown on either axis:

```
All stages settled on both axes:
  ~30 min, ~$5.70  (47 runs of this configuration)

All stages have shipped baselines, no local data:
  ~30 min, ~$5  (rough first-time guess — improves with use)

Time axis settled, cost axis split — partial cost known:
  ~30 min, ~$4 known plus s10 cost unknown (first run with apple-fm@macOS-26)

Both axes have unknowns:
  Time and cost unknown for this configuration on this machine.
  Actuals reported as the run completes.
```

#### Cost display rounding (same at all three moments)

Two significant figures, ever, with a leading tilde to signal approximation:

| Sample count | Format | Examples |
|---|---|---|
| N ≥ 3 | 2 sig figs | `~$5.70`, `~$47`, `~$470`, `~$0.42` |
| N < 3 or shipped only | 1 sig fig | `~$5`, `~$50`, `~$0.40` |
| sub-cent | 4dp | `~$0.0042` |

The absence of pennies on a rough estimate is the message. `~$5` says "we know it's a fiver, not fifty"; that's the resolution that matters.

#### Time display: pad up front, narrow as you go, never visibly revise upward

Cost rounds to median; time pads to a percentile. The asymmetry comes from Harrison's empirical finding (UIST 2007, CHI 2010): **users tolerate slow-but-monotone bars; they hate upward revisions.** Median-based time forecasts under-promise half the time by construction — exactly the failure mode that erodes trust. So:

- **Pre-run time estimate uses P75 of the cohort** (not median). "We'll be done by ~45 min" is a budget, not a wish. Beating it is positive surprise; missing it requires explicit acknowledgement, never silent extension.
- **Padded point, not a range.** Show `~45 min`, not `~30–45 min`. Users plan discretely, not continuously — they commit to a return time and organise around it. A range invites optimising around the lower bound ("maybe I'll be back early") which is exactly the watched-kettle anti-pattern: they return too soon, watch the last 15 minutes of the bar, and feel worse than if they'd stayed at lunch. The point estimate is the time the user organises *around*; the system makes the planning decision for them. Harrison (UIST 2007) suggests ranges as one mitigation for upward revisions; we use the padded-point variant of the same idea instead.
- **The asymmetric-revision-tolerance gradient.** Not all revisions are equal. The user's emotional response runs:

  | Revision | User feels |
  |---|---|
  | Small downward (`~45 min` → `~40 min`) | gift, ahead of schedule |
  | Large downward (`~45 min` → `~15 min`) | "the original number was a lie" — trust collapses |
  | Any upward (`~45 min` → `~50 min`) | betrayal, broken promise |
  | Bidirectional bouncing | noise, user learns to ignore the number |

  So the rule is sharper than "don't revise upward": **hold the number almost always; if you must change it, only down, only a little, never both ways.** Aggressive recomputation is the enemy. The default is hold; revision is the exception with explicit conditions.
- **When uncertainty is high, stay coarse — don't fake precision.** `~3 hours` held steady is more trustworthy than `2h 47m` that drifts. If the cohort is thin, accept the wider rounding — it's the honest signal that we don't know better, and the user's plan ("done before tomorrow morning") doesn't need finer than that.
- **Cost stays at median.** No perceptual cost to spending $4.20 instead of $5.70 — the user isn't waiting on the cost. The asymmetry only matters for time.

#### User planning units, not rounding precision

The buckets in the pre-run forecast table aren't arbitrary precisions; they're the discrete plans humans make. Worth naming them as such because the design serves the plan, not the number:

| User plan | Estimate band | Decision |
|---|---|---|
| "Get a coffee" | < 10 min | wait at desk-ish |
| "Coffee shop / a quick errand" | 10–25 min | step away, come back |
| "Get lunch" | 25–75 min | leave the building |
| "Done by my afternoon meeting" | within working hours | start it now, plan the rest of the day around it |
| "Tomorrow morning" | overnight | go home, leave the lid open if Mac |
| "Worth watching the last minute" | < 1 min | see §Watchable countdown below |

The system serves the plan: the displayed number is the time the plan commits to. Engineers' instinct ("but the *real* uncertainty is wider!") serves their mental model, not the user's. We commit on the user's behalf and accept the engineering pressure of getting the commit right.

#### The watchable countdown — Artemis logic

The last minute or so of any long-running operation is a different UX moment from the rest of it. NASA's Artemis launches make the principle vivid: the nerds watch from the night before; the keenly interested turn on the TV an hour out; 99% of the audience joins for the last minute, and when the announcer reaches `10, 9, 8, 7…` they say it along. The countdown is participatory ritual, not just timekeeping.

Bristlenose's in-run UX has the same structure already (see §Layout):

- **Night before / hours out** — disclosure triangle expanded, CLI tail visible, full firehose. The engineer-curious user.
- **Hour out / general background** — ambient default, glance at the strip occasionally. Most users, most of the time.
- **Last minute** — should reward attention. The user who chose to watch the end deserves a UX moment that says "this is the bit worth watching."

What that means concretely:

- The bottom strip's time number can grow slightly more prominent in the last ~60 seconds (visual weight, not blink/animate — calmly assertive).
- The shoal can begin a slow convergence pattern in the last ~30 seconds, ending with all boids settling into a final formation as the run completes. Maps to Reynolds' `arrive` steering behaviour — already in the v0.1 archive's `AliveFlocking`.
- Cascade startles can ramp slightly in the final stretch, telegraphing "almost there" without a modal toast.
- Resist 10-9-8-style countdown styling — it's twee in a productivity tool and reads as gimmick. The principle is *attention reward*, not *visual countdown*.

This isn't extra scope; it's the principle that the in-run UX should *recognise* the last-minute moment as different from the rest of the run. Implementation rides on the same data layer (we already know when remaining < 60s).

**Pre-run forecast — qualitative buckets, never seconds.** The user is making a "what do I do with the next bit of the day?" decision; second-precision is false confidence. Match the bucket the user actually plans against:

| Forecast | Display | Bucket |
|---|---|---|
| > 3 hours | `3+ hours` or `overnight` | fire and forget; leave the lid open |
| 1–3 hours | `~2 hours` (nearest hour, or `~1.5 hours` for 1¼–1¾) | plan around it |
| 30–60 min | `~45 min` (nearest 5 min) | go for lunch |
| 10–30 min | `~15 min` (nearest 5 min) | back at desk soon |
| 5–10 min | `~6 min` (nearest minute) | grab a coffee |
| 2–5 min | `~3 min` (nearest minute) | wait at desk |
| < 2 min | `~90 sec` (nearest 10 sec) | watching |

**In-run countdown** — precision tightens as the remainder shrinks (the *cone-of-uncertainty* pattern from project estimation, applied to one run). The "watched kettle" phase wants finer numbers exactly when the user is most impatient:

| Remaining | Format | Examples |
|---|---|---|
| > 3h | `3+ hours` (don't false-precise the long tail) | `3+ hours`, `overnight` |
| 1h–3h | nearest 30 min | `~2h 30m`, `~1h 30m` |
| 10m–1h | nearest 5 min | `~45 min`, `~15 min` |
| 5m–10m | nearest minute | `6 min`, `8 min` |
| 2m–5m | nearest 30 sec | `3m 30s`, `4m 0s` |
| 30s–2m | nearest 5 sec | `1m 35s`, `45s` |
| < 30s | nearest second | `15s`, `10s`, `5s` |

The transitions between bands are the important part — the user sees the bar's precision *increase* as it approaches done, mirroring their own focus.

**Tilde drops at high precision.** `~3 hours` (rough) but `15s` (specific). The tilde signals "rough"; once we're showing seconds we're not rough anymore.

**Time unit picks itself:** < 90 s → seconds, < 90 min → minutes, otherwise hours-and-minutes. Avoid mixed units except for hours+minutes in the 1h–3h band where it materially helps ("2h 30m" vs "150 minutes").

**Leave-the-lid-open hint** for forecasts or remainders > 1 hour on Macs:

```
~3 hours, ~$5  (long run — leave the lid open if on a Mac)
```

Macs sleep on lid close by default; long local runs need `caffeinate` or an explicit Energy Saver setting. Worth a hint in the display, not just docs.

### History scope and shipped baselines

Cohort lookup reads **only the current project's** `.bristlenose/llm-calls.jsonl`. No cross-project scan, no machine-wide aggregation. Each release ships `bristlenose/llm/cohort-baselines.json` covering the cohorts the maintainer can pre-calibrate against (cloud providers + standard Ollama tags). On-device cohorts (Apple FM, MLX, user-pulled Ollama, custom Azure deployments) inherently lack shipped baselines — they enter `basis = "none"` until local rows accumulate.

**Why shipped baselines are safe here.** Prompts and shipped baselines move together — a release that bumps `prompt_version` also re-runs FOSSDA and ships an updated `cohort-baselines.json`. The user always receives the prompt version and its calibration atomically; the "theme → themes" trap can't bite a user, only a maintainer who forgot to re-baseline before tagging. A CI gate enforces freshness (see Implementation).

**Retention.** Per-project JSONL caps at the **last 1,000 rows** by default (configurable via `BRISTLENOSE_LLM_CALLS_RETAIN`). On exceeding, file is rewritten dropping oldest rows.

### Scope discipline: number first, narrative behind `--verbose`

The default display surface (CLI summary line, desktop bottom strip) shows **a number, never a narrative.** State-appropriate precision and rounding handle most of the user's information need. Comparative narratives ("you've previously run with Sonnet, Haiku is cheaper…") belong behind `--verbose` mode and the disclosure-triangle CLI tail, not the default surface.

The reason: the only user-visible config changes that exist today are explicit user-initiated acts — `--llm` provider swap, `bristlenose configure <provider>`, hardware migration. Each is intentional; the user knows they changed something. A different number in response is enough signal that the system noticed. They don't need a sentence telling them what they just did.

When per-stage backend selection ships (post-Phase-4, downstream of [design-stage-backends.md](design-stage-backends.md)), the comparative narrative becomes more useful because the surface area for accidental config divergence widens. That's the right time to design it against the actual UX. Until then, the elaborate "Anchored" comparative state is a `--verbose`-only feature; the default state machine is `Settled` / `RoughFirstGuess` / `Unknown` only.

**Threshold logic still applies to state decisions, not narrative.** If a config change affects <10% of the run total on both axes, the existing cohort's median is reused (the change is in the noise floor of normal run-to-run variance). Above the threshold, the affected stage falls back to `RoughFirstGuess` or `Unknown` for that stage. Either way, the default surface just shows a number; the threshold gates *which* number, not whether to narrate.

### Function shape

```python
def estimate_pipeline_cost(
    n_sessions: int,
    stages: list[StageDispatch],   # (stage_id, prompt_template, model_response)
    project_history: Path,
    shipped_baselines: dict[CohortKey, BaselineTokens],
) -> RunForecast:
    """Per-stage Estimate, plus aggregated run total + display string.

    Aggregation rule defined in §Architecture: known sum + unknown stages
    surfaced explicitly; precision = min across known stages.
    """
```

The hardcoded `_TOKENS_PER_SESSION` constant at [bristlenose/llm/pricing.py:51](../bristlenose/llm/pricing.py:51) is removed. Its replacement is `cohort-baselines.json`, computed empirically from FOSSDA runs at release time. Tests that need a deterministic number construct an `Estimate` directly.

Return both a point estimate and a range:

```
"based on 47 similar runs: $0.90 – $1.50 (est., median $1.20)"
```

When low-confidence:

```
"~$1.50 (est., calibration data thin — confidence will improve after a few runs)"
```

### Cohort dimensions

See §Architecture above. Cohort key is `(stage_id, prompt_id, prompt_version, model_family, model_major)`. Snapshot dates, hardware, transcript length, language, and time-of-day all drop out of the key by deliberate design.

### Prompt versioning: explicit frontmatter, not implicit hash

Every prompt in `bristlenose/llm/prompts/*.md` carries YAML frontmatter:

```markdown
---
id: extract_quotes
version: 0.4.2
---

# Quote extraction prompt
...
```

- **`id`** — stable name. Survives file moves and renames.
- **`version`** — semver, bumped by the human writing the prompt whenever the change is meaningful (i.e. always — accidental whitespace edits aren't a thing in practice; prompts are rewritten deliberately).
- **`prompt_template_sha`** — kept in the schema as an integrity backstop. A unit test fails if file content changed but `version` didn't bump. Catches the "I tweaked it but forgot to bump" case.

The cohort key is `(stage_id, prompt_id, prompt_version, gen_ai.response.model)`. SHA is observability only.

**Why version is the primary cohort key, not SHA:**

- Lets the user grep "show me cost over time for `extract_quotes` across versions" — the analysis they actually want when iterating on prompt quality.
- A prompt rewrite from `"find themes"` to `"find themes relevant to professors of old English, sorted by citation count"` is *deliberately* more expensive. The cohort *should* split. The forecast *should* say "0 prior runs of v0.5.0, falling back to baseline" until 5 runs accumulate. Honest > clever.
- Quality and cost are separate questions. Versioning the prompt lets both be answered: "did v0.5 cost more than v0.4?" (this telemetry) and "did v0.5 produce better themes?" (separate eval, can join on the same `prompt_version` field but is out of scope here).

**Implementation note.** Frontmatter parsing is small: regex to split header, `yaml.safe_load` on the YAML block. PyYAML is already a transitive dep (verify before assuming). Or hand-roll 10 lines — only two fields to parse. Add a `PromptTemplate(id, version, sha, body)` dataclass that loaders return. Replaces the current "stages read .md files and concatenate strings" pattern.

**Discipline backstop.** A unit test walks `bristlenose/llm/prompts/`, computes SHA per file, asserts that for each file in the repo's working tree, `(filename, version, sha)` matches a known good triple in a `prompts.lock` file (regenerated on each version bump). Without this, version drift goes silent.

### Cost calculation: actual vs predicted

The "actual" cost in the JSONL is still an estimate — provider billing has invisible adjustments (cache discounts, batch tiers, custom contracts). Keep the `cost_usd_actual_estimate` naming. Never write `cost_usd_actual` — it would be a lie.

The delta `cost_usd_actual_estimate - cost_usd_predicted` is the residual. Useful aggregations:

- median residual per cohort → systematic bias signal
- residual SD per cohort → cohort tightness; high SD means split further
- residual time series → calibration drift after a prompt rewrite

These are all post-hoc queries against the JSONL. No live aggregation.

### Local-first considerations

- The JSONL stays on the user's machine. Same posture as `pipeline-events.jsonl`.
- No automatic upload, no phone-home.
- The forecast lookup reads only from the local user's history. We do not pool across users.
- If we later want anonymous opt-in telemetry to improve the bundled defaults, that's a separate design (alpha-telemetry Phase 2+, see `docs/private/road-to-alpha.md` §13b).

## Known pitfalls (lifted from postmortems)

These are the mistakes that have already been made publicly. We get to skip them.

1. **Retry double-counting.** Log only on terminal outcome, not per attempt. Bristlenose's local-model retry path (3× exponential backoff in `_analyze_local`) must not emit three rows for one logical call. **However:** if attempt 1 hit the API and only failed at JSON parse, the user paid for those tokens. **Decision:** sum tokens and `elapsed_ms` across all attempts into the terminal row, surface `retry_count` so wasted spend is visible. Lying about cost to keep the writer simpler is not acceptable.
2. **Streaming usage arrives at the end.** `usage` is null until the final chunk. If we ever stream, span ends on final chunk; attributes set then.
3. **Cache hits skew predictions.** Split `cache_read_input_tokens` and `cache_creation_input_tokens` from raw input. Anthropic reports both; OpenAI reports cache reads via a separate field on their newer SDKs.
4. **PII in prompt hashes.** Hash the template, not the rendered prompt. Documented above; aligned with Bristlenose's PII boundary discipline (`docs/design-export-html.md`, anonymisation section).
5. **Model alias drift.** `claude-3-5-sonnet-latest` is unstable. Always log `gen_ai.response.model` from the response, not the request.
6. **Tools/functions count toward input.** Tool definitions add 5–15% to input tokens, easy to miss in pre-call estimates. Bristlenose doesn't use tools today, but if we ever add them this matters.
7. **Local Ollama may report zero usage.** The OpenAI SDK wrapper around Ollama sometimes doesn't surface usage. Compute from the tokenizer if the response field is missing/zero, mark `usage_source: "computed"` vs `"reported"`.
8. **Truncated calls are real spend.** Don't filter `outcome=truncated` rows out of the cohort; they're the calls that hit `max_tokens`. Filtering them biases the cohort low.
9. **Azure deployment names ≠ model names.** Azure cost estimation already returns `None` for unknown deployments (see [bristlenose/llm/pricing.py:42](../bristlenose/llm/pricing.py:42)). The telemetry row should still be written with `cost_usd_actual_estimate=null` and a flag — token counts are still useful even when cost lookup fails.

## Implementation phases

The original problem is **"can we estimate cost honestly?"** — the hardcoded constant has been wrong for two months. Time falls out of the same data layer as a near-free second axis. The in-run UX layout and the shoal revival sit on top, much later.

### Phase 1 — Cost telemetry + cost forecast (the original brief)

Done criteria: the hardcoded `_TOKENS_PER_SESSION` is gone. Cost forecast uses real captured data. Out of the box it's no worse than today's constant. After ~5 runs it's measurably better and improves silently.

Scope:

- **Schema + writer.** `LLMCallEvent` Pydantic model with OTel-aligned field names. `bristlenose/llm/telemetry.py` with `record_call()`. Per-run file `<output_dir>/.bristlenose/llm-calls-<run_id>.jsonl` using `events.py`'s exact write primitives (`O_APPEND | O_NOFOLLOW | 0o600`, single `os.write()` per row).
- **Plumbing.** `contextvars` for `run_id` and `stage` set by the pipeline runner; `LLMClient.analyze()` reads them. Existing CLI log line stays for humans; structured row is the new datum.
- **Retry handling.** Sum tokens across attempts in `_analyze_local`'s retry loop; emit one terminal row with `retry_count` surfaced. Don't double-count.
- **Prompt versioning.** YAML frontmatter (`id`, `version`) on every `bristlenose/llm/prompts/*.md`. New `PromptTemplate(id, version, sha, body)` dataclass. `bristlenose/llm/prompts.lock` with `(filename, version, sha)` triples + unit test that fails if they drift.
- **Cohort normalisation.** `bristlenose/llm/cohort_normalise.py` — one tested function per provider mapping `response_model` → `(family, major)`. No hardware in cost cohort key.
- **Shipped baselines.** `bristlenose/llm/cohort-baselines.json` covering cloud cohorts only (Anthropic/OpenAI/Azure/Gemini at families known at release time). On-device cohorts get `basis="none"` until local data accumulates.
- **Release ritual.** `scripts/regenerate-cohort-baselines.py` reads a maintainer's FOSSDA-run JSONL and writes the JSON. CI gate fails if `prompts.lock` and `cohort-baselines.json` drift apart for cloud cohorts.
- **Forecast lookup.** `estimate_pipeline_cost()` returns per-stage `Estimate` (cost axis only this phase) → aggregated `RunForecast`. Local rows preferred; shipped baselines next; `none` otherwise. `_TOKENS_PER_SESSION` deleted.
- **Display.** 1–2 sig figs, leading tilde. CLI rendering of `Settled` / `RoughFirstGuess` / `Unknown` aggregate states — but not by name; just as numbers + per-stage flags.
- **Trust boundary.** Add `CLAUDE.md` gotcha line classifying `llm-calls.jsonl` as a re-identification key sibling to `pii_summary.txt`. Never in exports.
- **Tests.** `tests/test_llm_telemetry.py` — schema, retry-summing, missing-usage, contextvar isolation, file mode `0o600`/`O_NOFOLLOW`, cohort N<5 / N≥3 / N≥5, lockfile drift.

Estimated weekend.

### Phase 2 — Time forecast (data is already there)

Done criteria: pre-run forecast displays both cost and time side-by-side. CLI shows `~30 min, ~$5.70`. In-run progress shows time-remaining countdown that holds steady (per the displayed-number-holds rule).

Scope:

- **TimeCohortKey** = CostCohortKey + `hardware_signature`. New `bristlenose/runtime.py` for the coarse-signature probe (`darwin-arm64-M2-24GB` etc.).
- **Time data sources.** Per-call `elapsed_ms` (already in Phase 1's JSONL) + per-stage timestamps from `pipeline-events.jsonl`/manifest. Logic lifted from `scripts/perf-breakdown.py`.
- **P75 padding for time.** `Estimate.wall_seconds` uses P75 of cohort, not median. Cost stays at median.
- **Display rules.** Pre-run uses qualitative buckets (coffee/lunch/overnight). In-run uses cone-of-uncertainty rounding (precision tightens as remainder shrinks). Both axes side-by-side.
- **Hold-the-number contract.** Displayed time is set at run start and doesn't budge until completion or explicit overrun acknowledgement. Step count is the always-present spine.
- **`bristlenose/timing.py` refactor.** Becomes the progress-bar consumer of the same data layer rather than its own hardware-keyed history. Welford's online-variance preserved as the within-stage smoothing primitive; pre-run uses median, progress bar uses smoothed running estimate.
- **Step-count + activity label.** Step count and current-stage label always present, regardless of time-data state. Existing CLI runner output is the activity-label source.
- **Trust boundary update.** `hardware_signature` joins the re-id classification (already coarse, no extra mitigation needed).

Estimated weekend.

### Phase 3 — In-run UX layout (after first cohort feedback)

Done criteria: desktop app's in-run view is the ambient layout (full-screen flock placeholder, bottom strip, disclosure-triangle CLI overlay). The "watchable countdown" last-minute moment is recognisably different from the rest.

Scope:

- Bottom-strip composition (step count + time + activity + bar).
- Disclosure-triangle expand/collapse with `NSVisualEffectView` blur.
- Last-state-wins persistence.
- CLI tail overlay (existing CLI output, scrolled in a pane, pause-on-hover).
- Last-minute attention reward (subtle prominence change — not 10-9-8 styling).
- Accessibility (strip is the real progress UI; flock placeholder is decorative).

Static placeholder graphic in place of shoal. No new instrumentation needed; everything reads from Phase 2's data layer.

### Phase 4 — Shoal revival (post-alpha; the much-later layer)

Done criteria: the static placeholder becomes the Typographic Shoal. Pipeline events drive the progressive narrative reveal (words → sentiment → codes → sections → themes → signals). Cascade startles fire on stage completion.

Scope:

- Revive `desktop/v0.1-archive/.../Shoal/` Swift code into the v0.2 app.
- Wire `pipeline-events.jsonl` events to cascade startles + boundary effects.
- Progressive reveal mapping (per the table in §In-run UX).
- React/Canvas port for serve mode (later still — alpha is desktop-led).
- Profile-and-throttle path for GPU-saturated machines.

This is where the indie-vs-corporate positioning compounds. Worth getting right; not worth blocking the cost forecast on.

### Phase 5 — Empirical validation (runs alongside Phase 3 onwards)

Bristlenose dogfoods Bristlenose. Diary studies with alpha cohort, moment probes, instrumented in-run experience, A/B candidates if alpha volume permits. See §Psychology hypotheses. Not a build phase per se — a parallel research workstream that informs Phase 3 and Phase 4 sequencing.

### Explicit non-goals across all phases

- OTLP / OTel SDK integration. We adopt the *schema*, not the runtime. Adding the OTel SDK pulls a transitive dep tree we don't want.
- Cross-machine aggregation, opt-in telemetry upload. Belongs to alpha-telemetry Phase 2+, separate design.
- Real-time dashboards. The JSONL is queryable post-hoc; that's enough.
- Streaming-aware capture. We don't stream today.
- Penny-precise cost reporting. We round, deliberately.
- Hash chaining for SOC2 audit-trail integrity. Reserve `prev_row_sha` field name later if a procurement conversation requires it; not now.

## Decisions taken (was: open questions)

Resolved on review:

- **Per-call vs per-run cost reconciliation: independent, accept rounding.** It's an estimation; don't overthink. The terminus-cost in `pipeline-events.jsonl` stays the canonical user-facing number; per-call rows in `llm-calls.jsonl` are for analysis. They might disagree by pennies. Fine.
- **Prompt-template handle: full `PromptTemplate(id, version, sha, body)` dataclass.** YAML frontmatter on every prompt. Pattern B over Pattern A. Worth the ~6 call-site refactor — unlocks the cross-version analysis that's the whole point.
- **Architecture: configuration → estimate.** Single abstraction collapses what was previously several rules (cohort dimensions, model granularity, three-state forecast type, family-fallback). Cohort key is `(stage_id, prompt_id, prompt_version, model_family, model_major)`. Snapshot dates and hardware drop out of the key by design — your "ran 3, then 7 more next week" and "switched hardware, run 2 estimate is credible" cases work without special handling.
- **Shipped baselines per release.** Day-one estimates need them. Maintainer's job to set adequate expectations; system's job to refine silently. Atomic ship of new prompt + new baseline avoids the "stale baseline" trap.
- **Cohort invalidation: binary version bump.** Whitespace-normalisation is solving a problem we don't have. Prompts are written deliberately; edits are deliberate. Forget normalisation.
- **OTel: schema-aligned, not spec-bound.** Use the dotted field names. Don't commit to spec drift. If `gen_ai.usage.cache_*` diverges from whatever Anthropic ships, we'll cross that bridge.

Still open, not blocking:

- **Phase 1 alone or Phase 1+2 together?** Steelman for split: lets schema settle before forecast logic depends on it. Steelman for combined: writing JSONL nobody reads is dead weight. Probably combine — one weekend either way.
- **Hash chaining for SOC2/healthcare.** Reserve `prev_row_sha: null` field now for additive-migration later, or skip? Skip; the alpha audience is UX research not health-tech.
- **Tokencost dep.** Could replace the `PRICING` dict. Revisit when adding new providers.
- **`bristlenose forget <session_id>` erasure CLI.** GDPR Art 5(e). Out of scope here. JSONL design supports it (append-only doesn't block rewrite-on-erasure).
- **Tiny query CLI.** `bristlenose costs --by stage --by prompt-version`. v3 territory.

## In-run UX: the shoal as progressive narrative reveal

The data layer above gives the *number*. The number alone is not the whole answer to "how long?" — Maister #1 (*unoccupied time feels longer than occupied*) says we also need something to look at. But "fill the wait" is the weak version of this idea.

The strong version, and the one Bristlenose can credibly ship: **the wait IS the reveal.** As the pipeline progresses, the shoal renders the actual data emerging from each stage:

| Stage | What the shoal reveals |
|---|---|
| Transcribe | Words from the transcript drift into the flock as text-shaped boids |
| Speaker ID | Boids gain colour by participant |
| PII removal | Redacted strings dissolve and reform as `[NAME]`, `[ORG]` |
| Topic segmentation | The flock divides into sub-shoals along topic boundaries |
| Quote extraction | Quote-shaped boids leave the main flock and form a new pattern |
| Clustering | Sub-shoals merge by similarity |
| Thematic grouping | Theme labels coalesce as the shoal organises around them |
| Sentiment / signal concentration | Boids glow by sentiment; signal-dense regions brighten |

A user who looks away during the run misses nothing functional. A user who chooses to watch sees their study come into focus from raw transcript through quotes through themes through signals — a progressive disclosure of what the AI is finding. The wait becomes a moment of curiosity and small joy, not a chore.

That's the design ambition. It draws on existing prior art:

- **Code:** `desktop/v0.1-archive/Bristlenose/Bristlenose/Shoal/` — five Swift files, three runtime-switchable behaviours (ClassicFlocking → AliveFlocking → AliveV2Flocking). Designed for the v0.1 pipeline-processing view; didn't survive the v0.2 rewrite. Reviving rather than building from scratch.
- **Bibliography:** [docs/bibliography-flocking.md](bibliography-flocking.md) — Reynolds 1987 (boids), Ballerini 2008 (topological neighbours), Attanasi 2014 (cascade startle as information-transfer wave), Herbert-Read 2011 (mosquitofish), Potts 2022 (boldness spectrum, scale-free cascades).
- **Mechanics that map to pipeline events:**
  - **Cascade startle** as stage-completion signal — a stage finishing ripples through the flock as a directional shift, rather than a modal "STAGE 5 DONE" toast (Maister #5: explained > unexplained, but ambient).
  - **Topological neighbours** rather than metric — sub-shoals form and merge naturally as data clusters, mirroring the actual cluster→theme analysis.
  - **Boldness/curiosity cycle** — organic variation between events, so the user never feels time has stopped.

### Why this is plausibly an indie competitive advantage

Worth recording as positioning context. Corporate research tools (Dovetail, Hey Marvin, Condens, etc.) are unlikely to ship something like this. A flocking-data reveal is hard to defend in a corporate review:

- It costs engineering time without serving a clear "feature" line on a comparison grid.
- It's expressive in a way that reviewers worry about — "what if a customer thinks it's frivolous?"
- Quality bar is judged subjectively, not measurably; harder to QA against a checklist.
- "We built a better progress bar" doesn't pitch as well as "we added X integrations."

An indie product survives the cost-benefit conversation differently. The shoal is exactly the kind of thing Bristlenose can ship and Marvin cannot — and that asymmetry is a moat that doesn't appear on any feature-comparison grid but contributes to the felt quality of the product. Researchers who've sat through a Bristlenose run remember the moment their themes cohered out of the flock; that memory is hard to compete with via spec-sheet feature parity.

This positioning point matters for sequencing: the shoal is not "polish to add at the end." It's a load-bearing piece of the product's emotional reason-to-exist. Worth getting it back into the desktop app early in the alpha, with a parallel React/Canvas implementation tracking it for serve mode.

### Engineering risk: low

The shoal looks expensive but isn't, because of where the real work happens. In ~99% of alpha-realistic runs:

- The dominant LLM stages (s10 quote extraction, s11 clustering, s12 theming) execute **on the provider's hardware**, not the user's. The user's machine is HTTP-blocked, mostly idle. Sprite rendering on the local GPU is essentially free.
- The non-LLM stages that do hit local hardware (transcribe via MLX Whisper, possibly s10 on MLX or Apple FM for a small future cohort) use the **Neural Engine + Metal compute**. SpriteKit uses Metal render. They share the GPU but at different pipeline stages, and even on M2 a few hundred boids is sub-1% GPU utilisation. Won't dent transcribe time.
- The CPU-bound stages (PII redaction, deterministic clustering) don't touch the GPU at all. Shoal contention is zero.

The corner case is M1/M2 users running large local LLMs (e.g., Llama 70b on MLX) where GPU is genuinely saturated — a smaller cohort even within the on-device user set. The mitigation is a profile-and-throttle path: measure GPU contention once, drop the shoal to reduced-quality mode (fewer boids, lower frame rate, or paused) if it meaningfully slows pipeline progress on this machine. Implementation detail; not a design blocker.

So the engineering risk profile is: free for the cloud-LLM path that dominates alpha, free for CPU-bound stages, near-free for typical local hardware, throttleable for the rare GPU-saturated case. Corporate decision-making would pattern-match "fancy animation = risk"; the actual cost is below the noise floor of the work being waited on.

### Layout

The in-run view has two states. Default is calm and ambient; one click for the firehose.

**Default — ambient:**

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│                                                              │
│                                                              │
│              [ full-screen Typographic Shoal ]               │
│                                                              │
│                                                              │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ ▶ Step 8 of 12 · ~12 min remaining · clustering quotes  ████ │
└──────────────────────────────────────────────────────────────┘
```

The bottom strip carries the four signals from the data layer above, in one line, always visible:

1. **Step count** (`Step 8 of 12`) — the always-honest spine.
2. **Time remaining** (`~12 min remaining`) — cone-of-uncertainty rounding (this design's §Time display rules).
3. **Activity label** (`clustering quotes`) — the same currently-running line the CLI's Cargo/uv-style runner already produces in `bristlenose/timing.py`. Reused, not reinvented.
4. **Visual bar** — driven by step count (always determinate), not time (avoids Harrison's upward-revision trap).

The **▶ disclosure triangle** at the start of the strip is the only interactive element in the default state.

**Expanded — disclosure triangle clicked:**

```
┌──────────────────────────────────────────────────────────────┐
│ ▼ Step 8 of 12 · ~12 min remaining · clustering quotes  ████ │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   ✓ ingest                          0.4s                     │
│   ✓ extract audio                   9.4s                     │
│   ✓ transcribe                  17m 21s                      │
│   ✓ identify speakers             39.5s                      │
│   ✓ merge transcript               <0.1s                     │
│   ✓ topic segmentation            35.9s                      │
│   ✓ pii removal                   12.3s                      │
│   → quote extraction (8 of 10 sessions, 4m 12s elapsed)      │
│   ⋯ cluster_and_group                                        │
│   ⋯ thematic grouping                                        │
│   ⋯ render                                                   │
│                                                              │
│           [ shoal blurred + at 35% opacity behind text ]     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

The text overlay is the live CLI tail — same content as `bristlenose run` produces in a terminal. Latest line at the bottom, history scrolls up. Pause-on-hover (nobody else does this; Bristlenose can). Click the disclosure (now ▼) to collapse back to ambient.

The shoal continues animating behind the text. `NSVisualEffectView` with `.behindWindow` material handles the blur natively (HIG-compliant, dark/light auto, GPU-cheap). Opacity 35% — low enough not to compete with the text, high enough that cascade-startle ripples on stage completion still register peripherally. The Reynolds wander behaviour gives enough sustained motion that the ambient sense doesn't vanish at low opacity.

**State persistence.** Last-state-wins: if the user expanded the overlay last run, default to expanded next run. No preference setting; respect the last gesture. Standard macOS document-state behaviour.

**Accessibility.** The shoal is decorative — AppKit `accessibilityElement = false`, AX-hidden. The bottom strip is the real progress UI, fully labelled (step count read as `"step 8 of 12"`, time remaining read as `"about 12 minutes remaining"`, activity as `"currently clustering quotes"`). The CLI overlay is a log region with auto-announcing of new lines (rate-limited to avoid screen-reader spam — once per stage transition is enough).

**Multi-project layout — out of scope for this doc.** Alpha shows one project's run at a time. When multiple-projects-processing lands as a desktop feature, the layout questions (sidebar list? per-project window? tabbed?) are downstream of this design.

This design doc owns the data layer (per-stage Estimate, two cohort keys, three UX moments). The shoal revival and the layout above are downstream desktop-app work, called out here because the in-run number alone is not the whole answer to "how long?" — and because the shoal is what turns the wait from a friction into the experience.

## Relationship to per-stage pluggable backends

This design is a direct dependency for [design-stage-backends.md](design-stage-backends.md), and pre-emptively answers a question that doc explicitly defers:

> *"LLM seconds is a cost proxy, not a cost. Real $ depends on input vs output token ratios, which vary wildly by stage. To get truth, `LLMClient` needs to emit token counts — cheap to add, deferred."*

This telemetry **is** that work. Once `llm-calls.jsonl` exists, [scripts/perf-breakdown.py](../scripts/perf-breakdown.py) — which today bucket-attributes free-text `llm_request | elapsed_ms=...` log lines into stages by timestamp — gets a structured input with token counts, exact cohort keys, retry counts, and outcome already attached. The "LLM seconds is a proxy" caveat goes away.

**Cohort design holds under per-stage backends without modification.** The pluggable-stages doc anticipates a single pipeline run producing calls against multiple `(stage, model)` combinations — Claude for s11/s12, MLX for s10, Apple Foundation Models for s08. Our cohort key `(stage_id, prompt_id, prompt_version, gen_ai.response.model)` already partitions on stage and model. A run with three different backends produces rows in three different cohorts; the forecast sums across them naturally.

**On-device backends start with `basis = "none"` (no shipped baseline).** Apple FM, MLX, and user-pulled Ollama models lack shipped baselines because the maintainer can't pre-calibrate against hardware they don't own. Token counts on these backends only depend on the model+prompt, not the hardware (the tokenizer is the same on M2 and M5), so a single user run is enough to populate the local cohort and drop the user from `basis="none"` to `basis="local"` with a 1-sig-fig estimate. After three runs the display tightens to 2 sig figs. This handles your "switched hardware, run 2 estimate is credible" case without special-casing.

**The JSONL is the substrate for the per-stage benchmark.** [design-stage-backends.md](design-stage-backends.md) frames the s10 spike as "a re-runnable benchmark we re-measure each quarter, at WWDC, at each Claude generation, at M5 availability." Every Bristlenose run on a maintainer's machine, on a beta tester's machine, in CI, and (eventually, opt-in) anonymised across users adds rows to that benchmark. By Apr 2027 the dataset is the answer to "did the per-stage architecture earn its keep?" — measured, not argued.

**Manifest visibility for quality drift.** The pluggable-stages doc flags that "the report now depends on which Mac it ran on" and the manifest must record `"s10: claude-opus-4-7; s08: apple-foundation-models-3b"`. This telemetry's per-call rows already hold that exact information; the manifest writer can derive its per-stage backend record from the JSONL rather than tracking it separately. One source per fact.

**What this design defers to the per-stage doc:** the `BackendResolver` itself — the runtime decision of which backend handles which stage on this host with this user preference. The cost forecast assumes the resolver has already chosen by the time the forecast runs (so it knows `gen_ai.request.model` for each stage). Wiring the forecast into a UI that shows alternative-backend cost comparisons ("running s10 on MLX would be ~$0.10 vs ~$0.40 on Claude") is downstream of both docs landing.

## Psychology hypotheses we're betting on (mostly without evidence)

The maths in this design is real and interesting. Cohort sizing, percentile selection, smoothing windows, drift detection, when to prefer median over mean over trimmed-mean — none of these have single right answers; the engineering is properly hard. None of that is being dismissed.

The risk is more subtle: **engineers get absorbed in the tractable maths because they get traction there, and lose sight of the destination — which is the psychology of waiting.** The maths is the means. The psychology is the end. We picked P75 not because it's mathematically optimal but because of how humans react to broken promises. We hold the displayed number because users plan discretely. We round to qualitative buckets because users plan around lunch and coffee, not minutes. Each maths choice is an *answer* to a psychology question, and the psychology questions are the ones less validated for our context.

So this section names the psychology calls explicitly. They sit underneath the maths and are mostly plausible-but-untested.

Hypotheses we're committing to without validation. Each is plausible; none is empirically confirmed for this product or audience:

| Hypothesis | Source of confidence | What we don't know |
|---|---|---|
| P75 is the right padding for time estimates | Harrison + intuition | Could be P70, P80, P85, P90. Unknown what the marginal gain looks like. |
| Padded point > range for "lunch or coffee?" planning | Argued in §Time display from first principles | Untested. Some users may genuinely prefer the range and the autonomy. |
| Asymmetric revision tolerance (small ↓ = gift, large ↓ = lie, any ↑ = betrayal) | Plausible from common experience | Never measured for software-progress UI specifically. |
| The displayed number should hold steady, not glide-update with each completed stage | Extrapolated from Harrison's revision-aversion | Untested. Glide-update may feel responsive rather than nervous. |
| Last-minute attention reward (the Artemis moment) is a real UX gain | Aesthetic intuition + analogy | No empirical test in productivity-tool contexts. |
| The shoal-as-narrative-reveal is delight, not distraction | Aesthetic intuition | The opposite is also plausible — could feel gimmicky to some users. |
| Step-count + time-number > step-count alone or time-number alone | Convergence of `tqdm` + Microsoft + intuition | Untested for our specific audience and run-length distribution. |
| Maister's 1985 principles transfer to single-user software in 2026 | Service-encounter literature | Maister studied multi-person queues; transfer is plausible but not proven. |
| Users will tolerate `unknown` cost / time states as honest, not unfinished | Argued from "no estimate beats wrong estimate" | Untested. Some users may read `unknown` as "the tool is broken." |
| The buckets at 10 / 25 / 75 / 240 / overnight are the right break points | Folk psychology / personal observation | Untested. Real human break points may be culture-specific or task-specific. |

This is more "we don't know" than the rest of the doc admits.

### Test these with the alpha (Bristlenose dogfoods Bristlenose)

The alpha is the natural test substrate. We have a small, identified, willing-to-be-interviewed user base in the alpha cohort and a tool for analysing the resulting interviews. The recursive loop is genuinely available: run user interviews about the experience of running Bristlenose, drop the recordings into Bristlenose, analyse them with Bristlenose, learn how to improve Bristlenose. That's the kind of thing competitors can't credibly do — most user-research tools are not themselves the subject of user research.

Concrete proposals (out of scope for this doc to schedule, but worth naming):

- **Diary-study questions** for alpha cohort: "Tell me about the last long Bristlenose run. What did you do during the wait? Did you check on it? Did the time estimate match what happened? How did you feel when it finished?"
- **Specific moment probes:** Did the number ever change while you were watching? How did that feel? Did you ever come back early because the bar looked close to done? Did you ever stay watching the end?
- **Eye-tracking or screen-recording** during the in-run view (with consent). Does anyone actually look at the shoal? Does the strip get glanced at, or do users tab away entirely?
- **A/B candidates** if/when we have enough alpha volume: P75 vs P80 padding; padded-point vs range display; with-shoal vs minimal-spinner (control); last-minute prominence vs flat.

We are designing for a small, professional, articulate audience that knows how to give good feedback. We should ask. The answer is unlikely to be "every hypothesis above was right"; it might be "two were dead wrong and one we didn't expect mattered most."

### Lessons from MAAS (and similar)

Concrete prior art from real-world infrastructure: Canonical's MAAS (Metal as a Service) provisions whole data centres — long-running processes spanning hundreds of physical machines, with every realistic failure mode and uncertainty. The MAAS engineering team was rightly worried about predictions they couldn't keep. They were also not engaging with the psychology problem. The result: a retreat to "we're just going to have to tell the user they have to wait."

That's the engineer-rightness-as-unhelpfulness failure mode in pure form. Right that predictions could fail; unhelpful in declining to attempt them. The user's planning need didn't go away just because the engineering risk was real.

The deeper lesson from that experience: **the "simple" progress bar is the most expensive UI component to build correctly, because it's a downstream consequence of every upstream data choice.** If the pipeline doesn't capture the right data from day one, no amount of frontend cleverness rescues it. You can't bolt observability on after the fact and get a credible progress experience.

This is why the data-layer parts of this design (per-call JSONL, hardware signatures, prompt versions, cohort keys, per-stage timestamps in `pipeline-events.jsonl`) are load-bearing, not over-engineering. In isolation each looks ornamental. In aggregate they're the difference between "we can build a good progress UX later" and "we have to tell the user to wait." MAAS shows what the latter looks like at scale; we'd rather not relive it.

The recurring failure mode worth naming for any future contributor reading this: **being right about uncertainty isn't a licence to stop trying.** It's the brief.

#### The closing argument: retrospective instrumentation is never justifiable

There's a sharper, harder lesson from MAAS that's worth landing. The progress-bar problem there was never fixed retrospectively — not because nobody understood how, but because **by the time the cost was felt, the cost of fixing it was always greater than the political will to do so.** Years pass. The user is still tailing logs.

The window for adding upstream instrumentation closes the moment a project is big enough to need it. Once a codebase has thousands of contributors, hundreds of plugins, dependent customers, and a release cadence, "go back and capture per-stage timing data through every code path" stops being a weekend job and starts being a multi-quarter migration that always loses to the next priority. "We'll add it later" is how teams arrive at "this stays the user's problem forever."

Bristlenose has the choice MAAS didn't, but only briefly:

- The codebase is small.
- The audience is small.
- The data layer is already being touched (Phase 1f shipped Apr 2026 added `pipeline-events.jsonl`; this design extends rather than retrofits).
- The user pain is felt directly by the maintainer (cost forecast has been wrong for two months).

This window will close. The right move is to ship Phase 1's instrumentation early and make it discipline that survives — every new stage, every new provider, every new prompt is instrumented at the moment it's added, not "soon." Skipping it for any single feature breaks the contract; once broken, the cohort lookup loses fidelity for everything downstream of the gap.

So: the cost-forecast brief is the felt user pain that justifies the work today. The time forecast follows for free. The shoal compounds the value much later. None of it is possible if Phase 1 doesn't ship before the window closes.

### The bigger meta-point

Most of this design space — progress UI, time estimation, user expectation management — gets framed as a maths problem in industry. The maths is genuinely interesting and the engineering choices matter, but the maths is in service of the psychology of waiting, not the other way around. Anyone reading this doc who is more comfortable with the maths than the psychology (the typical engineer reflex, including mine) should treat the psychology as the harder, less-validated half — not because it's worth less, but because the maths gives an illusion of precision that disguises how much we're guessing on the human side. We need more psychologists in this loop than we have. The alpha is when we fix that.

## Out-of-scope work this enables (downstream)

Once the JSONL exists:

- Cost-per-quote-extracted ratchet (`docs/methodology/tag-rejections-are-great.md`).
- Prompt-engineering feedback loop: "your v0.5 prompt is 18% more expensive than v0.4 — was that intentional?"
- Per-stage budget alerts in serve mode.
- Honest range UI: replace `~$1.50 (est.)` with `$0.90–$1.50 (median $1.20, n=47)`.
- Public blog post: "we replaced our hardcoded LLM cost forecast with a self-correcting one and here's what we learned."

## Implementation sketch (for reviewers)

Files touched:

- **New:** `bristlenose/llm/telemetry.py` — `record_call()` writer, `read_history()` streaming reader, cohort lookup, aggregated cache compaction.
- **New:** `LLMCallEvent(BaseModel)` Pydantic model (in `telemetry.py` or `events.py`) — schema definition with OTel `Field(alias=...)`.
- **Edit:** `bristlenose/llm/client.py` — call `record_call()` from each provider's terminal success/failure path. Reads `contextvars` set by the pipeline runner. Sums tokens across retry attempts in `_analyze_local`.
- **Edit:** `bristlenose/llm/pricing.py` — `estimate_pipeline_cost()` returns `RunForecast` (per-stage `Estimate` with both axes + aggregated totals + display strings). Removes the hardcoded `_TOKENS_PER_SESSION` constant.
- **Edit/refactor:** `bristlenose/timing.py` — folded into the same data layer. `timing.py` becomes the progress-bar consumer of the same per-stage `Estimate` objects, replacing its own hardware-keyed history with the new shared lookup. Welford's online-variance logic preserved as the within-stage smoothing primitive; the pre-run forecast uses median, the progress bar uses the smoothed running estimate.
- **New:** `bristlenose/runtime.py` — `hardware_signature()` function. Probes platform/chip/RAM and returns the coarse signature string. Cached at process start.
- **New:** `bristlenose/llm/cohort_normalise.py` — one function per provider mapping `response_model` → `(family, major)`. Tested against fixtures of real provider responses.
- **New:** `bristlenose/llm/cohort-baselines.json` — shipped per `(stage_id, prompt_id, prompt_version, family, major)`.
- **New:** `scripts/regenerate-cohort-baselines.py` — reads a developer's FOSSDA-run `llm-calls.jsonl`, computes medians, writes the JSON. Joined to the release ritual.
- **CI gate:** unit test fails if any prompt's `(id, version, sha)` triple in `prompts.lock` doesn't have a matching entry in `cohort-baselines.json` for at least the cloud cohorts. Forgot to re-baseline → release blocked.
- **Edit:** `bristlenose/cli.py` — render `Estimate` shape: `~$5.70` (2 sig figs when N≥3), `~$5` (1 sig fig otherwise), partial known-plus-unknown when stages diverge.
- **Edit:** every file in `bristlenose/llm/prompts/*.md` — add YAML frontmatter (`id`, `version`).
- **New:** `bristlenose/llm/prompts.lock` — `(filename, version, sha)` triples; unit test asserts no drift between repo content and lockfile.
- **Edit:** `bristlenose/pipeline.py` — set `contextvars` for `run_id`, `stage`, `output_dir` at each stage entry.
- **Edit:** `bristlenose/cli.py` — display range + sample count instead of point estimate when cohort is rich.
- **Edit:** `CLAUDE.md` — add gotcha line classifying `llm-calls.jsonl` as a re-identification key, sibling to existing `pii_summary.txt` line.
- **Edit:** `bristlenose/run_lifecycle.py` — verify `run_id` is exposed for the new writer to read (no schema change).
- **New tests:** `tests/test_llm_telemetry.py` — schema round-trip, retry-tokens-summed, missing-usage handling, contextvar isolation under asyncio, per-run-file isolation, cohort lookup with N<5 / N≥5 / M≥10, opt-out env var, file mode `0o600`, `O_NOFOLLOW`. Use `tmp_path` everywhere — never write into the repo or `~`.
- **Existing tests to update:** `tests/test_llm_usage.py`, `tests/test_cost.py`.

Estimated weekend for Phase 1 (writer + schema + per-run file + retention cap); another weekend for Phase 2 (aggregated cache + cohort lookup + CLI display).

## References

- OTel GenAI semantic conventions: <https://opentelemetry.io/docs/specs/semconv/gen-ai/>
- LiteLLM cost tables: <https://github.com/BerriAI/litellm/blob/main/litellm/model_prices_and_context_window_backup.json>
- Simon Willison's `llm`: <https://llm.datasette.io>
- Tokencost: <https://github.com/AgentOps-AI/tokencost>
- tiktoken: <https://github.com/openai/tiktoken>
- Anthropic token counting: <https://github.com/anthropics/anthropic-cookbook/blob/main/misc/how_to_count_tokens.ipynb>
- Vercel AI SDK telemetry: <https://sdk.vercel.ai/docs/ai-sdk-core/telemetry>
- promptfoo: <https://www.promptfoo.dev>
- Microsoft Prompty: <https://prompty.ai>
- Replit Agent retro: <https://blog.replit.com/agent-3>
- Cursor Shadow Workspace: <https://www.cursor.com/blog/shadow-workspace>
