"""The quote DOM id has one builder and one parser (R86).

``q-{participant}-{int(start)}`` for the first quote a speaker starts in a
second, ``-{ordinal}`` appended for every later one. Ordinal 0 keeps the form
every stored key, URL anchor and Screens card already uses.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from bristlenose.server.grounding import parse_quote_dom_id, quote_dom_id

_ROOT = Path(__file__).parent.parent / "bristlenose"


class TestBuilder:
    def test_ordinal_zero_is_todays_form(self) -> None:
        assert quote_dom_id("p1", 123.9, 0) == "q-p1-123"

    def test_a_later_quote_in_the_second_carries_its_ordinal(self) -> None:
        assert quote_dom_id("p1", 123.0, 1) == "q-p1-123-1"
        assert quote_dom_id("m2", 0.0, 3) == "q-m2-0-3"

    @pytest.mark.parametrize("dom_id", ["q-p1-10", "q-p1-10-1", "q-m12-3599-7", "q-p1-0"])
    def test_build_and_parse_round_trip(self, dom_id: str) -> None:
        pid, start, ordinal = parse_quote_dom_id(dom_id)
        assert quote_dom_id(pid, start, ordinal) == dom_id


class TestParser:
    def test_cases(self) -> None:
        assert parse_quote_dom_id("q-p1-10") == ("p1", 10, 0)
        assert parse_quote_dom_id("q-p1-10-1") == ("p1", 10, 1)
        assert parse_quote_dom_id("q-long-name-123") == ("long-name", 123, 0)

    @pytest.mark.parametrize("bad", ["q-p1-10-x", "q-p1-x", "q-p1", "p1-10", "q--10",
                                     "q-p1-1_0", "q-p1-10- 1", "q-p1-10-", "q-p1-١"])
    def test_rejects(self, bad: str) -> None:
        with pytest.raises(ValueError):
            parse_quote_dom_id(bad)


#: Every spelling of a built id: an f-string in either quote, concatenation, ``%`` and
#: ``.format`` templates, and a Jinja expression. A gate that knows one spelling cannot fail
#: for the next.
_BUILT_ID = re.compile(r"""f["']q-\{|["']q-["']\s*\+|["']q-\{\}|["']q-%|q-\{\{""")


def test_dom_ids_are_built_in_one_place() -> None:
    """No quote id is built outside the helper: a second builder is how the ordinal gets
    forgotten."""
    builders = sorted(
        f"{f.relative_to(_ROOT.parent)}:{n}"
        for f in _ROOT.rglob("*")
        if f.suffix in {".py", ".html", ".j2", ".jinja", ".jinja2", ".js", ".ts", ".tsx"}
        and f.name != "grounding.py"
        for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1)
        if _BUILT_ID.search(line)
    )
    assert builders == [], f"quote DOM ids built outside grounding.quote_dom_id: {builders}"


def test_the_gate_knows_each_spelling() -> None:
    for spelling in ('f"q-{pid}-{s}"', "f'q-{pid}'", '"q-" + pid', '"q-{}-{}".format(a, b)',
                     '"q-%s-%d" % (a, b)', 'id="q-{{ q.participant_id }}"'):
        assert _BUILT_ID.search(spelling), spelling
    for innocent in ('"q-p1-10"', "quote_dom_id(pid, start)", "`q-{participant}-{start}`"):
        assert not _BUILT_ID.search(innocent), innocent
