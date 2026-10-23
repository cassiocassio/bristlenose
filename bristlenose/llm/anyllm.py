"""any-llm: one way in to the providers Bristlenose doesn't build in.

mozilla-ai/any-llm (``any-llm-sdk``) is one call over the official SDKs of
about fifty providers. Bristlenose offers it as the sixth provider, ``anyllm``,
for the long tail (Mistral, OpenRouter, DeepSeek…); the five built-in providers
keep their own code paths. Design: ``docs/design-any-llm.md``.

Everything any-llm-specific lives here, so ``client.py``, ``cli.py``,
``doctor.py`` and the server ask one module the same questions. The library is
an optional extra (``bristlenose[any-llm]``) and is imported lazily, inside the
functions that need it, never at module top.

The model is written ``provider:model`` (``mistral:mistral-large-latest``).
The part before the first colon is the *inner* provider.
"""

from __future__ import annotations

import difflib
import importlib.util
import logging
import os
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from bristlenose.config import BristlenoseSettings

logger = logging.getLogger(__name__)

#: The distribution the extra installs. Checked by name because an unrelated
#: package called ``anyllm`` exists on PyPI.
DISTRIBUTION = "any-llm-sdk"

#: Inner providers any-llm offers that Bristlenose already builds in, mapped to
#: the name ``bristlenose configure`` / ``use`` takes and the product name. The
#: built-in route has our tuned request settings, pricing and error rules, so
#: any-llm is never a second, worse way to the same provider.
NATIVE_PREFIXES: dict[str, tuple[str, str]] = {
    "anthropic": ("claude", "Claude"),
    "openai": ("chatgpt", "ChatGPT"),
    "gemini": ("gemini", "Gemini"),
    "azureopenai": ("azure", "Azure OpenAI"),
    "ollama": ("local", "Ollama"),
}

#: Product names for the inner providers we name in copy. Display only: a
#: provider missing here is named by its id, title-cased.
_DISPLAY: dict[str, str] = {
    "mistral": "Mistral",
    "openrouter": "OpenRouter",
    "deepseek": "DeepSeek",
    "groq": "Groq",
    "xai": "xAI",
    "cohere": "Cohere",
    "together": "Together",
    "fireworks": "Fireworks",
    "perplexity": "Perplexity",
}

#: Inner providers that pass the request on to another company (the model's
#: host). ``configure`` says so when one is chosen.
GATEWAYS: frozenset[str] = frozenset(
    {"openrouter", "portkey", "requesty", "edenai", "otari", "mzai"}
)


def display_name(inner: str) -> str:
    """The product name for an inner provider id (``mistral`` → ``Mistral``)."""
    return _DISPLAY.get(inner, inner.title())


def split_model(model: str) -> tuple[str, str] | None:
    """``"mistral:mistral-large-latest"`` → ``("mistral", "mistral-large-latest")``.

    Splits on the first colon, as any-llm does, so a model id may itself contain
    colons (``openrouter:meta-llama/llama-3.3-70b-instruct:free``). Returns None
    when the string is not in the ``provider:model`` form.
    """
    inner, sep, model_id = model.strip().partition(":")
    inner = inner.strip().lower()
    model_id = model_id.strip()
    if not sep or not inner or not model_id or "/" in inner:
        return None
    return inner, model_id


def credential_key(inner: str) -> str:
    """The credential-store key for an inner provider's API key."""
    return f"anyllm_{inner}"


def install_state() -> str | None:
    """``None`` when any-llm imports; otherwise why not.

    ``"not-installed"`` when the package is simply absent. Any other failure to
    import is returned verbatim: a present-but-broken install must not be told
    to install what it already has.
    """
    try:
        if "any_llm" not in sys.modules and importlib.util.find_spec("any_llm") is None:
            return "not-installed"
    except (ImportError, ValueError):
        return "not-installed"
    try:
        import any_llm  # noqa: F401
    except ModuleNotFoundError as exc:
        if (exc.name or "").split(".")[0] == "any_llm":
            return "not-installed"
        return f"{type(exc).__name__}: {exc}"
    except Exception as exc:  # a broken install, shown as it is
        return f"{type(exc).__name__}: {exc}"
    return None


def installed_version() -> str | None:
    """The installed ``any-llm-sdk`` version, or None."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(DISTRIBUTION)
    except PackageNotFoundError:
        return None


def enable_unified_exceptions() -> None:
    """Ask any-llm for its typed errors in this process only.

    any-llm 1.27 converts provider errors into its own types only when this
    variable is set; otherwise it re-raises each SDK's own exception. Set in
    Bristlenose's process, never the user's shell. (From 1.29 the same switch is
    a ``create`` argument; the variable still works.)
    """
    # Assigned, not setdefault: an inherited =0 would turn the typed errors off
    # and leave classification reading raw SDK shapes.
    os.environ["ANY_LLM_UNIFIED_EXCEPTIONS"] = "1"


@dataclass(frozen=True)
class Readiness:
    """The answer to "can a call go out?", worked out offline.

    ``status`` is one of: ``ready``, ``not-installed``, ``old-python``,
    ``broken``, ``no-model``, ``bad-model``, ``key-as-model``, ``native``,
    ``unknown-provider``, ``sdk-missing``, ``no-key``.
    """

    status: str
    model: str = ""
    inner: str = ""
    #: The stored key to pass as ``api_key=``; None when any-llm finds the key in
    #: the environment itself, or when there is none.
    api_key: str | None = None
    #: Where the key came from: ``environment``, the store's label, or "".
    key_source: str = ""
    #: The variable the provider's key is read from, as any-llm names it.
    env_var: str = ""
    #: ``unknown-provider``: the closest known provider, if any.
    suggestion: str = ""
    #: ``broken`` / ``sdk-missing``: the import error, verbatim.
    detail: str = ""
    #: A key was given, but this variable is set and wins at run time.
    shadowed_by: str = ""

    @property
    def ready(self) -> bool:
        return self.status == "ready"


def readiness(settings: BristlenoseSettings, *, api_key: str | None = None) -> Readiness:
    """Work out whether an any-llm call can go out, without calling anyone.

    One answer shared by ``configure``, ``doctor``, the server and the client.
    ``api_key`` is a key the caller has in hand (``configure`` before storing).
    Key lookup: the provider's own environment variable first (any-llm reads it
    itself), then ``api_key``, then the credential store.
    """
    model = (settings.anyllm_model or "").strip()
    state = install_state()
    if state == "not-installed":
        if sys.version_info < (3, 11):
            return Readiness("old-python", model=model)
        return Readiness("not-installed", model=model)
    if state is not None:
        return Readiness("broken", model=model, detail=state)
    return readiness_for_model(model, api_key=api_key)


def readiness_for_model(model: str, *, api_key: str | None = None) -> Readiness:
    """:func:`readiness` for a model string, with any-llm known to import."""
    if not model:
        return Readiness("no-model")
    parts = split_model(model)
    if parts is None:
        return Readiness("bad-model", model=model)
    inner, _ = parts
    if inner in NATIVE_PREFIXES:
        return Readiness("native", model=model, inner=inner)

    from any_llm import AnyLLM
    from any_llm.exceptions import MissingApiKeyError

    supported = AnyLLM.get_supported_providers()
    if inner not in supported:
        close = difflib.get_close_matches(inner, supported, n=1, cutoff=0.75)
        return Readiness(
            "unknown-provider", model=model, inner=inner,
            suggestion=close[0] if close else "",
        )

    try:
        cls = AnyLLM.get_provider_class(inner)
    except ImportError as exc:
        return Readiness("sdk-missing", model=model, inner=inner, detail=str(exc))
    if getattr(cls, "MISSING_PACKAGES_ERROR", None) is not None:
        return Readiness(
            "sdk-missing", model=model, inner=inner,
            detail=str(cls.MISSING_PACKAGES_ERROR),
        )

    # Building the provider makes a client object from the key; nothing goes
    # over the network for the providers we name. Anything it raises besides a
    # missing key is shown as it is, never allowed to escape: callers include
    # `doctor` and the server's key checks (Vertex raises google-auth's
    # DefaultCredentialsError, Azure-hosted Anthropic a ValueError).
    env_value = env_key(inner)
    if api_key is not None:
        # A key the user just gave (configure --key, or the prompt) is the one
        # to check, even when the provider's variable is also set; that variable
        # still wins at run time, so say so.
        try:
            AnyLLM.create(inner, api_key=api_key)
        except Exception as exc:  # noqa: BLE001 — shown verbatim
            return _broken(model, inner, exc)
        # Only a different key is shadowed: the walk re-entered the key it had
        # exported and was warned about two identical keys.
        env_name = env_var_name(inner) if env_value and env_value != api_key else ""
        return _check_key_is_not_model(Readiness(
            "ready", model=model, inner=inner, api_key=api_key,
            key_source="given", shadowed_by=env_name,
        ))
    try:
        AnyLLM.create(inner)
        return _check_key_is_not_model(
            Readiness("ready", model=model, inner=inner, key_source="environment",
                      env_var=env_var_name(inner))
        )
    except MissingApiKeyError as exc:
        env_var = exc.env_var_name
    except ImportError as exc:
        return Readiness("sdk-missing", model=model, inner=inner, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 — shown verbatim
        return _broken(model, inner, exc)

    stored = stored_key(inner)
    if not stored:
        return Readiness("no-key", model=model, inner=inner, env_var=env_var)
    try:
        AnyLLM.create(inner, api_key=stored)
    except MissingApiKeyError:
        return Readiness("no-key", model=model, inner=inner, env_var=env_var)
    except Exception as exc:  # noqa: BLE001 — shown verbatim
        return _broken(model, inner, exc)
    return _check_key_is_not_model(Readiness(
        "ready", model=model, inner=inner, api_key=stored,
        key_source=_store_label(), env_var=env_var,
    ))


def _broken(model: str, inner: str, exc: BaseException) -> Readiness:
    return Readiness("broken", model=model, inner=inner, detail=f"{type(exc).__name__}: {exc}")


def _check_key_is_not_model(ready: Readiness) -> Readiness:
    """``provider:<the key>``: a key pasted where the model goes.

    An exact comparison, not a pattern: the model id is the key that would be
    sent. Caught before anything echoes, stores or logs the model string.
    """
    parts = split_model(ready.model)
    key = ready.api_key or env_key(ready.inner)
    if parts and key and parts[1] == key:
        return Readiness("key-as-model", inner=ready.inner)
    return ready


def env_var_name(inner: str) -> str:
    """The provider's key variable, when any-llm's class names a real one.

    Display and comparison only, never readiness: ``ENV_API_KEY_NAME`` is
    ``"None"`` for llama.cpp, empty for Vertex and a sentence for SageMaker, so
    whether a key is *needed* is answered by building the provider.
    """
    try:
        from any_llm import AnyLLM

        name = getattr(AnyLLM.get_provider_class(inner), "ENV_API_KEY_NAME", "")
    except Exception:
        return ""
    if isinstance(name, str) and name.isidentifier() and name != "None":
        return name
    return ""


def env_key(inner: str) -> str:
    """The provider's key from the environment, or ""."""
    name = env_var_name(inner)
    return os.environ.get(name, "") if name else ""


def stored_key(inner: str) -> str | None:
    """The key ``bristlenose configure any-llm`` stored for ``inner``, if any."""
    from bristlenose.credentials import get_credential_store

    try:
        return get_credential_store().get(credential_key(inner)) or None
    except Exception:  # a store that cannot answer has no key for us
        # WARNING, not DEBUG: the next thing the user reads is "none is
        # stored", which this makes false.
        logger.warning("credential store read failed for %s", inner, exc_info=True)
        return None


def _store_label() -> str:
    from bristlenose.credentials import get_credential_store_label

    return get_credential_store_label()


def api_base(inner: str) -> tuple[str | None, str]:
    """The base URL any-llm will send to, and the variable it came from.

    Resolved as the library does (``AnyLLM._resolve_api_base``): the provider's
    ``*_API_BASE`` variable over the class default. A variable left in a shell
    profile by another tool sends the transcripts and the key elsewhere, so it
    is never shown as the default host.
    """
    try:
        from any_llm import AnyLLM

        cls = AnyLLM.get_provider_class(inner)
    except Exception:
        return None, ""
    var = getattr(cls, "ENV_API_BASE_NAME", None) or ""
    override = os.environ.get(var) if var else None
    if override:
        return override, var
    base = getattr(cls, "API_BASE", None)
    return (base if isinstance(base, str) else None), ""


def destination(inner: str) -> str:
    """Where transcripts go, as a researcher reads it.

    The host the request will reach, from :func:`api_base`; a class with no
    default host and no override (Mistral, in 1.27) is named by its product
    name. Never a table we keep.
    """
    base, var = api_base(inner)
    host = urlparse(base).hostname if base else None
    if not host:
        return display_name(inner)
    if var:
        return f"{display_name(inner)} ({host}, from {var})"
    return f"{display_name(inner)} ({host})"


def insecure_base(inner: str) -> bool:
    """True when transcripts would go over plain HTTP to a host off this machine."""
    base, _ = api_base(inner)
    if not base:
        return False
    parsed = urlparse(base)
    local = {"localhost", "127.0.0.1", "::1"}
    return parsed.scheme == "http" and (parsed.hostname or "") not in local


def install_hint() -> str:
    """How to add any-llm to this copy of Bristlenose, for its install channel."""
    from bristlenose.utils.install_channel import add_extra_command

    return add_extra_command("any-llm")


def inject_hint(inner: str) -> str:
    """How to add the SDK an inner provider needs to this copy of Bristlenose."""
    from bristlenose.utils.install_channel import inject_command

    version = installed_version()
    pin = f"=={version}" if version else ""
    return inject_command(f"any-llm-sdk[{inner}]{pin}")


def classify(exc: BaseException) -> Any:
    """Classify a failure from any-llm into an ``LLMFailureKind``.

    The provider's own error first: the original SDK exception carries the
    status and code our generic rules read (only the provider-agnostic ones:
    the provider-scoped rules describe the five built-in providers' wires). Then
    any-llm's type, for the cases the wire does not mark.
    """
    from bristlenose.llm.failure_classifier import LLMFailureKind, classify_fields

    if is_network_error(exc):
        return LLMFailureKind.NETWORK
    original = getattr(exc, "original_exception", None)
    kind = LLMFailureKind.UNKNOWN
    for candidate in (original, exc):
        if isinstance(candidate, BaseException):
            kind = classify_fields("anyllm", candidate)
            if kind is not LLMFailureKind.UNKNOWN:
                break
    if (
        type(exc).__name__ == "ModelNotFoundError"
        and kind in (LLMFailureKind.BAD_REQUEST, LLMFailureKind.UNKNOWN)
        and upstream(exc) is None
    ):
        # any-llm's own reading of a 404 the wire leaves generic: the model
        # (R102), as the preflight reads it. A gateway's 404 from the model's
        # host keeps the host's reading, which names it.
        return LLMFailureKind.MODEL_UNAVAILABLE
    if kind is not LLMFailureKind.UNKNOWN:
        return kind
    # Only what the status can't say: any-llm's errors carry the provider's
    # status_code, which the rules above already read.
    by_type = {
        "InsufficientFundsError": LLMFailureKind.OUT_OF_CREDIT,
        "MissingApiKeyError": LLMFailureKind.INVALID_KEY,
    }
    return by_type.get(type(exc).__name__, LLMFailureKind.UNKNOWN)


def explain(ready: Readiness) -> list[str]:
    """What to say when :func:`readiness` is not ``ready``: the problem, then
    the fix, one line each. Shared by the CLI, ``doctor`` and ``LLMClient``, so
    the same state reads the same everywhere. Plain text (no Rich markup); the
    caller escapes it."""
    inner = ready.inner
    name = display_name(inner) if inner else ""
    if ready.status == "not-installed":
        return [
            "any-llm isn't installed in this copy of Bristlenose.",
            f"Add it:  {install_hint()}",
        ]
    if ready.status == "old-python":
        return [
            "any-llm needs Python 3.11 or newer; this Bristlenose runs on "
            f"Python {sys.version_info.major}.{sys.version_info.minor}.",
            "Reinstall Bristlenose with a newer Python, e.g. "
            "pipx install --python python3.12 \"bristlenose[any-llm]\"",
        ]
    if ready.status == "broken":
        if ready.inner:
            return [f"any-llm can't set up {name}.", ready.detail]
        return ["any-llm is installed but won't load.", ready.detail]
    if ready.status == "no-model":
        return [
            "any-llm needs a model, written as provider:model.",
            "Set it once:  bristlenose configure any-llm",
            "Or per run:   BRISTLENOSE_ANYLLM_MODEL=mistral:mistral-large-latest",
        ]
    if ready.status == "bad-model":
        return ["Write the model as provider:model, e.g. mistral:mistral-large-latest"]
    if ready.status == "key-as-model":
        return [
            f"That's your {name} API key, not a model. Write the model as "
            "provider:model, e.g. mistral:mistral-large-latest",
        ]
    if ready.status == "native":
        cli_name, product = NATIVE_PREFIXES[inner]
        return [f"{product} is built in. Use:  bristlenose configure {cli_name}"]
    if ready.status == "unknown-provider":
        line = f'any-llm doesn\'t know a provider called "{inner}".'
        if ready.suggestion:
            line += f" Did you mean {ready.suggestion}?"
        return [line, "Providers: https://mozilla-ai.github.io/any-llm/providers/"]
    if ready.status == "sdk-missing":
        return [
            f"{name} needs an add-on this install doesn't have.",
            f"Add it:  {inject_hint(inner)}",
        ]
    if ready.status == "no-key":
        return [
            f"No {name} API key: {ready.env_var} isn't set and none is stored.",
            "Store one:  bristlenose configure any-llm",
            f"(A .env file isn't read for {ready.env_var}; set it in your shell.)",
        ]
    return []


def account_name(settings: BristlenoseSettings) -> str:
    """The product whose account a run uses ("Mistral"), for failure copy.

    A key is rejected, or credit runs out, at Mistral or OpenRouter, never at
    any-llm, which is a library. "" when no model is set.
    """
    parts = split_model(settings.anyllm_model or "")
    return display_name(parts[0]) if parts else ""


def active_key(settings: BristlenoseSettings) -> str:
    """The key a run will send for the current any-llm model, or "".

    The provider's own environment variable first (as any-llm reads it), then
    the stored key. Used only to show the last characters of a rejected key.
    """
    parts = split_model(settings.anyllm_model or "")
    if parts is None or install_state() is not None:
        return ""
    return env_key(parts[0]) or stored_key(parts[0]) or ""


#: Connection-failure classes, matched by name across the SDKs any-llm wraps:
#: httpx and httpx2 (mistralai imports httpx2 as httpx; its ConnectError is not
#: httpx's) and openai's own. Names, because the classes are not related.
_NETWORK_NAMES = frozenset({
    "ConnectError", "ConnectTimeout", "ReadTimeout", "WriteTimeout", "PoolTimeout",
    "ReadError", "WriteError",
    "APIConnectionError", "APITimeoutError", "RemoteProtocolError",
})


def is_network_error(exc: BaseException) -> bool:
    """True when the failure is reaching the provider, not the provider's answer.

    any-llm wraps a connection failure as a status-less ``ProviderError``; the
    cause is down the chain (``original_exception``, ``__cause__``,
    ``__context__``), so walk it.
    """
    seen: set[int] = set()
    todo: list[BaseException | None] = [exc]
    while todo:
        cur = todo.pop()
        if cur is None or id(cur) in seen:
            continue
        seen.add(id(cur))
        if type(cur).__name__ in _NETWORK_NAMES:
            return True
        todo += [getattr(cur, "original_exception", None), cur.__cause__, cur.__context__]
    return False


def upstream(exc: BaseException) -> tuple[str, str] | None:
    """For a gateway's error, the host that actually failed and why, if it says.

    OpenRouter wraps a failure at the model's host as ``Provider returned
    error`` with ``metadata.provider_name`` ("Mistral") and, for a busy shared
    pool, ``metadata.limit_source`` ("upstream_provider_shared_pool"). The key
    and OpenRouter are fine then; saying "rate-limiting this key" sends the
    researcher the wrong way (found by the OpenRouter walk, 23 Oct 2026).
    Returns ``(host, limit_source)``, either possibly "", or None. The message
    alone marks it as the host's failure when the metadata is missing; the host
    is then "" and the caller says "the model's host".

    The host is the gateway's text, printed and written to the events log, so
    it is cut to a name's length and kept to printable characters.
    """
    seen: set[int] = set()
    todo: list[BaseException | None] = [exc]
    while todo:
        cur = todo.pop()
        if cur is None or id(cur) in seen:
            continue
        seen.add(id(cur))
        body = getattr(cur, "body", None)
        if isinstance(body, dict):
            # The openai SDK unwraps OpenRouter's {"error": {...}}; others don't.
            err = body["error"] if isinstance(body.get("error"), dict) else body
            meta = err.get("metadata")
            meta = meta if isinstance(meta, dict) else {}
            if (
                meta.get("provider_name")
                or meta.get("limit_source")
                or err.get("message") == _UPSTREAM_MESSAGE
            ):
                return _host_name(meta.get("provider_name")), str(meta.get("limit_source") or "")
        # Not __context__: that is whatever was being handled when this was
        # raised. The json_object fallback runs inside the except that caught a
        # host's refusal, so a later key-level 429 would be blamed on the host.
        todo += [getattr(cur, "original_exception", None), cur.__cause__]
    return None


#: OpenRouter's message when the model's host, not OpenRouter, failed.
_UPSTREAM_MESSAGE = "Provider returned error"


def _host_name(value: object) -> str:
    text = "".join(ch for ch in str(value or "") if ch.isprintable()).strip()
    return text[:40]
