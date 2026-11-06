"""A quote the researcher hid is not an exemplar either (found by the defect-mining pass, 5 Nov 2026).

Hiding a quote discounts it as evidence (owner, 22 Oct 2026): Signals, the sentiment bars, the
featured quotes, the clip export, the codebook counts and the builder's candidate scan all leave it
out (``tests/test_serve_hidden_counts_nowhere.py``). The dynamic codebook builder's own coded
quotes (``routes/codebook_builder._coded_quotes``, the exemplars a tag's prompt is synthesised
from, and the count that says "ready to synthesize") are read with no such filter: a hidden quote
still carrying the tag is counted, and its words are sent to the model as a definition's evidence.

Pinned strict because the rule's reach over exemplars is the owner's to rule on (they are the
researcher's own hand-coding, which hiding may not be meant to undo); if the ruling is "hidden
means hidden", delete the xfail and fix ``_coded_quotes`` to go through
``speaker_slots.analysis_quotes``. Same shape as the other pins that wait on a ruling.
"""

from __future__ import annotations

import pytest

from bristlenose.server.models import Quote
from tests.test_codebook_builder import client_with_coded_tag  # noqa: F401  (fixture)
from tests.test_serve_hidden_counts_nowhere import _hide


def _coded_count(client, tag_id: int) -> int:
    resp = client.get(f"/api/projects/1/codebook/tags/{tag_id}/builder")
    assert resp.status_code == 200
    return resp.json()["coded_count"]


def test_the_exemplar_count_starts_at_the_coded_quotes(client_with_coded_tag) -> None:  # noqa: F811
    client, tag_id = client_with_coded_tag
    assert _coded_count(client, tag_id) == 3


@pytest.mark.xfail(strict=True, reason="awaits the owner's ruling: does hidden discount an exemplar?")
def test_a_hidden_quote_is_not_counted_as_an_exemplar(client_with_coded_tag) -> None:  # noqa: F811
    client, tag_id = client_with_coded_tag
    db = client.app.state.db_factory()
    try:
        first = db.query(Quote).filter_by(project_id=1).order_by(Quote.id).first()
        dom = f"q-{first.participant_id}-{int(first.start_timecode)}"
    finally:
        db.close()
    _hide(client, dom)
    assert _coded_count(client, tag_id) == 2
