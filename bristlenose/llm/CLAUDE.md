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

- **CLI command**: `bristlenose configure <provider>` — prompts for key, validates with API, stores in keychain. Accepts `--key` option to bypass interactive prompt (useful in scripts or when TTY has issues)
- **Provider aliases**: `claude` → `anthropic`, `chatgpt`/`gpt` → `openai`, `gemini` → `google`
- **Priority order**: env var (`BRISTLENOSE_<PROVIDER>_API_KEY` or bare `ANTHROPIC_API_KEY`) → .env file → keychain. On the sandboxed desktop sidecar the env var is always set by Swift before launch, so keychain is effectively bypassed there; CLI Mac users hit the keychain fallback as usual.
- **macOS**: `bristlenose/credentials_macos.py` — uses `security` CLI (add-generic-password, find-generic-password, delete-generic-password). Service names: "Bristlenose Anthropic API Key", "Bristlenose OpenAI API Key", "Bristlenose Google Gemini API Key"
- **Linux**: `bristlenose/credentials_linux.py` — uses `secret-tool` (Secret Service API). Falls back to `EnvCredentialStore` if secret-tool unavailable
- **Fallback**: `bristlenose/credentials.py` — `EnvCredentialStore` reads from env vars (cannot write)
- **Integration**: `_populate_keys_from_keychain()` in `config.py` loads from keychain when settings don't have keys from env/.env
- **Doctor display**: shows platform-specific suffix when key source is keychain — "(Keychain)" on macOS, "(Secret Service)" on Linux
- **Validation**: keys are validated before storing — catches typos/truncation
- **Tests**: `tests/test_credentials.py` — 25 tests (macOS tests run on macOS, Linux tests skipped)
- **Design doc**: `docs/design-keychain.md`

## Local LLM provider (Ollama)

`bristlenose/ollama.py` handles Ollama detection, installation, and model management. `bristlenose/providers.py` defines the provider registry.

- **Provider registry**: `ProviderSpec` dataclass with `name`, `display_name`, `aliases`, `default_model`, `sdk_module`, `pricing_url`. `PROVIDERS` dict maps canonical names to specs. `resolve_provider()` normalises aliases (claude→anthropic, chatgpt→openai, ollama→local)
- **Interactive first-run prompt**: `_prompt_for_provider()` in `cli.py` — when no API key and default provider, offers 3 choices: Local (free), Claude (~$1.50/study), ChatGPT (~$1.00/study). Only triggers for default anthropic case; explicit `--llm` choices skip the prompt
- **Ollama detection**: `check_ollama()` hits `http://localhost:11434/api/tags` to check if running and list models. `is_ollama_installed()` checks PATH. `validate_local_endpoint()` returns `(True, "")`, `(False, error)`, or `(None, error)` for connection issues
- **Auto-install**: `get_install_method()` returns "brew"/"snap"/"curl"/None based on platform and available tools. `install_ollama(method)` runs the appropriate command. Priority: macOS prefers brew, Linux prefers snap, fallback to curl script. Falls back to download page on failure
- **Auto-start**: `start_ollama_serve()` — macOS uses `open -a Ollama`, Linux uses `ollama serve` in background with `start_new_session=True`. Waits 2s and verifies running
- **Model auto-pull**: `pull_model()` runs `ollama pull` with stdout passthrough for progress bar. Triggered via interactive prompt when no suitable model found
- **Preferred models**: `PREFERRED_MODELS` list in order — `llama3.2:3b` (default), `llama3.2`, `llama3.2:1b`, `llama3.1:8b`, `mistral:7b`, `qwen2.5:7b`
- **LLM client**: `_analyze_local()` in `llm/client.py` uses OpenAI SDK with `base_url=settings.local_url`. Includes JSON schema in system prompt and 3 retries with exponential backoff for parse failures (~85% reliability vs ~99% for cloud)
- **Doctor integration**: `check_local_provider()` validates endpoint and model. Three fix keys: `ollama_not_installed`, `ollama_not_running`, `ollama_model_missing`. Fix messages are context-aware — suggest `--llm claude` only if user has Anthropic key, etc.
- **Config**: `local_url` (default `http://localhost:11434/v1`), `local_model` (default `llama3.2:3b`)
- **Tests**: `tests/test_providers.py` (47 tests), `tests/test_provider_horror_scenarios.py` (31 tests) — covers all error paths, fix messages, interactive prompt logic

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

Default `llm_max_tokens` is **64000** (set in `config.py`, raised from 32768 on 17 Apr 2026 after FOSSDA baseline hit truncation on a dense session). This is the output token ceiling per LLM call — users only pay for tokens actually generated, not the limit. All 5 providers detect when the response is truncated and raise `RuntimeError` with an actionable message pointing to `BRISTLENOSE_LLM_MAX_TOKENS` in `.env`.

**Why 64000 not 65536**: Anthropic's `claude-sonnet-4-20250514` hard-caps output at 64000 (decimal), not 65536 (2^16). GPT-5 allows 128K, Gemini 2.5 Pro allows 65K. 64000 is the portable ceiling across all three frontier providers. Going higher requires per-provider branching — not worth the complexity until smart-splitting lands.

- **Anthropic**: checks `response.stop_reason == "max_tokens"`
- **OpenAI / Azure / Local**: checks `response.choices[0].finish_reason == "length"`
- **Gemini**: checks `response.candidates[0].finish_reason` for `"MAX_TOKENS"` or `"2"`

If the default is too low for a workload (very long transcripts with many quotes), the error message tells the user exactly what to set and where. Quote extraction is the most output-heavy stage — a 1-hour transcript can produce 80-100 quotes at ~150 tokens each. Tests in `tests/test_llm_truncation.py`.

## Gotchas

- **Anthropic SDK timeout heuristic** — the SDK (v0.77+) rejects non-streaming requests when `max_tokens > ~21K` with `ValueError: "Streaming is required for operations that may take longer than 10 minutes"`. The heuristic is `3600 * max_tokens / 128000 > 600`. Fix: pass `timeout=600.0` to `client.messages.create()`, which bypasses the check. This is already done in `_analyze_anthropic()`. If you ever remove the explicit timeout, the SDK will start rejecting quote extraction calls
- **Provider registry** — `bristlenose/providers.py` is the single source of truth for provider metadata (names, aliases, default models, SDK modules). `resolve_provider()` handles alias normalisation (claude→anthropic, azure-openai→azure, ollama→local). `load_settings()` in `config.py` calls the registry to normalise aliases
- **Azure OpenAI uses `AsyncAzureOpenAI`** — same OpenAI SDK, different client class. Key differences from regular OpenAI: needs `azure_endpoint` and `api_version` on client init, uses deployment name (not model name) as the `model` parameter. `configure azure` stores only the API key in keychain — endpoint and deployment are non-secret, go in env vars or `.env`
- **Azure cost estimation returns None** — deployment names are user-defined strings, not model names, so `estimate_cost()` can't look up pricing. The pricing URL is still shown
- **Local LLM uses OpenAI SDK** — Ollama is OpenAI-compatible, so `_analyze_local()` in `llm/client.py` uses the same `openai.AsyncOpenAI` client with `base_url=settings.local_url` and `api_key="ollama"` (required by SDK but ignored by Ollama)
- **Local model retry logic** — `_analyze_local()` retries JSON parsing failures up to 3 times with exponential backoff; local models are ~85% reliable vs ~99% for cloud
- **`_needs_provider_prompt()` checks Ollama status** — for local provider, it calls `validate_local_endpoint()` to check if Ollama is running and has the model; for cloud providers, it just checks if the API key is set
- **Gemini uses native JSON schema** — not JSON mode or tool use. `response_mime_type="application/json"` + `response_schema=schema_dict` on the `GenerationConfig`. This gives structured output without tool-call overhead
- **`_flatten_schema_for_gemini()`** — Gemini's schema support is a subset of JSON Schema. The helper inlines `$defs`/`$ref` (recursive resolution), converts `anyOf`-with-null to `{"type": "STRING", "nullable": true}`, maps Python types to Gemini types (`string`→`STRING`, `integer`→`INTEGER`, etc.), and strips unsupported keys (`title`, `default`, `$defs`). Without this, Gemini rejects Pydantic-generated schemas
- **Gemini async via `.aio` property** — `google.genai.Client` exposes async methods as `client.aio.models.generate_content()`, not a separate `AsyncClient` class. This is different from the Anthropic/OpenAI pattern
- **Gemini lazy client init** — same `_get_or_create_client()` pattern as other providers. Client is created on first call, cached as `_gemini_client` on the `LLMClient` instance
- **`google.genai.errors.APIError.details` is the WHOLE response JSON, not the details array.** The attribute name is misleading: `.details` returns the entire response-body dict (`{"error": {"code": ..., "message": ..., "status": ..., "details": [...]}}`). The actual array (`API_KEY_INVALID` reasons, etc.) lives nested at `details["error"]["details"]`. When classifying Gemini errors by reason (e.g. distinguishing `INVALID_ARGUMENT`-with-`API_KEY_INVALID`-detail from a plain bad argument), read `getattr(exc, 'details', None)` → guard `isinstance(blob, dict)` → drill into `blob["error"]["details"]` → guard `isinstance(inner, list)` before iterating. See `bristlenose/preflight/api_key.py:_validate_google` for the canonical traversal.
- **Local-provider preflight uses the openai SDK, not the `ollama` package.** Ollama exposes an OpenAI-compatible HTTP API, so the runtime `_analyze_local()` and the preflight `_validate_local()` both speak openai-SDK. The `ollama` Python package is **not** a project dependency — don't import it for new local-provider work. `openai.APIConnectionError` covers Ollama-not-running; `openai.NotFoundError` covers model-not-pulled. The recovery route is `recovery_message` switching on `(provider="local", error_class)` to emit Ollama-specific copy from the generic 4-bucket vocabulary.
- **Provider-error strings rendered via Rich need escaping.** `recovery_message` interpolates `str(exc)` from the provider SDK into copy that's `console.print`ed. A hostile / MITM'd provider response can embed `[link=…]` OSC-8 hyperlinks or other Rich markup that the terminal renders as clickable. `bristlenose/llm/billing_hints.py` uses `rich.markup.escape(raw_message)` at the interpolation site — preserves intentional locale-template markup while neutralising provider-controlled text. Same class as the `[name]`-style `console.print` gotcha above; provider exception strings are simply another untrusted-input channel.
- **gpt-4o / gpt-4o-mini cap output at 16384 — the 64000 default is Claude-tuned.** `llm_max_tokens` defaults to 64000 (Claude Sonnet 4's hard cap). gpt-4o/gpt-4o-mini reject `max_tokens > 16384` with a 400 (`max_tokens is too large`). `client.py` clamps per-model via `_MODEL_MAX_OUTPUT_TOKENS` / `_clamp_max_tokens` (logs `llm_max_tokens_clamped`); models absent from the dict aren't clamped. **Raising the clamp doesn't help gpt-4o** — 16384 is its ceiling. Consequence still open: quote extraction (the output-heaviest stage) can legitimately need >16384 output on a *dense* transcript, which then **truncates** (RuntimeError "response was truncated") and fails the run ~1/3 of the time on gpt-4o. The truncation message suggesting `BRISTLENOSE_LLM_MAX_TOKENS=65536` is misleading for gpt-4o (clamp caps it back). Real fix = chunked/smart-split quote extraction — see `100days.md:674` "smart-split-on-truncation fallback". When adding a model whose output ceiling is below 64000, add it to `_MODEL_MAX_OUTPUT_TOKENS`.
- **Python 3.14 + pydantic v1 crash** — `import presidio_analyzer` → spacy → pydantic v1 → `ConfigError` on Python 3.14. `check_pii` in `doctor.py` catches `Exception` (not just `ImportError`) and returns `SKIP` when `pii_enabled=False` (the default). If adding new import-guarded checks, use `except Exception` for robustness
