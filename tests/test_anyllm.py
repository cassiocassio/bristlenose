"""any-llm as the sixth provider (docs/design-any-llm.md §9).

CI never installs any-llm and never makes a paid call: a fake ``any_llm``
module stands in. It is shaped like the real 1.27 library where that shape is
what we depend on — ``MissingApiKeyError.env_var_name`` raised by ``create``, a
class-level ``MISSING_PACKAGES_ERROR``, ``API_BASE``, a raw ``ChatCompletion``
when the response format is a dict — so a test here fails the way the real
library would. ``scripts/check-providers-live.py`` asks the real thing.
"""

from __future__ import annotations

import asyncio
import json
import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from bristlenose import __version__
from bristlenose.config import BristlenoseSettings, load_settings
from bristlenose.llm import anyllm
from bristlenose.llm.client import LLMClient, TruncatedResponseError
from bristlenose.llm.failure_classifier import LLMFailureKind, classify_exception

MODEL = "mistral:mistral-large-latest"


class Theme(BaseModel):
    label: str
    quotes: list[str]


# ---------------------------------------------------------------------------
# The fake library
# ---------------------------------------------------------------------------


class _MissingApiKeyError(Exception):
    """any-llm's: raised by ``create`` when neither ``api_key`` nor the
    provider's variable is set, carrying the variable's name."""

    def __init__(self, provider_name: str, env_var_name: str) -> None:
        self.env_var_name = env_var_name
        super().__init__(f"No {provider_name} API key provided.")


def _response(content: str | None, finish_reason: str = "stop", refusal: str | None = None) -> Any:
    return SimpleNamespace(
        model="mistral-large-2411",
        usage=SimpleNamespace(prompt_tokens=120, completion_tokens=30),
        choices=[
            SimpleNamespace(
                finish_reason=finish_reason,
                message=SimpleNamespace(content=content, refusal=refusal),
            )
        ],
    )


_STILL_THINKING = object()  # a reply that never comes before s09's deadline


class _FakeProvider:
    def __init__(self, library: _FakeLibrary) -> None:
        self.library = library

    async def acompletion(self, **kwargs: Any) -> Any:
        if self.library.replies and self.library.replies[0] is _STILL_THINKING:
            self.library.calls.append(kwargs)
            self.library.replies.pop(0)
            await asyncio.sleep(10**6)  # answers only when cancelled, as a slow model does
        return self.completion(**kwargs)

    def completion(self, **kwargs: Any) -> Any:  # the preflight's sync call
        unexpected = set(kwargs) - {
            "model", "messages", "response_format", "max_tokens", "temperature",
            "reasoning_effort",
        }
        assert not unexpected, f"a parameter the call should not send: {unexpected}"
        self.library.calls.append(kwargs)
        if self.library.always_thinks and kwargs.get("reasoning_effort") == "none":
            # OpenRouter's answer for Gemini 2.5 Pro and GPT-5 mini (23 Oct 2026),
            # raised as any-llm's InvalidRequestError, which carries the status.
            raise _StatusError(400, "Reasoning is mandatory for this endpoint and cannot be disabled.")
        reply = self.library.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply


class _FakeLibrary:
    """``AnyLLM`` as a class with classmethods, like the real one."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.replies: list[Any] = []
        self.always_thinks = False  # a model that cannot switch thinking off
        self.created: list[tuple[str, str | None]] = []
        self.classes = {
            # Mistral's class names no API_BASE in 1.27.
            "mistral": types.SimpleNamespace(
                API_BASE=None, ENV_API_KEY_NAME="MISTRAL_API_KEY", MISSING_PACKAGES_ERROR=None,
                ENV_API_BASE_NAME="MISTRAL_API_BASE",
            ),
            "openrouter": types.SimpleNamespace(
                API_BASE="https://openrouter.ai/api/v1",
                ENV_API_KEY_NAME="OPENROUTER_API_KEY",
                MISSING_PACKAGES_ERROR=None,
                ENV_API_BASE_NAME="OPENROUTER_API_BASE",
            ),
            # Builds only with cloud credentials it can't find, as Vertex does.
            "vertexai": types.SimpleNamespace(
                API_BASE=None, ENV_API_KEY_NAME="", MISSING_PACKAGES_ERROR=None,
            ),
            # A provider whose SDK this install lacks.
            "cohere": types.SimpleNamespace(
                API_BASE=None, ENV_API_KEY_NAME="COHERE_API_KEY",
                MISSING_PACKAGES_ERROR=ImportError("No module named 'cohere'"),
            ),
            # Needs no key at all; its class names the variable "None".
            "llamacpp": types.SimpleNamespace(
                API_BASE="http://127.0.0.1:8080/v1", ENV_API_KEY_NAME="None",
                MISSING_PACKAGES_ERROR=None,
            ),
        }

    def module(self) -> types.ModuleType:
        library = self

        class AnyLLM:
            @classmethod
            def get_supported_providers(cls) -> list[str]:
                return [*library.classes, "anthropic", "openai", "gemini", "ollama"]

            @classmethod
            def get_provider_class(cls, provider: str) -> Any:
                return library.classes[provider]

            @classmethod
            def create(cls, provider: str, api_key: str | None = None, **_: Any) -> Any:
                import os

                spec = library.classes[provider]
                if provider == "vertexai":
                    raise ValueError("Your default credentials were not found")
                needs_key = spec.ENV_API_KEY_NAME not in ("None", "")
                if needs_key and not api_key and not os.environ.get(spec.ENV_API_KEY_NAME):
                    raise _MissingApiKeyError(provider, spec.ENV_API_KEY_NAME)
                library.created.append((provider, api_key))
                return _FakeProvider(library)

        import importlib.machinery

        module = types.ModuleType("any_llm")
        module.__spec__ = importlib.machinery.ModuleSpec("any_llm", None)
        module.AnyLLM = AnyLLM  # type: ignore[attr-defined]
        return module


@pytest.fixture
def fake_anyllm(monkeypatch: pytest.MonkeyPatch) -> _FakeLibrary:
    library = _FakeLibrary()
    exceptions = types.ModuleType("any_llm.exceptions")
    exceptions.MissingApiKeyError = _MissingApiKeyError  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "any_llm", library.module())
    monkeypatch.setitem(sys.modules, "any_llm.exceptions", exceptions)
    monkeypatch.setattr(anyllm, "install_state", lambda: None)
    monkeypatch.setattr(anyllm, "installed_version", lambda: "1.27.0")
    monkeypatch.setattr(anyllm, "stored_key", lambda inner: None)
    # Set by the client on first use; restored after the test.
    monkeypatch.delenv("ANY_LLM_UNIFIED_EXCEPTIONS", raising=False)
    for var in ("MISTRAL_API_KEY", "OPENROUTER_API_KEY", "COHERE_API_KEY",
                "MISTRAL_API_BASE", "OPENROUTER_API_BASE"):
        monkeypatch.delenv(var, raising=False)
    return library


def _client(monkeypatch: pytest.MonkeyPatch, model: str = MODEL) -> LLMClient:
    monkeypatch.setenv("BRISTLENOSE_LLM_PROVIDER", "any-llm")
    monkeypatch.setenv("BRISTLENOSE_ANYLLM_MODEL", model)
    return LLMClient(load_settings())


# ---------------------------------------------------------------------------
# 1–2. The call composes, and the Claude default is never sent or shown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_run_sends_the_named_model_as_a_schema_dict_with_no_sampling(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Env provider alias + model → settings → client → the wire. The model is
    split at the first colon; the schema goes as a dict (a class would make
    any-llm parse, and lose the content on a failure); neither max_tokens nor
    temperature is sent, because ours are refused by small-output and reasoning
    models."""
    monkeypatch.setenv("MISTRAL_API_KEY", "sk-env")
    fake_anyllm.replies.append(_response(json.dumps({"label": "Checkout", "quotes": ["slow"]})))
    client = _client(monkeypatch)

    assert client.settings.llm_provider == "anyllm"
    result = await client.analyze("sys", "usr", Theme)

    assert result == Theme(label="Checkout", quotes=["slow"])
    (sent,) = fake_anyllm.calls
    assert sent["model"] == "mistral-large-latest"
    assert sent["response_format"]["type"] == "json_schema"
    assert "max_tokens" not in sent
    assert "temperature" not in sent
    assert sent["reasoning_effort"] == "none"
    assert client.tracker.input_tokens == 120


def test_no_model_refuses_before_any_call(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BRISTLENOSE_LLM_PROVIDER", "anyllm")
    with pytest.raises(ValueError, match="provider:model"):
        LLMClient(load_settings())
    assert fake_anyllm.calls == []


def test_the_reported_model_is_the_one_that_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cost lines, logs and the manifest read ``llm_model``. It stayed at
    Claude's default for Azure (verified 23 Oct 2026) and would have for
    any-llm; a stale BRISTLENOSE_LLM_MODEL must not be shown for any-llm."""
    from bristlenose.llm.pricing import estimate_cost

    monkeypatch.setenv("BRISTLENOSE_LLM_PROVIDER", "anyllm")
    monkeypatch.setenv("BRISTLENOSE_ANYLLM_MODEL", MODEL)
    monkeypatch.setenv("BRISTLENOSE_LLM_MODEL", "claude-sonnet-4-6")
    settings = load_settings()
    assert settings.llm_model == MODEL
    assert estimate_cost(settings.llm_model, 1000, 1000) is None

    monkeypatch.delenv("BRISTLENOSE_LLM_MODEL")
    monkeypatch.setenv("BRISTLENOSE_LLM_PROVIDER", "azure")
    monkeypatch.setenv("BRISTLENOSE_AZURE_DEPLOYMENT", "prod-eastus")
    assert load_settings().llm_model == "prod-eastus"


# ---------------------------------------------------------------------------
# 3. Classification
# ---------------------------------------------------------------------------


class _StatusError(Exception):
    def __init__(self, status: int, message: str = "error") -> None:
        super().__init__(message)
        self.status_code = status


class _WrappedError(Exception):
    """any-llm's unified error: the provider's own exception inside."""

    def __init__(self, original: BaseException) -> None:
        super().__init__(str(original))
        self.original_exception = original


class InsufficientFundsError(Exception):  # named as any-llm names it
    pass


@pytest.mark.parametrize(
    ("exc", "kind"),
    [
        (_StatusError(402, "Insufficient credits"), LLMFailureKind.OUT_OF_CREDIT),  # OpenRouter
        (_StatusError(402, "Insufficient Balance"), LLMFailureKind.OUT_OF_CREDIT),  # DeepSeek
        (_WrappedError(_StatusError(429, "too many")), LLMFailureKind.RATE_LIMITED),
        (_WrappedError(_StatusError(401, "unauthorised")), LLMFailureKind.INVALID_KEY),
        (_StatusError(503), LLMFailureKind.SERVER_ERROR),
        (_StatusError(400, "unknown model"), LLMFailureKind.BAD_REQUEST),
        (InsufficientFundsError("no status on the wire"), LLMFailureKind.OUT_OF_CREDIT),
    ],
)
def test_failures_are_read_from_the_providers_own_error_first(
    exc: BaseException, kind: LLMFailureKind
) -> None:
    assert classify_exception("anyllm", exc) is kind


# ---------------------------------------------------------------------------
# 4–5. Truncation, refusal, emptiness, unreadable replies
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_reply_cut_off_at_the_cap_reaches_split_and_retry(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "sk-env")
    fake_anyllm.replies.append(_response('{"label": "Chec', finish_reason="length"))
    with pytest.raises(TruncatedResponseError, match="BRISTLENOSE_LLM_MAX_TOKENS"):
        await _client(monkeypatch).analyze("sys", "usr", Theme)


@pytest.mark.asyncio
async def test_mistrals_model_length_is_truncation_not_unreadable(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    """any-llm 1.27 checks finish_reason against OpenAI's five values, so
    Mistral's "model_length" (its context window, the only cap once we send no
    max_tokens) arrives as a pydantic error on that field. It must still reach
    s09's split-and-retry. The error here has the real one's shape."""
    from typing import Literal

    class Choice(BaseModel):
        finish_reason: Literal["stop", "length", "tool_calls", "content_filter", "function_call"]

    try:
        Choice.model_validate({"finish_reason": "model_length"})
    except ValidationError as exc:
        model_length = exc
    monkeypatch.setenv("MISTRAL_API_KEY", "sk-env")
    fake_anyllm.replies.append(model_length)
    with pytest.raises(TruncatedResponseError):
        await _client(monkeypatch).analyze("sys", "usr", Theme)


@pytest.mark.asyncio
async def test_a_rate_limit_is_retried_honouring_retry_after(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mistral's SDK tries once and the OpenAI SDK three times; a small tier's
    429 would drop the participant. Retried, waiting what the provider asked
    (any-llm keeps the header as a string)."""
    import asyncio as _asyncio

    waits: list[float] = []

    async def no_sleep(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(_asyncio, "sleep", no_sleep)
    limited = _StatusError(429, "rate limited")
    limited.retry_after = "7"  # type: ignore[attr-defined]
    monkeypatch.setenv("MISTRAL_API_KEY", "sk-env")
    fake_anyllm.replies += [limited, _response('{"label": "a", "quotes": []}')]
    assert (await _client(monkeypatch).analyze("s", "u", Theme)).label == "a"
    assert waits == [7.0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reply", "match"),
    [
        (_response(None, finish_reason="content_filter"), "declined"),
        (_response(None, refusal="I can't help with that"), "declined"),
        (_response(""), "Empty response"),
    ],
)
async def test_a_refusal_or_an_empty_reply_fails_loudly(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch, reply: Any, match: str
) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "sk-env")
    fake_anyllm.replies.append(reply)
    with pytest.raises(RuntimeError, match=match):
        await _client(monkeypatch).analyze("sys", "usr", Theme)


@pytest.mark.asyncio
async def test_a_reply_any_llm_cannot_read_never_quotes_it(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    """1.27 validates the provider's reply against OpenAI's shape and rejects a
    finish reason outside OpenAI's five. pydantic's message quotes the reply,
    which quotes the transcript; the error we raise must not."""
    participant_words = "my GP said the wound was infected"
    try:
        Theme.model_validate({"label": "x", "quotes": participant_words})
    except ValidationError as exc:
        unreadable = exc
    assert participant_words in str(unreadable)  # the hazard is real
    monkeypatch.setenv("MISTRAL_API_KEY", "sk-env")
    fake_anyllm.replies.append(unreadable)
    with pytest.raises(RuntimeError, match="couldn't read") as raised:
        await _client(monkeypatch).analyze("sys", "usr", Theme)
    assert participant_words not in str(raised.value)


@pytest.mark.asyncio
async def test_fenced_json_is_read_and_a_refused_schema_falls_back_once(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DeepSeek, for one, takes only ``json_object``: fall back, and remember."""
    monkeypatch.setenv("MISTRAL_API_KEY", "sk-env")
    fake_anyllm.replies += [
        _StatusError(400, "response_format json_schema is not supported"),
        _response('```json\n{"label": "a", "quotes": []}\n```'),
        _response('{"label": "b", "quotes": []}'),
    ]
    client = _client(monkeypatch)
    assert (await client.analyze("s", "u", Theme)).label == "a"
    assert (await client.analyze("s", "u", Theme)).label == "b"
    formats = [call["response_format"]["type"] for call in fake_anyllm.calls]
    assert formats == ["json_schema", "json_object", "json_object"]


# ---------------------------------------------------------------------------
# 6. Telemetry rows survive, unpriced
# ---------------------------------------------------------------------------


def test_telemetry_keys_rows_on_the_requested_model_and_prices_none(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bristlenose.llm import telemetry
    from bristlenose.llm.cohort_normalise import normalise_model

    assert normalise_model("anyllm", "Mistral:Mistral-Large-Latest") == (
        "mistral:mistral-large-latest", "0",
    )
    monkeypatch.setattr(
        telemetry, "_actual_cost",
        lambda *a, **k: pytest.fail("an any-llm call must not be priced"),
    )
    run_dir = tmp_path / ".bristlenose"
    tokens = telemetry.set_run_context("run-anyllm", run_dir)
    try:
        with telemetry.stage("s09_quote_extraction"):
            telemetry.record_call(
                provider="anyllm", request_model=MODEL, response_model="mistral-large-2411",
                input_chars=10, elapsed_ms=5, outcome="ok", price_table_version="t",
                input_tokens=120, output_tokens=30,
            )
    finally:
        telemetry.reset_run_context(tokens)
    (row,) = list(telemetry.iter_rows(run_dir))
    assert row["outcome"] == "ok"
    assert row.get("cost_usd_actual_estimate") is None


# ---------------------------------------------------------------------------
# 7. The readiness probe: every state, offline
# ---------------------------------------------------------------------------


def _ready(model: str, **kw: Any) -> anyllm.Readiness:
    return anyllm.readiness(BristlenoseSettings(anyllm_model=model), **kw)


def test_readiness_names_every_state(fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _ready("").status == "no-model"
    assert _ready("mistral-large").status == "bad-model"
    assert _ready("anthropic:claude-sonnet-4-6").status == "native"
    assert _ready("ollama:llama3.2:3b").status == "native"  # Ollama is built in
    unknown = _ready("mistrall:large")
    assert (unknown.status, unknown.suggestion) == ("unknown-provider", "mistral")
    assert _ready("cohere:command-r").status == "sdk-missing"

    no_key = _ready(MODEL)
    assert (no_key.status, no_key.env_var) == ("no-key", "MISTRAL_API_KEY")

    monkeypatch.setattr(anyllm, "stored_key", lambda inner: "sk-stored")
    stored = _ready(MODEL)
    assert stored.ready and stored.api_key == "sk-stored"

    monkeypatch.setenv("MISTRAL_API_KEY", "sk-env")
    from_env = _ready(MODEL)
    assert from_env.ready and from_env.api_key is None  # any-llm reads it itself
    assert from_env.key_source == "environment"

    # A provider that needs no key: its class names the variable "None", which
    # a variable lookup would have refused.
    assert _ready("llamacpp:llama3.2:3b").ready


def test_readiness_without_the_library(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing on 3.11+ is "add the extra"; on 3.10 the extra can't install
    (any-llm needs 3.11), so the answer is the Python. Both pinned, whatever
    interpreter runs the suite: this test was red on the 3.10 CI cells."""
    monkeypatch.setattr(anyllm, "install_state", lambda: "not-installed")
    monkeypatch.setattr(sys, "version_info", (3, 12, 0))
    assert _ready(MODEL).status == "not-installed"
    monkeypatch.setattr(sys, "version_info", (3, 10, 0))
    assert _ready(MODEL).status == "old-python"
    monkeypatch.setattr(anyllm, "install_state", lambda: "ImportError: cannot import name 'x'")
    broken = _ready(MODEL)
    assert broken.status == "broken" and "cannot import" in broken.detail


def test_every_state_but_ready_says_what_to_do(fake_anyllm: _FakeLibrary) -> None:
    for status in (
        "not-installed", "broken", "no-model", "bad-model", "native",
        "unknown-provider", "sdk-missing", "no-key",
    ):
        lines = anyllm.explain(
            anyllm.Readiness(status, inner="anthropic" if status == "native" else "mistral")
        )
        assert lines, status


# ---------------------------------------------------------------------------
# 8. The server's three key checks accept a ready any-llm, refuse one that isn't
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ready", [True, False])
def test_server_sites_ask_readiness(monkeypatch: pytest.MonkeyPatch, ready: bool) -> None:
    from bristlenose.server import chat_lens, elaboration
    from bristlenose.server.routes import autocode

    status = "ready" if ready else "no-key"
    monkeypatch.setattr(
        anyllm, "readiness", lambda settings, **kw: anyllm.Readiness(status, inner="mistral")
    )
    settings = BristlenoseSettings(llm_provider="anyllm", anyllm_model=MODEL)
    assert autocode._has_api_key(settings) is ready
    assert elaboration._has_api_key(settings) is ready
    assert chat_lens.has_usable_provider(settings)[0] is ready


# ---------------------------------------------------------------------------
# 9. Explicit only
# ---------------------------------------------------------------------------


def test_a_provider_key_alone_never_chooses_any_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    from bristlenose.config import get_provider_resolution

    monkeypatch.setenv("MISTRAL_API_KEY", "sk-env")
    monkeypatch.setenv("BRISTLENOSE_ANYLLM_MODEL", MODEL)
    settings = load_settings()
    assert settings.llm_provider != "anyllm"
    resolution = get_provider_resolution()
    assert resolution is not None and "anyllm" not in resolution.configured


# ---------------------------------------------------------------------------
# 10. Install hints name a command that works here
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("prefix", "extra", "inject"),
    [
        (("home", "u", ".venv"), 'pip install "bristlenose[any-llm]"',
         'pip install "any-llm-sdk[cohere]==1.27.0"'),
        (("home", "u", ".local", "pipx", "venvs", "bristlenose"),
         'pipx install --force "bristlenose[any-llm]"',
         'pipx inject bristlenose "any-llm-sdk[cohere]==1.27.0"'),
        (("home", "u", ".local", "share", "uv", "tools", "bristlenose"),
         'uv tool install --force "bristlenose[any-llm]"',
         'uv tool install --force "bristlenose[any-llm]" --with "any-llm-sdk[cohere]==1.27.0"'),
        (("opt", "homebrew", "Cellar", "bristlenose", "0.43.0", "libexec"),
         '$(brew --prefix bristlenose)/libexec/bin/pip install "bristlenose[any-llm]==' + __version__ + '"',
         '$(brew --prefix bristlenose)/libexec/bin/pip install "any-llm-sdk[cohere]==1.27.0"'),
    ],
)
def test_install_hints_follow_the_channel(
    monkeypatch: pytest.MonkeyPatch, prefix: tuple[str, ...], extra: str, inject: str
) -> None:
    from pathlib import Path

    from bristlenose.utils import install_channel

    monkeypatch.setattr(sys, "prefix", str(Path("/", *prefix)))
    monkeypatch.setattr(install_channel, "installed_extras", list)
    monkeypatch.setattr(anyllm, "installed_version", lambda: "1.27.0")
    assert anyllm.install_hint() == extra
    assert anyllm.inject_hint("cohere") == inject


# ---------------------------------------------------------------------------
# CLI: `use provider:model` switches with no call, or changes nothing
# ---------------------------------------------------------------------------


def test_use_a_model_string(fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    from bristlenose.cli import app
    from bristlenose.credentials import read_user_config_var

    runner = CliRunner()
    refused = runner.invoke(app, ["use", MODEL])
    assert refused.exit_code == 1
    assert "MISTRAL_API_KEY" in refused.output
    assert read_user_config_var("BRISTLENOSE_ANYLLM_MODEL") is None

    monkeypatch.setenv("MISTRAL_API_KEY", "sk-env")
    switched = runner.invoke(app, ["use", MODEL])
    assert switched.exit_code == 0, switched.output
    assert read_user_config_var("BRISTLENOSE_ANYLLM_MODEL") == MODEL
    assert read_user_config_var("BRISTLENOSE_LLM_PROVIDER") == "anyllm"
    assert fake_anyllm.calls == []  # no network, like `use claude`

    native = runner.invoke(app, ["use", "anthropic:claude-sonnet-4-6"])
    assert native.exit_code == 1 and "configure claude" in native.output


@pytest.mark.asyncio
async def test_other_errors_are_not_mistaken_for_a_refused_schema(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a refusal that names the response format falls back; a bad model
    id is a real failure and must surface, not be retried in another shape."""
    monkeypatch.setenv("MISTRAL_API_KEY", "sk-env")
    fake_anyllm.replies += [_StatusError(400, "unknown model mistral-larg"), _response("{}")]
    with pytest.raises(_StatusError):
        await _client(monkeypatch).analyze("s", "u", Theme)
    assert len(fake_anyllm.calls) == 1


def test_an_install_hint_keeps_the_extras_already_there(monkeypatch: pytest.MonkeyPatch) -> None:
    """pipx/uv --force rebuild from what the command names: naming only one
    extra would quietly remove the voice pass."""
    from pathlib import Path

    from bristlenose.utils import install_channel

    monkeypatch.setattr(sys, "prefix", str(Path("/home/u/.local/pipx/venvs/bristlenose")))
    monkeypatch.setattr(install_channel, "installed_extras", lambda: ["voice"])
    assert anyllm.install_hint() == 'pipx install --force "bristlenose[any-llm,voice]"'


# ---------------------------------------------------------------------------
# Review pass 2 (23 Oct 2026): preflight, configure, doctor, destination
# ---------------------------------------------------------------------------


def test_the_preflight_sends_the_runs_request_and_falls_back_like_the_run(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The check `configure` and `run` make before anything else: the run's
    shape (a json_schema dict, no sampling), and the run's fallback, or a
    provider that takes only json_object (DeepSeek) could never start."""
    from bristlenose.preflight.api_key import _validate_anyllm

    monkeypatch.setenv("MISTRAL_API_KEY", "sk-env")
    fake_anyllm.replies += [
        _StatusError(400, "response_format json_schema is not supported"),
        _response("{}"),
    ]
    assert _validate_anyllm("", MODEL).ok
    first, second = fake_anyllm.calls
    assert first["response_format"]["type"] == "json_schema"
    assert "max_tokens" not in first and "temperature" not in first
    assert second["response_format"] == {"type": "json_object"}
    assert any("JSON" in m["content"] for m in second["messages"])


def test_the_preflight_drops_reasoning_off_where_the_model_always_thinks(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gemini 2.5 Pro and GPT-5 mini through OpenRouter refuse "none"; the run
    then asks with the model's default, so the check must too, or `configure`
    turns away a model that would run. Both fallbacks compose."""
    from bristlenose.preflight.api_key import _validate_anyllm

    monkeypatch.setenv("MISTRAL_API_KEY", "sk-env")
    fake_anyllm.always_thinks = True
    fake_anyllm.replies += [
        _StatusError(400, "response_format json_schema is not supported"),
        _response("{}"),
    ]
    assert _validate_anyllm("", MODEL).ok
    sent = [(c["response_format"]["type"], c.get("reasoning_effort")) for c in fake_anyllm.calls]
    assert sent == [
        ("json_schema", "none"), ("json_schema", None), ("json_object", None),
    ]


class APIConnectionError(Exception):  # named as openai's is
    pass


@pytest.mark.parametrize(
    ("failure", "bucket"),
    [
        (_StatusError(402, "Insufficient credits"), "billing_empty"),
        (_StatusError(401, "bad key"), "invalid_key"),
        (_StatusError(429, "slow down"), "rate_limit"),
        (_WrappedError(APIConnectionError("Connection error.")), "network"),
    ],
)
def test_the_preflight_buckets_what_the_provider_says(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch,
    failure: BaseException, bucket: str,
) -> None:
    from bristlenose.preflight.api_key import _validate_anyllm

    monkeypatch.setenv("MISTRAL_API_KEY", "sk-env")
    fake_anyllm.replies.append(failure)
    result = _validate_anyllm("", MODEL)
    assert (result.ok, result.error_class) == (False, bucket)


def test_a_run_with_any_llm_reaches_its_preflight(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Dropping anyllm from the preflight's provider set would skip the check
    silently, and a bad key would surface at stage 8 (R104)."""
    import io

    from rich.console import Console

    from bristlenose.preflight import api_key as preflight

    seen: list[tuple[str, str]] = []

    def validator(key: str, model: str, *, params: Any = None) -> Any:
        seen.append((key, model))
        return preflight.ValidationResult(ok=True)

    monkeypatch.setattr(preflight, "_validate_anyllm", validator)
    monkeypatch.setattr(preflight, "state_path", lambda: tmp_path / "state.json")
    monkeypatch.delenv("BRISTLENOSE_SKIP_PREFLIGHT", raising=False)  # set suite-wide
    monkeypatch.setenv("MISTRAL_API_KEY", "sk-env")
    settings = BristlenoseSettings(llm_provider="anyllm", anyllm_model=MODEL)
    preflight.preflight_api_key(settings=settings, console=Console(file=io.StringIO()))
    assert seen == [("", MODEL)]


def test_configure_checks_stores_and_switches(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    from typer.testing import CliRunner

    from bristlenose import credentials
    from bristlenose.cli import app
    from bristlenose.credentials import FileCredentialStore, read_user_config_var
    from bristlenose.preflight import api_key as preflight

    store = FileCredentialStore(tmp_path / "keys.env")
    monkeypatch.setattr(credentials, "get_credential_store", lambda: store)
    verdict = {"result": preflight.ValidationResult(ok=True)}
    monkeypatch.setattr(preflight, "_validate_anyllm", lambda *a, **k: verdict["result"])
    monkeypatch.setenv("BRISTLENOSE_ANYLLM_MODEL", MODEL)
    runner = CliRunner()

    ok = runner.invoke(app, ["configure", "any-llm", "--key", "sk-secret-123"])
    assert ok.exit_code == 0, ok.output
    assert store.get(anyllm.credential_key("mistral")) == "sk-secret-123"
    assert read_user_config_var("BRISTLENOSE_LLM_PROVIDER") == "anyllm"
    assert "sk-secret-123" not in ok.output

    store.delete(anyllm.credential_key("mistral"))
    verdict["result"] = preflight.ValidationResult(ok=False, error_class="invalid_key")
    refused = runner.invoke(app, ["configure", "any-llm", "--key", "sk-bad"])
    assert refused.exit_code == 1
    assert store.get(anyllm.credential_key("mistral")) is None

    verdict["result"] = preflight.ValidationResult(ok=False, error_class="network")
    offline = runner.invoke(app, ["configure", "any-llm", "--key", "sk-offline"])
    assert offline.exit_code == 0, offline.output
    assert store.get(anyllm.credential_key("mistral")) == "sk-offline"


def test_a_rejected_environment_key_names_its_variable(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The run's banner sends a rejected key here; for a key from the shell the
    only fix is where it is set, so say which variable — never loop."""
    from typer.testing import CliRunner

    from bristlenose.cli import app
    from bristlenose.preflight import api_key as preflight

    monkeypatch.setattr(
        preflight, "_validate_anyllm",
        lambda *a, **k: preflight.ValidationResult(ok=False, error_class="invalid_key"),
    )
    monkeypatch.setenv("BRISTLENOSE_ANYLLM_MODEL", MODEL)
    monkeypatch.setenv("MISTRAL_API_KEY", "sk-revoked")
    result = CliRunner().invoke(app, ["configure", "any-llm"])
    assert result.exit_code == 1
    assert "MISTRAL_API_KEY is set in your environment and was rejected" in result.output


def test_a_key_pasted_as_the_model_is_caught(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-abc")
    caught = _ready("openrouter:sk-or-v1-abc")
    assert caught.status == "key-as-model"
    assert "sk-or-v1-abc" not in " ".join(anyllm.explain(caught))


def test_a_given_key_is_the_one_checked_and_an_env_key_is_named(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "sk-old")
    given = anyllm.readiness_for_model(MODEL, api_key="sk-new")
    assert (given.api_key, given.key_source, given.shadowed_by) == (
        "sk-new", "given", "MISTRAL_API_KEY",
    )


def test_a_provider_that_cannot_be_built_is_shown_not_raised(
    fake_anyllm: _FakeLibrary,
) -> None:
    """Callers include doctor and the server's key checks: an escaping
    exception aborts doctor and turns the chat lens into a 500."""
    broken = _ready("vertexai:gemini-pro")
    assert broken.status == "broken" and "credentials were not found" in broken.detail


def test_the_destination_is_where_the_request_goes(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A *_API_BASE variable left by another tool sends the key and the
    transcripts elsewhere; the line that names the destination must say so."""
    assert anyllm.destination("openrouter") == "OpenRouter (openrouter.ai)"
    assert anyllm.destination("mistral") == "Mistral"
    monkeypatch.setenv("OPENROUTER_API_BASE", "http://proxy.example:8080/v1")
    assert anyllm.destination("openrouter") == (
        "OpenRouter (proxy.example, from OPENROUTER_API_BASE)"
    )
    assert anyllm.insecure_base("openrouter")
    monkeypatch.setenv("OPENROUTER_API_BASE", "http://127.0.0.1:8080/v1")
    assert not anyllm.insecure_base("openrouter")


def test_a_connection_failure_is_found_down_the_chain() -> None:
    class ConnectError(Exception):  # httpx2's, which is not httpx's
        pass

    inner = RuntimeError("provider error")
    inner.__cause__ = ConnectError("All connection attempts failed")
    assert anyllm.is_network_error(_WrappedError(inner))
    assert not anyllm.is_network_error(_StatusError(400))


def test_doctor_rows(fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch) -> None:
    from bristlenose.doctor import CheckStatus, check_anyllm, check_anyllm_key

    missing_sdk = check_anyllm_key(
        BristlenoseSettings(llm_provider="anyllm", anyllm_model="cohere:command-r")
    )
    assert (missing_sdk.status, missing_sdk.fix_key) == (CheckStatus.FAIL, "anyllm_not_ready")
    monkeypatch.setattr(anyllm, "install_state", lambda: "not-installed")
    assert check_anyllm().status is CheckStatus.SKIP  # optional, so never a FAIL


@pytest.mark.parametrize("gate", ["desktop", "explicit-model"])
def test_the_azure_model_copy_keeps_its_gates(monkeypatch: pytest.MonkeyPatch, gate: str) -> None:
    """CLI only (desktop Azure runs don't move in the reliability phase), and an
    explicit model always wins."""
    from bristlenose import config

    monkeypatch.setenv("BRISTLENOSE_LLM_PROVIDER", "azure")
    monkeypatch.setenv("BRISTLENOSE_AZURE_DEPLOYMENT", "prod-eastus")
    if gate == "desktop":
        monkeypatch.setenv(config._HOSTED_BY_DESKTOP_ENV, "1")
        expected = BristlenoseSettings.model_fields["llm_model"].default
    else:
        monkeypatch.setenv("BRISTLENOSE_LLM_MODEL", "gpt-4o")
        expected = "gpt-4o"
    assert load_settings().llm_model == expected


# ---------------------------------------------------------------------------
# The real library, where installed: the fake's assumptions, and no telemetry
# ---------------------------------------------------------------------------


def test_the_real_library_has_the_shape_the_fake_assumes() -> None:
    """Skipped where any-llm isn't installed (CI); runs on a dev machine and in
    the release walk. The fakes above stand in for exactly these."""
    import importlib.util
    import inspect
    import subprocess

    real = pytest.importorskip("any_llm")
    # Every fake goes in through monkeypatch, so a fake here is a leak from
    # another test: fail on it rather than skip and read as a pass.
    assert hasattr(real, "__file__"), "a fake any_llm leaked into sys.modules"
    from any_llm.exceptions import MissingApiKeyError

    assert "api_key" in inspect.signature(real.AnyLLM.create).parameters
    assert "env_var_name" in inspect.signature(MissingApiKeyError.__init__).parameters
    for inner in ("mistral", "openrouter", "deepseek"):
        cls = real.AnyLLM.get_provider_class(inner)
        assert cls.MISSING_PACKAGES_ERROR is None, inner  # the extra carries them
        assert hasattr(cls, "ENV_API_BASE_NAME"), inner

    # Nothing that reports anywhere came in with the extra.
    for name in ("opentelemetry.sdk", "any_llm_platform_client"):
        assert importlib.util.find_spec(name) is None, f"{name} is installed"

    # And importing it makes no network call.
    probe = (
        "import socket\n"
        "def _no(*a, **k): raise OSError('network at import')\n"
        "socket.socket.connect = _no\n"
        "socket.create_connection = _no\n"
        "import any_llm, any_llm.providers.mistral, any_llm.providers.openrouter\n"
    )
    done = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr[-500:]


def test_recovery_copy_names_the_provider_and_keeps_its_words_short() -> None:
    """Found with real fake-key calls (23 Oct 2026): a Mistral 401 read "If
    this looks like a credit-balance issue, top up…", and a gateway pointed at
    a web page printed the whole page."""
    from bristlenose.llm.billing_hints import recovery_message

    rejected = recovery_message(
        "anyllm", "invalid_key", raw_message="Status 401 Invalid API Key",
        provider_display="Mistral",
    )
    assert rejected.startswith("Mistral rejected the API key.")
    assert "credit-balance" not in rejected
    page = recovery_message("anyllm", "", raw_message="<html>" + "x" * 5000, provider_display="OpenRouter")
    assert len(page) < 500 and page.startswith("OpenRouter refused the request.")


def test_a_dotenv_that_overrides_the_choice_is_named(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """`use` writes the user-level config; a project .env is read after it and
    wins, so "now your provider" would be announced while runs from that folder
    still used Claude (found by the any-llm walks, 23 Oct 2026)."""
    from pathlib import Path

    from typer.testing import CliRunner

    from bristlenose import config
    from bristlenose.cli import app

    project_env = tmp_path / ".env"
    project_env.write_text("BRISTLENOSE_LLM_PROVIDER=anthropic\n")
    monkeypatch.setattr(config, "_find_env_files", lambda: [Path(project_env)])
    monkeypatch.delenv("BRISTLENOSE_LLM_PROVIDER", raising=False)
    result = CliRunner().invoke(app, ["use", "local"])
    assert result.exit_code == 0, result.output
    assert "BRISTLENOSE_LLM_PROVIDER=anthropic" in result.output
    assert "Remove the line" in result.output


@pytest.mark.asyncio
async def test_a_reply_that_misses_the_schema_is_asked_for_again_once(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Found on Mistral Small (23 Oct 2026): one quote missing one field threw
    away that session's quotes. Asked again once, as the Ollama route retries;
    a second miss still fails loudly."""
    monkeypatch.setenv("MISTRAL_API_KEY", "sk-env")
    missing_field = _response('{"label": "a"}')  # no quotes
    fake_anyllm.replies += [missing_field, _response('{"label": "b", "quotes": []}')]
    client = _client(monkeypatch)
    assert (await client.analyze("s", "u", Theme)).label == "b"
    assert len(fake_anyllm.calls) == 2

    fake_anyllm.replies += [missing_field, missing_field]
    with pytest.raises(ValidationError):
        await client.analyze("s", "u", Theme)
    assert len(fake_anyllm.calls) == 4


@pytest.mark.asyncio
async def test_a_schema_retry_is_its_own_telemetry_row(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Found by the Mistral walk: the retry's row said retry_count=0 and timed
    both attempts together."""
    from bristlenose.llm import telemetry

    monkeypatch.setenv("MISTRAL_API_KEY", "sk-env")
    fake_anyllm.replies += [_response('{"label": "a"}'), _response('{"label": "b", "quotes": []}')]
    client = _client(monkeypatch)
    run_dir = tmp_path / ".bristlenose"
    tokens = telemetry.set_run_context("run-retry", run_dir)
    try:
        with telemetry.stage("s09_quote_extraction"):
            await client.analyze("s", "u", Theme)
    finally:
        telemetry.reset_run_context(tokens)
    rows = list(telemetry.iter_rows(run_dir))
    assert [(r["outcome"], r["retry_count"]) for r in rows] == [("error", 0), ("ok", 1)]


# ---------------------------------------------------------------------------
# Thinking (23 Oct 2026, the OpenRouter walk): a hybrid model reached through a
# gateway thinks by default, billed as output; Qwen 3.8 Flash ran every s09 pass
# past its deadline. Each call asks for none; a model that refuses is asked again
# with its own default, once per client.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_model_that_always_thinks_is_asked_again_with_its_default_and_remembered(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "sk-env")
    fake_anyllm.always_thinks = True
    fake_anyllm.replies += [
        _response('{"label": "a", "quotes": []}'),
        _response('{"label": "b", "quotes": []}'),
    ]
    client = _client(monkeypatch)
    assert (await client.analyze("s", "u", Theme)).label == "a"
    assert (await client.analyze("s", "u", Theme)).label == "b"
    assert [c.get("reasoning_effort") for c in fake_anyllm.calls] == ["none", None, None]


@pytest.mark.asyncio
async def test_a_400_that_does_not_name_reasoning_is_not_a_reason_to_think(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bad model id must surface, not be resent with thinking switched on."""
    monkeypatch.setenv("MISTRAL_API_KEY", "sk-env")
    fake_anyllm.replies += [_StatusError(400, "unknown model mistral-larg"), _response("{}")]
    with pytest.raises(_StatusError):
        await _client(monkeypatch).analyze("s", "u", Theme)
    assert [c.get("reasoning_effort") for c in fake_anyllm.calls] == ["none"]


def test_the_real_library_maps_none_to_thinking_off_where_we_measured_it() -> None:
    """What the fix rests on, asked of the installed library (skipped in CI):
    OpenRouter forwards "none" as a top-level ``reasoning_effort``, which its
    API reads as thinking off (measured 23 Oct 2026); DeepSeek and Mistral read
    it as their own off, never as the "high" Mistral makes of "low"."""
    real = pytest.importorskip("any_llm")
    # Every fake goes in through monkeypatch, so a fake here is a leak from
    # another test: fail on it rather than skip and read as a pass.
    assert hasattr(real, "__file__"), "a fake any_llm leaked into sys.modules"
    from any_llm.providers.deepseek.deepseek import DeepseekProvider
    from any_llm.providers.mistral.mistral import MistralProvider
    from any_llm.providers.openrouter.openrouter import OpenrouterProvider
    from any_llm.types.completion import CompletionParams

    def params(model: str) -> CompletionParams:
        return CompletionParams(
            model_id=model, messages=[{"role": "user", "content": "."}],
            reasoning_effort="none",
        )

    openrouter = OpenrouterProvider._convert_completion_params(params("qwen/qwen3.8-flash"))
    assert openrouter.get("reasoning_effort") == "none"
    assert "reasoning" not in openrouter.get("extra_body", {})
    deepseek = DeepseekProvider._convert_completion_params(params("deepseek-flash"))
    assert deepseek["extra_body"]["thinking"] == {"type": "disabled"}
    mistral = MistralProvider._convert_completion_params(params("mistral-large-latest"))
    assert "reasoning_effort" not in mistral


def _one_turn_session() -> Any:
    from datetime import datetime, timezone

    from bristlenose.models import PiiCleanTranscript, SpeakerRole, TranscriptSegment

    segment = TranscriptSegment(
        start_time=0.0, end_time=30.0, text="I kept going back to it", segment_index=0,
        speaker_role=SpeakerRole.PARTICIPANT, speaker_code="p1", source="whisper",
    )
    return PiiCleanTranscript(
        participant_id="p1", session_id="s1", source_file="s1.mp4",
        session_date=datetime(2026, 1, 10, tzinfo=timezone.utc),
        duration_seconds=30, segments=[segment],
    )


@pytest.mark.asyncio
async def test_a_model_still_writing_at_the_deadline_is_not_called_the_network(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The provider answered and the model was still thinking: "check your
    connection" would send the researcher the wrong way. The built-in
    providers keep NETWORK (tests/test_quote_extraction_timeout.py)."""
    from bristlenose.events import CauseCategoryEnum
    from bristlenose.models import SessionTopicMap
    from bristlenose.stages import s09_quote_extraction as s09

    monkeypatch.setenv("MISTRAL_API_KEY", "sk-env")
    monkeypatch.setattr(s09, "_PASS_DEADLINE_S", 0.05)
    fake_anyllm.replies.append(_STILL_THINKING)
    topic_map = SessionTopicMap(participant_id="p1", session_id="s1", boundaries=[])

    quotes, outcome = await s09.extract_quotes(
        [_one_turn_session()], [topic_map], _client(monkeypatch)
    )

    assert quotes == [] and len(fake_anyllm.calls) == 1
    (failure,) = outcome.failed
    assert failure.cause.category == CauseCategoryEnum.UNKNOWN
    # A real network failure through any-llm is still one.
    from bristlenose.run_lifecycle import _build_cause

    network = _build_cause(TimeoutError("read timeout"), stage="quote_extraction", provider="anyllm")
    assert network.category == CauseCategoryEnum.NETWORK


def test_an_unexplained_give_up_names_the_model_and_how_to_change_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Measured on Nemotron through OpenRouter: "All quote extraction calls
    failed." and nothing else, after half an hour."""
    from bristlenose import cli
    from bristlenose.events import Cause, CauseCategoryEnum

    monkeypatch.setenv("BRISTLENOSE_LLM_PROVIDER", "any-llm")
    monkeypatch.setenv("BRISTLENOSE_ANYLLM_MODEL", "openrouter:nvidia/nemotron-3.5-super-vl:free")
    settings = load_settings()
    lines: list[str] = []
    monkeypatch.setattr(cli.console, "print", lambda *a, **k: lines.append(" ".join(map(str, a))))
    monkeypatch.setattr(cli, "_say", lambda kind, text: lines.append(text))

    def banner(category: CauseCategoryEnum) -> str:
        lines.clear()
        cause = Cause(category=category, message="All quote extraction calls failed.",
                      provider="anyllm", stage="quote_extraction")
        cli._print_pipeline_failure(cause, tmp_path / "interviews", settings)
        return "\n".join(lines)

    unexplained = banner(CauseCategoryEnum.UNKNOWN)
    assert "All quote extraction calls failed." in unexplained
    assert "openrouter:nvidia/nemotron-3.5-super-vl:free" in unexplained
    assert "bristlenose use provider:model" in unexplained
    # A failure with its own remedy keeps it, and no model advice.
    assert "bristlenose use" not in banner(CauseCategoryEnum.NETWORK)


# ---------------------------------------------------------------------------
# The model's host behind a gateway (OpenRouter walk, 23 Oct 2026)
# ---------------------------------------------------------------------------
#
# OpenRouter passes the request to the model's host and, when the host fails,
# answers "Provider returned error" naming it in ``metadata``. The bodies below
# are the walk's, verbatim but for the ids. The SDK exception is the real
# openai one (the openai client unwraps ``{"error": …}`` into ``body``); the
# any-llm error around it is a fake shaped like 1.27's ``convert_exception``.


class _AnyLLMError(Exception):
    """any-llm's unified error: its own message, the status, the SDK's error."""

    def __init__(self, original: BaseException, status: int) -> None:
        super().__init__(f"[openrouter] {original}")
        self.original_exception = original
        self.status_code = status
        self.retry_after = None


class ModelNotFoundError(_AnyLLMError):  # named as any-llm names it (preflight reads it)
    pass


def _openrouter(status: int, error: dict[str, Any]) -> BaseException:
    import httpx
    import openai

    sdk_class = {
        401: openai.AuthenticationError, 404: openai.NotFoundError,
        429: openai.RateLimitError, 502: openai.InternalServerError,
    }[status]
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    response = httpx.Response(status, json={"error": error}, request=request)
    sdk = sdk_class(f"Error code: {status} - {{'error': {error!r}}}", response=response, body=error)
    return (ModelNotFoundError if status == 404 else _AnyLLMError)(sdk, status)


_HOST_404 = {  # free Nemotron: the id is listed, NVIDIA's endpoint is not there
    "message": "Provider returned error", "code": 404,
    "metadata": {
        "raw": '{"status":404,"title":"Not Found","detail":"Function f: Not found for account a"}',
        "provider_name": "Nvidia",
    },
}
_HOST_429 = {  # free Gemma: the host is limiting, not this key
    "message": "Provider returned error", "code": 429,
    "metadata": {"raw": "google/gemma-4-31b-it:free is temporarily rate-limited upstream.",
                 "provider_name": "Google AI Studio"},
}
_SHARED_POOL_429 = {  # Mistral Large: OpenRouter's shared pool at Mistral is full
    "message": "Provider returned error", "code": 429,
    "metadata": {
        "raw": "mistralai/mistral-large-2512 is temporarily rate-limited upstream. Please retry "
               "shortly, or add your own key to accumulate your rate limits",
        "provider_name": "Mistral", "is_byok": False,
        "limit_source": "upstream_provider_shared_pool",
    },
}
_UNNAMED_HOST = {"message": "Provider returned error", "code": 502}
_BAD_KEY = {"message": "User not found.", "code": 401}
_OWN_LIMIT = {"message": "Rate limit exceeded: free-models-per-day. ", "code": 429}
_UNKNOWN_MODEL = {"message": "No endpoints found for nvidia/not-a-model.", "code": 404}
_BARE_404 = {"message": "Not Found", "code": 404}
_HOST_MODEL_GONE = {  # the host itself no longer serves the id OpenRouter routed to it
    "message": "Provider returned error", "code": 404,
    "metadata": {"raw": "The model `mistral-large-2407` does not exist.",
                 "provider_name": "Mistral"},
}

_OPENROUTER_CASES = [
    # (status, body, preflight bucket, host)
    (404, _HOST_404, "upstream_failed", "Nvidia"),
    (429, _HOST_429, "upstream_busy", "Google AI Studio"),
    (429, _SHARED_POOL_429, "upstream_busy", "Mistral"),
    (502, _UNNAMED_HOST, "upstream_failed", ""),
    # OpenRouter's own answers keep their wording: the key, its limit, the id.
    (401, _BAD_KEY, "invalid_key", None),
    (429, _OWN_LIMIT, "rate_limit", None),
    (404, _UNKNOWN_MODEL, "model_unavailable", None),
]
OPENROUTER_MODEL = "openrouter:mistralai/mistral-large-2512"


@pytest.mark.parametrize(("status", "body", "bucket", "host"), _OPENROUTER_CASES)
def test_the_preflight_tells_the_models_host_from_the_key(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch,
    status: int, body: dict[str, Any], bucket: str, host: str | None,
) -> None:
    from bristlenose.preflight.api_key import _validate_anyllm

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-env")
    fake_anyllm.replies.append(_openrouter(status, body))
    result = _validate_anyllm("", OPENROUTER_MODEL)
    assert (result.ok, result.error_class, result.host) == (False, bucket, host)


@pytest.mark.parametrize(
    ("bucket", "host", "says"),
    [
        ("upstream_busy", "Mistral", "Mistral, reached through OpenRouter, is busy. Your key works."),
        ("upstream_failed", "Nvidia",
         "Nvidia, reached through OpenRouter, couldn't serve that model. Your key works."),
        ("upstream_busy", "", "The model's host, reached through OpenRouter, is busy."),
    ],
)
def test_a_host_failure_is_worded_about_the_host_not_the_key(
    bucket: str, host: str, says: str
) -> None:
    from bristlenose.llm.billing_hints import recovery_message

    text = recovery_message(
        "anyllm", bucket, raw_message="Provider returned error",
        provider_display="OpenRouter", host=host,
    )
    assert text.startswith(says)
    assert "this key" not in text and "another model" in text


def test_a_host_name_from_the_gateway_is_printable_and_escaped() -> None:
    from bristlenose.llm.billing_hints import recovery_message

    error = dict(_HOST_429, metadata={"provider_name": "[link=https://x.test]Evil[/link]\x1b[31m" + "x" * 80})
    host = anyllm.upstream(_openrouter(429, error))
    assert host is not None and "\x1b" not in host[0] and len(host[0]) <= 40
    text = recovery_message("anyllm", "upstream_busy", provider_display="OpenRouter", host=host[0])
    assert "\\[link=" in text  # Rich would otherwise render a hyperlink


def test_configure_keeps_a_key_the_gateway_accepted_when_the_host_is_busy(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """The walk got "✗ Not valid — OpenRouter is rate-limiting this key" for a
    good key, and nothing stored. The key passed; only the model's host refused."""
    from typer.testing import CliRunner

    from bristlenose import credentials
    from bristlenose.cli import app
    from bristlenose.credentials import FileCredentialStore

    store = FileCredentialStore(tmp_path / "keys.env")
    monkeypatch.setattr(credentials, "get_credential_store", lambda: store)
    monkeypatch.setenv("BRISTLENOSE_ANYLLM_MODEL", OPENROUTER_MODEL)
    fake_anyllm.replies.append(_openrouter(429, _SHARED_POOL_429))
    result = CliRunner().invoke(app, ["configure", "any-llm", "--key", "sk-or-new"])
    assert result.exit_code == 0, result.output
    assert "Mistral, reached through OpenRouter, is busy" in " ".join(result.output.split())
    assert "Not valid" not in result.output and "this key" not in result.output
    assert store.get(anyllm.credential_key("openrouter")) == "sk-or-new"


@pytest.mark.parametrize(
    ("status", "body", "category", "host"),
    [
        (429, _SHARED_POOL_429, "quota", "Mistral"),
        (404, _HOST_404, "api_request", "Nvidia"),
        (502, _UNNAMED_HOST, "api_server", ""),
        (401, _BAD_KEY, "auth", None),
        (429, _OWN_LIMIT, "quota", None),
        # OpenRouter's own "no such id" names the model, as the preflight does
        # (R102); the host's 404 above stays the host's.
        (404, _UNKNOWN_MODEL, "model_unavailable", None),
        (404, _HOST_MODEL_GONE, "model_unavailable", "Mistral"),
        # A bare 404 any-llm itself calls ModelNotFoundError: the model, on the
        # run path too, not "rejected the request" (review of c4e2aee97).
        (404, _BARE_404, "model_unavailable", None),
    ],
)
def test_a_run_records_which_host_failed(
    status: int, body: dict[str, Any], category: str, host: str | None
) -> None:
    from bristlenose.events import Cause
    from bristlenose.pipeline import _dominant_cause
    from bristlenose.run_lifecycle import _build_cause

    cause = _build_cause(
        _openrouter(status, body), stage="topic_segmentation", provider="anyllm",
    )
    assert (cause.category.value, cause.model_host) == (category, host)
    # It survives the stage's give-up, which restamps the message, and the log.
    from bristlenose.events import StageFailure

    abandoned = _dominant_cause(
        [StageFailure(session_id="s1", cause=cause)],
        default_category=cause.category, message="Topic segmentation failed.",
    )
    assert Cause.model_validate_json(abandoned.model_dump_json()).model_host == host


def test_a_built_in_provider_never_gets_a_model_host() -> None:
    from bristlenose.run_lifecycle import _build_cause

    cause = _build_cause(_openrouter(429, _SHARED_POOL_429), stage="s", provider="openai")
    assert cause.model_host is None


@pytest.mark.parametrize(
    ("category", "host", "headline"),
    [
        ("quota", "Mistral", "Mistral, reached through OpenRouter, is busy."),
        ("api_request", "Nvidia", "Nvidia, reached through OpenRouter, couldn't serve the model."),
        ("quota", "", "The model's host, reached through OpenRouter, is busy."),
        ("quota", None, "Rate-limited by OpenRouter."),  # OpenRouter's own limit: unchanged
    ],
)
def test_the_run_banner_names_the_host_that_failed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any,
    category: str, host: str | None, headline: str,
) -> None:
    from bristlenose import cli
    from bristlenose.events import Cause, CauseCategoryEnum

    monkeypatch.setenv("BRISTLENOSE_LLM_PROVIDER", "any-llm")
    monkeypatch.setenv("BRISTLENOSE_ANYLLM_MODEL", OPENROUTER_MODEL)
    settings = load_settings()
    lines: list[str] = []
    monkeypatch.setattr(cli.console, "print", lambda *a, **k: lines.append(" ".join(map(str, a))))
    monkeypatch.setattr(cli, "_say", lambda kind, text: lines.append(text))
    cause = Cause(category=CauseCategoryEnum(category), provider="anyllm",
                  stage="topic_segmentation", message="x", model_host=host)
    cli._print_pipeline_failure(cause, tmp_path / "tx-ikea", settings, command="analyze")
    assert headline in lines
    if host is not None:
        assert "bristlenose use provider:model" in "\n".join(lines)
        assert "Rate-limited by" not in "\n".join(lines)


def _unreadable_completion(finish_reason: str, content: str) -> ValidationError:
    """The error any-llm 1.27 raises reading a reply whose finish reason is
    outside OpenAI's five; pydantic's input is the reply, so the transcript."""
    from typing import Literal

    class Message(BaseModel):
        content: str

    class Choice(BaseModel):
        finish_reason: Literal["stop", "length", "tool_calls", "content_filter", "function_call"]
        message: Message

    class ChatCompletion(BaseModel):
        choices: list[Choice]

    try:
        ChatCompletion.model_validate(
            {"choices": [{"finish_reason": finish_reason, "message": {"content": content}}]}
        )
    except ValidationError as exc:
        return exc
    raise AssertionError("expected a ValidationError")


@pytest.mark.asyncio
async def test_an_unreadable_reply_names_its_fields_never_its_text(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The walk's log read "1 validation errors" and nothing more, so a missing
    choice, a null content and a host's error reply all looked alike."""
    from bristlenose.llm.client import UnreadableReplyError

    participant_words = "my GP said the wound was infected"
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-env")
    fake_anyllm.replies.append(_unreadable_completion("error", participant_words))
    with pytest.raises(UnreadableReplyError) as raised:
        await _client(monkeypatch, OPENROUTER_MODEL).analyze("sys", "usr", Theme)
    said = str(raised.value)
    assert "choices.0.finish_reason (literal_error)" in said
    assert "finish_reason='error'" in said
    assert "1 validation error(s)" in said and "validation errors" not in said
    assert participant_words not in said


def test_a_long_or_odd_finish_reason_is_not_repeated() -> None:
    """Only a short printable enum is quoted; anything else could be reply text."""
    from bristlenose.llm.client import _unreadable_fields

    long_text = "the participant said a great deal here " * 3
    assert long_text.strip() not in _unreadable_fields(_unreadable_completion(long_text, "x"))
    assert "finish_reason=" not in _unreadable_fields(_unreadable_completion("a\nb", "x"))


def test_the_run_preflight_names_the_host_too(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """``run`` checks before stage 8 with the same request; its refusal must
    not fall back to blaming the key."""
    import io

    from rich.console import Console

    from bristlenose.preflight import api_key as preflight

    monkeypatch.setattr(preflight, "state_path", lambda: tmp_path / "state.json")
    monkeypatch.delenv("BRISTLENOSE_SKIP_PREFLIGHT", raising=False)  # set suite-wide
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-env")
    fake_anyllm.replies.append(_openrouter(429, _SHARED_POOL_429))
    settings = BristlenoseSettings(llm_provider="anyllm", anyllm_model=OPENROUTER_MODEL)
    with pytest.raises(preflight.ApiKeyPreflightAbortedError) as refused:
        preflight.preflight_api_key(settings=settings, console=Console(file=io.StringIO()))
    assert str(refused.value).startswith("Mistral, reached through OpenRouter, is busy.")


# ---------------------------------------------------------------------------
# Salvage on any-llm's own call path (review round 2, finding 58)
# ---------------------------------------------------------------------------


def _quotes(n: int, bad: tuple[int, ...]) -> str:
    quotes = []
    for i in range(n):
        q = {
            "start_timecode": f"00:00:{10 + i:02d}", "end_timecode": f"00:00:{11 + i:02d}",
            "text": f"quote {i}", "verbatim_excerpt": f"quote {i}",
            "topic_label": "Onboarding", "quote_type": "general_context",
        }
        if i in bad:
            del q["start_timecode"]
        quotes.append(q)
    return json.dumps({"quotes": quotes})


@pytest.mark.asyncio
async def test_one_bad_quote_keeps_the_rest_without_asking_again(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bristlenose.llm.structured import QuoteExtractionResult, dropped_items

    monkeypatch.setenv("MISTRAL_API_KEY", "sk-env")
    fake_anyllm.replies.append(_response(_quotes(3, bad=(1,))))
    result = await _client(monkeypatch).analyze("sys", "usr", QuoteExtractionResult)
    assert [q.verbatim_excerpt for q in result.quotes] == ["quote 0", "quote 2"]
    assert dropped_items(result) == 1
    assert len(fake_anyllm.calls) == 1  # one bad quote isn't worth a second bill


@pytest.mark.asyncio
async def test_a_mostly_wrong_reply_is_asked_for_again(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bristlenose.llm.structured import QuoteExtractionResult

    monkeypatch.setenv("MISTRAL_API_KEY", "sk-env")
    fake_anyllm.replies += [_response(_quotes(3, bad=(0, 1))), _response(_quotes(3, bad=()))]
    result = await _client(monkeypatch).analyze("sys", "usr", QuoteExtractionResult)
    assert len(result.quotes) == 3
    assert len(fake_anyllm.calls) == 2


def test_configure_doesnt_tell_you_to_run_configure(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Inside `configure`, a rejected key is followed by its own prompt (or, with
    --key, by the command already typed): "Store a new one: bristlenose
    configure any-llm" was noise there (Mistral and OpenRouter walks). Every
    other place that shows a rejected key still says it."""
    from typer.testing import CliRunner

    from bristlenose import credentials
    from bristlenose.cli import app
    from bristlenose.credentials import FileCredentialStore
    from bristlenose.llm.billing_hints import recovery_message

    monkeypatch.setattr(credentials, "get_credential_store", lambda: FileCredentialStore(
        tmp_path / "keys.env"))
    monkeypatch.setenv("BRISTLENOSE_ANYLLM_MODEL", OPENROUTER_MODEL)
    fake_anyllm.replies.append(_openrouter(401, _BAD_KEY))
    result = CliRunner().invoke(app, ["configure", "any-llm", "--key", "sk-or-bad"])
    assert result.exit_code == 1
    assert "rejected the API key" in result.output
    assert "Store a new one" not in result.output
    assert "Store a new one: bristlenose configure any-llm" in recovery_message(
        "anyllm", "invalid_key", raw_message="401", provider_display="OpenRouter",
    )


def test_a_providers_words_reach_the_terminal_as_text() -> None:
    """Provider text printed through Rich: markup is escaped (any-llm's
    "[openrouter]" prefix was eaten, "[/b]" raised after the paid calls) and
    control characters are dropped (mistralai's SDKError appends the raw body)."""
    from rich.console import Console

    from bristlenose.llm.billing_hints import recovery_message
    from bristlenose.pipeline import _short_reason

    reason, _ = _short_reason(["[openrouter] Provider returned error [/b]"])
    console = Console(record=True, width=200)
    console.print(f"[dim yellow]{reason}[/dim yellow]")
    assert "[openrouter] Provider returned error [/b]" in console.export_text()

    said = recovery_message(
        "anyllm", "", raw_message="Status 500 \x1b]8;;https://evil.example\x1b\\click\x1b]8;;\x1b\\",
        provider_display="Mistral",
    )
    assert "\x1b" not in said and "click" in said


def test_a_later_failure_is_not_blamed_on_an_earlier_host() -> None:
    """The json_object fallback runs inside the `except` that caught a host's
    refusal, so anything it raises carries that refusal as `__context__`.
    OpenRouter's own key-level 429 there was worded "Mistral, reached through
    OpenRouter, is busy. Your key works." (review round 2, finding 38)."""
    host_refusal = _openrouter(502, {
        "message": "Provider returned error", "code": 502,
        "metadata": {"provider_name": "Mistral"},
    })
    try:
        try:
            raise host_refusal
        except Exception:
            raise _openrouter(429, _OWN_LIMIT)  # noqa: B904 -- the shape under test
    except Exception as later:
        assert later.__context__ is host_refusal
        assert anyllm.upstream(later) is None
    assert anyllm.upstream(host_refusal) == ("Mistral", "")


@pytest.mark.asyncio
async def test_a_refusal_on_the_last_retry_is_still_resent(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Five 429s, then the endpoint refuses thinking off: the resend without it
    must still go out. It spent a retry slot and, on the last one, fell out of
    the loop as AssertionError("unreachable"), printed as the session's reason
    (review round 2, finding 39)."""
    import bristlenose.llm.client as client_module
    from bristlenose.llm.client import _CLOUD_MAX_RETRIES

    async def no_wait(_: float) -> None:
        return None

    monkeypatch.setattr(client_module.asyncio, "sleep", no_wait)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-env")
    fake_anyllm.replies += [_openrouter(429, _OWN_LIMIT)] * (_CLOUD_MAX_RETRIES - 1)
    fake_anyllm.replies += [
        _StatusError(400, "Reasoning is mandatory for this endpoint and cannot be disabled."),
        _response(json.dumps({"label": "Checkout", "quotes": []})),
    ]
    result = await _client(monkeypatch, OPENROUTER_MODEL).analyze("s", "u", Theme)
    assert result.label == "Checkout"
    assert "reasoning_effort" not in fake_anyllm.calls[-1]


@pytest.mark.parametrize(("error", "refuses"), [
    (_StatusError(400, "Reasoning is mandatory for this endpoint and cannot be disabled."), True),
    (_StatusError(400, "'reasoning_effort' is not supported for this model"), True),
    (_StatusError(400, "deepseek/deepseek-reasoner is not a valid model ID"), False),
    (_StatusError(400, "context length exceeded, including reasoning tokens"), False),
    (_StatusError(500, "Reasoning is mandatory for this endpoint"), False),
])
def test_only_the_refusals_own_words_switch_thinking_back_on(
    error: BaseException, refuses: bool
) -> None:
    """`str(exc)` is the whole body: the bare word "reasoning" in a model id or
    a host's message turned thinking back on for the rest of the run, the cost
    and the deadline failure thinking-off exists to prevent (finding 40)."""
    from bristlenose.llm.client import _refuses_reasoning_off

    assert _refuses_reasoning_off(error) is refuses


def test_use_any_llm_with_no_model_refuses_rather_than_switching(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """It announced "any-llm is now your provider" and the next run failed at
    its preflight (docs review, 24 Oct 2026)."""
    from typer.testing import CliRunner

    from bristlenose import cli
    from bristlenose.cli import app

    switched: list[str] = []
    monkeypatch.setattr(cli, "_set_current_provider", switched.append)
    monkeypatch.delenv("BRISTLENOSE_ANYLLM_MODEL", raising=False)
    result = CliRunner().invoke(app, ["use", "any-llm"])
    assert result.exit_code == 1
    assert switched == []
    assert "needs a model" in result.output


def test_the_snap_and_fedora_packages_say_any_llm_isnt_in_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Their Python has no usable pip, so the pip command was a dead end."""
    from bristlenose import doctor_fixes

    monkeypatch.setattr(doctor_fixes, "detect_install_method", lambda: "snap")
    lines = anyllm.explain(anyllm.Readiness("not-installed", model=MODEL))
    assert "isn't part of this package" in lines[0]
    assert not any("pip install" in line for line in lines)
    monkeypatch.setattr(doctor_fixes, "detect_install_method", lambda: "pip")
    assert "pip install" in " ".join(anyllm.explain(anyllm.Readiness("not-installed", model=MODEL)))


def test_the_newer_python_hint_keeps_what_is_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """It suggested `pipx install --python python3.12 "bristlenose[any-llm]"`:
    refused by pipx without --force, and dropping [voice] with it."""
    from bristlenose.utils import install_channel

    monkeypatch.setattr(install_channel, "install_channel", lambda: "pipx")
    monkeypatch.setattr(install_channel, "installed_extras", lambda: ["voice"])
    hint = " ".join(anyllm.explain(anyllm.Readiness("old-python", model=MODEL)))
    assert 'pipx install --force --python python3.12 "bristlenose[any-llm,voice]"' in hint
