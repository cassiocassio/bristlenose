"""Sticky session ids and speaker slots — ``bristlenose/session_registry.py``.

The end-to-end proof (an older recording arriving through the real
``Pipeline.run``) is ``TestStickySessions`` in
``tests/test_pipeline_platform_transcripts.py``; these are the unit contracts.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bristlenose.models import FileType, InputFile, InputSession, SpeakerRole, TranscriptSegment
from bristlenose.session_registry import SessionRegistry, registry_path
from bristlenose.stages.s01_ingest import group_into_sessions, session_key
from bristlenose.stages.s05b_identify_speakers import assign_speaker_codes

_T0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)


def _file(tmp_path: Path, name: str, day: int, kind: FileType = FileType.AUDIO) -> InputFile:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    return InputFile(
        path=path, file_type=kind, created_at=_T0 + timedelta(days=day), size_bytes=1,
    )


def _ingest(files: list[InputFile]) -> list[InputSession]:
    """What a fresh run's ingest returns: date order, ids from 1."""
    return group_into_sessions(files)


class TestSessionKey:
    def test_a_later_transcript_does_not_change_the_key(self, tmp_path: Path) -> None:
        video = _file(tmp_path, "interview-ann.wav", 0)
        vtt = _file(tmp_path, "interview-ann.vtt", 0, FileType.SUBTITLE_VTT)
        assert session_key([video]) == session_key([video, vtt])

    def test_a_stamped_download_is_keyed_by_stamp_and_title(self, tmp_path: Path) -> None:
        a = _file(tmp_path, "2026-09-03 1000 — Weekly sync.mp4", 0)
        b = _file(tmp_path, "2026-09-10 1000 — Weekly sync.mp4", 7)
        assert session_key([a]) != session_key([b])

    def test_a_zoom_folder_is_its_own_key(self, tmp_path: Path) -> None:
        folder = "2026-09-03 10.00.00 Ann Interview 81234567890"
        a = _file(tmp_path, f"{folder}/audio1.m4a", 0)
        b = _file(tmp_path, f"{folder}/video1.mp4", 0, FileType.VIDEO)
        assert session_key([a]) == session_key([b]) == f"zoom:{folder}"


class TestSessionIds:
    def test_a_fresh_project_numbers_by_date_as_before(self, tmp_path: Path) -> None:
        files = [_file(tmp_path, "c.wav", 2), _file(tmp_path, "a.wav", 0), _file(tmp_path, "b.wav", 1)]
        before = [(s.session_id, s.files[0].path.name) for s in _ingest(files)]
        reg = SessionRegistry.load(tmp_path / "out")
        after = [(s.session_id, s.files[0].path.name) for s in reg.apply(_ingest(files))]
        assert after == before == [("s1", "a.wav"), ("s2", "b.wav"), ("s3", "c.wav")]

    def test_session_ids_are_sticky_when_an_older_recording_arrives(self, tmp_path: Path) -> None:
        out = tmp_path / "out"
        b, c = _file(tmp_path, "b.wav", 1), _file(tmp_path, "c.wav", 2)
        reg = SessionRegistry.load(out)
        reg.apply(_ingest([b, c]))
        reg.save()

        a = _file(tmp_path, "a.wav", 0)  # recorded before both, arrives after
        sessions = SessionRegistry.load(out).apply(_ingest([a, b, c]))
        assert {s.files[0].path.name: s.session_id for s in sessions} == {
            "b.wav": "s1", "c.wav": "s2", "a.wav": "s3",
        }
        assert [s.session_number for s in sessions] == [1, 2, 3]
        assert sessions[2].participant_id == "p3"  # provisional follows the sid

    def test_a_removed_session_keeps_its_number_reserved(self, tmp_path: Path) -> None:
        out = tmp_path / "out"
        a, b = _file(tmp_path, "a.wav", 0), _file(tmp_path, "b.wav", 1)
        reg = SessionRegistry.load(out)
        reg.apply(_ingest([a, b]))
        reg.save()

        c = _file(tmp_path, "c.wav", 2)
        sessions = SessionRegistry.load(out).apply(_ingest([b, c]))  # a was deleted
        assert {s.files[0].path.name: s.session_id for s in sessions} == {"b.wav": "s2", "c.wav": "s3"}

        # …and comes back as itself.
        again = SessionRegistry.load(out)
        again.apply(_ingest([b, c]))
        again.save()
        back = SessionRegistry.load(out).apply(_ingest([a, b, c]))
        assert {s.files[0].path.name: s.session_id for s in back}["a.wav"] == "s1"

    def test_unreadable_file_is_refused_not_replaced(self, tmp_path: Path) -> None:
        out = tmp_path / "out"
        path = registry_path(out)
        path.parent.mkdir(parents=True)
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(ValueError, match="session numbering"):
            SessionRegistry.load(out)
        assert path.read_text(encoding="utf-8") == "{not json"

    def test_a_newer_version_is_refused(self, tmp_path: Path) -> None:
        out = tmp_path / "out"
        path = registry_path(out)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"version": 2, "sessions": {}}), encoding="utf-8")
        with pytest.raises(ValueError, match="version 2"):
            SessionRegistry.load(out)

    def test_save_round_trips(self, tmp_path: Path) -> None:
        out = tmp_path / "out"
        reg = SessionRegistry.load(out)
        reg.sessions = {"stem:a": "s1"}
        reg.record_speakers("s1", {"Speaker A": "p1", "Speaker B": "m1"})
        reg.save()
        again = SessionRegistry.load(out)
        assert again.sessions == {"stem:a": "s1"}
        assert again.speakers_for("s1") == {"Speaker A": "p1", "Speaker B": "m1"}
        assert not list(registry_path(out).parent.glob(".sessions.*.tmp"))


def _segs(*pairs: tuple[str, SpeakerRole]) -> list[TranscriptSegment]:
    return [
        TranscriptSegment(
            start_time=float(i), end_time=float(i) + 1, text="words",
            speaker_label=label, speaker_role=role,
        )
        for i, (label, role) in enumerate(pairs)
    ]


R, P, OBS = SpeakerRole.RESEARCHER, SpeakerRole.PARTICIPANT, SpeakerRole.OBSERVER


class TestSpeakerSlots:
    def test_no_known_map_is_identical_to_before(self) -> None:
        codes, nxt = assign_speaker_codes(4, _segs(("Mod", R), ("Ann", P), ("Bob", P), ("Obs", OBS)))
        assert codes == {"Mod": "m1", "Ann": "p4", "Bob": "p5", "Obs": "o1"}
        assert nxt == 6

    def test_known_codes_are_kept_while_the_role_matches(self) -> None:
        known = {"Mod": "m1", "Ann": "p2", "Bob": "p3"}
        codes, nxt = assign_speaker_codes(9, _segs(("Mod", R), ("Ann", P), ("Bob", P)), known=known)
        assert codes == known
        assert nxt == 9  # nothing new was numbered

    def test_a_role_change_gets_a_fresh_code(self) -> None:
        # The role pass now calls Bob a moderator: his old participant code
        # must not be re-used for a moderator, and Mod keeps m1.
        known = {"Mod": "m1", "Bob": "p3"}
        codes, nxt = assign_speaker_codes(9, _segs(("Mod", R), ("Bob", R)), known=known)
        assert codes == {"Mod": "m1", "Bob": "m2"}
        assert nxt == 9

    def test_a_new_moderator_skips_a_kept_code(self) -> None:
        codes, _ = assign_speaker_codes(1, _segs(("New", R), ("Old", R)), known={"Old": "m1"})
        assert codes == {"New": "m2", "Old": "m1"}

    def test_primary_participant_stays_first_in_appearance_order(self) -> None:
        codes, _ = assign_speaker_codes(9, _segs(("Ann", P), ("Bob", P)), known={"Bob": "p3"})
        assert list(codes) == ["Ann", "Bob"]
        assert codes == {"Ann": "p9", "Bob": "p3"}

    def test_next_participant_number_counts_every_code_ever_issued(self, tmp_path: Path) -> None:
        reg = SessionRegistry.load(tmp_path)
        assert reg.next_participant_number() == 1
        reg.record_speakers("s1", {"A": "p1", "M": "m1"})
        reg.record_speakers("s2", {"B": "p4"})
        assert reg.next_participant_number() == 5

    def test_a_number_is_not_reissued_after_its_speaker_changes_role(
        self, tmp_path: Path,
    ) -> None:
        # s2's participant is re-identified as an observer on a later run, so
        # p2 leaves the map. A study's next participant must still be p3: a
        # reissued p2 would carry the name typed for the old one.
        reg = SessionRegistry.load(tmp_path)
        reg.record_speakers("s1", {"A": "p1", "M": "m1"})
        reg.record_speakers("s2", {"C": "p2", "D": "m1"})
        reg.save()
        reg = SessionRegistry.load(tmp_path)
        reg.record_speakers("s2", {"C": "o1", "D": "m1"})
        reg.save()
        assert SessionRegistry.load(tmp_path).next_participant_number() == 3
