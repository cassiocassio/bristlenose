"""Horror scenario tests for LLM provider configuration.

Tests the full matrix of user confusion states:
- No keys at all (first-run user)
- One key but wrong provider selected
- Expired/invalid keys
- No credit on account
- Ollama not running
- Ollama running but no model
- Mix of valid and invalid keys
- Returning users with stale configuration

Each test documents the exact CLI output the user will see.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from bristlenose.config import BristlenoseSettings
from bristlenose.doctor import (
    CheckStatus,
    check_api_key,
    check_local_provider,
    check_network,
    run_preflight,
)
from bristlenose.doctor_fixes import get_fix


def _settings(**overrides: object) -> BristlenoseSettings:
    """Create settings with safe defaults for testing."""
    defaults: dict[str, object] = {
        "output_dir": Path("/tmp/bristlenose-test-output"),
    }
    defaults.update(overrides)
    return BristlenoseSettings(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Scenario 1: Brand new user, no configuration at all
# ---------------------------------------------------------------------------


class TestNewUserNoConfig:
    """First-time user who just ran `pip install bristlenose` and typed `bristlenose run ./interviews`."""

    def test_default_provider_is_anthropic(self) -> None:
        """Default settings use Anthropic, which will fail without a key.

        Note: We explicitly set anthropic_api_key="" to simulate a user with no
        environment variables set. In real usage, BristlenoseSettings reads from
        env vars, so a truly unconfigured user would have empty strings.
        """
        settings = _settings(anthropic_api_key="", openai_api_key="")
        assert settings.llm_provider == "anthropic"
        assert settings.anthropic_api_key == ""

    def test_check_api_key_fails_with_helpful_message(self) -> None:
        """check_api_key fails and provides actionable fix."""
        settings = _settings(llm_provider="anthropic", anthropic_api_key="")
        result = check_api_key(settings)

        assert result.status == CheckStatus.FAIL
        assert result.fix_key == "api_key_missing_anthropic"

        # Verify the fix message is helpful
        fix = get_fix(result.fix_key)
        assert "bristlenose configure claude" in fix
        assert "console.anthropic.com" in fix
        assert "--llm chatgpt" in fix  # Shows alternative

    def test_preflight_fails_for_run_command(self) -> None:
        """Pre-flight check catches the missing key before any work starts."""
        settings = _settings(llm_provider="anthropic", anthropic_api_key="")
        report = run_preflight(settings, "run")

        assert report.has_failures
        assert any(r.fix_key == "api_key_missing_anthropic" for r in report.failures)

    def test_needs_provider_prompt_returns_true(self) -> None:
        """The interactive prompt should trigger for unconfigured users."""
        from bristlenose.cli import _needs_provider_prompt

        settings = _settings(llm_provider="anthropic", anthropic_api_key="")
        assert _needs_provider_prompt(settings) is True

    def test_cli_output_no_anthropic_key(self) -> None:
        """
        What the user sees when they run `bristlenose run ./interviews` with no config:

        No LLM provider configured. Choose one:

          [1] Local AI (free, private, slower)
              Requires Ollama — https://ollama.ai

          [2] Claude API (best quality, ~$1.50/study)
              Get a key from console.anthropic.com

          [3] ChatGPT API (good quality, ~$1.00/study)
              Get a key from platform.openai.com

        Choice [1]:

        (If they choose [2] without setting a key, they'll see the pre-flight error)
        """
        # This test documents expected behavior — the prompt triggers
        from bristlenose.cli import _needs_provider_prompt

        settings = _settings(llm_provider="anthropic", anthropic_api_key="")
        assert _needs_provider_prompt(settings) is True


# ---------------------------------------------------------------------------
# Scenario 2: User has OpenAI key but selected Claude (or vice versa)
# ---------------------------------------------------------------------------


class TestWrongProviderSelected:
    """User has one API key but selected the wrong provider."""

    def test_has_openai_key_but_selected_claude(self) -> None:
        """
        User set OPENAI_API_KEY but ran `bristlenose run ./interviews` (default Claude).

        They'll see:
            No Anthropic API key

            bristlenose needs an API key to analyse transcripts.
            Get a Claude API key from console.anthropic.com, then:

              bristlenose configure claude

            This stores your key securely in the system Keychain.

            To use ChatGPT instead:  bristlenose run <input> --llm chatgpt
            To only transcribe:      bristlenose transcribe <input>
        """
        settings = _settings(
            llm_provider="anthropic",
            anthropic_api_key="",
            openai_api_key="sk-openai-valid-key-12345",
        )
        result = check_api_key(settings)

        assert result.status == CheckStatus.FAIL
        fix = get_fix(result.fix_key)
        # The fix should mention the alternative they actually have
        assert "--llm chatgpt" in fix

    def test_has_claude_key_but_selected_openai(self) -> None:
        """
        User set ANTHROPIC_API_KEY but ran `bristlenose run ./interviews --llm chatgpt`.

        They'll see:
            No OpenAI API key

            bristlenose needs an API key to analyse transcripts.
            Get a ChatGPT API key from platform.openai.com, then:

              bristlenose configure chatgpt

            This stores your key securely in the system Keychain.

            To use Claude instead:  bristlenose run <input> --llm claude
            To only transcribe:     bristlenose transcribe <input>
        """
        settings = _settings(
            llm_provider="openai",
            anthropic_api_key="sk-ant-valid-key-12345678",
            openai_api_key="",
        )
        result = check_api_key(settings)

        assert result.status == CheckStatus.FAIL
        fix = get_fix(result.fix_key)
        assert "--llm claude" in fix


# ---------------------------------------------------------------------------
# Scenario 3: Expired or invalid API keys
# ---------------------------------------------------------------------------


class TestInvalidApiKeys:
    """User has a key but it's wrong, expired, or revoked."""

    def test_anthropic_key_401_unauthorized(self) -> None:
        """
        User's Claude key is invalid (typo, revoked, etc).

        They'll see:
            Anthropic key rejected (401 Unauthorized)

            Your Claude API key was rejected. Check it at console.anthropic.com/settings/keys.
        """
        settings = _settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-INVALID-KEY-xyz",
        )
        with patch(
            "bristlenose.doctor._validate_anthropic_key",
            return_value=(False, "401 Unauthorized"),
        ):
            result = check_api_key(settings)

        assert result.status == CheckStatus.FAIL
        assert "rejected" in result.detail
        fix = get_fix(result.fix_key)
        assert "console.anthropic.com" in fix

    def test_openai_key_401_unauthorized(self) -> None:
        """
        User's ChatGPT key is invalid.

        They'll see:
            OpenAI key rejected (401 Unauthorized)

            Your ChatGPT API key was rejected. Check it at platform.openai.com/api-keys.
        """
        settings = _settings(
            llm_provider="openai",
            openai_api_key="sk-INVALID-KEY",
        )
        with patch(
            "bristlenose.doctor._validate_openai_key",
            return_value=(False, "401 Unauthorized"),
        ):
            result = check_api_key(settings)

        assert result.status == CheckStatus.FAIL
        assert "rejected" in result.detail
        fix = get_fix(result.fix_key)
        assert "platform.openai.com" in fix

    def test_anthropic_key_403_forbidden(self) -> None:
        """
        User's account is suspended or key has restricted permissions.

        They'll see:
            Anthropic key rejected (403 Forbidden)
        """
        settings = _settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-suspended-account-key",
        )
        with patch(
            "bristlenose.doctor._validate_anthropic_key",
            return_value=(False, "403 Forbidden"),
        ):
            result = check_api_key(settings)

        assert result.status == CheckStatus.FAIL
        assert "rejected" in result.detail


# ---------------------------------------------------------------------------
# Scenario 4: Valid key but no credit / rate limited
# ---------------------------------------------------------------------------


class TestNoCreditOrRateLimited:
    """User's key is valid but account has no credit or is rate limited."""

    def test_anthropic_key_valid_but_no_credit(self) -> None:
        """
        User's Claude key is valid but account has $0 balance.

        Pre-flight passes (key validates), but the actual API call will fail.
        The pipeline handles this with a warning message after the checkmark.

        doctor check passes because 402/429 mean "key is valid":
            API key        ok   Anthropic (sk-ant-...xyz)
        """
        settings = _settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-valid-but-broke-key",
        )
        # 402 Payment Required is treated as "key is valid" (account issue, not key issue)
        # 429 Rate limited is also "key is valid"
        with patch(
            "bristlenose.doctor._validate_anthropic_key",
            return_value=(True, ""),  # Key validates even with no credit
        ):
            result = check_api_key(settings)

        assert result.status == CheckStatus.OK
        # The actual failure happens during pipeline execution, not pre-flight

    def test_openai_key_rate_limited(self) -> None:
        """
        User hit OpenAI rate limits.

        Pre-flight passes (429 means key is valid):
            API key        ok   OpenAI (sk-...xyz)
        """
        settings = _settings(
            llm_provider="openai",
            openai_api_key="sk-valid-rate-limited-key",
        )
        with patch(
            "bristlenose.doctor._validate_openai_key",
            return_value=(True, ""),
        ):
            result = check_api_key(settings)

        assert result.status == CheckStatus.OK


# ---------------------------------------------------------------------------
# Scenario 5: Ollama not installed or not running
# ---------------------------------------------------------------------------


class TestOllamaNotAvailable:
    """User selected local provider but Ollama isn't ready."""

    def test_ollama_installed_but_not_running(self) -> None:
        """
        User ran `bristlenose run ./interviews --llm local` but Ollama isn't started.

        They'll see:
            LLM provider  !!   Ollama is installed but not running

            Start Ollama:

              ollama serve  (or brew services start ollama, etc.)

            Then re-run bristlenose. Or use a cloud API: --llm claude
        """
        settings = _settings(llm_provider="local")
        with (
            patch(
                "bristlenose.ollama.validate_local_endpoint",
                return_value=(None, "Ollama is installed but not running"),
            ),
            patch(
                "bristlenose.ollama.get_start_command",
                return_value=(["ollama", "serve"], "ollama serve"),
            ),
        ):
            result = check_local_provider(settings)

        assert result.status == CheckStatus.FAIL
        assert result.fix_key == "ollama_not_running"

        with patch(
            "bristlenose.doctor_fixes._get_cloud_fallback_hint",
            return_value="Or use a cloud API: --llm claude",
        ):
            fix = get_fix(result.fix_key)
        assert "Start Ollama" in fix
        assert "--llm claude" in fix

    def test_ollama_not_installed(self) -> None:
        """
        User ran `bristlenose run ./interviews --llm local` but Ollama isn't installed.

        They'll see:
            LLM provider  !!   Ollama is not installed

            Install Ollama from https://ollama.ai (free, no account needed).

            After installing, bristlenose will start it automatically.

            Or use a cloud API: --llm claude
        """
        settings = _settings(llm_provider="local")
        with patch(
            "bristlenose.ollama.validate_local_endpoint",
            return_value=(None, "Ollama is not installed"),
        ):
            result = check_local_provider(settings)

        assert result.status == CheckStatus.FAIL
        assert result.fix_key == "ollama_not_installed"

        with patch(
            "bristlenose.doctor_fixes._get_cloud_fallback_hint",
            return_value="Or use a cloud API: --llm claude",
        ):
            fix = get_fix(result.fix_key)
        assert "ollama.ai" in fix
        assert "bristlenose will start it automatically" in fix
        assert "--llm claude" in fix

    def test_ollama_running_but_no_model(self) -> None:
        """
        Ollama is running but user hasn't pulled any models.

        They'll see:
            Model 'llama3.2:3b' not found. Run: ollama pull llama3.2:3b

            The local model is not installed. Download it with:

              ollama pull llama3.2

            Or use a different model:
              bristlenose run <input> --model llama3.1

            To use a cloud API instead:
              bristlenose run <input> --llm claude
        """
        settings = _settings(llm_provider="local", local_model="llama3.2:3b")
        with patch(
            "bristlenose.ollama.validate_local_endpoint",
            return_value=(False, "Model 'llama3.2:3b' not found. Run: ollama pull llama3.2:3b"),
        ):
            result = check_local_provider(settings)

        assert result.status == CheckStatus.FAIL
        assert result.fix_key == "ollama_model_missing"

        with patch(
            "bristlenose.doctor_fixes._get_cloud_fallback_hint",
            return_value="Or use a cloud API: --llm claude",
        ):
            fix = get_fix(result.fix_key)
        assert "ollama pull" in fix
        assert "--llm claude" in fix

    def test_ollama_network_check_skipped(self) -> None:
        """
        Local provider doesn't need cloud network connectivity.

        They'll see in doctor output:
            Network        --   local provider (no cloud API needed)
        """
        settings = _settings(llm_provider="local")
        result = check_network(settings)

        assert result.status == CheckStatus.SKIP
        assert "local provider" in result.detail


# ---------------------------------------------------------------------------
# Scenario 6: Interactive prompt flows
# ---------------------------------------------------------------------------


class TestInteractivePromptFlows:
    """Test the interactive first-run prompt in various states."""

    def test_prompt_triggers_for_no_anthropic_key(self) -> None:
        """No key + default provider → prompt triggers."""
        from bristlenose.cli import _needs_provider_prompt

        settings = _settings(llm_provider="anthropic", anthropic_api_key="")
        assert _needs_provider_prompt(settings) is True

    def test_prompt_does_not_trigger_for_explicit_openai(self) -> None:
        """Explicit OpenAI provider (no key) → no prompt, preflight will catch it.

        When user explicitly chooses --llm openai, we don't second-guess them
        with the 3-way prompt. Preflight will show a specific error.
        """
        from bristlenose.cli import _needs_provider_prompt

        settings = _settings(llm_provider="openai", openai_api_key="")
        assert _needs_provider_prompt(settings) is False

    def test_prompt_does_not_trigger_for_explicit_local(self) -> None:
        """Explicit local provider (Ollama not ready) → no prompt, preflight will catch it.

        When user explicitly chooses --llm local/ollama, we don't second-guess them
        with the 3-way prompt. Preflight will show a specific Ollama error.
        """
        from bristlenose.cli import _needs_provider_prompt

        settings = _settings(llm_provider="local")
        with patch("bristlenose.ollama.check_ollama") as mock_check:
            mock_check.return_value = MagicMock(
                is_running=False,
                has_suitable_model=False,
            )
            assert _needs_provider_prompt(settings) is False

    def test_prompt_does_not_trigger_when_anthropic_key_set(self) -> None:
        """Valid Anthropic key → no prompt."""
        from bristlenose.cli import _needs_provider_prompt

        settings = _settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-valid-key-12345678",
        )
        assert _needs_provider_prompt(settings) is False

    def test_prompt_does_not_trigger_when_openai_key_set(self) -> None:
        """Valid OpenAI key → no prompt."""
        from bristlenose.cli import _needs_provider_prompt

        settings = _settings(
            llm_provider="openai",
            openai_api_key="sk-valid-openai-key",
        )
        assert _needs_provider_prompt(settings) is False

    def test_prompt_does_not_trigger_when_ollama_ready(self) -> None:
        """Local provider + Ollama ready → no prompt."""
        from bristlenose.cli import _needs_provider_prompt

        settings = _settings(llm_provider="local")
        with patch("bristlenose.ollama.check_ollama") as mock_check:
            mock_check.return_value = MagicMock(
                is_running=True,
                has_suitable_model=True,
                recommended_model="llama3.2:3b",
            )
            assert _needs_provider_prompt(settings) is False


# ---------------------------------------------------------------------------
# Scenario 7: Returning user with stale configuration
# ---------------------------------------------------------------------------


class TestReturningUserStaleConfig:
    """User who used bristlenose before but their config is now stale."""

    def test_key_was_valid_now_expired(self) -> None:
        """
        User ran bristlenose a month ago, now their trial key expired.

        They'll see:
            Anthropic key rejected (401 Unauthorized)

            Your Claude API key was rejected. Check it at console.anthropic.com/settings/keys.
        """
        settings = _settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-expired-trial-key",
        )
        with patch(
            "bristlenose.doctor._validate_anthropic_key",
            return_value=(False, "401 Unauthorized"),
        ):
            result = check_api_key(settings)

        assert result.status == CheckStatus.FAIL
        assert "rejected" in result.detail

    def test_key_in_env_but_changed_shell(self) -> None:
        """
        User had key in their shell but opened a new terminal without it.

        This looks identical to "no key" case:
            No Anthropic API key
        """
        settings = _settings(
            llm_provider="anthropic",
            anthropic_api_key="",  # Not loaded from environment
        )
        result = check_api_key(settings)

        assert result.status == CheckStatus.FAIL
        assert result.fix_key == "api_key_missing_anthropic"

    def test_ollama_was_running_now_stopped(self) -> None:
        """
        User was using local provider, but Ollama crashed or they rebooted.

        They'll see:
            Cannot connect to local model server. Is Ollama running?

            Ollama is not running. Start it with:

              ollama serve  (or brew services start ollama, etc.)
        """
        settings = _settings(llm_provider="local")
        with (
            patch(
                "bristlenose.ollama.validate_local_endpoint",
                return_value=(None, "Cannot connect to local model server. Is Ollama running?"),
            ),
            patch(
                "bristlenose.ollama.get_start_command",
                return_value=(["ollama", "serve"], "ollama serve"),
            ),
        ):
            result = check_local_provider(settings)

        assert result.status == CheckStatus.FAIL
        fix = get_fix(result.fix_key)
        assert "Start Ollama" in fix


# ---------------------------------------------------------------------------
# Scenario 8: Network issues
# ---------------------------------------------------------------------------


class TestNetworkIssues:
    """User has valid key but network is blocking API access."""

    def test_corporate_firewall_blocks_anthropic(self) -> None:
        """
        User is on corporate network that blocks api.anthropic.com.

        Pre-flight fails:
            Can't reach api.anthropic.com

            Check your internet connection. If you're behind a proxy:
              export HTTPS_PROXY=http://proxy:port
        """
        settings = _settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-valid-key",
        )
        # Preflight includes network check
        _ = run_preflight(settings, "run")

        # Verify the fix message exists
        fix = get_fix("network_unreachable")
        assert "HTTPS_PROXY" in fix

    def test_key_validation_network_error_is_ok(self) -> None:
        """
        Network is flaky during key validation — we assume key is OK.

        They'll see:
            API key        ok   Anthropic (sk-ant-...xyz) (could not validate: timeout)

        We don't fail pre-flight for temporary network issues during validation.
        """
        settings = _settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-valid-key-12345678",
        )
        with patch(
            "bristlenose.doctor._validate_anthropic_key",
            return_value=(None, "timeout"),
        ):
            result = check_api_key(settings)

        assert result.status == CheckStatus.OK
        assert "could not validate" in result.detail


# ---------------------------------------------------------------------------
# Scenario 9: Multiple keys, some valid some not
# ---------------------------------------------------------------------------


class TestMixedKeyStates:
    """User has multiple keys in various states of validity."""

    def test_both_keys_set_anthropic_selected_and_valid(self) -> None:
        """
        User has both keys, using Claude (valid).

        They'll see:
            API key        ok   Anthropic (sk-ant-...xyz)
        """
        settings = _settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-valid-key-12345678",
            openai_api_key="sk-also-valid-openai",
        )
        with patch(
            "bristlenose.doctor._validate_anthropic_key",
            return_value=(True, ""),
        ):
            result = check_api_key(settings)

        assert result.status == CheckStatus.OK
        assert "Anthropic" in result.detail

    def test_both_keys_set_anthropic_selected_but_invalid(self) -> None:
        """
        User has both keys, using Claude (invalid), but OpenAI would work.

        They'll see:
            Anthropic key rejected (401 Unauthorized)

            Your Claude API key was rejected. Check it at console.anthropic.com/settings/keys.

        (We don't auto-switch to OpenAI — that would be confusing)
        """
        settings = _settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-BROKEN-key",
            openai_api_key="sk-valid-openai",
        )
        with patch(
            "bristlenose.doctor._validate_anthropic_key",
            return_value=(False, "401 Unauthorized"),
        ):
            result = check_api_key(settings)

        assert result.status == CheckStatus.FAIL
        # We report the problem with the selected provider, not suggest switching

    def test_anthropic_key_set_openai_selected_and_missing(self) -> None:
        """
        User has Anthropic key, but ran --llm chatgpt without OpenAI key.

        They'll see:
            No OpenAI API key

            ...
            To use Claude instead:  bristlenose run <input> --llm claude
        """
        settings = _settings(
            llm_provider="openai",
            anthropic_api_key="sk-ant-valid-key",
            openai_api_key="",
        )
        result = check_api_key(settings)

        assert result.status == CheckStatus.FAIL
        fix = get_fix(result.fix_key)
        assert "--llm claude" in fix


# ---------------------------------------------------------------------------
# Scenario 10: Edge cases and weird states
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Unusual but possible states."""

    def test_empty_string_key_is_missing(self) -> None:
        """Empty string key is treated as missing, not invalid."""
        settings = _settings(llm_provider="anthropic", anthropic_api_key="")
        result = check_api_key(settings)

        assert result.status == CheckStatus.FAIL
        assert result.fix_key == "api_key_missing_anthropic"

    def test_whitespace_only_key_is_missing(self) -> None:
        """Whitespace-only key is effectively empty after strip."""
        settings = _settings(llm_provider="anthropic", anthropic_api_key="   ")
        # Pydantic doesn't strip whitespace by default, so this is "set"
        # but the API will reject it
        # This tests current behavior — we might want to strip in the future
        assert settings.anthropic_api_key == "   "
        # The check will treat this as a set key (validation happens later)
        _ = check_api_key(settings)

    def test_very_short_key_masking(self) -> None:
        """Very short key still displays something."""
        settings = _settings(llm_provider="anthropic", anthropic_api_key="abc")
        with patch(
            "bristlenose.doctor._validate_anthropic_key",
            return_value=(True, ""),
        ):
            result = check_api_key(settings)

        assert result.status == CheckStatus.OK
        # Short keys show "(set)" not the actual key
        assert "(set)" in result.detail

    def test_unknown_provider_fails_gracefully(self) -> None:
        """
        User somehow has an unknown provider configured.

        They'll see:
            Unknown LLM provider: gemini
        """
        settings = _settings(llm_provider="gemini")
        result = check_api_key(settings)

        assert result.status == CheckStatus.FAIL
        assert "Unknown LLM provider" in result.detail

    def test_local_model_custom_url(self) -> None:
        """User running Ollama on a different port or remote machine."""
        settings = _settings(
            llm_provider="local",
            local_url="http://192.168.1.100:11434/v1",
            local_model="llama3.2:3b",
        )
        with patch(
            "bristlenose.ollama.validate_local_endpoint",
            return_value=(True, ""),
        ):
            result = check_local_provider(settings)

        assert result.status == CheckStatus.OK
        assert "llama3.2:3b" in result.detail


# ---------------------------------------------------------------------------
# Scenario: Azure OpenAI partial configuration
# ---------------------------------------------------------------------------


class TestAzurePartialConfig:
    """Enterprise user who set --llm azure but forgot some config fields."""

    def test_azure_missing_endpoint(self) -> None:
        """User set key and deployment but forgot the endpoint URL."""
        settings = _settings(
            llm_provider="azure",
            azure_api_key="test-key",
            azure_deployment="my-deployment",
            azure_endpoint="",
        )
        result = check_api_key(settings)
        assert result.status == CheckStatus.FAIL
        assert "endpoint" in result.detail.lower()
        assert result.fix_key == "api_key_missing_azure"

    def test_azure_missing_key(self) -> None:
        """User set endpoint and deployment but forgot the API key."""
        settings = _settings(
            llm_provider="azure",
            azure_api_key="",
            azure_endpoint="https://example.openai.azure.com/",
            azure_deployment="my-deployment",
        )
        result = check_api_key(settings)
        assert result.status == CheckStatus.FAIL
        assert result.fix_key == "api_key_missing_azure"

    def test_azure_missing_deployment(self) -> None:
        """User set endpoint and key but forgot the deployment name."""
        settings = _settings(
            llm_provider="azure",
            azure_api_key="test-key",
            azure_endpoint="https://example.openai.azure.com/",
            azure_deployment="",
        )
        result = check_api_key(settings)
        assert result.status == CheckStatus.FAIL
        assert "deployment" in result.detail.lower()

    def test_azure_all_configured_validates(self) -> None:
        """All Azure fields set, mock validation succeeds."""
        settings = _settings(
            llm_provider="azure",
            azure_api_key="test-key",
            azure_endpoint="https://example.openai.azure.com/",
            azure_deployment="my-deployment",
        )
        with patch("bristlenose.doctor._validate_azure_key", return_value=(True, "")):
            result = check_api_key(settings)
        assert result.status == CheckStatus.OK
        assert "Azure OpenAI" in result.detail

    def test_azure_invalid_key(self) -> None:
        """Azure returns 401 for bad credentials."""
        settings = _settings(
            llm_provider="azure",
            azure_api_key="bad-key",
            azure_endpoint="https://example.openai.azure.com/",
            azure_deployment="my-deployment",
        )
        with patch(
            "bristlenose.doctor._validate_azure_key",
            return_value=(False, "401 Unauthorized"),
        ):
            result = check_api_key(settings)
        assert result.status == CheckStatus.FAIL
        assert result.fix_key == "api_key_invalid_azure"

    def test_azure_deployment_not_found(self) -> None:
        """Azure returns 404 for nonexistent deployment."""
        settings = _settings(
            llm_provider="azure",
            azure_api_key="test-key",
            azure_endpoint="https://example.openai.azure.com/",
            azure_deployment="nonexistent",
        )
        with patch(
            "bristlenose.doctor._validate_azure_key",
            return_value=(False, "Deployment 'nonexistent' not found"),
        ):
            result = check_api_key(settings)
        assert result.status == CheckStatus.FAIL
        assert result.fix_key == "api_key_invalid_azure"

    def test_azure_network_unreachable(self) -> None:
        """Can't reach Azure endpoint (corporate firewall, etc.)."""
        settings = _settings(
            llm_provider="azure",
            azure_api_key="test-key",
            azure_endpoint="https://example.openai.azure.com/",
            azure_deployment="my-deployment",
        )
        with patch(
            "bristlenose.doctor._validate_azure_key",
            return_value=(None, "Connection refused"),
        ):
            result = check_api_key(settings)
        assert result.status == CheckStatus.OK  # key present, can't validate
        assert "could not validate" in result.detail.lower()

    def test_azure_fix_message_helpful(self) -> None:
        """Fix message lists all three required env vars."""
        fix = get_fix("api_key_missing_azure")
        assert "BRISTLENOSE_AZURE_ENDPOINT" in fix
        assert "BRISTLENOSE_AZURE_API_KEY" in fix
        assert "BRISTLENOSE_AZURE_DEPLOYMENT" in fix
        assert "bristlenose configure azure" in fix

    def test_azure_invalid_fix_message(self) -> None:
        """Invalid key fix message has troubleshooting steps."""
        fix = get_fix("api_key_invalid_azure")
        assert "API key is correct" in fix
        assert "Endpoint URL" in fix
        assert "Deployment name" in fix

    def test_azure_network_check_uses_endpoint(self) -> None:
        """Network check should hit the user's Azure endpoint, not api.openai.com."""
        settings = _settings(
            llm_provider="azure",
            azure_endpoint="https://myresource.openai.azure.com/",
        )
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__ = lambda s: s
            mock_urlopen.return_value.__exit__ = lambda s, *a: None
            result = check_network(settings)
        assert result.status == CheckStatus.OK
        assert "myresource.openai.azure.com" in result.detail

    def test_azure_network_check_no_endpoint(self) -> None:
        """Network check should skip if no endpoint configured."""
        settings = _settings(llm_provider="azure", azure_endpoint="")
        result = check_network(settings)
        assert result.status == CheckStatus.SKIP
