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
        # Anthropic returns 400 with "credit_balance_too_low" when the
        # workspace is funded but has no remaining credit.
        if "credit_balance_too_low" in str(exc):
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
        # ``insufficient_quota`` code in the response body.
        if "insufficient_quota" in str(exc):
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


# Providers with rich validation (paid /messages call + error-class translation).
# Other providers — azure, google, local — fall through to the generic "Provider
# says: ..." path on the call site.
_SUPPORTED_PROVIDERS = frozenset({"anthropic", "openai"})


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
    api_key, source = _api_key_for(settings)
    if not api_key:
        return

    state = read_state()
    first_run = bool(state.get("first_run", True))
    if _is_recently_validated(state, provider):
        return

    facts = billing_for(provider)
    if first_run and facts is not None and sys.stdin.isatty():
        # Source attribution on first run only, TTY only (per "anti-patterns:
        # silent magic on credential surfaces"). ``first_run`` is
        # until-first-success, not until-first-attempt: an invalid-key first
        # run leaves the flag set so the attribution fires again next time.
        console.print(
            "  "
            + t(
                "preflight.api_key.source_attribution",
                provider_display=facts.display_name,
                source=source,
            )
        )

    # Resolve the validator through globals() rather than a module-level dict:
    # tests monkeypatch ``_validate_anthropic`` / ``_validate_openai`` by name,
    # and a captured-at-import dict reference would not pick that up.
    validator = globals()[f"_validate_{provider}"]
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
