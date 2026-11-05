"""Property-based tests for quote identity: the id a quote is known by never collides, never
moves with the order things were read in, and parses back to the quote it came from (R86).

What a researcher would notice if it broke: a star, hide, tag or edit on one quote lands on
another that starts in the same second; an export or an agent's citation names the wrong one;
a re-import renumbers quotes so curation sticks to the wrong words. The defect-mining pass of
5 Nov 2026 found this shape (identity by a loose key at a persisted boundary) in the largest
group of serious fixes, so the invariants are stated once, for every input, not for the cases
that happened to break. Placement rule: docs/design-test-philosophy.md.

CI runs these derandomised (tests/conftest.py); a kill that matters is pinned with @example.
"""

from __future__ import annotations

import random

from hypothesis import assume, example, given
from hypothesis import strategies as st

from bristlenose.server.grounding import parse_quote_dom_id, quote_dom_id
from bristlenose.server.importer import QuoteRankKey, rank_quote_ordinals

# Small alphabets on purpose: two quotes sharing a session, speaker and whole second is the
# case that matters, so the generator is steered into collisions instead of avoiding them.
SESSIONS = st.sampled_from(["s1", "s2"])
SPEAKERS = st.sampled_from(["p1", "p2", "m1"])
STARTS = st.sampled_from([0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.25])
ENDS = st.sampled_from([0.5, 1.0, 1.5, 3.0, 4.0])
CONTENT = st.sampled_from(["", "a", "b", "ab", "same words", "Same words"])
KEYS = st.tuples(SESSIONS, SPEAKERS, STARTS, ENDS, CONTENT, st.just(0))
KEY_LISTS = st.lists(KEYS, min_size=1, max_size=12)

# A speaker code is [pmo]\d+ (assign_speaker_codes): the only participants an id is built for.
CODES = st.builds(lambda letter, n: f"{letter}{n}", st.sampled_from("pmo"),
                  st.integers(min_value=1, max_value=999))
SECONDS = st.integers(min_value=0, max_value=100 * 3600)
ORDINALS = st.integers(min_value=0, max_value=10_000)


def _group(key: QuoteRankKey) -> tuple[str, str, int]:
    return key[0], key[1], int(key[2])


# --- the id ---------------------------------------------------------------------------


@given(CODES, SECONDS, ORDINALS)
@example("p1", 123, 0)
@example("p1", 123, 1)
@example("m12", 0, 10_000)
def test_an_id_parses_back_to_what_built_it(code: str, second: int, ordinal: int) -> None:
    assert parse_quote_dom_id(quote_dom_id(code, float(second), ordinal)) == (
        code, second, ordinal)


@given(CODES, SECONDS, ORDINALS, CODES, SECONDS, ORDINALS)
def test_distinct_quotes_never_share_an_id(
    c1: str, s1: int, o1: int, c2: str, s2: int, o2: int,
) -> None:
    same_quote = (c1, s1, o1) == (c2, s2, o2)
    same_id = quote_dom_id(c1, float(s1), o1) == quote_dom_id(c2, float(s2), o2)
    assert same_id == same_quote


@given(CODES, SECONDS, st.floats(min_value=0.0, max_value=0.999, allow_nan=False))
def test_a_fraction_of_a_second_does_not_change_the_id(
    code: str, second: int, fraction: float,
) -> None:
    # The id carries whole seconds; two quotes a fraction apart are told apart by ordinal.
    assert quote_dom_id(code, second + fraction, 0) == quote_dom_id(code, float(second), 0)


# --- the ordinal: what tells two quotes in one second apart ---------------------------


@given(KEY_LISTS)
def test_quotes_in_one_second_get_distinct_consecutive_ordinals(keys: list) -> None:
    ranks = rank_quote_ordinals(keys)
    groups: dict[tuple[str, str, int], list[int]] = {}
    for key in set(keys):
        groups.setdefault(_group(key), []).append(ranks[key])
    for ordinals in groups.values():
        assert sorted(ordinals) == list(range(len(ordinals)))


@given(KEY_LISTS, st.randoms(use_true_random=False))
@example([("s1", "p1", 1.0, 2.0, "a", 0), ("s1", "p1", 1.5, 2.0, "a", 0)], random.Random(0))
def test_the_order_quotes_were_read_in_does_not_change_their_ordinals(
    keys: list, rnd: random.Random,
) -> None:
    shuffled = list(keys)
    rnd.shuffle(shuffled)
    assert rank_quote_ordinals(shuffled) == rank_quote_ordinals(keys)


@given(KEY_LISTS)
def test_the_first_quote_in_a_second_keeps_the_id_it_always_had(keys: list) -> None:
    ranks = rank_quote_ordinals(keys)
    groups: dict[tuple[str, str, int], list[QuoteRankKey]] = {}
    for key in set(keys):
        groups.setdefault(_group(key), []).append(key)
    for members in groups.values():
        earliest = min(members, key=lambda k: (k[2], k[3], k[4], k[5]))
        assert ranks[earliest] == 0


@given(KEY_LISTS)
def test_the_same_quote_read_twice_is_one_quote(keys: list) -> None:
    assert rank_quote_ordinals(keys + keys) == rank_quote_ordinals(keys)


@given(KEY_LISTS, KEYS)
def test_a_quote_elsewhere_does_not_renumber_these(keys: list, other: QuoteRankKey) -> None:
    # Locality: a quote in another session, speaker or second leaves every other id alone.
    assume(all(_group(other) != _group(k) for k in keys))
    before = rank_quote_ordinals(keys)
    after = rank_quote_ordinals([*keys, other])
    assert all(after[k] == before[k] for k in before)
