"""Unit tests for bristlenose.utils.bundled_binary.bundled_binary_path."""

from __future__ import annotations

import os
import stat
from unittest.mock import patch

from bristlenose.utils.bundled_binary import (
    bundled_binaries_dir,
    bundled_binary_path,
    prepend_bundled_to_path,
)


class TestEnvVarBranch:
    """Branch 1: BRISTLENOSE_<NAME> env var wins."""

    def test_env_var_returned_verbatim(self, monkeypatch):
        monkeypatch.setenv("BRISTLENOSE_FFMPEG", "/some/explicit/path/ffmpeg")
        monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)
        assert bundled_binary_path("ffmpeg") == "/some/explicit/path/ffmpeg"

    def test_env_var_uppercased(self, monkeypatch):
        monkeypatch.setenv("BRISTLENOSE_FFPROBE", "/p/ffprobe")
        assert bundled_binary_path("ffprobe") == "/p/ffprobe"

    def test_empty_env_var_falls_through(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BRISTLENOSE_FFMPEG", "")
        monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)
        with patch("bristlenose.utils.bundled_binary.shutil.which", return_value="/from/which"):
            assert bundled_binary_path("ffmpeg") == "/from/which"


class TestBundleRelativeBranch:
    """Branch 2: _BRISTLENOSE_HOSTED_BY_DESKTOP=1 + bundle layout."""

    def test_bundle_relative_when_hosted_and_executable(self, monkeypatch, tmp_path):
        monkeypatch.delenv("BRISTLENOSE_FFMPEG", raising=False)
        monkeypatch.setenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", "1")

        # Mimic Contents/Resources/bristlenose-sidecar/bristlenose-sidecar
        resources = tmp_path / "Resources"
        sidecar_dir = resources / "bristlenose-sidecar"
        sidecar_dir.mkdir(parents=True)
        sidecar = sidecar_dir / "bristlenose-sidecar"
        sidecar.write_text("#!/bin/sh\n")
        sidecar.chmod(sidecar.stat().st_mode | stat.S_IEXEC)

        ffmpeg = resources / "ffmpeg"
        ffmpeg.write_text("#!/bin/sh\n")
        ffmpeg.chmod(ffmpeg.stat().st_mode | stat.S_IEXEC)

        with patch("bristlenose.utils.bundled_binary.sys.executable", str(sidecar)):
            assert bundled_binary_path("ffmpeg") == str(ffmpeg)

    def test_bundle_relative_skipped_when_sentinel_unset(self, monkeypatch):
        monkeypatch.delenv("BRISTLENOSE_FFMPEG", raising=False)
        monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)
        with patch("bristlenose.utils.bundled_binary.shutil.which", return_value="/usr/local/bin/ffmpeg"):
            assert bundled_binary_path("ffmpeg") == "/usr/local/bin/ffmpeg"

    def test_bundle_relative_falls_through_when_file_missing(self, monkeypatch, tmp_path):
        monkeypatch.delenv("BRISTLENOSE_FFMPEG", raising=False)
        monkeypatch.setenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", "1")

        resources = tmp_path / "Resources"
        sidecar_dir = resources / "bristlenose-sidecar"
        sidecar_dir.mkdir(parents=True)
        sidecar = sidecar_dir / "bristlenose-sidecar"
        sidecar.write_text("")
        # Note: no ffmpeg file written — bundle branch must fall through

        with patch("bristlenose.utils.bundled_binary.sys.executable", str(sidecar)), \
             patch("bristlenose.utils.bundled_binary.shutil.which", return_value="/which/ffmpeg"):
            assert bundled_binary_path("ffmpeg") == "/which/ffmpeg"

    def test_bundle_relative_falls_through_when_not_executable(self, monkeypatch, tmp_path):
        monkeypatch.delenv("BRISTLENOSE_FFMPEG", raising=False)
        monkeypatch.setenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", "1")

        resources = tmp_path / "Resources"
        sidecar_dir = resources / "bristlenose-sidecar"
        sidecar_dir.mkdir(parents=True)
        sidecar = sidecar_dir / "bristlenose-sidecar"
        sidecar.write_text("")

        ffmpeg = resources / "ffmpeg"
        ffmpeg.write_text("")
        # Mode 0o644 — present but not executable
        ffmpeg.chmod(0o644)

        with patch("bristlenose.utils.bundled_binary.sys.executable", str(sidecar)), \
             patch("bristlenose.utils.bundled_binary.shutil.which", return_value="/which/ffmpeg"):
            assert bundled_binary_path("ffmpeg") == "/which/ffmpeg"


class TestPathFallback:
    """Branch 3: shutil.which fallback for CLI users."""

    def test_which_used_when_no_env_var_no_sentinel(self, monkeypatch):
        monkeypatch.delenv("BRISTLENOSE_FFMPEG", raising=False)
        monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)
        with patch("bristlenose.utils.bundled_binary.shutil.which", return_value="/opt/homebrew/bin/ffmpeg"):
            assert bundled_binary_path("ffmpeg") == "/opt/homebrew/bin/ffmpeg"

    def test_returns_none_when_nothing_found(self, monkeypatch):
        monkeypatch.delenv("BRISTLENOSE_FFMPEG", raising=False)
        monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)
        with patch("bristlenose.utils.bundled_binary.shutil.which", return_value=None):
            assert bundled_binary_path("ffmpeg") is None


class TestPriorityOrdering:
    """Env var beats bundle; bundle beats which."""

    def test_env_var_beats_bundle(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BRISTLENOSE_FFMPEG", "/explicit/ffmpeg")
        monkeypatch.setenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", "1")

        resources = tmp_path / "Resources"
        sidecar_dir = resources / "bristlenose-sidecar"
        sidecar_dir.mkdir(parents=True)
        sidecar = sidecar_dir / "bristlenose-sidecar"
        sidecar.write_text("")
        ffmpeg = resources / "ffmpeg"
        ffmpeg.write_text("")
        ffmpeg.chmod(ffmpeg.stat().st_mode | stat.S_IEXEC)

        with patch("bristlenose.utils.bundled_binary.sys.executable", str(sidecar)):
            # Env var wins over bundle
            assert bundled_binary_path("ffmpeg") == "/explicit/ffmpeg"


class TestBundledBinariesDir:
    """bundled_binaries_dir resolves the directory holding bundled ffmpeg/ffprobe."""

    def test_returns_none_outside_bundle(self, monkeypatch):
        monkeypatch.delenv("BRISTLENOSE_FFMPEG", raising=False)
        monkeypatch.delenv("BRISTLENOSE_FFPROBE", raising=False)
        monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)
        assert bundled_binaries_dir() is None

    def test_resolves_from_env_var_parent(self, monkeypatch, tmp_path):
        monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)
        ffmpeg = tmp_path / "ffmpeg"
        ffmpeg.write_text("")
        monkeypatch.setenv("BRISTLENOSE_FFMPEG", str(ffmpeg))
        assert bundled_binaries_dir() == tmp_path

    def test_resolves_from_bundle_layout(self, monkeypatch, tmp_path):
        monkeypatch.delenv("BRISTLENOSE_FFMPEG", raising=False)
        monkeypatch.delenv("BRISTLENOSE_FFPROBE", raising=False)
        monkeypatch.setenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", "1")
        resources = tmp_path / "Resources"
        sidecar_dir = resources / "bristlenose-sidecar"
        sidecar_dir.mkdir(parents=True)
        sidecar = sidecar_dir / "bristlenose-sidecar"
        sidecar.write_text("")
        with patch("bristlenose.utils.bundled_binary.sys.executable", str(sidecar)):
            assert bundled_binaries_dir() == resources.resolve()


class TestPrependBundledToPath:
    """prepend_bundled_to_path makes bundled ffmpeg reachable to bare-name shellouts."""

    def test_noop_outside_bundle(self, monkeypatch):
        monkeypatch.delenv("BRISTLENOSE_FFMPEG", raising=False)
        monkeypatch.delenv("BRISTLENOSE_FFPROBE", raising=False)
        monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)
        monkeypatch.setenv("PATH", "/usr/bin:/bin")
        prepend_bundled_to_path()
        assert os.environ["PATH"] == "/usr/bin:/bin"

    def test_prepends_when_bundle_dir_resolved(self, monkeypatch, tmp_path):
        monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)
        ffmpeg = tmp_path / "ffmpeg"
        ffmpeg.write_text("")
        monkeypatch.setenv("BRISTLENOSE_FFMPEG", str(ffmpeg))
        monkeypatch.setenv("PATH", "/usr/bin")
        prepend_bundled_to_path()
        assert os.environ["PATH"] == f"{tmp_path}{os.pathsep}/usr/bin"

    def test_idempotent(self, monkeypatch, tmp_path):
        monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)
        ffmpeg = tmp_path / "ffmpeg"
        ffmpeg.write_text("")
        monkeypatch.setenv("BRISTLENOSE_FFMPEG", str(ffmpeg))
        monkeypatch.setenv("PATH", "/usr/bin")
        prepend_bundled_to_path()
        prepend_bundled_to_path()
        # Single prepend, not doubled
        assert os.environ["PATH"] == f"{tmp_path}{os.pathsep}/usr/bin"

    def test_handles_empty_path(self, monkeypatch, tmp_path):
        monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)
        ffmpeg = tmp_path / "ffmpeg"
        ffmpeg.write_text("")
        monkeypatch.setenv("BRISTLENOSE_FFMPEG", str(ffmpeg))
        monkeypatch.setenv("PATH", "")
        prepend_bundled_to_path()
        assert os.environ["PATH"] == str(tmp_path)
