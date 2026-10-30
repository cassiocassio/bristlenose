"""A stored Signals snapshot follows a hide (docs/design-signals-follow-hide.md)."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from bristlenose.server.models import Quote, QuoteState
from bristlenose.server.signal_snapshots import (
    filter_snapshot_to_counted,
    quote_reference_for_row,
    store_completed_snapshot,
)
from tests.test_serve_signals_api import _create_tagged_project


def _quote(ref: str, pid: str, intensity: int = 2) -> dict[str, Any]:
    return {"quote_id": ref, "participant_id": pid, "intensity": intensity, "text": ref}


def _card(refs: list[tuple[str, str]], *, source: str = "section", assertions=()) -> dict[str, Any]:
    return {
        "location": "Checkout", "source_type": source, "group_name": "Friction",
        "count": len(refs), "participants": sorted({p for _, p in refs}),
        "concentration": 1.8, "composite_signal": 0.62, "n_eff": 2.5,
        "signal_name": "Headline", "elaboration": "Claim.",
        "quotes": [_quote(r, p) for r, p in refs],
        "evidence_assertions": [
            {"id": f"ea_{r}", "ordinal": i, "text": "t", "source_quote_id": r,
             "participant_id": "p1", "source_excerpt": "e", "intervention_fragment": None}
            for i, r in enumerate(assertions)
        ],
    }


def _payload(card: dict[str, Any], *, matrix: str = "section_matrix") -> dict[str, Any]:
    refs = card["quotes"]
    cell = {
        "count": len(refs), "weighted_count": float(len(refs)),
        "participants": {}, "intensities": [q["intensity"] for q in refs],
    }
    for q in refs:
        cell["participants"][q["participant_id"]] = cell["participants"].get(q["participant_id"], 0) + 1
    empty = {"cells": {}, "row_totals": {}, "col_totals": {}, "grand_total": 0, "row_labels": []}
    target = {
        "cells": {"Checkout|Friction": cell},
        "row_totals": {"Checkout": len(refs)}, "col_totals": {"Friction": len(refs)},
        "grand_total": len(refs), "row_labels": ["Checkout"],
    }
    other = "theme_matrix" if matrix == "section_matrix" else "section_matrix"
    return {"codebooks": [{
        "codebook_id": "x", "signals": [card], matrix: target, other: copy.deepcopy(empty),
    }], "total_participants": 4}


ALL = [("a", "p1"), ("b", "p2"), ("c", "p2"), ("d", "p3")]


def test_a_snapshot_whose_quotes_all_still_count_comes_back_unchanged() -> None:
    payload = _payload(_card(ALL, assertions=["a"]))
    before = copy.deepcopy(payload)
    assert filter_snapshot_to_counted(payload, {"a", "b", "c", "d"}) == before


def test_a_removed_quote_leaves_the_card_the_count_and_the_voices() -> None:
    payload = _payload(_card(ALL))
    out = filter_snapshot_to_counted(payload, {"a", "b", "c"})  # d (p3) no longer counts
    card = out["codebooks"][0]["signals"][0]
    assert [q["quote_id"] for q in card["quotes"]] == ["a", "b", "c"]
    assert card["count"] == 3
    assert card["participants"] == ["p1", "p2"]  # p3 only had the quote that left
    # Everything that is a calculation stays as it was.
    assert (card["concentration"], card["composite_signal"], card["signal_name"]) == (
        1.8, 0.62, "Headline")


def test_the_cells_in_the_matrix_lose_the_same_quotes() -> None:
    out = filter_snapshot_to_counted(_payload(_card(ALL)), {"a", "c"})  # b and d leave
    matrix = out["codebooks"][0]["section_matrix"]
    cell = matrix["cells"]["Checkout|Friction"]
    assert cell["count"] == 2
    assert cell["participants"] == {"p1": 1, "p2": 1}
    assert cell["intensities"] == [2, 2]
    assert (matrix["row_totals"]["Checkout"], matrix["col_totals"]["Friction"]) == (2, 2)
    assert matrix["grand_total"] == 2
    assert out["codebooks"][0]["theme_matrix"]["grand_total"] == 0  # the other matrix is untouched


def test_a_theme_card_changes_the_theme_matrix_not_the_section_one() -> None:
    card = _card(ALL, source="theme")
    out = filter_snapshot_to_counted(_payload(card, matrix="theme_matrix"), {"a", "b", "c"})
    assert out["codebooks"][0]["theme_matrix"]["grand_total"] == 3
    assert out["codebooks"][0]["section_matrix"]["grand_total"] == 0


def test_an_assertion_citing_a_quote_that_left_is_dropped_and_the_rest_renumbered() -> None:
    payload = _payload(_card(ALL, assertions=["a", "b", "d"]))
    card = filter_snapshot_to_counted(payload, {"b", "c", "d"})["codebooks"][0]["signals"][0]
    assert [(a["source_quote_id"], a["ordinal"]) for a in card["evidence_assertions"]] == [
        ("b", 0), ("d", 1)]
    assert card["had_evidence_assertions"] is True


def test_when_the_only_cited_quote_leaves_the_card_remembers_it_had_assertions() -> None:
    payload = _payload(_card(ALL, assertions=["a"]))
    card = filter_snapshot_to_counted(payload, {"b", "c", "d"})["codebooks"][0]["signals"][0]
    assert card["evidence_assertions"] == []
    assert card["had_evidence_assertions"] is True


def test_a_card_with_no_counted_quote_left_is_dropped() -> None:
    out = filter_snapshot_to_counted(_payload(_card(ALL)), set())
    assert out["codebooks"][0]["signals"] == []
    assert out["codebooks"][0]["section_matrix"]["grand_total"] == 0


def test_a_quote_without_a_reference_is_not_counted() -> None:
    payload = _payload(_card([("", "p1"), ("b", "p2")]))
    out = filter_snapshot_to_counted(payload, {"b"})
    assert [q["quote_id"] for q in out["codebooks"][0]["signals"][0]["quotes"]] == ["b"]


def test_a_card_that_never_had_quotes_is_left_alone() -> None:
    payload = {"codebooks": [{"codebook_id": "c", "signals": [{"location": "x"}]}]}
    assert filter_snapshot_to_counted(copy.deepcopy(payload), set()) == payload


def test_filtering_twice_gives_the_same_answer_as_once() -> None:
    payload = _payload(_card(ALL, assertions=["a", "b"]))
    once = filter_snapshot_to_counted(copy.deepcopy(payload), {"b", "c"})
    twice = filter_snapshot_to_counted(copy.deepcopy(once), {"b", "c"})
    assert twice == once


# ── Through the real reader, the real counted set and the real hide ──────────────


def _stored_project(*, hide_before: tuple[int, ...] = ()):
    client = _create_tagged_project()
    db = client.app.state.db_factory()
    try:
        for quote_id in hide_before:
            db.add(QuoteState(quote_id=quote_id, is_hidden=True))
        db.commit()
        live = client.get("/api/projects/1/signals/codebooks").json()
        assert any(cb["signals"] for cb in live["codebooks"]), "fixture must yield cards"
        store_completed_snapshot(db, 1, source="codebook_apply", payload=live)
        db.commit()
    finally:
        db.close()
    return client


def _snapshot_quote_texts(client) -> set[str]:
    snap = client.get("/api/projects/1/signals/snapshot").json()["snapshot"]
    return {q["text"] for cb in snap["codebooks"] for s in cb["signals"] for q in s["quotes"]}


def _a_card_quote_row(client) -> Quote:
    db = client.app.state.db_factory()
    try:
        snap = client.get("/api/projects/1/signals/snapshot").json()["snapshot"]
        text = next(q["text"] for cb in snap["codebooks"] for s in cb["signals"] for q in s["quotes"])
        row = db.query(Quote).filter_by(text=text).first()
        db.expunge(row)
        return row
    finally:
        db.close()


def _set_hidden(client, quote_id: int, hidden: bool) -> None:
    db = client.app.state.db_factory()
    try:
        state = db.query(QuoteState).filter_by(quote_id=quote_id).first()
        if state is None:
            db.add(QuoteState(quote_id=quote_id, is_hidden=hidden))
        else:
            state.is_hidden = hidden
        db.commit()
    finally:
        db.close()


def test_hiding_a_quote_after_the_build_removes_it_and_unhiding_brings_it_back() -> None:
    client = _stored_project()
    row = _a_card_quote_row(client)
    assert row.text in _snapshot_quote_texts(client)

    _set_hidden(client, row.id, True)
    assert row.text not in _snapshot_quote_texts(client)

    _set_hidden(client, row.id, False)
    assert row.text in _snapshot_quote_texts(client)


def test_a_quote_hidden_before_the_build_is_not_in_the_snapshot_to_unhide() -> None:
    client = _create_tagged_project()
    db = client.app.state.db_factory()
    try:
        victim = db.query(Quote).filter_by(project_id=1).order_by(Quote.id).first()
        victim_id, victim_text = victim.id, victim.text
    finally:
        db.close()
    client = _stored_project_with_hidden_first(victim_id)
    assert victim_text not in _snapshot_quote_texts(client)
    _set_hidden(client, victim_id, False)
    # The filter only removes: the quote was never built into the snapshot.
    assert victim_text not in _snapshot_quote_texts(client)


def _stored_project_with_hidden_first(quote_id: int):
    client = _create_tagged_project()
    _set_hidden(client, quote_id, True)
    db = client.app.state.db_factory()
    try:
        live = client.get("/api/projects/1/signals/codebooks").json()
        store_completed_snapshot(db, 1, source="codebook_apply", payload=live)
        db.commit()
    finally:
        db.close()
    return client


def test_reading_the_snapshot_never_calculates_or_calls_a_model(monkeypatch) -> None:
    client = _stored_project()
    from bristlenose.server.routes import signals as routes

    def forbidden(*args, **kwargs):
        raise AssertionError("the snapshot reader must only read and filter")

    monkeypatch.setattr(routes, "_build_codebook_analysis", forbidden)
    monkeypatch.setattr(routes, "detect_signals_generic", forbidden)
    row = _a_card_quote_row(client)
    _set_hidden(client, row.id, True)
    assert client.get("/api/projects/1/signals/snapshot").status_code == 200


def test_the_references_in_the_snapshot_are_the_ones_the_counted_set_is_built_from() -> None:
    client = _stored_project()
    snap = client.get("/api/projects/1/signals/snapshot").json()["snapshot"]
    db = client.app.state.db_factory()
    try:
        counted = {quote_reference_for_row(q) for q in db.query(Quote).filter_by(project_id=1)}
    finally:
        db.close()
    refs = {q["quote_id"] for cb in snap["codebooks"] for s in cb["signals"] for q in s["quotes"]}
    assert refs and refs <= counted


@pytest.mark.parametrize("hide_all", [True])
def test_hiding_every_quote_of_the_cards_drops_the_cards(hide_all) -> None:
    client = _stored_project()
    db = client.app.state.db_factory()
    try:
        for row in db.query(Quote).filter_by(project_id=1):
            state = db.query(QuoteState).filter_by(quote_id=row.id).first()
            if state is None:
                db.add(QuoteState(quote_id=row.id, is_hidden=True))
            else:
                state.is_hidden = True
        db.commit()
    finally:
        db.close()
    snap = client.get("/api/projects/1/signals/snapshot").json()["snapshot"]
    assert all(cb["signals"] == [] for cb in snap["codebooks"])


def _exported_snapshot(client) -> dict[str, Any]:
    """The Signals snapshot a researcher's HTML export carries."""
    import json

    html = client.get("/api/projects/1/export").text
    start = html.index("window.BRISTLENOSE_EXPORT=") + len("window.BRISTLENOSE_EXPORT=")
    data, _ = json.JSONDecoder().raw_decode(html[start:])
    return data["endpoints"]["/signals/snapshot"]["snapshot"]


def test_an_export_made_after_a_hide_does_not_carry_the_hidden_quote_in_signals() -> None:
    client = _stored_project()
    row = _a_card_quote_row(client)
    texts = lambda snap: {  # noqa: E731
        q["text"] for cb in snap["codebooks"] for s in cb["signals"] for q in s["quotes"]}
    assert row.text in texts(_exported_snapshot(client))

    _set_hidden(client, row.id, True)
    exported = _exported_snapshot(client)
    assert row.text not in texts(exported)
    # No assertion may cite it either.
    cited = {a["source_quote_id"] for cb in exported["codebooks"] for s in cb["signals"]
             for a in s.get("evidence_assertions", [])}
    assert quote_reference_for_row(row) not in cited
