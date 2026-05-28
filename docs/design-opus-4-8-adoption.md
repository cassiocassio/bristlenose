# Adapting the transcript-analysis pipeline to Claude Opus 4.8

**Status:** Findings + proposed plan. **No pipeline behaviour changed yet — awaiting approval.**
**Date:** 28 May 2026. **Branch:** `claude/opus-4-8-transcript-eval`.
**Related:** [design-pluggable-llm-routing.md](design-pluggable-llm-routing.md), [design-perf-scale-and-tokens.md](design-perf-scale-and-tokens.md), [design-llm-call-telemetry.md](design-llm-call-telemetry.md), [design-cost-forecast-phase1.md](design-cost-forecast-phase1.md), [bristlenose/llm/CLAUDE.md](../bristlenose/llm/CLAUDE.md).

---

## 1. Scope

This document investigates what it takes to adopt **Claude Opus 4.8** (`claude-opus-4-8`, released 2026-05-28) in the transcript-analysis pipeline, and proposes a phased plan. It deliberately stops short of changing any pipeline behaviour.

### Verified Opus 4.8 facts (provided, not from training data)

- Model id `claude-opus-4-8`.
- **1M-token context** by default on the Claude API (was 200K). Vertex/Bedrock also 1M; Microsoft Foundry 200K.
- **128K max output** tokens.
- **Adaptive thinking** — model decides per-turn whether to think; fewer wasted thinking tokens at a given effort level.
- **Prompt caching** — minimum cacheable prompt lowered to **1,024 tokens**; up to 90% savings on cached input.
- Messages API now accepts `role:"system"` entries inside the `messages` array (mid-task instruction updates without breaking the prompt cache).
- Improved tool triggering vs 4.7.
- Claimed better long-context quality and compaction handling.
- **Batch processing: 50% cost savings.** Pricing unchanged at **$5 / $25 per M tokens** (input/output).

---

## 2. How the pipeline calls Claude today

### 2.1 The single API call site

Every LLM call funnels through `LLMClient.analyze()` ([bristlenose/llm/client.py:180](../bristlenose/llm/client.py)), which dispatches per provider. The Anthropic path is `_analyze_anthropic()` ([client.py:324](../bristlenose/llm/client.py)):

- Builds a **forced tool-use** call for structured output: a single tool `structured_output` whose `input_schema` is the Pydantic model's JSON schema, with `tool_choice={"type":"tool","name":"structured_output"}` ([client.py:345–365](../bristlenose/llm/client.py)).
- `system=system_prompt` (a plain string), `messages=[{"role":"user","content":user_prompt}]`.
- `temperature=0.1` ([config.py:57](../bristlenose/config.py)), `max_tokens` from settings (default 64000).
- `timeout=600.0` is set explicitly to bypass the SDK's streaming heuristic for high `max_tokens` ([client.py:368](../bristlenose/llm/client.py); see CLAUDE.md gotcha).
- Token usage is already read back, **including `cache_read_input_tokens` and `cache_creation_input_tokens`** ([client.py:393–394](../bristlenose/llm/client.py)) — telemetry is wired for caching even though we never request it.

**What is *not* used today:** no `cache_control`, no `anthropic-beta` headers, no extended/adaptive thinking, no `role:"system"` mid-message, no Batch API, no per-stage model routing. Confirmed by grep — the only `cache_control` / `extra_headers` hits in the tree are HTTP response headers and the markdown transcript-header writer, not the LLM client.

### 2.2 Where Claude is invoked in the pipeline

| Stage | Call site | Granularity | Input shape | Output-heavy? |
|------|-----------|-------------|-------------|---------------|
| 5b speaker id / split | [s05b_identify_speakers.py:251,378](../bristlenose/stages/s05b_identify_speakers.py) | per session | first ~5–10 min of transcript | no |
| 8 topic segmentation | [s08_topic_segmentation.py:133](../bristlenose/stages/s08_topic_segmentation.py) | per session | full transcript | small (boundaries only) |
| 9 quote extraction | [s09_quote_extraction.py:207](../bristlenose/stages/s09_quote_extraction.py) | per session | full transcript + topic boundaries | **yes — the truncation hotspot** |
| 10 quote clustering | [s10_quote_clustering.py:68](../bristlenose/stages/s10_quote_clustering.py) | per run | all screen-specific quotes (compact JSON) | medium |
| 11 thematic grouping | [s11_thematic_grouping.py:68](../bristlenose/stages/s11_thematic_grouping.py) | per run | all contextual quotes (compact JSON) | medium |
| AutoCode (serve) | [server/autocode.py:339](../bristlenose/server/autocode.py) | per batch of 25 quotes | codebook taxonomy + 25 quotes | medium |
| Signal elaboration (serve) | [server/elaboration.py:305](../bristlenose/server/elaboration.py) | per batch | signal cards | small |

Per-session stages (5b/8/9) run **concurrently, bounded by `llm_concurrency=3`** ([config.py:119](../bristlenose/config.py)); stages 10/11 run as one call each. AutoCode batches with `BATCH_SIZE=25` ([autocode.py:37](../bristlenose/server/autocode.py)), bounded by the same semaphore.

### 2.3 Ingestion / chunking / segmentation

- **Ingestion** (s01–s06) is non-LLM: file grouping, audio extraction, transcription (Whisper), merge. No model concern.
- **There is no transcript chunking or windowing anywhere.** Each per-session stage sends the *entire* `transcript.full_text()` in one call ([s08:129](../bristlenose/stages/s08_topic_segmentation.py), [s09:203](../bristlenose/stages/s09_quote_extraction.py)). The only size management is **output**-side truncation detection (`stop_reason == "max_tokens"` → `RuntimeError`).
- Per the scale analysis ([design-perf-scale-and-tokens.md](design-perf-scale-and-tokens.md)), even the largest observed session is ~18.5K input tokens — far below 200K, let alone 1M. **Input context has never been the constraint; output ceiling is.**

### 2.4 Model identity, pricing, cohorts

- Default model is **`claude-sonnet-4-20250514`** ([config.py:55](../bristlenose/config.py), [providers.py:50](../bristlenose/providers.py)). Opus is not the default and **is not in the pricing table**.
- `PRICING` ([pricing.py:34](../bristlenose/llm/pricing.py)) and `_MODEL_PROVIDER` ([pricing.py:47](../bristlenose/llm/pricing.py)) have no `claude-opus-*` entry. `estimate_cost()` returns `None` for unknown models, so **cost reporting and the pre-run forecast silently go dark for Opus**.
- `max_tokens` default is **64000** ([config.py:56](../bristlenose/config.py)) — deliberately the "portable ceiling" because Sonnet 4 hard-caps output at 64000 ([llm/CLAUDE.md §max_tokens](../bristlenose/llm/CLAUDE.md)). Opus 4.8 allows 128K, but raising the global default would break the other providers; this needs a per-model clamp.
- **Good news:** `cohort_normalise._ANTHROPIC_RE` already parses `claude-opus-4-8` → `("claude-opus", "4")` ([cohort_normalise.py](../bristlenose/llm/cohort_normalise.py)). Telemetry/cohort keys work unchanged. But `cohort-baselines.json` has no `claude-opus` baseline, so the *pre-run* forecast for Opus falls through to `None` until a local run populates `llm-calls.jsonl`.
- The Anthropic SDK is pinned `anthropic>=0.39` ([pyproject.toml:30](../pyproject.toml)). Prompt caching is GA and fine on 0.39, but the **1M-context beta header and `role:"system"`-in-messages need a newer SDK** — pin must be verified/bumped before using those.

---

## 3. Opportunity analysis — which Opus 4.8 features actually help Bristlenose

Ranked by value-to-effort for *this* codebase.

### A. Prompt caching — highest value, low risk

Two call patterns repeat an identical large prefix many times per run:

1. **Per-session stages 8 & 9.** The `system` prompt + tool schema is byte-identical across every session in a study (10–20 calls). The quote-extraction system prompt + schema is well over 1,024 tokens, so it now qualifies for caching with the lowered minimum.
2. **AutoCode.** System prompt + codebook taxonomy is ~14–17K tokens ([design-autocode.md](design-autocode.md)) and is identical across every 25-quote batch — a large, highly-repeated prefix. This is the single best caching candidate in the product.

Caching the stable prefix (system + tool definition + taxonomy) could cut input cost up to 90% on the repeated portion and offset most of Opus's higher input price. **Caveat:** caching is Anthropic-only and must be gated to `_analyze_anthropic` — it must not leak into the OpenAI/Azure/Gemini/local paths. The provider-agnostic `analyze()` signature means the "what is the cacheable prefix" decision has to be expressed in a provider-neutral way (e.g. mark system+tool as cacheable, let each provider honour or ignore it).

### B. Cost + per-model `max_tokens` clamp — required for correctness

Adopting Opus *requires* adding it to the pricing table (`(5.0, 25.0)`) and `_MODEL_PROVIDER`, or cost reporting breaks. Separately, the 64000 portable ceiling can be lifted **for Opus only** via a per-model output cap (Opus → 128000), which directly retires the stage-9 truncation hotspot on dense oral-history sessions without the deferred "smart-splitting" work.

### C. 1M context — headroom, not a current need

No current dataset approaches even 200K input. 1M context does *not* unblock anything today, but it:
- removes any future need to chunk long oral-history corpora,
- lets AutoCode raise `BATCH_SIZE` substantially (fewer round-trips, better cross-quote consistency),
- could enable a future "whole-study in one call" thematic pass.
Lower priority; revisit when a real >200K dataset appears. Note the **Microsoft Foundry 200K** asymmetry if Azure-routed.

### D. Batch API (50% off) — strong fit, medium effort

The `run` pipeline is fundamentally batch-like (not interactive). Routing stages 8/9 (and AutoCode) through the Batch API would halve their cost, stacking with caching. Cost: async submit/poll plumbing, and it trades latency for price — so it should be opt-in (e.g. `--batch` or a non-interactive default), not forced on the serve-mode interactive paths.

### E. Adaptive thinking — measure before enabling

Could improve thematic grouping / clustering quality (the cross-session reasoning stages) at controlled token cost. Needs the eval harness (§5) to justify; don't enable blind.

### F. Improved tool triggering / `role:"system"` — low relevance

We already *force* `tool_choice`, so "model skips the tool" isn't our failure mode. `role:"system"` mid-message has no current use case. Park both.

---

## 4. Risks & constraints

- **Cost.** Opus is $5/$25 vs Sonnet $3/$15 — ~1.67× input, ~1.67× output. For a tool that advertises "~$1.50/study", that's material. Caching (A) + Batch (D) are what make Opus defensible; adopting Opus *without* them raises user cost noticeably.
- **Provider isolation.** `LLMClient.analyze()` is provider-agnostic. Every Opus-specific feature must be confined to `_analyze_anthropic`; a leaked kwarg breaks ChatGPT/Azure/Gemini/Ollama users.
- **Default-change blast radius.** Many tests assert on `claude-sonnet-4-20250514` (test_providers, test_cost, test_llm_truncation, test_autocode_engine, test_cohort_normalise, …) and docs cite it. Changing the *default* is a larger, noisier change than adding Opus as an *option*.
- **SDK pin.** Verify `anthropic` runtime version supports any beta features used; bump `>=0.39` if needed (and re-check the streaming-timeout heuristic).
- **`max_tokens` portability.** The current single global default is load-bearing across 5 providers; a per-model clamp is the clean way to give Opus 128K without breaking Haiku/GPT-4o (which already fail above their ceilings — see scale doc).
- **No behaviour change without measurement.** This branch is named `transcript-eval` for a reason: we should *prove* Opus changes report quality (better/neutral/worse per stage), not assume it.

---

## 5. Proposed plan (phased, gated on approval)

Sequenced so each phase is independently shippable and reversible. **Nothing here is implemented yet.**

**Phase 0 — Make Opus selectable & honest (small, safe).**
- Add `claude-opus-4-8` to `PRICING` `(5.0, 25.0)` and `_MODEL_PROVIDER` ([pricing.py](../bristlenose/llm/pricing.py)).
- Add a per-model output-cap helper; clamp `max_tokens` to the model ceiling (Opus 128K, Sonnet 64K, etc.) instead of the single global 64000. Warn (don't fail) when the configured value exceeds the cap.
- Confirm/bump the `anthropic` SDK pin.
- Users can then run `--model claude-opus-4-8` with correct cost reporting. **Default stays Sonnet.** Tests + docs updated for the new pricing row only.

**Phase 1 — Eval harness (decide with data).**
- Build the `bristlenose eval` slice from [design-pluggable-llm-routing.md §3](design-pluggable-llm-routing.md) against the **public FOSSDA** golden set only (never private `trial-runs/`).
- Metrics per stage: quote precision/recall + Jaccard, segmentation boundary F1, clustering/theme ARI, plus tokens/cost/latency/parse-failure rate.
- Run **Sonnet 4 vs Opus 4.8** head-to-head. This is the artifact that answers "should Opus be the default?" — output a comparison table, change nothing yet.

**Phase 2 — Prompt caching (cost offset).**
- Gate `cache_control` to `_analyze_anthropic`, marking system + tool schema (and AutoCode taxonomy) as the cached prefix; keep the interface provider-neutral.
- Verify via the already-wired `cache_read_input_tokens` telemetry that hit-rates are real. Expected biggest win on AutoCode.

**Phase 3 — Decide default & adaptive thinking (data-driven).**
- If Phase 1 shows Opus materially better and Phase 2 offsets cost, promote Opus to default (large test/doc sweep) — otherwise keep it opt-in.
- A/B adaptive thinking on stages 10/11 using the harness.

**Phase 4 — Batch API (optional, opt-in).**
- Route non-interactive `run` stages through the Batch API for 50% savings; leave serve-mode interactive paths synchronous.

**Deferred:** 1M context exploitation (raise AutoCode `BATCH_SIZE`, whole-study passes) — revisit when a >200K dataset appears.

---

## 6. Open questions for the user

1. **Adopt-as-option vs change-the-default?** Phase 0 (Opus selectable, Sonnet still default) is low-risk; making Opus the default is a big test/doc sweep and a cost increase. Recommend gating the default change on Phase 1 eval results.
2. **Is the eval harness in scope for this branch**, or is the immediate ask narrower (just "make Opus work")? The branch name suggests eval; confirming changes the size of the work.
3. **Cost posture.** Are we willing to ship Opus only *with* caching/Batch to hold the per-study cost, or is a higher per-study cost acceptable for a quality gain?
4. **Where should the findings live** — this doc (`docs/design-opus-4-8-adoption.md`) is the developer-facing home; happy to relocate/rename.
