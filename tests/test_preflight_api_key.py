"""Tests for bristlenose.preflight.api_key."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from bristlenose.preflight.api_key import (
    ApiKeyPreflightAbortedError,
    ValidationResult,
    _is_recently_validated,
    _mark_validated,
    _openai_error_code,
    _validate_anthropic,
    _validate_azure,
    _validate_google,
    _validate_local,
    _validate_openai,
    preflight_api_key,
    read_state,
    state_path,
    write_state,
)


@pytest.fixture(autouse=True)
def _allow_preflight(monkeypatch):
    """Opt out of the global ``BRISTLENOSE_SKIP_PREFLIGHT=1`` set in
    ``tests/conftest.py`` — this file tests the preflight itself."""
    monkeypatch.delenv("BRISTLENOSE_SKIP_PREFLIGHT", raising=False)


def _settings(**kwargs) -> MagicMock:
    s = MagicMock()
    s.llm_provider = kwargs.get("llm_provider", "anthropic")
    s.llm_model = kwargs.get("llm_model", "claude-sonnet-4-5-20250929")
    s.anthropic_api_key = kwargs.get("anthropic_api_key", "")
    s.openai_api_key = kwargs.get("openai_api_key", "")
    s.azure_api_key = kwargs.get("azure_api_key", "")
    s.azure_endpoint = kwargs.get("azure_endpoint", "https://example.openai.azure.com/")
    s.azure_deployment = kwargs.get("azure_deployment", "gpt-4o")
    s.azure_api_version = kwargs.get("azure_api_version", "2024-10-21")
    s.google_api_key = kwargs.get("google_api_key", "")
    s.local_url = kwargs.get("local_url", "http://localhost:11434/v1")
    s.local_model = kwargs.get("local_model", "llama3.2:3b")
    s.local_api_key = ""
    return s


def _console() -> Console:
    return Console(force_terminal=False, no_color=True, width=80)


# ---------------------------------------------------------------------------
# state file
# ---------------------------------------------------------------------------


class TestStateFile:
    def test_state_path_under_app_support_on_macos(self, monkeypatch):
        monkeypatch.setattr("bristlenose.preflight.api_key.sys.platform", "darwin")
        path = state_path()
        assert "Application Support" in str(path)
        assert path.name == "state.json"

    def test_state_path_under_xdg_on_linux(self, monkeypatch, tmp_path):
        monkeypatch.setattr("bristlenose.preflight.api_key.sys.platform", "linux")
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        path = state_path()
        assert str(tmp_path) in str(path)
        assert path.name == "state.json"

    def test_read_state_missing_returns_first_run_schema(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.state_path",
            lambda: tmp_path / "state.json",
        )
        state = read_state()
        assert state["first_run"] is True
        assert state["providers"] == {}
        assert state["version"] >= 1

    def test_write_then_read_roundtrip(self, monkeypatch, tmp_path):
        path = tmp_path / "state.json"
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.state_path", lambda: path,
        )
        write_state({"version": 1, "first_run": False, "providers": {"x": {}}})
        again = read_state()
        assert again["first_run"] is False
        assert "x" in again["providers"]

    def test_corrupt_json_falls_back_to_empty_schema(self, monkeypatch, tmp_path):
        path = tmp_path / "state.json"
        path.write_text("{not json", encoding="utf-8")
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.state_path", lambda: path,
        )
        state = read_state()
        assert state["first_run"] is True


class TestTTL:
    def test_recent_validation_within_window(self):
        state = {
            "providers": {
                "anthropic": {"last_validated_epoch": int(time.time())},
            },
        }
        assert _is_recently_validated(state, "anthropic")

    def test_old_validation_outside_window(self):
        state = {
            "providers": {
                "anthropic": {
                    "last_validated_epoch": int(time.time()) - 25 * 3600,
                },
            },
        }
        assert not _is_recently_validated(state, "anthropic")

    def test_missing_provider_not_recent(self):
        assert not _is_recently_validated({"providers": {}}, "anthropic")

    def test_mark_validated_sets_timestamp_and_clears_first_run(self):
        state = {"first_run": True, "providers": {}}
        _mark_validated(state, "anthropic", source="env")
        assert state["first_run"] is False
        info = state["providers"]["anthropic"]
        assert info["source"] == "env"
        assert abs(info["last_validated_epoch"] - time.time()) < 5


# ---------------------------------------------------------------------------
# Validators (transport errors mocked)
# ---------------------------------------------------------------------------


class TestValidateAnthropic:
    def _fake_anthropic(self, exc_class=None, exc=None):
        fake = MagicMock()
        client = MagicMock()
        fake.Anthropic.return_value = client
        if exc is not None:
            client.messages.create.side_effect = exc
        else:
            client.messages.create.return_value = MagicMock()
        # The validator catches by class — expose the same exception classes.
        if exc_class is not None:
            for attr in (
                "AuthenticationError", "BadRequestError",
                "RateLimitError", "APIStatusError",
            ):
                setattr(
                    fake, attr,
                    type(attr, (Exception,), {}) if attr != exc_class.__name__ else exc_class,
                )
        else:
            fake.AuthenticationError = type("AuthenticationError", (Exception,), {})
            fake.BadRequestError = type("BadRequestError", (Exception,), {})
            fake.RateLimitError = type("RateLimitError", (Exception,), {})
            fake.APIStatusError = type("APIStatusError", (Exception,), {})
        return fake

    def test_ok_path(self, monkeypatch):
        fake = self._fake_anthropic()
        monkeypatch.setitem(__import__("sys").modules, "anthropic", fake)
        result = _validate_anthropic("sk-key", "claude-sonnet-4-5-20250929")
        assert result.ok

    def test_auth_error_maps_to_invalid_key(self, monkeypatch):
        auth_error = type("AuthenticationError", (Exception,), {})
        fake = self._fake_anthropic(exc_class=auth_error, exc=auth_error("401 bad key"))
        monkeypatch.setitem(__import__("sys").modules, "anthropic", fake)
        result = _validate_anthropic("sk-bad", "claude-sonnet-4-5-20250929")
        assert not result.ok
        assert result.error_class == "invalid_key"

    def test_credit_balance_too_low_maps_to_billing_empty(self, monkeypatch):
        # Real SDK message shape — "credit balance" with spaces, not the
        # underscored error.type. The classifier matches on this verbatim;
        # if a future refactor reverts to "credit_balance_too_low" the
        # branch will silently miss and route to model_unavailable.
        bad_req = type("BadRequestError", (Exception,), {})
        real_msg = (
            "Your credit balance is too low to access the Claude API. "
            "Please go to Plans & Billing to upgrade or purchase credits."
        )
        fake = self._fake_anthropic(exc_class=bad_req, exc=bad_req(real_msg))
        monkeypatch.setitem(__import__("sys").modules, "anthropic", fake)
        result = _validate_anthropic("sk-key", "claude-sonnet-4-5-20250929")
        assert not result.ok
        assert result.error_class == "billing_empty"
        assert "credit balance" in result.raw_message.lower()

    def test_other_bad_request_maps_to_model_unavailable(self, monkeypatch):
        bad_req = type("BadRequestError", (Exception,), {})
        fake = self._fake_anthropic(
            exc_class=bad_req, exc=bad_req("400 model not found"),
        )
        monkeypatch.setitem(__import__("sys").modules, "anthropic", fake)
        result = _validate_anthropic("sk-key", "gibberish-model")
        assert not result.ok
        assert result.error_class == "model_unavailable"

    def test_rate_limit_maps_to_rate_limit(self, monkeypatch):
        rl = type("RateLimitError", (Exception,), {})
        fake = self._fake_anthropic(exc_class=rl, exc=rl("429 slow down"))
        monkeypatch.setitem(__import__("sys").modules, "anthropic", fake)
        result = _validate_anthropic("sk-key", "claude-sonnet-4-5-20250929")
        assert not result.ok
        assert result.error_class == "rate_limit"


class TestValidateOpenai:
    def _fake_openai(self, exc_class=None, exc=None):
        fake = MagicMock()
        client = MagicMock()
        fake.OpenAI.return_value = client
        if exc is not None:
            client.chat.completions.create.side_effect = exc
        else:
            client.chat.completions.create.return_value = MagicMock()
        fake.AuthenticationError = type("AuthenticationError", (Exception,), {})
        fake.RateLimitError = type("RateLimitError", (Exception,), {})
        fake.NotFoundError = type("NotFoundError", (Exception,), {})
        fake.APIStatusError = type("APIStatusError", (Exception,), {})
        if exc_class is not None:
            setattr(fake, exc_class.__name__, exc_class)
        return fake

    def test_ok_path(self, monkeypatch):
        fake = self._fake_openai()
        monkeypatch.setitem(__import__("sys").modules, "openai", fake)
        result = _validate_openai("sk-key", "gpt-4o-mini")
        assert result.ok

    def test_429_insufficient_quota_maps_to_billing_empty(self, monkeypatch):
        rl = type("RateLimitError", (Exception,), {})
        fake = self._fake_openai(
            exc_class=rl, exc=rl("429 insufficient_quota"),
        )
        monkeypatch.setitem(__import__("sys").modules, "openai", fake)
        result = _validate_openai("sk-key", "gpt-4o-mini")
        assert not result.ok
        assert result.error_class == "billing_empty"

    def test_429_regular_maps_to_rate_limit(self, monkeypatch):
        rl = type("RateLimitError", (Exception,), {})
        fake = self._fake_openai(exc_class=rl, exc=rl("429 too many requests"))
        monkeypatch.setitem(__import__("sys").modules, "openai", fake)
        result = _validate_openai("sk-key", "gpt-4o-mini")
        assert not result.ok
        assert result.error_class == "rate_limit"


# ---------------------------------------------------------------------------
# Real-SDK-exception validators (Azure, Google, Local, OpenAI-structured).
# Per Bach finding on the prior branch: faked-SDK tests let bugs through
# because the fakes didn't match real exception shapes. These instantiate
# real SDK exception classes with realistic body dicts.
# ---------------------------------------------------------------------------


def _openai_exc(cls, *, status_code: int, code: str | None, message: str = "err"):
    """Build a real openai SDK exception with a structured body."""
    import httpx

    req = httpx.Request("POST", "https://example.com/")
    body: dict = {"error": {"message": message}}
    if code is not None:
        body["error"]["code"] = code
    resp = httpx.Response(status_code, request=req, json=body)
    return cls(message=message, response=resp, body=body)  # type: ignore[arg-type]


class TestOpenaiErrorCodeHelper:
    def test_reads_body_error_code(self):
        import openai
        exc = _openai_exc(openai.RateLimitError, status_code=429,
                          code="insufficient_quota", message="no funds")
        assert _openai_error_code(exc) == "insufficient_quota"

    def test_returns_none_when_body_missing(self):
        import openai
        # APIError accepts a None body shape — should degrade gracefully.
        exc = _openai_exc(openai.RateLimitError, status_code=429,
                          code=None, message="generic")
        assert _openai_error_code(exc) is None


class TestValidateOpenaiSDKExceptions:
    """Use real openai SDK exceptions to verify structured-field reads."""

    def _patched_client(self, monkeypatch, exc):
        import openai
        client = MagicMock()
        client.chat.completions.create.side_effect = exc
        monkeypatch.setattr(openai, "OpenAI", lambda **kw: client)

    def test_insufficient_quota_via_structured_code(self, monkeypatch):
        import openai
        exc = _openai_exc(
            openai.RateLimitError, status_code=429, code="insufficient_quota",
            message="You exceeded your current quota",
        )
        self._patched_client(monkeypatch, exc)
        result = _validate_openai("sk-key", "gpt-4o-mini")
        assert not result.ok
        assert result.error_class == "billing_empty"

    def test_plain_rate_limit_no_quota_code(self, monkeypatch):
        import openai
        exc = _openai_exc(
            openai.RateLimitError, status_code=429, code="rate_limit_exceeded",
            message="429 Too Many Requests",
        )
        self._patched_client(monkeypatch, exc)
        result = _validate_openai("sk-key", "gpt-4o-mini")
        assert not result.ok
        assert result.error_class == "rate_limit"


class TestValidateAzure:
    def _patched_client(self, monkeypatch, exc=None):
        import openai
        client = MagicMock()
        if exc is not None:
            client.chat.completions.create.side_effect = exc
        else:
            client.chat.completions.create.return_value = MagicMock()
        monkeypatch.setattr(openai, "AzureOpenAI", lambda **kw: client)

    def test_ok_path(self, monkeypatch):
        self._patched_client(monkeypatch)
        result = _validate_azure(
            "az-key", "https://x.openai.azure.com/", "gpt-4o", "2024-10-21",
        )
        assert result.ok

    def test_auth_error_maps_to_invalid_key(self, monkeypatch):
        import openai
        exc = _openai_exc(
            openai.AuthenticationError, status_code=401, code="invalid_api_key",
            message="401 unauthorized",
        )
        self._patched_client(monkeypatch, exc)
        result = _validate_azure(
            "bad-key", "https://x.openai.azure.com/", "gpt-4o", "2024-10-21",
        )
        assert not result.ok
        assert result.error_class == "invalid_key"

    def test_deployment_not_found_maps_to_model_unavailable(self, monkeypatch):
        # Headline Azure foot-gun. The downstream-disambiguation contract
        # (raw_message → recovery_message override copy) is tested in
        # test_billing_hints.py, not here — keeps this test loose to a
        # refactor of the raw_message prefix.
        import openai
        exc = _openai_exc(
            openai.NotFoundError, status_code=404, code="DeploymentNotFound",
            message="The API deployment for this resource does not exist.",
        )
        self._patched_client(monkeypatch, exc)
        result = _validate_azure(
            "az-key", "https://x.openai.azure.com/", "missing-deploy", "2024-10-21",
        )
        assert not result.ok
        assert result.error_class == "model_unavailable"

    def test_other_not_found_maps_to_model_unavailable(self, monkeypatch):
        import openai
        exc = _openai_exc(
            openai.NotFoundError, status_code=404, code="model_not_found",
            message="not found",
        )
        self._patched_client(monkeypatch, exc)
        result = _validate_azure(
            "az-key", "https://x.openai.azure.com/", "gpt-4o", "2024-10-21",
        )
        assert not result.ok
        assert result.error_class == "model_unavailable"

    def test_rate_limit_maps_to_rate_limit(self, monkeypatch):
        import openai
        exc = _openai_exc(
            openai.RateLimitError, status_code=429, code=None, message="429",
        )
        self._patched_client(monkeypatch, exc)
        result = _validate_azure(
            "az-key", "https://x.openai.azure.com/", "gpt-4o", "2024-10-21",
        )
        assert not result.ok
        assert result.error_class == "rate_limit"


class TestValidateGoogle:
    def _patched_client(self, monkeypatch, exc=None):
        from google import genai
        models = MagicMock()
        if exc is not None:
            models.generate_content.side_effect = exc
        else:
            models.generate_content.return_value = MagicMock()
        client_instance = MagicMock()
        client_instance.models = models
        monkeypatch.setattr(genai, "Client", lambda **kw: client_instance)

    def _api_error(self, *, code: int, status: str, message: str = "err",
                   details: list | None = None):
        """Build a real google.genai APIError. APIError __init__ takes
        (code, response_json, response=None)."""
        from google.genai import errors as genai_errors
        response_json = {
            "error": {"code": code, "message": message, "status": status,
                      "details": details or []}
        }
        return genai_errors.APIError(code, response_json)

    def test_ok_path(self, monkeypatch):
        self._patched_client(monkeypatch)
        result = _validate_google("g-key", "gemini-2.5-pro")
        assert result.ok

    def test_unauthenticated_maps_to_invalid_key(self, monkeypatch):
        exc = self._api_error(code=401, status="UNAUTHENTICATED")
        self._patched_client(monkeypatch, exc)
        result = _validate_google("bad-key", "gemini-2.5-pro")
        assert not result.ok
        assert result.error_class == "invalid_key"

    def test_api_key_invalid_detail_maps_to_invalid_key(self, monkeypatch):
        # Some failures surface as INVALID_ARGUMENT (400) but carry an
        # API_KEY_INVALID reason in details — still invalid_key.
        exc = self._api_error(
            code=400, status="INVALID_ARGUMENT",
            details=[{"reason": "API_KEY_INVALID"}],
        )
        self._patched_client(monkeypatch, exc)
        result = _validate_google("bad-key", "gemini-2.5-pro")
        assert not result.ok
        assert result.error_class == "invalid_key"

    def test_permission_denied_maps_to_model_unavailable(self, monkeypatch):
        exc = self._api_error(code=403, status="PERMISSION_DENIED")
        self._patched_client(monkeypatch, exc)
        result = _validate_google("g-key", "gemini-2.5-pro")
        assert not result.ok
        assert result.error_class == "model_unavailable"

    def test_resource_exhausted_maps_to_rate_limit(self, monkeypatch):
        exc = self._api_error(code=429, status="RESOURCE_EXHAUSTED")
        self._patched_client(monkeypatch, exc)
        result = _validate_google("g-key", "gemini-2.5-pro")
        assert not result.ok
        assert result.error_class == "rate_limit"

    def test_not_found_maps_to_model_unavailable(self, monkeypatch):
        exc = self._api_error(code=404, status="NOT_FOUND")
        self._patched_client(monkeypatch, exc)
        result = _validate_google("g-key", "fake-model")
        assert not result.ok
        assert result.error_class == "model_unavailable"


class TestValidateLocal:
    def _patched_client(self, monkeypatch, exc=None):
        import openai
        client = MagicMock()
        if exc is not None:
            client.chat.completions.create.side_effect = exc
        else:
            client.chat.completions.create.return_value = MagicMock()
        monkeypatch.setattr(openai, "OpenAI", lambda **kw: client)

    def test_ok_path(self, monkeypatch):
        self._patched_client(monkeypatch)
        result = _validate_local("http://localhost:11434/v1", "llama3.2:3b")
        assert result.ok

    def test_connection_refused_maps_to_network(self, monkeypatch):
        import httpx
        import openai
        # APIConnectionError wraps an httpx error. Construct it via the
        # SDK's documented signature so the test exercises the real class.
        req = httpx.Request("POST", "http://localhost:11434/v1/chat/completions")
        underlying = httpx.ConnectError("Connection refused", request=req)
        exc = openai.APIConnectionError(request=req)
        exc.__cause__ = underlying
        self._patched_client(monkeypatch, exc)
        result = _validate_local("http://localhost:11434/v1", "llama3.2:3b")
        assert not result.ok
        assert result.error_class == "network"

    def test_model_not_pulled_maps_to_model_unavailable(self, monkeypatch):
        import openai
        # Ollama's 404 body is free-text ("model 'foo' not found, try
        # pulling it first").
        exc = _openai_exc(
            openai.NotFoundError, status_code=404, code=None,
            message="model 'foo' not found, try pulling it first",
        )
        self._patched_client(monkeypatch, exc)
        result = _validate_local("http://localhost:11434/v1", "foo")
        assert not result.ok
        assert result.error_class == "model_unavailable"


# ---------------------------------------------------------------------------
# preflight_api_key orchestration
# ---------------------------------------------------------------------------


class TestPreflightApiKey:
    def test_non_tty_still_validates_silently(self, monkeypatch, tmp_path):
        # Non-TTY (CI) must still validate so expired keys abort early —
        # only the first-run *banner* is suppressed in non-TTY runs.
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.sys.stdin.isatty", lambda: False,
        )
        path = tmp_path / "state.json"
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.state_path", lambda: path,
        )
        with patch(
            "bristlenose.preflight.api_key._validate_anthropic",
            return_value=ValidationResult(ok=True),
        ) as validator:
            preflight_api_key(
                settings=_settings(anthropic_api_key="sk"), console=_console(),
            )
        validator.assert_called_once()

    def test_explicit_env_skip(self, monkeypatch):
        monkeypatch.setenv("BRISTLENOSE_SKIP_PREFLIGHT", "1")
        with patch(
            "bristlenose.preflight.api_key._validate_anthropic"
        ) as validator:
            preflight_api_key(
                settings=_settings(anthropic_api_key="sk"), console=_console(),
            )
        validator.assert_not_called()

    def test_local_provider_validates_without_api_key(self, monkeypatch, tmp_path):
        # Local has no key but still runs validation (server-running + model-pulled).
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.sys.stdin.isatty", lambda: True,
        )
        path = tmp_path / "state.json"
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.state_path", lambda: path,
        )
        with patch(
            "bristlenose.preflight.api_key._validate_local",
            return_value=ValidationResult(ok=True),
        ) as validator:
            preflight_api_key(
                settings=_settings(llm_provider="local"),
                console=_console(),
            )
        validator.assert_called_once()

    def test_google_provider_validates_when_key_present(self, monkeypatch, tmp_path):
        # Pin the (api_key, model) call shape — symmetric to the Azure
        # test below; catches silent regressions if the orchestrator's
        # arg threading for google drifts.
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.sys.stdin.isatty", lambda: True,
        )
        path = tmp_path / "state.json"
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.state_path", lambda: path,
        )
        with patch(
            "bristlenose.preflight.api_key._validate_google",
            return_value=ValidationResult(ok=True),
        ) as validator:
            preflight_api_key(
                settings=_settings(
                    llm_provider="google",
                    google_api_key="g-key",
                    llm_model="gemini-2.5-pro",
                ),
                console=_console(),
            )
        validator.assert_called_once_with("g-key", "gemini-2.5-pro")

    def test_azure_provider_validates_when_key_present(self, monkeypatch, tmp_path):
        # Azure now has a real validator — confirm it runs and threads
        # the 4-arg (api_key, endpoint, deployment, api_version) signature.
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.sys.stdin.isatty", lambda: True,
        )
        path = tmp_path / "state.json"
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.state_path", lambda: path,
        )
        with patch(
            "bristlenose.preflight.api_key._validate_azure",
            return_value=ValidationResult(ok=True),
        ) as validator:
            preflight_api_key(
                settings=_settings(llm_provider="azure", azure_api_key="az-key"),
                console=_console(),
            )
        validator.assert_called_once_with(
            "az-key", "https://example.openai.azure.com/", "gpt-4o", "2024-10-21",
        )

    def test_no_key_skips(self, monkeypatch):
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.sys.stdin.isatty", lambda: True,
        )
        with patch(
            "bristlenose.preflight.api_key._validate_anthropic"
        ) as validator:
            preflight_api_key(
                settings=_settings(anthropic_api_key=""),
                console=_console(),
            )
        validator.assert_not_called()

    def test_recent_validation_skips(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.sys.stdin.isatty", lambda: True,
        )
        path = tmp_path / "state.json"
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.state_path", lambda: path,
        )
        path.write_text(
            '{"first_run": false, "providers": '
            f'{{"anthropic": {{"last_validated_epoch": {int(time.time())}}}}}}}',
            encoding="utf-8",
        )
        with patch(
            "bristlenose.preflight.api_key._validate_anthropic"
        ) as validator:
            preflight_api_key(
                settings=_settings(anthropic_api_key="sk"),
                console=_console(),
            )
        validator.assert_not_called()

    def test_ok_writes_state(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.sys.stdin.isatty", lambda: True,
        )
        path = tmp_path / "state.json"
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.state_path", lambda: path,
        )
        with patch(
            "bristlenose.preflight.api_key._validate_anthropic",
            return_value=ValidationResult(ok=True),
        ):
            preflight_api_key(
                settings=_settings(anthropic_api_key="sk"),
                console=_console(),
            )
        assert path.exists()
        state = read_state()
        assert "anthropic" in state["providers"]
        assert state["first_run"] is False

    def test_failure_raises_with_recovery_copy(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.sys.stdin.isatty", lambda: True,
        )
        path = tmp_path / "state.json"
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.state_path", lambda: path,
        )
        with patch(
            "bristlenose.preflight.api_key._validate_anthropic",
            return_value=ValidationResult(
                ok=False, error_class="billing_empty",
                raw_message="credit_balance_too_low",
            ),
        ):
            with pytest.raises(ApiKeyPreflightAbortedError) as exc_info:
                preflight_api_key(
                    settings=_settings(anthropic_api_key="sk"),
                    console=_console(),
                )
        # Recovery copy from billing_hints.recovery_message should be present.
        assert "no API credit" in str(exc_info.value)
        assert "settings/billing" in str(exc_info.value)

    def test_first_run_prints_source_attribution(
        self, monkeypatch, tmp_path, capsys
    ):
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.sys.stdin.isatty", lambda: True,
        )
        path = tmp_path / "state.json"
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.state_path", lambda: path,
        )
        monkeypatch.setenv("BRISTLENOSE_ANTHROPIC_API_KEY", "sk-fromenv")
        with patch(
            "bristlenose.preflight.api_key._validate_anthropic",
            return_value=ValidationResult(ok=True),
        ):
            preflight_api_key(
                settings=_settings(anthropic_api_key="sk-fromenv"),
                console=_console(),
            )
        out = capsys.readouterr().out
        assert "Using Claude API key from env" in out
        assert "Verifying: ~$0.0001" in out

    def test_subsequent_run_silent_after_first(
        self, monkeypatch, tmp_path, capsys
    ):
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.sys.stdin.isatty", lambda: True,
        )
        path = tmp_path / "state.json"
        # State indicates first_run=False (we've validated before) but TTL expired.
        path.write_text(
            '{"first_run": false, "providers": '
            f'{{"anthropic": {{"last_validated_epoch": {int(time.time()) - 25 * 3600}}}}}}}',
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.state_path", lambda: path,
        )
        with patch(
            "bristlenose.preflight.api_key._validate_anthropic",
            return_value=ValidationResult(ok=True),
        ):
            preflight_api_key(
                settings=_settings(anthropic_api_key="sk"),
                console=_console(),
            )
        out = capsys.readouterr().out
        # No "Using ... from" attribution on subsequent runs.
        assert "Using Claude API key from" not in out
