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
    # Each file its own bytes: a session is found by its recording's content
    # first (registry version 3), and real recordings never share bytes.
    data = name.encode("utf-8")
    path.write_bytes(data)
    return InputFile(
        path=path, file_type=kind, created_at=_T0 + timedelta(days=day), size_bytes=len(data),
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
        path.write_text(json.dumps({"version": 4, "sessions": {}}), encoding="utf-8")
        with pytest.raises(ValueError, match="version 4"):
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
        assert data["version"] == 3
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


class TestContentKeys:
    """Registry version 3: a session is its recording's bytes first."""

    def test_a_recording_missing_for_a_run_keeps_its_key(self, tmp_path: Path) -> None:
        """The recording is gone for one run while its transcript stays: the
        session's key stays the recording's, so a different recording saved
        under the old name later is still a new session (Fable review,
        16 Oct 2026)."""
        out = tmp_path / "out"
        mp4 = _file(tmp_path, "ann.mp4", 0, FileType.VIDEO)
        vtt = _file(tmp_path, "ann.vtt", 0, FileType.SUBTITLE_VTT)

        def run(files: list[InputFile]) -> str:
            reg = SessionRegistry.load(out)
            sid = reg.apply(_ingest(files), tmp_path)[0].session_id
            reg.save()
            return sid

        first = run([mp4, vtt])
        mp4.path.unlink()
        assert run([vtt]) == first
        mp4.path.write_bytes(b"a different interview saved under the old name")
        other = InputFile(path=mp4.path, file_type=FileType.VIDEO, created_at=mp4.created_at,
                          size_bytes=mp4.path.stat().st_size)
        assert run([other, vtt]) != first, "a different recording inherited the session"

    def test_a_symlinked_recording_has_a_place(self, tmp_path: Path) -> None:
        """A recording linked into the interview folder from elsewhere is
        placed where it sits in the folder, so its key always has a place
        (Fable review, 16 Oct 2026)."""
        from bristlenose.session_registry import _place

        study, elsewhere = tmp_path / "study", tmp_path / "elsewhere"
        study.mkdir()
        elsewhere.mkdir()
        (elsewhere / "ann.mp4").write_bytes(b"x")
        (study / "ann.mp4").symlink_to(elsewhere / "ann.mp4")
        assert _place(study / "ann.mp4", study) == "ann.mp4"
        assert _place(elsewhere / "ann.mp4", study) is None
        # However the folder was spelled on the command line.
        dotted = study / ".." / "study"
        assert _place(dotted / "ann.mp4", dotted) == "ann.mp4"
        # A folder spelled through a link and back (`lk/..`): the place is
        # the file's place in that folder, not one inside the link's target.
        parent = tmp_path / "parent"
        (parent / "real").mkdir(parents=True)
        (parent / "study2").mkdir()
        (parent / "study2" / "lk").symlink_to(parent / "real")
        spelled = parent / "study2" / "lk" / ".."  # the OS reads this as `parent`
        (parent / "q.mp4").symlink_to(elsewhere / "ann.mp4")
        assert _place(spelled / "q.mp4", spelled) == "q.mp4"

    def test_a_recording_with_no_known_place_returns_to_its_session(
        self, tmp_path: Path,
    ) -> None:
        """With no place recorded for its key (no input folder known), a
        recording that is absent for one run and then returns unchanged keeps
        its session (Fable review, 16 Oct 2026)."""
        out = tmp_path / "out"
        mp4 = _file(tmp_path, "ann.mp4", 0, FileType.VIDEO)
        vtt = _file(tmp_path, "ann.vtt", 0, FileType.SUBTITLE_VTT)
        held = mp4.path.read_bytes()

        def run(files: list[InputFile]) -> str:
            reg = SessionRegistry.load(out)
            sid = reg.apply(_ingest(files), None)[0].session_id
            reg.save()
            return sid

        first = run([mp4, vtt])
        mp4.path.unlink()
        assert run([vtt]) == first
        mp4.path.write_bytes(held)
        assert run([mp4, vtt]) == first, "an unchanged recording lost its session"

    def test_a_recording_arriving_for_a_transcript_only_session_joins_it(
        self, tmp_path: Path,
    ) -> None:
        """Analysed from Teams transcripts, then the recordings are dropped in
        for playback: each joins its session rather than becoming a new one
        and orphaning the curation (Fable review, 15 Oct 2026)."""
        out = tmp_path / "out"
        vtts = [_file(tmp_path, f"{n}.vtt", d, FileType.SUBTITLE_VTT)
                for n, d in (("ann", 0), ("bob", 1))]
        reg = SessionRegistry.load(out)
        first = {s.files[0].path.stem: s.session_id for s in reg.apply(_ingest(vtts), tmp_path)}
        reg.save()
        mp4s = [_file(tmp_path, f"{n}.mp4", d, FileType.VIDEO) for n, d in (("ann", 0), ("bob", 1))]
        reg = SessionRegistry.load(out)
        after = {s.files[0].path.stem: s.session_id
                 for s in reg.apply(_ingest(vtts + mp4s), tmp_path)}
        reg.save()
        assert after == first
        again = {s.files[0].path.stem: s.session_id
                 for s in SessionRegistry.load(out).apply(_ingest(vtts + mp4s), tmp_path)}
        assert again == first, "the sessions moved on the next run"

    def test_a_recording_renamed_while_in_the_cloud_keeps_its_session(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Renamed in Finder while evicted: no bytes, no hint at the new place,
        no name. It is fetched and identified by its bytes rather than given a
        new session and transcribed again (Fable review, 15 Oct 2026)."""
        import bristlenose.utils.fingerprint as fingerprint_mod
        import bristlenose.utils.fs as fs_mod

        out = tmp_path / "out"
        a, b = _file(tmp_path, "rec-1433.wav", 0), _file(tmp_path, "b.wav", 1)
        reg = SessionRegistry.load(out)
        first = {s.files[0].path.name: s.session_id for s in reg.apply(_ingest([a, b]), tmp_path)}
        reg.save()

        renamed = tmp_path / "p1 sarah.wav"
        a.path.rename(renamed)
        evicted = {renamed}
        fetched: list[Path] = []

        def dataless(path: Path) -> bool:
            return path in evicted

        def fetch(path: Path, *args: object, **kwargs: object) -> bool:
            fetched.append(path)
            evicted.discard(path)
            return True

        monkeypatch.setattr(fingerprint_mod, "is_dataless", dataless)
        monkeypatch.setattr(fs_mod, "is_dataless", dataless)
        monkeypatch.setattr(fs_mod, "ensure_materialised", fetch)
        a2 = InputFile(path=renamed, file_type=FileType.AUDIO, created_at=a.created_at,
                       size_bytes=a.size_bytes)
        # Serve's re-render resolves ids too, and must never download.
        SessionRegistry.load(out).apply(_ingest([a2, b]), tmp_path)
        assert fetched == []
        # Nor for a recording with a transcript beside it: Whisper won't read it.
        with_transcript = _ingest([a2, b])
        for session in with_transcript:
            session.has_existing_transcript = True
        SessionRegistry.load(out).apply(with_transcript, tmp_path, fetch=True)
        assert fetched == []

        again = {s.files[0].path.name: s.session_id
                 for s in SessionRegistry.load(out).apply(_ingest([a2, b]), tmp_path, fetch=True)}
        assert again == {"p1 sarah.wav": first["rec-1433.wav"], "b.wav": first["b.wav"]}
        assert fetched == [renamed]

    def test_a_fetched_duplicate_does_not_take_a_live_sessions_key(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A recording found by its place while evicted, a deleted one (so
        something is missing), and a Finder duplicate of the first, evicted
        too: the duplicate is fetched, its bytes are the live session's, so it
        is folded into that session (R49, 20 Oct 2026), which keeps its key
        (Fable review of the fetch, 15 Oct 2026)."""
        import bristlenose.utils.fingerprint as fingerprint_mod
        import bristlenose.utils.fs as fs_mod

        out = tmp_path / "out"
        a, b = _file(tmp_path, "a.wav", 0), _file(tmp_path, "b.wav", 1)
        reg = SessionRegistry.load(out)
        first = {s.files[0].path.name: s.session_id for s in reg.apply(_ingest([a, b]), tmp_path)}
        reg.save()

        b.path.unlink()
        dup = tmp_path / "a copy.wav"
        dup.write_bytes(a.path.read_bytes())
        evicted = {a.path, dup}
        monkeypatch.setattr(fingerprint_mod, "is_dataless", lambda p: p in evicted)
        monkeypatch.setattr(fs_mod, "is_dataless", lambda p: p in evicted)
        monkeypatch.setattr(fs_mod, "ensure_materialised",
                            lambda p, *x, **k: evicted.discard(p) or True)
        d = InputFile(path=dup, file_type=FileType.AUDIO, created_at=_T0 + timedelta(days=2),
                      size_bytes=dup.stat().st_size)
        reg = SessionRegistry.load(out)
        fetched_run = reg.apply(_ingest([a, d]), tmp_path, fetch=True)
        reg.save()
        assert [s.session_id for s in fetched_run] == [first["a.wav"]], "the copy became a session"
        assert [f.error is None for f in fetched_run[0].files] == [True, False]

        evicted.clear()
        reg = SessionRegistry.load(out)
        settled = {s.files[0].path.name: s.session_id for s in reg.apply(_ingest([a, d]), tmp_path)}
        reg.save()
        assert settled == {"a.wav": first["a.wav"]}, "the live recording lost its session"
        # And it keeps it through a rename: one session, found by its bytes
        # (Fable review, 15 Oct 2026). Which of the two copies is then used is
        # name order, as the copy's name is not remembered.
        renamed = tmp_path / "p1 sarah.wav"
        a.path.rename(renamed)
        a2 = InputFile(path=renamed, file_type=FileType.AUDIO, created_at=a.created_at,
                       size_bytes=a.size_bytes)
        after = SessionRegistry.load(out).apply(_ingest([a2, d]), tmp_path)
        assert [s.session_id for s in after] == [first["a.wav"]], "the renamed original was orphaned"

    def test_a_restored_original_returns_to_its_session_after_a_re_export(
        self, tmp_path: Path,
    ) -> None:
        """Re-exported under its name (a new session, §5), then the original
        restored: it is its old session again, not a third one, and toggling
        never mints more (Fable review, 15 Oct 2026)."""
        out = tmp_path / "out"
        path = tmp_path / "a.wav"

        def run(data: bytes) -> str:
            path.write_bytes(data)
            f = InputFile(path=path, file_type=FileType.AUDIO, created_at=_T0,
                          size_bytes=len(data))
            reg = SessionRegistry.load(out)
            sid = reg.apply(_ingest([f]), tmp_path)[0].session_id
            reg.save()
            return sid

        original = run(b"original recording")
        trimmed = run(b"trimmed recording")
        assert trimmed != original
        assert run(b"original recording") == original
        assert run(b"trimmed recording") == trimmed

    def test_a_fetch_that_times_out_stops_the_run_rather_than_guess(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A renamed placeholder still downloading after the full wait is
        neither the missing session nor a new one: the run stops and says so
        (Fable review, 16 Oct 2026)."""
        import bristlenose.utils.fingerprint as fingerprint_mod
        import bristlenose.utils.fs as fs_mod
        from bristlenose.utils.fs import CloudFetchTimeoutError

        out = tmp_path / "out"
        a, b = _file(tmp_path, "rec-1433.wav", 0), _file(tmp_path, "b.wav", 1)
        reg = SessionRegistry.load(out)
        reg.apply(_ingest([a, b]), tmp_path)
        reg.save()
        renamed = tmp_path / "p1 sarah.wav"
        a.path.rename(renamed)

        def slow(path: Path, *args: object, **kwargs: object) -> bool:
            raise CloudFetchTimeoutError("still downloading")

        monkeypatch.setattr(fingerprint_mod, "is_dataless", lambda p: p == renamed)
        monkeypatch.setattr(fs_mod, "is_dataless", lambda p: p == renamed)
        monkeypatch.setattr(fs_mod, "ensure_materialised", slow)
        a2 = InputFile(path=renamed, file_type=FileType.AUDIO, created_at=a.created_at,
                       size_bytes=a.size_bytes)
        with pytest.raises(CloudFetchTimeoutError):
            SessionRegistry.load(out).apply(_ingest([a2, b]), tmp_path, fetch=True)

    def test_a_first_analysis_does_not_fetch_placeholders_early(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Nothing known is missing, so nothing is fetched at ingest: a fully
        evicted new study downloads at transcription, as before."""
        import bristlenose.utils.fingerprint as fingerprint_mod
        import bristlenose.utils.fs as fs_mod

        a, b = _file(tmp_path, "a.wav", 0), _file(tmp_path, "b.wav", 1)
        fetched: list[Path] = []
        monkeypatch.setattr(fingerprint_mod, "is_dataless", lambda p: True)
        monkeypatch.setattr(fs_mod, "is_dataless", lambda p: True)
        monkeypatch.setattr(fs_mod, "ensure_materialised",
                            lambda p, *a, **k: fetched.append(p) or True)
        SessionRegistry.load(tmp_path / "out").apply(_ingest([a, b]), tmp_path, fetch=True)
        assert fetched == []

    def test_a_renamed_recording_keeps_its_session(self, tmp_path: Path) -> None:
        out = tmp_path / "out"
        a, b = _file(tmp_path, "rec-1433.wav", 0), _file(tmp_path, "b.wav", 1)
        reg = SessionRegistry.load(out)
        reg.apply(_ingest([a, b]), tmp_path)
        reg.save()
        renamed = tmp_path / "p1 sarah.wav"
        a.path.rename(renamed)
        a2 = InputFile(path=renamed, file_type=FileType.AUDIO, created_at=a.created_at,
                       size_bytes=a.size_bytes)
        sessions = SessionRegistry.load(out).apply(_ingest([a2, b]), tmp_path)
        assert {s.files[0].path.name: s.session_id for s in sessions} == {
            "p1 sarah.wav": "s1", "b.wav": "s2",
        }

    def test_a_new_recording_given_an_old_name_is_a_new_session(self, tmp_path: Path) -> None:
        """Once a recording has turned up under a new name, its old name is
        free: a different recording given it must not inherit the session."""
        out = tmp_path / "out"
        a = _file(tmp_path, "interview.wav", 0)
        reg = SessionRegistry.load(out)
        reg.apply(_ingest([a]), tmp_path)
        reg.save()
        moved = tmp_path / "interview-ann.wav"
        a.path.rename(moved)
        a2 = InputFile(path=moved, file_type=FileType.AUDIO, created_at=a.created_at,
                       size_bytes=a.size_bytes)
        reg = SessionRegistry.load(out)
        reg.apply(_ingest([a2]), tmp_path)
        reg.save()
        stranger = tmp_path / "interview.wav"
        stranger.write_bytes(b"a different interview entirely")
        s = InputFile(path=stranger, file_type=FileType.AUDIO, created_at=a.created_at,
                      size_bytes=stranger.stat().st_size)
        sessions = SessionRegistry.load(out).apply(_ingest([a2, s]), tmp_path)
        assert {x.files[0].path.name: x.session_id for x in sessions} == {
            "interview-ann.wav": "s1", "interview.wav": "s2",
        }

    def test_an_edited_transcript_keeps_its_session_by_name(self, tmp_path: Path) -> None:
        """New bytes, same name: found by name, and its new content recorded."""
        out = tmp_path / "out"
        vtt = _file(tmp_path, "ann.vtt", 0, FileType.SUBTITLE_VTT)
        reg = SessionRegistry.load(out)
        reg.apply(_ingest([vtt]), tmp_path)
        reg.save()
        vtt.path.write_bytes(b"WEBVTT corrected name")
        reg = SessionRegistry.load(out)
        sessions = reg.apply(_ingest([vtt]), tmp_path)
        reg.save()
        assert [x.session_id for x in sessions] == ["s1"]
        # The NEXT run must still load the file: the old content key goes.
        again = SessionRegistry.load(out).apply(_ingest([vtt]), tmp_path)
        assert [x.session_id for x in again] == ["s1"]

    def test_a_deleted_recording_does_not_hand_its_session_to_a_new_one_of_its_name(
        self, tmp_path: Path,
    ) -> None:
        """Different bytes under an old name are a different recording (§5): the
        new one must not inherit the old participant's session, codes and names."""
        out = tmp_path / "out"
        a = _file(tmp_path, "p1.wav", 0)
        reg = SessionRegistry.load(out)
        reg.apply(_ingest([a]), tmp_path)
        reg.save()
        a.path.unlink()
        a.path.write_bytes(b"a different interview recorded later")
        b = InputFile(path=a.path, file_type=FileType.AUDIO, created_at=a.created_at,
                      size_bytes=a.path.stat().st_size)
        with _Capture("bristlenose.session_registry") as said:
            sessions = SessionRegistry.load(out).apply(_ingest([b]), tmp_path)
        assert [x.session_id for x in sessions] == ["s2"]
        assert any("new content under a name s1 held" in m for m in said), said

    def test_a_cloud_placeholder_keeps_its_session_by_its_place(
        self, tmp_path: Path, monkeypatch,
    ) -> None:
        """No bytes on disk, so no fingerprint: the place it was last seen
        finds it, even under a name the registry has never keyed."""
        out = tmp_path / "out"
        a = _file(tmp_path, "Round 1/ann.wav", 0)
        reg = SessionRegistry.load(out)
        reg.apply(_ingest([a]), tmp_path)
        reg.save()
        # Evicted, and its name key lost (as a v2 registry upgraded mid-way would).
        data = json.loads(registry_path(out).read_text())
        data["sessions"] = {k: v for k, v in data["sessions"].items() if k.startswith("fp:")}
        registry_path(out).write_text(json.dumps(data))
        import bristlenose.session_registry as sr

        monkeypatch.setattr(sr, "_fingerprint", lambda _p: None)
        sessions = SessionRegistry.load(out).apply(_ingest([a]), tmp_path)
        assert [x.session_id for x in sessions] == ["s1"]

    def test_a_place_remembers_only_its_latest_recording(
        self, tmp_path: Path, monkeypatch,
    ) -> None:
        """A deleted recording's place reused by a new one, which is then
        evicted: the placeholder must find the NEW recording's session, not the
        withdrawn participant's (second review, 15 Oct 2026)."""
        out = tmp_path / "out"
        a = _file(tmp_path, "p1.wav", 0)
        reg = SessionRegistry.load(out)
        reg.apply(_ingest([a]), tmp_path)
        reg.save()
        a.path.write_bytes(b"a different interview recorded later, same name")
        b = InputFile(path=a.path, file_type=FileType.AUDIO, created_at=a.created_at,
                      size_bytes=a.path.stat().st_size)
        reg = SessionRegistry.load(out)
        new_sid = reg.apply(_ingest([b]), tmp_path)[0].session_id
        reg.save()
        assert new_sid != "s1"
        import bristlenose.session_registry as sr

        monkeypatch.setattr(sr, "_fingerprint", lambda _p: None)  # evicted
        reg = SessionRegistry.load(out)
        assert [x.session_id for x in reg.apply(_ingest([b]), tmp_path)] == [new_sid]
        assert reg.last_known_fingerprint(b.path, tmp_path) is not None
        assert list(reg.hints.values()).count("p1.wav") == 1

    def test_version_2_upgrades_in_place(self, tmp_path: Path) -> None:
        out = tmp_path / "out"
        a = _file(tmp_path, "a.wav", 0)
        path = registry_path(out)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"version": 2, "sessions": {"stem:a": "s7"},
                                    "speakers": {}, "participants_issued": 0}))
        reg = SessionRegistry.load(out)
        sessions = reg.apply(_ingest([a]), tmp_path)
        reg.save()
        assert [x.session_id for x in sessions] == ["s7"]
        data = json.loads(path.read_text())
        assert data["version"] == 3
        assert any(k.startswith("fp:v1:") and v == "s7" for k, v in data["sessions"].items())


def _copies(tmp_path: Path, *names: str, data: bytes = b"one recording") -> list[InputFile]:
    """Byte-identical recordings under *names*, a day apart in date order."""
    files = []
    for day, name in enumerate(names):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        files.append(InputFile(path=path, file_type=FileType.AUDIO,
                               created_at=_T0 + timedelta(days=day), size_bytes=len(data)))
    return files


def _transcripts(
    tmp_path: Path, *names: str, kind: FileType = FileType.SUBTITLE_VTT,
    data: bytes = b"WEBVTT the same meeting",
) -> list[InputFile]:
    """Byte-identical transcript files under *names*, a day apart."""
    files = _copies(tmp_path, *names, data=data)
    for f in files:
        f.file_type = kind
    return files


class TestDuplicateRecordings:
    """Identical bytes under two names are one recording (design-project-identity
    §5): one session, the copy set aside and stated, never a second participant
    (R49, 20 Oct 2026). Until then both were sessions, both were transcribed,
    and the copy's quotes read as agreement."""

    def test_two_identical_recordings_are_one_session(self, tmp_path: Path) -> None:
        from bristlenose.events import UnusableReason

        files = _copies(tmp_path, "P3.wav", "P3 (1).wav")
        with _Capture("bristlenose.stages.s01_ingest") as said:
            sessions = SessionRegistry.load(tmp_path / "out").apply(_ingest(files), tmp_path)
        assert [s.session_id for s in sessions] == ["s1"]
        kept, aside = sessions[0].files
        assert (kept.path.name, kept.error) == ("P3.wav", None)
        assert (aside.path.name, aside.error) == (
            "P3 (1).wav", UnusableReason.DUPLICATE_RECORDING.value,
        )
        assert any("P3 (1).wav" in m and "P3.wav" in m for m in said), said

    def test_identical_recordings_in_two_folders_are_one_session(self, tmp_path: Path) -> None:
        """Two folders both holding ``interview.wav`` are two sessions when the
        bytes differ (12 Oct 2026); when the bytes are the same they are one
        recording, whatever the folders say."""
        files = _copies(tmp_path, "alice/interview.wav", "bob/interview.wav")
        sessions = SessionRegistry.load(tmp_path / "out").apply(_ingest(files), tmp_path)
        assert [s.session_id for s in sessions] == ["s1"]
        assert [f.error is None for f in sessions[0].files] == [True, False]

    def test_the_copy_that_owns_the_key_is_the_one_used(self, tmp_path: Path) -> None:
        """Which copy is used follows the registry's own rank — the key's
        owner, then a renamed one, then name order — never ingest's date
        order, which cloud sync rewrites (§11a)."""
        out = tmp_path / "out"

        def used(files: list[InputFile]) -> tuple[list[str], str]:
            reg = SessionRegistry.load(out)
            sessions = reg.apply(_ingest(files), tmp_path)
            reg.save()
            return [s.session_id for s in sessions], sessions[0].files[0].path.name

        files = _copies(tmp_path, "b.wav", "a.wav")
        assert used(files) == (["s1"], "a.wav"), "a fresh tie is broken by name"
        files[0].created_at, files[1].created_at = files[1].created_at, files[0].created_at
        assert used(files) == (["s1"], "a.wav"), "the used copy followed the date order"
        # Renaming the used copy: still one session, found by its bytes. (Which
        # copy is then used is name order — the set-aside copy's name is not
        # remembered, so nothing says the renamed one was the owner.)
        renamed = tmp_path / "z.wav"
        files[1].path.rename(renamed)
        files[1] = InputFile(path=renamed, file_type=FileType.AUDIO,
                             created_at=files[1].created_at, size_bytes=13)
        assert used(files)[0] == ["s1"], "renaming the used copy minted a session"

    def test_deleting_the_kept_copy_leaves_the_session_to_the_other(
        self, tmp_path: Path,
    ) -> None:
        """The other copy is the same bytes, so it is the same session, with
        the same number and everything keyed by it."""
        out = tmp_path / "out"
        files = _copies(tmp_path, "a.wav", "b.wav")
        reg = SessionRegistry.load(out)
        assert [s.session_id for s in reg.apply(_ingest(files), tmp_path)] == ["s1"]
        reg.save()
        files[0].path.unlink()
        reg = SessionRegistry.load(out)
        alone = reg.apply(_ingest([files[1]]), tmp_path)
        reg.save()
        assert [(s.session_id, s.files[0].path.name) for s in alone] == [("s1", "b.wav")]
        # And the next run still reads the file it wrote.
        assert [s.session_id for s in SessionRegistry.load(out).apply(_ingest([files[1]]), tmp_path)] == ["s1"]

    def test_a_transcript_beside_the_copy_joins_the_session(self, tmp_path: Path) -> None:
        """The copy's companions are the recording's companions: its transcript
        file is read for the one session, so the recording is not transcribed."""
        files = _copies(tmp_path, "P3.wav", "P3 (1).wav")
        vtt = _file(tmp_path, "P3 (1).vtt", 1, FileType.SUBTITLE_VTT)
        sessions = SessionRegistry.load(tmp_path / "out").apply(_ingest(files + [vtt]), tmp_path)
        assert [s.session_id for s in sessions] == ["s1"]
        assert sessions[0].has_existing_transcript
        assert [f.path.name for f in sessions[0].files if f.error is None] == ["P3.wav", "P3 (1).vtt"]

    def test_a_study_from_before_the_fold_retires_the_copys_old_session(
        self, tmp_path: Path,
    ) -> None:
        """Until 20 Oct 2026 the copy was its own session, keyed by name only.
        On the first run after, it is folded and that session retired: its
        name can never find the copy again — or deleting the kept copy would
        hand the survivor the copy's old number — and its number is kept, as
        every vanished session's is, so nothing new is numbered over it."""
        out = tmp_path / "out"
        a = _copies(tmp_path, "P3.wav", data=b"the interview")[0]
        b = _copies(tmp_path, "P3 (1).wav", data=b"something else for now")[0]
        b.created_at = a.created_at + timedelta(days=1)
        reg = SessionRegistry.load(out)
        assert [s.session_id for s in reg.apply(_ingest([a, b]), tmp_path)] == ["s1", "s2"]
        reg.save()
        # What a pre-fold registry holds for the copy: its name, no content key.
        data = json.loads(registry_path(out).read_text())
        data["sessions"] = {k: v for k, v in data["sessions"].items()
                            if not (k.startswith("fp:") and v == "s2")}
        registry_path(out).write_text(json.dumps(data))
        b.path.write_bytes(a.path.read_bytes())
        b.size_bytes = a.size_bytes

        reg = SessionRegistry.load(out)
        with _Capture("bristlenose.session_registry") as said:
            folded = reg.apply(_ingest([a, b]), tmp_path)
        reg.save()
        assert [s.session_id for s in folded] == ["s1"]
        assert any("s2" in m and "retired" in m for m in said), said
        keys = json.loads(registry_path(out).read_text())["sessions"]
        assert "stem:p3 (1)" not in keys and keys.get("retired:s2") == "s2"

        a.path.unlink()
        reg = SessionRegistry.load(out)
        survivor = reg.apply(_ingest([b]), tmp_path)
        reg.save()
        assert [s.session_id for s in survivor] == ["s1"], "the survivor took the copy's old number"

        c = _copies(tmp_path, "P4.wav", data=b"a new interview")[0]
        c.created_at = b.created_at + timedelta(days=1)
        later = SessionRegistry.load(out).apply(_ingest([b, c]), tmp_path)
        assert [s.session_id for s in later] == ["s1", "s3"], "the retired number was reused"

    # ── Identical transcript files, no recording (decision #97, 21 Oct 2026) ──
    # The same Teams ``.vtt`` or ``.docx`` downloaded twice is one session, as
    # identical recordings are. Until then the two were kept apart (R49 review
    # finding 2) and the copy's quotes read as a second participant agreeing.
    # The wire value is spelled out, not taken from the enum: it is what the
    # Files bucket and the locale key are built from.

    def test_two_identical_transcripts_are_one_session(self, tmp_path: Path) -> None:
        files = _transcripts(tmp_path, "transcript.vtt", "transcript (1).vtt")
        with _Capture("bristlenose.stages.s01_ingest") as said:
            sessions = SessionRegistry.load(tmp_path / "out").apply(_ingest(files), tmp_path)
        assert [s.session_id for s in sessions] == ["s1"]
        kept, aside = sessions[0].files
        assert (kept.path.name, kept.error) == ("transcript.vtt", None)
        assert (aside.path.name, aside.error) == ("transcript (1).vtt", "duplicate_transcript")
        assert sessions[0].has_existing_transcript
        assert any("transcript (1).vtt" in m and "transcript.vtt" in m for m in said), said

    def test_two_identical_docx_are_one_session(self, tmp_path: Path) -> None:
        files = _transcripts(
            tmp_path, "notes.docx", "notes (1).docx", kind=FileType.DOCX, data=b"PK docx bytes",
        )
        sessions = SessionRegistry.load(tmp_path / "out").apply(_ingest(files), tmp_path)
        assert [s.session_id for s in sessions] == ["s1"]
        assert [(f.path.name, f.error) for f in sessions[0].files] == [
            ("notes.docx", None), ("notes (1).docx", "duplicate_transcript"),
        ]

    def test_identical_transcripts_in_two_folders_are_one_session(self, tmp_path: Path) -> None:
        files = _transcripts(tmp_path, "alice/interview.vtt", "bob/interview.vtt")
        sessions = SessionRegistry.load(tmp_path / "out").apply(_ingest(files), tmp_path)
        assert [s.session_id for s in sessions] == ["s1"]
        assert [f.error for f in sessions[0].files] == [None, "duplicate_transcript"]

    def test_deleting_the_kept_transcript_leaves_the_session_to_the_other(
        self, tmp_path: Path,
    ) -> None:
        out = tmp_path / "out"
        files = _transcripts(tmp_path, "a.vtt", "b.vtt")
        reg = SessionRegistry.load(out)
        assert [s.session_id for s in reg.apply(_ingest(files), tmp_path)] == ["s1"]
        reg.save()
        files[0].path.unlink()
        reg = SessionRegistry.load(out)
        # A new run's ingest builds its files afresh (the first apply marked
        # this one set aside).
        alone = reg.apply(_ingest(_transcripts(tmp_path, "b.vtt")), tmp_path)
        reg.save()
        assert [(s.session_id, s.files[0].path.name, s.files[0].error) for s in alone] == [
            ("s1", "b.vtt", None),
        ]

    def test_a_study_from_before_the_fold_retires_the_transcript_copys_session(
        self, tmp_path: Path,
    ) -> None:
        """Until 21 Oct 2026 the copy was its own session, keyed by name only
        (the copy never owned the content key). The first run after folds it
        and retires that session, number kept, exactly as for a recording."""
        out = tmp_path / "out"
        a = _transcripts(tmp_path, "ann.vtt", data=b"WEBVTT the interview")[0]
        b = _transcripts(tmp_path, "ann (1).vtt", data=b"WEBVTT for now, other")[0]
        b.created_at = a.created_at + timedelta(days=1)
        reg = SessionRegistry.load(out)
        assert [s.session_id for s in reg.apply(_ingest([a, b]), tmp_path)] == ["s1", "s2"]
        reg.save()
        data = json.loads(registry_path(out).read_text())
        data["sessions"] = {k: v for k, v in data["sessions"].items()
                            if not (k.startswith("fp:") and v == "s2")}
        registry_path(out).write_text(json.dumps(data))
        b.path.write_bytes(a.path.read_bytes())
        b.size_bytes = a.size_bytes

        reg = SessionRegistry.load(out)
        folded = reg.apply(_ingest([a, b]), tmp_path)
        reg.save()
        assert [s.session_id for s in folded] == ["s1"]
        keys = json.loads(registry_path(out).read_text())["sessions"]
        assert "stem:ann (1)" not in keys and keys.get("retired:s2") == "s2"

        a.path.unlink()
        survivor = SessionRegistry.load(out).apply(_ingest([b]), tmp_path)
        assert [s.session_id for s in survivor] == ["s1"], "the survivor took the copy's old number"

    def test_a_teams_pair_downloaded_twice_is_one_session_whatever_the_order(
        self, tmp_path: Path,
    ) -> None:
        """The .vtt and the .docx of one meeting, downloaded twice. Each copy
        of each file is set aside — none is read again — and the fold does
        not depend on which file of a download landed first (a session's
        first file is its key; the two downloads can disagree)."""
        def pair(names: tuple[str, str], days: tuple[int, int]) -> list[InputFile]:
            out = []
            for name, day in zip(names, days, strict=True):
                kind = FileType.DOCX if name.endswith(".docx") else FileType.SUBTITLE_VTT
                f = _transcripts(tmp_path, name, kind=kind, data=f"bytes of {kind.value}".encode())[0]
                f.created_at = _T0 + timedelta(days=day)
                out.append(f)
            return out

        for second in ((2, 3), (3, 2)):  # the copy's .vtt first, then its .docx first
            files = pair(("mtg.vtt", "mtg.docx"), (0, 1)) + pair(
                ("mtg (1).vtt", "mtg (1).docx"), second,
            )
            files.sort(key=lambda f: (f.created_at, f.path.name))  # as discover_files does
            sessions = SessionRegistry.load(tmp_path / f"out{second}").apply(
                _ingest(files), tmp_path,
            )
            assert [s.session_id for s in sessions] == ["s1"], second
            assert sorted((f.path.name, f.error) for f in sessions[0].files) == [
                ("mtg (1).docx", "duplicate_transcript"),
                ("mtg (1).vtt", "duplicate_transcript"),
                ("mtg.docx", None),
                ("mtg.vtt", None),
            ], second

    def test_a_copy_with_a_different_companion_joins_it_as_a_candidate(
        self, tmp_path: Path,
    ) -> None:
        """Only identical files are set aside: a companion the copy carries
        that differs is another transcript of the meeting, and competes."""
        a = _transcripts(tmp_path, "mtg.vtt")[0]
        b = _transcripts(tmp_path, "mtg (1).vtt")[0]
        extra = _transcripts(tmp_path, "mtg (1).srt", kind=FileType.SUBTITLE_SRT, data=b"other")[0]
        for f, day in ((b, 1), (extra, 2)):
            f.created_at = _T0 + timedelta(days=day)
        sessions = SessionRegistry.load(tmp_path / "out").apply(_ingest([a, b, extra]), tmp_path)
        assert [s.session_id for s in sessions] == ["s1"]
        assert [(f.path.name, f.error) for f in sessions[0].files] == [
            ("mtg.vtt", None), ("mtg (1).vtt", "duplicate_transcript"), ("mtg (1).srt", None),
        ]

    def test_a_copy_file_whose_bytes_are_not_here_is_not_set_aside(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A file with no fingerprint (an evicted placeholder) proves nothing
        about being a copy, even when the owner has one too: it joins as a
        candidate rather than being stated as a duplicate it may not be."""
        import bristlenose.session_registry as sr

        real = sr._fingerprint
        monkeypatch.setattr(
            sr, "_fingerprint", lambda p: None if p is not None and p.suffix == ".srt" else real(p),
        )
        a, b = _transcripts(tmp_path, "mtg.vtt", "mtg (1).vtt")
        a_srt = _transcripts(tmp_path, "mtg.srt", kind=FileType.SUBTITLE_SRT, data=b"x")[0]
        b_srt = _transcripts(tmp_path, "mtg (1).srt", kind=FileType.SUBTITLE_SRT, data=b"y")[0]
        for f, day in ((a_srt, 1), (b, 2), (b_srt, 3)):
            f.created_at = _T0 + timedelta(days=day)
        sessions = SessionRegistry.load(tmp_path / "out").apply(
            _ingest([a, a_srt, b, b_srt]), tmp_path,
        )
        assert [s.session_id for s in sessions] == ["s1"]
        assert {f.path.name: f.error for f in sessions[0].files}["mtg (1).srt"] is None

    def test_a_recording_and_a_transcript_with_one_fingerprint_stay_apart(
        self, tmp_path: Path,
    ) -> None:
        """Only like folds with like: a recording's and a transcript's bytes
        being equal is not two copies of one thing, and is said."""
        rec = _copies(tmp_path, "ann.wav", data=b"same bytes")[0]
        vtt = _transcripts(tmp_path, "bob.vtt", data=b"same bytes")[0]
        vtt.created_at = rec.created_at + timedelta(days=1)
        with _Capture("bristlenose.session_registry") as said:
            sessions = SessionRegistry.load(tmp_path / "out").apply(_ingest([rec, vtt]), tmp_path)
        assert [s.session_id for s in sessions] == ["s1", "s2"]
        assert any("kept apart" in m for m in said), said

    def test_different_bytes_under_two_names_stay_two_sessions(self, tmp_path: Path) -> None:
        """A re-export or a trim is a different recording (§5): out of scope."""
        a = _copies(tmp_path, "P3.wav", data=b"the export")[0]
        b = _copies(tmp_path, "P3 (1).wav", data=b"the export, trimmed")[0]
        b.created_at = a.created_at + timedelta(days=1)
        sessions = SessionRegistry.load(tmp_path / "out").apply(_ingest([a, b]), tmp_path)
        assert [s.session_id for s in sessions] == ["s1", "s2"]


class TestCarriedStarts:
    """A Re-analyse resets numbering, not when an interview happened (§8)."""

    def _first_run(self, tmp_path: Path, source: str) -> tuple[Path, InputFile]:
        out = tmp_path / "out"
        a = _file(tmp_path, "rec.wav", 0)
        reg = SessionRegistry.load(out)
        sessions = reg.apply(_ingest([a]), tmp_path)
        sessions[0].session_start_source = source
        sessions[0].session_date = datetime(2026, 10, 2, 13, 33, tzinfo=timezone.utc)
        reg.settle_starts(sessions)
        reg.save()
        return out, a

    def test_a_better_start_survives_a_reset_the_new_run_can_only_read_worse(
        self, tmp_path: Path,
    ) -> None:
        from bristlenose.session_registry import starts_by_content, write_carried_starts

        out, a = self._first_run(tmp_path, "filename_zoned")
        carried = starts_by_content(out)
        assert len(carried) == 1
        fresh = tmp_path / "fresh-out"
        write_carried_starts(fresh, carried)

        reg = SessionRegistry.load(fresh)
        sessions = reg.apply(_ingest([a]), tmp_path)
        sessions[0].session_start_source = "birthtime"  # evicted: only the file date
        sessions[0].session_date = datetime(2026, 10, 9, 9, 0, tzinfo=timezone.utc)
        reg.settle_starts(sessions)
        reg.save()
        assert sessions[0].session_start_source == "filename_zoned"
        assert sessions[0].session_date == datetime(2026, 10, 2, 13, 33, tzinfo=timezone.utc)
        again = SessionRegistry.load(fresh)
        assert again.starts["s1"]["source"] == "filename_zoned"
        from bristlenose.session_registry import carried_starts_path

        assert not carried_starts_path(fresh).exists(), "the carry outlived its run"

    def test_the_carry_is_content_only_and_never_identifying(self, tmp_path: Path) -> None:
        from bristlenose.session_registry import starts_by_content

        out, _a = self._first_run(tmp_path, "filename_local")
        carried = starts_by_content(out)
        (fp, entry), = carried.items()
        assert fp.startswith("v1:")
        assert set(entry) == {"utc", "source"}

    def test_a_session_with_no_content_key_carries_its_start_by_a_hashed_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A study analysed before content keys, its recording still evicted:
        no fingerprint, so the start crosses under a hash of the name key,
        never the name (Fable review, 15 Oct 2026)."""
        import bristlenose.utils.fingerprint as fingerprint_mod
        from bristlenose.session_registry import starts_by_content, write_carried_starts

        monkeypatch.setattr(fingerprint_mod, "is_dataless", lambda p: True)
        out, a = self._first_run(tmp_path, "filename_zoned")
        carried = starts_by_content(out)
        (key, entry), = carried.items()
        assert key.startswith("name:") and "rec" not in key
        assert set(entry) == {"utc", "source"}

        fresh = tmp_path / "fresh-out"
        write_carried_starts(fresh, carried)
        reg = SessionRegistry.load(fresh)
        sessions = reg.apply(_ingest([a]), tmp_path)
        sessions[0].session_start_source = "birthtime"
        sessions[0].session_date = datetime(2026, 10, 9, 9, 0, tzinfo=timezone.utc)
        reg.settle_starts(sessions)
        assert sessions[0].session_start_source == "filename_zoned"

    def test_a_carried_start_never_beats_a_better_new_one(self, tmp_path: Path) -> None:
        from bristlenose.session_registry import starts_by_content, write_carried_starts

        out, a = self._first_run(tmp_path, "birthtime")
        fresh = tmp_path / "fresh-out"
        write_carried_starts(fresh, starts_by_content(out))
        reg = SessionRegistry.load(fresh)
        sessions = reg.apply(_ingest([a]), tmp_path)
        sessions[0].session_start_source = "container"
        reg.settle_starts(sessions)
        assert sessions[0].session_start_source == "container"


class _Capture:
    """Collect one logger's messages (caplog is fine here, but this matches the
    server tests' habit and needs no fixture)."""

    def __init__(self, name: str) -> None:
        import logging

        self.logger, self.seen = logging.getLogger(name), []
        outer = self

        class _H(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                outer.seen.append(record.getMessage())

        self.handler = _H(level=logging.WARNING)

    def __enter__(self) -> list:
        self.logger.addHandler(self.handler)
        return self.seen

    def __exit__(self, *exc: object) -> None:
        self.logger.removeHandler(self.handler)


class TestSaveOnWindows:
    """Windows refuses a rename onto a file a reader holds open; the report
    server reads the registry on every import (CI, 16 Oct 2026)."""

    def _held_then_free(self, monkeypatch: pytest.MonkeyPatch, held: int) -> list[int]:
        import bristlenose.utils.fs as fs_mod

        calls: list[int] = []
        real = fs_mod.os.replace

        def replace(src, dst):  # type: ignore[no-untyped-def]
            calls.append(1)
            if len(calls) <= held:
                raise PermissionError(5, "Access is denied")
            real(src, dst)

        monkeypatch.setattr(fs_mod.os, "replace", replace)
        monkeypatch.setattr(fs_mod.time, "sleep", lambda _s: None)
        return calls

    def test_a_save_waits_out_a_reader(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        out = tmp_path / "out"
        reg = SessionRegistry.load(out)
        reg.apply(_ingest([_file(tmp_path, "a.wav", 0)]), tmp_path)
        calls = self._held_then_free(monkeypatch, held=3)
        reg.save()
        assert len(calls) == 4
        assert SessionRegistry.load(out).sessions, "the registry was not written"
        assert not list((out / ".bristlenose").glob(".sessions.*.tmp")), "a temp file was left"

    def test_a_save_still_fails_when_the_lock_never_lifts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        out = tmp_path / "out"
        reg = SessionRegistry.load(out)
        reg.apply(_ingest([_file(tmp_path, "a.wav", 0)]), tmp_path)
        self._held_then_free(monkeypatch, held=10_000)
        with pytest.raises(PermissionError):
            reg.save()
        assert not list((out / ".bristlenose").glob(".sessions.*.tmp")), "a temp file was left"

