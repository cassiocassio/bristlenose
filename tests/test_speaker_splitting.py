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
    async def test_late_segments_are_read_not_inherited(self) -> None:
        """The whole transcript is read: a turn ten minutes in gets its own label.

        Until 3 Oct 2026 only the first 5-8 minutes were sent and the last label
        was carried to the end, so segment 3 here came back as Speaker B.
        """
        from bristlenose.llm.structured import SpeakerBoundary, SpeakerSplitAssignment
        from bristlenose.stages.s05b_identify_speakers import split_single_speaker_llm

        segments = [
            _seg(0.0, 10.0, "Welcome.", None),
            _seg(11.0, 20.0, "Thanks.", None),
            _seg(610.0, 620.0, "So what happened next?", None),
            _seg(621.0, 630.0, "We went back to the shop.", None),
        ]
        mock_client = AsyncMock()
        mock_client.analyze = AsyncMock(return_value=SpeakerSplitAssignment(
            speaker_count=2,
            boundaries=[
                SpeakerBoundary(segment_index=0, speaker_id="Speaker A"),
                SpeakerBoundary(segment_index=1, speaker_id="Speaker B"),
                SpeakerBoundary(segment_index=2, speaker_id="Speaker A"),
                SpeakerBoundary(segment_index=3, speaker_id="Speaker B"),
            ],
        ))

        await split_single_speaker_llm(segments, mock_client)

        prompt = mock_client.analyze.call_args.kwargs["user_prompt"]
        assert "We went back to the shop." in prompt
        assert [s.speaker_label for s in segments] == [
            "Speaker A", "Speaker B", "Speaker A", "Speaker B",
        ]

    @pytest.mark.asyncio
    async def test_long_transcript_is_read_in_parts_that_carry_identities(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Each part after the first is shown the lines before it, labelled."""
        import bristlenose.stages.s05b_identify_speakers as s05b
        from bristlenose.llm.structured import SpeakerBoundary, SpeakerSplitAssignment

        monkeypatch.setattr(s05b, "SPLIT_CHUNK_SEGMENTS", 3)
        segments = [_seg(i * 10.0, i * 10.0 + 9, f"line {i}", None) for i in range(7)]
        parts = [
            [(0, "Speaker A"), (1, "Speaker B")],
            [(3, "Speaker A"), (5, "Speaker B")],  # line 4 stays A
            [],  # no change in the last part: line 6 continues as B
        ]
        mock_client = AsyncMock()
        mock_client.analyze = AsyncMock(side_effect=[
            SpeakerSplitAssignment(speaker_count=2, boundaries=[
                SpeakerBoundary(segment_index=i, speaker_id=who) for i, who in part
            ])
            for part in parts
        ])

        await s05b.split_single_speaker_llm(segments, mock_client)

        assert mock_client.analyze.call_count == 3
        prompts = [c.kwargs["user_prompt"] for c in mock_client.analyze.call_args_list]
        assert "untrusted_labelled_lines" not in prompts[0]
        assert "[2] (Speaker B) line 2" in prompts[1]
        assert "[5] (Speaker B) line 5" in prompts[2]
        assert "[6] line 6" in prompts[2] and "[2] line 2" not in prompts[2]
        assert [s.speaker_label for s in segments] == [
            "Speaker A", "Speaker B", "Speaker B",
            "Speaker A", "Speaker A", "Speaker B", "Speaker B",
        ]

    @pytest.mark.asyncio
    async def test_a_failed_later_part_keeps_the_parts_already_labelled(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import bristlenose.stages.s05b_identify_speakers as s05b
        from bristlenose.llm.structured import SpeakerBoundary, SpeakerSplitAssignment

        monkeypatch.setattr(s05b, "SPLIT_CHUNK_SEGMENTS", 2)
        segments = [_seg(i * 10.0, i * 10.0 + 9, f"line {i}", None) for i in range(5)]
        mock_client = AsyncMock()
        mock_client.analyze = AsyncMock(side_effect=[
            SpeakerSplitAssignment(speaker_count=2, boundaries=[
                SpeakerBoundary(segment_index=0, speaker_id="Speaker A"),
                SpeakerBoundary(segment_index=1, speaker_id="Speaker B"),
            ]),
            RuntimeError("rate limited"),
        ])
        errors: list[str] = []

        await s05b.split_single_speaker_llm(segments, mock_client, errors=errors)

        assert mock_client.analyze.call_count == 2  # stops at the failure
        assert [s.speaker_label for s in segments] == ["Speaker A"] + ["Speaker B"] * 4
        assert errors == ["speaker splitting (part 2 of 3): rate limited"]

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

    def test_ikea_shape_inputs_assign_roles_correctly(self) -> None:
        """Heavy word-share asymmetry survives participant rhetorical questions.

        Regression pin (b1-long-audio-quality, 2026-05-14): IKEA-shape session
        where the moderator gives short prompts and the participant runs long
        monologues that occasionally include question-shaped utterances
        ("Do you know what I mean?"). The ~10:1 word ratio should ensure
        word_asymmetry dominates, keeping the right speaker as moderator.
        """
        from bristlenose.stages.s05b_identify_speakers import (
            identify_speaker_roles_heuristic,
        )

        segments = [
            _seg(0.0, 5.0, "Tell me about your favourite household object.", "Mod"),
            _seg(6.0, 80.0,
                 "Well, I've got one of those crock pots that you use for "
                 "fermentation, do you know what I mean? It's kind of a "
                 "classic design. The thing about it is that the water "
                 "creates a seal so when it's fermenting the gas can come "
                 "out, which is ingenious really. And the alternatives are "
                 "all just plastic with these silly burping lids. Is that "
                 "the right thing to be saying? I think so.",
                 "Guest"),
            _seg(81.0, 84.0, "Okay. What else?", "Mod"),
            _seg(85.0, 180.0,
                 "Then there's the IKEA shopping experience itself. I'd "
                 "probably go straight to search because some of these "
                 "taxonomies, I'm not sure if they would be helpful. Maybe "
                 "I'd check the room seating but actually I'd probably look "
                 "for a specific thing I had in mind, you know? It's quite "
                 "busy, the homepage. I'd want kitchenware probably. Do you "
                 "see what I'm getting at? Hard to say without trying.",
                 "Guest"),
            _seg(181.0, 184.0, "Walk me through what you'd do.", "Mod"),
            _seg(185.0, 280.0,
                 "So I'd type crockpot and probably get nothing useful. "
                 "Then I'd browse food and storage, find one of the jars "
                 "and tins sections. Actually that's exactly what I want. "
                 "The naming is interesting, all Swedish, slight plays on "
                 "words. It feels designed for browsing rather than direct "
                 "search, which worked for me in the end. Although I got "
                 "confused at checkout with the minimum order business.",
                 "Guest"),
        ]

        identify_speaker_roles_heuristic(segments)

        for seg in segments:
            if seg.speaker_label == "Mod":
                assert seg.speaker_role == SpeakerRole.RESEARCHER, (
                    f"Expected RESEARCHER for moderator segment: {seg.text[:40]!r}"
                )
            else:
                assert seg.speaker_role == SpeakerRole.PARTICIPANT, (
                    f"Expected PARTICIPANT for guest segment: {seg.text[:40]!r}"
                )


# ---------------------------------------------------------------------------
# The gate in front of the splitter (1b, 1 Oct 2026)
# ---------------------------------------------------------------------------
#
# `split_single_speaker_llm` was unchanged by this gate; its window and
# propagation were replaced on 3 Oct 2026 by whole-transcript splitting. What changed is WHICH
# sessions reach it: a platform transcript that names its speakers never does,
# because the splitter overwrote the one real name an in-room interview carried
# with "Speaker A/B" (measured, 30 Sep 2026).


def _platform_seg(label: str | None, source: str, i: int = 0) -> TranscriptSegment:
    return TranscriptSegment(
        start_time=float(i * 10), end_time=float(i * 10 + 9), text="words here",
        speaker_label=label, source=source,
    )


class TestSplitGate:
    def _gate(self, labels: list[str | None], source: str):
        from bristlenose.stages.s05b_identify_speakers import split_gate

        return split_gate([_platform_seg(lbl, source, i) for i, lbl in enumerate(labels)])

    def test_whisper_with_no_labels_splits(self) -> None:
        from bristlenose.stages.s05b_identify_speakers import SplitGate

        assert self._gate([None] * 5, "whisper") is SplitGate.SPLIT
        assert self._gate([None] * 5, "mlx-whisper") is SplitGate.SPLIT

    def test_whisper_with_one_placeholder_label_splits(self) -> None:
        from bristlenose.stages.s05b_identify_speakers import SplitGate

        assert self._gate(["Speaker 1"] * 5, "faster-whisper") is SplitGate.SPLIT

    def test_two_labels_are_already_separated(self) -> None:
        from bristlenose.stages.s05b_identify_speakers import SplitGate

        assert self._gate(["Ana", "Bruno", "Ana"], "vtt") is SplitGate.SEPARATED
        assert self._gate(["Speaker A", "Speaker B"], "whisper") is SplitGate.SEPARATED

    def test_one_real_name_on_a_platform_transcript_is_the_account(self) -> None:
        """Two people in a room, one Teams account: the name is real and it
        is kept. Splitting would overwrite it with Speaker A/B."""
        from bristlenose.stages.s05b_identify_speakers import SplitGate

        assert self._gate(["Martin Storey"] * 6, "vtt") is SplitGate.NOT_SEPARATED
        assert self._gate(["Martin Storey"] * 6, "docx") is SplitGate.NOT_SEPARATED
        assert self._gate(["Martin Storey"] * 6, "srt") is SplitGate.NOT_SEPARATED

    def test_cloud_transcript_with_no_names_splits(self) -> None:
        """The writer said `speakers: none`. Until 4 Oct 2026 that kept the
        interview as one voice; now the whole-transcript splitter guesses."""
        from bristlenose.stages.s03_parse_subtitles import CLOUD_TRANSCRIPT_SOURCE
        from bristlenose.stages.s05b_identify_speakers import SplitGate

        assert self._gate([None] * 6, CLOUD_TRANSCRIPT_SOURCE) is SplitGate.SPLIT

    def test_vendor_captions_with_no_names_still_split(self) -> None:
        """A bare caption track dropped in by hand behaves as it did yesterday."""
        from bristlenose.stages.s05b_identify_speakers import SplitGate

        assert self._gate([None] * 6, "vtt") is SplitGate.SPLIT
        assert self._gate(["Speaker 1"] * 6, "srt") is SplitGate.SPLIT

    def test_a_phone_number_is_not_a_name(self) -> None:
        from bristlenose.stages.s05b_identify_speakers import SplitGate

        assert self._gate(["+44 7700 ****23"] * 6, "vtt") is SplitGate.SPLIT

    def test_empty_session_has_nothing_to_split(self) -> None:
        from bristlenose.stages.s05b_identify_speakers import SplitGate, split_gate

        assert split_gate([]) is SplitGate.SEPARATED
