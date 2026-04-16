"""Tests for LLM-based speaker splitting (single-speaker → multi-speaker)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from bristlenose.models import SpeakerRole, TranscriptSegment


def _seg(
    start: float,
    end: float,
    text: str,
    label: str | None = None,
) -> TranscriptSegment:
    return TranscriptSegment(
        start_time=start,
        end_time=end,
        text=text,
        speaker_label=label,
        source="whisper",
    )


# ---------------------------------------------------------------------------
# Guard: already multi-speaker → no-op
# ---------------------------------------------------------------------------


class TestSplitGuard:
    @pytest.mark.asyncio
    async def test_multi_speaker_returns_unchanged(self) -> None:
        from bristlenose.stages.s05b_identify_speakers import split_single_speaker_llm

        segments = [
            _seg(0.0, 10.0, "Hello.", "Speaker A"),
            _seg(11.0, 20.0, "Hi there.", "Speaker B"),
        ]
        result = await split_single_speaker_llm(segments, object())

        assert result is segments
        assert segments[0].speaker_label == "Speaker A"
        assert segments[1].speaker_label == "Speaker B"

    @pytest.mark.asyncio
    async def test_empty_segments_returns_unchanged(self) -> None:
        from bristlenose.stages.s05b_identify_speakers import split_single_speaker_llm

        result = await split_single_speaker_llm([], object())
        assert result == []


# ---------------------------------------------------------------------------
# Successful split
# ---------------------------------------------------------------------------


class TestSplitSuccess:
    @pytest.mark.asyncio
    async def test_splits_single_speaker_into_two(self) -> None:
        from bristlenose.llm.structured import SpeakerBoundary, SpeakerSplitAssignment
        from bristlenose.stages.s05b_identify_speakers import split_single_speaker_llm

        segments = [
            _seg(0.0, 10.0, "Welcome to the interview.", None),
            _seg(11.0, 20.0, "My name is Brian.", None),
            _seg(21.0, 30.0, "Thank you Brian, happy to be here.", None),
            _seg(31.0, 40.0, "So tell me about your work.", None),
            _seg(41.0, 50.0, "I work in product design.", None),
        ]

        mock_result = SpeakerSplitAssignment(
            speaker_count=2,
            boundaries=[
                SpeakerBoundary(segment_index=0, speaker_id="Speaker A", person_name="Brian"),
                SpeakerBoundary(segment_index=2, speaker_id="Speaker B"),
                SpeakerBoundary(segment_index=3, speaker_id="Speaker A", person_name="Brian"),
                SpeakerBoundary(segment_index=4, speaker_id="Speaker B"),
            ],
        )

        mock_client = AsyncMock()
        mock_client.analyze = AsyncMock(return_value=mock_result)

        result = await split_single_speaker_llm(segments, mock_client)

        assert result is segments
        assert segments[0].speaker_label == "Speaker A"
        assert segments[1].speaker_label == "Speaker A"
        assert segments[2].speaker_label == "Speaker B"
        assert segments[3].speaker_label == "Speaker A"
        assert segments[4].speaker_label == "Speaker B"

    @pytest.mark.asyncio
    async def test_carry_forward_beyond_sample_window(self) -> None:
        """Segments beyond the sample window get the last speaker's label."""
        from bristlenose.llm.structured import SpeakerBoundary, SpeakerSplitAssignment
        from bristlenose.stages.s05b_identify_speakers import split_single_speaker_llm

        segments = [
            _seg(0.0, 10.0, "Welcome.", None),
            _seg(11.0, 20.0, "Thanks.", None),
            # Beyond sample window (ceiling = min(max(300, 630*0.18), 480) = 300s)
            _seg(610.0, 620.0, "This is later in the conversation.", None),
            _seg(621.0, 630.0, "Much later.", None),
        ]

        mock_result = SpeakerSplitAssignment(
            speaker_count=2,
            boundaries=[
                SpeakerBoundary(segment_index=0, speaker_id="Speaker A"),
                SpeakerBoundary(segment_index=1, speaker_id="Speaker B"),
            ],
        )

        mock_client = AsyncMock()
        mock_client.analyze = AsyncMock(return_value=mock_result)

        await split_single_speaker_llm(segments, mock_client)

        # Segments beyond sample window carry forward last boundary speaker
        assert segments[2].speaker_label == "Speaker B"
        assert segments[3].speaker_label == "Speaker B"

    @pytest.mark.asyncio
    async def test_single_speaker_confirmed_no_change(self) -> None:
        """LLM confirms single speaker → labels unchanged."""
        from bristlenose.llm.structured import SpeakerBoundary, SpeakerSplitAssignment
        from bristlenose.stages.s05b_identify_speakers import split_single_speaker_llm

        segments = [
            _seg(0.0, 10.0, "Just me talking.", None),
            _seg(11.0, 20.0, "Still me.", None),
        ]
        original_labels = [seg.speaker_label for seg in segments]

        mock_result = SpeakerSplitAssignment(
            speaker_count=1,
            boundaries=[
                SpeakerBoundary(segment_index=0, speaker_id="Speaker A"),
            ],
        )

        mock_client = AsyncMock()
        mock_client.analyze = AsyncMock(return_value=mock_result)

        await split_single_speaker_llm(segments, mock_client)

        assert [seg.speaker_label for seg in segments] == original_labels


# ---------------------------------------------------------------------------
# Failure / fallback
# ---------------------------------------------------------------------------


class TestSplitFallback:
    @pytest.mark.asyncio
    async def test_llm_exception_returns_unchanged(self) -> None:
        from bristlenose.stages.s05b_identify_speakers import split_single_speaker_llm

        segments = [
            _seg(0.0, 10.0, "Hello.", None),
            _seg(11.0, 20.0, "World.", None),
        ]

        mock_client = AsyncMock()
        mock_client.analyze = AsyncMock(side_effect=RuntimeError("LLM failed"))

        errors: list[str] = []
        await split_single_speaker_llm(segments, mock_client, errors=errors)

        assert segments[0].speaker_label is None
        assert segments[1].speaker_label is None
        assert len(errors) == 1
        assert "speaker splitting" in errors[0]

    @pytest.mark.asyncio
    async def test_llm_exception_no_errors_list(self) -> None:
        """Exception handling works even without errors list."""
        from bristlenose.stages.s05b_identify_speakers import split_single_speaker_llm

        segments = [_seg(0.0, 10.0, "Hello.", None)]

        mock_client = AsyncMock()
        mock_client.analyze = AsyncMock(side_effect=RuntimeError("boom"))

        # Should not raise
        await split_single_speaker_llm(segments, mock_client)
        assert segments[0].speaker_label is None


# ---------------------------------------------------------------------------
# Integration with heuristic pass
# ---------------------------------------------------------------------------


class TestSplitThenHeuristic:
    @pytest.mark.asyncio
    async def test_split_enables_heuristic_role_detection(self) -> None:
        """After splitting, the heuristic can detect researcher vs participant."""
        from bristlenose.llm.structured import SpeakerBoundary, SpeakerSplitAssignment
        from bristlenose.stages.s05b_identify_speakers import (
            identify_speaker_roles_heuristic,
            split_single_speaker_llm,
        )

        segments = [
            _seg(0.0, 10.0, "Can you tell me about your experience?", None),
            _seg(11.0, 20.0, "What do you think of the new design?", None),
            _seg(21.0, 40.0, "Yeah I really liked it actually, I think the layout is much better now.", None),
            _seg(41.0, 50.0, "How would you rate it on a scale of 1 to 10?", None),
            _seg(51.0, 70.0, "I would say about an 8, the navigation is smooth and intuitive.", None),
            _seg(71.0, 80.0, "Walk me through how you use it day to day.", None),
            _seg(81.0, 100.0, "I open it every morning to check my dashboard and review tasks.", None),
        ]

        mock_result = SpeakerSplitAssignment(
            speaker_count=2,
            boundaries=[
                SpeakerBoundary(segment_index=0, speaker_id="Speaker A"),
                SpeakerBoundary(segment_index=2, speaker_id="Speaker B"),
                SpeakerBoundary(segment_index=3, speaker_id="Speaker A"),
                SpeakerBoundary(segment_index=4, speaker_id="Speaker B"),
                SpeakerBoundary(segment_index=5, speaker_id="Speaker A"),
                SpeakerBoundary(segment_index=6, speaker_id="Speaker B"),
            ],
        )

        mock_client = AsyncMock()
        mock_client.analyze = AsyncMock(return_value=mock_result)

        await split_single_speaker_llm(segments, mock_client)
        identify_speaker_roles_heuristic(segments)

        # Speaker A asks questions → researcher
        assert segments[0].speaker_role == SpeakerRole.RESEARCHER
        assert segments[1].speaker_role == SpeakerRole.RESEARCHER
        assert segments[3].speaker_role == SpeakerRole.RESEARCHER
        assert segments[5].speaker_role == SpeakerRole.RESEARCHER

        # Speaker B answers → participant
        assert segments[2].speaker_role == SpeakerRole.PARTICIPANT
        assert segments[4].speaker_role == SpeakerRole.PARTICIPANT
        assert segments[6].speaker_role == SpeakerRole.PARTICIPANT


# ---------------------------------------------------------------------------
# All-Unknown label handling
# ---------------------------------------------------------------------------


class TestUnknownLabelHandling:
    @pytest.mark.asyncio
    async def test_all_unknown_labels_triggers_split(self) -> None:
        """Segments with speaker_label='Unknown' should trigger splitting."""
        from bristlenose.llm.structured import SpeakerBoundary, SpeakerSplitAssignment
        from bristlenose.stages.s05b_identify_speakers import split_single_speaker_llm

        segments = [
            _seg(0.0, 10.0, "Hello.", "Unknown"),
            _seg(11.0, 20.0, "Hi there.", "Unknown"),
        ]

        mock_result = SpeakerSplitAssignment(
            speaker_count=2,
            boundaries=[
                SpeakerBoundary(segment_index=0, speaker_id="Speaker A"),
                SpeakerBoundary(segment_index=1, speaker_id="Speaker B"),
            ],
        )

        mock_client = AsyncMock()
        mock_client.analyze = AsyncMock(return_value=mock_result)

        await split_single_speaker_llm(segments, mock_client)

        assert segments[0].speaker_label == "Speaker A"
        assert segments[1].speaker_label == "Speaker B"

    @pytest.mark.asyncio
    async def test_all_same_label_triggers_split(self) -> None:
        """Segments all with same non-null label should trigger splitting."""
        from bristlenose.llm.structured import SpeakerBoundary, SpeakerSplitAssignment
        from bristlenose.stages.s05b_identify_speakers import split_single_speaker_llm

        segments = [
            _seg(0.0, 10.0, "Hello.", "Speaker 1"),
            _seg(11.0, 20.0, "Hi there.", "Speaker 1"),
        ]

        mock_result = SpeakerSplitAssignment(
            speaker_count=2,
            boundaries=[
                SpeakerBoundary(segment_index=0, speaker_id="Speaker A"),
                SpeakerBoundary(segment_index=1, speaker_id="Speaker B"),
            ],
        )

        mock_client = AsyncMock()
        mock_client.analyze = AsyncMock(return_value=mock_result)

        await split_single_speaker_llm(segments, mock_client)

        assert segments[0].speaker_label == "Speaker A"
        assert segments[1].speaker_label == "Speaker B"

    @pytest.mark.asyncio
    async def test_out_of_range_boundaries_filtered(self) -> None:
        """Boundary indices beyond segment count are ignored."""
        from bristlenose.llm.structured import SpeakerBoundary, SpeakerSplitAssignment
        from bristlenose.stages.s05b_identify_speakers import split_single_speaker_llm

        segments = [
            _seg(0.0, 10.0, "Hello.", None),
            _seg(11.0, 20.0, "Hi.", None),
        ]

        mock_result = SpeakerSplitAssignment(
            speaker_count=2,
            boundaries=[
                SpeakerBoundary(segment_index=0, speaker_id="Speaker A"),
                SpeakerBoundary(segment_index=1, speaker_id="Speaker B"),
                SpeakerBoundary(segment_index=999, speaker_id="Speaker C"),
            ],
        )

        mock_client = AsyncMock()
        mock_client.analyze = AsyncMock(return_value=mock_result)

        await split_single_speaker_llm(segments, mock_client)

        assert segments[0].speaker_label == "Speaker A"
        assert segments[1].speaker_label == "Speaker B"


# ---------------------------------------------------------------------------
# Heuristic: oral history role detection
# ---------------------------------------------------------------------------


class TestInterviewerHeuristic:
    """Verify the heuristic detects interviewers across interview styles.

    Covers: word count asymmetry (researcher speaks less), open-ended
    prompting phrases, and task-oriented UXR phrases.
    """

    def test_interviewer_detected_by_word_asymmetry(self) -> None:
        """Speaker who talks much less should be tagged RESEARCHER."""
        from bristlenose.stages.s05b_identify_speakers import (
            identify_speaker_roles_heuristic,
        )

        # Interviewer: short prompts (few words)
        # Interviewee: long substantive answers (many words)
        segments = [
            _seg(0.0, 5.0, "Welcome to today's interview.", "Interviewer"),
            _seg(6.0, 60.0,
                 "Thank you. So I started at Pixar in 1995, working on Toy Story. "
                 "It was an incredible experience because we were pioneering computer "
                 "animation and nobody really knew what was possible yet. The team was "
                 "small and we all wore many hats.",
                 "Guest"),
            _seg(61.0, 65.0, "Tell me about those early days.", "Interviewer"),
            _seg(66.0, 130.0,
                 "Well the early days were chaotic in the best way. We had this "
                 "tiny office and everyone was passionate about pushing the boundaries "
                 "of what computers could do with animation. John Lasseter had this "
                 "incredible vision and we were all just trying to keep up with his "
                 "ideas. The rendering alone took forever back then.",
                 "Guest"),
            _seg(131.0, 135.0, "What happened next?", "Interviewer"),
            _seg(136.0, 200.0,
                 "After Toy Story shipped, everything changed. The company grew rapidly "
                 "and we went from this scrappy startup to a major studio almost "
                 "overnight. I moved into a leadership role managing the rendering "
                 "pipeline team. We had to figure out how to scale everything we had "
                 "built for one movie to support multiple productions simultaneously.",
                 "Guest"),
        ]

        identify_speaker_roles_heuristic(segments)

        # Interviewer speaks ~15 words, Guest speaks ~150+
        # Word asymmetry + open-ended prompting phrases -> RESEARCHER
        for seg in segments:
            if seg.speaker_label == "Interviewer":
                assert seg.speaker_role == SpeakerRole.RESEARCHER, (
                    f"Expected RESEARCHER for interviewer segment: {seg.text[:40]}"
                )
            else:
                assert seg.speaker_role == SpeakerRole.PARTICIPANT, (
                    f"Expected PARTICIPANT for guest segment: {seg.text[:40]}"
                )

    def test_open_ended_phrases_contribute_to_score(self) -> None:
        """Open-ended prompting phrases should be recognised as researcher signals."""
        from bristlenose.stages.s05b_identify_speakers import (
            identify_speaker_roles_heuristic,
        )

        # Two speakers with roughly equal word counts, but one uses
        # oral-history interviewer phrases
        segments = [
            _seg(0.0, 10.0, "Tell me about your work on the project.", "A"),
            _seg(11.0, 20.0, "I joined the team in January and started coding.", "B"),
            _seg(21.0, 30.0, "Can you describe what the process was like?", "A"),
            _seg(31.0, 40.0, "It was very collaborative with daily standups.", "B"),
            _seg(41.0, 50.0, "How did you get involved with that initiative?", "A"),
            _seg(51.0, 60.0, "My manager recommended me for the role initially.", "B"),
        ]

        identify_speaker_roles_heuristic(segments)

        # Speaker A uses open-ended prompts that match _RESEARCHER_PHRASES
        assert segments[0].speaker_role == SpeakerRole.RESEARCHER
        assert segments[1].speaker_role == SpeakerRole.PARTICIPANT

    def test_uxr_still_works_after_changes(self) -> None:
        """Verify no regression: UXR moderator phrases still trigger RESEARCHER."""
        from bristlenose.stages.s05b_identify_speakers import (
            identify_speaker_roles_heuristic,
        )

        segments = [
            _seg(0.0, 10.0, "Can you try clicking on the settings icon?", "Mod"),
            _seg(11.0, 30.0, "Sure, let me click here. Oh I see the menu now.", "User"),
            _seg(31.0, 40.0, "Walk me through what you see on this screen.", "Mod"),
            _seg(41.0, 60.0, "There's a list of options and a search bar at the top.", "User"),
            _seg(61.0, 70.0, "What would you expect to find in settings?", "Mod"),
            _seg(71.0, 90.0, "Probably account info, notifications, maybe theme options.", "User"),
        ]

        identify_speaker_roles_heuristic(segments)

        assert segments[0].speaker_role == SpeakerRole.RESEARCHER
        assert segments[1].speaker_role == SpeakerRole.PARTICIPANT
