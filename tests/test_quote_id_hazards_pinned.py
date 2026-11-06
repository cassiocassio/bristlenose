"""Quote-id hazards found by the usual-suspects fresh-eyes review (6 Nov 2026), pinned strict.

None is reachable from the pipeline today: each needs an input the pipeline should never produce
(a negative or enormous start, a dashed participant code, a NaN timecode). They are real in the
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
from bristlenose.server.importer import _rank_key, rank_quote_ordinals


def test_the_ordinary_case_round_trips() -> None:
    # The control: the pins below mean something only if this holds.
    assert parse_quote_dom_id(quote_dom_id("p1", 123.9, 2)) == ("p1", 123, 2)


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="a negative start builds q-p1--1, which reads back as ('p1-', 1, 0)")
def test_a_negative_start_never_reads_back_as_a_different_quote() -> None:
    built = quote_dom_id("p1", -1.5, 0)
    try:
        parsed = parse_quote_dom_id(built)
    except ValueError:
        return  # refusing is fine
    assert parsed == ("p1", int(-1.5), 0), f"{built} read back as {parsed}"


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="('p1-2', 5s, 0) and ('p1', 2s, 5) are both q-p1-2-5")
def test_a_dashed_participant_does_not_share_an_id_with_another_quote() -> None:
    assert quote_dom_id("p1-2", 5.0, 0) != quote_dom_id("p1", 2.0, 5)


@pytest.mark.xfail(strict=True, raises=ValueError,
                   reason="a start over 100 h builds an id the parser then refuses")
def test_an_id_the_builder_emits_is_one_the_parser_accepts() -> None:
    parse_quote_dom_id(quote_dom_id("p1", 360_001.0, 0))


@pytest.mark.xfail(strict=True, raises=ValueError,
                   reason="a NaN start reaches int() and stops the import with 'cannot convert'")
def test_one_nan_timecode_does_not_stop_the_ranking() -> None:
    row = {"session_id": "s1", "participant_id": "p1", "start_timecode": float("nan")}
    rank_quote_ordinals([_rank_key(row)])
