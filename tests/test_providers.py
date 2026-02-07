"""Tests for LLM provider registry and Ollama support."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bristlenose.config import BristlenoseSettings, load_settings
from bristlenose.providers import (
    PROVIDERS,
    get_provider_aliases,
    resolve_provider,
)

# ---------------------------------------------------------------------------
# Provider registry tests
# ---------------------------------------------------------------------------


class TestProviderSpec:
    def test_anthropic_spec(self) -> None:
        spec = PROVIDERS["anthropic"]
        assert spec.name == "anthropic"
        assert spec.display_name == "Claude"
        assert "claude" in spec.aliases
        assert spec.default_model == "claude-sonnet-4-20250514"
        assert spec.sdk_module == "anthropic"

    def test_openai_spec(self) -> None:
        spec = PROVIDERS["openai"]
        assert spec.name == "openai"
        assert spec.display_name == "ChatGPT"
        assert "chatgpt" in spec.aliases
        assert "gpt" in spec.aliases
        assert spec.default_model == "gpt-4o"
        assert spec.sdk_module == "openai"

    def test_azure_spec(self) -> None:
        spec = PROVIDERS["azure"]
        assert spec.name == "azure"
        assert spec.display_name == "Azure OpenAI"
        assert "azure-openai" in spec.aliases
        assert spec.default_model == ""  # Azure uses deployment names
        assert spec.sdk_module == "openai"
        assert len(spec.config_fields) == 4

    def test_local_spec(self) -> None:
        spec = PROVIDERS["local"]
        assert spec.name == "local"
        assert spec.display_name == "Local (Ollama)"
        assert "ollama" in spec.aliases
        assert spec.default_model == "llama3.2:3b"
        assert spec.sdk_module == "openai"  # Ollama is OpenAI-compatible
        assert spec.pricing_url == ""  # Free


class TestResolveProvider:
    def test_canonical_names(self) -> None:
        assert resolve_provider("anthropic") == "anthropic"
        assert resolve_provider("openai") == "openai"
        assert resolve_provider("azure") == "azure"
        assert resolve_provider("local") == "local"

    def test_aliases(self) -> None:
        assert resolve_provider("claude") == "anthropic"
        assert resolve_provider("chatgpt") == "openai"
        assert resolve_provider("gpt") == "openai"
        assert resolve_provider("azure-openai") == "azure"
        assert resolve_provider("ollama") == "local"

    def test_case_insensitive(self) -> None:
        assert resolve_provider("Claude") == "anthropic"
        assert resolve_provider("CHATGPT") == "openai"
        assert resolve_provider("Azure") == "azure"
        assert resolve_provider("Ollama") == "local"

    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            resolve_provider("gemini")

    def test_error_message_lists_valid_providers(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            resolve_provider("unknown")
        msg = str(exc_info.value)
        assert "anthropic" in msg
        assert "openai" in msg
        assert "azure" in msg
        assert "local" in msg


class TestGetProviderAliases:
    def test_returns_alias_dict(self) -> None:
        aliases = get_provider_aliases()
        assert aliases["claude"] == "anthropic"
        assert aliases["chatgpt"] == "openai"
        assert aliases["gpt"] == "openai"
        assert aliases["azure-openai"] == "azure"
        assert aliases["ollama"] == "local"


# ---------------------------------------------------------------------------
# Config integration tests
# ---------------------------------------------------------------------------


class TestConfigProviderAliases:
    def test_load_settings_normalises_claude(self) -> None:
        settings = load_settings(llm_provider="claude")
        assert settings.llm_provider == "anthropic"

    def test_load_settings_normalises_chatgpt(self) -> None:
        settings = load_settings(llm_provider="chatgpt")
        assert settings.llm_provider == "openai"

    def test_load_settings_normalises_azure_openai(self) -> None:
        settings = load_settings(llm_provider="azure-openai")
        assert settings.llm_provider == "azure"

    def test_load_settings_normalises_ollama(self) -> None:
        settings = load_settings(llm_provider="ollama")
        assert settings.llm_provider == "local"

    def test_load_settings_preserves_canonical(self) -> None:
        settings = load_settings(llm_provider="local")
        assert settings.llm_provider == "local"

    def test_local_settings_defaults(self) -> None:
        settings = load_settings(llm_provider="local")
        assert settings.local_url == "http://localhost:11434/v1"
        assert settings.local_model == "llama3.2:3b"


# ---------------------------------------------------------------------------
# Ollama helper tests
# ---------------------------------------------------------------------------


class TestOllamaHelpers:
    def test_check_ollama_not_running(self) -> None:
        import urllib.error

        from bristlenose.ollama import check_ollama

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            status = check_ollama()

        assert status.is_running is False
        assert status.has_suitable_model is False
        assert status.recommended_model is None
        assert "not running" in status.message

    def test_check_ollama_running_with_model(self) -> None:
        import json

        from bristlenose.ollama import check_ollama

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "models": [
                {"name": "llama3.2:3b"},
                {"name": "mistral:7b"},
            ]
        }).encode()
        mock_response.__enter__ = lambda self: self
        mock_response.__exit__ = lambda *args: None

        with patch("urllib.request.urlopen", return_value=mock_response):
            status = check_ollama()

        assert status.is_running is True
        assert status.has_suitable_model is True
        assert status.recommended_model == "llama3.2:3b"
        assert "llama3.2:3b" in status.message

    def test_check_ollama_running_no_suitable_model(self) -> None:
        import json

        from bristlenose.ollama import check_ollama

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "models": [
                {"name": "phi:2.7b"},  # Not in preferred list
            ]
        }).encode()
        mock_response.__enter__ = lambda self: self
        mock_response.__exit__ = lambda *args: None

        with patch("urllib.request.urlopen", return_value=mock_response):
            status = check_ollama()

        assert status.is_running is True
        assert status.has_suitable_model is False
        assert status.recommended_model is None

    def test_is_ollama_installed_true(self) -> None:
        from bristlenose.ollama import is_ollama_installed

        with patch("shutil.which", return_value="/usr/local/bin/ollama"):
            assert is_ollama_installed() is True

    def test_is_ollama_installed_false(self) -> None:
        from bristlenose.ollama import is_ollama_installed

        with patch("shutil.which", return_value=None):
            assert is_ollama_installed() is False

    def test_get_install_method_macos_with_brew(self) -> None:
        from bristlenose.ollama import get_install_method

        with (
            patch("platform.system", return_value="Darwin"),
            patch("shutil.which", side_effect=lambda cmd: "/usr/local/bin/brew" if cmd == "brew" else None),
        ):
            assert get_install_method() == "brew"

    def test_get_install_method_macos_without_brew(self) -> None:
        from bristlenose.ollama import get_install_method

        with (
            patch("platform.system", return_value="Darwin"),
            patch("shutil.which", side_effect=lambda cmd: "/usr/bin/curl" if cmd == "curl" else None),
        ):
            assert get_install_method() == "curl"

    def test_get_install_method_linux_with_snap(self) -> None:
        from bristlenose.ollama import get_install_method

        with (
            patch("platform.system", return_value="Linux"),
            patch("shutil.which", side_effect=lambda cmd: "/usr/bin/snap" if cmd == "snap" else None),
        ):
            assert get_install_method() == "snap"

    def test_get_install_method_linux_without_snap(self) -> None:
        from bristlenose.ollama import get_install_method

        with (
            patch("platform.system", return_value="Linux"),
            patch("shutil.which", side_effect=lambda cmd: "/usr/bin/curl" if cmd == "curl" else None),
        ):
            assert get_install_method() == "curl"

    def test_get_install_method_windows(self) -> None:
        from bristlenose.ollama import get_install_method

        with patch("platform.system", return_value="Windows"):
            assert get_install_method() is None

    def test_install_ollama_brew(self) -> None:
        from bristlenose.ollama import install_ollama

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert install_ollama("brew") is True
            mock_run.assert_called_once()
            assert mock_run.call_args[0][0] == ["brew", "install", "ollama"]

    def test_install_ollama_snap(self) -> None:
        from bristlenose.ollama import install_ollama

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert install_ollama("snap") is True
            mock_run.assert_called_once()
            assert mock_run.call_args[0][0] == ["sudo", "snap", "install", "ollama"]

    def test_install_ollama_curl(self) -> None:
        from bristlenose.ollama import install_ollama

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert install_ollama("curl") is True
            mock_run.assert_called_once()

    def test_install_ollama_no_method(self) -> None:
        from bristlenose.ollama import install_ollama

        with patch("bristlenose.ollama.get_install_method", return_value=None):
            assert install_ollama() is False

    def test_start_ollama_serve_macos_app(self) -> None:
        """On macOS with Ollama.app, should use 'open -a Ollama'."""
        from bristlenose.ollama import start_ollama_serve

        with (
            patch("bristlenose.ollama.get_ollama_install_method", return_value="app"),
            patch("subprocess.Popen") as mock_popen,
            patch("time.sleep"),
            patch("bristlenose.ollama.check_ollama") as mock_check,
        ):
            mock_check.return_value = MagicMock(is_running=True)
            assert start_ollama_serve() is True
            mock_popen.assert_called_once()
            assert mock_popen.call_args[0][0] == ["open", "-a", "Ollama"]

    def test_start_ollama_serve_macos_brew(self) -> None:
        """On macOS with Homebrew, should use 'brew services start ollama'."""
        from bristlenose.ollama import start_ollama_serve

        with (
            patch("bristlenose.ollama.get_ollama_install_method", return_value="brew"),
            patch("subprocess.run") as mock_run,
            patch("time.sleep"),
            patch("bristlenose.ollama.check_ollama") as mock_check,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            mock_check.return_value = MagicMock(is_running=True)
            assert start_ollama_serve() is True
            mock_run.assert_called_once()
            assert mock_run.call_args[0][0] == ["brew", "services", "start", "ollama"]

    def test_start_ollama_serve_linux_generic(self) -> None:
        """On Linux with generic install, should use 'ollama serve'."""
        from bristlenose.ollama import start_ollama_serve

        with (
            patch("bristlenose.ollama.get_ollama_install_method", return_value=None),
            patch("subprocess.Popen") as mock_popen,
            patch("time.sleep"),
            patch("bristlenose.ollama.check_ollama") as mock_check,
        ):
            mock_check.return_value = MagicMock(is_running=True)
            assert start_ollama_serve() is True
            mock_popen.assert_called_once()
            assert mock_popen.call_args[0][0] == ["ollama", "serve"]

    def test_start_ollama_serve_linux_systemd(self) -> None:
        """On Linux with systemd service, should use 'systemctl start ollama'."""
        from bristlenose.ollama import start_ollama_serve

        with (
            patch("bristlenose.ollama.get_ollama_install_method", return_value="systemd"),
            patch("subprocess.run") as mock_run,
            patch("time.sleep"),
            patch("bristlenose.ollama.check_ollama") as mock_check,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            mock_check.return_value = MagicMock(is_running=True)
            assert start_ollama_serve() is True
            mock_run.assert_called_once()
            assert mock_run.call_args[0][0] == ["systemctl", "start", "ollama"]

    def test_validate_local_endpoint_success(self) -> None:
        import json

        from bristlenose.ollama import validate_local_endpoint

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "models": [{"name": "llama3.2:3b"}]
        }).encode()
        mock_response.__enter__ = lambda self: self
        mock_response.__exit__ = lambda *args: None

        with patch("urllib.request.urlopen", return_value=mock_response):
            valid, err = validate_local_endpoint(
                "http://localhost:11434/v1", "llama3.2:3b"
            )

        assert valid is True
        assert err == ""

    def test_validate_local_endpoint_model_not_found(self) -> None:
        import json

        from bristlenose.ollama import validate_local_endpoint

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "models": [{"name": "mistral:7b"}]
        }).encode()
        mock_response.__enter__ = lambda self: self
        mock_response.__exit__ = lambda *args: None

        with patch("urllib.request.urlopen", return_value=mock_response):
            valid, err = validate_local_endpoint(
                "http://localhost:11434/v1", "llama3.2:3b"
            )

        assert valid is False
        assert "not found" in err

    def test_validate_local_endpoint_not_reachable_installed(self) -> None:
        import urllib.error

        from bristlenose.ollama import validate_local_endpoint

        with (
            patch(
                "urllib.request.urlopen",
                side_effect=urllib.error.URLError("Connection refused"),
            ),
            patch("bristlenose.ollama.is_ollama_installed", return_value=True),
        ):
            valid, err = validate_local_endpoint(
                "http://localhost:11434/v1", "llama3.2:3b"
            )

        assert valid is None
        assert "installed but not running" in err

    def test_validate_local_endpoint_not_reachable_not_installed(self) -> None:
        import urllib.error

        from bristlenose.ollama import validate_local_endpoint

        with (
            patch(
                "urllib.request.urlopen",
                side_effect=urllib.error.URLError("Connection refused"),
            ),
            patch("bristlenose.ollama.is_ollama_installed", return_value=False),
        ):
            valid, err = validate_local_endpoint(
                "http://localhost:11434/v1", "llama3.2:3b"
            )

        assert valid is None
        assert "not installed" in err


# ---------------------------------------------------------------------------
# Doctor integration tests for local provider
# ---------------------------------------------------------------------------


def _settings(**overrides: object) -> BristlenoseSettings:
    """Create settings with safe defaults for testing."""
    defaults: dict[str, object] = {
        "llm_provider": "local",
        "local_url": "http://localhost:11434/v1",
        "local_model": "llama3.2:3b",
        "output_dir": Path("/tmp/bristlenose-test-output"),
    }
    defaults.update(overrides)
    return BristlenoseSettings(**defaults)  # type: ignore[arg-type]


class TestDoctorLocalProvider:
    def test_check_api_key_local_provider_ok(self) -> None:
        from bristlenose.doctor import check_api_key

        settings = _settings()
        with patch(
            "bristlenose.doctor.check_local_provider"
        ) as mock_check:
            mock_check.return_value = MagicMock(status="ok")
            _ = check_api_key(settings)

        # Should delegate to check_local_provider
        mock_check.assert_called_once_with(settings)

    def test_check_local_provider_ollama_running(self) -> None:
        from bristlenose.doctor import CheckStatus, check_local_provider

        settings = _settings()
        with patch(
            "bristlenose.ollama.validate_local_endpoint",
            return_value=(True, ""),
        ):
            result = check_local_provider(settings)

        assert result.status == CheckStatus.OK
        assert "llama3.2:3b" in result.detail
        assert "Ollama" in result.detail

    def test_check_local_provider_model_missing(self) -> None:
        from bristlenose.doctor import CheckStatus, check_local_provider

        settings = _settings()
        with patch(
            "bristlenose.ollama.validate_local_endpoint",
            return_value=(False, "Model 'llama3.2:3b' not found"),
        ):
            result = check_local_provider(settings)

        assert result.status == CheckStatus.FAIL
        assert result.fix_key == "ollama_model_missing"

    def test_check_local_provider_not_running(self) -> None:
        from bristlenose.doctor import CheckStatus, check_local_provider

        settings = _settings()
        with patch(
            "bristlenose.ollama.validate_local_endpoint",
            return_value=(None, "Ollama is installed but not running"),
        ):
            result = check_local_provider(settings)

        assert result.status == CheckStatus.FAIL
        assert result.fix_key == "ollama_not_running"

    def test_check_local_provider_not_installed(self) -> None:
        from bristlenose.doctor import CheckStatus, check_local_provider

        settings = _settings()
        with patch(
            "bristlenose.ollama.validate_local_endpoint",
            return_value=(None, "Ollama is not installed"),
        ):
            result = check_local_provider(settings)

        assert result.status == CheckStatus.FAIL
        assert result.fix_key == "ollama_not_installed"

    def test_check_network_skipped_for_local(self) -> None:
        from bristlenose.doctor import CheckStatus, check_network

        settings = _settings()
        result = check_network(settings)

        assert result.status == CheckStatus.SKIP
        assert "local provider" in result.detail


class TestDoctorFixesOllama:
    def test_fix_ollama_not_running(self) -> None:
        from unittest.mock import patch

        from bristlenose.doctor_fixes import get_fix

        # Mock get_start_command to return generic "ollama serve" for test consistency
        with patch(
            "bristlenose.ollama.get_start_command",
            return_value=(["ollama", "serve"], "ollama serve"),
        ):
            fix = get_fix("ollama_not_running", "pip")
        assert "Start Ollama" in fix
        assert "ollama serve" in fix
        # Cloud fallback hint should be present (varies based on available keys)
        assert "cloud" in fix.lower() or "claude" in fix.lower() or "console.anthropic.com" in fix

    def test_fix_ollama_not_installed(self) -> None:
        from bristlenose.doctor_fixes import get_fix

        fix = get_fix("ollama_not_installed", "pip")
        assert "ollama.ai" in fix
        # Auto-start message instead of manual command (we can't know the start
        # command before Ollama is installed)
        assert "bristlenose will start it automatically" in fix
        # Cloud fallback hint should be present
        assert "cloud" in fix.lower() or "claude" in fix.lower() or "console.anthropic.com" in fix

    def test_fix_ollama_model_missing(self) -> None:
        from bristlenose.doctor_fixes import get_fix

        fix = get_fix("ollama_model_missing", "pip")
        assert "ollama pull" in fix
        # Cloud fallback hint should be present
        assert "cloud" in fix.lower() or "claude" in fix.lower() or "console.anthropic.com" in fix

    def test_cloud_fallback_with_anthropic_key(self) -> None:
        """When user has Anthropic key, suggest --llm claude."""
        from bristlenose.doctor_fixes import get_fix

        with patch(
            "bristlenose.config.load_settings",
            return_value=MagicMock(
                anthropic_api_key="sk-ant-xxx", openai_api_key="",
                azure_api_key="", azure_endpoint="",
            ),
        ):
            fix = get_fix("ollama_not_running", "pip")
            assert "--llm claude" in fix

    def test_cloud_fallback_with_openai_key(self) -> None:
        """When user has only OpenAI key, suggest --llm chatgpt."""
        from bristlenose.doctor_fixes import get_fix

        with patch(
            "bristlenose.config.load_settings",
            return_value=MagicMock(
                anthropic_api_key="", openai_api_key="sk-xxx",
                azure_api_key="", azure_endpoint="",
            ),
        ):
            fix = get_fix("ollama_not_running", "pip")
            assert "--llm chatgpt" in fix

    def test_cloud_fallback_with_both_keys(self) -> None:
        """When user has both keys, suggest both options."""
        from bristlenose.doctor_fixes import get_fix

        with patch(
            "bristlenose.config.load_settings",
            return_value=MagicMock(
                anthropic_api_key="sk-ant-xxx", openai_api_key="sk-xxx",
                azure_api_key="", azure_endpoint="",
            ),
        ):
            fix = get_fix("ollama_not_running", "pip")
            assert "--llm claude" in fix
            assert "--llm chatgpt" in fix

    def test_cloud_fallback_with_no_keys(self) -> None:
        """When user has no keys, suggest getting a Claude key."""
        from bristlenose.doctor_fixes import get_fix

        with patch(
            "bristlenose.config.load_settings",
            return_value=MagicMock(
                anthropic_api_key="", openai_api_key="",
                azure_api_key="", azure_endpoint="",
            ),
        ):
            fix = get_fix("ollama_not_running", "pip")
            assert "console.anthropic.com" in fix
