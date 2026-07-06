"""Shared builders for server round-trip tests (importer + curation).

Deterministic synthetic-project helpers: write intermediate pipeline JSON,
re-import against a live DB, assert what survives.  Hoisted here so the
curation round-trip suite and its Phase 2/3 extensions share one copy rather
than forking the pattern (see docs/private/reviews/curation-persistence-plan.md
Finding 5).  The older ``_write_pipeline_output`` / ``_make_quote`` variant in
tests/test_serve_importer.py predates this module and has a different shape;
it can migrate here opportunistically, but is left as-is for now.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from bristlenose.server.models import Quote


def quote(pid: str, tc: float, text: str, sentiment: str | None = None) -> dict:
    q = {
        "session_id": "s1",
        "participant_id": pid,
        "start_timecode": float(tc),
        "end_timecode": float(tc) + 5.0,
        "text": text,
        "topic_label": "Topic",
        "quote_type": "screen_specific",
    }
    if sentiment:
        q["sentiment"] = sentiment
    return q


def cluster(label: str, quotes: list[dict], order: int = 1) -> dict:
    return {
        "screen_label": label,
        "description": "",
        "display_order": order,
        "quotes": quotes,
    }


def theme(label: str, quotes: list[dict]) -> dict:
    return {"theme_label": label, "description": "", "quotes": quotes}


def write_intermediate(
    project_dir: Path,
    clusters: list[dict],
    themes: list[dict] | None = None,
    project_name: str = "Freeze Test",
) -> None:
    inter = project_dir / "bristlenose-output" / ".bristlenose" / "intermediate"
    inter.mkdir(parents=True, exist_ok=True)
    (inter / "metadata.json").write_text(json.dumps({"project_name": project_name}))
    (inter / "screen_clusters.json").write_text(json.dumps(clusters))
    (inter / "theme_groups.json").write_text(json.dumps(themes or []))


def dom_id(pid: str, tc: float) -> str:
    return f"q-{pid}-{int(tc)}"


def quote_at(db: Session, tc: float) -> Quote:
    return db.query(Quote).filter_by(start_timecode=float(tc)).one()
