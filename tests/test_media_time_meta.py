"""Tier 2 § 5.1 — container time metadata capture (docs/design-timezones.md).

Capture only: nothing here changes `session_date`. The pure parser is tested on
the exact tag dictionaries measured from real files on 12 Sep 2026, so CI needs
no ffprobe; the corpus-backed test skips when the format-torture corpus is not
on disk (it is gitignored), exactly as the acceptance tests do.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bristlenose.models import MediaTimeMeta
from bristlenose.utils.audio import probe_time_meta, time_meta_from_ffprobe

CORPUS = Path(__file__).resolve().parents[1] / "trial-runs" / "folder-of-horrors"

# Exact dictionaries as ffprobe returned them (format_tags), measured.
IPHONE = {"format": {"tags": {
    "com.apple.quicktime.creationdate": "2020-06-21T13:34:08+0100",
    "creation_time": "2020-06-21T12:34:08.000000Z",
    "com.apple.quicktime.make": "Apple",
    "com.apple.quicktime.model": "iPhone 11 Pro",
    "com.apple.quicktime.software": "13.4.1",
}}}
REPLAYKIT = {"format": {"tags": {
    "creation_time": "2026-01-28T00:18:35.000000Z",
    "com.apple.quicktime.author": "ReplayKitRecording",
}}}
TRANSCODED = {"format": {"tags": {"encoder": "Lavf58.29.100"}}}
MATROSKA = {"format": {"tags": {"creation_time": "2026-07-19T14:20:07.000000Z", "ENCODER": "Lavf62.12.101"}}}
STREAM_ONLY = {"format": {"tags": {}}, "streams": [{"tags": {"creation_time": "2022-03-08T17:16:30.000000Z"}}]}


class TestPureParser:
    def test_iphone_carries_local_time_with_offset_and_utc(self) -> None:
        m = time_meta_from_ffprobe(IPHONE)
        assert m is not None
        assert m.creation_utc == datetime(2020, 6, 21, 12, 34, 8, tzinfo=timezone.utc)
        assert m.offset_minutes == 60
        assert m.creation_local is not None
        assert m.creation_local.utcoffset() == timedelta(hours=1)
        assert m.creation_local.hour == 13          # what the clock in the room said
        assert m.creation_local == m.creation_utc  # same instant
        assert m.make == "Apple" and m.model == "iPhone 11 Pro" and m.software == "13.4.1"

    def test_replaykit_marks_its_writer(self) -> None:
        m = time_meta_from_ffprobe(REPLAYKIT)
        assert m is not None
        assert m.creation_utc == datetime(2026, 1, 28, 0, 18, 35, tzinfo=timezone.utc)
        assert m.offset_minutes is None
        assert m.author == "ReplayKitRecording"

    def test_transcoded_file_has_no_time_but_names_its_encoder(self) -> None:
        m = time_meta_from_ffprobe(TRANSCODED)
        assert m is not None
        assert m.creation_utc is None and m.creation_local is None
        assert m.encoder == "Lavf58.29.100"

    def test_matroska_dateutc_arrives_under_the_same_key(self) -> None:
        m = time_meta_from_ffprobe(MATROSKA)
        assert m is not None and m.creation_utc == datetime(2026, 7, 19, 14, 20, 7, tzinfo=timezone.utc)
        assert m.encoder == "Lavf62.12.101"  # case-insensitive tag lookup

    def test_falls_back_to_stream_tags(self) -> None:
        m = time_meta_from_ffprobe(STREAM_ONLY)
        assert m is not None and m.creation_utc == datetime(2022, 3, 8, 17, 16, 30, tzinfo=timezone.utc)

    def test_nothing_at_all_is_none_not_an_empty_record(self) -> None:
        assert time_meta_from_ffprobe({"format": {}}) is None
        assert time_meta_from_ffprobe({}) is None

    def test_garbage_dates_do_not_raise(self) -> None:
        m = time_meta_from_ffprobe({"format": {"tags": {"creation_time": "yesterday-ish"}}})
        assert m is None or m.creation_utc is None


@pytest.mark.skipif(not (CORPUS / "IMG_2544.MOV").exists(), reason="format-torture corpus not on disk")
class TestAgainstTheCorpus:
    def test_iphone_file_end_to_end(self) -> None:
        m = probe_time_meta(CORPUS / "IMG_2544.MOV")
        assert m is not None
        assert m.offset_minutes == 60
        assert m.creation_utc is not None and m.creation_utc.hour == 12

    def test_transcoded_download_has_no_time(self) -> None:
        # a Lavf-written file in the corpus with no creation_time
        m = probe_time_meta(CORPUS / "browser-capture.webm")
        assert m is None or m.creation_utc is None


class TestIngestCaptures:
    def test_input_file_carries_the_meta(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Wiring: ingest records container meta on InputFile without touching
        created_at / session_date. Probes are mocked, as the duration probe is
        in the sibling tests."""
        import bristlenose.stages.s01_ingest as ingest
        (tmp_path / "a.mp4").write_bytes(b"\\x00" * 16)
        meta = MediaTimeMeta(creation_utc=datetime(2020, 6, 21, 12, 34, 8, tzinfo=timezone.utc),
                             offset_minutes=60, make="Apple")
        monkeypatch.setattr(ingest, "probe_duration", lambda p: 12.0)
        monkeypatch.setattr(ingest, "probe_time_meta", lambda p: meta)
        files = ingest.discover_files(tmp_path)
        assert len(files) == 1
        assert files[0].container_meta == meta
        assert files[0].duration_seconds == 12.0
