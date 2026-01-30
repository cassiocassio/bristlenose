"""Shared test fixtures for Bristlenose tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from bristlenose.models import (
    ExtractedQuote,
    FileType,
    FullTranscript,
    InputFile,
    InputSession,
    QuoteType,
    SpeakerRole,
    TranscriptSegment,
)


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for test outputs."""
    return tmp_path


@pytest.fixture
def sample_session() -> InputSession:
    """Create a sample InputSession for testing."""
    return InputSession(
        participant_id="p1",
        participant_number=1,
        files=[
            InputFile(
                path=Path("/tmp/interview_01.mp4"),
                file_type=FileType.VIDEO,
                created_at=datetime(2026, 1, 10, 10, 0, 0, tzinfo=timezone.utc),
                size_bytes=100_000_000,
                duration_seconds=2700.0,
            )
        ],
        session_date=datetime(2026, 1, 10, 10, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_segments() -> list[TranscriptSegment]:
    """Create sample transcript segments with mixed speaker roles."""
    return [
        TranscriptSegment(
            start_time=0.0,
            end_time=15.0,
            text="Hi, thanks for joining us today. I'm going to show you a few screens and I'd like you to tell me what you think.",
            speaker_label="Speaker A",
            speaker_role=SpeakerRole.RESEARCHER,
            source="whisper",
        ),
        TranscriptSegment(
            start_time=16.0,
            end_time=35.0,
            text="Yeah sure, um, so I've been using this kind of tool for about two years now, you know, and it's like, honestly a bit of a nightmare sometimes.",
            speaker_label="Speaker B",
            speaker_role=SpeakerRole.PARTICIPANT,
            source="whisper",
        ),
        TranscriptSegment(
            start_time=36.0,
            end_time=42.0,
            text="Can you tell me more about what makes it a nightmare?",
            speaker_label="Speaker A",
            speaker_role=SpeakerRole.RESEARCHER,
            source="whisper",
        ),
        TranscriptSegment(
            start_time=43.0,
            end_time=70.0,
            text="Well the thing is like, you know, every morning I have to open three different apps just to figure out what I'm supposed to be working on. It's ridiculous.",
            speaker_label="Speaker B",
            speaker_role=SpeakerRole.PARTICIPANT,
            source="whisper",
        ),
    ]


@pytest.fixture
def sample_transcript(sample_segments: list[TranscriptSegment]) -> FullTranscript:
    """Create a sample FullTranscript for testing."""
    return FullTranscript(
        participant_id="p1",
        source_file="interview_01.mp4",
        session_date=datetime(2026, 1, 10, 10, 0, 0, tzinfo=timezone.utc),
        duration_seconds=70.0,
        segments=sample_segments,
    )


@pytest.fixture
def sample_quotes() -> list[ExtractedQuote]:
    """Create sample extracted quotes for testing."""
    return [
        ExtractedQuote(
            participant_id="p1",
            start_timecode=16.0,
            end_timecode=35.0,
            text="I\u2019ve been using this kind of tool for about two years now... and it\u2019s honestly a bit of a nightmare sometimes.",
            topic_label="General context",
            quote_type=QuoteType.GENERAL_CONTEXT,
        ),
        ExtractedQuote(
            participant_id="p1",
            start_timecode=43.0,
            end_timecode=70.0,
            text="Every morning I have to open three different apps just to figure out what I\u2019m supposed to be working on. It\u2019s ridiculous.",
            topic_label="Daily workflow",
            quote_type=QuoteType.GENERAL_CONTEXT,
            researcher_context="When asked about what makes it a nightmare",
        ),
    ]
