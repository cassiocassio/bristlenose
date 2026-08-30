"""Python side of the cross-language URL-safety contract.

Reads the same ``tests/fixtures/safe-url-contract.json`` as
``frontend/src/utils/safeUrl.test.ts``.  A language that disagrees fails its own
suite with the offending URL named.

Sibling of ``test_shared_format_contract.py``, which does this for *rendered*
formats.  The difference is what a mismatch costs: there, a visible
inconsistency; here, a hole.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bristlenose.utils.safe_url import (
    ALLOWED_SCHEMES,
    CONFIG_SCHEMES,
    is_safe_url,
    safe_url_or_none,
)

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "safe-url-contract.json"
_CASES = json.loads(_FIXTURE.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", _CASES, ids=lambda c: c["why"][:44])
def test_contract_case(case: dict) -> None:
    assert is_safe_url(case["url"]) is case["safe"], case["why"]


def test_unsafe_urls_return_none_rather_than_a_string() -> None:
    """A caller that forgets to check the bool must still not get a URL."""
    for case in _CASES:
        if not case["safe"]:
            assert safe_url_or_none(case["url"]) is None, case["why"]


def test_the_allowlist_is_an_allowlist() -> None:
    """Three schemes. If this grows, the Swift and TypeScript sides grow with it."""
    assert ALLOWED_SCHEMES == {"http", "https", "mailto"}


def test_non_strings_are_refused() -> None:
    for value in (None, 0, [], {}, True):
        assert is_safe_url(value) is False  # type: ignore[arg-type]


def test_every_shipped_codebook_link_passes() -> None:
    """The nine curated codebooks must not themselves trip the guard.

    A rule that rejects our own data is a rule nobody will keep.
    """
    import yaml

    codebooks = Path(__file__).resolve().parent.parent / "bristlenose" / "server" / "codebook"
    checked = 0
    for path in sorted(codebooks.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for link in data.get("author_links") or []:
            url = link.get("url") if isinstance(link, dict) else link
            if not url:
                continue
            checked += 1
            assert is_safe_url(url), f"{path.name}: {url}"
    assert checked > 0, "no author_links found — has the YAML shape changed?"


def test_config_schemes_are_narrower_than_href_schemes() -> None:
    """Two questions, two answers.

    ``ALLOWED_SCHEMES`` answers "may this be an href at all" -- the right
    question for a URL the researcher reached. ``CONFIG_SCHEMES`` answers "may a
    stranger put this in our corpus", which is not the same question and must
    not inherit the same answer.
    """
    assert CONFIG_SCHEMES == {"https"}
    assert CONFIG_SCHEMES < ALLOWED_SCHEMES


def test_plain_http_is_refused_from_config_but_allowed_as_an_href() -> None:
    assert is_safe_url("http://example.org/") is True
    assert is_safe_url("http://example.org/", CONFIG_SCHEMES) is False


def test_parse_time_gate_drops_an_unsafe_link(tmp_path) -> None:
    """The gate is at parse time, so no renderer can be the one that forgot."""
    from bristlenose.server.codebook import _parse_template  # type: ignore[attr-defined]

    raw = {
        "id": "x", "title": "X", "description": "d",
        "author_links": [
            {"label": "real", "url": "https://example.org/"},
            {"label": "nngroup.com", "url": "javascript:alert(1)"},
            {"label": "downgrade", "url": "http://example.org/"},
        ],
        "subtitle": "s",
        "groups": [{"name": "G", "subtitle": "gs", "colour_set": "ux", "tags": [{"name": "t"}]}],
    }
    tmpl = _parse_template(raw, "x.yaml")
    assert [u for _, u in tmpl.author_links] == ["https://example.org/"]
