"""Subtitles and transcripts saved by Windows tools are read, not refused (R118).

Every reader opened these files as UTF-8, so a Windows-1252 `.srt` (Subtitle
Edit, older Premiere exports) or a UTF-16 one (Notepad's "Unicode") was a
"could not be read" row, and one such `.txt` crashed `analyze` with a
UnicodeDecodeError. A byte-order mark is believed first, then UTF-8, then
Windows-1252.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from bristlenose.models import FileType, InputFile
from bristlenose.pipeline import load_transcripts_from_dir
from bristlenose.stages.s03_parse_subtitles import parse_subtitle_file, read_text_any_encoding

_LINE = "Café, déjà vu — naïve “quotes”"
_SRT = f"1\n00:00:01,000 --> 00:00:03,000\nAnna: {_LINE}\n"
_VTT = f"WEBVTT\n\n00:00:01.000 --> 00:00:03.000\n<v Anna>{_LINE}\n"

_ENCODINGS = ["utf-8", "utf-8-sig", "cp1252", "utf-16"]


def _input(path: Path, kind: FileType) -> InputFile:
    return InputFile(
        path=path, file_type=kind,
        created_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
        size_bytes=path.stat().st_size,
    )


@pytest.mark.parametrize("encoding", _ENCODINGS)
def test_an_srt_is_read_in_any_common_encoding(tmp_path: Path, encoding: str) -> None:
    path = tmp_path / "s.srt"
    path.write_bytes(_SRT.encode(encoding))
    (seg,) = parse_subtitle_file(_input(path, FileType.SUBTITLE_SRT))
    assert seg.text == _LINE
    assert seg.speaker_label == "Anna"


@pytest.mark.parametrize("encoding", _ENCODINGS)
def test_a_vtt_is_read_in_any_common_encoding(tmp_path: Path, encoding: str) -> None:
    path = tmp_path / "s.vtt"
    path.write_bytes(_VTT.encode(encoding))
    (seg,) = parse_subtitle_file(_input(path, FileType.SUBTITLE_VTT))
    assert seg.text == _LINE
    assert seg.speaker_label == "Anna"


@pytest.mark.parametrize("encoding", _ENCODINGS)
def test_analyze_reads_a_transcript_in_any_common_encoding(
    tmp_path: Path, encoding: str,
) -> None:
    (tmp_path / "s1.txt").write_bytes(
        f"# Transcript: s1\n\n[00:01] [p1] {_LINE}\n".encode(encoding),
    )
    (transcript,) = load_transcripts_from_dir(tmp_path)
    assert transcript.segments[0].text == _LINE


def test_utf8_wins_over_windows_1252_when_both_would_decode(tmp_path: Path) -> None:
    """Every UTF-8 file also decodes as Windows-1252, as mojibake: order matters."""
    path = tmp_path / "t.txt"
    path.write_bytes("é".encode())
    assert read_text_any_encoding(path) == "é"


def test_bytes_windows_1252_leaves_undefined_still_read(tmp_path: Path) -> None:
    path = tmp_path / "t.txt"
    path.write_bytes(b"caf\xe9 \x81")
    assert read_text_any_encoding(path).startswith("café")
