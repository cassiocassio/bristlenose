"""Tests for transcript file writing (.txt and .md)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from bristlenose.models import (
    FullTranscript,
    PiiCleanTranscript,
    SpeakerRole,
    TranscriptSegment,
)
from bristlenose.stages.merge_transcript import (
    write_raw_transcripts,
    write_raw_transcripts_md,
)
from bristlenose.stages.pii_removal import (
    write_cooked_transcripts,
    write_cooked_transcripts_md,
)


def _make_transcript() -> FullTranscript:
    """Build a minimal FullTranscript for testing."""
    return FullTranscript(
        participant_id="p1",
        source_file="interview_01.mp4",
        session_date=datetime(2026, 1, 10, 10, 0, 0, tzinfo=timezone.utc),
        duration_seconds=70.0,
        segments=[
            TranscriptSegment(
                start_time=0.0,
                end_time=15.0,
                text="Hi, thanks for joining us today.",
                speaker_label="Speaker A",
                speaker_role=SpeakerRole.RESEARCHER,
                source="whisper",
            ),
            TranscriptSegment(
                start_time=16.0,
                end_time=35.0,
                text="Yeah I\u2019ve been using this for about two years.",
                speaker_label="Speaker B",
                speaker_role=SpeakerRole.PARTICIPANT,
                source="whisper",
            ),
        ],
    )


def _make_cooked_transcript() -> PiiCleanTranscript:
    """Build a minimal PiiCleanTranscript for testing."""
    return PiiCleanTranscript(
        participant_id="p1",
        source_file="interview_01.mp4",
        session_date=datetime(2026, 1, 10, 10, 0, 0, tzinfo=timezone.utc),
        duration_seconds=70.0,
        pii_entities_found=2,
        segments=[
            TranscriptSegment(
                start_time=0.0,
                end_time=15.0,
                text="Hi, thanks for joining us today.",
                speaker_role=SpeakerRole.RESEARCHER,
                source="whisper",
            ),
            TranscriptSegment(
                start_time=16.0,
                end_time=35.0,
                text="[NAME] has been using this for about two years.",
                speaker_role=SpeakerRole.PARTICIPANT,
                source="whisper",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Raw markdown transcripts
# ---------------------------------------------------------------------------


def test_write_raw_transcripts_md_creates_file(tmp_path: Path) -> None:
    transcript = _make_transcript()
    paths = write_raw_transcripts_md([transcript], tmp_path)
    assert len(paths) == 1
    assert paths[0].suffix == ".md"
    assert paths[0].name == "p1_raw.md"
    assert paths[0].exists()


def test_write_raw_transcripts_md_heading(tmp_path: Path) -> None:
    transcript = _make_transcript()
    write_raw_transcripts_md([transcript], tmp_path)
    content = (tmp_path / "p1_raw.md").read_text()
    assert content.startswith("# Transcript: p1")


def test_write_raw_transcripts_md_metadata(tmp_path: Path) -> None:
    transcript = _make_transcript()
    write_raw_transcripts_md([transcript], tmp_path)
    content = (tmp_path / "p1_raw.md").read_text()
    assert "**Source:** interview_01.mp4" in content
    assert "**Date:** 2026-01-10" in content
    assert "**Duration:** 01:10" in content


def test_write_raw_transcripts_md_segments(tmp_path: Path) -> None:
    transcript = _make_transcript()
    write_raw_transcripts_md([transcript], tmp_path)
    content = (tmp_path / "p1_raw.md").read_text()
    # Bold timecode + participant code
    assert "**[00:00] p1**" in content
    assert "**[00:16] p1**" in content
    # Speaker labels in parentheses
    assert "(Speaker A)" in content
    assert "(Speaker B)" in content
    # Segment text
    assert "Hi, thanks for joining us today." in content


def test_write_raw_transcripts_md_horizontal_rule(tmp_path: Path) -> None:
    transcript = _make_transcript()
    write_raw_transcripts_md([transcript], tmp_path)
    content = (tmp_path / "p1_raw.md").read_text()
    assert "\n---\n" in content


def test_write_raw_transcripts_md_multiple(tmp_path: Path) -> None:
    t1 = _make_transcript()
    t2 = FullTranscript(
        participant_id="p2",
        source_file="interview_02.mp4",
        session_date=datetime(2026, 1, 11, 14, 0, 0, tzinfo=timezone.utc),
        duration_seconds=45.0,
        segments=[
            TranscriptSegment(
                start_time=0.0,
                end_time=10.0,
                text="Hello.",
                speaker_role=SpeakerRole.PARTICIPANT,
                source="whisper",
            ),
        ],
    )
    paths = write_raw_transcripts_md([t1, t2], tmp_path)
    assert len(paths) == 2
    assert (tmp_path / "p1_raw.md").exists()
    assert (tmp_path / "p2_raw.md").exists()


# ---------------------------------------------------------------------------
# Cooked markdown transcripts
# ---------------------------------------------------------------------------


def test_write_cooked_transcripts_md_creates_file(tmp_path: Path) -> None:
    transcript = _make_cooked_transcript()
    paths = write_cooked_transcripts_md([transcript], tmp_path)
    assert len(paths) == 1
    assert paths[0].suffix == ".md"
    assert paths[0].name == "p1_cooked.md"
    assert paths[0].exists()


def test_write_cooked_transcripts_md_heading(tmp_path: Path) -> None:
    transcript = _make_cooked_transcript()
    write_cooked_transcripts_md([transcript], tmp_path)
    content = (tmp_path / "p1_cooked.md").read_text()
    assert content.startswith("# Transcript (cooked): p1")


def test_write_cooked_transcripts_md_pii_count(tmp_path: Path) -> None:
    transcript = _make_cooked_transcript()
    write_cooked_transcripts_md([transcript], tmp_path)
    content = (tmp_path / "p1_cooked.md").read_text()
    assert "**PII entities redacted:** 2" in content


def test_write_cooked_transcripts_md_segments(tmp_path: Path) -> None:
    transcript = _make_cooked_transcript()
    write_cooked_transcripts_md([transcript], tmp_path)
    content = (tmp_path / "p1_cooked.md").read_text()
    # Bold timecode + participant code (no speaker label in cooked)
    assert "**[00:00] p1**" in content
    assert "**[00:16] p1**" in content
    # No parenthesised speaker labels
    assert "(Speaker" not in content
    # PII redaction label preserved in text
    assert "[NAME]" in content


# ---------------------------------------------------------------------------
# Raw plaintext transcripts
# ---------------------------------------------------------------------------


def test_write_raw_transcripts_txt_creates_file(tmp_path: Path) -> None:
    transcript = _make_transcript()
    paths = write_raw_transcripts([transcript], tmp_path)
    assert len(paths) == 1
    assert paths[0].suffix == ".txt"
    assert paths[0].name == "p1_raw.txt"
    assert paths[0].exists()


def test_write_raw_transcripts_txt_header(tmp_path: Path) -> None:
    transcript = _make_transcript()
    write_raw_transcripts([transcript], tmp_path)
    content = (tmp_path / "p1_raw.txt").read_text()
    assert "# Transcript: p1" in content
    assert "# Source: interview_01.mp4" in content
    assert "# Date: 2026-01-10" in content
    assert "# Duration: 01:10" in content


def test_write_raw_transcripts_txt_participant_codes(tmp_path: Path) -> None:
    transcript = _make_transcript()
    write_raw_transcripts([transcript], tmp_path)
    content = (tmp_path / "p1_raw.txt").read_text()
    # Participant code in brackets, not role label
    assert "[00:00] [p1]" in content
    assert "[00:16] [p1]" in content
    # Should NOT contain role labels like [RESEARCHER] or [PARTICIPANT]
    assert "[RESEARCHER]" not in content
    assert "[PARTICIPANT]" not in content


def test_write_raw_transcripts_txt_speaker_labels(tmp_path: Path) -> None:
    transcript = _make_transcript()
    write_raw_transcripts([transcript], tmp_path)
    content = (tmp_path / "p1_raw.txt").read_text()
    # Speaker labels in parentheses
    assert "(Speaker A)" in content
    assert "(Speaker B)" in content


def test_write_raw_transcripts_txt_segment_text(tmp_path: Path) -> None:
    transcript = _make_transcript()
    write_raw_transcripts([transcript], tmp_path)
    content = (tmp_path / "p1_raw.txt").read_text()
    assert "Hi, thanks for joining us today." in content
    assert "Yeah I\u2019ve been using this for about two years." in content


# ---------------------------------------------------------------------------
# Cooked plaintext transcripts
# ---------------------------------------------------------------------------


def test_write_cooked_transcripts_txt_creates_file(tmp_path: Path) -> None:
    transcript = _make_cooked_transcript()
    paths = write_cooked_transcripts([transcript], tmp_path)
    assert len(paths) == 1
    assert paths[0].suffix == ".txt"
    assert paths[0].name == "p1_cooked.txt"
    assert paths[0].exists()


def test_write_cooked_transcripts_txt_header(tmp_path: Path) -> None:
    transcript = _make_cooked_transcript()
    write_cooked_transcripts([transcript], tmp_path)
    content = (tmp_path / "p1_cooked.txt").read_text()
    assert "# Transcript (cooked): p1" in content
    assert "# PII entities redacted: 2" in content


def test_write_cooked_transcripts_txt_participant_codes(tmp_path: Path) -> None:
    transcript = _make_cooked_transcript()
    write_cooked_transcripts([transcript], tmp_path)
    content = (tmp_path / "p1_cooked.txt").read_text()
    # Participant code in brackets, not role label
    assert "[00:00] [p1]" in content
    assert "[00:16] [p1]" in content
    # Should NOT contain role labels
    assert "[RESEARCHER]" not in content
    assert "[PARTICIPANT]" not in content


def test_write_cooked_transcripts_txt_pii_text(tmp_path: Path) -> None:
    transcript = _make_cooked_transcript()
    write_cooked_transcripts([transcript], tmp_path)
    content = (tmp_path / "p1_cooked.txt").read_text()
    assert "[NAME] has been using this for about two years." in content


# ---------------------------------------------------------------------------
# Transcript parser (round-trip: write → load)
# ---------------------------------------------------------------------------


def test_parser_reads_participant_code_format(tmp_path: Path) -> None:
    """Parser loads .txt files that use participant codes [p1]."""
    from bristlenose.pipeline import _load_transcripts_from_dir

    transcript = _make_cooked_transcript()
    write_cooked_transcripts([transcript], tmp_path)
    loaded = _load_transcripts_from_dir(tmp_path)
    assert len(loaded) == 1
    assert loaded[0].participant_id == "p1"
    assert len(loaded[0].segments) == 2
    assert loaded[0].segments[0].text == "Hi, thanks for joining us today."
    assert "[NAME]" in loaded[0].segments[1].text


def test_parser_reads_legacy_role_format(tmp_path: Path) -> None:
    """Parser loads legacy .txt files that use role labels [PARTICIPANT]."""
    from bristlenose.pipeline import _load_transcripts_from_dir

    # Write a legacy-format file manually
    legacy = (
        "# Transcript: p3\n"
        "# Source: interview_03.mp4\n"
        "# Date: 2026-01-15\n"
        "# Duration: 00:01:00\n"
        "\n"
        "[00:00:00] [RESEARCHER] Welcome to the session.\n"
        "\n"
        "[00:00:15] [PARTICIPANT] Thanks for having me.\n"
    )
    (tmp_path / "p3_cooked.txt").write_text(legacy, encoding="utf-8")
    loaded = _load_transcripts_from_dir(tmp_path)
    assert len(loaded) == 1
    assert loaded[0].participant_id == "p3"
    assert len(loaded[0].segments) == 2
    assert loaded[0].segments[0].text == "Welcome to the session."
    assert loaded[0].segments[1].text == "Thanks for having me."


def test_parser_extracts_metadata(tmp_path: Path) -> None:
    """Parser correctly reads header metadata from .txt files."""
    from bristlenose.pipeline import _load_transcripts_from_dir

    transcript = _make_cooked_transcript()
    write_cooked_transcripts([transcript], tmp_path)
    loaded = _load_transcripts_from_dir(tmp_path)
    assert loaded[0].source_file == "interview_01.mp4"
