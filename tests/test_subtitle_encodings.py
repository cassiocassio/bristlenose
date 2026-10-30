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
    path.write_bytes(b"un caf\xe9 au lait \x81")
    assert read_text_any_encoding(path).startswith("un café")


@pytest.mark.parametrize("encoding", ["utf-16-le", "utf-16-be"])
def test_utf16_without_a_byte_order_mark_is_read(tmp_path: Path, encoding: str) -> None:
    """Without a BOM it is also valid UTF-8 (ASCII with NULs between), and every
    cue then failed its timing check."""
    path = tmp_path / "s.srt"
    path.write_bytes(_SRT.encode(encoding))
    (seg,) = parse_subtitle_file(_input(path, FileType.SUBTITLE_SRT))
    assert seg.text == _LINE


@pytest.mark.parametrize("text, encoding", [
    ("1\n00:00:01,000 --> 00:00:03,000\n我们今天讨论一下这个应用的使用体验。\n", "gbk"),
    ("1\n00:00:01,000 --> 00:00:03,000\n今日はアプリについてお話しします。\n", "shift_jis"),
    ("1\n00:00:01,000 --> 00:00:03,000\nСегодня мы поговорим о приложении.\n", "cp1251"),
])
def test_a_non_western_legacy_file_is_refused_not_misread(
    tmp_path: Path, text: str, encoding: str,
) -> None:
    """Read as 1252 it would be fluent-looking nonsense, analysed and paid for.
    Refused, as before, it is a stated "could not be read" row."""
    path = tmp_path / "s.srt"
    path.write_bytes(text.encode(encoding))
    with pytest.raises(UnicodeDecodeError):
        read_text_any_encoding(path)


# --- One stray invalid byte in an otherwise-UTF-8 file (ruling 5, #191) -------------

_FRENCH = "J’ai trouvé ça très difficile à utiliser. Il faut être patient, déjà."


def _utf8_with_a_stray_windows_quote(text: str) -> bytes:
    """A UTF-8 file with one 0x92 (cp1252's right single quote) pasted in."""
    return text.encode("utf-8") + b" \x92 fin."


def test_a_utf8_file_with_one_stray_byte_stays_utf8() -> None:
    from bristlenose.stages.s03_parse_subtitles import decode_text_any_encoding

    text = decode_text_any_encoding(_utf8_with_a_stray_windows_quote(_FRENCH), "t.txt")
    assert text.startswith(_FRENCH)  # every accent intact, not "trouvÃ©"
    assert text.count("�") == 1  # the one bad byte, marked, not dropped


def test_a_stray_byte_in_a_cjk_utf8_file_stays_utf8() -> None:
    from bristlenose.stages.s03_parse_subtitles import decode_text_any_encoding

    zh = "我觉得这个功能很难找到，而且不太直观。"
    text = decode_text_any_encoding(zh.encode("utf-8") + b"\x92", "t.txt")
    assert text.startswith(zh)  # the plausibility guard must not refuse UTF-8 text


def test_a_real_windows_file_with_one_accent_is_still_windows_text() -> None:
    from bristlenose.stages.s03_parse_subtitles import decode_text_any_encoding

    data = "Anna: Un café, s'il vous plaît.".encode("cp1252")
    assert decode_text_any_encoding(data, "t.txt") == "Anna: Un café, s'il vous plaît."


def test_a_windows_file_with_one_valid_looking_pair_is_not_taken_for_utf8() -> None:
    """One accidental C3 A9 pair beside many cp1252-only bytes stays Windows text."""
    from bristlenose.stages.s03_parse_subtitles import decode_text_any_encoding

    line = "Il a dit « déjà vu » à l’équipe, très étonné, après être resté là."
    data = line.encode("cp1252") + b" \xc3\xa9"  # one pair that happens to be valid UTF-8
    assert decode_text_any_encoding(data, "t.txt").startswith(line)


def test_a_file_with_many_bad_bytes_is_not_taken_for_utf8() -> None:
    from bristlenose.stages.s03_parse_subtitles import decode_text_any_encoding

    data = "é".encode() + "été à la plage ça va très bien".encode("cp1252")
    assert "été à la plage" in decode_text_any_encoding(data, "t.txt")
