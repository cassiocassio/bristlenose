"""API-key preflight — validates the active provider's key against billing before stage 1.

The friendly-CTO call on 9 May 2026 found three different failure modes for
"unconfigured Claude account" that all looked identical to a researcher: key
missing, key invalid, and key valid but no billing balance. The first two
were caught by existing checks; the third surfaced only when the first LLM
stage actually ran, several minutes into the pipeline.

This preflight runs a paid ``/messages`` call up-front. Per finding 15:

- The run's own request: the model and every parameter a pipeline call
  carries (output cap, sampling, the cap's name), from the client's
  ``request_params`` rather than a copy of it. Until 20 Oct 2026 this was a
  one-token ping that sent none of them, so a model refusing ``temperature``,
  or a cap above the model's ceiling, passed here and failed the run at its
  first stage (R104). A high cap costs nothing by itself: billing is per token
  produced, and the reply to ``"."`` is a few tokens.
- Locked inert prompt: ``"."`` (constant; never user-derived — so the call
  is greppable and cannot leak transcript content)
- ``User-Agent: bristlenose/<version>`` so server-side logs identify us
- One call per validation

The point is to *exercise billing*. A free probe (e.g. ``/models``) can't
distinguish "key valid + paid" from "key valid + no balance" — both return
200. A paid call does.

State (finding 8): :func:`state_path` returns ``~/Library/Application
Support/Bristlenose/state.json`` on macOS and ``$XDG_DATA_HOME/Bristlenose/
state.json`` on Linux. The 24-hour TTL means a successful validation skips
the network on subsequent runs within the window — for the same request only:
each record carries :func:`request_fingerprint` (the model, the
``request_params``, a hash of the key, and where it goes: the Azure endpoint
and API version, or the Ollama address), so a model, ``llm_max_tokens``, key or
endpoint changed the same day is checked again. The key itself is never
written. Until 20 Oct 2026 the record was keyed by provider alone, and until
the next day by model and parameters alone.

Whitelist (finding 4): the preflight is only called from LLM-touching
commands (``run``, ``analyze``, ``transcribe-only``). Read-only commands
(``status``, ``render``, ``doctor``, ``--help``, ``--version``) never
trigger it.

Scope: this preflight covers the **has-a-key, validate-it-now** path. The
**no-account-yet** branch (first-run provider guidance) and the
credential-storage integration both live on the existing
``_maybe_guide_provider_setup`` path in ``cli.py`` and are not duplicated
here — this module assumes a key is already in settings (env var,
keychain/store, or fresh paste).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rich.console import Console

    from bristlenose.config import BristlenoseSettings

from bristlenose import __version__
from bristlenose.i18n import t
from bristlenose.llm.billing_hints import billing_for, recovery_message
from bristlenose.llm.client import request_params
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


def read_state() -> dict[str, Any]:
    """Read the state JSON; return an empty schema on first run / parse error."""
    path = state_path()
    if not path.exists():
        return {"version": _STATE_VERSION, "first_run": True, "providers": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": _STATE_VERSION, "first_run": True, "providers": {}}
    if not isinstance(data, dict):
        return {"version": _STATE_VERSION, "first_run": True, "providers": {}}
    data.setdefault("version", _STATE_VERSION)
    data.setdefault("first_run", True)
    data.setdefault("providers", {})
    return data


def write_state(state: dict[str, Any]) -> None:
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


def request_fingerprint(
    model: str,
    params: dict[str, Any],
    *,
    key: str = "",
    endpoint: tuple[str, ...] = (),
) -> str:
    """A short digest of the request a validation sent: the model, the
    parameters from ``request_params``, the key, and where it was sent
    (``endpoint``: the Azure endpoint and API version, or the Ollama address;
    empty for a provider with one fixed address). The 24-hour cache holds only
    for the same request; a model, ``llm_max_tokens``, key or endpoint changed
    the same day is a new request, which the provider may refuse, so it is
    checked again. The key enters as its own SHA-256, never as itself."""
    key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest() if key else ""
    blob = json.dumps(
        {"model": model, "params": params, "key": key_hash, "endpoint": list(endpoint)},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _is_recently_validated(
    state: dict[str, Any], provider: str, request: str | None = None
) -> bool:
    info = state.get("providers", {}).get(provider, {})
    last = info.get("last_validated_epoch")
    if not isinstance(last, (int, float)):
        return False
    # A record from another request, or from before records named one (the
    # one-token ping that sent none of the run's parameters), proves nothing
    # about this request.
    if request is not None and info.get("request") != request:
        return False
    return (time.time() - last) < _TTL_SECONDS


def _mark_validated(
    state: dict[str, Any], provider: str, *, source: str, request: str | None = None
) -> None:
    info: dict[str, Any] = {
        "last_validated_epoch": int(time.time()),
        "source": source,
    }
    if request is not None:
        info["request"] = request
    state.setdefault("providers", {})[provider] = info
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


def _params_for(provider: str, model: str, params: dict[str, Any] | None) -> dict[str, Any]:
    """The pipeline's parameters for ``model``: given by the orchestrator from the
    run's settings, or, for a direct call, at the settings' defaults."""
    if params is not None:
        return params
    from bristlenose.config import BristlenoseSettings

    fields = BristlenoseSettings.model_fields
    return request_params(
        provider, model, fields["llm_max_tokens"].default, fields["llm_temperature"].default
    )


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


def _validate_anthropic(
    api_key: str, model: str, *, params: dict[str, Any] | None = None
) -> ValidationResult:
    """Exercise billing with the run's own ``/messages`` request to the Anthropic API."""
    import anthropic

    params = _params_for("anthropic", model, params)

    client = anthropic.Anthropic(
        api_key=api_key,
        default_headers={"User-Agent": f"bristlenose/{__version__}"},
    )
    try:
        client.messages.create(
            model=model,
            messages=[{"role": "user", "content": _VALIDATION_PROMPT}],
            max_tokens=params["max_tokens"],
            timeout=params["timeout"],
            extra_body=params["extra_body"],
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
        # Any other 400 is the request itself: an output cap above the model's
        # ceiling, a sampling parameter the model refuses (R104 sends both, as the
        # run does). Said in the provider's own words; "the model is not available
        # for your account" sent researchers to the wrong console. An unknown
        # model is a 404, handled below.
        return ValidationResult(ok=False, error_class=None, raw_message=str(exc))
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


def _validate_openai(
    api_key: str, model: str, *, params: dict[str, Any] | None = None
) -> ValidationResult:
    """Exercise billing with the run's own chat-completion request to the OpenAI API.

    The parameters, and their names, are the client's (``request_params``):
    GPT-5 onward refuses ``max_tokens`` and a non-default temperature, the
    models before it refuse ``max_completion_tokens``. On 4 Sep 2026 the client
    was gated and this validator was not, and every ChatGPT run aborted here on
    a good key; mocked tests passed throughout, because a mock accepts any
    keyword.
    """
    import openai

    params = _params_for("openai", model, params)

    client = openai.OpenAI(
        api_key=api_key,
        default_headers={"User-Agent": f"bristlenose/{__version__}"},
    )
    try:
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": _VALIDATION_PROMPT}],
            **params,
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
    api_key: str,
    endpoint: str,
    deployment: str,
    api_version: str,
    *,
    params: dict[str, Any] | None = None,
) -> ValidationResult:
    """Exercise the Azure OpenAI deployment with the run's own chat-completion request.

    Shares the openai SDK; differs from OpenAI in needing endpoint URL,
    deployment name (distinct from model id), and api version. The
    ``DeploymentNotFound`` 404 is the most common Azure foot-gun — recovery
    copy must call out that this is the **portal deployment name**, not
    a model id.
    """
    import openai

    params = _params_for("azure", deployment, params)
    client = openai.AzureOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=api_version,
        default_headers={"User-Agent": f"bristlenose/{__version__}"},
    )
    try:
        # The legacy shape, as ``LLMClient._analyze_azure`` sends it: a
        # deployment name is the customer's own word and cannot say whether a
        # GPT-5-class model sits behind it. One builder (``request_params``),
        # so the two move together.
        client.chat.completions.create(
            model=deployment,
            messages=[{"role": "user", "content": _VALIDATION_PROMPT}],
            **params,
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


def _validate_google(
    api_key: str, model: str, *, params: dict[str, Any] | None = None
) -> ValidationResult:
    """Exercise the Gemini API with the run's own ``generate_content`` parameters.

    Reads structured ``.code`` / ``.status`` fields on ``APIError`` instead
    of substring-matching the message. Gemini has no billing-empty concept
    (post-paid via GCP billing) — those errors route to model_unavailable.
    """
    from google import genai
    from google.genai import errors as genai_errors
    from google.genai import types

    params = _params_for("google", model, params)
    client = genai.Client(api_key=api_key)
    try:
        client.models.generate_content(
            model=model,
            contents=_VALIDATION_PROMPT,
            config=types.GenerateContentConfig(
                max_output_tokens=params["max_output_tokens"],
                temperature=params["temperature"],
            ),
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
        details_list: list[Any] = []
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


def _validate_local(
    local_url: str, model: str, *, params: dict[str, Any] | None = None
) -> ValidationResult:
    """Exercise a local Ollama-compatible endpoint with the run's own request.

    Runtime path uses the openai SDK pointed at ``local_url`` (Ollama is
    OpenAI-compatible); the preflight does the same — keeps the dep
    surface narrow and the failure modes consistent. No api key, no
    billing — failures are server-down or model-not-pulled.
    """
    import openai

    # The run's parameters, but not its output cap: Ollama refuses no cap, so
    # sending 64000 proves nothing, and a small model that rambles on "." could
    # hold setup for minutes on a laptop.
    params = {**_params_for("local", model, params), "max_tokens": 1}
    client = openai.OpenAI(
        base_url=local_url,
        api_key="ollama",  # required by SDK, ignored by Ollama
        default_headers={"User-Agent": f"bristlenose/{__version__}"},
    )
    try:
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": _VALIDATION_PROMPT}],
            **params,
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


def _validate_anyllm(
    api_key: str, model: str, *, params: dict[str, Any] | None = None
) -> ValidationResult:
    """Exercise a provider reached through any-llm with the run's own request.

    The run's parameters (``request_params`` sends none unless the user set
    them) and its response format, a ``json_schema`` dict, with the inert
    prompt: a provider that refuses the format, the model or the key refuses it
    here, not at the topic-segmentation stage (R104). ``api_key`` is "" when
    any-llm finds the key in the environment itself.
    """
    from any_llm import AnyLLM

    from bristlenose.llm import anyllm
    from bristlenose.llm.failure_classifier import LLMFailureKind

    anyllm.enable_unified_exceptions()
    parts = anyllm.split_model(model)
    if parts is None:
        return ValidationResult(ok=False, raw_message=f"not a provider:model string: {model!r}")
    inner, model_id = parts
    params = _params_for("anyllm", model, params)
    from bristlenose.llm.client import _refuses_json_schema

    schema_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "preflight",
            "schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}},
        },
    }
    try:
        provider = AnyLLM.create(inner, api_key=api_key or None)
        try:
            provider.completion(
                model=model_id,
                messages=[{"role": "user", "content": _VALIDATION_PROMPT}],
                response_format=schema_format,
                **params,
            )
        except Exception as exc:
            if not _refuses_json_schema(exc):
                raise
            # The run falls back to json_object for a provider that refuses the
            # schema (DeepSeek, for one); so does its check, or the run could
            # never start. json_object mode wants the word JSON in the messages.
            provider.completion(
                model=model_id,
                messages=[
                    {"role": "system", "content": "Reply in JSON."},
                    {"role": "user", "content": _VALIDATION_PROMPT},
                ],
                response_format={"type": "json_object"},
                **params,
            )
    except Exception as exc:
        network = _classify_network_error(exc)
        if network is not None:
            return network
        kind = anyllm.classify(exc)
        bucket = {
            LLMFailureKind.INVALID_KEY: "invalid_key",
            LLMFailureKind.OUT_OF_CREDIT: "billing_empty",
            LLMFailureKind.RATE_LIMITED: "rate_limit",
            LLMFailureKind.NETWORK: "network",
        }.get(kind)
        if bucket is None and type(exc).__name__ == "ModelNotFoundError":
            bucket = "model_unavailable"
        return ValidationResult(ok=False, error_class=bucket, raw_message=str(exc))
    return ValidationResult(ok=True)


# Providers with rich validation. Local has no key; orchestrator handles that.
_SUPPORTED_PROVIDERS = frozenset({"anthropic", "openai", "azure", "google", "local", "anyllm"})


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
    - **Recently validated** (24h TTL) with the same request (model,
      parameters, key and endpoint, :func:`request_fingerprint`): skip the
      network call.
    - **No key at all**: skip — the existing ``_maybe_guide_provider_setup``
      handles missing-key UX; the preflight only validates *present* keys.
    - **Non-TTY**: skip the first-run *banner* but still validate. A CI run
      with an expired key should abort here, not burn LLM cost at stage 8.
    - **Otherwise**: call the provider's paid validation endpoint with the
      run's own request (model and parameters) and an inert prompt. On failure raise :class:`PreflightAbortedError` with
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
    elif provider == "anyllm":
        # The key is the inner provider's: the environment (any-llm reads it)
        # or the one `configure any-llm` stored. Not ready → no request to
        # check; LLMClient refuses with the reason before any call.
        from bristlenose.llm import anyllm

        ready = anyllm.readiness(settings)
        if not ready.ready:
            return
        api_key, source = ready.api_key or "", ready.key_source
        # The cache key needs the key actually used — "" stands for an
        # environment key the validator lets any-llm read — and the host, which
        # a *_API_BASE variable can change. Either changing the same day is a
        # new request, checked again.
        _anyllm_fp_key = anyllm.active_key(settings)
        _anyllm_endpoint = (ready.inner, anyllm.api_base(ready.inner)[0] or "")
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

    # The request this run will send — the model on the wire, every parameter
    # the pipeline's calls carry, the key and the address it goes to — which the
    # cache below is keyed by.
    _wire_model = settings.azure_deployment if provider == "azure" else (
        settings.local_model if provider == "local" else (
            settings.anyllm_model if provider == "anyllm" else settings.llm_model
        )
    )
    params = request_params(
        provider, _wire_model, settings.llm_max_tokens, settings.llm_temperature
    )
    if provider == "azure":
        endpoint: tuple[str, ...] = (
            str(settings.azure_endpoint), str(settings.azure_api_version),
        )
    elif provider == "local":
        endpoint = (str(settings.local_url),)
    elif provider == "anyllm":
        endpoint = _anyllm_endpoint
    else:
        endpoint = ()
    request = request_fingerprint(
        _wire_model, params,
        key=_anyllm_fp_key if provider == "anyllm" else api_key,
        endpoint=endpoint,
    )

    state = read_state()
    first_run = bool(state.get("first_run", True))
    if _is_recently_validated(state, provider, request):
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
            params=params,
        )
    elif provider == "local":
        result = validator(settings.local_url, settings.local_model, params=params)
    elif provider == "anyllm":
        result = validator(api_key, settings.anyllm_model, params=params)
    else:
        result = validator(api_key, settings.llm_model, params=params)
    if result.ok:
        _mark_validated(state, provider, source=source, request=request)
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
