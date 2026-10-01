"""Stage 3 subtitle parsing — the cloud-transcript NOTE, voice tags, escapes.

The three ``cloud-transcript-*.vtt`` fixtures are the pipeline half of the
golden-file contract in ``docs/design-cloud-import-transcripts.md`` §4: the
Swift writer must produce these bytes, and this module must read them. A
change to either side that the other does not follow fails here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bristlenose.models import FileType, InputFile, TranscriptSegment
from bristlenose.stages.s03_parse_subtitles import (
    CLOUD_TRANSCRIPT_SOURCE,
    CloudTranscriptVersionError,
    parse_subtitle_file,
    read_cloud_transcript_note,
)

FIXTURES = Path(__file__).parent / "fixtures" / "platform-transcripts"


def _input_file(path: Path) -> InputFile:
    from datetime import datetime, timezone

    return InputFile(
        path=path,
        file_type=FileType.SUBTITLE_VTT,
        created_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
        size_bytes=path.stat().st_size,
    )


def _write_vtt(tmp_path: Path, body: str, name: str = "t.vtt") -> InputFile:
    path = tmp_path / name
    path.write_text("WEBVTT\n\n" + body, encoding="utf-8")
    return _input_file(path)


def _parse(path: Path) -> list[TranscriptSegment]:
    return parse_subtitle_file(_input_file(path))


# ═══════════════════════════════════════════════════════════════════════════
# The golden files
# ═══════════════════════════════════════════════════════════════════════════


class TestGoldenNamed:
    PATH = FIXTURES / "cloud-transcript-named.vtt"

    def test_note_is_read(self) -> None:
        note = read_cloud_transcript_note(self.PATH)
        assert note is not None
        assert note.version == "1"
        assert note.source == "meet"
        assert note.speakers == "named"
        assert note.language == "pt-BR"
        assert note.media == "2026-09-24 0934 — P07 Interview.mp4"
        assert note.media_duration == pytest.approx(3131.42)
        assert note.rebased_by == pytest.approx(0.0)
        assert note.dropped_outside_media == 0

    def test_every_turn_carries_the_platform_name(self) -> None:
        segments = _parse(self.PATH)
        assert len(segments) == 5
        assert [s.speaker_label for s in segments] == [
            "Ana Souza", "Bruno Lima", "Ana Souza", "Bruno Lima", "Ana Souza",
        ]

    def test_segments_are_marked_as_cloud_transcript(self) -> None:
        segments = _parse(self.PATH)
        assert {s.source for s in segments} == {CLOUD_TRANSCRIPT_SOURCE}

    def test_text_is_unescaped(self) -> None:
        texts = [s.text for s in _parse(self.PATH)]
        assert "Ponte & Filhos" in texts[1]
        assert "<Pagamentos>" in texts[2]

    def test_colon_heuristic_is_off_for_a_cloud_transcript(self) -> None:
        """``Honestamente: nada`` is speech by Bruno, not a speaker called
        Honestamente — the writer's ``<v>`` is the only speaker signal."""
        seg = _parse(self.PATH)[3]
        assert seg.speaker_label == "Bruno Lima"
        assert seg.text.startswith("Honestamente: nada")

    def test_times_are_the_writers_times(self) -> None:
        segments = _parse(self.PATH)
        assert segments[0].start_time == pytest.approx(0.0)
        assert segments[1].start_time == pytest.approx(3.9)
        assert all(s.end_time > s.start_time for s in segments)


class TestGoldenUnnamed:
    PATH = FIXTURES / "cloud-transcript-unnamed.vtt"

    def test_note_says_speakers_none(self) -> None:
        note = read_cloud_transcript_note(self.PATH)
        assert note is not None
        assert note.speakers == "none"
        assert note.source == "teams"
        assert note.language == "en-GB"

    def test_no_speaker_is_invented(self) -> None:
        """No ``<v>`` means no label at all — never a made-up "Speaker 1", and
        never a colon-word promoted to a name."""
        segments = _parse(self.PATH)
        assert len(segments) == 4
        assert all(s.speaker_label is None for s in segments)
        assert segments[1].text.startswith("Note: the prototype")
        assert segments[2].text.startswith("Honestly: I never")


class TestGoldenRebasedWithDrops:
    PATH = FIXTURES / "cloud-transcript-rebased-drops.vtt"

    def test_note_records_the_rebase_and_the_drops(self) -> None:
        note = read_cloud_transcript_note(self.PATH)
        assert note is not None
        assert note.rebased_by == pytest.approx(-12.4)
        assert note.dropped_outside_media == 3
        assert note.media_duration == pytest.approx(2410.5)
        assert note.language == "de"

    def test_cues_start_at_the_media_clock(self) -> None:
        segments = _parse(self.PATH)
        assert segments[0].start_time == pytest.approx(0.0)
        assert all(s.end_time > s.start_time for s in segments)
        assert segments[-1].end_time <= 2410.5

    def test_non_ascii_names_survive(self) -> None:
        labels = {s.speaker_label for s in _parse(self.PATH)}
        assert labels == {"Jürgen Müller", "Işık Barış"}


# ═══════════════════════════════════════════════════════════════════════════
# The NOTE block's grammar
# ═══════════════════════════════════════════════════════════════════════════


class TestNoteGrammar:
    def test_plain_vendor_vtt_has_no_note(self, tmp_path: Path) -> None:
        f = _write_vtt(tmp_path, "00:00:01.000 --> 00:00:02.000\n<v Sam>Hi</v>\n")
        assert read_cloud_transcript_note(f.path) is None
        segs = parse_subtitle_file(f)
        assert segs[0].source == "vtt"

    def test_an_unrelated_note_is_not_ours(self, tmp_path: Path) -> None:
        f = _write_vtt(
            tmp_path,
            "NOTE exported from somewhere else\n\n"
            "00:00:01.000 --> 00:00:02.000\n<v Sam>Hi</v>\n",
        )
        assert read_cloud_transcript_note(f.path) is None
        assert parse_subtitle_file(f)[0].source == "vtt"

    def test_minor_version_is_accepted(self, tmp_path: Path) -> None:
        """A later ``1.x`` writer adds fields; a ``1`` reader ignores them."""
        f = _write_vtt(
            tmp_path,
            "NOTE bristlenose-cloud-transcript 1.3\nsource: meet\nspeakers: named\n"
            "future-field: whatever\n\n"
            "00:00:01.000 --> 00:00:02.000\n<v Sam>Hi</v>\n",
        )
        note = read_cloud_transcript_note(f.path)
        assert note is not None
        assert note.version == "1.3"
        assert note.source == "meet"
        assert note.language is None
        assert note.media_duration is None
        assert parse_subtitle_file(f)[0].speaker_label == "Sam"

    def test_unknown_major_version_is_refused_loudly(self, tmp_path: Path) -> None:
        f = _write_vtt(
            tmp_path,
            "NOTE bristlenose-cloud-transcript 2\nsource: meet\nspeakers: named\n\n"
            "00:00:01.000 --> 00:00:02.000\n<v Sam>Hi</v>\n",
        )
        with pytest.raises(CloudTranscriptVersionError):
            read_cloud_transcript_note(f.path)
        with pytest.raises(CloudTranscriptVersionError):
            parse_subtitle_file(f)

    def test_values_are_unescaped(self, tmp_path: Path) -> None:
        f = _write_vtt(
            tmp_path,
            "NOTE bristlenose-cloud-transcript 1\nsource: teams\nspeakers: named\n"
            "media: R&amp;D sync &lt;final&gt;.mp4\n\n"
            "00:00:01.000 --> 00:00:02.000\n<v Sam>Hi</v>\n",
        )
        note = read_cloud_transcript_note(f.path)
        assert note is not None
        assert note.media == "R&D sync <final>.mp4"


# ═══════════════════════════════════════════════════════════════════════════
# Voice tags on vendor files (Teams writes these itself)
# ═══════════════════════════════════════════════════════════════════════════


class TestVoiceTags:
    def test_two_voices_in_one_cue_become_two_segments(self, tmp_path: Path) -> None:
        """Measured on Teams: a two-voice cue used to hand the whole cue to the
        first voice. Each voice gets its own segment and a share of the time."""
        f = _write_vtt(
            tmp_path,
            "00:00:10.000 --> 00:00:14.000\n"
            "<v Ana Souza>Shall we start?</v><v Bruno Lima>Yes, go ahead please.</v>\n",
        )
        segs = parse_subtitle_file(f)
        assert [s.speaker_label for s in segs] == ["Ana Souza", "Bruno Lima"]
        assert [s.text for s in segs] == ["Shall we start?", "Yes, go ahead please."]
        assert segs[0].start_time == pytest.approx(10.0)
        assert segs[1].end_time == pytest.approx(14.0)
        assert segs[0].end_time == pytest.approx(segs[1].start_time)
        assert segs[0].end_time > segs[0].start_time
        assert segs[1].end_time > segs[1].start_time
        # The second speaker said more, so gets more of the cue.
        assert (segs[1].end_time - segs[1].start_time) > (
            segs[0].end_time - segs[0].start_time
        )

    def test_name_and_text_are_html_unescaped(self, tmp_path: Path) -> None:
        f = _write_vtt(
            tmp_path,
            "00:00:01.000 --> 00:00:02.000\n"
            "<v Smith &amp; Jones>It said &quot;error&quot; &lt;twice&gt;</v>\n",
        )
        seg = parse_subtitle_file(f)[0]
        assert seg.speaker_label == "Smith & Jones"
        assert seg.text == 'It said "error" <twice>'

    def test_unclosed_voice_tag_still_one_segment(self, tmp_path: Path) -> None:
        f = _write_vtt(
            tmp_path,
            "00:00:01.000 --> 00:00:02.000\n<v Sam>Hello everyone\n",
        )
        segs = parse_subtitle_file(f)
        assert len(segs) == 1
        assert segs[0].speaker_label == "Sam"
        assert segs[0].text == "Hello everyone"

    def test_empty_voice_is_dropped(self, tmp_path: Path) -> None:
        f = _write_vtt(
            tmp_path,
            "00:00:01.000 --> 00:00:02.000\n<v Sam></v><v Pat>Hi</v>\n",
        )
        segs = parse_subtitle_file(f)
        assert [s.speaker_label for s in segs] == ["Pat"]

    def test_colon_heuristic_still_applies_to_a_vendor_cue(self, tmp_path: Path) -> None:
        """Zoom's ``Name: text`` files have no ``<v>``; the heuristic is for them."""
        f = _write_vtt(
            tmp_path,
            "00:00:01.000 --> 00:00:02.000\nSanjay Gupta, WUD: Good afternoon\n",
        )
        seg = parse_subtitle_file(f)[0]
        assert seg.speaker_label == "Sanjay Gupta, WUD"
        assert seg.text == "Good afternoon"
