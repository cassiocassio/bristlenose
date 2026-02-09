"""Tests for transcript page quote annotations (highlighting + margin data)."""

from __future__ import annotations

from pathlib import Path

from bristlenose.models import (
    ExtractedQuote,
    QuoteType,
    ScreenCluster,
    Sentiment,
    ThemeGroup,
)
from bristlenose.stages.render_html import (
    _build_transcript_quote_map,
    _highlight_quoted_text,
    render_transcript_pages,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RAW_TRANSCRIPT = """\
# Transcript: s1
# Source: interview_01.mp4
# Date: 2026-01-20
# Duration: 00:05:00

[00:10] [p1] Yeah um I've been using this for a while.

[00:42] [p1] The login page was really confusing at first.

[01:10] [p1] But once I figured it out it was fine.

[01:45] [m1] Can you tell me more about that?

[02:00] [p1] Sure it's just the buttons were hard to find.
"""


def _write_transcripts(output_dir: Path) -> None:
    raw_dir = output_dir / "transcripts-raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "s1.txt").write_text(_RAW_TRANSCRIPT, encoding="utf-8")


def _make_quote(
    start: float = 42.0,
    end: float = 48.0,
    text: str = "The login page was really confusing at first",
    verbatim: str = "The login page was really confusing at first.",
    session_id: str = "s1",
    participant_id: str = "p1",
    quote_type: QuoteType = QuoteType.SCREEN_SPECIFIC,
    sentiment: Sentiment | None = Sentiment.CONFUSION,
) -> ExtractedQuote:
    return ExtractedQuote(
        session_id=session_id,
        participant_id=participant_id,
        start_timecode=start,
        end_timecode=end,
        text=text,
        verbatim_excerpt=verbatim,
        topic_label="Login flow",
        quote_type=quote_type,
        sentiment=sentiment,
    )


def _make_cluster(quotes: list[ExtractedQuote]) -> ScreenCluster:
    return ScreenCluster(
        screen_label="Login page",
        description="Issues with the login screen",
        display_order=1,
        quotes=quotes,
    )


def _make_theme(quotes: list[ExtractedQuote]) -> ThemeGroup:
    return ThemeGroup(
        theme_label="Onboarding friction",
        description="Difficulty getting started",
        quotes=quotes,
    )


# ---------------------------------------------------------------------------
# _build_transcript_quote_map
# ---------------------------------------------------------------------------


def test_quote_map_empty_when_no_quotes() -> None:
    result = _build_transcript_quote_map(None, None, None)
    assert result == {}


def test_quote_map_empty_list() -> None:
    result = _build_transcript_quote_map([], [], [])
    assert result == {}


def test_quote_map_groups_by_session() -> None:
    q1 = _make_quote(session_id="s1")
    q2 = _make_quote(session_id="s2", start=10.0, end=15.0)
    result = _build_transcript_quote_map([q1, q2], [], [])
    assert "s1" in result
    assert "s2" in result
    assert len(result["s1"]) == 1
    assert len(result["s2"]) == 1


def test_quote_map_includes_cluster_label() -> None:
    q = _make_quote()
    cluster = _make_cluster([q])
    result = _build_transcript_quote_map([q], [cluster], [])
    ann = result["s1"][0]
    assert ann.label == "Login page"
    assert ann.label_type == "section"


def test_quote_map_includes_theme_label() -> None:
    q = _make_quote(quote_type=QuoteType.GENERAL_CONTEXT)
    theme = _make_theme([q])
    result = _build_transcript_quote_map([q], [], [theme])
    ann = result["s1"][0]
    assert ann.label == "Onboarding friction"
    assert ann.label_type == "theme"


def test_quote_map_includes_sentiment() -> None:
    q = _make_quote(sentiment=Sentiment.FRUSTRATION)
    result = _build_transcript_quote_map([q], [], [])
    ann = result["s1"][0]
    assert ann.sentiment == "frustration"


def test_quote_map_no_sentiment() -> None:
    q = _make_quote(sentiment=None)
    result = _build_transcript_quote_map([q], [], [])
    ann = result["s1"][0]
    assert ann.sentiment == ""


def test_quote_map_verbatim_excerpt_preserved() -> None:
    q = _make_quote(verbatim="The login page was really confusing at first.")
    result = _build_transcript_quote_map([q], [], [])
    ann = result["s1"][0]
    assert ann.verbatim_excerpt == "The login page was really confusing at first."


def test_quote_map_no_assignment() -> None:
    """Quote with no cluster or theme gets empty label."""
    q = _make_quote()
    result = _build_transcript_quote_map([q], [], [])
    ann = result["s1"][0]
    assert ann.label == ""
    assert ann.label_type == ""


# ---------------------------------------------------------------------------
# _highlight_quoted_text
# ---------------------------------------------------------------------------


def test_highlight_with_verbatim_match() -> None:
    from bristlenose.stages.render_html import _QuoteAnnotation

    ann = _QuoteAnnotation(
        quote_id="q-p1-42",
        participant_id="p1",
        start_tc=42.0,
        end_tc=48.0,
        verbatim_excerpt="really confusing",
        label="Login",
        label_type="section",
        sentiment="confusion",
    )
    segment_text = "The login page was really confusing at first."
    result = _highlight_quoted_text(segment_text, [ann])
    assert '<mark class="bn-cited"' in result
    assert "really confusing" in result
    # Text before the match should be plain
    assert "The login page was " in result
    # Text after the match should be plain
    assert " at first." in result


def test_highlight_no_verbatim_falls_back_to_whole_segment() -> None:
    from bristlenose.stages.render_html import _QuoteAnnotation

    ann = _QuoteAnnotation(
        quote_id="q-p1-42",
        participant_id="p1",
        start_tc=42.0,
        end_tc=48.0,
        verbatim_excerpt="",
        label="Login",
        label_type="section",
        sentiment="",
    )
    segment_text = "The login page was confusing."
    result = _highlight_quoted_text(segment_text, [ann])
    # Entire segment should be wrapped in <mark>
    assert '<mark class="bn-cited"' in result
    assert "The login page was confusing." in result


def test_highlight_verbatim_not_found_falls_back() -> None:
    from bristlenose.stages.render_html import _QuoteAnnotation

    ann = _QuoteAnnotation(
        quote_id="q-p1-42",
        participant_id="p1",
        start_tc=42.0,
        end_tc=48.0,
        verbatim_excerpt="this text does not exist in the segment",
        label="Login",
        label_type="section",
        sentiment="",
    )
    segment_text = "The login page was confusing."
    result = _highlight_quoted_text(segment_text, [ann])
    # Should fall back to highlighting the whole segment
    assert '<mark class="bn-cited"' in result


def test_highlight_html_escapes_text() -> None:
    from bristlenose.stages.render_html import _QuoteAnnotation

    ann = _QuoteAnnotation(
        quote_id="q-p1-42",
        participant_id="p1",
        start_tc=42.0,
        end_tc=48.0,
        verbatim_excerpt="it's <great>",
        label="Login",
        label_type="section",
        sentiment="",
    )
    segment_text = "I think it's <great> honestly."
    result = _highlight_quoted_text(segment_text, [ann])
    # HTML should be escaped
    assert "&lt;great&gt;" in result
    assert "it&#x27;s" in result
    # No raw < or > in the output (except our <mark> tags)
    assert "<great>" not in result


def test_highlight_multiple_quotes_in_segment() -> None:
    from bristlenose.stages.render_html import _QuoteAnnotation

    ann1 = _QuoteAnnotation(
        quote_id="q-p1-42",
        participant_id="p1",
        start_tc=42.0,
        end_tc=48.0,
        verbatim_excerpt="really confusing",
        label="Login",
        label_type="section",
        sentiment="confusion",
    )
    ann2 = _QuoteAnnotation(
        quote_id="q-p1-43",
        participant_id="p1",
        start_tc=42.0,
        end_tc=48.0,
        verbatim_excerpt="at first",
        label="Onboarding",
        label_type="theme",
        sentiment="",
    )
    segment_text = "The login page was really confusing at first."
    result = _highlight_quoted_text(segment_text, [ann1, ann2])
    # Both should be highlighted
    assert result.count('<mark class="bn-cited"') == 2


def test_highlight_empty_annotations() -> None:
    result = _highlight_quoted_text("Some text.", [])
    assert result == "Some text."


# ---------------------------------------------------------------------------
# Rendered transcript page with annotations
# ---------------------------------------------------------------------------


def test_transcript_page_has_segment_quoted_class(tmp_path: Path) -> None:
    _write_transcripts(tmp_path)
    q = _make_quote()
    render_transcript_pages(
        sessions=[], project_name="Test", output_dir=tmp_path,
        all_quotes=[q], screen_clusters=[_make_cluster([q])],
    )
    html = (tmp_path / "sessions" / "transcript_s1.html").read_text(encoding="utf-8")
    assert "segment-quoted" in html


def test_transcript_page_has_quote_map_data(tmp_path: Path) -> None:
    _write_transcripts(tmp_path)
    q = _make_quote()
    render_transcript_pages(
        sessions=[], project_name="Test", output_dir=tmp_path,
        all_quotes=[q], screen_clusters=[_make_cluster([q])],
    )
    html = (tmp_path / "sessions" / "transcript_s1.html").read_text(encoding="utf-8")
    assert "BRISTLENOSE_QUOTE_MAP" in html
    assert "Login page" in html


def test_transcript_page_has_report_url(tmp_path: Path) -> None:
    _write_transcripts(tmp_path)
    q = _make_quote()
    render_transcript_pages(
        sessions=[], project_name="Test", output_dir=tmp_path,
        all_quotes=[q], screen_clusters=[_make_cluster([q])],
    )
    html = (tmp_path / "sessions" / "transcript_s1.html").read_text(encoding="utf-8")
    assert "BRISTLENOSE_REPORT_URL" in html
    assert "bristlenose-test-report.html" in html


def test_transcript_page_has_citation_mark(tmp_path: Path) -> None:
    _write_transcripts(tmp_path)
    q = _make_quote(
        verbatim="The login page was really confusing at first.",
    )
    render_transcript_pages(
        sessions=[], project_name="Test", output_dir=tmp_path,
        all_quotes=[q],
    )
    html = (tmp_path / "sessions" / "transcript_s1.html").read_text(encoding="utf-8")
    assert '<mark class="bn-cited"' in html


def test_transcript_page_moderator_not_quoted(tmp_path: Path) -> None:
    """Moderator segments should never get segment-quoted class."""
    _write_transcripts(tmp_path)
    # Create a quote that happens to overlap with the moderator segment timing
    q = _make_quote(start=100.0, end=120.0, participant_id="m1")
    render_transcript_pages(
        sessions=[], project_name="Test", output_dir=tmp_path,
        all_quotes=[q],
    )
    html = (tmp_path / "sessions" / "transcript_s1.html").read_text(encoding="utf-8")
    # The moderator segment at 01:45 should not be marked as quoted
    lines = html.split("\n")
    for line in lines:
        if "segment-moderator" in line:
            assert "segment-quoted" not in line


def test_transcript_page_no_quotes_no_annotations(tmp_path: Path) -> None:
    """When no quotes are provided, page renders without annotations."""
    _write_transcripts(tmp_path)
    render_transcript_pages(
        sessions=[], project_name="Test", output_dir=tmp_path,
    )
    html = (tmp_path / "sessions" / "transcript_s1.html").read_text(encoding="utf-8")
    # No segment divs should have the segment-quoted class
    # (the class name appears in the CSS stylesheet, so check div elements only)
    assert 'class="transcript-segment segment-quoted' not in html
    assert "BRISTLENOSE_QUOTE_MAP = {};" in html


def test_transcript_page_init_annotations_called(tmp_path: Path) -> None:
    _write_transcripts(tmp_path)
    q = _make_quote()
    render_transcript_pages(
        sessions=[], project_name="Test", output_dir=tmp_path,
        all_quotes=[q],
    )
    html = (tmp_path / "sessions" / "transcript_s1.html").read_text(encoding="utf-8")
    assert "initTranscriptAnnotations();" in html


def test_transcript_page_data_attributes(tmp_path: Path) -> None:
    """Quoted segments should have data-quote-ids and timing attributes."""
    _write_transcripts(tmp_path)
    q = _make_quote()
    render_transcript_pages(
        sessions=[], project_name="Test", output_dir=tmp_path,
        all_quotes=[q],
    )
    html = (tmp_path / "sessions" / "transcript_s1.html").read_text(encoding="utf-8")
    assert 'data-quote-ids="q-p1-42"' in html
    assert "data-start-seconds=" in html
    assert "data-end-seconds=" in html


# ---------------------------------------------------------------------------
# ExtractedQuote.verbatim_excerpt backward compat
# ---------------------------------------------------------------------------


def test_verbatim_excerpt_defaults_empty() -> None:
    """Existing quotes without verbatim_excerpt should default to empty string."""
    q = ExtractedQuote(
        participant_id="p1",
        start_timecode=42.0,
        end_timecode=48.0,
        text="The login page was confusing",
        topic_label="Login",
        quote_type=QuoteType.SCREEN_SPECIFIC,
    )
    assert q.verbatim_excerpt == ""


def test_verbatim_excerpt_round_trip_json() -> None:
    """verbatim_excerpt should survive JSON serialisation."""
    q = _make_quote(verbatim="original words here")
    data = q.model_dump()
    assert data["verbatim_excerpt"] == "original words here"
    q2 = ExtractedQuote(**data)
    assert q2.verbatim_excerpt == "original words here"


def test_verbatim_excerpt_missing_in_json() -> None:
    """Loading JSON without verbatim_excerpt should default to empty string."""
    data = {
        "participant_id": "p1",
        "start_timecode": 42.0,
        "end_timecode": 48.0,
        "text": "Some quote",
        "topic_label": "Topic",
        "quote_type": "screen_specific",
    }
    q = ExtractedQuote(**data)
    assert q.verbatim_excerpt == ""
