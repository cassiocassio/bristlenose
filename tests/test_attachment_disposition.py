"""`attachment_disposition` — the download header every named export uses.

Header-level facts, so they are tested on the string: what an HTTP stack
refuses (control characters), what a save dialog misreads (bidi overrides),
and what a browser decodes on its own (a bare `filename` with `%20`).
"""

from __future__ import annotations

from urllib.parse import unquote

import pytest

from bristlenose.server.export_core import attachment_disposition


def _star(header: str) -> str:
    assert "filename*=UTF-8''" in header, header
    return unquote(header.split("filename*=UTF-8''", 1)[1])


def test_an_ascii_name_still_carries_filename_star():
    """Chromium percent-decodes a bare `filename`, so `100%20 study` would save
    as `100 study`; with `filename*` present it reads that instead."""
    h = attachment_disposition("100%20 study-quotes.csv")
    assert _star(h) == "100%20 study-quotes.csv"
    assert "%2520" in h  # the % itself is encoded, not passed through


@pytest.mark.parametrize("bad", ["\x0b", "\x1f", "\x7f", "\t", "‮", "⁦"])
def test_control_and_bidi_characters_never_reach_the_header(bad):
    h = attachment_disposition(f"a{bad}b-figjam-board.json")
    assert bad not in h
    assert h.isascii()
    assert _star(h) == "ab-figjam-board.json"


def test_slash_is_encoded_even_if_a_caller_forgot_safe_filename():
    assert "%2F" in attachment_disposition("a/b.json")


def test_a_non_latin_name_round_trips_with_an_ascii_fallback():
    h = attachment_disposition("駅の調査-quotes.csv")
    assert h.isascii()
    assert 'filename="____-quotes.csv"' in h
    assert _star(h) == "駅の調査-quotes.csv"
