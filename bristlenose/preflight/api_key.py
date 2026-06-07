"""API-key preflight — validates the active provider's key against billing before stage 1.

The friendly-CTO call on 9 May 2026 found three different failure modes for
"unconfigured Claude account" that all looked identical to a researcher: key
missing, key invalid, and key valid but no billing balance. The first two
were caught by existing checks; the third surfaced only when the first LLM
stage actually ran, several minutes into the pipeline.

This preflight runs a paid ``/messages`` call up-front. Per finding 15:

- Single token: ``max_tokens=1``
- Locked inert prompt: ``"."`` (constant; never user-derived — so the call
  is greppable and cannot leak transcript content)
- ``User-Agent: bristlenose/<version>`` so server-side logs identify us
- Cost: ~$0.0001 per call

The point is to *exercise billing*. A free probe (e.g. ``/models``) can't
distinguish "key valid + paid" from "key valid + no balance" — both return
200. A paid call does.

State (finding 8): :func:`state_path` returns ``~/Library/Application
Support/Bristlenose/state.json`` on macOS and ``$XDG_DATA_HOME/Bristlenose/
state.json`` on Linux. The 24-hour TTL means a successful validation skips
the network on subsequent runs within the window.

Whitelist (finding 4): the preflight is only called from LLM-touching
commands (``run``, ``analyze``, ``transcribe-only``). Read-only commands
(``status``, ``render``, ``doctor``, ``--help``, ``--version``) never
trigger it.

Scope: this preflight covers the **has-a-key, validate-it-now** path. The
**no-account-yet** branch (numbered URL flow per the handoff) and the
Keychain-storage integration both live on the existing
``_maybe_prompt_for_provider`` path in ``cli.py`` and are not duplicated
here — this module assumes a key is already in settings (env var,
Keychain, or fresh paste).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

    from bristlenose.config import BristlenoseSettings

from bristlenose import __version__
from bristlenose.i18n import t
from bristlenose.llm.billing_hints import billing_for, recovery_message
from bristlenose.preflight import PreflightAbortedError

# Back-compat alias — see preflight/whisper.py for the unification rationale.
ApiKeyPreflightAbortedError = PreflightAbortedError

logger = logging.getLogger(__name__)

_VALIDATION_PROMPT = "."
_TTL_SECONDS = 24 * 3600  # 24 h per finding 7
_STATE_VERSION = 1


# ---------------------------------------------------------------------------
# State file
# ---------------------------------------------------------------------------


def state_path() -> Path:
    """Return the per-user state file path. macOS uses Application Support;
    Linux uses ``$XDG_DATA_HOME`` (default ``~/.local/share``).

    Note on the sandboxed desktop sidecar: macOS App Sandbox redirects
    ``~/Library/Application Support/Bristlenose/`` to
    ``~/Library/Containers/<bundle-id>/Data/Library/Application Support/Bristlenose/``,
    so the CLI and the desktop sidecar each keep their own 24h-TTL state.
    That separation is intentional — each surface validates independently.
    Unifying would require a group-container entitlement; don't.
    """
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "Bristlenose"
    else:
        base = (
            Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
            / "Bristlenose"
        )
    return base / "state.json"


def read_state() -> dict:
    """Read the state JSON; return an empty schema on first run / parse error."""
    path = state_path()
    if not path.exists():
        return {"version": _STATE_VERSION, "first_run": True, "providers": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": _STATE_VERSION, "first_run": True, "providers": {}}
    data.setdefault("version", _STATE_VERSION)
    data.setdefault("first_run", True)
    data.setdefault("providers", {})
    return data


def write_state(state: dict) -> None:
    """Write the state JSON atomically with mode 0o600.

    Mode is enforced explicitly because the umask-inherited 0o644 default
    on Linux would expose the file (validation timestamps + provider list
    = a low-grade activity fingerprint) to other local users on shared
    hosts. macOS Application Support is per-user-protected but we apply
    the same mode for consistency. Matches the pattern used by
    ``bristlenose/llm/telemetry.py`` for ``llm-calls.jsonl``.
    """
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, indent=2)
    # os.open + 0o600 avoids the race between create-default-mode and chmod.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(payload)


def _is_recently_validated(state: dict, provider: str) -> bool:
    info = state.get("providers", {}).get(provider, {})
    last = info.get("last_validated_epoch")
    if not isinstance(last, (int, float)):
        return False
    return (time.time() - last) < _TTL_SECONDS


def _mark_validated(state: dict, provider: str, *, source: str) -> None:
    state.setdefault("providers", {})[provider] = {
        "last_validated_epoch": int(time.time()),
        "source": source,
    }
    state["first_run"] = False


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of a paid validation call."""

    ok: bool
    error_class: str | None = None  # one of billing_hints' four buckets or None
    raw_message: str = ""


def _classify_network_error(exc: BaseException) -> ValidationResult | None:
    """Return a ValidationResult for transport-layer errors, or None.

    Surface network / TLS / corporate-proxy interception distinctly from
    provider errors so a researcher behind a TLS-terminating proxy gets an
    actionable IT message rather than ``"Provider says: ..."``.
    """
    # Imported lazily — these are stdlib + a Bristlenose dep, but doing it
    # here keeps the validator helpers self-contained.
    import ssl

    try:
        import httpx
    except ImportError:
        httpx = None  # type: ignore[assignment]

    if isinstance(exc, ssl.SSLError):
        return ValidationResult(
            ok=False,
            error_class="network",
            raw_message=(
                "TLS handshake failed — if a corporate proxy intercepts HTTPS, "
                "contact IT. Underlying: " + str(exc)
            ),
        )
    if httpx is not None and isinstance(exc, httpx.ProxyError):
        return ValidationResult(
            ok=False,
            error_class="network",
            raw_message="HTTPS proxy refused the connection: " + str(exc),
        )
    if httpx is not None and isinstance(exc, httpx.ConnectError):
        return ValidationResult(
            ok=False,
            error_class="network",
            raw_message=(
                "Network connect failed — check DNS / VPN / offline status. "
                "Underlying: " + str(exc)
            ),
        )
    return None


def _validate_anthropic(api_key: str, model: str) -> ValidationResult:
    """Exercise billing via a 1-token ``/messages`` call to the Anthropic API."""
    import anthropic

    client = anthropic.Anthropic(
        api_key=api_key,
        default_headers={"User-Agent": f"bristlenose/{__version__}"},
    )
    try:
        client.messages.create(
            model=model,
            max_tokens=1,
            messages=[{"role": "user", "content": _VALIDATION_PROMPT}],
        )
    except anthropic.AuthenticationError as exc:
        return ValidationResult(ok=False, error_class="invalid_key", raw_message=str(exc))
    except anthropic.BadRequestError as exc:
        # Live SDK message is "Your credit balance is too low to access the
        # Claude API. ..." — match the spaced phrase, not the underscored
        # error.type token (which doesn't appear in str(exc)).
        if "credit balance" in str(exc).lower():
            return ValidationResult(
                ok=False, error_class="billing_empty", raw_message=str(exc)
            )
        return ValidationResult(
            ok=False, error_class="model_unavailable", raw_message=str(exc)
        )
    except anthropic.RateLimitError as exc:
        return ValidationResult(
            ok=False, error_class="rate_limit", raw_message=str(exc)
        )
    except anthropic.APIStatusError as exc:
        return ValidationResult(ok=False, error_class=None, raw_message=str(exc))
    except Exception as exc:
        # Surface network / TLS / proxy faults with their own message before
        # falling through to the generic "Provider says: ..." copy.
        network = _classify_network_error(exc)
        if network is not None:
            return network
        logger.warning(
            "anthropic validation unknown error: %s: %s",
            type(exc).__name__, exc,
        )
        return ValidationResult(ok=False, error_class=None, raw_message=str(exc))
    return ValidationResult(ok=True)


def _openai_error_code(exc: BaseException) -> str | None:
    """Safely read ``exc.body["error"]["code"]`` from an openai SDK exception.

    Recent SDK versions sometimes wrap the body; guard against non-dict shapes.
    Same body schema is used by Azure (shares the openai SDK), so this helper
    is reused there.
    """
    body = getattr(exc, "body", None)
    if not isinstance(body, dict):
        return None
    error = body.get("error")
    if not isinstance(error, dict):
        return None
    code = error.get("code")
    return code if isinstance(code, str) else None


def _validate_openai(api_key: str, model: str) -> ValidationResult:
    """Exercise billing via a 1-token chat-completion to the OpenAI API."""
    import openai

    client = openai.OpenAI(
        api_key=api_key,
        default_headers={"User-Agent": f"bristlenose/{__version__}"},
    )
    try:
        client.chat.completions.create(
            model=model,
            max_tokens=1,
            messages=[{"role": "user", "content": _VALIDATION_PROMPT}],
        )
    except openai.AuthenticationError as exc:
        return ValidationResult(ok=False, error_class="invalid_key", raw_message=str(exc))
    except openai.RateLimitError as exc:
        # OpenAI overloads 429 — billing-empty is signalled by the
        # ``insufficient_quota`` code in the response body. Read the
        # structured field; the substring fallback covers SDK versions
        # that don't surface ``exc.body`` as a dict.
        code = _openai_error_code(exc)
        if code == "insufficient_quota" or "insufficient_quota" in str(exc):
            return ValidationResult(
                ok=False, error_class="billing_empty", raw_message=str(exc)
            )
        return ValidationResult(
            ok=False, error_class="rate_limit", raw_message=str(exc)
        )
    except openai.NotFoundError as exc:
        return ValidationResult(
            ok=False, error_class="model_unavailable", raw_message=str(exc)
        )
    except openai.APIStatusError as exc:
        return ValidationResult(ok=False, error_class=None, raw_message=str(exc))
    except Exception as exc:
        network = _classify_network_error(exc)
        if network is not None:
            return network
        logger.warning(
            "openai validation unknown error: %s: %s",
            type(exc).__name__, exc,
        )
        return ValidationResult(ok=False, error_class=None, raw_message=str(exc))
    return ValidationResult(ok=True)


def _validate_azure(
    api_key: str, endpoint: str, deployment: str, api_version: str
) -> ValidationResult:
    """Exercise the Azure OpenAI deployment via a 1-token chat-completion.

    Shares the openai SDK; differs from OpenAI in needing endpoint URL,
    deployment name (distinct from model id), and api version. The
    ``DeploymentNotFound`` 404 is the most common Azure foot-gun — recovery
    copy must call out that this is the **portal deployment name**, not
    a model id.
    """
    import openai

    client = openai.AzureOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=api_version,
        default_headers={"User-Agent": f"bristlenose/{__version__}"},
    )
    try:
        client.chat.completions.create(
            model=deployment,
            max_tokens=1,
            messages=[{"role": "user", "content": _VALIDATION_PROMPT}],
        )
    except openai.AuthenticationError as exc:
        return ValidationResult(ok=False, error_class="invalid_key", raw_message=str(exc))
    except openai.NotFoundError as exc:
        # DeploymentNotFound is the headline Azure error; the recovery
        # copy distinguishes it from generic model_unavailable.
        code = _openai_error_code(exc)
        raw = str(exc)
        if code == "DeploymentNotFound":
            return ValidationResult(
                ok=False,
                error_class="model_unavailable",
                raw_message=f"DeploymentNotFound: {raw}",
            )
        return ValidationResult(
            ok=False, error_class="model_unavailable", raw_message=raw
        )
    except openai.RateLimitError as exc:
        # Azure has no insufficient_quota concept — subscription billing
        # is separate, not credit-pool based.
        return ValidationResult(
            ok=False, error_class="rate_limit", raw_message=str(exc)
        )
    except openai.BadRequestError as exc:
        # Content filter and invalid_api_version fall through with no
        # recovery bucket — surface raw message.
        return ValidationResult(ok=False, error_class=None, raw_message=str(exc))
    except openai.APIStatusError as exc:
        return ValidationResult(ok=False, error_class=None, raw_message=str(exc))
    except Exception as exc:
        network = _classify_network_error(exc)
        if network is not None:
            return network
        logger.warning(
            "azure validation unknown error: %s: %s",
            type(exc).__name__, exc,
        )
        return ValidationResult(ok=False, error_class=None, raw_message=str(exc))
    return ValidationResult(ok=True)


def _validate_google(api_key: str, model: str) -> ValidationResult:
    """Exercise the Gemini API via a minimal ``generate_content`` call.

    Reads structured ``.code`` / ``.status`` fields on ``APIError`` instead
    of substring-matching the message. Gemini has no billing-empty concept
    (post-paid via GCP billing) — those errors route to model_unavailable.
    """
    from google import genai
    from google.genai import errors as genai_errors
    from google.genai import types

    client = genai.Client(api_key=api_key)
    try:
        client.models.generate_content(
            model=model,
            contents=_VALIDATION_PROMPT,
            config=types.GenerateContentConfig(max_output_tokens=1),
        )
    except genai_errors.APIError as exc:
        status = (getattr(exc, "status", "") or "").upper()
        code = getattr(exc, "code", None)
        raw = str(exc)
        # Some details flag bad API keys even when the top-level status is
        # INVALID_ARGUMENT — surface as invalid_key. ``.details`` on the
        # SDK exception holds the full response JSON dict; the actual
        # details array lives at ``details["error"]["details"]``.
        details_blob = getattr(exc, "details", None)
        details_list: list = []
        if isinstance(details_blob, dict):
            err = details_blob.get("error")
            if isinstance(err, dict):
                inner = err.get("details")
                if isinstance(inner, list):
                    details_list = inner
        api_key_flagged = any(
            isinstance(d, dict) and d.get("reason") == "API_KEY_INVALID"
            for d in details_list
        )

        if status == "UNAUTHENTICATED" or code == 401 or api_key_flagged:
            return ValidationResult(
                ok=False, error_class="invalid_key", raw_message=raw
            )
        if status == "PERMISSION_DENIED" or code == 403:
            return ValidationResult(
                ok=False, error_class="model_unavailable", raw_message=raw
            )
        if status == "RESOURCE_EXHAUSTED" or code == 429:
            return ValidationResult(
                ok=False, error_class="rate_limit", raw_message=raw
            )
        if status == "NOT_FOUND" or code == 404:
            return ValidationResult(
                ok=False, error_class="model_unavailable", raw_message=raw
            )
        return ValidationResult(ok=False, error_class=None, raw_message=raw)
    except Exception as exc:
        network = _classify_network_error(exc)
        if network is not None:
            return network
        logger.warning(
            "google validation unknown error: %s: %s",
            type(exc).__name__, exc,
        )
        return ValidationResult(ok=False, error_class=None, raw_message=str(exc))
    return ValidationResult(ok=True)


def _validate_local(local_url: str, model: str) -> ValidationResult:
    """Exercise a local Ollama-compatible endpoint via a 1-token call.

    Runtime path uses the openai SDK pointed at ``local_url`` (Ollama is
    OpenAI-compatible); the preflight does the same — keeps the dep
    surface narrow and the failure modes consistent. No api key, no
    billing — failures are server-down or model-not-pulled.
    """
    import openai

    client = openai.OpenAI(
        base_url=local_url,
        api_key="ollama",  # required by SDK, ignored by Ollama
        default_headers={"User-Agent": f"bristlenose/{__version__}"},
    )
    try:
        client.chat.completions.create(
            model=model,
            max_tokens=1,
            messages=[{"role": "user", "content": _VALIDATION_PROMPT}],
        )
    except openai.APIConnectionError as exc:
        # Server down is the dominant local failure — surface as a
        # network-class result. ``recovery_message`` switches on
        # provider=="local" to emit "Start Ollama with `ollama serve`"
        # instead of the generic network copy. Note: this catches
        # *before* ``_classify_network_error`` runs, so SSL / corporate
        # proxy errors don't get their specific recovery message —
        # acceptable narrowing since ``local_url`` defaults to plain
        # HTTP on loopback.
        return ValidationResult(
            ok=False, error_class="network", raw_message=str(exc)
        )
    except openai.NotFoundError as exc:
        # Ollama returns 404 with a "not found, try pulling" body when
        # the model isn't downloaded. Both 404 shapes map to
        # model_unavailable; recovery_message handles the per-provider
        # "ollama pull" wording.
        return ValidationResult(
            ok=False, error_class="model_unavailable", raw_message=str(exc)
        )
    except openai.APIStatusError as exc:
        return ValidationResult(ok=False, error_class=None, raw_message=str(exc))
    except Exception as exc:
        network = _classify_network_error(exc)
        if network is not None:
            return network
        logger.warning(
            "local validation unknown error: %s: %s",
            type(exc).__name__, exc,
        )
        return ValidationResult(ok=False, error_class=None, raw_message=str(exc))
    return ValidationResult(ok=True)


# Providers with rich validation. Local has no key; orchestrator handles that.
_SUPPORTED_PROVIDERS = frozenset({"anthropic", "openai", "azure", "google", "local"})


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _api_key_for(settings: BristlenoseSettings) -> tuple[str, str]:
    """Return ``(api_key, source_label)`` for the active provider, or ``("", "")``.

    ``source_label`` is one of ``"env"`` / ``"keychain"`` / ``"settings"`` —
    used for the first-run source attribution line.
    """
    provider = settings.llm_provider
    field = f"{provider}_api_key"
    key = str(getattr(settings, field, "") or "")
    if not key:
        return "", ""

    env_var = f"BRISTLENOSE_{provider.upper()}_API_KEY"
    if os.environ.get(env_var) == key:
        return key, "env"
    # We can't reliably distinguish keychain from .env / config-file here
    # without another probe; the safe label is "stored".
    return key, "stored"


def preflight_api_key(
    *,
    settings: BristlenoseSettings,
    console: Console,
) -> None:
    """Run the API-key preflight.

    Behaviour:
    - **``BRISTLENOSE_SKIP_PREFLIGHT=1``**: explicit escape hatch, skip silently.
      Defence-in-depth for spoofed-TTY CI runners (Buildkite, tmux-from-cron,
      `script(1)` wrappers) where the TTY heuristic isn't reliable.
    - **Provider == "local"** (Ollama): skip — no key, no billing.
    - **Provider with no rich support** (azure, google): skip rich validation;
      let downstream LLM calls surface failure naturally with the generic
      "Provider says: ..." copy on the call-site.
    - **Recently validated** (24h TTL): skip the network call.
    - **No key at all**: skip — the existing ``_maybe_prompt_for_provider``
      handles missing-key UX; the preflight only validates *present* keys.
    - **Non-TTY**: skip the first-run *banner* but still validate. A CI run
      with an expired key should abort here, not burn LLM cost at stage 8.
    - **Otherwise**: call the provider's paid validation endpoint with a
      1-token request. On failure raise :class:`PreflightAbortedError` with
      the recovery copy from :mod:`billing_hints`. On success, update the
      state file with the validation timestamp.
    """
    if os.environ.get("BRISTLENOSE_SKIP_PREFLIGHT") == "1":
        return
    provider = settings.llm_provider
    if provider not in _SUPPORTED_PROVIDERS:
        return

    # Local has no API key but still validates (server-running, model-pulled).
    if provider == "local":
        api_key, source = "", "stored"
    else:
        api_key, source = _api_key_for(settings)
        if not api_key:
            return

    # Azure needs endpoint + deployment alongside the key; mirror the
    # missing-key early-exit rather than letting AzureOpenAI('', ...) send
    # to a nonsense URL on first-setup.
    if provider == "azure" and not (
        settings.azure_endpoint and settings.azure_deployment
    ):
        return

    state = read_state()
    first_run = bool(state.get("first_run", True))
    if _is_recently_validated(state, provider):
        return

    facts = billing_for(provider)
    if first_run and facts is not None and sys.stdin.isatty() and provider != "local":
        # Source attribution on first run only, TTY only (per "anti-patterns:
        # silent magic on credential surfaces"). ``first_run`` is
        # until-first-success, not until-first-attempt: an invalid-key first
        # run leaves the flag set so the attribution fires again next time.
        # Local has no key source to attribute — skip the line.
        console.print(
            "  "
            + t(
                "preflight.api_key.source_attribution",
                provider_display=facts.display_name,
                source=source,
            )
        )

    # The moment the provider/model pair is sent on the wire — this is where a
    # provider≠model mismatch (e.g. anthropic endpoint + gpt-4o) surfaces as a
    # 404. Logged so the run log pinpoints which pair was validated.
    _wire_model = settings.azure_deployment if provider == "azure" else (
        settings.local_model if provider == "local" else settings.llm_model
    )
    logger.info(
        "llm_preflight_validate | provider=%s | model=%s | event=preflight_api_key "
        "[preflight/api_key.py] validator=_validate_%s",
        provider,
        _wire_model,
        provider,
    )

    # Resolve the validator through globals() rather than a module-level dict:
    # tests monkeypatch ``_validate_*`` by name, and a captured-at-import
    # dict reference would not pick that up.
    validator = globals()[f"_validate_{provider}"]
    if provider == "azure":
        result = validator(
            api_key,
            settings.azure_endpoint,
            settings.azure_deployment,
            settings.azure_api_version,
        )
    elif provider == "local":
        result = validator(settings.local_url, settings.local_model)
    else:
        result = validator(api_key, settings.llm_model)
    if result.ok:
        _mark_validated(state, provider, source=source)
        try:
            write_state(state)
        except OSError as exc:
            # State write failure is non-fatal: validation succeeded.
            logger.warning("Could not write preflight state: %s", exc)
        return

    raise ApiKeyPreflightAbortedError(
        recovery_message(
            provider,
            result.error_class or "",
            raw_message=result.raw_message,
        )
    )
