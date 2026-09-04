"""Provider resolution ladder: derive-or-diagnose, never a vendor default.

The CLI resolves the analysis provider as: ``--llm`` → ``BRISTLENOSE_LLM_PROVIDER``
(env var or ``.env`` — including the user-level current-provider preference that
``bristlenose configure`` / ``bristlenose use`` persist) → the sole configured
key → diagnose (``none`` / ``ambiguous``). The ``llm_provider`` field default
stays ``"anthropic"`` purely as the desktop-contract backstop
(``tests/test_swift_python_contract.py``); a CLI run never reaches it — the
``none``/``ambiguous`` statuses stop the run first.

The current provider mirrors the macOS app: it stays whatever you last set
(``configure`` writes it loudly; ``use`` switches it), and ``run``/``analyze``
never prompt.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from bristlenose import config
from bristlenose.config import BristlenoseSettings
from bristlenose.providers import PROVIDERS

# Explicit empty keys for every cloud provider — beats env vars, .env files,
# and (with the keychain patched out) leaves each test in full control.
KEYS_OFF: dict[str, str] = {
    "anthropic_api_key": "",
    "openai_api_key": "",
    "azure_api_key": "",
    "google_api_key": "",
}


@pytest.fixture
def hermetic(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """No keychain, no .env discovery, no provider/model/hosting env vars."""
    monkeypatch.setattr(config, "_populate_keys_from_keychain", lambda s: s)
    monkeypatch.setattr(config, "_find_env_files", lambda: [])
    for var in (
        "BRISTLENOSE_LLM_PROVIDER",
        "BRISTLENOSE_LLM_MODEL",
        "_BRISTLENOSE_HOSTED_BY_DESKTOP",
    ):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def _load(**key_overrides: str) -> BristlenoseSettings:
    return config.load_settings(**{**KEYS_OFF, **key_overrides})


class TestDeriveLadder:
    def test_sole_key_derives_that_provider(self, hermetic) -> None:
        """A single configured key is an unambiguous choice — used automatically."""
        s = _load(google_api_key="g-key")
        assert s.llm_provider == "google"
        # And the model snaps to the derived provider's default (composition
        # with _fill_provider_default_model — the reorder under test).
        assert s.llm_model == PROVIDERS["google"].default_model
        res = config.get_provider_resolution()
        assert res is not None
        assert res.status == "derived"
        assert res.provider == "google"
        assert res.source == "sole-configured-key"

    def test_sole_anthropic_key_same_rule(self, hermetic) -> None:
        """Claude wins by the same rule as everyone else — sole key, not favouritism."""
        s = _load(anthropic_api_key="sk-ant-x")
        assert s.llm_provider == "anthropic"
        res = config.get_provider_resolution()
        assert res is not None and res.status == "derived"

    def test_zero_keys_is_none_never_a_vendor_pick(self, hermetic) -> None:
        _load()
        res = config.get_provider_resolution()
        assert res is not None
        assert res.status == "none"
        assert res.configured == ()

    def test_two_keys_is_ambiguous_never_a_vendor_pick(self, hermetic) -> None:
        _load(anthropic_api_key="sk-ant-x", openai_api_key="sk-oai-x")
        res = config.get_provider_resolution()
        assert res is not None
        assert res.status == "ambiguous"
        assert set(res.configured) == {"anthropic", "openai"}

    def test_cli_override_wins_over_derivation(self, hermetic) -> None:
        s = config.load_settings(
            **{**KEYS_OFF, "google_api_key": "g-key"}, llm_provider="chatgpt"
        )
        assert s.llm_provider == "openai"  # alias-normalised, not derived
        res = config.get_provider_resolution()
        assert res is not None
        assert res.status == "explicit"
        assert res.source == "cli-override"

    def test_env_var_wins_over_derivation(self, hermetic, monkeypatch) -> None:
        monkeypatch.setenv("BRISTLENOSE_LLM_PROVIDER", "google")
        _load(openai_api_key="sk-oai-x")
        res = config.get_provider_resolution()
        assert res is not None
        assert res.status == "explicit"
        assert res.source == "env-var"

    def test_dotenv_value_counts_as_explicit(self, tmp_path: Path, hermetic) -> None:
        """A .env-supplied provider — including the stored current-provider
        preference in the user-level config .env — is an explicit choice, never
        overridden by derivation."""
        env = tmp_path / ".env"
        env.write_text("BRISTLENOSE_LLM_PROVIDER=openai\n")
        settings = BristlenoseSettings(
            **{**KEYS_OFF, "anthropic_api_key": "sk-ant-x", "google_api_key": "g-key"}
        )
        _, res = config._derive_provider(settings, {}, None, [str(env)])
        assert res.status == "explicit"
        assert res.source == "dotenv"

    def test_local_is_never_derived(self, hermetic) -> None:
        """Zero cloud keys does not fall through to Ollama — going local is
        always an explicit act (--llm local / env / `bristlenose use local`)."""
        _load()
        res = config.get_provider_resolution()
        assert res is not None
        assert res.status == "none"
        assert res.provider != "local"

    def test_hosted_skips_derivation_entirely(self, hermetic, monkeypatch) -> None:
        """Desktop-hosted: the Swift host owns provider choice; the field
        default stays the documented backstop (Swift contract toe #2)."""
        monkeypatch.setenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", "1")
        s = _load(google_api_key="g-key")
        assert s.llm_provider == "anthropic"  # backstop, NOT derived to google
        res = config.get_provider_resolution()
        assert res is not None and res.status == "hosted"

    def test_stateless_recompute_matches(self, hermetic) -> None:
        """provider_resolution_for computes the same ladder without the global
        (the serve/AutoCode path, where the global may be another context's)."""
        settings = BristlenoseSettings(**{**KEYS_OFF, "openai_api_key": "sk-oai-x"})
        res = config.provider_resolution_for(settings)
        assert res.status == "derived"
        assert res.provider == "openai"

    def test_stateless_recompute_tolerates_test_doubles(self, hermetic) -> None:
        """Non-string key attrs (MagicMock settings in serve tests) never count
        as configured — the guard must not misread a mock as four keys."""
        from unittest.mock import MagicMock

        res = config.provider_resolution_for(MagicMock())
        assert res.status == "none"


class TestCurrentProviderStore:
    @pytest.fixture
    def config_home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        monkeypatch.delenv("SNAP_USER_COMMON", raising=False)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        return tmp_path / "bristlenose" / ".env"

    def test_roundtrip_and_key_preservation(self, config_home: Path) -> None:
        from bristlenose.credentials import (
            read_user_config_var,
            write_user_config_var,
        )

        write_user_config_var("BRISTLENOSE_GOOGLE_API_KEY", "g-key")
        write_user_config_var("BRISTLENOSE_LLM_PROVIDER", "google")
        write_user_config_var("BRISTLENOSE_LLM_PROVIDER", "openai")  # upsert

        assert read_user_config_var("BRISTLENOSE_LLM_PROVIDER") == "openai"
        assert read_user_config_var("BRISTLENOSE_GOOGLE_API_KEY") == "g-key"
        content = config_home.read_text()
        assert content.count("BRISTLENOSE_LLM_PROVIDER") == 1
        # Secrets file discipline: mode 0600.
        assert (config_home.stat().st_mode & 0o777) == 0o600


class TestUseCommand:
    """`bristlenose use <provider>` — the explicit switch, no key re-paste."""

    @pytest.fixture
    def runner_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, hermetic
    ) -> Path:
        monkeypatch.delenv("SNAP_USER_COMMON", raising=False)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        return tmp_path / "bristlenose" / ".env"

    def _use(self, *args: str):
        from bristlenose.cli import app

        return CliRunner().invoke(app, ["use", *args])

    def test_use_with_key_persists_canonical_name(
        self, runner_env: Path, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            "bristlenose.cli.load_settings",
            lambda **kw: BristlenoseSettings(**{**KEYS_OFF, "google_api_key": "g"}),
        )
        result = self._use("gemini")
        assert result.exit_code == 0
        assert "Gemini is now your provider for analysis" in result.output
        assert "BRISTLENOSE_LLM_PROVIDER=google" in runner_env.read_text()

    def test_use_without_key_teaches_configure(
        self, runner_env: Path, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            "bristlenose.cli.load_settings",
            lambda **kw: BristlenoseSettings(**KEYS_OFF),
        )
        result = self._use("chatgpt")
        assert result.exit_code == 1
        assert "No ChatGPT key is configured" in result.output
        assert "bristlenose configure chatgpt" in result.output
        assert not runner_env.exists()  # nothing written on failure

    def test_use_local_needs_no_key(self, runner_env: Path) -> None:
        result = self._use("local")
        assert result.exit_code == 0
        assert "BRISTLENOSE_LLM_PROVIDER=local" in runner_env.read_text()

    def test_use_unknown_provider_lists_choices(self, runner_env: Path) -> None:
        result = self._use("copilot")
        assert result.exit_code == 1
        assert "claude, chatgpt, gemini, azure, local" in result.output

    def test_use_warns_when_env_var_masks_choice(
        self, runner_env: Path, monkeypatch
    ) -> None:
        monkeypatch.setenv("BRISTLENOSE_LLM_PROVIDER", "openai")
        monkeypatch.setattr(
            "bristlenose.cli.load_settings",
            lambda **kw: BristlenoseSettings(**{**KEYS_OFF, "google_api_key": "g"}),
        )
        result = self._use("gemini")
        assert result.exit_code == 0
        assert "BRISTLENOSE_LLM_PROVIDER=openai" in result.output  # the warning


class TestConfigureSetsCurrent:
    """`configure` = choose: the freshly-keyed provider becomes current, loudly."""

    class _FakeStore:
        def __init__(self) -> None:
            self.saved: dict[str, str] = {}

        def get(self, key: str) -> str | None:
            return self.saved.get(key)

        def set(self, key: str, value: str) -> None:
            self.saved[key] = value

        def delete(self, key: str) -> None:
            self.saved.pop(key, None)

    @pytest.fixture
    def configure_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, hermetic
    ) -> Path:
        monkeypatch.delenv("SNAP_USER_COMMON", raising=False)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        monkeypatch.setattr(
            "bristlenose.credentials.get_credential_store",
            lambda: TestConfigureSetsCurrent._FakeStore(),
        )
        monkeypatch.setattr(
            "bristlenose.doctor._validate_google_key", lambda key: (True, None)
        )
        return tmp_path / "bristlenose" / ".env"

    def test_configure_makes_provider_current(self, configure_env: Path) -> None:
        from bristlenose.cli import app

        result = CliRunner().invoke(app, ["configure", "gemini", "--key", "g-key"])
        assert result.exit_code == 0
        assert "Gemini is now your provider for analysis" in result.output
        assert "BRISTLENOSE_LLM_PROVIDER=google" in configure_env.read_text()

    def test_configure_names_the_item_keychain_access_shows(
        self, configure_env: Path
    ) -> None:
        """The printed name is the stored item's, not one re-derived from the
        product name — it said "Bristlenose Gemini API Key" for an item called
        "Bristlenose Google Gemini API Key" until 4 Sep 2026."""
        from bristlenose.cli import app

        result = CliRunner().invoke(app, ["configure", "gemini", "--key", "g-key"])
        assert result.exit_code == 0
        assert "Bristlenose Google Gemini API Key" in result.output
        assert "Bristlenose Gemini API Key" not in result.output

    def test_configure_refuses_a_key_it_cannot_read_back(
        self, configure_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A store that accepts and discards must not produce "Stored in …".

        The macOS store returns cleanly from a refused `security` write by
        design; before the read-back, `configure` printed the keychain line
        and made the provider current on the strength of nothing.
        """
        from bristlenose.cli import app

        class _NoOpStore(TestConfigureSetsCurrent._FakeStore):
            def set(self, key: str, value: str) -> None:
                pass

        monkeypatch.setattr(
            "bristlenose.credentials.get_credential_store", lambda: _NoOpStore()
        )
        result = CliRunner().invoke(app, ["configure", "gemini", "--key", "g-key"])
        assert result.exit_code == 1
        assert "Not saved" in result.output
        assert "Stored in" not in result.output
        assert "now your provider" not in result.output
        assert (
            not configure_env.exists()
            or "BRISTLENOSE_LLM_PROVIDER=google" not in configure_env.read_text()
        )

    def test_configure_second_provider_switches_and_names_the_previous(
        self, configure_env: Path
    ) -> None:
        from bristlenose.cli import app
        from bristlenose.credentials import write_user_config_var

        write_user_config_var("BRISTLENOSE_LLM_PROVIDER", "anthropic")
        result = CliRunner().invoke(app, ["configure", "gemini", "--key", "g-key"])
        assert result.exit_code == 0
        assert "(was Claude)" in result.output
        assert "bristlenose use claude" in result.output  # the way back
        assert "BRISTLENOSE_LLM_PROVIDER=google" in configure_env.read_text()
