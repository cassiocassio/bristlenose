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

    def test_fresh_install_prints_framed_banner(self, capsys):
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
    # BOTH files: spaCy's load_model_from_path reads meta.json (via
    # get_model_meta) before it reads config.cfg, so a fixture with only the
    # latter is the degenerate case the resolver now rejects.
    (d / "meta.json").write_text('{"lang": "en", "name": "core_web_lg"}', encoding="utf-8")
    (d / "config.cfg").write_text('[nlp]\nlang = "en"\n', encoding="utf-8")
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


class TestModelDirLivenessNeedsBothFiles:
    """spaCy reads meta.json first, so config.cfg alone is not a loadable model."""

    def test_config_only_is_rejected(self, tmp_path, monkeypatch):
        d = tmp_path / "half-unpacked"
        d.mkdir()
        (d / "config.cfg").write_text("[nlp]\n", encoding="utf-8")
        monkeypatch.setenv(PII_MODEL_DIR_ENV, str(d))
        with pytest.raises(ValueError, match="not a loadable"):
            resolve_spacy_model()

    def test_meta_only_is_rejected(self, tmp_path, monkeypatch):
        d = tmp_path / "half-unpacked"
        d.mkdir()
        (d / "meta.json").write_text("{}", encoding="utf-8")
        monkeypatch.setenv(PII_MODEL_DIR_ENV, str(d))
        with pytest.raises(ValueError, match="not a loadable"):
            resolve_spacy_model()


class TestNoFetchIsHonoured:
    """`--no-fetch` means "do not reach the network".

    A silent 425 MB download is the largest possible way to disobey that flag,
    and until 12 Sep 2026 stage 7 did exactly that: `_ensure_spacy_model` took
    no argument and `settings.no_fetch` never reached it. Whisper's preflight
    has honoured the same flag since it was introduced, so this was the one
    heavyweight fetch in the pipeline that ignored it.
    """

    def test_missing_model_under_no_fetch_refuses_instead_of_downloading(self):
        fake_spacy = MagicMock()
        fake_spacy.load.side_effect = OSError("not found")
        with patch.dict(sys.modules, {"spacy": fake_spacy}):
            with patch(
                "bristlenose.utils.package_install.ensure_spacy_model"
            ) as installer:
                with pytest.raises(PackageInstallError) as exc_info:
                    _ensure_spacy_model(allow_fetch=False)
        installer.assert_not_called()
        assert "--no-fetch" in str(exc_info.value)

    def test_refusal_classifies_as_missing_dep(self):
        """So the desktop gets a routable row, not `unknown`.

        `PackageInstallError` is deliberate rather than a bespoke abort type:
        stage 7's handler turns it into a clean abandon with a privacy-safe
        Cause, and this is the arm that decides which row the project shows.
        """
        from bristlenose.events import CauseCategoryEnum
        from bristlenose.run_lifecycle import categorise_exception

        fake_spacy = MagicMock()
        fake_spacy.load.side_effect = OSError("not found")
        with patch.dict(sys.modules, {"spacy": fake_spacy}):
            with patch("bristlenose.utils.package_install.ensure_spacy_model"):
                with pytest.raises(PackageInstallError) as exc_info:
                    _ensure_spacy_model(allow_fetch=False)

        cause = categorise_exception(exc_info.value)
        assert cause.category == CauseCategoryEnum.MISSING_DEP

    def test_present_model_under_no_fetch_is_not_disturbed(self):
        """`--no-fetch` forbids fetching, not using what is already there."""
        fake_spacy = MagicMock()
        fake_spacy.load.return_value = MagicMock()
        with patch.dict(sys.modules, {"spacy": fake_spacy}):
            with patch(
                "bristlenose.utils.package_install.ensure_spacy_model"
            ) as installer:
                _ensure_spacy_model(allow_fetch=False)
        installer.assert_not_called()

    def test_stage_seven_threads_the_flag_from_settings(self):
        """The wiring, not just the helper — the defect was the missing arg.

        `_ensure_spacy_model` could refuse perfectly and still download 425 MB
        if `_init_presidio` never passed `settings.no_fetch` through, which is
        precisely the bug this closes.
        """
        from bristlenose.stages import s07_pii_removal

        settings = MagicMock()
        settings.no_fetch = True

        with patch.object(s07_pii_removal, "_ensure_spacy_model") as ensure:
            ensure.side_effect = PackageInstallError("refused")
            with pytest.raises(PackageInstallError):
                s07_pii_removal._init_presidio(settings)

        ensure.assert_called_once_with(allow_fetch=False, status=None)


class TestDownloaderGetsTheTerminalToItself:
    """The 425 MB download must not be written over.

    `ensure_spacy_model` shells out with `subprocess.run(..., check=True)` and
    **no capture**, so pip writes progress straight to our stdout — while
    `Pipeline.run` holds a Rich `console.status` spinner open across the entire
    run. Two things therefore have to be true: our own line must be terminated
    (it used to be `end=""`, so pip's first line landed on it), and the spinner
    must be stopped for the duration. Whisper's preflight already does both.
    """

    def test_our_line_is_terminated_before_the_downloader_writes(self, capsys):
        fake_spacy = MagicMock()
        fake_spacy.load.side_effect = [OSError("not found"), MagicMock()]
        with patch.dict(sys.modules, {"spacy": fake_spacy}):
            with patch("bristlenose.utils.package_install.ensure_spacy_model"):
                _ensure_spacy_model()
        out = capsys.readouterr().out
        # The banner line ends; nothing may be appended to it.
        assert "one-off)...\n" in out, (
            f"downloading line was not terminated — pip's output will land on "
            f"it: {out!r}"
        )

    def test_spinner_is_stopped_around_the_download_and_restarted(self):
        stopped_during_download = []
        status = MagicMock()

        fake_spacy = MagicMock()
        fake_spacy.load.side_effect = [OSError("not found"), MagicMock()]

        def _record(_model):
            stopped_during_download.append(status.stop.called)

        with patch.dict(sys.modules, {"spacy": fake_spacy}):
            with patch(
                "bristlenose.utils.package_install.ensure_spacy_model", new=_record
            ):
                _ensure_spacy_model(status=status)

        assert stopped_during_download == [True], (
            "the spinner was still running while the downloader wrote to stdout"
        )
        status.start.assert_called_once()

    def test_spinner_is_restarted_even_when_the_download_fails(self):
        """Otherwise one failed fetch leaves the rest of the run with no spinner."""
        status = MagicMock()
        fake_spacy = MagicMock()
        fake_spacy.load.side_effect = OSError("not found")

        with patch.dict(sys.modules, {"spacy": fake_spacy}):
            with patch(
                "bristlenose.utils.package_install.ensure_spacy_model"
            ) as installer:
                installer.side_effect = PackageInstallError("network down")
                with pytest.raises(PackageInstallError):
                    _ensure_spacy_model(status=status)

        status.stop.assert_called_once()
        status.start.assert_called_once()


@pytest.mark.slow
def test_a_path_delivered_model_redacts_with_no_package_installed(monkeypatch):
    """The assumption the whole .dmg / TestFlight delivery rests on.

    Those two acquirers unpack a model *directory* and set
    `BRISTLENOSE_PII_MODEL_DIR`; `spacy download` never runs, so the importable
    package does not exist on those machines. Everything else in the tree only
    proves `resolve_spacy_model()` *returns* the path — nothing proved Presidio
    would load and behave from one, and the place to discover otherwise is not
    TestFlight.

    Blocking the import is what makes this a real test rather than a
    coincidence: without it the installed package could be doing the work.

    Measured 12 Sep 2026 on the planted-PII corpus: the path route scored
    identically to the package route — 45/52 targeted, 9/32 false positives,
    92 redactions, same misses.
    """
    import importlib.util
    from datetime import datetime, timezone

    from bristlenose.config import BristlenoseSettings
    from bristlenose.models import FullTranscript, TranscriptSegment
    from bristlenose.stages.s07_pii_removal import remove_pii

    spec = importlib.util.find_spec("en_core_web_lg")
    if spec is None or not spec.submodule_search_locations:
        pytest.skip("en_core_web_lg not installed")
    pkg_dir = Path(list(spec.submodule_search_locations)[0])
    model_dirs = [
        d for d in pkg_dir.iterdir()
        if d.is_dir() and (d / "meta.json").is_file() and (d / "config.cfg").is_file()
    ]
    assert model_dirs, f"no unpacked model directory under {pkg_dir}"

    class _Blocker:
        """Make the package unimportable — a .dmg machine has never seen it."""

        def find_spec(self, name, path=None, target=None):
            if name == "en_core_web_lg":
                raise ModuleNotFoundError(name)
            return None

    blocker = _Blocker()
    sys.meta_path.insert(0, blocker)
    try:
        monkeypatch.setenv(PII_MODEL_DIR_ENV, str(model_dirs[0]))
        assert resolve_spacy_model() != SPACY_MODEL, "should resolve to a path"

        transcript = FullTranscript(
            session_id="s1",
            participant_id="p1",
            source_file="x.txt",
            session_date=datetime.now(timezone.utc),
            duration_seconds=30.0,
            segments=[
                TranscriptSegment(
                    start_time=0.0,
                    end_time=5.0,
                    text="I spoke to Priya Raghunathan about the onboarding flow.",
                    source="whisper",
                    segment_index=0,
                )
            ],
        )
        clean, redactions = remove_pii(
            [transcript], BristlenoseSettings(project_name="t", pii_enabled=True)
        )
    finally:
        sys.meta_path.remove(blocker)

    assert "Priya Raghunathan" not in clean[0].segments[0].text
    assert redactions, "the path-delivered model detected nothing at all"
