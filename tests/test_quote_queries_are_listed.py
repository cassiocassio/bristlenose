"""Every function in the server that reads Quote rows itself is listed, with why (the "which quotes
count" seam).

Hiding a quote discounts it as evidence, and a quote whose words moved to another speaker is out of
evidence altogether. The one function that answers "which quotes count" is
``speaker_slots.analysis_quotes`` (with ``evidence_quotes`` / ``evidence_out`` / ``counts`` beside
it). Five of the serious defects fixed in October 2026 were a consumer that read Quote rows itself
and forgot the filter, found one route at a time (RE#79 and its follow-ups). Per-route example
tests can only name the routes someone thought of, so this lists the *functions* that read Quote
through the ORM: a new one, or one more read inside a listed one, fails here until someone decides
whether it is a COUNT (go through ``analysis_quotes``) or a LOOKUP (an id, a DOM id, an import, the
filter itself) and says so below. Same family as ``tests/test_serve_export_coverage.py``.

This is a tripwire, not a census. It reads the syntax tree for ``query(...)`` / ``select(...)`` /
``join(...)`` / ``outerjoin(...)`` with ``Quote`` among the arguments (``query(Quote)``,
``query(Quote.id)``, ``.join(Quote, ...)``) and for ``db.get(Quote, id)``. It does not see
relationship traversal (``session.quotes``), raw SQL, or a reader that receives rows from
another function. The first version matched only ``query(Quote)`` and missed the joins and column
reads where the count-shaped consumers actually live (usual-suspects review, 6 Nov 2026), which is
why the key is a function and the match is the syntax tree.
"""

from __future__ import annotations

import ast
from pathlib import Path

SERVER = Path(__file__).parent.parent / "bristlenose" / "server"
_JOINS = {"query", "select", "join", "outerjoin"}

# Reason categories, so a reader can scan the table:
FILTER = "the filter itself"
IMPORT = "the import: writes and re-reads every row, hidden or not"
DEV = "dev-only inspection"
STATE = "researcher state by DOM id: needs hidden quotes too (the Quotes lens unhides)"
SCOPE = "scopes a tag/edit lookup to this project; not a count of evidence"
LOSS = "a loss the researcher confirms counts hidden tagging on purpose"
FILTERED = "a count that applies the evidence filter after the read"
CHOSEN = "rows for ids its caller chose; scoped-export tests filter upstream"

#: "file::function" -> (reads, why this one is not an unfiltered count).
LISTED: dict[str, tuple[int, str]] = {
    "speaker_slots.py::analysis_quotes": (1, FILTER),
    "speaker_slots.py::evidence_quotes": (1, FILTER),
    "speaker_slots.py::_moved_quotes": (1, FILTER),
    "importer.py::import_project": (1, IMPORT),
    "importer.py::_assign_ordinals": (1, IMPORT),
    "importer.py::_auto_tag_from_sentiment_field": (1, IMPORT),
    "importer.py::_cleanup_stale_data": (6, IMPORT),
    "importer.py::_get_or_create_quote": (1, IMPORT),
    "importer.py::_hide_wrong_speakers_quotes": (1, IMPORT),
    "importer.py::_import_quotes_from_clusters": (1, IMPORT),
    "importer.py::_import_quotes_from_themes": (1, IMPORT),
    "importer.py::_missing_output": (1, IMPORT),
    "importer.py::_pinned_quote_ids": (5, IMPORT),
    "importer.py::_prune_arrangements": (1, IMPORT),
    "routes/data.py::_quote_ids_for_project": (1, STATE),
    "routes/data.py::_resolve_quote": (1, STATE),
    "routes/data.py::get_deleted_badges": (1, STATE),
    "routes/data.py::get_edits": (1, STATE),
    "routes/data.py::get_hidden": (1, STATE),
    "routes/data.py::get_starred": (1, STATE),
    "routes/data.py::get_tags": (1, STATE),
    "routes/data.py::put_starred": (1, STATE),
    "routes/dev.py::_aggregate_sentiments": (1, DEV),
    "routes/dev.py::codebook_lab_candidates": (1, DEV),
    "routes/dev.py::codebook_lab_tags": (2, DEV),
    "routes/codebook.py::_rehome_human_applications": (1, SCOPE),
    "routes/codebook.py::remove_framework": (1, SCOPE),
    "routes/codebook.py::remove_framework_impact": (1, LOSS),
    "routes/codebook.py::_tag_tentative_counts": (1, FILTERED + " (pending proposals; tested)"),
    "routes/autocode.py::get_proposals": (2, FILTERED + " (_counted_quote_ids)"),
    "routes/dashboard.py::get_dashboard": (1, FILTERED + " (`if quote_id in counted`)"),
    "routes/discussion.py::_report_quotes": (1, "edits lookup; rows come from evidence_quotes"),
    "routes/transcript.py::get_transcript": (1, "shows a hidden quote on purpose; speaker_slots.counts"),
    "routes/clips_export.py::_load_starred_quotes": (2, FILTERED + " (evidence_out)"),
    "routes/clips_export.py::_load_corrections": (2, "edits near a clip: a lookup"),
    "export_core.py::_load_all_visible": (2, FILTERED + " (evidence_out)"),
    "export_core.py::_resolve_quote_ids": (1, CHOSEN),
    "routes/screens_export.py::_hidden_dom_ids": (1, "builds the set of hidden DOM ids: must see all"),
    "miro_export.py::load_pauses": (1, CHOSEN),
    "journey.py::derive_journeys_with_anchors": (
        1, "a hidden quote keeps its journey step (owner, 22 Oct 2026); evidence_quotes gates it"),
    "routes/codebook_builder.py::_coded_quotes": (
        2, "KNOWN GAP: counts hidden exemplars; pinned strict in"
           " tests/test_hidden_counts_nowhere_exemplars.py until the owner rules"),
}


def _names(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _reads(source: str) -> dict[str, int]:
    """Quote reads per enclosing function in one module (``<module>`` outside any function)."""
    found: dict[str, int] = {}

    def visit(node: ast.AST, fn: str | None) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn = node.name
        if isinstance(node, ast.Call):
            f = node.func
            attr = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
            hit = False
            if attr in _JOINS:
                hit = any("Quote" in _names(a) for a in node.args)
            elif attr == "get" and isinstance(f, ast.Attribute) and node.args:
                first = node.args[0]
                hit = isinstance(first, ast.Name) and first.id == "Quote"
            if hit:
                found[fn or "<module>"] = found.get(fn or "<module>", 0) + 1
        for child in ast.iter_child_nodes(node):
            visit(child, fn)

    visit(ast.parse(source), None)
    return found


def _census() -> dict[str, int]:
    out: dict[str, int] = {}
    for path in sorted(SERVER.rglob("*.py")):
        rel = path.relative_to(SERVER).as_posix()
        for fn, n in _reads(path.read_text(encoding="utf-8")).items():
            out[f"{rel}::{fn}"] = n
    return out


def test_the_census_sees_the_shapes_the_first_version_missed() -> None:
    # The gate's own proof of reach: a bare query, a column query, a join and a get.
    src = (
        "def a(db):\n    return db.query(Quote).all()\n"
        "def b(db):\n    return db.query(Quote.id).all()\n"
        "def c(db):\n    return db.query(QuoteTag).join(Quote, QuoteTag.quote_id == Quote.id)\n"
        "def d(db, i):\n    return db.get(Quote, i)\n"
        "def e(db):\n    return db.query(QuoteTag).all()\n"
    )
    assert _reads(src) == {"a": 1, "b": 1, "c": 1, "d": 1}


def test_every_function_that_reads_quote_rows_is_listed_with_its_reason() -> None:
    found = _census()
    unlisted = {k: n for k, n in found.items() if k not in LISTED}
    grown = {k: (n, LISTED[k][0]) for k, n in found.items() if k in LISTED and n > LISTED[k][0]}
    assert not unlisted and not grown, (
        "A new read of Quote rows. Decide: is it a COUNT (use speaker_slots.analysis_quotes) or a "
        "LOOKUP (an id, an import, the filter itself)? Then list its function in LISTED with a "
        "reason that says which, and does not just repeat a neighbour's. "
        f"Unlisted: {unlisted}. Grown: {grown}."
    )


def test_a_listed_function_that_stopped_reading_quote_is_dropped_from_the_list() -> None:
    found = _census()
    stale = {k: (found.get(k, 0), n) for k, (n, _) in LISTED.items() if found.get(k, 0) < n}
    assert not stale, f"List is out of date (fewer reads than listed): {stale}"
