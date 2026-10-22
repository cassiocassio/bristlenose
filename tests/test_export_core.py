"""Tests for bristlenose.server.export_core — shared extraction layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from bristlenose.server.app import create_app
from bristlenose.server.export_core import (
    ExportableQuote,
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


# _format_timecode() was a private copy of bristlenose.utils.timecodes.format_timecode
# and was deleted on 22 Aug 2026 when the nine timecode implementations were
# consolidated to one per language. Its five cases (0, 5, 125, 3661, 10.7 s) moved
# to tests/fixtures/shared-format-contract.json, where they now hold every
# implementation rather than this one. See docs/design-shared-formats.md.


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

    def test_quote_ids_leaves_out_hidden(self, db_session):
        """A hidden quote is left out of a selection too (owner, 22 Oct 2026, #122).
        Until then a selection included it."""
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
        assert quotes == []

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


def test_rows_sort_by_time_not_by_the_timecode_as_text(db_session):
    """An hour-long session: 59:00 comes before 1:00:05. Sorted as text, "1:00:05" came first,
    which reordered CSV rows and every board's theme columns."""
    from bristlenose.server.models import Quote

    early, late = (db_session.query(Quote).filter_by(project_id=1)
                   .order_by(Quote.start_timecode).all()[:2])  # both in Dashboard
    early.start_timecode, early.end_timecode = 3540.0, 3545.0
    late.start_timecode, late.end_timecode = 3605.0, 3610.0
    db_session.commit()
    rows = [q for q in extract_quotes_for_export(db_session, project_id=1)
            if q.section == "Dashboard"]
    assert [q.timecode for q in rows] == ["59:00", "1:00:05"]


def test_resolve_quote_ids_returns_both_of_a_pair(db_session):
    """Two quotes with one start are ``q-p1-10`` and ``q-p1-10-1``; a selection naming
    both gets both rows, in the order asked (R86)."""
    from bristlenose.server.export_core import _resolve_quote_ids
    from bristlenose.server.models import Quote

    first = (db_session.query(Quote).filter_by(project_id=1)
             .order_by(Quote.start_timecode).first())
    assert int(first.start_timecode) == 10
    second = Quote(project_id=1, session_id=first.session_id, participant_id="p1",
                   start_timecode=first.start_timecode, ordinal=1, end_timecode=60.0,
                   text="the second half", quote_type=first.quote_type, topic_label="")
    db_session.add(second)
    db_session.commit()
    rows = _resolve_quote_ids(db_session, 1, ["q-p1-10-1", "q-p1-10"])
    assert [q.id for q in rows] == [second.id, first.id]
    [row] = extract_quotes_for_export(db_session, project_id=1, quote_ids=["q-p1-10-1"])
    assert (row.quote_id, row.ordinal) == (second.id, 1)


def test_an_id_names_its_own_quote_not_its_neighbour_in_the_second(db_session):
    """Two quotes from one speaker in the same second are ``q-p1-10`` and ``q-p1-10-1``, as
    the importer ranks them (the earlier start first); each selection names its own row on
    every export that takes one (CSV, XLSX, both boards)."""
    from bristlenose.server.models import Quote

    first, second = (db_session.query(Quote).filter_by(project_id=1)
                     .order_by(Quote.start_timecode).all()[:2])
    second.start_timecode, second.ordinal = 10.2, 0
    first.start_timecode, first.ordinal = 10.7, 1
    db_session.commit()
    [row] = extract_quotes_for_export(db_session, project_id=1, quote_ids=["q-p1-10"])
    assert row.quote_id == second.id
    [row] = extract_quotes_for_export(db_session, project_id=1, quote_ids=["q-p1-10-1"])
    assert row.quote_id == first.id
