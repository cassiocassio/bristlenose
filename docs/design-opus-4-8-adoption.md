# Adapting transcript analysis to Claude Opus 4.8

> **Status:** Findings + plan, reconciled against **pipeline-view v2** (shipped on `main`, v0.15.13, 4 Jun 2026). **No pipeline behaviour changed.**
> **⏰ REVISIT 18 Jun 2026 (post-WWDC).** Opus 4.8's value may be partly superseded by Apple Foundation Models announced at WWDC (week of 8 Jun). Treat the bigger investments below as *decide-after-WWDC*; only the low-regret data work is safe to do before.
> **🚦 Must NOT block TestFlight.** Per-stage execution routing and Opus adoption are post-TF / non-blocking. TF ships on the current single-global-model dispatch.

**Date:** 4 Jun 2026. **Branch:** `claude/opus-4-8-transcript-eval`.
**Related:** [design-pluggable-llm-routing.md](design-pluggable-llm-routing.md), [design-perf-scale-and-tokens.md](design-perf-scale-and-tokens.md), `bristlenose/pipeline_view/` (v2), [bristlenose/llm/CLAUDE.md](../bristlenose/llm/CLAUDE.md).

---

## 1. Verified Opus 4.8 facts (provided; not from training data)

- Model id `claude-opus-4-8`; released 2026-05-28.
- **1M context** default on the Claude API (Vertex/Bedrock 1M; MS Foundry 200K). **128K max output.**
- Pricing **$5 / $25** per M tok (in/out) — vs Sonnet 4 at $3/$15 → **~1.67×**.
- **Prompt caching:** min cacheable prefix lowered to **1,024 tokens**; up to **90%** off cached input. (Caching itself is GA on current models — see §4.)
- Adaptive thinking; Batch API 50% off; `role:"system"` allowed mid-`messages`; improved tool triggering; better long-context/compaction.

## 2. Current state of the codebase (v2)

### 2.1 The per-stage model framework — what shipped

`pipeline-view v2` (`4290174`) added the **model axis** that earlier drafts of this doc flagged as missing:

- The catalogue is now keyed **`(stage, provider, model)`**. `BackendOption` (provider) holds `models: list[ModelOption]`; each `ModelOption` carries `default`, `publisher`, model-level `requires`.
- Quality cells (`_LLM_QUALITY`) and the orthogonal **`recommended` vs `default`** flags are per-model. v2 is the first time `recommended ≠ default` fires (Opus 4, gpt-4o recommended-but-not-default).
- Claude is catalogued with `claude-sonnet-4-20250514` (Sonnet 4, `default`) and **`claude-opus-4-20250514` (Opus *4*)**.

**Two live gaps this introduced:**
1. **The catalogued Opus is a generation stale** — `claude-opus-4-20250514` (May 2025), not `claude-opus-4-8`.
2. **Opus 4 is `recommended=True` but unpriced** — `PRICING` has only Sonnet + Haiku, so `estimate_cost()` returns `None` for a model BN now actively recommends. Cost forecast silently dark on a recommended option. The 4-level rating enum can't differentiate Opus from Sonnet anyway (both flat `"excellent"`, `source="editorial"` = unmeasured).

### 2.2 What v2 did **not** change: dispatch is still global

The per-model grain is a **recommendation surface, not execution.** `LLMClient.analyze()` ([client.py:180](../bristlenose/llm/client.py)) has **no `stage` kwarg**; there is **no `llm_stages` config**. All five LLM stages dispatch the single global `settings.llm_provider` / `llm_model`. The catalogue docstrings still state "dispatch is singular." So "Opus on synthesis only" is advisory in the Pipeline view — `run` cannot yet act on it.

### 2.3 How Claude is actually called (unchanged)

- One Anthropic call site: `_analyze_anthropic()` ([client.py:324](../bristlenose/llm/client.py)) — forced tool-use for structured output, `system` as a plain string, one user message, `temperature=0.1`, `max_tokens` default **64000** (global; the "portable ceiling" because Sonnet caps output at 64000).
- **No `cache_control`, no betas, no thinking, no Batch, no `role:"system"`.** Token usage already reads back `cache_read_input_tokens` — telemetry is pre-wired for caching.
- **No transcript chunking anywhere.** Each per-session stage (8 segmentation, 9 quote-extraction) sends the full transcript in one call; stages 10/11 + AutoCode send all quotes / the whole taxonomy in one call. Largest observed input ~18.5K tok — input ceiling has never been the constraint; **output** is.
- Pricing/cohort: `cohort_normalise` already parses `claude-opus-4-8` → `("claude-opus","4")`; no change needed. `PRICING` has no Opus row at all.

## 3. Opportunities mapped to 4.8 features

- **A. Prompt caching — biggest cost lever, zero dependencies, available today (see §4).** AutoCode taxonomy + per-session system/tool prefix.
- **B. Price Opus + per-model `max_tokens` clamp + add `claude-opus-4-8` ModelOption.** Required correctness; now mostly *data* because the model axis exists. Fixes the §2.1 gaps.
- **C. 1M context — headroom, not a need.** Largest input far below 200K. Enables bigger AutoCode batches / whole-study passes later. Defer.
- **D. Batch API (50%)** — fits non-interactive `run`; stacks with caching; not for serve/interactive.
- **E. Adaptive thinking** — measure on synthesis stages before enabling.
- **F. `role:"system"` / tool-triggering** — no current use (we force `tool_choice`). Park.

## 4. Why caching needs nothing from 4.8

Prompt caching is GA on the currently-shipped `claude-sonnet-4-20250514`. The repeated prefixes we'd cache (AutoCode's ~14–17K-token taxonomy; the per-session system+tool prefix) are well above any minimum, so they qualify **today**. 4.8 only lowers the minimum to 1,024 tokens and advertises up to 90%. **Implication: ship caching now on Sonnet, independent of Opus/WWDC/TF.** Gate `cache_control` to the Anthropic path only — it must not leak to OpenAI/Azure/Gemini/local.

## 5. Plan (sequenced around TF + WWDC)

**Now — low-regret, TF-non-blocking, no WWDC dependency:**
- **P1. Prompt caching** on the Anthropic path (system+tool / AutoCode taxonomy). Cost win on current models; ships independent of everything.
- **P2. Price Opus + per-model `max_tokens` clamp + add `claude-opus-4-8` as a `ModelOption`** (replace/augment the stale Opus 4). Fixes the recommend-but-unpriced bug and the stale-model gap. Pure data + a clamp.

**After WWDC (decide 18 Jun) — only if Opus still looks worth it vs Apple FM:**
- **P3. Eval harness** (FOSSDA, Sonnet vs Opus 4.8 vs Apple FM). Converts the `editorial` quality cells into measured ones; earns the right to recommend/default Opus.
- **P4. Execution routing** (`stage:` kwarg + `llm_stages`). The remaining prerequisite to make v2's per-model recommendation *executable*. **Post-TF.**
- **P5. Opus 4.8 recommended/default on synthesis stages (10/11) only**, expressed via the existing `recommended`/`default` flags + cost signal — no new "best" tier needed. **Gated on P3 + P4.**
- **P6. Batch API / adaptive thinking** — opt-in, gated on the eval.

## 6. Gains per move — quality / speed / cost

| Move | Quality | Speed | Cost | Notes |
|---|---|---|---|---|
| **P1 caching** | — | ↑ small | ⬇⬇⬇ **dominant** | Up to ~90% off the repeated AutoCode taxonomy + per-session prefix. **Today, Sonnet, no routing.** |
| **P2 price + 4.8 ModelOption + clamp** | — | — | ⬆ accuracy | Fixes recommend-but-unpriced bug; clamp also fixes latent Haiku/GPT over-cap errors. XS–S. |
| **P3 eval harness** | ⬆ *measures* | — | — | Flips Opus cells off `editorial`; decides default vs Apple FM. |
| **P4 execution routing** | enables ↑ | enables ↕ | enables ⬇⬇ | Makes per-model grain executable. Mixture-of-models: cheap/local on prep, frontier on synthesis. **Post-TF.** |
| **P5 Opus on 10/11** | ⬆⬆ cross-session reasoning | ↓ (slower) | ⬆ 1.67×, offset by P1+P4 | Synthesis only; structural stays `recommended=False` (equal quality, pure overpay). |
| **P6 batch / thinking** | thinking ↑ maybe | batch ↓↓ / thinking ↓ | batch ⬇⬇ 50% | Gate thinking on P3. |
| *1M context (deferred)* | ↑ marginal | ↑ marginal | ⬇ marginal | No current need. |

## 7. WWDC supersession risk

Apple Foundation Models (WWDC, week of 8 Jun) may make on-device inference the right home for the *structural* prep stages (speaker-id, segmentation) — exactly the stages where Opus offers no advantage. If Apple FM lands strong, the case narrows to **Opus 4.8 on the two synthesis stages only**, and the routing layer (P4) becomes more about "local prep + frontier synthesis" than "Opus everywhere." **Decision point: 18 Jun.** Don't commit to P3–P5 before then. P1–P2 are WWDC-proof.

## 8. Open decisions (for 18 Jun revisit)

1. Replace Opus 4 in the catalogue with Opus 4.8, or list both?
2. After the eval: does Opus 4.8 earn `default` on synthesis, or stay `recommended`-only with Sonnet as default?
3. Is P4 (execution routing) a post-TF priority, or does Apple FM reshape it first?
