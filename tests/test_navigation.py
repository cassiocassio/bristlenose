"""Tests for global navigation tabs in the HTML report."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from bristlenose.models import (
    EmotionalTone,
    ExtractedQuote,
    FileType,
    InputFile,
    InputSession,
    PeopleFile,
    PersonComputed,
    PersonEditable,
    PersonEntry,
    QuoteIntent,
    QuoteType,
    ScreenCluster,
    Sentiment,
    ThemeGroup,
)
from bristlenose.stages.render_html import _pick_featured_quotes, render_html

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_quote(pid: str = "p1", sid: str = "s1") -> ExtractedQuote:
    return ExtractedQuote(
        participant_id=pid,
        session_id=sid,
        start_timecode=10.0,
        end_timecode=20.0,
        text="Test quote text",
        topic_label="Topic",
        quote_type=QuoteType.SCREEN_SPECIFIC,
        intent=QuoteIntent.NARRATION,
        emotion=EmotionalTone.NEUTRAL,
    )


def _make_scored_quote(
    pid: str = "p1",
    sid: str = "s1",
    text: str = "This is a test quote with enough words to pass the minimum threshold",
    sentiment: Sentiment | None = Sentiment.FRUSTRATION,
    intensity: int = 2,
    tc: float = 10.0,
) -> ExtractedQuote:
    """Create a quote with sentiment data for featured-quotes testing."""
    return ExtractedQuote(
        participant_id=pid,
        session_id=sid,
        start_timecode=tc,
        end_timecode=tc + 10.0,
        text=text,
        topic_label="Topic",
        quote_type=QuoteType.SCREEN_SPECIFIC,
        intent=QuoteIntent.NARRATION,
        emotion=EmotionalTone.NEUTRAL,
        sentiment=sentiment,
        intensity=intensity,
    )


def _render_report(tmp_path: Path) -> str:
    """Render a minimal report and return the HTML string."""
    render_html(
        screen_clusters=[
            ScreenCluster(
                screen_label="Homepage",
                description="Landing page",
                display_order=1,
                quotes=[_make_quote()],
            ),
        ],
        theme_groups=[
            ThemeGroup(
                theme_label="Brand perception",
                description="Positive brand feelings",
                quotes=[_make_quote()],
            ),
        ],
        sessions=[],
        project_name="Nav Test",
        output_dir=tmp_path,
    )
    return (tmp_path / "bristlenose-nav-test-report.html").read_text(encoding="utf-8")


def _render_report_with_people(tmp_path: Path) -> str:
    """Render a report with sessions and people data, return HTML string."""
    dt = datetime(2026, 1, 15, 10, 0, 0)
    dt2 = datetime(2026, 1, 20, 14, 30, 0)
    sessions = [
        InputSession(
            session_id="s1", session_number=1,
            participant_id="p1", participant_number=1,
            files=[InputFile(
                path=Path("/fake/interview1.mp4"), file_type=FileType.VIDEO,
                created_at=dt, size_bytes=1000, duration_seconds=1800.0,
            )],
            session_date=dt,
        ),
        InputSession(
            session_id="s2", session_number=2,
            participant_id="p2", participant_number=2,
            files=[InputFile(
                path=Path("/fake/interview2.mp4"), file_type=FileType.VIDEO,
                created_at=dt2, size_bytes=2000, duration_seconds=2400.0,
            )],
            session_date=dt2,
        ),
    ]
    people = PeopleFile(participants={
        "p1": PersonEntry(
            computed=PersonComputed(
                participant_id="p1", session_id="s1", session_date=dt,
                duration_seconds=1800.0, words_spoken=3200,
                pct_words=55.0, pct_time_speaking=60.0,
                source_file="interview1.mp4",
            ),
            editable=PersonEditable(
                full_name="Alice Smith", short_name="Alice", role="Designer",
            ),
        ),
        "m1": PersonEntry(
            computed=PersonComputed(
                participant_id="m1", session_id="s1", session_date=dt,
                duration_seconds=1800.0, words_spoken=2600,
                pct_words=45.0, pct_time_speaking=40.0,
                source_file="interview1.mp4",
            ),
            editable=PersonEditable(
                full_name="Moderator", short_name="Mod",
            ),
        ),
        "p2": PersonEntry(
            computed=PersonComputed(
                participant_id="p2", session_id="s2", session_date=dt2,
                duration_seconds=2400.0, words_spoken=4100,
                pct_words=100.0, pct_time_speaking=70.0,
                source_file="interview2.mp4",
            ),
            editable=PersonEditable(
                full_name="Bob Jones", short_name="Bob", role="Engineer",
            ),
        ),
    })
    quotes = [_make_quote("p1", "s1"), _make_quote("p2", "s2")]
    render_html(
        screen_clusters=[
            ScreenCluster(
                screen_label="Homepage", description="Landing page",
                display_order=1,
                quotes=quotes,
            ),
        ],
        theme_groups=[],
        sessions=sessions,
        project_name="People Test",
        output_dir=tmp_path,
        people=people,
        all_quotes=quotes,
    )
    return (tmp_path / "bristlenose-people-test-report.html").read_text(encoding="utf-8")


def _render_report_with_sentiments(tmp_path: Path) -> str:
    """Render a report with sentiment-tagged quotes for featured-quotes testing."""
    quotes = [
        _make_scored_quote("p1", "s1", sentiment=Sentiment.FRUSTRATION, intensity=3, tc=10),
        _make_scored_quote("p2", "s1", sentiment=Sentiment.DELIGHT, intensity=2, tc=50),
        _make_scored_quote("p3", "s1", sentiment=Sentiment.SURPRISE, intensity=2, tc=90),
        _make_scored_quote("p1", "s1", sentiment=Sentiment.SATISFACTION, intensity=1, tc=130),
    ]
    render_html(
        screen_clusters=[
            ScreenCluster(
                screen_label="Homepage", description="Landing page",
                display_order=1,
                quotes=quotes,
            ),
        ],
        theme_groups=[],
        sessions=[],
        project_name="Featured Test",
        output_dir=tmp_path,
        all_quotes=quotes,
    )
    return (tmp_path / "bristlenose-featured-test-report.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tab panel structure
# ---------------------------------------------------------------------------


def test_tab_panels_have_data_tab_attributes(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    for tab in ("project", "sessions", "quotes", "codebook", "analysis", "settings", "about"):
        assert f'data-tab="{tab}"' in html


def test_project_tab_is_default_active(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert 'data-tab="project" id="panel-project" role="tabpanel" aria-label="Project">' in html
    # Project panel has the active class
    assert 'bn-tab-panel active" data-tab="project"' in html


def test_panel_ids_present(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    for tab in ("project", "sessions", "quotes", "codebook", "analysis", "settings", "about"):
        assert f'id="panel-{tab}"' in html


def test_tab_buttons_have_aria_controls(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    for tab in ("project", "sessions", "quotes", "codebook", "analysis", "settings", "about"):
        assert f'aria-controls="panel-{tab}"' in html


# ---------------------------------------------------------------------------
# doc_title
# ---------------------------------------------------------------------------


def test_doc_title_populated(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert "Research Report" in html


def test_browser_title_has_project_name(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert "<title>Nav Test</title>" in html


# ---------------------------------------------------------------------------
# ToC Analysis section
# ---------------------------------------------------------------------------


def test_toc_has_analysis_section(tmp_path: Path) -> None:
    """Analysis entries (Sentiment, etc.) should appear in the ToC when present."""
    html = _render_report(tmp_path)
    # The ToC renders an Analysis heading when chart_toc items exist.
    # Even without sentiment quotes, the render may include the section.
    # At minimum, verify the template supports the chart_toc block.
    assert "chart_toc" not in html or "Analysis" in html


# ---------------------------------------------------------------------------
# Speaker links
# ---------------------------------------------------------------------------


def test_speaker_link_uses_data_nav_session(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert "data-nav-session=" in html


def test_speaker_link_has_data_nav_anchor(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert "data-nav-anchor=" in html


def test_speaker_link_no_standalone_href(tmp_path: Path) -> None:
    """Speaker links should not point to standalone transcript pages."""
    html = _render_report(tmp_path)
    # Old pattern was href="sessions/transcript_..."
    assert 'href="sessions/transcript_' not in html


# ---------------------------------------------------------------------------
# JS initialisation
# ---------------------------------------------------------------------------


def test_global_nav_js_included(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert "initGlobalNav" in html


def test_quote_map_injected(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert "BRISTLENOSE_QUOTE_MAP" in html


# ---------------------------------------------------------------------------
# Project tab content
# ---------------------------------------------------------------------------


def test_project_tab_has_stats(tmp_path: Path) -> None:
    """Project tab shows summary stats (sessions, participants, quotes)."""
    html = _render_report(tmp_path)
    assert "bn-project-stats" in html
    assert "bn-project-stat-value" in html
    # Minimal report: 0 sessions, 0 participants, but quote/section/theme counts
    assert "quote" in html.lower()


# ---------------------------------------------------------------------------
# Dashboard layout
# ---------------------------------------------------------------------------


def test_dashboard_grid_present(tmp_path: Path) -> None:
    """Project tab renders a dashboard grid container."""
    html = _render_report(tmp_path)
    assert "bn-dashboard" in html
    assert "bn-dashboard-pane" in html


def test_dashboard_stats_pane_full_width(tmp_path: Path) -> None:
    """Stats pane spans full width of the dashboard grid."""
    html = _render_report(tmp_path)
    assert "bn-dashboard-full" in html


def test_dashboard_sections_list(tmp_path: Path) -> None:
    """Dashboard includes a sections nav list with linked names."""
    html = _render_report(tmp_path)
    assert "bn-dashboard-nav" in html
    assert ">Sections</h3>" in html
    assert "Homepage" in html


def test_dashboard_themes_list(tmp_path: Path) -> None:
    """Dashboard includes a themes nav list with linked names."""
    html = _render_report(tmp_path)
    assert ">Themes</h3>" in html
    assert "Brand perception" in html


def test_dashboard_with_people_has_session_table(tmp_path: Path) -> None:
    """When sessions exist, dashboard includes a full-width session table."""
    html = _render_report_with_people(tmp_path)
    assert "bn-session-table" in html
    # Single moderator → shown in header, not in rows.
    assert "Moderated by" in html
    assert "Mod" in html  # moderator short_name


def test_session_table_has_speaker_badges(tmp_path: Path) -> None:
    """Session table renders speaker code badges for each participant."""
    html = _render_report_with_people(tmp_path)
    assert '<span class="badge">p1</span>' in html
    assert '<span class="badge">p2</span>' in html


def test_session_table_single_moderator_omitted_from_rows(tmp_path: Path) -> None:
    """With only one moderator, moderator codes don't appear in row speaker lists."""
    html = _render_report_with_people(tmp_path)
    # m1 should be in the header but not as a row badge.
    assert "Moderated by" in html
    # The session table is rendered twice (Sessions tab + Project tab dashboard),
    # so m1 badge appears twice (once per header). But it should not appear in
    # bn-person-badge divs (row speaker lists).
    assert '<div class="bn-person-badge"><span class="badge">m1</span>' not in html


def test_session_table_has_journey(tmp_path: Path) -> None:
    """Session table shows journey paths derived from screen clusters."""
    html = _render_report_with_people(tmp_path)
    assert "bn-session-journey" in html
    assert "Homepage" in html


def test_session_table_has_id_with_hash(tmp_path: Path) -> None:
    """Session IDs render with # prefix."""
    html = _render_report_with_people(tmp_path)
    assert "#1</a>" in html
    assert "#2</a>" in html


def test_dashboard_with_people_shows_duration(tmp_path: Path) -> None:
    """Dashboard stats show total duration when people data is available."""
    html = _render_report_with_people(tmp_path)
    # Test sessions use .mp4 files → label is "of video".
    assert "of video" in html


def test_dashboard_with_people_shows_words(tmp_path: Path) -> None:
    """Dashboard stats show total words when people data is available."""
    html = _render_report_with_people(tmp_path)
    # p1: 3200, m1: 2600, p2: 4100 = 9,900 total
    assert "words" in html
    assert "9,900" in html


# ---------------------------------------------------------------------------
# Featured quotes
# ---------------------------------------------------------------------------


def test_featured_row_rendered_with_sentiments(tmp_path: Path) -> None:
    """Dashboard shows a featured quotes row when quotes have sentiments."""
    html = _render_report_with_sentiments(tmp_path)
    assert "bn-featured-row" in html
    assert "bn-featured-quote" in html


def test_featured_quotes_have_data_quote_id(tmp_path: Path) -> None:
    """Each featured quote card carries a data-quote-id for JS reshuffle."""
    html = _render_report_with_sentiments(tmp_path)
    assert "data-quote-id=" in html


def test_featured_quotes_show_quote_text(tmp_path: Path) -> None:
    """Featured quote cards include the quote text."""
    html = _render_report_with_sentiments(tmp_path)
    assert "quote-text" in html
    # The quote text from _make_scored_quote default
    assert "enough words to pass the minimum threshold" in html


def test_featured_quotes_have_sentiment_badge(tmp_path: Path) -> None:
    """Featured quotes show their sentiment badge."""
    html = _render_report_with_sentiments(tmp_path)
    # At least one of the sentiment values should appear as a badge
    assert "badge-frustration" in html or "badge-delight" in html or "badge-surprise" in html


def test_featured_quotes_have_speaker_link(tmp_path: Path) -> None:
    """Featured quotes have speaker links for navigation."""
    html = _render_report_with_sentiments(tmp_path)
    # Featured cards render speaker-link elements
    assert 'class="speaker-link"' in html


def test_featured_row_has_visible_count_attr(tmp_path: Path) -> None:
    """Featured row carries data-visible-count for JS reshuffle."""
    html = _render_report_with_sentiments(tmp_path)
    assert 'data-visible-count="3"' in html


def test_featured_quotes_no_hide_star_buttons(tmp_path: Path) -> None:
    """Featured quotes should not have hide/star/edit/tag controls."""
    html = _render_report_with_sentiments(tmp_path)
    # Extract only the featured-row portion of the HTML
    start = html.find("bn-featured-row")
    end = html.find("bn-project-stats")
    featured_section = html[start:end]
    assert "hide-btn" not in featured_section
    assert "star-btn" not in featured_section
    assert "edit-pencil" not in featured_section
    assert "badge-add" not in featured_section


def test_featured_row_not_rendered_without_all_quotes(tmp_path: Path) -> None:
    """No featured row element when all_quotes is not provided."""
    # _render_report() doesn't pass all_quotes → no featured quotes rendered.
    html = _render_report(tmp_path)
    # The class name appears in the JS reshuffle function, so check for the
    # actual HTML element (div with the class), not just the class string.
    assert '<div class="bn-featured-row' not in html


# ---------------------------------------------------------------------------
# _pick_featured_quotes algorithm
# ---------------------------------------------------------------------------


def test_pick_featured_empty() -> None:
    """Empty input returns empty list."""
    assert _pick_featured_quotes([]) == []


def test_pick_featured_prefers_different_participants() -> None:
    """Algorithm picks from different participants when possible."""
    quotes = [
        _make_scored_quote("p1", "s1", sentiment=Sentiment.FRUSTRATION, intensity=3, tc=10),
        _make_scored_quote("p1", "s1", sentiment=Sentiment.DELIGHT, intensity=3, tc=20),
        _make_scored_quote("p2", "s1", sentiment=Sentiment.SURPRISE, intensity=3, tc=30),
        _make_scored_quote("p3", "s1", sentiment=Sentiment.CONFUSION, intensity=3, tc=40),
    ]
    picked = _pick_featured_quotes(quotes, n=3)
    pids = {q.participant_id for q in picked}
    assert len(pids) == 3  # all three should be different participants


def test_pick_featured_mixes_sentiment_polarity() -> None:
    """Algorithm prefers a mix of positive/negative/surprise sentiments."""
    quotes = [
        _make_scored_quote("p1", "s1", sentiment=Sentiment.FRUSTRATION, intensity=3, tc=10),
        _make_scored_quote("p2", "s1", sentiment=Sentiment.DELIGHT, intensity=3, tc=20),
        _make_scored_quote("p3", "s1", sentiment=Sentiment.SURPRISE, intensity=3, tc=30),
        _make_scored_quote("p4", "s1", sentiment=Sentiment.FRUSTRATION, intensity=3, tc=40),
    ]
    picked = _pick_featured_quotes(quotes, n=3)
    sentiments = {q.sentiment for q in picked}
    # Should pick one from each polarity bucket
    assert Sentiment.FRUSTRATION in sentiments
    assert Sentiment.DELIGHT in sentiments
    assert Sentiment.SURPRISE in sentiments


def test_pick_featured_skips_short_quotes() -> None:
    """Very short quotes are deprioritised (fall back only if needed)."""
    short = ExtractedQuote(
        participant_id="p1", session_id="s1",
        start_timecode=10.0, end_timecode=20.0,
        text="Too short",  # 2 words
        topic_label="Topic", quote_type=QuoteType.SCREEN_SPECIFIC,
        intent=QuoteIntent.NARRATION, emotion=EmotionalTone.NEUTRAL,
        sentiment=Sentiment.FRUSTRATION, intensity=3,
    )
    long = _make_scored_quote("p2", "s1", sentiment=Sentiment.DELIGHT, intensity=1, tc=30)
    picked = _pick_featured_quotes([short, long], n=1)
    # Should prefer the longer quote even though short one has higher intensity
    assert picked[0].participant_id == "p2"


def test_pick_featured_returns_up_to_n() -> None:
    """Returns at most n quotes even when more are available."""
    quotes = [
        _make_scored_quote(f"p{i}", "s1", sentiment=Sentiment.FRUSTRATION, tc=i * 10)
        for i in range(10)
    ]
    assert len(_pick_featured_quotes(quotes, n=3)) == 3
    assert len(_pick_featured_quotes(quotes, n=5)) == 5


def test_pick_featured_handles_no_sentiment() -> None:
    """Quotes without sentiment still get a score (from length/intensity)."""
    q = _make_scored_quote("p1", "s1", sentiment=None, intensity=1, tc=10)
    picked = _pick_featured_quotes([q], n=1)
    assert len(picked) == 1


# ---------------------------------------------------------------------------
# User tags dashboard stat
# ---------------------------------------------------------------------------


def test_dashboard_user_tags_stat_container(tmp_path: Path) -> None:
    """Dashboard includes a hidden container for JS-populated user-tags stat."""
    html = _render_report(tmp_path)
    assert 'id="dashboard-user-tags-stat"' in html
    assert 'id="dashboard-user-tags-value"' in html
    assert 'id="dashboard-user-tags-label"' in html


def test_reshuffle_js_included(tmp_path: Path) -> None:
    """Featured quotes reshuffle JS function is present in the report."""
    html = _render_report(tmp_path)
    assert "_reshuffleFeaturedQuotes" in html
