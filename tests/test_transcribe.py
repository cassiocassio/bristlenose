"""Tests for stage 5 transcription helpers."""

from __future__ import annotations

from bristlenose.stages.s05_transcribe import collapse_adjacent_repeats


class TestCollapseAdjacentRepeats:
    """Collapse adjacent identical n-grams in transcript text.

    Asymmetric thresholds: content-word and phrase-level repeats collapse
    aggressively (almost always artefacts); interjection / discourse-marker
    doublings are protected because real speech does that (Thatcher's
    "No. No. No.", "yeah yeah", "very very good").
    """

    def test_leaves_normal_text_alone(self) -> None:
        text = "Thank you for your time. It was a great conversation."
        assert collapse_adjacent_repeats(text) == text

    def test_collapses_content_word_run(self) -> None:
        assert collapse_adjacent_repeats("thanks thanks thanks thanks") == "thanks"
        assert (
            collapse_adjacent_repeats("facebook facebook facebook") == "facebook"
        )
        assert collapse_adjacent_repeats("crockpot crockpot") == "crockpot"

    def test_collapses_bigram_repeat(self) -> None:
        # Phrase-level repeats collapse regardless of word-type.
        assert (
            collapse_adjacent_repeats("Thank you. Thank you. Thank you.")
            == "Thank you."
        )

    def test_collapses_longer_phrase(self) -> None:
        text = (
            "thanks very much for your time "
            "thanks very much for your time "
            "thanks very much for your time"
        )
        assert collapse_adjacent_repeats(text) == "thanks very much for your time"

    def test_preserves_natural_interjection_doubling(self) -> None:
        # Thatcher's iconic "No. No. No.", agreement-mirroring "yeah yeah",
        # emphatic intensifier doubling — real speech, protected.
        assert collapse_adjacent_repeats("No. No. No.") == "No. No. No."
        assert collapse_adjacent_repeats("yeah yeah") == "yeah yeah"
        assert collapse_adjacent_repeats("very very good") == "very very good"
        assert collapse_adjacent_repeats("well well well") == "well well well"
        assert collapse_adjacent_repeats("okay okay") == "okay okay"

    def test_collapses_extreme_interjection_loops(self) -> None:
        # Six or more repetitions of an interjection is Whisper looping,
        # past any plausible natural emphasis.
        assert collapse_adjacent_repeats("no no no no no no no") == "no"
        assert collapse_adjacent_repeats("yeah yeah yeah yeah yeah yeah") == "yeah"

    def test_handles_ikea_tail_pattern(self) -> None:
        # Synthesised from the actual 2026-05-09 IKEA Whisper output.
        text = (
            "thanks very much for your time stopping here "
            "thanks very much for your time "
            "thanks very much for your time "
            "thanks very much thanks thanks thanks thanks "
            "facebook facebook Thank you."
        )
        out = collapse_adjacent_repeats(text)
        assert " thanks thanks " not in out
        assert "facebook facebook" not in out

    def test_short_input(self) -> None:
        assert collapse_adjacent_repeats("") == ""
        assert collapse_adjacent_repeats("hi") == "hi"
