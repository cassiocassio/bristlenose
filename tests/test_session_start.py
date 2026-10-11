"""The session start resolver — design-timezones § 5.4, as built 11 Oct 2026.

Local-wall-clock rungs are read in this machine's zone, so every test that
involves one pins the zone to Europe/London (BST in summer, GMT in winter).
That pin is what lets a summer case and a winter case prove the DST handling
rather than happen to pass in whatever zone CI runs in.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bristlenose.models import FileType, InputFile, InputSession, MediaTimeMeta
from bristlenose.pipeline import _may_order_by_start
from bristlenose.session_registry import SessionRegistry, registry_path
from bristlenose.stages.s01_ingest import group_into_sessions
from bristlenose.utils.session_start import (
    CONFLICT_TOLERANCE,
    StartSource,
    candidates_for,
    resolve_session_start,
)

UTC = timezone.utc
_BIRTH = datetime(2026, 7, 21, 15, 0, 0, tzinfo=UTC)  # "saved at the end"
_LOG = "bristlenose.utils.session_start"


def _file(
    name: str,
    *,
    parent: str = "/input",
    file_type: FileType = FileType.VIDEO,
    created_at: datetime = _BIRTH,
    duration: float | None = 3600.0,
    meta: MediaTimeMeta | None = None,
) -> InputFile:
    return InputFile(
        path=Path(parent) / name,
        file_type=file_type,
        created_at=created_at,
        size_bytes=1000,
        duration_seconds=duration,
        container_meta=meta,
    )


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def _replaykit(end: datetime) -> MediaTimeMeta:
    return MediaTimeMeta(creation_utc=end, author="ReplayKitRecording")


# ---------------------------------------------------------------------------
# Each rung on its own
# ---------------------------------------------------------------------------


class TestRungs:
    def test_birthtime_is_the_floor(self) -> None:
        start = resolve_session_start([_file("interview.mp4")])
        assert start.source is StartSource.BIRTHTIME
        assert start.instant == _BIRTH
        assert start.conflict is False

    def test_cloud_import_stamp_in_summer_is_bst(self, london) -> None:
        start = resolve_session_start([_file("2026-07-21 1000 — P07 Interview.mp4")])
        assert start.source is StartSource.CLOUD_IMPORT
        assert start.instant == _utc(2026, 7, 21, 9, 0)  # 10:00 BST

    def test_cloud_import_stamp_in_winter_is_gmt(self, london) -> None:
        start = resolve_session_start([_file("2026-12-08 1000 — P07 Interview.mp4")])
        assert start.instant == _utc(2026, 12, 8, 10, 0)  # 10:00 GMT

    def test_an_untitled_meeting_is_the_bare_stamp(self, london) -> None:
        # CloudDownloadVerification.filename writes the stamp alone when the
        # meeting has no title.
        start = resolve_session_start([_file("2026-07-21 1000.mp4")])
        assert start.source is StartSource.CLOUD_IMPORT

    def test_a_second_part_keeps_its_stamp(self, london) -> None:
        start = resolve_session_start([_file("2026-07-21 1000 (2).mp4")])
        assert start.source is StartSource.CLOUD_IMPORT

    def test_container_utc_taken_as_written_for_an_unknown_writer(self) -> None:
        meta = MediaTimeMeta(creation_utc=_utc(2026, 7, 21, 13, 0))
        start = resolve_session_start([_file("interview.mov", meta=meta)])
        assert start.source is StartSource.CONTAINER
        # No duration subtracted: nothing has measured which end this writer stamps.
        assert start.instant == _utc(2026, 7, 21, 13, 0)

    def test_replaykit_stamps_the_end_and_is_moved_back(self) -> None:
        start = resolve_session_start(
            [_file("clip.mov", meta=_replaykit(_utc(2026, 7, 21, 14, 0)), duration=1800.0)]
        )
        assert start.source is StartSource.CONTAINER
        assert start.instant == _utc(2026, 7, 21, 13, 30)

    def test_replaykit_without_a_duration_is_not_trusted(self) -> None:
        start = resolve_session_start(
            [_file("clip.mov", meta=_replaykit(_utc(2026, 7, 21, 14, 0)), duration=None)]
        )
        assert start.source is StartSource.BIRTHTIME

    def test_a_person_named_in_author_is_not_a_writer_match(self) -> None:
        meta = MediaTimeMeta(creation_utc=_utc(2026, 7, 21, 14, 0), author="Martin Storey")
        start = resolve_session_start([_file("clip.mov", meta=meta)])
        assert start.instant == _utc(2026, 7, 21, 14, 0)

    def test_container_local_offset_is_the_same_instant(self) -> None:
        local = datetime(2020, 6, 21, 13, 34, 8, tzinfo=timezone(timedelta(hours=1)))
        meta = MediaTimeMeta(creation_utc=local.astimezone(UTC), creation_local=local, offset_minutes=60)
        start = resolve_session_start(
            [_file("IMG_2544.MOV", meta=meta, created_at=_utc(2026, 4, 6, 9, 0))]
        )
        assert start.instant == _utc(2020, 6, 21, 12, 34, 8)

    def test_apples_capture_date_beats_the_save_time(self) -> None:
        # Measured on a Mac-made QuickTime file: capture date 09:55:37+0200,
        # creation_time 07:56:11Z, which equals the file's creation (its save).
        local = datetime(2026, 7, 21, 9, 55, 37, tzinfo=timezone(timedelta(hours=2)))
        meta = MediaTimeMeta(creation_utc=_utc(2026, 7, 21, 7, 56, 11), creation_local=local)
        start = resolve_session_start(
            [_file("small2.mov", meta=meta, created_at=_utc(2026, 7, 21, 7, 56, 11), duration=10.0)]
        )
        assert start.source is StartSource.CONTAINER
        assert start.instant == _utc(2026, 7, 21, 7, 55, 37)

    def test_teams_utc_filename_is_zoned(self) -> None:
        f = _file("Weekly sync-20260719_142007UTC-Meeting Recording.mp4")
        start = resolve_session_start([f])
        assert start.source is StartSource.FILENAME_ZONED
        assert start.instant == _utc(2026, 7, 19, 14, 20, 7)

    def test_zoom_local_folder_is_the_meeting_start(self, london) -> None:
        f = _file("audio1234.m4a", parent="/input/2026-01-15 14.30.22 Kickoff 98765432101",
                  file_type=FileType.AUDIO)
        start = resolve_session_start([f])
        assert start.source is StartSource.FILENAME_LOCAL
        assert start.instant == _utc(2026, 1, 15, 14, 30, 22)  # GMT in January

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Screen Recording 2026-01-27 at 23.37.37.mov", _utc(2026, 1, 27, 23, 37, 37)),
            ("Bildschirmaufnahme 2026-01-27 um 23.37.37.mov", _utc(2026, 1, 27, 23, 37, 37)),
            ("Screen Recording 2026-01-27 at 11.37.37 PM.mov", _utc(2026, 1, 27, 23, 37, 37)),
            ("Screen Recording 2026-01-27 at 12.05.00 AM.mov", _utc(2026, 1, 27, 0, 5, 0)),
            ("화면 기록 2026-01-27 오후 11.37.37.mov", _utc(2026, 1, 27, 23, 37, 37)),
            ("화면 기록 2026-01-27 오전 9.05.00.mov", _utc(2026, 1, 27, 9, 5, 0)),
            ("画面収録 2026-01-27 午後11.37.37.mov", _utc(2026, 1, 27, 23, 37, 37)),
            ("画面収録 2026-01-27 23.37.37.mov", _utc(2026, 1, 27, 23, 37, 37)),
            ("Screen Recording 2026-07-27 at 09.00.00.mov", _utc(2026, 7, 27, 8, 0, 0)),
        ],
    )
    def test_screen_recording_filename(self, london, name: str, expected: datetime) -> None:
        start = resolve_session_start([_file(name)])
        assert start.source is StartSource.FILENAME_LOCAL
        assert start.instant == expected


class TestMoreConventions:
    @pytest.mark.parametrize(
        ("name", "file_type", "source", "expected"),
        [
            # Zoom cloud: named by the start in GMT.
            ("GMT20260715-143022_Recording_1920x1080.mp4", FileType.VIDEO,
             StartSource.FILENAME_ZONED, _utc(2026, 7, 15, 14, 30, 22)),
            ("GMT20260715-143022_Recording.m4a", FileType.AUDIO,
             StartSource.FILENAME_ZONED, _utc(2026, 7, 15, 14, 30, 22)),
            ("GMT20260715-143022_Recording.transcript.vtt", FileType.SUBTITLE_VTT,
             StartSource.FILENAME_ZONED, _utc(2026, 7, 15, 14, 30, 22)),
            # Pixel: UTC, milliseconds appended.
            ("PXL_20260715_143022123.mp4", FileType.VIDEO,
             StartSource.FILENAME_ZONED, _utc(2026, 7, 15, 14, 30, 22)),
            ("PXL_20260715_143022123.TS.mp4", FileType.VIDEO,
             StartSource.FILENAME_ZONED, _utc(2026, 7, 15, 14, 30, 22)),
            # Android, local (BST in July): an hour earlier in UTC.
            ("VID_20260715_143022.mp4", FileType.VIDEO,
             StartSource.FILENAME_LOCAL, _utc(2026, 7, 15, 13, 30, 22)),
            ("Screen_Recording_20260715-143022_Zoom.mp4", FileType.VIDEO,
             StartSource.FILENAME_LOCAL, _utc(2026, 7, 15, 13, 30, 22)),
            ("20260715_143022.mp4", FileType.VIDEO,
             StartSource.FILENAME_LOCAL, _utc(2026, 7, 15, 13, 30, 22)),
            # OBS default, and Windows Game Bar.
            ("2026-07-15 14-30-22.mkv", FileType.VIDEO,
             StartSource.FILENAME_LOCAL, _utc(2026, 7, 15, 13, 30, 22)),
            ("Zoom Meeting 2026-07-15 14-30-22.mp4", FileType.VIDEO,
             StartSource.FILENAME_LOCAL, _utc(2026, 7, 15, 13, 30, 22)),
            # Google Meet recording: a GMT offset is zoned; a named zone is local.
            ("Sync - 2026_07_15 14_30 GMT-5 - Recording.mp4", FileType.VIDEO,
             StartSource.FILENAME_ZONED, _utc(2026, 7, 15, 19, 30)),
            ("Sync - 2026_07_15 14_30 BST - Recording.mp4", FileType.VIDEO,
             StartSource.FILENAME_LOCAL, _utc(2026, 7, 15, 13, 30)),
        ],
    )
    def test_reads_the_start(self, london, name, file_type, source, expected) -> None:
        start = resolve_session_start([_file(name, file_type=file_type)])
        assert (start.source, start.instant) == (source, expected)

    def test_meet_in_another_named_zone_is_not_read(self, london) -> None:
        # CEST on a London Mac: somebody else's clock.
        f = _file("Sync - 2026_07_15 14_30 CEST - Recording.mp4")
        assert resolve_session_start([f]).source is StartSource.BIRTHTIME

    def test_meet_without_a_zone_is_not_read(self, london) -> None:
        f = _file("Sync - 2026_07_15 14_30 - Recording.mp4")
        assert resolve_session_start([f]).source is StartSource.BIRTHTIME

    def test_meet_notes_are_not_a_start(self, london) -> None:
        # Gemini's notes are stamped when Gemini finished, not at the start.
        f = _file("Sync - 2026_07_15 14_47 - Notes by Gemini.docx", file_type=FileType.DOCX)
        assert resolve_session_start([f]).source is StartSource.BIRTHTIME

    def test_meet_recording_and_notes_together_take_the_recording(self, london) -> None:
        rec = _file("Sync - 2026_07_15 14_30 BST - Recording.mp4")
        notes = _file("Sync - 2026_07_15 14_47 - Notes by Gemini.docx", file_type=FileType.DOCX)
        assert resolve_session_start([rec, notes]).instant == _utc(2026, 7, 15, 13, 30)

    def test_whatsapp_is_a_message_time_not_a_start(self, london) -> None:
        f = _file("WhatsApp Video 2026-07-15 at 14.30.22.mp4")
        assert resolve_session_start([f]).source is StartSource.BIRTHTIME


# ---------------------------------------------------------------------------
# What must NOT be read as a start
# ---------------------------------------------------------------------------


class TestNotAStart:
    @pytest.mark.parametrize(
        "name",
        [
            "Q3 planning 2026-08-15 14.00.mp4",  # a title with a date, no seconds
            "Screen Recording 2026-01-27 at 23.37.37 trimmed.mov",  # renamed: a title now
            "2026-07-21 notes.mp4",  # date-only, no time
            "2026-05-01 0001 - P1.mp4",  # hand-typed: a hyphen, and a sequence number
            "2026-07-21 0930 – P3 interview.mp4",  # hand-typed with an en dash
            "Weekly sync-20260719_142007-Meeting Recording.mp4",  # Teams, no zone: whose clock?
            "Topic_987654321_Jan_15_2026.mp4",  # Zoom cloud: date only
            "Q3 review 20260715.mp4",  # a date, no time
            "Interview 2026-07-15 14-30.mp4",  # OBS shape without seconds
            "GMT20260715_Recording.mp4",  # Zoom prefix without the time
        ],
    )
    def test_falls_back_to_birthtime(self, name: str) -> None:
        start = resolve_session_start([_file(name)])
        assert start.source is StartSource.BIRTHTIME

    def test_impossible_dates_are_ignored(self) -> None:
        start = resolve_session_start([_file("2026-02-30 1000 — Interview.mp4")])
        assert start.source is StartSource.BIRTHTIME

    def test_meridiem_hour_out_of_range_is_ignored(self) -> None:
        start = resolve_session_start([_file("Screen Recording 2026-01-27 at 13.00.00 PM.mov")])
        assert start.source is StartSource.BIRTHTIME

    @pytest.mark.parametrize(
        ("name", "parent"),
        [
            ("0001-01-01 0000 — x.mp4", "/input"),
            ("9999-12-31 2359 — x.mp4", "/input"),
            ("a.m4a", "/input/9999-12-31 23.59.59 Kickoff 98765432101"),
            ("Screen Recording 0001-01-01 at 00.00.00.mov", "/input"),
        ],
    )
    def test_extreme_years_cannot_stop_the_scan(self, name: str, parent: str) -> None:
        start = resolve_session_start([_file(name, parent=parent)])
        assert start.source is StartSource.BIRTHTIME


class TestContainerSanity:
    def test_a_1970_epoch_is_refused(self) -> None:
        meta = MediaTimeMeta(creation_utc=_utc(1970, 1, 1, 0, 0))
        assert resolve_session_start([_file("x.mp4", meta=meta)]).source is StartSource.BIRTHTIME

    def test_a_clock_set_in_the_future_is_refused(self) -> None:
        # Stamped after the file existed: a wrong clock, not a recording.
        meta = MediaTimeMeta(creation_utc=_utc(2031, 1, 1, 0, 0))
        assert resolve_session_start([_file("x.mp4", meta=meta)]).source is StartSource.BIRTHTIME

    def test_year_one_does_not_overflow_the_subtraction(self) -> None:
        meta = _replaykit(datetime(1, 1, 1, 0, 0, 30, tzinfo=UTC))
        assert resolve_session_start([_file("x.mov", meta=meta)]).source is StartSource.BIRTHTIME

    def test_a_naive_container_time_is_not_trusted(self) -> None:
        meta = MediaTimeMeta(creation_utc=datetime(2026, 7, 21, 13, 0))
        assert resolve_session_start([_file("x.mp4", meta=meta)]).source is StartSource.BIRTHTIME


# ---------------------------------------------------------------------------
# Precedence, multi-file sessions, disagreement
# ---------------------------------------------------------------------------


class TestPrecedence:
    def test_cloud_stamp_beats_container_and_birthtime(self, london) -> None:
        meta = MediaTimeMeta(creation_utc=_utc(2026, 7, 21, 9, 2))
        f = _file("2026-07-21 1000 — P07 Interview.mp4", meta=meta)
        start = resolve_session_start([f])
        assert start.source is StartSource.CLOUD_IMPORT
        assert start.conflict is False  # two minutes apart is within tolerance

    def test_a_trimmed_screen_recording_keeps_its_names_start(self, london) -> None:
        # Trimmed by 20 minutes: duration shrank, the container still says the
        # original end, so end − duration lands 20 minutes late. The name is exact.
        f = _file(
            "Screen Recording 2026-01-27 at 23.37.37.mov",
            meta=_replaykit(_utc(2026, 1, 28, 0, 17, 40)),
            duration=1200.0,
            created_at=_utc(2026, 1, 28, 0, 17, 41),
        )
        start = resolve_session_start([f])
        assert start.source is StartSource.FILENAME_LOCAL
        assert start.instant == _utc(2026, 1, 27, 23, 37, 37)

    def test_an_untrimmed_screen_recording_agrees_with_itself(self, london) -> None:
        f = _file(
            "Screen Recording 2026-01-27 at 23.37.37.mov",
            meta=_replaykit(_utc(2026, 1, 27, 23, 38, 56)),
            duration=79.0,
            created_at=_utc(2026, 1, 27, 23, 38, 57),
        )
        start = resolve_session_start([f])
        assert start.instant == _utc(2026, 1, 27, 23, 37, 37)
        assert start.conflict is False  # +0 s after subtraction

    def test_zoom_folder_beats_an_end_stamping_container(self, london, caplog) -> None:
        # Zoom's local transcode (expected, unmeasured) stamps the save moment.
        f = _file(
            "video1234.mp4",
            parent="/input/2026-01-15 14.30.22 Kickoff 98765432101",
            meta=MediaTimeMeta(creation_utc=_utc(2026, 1, 15, 15, 32)),
            created_at=_utc(2026, 1, 15, 15, 33),
        )
        with caplog.at_level(logging.WARNING, logger=_LOG):
            start = resolve_session_start([f])
        assert start.source is StartSource.FILENAME_LOCAL
        assert start.instant == _utc(2026, 1, 15, 14, 30, 22)
        assert start.conflict is True
        assert "video1234.mp4" in caplog.text

    def test_candidates_are_listed_best_first(self, london) -> None:
        meta = MediaTimeMeta(creation_utc=_utc(2026, 7, 21, 9, 1))
        f = _file("2026-07-21 1000 — P07 Interview.mp4", meta=meta)
        assert [c.source for c in candidates_for(f)] == [
            StartSource.CLOUD_IMPORT,
            StartSource.CONTAINER,
            StartSource.BIRTHTIME,
        ]

    def test_a_stamped_transcript_dates_a_session_its_video_cannot(self, london) -> None:
        video = _file("interview.mp4")  # hand-renamed: birthtime only
        notes = _file("2026-07-21 1000 — Interview.docx", file_type=FileType.DOCX)
        start = resolve_session_start([video, notes])
        assert start.source is StartSource.CLOUD_IMPORT

    def test_within_a_rank_the_earliest_wins(self) -> None:
        a = _file("a.mov", meta=MediaTimeMeta(creation_utc=_utc(2026, 7, 21, 13, 0)))
        b = _file("b.mov", meta=MediaTimeMeta(creation_utc=_utc(2026, 7, 21, 13, 1)))
        assert resolve_session_start([b, a]).instant == _utc(2026, 7, 21, 13, 0)


class TestConflict:
    def test_disagreement_beyond_tolerance_is_flagged_and_logged(self, london, caplog) -> None:
        # The measured shape: name says 13:16 local, container says 17:16Z.
        meta = MediaTimeMeta(creation_utc=_utc(2022, 3, 8, 17, 16, 30))
        f = _file("Screen Recording 2022-03-08 at 13.16.00.mov", meta=meta,
                  created_at=_utc(2022, 3, 8, 17, 17))
        with caplog.at_level(logging.WARNING, logger=_LOG):
            start = resolve_session_start([f])
        assert start.source is StartSource.FILENAME_LOCAL  # the higher rung stands
        assert start.conflict is True
        assert "session_start_conflict" in caplog.text
        assert "Screen Recording 2022-03-08 at 13.16.00.mov" in caplog.text

    def test_a_cloud_stamp_against_an_end_stamp_is_a_conflict(self, london) -> None:
        meta = MediaTimeMeta(creation_utc=_utc(2026, 7, 21, 10, 0))  # the save, an hour in
        f = _file("2026-07-21 1000 — Interview.mp4", meta=meta)
        start = resolve_session_start([f])
        assert start.source is StartSource.CLOUD_IMPORT
        assert start.conflict is True

    def test_birthtime_never_raises_a_conflict(self, london) -> None:
        # A download's birthtime is the download moment — days away, and meaningless.
        f = _file("2026-07-21 1000 — Interview.mp4", created_at=_utc(2026, 7, 25, 8, 0))
        assert resolve_session_start([f]).conflict is False

    def test_just_inside_tolerance_is_not_a_conflict(self) -> None:
        t = _utc(2026, 7, 21, 13, 0)
        a = _file("a.mov", meta=MediaTimeMeta(creation_utc=t))
        b = _file("b.mov", meta=MediaTimeMeta(creation_utc=t + CONFLICT_TOLERANCE))
        assert resolve_session_start([a, b]).conflict is False

    def test_empty_session_is_a_programming_error(self) -> None:
        with pytest.raises(ValueError):
            resolve_session_start([])


# ---------------------------------------------------------------------------
# Through ingest: what it stores, and how it numbers
# ---------------------------------------------------------------------------


def _two_downloads() -> list[InputFile]:
    # Downloaded in the opposite order to when the meetings happened.
    return [
        _file("2026-07-21 1000 — Earlier meeting.mp4", created_at=_utc(2026, 7, 25, 9, 0)),
        _file("2026-07-22 1000 — Later meeting.mp4", created_at=_utc(2026, 7, 25, 8, 0)),
    ]


class TestThroughIngest:
    def test_session_date_is_the_resolved_start(self, london) -> None:
        f = _file("2026-07-21 1000 — P07 Interview.mp4", created_at=_utc(2026, 7, 25, 8, 0))
        (session,) = group_into_sessions([f])
        assert session.session_date == _utc(2026, 7, 21, 9, 0)
        assert session.session_start_source == "cloud_import"

    def test_legacy_numbering_follows_creation_time(self, london) -> None:
        sessions = group_into_sessions(_two_downloads())
        assert [s.files[0].path.name for s in sessions] == [
            "2026-07-22 1000 — Later meeting.mp4",
            "2026-07-21 1000 — Earlier meeting.mp4",
        ]
        assert sessions[0].session_date == _utc(2026, 7, 22, 9, 0)

    def test_a_new_project_is_numbered_by_start(self, london) -> None:
        sessions = group_into_sessions(_two_downloads(), order_by_start=True)
        assert [s.files[0].path.name for s in sessions] == [
            "2026-07-21 1000 — Earlier meeting.mp4",
            "2026-07-22 1000 — Later meeting.mp4",
        ]


class TestMayOrderByStart:
    def test_a_new_project_may(self, tmp_path: Path) -> None:
        assert _may_order_by_start(tmp_path / "out") is True

    def test_a_project_with_a_registry_may(self, tmp_path: Path) -> None:
        (tmp_path / "transcripts-raw").mkdir()
        registry_path(tmp_path).parent.mkdir(parents=True)
        registry_path(tmp_path).write_text("{}")
        assert _may_order_by_start(tmp_path) is True

    def test_a_pre_registry_project_may_not(self, tmp_path: Path) -> None:
        (tmp_path / "transcripts-raw").mkdir()
        assert _may_order_by_start(tmp_path) is False


# ---------------------------------------------------------------------------
# The registry keeps the best start a run has seen
# ---------------------------------------------------------------------------


def _session(sid: str, at: datetime, source: str) -> InputSession:
    return InputSession(
        session_id=sid, session_number=int(sid[1:]), participant_id="p1",
        participant_number=1, files=[], session_date=at, session_start_source=source,
    )


class TestSettleStarts:
    def test_a_worse_signal_does_not_replace_a_better_one(self, tmp_path: Path) -> None:
        # Run 1 read the container; then iCloud evicted the file.
        reg = SessionRegistry.load(tmp_path)
        reg.settle_starts([_session("s1", _utc(2026, 7, 21, 9, 0), "container")])
        reg.save()
        later = _session("s1", _utc(2026, 7, 25, 8, 0), "birthtime")
        SessionRegistry.load(tmp_path).settle_starts([later])
        assert later.session_date == _utc(2026, 7, 21, 9, 0)
        assert later.session_start_source == "container"

    def test_a_better_signal_replaces_a_worse_one(self, tmp_path: Path) -> None:
        reg = SessionRegistry.load(tmp_path)
        reg.settle_starts([_session("s1", _utc(2026, 7, 25, 8, 0), "birthtime")])
        better = _session("s1", _utc(2026, 7, 21, 9, 0), "container")
        reg.settle_starts([better])
        assert better.session_date == _utc(2026, 7, 21, 9, 0)
        assert reg.starts["s1"]["source"] == "container"

    def test_the_same_signal_in_another_zone_keeps_the_first_reading(self, tmp_path: Path) -> None:
        reg = SessionRegistry.load(tmp_path)
        reg.settle_starts([_session("s1", _utc(2026, 7, 21, 9, 0), "cloud_import")])
        new_york = _session("s1", _utc(2026, 7, 21, 14, 0), "cloud_import")
        reg.settle_starts([new_york])
        assert new_york.session_date == _utc(2026, 7, 21, 9, 0)

    def test_an_unreadable_entry_is_skipped_not_fatal(self, tmp_path: Path) -> None:
        path = registry_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({
            "version": 2, "sessions": {"k": "s1"}, "speakers": {},
            "starts": {"s1": {"utc": "not a date", "source": "container"}, "bogus": 3},
        }))
        reg = SessionRegistry.load(tmp_path)
        assert reg.sessions == {"k": "s1"} and reg.starts == {}

    def test_a_source_from_a_newer_release_is_replaced(self, tmp_path: Path) -> None:
        reg = SessionRegistry.load(tmp_path)
        reg.starts["s1"] = {"utc": "2026-07-21T09:00:00+00:00", "source": "calendar_api"}
        s = _session("s1", _utc(2026, 7, 25, 8, 0), "birthtime")
        reg.settle_starts([s])
        assert s.session_date == _utc(2026, 7, 25, 8, 0)

    def test_starts_survive_a_save(self, tmp_path: Path) -> None:
        reg = SessionRegistry.load(tmp_path)
        reg.settle_starts([_session("s1", _utc(2026, 7, 21, 9, 0), "container")])
        reg.save()
        assert SessionRegistry.load(tmp_path).starts["s1"]["source"] == "container"


def test_the_london_fixture_really_pins_the_zone(london) -> None:
    from bristlenose.utils.timecodes import from_local

    assert from_local(datetime(2026, 7, 1, 12, 0)).utcoffset() == timedelta(hours=1)
    assert from_local(datetime(2026, 12, 1, 12, 0)).utcoffset() == timedelta(0)
