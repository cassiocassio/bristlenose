---
status: partial
last-trued: 2026-10-11
trued-against: HEAD@main on 2026-10-11
---

> **Truing status:** Partial (trued 2026-10-11). The display side — the
> catalogue and `bristlenose pipeline` — is shipped and described accurately.
> The selection side (per-stage choice, the eval harness, Apple FM) is still
> unbuilt and the proposal below is still the plan. Until it lands, every site
> that picks a model on its own is held to minor fixes: see
> [§Interim model pickers](#interim-model-pickers-fix-dont-grow).

## Changelog

- _2026-10-11_ — trued up: status pending → partial; corrected the dispatch
  description (env var `BRISTLENOSE_LLM_PROVIDER`, the provider ladder, telemetry
  now records tokens and cost, structured-output repair, the stage ContextVar);
  kept the 5 Jun drift table as a baseline and added the 5 Sep state (all three
  surfaces agree, pinned by tests); added §Interim model pickers, the rule and the
  sites it binds, including the local-model and Whisper hardware ladders the
  inventory lacked; refreshed inventory anchors to symbols; removed the
  non-existent TOML source; corrected §1's stage keys (PII is not an LLM stage;
  speaker identification, discussion and the serve callers were missing);
  dated per-item status in Sequencing (Gemma and RAM-aware defaults partly
  shipped, global and desktop-only); made this doc the canonical home for the
  resolver and the eval harness. Anchors: `pipeline_view/catalogue.py`,
  `tests/pipeline_view/test_models.py`, `tests/test_llm_sampling_params.py`,
  `llm/telemetry.py` `stage()`, `config.py` `_fill_provider_default_model` and
  `_guard_orphan_desktop_model`, commits "pipeline view: offer the models we
  ship, and stop offering one that 404s", "populate the local-model catalogue
  from the desktop picker", "ollama: one rule for \"is this model installed\",
  and it is Ollama's".
- _2026-06-07_ — trued up against the desktop provider-resolution fix.

# Pluggable LLM routing, per-stage model choice, and quality eval

**Status:** Design draft, partially shipped (May 2026). The **display side** of stage→provider routing — showing the user which backends each stage could use, which BN runs by default, and editorial quality ratings per (stage, backend) cell — shipped via the Pipeline view (v1.5 + v1.9). See [design-pipeline-view.md](design-pipeline-view.md) for the shipped catalogue surface. The **selection/dispatch side** (per-stage TOML config, `stage:` kwarg through `LLMClient`, Apple FM Swift endpoint, `bristlenose eval` harness) **remains unbuilt** — design below is unchanged. April 2026 framing of "durable plumbing vs provider shims" still applies: routing layer is durable; provider shims re-verify per release. See [design-stage-backends.md](design-stage-backends.md) §"Durable plumbing vs specific APIs" for the cost/urgency split. **Update (7 Jun 2026):** the immediate desktop provider/model-resolution fix landed (commits "desktop: run the LLM provider the user selected, with honest status + failure copy" and "docs: provider status lifecycle decisions + data-protection-keychain reconcile") — stops the impossible-(provider, model) desync at source on the desktop path; the cross-channel "validate, not decide" guard below remains the deferred future work (one check in the shared layer, protects CLI + serve + desktop).
**Canonical home.** This doc owns the resolver (per-stage selection) and the eval harness. [design-stage-backends.md](design-stage-backends.md) holds the evidence that motivated them (per-stage timings, the on-device landscape) and points here for the plan.

**Related:** [design-stage-backends.md](design-stage-backends.md), [design-pipeline-view.md](design-pipeline-view.md) (shipped catalogue surface), [design-modularity.md](design-modularity.md) §Modularisation matrix, [design-gemma4-local-models.md](design-gemma4-local-models.md), [design-perf-fossda-baseline.md](design-perf-fossda-baseline.md), [archive/design-llm-providers.md](archive/design-llm-providers.md) (historical roadmap)

## Why now

Three forces make the current "one provider for everything" model wrong for the next 12 months:

1. **Capability diverges per stage.** Topic segmentation on a cleaned transcript is a small job a 3B local model can do. Thematic grouping across 20 sessions is a frontier-model job. Paying Sonnet rates for stage 8 is wasteful; running stage 11 on `llama3.2:3b` produces mush.
2. **Hardware has landed.** Apple Intelligence (M1 and later, macOS 26) ships a ~3B on-device model with structured-output support ([apple/python-apple-fm-sdk](https://github.com/apple/python-apple-fm-sdk)). The Copilot+ PC class (Qualcomm X Elite, AMD XDNA2) is in the same bracket. "Free and good enough for prep stages" is becoming a real option per stage. _(Written April 2026 as "about to land"; updated 11 Oct 2026.)_
3. **Some stages carry more participant data than others.** Speaker identification runs against raw transcripts; thematic grouping sees quotes. A team whose governance asks for the raw-transcript stages to stay on the machine should be able to say so per stage, while still sending the rest to a cloud model. (Cloud analysis stays the default and the recommended path — this is a per-stage option for teams that need it, not a privacy-first stance.)

None of this is deliverable without (a) a stage → provider routing layer, and (b) a way to verify a model swap didn't silently degrade report quality.

## What exists today

**Dispatch side (unchanged in shape since April 2026):** One provider for the whole run, `BRISTLENOSE_LLM_PROVIDER`, resolved by the CLI's ladder (`--llm` → env → current provider written by `configure`/`use` → sole configured key → diagnose; `config.py` `_derive_provider`, [design-cli-provider-selection.md](design-cli-provider-selection.md)). `LLMClient` in [bristlenose/llm/client.py](../bristlenose/llm/client.py) dispatches `analyze()` to one of five backends (Claude, ChatGPT, Azure, Gemini, Ollama). No per-stage runtime configuration and no `stage:` kwarg on `analyze()` — but stage identity already reaches every call through the `_stage_id` ContextVar (`llm/telemetry.py`, `stage()`), which is the seam a resolver can read without threading a kwarg through every caller. Beyond "JSON parses and validates", the client now repairs malformed structured output (`_validate_repairing`) and recognises truncation as its own outcome; neither is a quality measure. `llm-calls.jsonl` records tokens, cache tokens, outcome and cost per call, and `llm/cohort-baselines.json` feeds cost forecasts — so cost is measured; **quality still is not**.

**Display side (shipped May 2026, v1.5 + v1.9):** A read-only **catalogue surface** in `bristlenose/pipeline_view/` declares per-stage backends, their eligibility predicates against host facts, and editorial quality ratings per (stage, backend) cell. The catalogue is consumed by the React Settings → Pipeline tab and the CLI `bristlenose pipeline` command — making per-stage backend choice **legible** to researchers, without committing to auto-pick logic. See [design-pipeline-view.md](design-pipeline-view.md). This means we now have *editorial* per-stage quality ratings as catalogue data, even though no runtime routing or eval-harness measurement exists.

### Corollary: model-identity drift is a symptom of the unbuilt selection side

Because the selection side is unbuilt, the *runtime* model is still one string per run — `settings.llm_model` for the cloud providers, `settings.local_model` for Ollama, `settings.azure_deployment` for Azure — read by `LLMClient` on every call ([bristlenose/llm/client.py](../bristlenose/llm/client.py)), seeded from `providers.py` `default_model`. The descriptive catalogue *selects nothing*: it is consumed only by `cli.py` (`pipeline` command) and `server/routes/pipeline.py` (`build_pipeline_view`) to render. So three surfaces each independently assert "the default model," and they can disagree — because there is no single authority that selects:

| Surface | Holds (Gemini), 5 Jun 2026 | Role |
|---|---|---|
| `providers.py` `default_model` | `gemini-2.5-flash` | seeds `settings.llm_model` — the real runtime decider |
| `LLMProvider.swift` `defaultModel` / `availableModels` | `gemini-2.5-flash` | desktop Settings picker that *writes* `llm_model` |
| `pipeline_view/catalogue.py` `ModelOption(default=True)` | `gemini-2.5-pro` | renders the Pipeline tab; selects nothing |

(5 Jun: the catalogue listed Pro because Pro was the only Gemini model anyone had rated.)

> **Since 5 Sep 2026 the three agree** — all hold `gemini-3.8-flash` — **and tests hold them there**: `tests/pipeline_view/test_models.py` (`test_catalogue_ids_match_the_shipping_model_lists`, `test_catalogue_default_model_is_the_registry_default`) and `tests/test_llm_sampling_params.py` (`test_swift_and_python_agree_on_every_provider_default`, `test_every_offered_model_can_produce_a_cost_estimate`). Gemini now ships unrated on purpose (the `_LLM_QUALITY` comment in `catalogue.py`). That is agreement by guard, not unification: there are still N copies, and the tests only stop them drifting apart. Commits: "pipeline view: offer the models we ship, and stop offering one that 404s", "gemini: both picker models are retired for new users — the default was already broken". **This divergence is not a bug to paper over with a code comment** — it's the expected shape of N consumers with no shared selector. Wiring the catalogue as the source that both seeds `llm_model` and feeds the picker (the selection side, below) collapses the three to one and **dissolves the divergence**.

**Model retirement is orthogonal — and stays a standing chore.** A single source of truth does not stop a provider retiring a model ID (an external-world event). It only (a) shrinks the fix from N edits to 1, and (b) makes it *catchable* via a guard that the source-of-truth IDs ∈ `pricing.PRICING` (or a live model list). **The `PRICING` half shipped** for the Swift picker (`test_every_offered_model_can_produce_a_cost_estimate`); detecting that a provider has *retired* an ID (a live model-list check) is still open. Worked example (5 Jun 2026): `gemini-2.0-flash` was retired by Google 3 Mar 2026 yet survived as the Swift default for months, because the swap costs two edits in a file no Python test sees, and no automated check knows a model is retired. Until unification lands, every retirement is an N-place patch; after it, it's one place plus a guard. The guard is the durable win — pin it on the unified source once there is one; `LLMProvider.swift` is still the live desktop picker today.

### Interim model pickers: fix, don't grow

Until the selection side below is built, a handful of sites each decide a model
on their own — some by fixed default, some by a ladder over RAM, chip or what
is installed. They are **interim**, and they are held to one rule:

> **Fix, don't grow.** A wrong tag, a retired model ID, a broken fallback, a
> mismatch with what the runtime actually loads — fix it, in place, small. A new
> tier, a new ladder rung, a new hardware variable, a per-stage choice, a second
> list of "good" models, or a new place that picks — **don't**. That is this
> doc's work, and a local version of it is one more copy the resolver has to
> retire. If the fix you need is bigger than a small edit, write it down here
> (Open questions, or the inventory below) instead of building it.

Each site carries a comment naming this section; `tests/test_interim_model_pickers.py`
fails if one loses it, so the list below and the code stay in step.

| Site | What it picks, and on what | Destination |
|---|---|---|
| `bristlenose/providers.py` `ProviderSpec.default_model` | cloud default per provider (fixed) | catalogue `ModelOption(default=True)` |
| `bristlenose/config.py` `local_model`, `whisper_model`, `whisper_backend` | the run's defaults (fixed) | the resolver |
| `bristlenose/ollama.py` `PREFERRED_MODELS`, `DEFAULT_MODEL`, `check_ollama` | CLI local model: preferred list, then any `llama`/`mistral`/`qwen` installed | catalogue `local` `BackendOption.models` |
| `bristlenose/cli.py` `_use_local_model` | which local model `configure local` saves (installed vs found) | the resolver |
| `bristlenose/utils/hardware.py` `recommended_whisper_backend`, `recommended_whisper_model` | Whisper backend by chip + MLX; model size by RAM | catalogue transcription `BackendOption` + eligibility |
| `bristlenose/stages/s05_transcribe.py` `_resolve_backend`, `MLX_REPO_FOR_MODEL` | `auto` → mlx / faster-whisper; short name → mlx-community repo | catalogue transcription `ModelOption.id` |
| `desktop/…/LLMProvider.swift` `defaultModel`, `availableModels`, `OllamaCatalog` (`curated`, `recommendedTag`, `tagForRAM`) | desktop picker lists; the Ollama default by RAM (≥47 → 31b, ≥35 → 26b, ≥15 → e4b, else llama3.2:3b) | catalogue, read rather than mirrored |
| `desktop/…/TranscriptionSettingsView.swift` `@AppStorage("whisperModel")` | desktop Whisper default | catalogue |

The catalogue (`bristlenose/pipeline_view/catalogue.py` + `eligibility.py`) is
not on this list: it is the **destination**. It already carries the curated four
local models with their RAM floors, mirrored from `OllamaCatalog` and kept in
step by hand; making the others read it is the resolver's job, not a side quest.

**Worked example of the rule (11 Oct 2026).** The local tier had six
definitions and four different rules for "is this model installed?" — `doctor`
passed `llama3.2:1b` for `llama3.2:3b`, and the CLI's own hint (`ollama pull
llama3.2`) installed a tag the run did not ask for. The fix was one shared rule
matching Ollama's (`ollama.ollama_has_model`) and the right tag in the hints.
Unifying the six lists, or teaching the CLI the desktop's RAM ladder, was left
here instead.

### Migration inventory: where model/provider facts are baked today

Every row below is a site that must be hand-edited when a model retires or a fact moves — i.e. a place that should eventually *defer to the schema* (`ProviderSpec` for vendor facts, catalogue `ModelOption` for model facts) rather than hold its own copy. Grouped by the fact-tier each defers to. (Built 5 Jun 2026 from a repo-wide grep; line numbers refreshed or replaced by symbols 11 Oct 2026 — still verify before acting.)

**Already-diverged today** (same concept, different values shipped) — the proof this isn't theoretical:
- Anthropic "pricing": `providers.py` `pricing_url` (`docs.anthropic.com/.../models`) vs `LLMProvider.swift` `links` (`anthropic.com/pricing`)
- Gemini "get a key": `aistudio.google.com/apikey` (cli / billing_hints / doctor_fixes) vs `/app/apikey` (`LLMProvider.swift` `links`) vs bare `aistudio.google.com` (`cli.py` provider guidance)
- Gemini "pricing": `ai.google.dev/gemini-api/docs/pricing` (`providers.py`) vs `ai.google.dev/pricing` (`LLMProvider.swift` `links`)
- `pricing_url` is defined twice in Python alone (`providers.py` + `llm/pricing.py` `PRICING_URLS`)
- Anthropic billing (added 11 Oct 2026): `platform.claude.com/settings/billing` (`pipeline.py`) vs `console.anthropic.com/settings/billing` (`llm/billing_hints.py`)

**A · LLM model selection (which model runs)**
| Site | Holds | Defer to |
|---|---|---|
| `config.py` `llm_model` | global default — since 5 Sep derived from `PROVIDERS["anthropic"].default_model` (pinned by `test_anthropic_default_matches_field_default`), so it already defers | decision-engine default |
| `providers.py` `default_model` ×5 | per-provider runtime seed | `ModelOption(default=True)` |
| `llm/client.py` `settings.llm_model` | the dispatch read | `resolve(stage) → model` |
| `LLMProvider.swift` `defaultModel` / `availableModels` | desktop picker default / available | generated `models.json` |

**B · LLM model facts (cost, quality, eligibility)**
| Site | Holds | Defer to |
|---|---|---|
| `llm/pricing.py` `PRICING` | model → cost | `ModelOption.cost` |
| `llm/pricing.py` `_MODEL_PROVIDER` | reverse lookup | `ModelOption` under its `BackendOption` |
| `catalogue.py` `QualityRating` / `ModelOption.requires` | quality, eligibility | *(already the home)* |

**C · Provider facts + URLs (the "things we know about Anthropic" mini-DB)**
| Site | Holds | Defer to |
|---|---|---|
| `providers.py` `ProviderSpec` | name/aliases/env/sdk/**pricing_url** | *(the home — extend with the full URL set)* |
| `llm/pricing.py` `PRICING_URLS` · `llm/billing_hints.py` · `cli.py` provider guidance · `doctor_fixes.py` key/billing fixes · `llm/client.py` error copy · `pipeline.py` billing link | docs / console / keys / billing / get-a-key URLs | `ProviderSpec` |
| `doctor.py` key validators · `LLMValidator.swift` | API-endpoint URLs | `ProviderSpec.api_endpoint` |
| `LLMProvider.swift` `links` | homepage / pricing / console | generated `providers.json` |
| `KeychainHelper.serviceNames` ↔ `credentials_macos` | keychain service name | `ProviderSpec` |
| handoff "Data use" URLs | terms / data-use | `ProviderSpec.terms_url` *(not in code anywhere yet)* |

**D · Transcription (Whisper) model selection** — same baked-choice smell, and the active cause of the 5 Jun transcription failure
| Site | Holds | Defer to |
|---|---|---|
| `config.py` `whisper_model` | default `large-v3-turbo` | transcription `BackendOption.models` default |
| `s05_transcribe.py` `MLX_REPO_FOR_MODEL` / `_mlx_model_name` | hardcoded short → `mlx-community/...` repo map | `ModelOption.id` per transcription backend |
| `s05_transcribe.py` `transcribe_mlx` | bakes `path_or_hf_repo`; **still ignores** `BRISTLENOSE_WHISPER_MODEL_DIR` (only faster-whisper reads it, checked 11 Oct 2026) | catalogue + host-aware / bundled-model resolution |
| `utils/hardware.py` `recommended_whisper_backend` / `recommended_whisper_model` | chip + MLX → backend; RAM → model size | catalogue transcription eligibility |
| `TranscriptionSettingsView.swift:9` | desktop default `large-v3-turbo` | generated `models.json` |
| `pipeline_view/catalogue.py` transcription `BackendOption` | `models=[]` (no model-level granularity yet) | **THE home — populate it** |

**E · Local (Ollama) model selection** — added 11 Oct 2026; six definitions, see [§Interim model pickers](#interim-model-pickers-fix-dont-grow)
| Site | Holds | Defer to |
|---|---|---|
| `config.py` `local_model` · `providers.py` local `ConfigField` | default `llama3.2:3b` | catalogue `local` default |
| `ollama.py` `PREFERRED_MODELS` / `DEFAULT_MODEL` | CLI "suitable model" list (no Gemma) | catalogue `local` models |
| `LLMProvider.swift` `OllamaCatalog` | curated four + RAM ladder | catalogue + eligibility |
| `pipeline_view/catalogue.py` `local` `BackendOption` | the curated four, mirrored from Swift | **THE home** |

The transcription rows make the point sharpest: the model is resolved from a hardcoded map in *stage code* (`_mlx_model_name`), not from the catalogue — so a host-aware, bundled, or quality-rated choice is impossible, and on Apple Silicon it silently forces a 1.5 GB `large-v3-turbo` HuggingFace download (the 5 Jun failure). Wiring transcription model choice through the catalogue — whose transcription `BackendOption.models` is empty today — is the same fix as the LLM tier, not a separate effort.

### Future: selection-tier validation (validate, not decide)

The catalogue above describes *what can be selected* (which models belong to which provider, eligibility, quality). The **selection** layer — "which provider/model is current" — has no shared source of truth: CLI reads flags / env / project `.env` / the user-level config `.env` written by `configure` and `use` / the keychain (there is no TOML settings source — the `config.py` module docstring that mentions one is stale); desktop reads UserDefaults (`activeProvider` + a global `llmModel` that can desync from it); serve/React is read-only and uses the launch config. They converge only at `settings.llm_provider` / `llm_model`. Nothing validates the chosen `(provider, model)` pair against the catalogue — which is why a desktop provider/model desync (provider=`anthropic` + model=`gemini-2.5-flash`) reached the provider as a raw 404 and was then mislabelled "Transcription failed" (5 Jun 2026).

The next *non-render* use of the catalogue is **validate, not decide**: at config resolution, reject a `(provider, model)` pair the catalogue knows is impossible (a `gemini-*` model under `anthropic`) with a clear message instead of a 404. Permissive for custom/unknown models, and it **never overrides the user's choice** — so the catalogue stays informational, not the auto-selector (the auto-pick unification stays deferred). One check, in the shared sidecar layer, protects CLI + serve + desktop at once. The model→provider fact already exists in `llm/pricing.py` (`_MODEL_PROVIDER`) and implicitly in `ModelOption`-under-`BackendOption`; this step makes the catalogue its single home and first consumer beyond rendering. **Deferred — captured here so it's not lost.** The immediate desktop fix (inject the active provider's per-provider model at spawn, not the global `llmModel` — `BristlenoseShared.overlayPreferences`) ships separately and stops the desync at source; this guard is the cross-channel defence-in-depth on top.

> **Point fixes shipped since (11 Oct 2026), the catalogue-backed check still unbuilt.** `config.py` `_fill_provider_default_model` gives `--llm <provider>` that provider's default model on the CLI, and `_guard_orphan_desktop_model` drops a desktop model that belongs to another provider; the desktop injects the per-provider `llmModel_<provider>` key (`BristlenoseShared.swift`). Both are value-coherence patches at one seam each — under the [interim rule](#interim-model-pickers-fix-dont-grow), not a substitute for the check above.

## Proposed design

### 1. Stage → provider routing

> **Corrections to the proposal below (11 Oct 2026).** (1) There is no TOML settings source today; `[llm_stages]` needs one added, or another home (the user config `.env` cannot hold a table). (2) PII removal is not an LLM stage (Presidio only; `pii_llm_pass` refuses the run), so it is not a routing key. (3) Missing keys: `speaker_identification`, `discussion`, and the serve-time callers (`serve_autocode`, `serve_chat_lens`, `serve_signal_elaboration`, `serve_codebook_*`) — decide whether those are routable. (4) Three stage vocabularies exist (catalogue ids, `manifest.STAGE_ORDER`, telemetry module ids such as `s08_topic_segmentation`); the routing key should be the **catalogue id**, translated once at the boundary. (5) The fallback is the provider ladder, not a first-run prompt. The example ids are updated to shipped ones.

> **Status (May 2026):** The display side of this routing — what backend each stage uses today + which alternatives are eligible + how good each is for the stage — shipped via the read-only Pipeline view (`bristlenose/pipeline_view/`, v1.5 + v1.9). See [design-pipeline-view.md](design-pipeline-view.md). The selection / dispatch side described below (per-stage TOML config, `stage:` kwarg through `LLMClient`) **remains unbuilt**. The display-first path means whatever resolver eventually lands inherits the catalogue as its knowledge base — no separate spec to maintain.

Extend config with an optional `llm_stages` mapping. Absent key = fall back to global `llm_provider`.

```toml
# .bristlenose.toml
llm_provider = "anthropic"          # global default
llm_model = "claude-sonnet-4-6"

[llm_stages]
speaker_identification = { provider = "local",  model = "llama3.2:3b" }
topic_segmentation     = { provider = "local",  model = "llama3.2:3b" }
quote_extraction       = { provider = "anthropic", model = "claude-haiku-4-5-20251001" }
quote_clustering       = { provider = "anthropic", model = "claude-sonnet-4-6" }
thematic_grouping      = { provider = "anthropic", model = "claude-sonnet-4-6" }
```

`LLMClient.analyze()` grows a `stage: str` kwarg. Resolution order: `llm_stages[stage]` → global `llm_provider` → the provider ladder ([design-cli-provider-selection.md](design-cli-provider-selection.md)). The provider dispatch table stays exactly as it is — only the **selection** layer is new.

This preserves the no-fork principle ([design-modularity.md](design-modularity.md)): CLI and desktop both get the same routing. Desktop surfaces it as a settings panel; CLI uses TOML.

### 2. Apple Foundation Models — Swift-side, not Python

Worth separating signal from noise. The [apple/python-apple-fm-sdk](https://github.com/apple/python-apple-fm-sdk) repo is **not** Apple opening on-device inference to the Python ecosystem. Reading the README and examples, it's a narrow shim aimed at Swift developers who want to evaluate their Swift Foundation Models app from a Python notebook — batch inference, transcript replay, quality analysis. Apple still positions Swift as the production path; Python is an eval sidecar for Swift app developers.

For Bristlenose this means the blessed route to Apple's on-device model is **Swift in the desktop host**, exposed to the Python sidecar over a **new** request channel (key injection today is one-way, env vars at spawn; there is no Python→Swift request path yet) — not `pip install apple-fm-sdk` inside the PyInstaller bundle. Concretely:

- Swift host registers an FM endpoint (analogous to how it already injects API keys for cloud providers — see [bristlenose/llm/CLAUDE.md](../bristlenose/llm/CLAUDE.md) on the sidecar credential flow).
- Python sidecar gets a new `"apple-fm"` provider whose `_analyze_apple()` calls the Swift-side endpoint and awaits a structured response.
- Availability gated by macOS 26 + Apple Intelligence + compatible Mac. CLI distributions (Homebrew, pip, Snap, Linux) never see this provider.

**Consequences:**

- **CLI parity is out of scope for Apple FM.** First explicit break from [design-modularity.md](design-modularity.md)'s no-fork principle. Justified: the feature is structurally tied to a macOS entitlement and Apple silicon. Document as a capability-gate, not a fork.
- **Structured output translation lives Swift-side.** Swift's `@Generable` is where the Pydantic schema needs to land. Two viable paths, both confirmed against the corpus (18 May 2026): (a) compile-time `@Generable` structs translated from our Pydantic models; (b) runtime `DynamicGenerationSchema` + `GenerationSchema(root:dependencies:)` for codebook stages where tags are user-defined. Nested `Generable` types and enums-with-associated-values are documented as supported, so `QuoteCluster` → `Quote[]` shapes translate without restructuring.
- **Starting role:** `topic_segmentation` (and perhaps `speaker_identification`) — per-session, short prompts, small-context-friendly, benefit most from "stays on device". Two compounding reasons: small context fits, and these are the lowest-guardrail-risk stages (see [design-stage-backends.md](design-stage-backends.md) §"Guardrails are an orthogonal axis"). Not `quote_clustering` / `thematic_grouping`, which need cross-session reasoning and a larger context than the on-device model provides.
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

- The per-stage view already exists as `bristlenose pipeline` (and the Settings ▸ Pipeline tab), not in `doctor`; per-stage choices belong there. Apple FM shows its `is_available()` reason when missing.
- Desktop settings panel: per-stage dropdown seeded with the provider's compatible models. Groupings: "On this Mac (free)", "Budget cloud", "Frontier cloud", "Enterprise (Azure)".
- First-run: no change. Global default still works. Per-stage routing is an optional power-user layer, not something a new user has to configure.

## Sequencing

> **Status (May 2026):** v1.5 + v1.9 took a different sequence than originally proposed below — the **display-first** path (catalogue surface in the Pipeline view) shipped before items 1 and 2. The display side makes per-stage backend choice legible without committing to runtime dispatch logic; researchers stay in control. The original items 1–5 sequence below remains correct for the unbuilt selection / eval / Apple-FM work.

Status per item as of 11 Oct 2026 in _italics_.

1. **Eval harness first.** Without it, every subsequent change is faith-based. Estimate: ~1 week including golden-set curation on 3–4 FOSSDA sessions. _Not built (no `bristlenose eval`). Precursors that can feed the golden-set design: `experiments/quote-stability/` (per-model quote recovery on FOSSDA, plus `run_s08.py` for segmentation), `scripts/codebook-harness.py` with `tests/fixtures/codebook-golden/`, and the `experiments/pii_*` corpora. The catalogue's ratings stay `source=editorial` because each of these measures one dimension ("ratings: the measurements did not move them, and say why in the file")._
2. **Stage routing config + `stage:` kwarg through `LLMClient`.** Purely mechanical. ~1 day. No new provider needed — immediate value: run `quote_extraction` on Haiku, keep `thematic_grouping` on Sonnet, measure the cost delta against quality. _Not built. Read the stage from the `_stage_id` ContextVar rather than threading a kwarg; needs a settings source for the table (no TOML today)._
3. **Apple FM provider.** Behind a feature flag. Target stages: `topic_segmentation` (originally also `pii_removal`, which is not an LLM stage). Requires the macOS 26 + Apple Intelligence gate, the Pydantic-to-`@generable` translator, and a sandbox entitlement spike. ~1 week. _Not built: placeholders only (`apple_fm` backend and `apple_foundation_models` stage in the catalogue, `host.apple_fm_status="unknown"`)._
4. **Gemma / larger local models for mid-tier stages.** Picks up [design-gemma4-local-models.md](design-gemma4-local-models.md) with the routing layer now in place. _Partly shipped, out of order: Gemma 4 is a **global** local-model choice on the desktop (`OllamaCatalog`) and is listed in the catalogue with RAM floors ("populate the local-model catalogue from the desktop picker"). Not per-stage, and the CLI's own list (`ollama.py` `PREFERRED_MODELS`) has no Gemma — an interim gap, not to be closed ad hoc._
5. **Hardware-aware defaults.** Detect M-series tier, RAM, Apple Intelligence status; suggest a routing profile. Uses the eval harness to validate each profile's quality on a small sample before recommending it. _Partly shipped, as two unrelated ladders: the desktop's Ollama default by RAM (`OllamaCatalog.recommendedTag`) and the Whisper backend/size suggestion (`utils/hardware.py`). Neither is a routing profile, neither is eval-validated, no Apple Intelligence detection. Both are [interim pickers](#interim-model-pickers-fix-dont-grow)._

## Open questions

- Swift-side FM endpoint: what's the XPC/messaging shape between Swift host and Python sidecar for a structured LLM call? Extension of the existing credential-injection bridge, but request/response is heavier. Needs a small spike.
- ~~Is Swift `@Generable` rich enough for our nested schemas (e.g. `QuoteCluster` with nested quote lists)?~~ **Resolved 18 May 2026 against corpus:** yes — nested `Generable` types and enums-with-associated-values are documented as supported (`structured-output/generating-swift-data-structures-with-guided-generation.md`). Runtime-known schemas use `DynamicGenerationSchema`. Spike not needed for the schema-shape question; still needed for the XPC bridge shape above.
- What's the right eval cadence? On every provider/model config change manually? Nightly on a perf branch? Pre-release only?
- Do we expose eval scores to end users ("this config scores 0.87 precision on the reference set"), or keep it an internal tool? Leaning internal until the numbers are defensible. _Leaning-resolved: the ratings decision keeps user-facing quality `editorial` until a measurement covers the dimension (`design-decisions.md`, the `_LLM_QUALITY` comment in `catalogue.py`)._
- **Guardrails on sensitive UR content.** Apple's guardrails fire on input and output; refusals throw `LanguageModelSession.GenerationError.refusal(_:_:)` for guided generation. The eval harness needs a sensitive-content slice (healthcare, end-of-life, abuse) to measure violation rate per stage. Routing must downgrade rather than fail when a session hits a violation. Open: what's the user-facing UX when this happens — silent fallback to cloud (with notice), or explicit opt-in per session?

## What this document is not

- Not a commitment to implement all five stages. Item 1 (eval) + item 2 (routing) is the minimum useful slice. Everything after depends on what the eval shows.
- Not a plan to deprecate any cloud provider. The goal is routing, not replacement.
- Not pricing strategy. Touches cost-to-serve, but IAP pricing and LLM brokering are in the private delivery repo.
