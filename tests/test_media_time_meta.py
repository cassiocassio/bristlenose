"""Tier 2 § 5.1 — container time metadata capture (docs/design-timezones.md).

Capture only: nothing here changes `session_date`. The pure parser is tested on
the exact tag dictionaries measured from real files on 12 Sep 2026, so CI needs
no ffprobe. The wiring test patches `subprocess.run` with measured ffprobe JSON,
so the argv, the JSON path and the degradation contract DO execute in CI — the
first review of this file found none of them did.

Run the corpus-backed class by hand before an ffmpeg bump or a new writer
family: `.venv/bin/python -m pytest tests/test_media_time_meta.py -k Corpus`
with `trial-runs/folder-of-horrors` on disk (gitignored).
"""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bristlenose.models import MediaTimeMeta
from bristlenose.utils.audio import probe_media, time_meta_from_ffprobe
from bristlenose.utils.timecodes import parse_iso_lenient

CORPUS = Path(__file__).resolve().parents[1] / "trial-runs" / "folder-of-horrors"

# Exact dictionaries as ffprobe returned them, measured. IPHONE carries the
# stream block too, because that is where the video CODEC lives under the same
# `encoder` key Matroska uses for the muxer — the first cut merged the two.
IPHONE = {"format": {"tags": {
    "com.apple.quicktime.creationdate": "2020-06-21T13:34:08+0100",
    "creation_time": "2020-06-21T12:34:08.000000Z",
    "com.apple.quicktime.make": "Apple",
    "com.apple.quicktime.model": "iPhone 11 Pro",
    "com.apple.quicktime.software": "13.4.1",
    "com.apple.quicktime.location.ISO6709": "+51.5214-000.0933+017.844/",
}}, "streams": [{"tags": {"creation_time": "2020-06-21T12:34:08.000000Z", "encoder": "HEVC"}}]}
REPLAYKIT = {"format": {"tags": {
    "creation_time": "2026-01-28T00:18:35.000000Z",
    "com.apple.quicktime.author": "ReplayKitRecording",
}}}
TRANSCODED = {"format": {"tags": {"encoder": "Lavf58.29.100"}}}
MATROSKA = {"format": {"tags": {"creation_time": "2026-07-19T14:20:07.000000Z", "ENCODER": "Lavf62.12.101"}}}
STREAM_ONLY = {"format": {"tags": {}}, "streams": [{"tags": {"creation_time": "2022-03-08T17:16:30.000000Z"}}]}
MEASURED_FFPROBE_JSON = {"format": {"duration": "265.575271", "tags": REPLAYKIT["format"]["tags"]},
                         "streams": [{"tags": {"creation_time": "2026-01-28T00:18:35.000000Z"}}]}


class TestIsoLenient:
    """The container's two date spellings, plus every shape the first review
    found could crash or mis-normalise."""

    @pytest.mark.parametrize(("raw", "utc"), [
        ("2020-06-21T12:34:08.000000Z", datetime(2020, 6, 21, 12, 34, 8, tzinfo=timezone.utc)),
        ("2020-06-21T13:34:08+0100", datetime(2020, 6, 21, 12, 34, 8, tzinfo=timezone.utc)),
        ("2020-06-21T07:04:08-0530", datetime(2020, 6, 21, 12, 34, 8, tzinfo=timezone.utc)),
        ("2020-06-21T13:34:08+01:00", datetime(2020, 6, 21, 12, 34, 8, tzinfo=timezone.utc)),
        ("2020-06-21T18:19:08+05:45", datetime(2020, 6, 21, 12, 34, 8, tzinfo=timezone.utc)),
    ])
    def test_offsets_normalise_to_the_same_instant(self, raw: str, utc: datetime) -> None:
        dt = parse_iso_lenient(raw)
        assert dt is not None and dt.astimezone(timezone.utc) == utc

    @pytest.mark.parametrize("raw", ["+0100", "-0530", "-1234", "Z", "yesterday-ish", "2020:06:21 13:34:08", ""])
    def test_garbage_returns_none_and_never_raises(self, raw: str, caplog: pytest.LogCaptureFixture) -> None:
        """H-review #1: `text[-6]` on a five-character match raised IndexError
        and aborted the whole folder scan. Every shape here returns None."""
        with caplog.at_level(logging.WARNING):
            assert parse_iso_lenient(raw) is None
        if raw:
            assert "time_value_unparseable" in caplog.text, "an unparseable value must be logged, not absorbed"


class TestPureParser:
    def test_iphone_carries_local_time_with_offset_and_utc(self) -> None:
        m = time_meta_from_ffprobe(IPHONE)
        assert m is not None
        assert m.creation_utc == datetime(2020, 6, 21, 12, 34, 8, tzinfo=timezone.utc)
        assert m.offset_minutes == 60
        assert m.creation_local is not None and m.creation_local.utcoffset() == timedelta(hours=1)
        assert m.creation_local.hour == 13 and m.creation_local == m.creation_utc
        assert m.make == "Apple" and m.model == "iPhone 11 Pro" and m.software == "13.4.1"

    def test_encoder_is_the_muxer_not_the_stream_codec(self) -> None:
        """Review #4: the merged tag dict handed § 5.2's writer classifier `HEVC`."""
        assert time_meta_from_ffprobe(IPHONE).encoder is None
        assert time_meta_from_ffprobe(TRANSCODED).encoder == "Lavf58.29.100"
        assert time_meta_from_ffprobe(MATROSKA).encoder == "Lavf62.12.101"   # case-insensitive

    def test_gps_is_excluded_by_the_allowlist(self) -> None:
        """Review #25: the iPhone dict carries ISO6709 location. It must not be
        retained anywhere on the model — this is a privacy boundary, not a
        convenience, and it is the test that evidences it."""
        dumped = time_meta_from_ffprobe(IPHONE).model_dump_json()
        assert "ISO6709" not in dumped and "51.52" not in dumped

    def test_strings_are_bounded_at_the_dict_layer_not_by_a_validator(self) -> None:
        """Review #6 + compose-check 3.1: `Field(max_length=)` REJECTS, so a long
        tag would re-create the whole-scan abort. Truncate instead; keep the rest."""
        d = {"format": {"tags": {"com.apple.quicktime.author": "A" * 300, "creation_time": "2026-01-28T00:18:35Z"}}}
        m = time_meta_from_ffprobe(d)
        assert m is not None and len(m.author or "") == 256
        assert m.creation_utc is not None, "a long tag must not cost the file its other fields"

    def test_naive_creationdate_is_logged_and_not_stamped(self, caplog: pytest.LogCaptureFixture) -> None:
        """Compose-check 3.3: `creationdate` is the room's wall clock by
        definition; relabelling a naive one as UTC manufactures a wrong instant
        § 5.4 would trust. Leave both time fields None and say so."""
        d = {"format": {"tags": {"com.apple.quicktime.creationdate": "2020-06-21T13:34:08"}}}
        with caplog.at_level(logging.WARNING):
            m = time_meta_from_ffprobe(d)
        assert m is None or (m.creation_local is None and m.creation_utc is None)
        assert "zone unknown" in caplog.text

    def test_replaykit_marks_its_writer(self) -> None:
        m = time_meta_from_ffprobe(REPLAYKIT)
        assert m.creation_utc == datetime(2026, 1, 28, 0, 18, 35, tzinfo=timezone.utc)
        assert m.offset_minutes is None and m.author == "ReplayKitRecording"

    def test_matroska_dateutc_arrives_under_the_same_key(self) -> None:
        assert time_meta_from_ffprobe(MATROSKA).creation_utc == datetime(2026, 7, 19, 14, 20, 7, tzinfo=timezone.utc)

    def test_falls_back_to_stream_tags_for_time_only(self) -> None:
        assert time_meta_from_ffprobe(STREAM_ONLY).creation_utc == datetime(2022, 3, 8, 17, 16, 30, tzinfo=timezone.utc)

    def test_nothing_at_all_is_none_not_an_empty_record(self) -> None:
        assert time_meta_from_ffprobe({"format": {}}) is None
        assert time_meta_from_ffprobe({}) is None

    def test_a_present_but_unparseable_date_is_logged_and_keeps_the_other_fields(self, caplog: pytest.LogCaptureFixture) -> None:
        """Review #8: this used to collapse to None, identical to "no tags"."""
        d = {"format": {"tags": {"creation_time": "2020:06:21 13:34:08", "com.apple.quicktime.make": "Apple"}}}
        with caplog.at_level(logging.WARNING):
            m = time_meta_from_ffprobe(d)
        assert m is not None and m.creation_utc is None and m.make == "Apple"
        assert "time_value_unparseable" in caplog.text


class TestProbeMediaWiring:
    """One spawn, one argv, the JSON path, and every degradation — in CI."""

    @staticmethod
    def _fake_run(stdout: str, rc: int = 0, stderr: str = ""):
        calls: list[list[str]] = []
        def run(argv, **kw):  # type: ignore[no-untyped-def]
            calls.append(list(argv))
            return subprocess.CompletedProcess(argv, rc, stdout=stdout, stderr=stderr)
        return calls, run

    def test_one_spawn_returns_duration_and_meta(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import bristlenose.utils.audio as audio
        calls, run = self._fake_run(json.dumps(MEASURED_FFPROBE_JSON))
        monkeypatch.setattr(audio.subprocess, "run", run)
        f = tmp_path / "a.mov"
        f.write_bytes(b"\x00" * 16)
        duration, meta = probe_media(f)
        assert len(calls) == 1, "review #23: two spawns per file, measured at ~30 ms each"
        argv = calls[0]
        assert argv[-2:] == ["--", str(f)], "review #24: end-of-options before a user-controlled path"
        assert "-v" in argv and argv[argv.index("-v") + 1] == "error", "so a refusal's stderr says something"
        assert duration == pytest.approx(265.575271)
        assert meta is not None and meta.author == "ReplayKitRecording"

    def test_ffprobe_refusal_is_logged_with_its_reason(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog) -> None:
        import bristlenose.utils.audio as audio
        _, run = self._fake_run("{}", rc=1, stderr="Invalid data found when processing input")
        monkeypatch.setattr(audio.subprocess, "run", run)
        f = tmp_path / "a.mov"
        f.write_bytes(b"\x00")
        with caplog.at_level(logging.WARNING):
            assert probe_media(f) == (None, None)
        assert "Invalid data found" in caplog.text, "review #12: the rc≠0 branch was silent"

    def test_a_bad_tag_costs_the_meta_not_the_duration(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog) -> None:
        """Compose-check 3.8: folding the probes under one `except` would have
        thrown away a perfectly good duration whenever a date tag was bad."""
        import bristlenose.utils.audio as audio
        bad = {"format": {"duration": "12.5", "tags": {"creation_time": "+0100"}}}
        _, run = self._fake_run(json.dumps(bad))
        monkeypatch.setattr(audio.subprocess, "run", run)
        f = tmp_path / "a.mov"
        f.write_bytes(b"\x00")
        with caplog.at_level(logging.WARNING):
            duration, meta = probe_media(f)
        assert duration == 12.5
        assert meta is None or meta.creation_utc is None

    def test_tool_missing_is_logged_and_degrades(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog) -> None:
        import bristlenose.utils.audio as audio
        def run(argv, **kw):  # type: ignore[no-untyped-def]
            raise FileNotFoundError("ffprobe")
        monkeypatch.setattr(audio.subprocess, "run", run)
        f = tmp_path / "a.mov"
        f.write_bytes(b"\x00")
        with caplog.at_level(logging.WARNING):
            assert probe_media(f) == (None, None)
        assert "Could not probe" in caplog.text


class TestIngestCaptures:
    def test_input_file_carries_both_from_one_probe(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import bristlenose.stages.s01_ingest as ingest
        (tmp_path / "a.mp4").write_bytes(b"\x00" * 16)
        meta = MediaTimeMeta(creation_utc=datetime(2020, 6, 21, 12, 34, 8, tzinfo=timezone.utc), offset_minutes=60, make="Apple")
        monkeypatch.setattr(ingest, "probe_media", lambda p: (12.0, meta))
        files = ingest.discover_files(tmp_path)
        assert len(files) == 1
        assert files[0].duration_seconds == 12.0 and files[0].container_meta == meta


@pytest.mark.skipif(not (CORPUS / "IMG_2544.MOV").exists(), reason="format-torture corpus not on disk")
class TestAgainstTheCorpus:
    def test_iphone_file_end_to_end(self) -> None:
        duration, m = probe_media(CORPUS / "IMG_2544.MOV")
        assert duration and duration > 0
        assert m is not None and m.offset_minutes == 60 and m.creation_utc.hour == 12 and m.encoder is None
