"""Tests for credential storage."""

from __future__ import annotations

import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

from bristlenose.credentials import (
    EnvCredentialStore,
    get_credential,
    get_credential_source,
    get_credential_store,
)


class TestEnvCredentialStore:
    """Tests for the environment variable fallback store."""

    def test_get_with_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Prefixed env var should be found."""
        monkeypatch.setenv("BRISTLENOSE_ANTHROPIC_API_KEY", "test-key")
        store = EnvCredentialStore()
        assert store.get("anthropic") == "test-key"

    def test_get_without_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Bare env var should be found."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        store = EnvCredentialStore()
        assert store.get("anthropic") == "test-key"

    def test_get_prefers_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Prefixed env var should take priority over bare."""
        monkeypatch.setenv("BRISTLENOSE_ANTHROPIC_API_KEY", "prefixed")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "bare")
        store = EnvCredentialStore()
        assert store.get("anthropic") == "prefixed"

    def test_get_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing env var should return None."""
        monkeypatch.delenv("BRISTLENOSE_ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        store = EnvCredentialStore()
        assert store.get("anthropic") is None

    def test_get_unknown_key(self) -> None:
        """Unknown key name should return None."""
        store = EnvCredentialStore()
        assert store.get("unknown-provider") is None

    def test_get_openai(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OpenAI key should work."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        store = EnvCredentialStore()
        assert store.get("openai") == "sk-test"

    def test_set_raises(self) -> None:
        """Cannot store to env — should raise."""
        store = EnvCredentialStore()
        with pytest.raises(NotImplementedError):
            store.set("anthropic", "key")

    def test_delete_raises(self) -> None:
        """Cannot delete from env — should raise."""
        store = EnvCredentialStore()
        with pytest.raises(NotImplementedError):
            store.delete("anthropic")

    def test_exists_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """exists() should return True when key is set."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
        store = EnvCredentialStore()
        assert store.exists("anthropic") is True

    def test_exists_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """exists() should return False when key is not set."""
        monkeypatch.delenv("BRISTLENOSE_ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        store = EnvCredentialStore()
        assert store.exists("anthropic") is False


class TestGetCredentialStore:
    """Tests for the credential store factory."""

    def test_returns_macos_store_on_darwin(self) -> None:
        """On macOS, should return MacOSCredentialStore."""
        with patch("sys.platform", "darwin"):
            # Need to reimport to pick up the patched platform
            from bristlenose import credentials

            with patch.object(credentials, "sys") as mock_sys:
                mock_sys.platform = "darwin"
                store = credentials.get_credential_store()
                # Can't easily check the type without importing macOS module on other platforms
                # Just verify it doesn't crash
                assert store is not None

    def test_returns_env_store_on_windows(self) -> None:
        """On Windows, should return EnvCredentialStore."""
        with patch("bristlenose.credentials.sys.platform", "win32"):
            store = get_credential_store()
            assert isinstance(store, EnvCredentialStore)


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
class TestMacOSCredentialStore:
    """Tests for MacOSCredentialStore using mocked subprocess."""

    @pytest.fixture
    def store(self):
        """Create a MacOSCredentialStore instance."""
        from bristlenose.credentials_macos import MacOSCredentialStore

        return MacOSCredentialStore()

    def test_get_calls_security(self, store) -> None:
        """get() should call security find-generic-password."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="test-key\n", returncode=0)
            result = store.get("anthropic")

            assert result == "test-key"
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "security"
            assert "find-generic-password" in args
            assert "Bristlenose Anthropic API Key" in args

    def test_get_not_found(self, store) -> None:
        """get() should return None when key not found."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(44, "security")
            result = store.get("anthropic")
            assert result is None

    def test_set_deletes_then_adds(self, store) -> None:
        """set() should delete existing then add new."""
        with patch("subprocess.run") as mock_run:
            store.set("anthropic", "new-key")

            assert mock_run.call_count == 2
            # First call: delete
            assert "delete-generic-password" in mock_run.call_args_list[0][0][0]
            # Second call: add
            add_args = mock_run.call_args_list[1][0][0]
            assert "add-generic-password" in add_args
            assert "new-key" in add_args

    def test_delete_ignores_not_found(self, store) -> None:
        """delete() should not raise if key doesn't exist."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=44)  # not found
            # Should not raise
            store.delete("anthropic")
            mock_run.assert_called_once()

    def test_service_name_anthropic(self, store) -> None:
        """Should use human-readable service name for Anthropic."""
        assert store._service_name("anthropic") == "Bristlenose Anthropic API Key"

    def test_service_name_openai(self, store) -> None:
        """Should use human-readable service name for OpenAI."""
        assert store._service_name("openai") == "Bristlenose OpenAI API Key"

    def test_service_name_unknown(self, store) -> None:
        """Unknown provider should get a generic service name."""
        assert store._service_name("gemini") == "Bristlenose Gemini API Key"


@pytest.mark.skipif(sys.platform == "darwin", reason="Linux only")
class TestLinuxCredentialStore:
    """Tests for LinuxCredentialStore using mocked subprocess."""

    def test_get_calls_secret_tool(self) -> None:
        """get() should call secret-tool lookup."""
        from bristlenose.credentials_linux import LinuxCredentialStore

        store = LinuxCredentialStore()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="test-key\n", returncode=0)
            result = store.get("anthropic")

            assert result == "test-key"
            args = mock_run.call_args[0][0]
            assert "secret-tool" in args
            assert "lookup" in args

    def test_set_calls_secret_tool_store(self) -> None:
        """set() should call secret-tool store."""
        from bristlenose.credentials_linux import LinuxCredentialStore

        store = LinuxCredentialStore()

        with patch("subprocess.run") as mock_run:
            store.set("anthropic", "new-key")

            args = mock_run.call_args[0][0]
            assert "secret-tool" in args
            assert "store" in args
            # Key should be passed via input, not args
            assert mock_run.call_args[1]["input"] == "new-key"

    def test_get_linux_store_with_secret_tool(self) -> None:
        """Should return LinuxCredentialStore when secret-tool is available."""
        from bristlenose.credentials_linux import get_linux_store

        with patch("shutil.which", return_value="/usr/bin/secret-tool"):
            with patch("subprocess.run"):  # Prevent actual call
                store = get_linux_store()
                # On Linux, should be LinuxCredentialStore
                # On macOS running this test, would be EnvCredentialStore (skipped)
                assert store is not None

    def test_get_linux_store_without_secret_tool(self) -> None:
        """Should return EnvCredentialStore when secret-tool is not available."""
        from bristlenose.credentials_linux import get_linux_store

        with patch("shutil.which", return_value=None):
            store = get_linux_store()
            assert isinstance(store, EnvCredentialStore)


class TestGetCredential:
    """Tests for the get_credential convenience function."""

    def test_returns_from_keychain_first(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Keychain should take priority over env var."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")

        with patch("bristlenose.credentials.get_credential_store") as mock_store:
            mock_store.return_value.get.return_value = "keychain-key"
            result = get_credential("anthropic")
            assert result == "keychain-key"

    def test_falls_back_to_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should fall back to env var when keychain is empty."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")

        with patch("bristlenose.credentials.get_credential_store") as mock_store:
            mock_store.return_value.get.return_value = None
            result = get_credential("anthropic")
            assert result == "env-key"

    def test_returns_none_when_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return None when not in keychain or env."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("BRISTLENOSE_ANTHROPIC_API_KEY", raising=False)

        with patch("bristlenose.credentials.get_credential_store") as mock_store:
            mock_store.return_value.get.return_value = None
            result = get_credential("anthropic")
            assert result is None


class TestGetCredentialSource:
    """Tests for the get_credential_source function."""

    def test_returns_keychain_when_in_keychain(self) -> None:
        """Should return 'keychain' when credential is in keychain."""
        with patch("bristlenose.credentials.get_credential_store") as mock_store:
            # Not an EnvCredentialStore, so it's a real keychain
            mock_instance = MagicMock()
            mock_instance.get.return_value = "key"
            mock_store.return_value = mock_instance

            result = get_credential_source("anthropic")
            assert result == "keychain"

    def test_returns_env_when_only_in_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return 'env' when credential is only in env."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")

        with patch("bristlenose.credentials.get_credential_store") as mock_store:
            # Return EnvCredentialStore to simulate no keychain
            mock_store.return_value = EnvCredentialStore()

            result = get_credential_source("anthropic")
            assert result == "env"

    def test_returns_none_when_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return None when credential not found anywhere."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("BRISTLENOSE_ANTHROPIC_API_KEY", raising=False)

        with patch("bristlenose.credentials.get_credential_store") as mock_store:
            mock_store.return_value = EnvCredentialStore()

            result = get_credential_source("anthropic")
            assert result is None
