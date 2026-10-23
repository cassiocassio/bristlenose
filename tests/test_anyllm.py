"""any-llm as the sixth provider (docs/design-any-llm.md §9).

CI never installs any-llm and never makes a paid call: a fake ``any_llm``
module stands in. It is shaped like the real 1.27 library where that shape is
what we depend on — ``MissingApiKeyError.env_var_name`` raised by ``create``, a
class-level ``MISSING_PACKAGES_ERROR``, ``API_BASE``, a raw ``ChatCompletion``
when the response format is a dict — so a test here fails the way the real
library would. ``scripts/check-providers-live.py`` asks the real thing.
"""

from __future__ import annotations

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


class _FakeProvider:
    def __init__(self, library: _FakeLibrary) -> None:
        self.library = library

    async def acompletion(self, **kwargs: Any) -> Any:
        return self.completion(**kwargs)

    def completion(self, **kwargs: Any) -> Any:  # the preflight's sync call
        unexpected = set(kwargs) - {
            "model", "messages", "response_format", "max_tokens", "temperature",
        }
        assert not unexpected, f"a parameter the call should not send: {unexpected}"
        self.library.calls.append(kwargs)
        reply = self.library.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply


class _FakeLibrary:
    """``AnyLLM`` as a class with classmethods, like the real one."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.replies: list[Any] = []
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
    monkeypatch.setattr(anyllm, "install_state", lambda: "not-installed")
    assert _ready(MODEL).status == "not-installed"
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
    if not isinstance(sys.modules.get("any_llm"), type(real)) or not hasattr(real, "__file__"):
        pytest.skip("a fake any_llm is installed in this process")
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
