"""A quote the researcher hid is not an exemplar either (found by the defect-mining pass, 5 Nov 2026).

Hiding a quote discounts it as evidence (owner, 22 Oct 2026): Signals, the sentiment bars, the
featured quotes, the clip export, the codebook counts and the builder's candidate scan all leave it
out (``tests/test_serve_hidden_counts_nowhere.py``). The dynamic codebook builder's own coded
quotes (``routes/codebook_builder._coded_quotes``, the exemplars a tag's prompt is synthesised
from, and the count that says "ready to synthesize") are read with no such filter: a hidden quote
still carrying the tag is counted, and its words are sent to the model as a definition's evidence.

Ruled 6 Nov 2026: hidden means hidden, exemplars included. ``_coded_quotes`` goes through
``speaker_slots.analysis_quotes``; this test was a strict xfail until then.

The setup (the hide, and proof that it took) lives in a fixture, outside the xfail, and the xfail
names ``AssertionError``: a broken setup is an ERROR and a changed route is an exception, never
a quiet "expected failure" that hides a pin gone stale.
"""

from __future__ import annotations

import pytest

from bristlenose.server.grounding import quote_dom_id
from bristlenose.server.models import Quote
from tests.test_codebook_builder import client_with_coded_tag  # noqa: F401  (fixture)
from tests.test_serve_hidden_counts_nowhere import _hide


def _coded_count(client, tag_id: int) -> int:
    resp = client.get(f"/api/projects/1/codebook/tags/{tag_id}/builder")
    assert resp.status_code == 200
    return resp.json()["coded_count"]


@pytest.fixture()
def one_coded_quote_hidden(client_with_coded_tag):  # noqa: F811
    client, tag_id = client_with_coded_tag
    assert _coded_count(client, tag_id) == 3  # the fixture codes the first three quotes
    db = client.app.state.db_factory()
    try:
        first = db.query(Quote).filter_by(project_id=1).order_by(Quote.id).first()
        dom = quote_dom_id(first.participant_id, first.start_timecode, first.ordinal)
    finally:
        db.close()
    _hide(client, dom)
    hidden = client.get("/api/projects/1/hidden").json()
    assert hidden.get(dom) is True, "the hide did not take: the pin below would prove nothing"
    return client, tag_id


def test_a_hidden_quote_is_not_counted_as_an_exemplar(one_coded_quote_hidden) -> None:
    client, tag_id = one_coded_quote_hidden
    assert _coded_count(client, tag_id) == 2
