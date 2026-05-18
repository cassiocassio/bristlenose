"""Catalogue invariants — behavioural, not snapshot."""

from __future__ import annotations

from bristlenose.pipeline_view.catalogue import STAGES, find_stage


def test_every_stage_has_unique_id() -> None:
    ids = [s.id for s in STAGES]
    assert len(ids) == len(set(ids)), "duplicate stage ids in catalogue"


def test_every_stage_has_non_empty_name_and_notes() -> None:
    for s in STAGES:
        assert s.name.strip(), f"empty name on {s.id}"
        assert s.notes.strip(), f"empty notes on {s.id}"


def test_apple_fm_row_present_and_typed_apple_fm() -> None:
    apple = find_stage("apple_foundation_models")
    assert apple is not None
    assert apple.kind == "apple_fm"


def test_find_stage_returns_none_on_unknown() -> None:
    assert find_stage("not_a_real_stage") is None


def test_kinds_are_within_known_set() -> None:
    allowed = {"transcription", "llm", "anonymisation", "apple_fm"}
    for s in STAGES:
        assert s.kind in allowed, f"unknown kind {s.kind!r} on {s.id}"
