"""Shared journey-derivation helper used by multiple route modules."""

from __future__ import annotations

from sqlalchemy.orm import Session

from bristlenose.server.models import ClusterQuote, Quote, ScreenCluster


class JourneyStep:
    """One screen in a participant's journey, with the anchor of its first moment.

    ``start_seconds`` is the earliest quote start-timecode for this participant on
    this screen — the timecode a transcript deep-link (``#t-<seconds>``) targets.
    """

    __slots__ = ("label", "start_seconds")

    def __init__(self, label: str, start_seconds: float) -> None:
        self.label = label
        self.start_seconds = start_seconds


def derive_journeys_with_anchors(
    db: Session,
    project_id: int,
) -> dict[str, list[JourneyStep]]:
    """Derive per-participant journey steps (label + first-moment anchor).

    Returns participant_id → ordered list of :class:`JourneyStep`. Order follows
    cluster ``display_order``; each screen label appears once (first occurrence),
    and its ``start_seconds`` is the minimum quote start-timecode for that
    participant across every cluster carrying that label — so the anchor is the
    true first moment, independent of cluster ordering.
    """
    clusters = (
        db.query(ScreenCluster)
        .filter_by(project_id=project_id)
        .order_by(ScreenCluster.display_order)
        .all()
    )

    # participant_id → {screen_label: min_start_seconds}
    label_anchors: dict[str, dict[str, float]] = {}
    # participant_id → ordered list of first-seen labels (display_order)
    label_order: dict[str, list[str]] = {}

    for cluster in clusters:
        cqs = db.query(ClusterQuote).filter_by(cluster_id=cluster.id).all()
        quote_ids = [cq.quote_id for cq in cqs]
        if not quote_ids:
            continue

        quotes = db.query(Quote).filter(Quote.id.in_(quote_ids)).all()
        label = cluster.screen_label
        for q in quotes:
            pid = q.participant_id
            anchors = label_anchors.setdefault(pid, {})
            order = label_order.setdefault(pid, [])
            if label not in anchors:
                anchors[label] = q.start_timecode
                order.append(label)
            elif q.start_timecode < anchors[label]:
                anchors[label] = q.start_timecode

    return {
        pid: [JourneyStep(label, label_anchors[pid][label]) for label in labels]
        for pid, labels in label_order.items()
    }


def derive_journeys(
    db: Session,
    project_id: int,
) -> dict[str, list[str]]:
    """Derive per-participant journey labels from screen clusters.

    Returns participant_id → ordered list of screen labels. Thin wrapper over
    :func:`derive_journeys_with_anchors` that drops the anchors (callers that
    only need the label sequence).
    """
    return {
        pid: [step.label for step in steps]
        for pid, steps in derive_journeys_with_anchors(db, project_id).items()
    }
