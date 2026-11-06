"""The chat lens grounds on codes only: the corpus handed to the model never carries a display name.

Tested on the corpus assembler itself (grounding.assemble_corpus_context), with a positive control that the
corpus is non-empty and cites the participant by CODE. The earlier version went through the whole ask flow and
passed with the guard removed (audit n6a1, 6 Nov 2026). Proven with docs/private/trust-map/audit_tools.py
mutate: making _quote_line emit a display name must fail it.
"""

from __future__ import annotations

from pathlib import Path

import bristlenose
from bristlenose.server.grounding import assemble_corpus_context
from tests.test_trust_planted_name import _carries_name, planted  # noqa: F401


def test_imports_this_tree() -> None:
    assert Path(bristlenose.__file__).is_relative_to(Path(__file__).parents[1])


def _corpus_text(app) -> str:
    db = app.state.db_factory()
    try:
        ctx = assemble_corpus_context(db, 1)
    finally:
        db.close()
    return "\n".join(str(getattr(ctx, f, "")) for f in ("text", "corpus", "prompt")) + repr(ctx)


def test_corpus_cites_by_code_and_carries_no_name(planted) -> None:  # noqa: F811
    app, _client = planted
    text = _corpus_text(app)
    assert "p1" in text, "positive control: the corpus must be non-empty and cite p1 by code"
    assert not _carries_name(text), "a display name reached the chat-lens corpus"
