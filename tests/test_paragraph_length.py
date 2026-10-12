"""Stage 6's reading rule: a long same-speaker run breaks at a sentence end,
and only for sessions not already paragraphed the old way."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from bristlenose.models import InputSession, TranscriptSegment
from bristlenose.pipeline import load_transcripts_from_dir
from bristlenose.stages.s06_merge_transcript import (
    PARAGRAPH_LENGTH,
    _merge_same_speaker,
    merge_transcripts,
    reading_length,
    sentence_paragraph_sessions,
    write_raw_transcripts,
    write_raw_transcripts_md,
)


def _seg(start: float, text: str, speaker: str = "Speaker B") -> TranscriptSegment:
    return TranscriptSegment(
        start_time=start, end_time=start + 4.0, text=text, speaker_label=speaker,
    )


def _sentence(n_words: int, end: str = ".") -> str:
    return " ".join(["word"] * n_words) + end


def _session(sid: str = "s1") -> InputSession:
    return InputSession(
        session_id=sid, session_number=1, participant_id="p1", participant_number=1,
        session_date=datetime(2026, 1, 1), files=[],
    )


class TestTheReadingRule:
    def test_a_long_run_breaks_at_the_next_sentence_end(self) -> None:
        segs = [_seg(0, _sentence(40)), _seg(4.5, _sentence(25)), _seg(9, _sentence(10))]
        merged = _merge_same_speaker(segs, sentence_paragraphs=True)
        assert [reading_length(m.text) for m in merged] == [65, 10]

    def test_without_a_sentence_end_it_keeps_merging(self) -> None:
        segs = [_seg(0, _sentence(40, "")), _seg(4.5, _sentence(25, ",")), _seg(9, _sentence(10))]
        assert len(_merge_same_speaker(segs, sentence_paragraphs=True)) == 1

    def test_a_short_run_stays_one_paragraph(self) -> None:
        segs = [_seg(0, _sentence(20)), _seg(4.5, _sentence(20)), _seg(9, _sentence(10))]
        assert len(_merge_same_speaker(segs, sentence_paragraphs=True)) == 1

    def test_the_old_rule_is_unchanged_without_the_flag(self) -> None:
        segs = [_seg(0, _sentence(40)), _seg(4.5, _sentence(25)), _seg(9, _sentence(10))]
        assert len(_merge_same_speaker(segs)) == 1

    def test_speaker_change_and_gap_still_break(self) -> None:
        segs = [_seg(0, "Okay."), _seg(4.5, "Yes.", speaker="Speaker A"), _seg(30, "Right.",
                                                                            speaker="Speaker A")]
        assert len(_merge_same_speaker(segs, sentence_paragraphs=True)) == 3

    def test_a_closing_quote_after_the_full_stop_is_a_sentence_end(self) -> None:
        segs = [_seg(0, _sentence(60, '."')), _seg(4.5, "Then we left.")]
        assert len(_merge_same_speaker(segs, sentence_paragraphs=True)) == 2

    def test_japanese_breaks_at_a_full_stop_after_about_150_characters(self) -> None:
        long_ja = "私は臨床心理学を習いたくて" * 12 + "。"   # 157 characters
        short_ja = "先生方がとても優しいです。"
        assert reading_length(long_ja) >= PARAGRAPH_LENGTH > reading_length(short_ja * 4)
        segs = [_seg(0, long_ja), _seg(4.5, short_ja)]
        assert len(_merge_same_speaker(segs, sentence_paragraphs=True)) == 2
        segs = [_seg(0, short_ja), _seg(4.5, short_ja)]
        assert len(_merge_same_speaker(segs, sentence_paragraphs=True)) == 1

    def test_punctuation_alone_is_not_a_word(self) -> None:
        assert reading_length("Well — you know … yes.") == 4


class TestOnlyNewSessionsGetTheRule:
    """Splits, joins and speaker moves are keyed to paragraph positions, so a
    session already written the old way must keep its paragraphs."""

    def _write(self, raw_dir: Path, sentence_paragraphs: set[str]) -> None:
        segs = {"s1": [_seg(0, _sentence(40)), _seg(4.5, _sentence(25)), _seg(9, _sentence(10))]}
        transcripts = merge_transcripts(
            [_session()], segs, sentence_paragraphs=sentence_paragraphs,
        )
        write_raw_transcripts(transcripts, raw_dir, sentence_paragraphs=sentence_paragraphs)
        write_raw_transcripts_md(transcripts, raw_dir, sentence_paragraphs=sentence_paragraphs)

    def test_a_new_session_gets_the_rule_and_the_header(self, tmp_path: Path) -> None:
        chosen = sentence_paragraph_sessions(tmp_path, ["s1"])
        assert chosen == {"s1"}
        self._write(tmp_path, chosen)
        txt = (tmp_path / "s1.txt").read_text(encoding="utf-8")
        assert "# Paragraphs: sentences" in txt
        assert "Paragraphs" in (tmp_path / "s1.md").read_text(encoding="utf-8")
        assert sentence_paragraph_sessions(tmp_path, ["s1"]) == {"s1"}

    def test_a_session_written_the_old_way_keeps_its_paragraphs(self, tmp_path: Path) -> None:
        self._write(tmp_path, set())  # what every existing project has on disk
        before = (tmp_path / "s1.txt").read_text(encoding="utf-8")

        chosen = sentence_paragraph_sessions(tmp_path, ["s1"])
        self._write(tmp_path, chosen)

        assert chosen == set()
        assert (tmp_path / "s1.txt").read_text(encoding="utf-8") == before

    def test_the_header_does_not_disturb_the_reader(self, tmp_path: Path) -> None:
        self._write(tmp_path, {"s1"})
        [transcript] = load_transcripts_from_dir(tmp_path)
        assert transcript.session_id == "s1"
        assert len(transcript.segments) == 2
        assert all("Paragraphs" not in s.text for s in transcript.segments)

    def test_a_deleted_transcript_of_an_analysed_session_is_not_new(self, tmp_path: Path) -> None:
        assert sentence_paragraph_sessions(tmp_path, ["s1", "s2"], analysed={"s1"}) == {"s2"}

    def test_the_marker_is_found_below_long_header_lines(self, tmp_path: Path) -> None:
        (tmp_path / "s1.txt").write_text(
            "# Transcript: s1\n# Source: " + "Weekly sync with the team " * 40 + ".mp4\n"
            "# Language: en (detected)\n# Paragraphs: sentences\n\n[00:00] [p1] Hello.\n",
            encoding="utf-8",
        )
        assert sentence_paragraph_sessions(tmp_path, ["s1"]) == {"s1"}

    def test_a_transcript_that_cannot_be_read_keeps_the_old_rule(self, tmp_path: Path) -> None:
        (tmp_path / "s1.txt").mkdir()  # exists, but opening it fails
        assert sentence_paragraph_sessions(tmp_path, ["s1"]) == set()

    def test_the_marker_in_speech_is_not_a_header(self, tmp_path: Path) -> None:
        (tmp_path / "s1.txt").write_text(
            "# Transcript: s1\n\n[00:00] [p1] # Paragraphs: sentences\n", encoding="utf-8",
        )
        assert sentence_paragraph_sessions(tmp_path, ["s1"]) == set()
