"""Tests for name extraction, auto-population, and short_name suggestion."""

from __future__ import annotations

from datetime import datetime, timezone

from bristlenose.models import (
    FullTranscript,
    PeopleFile,
    PersonComputed,
    PersonEditable,
    PersonEntry,
    SpeakerRole,
    TranscriptSegment,
)
from bristlenose.people import (
    auto_populate_names,
    extract_names_from_labels,
    suggest_short_names,
)
from bristlenose.stages.identify_speakers import SpeakerInfo

_NOW = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)


def _computed(pid: str) -> PersonComputed:
    return PersonComputed(
        participant_id=pid,
        session_date=_NOW,
        duration_seconds=600.0,
        words_spoken=100,
        pct_words=50.0,
        pct_time_speaking=50.0,
        source_file="test.mp4",
    )


def _people(*entries: tuple[str, str, str, str]) -> PeopleFile:
    """Build a PeopleFile from (pid, full_name, short_name, role) tuples."""
    participants: dict[str, PersonEntry] = {}
    for pid, full, short, role in entries:
        participants[pid] = PersonEntry(
            computed=_computed(pid),
            editable=PersonEditable(
                full_name=full, short_name=short, role=role
            ),
        )
    return PeopleFile(
        last_updated=_NOW,
        participants=participants,
    )


def _transcript(
    pid: str,
    speaker_label: str | None,
    role: SpeakerRole = SpeakerRole.PARTICIPANT,
) -> FullTranscript:
    return FullTranscript(
        participant_id=pid,
        source_file="test.mp4",
        session_date=_NOW,
        duration_seconds=600.0,
        segments=[
            TranscriptSegment(
                start_time=0.0,
                end_time=10.0,
                text="Hello world",
                speaker_label=speaker_label,
                speaker_role=role,
            ),
        ],
    )


# ---------------------------------------------------------------------------
# extract_names_from_labels
# ---------------------------------------------------------------------------


class TestExtractNamesFromLabels:
    def test_real_name(self) -> None:
        t = _transcript("p1", "Sarah Jones")
        result = extract_names_from_labels([t])
        assert result == {"p1": "Sarah Jones"}

    def test_generic_speaker_a(self) -> None:
        t = _transcript("p1", "Speaker A")
        result = extract_names_from_labels([t])
        assert result == {}

    def test_generic_speaker_1(self) -> None:
        t = _transcript("p1", "Speaker 1")
        result = extract_names_from_labels([t])
        assert result == {}

    def test_generic_speaker_00(self) -> None:
        t = _transcript("p1", "SPEAKER_00")
        result = extract_names_from_labels([t])
        assert result == {}

    def test_generic_unknown(self) -> None:
        t = _transcript("p1", "Unknown")
        result = extract_names_from_labels([t])
        assert result == {}

    def test_none_label(self) -> None:
        t = _transcript("p1", None)
        result = extract_names_from_labels([t])
        assert result == {}

    def test_numeric_label(self) -> None:
        t = _transcript("p1", "42")
        result = extract_names_from_labels([t])
        assert result == {}

    def test_researcher_segments_ignored(self) -> None:
        """Only PARTICIPANT-role segments contribute labels."""
        t = FullTranscript(
            participant_id="p1",
            source_file="test.mp4",
            session_date=_NOW,
            duration_seconds=600.0,
            segments=[
                TranscriptSegment(
                    start_time=0.0,
                    end_time=10.0,
                    text="Hello",
                    speaker_label="Dr Smith",
                    speaker_role=SpeakerRole.RESEARCHER,
                ),
                TranscriptSegment(
                    start_time=10.0,
                    end_time=20.0,
                    text="Hi",
                    speaker_label="Jane Doe",
                    speaker_role=SpeakerRole.PARTICIPANT,
                ),
            ],
        )
        result = extract_names_from_labels([t])
        assert result == {"p1": "Jane Doe"}

    def test_multiple_participants(self) -> None:
        t1 = _transcript("p1", "Alice Walker")
        t2 = _transcript("p2", "Bob Chen")
        result = extract_names_from_labels([t1, t2])
        assert result == {"p1": "Alice Walker", "p2": "Bob Chen"}


# ---------------------------------------------------------------------------
# auto_populate_names
# ---------------------------------------------------------------------------


class TestAutoPopulateNames:
    def test_fills_empty_from_llm(self) -> None:
        people = _people(("p1", "", "", ""))
        info = SpeakerInfo(
            speaker_label="Speaker A",
            role=SpeakerRole.PARTICIPANT,
            person_name="Sarah Jones",
            job_title="Product Manager",
        )
        auto_populate_names(people, {"p1": info}, {})
        assert people.participants["p1"].editable.full_name == "Sarah Jones"
        assert people.participants["p1"].editable.role == "Product Manager"

    def test_preserves_existing_name(self) -> None:
        people = _people(("p1", "Existing Name", "", "Existing Role"))
        info = SpeakerInfo(
            speaker_label="Speaker A",
            role=SpeakerRole.PARTICIPANT,
            person_name="LLM Name",
            job_title="LLM Role",
        )
        auto_populate_names(people, {"p1": info}, {})
        assert people.participants["p1"].editable.full_name == "Existing Name"
        assert people.participants["p1"].editable.role == "Existing Role"

    def test_llm_priority_over_label(self) -> None:
        people = _people(("p1", "", "", ""))
        info = SpeakerInfo(
            speaker_label="Sarah Jones",
            role=SpeakerRole.PARTICIPANT,
            person_name="Sarah J. Jones",
            job_title="Designer",
        )
        auto_populate_names(people, {"p1": info}, {"p1": "Sarah Jones"})
        # LLM name takes priority.
        assert people.participants["p1"].editable.full_name == "Sarah J. Jones"

    def test_label_fallback_when_no_llm(self) -> None:
        people = _people(("p1", "", "", ""))
        auto_populate_names(people, {}, {"p1": "John Smith"})
        assert people.participants["p1"].editable.full_name == "John Smith"

    def test_no_data_leaves_empty(self) -> None:
        people = _people(("p1", "", "", ""))
        auto_populate_names(people, {}, {})
        assert people.participants["p1"].editable.full_name == ""
        assert people.participants["p1"].editable.role == ""


# ---------------------------------------------------------------------------
# suggest_short_names
# ---------------------------------------------------------------------------


class TestSuggestShortNames:
    def test_basic(self) -> None:
        people = _people(("p1", "Sarah Jones", "", ""))
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "Sarah"

    def test_already_set(self) -> None:
        people = _people(("p1", "Sarah Jones", "SJ", ""))
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "SJ"

    def test_collision(self) -> None:
        people = _people(
            ("p1", "Sarah Jones", "", ""),
            ("p2", "Sarah King", "", ""),
        )
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "Sarah J."
        assert people.participants["p2"].editable.short_name == "Sarah K."

    def test_single_word_name(self) -> None:
        people = _people(("p1", "Madonna", "", ""))
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "Madonna"

    def test_hyphenated(self) -> None:
        people = _people(("p1", "Mary-Jane Watson", "", ""))
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "Mary-Jane"

    def test_empty_full_name(self) -> None:
        people = _people(("p1", "", "", ""))
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == ""

    def test_three_way_collision(self) -> None:
        people = _people(
            ("p1", "Sarah Jones", "", ""),
            ("p2", "Sarah King", "", ""),
            ("p3", "Sarah Lee", "", ""),
        )
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "Sarah J."
        assert people.participants["p2"].editable.short_name == "Sarah K."
        assert people.participants["p3"].editable.short_name == "Sarah L."

    def test_collision_same_initial(self) -> None:
        """When two people share first name AND last initial, both get same short."""
        people = _people(
            ("p1", "Sarah Jones", "", ""),
            ("p2", "Sarah Jackson", "", ""),
        )
        suggest_short_names(people)
        # Both get "Sarah J." — unavoidable, user can fix manually.
        assert people.participants["p1"].editable.short_name == "Sarah J."
        assert people.participants["p2"].editable.short_name == "Sarah J."

    def test_mixed_set_and_unset(self) -> None:
        """Only fills empty short_names; existing ones are untouched."""
        people = _people(
            ("p1", "Alice Walker", "AW", ""),
            ("p2", "Bob Chen", "", ""),
        )
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "AW"
        assert people.participants["p2"].editable.short_name == "Bob"

    def test_no_candidates(self) -> None:
        """No-op when everyone already has a short_name."""
        people = _people(
            ("p1", "Alice Walker", "Alice", ""),
            ("p2", "Bob Chen", "Bob", ""),
        )
        suggest_short_names(people)
        assert people.participants["p1"].editable.short_name == "Alice"
        assert people.participants["p2"].editable.short_name == "Bob"


# ---------------------------------------------------------------------------
# SpeakerRoleItem backward compatibility
# ---------------------------------------------------------------------------


class TestSpeakerRoleItemBackwardCompat:
    def test_without_new_fields(self) -> None:
        """SpeakerRoleItem works without person_name/job_title."""
        from bristlenose.llm.structured import SpeakerRoleItem

        item = SpeakerRoleItem(
            speaker_label="Speaker A",
            role="participant",
            reasoning="Main respondent",
        )
        assert item.person_name == ""
        assert item.job_title == ""

    def test_with_new_fields(self) -> None:
        from bristlenose.llm.structured import SpeakerRoleItem

        item = SpeakerRoleItem(
            speaker_label="Speaker A",
            role="participant",
            reasoning="Introduces as Sarah",
            person_name="Sarah",
            job_title="UX Designer",
        )
        assert item.person_name == "Sarah"
        assert item.job_title == "UX Designer"
