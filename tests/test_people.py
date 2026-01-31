"""Tests for the people file (participant registry): models, compute, merge, I/O."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from bristlenose.models import (
    FileType,
    FullTranscript,
    InputFile,
    InputSession,
    PeopleFile,
    PersonComputed,
    PersonEditable,
    PersonEntry,
    SpeakerRole,
    TranscriptSegment,
)
from bristlenose.people import (
    PEOPLE_FILENAME,
    build_display_name_map,
    compute_participant_stats,
    load_people_file,
    merge_people,
    write_people_file,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)


def _session(pid: str, num: int, filename: str = "test.mp4") -> InputSession:
    return InputSession(
        participant_id=pid,
        participant_number=num,
        files=[
            InputFile(
                path=Path(f"/tmp/{filename}"),
                file_type=FileType.VIDEO,
                created_at=_NOW,
                size_bytes=1000,
            )
        ],
        session_date=_NOW,
    )


def _transcript(
    pid: str,
    segments: list[TranscriptSegment],
    duration: float = 600.0,
) -> FullTranscript:
    return FullTranscript(
        participant_id=pid,
        source_file="test.mp4",
        session_date=_NOW,
        duration_seconds=duration,
        segments=segments,
    )


def _seg(
    text: str,
    role: SpeakerRole = SpeakerRole.PARTICIPANT,
    start: float = 0.0,
    end: float = 10.0,
) -> TranscriptSegment:
    return TranscriptSegment(
        start_time=start,
        end_time=end,
        text=text,
        speaker_role=role,
    )


def _computed(pid: str, words: int = 100, pct_words: float = 50.0) -> PersonComputed:
    return PersonComputed(
        participant_id=pid,
        session_date=_NOW,
        duration_seconds=600.0,
        words_spoken=words,
        pct_words=pct_words,
        pct_time_speaking=40.0,
        source_file="test.mp4",
    )


# ---------------------------------------------------------------------------
# Model round-trip
# ---------------------------------------------------------------------------


def test_people_model_roundtrip() -> None:
    """PeopleFile → YAML → PeopleFile preserves all data."""
    people = PeopleFile(
        last_updated=_NOW,
        participants={
            "p1": PersonEntry(
                computed=_computed("p1"),
                editable=PersonEditable(short_name="Alice", role="Designer"),
            ),
        },
    )

    data = people.model_dump(mode="json")
    yaml_str = yaml.dump(data, default_flow_style=False)
    loaded = PeopleFile.model_validate(yaml.safe_load(yaml_str))

    assert loaded.participants["p1"].editable.short_name == "Alice"
    assert loaded.participants["p1"].computed.words_spoken == 100


# ---------------------------------------------------------------------------
# compute_participant_stats
# ---------------------------------------------------------------------------


def test_compute_stats_basic() -> None:
    """Compute word count and speaking percentage for one participant."""
    sessions = [_session("p1", 1)]
    transcripts = [
        _transcript(
            "p1",
            [
                _seg("hello world how are you", start=0, end=10),
                _seg("I am the researcher asking", role=SpeakerRole.RESEARCHER, start=10, end=20),
                _seg("this is my answer yes indeed", start=20, end=30),
            ],
            duration=60.0,
        )
    ]

    stats = compute_participant_stats(sessions, transcripts)

    assert "p1" in stats
    # participant words: 5 + 6 = 11 (researcher excluded)
    assert stats["p1"].words_spoken == 11
    assert stats["p1"].pct_words == 100.0  # only one participant
    # speaking time: 10 + 10 = 20 seconds out of 60
    assert stats["p1"].pct_time_speaking == round(20 / 60 * 100, 1)


def test_compute_stats_multiple_participants() -> None:
    """pct_words distributes correctly across two participants."""
    sessions = [_session("p1", 1), _session("p2", 2)]
    transcripts = [
        _transcript("p1", [_seg("one two three")]),  # 3 words
        _transcript("p2", [_seg("four five six seven")]),  # 4 words
    ]

    stats = compute_participant_stats(sessions, transcripts)

    total = 3 + 4
    assert stats["p1"].pct_words == round(3 / total * 100, 1)
    assert stats["p2"].pct_words == round(4 / total * 100, 1)


def test_compute_stats_no_transcript() -> None:
    """Session with no matching transcript gets zero stats."""
    sessions = [_session("p1", 1)]
    transcripts: list[FullTranscript] = []

    stats = compute_participant_stats(sessions, transcripts)

    assert stats["p1"].words_spoken == 0
    assert stats["p1"].pct_time_speaking == 0.0


# ---------------------------------------------------------------------------
# merge_people
# ---------------------------------------------------------------------------


def test_merge_new_participants() -> None:
    """Merging with no existing file creates entries with default editable."""
    computed = {"p1": _computed("p1")}
    result = merge_people(None, computed)

    assert "p1" in result.participants
    assert result.participants["p1"].editable.short_name == ""
    assert result.participants["p1"].computed.words_spoken == 100


def test_merge_preserves_editable() -> None:
    """Existing short_name and role survive a re-run."""
    existing = PeopleFile(
        last_updated=_NOW,
        participants={
            "p1": PersonEntry(
                computed=_computed("p1", words=50),
                editable=PersonEditable(short_name="Sarah", role="PM"),
            ),
        },
    )

    new_computed = {"p1": _computed("p1", words=200, pct_words=100.0)}
    result = merge_people(existing, new_computed)

    entry = result.participants["p1"]
    assert entry.editable.short_name == "Sarah"
    assert entry.editable.role == "PM"
    # computed was refreshed
    assert entry.computed.words_spoken == 200


def test_merge_adds_new_participant() -> None:
    """New participant added alongside existing ones."""
    existing = PeopleFile(
        last_updated=_NOW,
        participants={
            "p1": PersonEntry(
                computed=_computed("p1"),
                editable=PersonEditable(short_name="Alice"),
            ),
        },
    )

    new_computed = {
        "p1": _computed("p1", words=150),
        "p2": _computed("p2", words=80),
    }
    result = merge_people(existing, new_computed)

    assert "p1" in result.participants
    assert "p2" in result.participants
    assert result.participants["p1"].editable.short_name == "Alice"
    assert result.participants["p2"].editable.short_name == ""  # new, default


def test_merge_keeps_removed_participant() -> None:
    """Participant missing from current run is kept (not deleted)."""
    existing = PeopleFile(
        last_updated=_NOW,
        participants={
            "p1": PersonEntry(
                computed=_computed("p1"),
                editable=PersonEditable(short_name="Alice", notes="Important"),
            ),
            "p2": PersonEntry(
                computed=_computed("p2"),
                editable=PersonEditable(short_name="Bob"),
            ),
        },
    )

    # New run only has p1
    new_computed = {"p1": _computed("p1", words=300)}
    result = merge_people(existing, new_computed)

    assert "p1" in result.participants
    assert "p2" in result.participants  # kept from old file
    assert result.participants["p2"].editable.short_name == "Bob"


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def test_write_people_file(tmp_path: Path) -> None:
    """Written YAML is valid and contains the header comment."""
    people = PeopleFile(
        last_updated=_NOW,
        participants={
            "p1": PersonEntry(
                computed=_computed("p1"),
                editable=PersonEditable(short_name="Sarah"),
            ),
        },
    )

    path = write_people_file(people, tmp_path)
    content = path.read_text(encoding="utf-8")

    assert path.name == PEOPLE_FILENAME
    assert "# people.yaml" in content
    assert "short_name" in content

    # Verify round-trip
    loaded = yaml.safe_load(content)
    assert loaded["participants"]["p1"]["editable"]["short_name"] == "Sarah"


def test_load_nonexistent(tmp_path: Path) -> None:
    """Loading from a directory without people.yaml returns None."""
    result = load_people_file(tmp_path)
    assert result is None


def test_load_existing(tmp_path: Path) -> None:
    """Load a previously written people file."""
    people = PeopleFile(
        last_updated=_NOW,
        participants={
            "p1": PersonEntry(
                computed=_computed("p1"),
                editable=PersonEditable(full_name="Sarah Jones", role="Designer"),
            ),
        },
    )
    write_people_file(people, tmp_path)

    loaded = load_people_file(tmp_path)
    assert loaded is not None
    assert loaded.participants["p1"].editable.full_name == "Sarah Jones"
    assert loaded.participants["p1"].computed.words_spoken == 100


# ---------------------------------------------------------------------------
# Display name map
# ---------------------------------------------------------------------------


def test_display_name_map_with_short_names() -> None:
    """short_name is used as display name when set."""
    people = PeopleFile(
        last_updated=_NOW,
        participants={
            "p1": PersonEntry(
                computed=_computed("p1"),
                editable=PersonEditable(short_name="Sarah"),
            ),
            "p2": PersonEntry(
                computed=_computed("p2"),
                editable=PersonEditable(),  # no short_name
            ),
        },
    )

    names = build_display_name_map(people)
    assert names["p1"] == "Sarah"
    assert names["p2"] == "p2"  # falls back to participant_id


def test_display_name_map_empty() -> None:
    """Empty people file produces empty map."""
    people = PeopleFile(last_updated=_NOW)
    names = build_display_name_map(people)
    assert names == {}


# ---------------------------------------------------------------------------
# Percentage sanity
# ---------------------------------------------------------------------------


def test_pct_words_sums_to_approximately_100() -> None:
    """pct_words across all participants should sum to ~100."""
    sessions = [_session("p1", 1), _session("p2", 2), _session("p3", 3)]
    transcripts = [
        _transcript("p1", [_seg("one two three")]),
        _transcript("p2", [_seg("four five")]),
        _transcript("p3", [_seg("six seven eight nine ten")]),
    ]

    stats = compute_participant_stats(sessions, transcripts)

    total_pct = sum(s.pct_words for s in stats.values())
    assert 99.5 <= total_pct <= 100.5  # allow rounding
