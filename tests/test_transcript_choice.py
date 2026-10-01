"""0d — one transcript per session.

A session can arrive with several transcript files: Teams' ``.vtt`` and its
``.docx`` for the same meeting (measured: every turn twice), or a cloud
transcript beside a hand-dropped one. Exactly one is used. The others are
superseded, and supersession is **stated** — a log line and a CLI warning
naming both files — never a silent drop.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bristlenose.models import FileType, InputFile, InputSession, TranscriptSegment
from bristlenose.stages.s03_parse_subtitles import CLOUD_TRANSCRIPT_SOURCE
from bristlenose.stages.transcript_choice import (
    ParsedTranscriptFile,
    choose_transcript,
)

_T0 = datetime(2026, 9, 24, 10, 0, tzinfo=timezone.utc)


def _file(name: str, file_type: FileType) -> InputFile:
    return InputFile(path=Path("/input") / name, file_type=file_type, created_at=_T0, size_bytes=1)


def _segs(
    source: str, labels: list[str | None], *, step: float = 10.0, start: float = 0.0
) -> list[TranscriptSegment]:
    out = []
    t = start
    for label in labels:
        out.append(
            TranscriptSegment(
                start_time=t, end_time=t + step - 1, text="words", speaker_label=label,
                source=source,
            )
        )
        t += step
    return out


def _vtt(name: str, labels: list[str | None], **kw) -> ParsedTranscriptFile:
    return ParsedTranscriptFile(_file(name, FileType.SUBTITLE_VTT), _segs("vtt", labels, **kw))


def _cloud(name: str, labels: list[str | None], **kw) -> ParsedTranscriptFile:
    return ParsedTranscriptFile(
        _file(name, FileType.SUBTITLE_VTT), _segs(CLOUD_TRANSCRIPT_SOURCE, labels, **kw)
    )


def _docx(name: str, labels: list[str | None], **kw) -> ParsedTranscriptFile:
    return ParsedTranscriptFile(_file(name, FileType.DOCX), _segs("docx", labels, **kw))


def _srt(name: str, labels: list[str | None], **kw) -> ParsedTranscriptFile:
    return ParsedTranscriptFile(_file(name, FileType.SUBTITLE_SRT), _segs("srt", labels, **kw))


class TestChooseTranscript:
    def test_single_candidate_is_chosen_with_nothing_superseded(self) -> None:
        only = _vtt("a.vtt", ["Ana", "Bruno"])
        chosen, superseded = choose_transcript([only])
        assert chosen is only
        assert superseded == []

    def test_named_beats_unnamed_whatever_the_format(self) -> None:
        """A hand-dropped .docx with real names beats a cloud VTT without."""
        unnamed_cloud = _cloud("meeting.vtt", [None] * 20)
        named_docx = _docx("meeting.docx", ["Ana", "Bruno"] * 10)
        chosen, superseded = choose_transcript([unnamed_cloud, named_docx])
        assert chosen is named_docx
        assert superseded == [unnamed_cloud]

    def test_generic_labels_do_not_count_as_names(self) -> None:
        speaker_1 = _vtt("captions.vtt", ["Speaker 1", "Speaker 2"] * 10)
        named_docx = _docx("meeting.docx", ["Ana", "Bruno"] * 10)
        chosen, _ = choose_transcript([speaker_1, named_docx])
        assert chosen is named_docx

    def test_coverage_beats_format_when_the_difference_is_real(self) -> None:
        """A VTT covering 10 minutes loses to a DOCX covering the whole hour."""
        short_vtt = _vtt("a.vtt", ["Ana", "Bruno"] * 3, step=100.0)  # ~10 min
        long_docx = _docx("a.docx", ["Ana", "Bruno"] * 18, step=100.0)  # ~1 h
        chosen, _ = choose_transcript([short_vtt, long_docx])
        assert chosen is long_docx

    def test_near_equal_coverage_falls_through_to_format(self) -> None:
        """Teams' .vtt and .docx of one meeting end a few seconds apart; that is
        the same coverage, and the VTT (timed cues) wins on format."""
        vtt = _vtt("a.vtt", ["Ana", "Bruno"] * 10, step=60.0)
        docx = _docx("a.docx", ["Ana", "Bruno"] * 10, step=60.0, start=3.0)
        chosen, superseded = choose_transcript([docx, vtt])
        assert chosen is vtt
        assert superseded == [docx]

    def test_cloud_vtt_beats_vendor_subtitles_beat_docx(self) -> None:
        """Cloud VTT > VTT/SRT > DOCX. VTT and SRT are one tier (both timed
        cues); among equals the caller's order decides, so a tie is stable."""
        labels: list[str | None] = ["Ana", "Bruno"] * 10
        cloud = _cloud("a.vtt", labels)
        vendor = _vtt("a (teams).vtt", labels)
        srt = _srt("a.srt", labels)
        docx = _docx("a.docx", labels)
        chosen, superseded = choose_transcript([docx, srt, vendor, cloud])
        assert chosen is cloud
        assert set(map(id, superseded)) == {id(docx), id(srt), id(vendor)}
        chosen, _ = choose_transcript([docx, srt, vendor])
        assert chosen is srt
        chosen, _ = choose_transcript([docx, vendor, srt])
        assert chosen is vendor
        chosen, _ = choose_transcript([docx, srt])
        assert chosen is srt

    def test_empty_candidates_are_never_chosen(self) -> None:
        empty = _vtt("a.vtt", [])
        docx = _docx("a.docx", ["Ana"])
        chosen, superseded = choose_transcript([empty, docx])
        assert chosen is docx
        assert superseded == [empty]

    def test_no_candidates_raises(self) -> None:
        with pytest.raises(ValueError):
            choose_transcript([])


# ── Through the pipeline seam ───────────────────────────────────────────────


class TestGatherUsesOneTranscript:
    """``Pipeline._gather_all_segments`` is where both files of a Teams pair
    used to be concatenated. Real files, real parsers, no Whisper."""

    def _vtt_file(self, tmp_path: Path, name: str, cues: list[tuple[str, str]]) -> InputFile:
        lines = ["WEBVTT", ""]
        t = 0
        for speaker, text in cues:
            lines.append(f"00:00:{t:02d}.000 --> 00:00:{t + 4:02d}.000")
            lines.append(f"<v {speaker}>{text}</v>")
            lines.append("")
            t += 5
        path = tmp_path / name
        path.write_text("\n".join(lines), encoding="utf-8")
        return InputFile(
            path=path, file_type=FileType.SUBTITLE_VTT, created_at=_T0,
            size_bytes=path.stat().st_size,
        )

    def _docx_file(self, tmp_path: Path, name: str, turns: list[tuple[str, str]]) -> InputFile:
        from docx import Document

        doc = Document()
        t = 0
        for speaker, text in turns:
            # Teams packs header and speech into one paragraph with a line break.
            doc.add_paragraph(f"{speaker}   0:{t:02d}\n{text}")
            t += 5
        path = tmp_path / name
        doc.save(str(path))
        return InputFile(
            path=path, file_type=FileType.DOCX, created_at=_T0, size_bytes=path.stat().st_size,
        )

    def _gather(self, files: list[InputFile]):
        from bristlenose.config import BristlenoseSettings
        from bristlenose.pipeline import Pipeline

        session = InputSession(
            session_id="s1", session_number=1, participant_id="p1", participant_number=1,
            files=files, has_existing_transcript=True, session_date=_T0,
        )
        pipeline = Pipeline(BristlenoseSettings(skip_transcription=True))
        return asyncio.run(pipeline._gather_all_segments([session]))

    def test_vtt_plus_docx_gives_each_turn_once(self, tmp_path: Path, caplog) -> None:
        turns = [("Ana Souza", "Shall we start?"), ("Bruno Lima", "Yes please.")] * 3
        vtt = self._vtt_file(tmp_path, "Meeting.vtt", turns)
        docx = self._docx_file(tmp_path, "Meeting.docx", turns)
        with caplog.at_level("WARNING", logger="bristlenose.pipeline"):
            segments, outcome = self._gather([vtt, docx])

        texts = [s.text for s in segments["s1"]]
        assert texts.count("Shall we start?") == 3, "every turn exactly once"
        assert {s.source for s in segments["s1"]} == {"vtt"}
        assert outcome.attempted == 1 and outcome.succeeded == 1
        assert outcome.failed == []

    def test_supersession_is_stated(self, tmp_path: Path, caplog) -> None:
        turns = [("Ana Souza", "Shall we start?"), ("Bruno Lima", "Yes please.")]
        vtt = self._vtt_file(tmp_path, "Meeting.vtt", turns)
        docx = self._docx_file(tmp_path, "Meeting.docx", turns)
        with caplog.at_level("WARNING", logger="bristlenose.pipeline"):
            self._gather([vtt, docx])
        stated = [r.getMessage() for r in caplog.records if "superseded" in r.getMessage()]
        assert stated, "a superseded transcript must be stated, not dropped"
        assert "Meeting.docx" in stated[0] and "Meeting.vtt" in stated[0]

    def test_a_failed_file_beside_a_good_one_is_still_recorded(self, tmp_path: Path) -> None:
        turns = [("Ana Souza", "Shall we start?"), ("Bruno Lima", "Yes please.")]
        vtt = self._vtt_file(tmp_path, "Meeting.vtt", turns)
        bad = tmp_path / "Meeting.docx"
        bad.write_bytes(b"not a docx")
        bad_file = InputFile(
            path=bad, file_type=FileType.DOCX, created_at=_T0, size_bytes=bad.stat().st_size,
        )
        segments, outcome = self._gather([vtt, bad_file])
        assert "s1" in segments
        assert outcome.succeeded == 1
        assert [f.source_file for f in outcome.failed] == ["Meeting.docx"]
