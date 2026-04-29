# Pluggable LLM routing, per-stage model choice, and quality eval

**Status:** Design draft — not yet implemented. April 2026.
**Related:** [design-gemma4-local-models.md](design-gemma4-local-models.md), [design-modularity.md](design-modularity.md), [design-perf-fossda-baseline.md](design-perf-fossda-baseline.md), [archive/design-llm-providers.md](archive/design-llm-providers.md) (historical roadmap)

## Why now

Three forces make the current "one provider for everything" model wrong for the next 12 months:

1. **Capability diverges per stage.** Topic segmentation on a cleaned transcript is a small job a 3B local model can do. Thematic grouping across 20 sessions is a frontier-model job. Paying Sonnet rates for stage 8 is wasteful; running stage 11 on `llama3.2:3b` produces mush.
2. **Hardware is about to land.** Apple Intelligence on M3+ ships a ~3B on-device model with structured-output support ([apple/python-apple-fm-sdk](https://github.com/apple/python-apple-fm-sdk), macOS 26). The Copilot+ PC class (Qualcomm X Elite, AMD XDNA2) is in the same bracket. Within a year, "free, private, good enough for prep stages" is a real default.
3. **Researchers care about where data goes.** PII redaction and speaker identification run against raw transcripts. A user may want those local even if they're happy to send a redacted summary to Claude for thematic work.

None of this is deliverable without (a) a stage → provider routing layer, and (b) a way to verify a model swap didn't silently degrade report quality.

## What exists today

Single global provider selection via `BRISTLENOSE_PROVIDER`. `LLMClient` in [bristlenose/llm/client.py](../bristlenose/llm/client.py) dispatches `analyze()` to one of five backends (Claude, ChatGPT, Azure, Gemini, Ollama). No per-stage configuration, no quality metric beyond "JSON parses and schema validates". FOSSDA perf baselines measure wall-clock and LLM latency only.

## Proposed design

### 1. Stage → provider routing

Extend config with an optional `llm_stages` mapping. Absent key = fall back to global `llm_provider`.

```toml
# .bristlenose.toml
llm_provider = "anthropic"          # global default
llm_model = "claude-sonnet-4"

[llm_stages]
pii_removal       = { provider = "local",  model = "llama3.2:3b" }
topic_segmentation = { provider = "local",  model = "llama3.2:3b" }
quote_extraction  = { provider = "anthropic", model = "claude-haiku-4" }
quote_clustering  = { provider = "anthropic", model = "claude-sonnet-4" }
thematic_grouping = { provider = "anthropic", model = "claude-sonnet-4" }
```

`LLMClient.analyze()` grows a `stage: str` kwarg. Resolution order: `llm_stages[stage]` → global `llm_provider` → first-run prompt. The provider dispatch table stays exactly as it is — only the **selection** layer is new.

This preserves the no-fork principle ([design-modularity.md](design-modularity.md)): CLI and desktop both get the same routing. Desktop surfaces it as a settings panel; CLI uses TOML.

### 2. Apple Foundation Models — Swift-side, not Python

Worth separating signal from noise. The [apple/python-apple-fm-sdk](https://github.com/apple/python-apple-fm-sdk) repo is **not** Apple opening on-device inference to the Python ecosystem. Reading the README and examples, it's a narrow shim aimed at Swift developers who want to evaluate their Swift Foundation Models app from a Python notebook — batch inference, transcript replay, quality analysis. Apple still positions Swift as the production path; Python is an eval sidecar for Swift app developers.

For Bristlenose this means the blessed route to Apple's on-device model is **Swift in the desktop host**, exposed to the Python sidecar over the existing WKWebView/XPC bridge — not `pip install apple-fm-sdk` inside the PyInstaller bundle. Concretely:

- Swift host registers an FM endpoint (analogous to how it already injects API keys for cloud providers — see [bristlenose/llm/CLAUDE.md](../bristlenose/llm/CLAUDE.md) on the sidecar credential flow).
- Python sidecar gets a new `"apple-fm"` provider whose `_analyze_apple()` calls the Swift-side endpoint and awaits a structured response.
- Availability gated by macOS 26 + Apple Intelligence + compatible Mac. CLI distributions (Homebrew, pip, Snap, Linux) never see this provider.

**Consequences:**

- **CLI parity is out of scope for Apple FM.** First explicit break from [design-modularity.md](design-modularity.md)'s no-fork principle. Justified: the feature is structurally tied to a macOS entitlement and Apple silicon. Document as a capability-gate, not a fork.
- **Structured output translation lives Swift-side.** Swift's `@Generable` is where the Pydantic schema needs to land. The Python side ships the JSON schema; Swift translates into an ad-hoc `@Generable` struct or uses the FM framework's raw-JSON-schema path when that surface matures.
- **Starting role:** `pii_removal` and `topic_segmentation` — per-session, short prompts, small-context-friendly, benefit most from "stays on device". Not `quote_clustering` / `thematic_grouping`, which need cross-session reasoning and a larger context than the on-device model provides.
- **Not the python-apple-fm-sdk.** Bundling it in the sidecar would drag Swift-backed dylibs into PyInstaller for no benefit — the model still needs the Swift entitlement to run. Python shim adds cost, not capability.

### 3. Quality eval harness

A model swap is only safe if we can measure what changed. Proposed `bristlenose eval` command:

- **Golden inputs:** the FOSSDA perf dataset (already whitelisted at `trial-runs/fossda-opensource/`). Public, reproducible, reshareable. Other `trial-runs/` content is private and must never be used for eval.
- **Golden outputs:** human-curated "known good" quote sets, theme groupings, and PII redactions for a subset of FOSSDA sessions. One-off upfront cost.
- **Metrics per stage:**
  - **PII:** precision/recall against labelled spans.
  - **Topic segmentation:** boundary F1 (within ±2 turns of golden boundary).
  - **Quote extraction:** precision/recall against curated quote set, plus Jaccard overlap on quote text.
  - **Clustering / thematic grouping:** Adjusted Rand Index against golden grouping.
  - **All stages:** wall-clock, tokens in/out, cost, schema-parse failure rate.
- **Output:** `eval-results.json` snapshot + `.eval-history.jsonl` append-only (matches the existing local-metric-archives pattern: snapshot gitignored, history gitignored, charts deferred). Table view in CLI; regression gate in CI if we later want one.

Matrix form: run N models × M stages, write a comparison table. This is the thing that makes "let's try Apple FM for segmentation" a one-command decision instead of a guess.

**Non-goal:** an eval framework like `promptfoo` or `lm-eval-harness`. We need **Bristlenose-task-specific** quality measurement, not general benchmarks. Keep it small, owned, and aligned with our pipeline stages.

### 4. Doctor and UX

- `bristlenose doctor` surfaces each configured stage with its provider and availability. Apple FM shows `is_available()` reason when missing.
- Desktop settings panel: per-stage dropdown seeded with the provider's compatible models. Groupings: "On-device (private, free)", "Budget cloud", "Frontier cloud", "Enterprise (Azure)".
- First-run: no change. Global default still works. Per-stage routing is an optional power-user layer, not something a new user has to configure.

## Sequencing

1. **Eval harness first.** Without it, every subsequent change is faith-based. Estimate: ~1 week including golden-set curation on 3–4 FOSSDA sessions.
2. **Stage routing config + `stage:` kwarg through `LLMClient`.** Purely mechanical. ~1 day. No new provider needed — immediate value: run `quote_extraction` on Haiku, keep `thematic_grouping` on Sonnet, measure the cost delta against quality.
3. **Apple FM provider.** Behind a feature flag. Target stages: `pii_removal`, `topic_segmentation`. Requires the macOS 26 + Apple Intelligence gate, the Pydantic-to-`@generable` translator, and a sandbox entitlement spike. ~1 week.
4. **Gemma / larger local models for mid-tier stages.** Picks up [design-gemma4-local-models.md](design-gemma4-local-models.md) with the routing layer now in place.
5. **Hardware-aware defaults.** Detect M-series tier, RAM, Apple Intelligence status; suggest a routing profile. Uses the eval harness to validate each profile's quality on a small sample before recommending it.

## Open questions

- Swift-side FM endpoint: what's the XPC/messaging shape between Swift host and Python sidecar for a structured LLM call? Extension of the existing credential-injection bridge, but request/response is heavier. Needs a small spike.
- Is Swift `@Generable` rich enough for our nested schemas (e.g. `QuoteCluster` with nested quote lists)? Flat looks fine, nested unclear — verify with a spike.
- What's the right eval cadence? On every provider/model config change manually? Nightly on a perf branch? Pre-release only?
- Do we expose eval scores to end users ("this config scores 0.87 precision on the reference set"), or keep it an internal tool? Leaning internal until the numbers are defensible.

## What this document is not

- Not a commitment to implement all five stages. Item 1 (eval) + item 2 (routing) is the minimum useful slice. Everything after depends on what the eval shows.
- Not a plan to deprecate any cloud provider. The goal is routing, not replacement.
- Not pricing strategy. Touches cost-to-serve, but IAP pricing and LLM brokering are in the private delivery repo.
