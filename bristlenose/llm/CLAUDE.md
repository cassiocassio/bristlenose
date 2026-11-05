# LLM / Provider Context

## Prompt-template versioning and archive

Prompt templates in `bristlenose/llm/prompts/*.md` carry a `version:` field in their frontmatter. **Archive prior versions to `bristlenose/llm/prompts-archive/` before bumping the minor or major version** — the archive is the audit trail for prompt evolution and how we trace cohort-baseline regressions to specific wording changes.

**Patch-bump exception**: a patch-version bump (e.g. `0.1.0` → `0.1.1`) for a one-line addition that doesn't change the prompt's semantic contract — boundary-tag prefaces, typo fixes, formatting — does **not** require an archive copy. The git history of the `.md` file is sufficient for these. Archive when bumping the minor (`0.1.x` → `0.2.0`) or major version, or when the change list is substantive (multiple rule changes, framing shift, output-shape change). The 8-prompt M1 sentinel-tagging round (May 2026) was a patch bump under this exception.

If unsure, archive — disk is cheap, missed audit trails are not.

## Untrusted-input boundary (prompt injection)

Every render call site that interpolates participant-derived content into an LLM prompt **must** wrap it via `bristlenose.llm.boundary.wrap_untrusted(name, content)`. The helper produces a per-call random-nonce sentinel envelope and escapes closing-tag-shaped substrings as defence-in-depth. The covered variables are `transcript_text`, `quotes_json`, `transcript_sample`, `signals_text`, `formatted_quotes`. A unit test in `tests/test_prompt_boundary.py` reads each call site's source and fails closed if a future edit drops the wrapper. When adding a new prompt template that interpolates untrusted text: (1) add the system-prompt preface naming the `<untrusted_*>` envelope, (2) wrap the variable at the render call site, (3) add the new (file, variable) pair to `CALL_SITES` in the test. See `docs/design-prompt-injection-defence.md` for the threat model and the Phase B roadmap (label allowlist, red-team corpus).

## Lazy-import discipline

Provider SDKs (`anthropic`, `openai`, `google-genai`) and transcription backends (`ctranslate2`, `mlx_whisper`) **must be imported inside the functions that use them, not at module top**. Heavy imports at module-level pay their cost on every `bristlenose serve` boot regardless of which provider the user picks — typically 3–6 s of dead time on cold start, much of which is spent loading SDKs the user will never call.

**Pattern:**

```python
def call_anthropic(prompt: str) -> str:
    from anthropic import Anthropic  # imported on first call only
    client = Anthropic()
    ...
```

The cost moves from boot to first-use, where the user is already engaged with the app. Same total work, vastly better perceived performance — Sketch / Linear / modern Photoshop pattern, not 2003-Photoshop "warming up your filters" pattern.

**Convention:** any new provider, any new heavy library, any new optional backend — defer the import. Module-top `import anthropic` in new code is a review reject.

## Credential storage (Keychain)

API keys are stored securely in the system keychain. Uses native CLI tools — no Python keyring shim.

**Sandboxed desktop sidecar (Track C C3, Apr 2026):** Swift host reads Keychain via Security.framework at sidecar launch and injects keys as `BRISTLENOSE_*_API_KEY` env vars. Python never touches Keychain in this deployment — pydantic-settings picks the env vars up before `_populate_keys_from_keychain` runs. `credentials_macos.py` stays as-is and remains the happy path for **CLI Mac distros** (Homebrew, pip — not sandboxed, `/usr/bin/security` works fine). No Mac-only Python dep; no-fork principle preserved per `docs/design-modularity.md`.

- **CLI command**: `bristlenose configure <provider>` — prompts for key, validates with API, stores in keychain **and reads it back** (`credentials.set_verified`; a key that does not read back exits 1 rather than printing "Stored in Keychain"). Accepts `--key` option to bypass interactive prompt (useful in scripts or when TTY has issues)
- **Provider aliases**: `claude` → `anthropic`, `chatgpt`/`gpt` → `openai`, `gemini` → `google`
- **Priority order**: env var (`BRISTLENOSE_<PROVIDER>_API_KEY` or bare `ANTHROPIC_API_KEY`) → .env file → keychain. The plain unprefixed names are accepted via `AliasChoices` on the settings fields (prefixed form wins when both are set); `populate_by_name=True` keeps the field name usable for direct construction. Coverage tracks what each SDK/user actually reaches for: `ANTHROPIC_API_KEY`; `OPENAI_API_KEY`; `GOOGLE_API_KEY` + `GEMINI_API_KEY` (google-genai reads both); Azure gets `AZURE_API_KEY` **and** the openai-SDK-native `AZURE_OPENAI_API_KEY` / `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_DEPLOYMENT`. `local` (no key) and `miro` (`MIRO_ACCESS_TOKEN` isn't a name anyone expects unprefixed) are intentionally left prefix-only. On the sandboxed desktop sidecar the env var is always set by Swift before launch, so keychain is effectively bypassed there; CLI Mac users hit the keychain fallback as usual.
- **macOS**: `bristlenose/credentials_macos.py` — uses `security` CLI (add-generic-password, find-generic-password, delete-generic-password). Service names: "Bristlenose Anthropic API Key", "Bristlenose OpenAI API Key", "Bristlenose Google Gemini API Key". **`security` reads the login keychain only** — the Mac app stores its keys in the data-protection keychain, which no unentitled process can see, so since 4 Sep 2026 the app keeps a login-keychain copy of all five CLI-read keys and adopts what `configure` writes there; a key set in either place is seen by both (`docs/design-keychain.md` § "One keyspace, two keychains")
- **Linux**: `bristlenose/credentials_linux.py` — uses `secret-tool` (Secret Service API). Falls back to `FileCredentialStore` if secret-tool unavailable
- **Fallback**: `bristlenose/credentials.py` — `FileCredentialStore` persists to a user-level config `.env` (`~/.config/bristlenose/.env`, honours `$SNAP_USER_COMMON`/`$XDG_CONFIG_HOME`), mode `0o600`. Same file is loaded by `config._find_env_files()`, so `configure` on a headless box (no keyring) actually leaves the user configured — no `export …` dead-end. `EnvCredentialStore` (read-only, env vars) remains the base class + a helper for pure reads
- **Integration**: `_populate_keys_from_keychain()` in `config.py` loads from keychain when settings don't have keys from env/.env
- **Doctor display**: shows platform-specific suffix when key source is keychain — "(Keychain)" on macOS, "(Secret Service)" on Linux
- **Validation**: keys are validated before storing — catches typos/truncation
- **Gotcha — `validation_alias` needs `populate_by_name`**: the API-key fields carry `validation_alias=AliasChoices("BRISTLENOSE_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY")` so the plain name works. But once a field has an explicit `validation_alias`, pydantic **stops** populating it from the field name — so `BristlenoseSettings(anthropic_api_key=…)` and `load_settings(anthropic_api_key=…)` silently no-op (field stays `""`) unless `model_config` sets `populate_by_name=True`. It does. If you add a `validation_alias` to any other field, keep that flag set or direct construction / `**overrides` breaks quietly. First alias listed wins when several are present (prefixed beats bare)
- **Tests**: `tests/test_credentials.py` — covers env store, `FileCredentialStore` (persist/roundtrip/perms/upsert/delete), unprefixed env aliases, and keychain population (macOS tests run on macOS, Linux tests skipped)
- **Design doc**: `docs/design-keychain.md`

## Local LLM provider (Ollama)

`bristlenose/ollama.py` handles Ollama detection, installation, and model management. `bristlenose/providers.py` defines the provider registry.

**Which model runs is an interim decision everywhere — fix, don't grow.** Defaults, preferred lists, RAM ladders and the Whisper hardware suggestion are all stand-ins for the per-stage resolver in `docs/design-pluggable-llm-routing.md`, whose §"Interim model pickers" lists every site (each carries a comment; `tests/test_interim_model_pickers.py` keeps the list honest). Fix a wrong tag, a retired ID or a broken fallback in place; don't add tiers, ladders, hardware rules or a new place that picks — write it down in that doc instead. "Is this model installed?" has one answer, Ollama's: `ollama.ollama_has_model` (a tag is its own name; a bare name means `:latest`).

- **Provider registry**: `ProviderSpec` dataclass with `name`, `display_name`, `aliases`, `default_model`, `sdk_module`, `pricing_url`. `PROVIDERS` dict maps canonical names to specs. `resolve_provider()` normalises aliases (claude→anthropic, chatgpt→openai, ollama→local)
- **First-run guidance (no menu, no prompts)**: `_print_provider_guidance()` in `cli.py` — when no provider is resolvable (`ProviderResolution` status `none`: zero keys, no explicit choice), prints where to get a key for each cloud provider + the one command (`bristlenose configure <provider>`) and exits (`_maybe_guide_provider_setup`; TTY exit 0, non-TTY a terse error + exit 2). No numbered picker, no cost/opinion copy, and `run`/`analyze` **never prompt** — 2+ keys with no choice exits 2 teaching `bristlenose use`. The "stores it securely (…)" label is resolved live via `get_credential_store_label()` (Keychain / Secret Service / config file). `configure local` routes to `_setup_local_provider()` (Ollama installer) so the verb is uniform across providers. Provider resolution is the current-provider ladder (`--llm` → env → `.env`/current → sole configured key → diagnose) — spec + rationale in `docs/design-cli-provider-selection.md`
- **Ollama detection**: `check_ollama()` hits `http://localhost:11434/api/tags` to check if running and list models. `is_ollama_installed()` checks PATH. `validate_local_endpoint()` returns `(True, "")`, `(False, error)`, or `(None, error)` for connection issues
- **Auto-install**: `get_install_method()` returns "brew"/"snap"/"curl"/None based on platform and available tools. `install_ollama(method)` runs the appropriate command. Priority: macOS prefers brew, Linux prefers snap, fallback to Ollama's install script, downloaded and checked before it runs (never `curl | sh`, whose exit status hides a failed download). Falls back to download page on failure
- **Auto-start**: `start_ollama_serve()` — macOS uses `open -a Ollama`, Linux uses `ollama serve` in background with `start_new_session=True`. Waits 2s and verifies running
- **Model auto-pull**: `pull_model()` runs `ollama pull` with stdout passthrough for progress bar. Triggered via interactive prompt when no suitable model found
- **Preferred models**: `PREFERRED_MODELS` list in order — `llama3.2:3b` (default), `llama3.2`, `llama3.2:1b`, `llama3.1:8b`, `mistral:7b`, `qwen2.5:7b`. No Gemma: the desktop's `OllamaCatalog` offers Gemma 4 by RAM and this list does not — a known interim gap, left for the resolver
- **LLM client**: `_analyze_local()` in `llm/client.py` uses OpenAI SDK with `base_url=settings.local_url`. Asks for the schema as `response_format` `json_schema` (the plain Pydantic schema, not strict; also in the system prompt), falling back once to `json_object` if the server refuses it (remembered per client, as any-llm). Up to 3 attempts; a retry is the first request plus one user turn naming what was wrong (`failure_summary`, never the reply). The "~85% vs ~99%" figure was never measured: RE#R105 (24 Oct 2026) found llama3.2:3b under plain JSON mode echoing the schema back and failing every run
- **Doctor integration**: `check_local_provider()` validates endpoint and model. Three fix keys: `ollama_not_installed`, `ollama_not_running`, `ollama_model_missing`. Fix messages are context-aware — suggest `--llm claude` only if user has Anthropic key, etc.
- **Config**: `local_url` (default `http://localhost:11434/v1`), `local_model` (default `llama3.2:3b`)
- **Tests**: `tests/test_providers.py` (47 tests), `tests/test_provider_horror_scenarios.py` (31 tests) — covers all error paths, fix messages, interactive prompt logic

## any-llm (the sixth provider)

`bristlenose/llm/anyllm.py` holds everything specific to mozilla-ai/any-llm (`any-llm-sdk`, optional extra `bristlenose[any-llm]`, exact pin `==1.44.0`, the first release allowing `anthropic>=1`; 1.27.1 to 1.43.0 cap `anthropic<1`). Provider id `anyllm` (aliases `any-llm`, `any_llm`), model in `anyllm_model` / `BRISTLENOSE_ANYLLM_MODEL` as `provider:model`. Plan and rationale: `docs/design-any-llm.md`.

**The working rules for the any-llm provider (one readiness answer, schema as a dict, typed errors, no `temperature`/`max_tokens`, thinking off, gateway errors, refused inner prefixes, destination, retries, keys, telemetry, logging via `failure_summary`, Rich escaping, tests, per-inner-provider keys) are in [`gotchas.md`](gotchas.md#any-llm-the-sixth-provider), 17 bullets.** Read them before touching `bristlenose/llm/anyllm.py` or `--anyllm`. Design: `docs/design-any-llm.md`.

## LLM concurrency

Per-participant LLM calls (stages 5b, 8, 9) run concurrently, bounded by `llm_concurrency` (default 3). Stages 10 + 11 also run concurrently with each other (single call each, independent inputs).

- **Config**: `llm_concurrency: int = 3` in `bristlenose/config.py`. Controls max concurrent API calls via `asyncio.Semaphore`
- **Pattern**: each parallelised stage uses `asyncio.Semaphore(concurrency)` + `asyncio.gather()`. The semaphore is created per stage call, not shared across stages (stages still run sequentially relative to each other)
- **Stage 5b** (pipeline.py): heuristic pass runs synchronously for all participants first, then LLM refinement runs concurrently. Results collected as `dict[str, list]` via gather + dict conversion
- **Stage 8** (topic_segmentation.py): `segment_topics()` accepts `concurrency` kwarg. Inner `_process()` closure wraps `_segment_single()` with semaphore. `asyncio.gather()` preserves input order
- **Stage 9** (quote_extraction.py): `extract_quotes()` accepts `concurrency` kwarg. Same pattern. Results flattened from `list[list[ExtractedQuote]]` to `list[ExtractedQuote]` in input order
- **Stages 10+11** (pipeline.py): `cluster_by_screen()` and `group_by_theme()` run via `asyncio.gather()` — no semaphore needed (only 2 calls). Applied in both `run()` and `run_analysis_only()`
- **Safety**: all per-participant calls are fully independent (no shared mutable state). `LLMClient` is safe to share — stateless across calls except for cached httpx client. asyncio's single-threaded model prevents lazy-init races
- **Error handling**: preserved from sequential version. Failed participants get empty results (empty `SessionTopicMap`, empty quote list). Exceptions logged, pipeline continues
- **Ordering**: `asyncio.gather()` returns results in input order — quote ordering by participant is preserved
- **Dependency chain**: stage 8 must complete before stage 9 (topic maps feed quote extraction). Stages 10+11 depend on stage 9 output. Concurrency is within-stage only, not cross-stage

## max_tokens and truncation detection

Default `llm_max_tokens` is **64000** (set in `config.py`, raised from 32768 on 17 Apr 2026 after FOSSDA baseline hit truncation on a dense session). This is the output token ceiling per LLM call — users only pay for tokens actually generated, not the limit. All 6 providers detect when the response is truncated and raise `RuntimeError` with an actionable message pointing to `BRISTLENOSE_LLM_MAX_TOKENS` in `.env`.

**Why 64000 not 65536**: Anthropic's `claude-sonnet-4-20250514` hard-caps output at 64000 (decimal), not 65536 (2^16). GPT-5 allows 128K, Gemini 2.5 Pro allows 65K. 64000 is the portable ceiling across all three frontier providers. Going higher requires per-provider branching — not worth the complexity until smart-splitting lands.

- **Anthropic**: checks `response.stop_reason == "max_tokens"`
- **OpenAI / Azure / Local**: checks `response.choices[0].finish_reason == "length"`
- **Gemini**: checks `response.candidates[0].finish_reason` for `"MAX_TOKENS"` or `"2"`

If the default is too low for a workload (very long transcripts with many quotes), the error message tells the user exactly what to set and where. Quote extraction is the most output-heavy stage — a 1-hour transcript can produce 80-100 quotes at ~150 tokens each. Tests in `tests/test_llm_truncation.py`.

## Gotchas

**The full entries — the incident, the measurement, the fix — are in [`gotchas.md`](gotchas.md), by theme.** Read the theme's section before working in that area. This index is the rule and the tell, nothing more: one line per entry, same order as the file. Add a new gotcha to `gotchas.md` and its headline here.

**Cost estimate and shipped baselines** (2) — [full entries](gotchas.md#cost-estimate-and-shipped-baselines)

- A data file shipped EMPTY is a feature that never runs — and `cohort-baselines.json` was empty for…
- …and the suite could not see any of it, because every fixture stubbed the file it was meant to test.

**Provider registry and model defaults** (5) — [full entries](gotchas.md#provider-registry-and-model-defaults)

- Provider registry — `bristlenose/providers.py` is the single source of truth for provider metadata…
- `--llm <provider>` fills that provider's default model (CLI).
- A model-default value is hardcoded in ~40 places — a bump is never a one-line change.
- Azure cost estimation returns None — deployment names are user-defined strings, not model names, so…
- A deprecation page carrying no retirement date is not evidence the model is obtainable.

**Claude, ChatGPT and Azure requests** (4) — [full entries](gotchas.md#claude-chatgpt-and-azure-requests)

- Anthropic SDK timeout heuristic — the SDK (v0.77+) rejects non-streaming requests when…
- Azure OpenAI uses `AsyncAzureOpenAI` — same OpenAI SDK, different client class. Key differences…
- gpt-4o / gpt-4o-mini cap output at 16384 — the 64000 default is Claude-tuned.
- Sampling parameters on Claude are per-MODEL, and rejected with a 400 — not ignored.

**Gemini** (6) — [full entries](gotchas.md#gemini)

- Gemini uses native JSON schema — not JSON mode or tool use. `response_mime_type="application/json"`…
- `_flatten_schema_for_gemini()` — Gemini's schema support is a subset of JSON Schema. The helper…
- Gemini async via `.aio` property — `google.genai.Client` exposes async methods as…
- Gemini lazy client init — same `_get_or_create_client()` pattern as other providers. Client is…
- `google.genai.errors.APIError.details` is the WHOLE response JSON, not the details array.
- google-genai sends with NO timeout and NEVER retries unless asked

**Local (Ollama)** (4) — [full entries](gotchas.md#local-ollama)

- Local LLM uses OpenAI SDK — Ollama is OpenAI-compatible, so `_analyze_local()` in `llm/client.py`…
- Local model retry logic — `_analyze_local()` retries a reply that doesn't parse or validate up to 3…
- `_needs_provider_prompt()` checks Ollama status — for local provider, it calls…
- Local-provider preflight uses the openai SDK, not the `ollama` package.

**Errors, retries and refusals** (4) — [full entries](gotchas.md#errors-retries-and-refusals)

- Provider-error strings rendered via Rich need escaping. `recovery_message` interpolates `str(exc)`…
- Cloud clients carry `max_retries=_CLOUD_MAX_RETRIES` (6); don't hand-roll backoff.
- A transport failure is `network` by its class, not its words
- A provider's content filter or refusal is `ContentBlockedError`, never an empty reply

**Testing LLM calls** (3) — [full entries](gotchas.md#testing-llm-calls)

- A bare `AsyncMock` accepts any kwarg, so the suite cannot see a request-SHAPE break at all.
- A second request builder drifts from the first the day a default moves.
- A terse fixture prompt is a different test from the product.

**Prompts and platform quirks** (2) — [full entries](gotchas.md#prompts-and-platform-quirks)

- Python 3.14 + pydantic v1 crash — `import presidio_analyzer` → spacy → pydantic v1 → `ConfigError`…
- A length rule in a prompt is calibrated per model, and the production model obeys where the cheap…
