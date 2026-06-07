---
status: pending
last-trued: 2026-06-07
trued-against: HEAD@desktop-provider-resolution on 2026-06-07
---

# Pluggable LLM routing, per-stage model choice, and quality eval

**Status:** Design draft, partially shipped (May 2026). The **display side** of stage→provider routing — showing the user which backends each stage could use, which BN runs by default, and editorial quality ratings per (stage, backend) cell — shipped via the Pipeline view (v1.5 + v1.9). See [design-pipeline-view.md](design-pipeline-view.md) for the shipped catalogue surface. The **selection/dispatch side** (per-stage TOML config, `stage:` kwarg through `LLMClient`, Apple FM Swift endpoint, `bristlenose eval` harness) **remains unbuilt** — design below is unchanged. April 2026 framing of "durable plumbing vs provider shims" still applies: routing layer is durable; provider shims re-verify per release. See [design-stage-backends.md](design-stage-backends.md) §"Durable plumbing vs specific APIs" for the cost/urgency split. **Update (7 Jun 2026):** the immediate desktop provider/model-resolution fix landed on `desktop-provider-resolution` (commits `1fe904e` + `743b784`) — stops the impossible-(provider, model) desync at source on the desktop path; the cross-channel "validate, not decide" guard below remains the deferred future work (one check in the shared layer, protects CLI + serve + desktop).
**Related:** [design-stage-backends.md](design-stage-backends.md), [design-pipeline-view.md](design-pipeline-view.md) (shipped catalogue surface), [design-modularity.md](design-modularity.md) §Modularisation matrix, [design-gemma4-local-models.md](design-gemma4-local-models.md), [design-perf-fossda-baseline.md](design-perf-fossda-baseline.md), [archive/design-llm-providers.md](archive/design-llm-providers.md) (historical roadmap)

## Why now

Three forces make the current "one provider for everything" model wrong for the next 12 months:

1. **Capability diverges per stage.** Topic segmentation on a cleaned transcript is a small job a 3B local model can do. Thematic grouping across 20 sessions is a frontier-model job. Paying Sonnet rates for stage 8 is wasteful; running stage 11 on `llama3.2:3b` produces mush.
2. **Hardware is about to land.** Apple Intelligence on M3+ ships a ~3B on-device model with structured-output support ([apple/python-apple-fm-sdk](https://github.com/apple/python-apple-fm-sdk), macOS 26). The Copilot+ PC class (Qualcomm X Elite, AMD XDNA2) is in the same bracket. Within a year, "free, private, good enough for prep stages" is a real default.
3. **Researchers care about where data goes.** PII redaction and speaker identification run against raw transcripts. A user may want those local even if they're happy to send a redacted summary to Claude for thematic work.

None of this is deliverable without (a) a stage → provider routing layer, and (b) a way to verify a model swap didn't silently degrade report quality.

## What exists today

**Dispatch side (unchanged from April 2026):** Single global provider selection via `BRISTLENOSE_PROVIDER`. `LLMClient` in [bristlenose/llm/client.py](../bristlenose/llm/client.py) dispatches `analyze()` to one of five backends (Claude, ChatGPT, Azure, Gemini, Ollama). No per-stage runtime configuration, no `stage:` kwarg, no derived quality metric beyond "JSON parses and schema validates". FOSSDA perf baselines measure wall-clock and LLM latency only.

**Display side (shipped May 2026, v1.5 + v1.9):** A read-only **catalogue surface** in `bristlenose/pipeline_view/` declares per-stage backends, their eligibility predicates against host facts, and editorial quality ratings per (stage, backend) cell. The catalogue is consumed by the React Settings → Pipeline tab and the CLI `bristlenose pipeline` command — making per-stage backend choice **legible** to researchers, without committing to auto-pick logic. See [design-pipeline-view.md](design-pipeline-view.md). This means we now have *editorial* per-stage quality ratings as catalogue data, even though no runtime routing or eval-harness measurement exists.

### Corollary: model-identity drift is a symptom of the unbuilt selection side

Because the selection side is unbuilt, the *runtime* model is still a single string — `settings.llm_model`, read by `LLMClient` on every call ([bristlenose/llm/client.py](../bristlenose/llm/client.py)), seeded from `providers.py` `default_model`. The descriptive catalogue *selects nothing*: it is consumed only by `cli.py` (`pipeline` command) and `server/routes/pipeline.py` (`build_pipeline_view`) to render. So three surfaces each independently assert "the default model," and they can disagree — because there is no single authority that selects:

| Surface | Holds (Gemini) | Role |
|---|---|---|
| `providers.py` `default_model` | `gemini-2.5-flash` | seeds `settings.llm_model` — the real runtime decider |
| `LLMProvider.swift` `defaultModel` / `availableModels` | `gemini-2.5-flash` | desktop Settings picker that *writes* `llm_model` |
| `pipeline_view/catalogue.py` `ModelOption(default=True)` | `gemini-2.5-pro` | renders the Pipeline tab; selects nothing |

(The catalogue lists Pro because Pro is the only Gemini model anyone wrote `QualityRating`s for — a descriptive-layer artifact, not a product stance.) **This divergence is not a bug to paper over with a code comment** — it's the expected shape of N consumers with no shared selector. Wiring the catalogue as the source that both seeds `llm_model` and feeds the picker (the selection side, below) collapses the three to one and **dissolves the divergence**.

**Model retirement is orthogonal — and stays a standing chore.** A single source of truth does not stop a provider retiring a model ID (an external-world event). It only (a) shrinks the fix from N edits to 1, and (b) makes it *catchable* via a guard that the source-of-truth IDs ∈ `pricing.PRICING` (or a live model list). Worked example (5 Jun 2026): `gemini-2.0-flash` was retired by Google 3 Mar 2026 yet survived as the Swift default for months, because the swap costs two edits in a file no Python test sees, and no automated check knows a model is retired. Until unification lands, every retirement is an N-place patch; after it, it's one place plus a guard. The guard is the durable win — pin it on the unified source, not on a Swift enum that's on its way out.

### Migration inventory: where model/provider facts are baked today

Every row below is a site that must be hand-edited when a model retires or a fact moves — i.e. a place that should eventually *defer to the schema* (`ProviderSpec` for vendor facts, catalogue `ModelOption` for model facts) rather than hold its own copy. Grouped by the fact-tier each defers to. (Built 5 Jun 2026 from a repo-wide grep; verify line numbers before acting.)

**Already-diverged today** (same concept, different values shipped) — the proof this isn't theoretical:
- Anthropic "pricing": `providers.py:52` (`docs.anthropic.com/.../models`) vs `LLMProvider.swift:142` (`anthropic.com/pricing`)
- Gemini "get a key": `aistudio.google.com/apikey` (cli / billing_hints / doctor_fixes) vs `/app/apikey` (`LLMProvider.swift:159`) vs bare `aistudio.google.com` (`cli.py:427,2195`)
- Gemini "pricing": `ai.google.dev/gemini-api/docs/pricing` (`providers.py:117`) vs `ai.google.dev/pricing` (`LLMProvider.swift:158`)
- `pricing_url` is defined twice in Python alone (`providers.py` + `pricing.py:57-60`)

**A · LLM model selection (which model runs)**
| Site | Holds | Defer to |
|---|---|---|
| `config.py:55` | `llm_model` global default | decision-engine default |
| `providers.py` `default_model` ×5 | per-provider runtime seed | `ModelOption(default=True)` |
| `llm/client.py` `settings.llm_model` | the dispatch read | `resolve(stage) → model` |
| `LLMProvider.swift:61-81` | desktop picker default / available | generated `models.json` |

**B · LLM model facts (cost, quality, eligibility)**
| Site | Holds | Defer to |
|---|---|---|
| `pricing.py` `PRICING` | model → cost | `ModelOption.cost` |
| `pricing.py` model→provider | reverse lookup | `ModelOption` under its `BackendOption` |
| `catalogue.py` `QualityRating` / `ModelOption.requires` | quality, eligibility | *(already the home)* |

**C · Provider facts + URLs (the "things we know about Anthropic" mini-DB)**
| Site | Holds | Defer to |
|---|---|---|
| `providers.py` `ProviderSpec` | name/aliases/env/sdk/**pricing_url** | *(the home — extend with the full URL set)* |
| `pricing.py` URL dict · `billing_hints.py:44-92` · `cli.py:418-462,2190` · `doctor_fixes.py:63-205` · `client.py:147-176` · `pipeline.py:317` | docs / console / keys / billing / get-a-key URLs | `ProviderSpec` |
| `doctor.py` · `LLMValidator.swift:119` | API-endpoint URLs | `ProviderSpec.api_endpoint` |
| `LLMProvider.swift:140-179` `links` | homepage / pricing / console | generated `providers.json` |
| `KeychainHelper.serviceNames` ↔ `credentials_macos` | keychain service name | `ProviderSpec` |
| handoff "Data use" URLs | terms / data-use | `ProviderSpec.terms_url` *(not in code anywhere yet)* |

**D · Transcription (Whisper) model selection** — same baked-choice smell, and the active cause of the 5 Jun transcription failure
| Site | Holds | Defer to |
|---|---|---|
| `config.py:74` | `whisper_model` default `large-v3-turbo` | transcription `BackendOption.models` default |
| `s05_transcribe.py:336` `_mlx_model_name` | hardcoded short → `mlx-community/...` repo map | `ModelOption.id` per transcription backend |
| `s05_transcribe.py:293` `transcribe_mlx` | bakes `path_or_hf_repo`; **ignores** `BRISTLENOSE_WHISPER_MODEL_DIR` | catalogue + host-aware / bundled-model resolution |
| `TranscriptionSettingsView.swift:9` | desktop default `large-v3-turbo` | generated `models.json` |
| `pipeline_view/catalogue.py` transcription `BackendOption` | `models=[]` (no model-level granularity yet) | **THE home — populate it** |

The transcription rows make the point sharpest: the model is resolved from a hardcoded map in *stage code* (`_mlx_model_name`), not from the catalogue — so a host-aware, bundled, or quality-rated choice is impossible, and on Apple Silicon it silently forces a 1.5 GB `large-v3-turbo` HuggingFace download (the 5 Jun failure). Wiring transcription model choice through the catalogue — whose transcription `BackendOption.models` is empty today — is the same fix as the LLM tier, not a separate effort.

### Future: selection-tier validation (validate, not decide)

The catalogue above describes *what can be selected* (which models belong to which provider, eligibility, quality). The **selection** layer — "which provider/model is current" — has no shared source of truth: CLI reads env / `.env` / `bristlenose.toml` / flags; desktop reads UserDefaults (`activeProvider` + a global `llmModel` that can desync from it); serve/React is read-only and uses the launch config. They converge only at `settings.llm_provider` / `llm_model`. Nothing validates the chosen `(provider, model)` pair against the catalogue — which is why a desktop provider/model desync (provider=`anthropic` + model=`gemini-2.5-flash`) reached the provider as a raw 404 and was then mislabelled "Transcription failed" (5 Jun 2026).

The next *non-render* use of the catalogue is **validate, not decide**: at config resolution, reject a `(provider, model)` pair the catalogue knows is impossible (a `gemini-*` model under `anthropic`) with a clear message instead of a 404. Permissive for custom/unknown models, and it **never overrides the user's choice** — so the catalogue stays informational, not the auto-selector (the auto-pick unification stays deferred). One check, in the shared sidecar layer, protects CLI + serve + desktop at once. The model→provider fact already exists in `pricing.py` (`MODEL_PROVIDER`) and implicitly in `ModelOption`-under-`BackendOption`; this step makes the catalogue its single home and first consumer beyond rendering. **Deferred — captured here so it's not lost.** The immediate desktop fix (inject the active provider's per-provider model at spawn, not the global `llmModel` — `BristlenoseShared.overlayPreferences`) ships separately and stops the desync at source; this guard is the cross-channel defence-in-depth on top.

## Proposed design

### 1. Stage → provider routing

> **Status (May 2026):** The display side of this routing — what backend each stage uses today + which alternatives are eligible + how good each is for the stage — shipped via the read-only Pipeline view (`bristlenose/pipeline_view/`, v1.5 + v1.9). See [design-pipeline-view.md](design-pipeline-view.md). The selection / dispatch side described below (per-stage TOML config, `stage:` kwarg through `LLMClient`) **remains unbuilt**. The display-first path means whatever resolver eventually lands inherits the catalogue as its knowledge base — no separate spec to maintain.

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
- **Structured output translation lives Swift-side.** Swift's `@Generable` is where the Pydantic schema needs to land. Two viable paths, both confirmed against the corpus (18 May 2026): (a) compile-time `@Generable` structs translated from our Pydantic models; (b) runtime `DynamicGenerationSchema` + `GenerationSchema(root:dependencies:)` for codebook stages where tags are user-defined. Nested `Generable` types and enums-with-associated-values are documented as supported, so `QuoteCluster` → `Quote[]` shapes translate without restructuring.
- **Starting role:** `pii_removal` and `topic_segmentation` — per-session, short prompts, small-context-friendly, benefit most from "stays on device". Two compounding reasons: small context fits, and these are the lowest-guardrail-risk stages (see [design-stage-backends.md](design-stage-backends.md) §"Guardrails are an orthogonal axis"). Not `quote_clustering` / `thematic_grouping`, which need cross-session reasoning and a larger context than the on-device model provides.
- **Specialized model variants worth evaluating** — `SystemLanguageModel.UseCase.contentTagging` ships a purpose-trained head for tagging tasks. Worth a per-stage A/B before routing tagging to the general-purpose model.
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

> **Status (May 2026):** v1.5 + v1.9 took a different sequence than originally proposed below — the **display-first** path (catalogue surface in the Pipeline view) shipped before items 1 and 2. The display side makes per-stage backend choice legible without committing to runtime dispatch logic; researchers stay in control. The original items 1–5 sequence below remains correct for the unbuilt selection / eval / Apple-FM work.

1. **Eval harness first.** Without it, every subsequent change is faith-based. Estimate: ~1 week including golden-set curation on 3–4 FOSSDA sessions.
2. **Stage routing config + `stage:` kwarg through `LLMClient`.** Purely mechanical. ~1 day. No new provider needed — immediate value: run `quote_extraction` on Haiku, keep `thematic_grouping` on Sonnet, measure the cost delta against quality.
3. **Apple FM provider.** Behind a feature flag. Target stages: `pii_removal`, `topic_segmentation`. Requires the macOS 26 + Apple Intelligence gate, the Pydantic-to-`@generable` translator, and a sandbox entitlement spike. ~1 week.
4. **Gemma / larger local models for mid-tier stages.** Picks up [design-gemma4-local-models.md](design-gemma4-local-models.md) with the routing layer now in place.
5. **Hardware-aware defaults.** Detect M-series tier, RAM, Apple Intelligence status; suggest a routing profile. Uses the eval harness to validate each profile's quality on a small sample before recommending it.

## Open questions

- Swift-side FM endpoint: what's the XPC/messaging shape between Swift host and Python sidecar for a structured LLM call? Extension of the existing credential-injection bridge, but request/response is heavier. Needs a small spike.
- ~~Is Swift `@Generable` rich enough for our nested schemas (e.g. `QuoteCluster` with nested quote lists)?~~ **Resolved 18 May 2026 against corpus:** yes — nested `Generable` types and enums-with-associated-values are documented as supported (`structured-output/generating-swift-data-structures-with-guided-generation.md`). Runtime-known schemas use `DynamicGenerationSchema`. Spike not needed for the schema-shape question; still needed for the XPC bridge shape above.
- What's the right eval cadence? On every provider/model config change manually? Nightly on a perf branch? Pre-release only?
- Do we expose eval scores to end users ("this config scores 0.87 precision on the reference set"), or keep it an internal tool? Leaning internal until the numbers are defensible.
- **Guardrails on sensitive UR content.** Apple's guardrails fire on input and output; refusals throw `LanguageModelSession.GenerationError.refusal(_:_:)` for guided generation. The eval harness needs a sensitive-content slice (healthcare, end-of-life, abuse) to measure violation rate per stage. Routing must downgrade rather than fail when a session hits a violation. Open: what's the user-facing UX when this happens — silent fallback to cloud (with notice), or explicit opt-in per session?

## What this document is not

- Not a commitment to implement all five stages. Item 1 (eval) + item 2 (routing) is the minimum useful slice. Everything after depends on what the eval shows.
- Not a plan to deprecate any cloud provider. The goal is routing, not replacement.
- Not pricing strategy. Touches cost-to-serve, but IAP pricing and LLM brokering are in the private delivery repo.
