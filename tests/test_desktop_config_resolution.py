"""Deterministic state-model for desktop LLM-config resolution.

These tests walk the provider/model/key resolution with ideal entry values
instead of a live pipeline run, so we can prove *exactly* what `config.py`
resolves to under each combination of (real env var, disk `.env`,
desktop-hosting flag) — the surface where a disk `.env` silently overrode the
GUI's provider choice and produced an anthropic-endpoint + gpt-4o-model 404.

The architectural guarantee under test: when the macOS app hosts the sidecar
(`_BRISTLENOSE_HOSTED_BY_DESKTOP=1`), disk `.env` files are invisible — only
real env vars (the host's transport for GUI/Keychain values) feed config.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bristlenose import config
from bristlenose.config import (
    BristlenoseSettings,
    _find_env_files,
    _key_fingerprint,
    hosted_by_desktop,
)


@pytest.fixture
def dotenv_in_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repo-style `.env` on disk, CWD pointed at it."""
    env = tmp_path / ".env"
    env.write_text(
        "BRISTLENOSE_LLM_PROVIDER=anthropic\n"
        "BRISTLENOSE_LLM_MODEL=claude-sonnet-4-20250514\n"
    )
    monkeypatch.chdir(tmp_path)
    return env


class TestEnvFileDiscovery:
    def test_finds_dotenv_when_not_desktop_hosted(
        self, dotenv_in_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)
        assert not hosted_by_desktop()
        assert dotenv_in_cwd in _find_env_files()

    def test_ignores_dotenv_when_desktop_hosted(
        self, dotenv_in_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The keystone: a disk `.env` exists and CWD is on it, but desktop
        # hosting makes file discovery return nothing.
        monkeypatch.setenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", "1")
        assert hosted_by_desktop()
        assert _find_env_files() == []


class TestPrecedence:
    """pydantic-settings layering, via an explicit _env_file."""

    def test_real_env_var_beats_dotenv(
        self, dotenv_in_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # GUI picked ChatGPT → Swift injects a real env var. It must win over
        # the disk `.env`'s anthropic.
        monkeypatch.setenv("BRISTLENOSE_LLM_PROVIDER", "openai")
        monkeypatch.setenv("BRISTLENOSE_LLM_MODEL", "gpt-4o")
        settings = BristlenoseSettings(_env_file=str(dotenv_in_cwd))
        assert settings.llm_provider == "openai"
        assert settings.llm_model == "gpt-4o"

    def test_dotenv_used_when_no_env_var(
        self, dotenv_in_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("BRISTLENOSE_LLM_PROVIDER", raising=False)
        monkeypatch.delenv("BRISTLENOSE_LLM_MODEL", raising=False)
        settings = BristlenoseSettings(_env_file=str(dotenv_in_cwd))
        assert settings.llm_provider == "anthropic"

    def test_desktop_ignores_dotenv_falls_to_coherent_default(
        self, dotenv_in_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The bug-prevention assertion. Desktop hosting, no env var injected
        # (the @AppStorage-default nil gap). With `.env` ignored, provider AND
        # model fall to Python defaults *together* — never anthropic + a stale
        # gpt-4o from a half-applied source.
        monkeypatch.setenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", "1")
        monkeypatch.delenv("BRISTLENOSE_LLM_PROVIDER", raising=False)
        monkeypatch.delenv("BRISTLENOSE_LLM_MODEL", raising=False)
        settings = BristlenoseSettings(_env_file=_find_env_files())
        assert settings.llm_provider == "anthropic"
        assert settings.llm_model.startswith("claude-")  # coherent with provider

    def test_desktop_full_injection_resolves_coherently(
        self, dotenv_in_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The happy path: GUI = ChatGPT, Swift injects provider+model+key.
        monkeypatch.setenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", "1")
        monkeypatch.setenv("BRISTLENOSE_LLM_PROVIDER", "openai")
        monkeypatch.setenv("BRISTLENOSE_LLM_MODEL", "gpt-4o")
        settings = BristlenoseSettings(_env_file=_find_env_files())
        assert settings.llm_provider == "openai"
        assert settings.llm_model == "gpt-4o"


class TestKeyFingerprint:
    def test_never_leaks_full_key(self) -> None:
        secret = "sk-ant-api03-SECRETBODY-wAA"
        fp = _key_fingerprint(secret)
        assert "SECRETBODY" not in fp
        assert fp.endswith("…-wAA)")  # last 4 chars only
        assert "len=" in fp

    def test_absent_key(self) -> None:
        assert _key_fingerprint("") == "absent"


class TestOrphanModelGuard:
    """Desktop defense: a model env var with no provider must not 404."""

    def test_orphan_model_snapped_to_provider_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The exact recurring bug: old Swift injects bare gpt-4o, no provider.
        monkeypatch.setattr(config, "_populate_keys_from_keychain", lambda s: s)
        monkeypatch.setenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", "1")
        monkeypatch.setenv("BRISTLENOSE_LLM_MODEL", "gpt-4o")
        monkeypatch.delenv("BRISTLENOSE_LLM_PROVIDER", raising=False)
        s = config.load_settings()
        assert s.llm_provider == "anthropic"
        assert s.llm_model == "claude-sonnet-4-20250514"  # NOT gpt-4o

    def test_coherent_pair_untouched(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config, "_populate_keys_from_keychain", lambda s: s)
        monkeypatch.setenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", "1")
        monkeypatch.setenv("BRISTLENOSE_LLM_PROVIDER", "openai")
        monkeypatch.setenv("BRISTLENOSE_LLM_MODEL", "gpt-4o")
        s = config.load_settings()
        assert s.llm_provider == "openai"
        assert s.llm_model == "gpt-4o"  # coherent — left alone

    def test_cli_model_override_not_orphan_guarded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Non-desktop CLI: a standalone model override is legitimate.
        monkeypatch.setattr(config, "_populate_keys_from_keychain", lambda s: s)
        monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)
        monkeypatch.setenv("BRISTLENOSE_LLM_MODEL", "gpt-4o")
        monkeypatch.delenv("BRISTLENOSE_LLM_PROVIDER", raising=False)
        s = config.load_settings()
        assert s.llm_model == "gpt-4o"  # CLI override respected


def test_resolution_ledger_built_and_replayable(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(config, "_populate_keys_from_keychain", lambda s: s)
    with caplog.at_level("INFO", logger="bristlenose.config"):
        config.load_settings(llm_provider="chatgpt")  # alias → openai
    msgs = [r.message for r in caplog.records]
    # Ledger covers inputs → alias → pydantic → final, each greppable.
    assert any("step=0-inputs" in m for m in msgs)
    assert any("step=1-alias" in m and "openai" in m for m in msgs)
    assert any("step=2-pydantic" in m for m in msgs)
    assert any("step=4-final" in m for m in msgs)
    # And it is stored for replay.
    trace = config.get_resolution_trace()
    assert trace and any("step=4-final" in line for line in trace)


def test_orphan_guard_recorded_in_ledger(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(config, "_populate_keys_from_keychain", lambda s: s)
    monkeypatch.setenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", "1")
    monkeypatch.setenv("BRISTLENOSE_LLM_MODEL", "gpt-4o")
    monkeypatch.delenv("BRISTLENOSE_LLM_PROVIDER", raising=False)
    with caplog.at_level("INFO", logger="bristlenose.config"):
        config.load_settings()
    msgs = [r.message for r in caplog.records]
    assert any("step=3-orphan-guard" in m and "gpt-4o" in m for m in msgs)
