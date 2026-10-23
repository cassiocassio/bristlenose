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
            ),
            "openrouter": types.SimpleNamespace(
                API_BASE="https://openrouter.ai/api/v1",
                ENV_API_KEY_NAME="OPENROUTER_API_KEY",
                MISSING_PACKAGES_ERROR=None,
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
                needs_key = spec.ENV_API_KEY_NAME not in ("None", "")
                if needs_key and not api_key and not os.environ.get(spec.ENV_API_KEY_NAME):
                    raise _MissingApiKeyError(provider, spec.ENV_API_KEY_NAME)
                library.created.append((provider, api_key))
                return _FakeProvider(library)

        module = types.ModuleType("any_llm")
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
    for var in ("MISTRAL_API_KEY", "OPENROUTER_API_KEY", "COHERE_API_KEY"):
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
async def test_any_llms_own_length_error_is_truncation_too(
    fake_anyllm: _FakeLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    class LengthFinishReasonError(Exception):
        completion = None

    monkeypatch.setenv("MISTRAL_API_KEY", "sk-env")
    fake_anyllm.replies.append(LengthFinishReasonError("length limit"))
    with pytest.raises(TruncatedResponseError):
        await _client(monkeypatch).analyze("sys", "usr", Theme)


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
         'pip install "any-llm-sdk[cohere]"'),
        (("home", "u", ".local", "pipx", "venvs", "bristlenose"),
         'pipx install --force "bristlenose[any-llm]"',
         'pipx inject bristlenose "any-llm-sdk[cohere]"'),
        (("home", "u", ".local", "share", "uv", "tools", "bristlenose"),
         'uv tool install --force "bristlenose[any-llm]"',
         'uv tool install --force "bristlenose" --with "any-llm-sdk[cohere]"'),
        (("opt", "homebrew", "Cellar", "bristlenose", "0.43.0", "libexec"),
         "brew reinstall bristlenose",
         '$(brew --prefix bristlenose)/libexec/bin/pip install "any-llm-sdk[cohere]"'),
    ],
)
def test_install_hints_follow_the_channel(
    monkeypatch: pytest.MonkeyPatch, prefix: tuple[str, ...], extra: str, inject: str
) -> None:
    from pathlib import Path

    monkeypatch.setattr(sys, "prefix", str(Path("/", *prefix)))
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
