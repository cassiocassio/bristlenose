"""Tests for bristlenose.server.export_core — shared extraction layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from bristlenose.server.app import create_app
from bristlenose.server.export_core import (
    ExportableQuote,
    _format_timecode,
    csv_safe,
    excel_sheet_name,
    extract_quotes_for_export,
)
from bristlenose.server.models import QuoteEdit, QuoteState

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session():
    """Create a DB session with smoke-test data imported."""
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    session = app.state.db_factory()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# csv_safe()
# ---------------------------------------------------------------------------


class TestCsvSafe:
    def test_normal_text_unchanged(self):
        assert csv_safe("Hello world") == "Hello world"

    def test_empty_string(self):
        assert csv_safe("") == ""

    def test_equals_prefix(self):
        assert csv_safe("=SUM(A1:A10)") == "\t=SUM(A1:A10)"

    def test_plus_prefix(self):
        assert csv_safe("+cmd|'calc'!A0") == "\t+cmd|'calc'!A0"

    def test_minus_prefix(self):
        assert csv_safe("-1+1") == "\t-1+1"

    def test_at_prefix(self):
        assert csv_safe("@mention") == "\t@mention"

    def test_tab_prefix(self):
        assert csv_safe("\tcontent") == "\t\tcontent"

    def test_cr_prefix(self):
        assert csv_safe("\rcontent") == "\t\rcontent"

    def test_normal_number_unchanged(self):
        assert csv_safe("42") == "42"


# ---------------------------------------------------------------------------
# excel_sheet_name()
# ---------------------------------------------------------------------------


class TestExcelSheetName:
    def test_normal_name(self):
        assert excel_sheet_name("My Project") == "My Project"

    def test_truncates_to_31(self):
        long_name = "A" * 50
        result = excel_sheet_name(long_name)
        assert len(result) == 31

    def test_strips_brackets(self):
        assert excel_sheet_name("Project [2026]") == "Project 2026"

    def test_strips_asterisk(self):
        assert excel_sheet_name("Project*") == "Project"

    def test_strips_question_mark(self):
        assert excel_sheet_name("Project?") == "Project"

    def test_strips_slashes(self):
        assert excel_sheet_name("A/B\\C") == "ABC"

    def test_strips_leading_trailing_quotes(self):
        assert excel_sheet_name("'My Project'") == "My Project"

    def test_empty_returns_quotes(self):
        assert excel_sheet_name("") == "Quotes"

    def test_all_illegal_returns_quotes(self):
        assert excel_sheet_name("[]*?/\\") == "Quotes"


# ---------------------------------------------------------------------------
# _format_timecode()
# ---------------------------------------------------------------------------


class TestFormatTimecode:
    def test_seconds_only(self):
        assert _format_timecode(5.0) == "0:05"

    def test_minutes_and_seconds(self):
        assert _format_timecode(125.0) == "2:05"

    def test_hours(self):
        assert _format_timecode(3661.0) == "1:01:01"

    def test_zero(self):
        assert _format_timecode(0.0) == "0:00"

    def test_fractional_truncated(self):
        assert _format_timecode(10.7) == "0:10"


# ---------------------------------------------------------------------------
# extract_quotes_for_export()
# ---------------------------------------------------------------------------


class TestExtractQuotesForExport:
    def test_returns_all_non_hidden(self, db_session):
        """Smoke-test fixture has 4 quotes, none hidden initially."""
        quotes = extract_quotes_for_export(db_session, project_id=1)
        assert len(quotes) == 4

    def test_returns_exportable_quotes(self, db_session):
        quotes = extract_quotes_for_export(db_session, project_id=1)
        assert all(isinstance(q, ExportableQuote) for q in quotes)

    def test_text_field_populated(self, db_session):
        quotes = extract_quotes_for_export(db_session, project_id=1)
        assert all(q.text for q in quotes)

    def test_participant_code_populated(self, db_session):
        quotes = extract_quotes_for_export(db_session, project_id=1)
        # Smoke test has p1 as participant
        assert all(q.participant_code == "p1" for q in quotes)

    def test_session_field(self, db_session):
        quotes = extract_quotes_for_export(db_session, project_id=1)
        assert all(q.session == "s1" for q in quotes)

    def test_sentiment_field(self, db_session):
        quotes = extract_quotes_for_export(db_session, project_id=1)
        sentiments = {q.sentiment for q in quotes}
        # Smoke test has confusion, frustration, delight
        assert sentiments & {"confusion", "frustration", "delight"}

    def test_timecode_formatted(self, db_session):
        quotes = extract_quotes_for_export(db_session, project_id=1)
        for q in quotes:
            assert ":" in q.timecode

    def test_section_populated(self, db_session):
        quotes = extract_quotes_for_export(db_session, project_id=1)
        sections = {q.section for q in quotes}
        # Smoke test has Dashboard, Search, Onboarding gaps
        assert len(sections) >= 1

    def test_hidden_quotes_excluded(self, db_session):
        """Mark a quote as hidden; it should be excluded."""
        from bristlenose.server.models import Quote

        q = db_session.query(Quote).filter(Quote.project_id == 1).first()
        state = QuoteState(quote_id=q.id, is_hidden=True)
        db_session.add(state)
        db_session.commit()

        quotes = extract_quotes_for_export(db_session, project_id=1)
        assert len(quotes) == 3  # 4 - 1 hidden

    def test_quote_ids_filter(self, db_session):
        quotes = extract_quotes_for_export(
            db_session, project_id=1, quote_ids=["q-p1-10"]
        )
        assert len(quotes) == 1
        assert quotes[0].participant_code == "p1"

    def test_quote_ids_includes_hidden(self, db_session):
        """When specific quote_ids are given, hidden quotes are included."""
        from bristlenose.server.models import Quote

        q = (
            db_session.query(Quote)
            .filter(Quote.project_id == 1, Quote.participant_id == "p1")
            .first()
        )
        state = QuoteState(quote_id=q.id, is_hidden=True)
        db_session.add(state)
        db_session.commit()

        dom_id = f"q-{q.participant_id}-{int(q.start_timecode)}"
        quotes = extract_quotes_for_export(
            db_session, project_id=1, quote_ids=[dom_id]
        )
        assert len(quotes) == 1

    def test_edited_text_preferred(self, db_session):
        """Edited text should override original quote text."""
        from bristlenose.server.models import Quote

        q = db_session.query(Quote).filter(Quote.project_id == 1).first()
        edit = QuoteEdit(quote_id=q.id, edited_text="EDITED TEXT")
        db_session.add(edit)
        db_session.commit()

        quotes = extract_quotes_for_export(db_session, project_id=1)
        edited = [eq for eq in quotes if eq.text == "EDITED TEXT"]
        assert len(edited) == 1

    def test_starred_flag(self, db_session):
        """Starred quotes should have starred=True."""
        from bristlenose.server.models import Quote

        q = db_session.query(Quote).filter(Quote.project_id == 1).first()
        state = QuoteState(quote_id=q.id, is_starred=True)
        db_session.add(state)
        db_session.commit()

        quotes = extract_quotes_for_export(db_session, project_id=1)
        starred = [eq for eq in quotes if eq.starred]
        assert len(starred) == 1

    def test_anonymise_blanks_name(self, db_session):
        quotes = extract_quotes_for_export(
            db_session, project_id=1, anonymise=True
        )
        for q in quotes:
            assert q.participant_name == ""

    def test_source_file_is_basename(self, db_session):
        """Source file should be basename only, no directory path."""
        quotes = extract_quotes_for_export(db_session, project_id=1)
        for q in quotes:
            if q.source_file:
                assert "/" not in q.source_file
                assert "\\" not in q.source_file

    def test_empty_project_returns_empty(self, db_session):
        quotes = extract_quotes_for_export(db_session, project_id=999)
        assert quotes == []

    def test_invalid_quote_id_ignored(self, db_session):
        quotes = extract_quotes_for_export(
            db_session, project_id=1, quote_ids=["invalid-id"]
        )
        assert quotes == []
