"""Every place the server reads Quote rows directly is listed, with why (the "which quotes count" seam).

Hiding a quote discounts it as evidence, and a quote whose words moved to another speaker is out of
evidence altogether. The one function that answers "which quotes count" is
``speaker_slots.analysis_quotes`` (with ``evidence_quotes`` / ``evidence_out`` / ``counts`` beside
it). Five of the serious defects fixed in October 2026 were a consumer that read Quote rows itself
and forgot the filter, found one route at a time (RE#79 and its follow-ups). Per-route example
tests can only name the routes someone thought of, so this lists the *files* that query Quote
directly: a new file, or one more query in a listed file, fails here until someone decides whether
the new read is a COUNT (go through ``analysis_quotes``) or a LOOKUP (an id, a DOM id, an import,
the filter itself) and says so below. Same shape as ``tests/test_serve_export_coverage.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

SERVER = Path(__file__).parent.parent / "bristlenose" / "server"
_QUERY = re.compile(r"\b(?:query|select)\(\s*Quote\s*[,)]")

#: file (relative to bristlenose/server) -> (direct Quote queries, why they are not a count).
LISTED: dict[str, tuple[int, str]] = {
    "importer.py": (8, "writes and re-reads every row, hidden or not: the import is the source"),
    "routes/data.py": (7, "resolves a DOM id to its row and writes researcher state; needs all"),
    "speaker_slots.py": (2, "the filter itself: analysis_quotes and the evidence helpers"),
    "routes/dev.py": (2, "dev-only inspection"),
    "export_core.py": (2, "a lookup by participant, and a read that then applies evidence_out"),
    "routes/transcript.py": (1, "shows a hidden quote on purpose; applies speaker_slots.counts"),
    "routes/screens_export.py": (1, "builds the set of hidden DOM ids, so it must see all"),
    "routes/clips_export.py": (2, "joins QuoteState and applies evidence_out; and a lookup of edits near a clip"),
    "miro_export.py": (1, "rows for ids its caller chose; the scoped-export tests filter upstream"),
    "journey.py": (1, "a hidden quote keeps its journey step; evidence_quotes gates it (owner)"),
    "routes/codebook_builder.py": (
        1, "KNOWN GAP: _coded_quotes counts hidden exemplars; pinned strict in"
           " tests/test_hidden_counts_nowhere_exemplars.py until the owner rules"),
}


def _found() -> dict[str, int]:
    out: dict[str, int] = {}
    for path in SERVER.rglob("*.py"):
        n = len(_QUERY.findall(path.read_text(encoding="utf-8")))
        if n:
            out[path.relative_to(SERVER).as_posix()] = n
    return out


def test_every_direct_quote_query_is_listed_with_its_reason() -> None:
    found = _found()
    unlisted = {f: n for f, n in found.items() if f not in LISTED}
    grown = {f: (n, LISTED[f][0]) for f, n in found.items() if f in LISTED and n > LISTED[f][0]}
    assert not unlisted and not grown, (
        "A new direct read of Quote rows. Decide: is it a COUNT (use "
        "speaker_slots.analysis_quotes) or a LOOKUP (an id, an import, the filter itself)? "
        f"Then list it in LISTED with the reason. Unlisted: {unlisted}. Grown: {grown}."
    )


def test_a_listed_file_that_stopped_querying_quote_is_dropped_from_the_list() -> None:
    found = _found()
    stale = {f: n for f, (n, _) in LISTED.items() if found.get(f, 0) < n}
    assert not stale, f"List is out of date (fewer queries than listed): {stale}"
