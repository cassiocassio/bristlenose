"""SECURITY.md says the feedback form posts to us (T23, trust map rows 61 and 69).

It said "nothing is sent to us, ever" while the feedback form posts the version, a rating and
the typed message to bristlenose.app when you press Send. A claim about what leaves the machine
has to name every case, so the host the form posts to must appear in the document.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from bristlenose.server.routes.health import DEFAULT_FEEDBACK_URL

_TEXT = (Path(__file__).parents[1] / "SECURITY.md").read_text(encoding="utf-8")


def test_the_host_the_feedback_form_posts_to_is_named_as_receiving_feedback() -> None:
    host = urlparse(DEFAULT_FEEDBACK_URL).hostname
    assert host
    assert any(host in line and "feedback" in line.lower() for line in _TEXT.splitlines())


def test_it_no_longer_says_nothing_is_ever_sent() -> None:
    assert "nothing is sent to us, ever" not in _TEXT
