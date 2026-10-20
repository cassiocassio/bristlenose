"""Filenames that look the same are the same session; one folder is scanned once (R123).

macOS writes some names decomposed (NFD: `e` + combining acute) and others
composed (NFC: `é`), depending on the tool that made the file. A recording
named one way and its transcript the other had different stems, so they became
two sessions and the recording was transcribed although its transcript sat
beside it. And a symlink to a folder inside the interview folder was scanned
as a second folder, so every session in it appeared twice.
"""

from __future__ import annotations

import os
import sys
import unicodedata
from pathlib import Path

import pytest

from bristlenose.stages.s01_ingest import discover_files, group_into_sessions, session_key

_VTT = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello\n"


def _write(path: Path, data: bytes = b"\0" * 64) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_an_nfd_recording_and_an_nfc_transcript_are_one_session(tmp_path: Path) -> None:
    nfd = unicodedata.normalize("NFD", "Entrevista José")
    nfc = unicodedata.normalize("NFC", "Entrevista José")
    assert nfd != nfc
    _write(tmp_path / f"{nfd}.mp4")
    _write(tmp_path / f"{nfc}.vtt", _VTT.encode())
    files = discover_files(tmp_path)
    assert len(files) == 2
    sessions = group_into_sessions(files)
    assert len(sessions) == 1, [[f.path.name for f in s.files] for s in sessions]


def test_the_session_key_does_not_depend_on_the_normal_form(tmp_path: Path) -> None:
    """The registry keys on it: one interview, one key, however it was spelled."""
    keys = set()
    for form in ("NFC", "NFD"):
        folder = tmp_path / form
        _write(folder / f"{unicodedata.normalize(form, 'Zoë')}.mp4")
        keys.add(session_key(discover_files(folder)))
    assert len(keys) == 1, keys


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_a_symlinked_folder_is_not_scanned_twice(tmp_path: Path) -> None:
    _write(tmp_path / "round-1" / "alice.mp4")
    _write(tmp_path / "round-1" / "bob.mp4")
    os.symlink(tmp_path / "round-1", tmp_path / "latest")
    files = discover_files(tmp_path)
    assert sorted(f.path.name for f in files) == ["alice.mp4", "bob.mp4"]


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_a_symlinked_recording_beside_its_original_is_not_a_second_session(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "alice.mp4")
    os.symlink(tmp_path / "alice.mp4", tmp_path / "alice-copy.mp4")
    assert [f.path.name for f in discover_files(tmp_path)] == ["alice.mp4"]


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_a_symlinked_interview_folder_is_still_scanned(tmp_path: Path) -> None:
    """Resolving once must not refuse a folder that is itself a link."""
    _write(tmp_path / "real" / "alice.mp4")
    os.symlink(tmp_path / "real", tmp_path / "link")
    assert [f.path.name for f in discover_files(tmp_path / "link")] == ["alice.mp4"]


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_a_link_back_to_the_interview_folder_adds_nothing(tmp_path: Path) -> None:
    _write(tmp_path / "alice.mp4")
    os.symlink(tmp_path, tmp_path / "zz-everything")
    assert [f.path.name for f in discover_files(tmp_path)] == ["alice.mp4"]


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_a_symlink_loop_is_stepped_over(tmp_path: Path) -> None:
    """Python 3.12's resolve() raises RuntimeError for a loop; one bad link must
    not end the scan."""
    _write(tmp_path / "alice.mp4")
    os.symlink(tmp_path / "loop-b", tmp_path / "loop-a")
    os.symlink(tmp_path / "loop-a", tmp_path / "loop-b")
    assert [f.path.name for f in discover_files(tmp_path)] == ["alice.mp4"]


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_a_link_that_sorts_first_still_leaves_the_target_its_own_path(tmp_path: Path) -> None:
    """`aaa/link` is reached before `zzz/real` in a sorted walk; the session
    must still carry the real path, not the link's."""
    _write(tmp_path / "zzz" / "real" / "alice.mp4")
    (tmp_path / "aaa").mkdir()
    os.symlink(tmp_path / "zzz" / "real", tmp_path / "aaa" / "link")
    (f,) = discover_files(tmp_path)
    assert f.path == tmp_path / "zzz" / "real" / "alice.mp4"


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_a_folder_too_deep_to_walk_is_still_reached_through_a_shallower_link(
    tmp_path: Path,
) -> None:
    """A folder past the depth limit was marked scanned without being walked, so
    a link to it nearer the top was skipped as already seen."""
    from bristlenose.stages.s01_ingest import _MAX_SCAN_DEPTH

    deep = tmp_path.joinpath(*[f"d{i}" for i in range(_MAX_SCAN_DEPTH)])
    _write(deep / "alice.mp4")
    os.symlink(deep, tmp_path / "shortcut")
    assert [f.path.name for f in discover_files(tmp_path)] == ["alice.mp4"]
