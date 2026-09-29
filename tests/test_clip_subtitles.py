"""Tests for clip subtitles: timing, corrections, cues, WebVTT/SRT."""

from __future__ import annotations

import pytest

from bristlenose.server.clip_subtitles import (
    APPLIED,
    MAX_LINE_CHARS,
    NO_WORDS,
    UNPLACED,
    Correction,
    SegmentInput,
    Token,
    WordTiming,
    apply_correction,
    assign_colours,
    build_cues,
    spread_evenly,
    to_srt,
    to_webvtt,
    tokens_for_segment,
    wrap_lines,
)


def _words(*triples: tuple[str, float, float]) -> tuple[WordTiming, ...]:
    return tuple(WordTiming(t, s, e) for t, s, e in triples)


def _tok(text: str, start: float, end: float, speaker: str = "p1") -> Token:
    return Token(text=text, start=start, end=end, speaker_code=speaker)


def _texts(tokens: list[Token]) -> list[str]:
    return [t.text for t in tokens]


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------


class TestSpreadEvenly:
    def test_covers_the_span_in_order(self) -> None:
        spans = spread_evenly(["a", "bbb", "cc"], 10.0, 19.0)
        assert spans[0][0] == 10.0
        assert spans[-1][1] == pytest.approx(19.0)
        for (s1, e1), (s2, _e2) in zip(spans, spans[1:]):
            assert e1 == pytest.approx(s2)
            assert s1 < e1

    def test_longer_words_get_longer_time(self) -> None:
        (a, b) = spread_evenly(["a", "abcdefg"], 0.0, 10.0)
        assert (b[1] - b[0]) > (a[1] - a[0])

    def test_empty(self) -> None:
        assert spread_evenly([], 0.0, 1.0) == []


class TestTokensForSegment:
    def test_uses_word_timings_when_they_match(self) -> None:
        seg = SegmentInput("p1", 10.0, 20.0, "I like it", _words(
            ("I", 10.5, 10.7), ("like", 10.8, 11.2), ("it", 11.3, 11.5),
        ))
        toks = tokens_for_segment(seg)
        assert _texts(toks) == ["I", "like", "it"]
        assert (toks[1].start, toks[1].end) == (10.8, 11.2)

    def test_unmatched_word_is_spread_between_neighbours(self) -> None:
        # Whisper's words and the segment text disagree on the middle word.
        seg = SegmentInput("p1", 10.0, 20.0, "I really like it", _words(
            ("I", 10.0, 10.2), ("like", 11.0, 11.4), ("it", 11.5, 11.7),
        ))
        toks = tokens_for_segment(seg)
        assert _texts(toks) == ["I", "really", "like", "it"]
        assert toks[1].start >= 10.2
        assert toks[1].end <= 11.0 + 1e-9

    def test_no_word_timings_spreads_across_the_segment(self) -> None:
        seg = SegmentInput("m1", 4.0, 8.0, "How was that?")
        toks = tokens_for_segment(seg)
        assert toks[0].start == 4.0
        assert toks[-1].end == pytest.approx(8.0)
        assert all(t.speaker_code == "m1" for t in toks)

    def test_times_never_run_backwards(self) -> None:
        seg = SegmentInput("p1", 0.0, 5.0, "a b c", _words(
            ("a", 2.0, 2.5), ("b", 1.0, 1.5), ("c", 3.0, 3.5),
        ))
        toks = tokens_for_segment(seg)
        starts = [t.start for t in toks]
        assert starts == sorted(starts)


# ---------------------------------------------------------------------------
# Researcher corrections
# ---------------------------------------------------------------------------


class TestApplyCorrection:
    def _span(self) -> list[Token]:
        return [
            _tok("we", 10.0, 10.2), _tok("um", 10.3, 10.5), _tok("moved", 10.6, 11.0),
            _tok("to", 11.1, 11.2), _tok("cube", 11.3, 11.6), _tok("ernetes", 11.6, 12.0),
            _tok("last", 12.1, 12.4), _tok("year.", 12.5, 12.9),
        ]

    def test_mis_transcription_is_replaced_keeping_neighbour_timings(self) -> None:
        corr = Correction(
            "p1", 10.0, 13.0,
            original="We moved to cube ernetes last year.",
            corrected="We moved to Kubernetes last year.",
        )
        out, outcome = apply_correction(self._span(), corr)
        assert outcome == APPLIED
        assert _texts(out) == ["we", "um", "moved", "to", "Kubernetes", "last", "year."]
        kube = out[4]
        assert (kube.start, kube.end) == pytest.approx((11.3, 12.0))
        assert (out[5].start, out[5].end) == (12.1, 12.4)

    def test_pipeline_tidying_does_not_remove_audible_words(self) -> None:
        # The pipeline dropped "um"; the researcher only fixed the product name.
        # "um" is still in the audio, so it stays in the subtitles.
        corr = Correction(
            "p1", 10.0, 13.0,
            original="We moved to cube ernetes last year.",
            corrected="We moved to Kubernetes last year.",
        )
        out, _ = apply_correction(self._span(), corr)
        assert "um" in _texts(out)

    def test_researcher_deletion_is_ignored(self) -> None:
        corr = Correction(
            "p1", 10.0, 13.0,
            original="We moved to cube ernetes last year.",
            corrected="We moved to cube ernetes.",
        )
        out, outcome = apply_correction(self._span(), corr)
        assert outcome == APPLIED
        assert _texts(out) == _texts(self._span())

    def test_insertion_of_a_dropped_word(self) -> None:
        corr = Correction(
            "p1", 10.0, 13.0,
            original="We moved to cube ernetes last year.",
            corrected="We moved to cube ernetes only last year.",
        )
        out, outcome = apply_correction(self._span(), corr)
        assert outcome == APPLIED
        assert _texts(out) == [
            "we", "um", "moved", "to", "cube", "ernetes", "only", "last", "year.",
        ]

    def test_bracket_in_place_of_a_spoken_name_is_shown(self) -> None:
        # The researcher's substitution wins: "[her]" must not revert to the
        # name, which is what per-word bracket handling did.
        tokens = [_tok("I", 0.0, 0.2), _tok("told", 0.3, 0.5), _tok("Sarah", 0.6, 1.0),
                  _tok("that.", 1.1, 1.4)]
        corr = Correction("p1", 0.0, 2.0, original="I told Sarah that.",
                          corrected="I told [her] that.")
        out, outcome = apply_correction(tokens, corr)
        assert outcome == APPLIED
        assert _texts(out) == ["I", "told", "[her]", "that."]
        assert (out[2].start, out[2].end) == (0.6, 1.0)

    def test_multi_word_editorial_insertion_is_not_subtitled(self) -> None:
        tokens = [_tok("it", 0.0, 0.2), _tok("crashed.", 0.3, 0.8)]
        corr = Correction("p1", 0.0, 2.0, original="it crashed.",
                          corrected="it [the app] crashed.")
        out, outcome = apply_correction(tokens, corr)
        assert outcome == APPLIED
        assert _texts(out) == ["it", "crashed."]

    def test_elisions_and_editorial_brackets_are_not_subtitled(self) -> None:
        corr = Correction(
            "p1", 10.0, 13.0,
            original="We moved to cube ernetes last year.",
            corrected="We moved to [the] Kubernetes … last year.",
        )
        out, _ = apply_correction(self._span(), corr)
        assert "…" not in _texts(out)
        assert "[the]" not in _texts(out)
        assert "Kubernetes" in _texts(out)

    def test_unplaceable_correction_changes_nothing(self) -> None:
        # Never a guess that could delete or repeat what was said: the
        # transcript's own words stand, and the caller logs the quote.
        corr = Correction(
            "p1", 10.0, 13.0,
            original="Something the transcript never said.",
            corrected="Something entirely different.",
        )
        out, outcome = apply_correction(self._span(), corr)
        assert outcome == UNPLACED
        assert out == self._span()

    def test_correction_to_words_past_the_quotes_recorded_end(self) -> None:
        # The model's end time falls before the quote's last words (measured
        # on real projects). The fix to those words must land once, in place:
        # no audible word lost, nothing shown twice.
        tokens = [
            _tok("Sure.", 10.0, 10.4), _tok("I", 10.5, 10.6), _tok("found", 10.7, 11.0),
            _tok("my", 17.0, 17.2), _tok("settings", 17.3, 17.8), _tok("were.", 18.2, 18.8),
        ]
        corr = Correction(
            "p1", 10.0, 18.0,
            original="I found my settings were.",
            corrected="I found my Settings panel was.",
        )
        out, outcome = apply_correction(tokens, corr)
        assert outcome == APPLIED
        assert _texts(out) == ["Sure.", "I", "found", "my", "Settings", "panel", "was."]
        assert out[-1].end == pytest.approx(18.8)

    def test_other_speakers_are_untouched(self) -> None:
        tokens = [*self._span(), _tok("Right.", 11.4, 11.5, "m1")]
        corr = Correction(
            "p1", 10.0, 13.0,
            original="We moved to cube ernetes last year.",
            corrected="Something entirely different.",
        )
        out, _ = apply_correction(tokens, corr)
        assert [t for t in out if t.speaker_code == "m1"] == [tokens[-1]]

    def test_correction_outside_the_tokens_changes_nothing(self) -> None:
        corr = Correction("p1", 50.0, 60.0, original="x", corrected="y")
        out, outcome = apply_correction(self._span(), corr)
        assert out == self._span()
        assert outcome == NO_WORDS


# ---------------------------------------------------------------------------
# Cues
# ---------------------------------------------------------------------------


class TestWrapLines:
    def test_short_text_is_one_line(self) -> None:
        assert wrap_lines(["It", "works."]) == ("It works.",)

    def test_long_text_splits_into_two_lines_within_the_limit(self) -> None:
        words = "I thought the export would be in the share menu but it was not".split()
        lines = wrap_lines(words)
        assert lines is not None and len(lines) == 2
        assert all(len(line) <= MAX_LINE_CHARS for line in lines)

    def test_too_long_for_two_lines_is_none(self) -> None:
        words = ("word " * 30).split()
        assert wrap_lines(words) is None

    def test_single_overlong_word_is_allowed(self) -> None:
        url = "https://example.com/" + "x" * 50
        assert wrap_lines([url]) == (url,)


class TestAssignColours:
    def test_participant_is_white_others_follow_bbc_order(self) -> None:
        colours = assign_colours(["m1", "p1", "o1", "p2"], primary="p1")
        assert colours == {"p1": "white", "m1": "yellow", "o1": "cyan", "p2": "green"}

    def test_cycles_past_four_without_reusing_white(self) -> None:
        colours = assign_colours(["a", "b", "c", "d"], primary="p1")
        assert colours["d"] == "yellow"
        assert "white" not in {colours[c] for c in "abcd"}


class TestBuildCues:
    def test_rebased_to_clip_time_and_clamped(self) -> None:
        toks = [_tok("Hello", 9.0, 10.5), _tok("there.", 10.6, 11.0)]
        cues = build_cues(toks, clip_start=10.0, clip_end=20.0, primary_speaker="p1")
        assert len(cues) == 1
        assert cues[0].start == 0.0
        assert cues[0].lines == ("Hello there.",)

    def test_tokens_outside_the_clip_are_dropped(self) -> None:
        toks = [_tok("before", 1.0, 2.0), _tok("inside", 11.0, 12.0), _tok("after", 30.0, 31.0)]
        cues = build_cues(toks, 10.0, 20.0, "p1")
        assert [c.lines for c in cues] == [("inside",)]

    def test_speaker_change_starts_a_new_cue_with_its_own_colour(self) -> None:
        toks = [
            _tok("So", 10.0, 10.2, "m1"), _tok("why?", 10.3, 10.6, "m1"),
            _tok("Because", 11.0, 11.4, "p1"), _tok("it", 11.5, 11.6, "p1"),
            _tok("broke.", 11.7, 12.0, "p1"),
        ]
        cues = build_cues(toks, 10.0, 20.0, primary_speaker="p1")
        assert [(c.speaker_code, c.colour) for c in cues] == [("m1", "yellow"), ("p1", "white")]
        assert cues[1].lines == ("Because it broke.",)

    def test_cue_never_exceeds_two_lines_or_seven_seconds(self) -> None:
        words = ("word " * 60).split()
        toks = [_tok(w, 10.0 + i * 0.4, 10.3 + i * 0.4) for i, w in enumerate(words)]
        cues = build_cues(toks, 10.0, 40.0, "p1")
        assert len(cues) > 1
        for c in cues:
            assert len(c.lines) <= 2
            assert all(len(line) <= MAX_LINE_CHARS for line in c.lines)
            assert c.end - c.start <= 7.0 + 1e-9

    def test_breaks_at_sentence_end_once_the_cue_has_substance(self) -> None:
        toks = [
            _tok("That", 0.0, 0.2), _tok("was", 0.3, 0.4), _tok("really", 0.5, 0.8),
            _tok("confusing.", 0.9, 1.3), _tok("Then", 1.5, 1.7), _tok("I", 1.8, 1.9),
            _tok("left.", 2.0, 2.3),
        ]
        cues = build_cues(toks, 0.0, 10.0, "p1")
        assert [c.lines for c in cues] == [("That was really confusing.",), ("Then I left.",)]

    def test_short_cue_is_held_for_the_minimum_without_overlapping(self) -> None:
        toks = [_tok("Yes.", 1.0, 1.2), _tok("No.", 1.5, 1.6, "m1")]
        cues = build_cues(toks, 0.0, 10.0, "p1")
        assert cues[0].end == pytest.approx(1.5)  # held, but stops at the next cue
        assert cues[1].end - cues[1].start == pytest.approx(5 / 6)

    def test_no_tokens_no_cues(self) -> None:
        assert build_cues([], 0.0, 10.0, "p1") == []


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


class TestSerialisation:
    def _cues(self) -> list:
        toks = [
            _tok("So", 1.0, 1.2, "m1"), _tok("why?", 1.3, 1.6, "m1"),
            _tok("Tom", 2.0, 2.2, "p1"), _tok("<said>", 2.3, 2.6, "p1"),
            _tok("R&D.", 2.7, 3.0, "p1"),
        ]
        return build_cues(toks, 0.0, 10.0, "p1")

    def test_webvtt(self) -> None:
        vtt = to_webvtt(self._cues())
        assert vtt.startswith("WEBVTT\n\n")
        assert "00:00:01.000 --> " in vtt
        assert "<c.yellow>So why?</c>" in vtt
        # The participant is white: no class, and markup is escaped.
        assert "\nTom &lt;said&gt; R&amp;D.\n" in vtt

    def test_webvtt_never_carries_a_speaker_code_or_name(self) -> None:
        vtt = to_webvtt(self._cues())
        assert "m1" not in vtt and "p1" not in vtt
        assert "<v" not in vtt

    def test_srt_is_plain(self) -> None:
        # Colour would be dropped by ffmpeg's mov_text encoder, so none is sent.
        srt = to_srt(self._cues())
        assert srt.startswith("1\n00:00:01,000 --> ")
        assert "\nSo why?\n" in srt
        assert "<font" not in srt
        assert "Tom ‹said› R&D." in srt

    def test_srt_backslash_cannot_become_a_line_break_or_override(self) -> None:
        cues = build_cues([_tok(r"C:\New", 0.0, 1.0), _tok(r"{\an8}top", 1.1, 2.0)],
                          0.0, 5.0, "p1")
        srt = to_srt(cues)
        assert "\\" not in srt
        assert "C:\u29f5New" in srt

    def test_zero_length_cue_is_dropped(self) -> None:
        # Two cues starting together: the first is clamped to no time at all.
        toks = [_tok("Yes.", 1.0, 1.0, "p1"), _tok("No.", 1.0, 1.5, "m1")]
        cues = build_cues(toks, 0.0, 10.0, "p1")
        assert all(c.end > c.start for c in cues)

    def test_hours_in_timestamps(self) -> None:
        cues = build_cues([_tok("late", 3725.5, 3726.0)], 0.0, 4000.0, "p1")
        assert "01:02:05.500 --> " in to_webvtt(cues)


class TestCaseFixes:
    def test_capitalisation_fix_is_applied(self) -> None:
        tokens = [_tok("we", 0.0, 0.2), _tok("use", 0.3, 0.5), _tok("ux", 0.6, 0.8),
                  _tok("tools", 0.9, 1.2)]
        corr = Correction("p1", 0.0, 2.0, original="We use ux tools",
                          corrected="We use UX tools")
        out, outcome = apply_correction(tokens, corr)
        assert outcome == APPLIED
        assert _texts(out) == ["we", "use", "UX", "tools"]
        assert (out[2].start, out[2].end) == (0.6, 0.8)

    def test_capitalisation_fix_keeps_the_transcripts_punctuation(self) -> None:
        tokens = [_tok("the", 0.0, 0.2), _tok("checkout,", 0.3, 0.8), _tok("then", 0.9, 1.0)]
        corr = Correction("p1", 0.0, 2.0, original="the checkout then",
                          corrected="the Checkout then")
        out, _ = apply_correction(tokens, corr)
        assert _texts(out) == ["the", "Checkout,", "then"]

    def test_pipeline_capitalisation_is_not_forced_onto_the_transcript(self) -> None:
        # The quote text capitalised "We" and the researcher left it: that is
        # the pipeline's tidying, not a correction, so the transcript keeps "we".
        tokens = [_tok("we", 0.0, 0.2), _tok("use", 0.3, 0.5)]
        corr = Correction("p1", 0.0, 2.0, original="We use", corrected="We use it")
        out, _ = apply_correction(tokens, corr)
        assert out[0].text == "we"


class TestRealTranscriptShapes:
    def test_label_with_brackets_inside_is_stripped_whole(self) -> None:
        # A Teams display name can carry its own brackets; stopping at the
        # first ")" left the surname on screen.
        seg = SegmentInput("p1", 0.0, 4.0, "(Robert (Bob) Smith) Yeah I use it")
        assert _texts(tokens_for_segment(seg)) == ["Yeah", "I", "use", "it"]

    def test_speaker_label_prefix_is_never_subtitled(self) -> None:
        seg = SegmentInput("p1", 0.0, 4.0, "(Sarah Jones) Well, thank you very much.")
        assert _texts(tokens_for_segment(seg))[0] == "Well,"

    def test_prefix_is_stripped_when_word_timings_exist_too(self) -> None:
        seg = SegmentInput("p1", 0.0, 4.0, "(Speaker B) Well, thanks.", _words(
            ("Well,", 0.5, 0.8), ("thanks.", 0.9, 1.3),
        ))
        toks = tokens_for_segment(seg)
        assert _texts(toks) == ["Well,", "thanks."]
        assert (toks[0].start, toks[0].end) == (0.5, 0.8)

    def test_line_break_prefers_a_clause_end(self) -> None:
        words = "I'm so glad that you're willing, to take the time to talk to me today.".split()
        lines = wrap_lines(words)
        assert lines is not None and lines[0].endswith("willing,")


# ---------------------------------------------------------------------------
# Japanese and Chinese (review log, export-clips, Finding 11)
# ---------------------------------------------------------------------------

# Real-shaped: segments from the ja-JP and zh-Hant demo projects, as the
# importer stores them (speaker label prefix, no spaces, CJK punctuation).
_JA = (
    "(Yuki) 雪が降ってて、夕方の五時半くらい。寒くて、手袋外してスマホ操作するのが"
    "嫌で、なるべく早く決めたかったんです。検索して、上位に出てきたのが、結局"
    "チェーン店ばっかりで。"
)
_ZH = (
    "(小美) 我上禮拜五下班之後想跟同事去喝一杯，可是在App上搜尋出來的全部都是"
    "連鎖店，一點都不像在地人會去的地方。後來我就直接問同事了。"
)
#: Characters that may not open a line (JLREQ cl-02..cl-07, CLREQ).
_NO_LINE_START = set("、。，．！？；：」』）】〉》ーっゃゅょッャュョァィゥェォ…")
_NO_LINE_END = set("「『（【〈《")


def _width(line: str) -> float:
    import unicodedata

    return sum(1.0 if unicodedata.east_asian_width(c) in "WF" else 0.5 for c in line)


def _cues_for(text: str, lang_speaker: str = "p1", end: float = 21.0) -> list:
    seg = SegmentInput(lang_speaker, 0.0, end, text)
    return build_cues(tokens_for_segment(seg), 0.0, end, lang_speaker)


class TestJapaneseAndChinese:
    def test_japanese_segment_is_split_into_short_cues(self) -> None:
        cues = _cues_for(_JA)
        assert len(cues) > 1
        for c in cues:
            assert len(c.lines) <= 2
            assert all(_width(line) <= 13 for line in c.lines), c.lines
            assert c.end - c.start <= 7.0 + 1e-9

    def test_chinese_segment_uses_the_chinese_line_length(self) -> None:
        # Spoken fast enough that the line length, not the 7 s cap, binds.
        cues = _cues_for(_ZH, end=12.0)
        assert len(cues) > 1
        assert all(_width(line) <= 16 for c in cues for line in c.lines)
        # 13 would be the Japanese figure: Chinese lines use the room they have.
        assert max(_width(line) for c in cues for line in c.lines) > 13

    def test_every_character_survives_and_no_space_is_inserted(self) -> None:
        for text in (_JA, _ZH):
            cues = _cues_for(text)
            assert sum(len(c.lines) for c in cues) > 2
            shown = "".join(line for c in cues for line in c.lines)
            assert shown == text.split(") ", 1)[1]

    def test_kinsoku_no_line_opens_on_closing_punctuation(self) -> None:
        for text in (_JA, _ZH):
            cues = _cues_for(text)
            assert sum(len(c.lines) for c in cues) > 2
            for c in cues:
                for line in c.lines:
                    assert line[0] not in _NO_LINE_START, line
                    assert line[-1] not in _NO_LINE_END, line

    def test_opening_bracket_stays_with_what_it_opens(self) -> None:
        text = "(Yuki) 友達に「このアプリ、地元の店が全然出てこないね」って言われました。"
        lines = [line for c in _cues_for(text, end=8.0) for line in c.lines]
        assert len(lines) > 1
        for line in lines:
            assert not line.endswith("「"), line

    def test_latin_word_inside_japanese_is_kept_whole(self) -> None:
        seg = SegmentInput("p1", 0.0, 4.0, "Figmaで作ったプロトタイプです。")
        texts = _texts(tokens_for_segment(seg))
        assert "Figma" in texts
        assert "で" in texts

    def test_half_width_letters_count_half_in_a_japanese_line(self) -> None:
        # Netflix Japanese: a half-width character counts 0.5. This is 22.5
        # units, so it fits one cue of 2 x 13; counted as 29 characters it
        # would not.
        cues = _cues_for("新しいiPhoneとMacBookのカメラはとても良いです", end=5.0)
        assert len(cues) == 1 and len(cues[0].lines) == 2
        assert all(_width(line) <= 13 for line in cues[0].lines)
        assert "iPhone" in cues[0].lines[0]

    def test_whisper_word_timings_are_used_for_japanese(self) -> None:
        # mlx-whisper times Japanese in multi-character chunks, no spaces.
        seg = SegmentInput("p1", 0.0, 10.0, "ありがとうございます。", _words(
            ("ありがとう", 1.0, 2.0), ("ございます。", 2.0, 3.0),
        ))
        toks = tokens_for_segment(seg)
        assert "".join(_texts(toks)) == "ありがとうございます。"
        assert toks[0].start == pytest.approx(1.0)
        assert toks[-1].end == pytest.approx(3.0)
        assert all(1.0 <= t.start and t.end <= 3.0 for t in toks)

    def test_researcher_correction_is_placed_in_japanese(self) -> None:
        seg = SegmentInput("p1", 0.0, 21.0, _JA)
        tokens = tokens_for_segment(seg)
        corr = Correction(
            "p1", 0.0, 21.0,
            original="寒くて、手袋外してスマホ操作するのが嫌で",
            corrected="寒くて、手袋を外してスマホを操作するのが嫌で",
        )
        out, outcome = apply_correction(tokens, corr)
        assert outcome == APPLIED
        shown = "".join(line for c in build_cues(out, 0.0, 21.0, "p1") for line in c.lines)
        assert "手袋を外してスマホを操作する" in shown
        # Words outside the quote are untouched.
        assert shown.startswith("雪が降ってて、")

    def test_latin_text_is_unchanged(self) -> None:
        words = "I thought the export would be in the share menu but it was not".split()
        lines = wrap_lines(words)
        assert lines is not None
        assert " ".join(lines) == " ".join(words)
        assert all(len(line) <= MAX_LINE_CHARS for line in lines)

    def test_no_character_or_two_is_left_alone_on_screen(self) -> None:
        # Filled to the last character that fits, these left "で。" and "ン。"
        # alone for 0.4 s (ja-JP demo, 29 Sep 2026).
        for text in (_JA, "(Yuki) なのにオススメに出るのはどこの街にもある居酒屋チェーン。"):
            for c in _cues_for(text, end=21.0 if text == _JA else 6.5):
                assert _width("".join(c.lines)) >= 13 / 3, c.lines

    def test_a_full_cue_ends_at_a_clause_rather_than_inside_a_word(self) -> None:
        firsts = ["".join(c.lines) for c in _cues_for(_JA)]
        assert "寒くて、手袋外してスマホ操作するのが嫌で、" in firsts

    def test_line_breaks_at_a_sentence_end_rather_than_inside_a_word(self) -> None:
        lines = _cues_for("(Yuki) あたりで。それでアプリを開きました。", end=3.0)[0].lines
        assert lines == ("あたりで。", "それでアプリを開きました。")
