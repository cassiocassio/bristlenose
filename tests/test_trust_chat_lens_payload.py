"""Trust gate: nothing handed to the model by the chat lens carries a participant's real name.

The corpus assembler is pinned by ``test_trust_chat_lens_corpus.py``. This is the same promise
one step later: the whole ask flow runs with a name planted through the people API, and every
argument of every model call (the answer and the support check) is searched. The name is
reachable (it is in the database, and the API returns it), the corpus is in the payload, and the
participant is cited by code. Proven by making ``_quote_line`` emit the display name: it fails.
"""

from __future__ import annotations

from tests.test_trust_planted_name import _ask, _carries_name, _payload, planted  # noqa: F401


def test_the_payload_handed_to_the_model_carries_no_display_name(planted) -> None:  # noqa: F811
    _, client = planted
    payload = _payload(_ask(client))
    assert "<untrusted_corpus_" in payload, "positive control: the corpus reached the model"
    assert "(p1" in payload, "positive control: the participant is cited by code"
    assert not _carries_name(payload)
