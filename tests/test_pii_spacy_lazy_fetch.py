"""Tests for the spaCy lazy-fetch path in s07_pii_removal._ensure_spacy_model."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from bristlenose.stages.s07_pii_removal import _ensure_spacy_model
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
        installer.assert_called_once_with("en_core_web_sm")
        out = capsys.readouterr().out
        assert "Downloading PII detector (~12 MB, one-off)..." in out
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
