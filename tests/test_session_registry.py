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
        path.write_text(json.dumps({"version": 3, "sessions": {}}), encoding="utf-8")
        with pytest.raises(ValueError, match="version 3"):
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

    def test_a_moderator_not_heard_this_run_keeps_their_code_out_of_reach(self) -> None:
        """§J7: m1 was Martin; this run hears only a new voice. It must not be
        m1, or it wears Martin's name in this session."""
        codes, _ = assign_speaker_codes(1, _segs(("Kerri", R)), known={"Martin": "m1"})
        assert codes == {"Kerri": "m2"}

    def test_a_flipped_code_is_never_issued_again_in_the_session(self, tmp_path: Path) -> None:
        reg = SessionRegistry.load(tmp_path)
        reg.record_speakers("s1", {"A": "m1"})
        # Run 2: A is re-identified as a participant, so m1 leaves A.
        codes, _ = assign_speaker_codes(
            reg.next_participant_number(), _segs(("A", P)), known=reg.speakers_for("s1"),
        )
        reg.record_speakers("s1", codes)
        reg.save()
        # Run 3, read back from disk: a new moderator voice still does not get m1.
        again = SessionRegistry.load(tmp_path)
        codes, _ = assign_speaker_codes(
            again.next_participant_number(), _segs(("A", P), ("New", R)), known=again.speakers_for("s1"),
        )
        assert codes["New"] == "m2"

    def test_a_retired_code_is_per_session(self, tmp_path: Path) -> None:
        reg = SessionRegistry.load(tmp_path)
        reg.record_speakers("s1", {"A": "m1"})
        reg.record_speakers("s1", {"A": "p1"})
        codes, _ = assign_speaker_codes(2, _segs(("Mod", R)), known=reg.speakers_for("s2"))
        assert codes == {"Mod": "m1"}, "another session's retired m1 is not this one's"

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


class TestPrimaryParticipant:
    """A session that hears no participant still gets a participant code — one
    nobody else holds, or its stats placeholder overwrites a real person's."""

    def _session(self, sid: str, n: int) -> InputSession:
        return InputSession(
            session_id=sid, session_number=n, participant_id=f"p{n}",
            participant_number=n, files=[], session_date=_T0,
        )

    def test_a_session_with_no_transcript_does_not_take_a_real_participants_code(
        self, tmp_path: Path,
    ) -> None:
        from bristlenose.pipeline import _assign_session_codes

        reg = SessionRegistry.load(tmp_path)
        s1, s2 = self._session("s1", 1), self._session("s2", 2)
        # s1 failed to transcribe; s2 has one participant.
        _assign_session_codes([s1, s2], {"s2": _segs(("Ann", P), ("Mod", R))}, reg)
        assert s2.participant_id == "p1"
        assert s1.participant_id != "p1"

    def test_its_code_is_never_issued_to_anyone_else(self, tmp_path: Path) -> None:
        from bristlenose.pipeline import _assign_session_codes

        # Run 1: s1 alone, and it failed to transcribe.
        reg = SessionRegistry.load(tmp_path)
        s1 = self._session("s1", 1)
        _assign_session_codes([s1], {}, reg)
        reg.save()
        # Run 2: a new session's participant must not be handed s1's code.
        reg = SessionRegistry.load(tmp_path)
        s1, s2 = self._session("s1", 1), self._session("s2", 2)
        _assign_session_codes([s1, s2], {"s2": _segs(("Ann", P))}, reg)
        assert s2.participant_id != s1.participant_id

    def test_the_placeholder_is_stable_across_runs(self, tmp_path: Path) -> None:
        from bristlenose.pipeline import _assign_session_codes

        reg = SessionRegistry.load(tmp_path)
        s1 = self._session("s1", 1)
        _assign_session_codes([s1], {}, reg)
        first = s1.participant_id
        reg.save()
        again = self._session("s1", 1)
        _assign_session_codes([again], {}, SessionRegistry.load(tmp_path))
        assert again.participant_id == first

    def test_a_session_keeps_its_earlier_participant_when_this_run_hears_none(
        self, tmp_path: Path,
    ) -> None:
        from bristlenose.pipeline import _assign_session_codes

        reg = SessionRegistry.load(tmp_path)
        reg.record_speakers("s1", {"Ann": "p4", "Mod": "m1"})
        s1 = self._session("s1", 1)
        _assign_session_codes([s1], {}, reg)
        assert s1.participant_id == "p4"


class TestRegistryFileIsChecked:
    """A file that is wrong is refused by name, with the remedy — never a bare
    crash mid-run, and never silently read as something else."""

    def _write(self, tmp_path: Path, payload: object) -> Path:
        out = tmp_path / "out"
        path = registry_path(out)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return out

    @pytest.mark.parametrize("payload", [
        {"version": 1, "sessions": [], "speakers": {}},
        {"version": 1, "sessions": {}, "speakers": {"s1": ["p1"]}},
        {"version": 1, "sessions": {"k": "session-one"}, "speakers": {}},
        {"version": 1, "sessions": {"a": "s1", "b": "s1"}, "speakers": {}},
        {"version": 1, "sessions": {}, "speakers": {"s1": {"A": "p"}}},
        {"version": 1, "sessions": {}, "speakers": {"s1": {"A": "px"}}},
        {"version": 1, "sessions": {}, "speakers": {"s1": {"A": "p01"}}},
        {"version": 1, "sessions": {}, "speakers": {"s1": {"A": "p-3"}}},
        {"version": 1, "sessions": {}, "speakers": {"s1": {"A": "x1"}}},
        {"version": 1, "sessions": {}, "speakers": {"s1": {"A": "p2"}, "s2": {"B": "p2"}}},
        {"version": 1, "sessions": {}, "speakers": {}, "participants_issued": "abc"},
        {"version": 1, "sessions": {}, "speakers": {}, "participants_issued": True},
        {"version": 1, "sessions": {}, "speakers": {}, "participants_issued": 3.9},
        {"version": 1, "sessions": {}, "speakers": {}, "participants_issued": -1},
        ["not", "an", "object"],
    ])
    def test_a_malformed_file_is_refused_by_name(self, tmp_path: Path, payload: object) -> None:
        out = self._write(tmp_path, payload)
        with pytest.raises(ValueError, match="sessions.json"):
            SessionRegistry.load(out)

    def test_a_file_without_the_high_water_mark_still_loads(self, tmp_path: Path) -> None:
        # Written before participants_issued existed: the speaker map stands in.
        out = self._write(tmp_path, {
            "version": 1, "sessions": {"k": "s1"}, "speakers": {"s1": {"A": "p3", "": "p5"}},
        })
        assert SessionRegistry.load(out).next_participant_number() == 6

    def test_save_flushes_to_disk_before_it_replaces(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # A rename that lands before the data can leave an empty file after a
        # power cut, and the remedy for an unreadable file renumbers the study.
        import os

        calls: list[str] = []
        real_fsync, real_replace = os.fsync, os.replace
        monkeypatch.setattr(os, "fsync", lambda fd: (calls.append("fsync"), real_fsync(fd))[1])
        monkeypatch.setattr(
            os, "replace", lambda a, b: (calls.append("replace"), real_replace(a, b))[1],
        )
        reg = SessionRegistry.load(tmp_path / "out")
        reg.sessions = {"k": "s1"}
        reg.save()
        assert "fsync" in calls and calls.index("fsync") < calls.index("replace")


class TestRolePins:
    """§J7 R3: a researcher's recode, pinned by label with the turns it was set
    on, is honoured before codes are assigned — and dropped, not misapplied,
    once the label covers other turns."""

    def _session(self) -> InputSession:
        return InputSession(
            session_id="s1", session_number=1, participant_id="p1",
            participant_number=1, files=[], session_date=_T0,
        )

    def test_a_pin_round_trips_and_version_1_still_reads(self, tmp_path: Path) -> None:
        from bristlenose.session_registry import RolePin

        path = registry_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"version": 1, "sessions": {"k": "s1"},
                                    "speakers": {"s1": {"A": "p1"}}}), encoding="utf-8")
        reg = SessionRegistry.load(tmp_path)
        assert reg.pins == {}
        reg.pin("s1", "A", RolePin(role="researcher", starts=[0.0, 2.0], from_code="p1",
                                   person="id-a"))
        reg.save()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["version"] == 2
        again = SessionRegistry.load(tmp_path)
        assert again.pins["s1"]["A"].role == "researcher"
        assert again.pins["s1"]["A"].person == "id-a"

    def test_a_pin_with_no_known_role_is_refused(self, tmp_path: Path) -> None:
        path = registry_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"version": 2, "pins": {"s1": {"A": {"role": "boss",
                                    "starts": [0]}}}}), encoding="utf-8")
        with pytest.raises(ValueError, match="no role"):
            SessionRegistry.load(tmp_path)

    def test_the_swap_is_honoured_and_codes_follow(self, tmp_path: Path) -> None:
        """The pipeline called the moderator the participant; the pins put it right."""
        from bristlenose.pipeline import _assign_session_codes
        from bristlenose.session_registry import RolePin

        reg = SessionRegistry.load(tmp_path)
        s1 = self._session()
        segs = _segs(("Me", P), ("Wylie", R), ("Me", P))
        _assign_session_codes([s1], {"s1": segs}, reg)
        assert reg.speakers["s1"] == {"Me": "p1", "Wylie": "m1"}
        reg.pin("s1", "Me", RolePin(role="researcher", starts=[0.0, 2.0], from_code="p1"))
        reg.pin("s1", "Wylie", RolePin(role="participant", starts=[1.0], from_code="m1"))
        segs = _segs(("Me", P), ("Wylie", R), ("Me", P))
        dropped: list[str] = []
        _assign_session_codes([s1], {"s1": segs}, reg, dropped)
        assert dropped == []
        assert [s.speaker_role for s in segs] == [R, P, R]
        assert reg.speakers["s1"]["Me"].startswith("m")
        assert reg.speakers["s1"]["Wylie"] == "p2", "a new participant number, never p1 again"
        assert s1.participant_id == "p2"

    def test_a_pin_whose_turns_moved_is_dropped_not_applied(self, tmp_path: Path) -> None:
        from bristlenose.pipeline import _assign_session_codes
        from bristlenose.session_registry import RolePin

        reg = SessionRegistry.load(tmp_path)
        s1 = self._session()
        reg.pin("s1", "Me", RolePin(role="researcher", starts=[0.0, 2.0]))
        # A re-run of speaker identification gave "Me" different turns.
        segs = _segs(("Wylie", R), ("Me", P), ("Wylie", R))
        dropped: list[str] = []
        _assign_session_codes([s1], {"s1": segs}, reg, dropped)
        assert dropped == ["s1 Me"]
        assert [s.speaker_role for s in segs] == [R, P, R]
        assert "Me" not in reg.pins.get("s1", {})

    def _real_segs(self) -> list[TranscriptSegment]:
        """Whisper-shaped: fractional starts, and two "Me" turns stage 6 merges."""
        def seg(a: float, b: float, label: str, role: SpeakerRole) -> TranscriptSegment:
            return TranscriptSegment(start_time=a, end_time=b, text="words",
                                     speaker_label=label, speaker_role=role)
        return [seg(0.4, 1.2, "Me", P), seg(1.9, 3.0, "Me", P),
                seg(3.5, 5.0, "Wylie", R), seg(9.7, 11.0, "Me", P)]

    def test_a_pin_matches_real_fractional_merged_turns(self, tmp_path: Path) -> None:
        """The evidence serve records is the transcript file's paragraph starts —
        merged, whole seconds. The run must compare the same thing, or every pin
        on a real recording is dropped and a paid re-analysis changes nothing."""
        from bristlenose.pipeline import _assign_session_codes
        from bristlenose.session_registry import RolePin

        reg = SessionRegistry.load(tmp_path)
        s1 = self._session()
        reg.pin("s1", "Me", RolePin(role="researcher", starts=[0.0, 9.0], from_code="p1"))
        reg.pin("s1", "Wylie", RolePin(role="participant", starts=[3.0], from_code="m1"))
        segs = self._real_segs()
        dropped: list[str] = []
        _assign_session_codes([s1], {"s1": segs}, reg, dropped)
        assert dropped == []
        assert [s.speaker_role for s in segs] == [R, R, P, R]

    def test_the_run_and_serve_read_the_same_starts(self, tmp_path: Path) -> None:
        """The contract under the test above: stage 6's file, as the importer
        parses it, gives each code the starts the run derives from raw segments."""
        from bristlenose.pipeline import _paragraph_starts
        from bristlenose.server.importer import _SEGMENT_RE, _parse_timecode_to_seconds
        from bristlenose.stages.s06_merge_transcript import (
            merge_transcripts,
            write_raw_transcripts,
        )

        segs = self._real_segs()
        for s in segs:
            s.speaker_code = "p1" if s.speaker_label == "Me" else "m1"
        expected = _paragraph_starts(segs)
        transcripts = merge_transcripts([self._session()], {"s1": segs})
        (path,) = write_raw_transcripts(transcripts, tmp_path)
        heard: dict[str, list[float]] = {}
        for tc, code, _ in _SEGMENT_RE.findall(path.read_text(encoding="utf-8")):
            heard.setdefault(code, []).append(_parse_timecode_to_seconds(tc))
        assert heard == {"p1": expected["Me"], "m1": expected["Wylie"]}
