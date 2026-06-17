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


class TestRunCommandDefaultDoesNotOverrideEnv:
    """The `run`/`analyze` --llm flag must NOT override an injected env provider.

    Regression: --llm defaulted to "claude" and was always passed as a CLI override,
    which beat the desktop-injected BRISTLENOSE_LLM_PROVIDER=openai → the run resolved
    to the anthropic endpoint while the model env var (gpt-4o) rode along → 404. The
    fix defaults --llm to None and only passes it when explicitly set. This test pins
    the invariant at the resolution layer: when llm_provider is NOT in overrides and a
    provider env var is present, the env var wins.
    """

    def test_env_provider_wins_when_no_cli_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(config, "_populate_keys_from_keychain", lambda s: s)
        monkeypatch.setenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", "1")
        monkeypatch.setenv("BRISTLENOSE_LLM_PROVIDER", "openai")
        monkeypatch.setenv("BRISTLENOSE_LLM_MODEL", "gpt-4o")
        # Mimic run() AFTER the fix: llm_provider omitted from kwargs entirely.
        s = config.load_settings(project_name="x", no_fetch=False)
        assert s.llm_provider == "openai"
        assert s.llm_model == "gpt-4o"

    def test_explicit_cli_override_still_wins(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(config, "_populate_keys_from_keychain", lambda s: s)
        monkeypatch.setenv("BRISTLENOSE_LLM_PROVIDER", "openai")
        # User explicitly passed --llm claude → still honoured.
        s = config.load_settings(llm_provider="claude")
        assert s.llm_provider == "anthropic"


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
        assert s.llm_model == "claude-sonnet-4-6"  # NOT gpt-4o

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


class TestProviderDefaultModelFill:
    """CLI: ``--llm <provider>`` with no model adopts that provider's default model.

    The bug: ``bristlenose run <folder> --llm chatgpt`` resolved provider=openai but
    left ``llm_model`` at the Anthropic code-default, which 404s when sent to OpenAI
    (cross-provider ``model_not_found``) → ``PipelineAbandonedError`` at s08. The fill
    snaps a *never-chosen* model to the resolved provider's ``default_model``. Gated to
    the CLI (no-op under desktop, which injects an explicit model) and to the
    code-default *value* (any explicitly-chosen model wins — rule 1).
    """

    def test_chatgpt_alias_fills_gpt_4o(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config, "_populate_keys_from_keychain", lambda s: s)
        monkeypatch.delenv("BRISTLENOSE_LLM_MODEL", raising=False)
        monkeypatch.delenv("BRISTLENOSE_LLM_PROVIDER", raising=False)
        s = config.load_settings(llm_provider="chatgpt")  # alias → openai
        assert s.llm_provider == "openai"
        assert s.llm_model == "gpt-4o"

    def test_gemini_fills_gemini_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config, "_populate_keys_from_keychain", lambda s: s)
        monkeypatch.delenv("BRISTLENOSE_LLM_MODEL", raising=False)
        monkeypatch.delenv("BRISTLENOSE_LLM_PROVIDER", raising=False)
        s = config.load_settings(llm_provider="gemini")  # alias → google
        assert s.llm_provider == "google"
        assert s.llm_model == "gemini-2.5-flash"

    def test_claude_keeps_code_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config, "_populate_keys_from_keychain", lambda s: s)
        monkeypatch.delenv("BRISTLENOSE_LLM_MODEL", raising=False)
        monkeypatch.delenv("BRISTLENOSE_LLM_PROVIDER", raising=False)
        s = config.load_settings(llm_provider="claude")  # alias → anthropic
        assert s.llm_provider == "anthropic"
        # default == provider default → no snap. Assert against the field default
        # (the implementation's own expression) so an Anthropic-default bump doesn't
        # redden this without a behaviour change.
        assert s.llm_model == BristlenoseSettings.model_fields["llm_model"].default

    def test_fill_fires_when_dotenv_present_but_sets_no_model(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The gap a source-label gate (`model_source == "code-default"`) would miss:
        # `_src` reports "dotenv-file" whenever a .env merely EXISTS, even if it sets
        # no model line. A user with provider+key in .env but no model must still get
        # the coherent provider default, not the Anthropic code-default → 404. The
        # value gate fires regardless of the source label. Goes red if anyone reverts
        # to a source-label gate.
        monkeypatch.setattr(config, "_populate_keys_from_keychain", lambda s: s)
        monkeypatch.setattr(config, "_find_env_files", lambda: [Path("/fake/.env")])
        monkeypatch.delenv("BRISTLENOSE_LLM_MODEL", raising=False)
        monkeypatch.delenv("BRISTLENOSE_LLM_PROVIDER", raising=False)
        s = config.load_settings(llm_provider="chatgpt")
        assert s.llm_model == "gpt-4o"

    def test_explicit_env_model_wins_over_fill(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Rule 1 precedes the value gate: a user who explicitly sets
        # BRISTLENOSE_LLM_MODEL to the Anthropic default string AND picks chatgpt has
        # made an (incoherent) explicit choice — the rule-1 short-circuit honours it
        # and does NOT snap, even though the value equals the code-default.
        monkeypatch.setattr(config, "_populate_keys_from_keychain", lambda s: s)
        monkeypatch.setenv("BRISTLENOSE_LLM_MODEL", "claude-sonnet-4-20250514")
        monkeypatch.delenv("BRISTLENOSE_LLM_PROVIDER", raising=False)
        s = config.load_settings(llm_provider="chatgpt")
        assert s.llm_model == "claude-sonnet-4-20250514"  # explicit env wins

    def test_azure_not_filled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Azure's default_model is "" (deployment names) → no snap.
        monkeypatch.setattr(config, "_populate_keys_from_keychain", lambda s: s)
        monkeypatch.delenv("BRISTLENOSE_LLM_MODEL", raising=False)
        monkeypatch.delenv("BRISTLENOSE_LLM_PROVIDER", raising=False)
        s = config.load_settings(llm_provider="azure")
        assert s.llm_provider == "azure"
        assert s.llm_model == BristlenoseSettings.model_fields["llm_model"].default  # unchanged


def test_anthropic_default_matches_field_default() -> None:
    # _fill_provider_default_model's value gate compares llm_model against the field
    # default; that stays correct only while the field default (config.py) and the
    # Anthropic registry default (providers.py) agree. They are independent literals
    # in two files — pin their equality so a one-sided bump reddens CI instead of
    # silently mis-firing the gate.
    from bristlenose.providers import PROVIDERS

    assert (
        BristlenoseSettings.model_fields["llm_model"].default
        == PROVIDERS["anthropic"].default_model
    )


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


def test_provider_default_fill_recorded_in_ledger(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(config, "_populate_keys_from_keychain", lambda s: s)
    monkeypatch.delenv("BRISTLENOSE_LLM_MODEL", raising=False)
    monkeypatch.delenv("BRISTLENOSE_LLM_PROVIDER", raising=False)
    with caplog.at_level("INFO", logger="bristlenose.config"):
        config.load_settings(llm_provider="chatgpt")  # alias → openai, no model
    msgs = [r.message for r in caplog.records]
    # Token presence, not the verbatim sentence (don't lock the formatting).
    assert any("step=3-provider-default" in m and "gpt-4o" in m for m in msgs)


class TestCliProviderDecisionLedger:
    """The CLI layer records its --llm forward-or-not decision in the ledger.

    load_settings only sees the *result* (llm_provider in overrides or not). The
    forwarding decision is made one layer up, in the run/analyze command — the
    actor that produced the 8 Jun 404 by forwarding a non-None --llm default that
    silently beat the desktop-injected env var. `describe_cli_provider_decision`
    + `note_resolution_input` make that decision legible, attributed to cli.py,
    at the front of the resolution trace. Pure-Python, so it's pinned in the only
    CI-running suite (the Swift spawn path can't be).
    """

    def test_forwarded_decision_is_pure_and_legible(self) -> None:
        line = config.describe_cli_provider_decision(
            "openai", hosted=True, command="run"
        )
        assert "step=cli-args" in line
        assert "event=run --llm [cli.py]" in line
        assert "'openai'" in line
        assert "forwarding as cli-override" in line
        assert "hosted_by_desktop=True" in line

    def test_absent_decision_is_pure_and_legible(self) -> None:
        line = config.describe_cli_provider_decision(
            None, hosted=False, command="analyze"
        )
        assert "step=cli-args" in line
        assert "event=analyze --llm [cli.py]" in line
        assert "--llm absent -> not forwarding" in line
        assert "hosted_by_desktop=False" in line

    def test_pending_note_drained_to_front_of_trace(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(config, "_populate_keys_from_keychain", lambda s: s)
        config.note_resolution_input(
            config.describe_cli_provider_decision(
                None, hosted=True, command="run"
            )
        )
        config.load_settings()
        trace = config.get_resolution_trace()
        # The CLI note leads the ledger, above load_settings' own step-0-inputs.
        assert trace[0].startswith("llm_resolve | step=cli-args")
        assert any("step=0-inputs" in line for line in trace)
        assert trace.index(trace[0]) < next(
            i for i, line in enumerate(trace) if "step=0-inputs" in line
        )

    def test_pending_note_cleared_after_drain(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(config, "_populate_keys_from_keychain", lambda s: s)
        config.note_resolution_input("llm_resolve | step=cli-args | once")
        config.load_settings()
        # A second resolution must not re-emit the first run's note (the sidecar
        # resolves once per process, but a stale note must never leak across runs).
        config.load_settings()
        trace = config.get_resolution_trace()
        assert not any("once" in line for line in trace)


class TestHostResolutionTrace:
    """The desktop host's cross-seam resolution lines lead every ledger.

    The Swift host (BristlenoseShared.childEnvironment) injects a newline-joined
    block of `step=host-defaults` lines describing the provider/model/key decision
    that produced the env vars this process inherits. Unlike the CLI-note queue,
    this is a stable PROPERTY of the spawn: re-read on every load_settings() call
    and never cleared, so autocode/analysis/run resolutions in one long-lived
    serve process all carry the same cross-seam origin. The 8 Jun 404 lived
    entirely on the Swift side of this seam, invisible to Python — these lines
    make it legible in the run log.
    """

    def test_drain_empty_when_not_hosted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("_BRISTLENOSE_HOST_RESOLUTION_TRACE", raising=False)
        assert config._drain_host_resolution_trace() == []

    def test_drain_splits_and_filters_blanks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(
            "_BRISTLENOSE_HOST_RESOLUTION_TRACE",
            "llm_resolve | step=host-defaults | a\n\nllm_resolve | "
            "step=host-defaults | b\n",
        )
        lines = config._drain_host_resolution_trace()
        assert lines == [
            "llm_resolve | step=host-defaults | a",
            "llm_resolve | step=host-defaults | b",
        ]

    def test_host_block_leads_the_ledger(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(config, "_populate_keys_from_keychain", lambda s: s)
        monkeypatch.setenv(
            "_BRISTLENOSE_HOST_RESOLUTION_TRACE",
            "llm_resolve | step=host-defaults | event=spawn [Swift] | "
            "activeProvider='openai' | key=present",
        )
        # A CLI note too, to pin the ordering host-defaults -> cli-args -> 0-inputs.
        config.note_resolution_input(
            config.describe_cli_provider_decision(None, hosted=True, command="run")
        )
        config.load_settings()
        trace = config.get_resolution_trace()
        assert trace[0].startswith("llm_resolve | step=host-defaults")
        host_i = 0
        cli_i = next(i for i, ln in enumerate(trace) if "step=cli-args" in ln)
        inputs_i = next(i for i, ln in enumerate(trace) if "step=0-inputs" in ln)
        assert host_i < cli_i < inputs_i

    def test_host_block_reread_every_call_not_cleared(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(config, "_populate_keys_from_keychain", lambda s: s)
        monkeypatch.setenv(
            "_BRISTLENOSE_HOST_RESOLUTION_TRACE",
            "llm_resolve | step=host-defaults | sticky",
        )
        # Idempotent env read: a second resolution (e.g. autocode after the run)
        # must STILL carry the origin — the env var is a property of the spawn.
        config.load_settings()
        config.load_settings()
        trace = config.get_resolution_trace()
        assert any("sticky" in line for line in trace)
