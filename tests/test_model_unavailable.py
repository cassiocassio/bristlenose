"""R102 — a retired, unknown or deprecated model is its own failure kind.

A provider retired a model and every analysis failed with "the provider
rejected the request": the classifier read a model-not-found answer as a
generic bad request (the bare 4xx rule), so the CLI said "rejected the
request" and the Mac said "Provider rejected request" when the remedy is to
choose another model.

The exceptions below are the real SDK classes, built the way each SDK builds
them from the wire (anthropic 1.x, openai 3.x, google-genai 2.x), with the
bodies each provider sends. No call leaves the machine.
"""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from bristlenose.events import Cause, CauseCategoryEnum, StageFailure, is_retryable
from bristlenose.llm.failure_classifier import (
    LLMFailureKind,
    classify_exception,
    classify_llm_failure,
)

# ---------------------------------------------------------------------------
# The wire shapes
# ---------------------------------------------------------------------------


def _http_error(sdk_class: type, status: int, url: str, body: dict, sdk_body: object) -> Any:
    import httpx

    request = httpx.Request("POST", url)
    response = httpx.Response(status, json=body, request=request)
    return sdk_class(f"Error code: {status} - {body!r}", response=response, body=sdk_body)


def _anthropic_404(message: str) -> Any:
    import anthropic

    body = {"type": "error", "error": {"type": "not_found_error", "message": message}}
    return _http_error(
        anthropic.NotFoundError, 404, "https://api.anthropic.com/v1/messages", body, body
    )


def _openai_404(error: dict, url: str = "https://api.openai.com/v1/chat/completions") -> Any:
    import openai

    # The openai client unwraps {"error": {...}} into ``body``.
    return _http_error(openai.NotFoundError, 404, url, {"error": error}, error)


def _gemini_404(message: str) -> Any:
    from google.genai import errors

    return errors.ClientError(
        404, {"error": {"code": 404, "message": message, "status": "NOT_FOUND"}}
    )


_AZURE_URL = "https://x.openai.azure.com/openai/deployments/gpt4/chat/completions"
_OLLAMA_URL = "http://localhost:11434/v1/chat/completions"

#: (provider, exception factory) for every shape a provider sends for a model
#: it doesn't serve.
_MODEL_GONE: list[Any] = [
    pytest.param(
        "anthropic", lambda: _anthropic_404("model: claude-3-opus-20240229"),
        id="claude-retired",
    ),
    pytest.param(
        "anthropic", lambda: _anthropic_404("model: claude-sonnet-9"), id="claude-unknown",
    ),
    pytest.param(
        "openai",
        lambda: _openai_404({
            "message": "The model `gpt-4-32k` does not exist or you do not have access to it.",
            "type": "invalid_request_error", "param": None, "code": "model_not_found",
        }),
        id="chatgpt-model-not-found",
    ),
    pytest.param(
        "openai",
        lambda: _openai_404({
            "message": "The model `text-davinci-003` has been deprecated, learn more here: "
                       "https://platform.openai.com/docs/deprecations",
            "type": "invalid_request_error", "param": None, "code": "model_not_found",
        }),
        id="chatgpt-deprecated",
    ),
    pytest.param(
        "azure",
        lambda: _openai_404(
            {
                "code": "DeploymentNotFound",
                "message": "The API deployment for this resource does not exist. If you "
                           "created the deployment within the last 5 minutes, please wait a "
                           "moment and try again.",
            },
            url=_AZURE_URL,
        ),
        id="azure-deployment-not-found",
    ),
    pytest.param(
        "google",
        lambda: _gemini_404(
            "models/gemini-1.5-pro is not found for API version v1beta, or is not "
            "supported for generateContent. Call ListModels to see the list of available "
            "models and their supported methods."
        ),
        id="gemini-not-found",
    ),
    pytest.param(
        "local",
        lambda: _openai_404(
            {"message": "model \"llama9:7b\" not found, try pulling it first",
             "type": "api_error", "param": None, "code": None},
            url=_OLLAMA_URL,
        ),
        id="ollama-openai-route",
    ),
    pytest.param(
        "local",
        lambda: _openai_404(
            {"message": "model 'llama9:7b' not found", "type": "api_error",
             "param": None, "code": None},
            url=_OLLAMA_URL,
        ),
        id="ollama-native-wording",
    ),
]


# ---------------------------------------------------------------------------
# The classifier
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("provider", "make"), _MODEL_GONE)
def test_a_model_the_provider_does_not_serve_is_model_unavailable(
    provider: str, make: Callable[[], Any]
) -> None:
    assert classify_exception(provider, make()) is LLMFailureKind.MODEL_UNAVAILABLE


@pytest.mark.parametrize(
    ("provider", "code"),
    [("openai", "model_not_found"), ("azure", "model_not_found"),
     ("azure", "DeploymentNotFound"), ("google", "NOT_FOUND")],
)
def test_the_structured_field_alone_is_enough(provider: str, code: str) -> None:
    # Structured field before message (the classifier's precedence): a proxy or
    # a later SDK that rewords the sentence must not turn it back into a bad
    # request.
    kind = classify_llm_failure(provider, status=404, error_code=code, message="reworded")
    assert kind is LLMFailureKind.MODEL_UNAVAILABLE


def test_a_refused_parameter_stays_a_bad_request() -> None:
    # The kind is for the model, not for every 4xx: a parameter the model
    # refuses is the request itself, and keeps the generic sentence.
    import anthropic

    body = {"type": "error", "error": {
        "type": "invalid_request_error",
        "message": "max_tokens: 200000 > 64000, which is the maximum allowed number of "
                   "output tokens for claude-sonnet-4-6",
    }}
    exc = _http_error(
        anthropic.BadRequestError, 400, "https://api.anthropic.com/v1/messages", body, body
    )
    assert classify_exception("anthropic", exc) is LLMFailureKind.BAD_REQUEST


def test_an_azure_404_that_is_not_the_deployment_stays_a_bad_request() -> None:
    # A wrong endpoint path is a 404 with no DeploymentNotFound code; the remedy
    # is the endpoint, not the model.
    exc = _openai_404({"code": "404", "message": "Resource not found"}, url=_AZURE_URL)
    assert classify_exception("azure", exc) is LLMFailureKind.BAD_REQUEST


# ---------------------------------------------------------------------------
# The run: cause, retry, abandon
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("provider", "make"), _MODEL_GONE)
def test_a_stage_failure_records_the_model_category(
    provider: str, make: Callable[[], Any]
) -> None:
    from bristlenose.run_lifecycle import _build_cause

    cause = _build_cause(make(), stage="topic_segmentation", provider=provider)
    assert cause.category is CauseCategoryEnum.MODEL_UNAVAILABLE
    # The events log is a re-identification surface: the message is ours.
    assert "Error code" not in cause.message


def test_the_category_is_not_retryable() -> None:
    assert is_retryable(CauseCategoryEnum.MODEL_UNAVAILABLE) is False


def test_a_tie_with_a_rate_limit_names_the_model() -> None:
    # Retrying does nothing for a model that is gone; the banner must not say
    # "wait a minute" when half the calls were also throttled.
    from bristlenose.pipeline import _dominant_cause

    failures = [
        StageFailure(session_id="s1", cause=Cause(category=CauseCategoryEnum.QUOTA, message="")),
        StageFailure(
            session_id="s2",
            cause=Cause(category=CauseCategoryEnum.MODEL_UNAVAILABLE, message=""),
        ),
    ]
    chosen = _dominant_cause(
        failures, default_category=CauseCategoryEnum.UNKNOWN, message="All calls failed."
    )
    assert chosen.category is CauseCategoryEnum.MODEL_UNAVAILABLE


# ---------------------------------------------------------------------------
# The CLI banner
# ---------------------------------------------------------------------------


def _banner(monkeypatch: pytest.MonkeyPatch, tmp_path: Any, provider: str, **fields: str) -> str:
    from bristlenose import cli

    lines: list[str] = []
    monkeypatch.setattr(cli.console, "print", lambda *a, **k: lines.append(" ".join(map(str, a))))
    monkeypatch.setattr(cli, "_say", lambda kind, text: lines.append(text))
    settings = SimpleNamespace(llm_provider=provider, **fields)
    cause = Cause(category=CauseCategoryEnum.MODEL_UNAVAILABLE, message="All calls failed.",
                  provider=provider, stage="topic_segmentation")
    cli._print_pipeline_failure(cause, tmp_path / "interviews", settings)
    return "\n".join(lines)


@pytest.mark.parametrize(
    ("provider", "fields", "says"),
    [
        ("anthropic", {"llm_model": "claude-3-opus-20240229"}, "BRISTLENOSE_LLM_MODEL"),
        ("openai", {"llm_model": "gpt-4-32k"}, "BRISTLENOSE_LLM_MODEL"),
        ("google", {"llm_model": "gemini-1.5-pro"}, "BRISTLENOSE_LLM_MODEL"),
        ("azure", {"azure_deployment": "gpt4-prod"}, "BRISTLENOSE_AZURE_DEPLOYMENT"),
        ("local", {"local_model": "llama9:7b"}, "ollama pull llama9:7b"),
    ],
)
def test_the_cli_names_the_model_and_where_to_change_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any,
    provider: str, fields: dict[str, str], says: str,
) -> None:
    text = _banner(monkeypatch, tmp_path, provider, **fields)
    verb = "have" if provider == "local" else "offer"
    assert f"doesn't {verb} the model {next(iter(fields.values()))}" in text
    assert says in text
    assert "bristlenose run interviews/" in text
    assert "rejected the request" not in text


# ---------------------------------------------------------------------------
# The preflight agrees with the run
# ---------------------------------------------------------------------------


def _raise(exc: Any) -> Callable[..., Any]:
    def create(*_a: Any, **_k: Any) -> Any:
        raise exc

    return create


def _validate(monkeypatch: pytest.MonkeyPatch, provider: str, exc: Any) -> Any:
    """Run the provider's preflight validator against a client that raises ``exc``."""
    from bristlenose.preflight import api_key

    client = SimpleNamespace(
        messages=SimpleNamespace(create=_raise(exc)),
        chat=SimpleNamespace(completions=SimpleNamespace(create=_raise(exc))),
        models=SimpleNamespace(generate_content=_raise(exc)),
    )
    if provider == "anthropic":
        import anthropic

        monkeypatch.setattr(anthropic, "Anthropic", lambda **_k: client)
        return api_key._validate_anthropic("sk-ant-test", "claude-x")
    if provider in ("openai", "local", "azure"):
        import openai

        monkeypatch.setattr(openai, "OpenAI", lambda **_k: client)
        monkeypatch.setattr(openai, "AzureOpenAI", lambda **_k: client)
        if provider == "openai":
            return api_key._validate_openai("sk-test", "gpt-x")
        if provider == "local":
            return api_key._validate_local("http://localhost:11434/v1", "llama9:7b")
        return api_key._validate_azure("k", "https://x.openai.azure.com", "gpt4", "2024-10-21")
    from google import genai

    monkeypatch.setattr(genai, "Client", lambda **_k: client)
    return api_key._validate_google("g-test", "gemini-x")


@pytest.mark.parametrize(("provider", "make"), _MODEL_GONE)
def test_the_preflight_reads_it_as_the_run_does(
    monkeypatch: pytest.MonkeyPatch, provider: str, make: Callable[[], Any]
) -> None:
    # Claude's 404 fell to the generic "Provider says: …" before (R102).
    result = _validate(monkeypatch, provider, make())
    assert result.ok is False
    assert result.error_class == "model_unavailable"


@pytest.mark.parametrize(
    ("provider", "make"),
    [
        pytest.param("azure", lambda: _openai_404(
            {"code": "404", "message": "Resource not found"}, url=_AZURE_URL), id="azure-path"),
        pytest.param("local", lambda: _openai_404(
            {"message": "404 page not found", "type": "api_error", "param": None,
             "code": None}, url=_OLLAMA_URL), id="ollama-no-v1"),
        pytest.param("openai", lambda: _openai_404(
            {"message": "Not Found", "type": "invalid_request_error", "param": None,
             "code": None}), id="chatgpt-path"),
    ],
)
def test_a_404_that_is_not_the_model_is_not_called_one(
    monkeypatch: pytest.MonkeyPatch, provider: str, make: Callable[[], Any]
) -> None:
    # The check said "model unavailable" for every 404 and the run said "rejected
    # the request". Now both say what the provider said.
    exc = make()
    assert classify_exception(provider, exc) is LLMFailureKind.BAD_REQUEST
    result = _validate(monkeypatch, provider, exc)
    assert (result.ok, result.error_class) == (False, None)


def test_the_preflight_copy_names_a_setting_that_exists() -> None:
    # It said `--llm-model`, a flag Bristlenose has never had.
    from bristlenose.llm.billing_hints import recovery_message

    for provider in ("anthropic", "openai", "google", "local"):
        text = recovery_message(provider, "model_unavailable", raw_message="404")
        assert "--llm-model" not in text
        assert "BRISTLENOSE_" in text, provider


# ---------------------------------------------------------------------------
# AutoCode in the report says it too
# ---------------------------------------------------------------------------


def test_every_failure_kind_has_an_autocode_sentence() -> None:
    # The server stores `classify_exception(...).value` as `failure_kind`; a
    # value the SPA doesn't map reads "Tagging failed.", which is how a new kind
    # would arrive unexplained. Read the map from the source, not a copy.
    import re
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "frontend" / "src" / "utils" / "autocodeFailure.ts"
    ).read_text(encoding="utf-8")
    block = source.split("const FAILURES", 1)[1].split("\n};", 1)[0]
    mapped = set(re.findall(r"^  (\w+): \{", block, re.M))
    assert {k.value for k in LLMFailureKind} <= mapped


# ---------------------------------------------------------------------------
# The Mac reads a preflight abort from stdout
# ---------------------------------------------------------------------------


def _swift_model_arm() -> str:
    """The pattern `PipelineRunner.categoriseFailure` returns `.modelUnavailable` on."""
    import re
    from pathlib import Path

    swift = (
        Path(__file__).resolve().parents[1]
        / "desktop" / "Bristlenose" / "Bristlenose" / "PipelineRunner.swift"
    ).read_text(encoding="utf-8")
    found = re.search(r'tail,\s*#"([^"]+)"#\s*\)\s*\{\s*return \.modelUnavailable', swift)
    assert found, "the .modelUnavailable arm moved; update this reader"
    return found.group(1)


@pytest.mark.parametrize(("provider", "make"), _MODEL_GONE)
def test_the_mac_recognises_every_preflight_model_sentence(
    monkeypatch: pytest.MonkeyPatch, provider: str, make: Callable[[], Any]
) -> None:
    # A preflight abort writes no terminus; the Mac classifies the English it
    # printed. The `preflight` namespace is English on every channel for this.
    # Built from the check's own result, so the raw text it quotes is real.
    import re

    from bristlenose.llm.billing_hints import recovery_message

    result = _validate(monkeypatch, provider, make())
    text = recovery_message(provider, result.error_class or "", raw_message=result.raw_message)
    assert re.search(_swift_model_arm(), text.lower()), text


def test_the_mac_recognises_any_llms_model_sentence() -> None:
    import re

    from bristlenose.llm.billing_hints import recovery_message

    text = recovery_message("anyllm", "model_unavailable", raw_message="404",
                            provider_display="Mistral")
    assert re.search(_swift_model_arm(), text.lower()), text


def test_a_gemini_403_is_not_read_as_the_model_on_the_mac(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The check words a 403 with the same sentence as a missing model; the run
    # reads it as the key's. The Mac must not tell the researcher to change the
    # model for it (review of c4e2aee97).
    import re

    from google.genai import errors

    from bristlenose.llm.billing_hints import recovery_message

    exc = errors.ClientError(403, {"error": {
        "code": 403, "message": "Permission denied on resource project x.",
        "status": "PERMISSION_DENIED"}})
    result = _validate(monkeypatch, "google", exc)
    text = recovery_message("google", result.error_class or "", raw_message=result.raw_message)
    assert not re.search(_swift_model_arm(), text.lower()), text


def test_a_whisper_warning_is_not_read_as_the_model() -> None:
    import re

    line = "whisper: BRISTLENOSE_WHISPER_MODEL set but model not found at /x; downloading"
    assert not re.search(_swift_model_arm(), line.lower())


@pytest.mark.parametrize(
    ("provider", "fields"),
    [
        ("anthropic", {"llm_model": "claude-3-opus-20240229"}),
        ("openai", {"llm_model": "gpt-4-32k"}),
        ("google", {"llm_model": "gemini-1.5-pro"}),
        ("azure", {"azure_deployment": "gpt4-prod"}),
        ("local", {"local_model": "llama9:7b"}),
        ("anyllm", {"anyllm_model": "openrouter:x/y"}),
    ],
)
def test_the_mac_recognises_the_cli_banner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any, provider: str, fields: dict[str, str]
) -> None:
    # The banner as printed, per provider, not a sentence typed here: a reword
    # that leaves the Swift arm behind fails this.
    import re

    text = _banner(monkeypatch, tmp_path, provider, **fields)
    assert re.search(_swift_model_arm(), text.lower()), text


def test_the_mac_recognises_the_host_banner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    import re

    from bristlenose import cli

    lines: list[str] = []
    monkeypatch.setattr(cli.console, "print", lambda *a, **k: lines.append(" ".join(map(str, a))))
    monkeypatch.setattr(cli, "_say", lambda kind, text: lines.append(text))
    monkeypatch.setattr("bristlenose.llm.anyllm.account_name", lambda s: "OpenRouter")
    cause = Cause(category=CauseCategoryEnum.MODEL_UNAVAILABLE, message="m",
                  provider="anyllm", model_host="Mistral")
    cli._print_pipeline_failure(
        cause, tmp_path / "interviews", SimpleNamespace(llm_provider="anyllm")
    )
    text = "\n".join(lines)
    assert "Mistral, reached through OpenRouter, doesn't offer the model." in text
    # Not retryable: waiting won't bring the model back.
    assert "again later" not in text
    assert re.search(_swift_model_arm(), text.lower()), text


@pytest.mark.parametrize("stage", ["quote_extraction", "thematic_grouping"])
def test_the_truncation_advice_names_a_setting_that_exists(stage: str) -> None:
    # It said "see the --llm and --model options"; there is no --model.
    from bristlenose.llm.client import TruncatedResponseError
    from bristlenose.run_lifecycle import _build_cause

    exc = TruncatedResponseError(
        "cut", provider="anthropic", model="m", requested_max_tokens=10, model_cap=10
    )
    cause = _build_cause(exc, stage=stage, provider="anthropic")
    assert cause.category is CauseCategoryEnum.OUTPUT_TRUNCATED
    assert "--model" not in cause.message
    assert "BRISTLENOSE_LLM_MODEL" in cause.message


def test_the_model_field_map_names_real_settings() -> None:
    # `wire_model` reads by name with a fail-open getattr; a renamed field would
    # blank the model in the banner and the check's cache key, silently.
    from bristlenose.config import _MODEL_FIELD, BristlenoseSettings

    for field in (*_MODEL_FIELD.values(), "llm_model"):
        assert field in BristlenoseSettings.model_fields, field
