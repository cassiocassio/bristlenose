"""What `discover_files` will and won't walk, and what it refuses outright.

Three behaviours that used to be one conflated guard:

* **Depth** — real folder shapes nest. A study grouped into weeks, each holding
  per-meeting Zoom folders, puts the media three levels below the drop point.
* **Refusal** — a filesystem or system root is not a study, at any file count.
  This is the actual protection against a root drop; the old session-count
  prompt never was, because it fired *after* the scan it was meant to gate.
* **Resilience** — one unreadable directory must not end the walk, and one
  cloud placeholder must not trigger a download.

No test here shells out: `probe_duration` is patched, so these run in CI where
there is no ffmpeg.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from bristlenose.refusals import UnusableReason
from bristlenose.stages import s01_ingest
from bristlenose.stages.s01_ingest import (
    SkippedFile,
    UnsuitableInputDirError,
    discover_files,
    group_into_sessions,
)


@pytest.fixture(autouse=True)
def _no_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(s01_ingest, "probe_duration", lambda p: 12.0)


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00")
    return path


class TestDepth:
    def test_walks_three_levels_and_stops(self, tmp_path: Path) -> None:
        """`project/week1/zoom1/video.mp4` is the shape that sets the limit."""
        _touch(tmp_path / "top.mp4")
        _touch(tmp_path / "week1" / "mid.mp4")
        _touch(tmp_path / "week1" / "zoom1" / "deep.mp4")
        _touch(tmp_path / "a" / "b" / "c" / "toodeep.mp4")

        found = {f.path.name for f in discover_files(tmp_path)}

        assert found == {"top.mp4", "mid.mp4", "deep.mp4"}
        assert "toodeep.mp4" not in found

    def test_zoom_folders_group_by_directory_at_depth(self, tmp_path: Path) -> None:
        """The Zoom rule keys on the *containing* folder, so depth is irrelevant.

        This is why three levels removes Zoom's special-casing rather than
        deepening it: `zoom1/` is just a folder that happens to hold media.
        """
        for meeting in ("2026-01-15 14.30.22 Kickoff 987654321",
                        "2026-01-16 09.05.10 Followup 987654322"):
            _touch(tmp_path / "week1" / meeting / "video.mp4")
            _touch(tmp_path / "week1" / meeting / "audio.m4a")

        sessions = group_into_sessions(discover_files(tmp_path))

        assert len(sessions) == 2, "each Zoom folder is one session, not one per file"
        assert all(len(s.files) == 2 for s in sessions)


class TestRefusal:
    @pytest.mark.parametrize("target", ["/", "~", "/Applications", "/System", "/Library"])
    def test_roots_are_refused_by_name(self, target: str) -> None:
        path = Path.home() if target == "~" else Path(target)
        if not path.exists():
            pytest.skip(f"{target} not present on this platform")
        with pytest.raises(UnsuitableInputDirError) as exc:
            discover_files(path)
        assert "can't be analysed" in str(exc.value)
        assert "folder holding your recordings" in str(exc.value)

    def test_an_ordinary_folder_is_not_refused(self, tmp_path: Path) -> None:
        _touch(tmp_path / "interview.mp4")
        assert len(discover_files(tmp_path)) == 1

    def test_a_folder_inside_home_is_not_refused(self, tmp_path: Path) -> None:
        """Only the roots themselves. ~/Documents is a normal place for a study."""
        assert s01_ingest._refuse_reason(tmp_path) is None

    def test_refusal_happens_before_any_walking(self, tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
        """The point of the check is to cost nothing on a bad drop."""
        called = False

        def _boom(*a: object, **k: object) -> None:
            nonlocal called
            called = True

        monkeypatch.setattr(s01_ingest, "_scan_dir", _boom)
        with pytest.raises(UnsuitableInputDirError):
            discover_files(Path("/"))
        assert not called, "refused input was scanned anyway"


class TestHiddenEntries:
    """Hidden entries are tool state, not study material.

    The failure mode is not a wrong file in the report — a `.json` would be
    refused anyway — it is the refusal itself: one `.claude/settings.local.json`
    in the drop folder demoted every otherwise-clean run to "Partial
    completion" over a file Finder doesn't even show (29 Aug 2026). The skip
    also keeps discovery in agreement with `ProjectFolderWatcher`'s
    `.skipsHiddenFiles`.
    """

    def test_hidden_directories_are_not_walked(self, tmp_path: Path) -> None:
        _touch(tmp_path / "interview.mp4")
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "settings.local.json").write_text("{}")

        skipped: list[SkippedFile] = []
        found = discover_files(tmp_path, skipped)

        assert [f.path.name for f in found] == ["interview.mp4"]
        assert skipped == [], "a hidden file must never surface as a refusal"

    def test_hidden_files_are_skipped_even_with_accepted_extensions(
        self, tmp_path: Path,
    ) -> None:
        _touch(tmp_path / "interview.mp4")
        _touch(tmp_path / ".hidden.mp4")

        skipped: list[SkippedFile] = []
        found = discover_files(tmp_path, skipped)

        assert [f.path.name for f in found] == ["interview.mp4"]
        assert skipped == []

    def test_visible_unsupported_files_are_still_refused(
        self, tmp_path: Path,
    ) -> None:
        """The hidden skip must not widen: a file the researcher CAN see
        still gets its stated row."""
        _touch(tmp_path / "interview.mp4")
        (tmp_path / "notes.json").write_text("{}")

        skipped: list[SkippedFile] = []
        found = discover_files(tmp_path, skipped)

        assert [f.path.name for f in found] == ["interview.mp4"]
        assert [s.path.name for s in skipped] == ["notes.json"]
        assert skipped[0].reason is UnusableReason.UNSUPPORTED_FORMAT


class TestResilience:
    def test_one_unreadable_directory_does_not_end_the_walk(self, tmp_path: Path) -> None:
        """`~/.Trash` is the everyday case: it used to raise out of iterdir and
        destroy the whole scan."""
        _touch(tmp_path / "good.mp4")
        locked = tmp_path / "locked"
        _touch(locked / "hidden.mp4")
        os.chmod(locked, 0o000)
        try:
            skipped: list[SkippedFile] = []
            found = discover_files(tmp_path, skipped)
        finally:
            os.chmod(locked, 0o755)

        assert [f.path.name for f in found] == ["good.mp4"]
        assert any(
            s.reason is UnusableReason.UNREADABLE_FOLDER for s in skipped
        ), (
            "the unreadable folder was stepped over without being reported"
        )

    def test_a_cloud_placeholder_is_not_faulted_in(self, tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
        """Duration at scan time is a nicety; it must not cost a download.

        Discovery probes every media file, and probe_duration materialises
        first — so without this, scanning a folder of evicted recordings pulls
        every one of them down before the researcher has agreed to anything.
        """
        _touch(tmp_path / "evicted.mp4")
        monkeypatch.setattr(s01_ingest, "is_dataless", lambda p: True)
        monkeypatch.setattr(
            s01_ingest, "probe_duration",
            lambda p: pytest.fail("probed a cloud placeholder — this downloads it"),
        )

        found = discover_files(tmp_path)

        assert len(found) == 1
        assert found[0].duration_seconds is None, "unknown length, not a fabricated one"
