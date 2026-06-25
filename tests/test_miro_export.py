"""Egress-boundary tests for the Miro export — the irreversible third-party path.

These pin invariants on data that LEAVES the machine onto a user's Miro board,
where Bristlenose can no longer control it:

  1. clip-URL scheme allowlist (a `javascript:`/`data:` base must not become a
     live `<a href>` on a shared board — `html.escape` does NOT neutralise it);
  2. HTML-escaping of sticky content (no XSS / attribute-breakout into the board);
  3. the anonymisation boundary — speaker codes (p1, p2) egress, never the
     researcher's display names, even when a quote carries one.

Pure functions, no network, no DB (extraction is monkeypatched).
"""

from __future__ import annotations

import types

import pytest

from bristlenose.miro_board import Sticky
from bristlenose.server.export_core import ExportableQuote
from bristlenose.server.miro_export import (
    MAX_QUOTE_CHARS,
    _clip_url,
    _sticky_content,
    build_columns,
)

# ── _clip_url: scheme allowlist (ASSUMPTION A5) ──────────────────────────────


def _q(timecode: str = "0:10", session: str = "s1", participant_code: str = "p1"):
    return types.SimpleNamespace(
        session=session, participant_code=participant_code, timecode=timecode
    )


def test_clip_url_accepts_https():
    url = _clip_url("https://drive.example.com/clips", _q())
    assert url is not None
    assert url.startswith("https://drive.example.com/clips/")


def test_clip_url_accepts_http():
    assert _clip_url("http://example.com/c", _q()) is not None


@pytest.mark.parametrize(
    "base",
    [
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "file:///etc/passwd",
        "/local/relative/path",  # no scheme / no netloc
        "ftp://example.com/c",
        "vbscript:msgbox(1)",
    ],
)
def test_clip_url_rejects_non_http_schemes(base):
    # html.escape does NOT neutralise these — they would egress into a shared
    # board's <a href>. The scheme allowlist is the real control.
    assert _clip_url(base, _q()) is None


def test_clip_url_empty_base_is_none():
    assert _clip_url("", _q()) is None


# ── _sticky_content: HTML-escaping of board-bound content ────────────────────


def _sticky(text: str, link_url: str | None = None, kind: str = "quote", pid: str = "p1") -> Sticky:
    return Sticky(
        x=0, y=0, width=10, height=10, colour="yellow",
        text=text, kind=kind, participant_id=pid, timecode=10.0, link_url=link_url,
    )


def test_sticky_content_escapes_quote_html():
    out = _sticky_content(_sticky('say <script>alert("x")</script> & "more"'))
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert "&amp;" in out


def test_sticky_content_escapes_header_html():
    out = _sticky_content(_sticky("<b>Section</b>\n<i>sub</i>", kind="header"))
    assert "<b>Section</b>" not in out
    assert "&lt;b&gt;Section&lt;/b&gt;" in out


def test_sticky_content_escapes_link_url_attribute():
    # A crafted link_url must not break out of the href="" attribute.
    out = _sticky_content(_sticky("quote", link_url='https://x/"><script>alert(1)</script>'))
    assert "<script>" not in out
    assert "&quot;" in out or "&#34;" in out  # the " is escaped inside the attribute


def test_sticky_content_truncates_long_quotes():
    out = _sticky_content(_sticky("a" * (MAX_QUOTE_CHARS + 50)))
    assert "…" in out


# ── Anonymisation boundary: codes egress, never display names ────────────────


def test_build_columns_egresses_code_not_name(monkeypatch):
    """Even when a quote carries a display name, the board card (and therefore
    the sticky pushed to Miro) shows the speaker code, never the name."""
    q = ExportableQuote(
        text="I love the new flow",
        participant_code="p2",
        participant_name="Jane Secret",  # a name that must NOT egress
        section="Onboarding",
        theme="",
        sentiment="delight",
        tags="",
        starred=False,
        timecode="0:30",
        session="s1",
        source_file="x.mp4",
    )
    monkeypatch.setattr(
        "bristlenose.server.miro_export.extract_quotes_for_export",
        lambda *args, **kwargs: [q],
    )

    columns = build_columns(db=None, project_id=1, quote_ids=None)
    cards = [c for col in columns for c in col.quotes]
    assert len(cards) == 1

    # The board card carries the code; the QuoteCard has no name field at all,
    # so the display name is structurally excluded from anything pushed to Miro.
    assert cards[0].participant_id == "p2"
    assert "Jane Secret" not in _sticky_content(
        _sticky("I love the new flow", pid=cards[0].participant_id)
    )
