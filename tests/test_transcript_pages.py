"""Tests for per-participant HTML transcript pages."""

from __future__ import annotations

from pathlib import Path

from bristlenose.models import (
    PeopleFile,
    PersonComputed,
    PersonEditable,
    PersonEntry,
)
from bristlenose.stages.render_html import (
    _resolve_speaker_name,
    render_transcript_pages,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RAW_TRANSCRIPT_P1 = """\
# Transcript: p1
# Source: interview_01.mp4
# Date: 2026-01-20
# Duration: 00:05:00

[00:16] [p1] Yeah I've been using this for a while.

[00:42] [p1] Can you tell me more about that feature?

[01:10] [p1] It was really confusing at first.
"""


def _write_raw_transcripts(output_dir: Path) -> None:
    """Write a minimal raw transcript to disk."""
    raw_dir = output_dir / "raw_transcripts"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "p1_raw.txt").write_text(_RAW_TRANSCRIPT_P1, encoding="utf-8")


def _make_people() -> PeopleFile:
    """Build a minimal PeopleFile with one participant."""
    from datetime import datetime, timezone

    return PeopleFile(
        last_updated=datetime.now(tz=timezone.utc),
        participants={
            "p1": PersonEntry(
                computed=PersonComputed(
                    participant_id="p1",
                    session_date=datetime(2026, 1, 20, tzinfo=timezone.utc),
                    duration_seconds=300.0,
                    words_spoken=42,
                    pct_words=100.0,
                    pct_time_speaking=80.0,
                    source_file="interview_01.mp4",
                ),
                editable=PersonEditable(
                    full_name="Sarah Jones",
                    short_name="Sarah",
                    role="Product Manager",
                ),
            ),
        },
    )


# ---------------------------------------------------------------------------
# _resolve_speaker_name
# ---------------------------------------------------------------------------


def test_resolve_speaker_name_short_name() -> None:
    people = _make_people()
    assert _resolve_speaker_name("p1", people, None) == "Sarah"


def test_resolve_speaker_name_full_name_fallback() -> None:
    people = _make_people()
    people.participants["p1"].editable.short_name = ""
    assert _resolve_speaker_name("p1", people, None) == "Sarah Jones"


def test_resolve_speaker_name_pid_fallback() -> None:
    people = _make_people()
    people.participants["p1"].editable.short_name = ""
    people.participants["p1"].editable.full_name = ""
    assert _resolve_speaker_name("p1", people, None) == "p1"


def test_resolve_speaker_name_no_people() -> None:
    assert _resolve_speaker_name("p1", None, None) == "p1"


# ---------------------------------------------------------------------------
# Transcript page generation
# ---------------------------------------------------------------------------


def test_transcript_page_generated(tmp_path: Path) -> None:
    _write_raw_transcripts(tmp_path)
    paths = render_transcript_pages(
        sessions=[], project_name="Test Project", output_dir=tmp_path,
    )
    assert len(paths) == 1
    assert paths[0].name == "transcript_p1.html"
    assert paths[0].exists()


def test_transcript_page_back_button(tmp_path: Path) -> None:
    _write_raw_transcripts(tmp_path)
    render_transcript_pages(
        sessions=[], project_name="Test Project", output_dir=tmp_path,
    )
    html = (tmp_path / "transcript_p1.html").read_text(encoding="utf-8")
    assert 'href="research_report.html"' in html
    assert "&larr; Test Project Research Report" in html


def test_transcript_page_heading_with_name(tmp_path: Path) -> None:
    _write_raw_transcripts(tmp_path)
    people = _make_people()
    render_transcript_pages(
        sessions=[], project_name="Test Project", output_dir=tmp_path,
        people=people,
    )
    html = (tmp_path / "transcript_p1.html").read_text(encoding="utf-8")
    assert '<h1 data-participant="p1">p1 Sarah Jones</h1>' in html


def test_transcript_page_heading_without_name(tmp_path: Path) -> None:
    _write_raw_transcripts(tmp_path)
    render_transcript_pages(
        sessions=[], project_name="Test Project", output_dir=tmp_path,
    )
    html = (tmp_path / "transcript_p1.html").read_text(encoding="utf-8")
    assert '<h1 data-participant="p1">p1</h1>' in html


def test_transcript_page_timecodes_without_media(tmp_path: Path) -> None:
    _write_raw_transcripts(tmp_path)
    render_transcript_pages(
        sessions=[], project_name="Test Project", output_dir=tmp_path,
    )
    html = (tmp_path / "transcript_p1.html").read_text(encoding="utf-8")
    # Without media, timecodes should be spans, not links
    assert '<span class="timecode"><span class="timecode-bracket">[</span>00:16<span class="timecode-bracket">]</span></span>' in html


def test_transcript_page_timecodes_with_media(tmp_path: Path) -> None:
    _write_raw_transcripts(tmp_path)
    video_map = {"p1": "file:///path/to/interview_01.mp4"}
    render_transcript_pages(
        sessions=[], project_name="Test Project", output_dir=tmp_path,
        video_map=video_map,
    )
    html = (tmp_path / "transcript_p1.html").read_text(encoding="utf-8")
    assert 'class="timecode"' in html
    assert 'data-participant="p1"' in html
    assert 'data-seconds="16.0"' in html


def test_transcript_page_speaker_name(tmp_path: Path) -> None:
    _write_raw_transcripts(tmp_path)
    people = _make_people()
    render_transcript_pages(
        sessions=[], project_name="Test Project", output_dir=tmp_path,
        people=people,
    )
    html = (tmp_path / "transcript_p1.html").read_text(encoding="utf-8")
    # short_name should be used as speaker label
    assert "Sarah:" in html


def test_transcript_page_segment_text(tmp_path: Path) -> None:
    _write_raw_transcripts(tmp_path)
    render_transcript_pages(
        sessions=[], project_name="Test Project", output_dir=tmp_path,
    )
    html = (tmp_path / "transcript_p1.html").read_text(encoding="utf-8")
    assert "Yeah I&#x27;ve been using this for a while." in html


def test_transcript_page_color_scheme(tmp_path: Path) -> None:
    _write_raw_transcripts(tmp_path)
    render_transcript_pages(
        sessions=[], project_name="Test", output_dir=tmp_path,
        color_scheme="dark",
    )
    html = (tmp_path / "transcript_p1.html").read_text(encoding="utf-8")
    assert 'data-theme="dark"' in html


def test_transcript_page_prefers_cooked(tmp_path: Path) -> None:
    """When both raw and cooked transcripts exist, prefer cooked."""
    _write_raw_transcripts(tmp_path)
    # Also write a cooked transcript with different text
    cooked_dir = tmp_path / "cooked_transcripts"
    cooked_dir.mkdir(parents=True, exist_ok=True)
    (cooked_dir / "p1_cooked.txt").write_text(
        "# Transcript (cooked): p1\n"
        "# Source: interview_01.mp4\n"
        "# Date: 2026-01-20\n"
        "# Duration: 00:05:00\n\n"
        "[00:16] [p1] [NAME] has been using this for a while.\n",
        encoding="utf-8",
    )
    render_transcript_pages(
        sessions=[], project_name="Test", output_dir=tmp_path,
    )
    html = (tmp_path / "transcript_p1.html").read_text(encoding="utf-8")
    assert "[NAME]" in html
    assert "Yeah" not in html


def test_transcript_page_no_transcripts(tmp_path: Path) -> None:
    """When no transcript directories exist, return empty list."""
    paths = render_transcript_pages(
        sessions=[], project_name="Test", output_dir=tmp_path,
    )
    assert paths == []


def test_transcript_page_segment_anchors(tmp_path: Path) -> None:
    _write_raw_transcripts(tmp_path)
    render_transcript_pages(
        sessions=[], project_name="Test", output_dir=tmp_path,
    )
    html = (tmp_path / "transcript_p1.html").read_text(encoding="utf-8")
    # Each segment should have an anchor id based on its start time in seconds
    assert 'id="t-16"' in html
    assert 'id="t-42"' in html
    assert 'id="t-70"' in html


def test_transcript_page_js_has_player(tmp_path: Path) -> None:
    _write_raw_transcripts(tmp_path)
    render_transcript_pages(
        sessions=[], project_name="Test", output_dir=tmp_path,
    )
    html = (tmp_path / "transcript_p1.html").read_text(encoding="utf-8")
    assert "initPlayer();" in html
    # Should NOT contain report-only modules
    assert "initFavourites" not in html
    assert "initEditing" not in html
    assert "initTags" not in html
