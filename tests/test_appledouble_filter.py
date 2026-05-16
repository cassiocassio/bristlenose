"""Regression tests for AppleDouble (`._*`) file filtering.

macOS Finder creates `._<name>` sidecar files when copying to filesystems that
can't store xattrs natively (ExFAT, FAT32, SMB). Scanners must skip these or
they'll try to decode binary metadata blobs as user content.

Hit 16 May 2026 when a project was copied to an ExFAT SD card — pipeline
crashed with UnicodeDecodeError while loading `._s1.txt` as a transcript and
emitted ffprobe warnings for `._foo.mp4`.
"""

from __future__ import annotations

from pathlib import Path

from bristlenose.pipeline import load_transcripts_from_dir
from bristlenose.stages.s01_ingest import discover_files
from bristlenose.utils.fs import is_os_metadata


def test_is_os_metadata_matches_appledouble() -> None:
    assert is_os_metadata(Path("._foo.mp4"))
    assert is_os_metadata(Path("/some/dir/._s1.txt"))
    assert is_os_metadata(Path(".DS_Store"))


def test_is_os_metadata_skips_normal_files() -> None:
    assert not is_os_metadata(Path("s1.txt"))
    assert not is_os_metadata(Path("interview.mp4"))
    assert not is_os_metadata(Path(".bristlenose"))  # dotdir, not AppleDouble
    assert not is_os_metadata(Path(".env"))


def test_load_transcripts_from_dir_skips_appledouble(tmp_path: Path) -> None:
    """`._s1.txt` is a binary metadata blob — must not be parsed as a transcript."""
    # Real transcript
    (tmp_path / "s1.txt").write_text(
        "# Transcript: s1\n"
        "# Source: foo.mp4\n"
        "# Date: 2026-01-01T00:00:00\n"
        "# Duration: 00:00:10\n"
        "\n"
        "[00:00:00] [p1] Hello.\n",
        encoding="utf-8",
    )
    # AppleDouble sidecar — binary, would crash utf-8 decode
    (tmp_path / "._s1.txt").write_bytes(b"\x00\x05\x16\x07\xb0\xff\xfe")

    transcripts = load_transcripts_from_dir(tmp_path)

    assert len(transcripts) == 1
    assert transcripts[0].session_id == "s1"


def test_discover_files_skips_appledouble(tmp_path: Path) -> None:
    """`._foo.mp4` is a binary metadata blob — ffprobe would fail on it."""
    # Real video file (empty body — discover_files only needs the extension
    # to classify; probe_duration returning None is fine for this test)
    (tmp_path / "foo.mp4").write_bytes(b"")
    # AppleDouble sidecar
    (tmp_path / "._foo.mp4").write_bytes(b"\x00\x05\x16\x07")
    # Finder cruft
    (tmp_path / ".DS_Store").write_bytes(b"\x00")

    files = discover_files(tmp_path)

    names = [f.path.name for f in files]
    assert "foo.mp4" in names
    assert "._foo.mp4" not in names
    assert ".DS_Store" not in names


def test_discover_files_skips_appledouble_in_subdir(tmp_path: Path) -> None:
    """Recursion into subdirectories must also skip `._*` files."""
    sub = tmp_path / "interviews"
    sub.mkdir()
    (sub / "bar.mp4").write_bytes(b"")
    (sub / "._bar.mp4").write_bytes(b"\x00\x05\x16\x07")

    files = discover_files(tmp_path)

    names = [f.path.name for f in files]
    assert "bar.mp4" in names
    assert "._bar.mp4" not in names
