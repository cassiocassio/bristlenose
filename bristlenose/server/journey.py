"""Shared journey-derivation helper used by multiple route modules."""

from __future__ import annotations

from sqlalchemy.orm import Session

from bristlenose.server.models import ClusterQuote, Quote, ScreenCluster


def derive_journeys(
    db: Session,
    project_id: int,
) -> dict[str, list[str]]:
    """Derive per-participant journey labels from screen clusters.

    Returns participant_id → ordered list of screen labels.
    """
    clusters = (
        db.query(ScreenCluster)
        .filter_by(project_id=project_id)
        .order_by(ScreenCluster.display_order)
        .all()
    )

    participant_screens: dict[str, list[str]] = {}
    for cluster in clusters:
        cqs = db.query(ClusterQuote).filter_by(cluster_id=cluster.id).all()
        quote_ids = [cq.quote_id for cq in cqs]
        if not quote_ids:
            continue

        quotes = db.query(Quote).filter(Quote.id.in_(quote_ids)).all()
        pids_in_cluster = {q.participant_id for q in quotes}

        for pid in pids_in_cluster:
            if pid not in participant_screens:
                participant_screens[pid] = []
            if cluster.screen_label not in participant_screens[pid]:
                participant_screens[pid].append(cluster.screen_label)

    return participant_screens
