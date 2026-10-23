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
GATEWAYS: frozenset[str] = frozenset({"openrouter", "portkey", "requesty", "edenai"})


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
    if importlib.util.find_spec("any_llm") is None:
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
    os.environ.setdefault("ANY_LLM_UNIFIED_EXCEPTIONS", "1")


@dataclass(frozen=True)
class Readiness:
    """The answer to "can a call go out?", worked out offline.

    ``status`` is one of: ``ready``, ``not-installed``, ``broken``, ``no-model``,
    ``bad-model``, ``native``, ``unknown-provider``, ``sdk-missing``, ``no-key``.
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

    # Building the provider is offline: it reads the key and makes a client
    # object; nothing goes over the network.
    try:
        AnyLLM.create(inner)
        return Readiness("ready", model=model, inner=inner, key_source="environment")
    except MissingApiKeyError as exc:
        env_var = exc.env_var_name
    except ImportError as exc:
        return Readiness("sdk-missing", model=model, inner=inner, detail=str(exc))

    if api_key is None:
        api_key = stored_key(inner)
        source = _store_label() if api_key else ""
    else:
        source = "given"
    if not api_key:
        return Readiness("no-key", model=model, inner=inner, env_var=env_var)
    try:
        AnyLLM.create(inner, api_key=api_key)
    except MissingApiKeyError:
        return Readiness("no-key", model=model, inner=inner, env_var=env_var)
    return Readiness(
        "ready", model=model, inner=inner, api_key=api_key,
        key_source=source, env_var=env_var,
    )


def stored_key(inner: str) -> str | None:
    """The key ``bristlenose configure any-llm`` stored for ``inner``, if any."""
    from bristlenose.credentials import get_credential_store

    try:
        return get_credential_store().get(credential_key(inner)) or None
    except Exception:  # a store that cannot answer has no key for us
        logger.debug("credential store read failed for %s", inner, exc_info=True)
        return None


def _store_label() -> str:
    from bristlenose.credentials import get_credential_store_label

    return get_credential_store_label()


def destination(inner: str) -> str:
    """Where transcripts go: the host when any-llm's provider class names one.

    Never a table we keep: a class with no ``API_BASE`` (Mistral, in 1.27) is
    named by its product name instead.
    """
    try:
        from any_llm import AnyLLM

        base = getattr(AnyLLM.get_provider_class(inner), "API_BASE", None)
    except Exception:
        base = None
    host = urlparse(base).hostname if isinstance(base, str) else None
    return f"{display_name(inner)} ({host})" if host else display_name(inner)


def install_hint() -> str:
    """How to add any-llm to this copy of Bristlenose, for its install channel."""
    from bristlenose.utils.install_channel import add_extra_command

    return add_extra_command("any-llm")


def inject_hint(inner: str) -> str:
    """How to add the SDK an inner provider needs to this copy of Bristlenose."""
    from bristlenose.utils.install_channel import inject_command

    return inject_command(f"any-llm-sdk[{inner}]")


def classify(exc: BaseException) -> Any:
    """Classify a failure from any-llm into an ``LLMFailureKind``.

    The provider's own error first: the original SDK exception carries the
    status and code our generic rules read (only the provider-agnostic ones:
    the provider-scoped rules describe the five built-in providers' wires). Then
    any-llm's type, for the cases the wire does not mark.
    """
    from bristlenose.llm.failure_classifier import LLMFailureKind, classify_fields

    original = getattr(exc, "original_exception", None)
    for candidate in (original, exc):
        if isinstance(candidate, BaseException):
            kind = classify_fields("anyllm", candidate)
            if kind is not LLMFailureKind.UNKNOWN:
                return kind
    name = type(exc).__name__
    by_type = {
        "InsufficientFundsError": LLMFailureKind.OUT_OF_CREDIT,
        "AuthenticationError": LLMFailureKind.INVALID_KEY,
        "MissingApiKeyError": LLMFailureKind.INVALID_KEY,
        "RateLimitError": LLMFailureKind.RATE_LIMITED,
        "ModelNotFoundError": LLMFailureKind.BAD_REQUEST,
        "ContextLengthExceededError": LLMFailureKind.BAD_REQUEST,
        "InvalidRequestError": LLMFailureKind.BAD_REQUEST,
        "GatewayTimeoutError": LLMFailureKind.SERVER_ERROR,
        "UpstreamProviderError": LLMFailureKind.SERVER_ERROR,
    }
    return by_type.get(name, LLMFailureKind.UNKNOWN)


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
    if ready.status == "broken":
        return ["any-llm is installed but won't load.", ready.detail]
    if ready.status == "no-model":
        return [
            "any-llm needs a model, written as provider:model.",
            "Set it once:  bristlenose configure any-llm",
            "Or per run:   BRISTLENOSE_ANYLLM_MODEL=mistral:mistral-large-latest",
        ]
    if ready.status == "bad-model":
        return ["Write the model as provider:model, e.g. mistral:mistral-large-latest"]
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
    try:
        from any_llm import AnyLLM

        env_name = getattr(AnyLLM.get_provider_class(parts[0]), "ENV_API_KEY_NAME", "")
    except Exception:
        env_name = ""
    if isinstance(env_name, str) and env_name.isidentifier() and os.environ.get(env_name):
        return os.environ[env_name]
    return stored_key(parts[0]) or ""

