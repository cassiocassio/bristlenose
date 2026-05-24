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
    _validate_anthropic,
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

    def test_local_provider_skips(self, monkeypatch):
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.sys.stdin.isatty", lambda: True,
        )
        with patch(
            "bristlenose.preflight.api_key._validate_anthropic"
        ) as validator:
            preflight_api_key(
                settings=_settings(llm_provider="local"),
                console=_console(),
            )
        validator.assert_not_called()

    def test_azure_provider_falls_through_silently(self, monkeypatch):
        monkeypatch.setattr(
            "bristlenose.preflight.api_key.sys.stdin.isatty", lambda: True,
        )
        # No validator registered for azure → return without raising.
        preflight_api_key(
            settings=_settings(llm_provider="azure"),
            console=_console(),
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
