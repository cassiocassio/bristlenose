"""The felt-reliability register agrees with itself (`docs/reliability-register.md`).

The caller that makes `scripts/check-reliability-register.py` a gate: CI runs
pytest, so a hand-typed score or a priority that disagrees with its row's
frequency and cost fails the build rather than drifting.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "check_reliability_register", ROOT / "scripts" / "check-reliability-register.py"
)
assert _spec and _spec.loader
reg = importlib.util.module_from_spec(_spec)
# A path-loaded module holding a @dataclass must be registered before it runs.
sys.modules[_spec.name] = reg
_spec.loader.exec_module(reg)


def test_the_register_agrees_with_itself() -> None:
    problems = reg.check(reg.REGISTER.read_text(encoding="utf-8"))
    assert problems == [], "\n".join(problems)


def test_priority_rule() -> None:
    assert reg.priority("some", "high") == "P1"
    assert reg.priority("rare", "high") == "P2"
    assert reg.priority("most", "med") == "P1"
    assert reg.priority("some", "med") == "P2"
    assert reg.priority("rare", "med") == "P3"
    assert reg.priority("every", "low") == "P2"
    assert reg.priority("some", "low") == "P3"


def _doc(rows: str) -> str:
    body = "\n".join([
        "| # | Meets | Class | Freq | Cost | P | Status | Where |",
        "|---|---|---|---|---|---|---|---|",
        rows,
        "",
        reg.SCORE_BEGIN,
        reg.SCORE_END,
    ])
    rows_, _ = reg.parse(body)
    return reg.rewrite(body, rows_, record=False, today="2026-10-19")


def test_each_check_can_fail() -> None:
    good = _doc("| R1 | a thing | FAKE | some | high | P1 | open | x.py:1 |")
    assert reg.check(good) == []

    wrong_p = good.replace("| P1 |", "| P3 |")
    assert any("rule says P1" in p for p in reg.check(wrong_p))

    stale = good.replace("| open |", "| fixed abc1234 |")
    assert any("score block is stale" in p for p in reg.check(stale))

    bare_fix = _doc("| R1 | a thing | FAKE | some | high | P1 | fixed | x.py:1 |")
    assert any("names no commit" in p for p in reg.check(bare_fix))

    dup = _doc(
        "| R1 | a | FAKE | some | high | P1 | open | x |\n"
        "| R1 | b | DEAD | rare | low | P3 | open | y |"
    )
    assert any("id used twice" in p for p in reg.check(dup))

    bad_class = _doc("| R1 | a | FLAKY | some | high | P1 | open | x |")
    assert any("unknown class" in p for p in reg.check(bad_class))


def test_record_replaces_todays_line() -> None:
    body = _doc("| R1 | a | FAKE | some | high | P1 | open | x |") + (
        f"\n{reg.LOG_BEGIN}\n| 2026-10-19 | 9 | 9 | 9 | 9 | 9 | 9 |\n{reg.LOG_END}\n"
    )
    rows, _ = reg.parse(body)
    out = reg.rewrite(body, rows, record=True, today="2026-10-19")
    assert out.count("| 2026-10-19 |") == 1
    assert "| 2026-10-19 | 1 | 0 | 1 | 1 | 0 | 0 |" in out
