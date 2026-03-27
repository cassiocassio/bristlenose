"""Tests for clip manifest builder — pure logic, no I/O."""

from __future__ import annotations

from pathlib import Path

from bristlenose.server.clip_manifest import (
    ClipSpec,
    _QuoteLike,
    apply_padding,
    build_clip_filename,
    build_clip_manifest,
    extract_gist,
    format_clip_timecode,
    merge_adjacent_clips,
    zero_pad_code,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_spec(**overrides) -> ClipSpec:  # type: ignore[no-untyped-def]
    defaults = dict(
        quote_id="q-p1-42",
        participant_id="p1",
        session_id="s1",
        source_path=Path("/media/video.mp4"),
        start=39.0,
        end=56.0,
        raw_start=42.0,
        speaker_name="Sarah",
        quote_gist="onboarding was confusing",
        is_audio_only=False,
        is_starred=True,
        is_hero=False,
    )
    defaults.update(overrides)
    return ClipSpec(**defaults)


def _make_quote(**overrides) -> _QuoteLike:  # type: ignore[no-untyped-def]
    defaults = dict(
        quote_id="q-p1-42",
        participant_id="p1",
        session_id="s1",
        start_timecode=42.0,
        end_timecode=54.0,
        text="The onboarding was really confusing for me",
        is_starred=True,
        is_hero=False,
    )
    defaults.update(overrides)
    return _QuoteLike(**defaults)


# ---------------------------------------------------------------------------
# extract_gist
# ---------------------------------------------------------------------------


class TestExtractGist:
    def test_basic(self) -> None:
        assert extract_gist("The onboarding was really confusing") == (
            "the onboarding was really confusing"
        )

    def test_six_word_limit(self) -> None:
        result = extract_gist("one two three four five six seven eight")
        assert result == "one two three four five six"

    def test_max_chars_truncation(self) -> None:
        result = extract_gist("a bb ccc dddd eeeee ffffff ggggggg", max_chars=15)
        assert len(result) <= 15
        assert result == "a bb ccc dddd"

    def test_strips_punctuation(self) -> None:
        result = extract_gist('He said "I can\'t believe it!"')
        assert '"' not in result
        assert "'" not in result
        assert "!" not in result

    def test_empty_text_returns_clip(self) -> None:
        assert extract_gist("") == "clip"

    def test_whitespace_only_returns_clip(self) -> None:
        assert extract_gist("   ") == "clip"

    def test_punctuation_only_returns_clip(self) -> None:
        assert extract_gist("?!...") == "clip"

    def test_lowercase(self) -> None:
        assert extract_gist("EVERYTHING WAS GREAT") == "everything was great"


# ---------------------------------------------------------------------------
# zero_pad_code
# ---------------------------------------------------------------------------


class TestZeroPadCode:
    def test_under_10_no_padding(self) -> None:
        assert zero_pad_code("p1", 5) == "p1"

    def test_10_plus_two_digit_padding(self) -> None:
        assert zero_pad_code("p1", 12) == "p01"
        assert zero_pad_code("p10", 12) == "p10"

    def test_100_plus_three_digit_padding(self) -> None:
        assert zero_pad_code("p1", 105) == "p001"
        assert zero_pad_code("p42", 105) == "p042"

    def test_moderator_code(self) -> None:
        assert zero_pad_code("m1", 12) == "m01"

    def test_no_digits_unchanged(self) -> None:
        assert zero_pad_code("moderator", 12) == "moderator"


# ---------------------------------------------------------------------------
# format_clip_timecode
# ---------------------------------------------------------------------------


class TestFormatClipTimecode:
    def test_under_one_hour(self) -> None:
        assert format_clip_timecode(225.0) == "03m45"

    def test_zero(self) -> None:
        assert format_clip_timecode(0.0) == "00m00"

    def test_use_hours(self) -> None:
        assert format_clip_timecode(225.0, use_hours=True) == "0h03m45"

    def test_over_one_hour_with_hours(self) -> None:
        assert format_clip_timecode(3730.0, use_hours=True) == "1h02m10"

    def test_exactly_one_hour(self) -> None:
        assert format_clip_timecode(3600.0, use_hours=True) == "1h00m00"


# ---------------------------------------------------------------------------
# build_clip_filename
# ---------------------------------------------------------------------------


class TestBuildClipFilename:
    def test_basic(self) -> None:
        spec = _make_spec(raw_start=225.0)
        result = build_clip_filename(spec, participant_count=5, use_hours=False)
        assert result == "p1 03m45 Sarah onboarding was confusing.mp4"

    def test_anonymised(self) -> None:
        spec = _make_spec(raw_start=225.0)
        result = build_clip_filename(
            spec, participant_count=5, use_hours=False, anonymise=True,
        )
        assert "Sarah" not in result
        assert result.startswith("p01 03m45")
        assert result.endswith(".mp4")

    def test_audio_only_extension(self) -> None:
        spec = _make_spec(is_audio_only=True, raw_start=225.0)
        result = build_clip_filename(spec, participant_count=5, use_hours=False)
        assert result.endswith(".m4a")

    def test_no_speaker_name(self) -> None:
        spec = _make_spec(speaker_name="", raw_start=225.0)
        result = build_clip_filename(spec, participant_count=5, use_hours=False)
        assert result == "p1 03m45 onboarding was confusing.mp4"

    def test_with_hours(self) -> None:
        spec = _make_spec(raw_start=3730.0)
        result = build_clip_filename(spec, participant_count=5, use_hours=True)
        assert "1h02m10" in result

    def test_safe_filename_applied(self) -> None:
        spec = _make_spec(speaker_name="Dr. O'Brien", quote_gist="it was great")
        result = build_clip_filename(spec, participant_count=5, use_hours=False)
        assert "/" not in result
        assert "\\" not in result
        assert ".." not in result


# ---------------------------------------------------------------------------
# apply_padding
# ---------------------------------------------------------------------------


class TestApplyPadding:
    def test_normal(self) -> None:
        start, end = apply_padding(10.0, 20.0, 300.0)
        assert start == 7.0
        assert end == 22.0

    def test_clamp_to_zero(self) -> None:
        start, end = apply_padding(1.0, 10.0, 300.0)
        assert start == 0.0

    def test_clamp_to_duration(self) -> None:
        start, end = apply_padding(295.0, 299.0, 300.0)
        assert end == 300.0

    def test_custom_padding(self) -> None:
        start, end = apply_padding(10.0, 20.0, 300.0, pad_before=5.0, pad_after=5.0)
        assert start == 5.0
        assert end == 25.0


# ---------------------------------------------------------------------------
# merge_adjacent_clips
# ---------------------------------------------------------------------------


class TestMergeAdjacentClips:
    def test_empty(self) -> None:
        assert merge_adjacent_clips([]) == []

    def test_single_clip(self) -> None:
        clips = [_make_spec()]
        result = merge_adjacent_clips(clips)
        assert len(result) == 1

    def test_within_threshold_merged(self) -> None:
        c1 = _make_spec(start=10.0, end=20.0)
        c2 = _make_spec(quote_id="q-p1-26", start=25.0, end=35.0)
        result = merge_adjacent_clips([c1, c2], threshold=10.0)
        assert len(result) == 1
        assert result[0].start == 10.0
        assert result[0].end == 35.0

    def test_beyond_threshold_not_merged(self) -> None:
        c1 = _make_spec(start=10.0, end=20.0)
        c2 = _make_spec(quote_id="q-p1-26", start=40.0, end=50.0)
        result = merge_adjacent_clips([c1, c2], threshold=10.0)
        assert len(result) == 2

    def test_different_sessions_not_merged(self) -> None:
        c1 = _make_spec(session_id="s1", start=10.0, end=20.0)
        c2 = _make_spec(quote_id="q-p2-5", session_id="s2", start=15.0, end=25.0)
        result = merge_adjacent_clips([c1, c2], threshold=10.0)
        assert len(result) == 2

    def test_merged_keeps_first_metadata(self) -> None:
        c1 = _make_spec(quote_gist="first gist", start=10.0, end=20.0)
        c2 = _make_spec(
            quote_id="q-p1-26", quote_gist="second gist", start=25.0, end=35.0,
        )
        result = merge_adjacent_clips([c1, c2], threshold=10.0)
        assert result[0].quote_gist == "first gist"

    def test_merged_preserves_starred(self) -> None:
        c1 = _make_spec(is_starred=False, start=10.0, end=20.0)
        c2 = _make_spec(quote_id="q-p1-26", is_starred=True, start=25.0, end=35.0)
        result = merge_adjacent_clips([c1, c2], threshold=10.0)
        assert result[0].is_starred is True


# ---------------------------------------------------------------------------
# build_clip_manifest
# ---------------------------------------------------------------------------


class TestBuildClipManifest:
    def test_empty_quotes(self) -> None:
        result = build_clip_manifest([], {}, {}, {})
        assert result == []

    def test_single_quote(self) -> None:
        q = _make_quote()
        result = build_clip_manifest(
            [q],
            speaker_map={("s1", "p1"): "Sarah"},
            session_media={"s1": (Path("/media/v.mp4"), False)},
            session_durations={"s1": 300.0},
        )
        assert len(result) == 1
        assert result[0].speaker_name == "Sarah"
        assert result[0].start < q.start_timecode  # padding applied

    def test_deduplication(self) -> None:
        q1 = _make_quote()
        q2 = _make_quote()  # same quote_id
        result = build_clip_manifest(
            [q1, q2],
            speaker_map={("s1", "p1"): "Sarah"},
            session_media={"s1": (Path("/media/v.mp4"), False)},
            session_durations={"s1": 300.0},
        )
        assert len(result) == 1

    def test_no_media_filtered(self) -> None:
        q = _make_quote()
        result = build_clip_manifest(
            [q],
            speaker_map={("s1", "p1"): "Sarah"},
            session_media={},  # no media for s1
            session_durations={"s1": 300.0},
        )
        assert result == []

    def test_anonymise(self) -> None:
        q = _make_quote()
        result = build_clip_manifest(
            [q],
            speaker_map={("s1", "p1"): "Sarah"},
            session_media={"s1": (Path("/media/v.mp4"), False)},
            session_durations={"s1": 300.0},
            anonymise=True,
        )
        assert result[0].speaker_name == ""

    def test_padding_clamped(self) -> None:
        q = _make_quote(start_timecode=1.0, end_timecode=5.0)
        result = build_clip_manifest(
            [q],
            speaker_map={("s1", "p1"): "Sarah"},
            session_media={"s1": (Path("/media/v.mp4"), False)},
            session_durations={"s1": 300.0},
        )
        assert result[0].start == 0.0  # clamped (1.0 - 3.0 = -2.0 → 0.0)

    def test_audio_only_flag(self) -> None:
        q = _make_quote()
        result = build_clip_manifest(
            [q],
            speaker_map={("s1", "p1"): "Sarah"},
            session_media={"s1": (Path("/media/audio.m4a"), True)},
            session_durations={"s1": 300.0},
        )
        assert result[0].is_audio_only is True
