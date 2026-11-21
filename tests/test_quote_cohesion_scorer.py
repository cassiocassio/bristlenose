"""The quote-cohesion lab's scorer measures what its README says it measures.

``experiments/quote-cohesion/score.py`` decides whether a stage-9 run kept each
passage together: the paid check in ``test_quote_cohesion_live.py`` and every
comparison in the lab read its verdict. These tests are free (no LLM): they pin
the scorer on hand-made quotes, then on the eight saved model runs, where prompt
0.2.0 cut the synthetic think-aloud one quote per line and 0.3.0 did not.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent / "experiments" / "quote-cohesion"


def _load_scorer():
    spec = importlib.util.spec_from_file_location("quote_cohesion_score", LAB / "score.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # A path-loaded module with @dataclass must be in sys.modules before it runs.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


score = _load_scorer()

_TRANSCRIPT = """\
# Transcript: s1

[00:00] [p1] I typed kettle and it came back with descaler first, which is odd.

[00:10] [p1] Okay, um. I expected the kettles themselves at the top of the list.

[00:20] [m1] And then?

[00:25] [p1] I would scroll down and look for a filter on the left side.
"""


def _quote(text: str, start: float, end: float, topic: str = "Search") -> dict:
    return {
        "session_id": "s1",
        "participant_id": "p1",
        "text": text,
        "verbatim_excerpt": text,
        "topic_label": topic,
        "start_timecode": start,
        "end_timecode": end,
    }


def _study(tmp_path: Path) -> Path:
    (tmp_path / "s1.txt").write_text(_TRANSCRIPT, encoding="utf-8")
    return tmp_path


def test_locate_finds_an_exact_excerpt_and_a_slipped_one() -> None:
    forms = [score.norm(w) for w in "one two three four five six seven eight nine ten".split()]
    exact = [score.norm(w) for w in "three four five".split()]
    assert score.locate(forms, exact) == (2, 4)
    # A long excerpt with one word the model changed in the middle is still found by
    # its first and last four words.
    slipped = [score.norm(w) for w in "one two three four FIVE six seven eight nine".split()]
    assert score.locate(forms, slipped) == (0, 8)
    assert score.locate(forms, [score.norm("eleven")]) is None


def test_two_halves_of_one_passage_are_a_touching_pair(tmp_path: Path) -> None:
    quotes = [
        _quote("I typed kettle and it came back with descaler first, which is odd.", 0, 9),
        _quote("I expected the kettles themselves at the top of the list.", 12, 19),
    ]
    f = score.fragmentation(_study(tmp_path), quotes)
    assert f.located == 2
    assert (f.touching, f.same_topic_touching) == (1, 1)


def test_a_researcher_question_between_quotes_is_not_a_cut(tmp_path: Path) -> None:
    # Two words: short enough for the gap rule, so only the speaker can rule it out.
    quotes = [
        _quote("I expected the kettles themselves at the top of the list.", 12, 19),
        _quote("I would scroll down and look for a filter on the left side.", 25, 30),
    ]
    f = score.fragmentation(_study(tmp_path), quotes)
    assert f.touching == 0


def test_coverage_counts_participant_words_only(tmp_path: Path) -> None:
    whole = (
        "I typed kettle and it came back with descaler first, which is odd. "
        "Okay, um. I expected the kettles themselves at the top of the list."
    )
    f = score.fragmentation(_study(tmp_path), [_quote(whole, 0, 19)])
    # 26 of the participant's 39 words are inside the quote; the researcher's two
    # words count on neither side.
    assert f.coverage == round(26 / 39, 2)


_TASKS = {
    "session_id": "s1",
    "tasks": [
        {"label": "A", "start": 0, "end": 60},
        {"label": "B", "start": 60, "end": 120},
    ],
    "max_quotes_per_task": 2,
}


def test_cohesion_passes_only_when_every_task_is_quoted_within_the_cap() -> None:
    ok = [_quote("x", 0, 30), _quote("x", 30, 59), _quote("x", 60, 119)]
    assert score.cohesion(_TASKS, ok).passed

    over_cap = ok + [_quote("x", 40, 50)]
    result = score.cohesion(_TASKS, over_cap)
    assert result.per_task == [3, 1] and not result.passed

    missing = [_quote("x", 0, 30)]
    result = score.cohesion(_TASKS, missing)
    assert result.unquoted_tasks == ["B"] and not result.passed


def test_a_quote_running_into_the_next_task_is_a_crossing() -> None:
    result = score.cohesion(_TASKS, [_quote("x", 30, 90), _quote("x", 90, 110)])
    assert result.crossing == 1 and not result.passed
    # Ending a second into the next task is a timestamp's slack, not a crossing.
    assert score.cohesion(_TASKS, [_quote("x", 0, 61), _quote("x", 61, 110)]).crossing == 0


def test_the_saved_runs_score_as_the_lab_reports() -> None:
    tasks = json.loads((LAB / "fixture" / "tasks.json").read_text(encoding="utf-8"))
    verdicts = {}
    for path in sorted((LAB / "results").glob("*.json")):
        quotes = score.load_quotes(path)
        verdicts[path.stem] = score.cohesion(tasks, quotes).passed
        assert score.fragmentation(LAB / "fixture" / "transcripts", quotes).coverage >= 0.95
    assert verdicts == {
        "v0.2.0-claude-1": False,
        "v0.2.0-claude-2": False,
        "v0.2.0-openai-1": False,
        "v0.2.0-openai-2": False,
        "v0.3.0-claude-1": True,
        "v0.3.0-claude-2": True,
        "v0.3.0-openai-1": True,
        "v0.3.0-openai-2": True,
    }
