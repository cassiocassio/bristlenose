"""Dev-only endpoints for visual parity testing.

Registered only when ``bristlenose serve --dev`` is active.
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape as _esc
from pathlib import Path as _Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from bristlenose.server.models import (
    ClusterQuote,
    Person,
    Project,
    Quote,
    ScreenCluster,
    SessionSpeaker,
)
from bristlenose.server.models import (
    Session as SessionModel,
)
from bristlenose.stages.render_html import _jinja_env, _render_sentiment_sparkline
from bristlenose.utils.markdown import format_finder_date, format_finder_filename

router = APIRouter(prefix="/api/dev")


# ---------------------------------------------------------------------------
# Database dependency
# ---------------------------------------------------------------------------


def _get_db(request: Request) -> Session:
    return request.app.state.db_factory()


# ---------------------------------------------------------------------------
# Helpers (mirroring sessions.py but producing Jinja2 template dicts)
# ---------------------------------------------------------------------------

_SPEAKER_PREFIX_ORDER = {"m": 0, "p": 1, "o": 2}


def _speaker_sort_key(sp: SessionSpeaker) -> tuple[int, int]:
    code = sp.speaker_code
    prefix = _SPEAKER_PREFIX_ORDER.get(code[0], 3) if code else 3
    num = int(code[1:]) if len(code) > 1 and code[1:].isdigit() else 0
    return (prefix, num)


def _derive_journeys(
    db: Session,
    project_id: int,
) -> dict[str, list[str]]:
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
        for q in quotes:
            pid = q.participant_id
            if pid not in participant_screens:
                participant_screens[pid] = []
            if cluster.screen_label not in participant_screens[pid]:
                participant_screens[pid].append(cluster.screen_label)
    return participant_screens


def _aggregate_sentiments(
    db: Session,
    project_id: int,
) -> dict[str, dict[str, int]]:
    quotes = db.query(Quote).filter_by(project_id=project_id).all()
    result: dict[str, dict[str, int]] = {}
    for q in quotes:
        if q.sentiment:
            if q.session_id not in result:
                result[q.session_id] = {}
            result[q.session_id][q.sentiment] = (
                result[q.session_id].get(q.sentiment, 0) + 1
            )
    return result


def _format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "\u2014"
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# Sessions table HTML (Jinja2-rendered fragment)
# ---------------------------------------------------------------------------


@router.get("/sessions-table-html", response_class=HTMLResponse)
def sessions_table_html(
    project_id: int = Query(default=1),
    db: Session = Depends(_get_db),  # type: ignore[assignment]
) -> str:
    """Render the sessions table using the Jinja2 template.

    Returns the same HTML fragment that ``render_html.py`` produces for the
    static report.  Used by the visual diff page to compare against the
    React ``SessionsTable`` component.
    """
    try:
        project = db.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        sessions = (
            db.query(SessionModel)
            .filter_by(project_id=project_id)
            .order_by(SessionModel.session_number)
            .all()
        )

        participant_screens = _derive_journeys(db, project_id)
        sentiment_by_session = _aggregate_sentiments(db, project_id)

        # Collect all moderator/observer codes across all sessions.
        all_moderator_codes: list[str] = []
        all_observer_codes: list[str] = []
        for sess in sessions:
            for sp in sess.session_speakers:
                if sp.speaker_code.startswith("m") and sp.speaker_code not in all_moderator_codes:
                    all_moderator_codes.append(sp.speaker_code)
                elif sp.speaker_code.startswith("o") and sp.speaker_code not in all_observer_codes:
                    all_observer_codes.append(sp.speaker_code)
        all_moderator_codes.sort(
            key=lambda c: int(c[1:]) if len(c) > 1 and c[1:].isdigit() else 0
        )
        all_observer_codes.sort(
            key=lambda c: int(c[1:]) if len(c) > 1 and c[1:].isdigit() else 0
        )

        omit_moderators_from_rows = len(all_moderator_codes) == 1

        # Moderator header HTML
        def _resolve_name(sp: SessionSpeaker) -> str:
            person = db.get(Person, sp.person_id)
            if person:
                return person.short_name or person.full_name or ""
            return ""

        # Build moderator header
        moderator_header = ""
        if all_moderator_codes:
            parts: list[str] = []
            for code in all_moderator_codes:
                # Find the speaker in any session
                sp = (
                    db.query(SessionSpeaker)
                    .filter_by(speaker_code=code)
                    .first()
                )
                if sp:
                    name = _resolve_name(sp)
                    name_html = f" {_esc(name)}" if name else ""
                    parts.append(
                        f'<span class="bn-person-badge">'
                        f'<span class="badge">{_esc(code)}</span>{name_html}'
                        f"</span>"
                    )
            moderator_header = "Moderated by " + _oxford_list(parts)

        # Build observer header
        observer_header = ""
        if all_observer_codes:
            parts = []
            for code in all_observer_codes:
                sp = (
                    db.query(SessionSpeaker)
                    .filter_by(speaker_code=code)
                    .first()
                )
                if sp:
                    name = _resolve_name(sp)
                    name_html = f" {_esc(name)}" if name else ""
                    parts.append(
                        f'<span class="bn-person-badge">'
                        f'<span class="badge">{_esc(code)}</span>{name_html}'
                        f"</span>"
                    )
            noun = "Observer" if len(parts) == 1 else "Observers"
            observer_header = f"{noun}: " + _oxford_list(parts)

        now = datetime.now(tz=timezone.utc)
        rows: list[dict[str, object]] = []
        for sess in sessions:
            sid = sess.session_id
            session_num = sid[1:] if len(sid) > 1 and sid[1:].isdigit() else sid

            # Date
            start = _esc(format_finder_date(sess.session_date, now=now)) if sess.session_date else "\u2014"

            # Duration
            duration = _format_duration(sess.duration_seconds)

            # Source file
            source = "&mdash;"
            source_folder_uri = ""
            if sess.source_files:
                sf = sess.source_files[0]
                full_name = _Path(sf.path).name
                display_fname = format_finder_filename(full_name)
                title_attr = f' title="{_esc(full_name)}"' if display_fname != full_name else ""
                source = f"<span{title_attr}>{_esc(display_fname)}</span>"

            # Speakers
            speakers_list: list[dict[str, str]] = []
            for sp in sorted(sess.session_speakers, key=_speaker_sort_key):
                if omit_moderators_from_rows and sp.speaker_code.startswith("m"):
                    continue
                name = _resolve_name(sp)
                display = _esc(name) if name else ""
                speakers_list.append({"code": _esc(sp.speaker_code), "name": display})

            # Journey
            session_pids = [
                sp.speaker_code
                for sp in sess.session_speakers
                if sp.speaker_code.startswith("p")
            ]
            journey_labels: list[str] = []
            for pid in session_pids:
                for label in participant_screens.get(pid, []):
                    if label not in journey_labels:
                        journey_labels.append(label)
            journey = " &rarr; ".join(journey_labels) if journey_labels else ""

            # Sparkline
            sparkline = _render_sentiment_sparkline(sentiment_by_session.get(sid, {}))

            rows.append({
                "sid": _esc(sid),
                "num": _esc(session_num),
                "speakers_list": speakers_list,
                "start": start,
                "duration": duration,
                "source": source,
                "journey": journey,
                "sentiment_sparkline": sparkline,
                "has_media": sess.has_media,
                "source_folder_uri": source_folder_uri,
            })

        html = _jinja_env.get_template("session_table.html").render(
            rows=rows,
            moderator_header=moderator_header,
            observer_header=observer_header,
        ).rstrip("\n")
        return html
    finally:
        db.close()


# ---------------------------------------------------------------------------
# System info for About tab developer section
# ---------------------------------------------------------------------------


@router.get("/info")
def dev_info() -> dict[str, object]:
    """System info for the About tab developer section."""
    from bristlenose.server.db import _DB_PATH, Base

    return {
        "db_path": str(_DB_PATH),
        "table_count": len(Base.metadata.tables),
        "endpoints": [
            {
                "label": "Database Browser",
                "url": "/admin/",
                "description": "Browse and edit all 22 tables (SQLAdmin)",
            },
            {
                "label": "API Documentation",
                "url": "/api/docs",
                "description": "Interactive Swagger UI for all endpoints",
            },
            {
                "label": "Sessions API",
                "url": "/api/projects/1/sessions",
                "description": "Sessions list with speakers, journeys, sentiment",
            },
            {
                "label": "Sessions HTML",
                "url": "/api/dev/sessions-table-html?project_id=1",
                "description": "Jinja2-rendered sessions table (visual diff)",
            },
            {
                "label": "Visual Diff",
                "url": "http://localhost:5173/visual-diff.html",
                "description": "Side-by-side React vs Jinja2 comparison",
            },
            {
                "label": "Health Check",
                "url": "/api/health",
                "description": "System status and version",
            },
        ],
    }


def _oxford_list(parts: list[str]) -> str:
    if len(parts) <= 1:
        return parts[0] if parts else ""
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return ", ".join(parts[:-1]) + ", and " + parts[-1]
