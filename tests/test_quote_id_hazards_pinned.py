"""Quote-id hazards found by the usual-suspects fresh-eyes review (6 Nov 2026), pinned strict.

The start-time hazards (negative, enormous, NaN) are closed at the import boundary by
``clean_start_timecode`` (owner, 6 Nov 2026) and tested above. What stays pinned is the builder's
dashed-participant collision, which needs a ruling on participant codes.

The pinned one needs an input the pipeline should never produce (a dashed participant code). They are real in the
code, reproduced with concrete inputs, and pinned on invariants that need no ruling to state:

* an id must never read back as a different quote (refusing is fine; guessing is not);
* two different quotes must never share an id;
* an id the builder emits must be one the parser accepts;
* an import must not stop on one bad timecode.

Each xfail is strict and names the exception it expects, so it goes red the day someone fixes the
hazard (delete the marker then) and cannot be satisfied by a broken setup. Whether to validate at
the import boundary, in the builder, or not at all is the owner's call (morning report, 6 Nov).
Same shape as ``tests/test_hidden_counts_nowhere_exemplars.py``.
"""

from __future__ import annotations

import pytest

from bristlenose.server.grounding import parse_quote_dom_id, quote_dom_id
from bristlenose.server.importer import _rank_key, clean_start_timecode, rank_quote_ordinals


def test_the_ordinary_case_round_trips() -> None:
    # The control: the pins below mean something only if this holds.
    assert parse_quote_dom_id(quote_dom_id("p1", 123.9, 2)) == ("p1", 123, 2)


@pytest.mark.parametrize("bad", [-1.5, -0.5, 360_001.0, float("nan"), float("inf"), "x", None])
def test_the_import_boundary_cleans_a_start_the_id_cannot_carry(bad: object) -> None:
    # Owner ruling, 6 Nov 2026: validate at import. A negative, huge, NaN or non-numeric start
    # is stored as 0, so the id round-trips and one bad timecode does not stop the import.
    row = {"session_id": "s1", "participant_id": "p1", "start_timecode": bad}
    start = _rank_key(row)[2]
    assert start == 0.0
    assert rank_quote_ordinals([_rank_key(row)])
    assert parse_quote_dom_id(quote_dom_id("p1", start, 0)) == ("p1", 0, 0)


def test_a_sane_start_is_kept_as_it_was() -> None:
    assert clean_start_timecode(123.9) == 123.9
    assert clean_start_timecode(0) == 0.0
    assert clean_start_timecode(360_000.0) == 360_000.0


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="('p1-2', 5s, 0) and ('p1', 2s, 5) are both q-p1-2-5")
def test_a_dashed_participant_does_not_share_an_id_with_another_quote() -> None:
    assert quote_dom_id("p1-2", 5.0, 0) != quote_dom_id("p1", 2.0, 5)
