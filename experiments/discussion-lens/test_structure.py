"""Tests for the deterministic half of the Discussion lens spike.

Run:  .venv/bin/python -m pytest experiments/discussion-lens/test_structure.py -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from structure import (  # noqa: E402
    Consolidated,
    Item,
    Label,
    Section,
    Topic,
    Turn,
    anchor,
    apply_labels,
    build_structure,
    decide_route,
    order_sections,
    place_by_flow,
    promote,
)


def turns_of(*specs):
    """specs: (session, seconds, text) → {id: Turn}"""
    out = {}
    for sid, sec, text in specs:
        tid = f"{sid}@{int(sec) // 60:02d}:{int(sec) % 60:02d}"
        out[tid] = Turn(tid, sid, float(sec), text)
    return out


def spine():
    return [
        Section("s0", "Consent", "instruction", items=[Item("s0.1", "Consent")]),
        Section("s1", "About you", items=[Item("s1.1", "Household"), Item("s1.2", "Big shop")]),
        Section("s2", "Planning", items=[Item("s2.1", "Deciding"), Item("s2.2", "Lists")]),
        Section("s3", "Ordering", items=[Item("s3.1", "Last order")]),
    ]


# ── apply_labels ──


def test_planned_turns_attach_and_flip_source_to_both():
    T = turns_of(("a", 10, "who lives with you"), ("b", 20, "who's at home"))
    secs, _ = apply_labels(spine(), [Label(t, "planned", item_id="s1.1") for t in T], [], [], T)
    item = secs[1].items[0]
    assert item.source == "both" and item.turns == ["a@00:10", "b@00:20"]
    assert secs[1].items[1].source == "planned" and secs[1].items[1].turns == []


def test_invalid_ids_are_counted_and_degraded_not_trusted():
    T = turns_of(("a", 10, "q1"))
    labels = [Label("a@00:10", "planned", item_id="s9.9"), Label("zz@99:99", "planned", item_id="s1.1")]
    secs, stats = apply_labels(spine(), labels, [], [], T)
    assert stats["invented_turn_ids"] == 1
    assert stats["planned_unknown_item"] == 1
    assert all(not it.turns for s in secs if s.origin == "planned" for it in s.items)
    # the turn is not lost: it becomes an unplaced emergent item
    assert any("a@00:10" in it.turns for s in secs for it in s.items)


def test_consolidated_adlib_joins_its_planned_section_and_topic_makes_emergent():
    T = turns_of(("a", 10, "paper or phone?"), ("a", 50, "budget?"), ("b", 30, "a set amount?"))
    labels = [Label("a@00:10", "adlib", section_id="s2"), Label("a@00:50", "new", cluster="money"),
              Label("b@00:30", "new", cluster="budget")]
    cons = [Consolidated(["a@00:10"], "List medium", "s2"),
            Consolidated(["a@00:50", "b@00:30"], "Set a budget", "Budget")]
    secs, stats = apply_labels(spine(), labels, cons, [Topic("Budget", "Budget", "Budget and prices")], T)
    assert [it.terse for it in secs[2].items][-1] == "List medium"
    e = [s for s in secs if s.origin == "emergent"]
    assert len(e) == 1 and e[0].heading == "Budget and prices"
    assert e[0].items[0].turns == ["a@00:50", "b@00:30"]
    assert stats["unconsolidated_turns"] == 0


def test_unplanned_turn_the_consolidator_dropped_still_appears():
    T = turns_of(("a", 10, "an ad-lib nobody consolidated"))
    secs, stats = apply_labels(spine(), [Label("a@00:10", "adlib", section_id="s2", terse="Ad-lib")], [], [], T)
    assert stats["unconsolidated_turns"] == 1
    assert secs[2].items[-1].turns == ["a@00:10"]


def test_consolidated_item_cannot_land_in_an_instruction_section():
    T = turns_of(("a", 10, "q"))
    secs, _ = apply_labels(spine(), [Label("a@00:10", "adlib", section_id="s0")],
                           [Consolidated(["a@00:10"], "Q", "s0")], [], T)
    assert secs[0].items == [Item("s0.1", "Consent")]


# ── promote ──


def emergent(name, *sessions_items):
    """sessions_items: list of lists of turn ids, one list per item"""
    return Section(name, name, origin="emergent",
                   items=[Item(f"{name}{i}", "x", source="asked", turns=ts) for i, ts in enumerate(sessions_items)])


def test_promotion_needs_two_sessions_and_three_asks():
    recurs = emergent("budget", ["a@01:00"], ["b@01:00"], ["a@02:00", "c@01:00"])
    one_session = emergent("recipes", ["b@01:00"], ["b@02:00"], ["b@03:00"])
    two_asks = emergent("pets", ["a@01:00"], ["b@01:00"])
    kept, homeless, dissolved = promote([recurs, one_session, two_asks])
    assert [s.title for s in kept] == ["budget"]
    assert dissolved == ["recipes", "pets"] and len(homeless) == 5


def test_promotion_counts_asks_not_how_finely_the_model_merged_them():
    # the same three asks across two sessions, merged into one item or kept as three
    merged = emergent("money", ["a@01:00", "a@02:00", "b@01:00"])
    split = emergent("money2", ["a@01:00"], ["a@02:00"], ["b@01:00"])
    kept, _, _ = promote([merged, split])
    assert len(kept) == 2


def test_planned_sections_are_never_dissolved_even_if_thin():
    kept, homeless, _ = promote(spine())
    assert len(kept) == 4 and homeless == []


# ── order_sections ──


def test_emergent_section_is_inserted_by_median_time_between_planned_ones():
    T = turns_of(("a", 100, "x"), ("a", 300, "y"), ("a", 500, "z"), ("a", 200, "m"), ("a", 210, "n"))
    s1 = Section("s1", "A", items=[Item("i1", "x", turns=["a@01:40"])])
    s2 = Section("s2", "B", items=[Item("i2", "y", turns=["a@05:00"])])
    s3 = Section("s3", "C", items=[Item("i3", "z", turns=["a@08:20"])])
    e = Section("e1", "E", origin="emergent", items=[Item("e", "m", turns=["a@03:20", "a@03:30"])])
    out = order_sections([s1, s2, s3, e], T, {"a": 600})
    assert [s.id for s in out] == ["s1", "e1", "s2", "s3"]


def test_without_a_guide_sections_sort_by_median_time_and_instruction_stays_first():
    T = turns_of(("a", 400, "late"), ("a", 100, "early"))
    instr = Section("s0", "Consent", "instruction")
    late = Section("e1", "Late", origin="emergent", items=[Item("l", "l", turns=["a@06:40"])])
    early = Section("e2", "Early", origin="emergent", items=[Item("e", "e", turns=["a@01:40"])])
    assert [s.id for s in order_sections([instr, late, early], T, {"a": 600})] == ["s0", "e2", "e1"]


def test_planned_section_never_asked_does_not_pull_an_emergent_one_forward():
    T = turns_of(("a", 500, "z"), ("a", 300, "m"))
    unasked = Section("s1", "Unasked", items=[Item("i1", "x")])
    asked = Section("s2", "Asked", items=[Item("i2", "z", turns=["a@08:20"])])
    e = Section("e1", "E", origin="emergent", items=[Item("e", "m", turns=["a@05:00"])])
    assert [s.id for s in order_sections([unasked, asked, e], T, {"a": 600})] == ["s1", "e1", "s2"]


# ── place_by_flow ──


def test_homeless_question_joins_the_section_the_session_was_in():
    T = turns_of(("a", 100, "p"), ("a", 130, "tangent"), ("a", 400, "q"))
    A = Section("s1", "A", items=[Item("i1", "p", turns=["a@01:40"])])
    B = Section("s2", "B", items=[Item("i2", "q", turns=["a@06:40"])])
    h = Item("h", "tangent", source="asked", turns=["a@02:10"])
    assert place_by_flow([A, B], [h], T) == []
    assert A.items[-1] is h and h.placed == "flow"


def test_opener_joins_the_next_section_closer_the_previous():
    T = turns_of(("a", 100, "p"), ("a", 390, "open"), ("a", 410, "close"), ("a", 400, "q"))
    A = Section("s1", "A", items=[Item("i1", "p", turns=["a@01:40"])])
    B = Section("s2", "B", items=[Item("i2", "q", turns=["a@06:40"])])
    opener = Item("o", "open", source="asked", role="opening", turns=["a@06:30"])
    closer = Item("c", "close", source="asked", role="closing", turns=["a@06:50"])
    place_by_flow([A, B], [opener, closer], T)
    assert B.items[0] is opener and B.items[-1] is closer


def test_split_vote_leaves_a_question_standalone():
    T = turns_of(("a", 100, "p"), ("a", 110, "h1"), ("b", 400, "q"), ("b", 410, "h2"))
    A = Section("s1", "A", items=[Item("i1", "p", turns=["a@01:40"])])
    B = Section("s2", "B", items=[Item("i2", "q", turns=["b@06:40"])])
    h = Item("h", "h", source="asked", turns=["a@01:50", "b@06:50"])
    assert place_by_flow([A, B], [h], T) == [h] and h.placed == ""


# ── anchor + decide_route ──


def test_anchor_is_the_last_question_before_the_quote_within_the_window():
    asked = [(100.0, "i1"), (200.0, "i2"), (900.0, "i3")]
    assert anchor("a", 150, asked) == "i1"
    assert anchor("a", 200, asked) == "i2"           # a quote at the same second answers it
    assert anchor("a", 50, asked) is None            # before the first question
    assert anchor("a", 600, asked) is None           # stale: 400 s after i2
    assert anchor("a", 600, asked, window=500) == "i2"


def test_route_agreement_topic_override_and_fallbacks():
    assert decide_route("s1", "s1", 0.2) == ("s1", "agree")
    assert decide_route("s1", "s2", 0.9) == ("s2", "topic")      # a confident drift wins
    assert decide_route("s1", "s2", 0.5) == ("s1", "anchor")     # a hesitant one does not
    assert decide_route(None, "s2", 0.1) == ("s2", "topic")      # no fresh anchor: topic decides
    assert decide_route("s1", None, 0.0) == ("s1", "anchor")
    assert decide_route(None, None, 0.0) == (None, "unrouted")


# ── end to end, deterministic ──


def test_build_structure_is_repeatable_for_the_same_labels():
    T = turns_of(("a", 60, "who"), ("a", 120, "budget"), ("b", 60, "who"), ("b", 300, "budget"),
                 ("c", 200, "budget"), ("b", 400, "recipe app"))
    def run():
        labels = [Label("a@01:00", "planned", item_id="s1.1"), Label("b@01:00", "planned", item_id="s1.1"),
                  Label("a@02:00", "new", cluster="b"), Label("b@05:00", "new", cluster="b"),
                  Label("c@03:20", "new", cluster="b"), Label("b@06:40", "new", cluster="r")]
        cons = [Consolidated(["a@02:00", "c@03:20"], "Set budget", "Budget"),
                Consolidated(["b@05:00"], "Prices", "Budget"),
                Consolidated(["b@06:40"], "Recipe app", "Recipes")]
        topics = [Topic("Budget", "Budget", "Budget"), Topic("Recipes", "Recipes", "Recipes")]
        secs, standalone, stats = build_structure(spine(), labels, cons, topics, T, {"a": 600, "b": 600, "c": 600})
        return [(s.title, [(i.terse, i.placed, tuple(i.turns)) for i in s.items]) for s in secs], stats
    first, stats = run()
    assert first == run()[0]
    assert "dissolved: Budget" not in stats  # 3 asks over 3 sessions → promoted
    assert "dissolved: Recipes" in stats
