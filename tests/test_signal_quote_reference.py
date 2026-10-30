"""A snapshot's quote references can be rebuilt from the database rows.

The Signals snapshot stores a reference for every card quote (``quote_id``). The filter that
makes a card follow a hide (docs/design-signals-follow-hide.md) works out the same reference from
each quote that counts, so the two must agree exactly. The stored shape is frozen in payload v4:
the signal path builds its record without a segment index or an ordinal, so every stored
reference is a hash with -1 and 0 whatever the row holds. A fixture whose rows are all (-1, 0)
cannot tell the right builder from the wrong one, so these rows carry real values.
"""

from __future__ import annotations

from bristlenose.server.elaboration import compute_quote_reference
from bristlenose.server.models import Quote
from bristlenose.server.signal_snapshots import quote_reference_for_row
from tests.test_serve_signals_api import _create_tagged_project


def _naive_reference(row: Quote) -> str:
    """The wrong way: the row's own segment index and ordinal."""
    return compute_quote_reference(
        type("R", (), {
            "participant_id": row.participant_id,
            "session_id": row.session_id,
            "start_seconds": row.start_timecode,
            "segment_index": row.segment_index,
            "ordinal": row.ordinal,
            "text": row.text,
        })()
    )


def test_a_reference_rebuilt_from_a_row_matches_the_stored_quote_id() -> None:
    client = _create_tagged_project()
    db = client.app.state.db_factory()
    try:
        rows = db.query(Quote).filter_by(project_id=1).order_by(Quote.id).all()
        for i, row in enumerate(rows):
            row.segment_index = 10 + i
            row.ordinal = i % 2
        db.commit()

        payload = client.get("/api/projects/1/signals/tags").json()
        stored = [q for s in payload["signals"] for q in s["quotes"]]
        assert stored, "the fixture must produce at least one card with quotes"

        by_key = {(r.participant_id, r.session_id, r.start_timecode, r.text): r for r in rows}
        matched_with_real_index = 0
        for quote in stored:
            row = by_key[(
                quote["participant_id"], quote["session_id"],
                quote["start_seconds"], quote["text"],
            )]
            assert quote["quote_id"] == quote_reference_for_row(row)
            if row.segment_index >= 0 and _naive_reference(row) != quote["quote_id"]:
                matched_with_real_index += 1
        # The point of the fixture: the row's own values would NOT have matched.
        assert matched_with_real_index == len(stored)
    finally:
        db.close()


def test_the_reference_does_not_depend_on_segment_index_or_ordinal() -> None:
    row = Quote(
        project_id=1, session_id="s1", participant_id="p1", start_timecode=12.5,
        end_timecode=20.0, text="It was hard to find.", quote_type="general_context",
        sentiment="frustration", intensity=2, segment_index=7, ordinal=3,
    )
    same = Quote(
        project_id=1, session_id="s1", participant_id="p1", start_timecode=12.5,
        end_timecode=20.0, text="It was hard to find.", quote_type="general_context",
        sentiment="frustration", intensity=2, segment_index=99, ordinal=0,
    )
    assert quote_reference_for_row(row) == quote_reference_for_row(same)
    assert quote_reference_for_row(row) != _naive_reference(row)
