"""Files in a format we never offered are left alone; files in one we offer can fail (6 Nov 2026).

Talismanic read "Partial completion" because ~30 scripts, logs and data files each counted as a
refusal. The rule now: a format we say we read (audio, video, .srt, .vtt, .docx) fails with a
reason when we open it and it is unusable; any other extension was never attempted (by `run`; `analyze` does offer `.txt`), so it is
counted as "left alone" on the run summary and named only in the log.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from bristlenose.events import UnusableReason
from bristlenose.models import FileType, InputFile, InputSession
from bristlenose.stages.s01_ingest import SkippedFile, discover_files, split_left_alone

_T0 = datetime(2026, 11, 5, tzinfo=timezone.utc)


def test_split_left_alone_keeps_every_other_reason_stated() -> None:
    declined = [
        SkippedFile(Path("a.py"), UnusableReason.UNSUPPORTED_FORMAT, ".py"),
        SkippedFile(Path("b.txt"), UnusableReason.UNSUPPORTED_FORMAT, ".txt"),
        SkippedFile(Path("locked"), UnusableReason.UNREADABLE_FOLDER, "denied"),
    ]
    stated, left_alone = split_left_alone(declined)

    assert [s.path.name for s in stated] == ["locked"]
    assert left_alone == 2


def test_a_folder_of_strays_beside_one_recording_has_nothing_to_state(tmp_path: Path) -> None:
    (tmp_path / "p1.mp4").write_bytes(b"x")
    for name in ("build.py", "notes.txt", "labels.xlsx", "guide.md", "tape.opus"):
        (tmp_path / name).write_bytes(b"x")
    declined: list[SkippedFile] = []

    found = discover_files(tmp_path, declined)
    stated, left_alone = split_left_alone(declined)

    assert [f.path.name for f in found] == ["p1.mp4"]
    assert stated == []
    assert left_alone == 5


def test_the_left_alone_count_reaches_the_summary_and_not_the_failures() -> None:
    from bristlenose.config import BristlenoseSettings
    from bristlenose.events import PipelineSummary
    from bristlenose.pipeline import Pipeline

    pipeline = Pipeline(BristlenoseSettings(skip_transcription=True))
    pipeline._summary = PipelineSummary()
    f = InputFile(path=Path("p1.mp4"), file_type=FileType.VIDEO, created_at=_T0, size_bytes=1)
    session = InputSession(
        session_id="s1", session_number=1, participant_id="p1", participant_number=1,
        files=[f], session_date=_T0,
    )

    pipeline._record_ingest_outcome([session], [], left_alone=30)

    assert pipeline._summary.ingest is not None
    assert pipeline._summary.ingest.left_alone == 30
    assert pipeline._summary.ingest.failed == []
    assert pipeline._summary.ingest.attempted == 1  # strays were never attempted


def test_a_discussion_guide_docx_is_refused_as_no_transcript(tmp_path: Path) -> None:
    from docx import Document

    from bristlenose.config import BristlenoseSettings
    from bristlenose.pipeline import Pipeline

    doc = Document()
    for line in ("Project Ikea Discussion Guide", "Warm-up: last furniture purchase.", "Probe on checkout."):
        doc.add_paragraph(line)
    path = tmp_path / "Discussion guide.docx"
    doc.save(str(path))
    f = InputFile(path=path, file_type=FileType.DOCX, created_at=_T0,
                  size_bytes=path.stat().st_size)
    session = InputSession(
        session_id="s1", session_number=1, participant_id="p1", participant_number=1,
        files=[f], has_existing_transcript=True, session_date=_T0,
    )
    pipeline = Pipeline(BristlenoseSettings(skip_transcription=True))

    segments, outcome = asyncio.run(pipeline._gather_all_segments([session]))

    assert segments == {}
    (failure,) = outcome.failed
    assert failure.cause.reason == UnusableReason.NO_TRANSCRIPT
    assert failure.source_file == "Discussion guide.docx"


# -- Zoom per-person audio tracks (16 Nov 2026) ------------------------------
#
# Zoom's "Record separate participant audio files" writes each person's track
# into "Audio Record/" inside the meeting folder, beside the mixed recording.
# The mixed one is transcribed; the tracks are an export option, not a second
# recording, so they are left alone like the folder's .zoom and .m3u files and
# the run reads complete. Shapes observed on the owner's own meetings, 22 Oct
# 2026 (names replaced).


def _zoom_meeting(root: str, top: list[tuple[str, FileType]], tracks: list[str]) -> list[InputFile]:
    meeting = Path("/input") / root
    files = [
        InputFile(path=meeting / "Audio Record" / name, file_type=FileType.AUDIO,
                  created_at=_T0, size_bytes=1)
        for name in tracks
    ]
    files += [
        InputFile(path=meeting / name, file_type=kind, created_at=_T0, size_bytes=1)
        for name, kind in top
    ]
    return files


_ZOOM_TODAY = _zoom_meeting(
    "2026-10-22 09.51.39 Alex Example's Zoom Meeting",
    [("video1470811890.mp4", FileType.VIDEO), ("audio1470811890.m4a", FileType.AUDIO)],
    ["audioAlexExample11470811890.m4a", "audioSamSample21470811890.m4a"],
)
_ZOOM_2021 = _zoom_meeting(
    "2021-06-14 11.44.02 Alex Example's Zoom Meeting 95138721600",
    [("zoom_0.mp4", FileType.VIDEO), ("audio_only.m4a", FileType.AUDIO)],
    ["audio_only_16778242_Alex_Example.m4a", "audio_only_16779266_Sam_Sample.m4a"],
)


def _ingest_outcome(files: list[InputFile], tmp_path: Path, left_alone: int = 0):  # type: ignore[no-untyped-def]
    from bristlenose.config import BristlenoseSettings
    from bristlenose.events import PipelineSummary
    from bristlenose.pipeline import Pipeline
    from bristlenose.stages.s01_ingest import group_into_sessions
    from bristlenose.stages.s02_extract_audio import extract_audio_for_sessions

    sessions = group_into_sessions([f.model_copy() for f in files])
    asyncio.run(extract_audio_for_sessions(sessions, tmp_path))
    pipeline = Pipeline(BristlenoseSettings(skip_transcription=True))
    pipeline._summary = PipelineSummary()
    pipeline._record_ingest_outcome(sessions, [], left_alone=left_alone)
    assert pipeline._summary.ingest is not None
    return sessions, pipeline._summary.ingest


def test_zoom_participant_tracks_are_left_alone_not_failed(tmp_path: Path) -> None:
    for files, mixed in ((_ZOOM_TODAY, "audio1470811890.m4a"), (_ZOOM_2021, "audio_only.m4a")):
        sessions, ingest = _ingest_outcome(files, tmp_path, left_alone=6)

        (session,) = sessions
        assert session.audio_path is not None and session.audio_path.name == mixed
        assert ingest.failed == [], [f.source_file for f in ingest.failed]
        assert ingest.left_alone == 6 + 2  # the folder's other files, plus the two tracks
        assert ingest.attempted == ingest.succeeded == 2  # the mixed audio and the video


def test_zoom_tracks_with_no_meeting_recording_are_still_the_recording(tmp_path: Path) -> None:
    """The meeting's own recording deleted: a track is the only recording there is,
    so it is used, and the second is stated as before. Not quiet: half a
    conversation is something to know about."""
    only_tracks = [f for f in _ZOOM_TODAY if f.path.parent.name == "Audio Record"]

    sessions, ingest = _ingest_outcome(only_tracks, tmp_path)

    (session,) = sessions
    assert session.audio_path is not None
    assert session.audio_path.parent.name == "Audio Record"
    assert [f.cause.reason for f in ingest.failed] == [UnusableReason.DUPLICATE_RECORDING]
    assert ingest.left_alone == 0


def test_the_tracks_stay_in_the_files_a_session_was_analysed_from() -> None:
    """The session's fingerprint is taken after stage 1 and before stage 2, and
    every Zoom study analysed so far was fingerprinted with its tracks in it. If
    stage 1 set them aside, that fingerprint would change on upgrade and every
    such meeting would be transcribed and paid for again (review, 16 Nov 2026)."""
    from bristlenose.pipeline import _transcribed_files
    from bristlenose.stages.s01_ingest import group_into_sessions

    (session,) = group_into_sessions([f.model_copy() for f in _ZOOM_TODAY])

    assert {f.path.name for f in _transcribed_files(session)} == {f.path.name for f in _ZOOM_TODAY}


def _zoom_on_disk(root: Path, *, mixed: bytes, video: bool) -> list[InputFile]:
    meeting = root / "2026-10-22 09.51.39 Alex Example's Zoom Meeting"
    (meeting / "Audio Record").mkdir(parents=True)
    paths = {
        meeting / "Audio Record" / "audioAlexExample11470811890.m4a": (FileType.AUDIO, b"a" * 64),
        meeting / "Audio Record" / "audioSamSample21470811890.m4a": (FileType.AUDIO, b"b" * 64),
        meeting / "audio1470811890.m4a": (FileType.AUDIO, mixed),
    }
    if video:
        paths[meeting / "video1470811890.mp4"] = (FileType.VIDEO, b"v" * 64)
    files = []
    for path, (kind, data) in paths.items():
        path.write_bytes(data)
        files.append(InputFile(path=path, file_type=kind, created_at=_T0, size_bytes=len(data)))
    return files


def test_an_empty_meeting_recording_leaves_a_track_as_the_recording(tmp_path: Path) -> None:
    """An interrupted conversion can leave the mixed audio empty. Then a track is
    the only conversation there is: it is used, and the rest is stated."""
    files = _zoom_on_disk(tmp_path, mixed=b"", video=False)

    sessions, ingest = _ingest_outcome(files, tmp_path / "work")

    (session,) = sessions
    assert session.audio_path is not None and session.audio_path.parent.name == "Audio Record"
    assert sorted(f.cause.reason for f in ingest.failed) == sorted(
        [UnusableReason.EMPTY, UnusableReason.DUPLICATE_RECORDING])
    assert ingest.left_alone == 0


def test_an_empty_mixed_audio_beside_the_video_still_leaves_the_tracks_alone(
    tmp_path: Path, monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """The video carries the mixed conversation too, so the tracks stay unused."""
    import bristlenose.stages.s02_extract_audio as s02

    async def _extracted(session, video_path, output_path, semaphore):  # type: ignore[no-untyped-def]
        session.audio_path = output_path

    monkeypatch.setattr(s02, "_extract_one", _extracted)
    files = _zoom_on_disk(tmp_path, mixed=b"", video=True)

    sessions, ingest = _ingest_outcome(files, tmp_path / "work")

    (session,) = sessions
    assert session.audio_path is not None and "extracted" in session.audio_path.name
    assert [f.cause.reason for f in ingest.failed] == [UnusableReason.EMPTY]
    assert ingest.left_alone == 2


def test_a_meeting_whose_recordings_all_failed_is_refused_not_silent() -> None:
    """The mixed audio empty, the video with no sound, the tracks left alone: no
    file was ever heard, so the session is refused with its own reasons and never
    called "nothing was said" (review, 16 Nov 2026)."""
    from bristlenose.pipeline import _refused_recording_sids
    from bristlenose.stages.s01_ingest import ZOOM_PARTICIPANT_TRACK

    errors = {
        "audio1470811890.m4a": UnusableReason.EMPTY.value,
        "video1470811890.mp4": UnusableReason.NO_AUDIO.value,
        "audioAlexExample11470811890.m4a": ZOOM_PARTICIPANT_TRACK,
        "audioSamSample21470811890.m4a": ZOOM_PARTICIPANT_TRACK,
    }
    files = [f.model_copy(update={"error": errors[f.path.name]}) for f in _ZOOM_TODAY]
    session = InputSession(
        session_id="s1", session_number=1, participant_id="p1", participant_number=1,
        files=files, session_date=_T0,
    )

    assert _refused_recording_sids([session], {}, set()) == {"s1"}
