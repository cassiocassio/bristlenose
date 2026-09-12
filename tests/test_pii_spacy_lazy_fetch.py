"""Tests for the spaCy lazy-fetch path in s07_pii_removal._ensure_spacy_model."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bristlenose.stages.s07_pii_removal import (
    PII_MODEL_DIR_ENV,
    SPACY_MODEL,
    _ensure_spacy_model,
    resolve_spacy_model,
)
from bristlenose.utils.package_install import PackageInstallError


class TestEnsureSpacyModel:
    def test_already_installed_skips_download(self, capsys):
        fake_spacy = MagicMock()
        fake_spacy.load.return_value = MagicMock()
        with patch.dict(sys.modules, {"spacy": fake_spacy}):
            with patch(
                "bristlenose.utils.package_install.ensure_spacy_model"
            ) as installer:
                _ensure_spacy_model()
        installer.assert_not_called()
        # No "Downloading..." line should print on the silent path.
        assert "Downloading" not in capsys.readouterr().out

    def test_fresh_install_prints_inline_status(self, capsys):
        fake_spacy = MagicMock()
        # First load() raises OSError (model missing); second load() (the verify
        # retry after download) succeeds.
        fake_spacy.load.side_effect = [OSError("not found"), MagicMock()]
        with patch.dict(sys.modules, {"spacy": fake_spacy}):
            with patch(
                "bristlenose.utils.package_install.ensure_spacy_model"
            ) as installer:
                _ensure_spacy_model()
        installer.assert_called_once_with("en_core_web_lg")
        out = capsys.readouterr().out
        assert "Downloading PII detector (~400 MB, one-off)..." in out
        # MessageKind.SUCCESS glyph follows on the done path.
        assert "✓" in out  # ✓
        # Verify retry: spacy.load called twice (probe + post-install confirm).
        assert fake_spacy.load.call_count == 2

    def test_install_failure_propagates(self, capsys):
        fake_spacy = MagicMock()
        fake_spacy.load.side_effect = OSError("not found")
        with patch.dict(sys.modules, {"spacy": fake_spacy}):
            with patch(
                "bristlenose.utils.package_install.ensure_spacy_model"
            ) as installer:
                installer.side_effect = PackageInstallError("network down")
                with pytest.raises(PackageInstallError):
                    _ensure_spacy_model()
        # MessageKind.ERROR glyph on the failure path.
        assert "✗" in capsys.readouterr().out


def _fake_model_dir(tmp_path):
    """A directory shaped like a loadable spaCy model (config.cfg is the tell)."""
    d = tmp_path / "en_core_web_lg" / "en_core_web_lg-3.8.0"
    d.mkdir(parents=True)
    (d / "config.cfg").write_text("[nlp]\nlang = \"en\"\n", encoding="utf-8")
    return d


class TestResolveSpacyModel:
    """The one resolver every load site goes through.

    The macOS host places the weights — Background Assets on TestFlight and the
    store, a plain HTTPS download on the Developer-ID .dmg — and names the
    directory in the environment. The CLI leaves it unset and resolves by name.
    """

    def test_unset_resolves_to_the_model_name(self, monkeypatch):
        monkeypatch.delenv(PII_MODEL_DIR_ENV, raising=False)
        assert resolve_spacy_model() == SPACY_MODEL

    def test_a_valid_directory_resolves_to_an_absolute_path(self, tmp_path, monkeypatch):
        d = _fake_model_dir(tmp_path)
        monkeypatch.setenv(PII_MODEL_DIR_ENV, str(d))
        got = resolve_spacy_model()
        assert Path(got).is_absolute()
        assert Path(got) == d

    def test_a_relative_override_is_made_absolute(self, tmp_path, monkeypatch):
        """Presidio's guard is Path(name).exists(), which a bad relative path fails."""
        _fake_model_dir(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv(PII_MODEL_DIR_ENV, "en_core_web_lg/en_core_web_lg-3.8.0")
        assert Path(resolve_spacy_model()).is_absolute()

    def test_a_bogus_override_raises_rather_than_falling_back(self, tmp_path, monkeypatch):
        """Fail-loud is the whole point — see the next test for what falling back costs."""
        monkeypatch.setenv(PII_MODEL_DIR_ENV, str(tmp_path / "not-a-model"))
        with pytest.raises(ValueError, match="not a loadable"):
            resolve_spacy_model()

    def test_an_empty_override_is_treated_as_unset(self, monkeypatch):
        monkeypatch.setenv(PII_MODEL_DIR_ENV, "   ")
        assert resolve_spacy_model() == SPACY_MODEL


class TestPresidioDownloadGuard:
    """Encodes the trap this resolver exists to avoid.

    presidio_analyzer's SpacyNlpEngine builder runs

        if not (spacy.util.is_package(name) or Path(name).exists()):
            spacy.cli.download(name)      # -> pip install from GitHub

    So a *name* it cannot resolve makes a sandboxed App Store binary shell out to
    pip — a §2.5.2 violation. A *path* satisfies Path().exists() and the download
    branch is unreachable. This asserts the property directly, without importing
    Presidio, so it holds even where presidio is not installed.
    """

    def test_a_path_satisfies_the_guard_but_an_unresolvable_name_does_not(
        self, tmp_path, monkeypatch
    ):
        d = _fake_model_dir(tmp_path)
        monkeypatch.setenv(PII_MODEL_DIR_ENV, str(d))
        resolved = resolve_spacy_model()
        assert Path(resolved).exists(), "the path form must satisfy Presidio's guard"

        monkeypatch.delenv(PII_MODEL_DIR_ENV, raising=False)
        assert not Path(resolve_spacy_model()).exists(), (
            "the name form does NOT satisfy the guard — which is why the desktop "
            "must always supply a path, and why a bogus override raises instead "
            "of quietly returning the name"
        )


class TestEnsureSpacyModelWithASuppliedPath:
    def test_a_supplied_path_skips_the_fetch_entirely(self, tmp_path, monkeypatch):
        """Nothing to download: the host already placed the weights."""
        d = _fake_model_dir(tmp_path)
        monkeypatch.setenv(PII_MODEL_DIR_ENV, str(d))
        fake_spacy = MagicMock()
        fake_spacy.load.return_value = MagicMock()
        with patch.dict(sys.modules, {"spacy": fake_spacy}):
            with patch(
                "bristlenose.utils.package_install.ensure_spacy_model"
            ) as installer:
                _ensure_spacy_model()
        installer.assert_not_called()
        fake_spacy.load.assert_called_once_with(str(d))
