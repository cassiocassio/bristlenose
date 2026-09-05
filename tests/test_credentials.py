"""Tests for credential storage."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
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

    def test_get_azure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Azure key should work."""
        monkeypatch.setenv("AZURE_API_KEY", "az-test")
        store = EnvCredentialStore()
        assert store.get("azure") == "az-test"

    def test_get_azure_with_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Prefixed Azure key should work."""
        monkeypatch.setenv("BRISTLENOSE_AZURE_API_KEY", "az-prefixed")
        store = EnvCredentialStore()
        assert store.get("azure") == "az-prefixed"

    def test_get_miro(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Miro token should work."""
        monkeypatch.setenv("MIRO_ACCESS_TOKEN", "miro-test")
        store = EnvCredentialStore()
        assert store.get("miro") == "miro-test"

    def test_get_miro_with_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Prefixed Miro token should work."""
        monkeypatch.setenv("BRISTLENOSE_MIRO_ACCESS_TOKEN", "miro-prefixed")
        store = EnvCredentialStore()
        assert store.get("miro") == "miro-prefixed"

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

    def test_returns_file_store_on_windows(self) -> None:
        """On Windows (no keyring wired), should return the persisting FileCredentialStore."""
        from bristlenose.credentials import FileCredentialStore

        with patch("bristlenose.credentials.sys.platform", "win32"):
            store = get_credential_store()
            assert isinstance(store, FileCredentialStore)


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

    def test_set_records_a_refused_delete(self, store, caplog) -> None:
        """A delete the ACL refuses is the measurement, so set() must record it.

        The app's login-keychain items name ``/usr/bin/security`` in their ACL,
        but a delete of an item another tool created was refused when the app
        tried it (``-25244 errSecInvalidOwnerEdit``). Whether the CLI's
        delete-then-add is refused on an *app*-owned item is answered by the
        next ``bristlenose configure`` — only if the outcome is logged, and at
        a level ``configure`` (which has no ``-v``) prints. The add must still
        run: ``-U`` updates in place when the delete could not clear the way.
        """
        import logging

        refused = MagicMock(
            returncode=1,
            stderr="security: SecKeychainItemDelete: errSecInvalidOwnerEdit (-25244)",
        )
        added = MagicMock(returncode=0, stderr="")
        with patch("subprocess.run", side_effect=[refused, added]) as mock_run, caplog.at_level(
            logging.WARNING, logger="bristlenose.credentials_macos"
        ):
            store.set("anthropic", "new-key")

        assert mock_run.call_count == 2
        assert "add-generic-password" in mock_run.call_args_list[1][0][0]
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert "Bristlenose Anthropic API Key" in warnings[0].getMessage()
        assert "-25244" in warnings[0].getMessage()

    def test_set_is_quiet_when_nothing_to_delete(self, store, caplog) -> None:
        """Not found (exit 44) and a clean delete are routine — no warning."""
        import logging

        for rc in (44, 0):
            caplog.clear()
            outcomes = [MagicMock(returncode=rc, stderr=""), MagicMock(returncode=0, stderr="")]
            with patch("subprocess.run", side_effect=outcomes), caplog.at_level(
                logging.WARNING, logger="bristlenose.credentials_macos"
            ):
                store.set("anthropic", "new-key")
            assert not [r for r in caplog.records if r.levelno >= logging.WARNING], rc

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

    def test_service_name_miro(self, store) -> None:
        """Miro should use 'Access Token' not 'API Key'."""
        assert store._service_name("miro") == "Bristlenose Miro Access Token"

    def test_service_name_unknown(self, store) -> None:
        """Unknown provider should get a generic service name."""
        assert store._service_name("gemini") == "Bristlenose Gemini API Key"

    # C3 (Apr 2026): exception broadening for App Sandbox contexts where
    # /usr/bin/security exec is blocked. Keep sandboxed-sidecar failure mode
    # graceful (None / no-op) rather than unhandled traceback.

    def test_get_handles_file_not_found(self, store, caplog) -> None:
        """get() returns None when /usr/bin/security is missing."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("security: No such file")
            with caplog.at_level("DEBUG", logger="bristlenose.credentials_macos"):
                result = store.get("anthropic")
            assert result is None
            assert any("security CLI failed" in r.message for r in caplog.records)

    def test_get_handles_permission_error(self, store) -> None:
        """get() returns None when sandbox denies exec."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = PermissionError("Operation not permitted")
            assert store.get("anthropic") is None

    def test_get_handles_generic_os_error(self, store) -> None:
        """get() returns None on any OSError (catchall)."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("sandbox violation")
            assert store.get("anthropic") is None

    def test_set_handles_exec_denial(self, store, caplog) -> None:
        """set() is a no-op if subprocess-exec is blocked."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("security: No such file")
            with caplog.at_level("DEBUG", logger="bristlenose.credentials_macos"):
                # Should not raise
                store.set("anthropic", "sk-ant-example")
            assert any("security CLI failed" in r.message for r in caplog.records)

    def test_delete_handles_exec_denial(self, store) -> None:
        """delete() is a no-op if subprocess-exec is blocked."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = PermissionError("Operation not permitted")
            # Should not raise
            store.delete("anthropic")


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


class TestPopulateKeysFromKeychain:
    """Tests for _populate_keys_from_keychain — ensures env wins over keychain.

    Motivation (C3): the sandboxed desktop sidecar relies on Swift injecting
    keys as BRISTLENOSE_*_API_KEY env vars before launch. pydantic-settings
    populates the settings field from env, then _populate_keys_from_keychain
    should NOT overwrite that with a (potentially stale) keychain value.
    """

    def test_env_wins_over_keychain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If env var is set, keychain is not consulted for that provider."""
        from bristlenose.config import BristlenoseSettings, _populate_keys_from_keychain

        settings = BristlenoseSettings(anthropic_api_key="env-injected-key")

        mock_store = MagicMock()
        mock_store.get.return_value = "keychain-stale-key"

        with patch("bristlenose.credentials.get_credential_store", return_value=mock_store):
            result = _populate_keys_from_keychain(settings)

        assert result.anthropic_api_key == "env-injected-key"
        # For providers WITHOUT env var set, keychain IS called. Just verify
        # the env-set provider's slot was not clobbered.
        get_calls_for_anthropic = [c for c in mock_store.get.call_args_list
                                   if c.args and c.args[0] == "anthropic"]
        assert get_calls_for_anthropic == [], \
            "Keychain should not be consulted when env var already populated the field"

    def test_keychain_fallback_when_env_empty(self) -> None:
        """If no env var set, keychain value populates the field."""
        from bristlenose.config import BristlenoseSettings, _populate_keys_from_keychain

        settings = BristlenoseSettings()  # no keys from env
        mock_store = MagicMock()
        mock_store.get.side_effect = lambda k: "kc-key" if k == "anthropic" else None

        with patch("bristlenose.credentials.get_credential_store", return_value=mock_store):
            result = _populate_keys_from_keychain(settings)

        assert result.anthropic_api_key == "kc-key"


class TestFileCredentialStore:
    """Tests for the persisting file fallback (no keyring available)."""

    @pytest.fixture
    def store(self, tmp_path):
        from bristlenose.credentials import FileCredentialStore

        return FileCredentialStore(path=tmp_path / ".env")

    def test_set_get_roundtrip(self, store) -> None:
        store.set("anthropic", "sk-ant-abc")
        assert store.get("anthropic") == "sk-ant-abc"

    def test_writes_prefixed_var(self, store) -> None:
        store.set("openai", "sk-oa-1")
        assert store.path.read_text() == "BRISTLENOSE_OPENAI_API_KEY=sk-oa-1\n"

    def test_file_is_owner_only(self, store) -> None:
        import stat

        store.set("anthropic", "secret")
        mode = stat.S_IMODE(store.path.stat().st_mode)
        assert mode == 0o600

    def test_upsert_replaces_not_duplicates(self, store) -> None:
        store.set("anthropic", "one")
        store.set("anthropic", "two")
        store.set("openai", "oa")
        text = store.path.read_text()
        assert text.count("BRISTLENOSE_ANTHROPIC_API_KEY=") == 1
        assert "BRISTLENOSE_ANTHROPIC_API_KEY=two" in text
        assert "BRISTLENOSE_OPENAI_API_KEY=oa" in text

    def test_delete_removes_line(self, store) -> None:
        store.set("anthropic", "one")
        store.set("openai", "oa")
        store.delete("anthropic")
        assert store.get("anthropic") is None
        assert store.get("openai") == "oa"

    def test_delete_missing_is_noop(self, store) -> None:
        store.delete("anthropic")  # file doesn't exist yet
        assert store.get("anthropic") is None

    def test_env_var_wins_over_file(self, store, monkeypatch: pytest.MonkeyPatch) -> None:
        store.set("anthropic", "from-file")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
        assert store.get("anthropic") == "from-env"

    def test_unmapped_key_roundtrips(self, store) -> None:
        # miro_refresh has no ENV_VAR_MAP entry — must still round-trip.
        store.set("miro_refresh", "refresh-token")
        assert store.get("miro_refresh") == "refresh-token"
        assert "BRISTLENOSE_MIRO_REFRESH=refresh-token" in store.path.read_text()

    def test_preserves_comments_and_other_lines(self, store) -> None:
        store.path.write_text("# my keys\nUNRELATED=keep-me\n")
        store.set("anthropic", "sk-ant")
        text = store.path.read_text()
        assert "# my keys" in text
        assert "UNRELATED=keep-me" in text
        assert "BRISTLENOSE_ANTHROPIC_API_KEY=sk-ant" in text


class TestUserConfigDir:
    """The fallback file location must land somewhere writable per platform."""

    def test_snap_common_wins(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        # On the snap, $SNAP_USER_COMMON is writable under strict confinement too
        # (no interface needed) — the file fallback must use it.
        from bristlenose.credentials import user_config_dir, user_config_env_path

        monkeypatch.setenv("SNAP_USER_COMMON", str(tmp_path))
        assert user_config_dir() == tmp_path
        assert user_config_env_path() == tmp_path / ".env"

    def test_xdg_config_home(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        from bristlenose.credentials import user_config_dir

        monkeypatch.delenv("SNAP_USER_COMMON", raising=False)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        assert user_config_dir() == tmp_path / "bristlenose"

    def test_default_home(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pathlib import Path

        from bristlenose.credentials import user_config_dir

        monkeypatch.delenv("SNAP_USER_COMMON", raising=False)
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        assert user_config_dir() == Path.home() / ".config" / "bristlenose"


class TestUnprefixedEnvAliases:
    """The plain, industry-standard key names (ANTHROPIC_API_KEY, …) must work."""

    def _reload(self):
        # BristlenoseSettings reads env at construction; no reload needed, but
        # clear any BRISTLENOSE_-prefixed collisions the test env might carry.
        from bristlenose.config import BristlenoseSettings

        return BristlenoseSettings

    def test_bare_anthropic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BRISTLENOSE_ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "bare-anthropic")
        assert self._reload()().anthropic_api_key == "bare-anthropic"

    def test_bare_openai(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BRISTLENOSE_OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "bare-openai")
        assert self._reload()().openai_api_key == "bare-openai"

    def test_prefix_wins_over_bare(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "bare")
        monkeypatch.setenv("BRISTLENOSE_ANTHROPIC_API_KEY", "prefixed")
        assert self._reload()().anthropic_api_key == "prefixed"

    def test_field_name_still_populates(self) -> None:
        # populate_by_name=True keeps direct construction working despite aliases.
        assert self._reload()(anthropic_api_key="direct").anthropic_api_key == "direct"

    def test_bare_openai_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BRISTLENOSE_OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "bare-oa")
        assert self._reload()().openai_api_key == "bare-oa"

    def test_gemini_api_key_alias(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # google-genai reads GEMINI_API_KEY as well as GOOGLE_API_KEY.
        monkeypatch.delenv("BRISTLENOSE_GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "gem")
        assert self._reload()().google_api_key == "gem"

    def test_azure_openai_sdk_names(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # The openai SDK's AzureOpenAI client reads these natively — an Azure user
        # reaches for them before the BRISTLENOSE_ names.
        for name in ("BRISTLENOSE_AZURE_API_KEY", "AZURE_API_KEY",
                     "BRISTLENOSE_AZURE_ENDPOINT", "BRISTLENOSE_AZURE_DEPLOYMENT"):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "az-key")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://x.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "dep")
        s = self._reload()()
        assert s.azure_api_key == "az-key"
        assert s.azure_endpoint == "https://x.openai.azure.com/"
        assert s.azure_deployment == "dep"


# ---------------------------------------------------------------------------
# Read-back verification — a clean `set()` is not evidence anything was stored
# ---------------------------------------------------------------------------


class _FakeSecurityCLI:
    """A stateful stand-in for ``/usr/bin/security``, keyed on (account, service).

    Emulates the three verbs ``MacOSCredentialStore`` uses with the exit codes
    the real tool returns (44 = not found), so a set-then-get through the
    store's actual argv is a round-trip through *this* rather than through the
    developer's login keychain. ``refuse_add`` is the sandboxed shape: the add
    fails, the store swallows it, and nothing raises.
    """

    def __init__(self, *, refuse_add: bool = False) -> None:
        self.items: dict[tuple[str, str], str] = {}
        self.calls: list[list[str]] = []
        self.refuse_add = refuse_add

    @staticmethod
    def _opt(args: list[str], flag: str) -> str | None:
        return args[args.index(flag) + 1] if flag in args else None

    def __call__(self, args: list[str], **kwargs):  # noqa: ANN001 — subprocess.run shape
        self.calls.append(list(args))
        verb = args[1]
        key = (self._opt(args, "-a") or "", self._opt(args, "-s") or "")
        if verb == "find-generic-password":
            if key in self.items:
                out = self.items[key] + "\n" if "-w" in args else ""
                return subprocess.CompletedProcess(args, 0, stdout=out, stderr="")
            if kwargs.get("check"):
                raise subprocess.CalledProcessError(44, args)
            return subprocess.CompletedProcess(args, 44, stdout="", stderr="not found")
        if verb == "add-generic-password":
            if self.refuse_add:
                if kwargs.get("check"):
                    raise subprocess.CalledProcessError(1, args)
                return subprocess.CompletedProcess(args, 1, stdout="", stderr="refused")
            self.items[key] = self._opt(args, "-w") or ""
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if verb == "delete-generic-password":
            self.items.pop(key, None)
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected security verb: {verb}")


_PATCH_MACOS_RUN = "bristlenose.credentials_macos.subprocess.run"


class TestMacOSStoreRoundTrip:
    """The macOS store's set→get, through its real argv, against a faked tool."""

    def test_set_then_get_round_trips(self) -> None:
        from bristlenose.credentials import set_verified
        from bristlenose.credentials_macos import MacOSCredentialStore

        fake = _FakeSecurityCLI()
        store = MacOSCredentialStore()
        with patch(_PATCH_MACOS_RUN, new=fake):
            store.set("google", "g-key")
            assert store.get("google") == "g-key"
            assert set_verified(store, "google", "g-key") is True
        # The login copy the Mac app reads is at exactly this service + account.
        assert ("bristlenose", "Bristlenose Google Gemini API Key") in fake.items

    def test_refused_write_is_caught_by_read_back(self, caplog) -> None:
        """The sandboxed shape: `set` returns cleanly, the key is nowhere."""
        from bristlenose.credentials import set_verified
        from bristlenose.credentials_macos import MacOSCredentialStore

        fake = _FakeSecurityCLI(refuse_add=True)
        store = MacOSCredentialStore()
        with patch(_PATCH_MACOS_RUN, new=fake), caplog.at_level("WARNING"):
            store.set("google", "g-key")  # swallows — by design
            assert set_verified(store, "google", "g-key") is False
        assert "did not round-trip" in caplog.text

    def test_missing_security_tool_is_caught_by_read_back(self) -> None:
        from bristlenose.credentials import set_verified
        from bristlenose.credentials_macos import MacOSCredentialStore

        store = MacOSCredentialStore()
        with patch(_PATCH_MACOS_RUN, side_effect=FileNotFoundError("security")):
            assert set_verified(store, "google", "g-key") is False


class _NoOpStore:
    """Accepts and discards; nothing raises. The invisible failure."""

    def get(self, key: str) -> str | None:
        return None

    def set(self, key: str, value: str) -> None:
        pass

    def delete(self, key: str) -> None:
        pass


class TestSetVerified:
    def test_working_store_is_true(self, tmp_path: Path) -> None:
        from bristlenose.credentials import FileCredentialStore, set_verified

        store = FileCredentialStore(tmp_path / ".env")
        assert set_verified(store, "anthropic", "sk-1") is True

    def test_no_op_store_is_false(self, caplog) -> None:
        from bristlenose.credentials import set_verified

        with caplog.at_level("WARNING"):
            assert set_verified(_NoOpStore(), "anthropic", "sk-1") is False  # type: ignore[arg-type]
        assert "did not round-trip" in caplog.text

    def test_read_only_store_raises_rather_than_lies(self) -> None:
        from bristlenose.credentials import set_verified

        with pytest.raises(NotImplementedError):
            set_verified(EnvCredentialStore(), "anthropic", "sk-1")

    def test_env_var_shadowing_the_file_is_false(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The write lands, and is not the value that will be used."""
        from bristlenose.credentials import FileCredentialStore, set_verified

        monkeypatch.setenv("BRISTLENOSE_ANTHROPIC_API_KEY", "shadow")
        store = FileCredentialStore(tmp_path / ".env")
        assert set_verified(store, "anthropic", "real") is False
        assert "BRISTLENOSE_ANTHROPIC_API_KEY=real" in (tmp_path / ".env").read_text()


# ---------------------------------------------------------------------------
# One table of credential names — `bristlenose/providers.py` `CREDENTIALS`
# ---------------------------------------------------------------------------


class TestCredentialRegistry:
    """The stores derive their names from the registry, never list them.

    A name changed in `CREDENTIALS` must reach the macOS service map, the
    env-var fallback and the Linux label without a second edit; these pin
    that, and pin the set of keys so a change to it is a deliberate one.
    """

    def test_registry_keys_are_the_five_the_cli_stores(self) -> None:
        from bristlenose.providers import CREDENTIALS

        assert set(CREDENTIALS) == {"anthropic", "openai", "azure", "google", "miro"}

    def test_macos_service_names_derive_from_the_registry(self) -> None:
        from bristlenose.credentials_macos import MacOSCredentialStore
        from bristlenose.providers import CREDENTIALS

        assert MacOSCredentialStore.SERVICE_NAMES == {
            key: spec.keychain_service for key, spec in CREDENTIALS.items()
        }
        assert MacOSCredentialStore()._service_name("google") == "Bristlenose Google Gemini API Key"

    def test_env_var_map_derives_from_the_registry(self) -> None:
        from bristlenose.providers import CREDENTIALS

        assert EnvCredentialStore.ENV_VAR_MAP == {
            key: spec.env_var for key, spec in CREDENTIALS.items()
        }

    def test_linux_label_is_the_same_name_as_macos(self) -> None:
        """A key stored on Linux is called what Keychain Access would call it."""
        from bristlenose.credentials_linux import LinuxCredentialStore

        with patch("bristlenose.credentials_linux.subprocess.run") as mock_run:
            LinuxCredentialStore().set("google", "g-key")
        args = mock_run.call_args[0][0]
        assert args[args.index("--label") + 1] == "Bristlenose Google Gemini API Key"

    def test_unregistered_key_keeps_the_derived_shape(self) -> None:
        from bristlenose.providers import credential_service_name

        assert credential_service_name("miro_refresh") == "Bristlenose Miro_Refresh API Key"

    def test_provider_env_vars_agree_with_the_credential_table(self) -> None:
        """`PROVIDERS` names the prefixed variable; `CREDENTIALS` the bare one."""
        from bristlenose.providers import CREDENTIALS, PROVIDERS

        for name, spec in PROVIDERS.items():
            key_fields = [f for f in spec.config_fields if f.name == "api_key"]
            if not key_fields:
                continue
            assert key_fields[0].env_var == f"BRISTLENOSE_{CREDENTIALS[name].env_var}", name
