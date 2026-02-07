# LLM / Provider Context

## Credential storage (Keychain)

API keys are stored securely in the system keychain. Uses native CLI tools — no Python keyring shim.

- **CLI command**: `bristlenose configure <provider>` — prompts for key, validates with API, stores in keychain. Accepts `--key` option to bypass interactive prompt (useful in scripts or when TTY has issues)
- **Provider aliases**: `claude` → `anthropic`, `chatgpt`/`gpt` → `openai`
- **Priority order**: keychain → env var (`ANTHROPIC_API_KEY`) → .env file
- **macOS**: `bristlenose/credentials_macos.py` — uses `security` CLI (add-generic-password, find-generic-password, delete-generic-password). Service names: "Bristlenose Anthropic API Key", "Bristlenose OpenAI API Key"
- **Linux**: `bristlenose/credentials_linux.py` — uses `secret-tool` (Secret Service API). Falls back to `EnvCredentialStore` if secret-tool unavailable
- **Fallback**: `bristlenose/credentials.py` — `EnvCredentialStore` reads from env vars (cannot write)
- **Integration**: `_populate_keys_from_keychain()` in `config.py` loads from keychain when settings don't have keys from env/.env
- **Doctor display**: shows "(Keychain)" suffix when key source is keychain
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

## Gotchas

- **Provider registry** — `bristlenose/providers.py` is the single source of truth for provider metadata (names, aliases, default models, SDK modules). `resolve_provider()` handles alias normalisation (claude→anthropic, azure-openai→azure, ollama→local). `load_settings()` in `config.py` calls the registry to normalise aliases
- **Azure OpenAI uses `AsyncAzureOpenAI`** — same OpenAI SDK, different client class. Key differences from regular OpenAI: needs `azure_endpoint` and `api_version` on client init, uses deployment name (not model name) as the `model` parameter. `configure azure` stores only the API key in keychain — endpoint and deployment are non-secret, go in env vars or `.env`
- **Azure cost estimation returns None** — deployment names are user-defined strings, not model names, so `estimate_cost()` can't look up pricing. The pricing URL is still shown
- **Local LLM uses OpenAI SDK** — Ollama is OpenAI-compatible, so `_analyze_local()` in `llm/client.py` uses the same `openai.AsyncOpenAI` client with `base_url=settings.local_url` and `api_key="ollama"` (required by SDK but ignored by Ollama)
- **Local model retry logic** — `_analyze_local()` retries JSON parsing failures up to 3 times with exponential backoff; local models are ~85% reliable vs ~99% for cloud
- **`_needs_provider_prompt()` checks Ollama status** — for local provider, it calls `validate_local_endpoint()` to check if Ollama is running and has the model; for cloud providers, it just checks if the API key is set
