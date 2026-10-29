"""Storage boundary for completed Signals-lens snapshots.

The reader deliberately has no signal calculation or LLM dependency.  Writing
is restricted to the LLM-backed codebook/new-interview lifecycle callers added
in the next slice; hand curation does not call this module in v1.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from bristlenose.server.models import SignalSnapshot

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
        .all()
    )
    for snapshot in snapshots:
        try:
            snapshot_payload(snapshot)
        except (TypeError, ValueError):
            continue
        return snapshot
    return None


def snapshot_payload(snapshot: SignalSnapshot) -> dict[str, Any]:
    """Decode a row at the reader boundary, failing loudly on corrupt storage."""
    payload = json.loads(snapshot.payload)
    if not isinstance(payload, dict):
        raise ValueError(f"Signal snapshot {snapshot.id} payload is not an object")
    return payload
