"""Start times from real recorders' own metadata — design-timezones § 5.9.

The tag dictionaries in ``fixtures/media-time-specimens.json`` were read by
ffprobe from real files (GoPro HERO5–8, MAX and Fusion from gopro/gpmf-parser's
samples; a Zoom F8 and a Zoom H1 from public Broadcast WAV fixtures), GPS
location removed. These tests parse what the recorders actually wrote, through
the real ``time_meta_from_ffprobe`` and the resolver.

Device clocks have no zone, so every local reading pins the zone with the
``pin_local_zone`` fixture — here to California, where the GoPro samples were
shot, which is what makes their measured GPS offsets checkable.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bristlenose.models import FileType, InputFile, MediaTimeMeta
from bristlenose.utils.audio import time_meta_from_ffprobe
from bristlenose.utils.session_start import StartSource, resolve_session_start

UTC = timezone.utc
_SPECIMENS = json.loads(
    (Path(__file__).parent / "fixtures" / "media-time-specimens.json").read_text(encoding="utf-8")
)["specimens"]
# Long after any specimen: the file was copied here years later.
_COPIED = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)


def _file(name: str, specimen: str, file_type: FileType) -> InputFile:
    data = _SPECIMENS[specimen]
    return InputFile(
        path=Path("/input") / name,
        file_type=file_type,
        created_at=_COPIED,
        size_bytes=1000,
        duration_seconds=float(data["format"]["duration"]),
        container_meta=time_meta_from_ffprobe(data),
    )


class TestGoPro:
    @pytest.mark.parametrize(
        ("specimen", "offset_h", "expected_utc"),
        [
            # creation_time's digits are Pacific wall clock; GPS (true UTC)
            # sits 7 h later in April (PDT) and 8 h later in Jan/Nov (PST).
            ("gopro_hero5", -7, datetime(2017, 4, 17, 17, 31, 43, tzinfo=UTC)),
            ("gopro_hero6", -8, datetime(2018, 1, 24, 19, 27, 32, tzinfo=UTC)),
            ("gopro_hero8", -8, datetime(2019, 11, 18, 23, 41, 25, tzinfo=UTC)),
            ("gopro_max", -8, datetime(2019, 11, 18, 23, 45, 32, tzinfo=UTC)),
        ],
    )
    def test_the_false_z_is_read_as_the_local_wall_clock(
        self, pin_local_zone, specimen, offset_h, expected_utc
    ) -> None:
        pin_local_zone(timezone(timedelta(hours=offset_h)))
        start = resolve_session_start([_file("GX010042.MP4", specimen, FileType.VIDEO)])
        assert start.source is StartSource.CONTAINER
        assert start.instant == expected_utc

    def test_a_gopro_is_recognised_by_its_firmware(self) -> None:
        for specimen in ("gopro_hero5", "gopro_hero6", "gopro_hero8", "gopro_max", "gopro_fusion"):
            meta = time_meta_from_ffprobe(_SPECIMENS[specimen])
            assert meta is not None and meta.firmware, specimen

    def test_a_reset_clock_is_not_trusted(self, pin_local_zone) -> None:
        pin_local_zone(timezone(timedelta(hours=-8)))
        start = resolve_session_start([_file("GX010001.MP4", "gopro_hero7_reset_clock", FileType.VIDEO)])
        assert start.source is StartSource.BIRTHTIME

    def test_no_gps_location_reaches_the_meta(self) -> None:
        meta = time_meta_from_ffprobe(_SPECIMENS["gopro_hero5"])
        assert meta is not None
        assert "location" not in json.dumps(meta.model_dump(mode="json")).lower()


class TestZoomRecorders:
    def test_an_f8_start_comes_from_its_broadcast_wav_fields(self, pin_local_zone) -> None:
        pin_local_zone(timezone(timedelta(hours=-8)))
        meta = time_meta_from_ffprobe(_SPECIMENS["zoom_f8"])
        assert meta is not None
        assert meta.origination == datetime(2019, 2, 13, 22, 40, 18)
        assert meta.originator == "ZOOM F8"
        assert meta.creation_utc is None  # the bare "22:40:18" is not an instant
        start = resolve_session_start([_file("F8_Tr1.WAV", "zoom_f8", FileType.AUDIO)])
        assert start.source is StartSource.CONTAINER
        assert start.instant == datetime(2019, 2, 14, 6, 40, 18, tzinfo=UTC)

    def test_an_h1_with_a_reset_clock_is_not_trusted(self, pin_local_zone) -> None:
        pin_local_zone(timezone.utc)
        meta = time_meta_from_ffprobe(_SPECIMENS["zoom_h1_reset_clock"])
        assert meta is not None and meta.origination == datetime(2010, 1, 1, 1, 15, 44)
        start = resolve_session_start([_file("ZOOM0002.WAV", "zoom_h1_reset_clock", FileType.AUDIO)])
        assert start.source is StartSource.BIRTHTIME

    def test_a_bare_time_logs_no_parse_warning(self, caplog) -> None:
        time_meta_from_ffprobe(_SPECIMENS["zoom_f8"])
        assert "time_value_unparseable" not in caplog.text


class TestVoiceMemos:
    def test_an_original_is_named_by_its_start(self, london) -> None:
        f = InputFile(path=Path("/input/20260715 143022-3A2B9C1D.m4a"), file_type=FileType.AUDIO,
                      created_at=_COPIED, size_bytes=1, duration_seconds=600.0)
        start = resolve_session_start([f])
        assert start.source is StartSource.FILENAME_LOCAL
        assert start.instant == datetime(2026, 7, 15, 13, 30, 22, tzinfo=UTC)

    def test_its_container_time_is_taken_as_the_end(self) -> None:
        meta = MediaTimeMeta(creation_utc=datetime(2026, 7, 23, 12, 6, 16, tzinfo=UTC),
                             encoder="com.apple.VoiceMemos (iPhone Version 17.0)")
        f = InputFile(path=Path("/input/New Recording.m4a"), file_type=FileType.AUDIO,
                      created_at=datetime(2026, 7, 23, 12, 10, 43, tzinfo=UTC),
                      size_bytes=1, duration_seconds=365.0, container_meta=meta)
        assert resolve_session_start([f]).instant == datetime(2026, 7, 23, 12, 0, 11, tzinfo=UTC)
