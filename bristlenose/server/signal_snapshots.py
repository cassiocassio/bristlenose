"""Storage boundary for completed Signals-lens snapshots.

The reader deliberately has no signal calculation or LLM dependency.  Writing
is restricted to the LLM-backed codebook/new-interview lifecycle callers added
in the next slice; hand curation does not call this module in v1.
"""

from __future__ import annotations

import json
import logging
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

