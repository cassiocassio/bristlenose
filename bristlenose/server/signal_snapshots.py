"""Storage boundary for completed Signals-lens snapshots.

The reader deliberately has no signal calculation or LLM dependency.  Writing
is restricted to the LLM-backed codebook/new-interview lifecycle callers; hand
curation never writes here.  A researcher's hide does change what the reader
returns, though: ``filter_snapshot_to_counted`` removes what no longer counts
on every read (docs/design-signals-follow-hide.md), and only ever removes.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from bristlenose.server.elaboration import compute_quote_reference
from bristlenose.server.models import Quote, SignalSnapshot
from bristlenose.signals.generic_detect import QuoteRecord

logger = logging.getLogger(__name__)

# A corrupt newest row is rare; look past a handful of rows, not the whole
# history, so a read stays cheap however many snapshots have accumulated.
_READ_WINDOW = 8

# This is a reader-contract version, deliberately separate from the database
# migration revision.  A release can improve the LLM-written narrative shape
# without changing SQLite.  On the next sidecar start, an older frozen report
# is refreshed once if a cloud provider is available; offline readers keep the
# last good report rather than receiving a blank lens or a maintenance task.
SIGNAL_SNAPSHOT_PAYLOAD_VERSION = 4


def store_completed_snapshot(
    db: Session,
    project_id: int,
    *,
    source: str,
    payload: Mapping[str, Any],
) -> SignalSnapshot:
    """Append one complete response payload and return its durable row."""
    snapshot = SignalSnapshot(
        project_id=project_id,
        source=source,
        payload_version=SIGNAL_SNAPSHOT_PAYLOAD_VERSION,
        payload=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def latest_completed_snapshot(db: Session, project_id: int) -> SignalSnapshot | None:
    """Return the newest readable snapshot without calculating anything.

    Snapshot writes are atomic, but an old development build, a manual SQLite
    repair, or future payload migration can still leave an unreadable row.
    The reader's job is to preserve the last good report, not turn that one bad
    row into an unavailable Signals lens.
    """
    snapshots = (
        db.query(SignalSnapshot)
        .filter_by(project_id=project_id)
        .order_by(SignalSnapshot.computed_at.desc(), SignalSnapshot.id.desc())
        .limit(_READ_WINDOW)
        .all()
    )
    for snapshot in snapshots:
        try:
            snapshot_payload(snapshot)
        except (TypeError, ValueError):
            # Ids only: the payload holds participant quotes.
            logger.warning(
                "Skipping unreadable signal snapshot %s for project %s",
                snapshot.id, project_id,
            )
            continue
        return snapshot
    return None


def snapshot_payload(snapshot: SignalSnapshot) -> dict[str, Any]:
    """Decode a row at the reader boundary, failing loudly on corrupt storage."""
    payload = json.loads(snapshot.payload)
    if not isinstance(payload, dict):
        raise ValueError(f"Signal snapshot {snapshot.id} payload is not an object")
    return payload


def signal_quote_record(quote: Quote, tag_names: list[str] | None = None) -> QuoteRecord:
    """The record the Signals route builds from a database quote.

    This is the single place it is built, so the reference stored in every
    snapshot (``quote_id``, an assertion's ``source_quote_id``) and the one
    derived from a row later cannot drift apart. The shape is deliberate and
    frozen in snapshot payload v4: no segment index and no ordinal, so those
    are the dataclass defaults (-1 and 0) whatever the row holds. The chat
    lens and MCP build theirs with the row's real values
    (``grounding.py``); the two are not unified, because that would change
    every stored reference and every elaboration cache key.
    """
    return QuoteRecord(
        text=quote.text,
        participant_id=quote.participant_id,
        session_id=quote.session_id,
        start_seconds=quote.start_timecode,
        intensity=quote.intensity,
        tag_names=tag_names if tag_names is not None else [],
    )


def quote_reference_for_row(quote: Quote) -> str:
    """The reference a snapshot holds for this database quote (payload v4 shape)."""
    return compute_quote_reference(signal_quote_record(quote))


_MATRIX_BY_SOURCE = {"section": "section_matrix", "theme": "theme_matrix"}


def filter_snapshot_to_counted(
    payload: dict[str, Any], counted_refs: Mapping[str, int] | set[str] | frozenset[str],
) -> dict[str, Any]:
    """Remove what no longer counts from a decoded snapshot, in place, and return it.

    A snapshot is built once and read many times; a hide made in between must not
    leave the quote on its card, in the count, or in the HTML export. The filter
    only removes, so the reader stays free of any signal calculation or LLM call
    (docs/design-signals-follow-hide.md):

    - a card keeps a quote only if its ``quote_id`` is in ``counted_refs``. Pass a
      ``Counter`` (how many counted quotes share each reference) and a card keeps at
      most that many entries per reference, so hiding one of two identical rows removes
      one entry and not neither; a plain set keeps every entry whose reference is in it;
    - an evidence assertion that cites a quote no longer counted is dropped, and
      ``had_evidence_assertions`` records that the card had some, so the reader
      does not fall back to prose that was written over every quote;
    - ``participants`` and ``count`` follow the remaining quotes;
    - a card left with no counted quote is dropped;
    - the card's cell in its matrix loses each removed quote (count, participant
      tally, one intensity, the row, column and grand totals).

    Strength, concentration, ranking, headline and claim are left as calculated.
    ``weighted_count`` is left too: it needs the quote's group weight, which the
    payload does not carry. A quote that was already out of the evidence when the
    snapshot was built is not in it, so nothing here can bring it back.
    """
    for codebook in payload.get("codebooks") or []:
        kept_signals: list[dict[str, Any]] = []
        for signal in codebook.get("signals") or []:
            quotes = signal.get("quotes") or []
            kept, removed = _split_quotes(quotes, counted_refs)
            if removed:
                _subtract_from_matrix(codebook, signal, removed)
            if quotes and not kept:
                continue  # nothing visible supports this signal any more
            if removed:
                signal["quotes"] = kept
                signal["count"] = len(kept)
                signal["participants"] = sorted({
                    q["participant_id"] for q in kept if q.get("participant_id")
                })
            assertions = signal.get("evidence_assertions") or []
            surviving = [a for a in assertions if _is_counted(a.get("source_quote_id"), counted_refs)]
            if len(surviving) != len(assertions):
                for ordinal, assertion in enumerate(surviving):
                    assertion["ordinal"] = ordinal
                signal["evidence_assertions"] = surviving
                signal["had_evidence_assertions"] = True
            kept_signals.append(signal)
        codebook["signals"] = kept_signals
    return payload


def _is_counted(ref: object, counted_refs: Mapping[str, int] | set[str] | frozenset[str]) -> bool:
    """Whether a reference still counts; a malformed (non-string) reference does not."""
    if not isinstance(ref, str) or not ref:
        return False
    if isinstance(counted_refs, Mapping):
        return counted_refs.get(ref, 0) > 0
    return ref in counted_refs


def _split_quotes(
    quotes: list[dict[str, Any]],
    counted_refs: Mapping[str, int] | set[str] | frozenset[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split a card's quotes into those that still count and those that do not."""
    remaining = Counter(counted_refs) if isinstance(counted_refs, Mapping) else None
    kept: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for quote in quotes:
        ref = quote.get("quote_id")
        if not _is_counted(ref, counted_refs):
            removed.append(quote)
        elif remaining is not None:
            if remaining[ref] > 0:
                remaining[ref] -= 1
                kept.append(quote)
            else:
                removed.append(quote)  # a twin whose row stopped counting
        else:
            kept.append(quote)
    return kept, removed


def _subtract_from_matrix(
    codebook: dict[str, Any], signal: dict[str, Any], removed: list[dict[str, Any]],
) -> None:
    """Take each removed quote out of the signal's cell and the matrix totals."""
    matrix = codebook.get(_MATRIX_BY_SOURCE.get(signal.get("source_type"), ""))
    row, col = signal.get("location"), signal.get("group_name")
    if not matrix or row is None or col is None:
        return
    cell = (matrix.get("cells") or {}).get(f"{row}|{col}")
    for quote in removed:
        if cell is not None:
            if cell.get("count", 0) <= 0:
                _warn_disagreement(row, col, "cell count")
            cell["count"] = max(0, cell.get("count", 0) - 1)
            tally = cell.get("participants") or {}
            pid = quote.get("participant_id")
            if pid in tally:
                tally[pid] -= 1
                if tally[pid] <= 0:
                    del tally[pid]
            intensities = cell.get("intensities") or []
            if quote.get("intensity") in intensities:
                intensities.remove(quote["intensity"])
        for totals, key in ((matrix.get("row_totals"), row), (matrix.get("col_totals"), col)):
            if totals is not None and key in totals:
                if totals[key] <= 0:
                    _warn_disagreement(row, col, "row or column total")
                totals[key] = max(0, totals[key] - 1)
        if "grand_total" in matrix:
            if matrix["grand_total"] <= 0:
                _warn_disagreement(row, col, "grand total")
            matrix["grand_total"] = max(0, matrix["grand_total"] - 1)


def _warn_disagreement(row: object, col: object, what: str) -> None:
    """The matrix and its card disagree: a count would have gone below zero.

    Names the cell only; the payload holds participant quotes.
    """
    logger.warning(
        "Signal snapshot matrix disagrees with its card for cell %r|%r: %s was already 0",
        row, col, what,
    )

