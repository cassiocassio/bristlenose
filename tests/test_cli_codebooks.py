"""Tests for the C1 CLI codebook plumbing: `codebooks` subcommand + `--codebook` flag."""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from bristlenose.cli import _validate_codebook_slug, app
from bristlenose.server.codebook import list_available_slugs, load_all_templates

# ---------------------------------------------------------------------------
# _validate_codebook_slug (unit)
# ---------------------------------------------------------------------------


class TestValidateCodebookSlug:
    def test_known_slug_returns_none(self) -> None:
        """A real slug validates silently (no exit, no return value)."""
        slug = list_available_slugs()[0]
        assert _validate_codebook_slug(slug) is None

    def test_unknown_slug_exits_two(self) -> None:
        """Bogus slugs exit with code 2 (preflight-abort convention)."""
        with pytest.raises(typer.Exit) as exc_info:
            _validate_codebook_slug("bogus-codebook-name")
        assert exc_info.value.exit_code == 2

    def test_unknown_slug_self_correctable(self, capsys: pytest.CaptureFixture[str]) -> None:
        """The error output gives the user enough to self-correct."""
        with pytest.raises(typer.Exit):
            _validate_codebook_slug("does-not-exist")
        out = capsys.readouterr().out
        assert "Unknown codebook" in out
        assert "Available:" in out
        assert "bristlenose codebooks" in out

    def test_empty_available_list_omits_available_line(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """When every codebook is disabled, the validator still exits cleanly
        and skips the empty `Available:` line."""
        monkeypatch.setattr("bristlenose.cli.list_available_slugs", lambda: [], raising=False)
        # The CLI helper imports lazily, so patch at the source module too.
        monkeypatch.setattr(
            "bristlenose.server.codebook.list_available_slugs", lambda: []
        )
        with pytest.raises(typer.Exit):
            _validate_codebook_slug("anything")
        out = capsys.readouterr().out
        assert "Unknown codebook" in out
        assert "Available:" not in out


# ---------------------------------------------------------------------------
# `bristlenose codebooks` subcommand
# ---------------------------------------------------------------------------


class TestCodebooksCommand:
    def test_codebooks_exits_clean(self) -> None:
        result = CliRunner().invoke(app, ["codebooks"])
        assert result.exit_code == 0

    def test_codebooks_lists_every_enabled_slug(self) -> None:
        """Silent regression target: a YAML parse error dropping a codebook
        from the list would otherwise go unnoticed."""
        result = CliRunner().invoke(app, ["codebooks"])
        assert result.exit_code == 0
        for slug in list_available_slugs():
            assert slug in result.output


# ---------------------------------------------------------------------------
# `--codebook` flag on `run` and `analyze`
# ---------------------------------------------------------------------------


class TestCodebookFlagPropagation:
    """Bogus slug must abort BEFORE settings load / pipeline spawn."""

    def test_run_rejects_bogus_codebook(self, tmp_path: Path) -> None:
        result = CliRunner().invoke(
            app, ["run", "--codebook=does-not-exist", str(tmp_path)]
        )
        assert result.exit_code == 2
        assert "Unknown codebook" in result.output

    def test_analyze_rejects_bogus_codebook(self, tmp_path: Path) -> None:
        result = CliRunner().invoke(
            app, ["analyze", "--codebook=does-not-exist", str(tmp_path)]
        )
        assert result.exit_code == 2
        assert "Unknown codebook" in result.output


# ---------------------------------------------------------------------------
# Settings carries the field
# ---------------------------------------------------------------------------


class TestSettingsCarriesCodebook:
    def test_load_settings_accepts_codebook(self) -> None:
        from bristlenose.config import load_settings

        settings = load_settings(codebook="garrett")
        assert settings.codebook == "garrett"

    def test_load_settings_default_is_none(self) -> None:
        from bristlenose.config import load_settings

        settings = load_settings()
        assert settings.codebook is None


# ---------------------------------------------------------------------------
# list_available_slugs helper
# ---------------------------------------------------------------------------


class TestListAvailableSlugs:
    def test_returns_only_enabled_in_display_order(self) -> None:
        """Combined invariant: only enabled templates, in the same order as
        load_all_templates yields them."""
        slugs = list_available_slugs()
        ordered_enabled = [t.id for t in load_all_templates() if t.enabled]
        assert slugs == ordered_enabled
