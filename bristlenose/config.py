"""Application settings loaded from environment variables, .env, or bristlenose.toml."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Set by the macOS desktop host (BristlenoseShared.childEnvironment) on every
# spawned sidecar. Its presence means "the GUI + Keychain are the single source
# of truth for this process" — see _find_env_files for why that disables disk
# `.env` discovery.
_HOSTED_BY_DESKTOP_ENV = "_BRISTLENOSE_HOSTED_BY_DESKTOP"

# Set by the macOS desktop host (BristlenoseShared.childEnvironment) on every
# spawned sidecar: a newline-joined block of `llm_resolve | step=host-defaults …`
# ledger lines describing the Swift-side decision that produced the provider/model
# env vars this process inherits (which provider is active, whether a model
# override and an API key are present). Unlike _PENDING_RESOLUTION_NOTES (an
# in-process queue drained once per invocation), this is a stable PROPERTY of the
# spawn — re-read on every load_settings() call and NEVER cleared, so every
# resolution in a long-lived serve process (run pipeline, autocode, analysis)
# carries the same cross-seam origin. Human-read-only (nothing parses it), so
# format drift degrades gracefully. Swift emits key=present/absent ONLY — these
# lines ride into bristlenose.log and are `ps -E`-visible, never the key value.
_HOST_RESOLUTION_TRACE_ENV = "_BRISTLENOSE_HOST_RESOLUTION_TRACE"


def hosted_by_desktop() -> bool:
    """True when this process was spawned by the macOS desktop app."""
    return bool(os.environ.get(_HOSTED_BY_DESKTOP_ENV))


def _drain_host_resolution_trace() -> list[str]:
    """Read the host-emitted resolution ledger lines (cross-seam, Swift origin).

    Returns the desktop host's `step=host-defaults` lines, or [] when not hosted
    (CLI/dev). Idempotent: reading an env var has no side effect, so unlike the
    CLI-note queue this is NOT cleared — every load_settings() in a long-lived
    serve process re-reads it and prepends the same origin to its ledger.
    """
    raw = os.environ.get(_HOST_RESOLUTION_TRACE_ENV)
    if not raw:
        return []
    return [line for line in raw.split("\n") if line.strip()]


def _find_env_files() -> list[Path]:
    """Find .env files to load, searching upward from CWD and in the package dir.

    Checks (in priority order, last wins in pydantic-settings):
    1. The bristlenose package directory (next to this file)
    2. The current working directory
    3. Parent directories up to the filesystem root

    This means ``bristlenose`` finds its .env whether you run it from the
    project root, a trial-runs subfolder, or anywhere on your system.

    **Desktop deployment carve-out:** when the process is spawned by the macOS
    app (``_BRISTLENOSE_HOSTED_BY_DESKTOP=1``), disk ``.env`` files are ignored
    entirely. A desktop user configures provider/model in GUI Settings and keys
    in Keychain; a stray ``.env`` on disk (e.g. the repo root during dev, or a
    file inside a dropped project folder) must never silently override those
    choices — that's a consent-integrity violation, not a convenience. Real env
    vars the host injects (Swift's transport for the GUI/Keychain values) are
    unaffected; only file discovery is disabled.
    """
    if hosted_by_desktop():
        return []

    candidates: list[Path] = []

    # Package directory (where bristlenose is installed / editable-linked)
    pkg_env = Path(__file__).resolve().parent.parent / ".env"
    if pkg_env.is_file():
        candidates.append(pkg_env)

    # Walk up from CWD to find .env files
    cwd = Path.cwd().resolve()
    for parent in [cwd, *cwd.parents]:
        env_path = parent / ".env"
        if env_path.is_file() and env_path not in candidates:
            candidates.append(env_path)
            break  # stop at first match going upward

    return candidates


class BristlenoseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BRISTLENOSE_",
        env_file=_find_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Project
    project_name: str = "User Research"

    # LLM
    llm_provider: str = "anthropic"  # "anthropic", "openai", "azure", "google", or "local"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_model: str = "claude-sonnet-4-6"
    llm_max_tokens: int = 64000
    llm_temperature: float = 0.1

    # Azure OpenAI
    azure_api_key: str = ""
    azure_endpoint: str = ""  # e.g. https://my-resource.openai.azure.com/
    azure_deployment: str = ""  # Deployment name from Azure portal
    azure_api_version: str = "2024-10-21"

    # Google (Gemini)
    google_api_key: str = ""

    # Local LLM (Ollama)
    local_url: str = "http://localhost:11434/v1"
    local_model: str = "llama3.2:3b"

    # Whisper
    whisper_backend: str = "auto"  # "auto", "mlx", "faster-whisper"
    whisper_model: str = "large-v3-turbo"
    whisper_language: str = "en"
    whisper_device: str = "auto"  # "cpu", "cuda", "auto" (faster-whisper only)
    whisper_compute_type: str = "int8"  # faster-whisper only

    # PII
    pii_enabled: bool = False
    pii_llm_pass: bool = False  # Not yet implemented — see runtime warning below
    pii_custom_names: list[str] = Field(default_factory=list)  # Not yet implemented
    # Confidence threshold for Presidio PII detection (0.0–1.0).
    # Lower = catch more PII but more false positives (over-redaction).
    # 0.5 = aggressive (sensitive data, accept over-redaction)
    # 0.7 = balanced (default)
    # 0.9 = conservative (minimise false positives, risk missing some PII)
    # See: https://microsoft.github.io/presidio/analyzer/
    pii_score_threshold: float = Field(default=0.7, ge=0.0, le=1.0)

    # Codebook (AutoCode framework). Slug matches a YAML file under
    # bristlenose/server/codebook/ (e.g. "garrett", "norman", "uxr").
    # None = no preference; user picks in the report UI.
    codebook: str | None = None

    # Codebook lab — the dynamic-codebook-builder experiment surface. On by
    # default so it ships in the desktop sidecar + plain `serve` for cohort
    # testing; set BRISTLENOSE_EXPERIMENTAL_CODEBOOK_LAB=0 to disable (escape
    # hatch to turn off post-TestFlight if it causes trouble). Stays an
    # "experiment" until validated with real data by real researchers.
    experimental_codebook_lab: bool = True

    # Miro
    miro_access_token: str = ""

    # Theme
    color_scheme: str = "auto"  # "auto", "light", or "dark"

    # Pipeline
    skip_transcription: bool = False
    write_intermediate: bool = True

    # Preflight model-fetch policy. When True, missing runtime-fetched models
    # (Whisper, spaCy, etc.) abort the pipeline with an instructive message
    # instead of fetching them. Escape hatch for offline / air-gapped runs.
    no_fetch: bool = False

    output_dir: Path = Path("output")
    input_dir: Path = Path("input")

    # Quote extraction
    min_quote_words: int = 5
    merge_speaker_gap_seconds: float = 2.0

    # Concurrency
    llm_concurrency: int = 3


# Provider/model resolution ledger. Each load_settings() call rebuilds this as
# an ordered list of human-readable steps: the value of provider+model at every
# moment it is set or changed, what event caused the change, and the source of
# the new value. Stored module-global (the sidecar runs one resolution per
# process) so it can be REPLAYED into the log file after the per-run log handler
# attaches — load_settings runs before pipeline._configure_logging, so a live
# emit at resolution time is lost from the run log. See log_resolution_trace.
_LAST_RESOLUTION_TRACE: list[str] = []


def get_resolution_trace() -> list[str]:
    """Return a copy of the last provider/model resolution ledger."""
    return list(_LAST_RESOLUTION_TRACE)


# CLI-layer notes queued for the NEXT load_settings() trace. load_settings builds
# the ledger from step-0-inputs onward, but the value of provider/model is decided
# one layer up — in the `run`/`analyze` command, which chooses whether to forward
# `--llm` as a cli-override at all. That decision (the actor that spoke uninvited
# in the 8 Jun 404) is invisible to load_settings, which only sees the *result*
# (`llm_provider` present in overrides or not). The CLI records its own decision
# here; load_settings drains it to the FRONT of the trace so the ledger reads
# top-down: who spoke → what they said → how pydantic resolved it. Pure-Python and
# pytest-testable (the only CI-running suite), unlike the Swift spawn path.
_PENDING_RESOLUTION_NOTES: list[str] = []


def note_resolution_input(line: str) -> None:
    """Queue a CLI-layer ledger line for the next load_settings() trace.

    Drained (and cleared) at the top of load_settings — one resolution per
    process for the sidecar, so stale notes can't leak across runs.
    """
    _PENDING_RESOLUTION_NOTES.append(line)


def describe_cli_provider_decision(
    llm_provider: str | None, *, hosted: bool, command: str = "run"
) -> str:
    """Render the `<command> --llm` forwarding decision as a ledger line.

    Pure — no I/O, no globals. The 404 root cause was the CLI forwarding a
    non-None `--llm` default as a cli-override that silently beat the
    desktop-injected ``BRISTLENOSE_LLM_PROVIDER`` env var. This line makes the
    forward-or-not decision legible in the run log, attributed to the layer that
    actually made it (cli.py), above load_settings' own step-0-inputs.
    """
    if llm_provider is not None:
        decision = (
            f"--llm={llm_provider!r} provided -> forwarding as cli-override "
            "(beats env var)"
        )
    else:
        decision = "--llm absent -> not forwarding (env/config decides)"
    return (
        f"llm_resolve | step=cli-args | event={command} --llm [cli.py] | "
        f"{decision} | hosted_by_desktop={hosted}"
    )


def log_resolution_trace(target: logging.Logger | None = None) -> None:
    """Replay the provider/model resolution ledger into the (now-attached) log.

    Called from points that run AFTER logging is configured — LLMClient init
    (analysis stage) and the early-logging hook in the ``run`` command — so the
    full ledger lands in ``<output>/.bristlenose/bristlenose.log`` next to the
    LLM call. Cheap and short (a handful of lines); duplication across call
    sites is acceptable and even useful (confirms the value didn't drift).
    """
    lg = target or logger
    for line in _LAST_RESOLUTION_TRACE:
        lg.info(line)


def load_settings(**overrides: object) -> BristlenoseSettings:
    """Load settings with optional CLI overrides.

    Normalises LLM provider aliases (claude → anthropic, chatgpt/gpt → openai,
    ollama → local).

    Also populates API keys from the system keychain if not already set
    from environment variables or .env file.

    Builds the provider/model resolution ledger (``_LAST_RESOLUTION_TRACE``) as
    a side effect — every mutation of provider/model is recorded with its cause
    and source for later replay into the run log.
    """
    # Import here to avoid circular import at module load time
    from bristlenose.providers import get_provider_aliases

    trace: list[str] = []
    # Prepend the host-defaults block (Swift origin) to the very front — it
    # describes the cross-seam decision (which provider/model/key the desktop app
    # injected) that precedes everything Python sees. Re-read every call, never
    # cleared, so autocode/analysis resolutions in a long-lived serve process all
    # carry the same origin. Empty on CLI/dev.
    trace.extend(_drain_host_resolution_trace())
    # Drain any CLI-layer notes next — they describe the decision (forward
    # --llm or not) that produced the `overrides` this function is about to resolve.
    if _PENDING_RESOLUTION_NOTES:
        trace.extend(_PENDING_RESOLUTION_NOTES)
        _PENDING_RESOLUTION_NOTES.clear()
    raw_env_provider = os.environ.get("BRISTLENOSE_LLM_PROVIDER")
    raw_env_model = os.environ.get("BRISTLENOSE_LLM_MODEL")
    dotenv = [str(p) for p in _find_env_files()]
    trace.append(
        "llm_resolve | step=0-inputs | event=load_settings() [config.py] | "
        f"env.BRISTLENOSE_LLM_PROVIDER={raw_env_provider!r} | "
        f"env.BRISTLENOSE_LLM_MODEL={raw_env_model!r} | "
        f"dotenv_files={dotenv} | hosted_by_desktop={hosted_by_desktop()} | "
        f"overrides={sorted(overrides)}"
    )

    # Normalise LLM provider aliases (claude→anthropic, etc.)
    if "llm_provider" in overrides and isinstance(overrides["llm_provider"], str):
        before = overrides["llm_provider"]
        provider = before.lower()
        aliases = get_provider_aliases()
        overrides["llm_provider"] = aliases.get(provider, provider)
        if overrides["llm_provider"] != before:
            trace.append(
                "llm_resolve | step=1-alias | "
                "event=alias-normalise [config.py:load_settings] | "
                f"provider {before!r} -> {overrides['llm_provider']!r} | "
                "source=cli-override (get_provider_aliases)"
            )

    settings = BristlenoseSettings(**overrides)  # type: ignore[arg-type]

    def _src(field: str, raw_env: str | None) -> str:
        if field in overrides:
            return "cli-override"
        if raw_env is not None:
            return "env-var"
        if dotenv and not hosted_by_desktop():
            return "dotenv-file"
        return "code-default"

    trace.append(
        "llm_resolve | step=2-pydantic | "
        "event=BristlenoseSettings(**overrides) [config.py] | "
        f"provider={settings.llm_provider} (source={_src('llm_provider', raw_env_provider)}) | "
        f"model={settings.llm_model} (source={_src('llm_model', raw_env_model)})"
    )

    before_model = settings.llm_model
    settings = _fill_provider_default_model(settings, overrides, raw_env_model)
    if settings.llm_model != before_model:
        trace.append(
            "llm_resolve | step=3-provider-default | "
            "event=_fill_provider_default_model [config.py] | "
            f"model {before_model!r} -> {settings.llm_model!r} | "
            "cause=provider-selected-no-explicit-model | "
            f"source={settings.llm_provider}-provider-default"
        )

    before_model = settings.llm_model
    settings = _guard_orphan_desktop_model(settings, overrides)
    if settings.llm_model != before_model:
        trace.append(
            "llm_resolve | step=3-orphan-guard | "
            "event=_guard_orphan_desktop_model [config.py] | "
            f"model {before_model!r} -> {settings.llm_model!r} | "
            "cause=model-injected-without-provider-under-desktop | "
            f"source={settings.llm_provider}-provider-default"
        )

    # Populate API keys from keychain if not set from env/.env
    settings = _populate_keys_from_keychain(settings)

    key_value = {
        "anthropic": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
        "azure": settings.azure_api_key,
        "google": settings.google_api_key,
        "local": "",
    }.get(settings.llm_provider, "")
    trace.append(
        "llm_resolve | step=4-final | event=load_settings() return [config.py] | "
        f"provider={settings.llm_provider} | model={settings.llm_model} | "
        f"key={_key_fingerprint(key_value)}"
    )

    _LAST_RESOLUTION_TRACE[:] = trace
    # Live emit too — lands when logging is already configured (e.g. the run
    # command's early-logging hook); otherwise replayed later via
    # log_resolution_trace from LLMClient.
    for line in trace:
        logger.info(line)

    return settings


def _fill_provider_default_model(
    settings: BristlenoseSettings,
    overrides: dict[str, object],
    raw_env_model: str | None,
) -> BristlenoseSettings:
    """Snap a never-chosen model to the resolved provider's default model (CLI only).

    On the CLI, selecting a provider (``--llm chatgpt`` / ``BRISTLENOSE_LLM_PROVIDER``)
    without a model left ``llm_model`` at its Anthropic code-default
    (``config.py`` ``llm_model`` field). Sending that name to a non-Anthropic
    provider 404s (cross-provider ``model_not_found``), surfacing as
    ``PipelineAbandonedError`` at topic segmentation. When the user expressed no
    model preference, adopt the resolved provider's ``default_model`` so provider
    and model stay coherent.

    Gating, in order:

    - **Desktop is a no-op** — desktop model coherence is owned wholly by
      ``_guard_orphan_desktop_model``; this fix stays on the CLI.
    - **Rule 1: an explicit model always wins** — a ``--model`` override (none
      today) or ``BRISTLENOSE_LLM_MODEL`` env var is never overridden.
    - **Value gate** — fire only when ``llm_model`` is *still the field's
      code-default value*. This is deliberately a value comparison, not the
      ``_src`` ``"dotenv-file"`` source label: ``_src`` reports ``"dotenv-file"``
      whenever a ``.env`` merely exists (file presence, not field presence), so a
      user who sets provider+key in ``.env`` but omits the model would otherwise be
      mislabelled and 404. A ``.env`` that sets a *real* model leaves a non-default
      value and is honoured (rule 1); a ``.env`` that omits it leaves the
      code-default and is filled.

    Azure (``default_model == ""``) is skipped by the final ``if default`` guard.

    For ``local`` (Ollama) the snap is cosmetic: execution reads ``local_model`` /
    ``BRISTLENOSE_LOCAL_MODEL`` (a separate axis), not ``llm_model`` — so the
    ``step=3-provider-default`` line on a local run records a config decision that
    never reaches a request. Harmless, and not worth a fourth gate to suppress.
    """
    if hosted_by_desktop():
        return settings
    if "llm_model" in overrides or raw_env_model is not None:
        return settings
    if settings.llm_model != BristlenoseSettings.model_fields["llm_model"].default:
        return settings

    from bristlenose.providers import PROVIDERS

    spec = PROVIDERS.get(settings.llm_provider)
    default = spec.default_model if spec else ""
    if default and default != settings.llm_model:
        settings = settings.model_copy(update={"llm_model": default})
    return settings


def _guard_orphan_desktop_model(
    settings: BristlenoseSettings, overrides: dict[str, object]
) -> BristlenoseSettings:
    """Under desktop hosting, drop a model env var that has no matching provider.

    The desktop injects provider+model together or neither. A
    ``BRISTLENOSE_LLM_MODEL`` with no ``BRISTLENOSE_LLM_PROVIDER`` is therefore
    a malformed injection (the historical Swift ``else if`` bug: a stale global
    ``llmModel`` like ``gpt-4o`` rode in while the provider defaulted to
    anthropic → cross-provider 404). Rather than let that orphan model 404, snap
    the model back to the resolved provider's coherent default. Defense-in-depth
    so a buggy or stale host binary can't produce an impossible provider/model
    pair. CLI runs (not desktop-hosted) keep ``BRISTLENOSE_LLM_MODEL`` as a
    valid standalone override.
    """
    if not hosted_by_desktop():
        return settings
    if "llm_model" in overrides or "llm_provider" in overrides:
        return settings  # explicit CLI override wins
    model_set = os.environ.get("BRISTLENOSE_LLM_MODEL") is not None
    provider_set = os.environ.get("BRISTLENOSE_LLM_PROVIDER") is not None
    if not (model_set and not provider_set):
        return settings

    from bristlenose.providers import PROVIDERS

    spec = PROVIDERS.get(settings.llm_provider)
    coherent = spec.default_model if spec else settings.llm_model
    if coherent and coherent != settings.llm_model:
        logger.warning(
            "orphan_model_dropped | desktop injected model=%r with no provider; "
            "snapping to %s default %r to avoid a cross-provider mismatch",
            settings.llm_model,
            settings.llm_provider,
            coherent,
        )
        settings = settings.model_copy(update={"llm_model": coherent})
    return settings


def _key_fingerprint(value: str) -> str:
    """Non-reversible fingerprint for a secret: length + last 4 chars only.

    Mirrors what the preflight UI already shows ("sk-ant-...wAA"). Safe to log;
    never emit the full key.
    """
    if not value:
        return "absent"
    tail = value[-4:] if len(value) >= 4 else "?"
    return f"present(len={len(value)}, …{tail})"


def _populate_keys_from_keychain(settings: BristlenoseSettings) -> BristlenoseSettings:
    """Check keychain for API keys not already set from env vars.

    Returns a new settings object with keys populated from keychain.
    """
    from bristlenose.credentials import get_credential_store

    store = get_credential_store()
    updates: dict[str, str] = {}

    # Only check keychain if the key isn't already set
    if not settings.anthropic_api_key:
        key = store.get("anthropic")
        if key:
            updates["anthropic_api_key"] = key

    if not settings.openai_api_key:
        key = store.get("openai")
        if key:
            updates["openai_api_key"] = key

    if not settings.azure_api_key:
        key = store.get("azure")
        if key:
            updates["azure_api_key"] = key

    if not settings.google_api_key:
        key = store.get("google")
        if key:
            updates["google_api_key"] = key

    if not settings.miro_access_token:
        key = store.get("miro")
        if key:
            updates["miro_access_token"] = key

    if not updates:
        return settings

    # Create new settings with keychain values
    # We need to merge the original values with keychain values
    return settings.model_copy(update=updates)
