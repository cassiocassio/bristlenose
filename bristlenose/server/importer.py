"""Import pipeline output into the SQLite database.

Reads intermediate JSON files from the pipeline output directory and
populates all project-scoped tables.  Built as upsert from day one —
matched by stable key, researcher state never overwritten.

Called on ``bristlenose serve`` startup.  Always re-imports to pick up
pipeline re-runs (added/removed sessions).  Stale data from deleted
sessions is cleaned up; researcher state (starred, hidden, tags, edits,
deleted badges) is preserved for quotes that survive the re-import.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from bristlenose.server.models import (
    ClusterQuote,
    DeletedBadge,
    Person,
    Project,
    Quote,
    QuoteEdit,
    QuoteState,
    QuoteTag,
    ScreenCluster,
    SessionSpeaker,
    SourceFile,
    ThemeGroup,
    ThemeQuote,
    TopicBoundary,
    TranscriptSegment,
)
from bristlenose.server.models import (
    Session as SessionModel,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Transcript header parsing
# ---------------------------------------------------------------------------

_HEADER_DATE_RE = re.compile(r"^#\s*Date:\s*(.+)$", re.MULTILINE)
_HEADER_DURATION_RE = re.compile(r"^#\s*Duration:\s*(.+)$", re.MULTILINE)
_HEADER_SOURCE_RE = re.compile(r"^#\s*Source:\s*(.+)$", re.MULTILINE)
_SEGMENT_RE = re.compile(
    r"^\[(\d+:\d{2}(?::\d{2})?)\]\s+\[(\w+)\]\s+(.+)$", re.MULTILINE
)


def _parse_timecode_to_seconds(tc: str) -> float:
    """Parse ``MM:SS`` or ``HH:MM:SS`` into seconds."""
    parts = tc.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return 0.0


def _parse_duration_to_seconds(dur: str) -> float:
    """Parse a duration string like ``00:01:18`` or ``01:18`` into seconds."""
    dur = dur.strip()
    return _parse_timecode_to_seconds(dur)


def _parse_date(date_str: str) -> datetime | None:
    """Parse a date string like ``2026-01-20`` into a datetime."""
    date_str = date_str.strip()
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Transcript discovery
# ---------------------------------------------------------------------------


def _find_transcripts_dir(project_dir: Path, output_dir: Path) -> Path:
    """Find the best transcript directory from several candidate locations.

    Search order:
        1. ``output_dir/transcripts-cooked`` — PII-redacted (preferred)
        2. ``output_dir/transcripts-raw``     — standard pipeline output
        3. ``project_dir/transcripts-raw``    — input-dir layout
        4. ``project_dir/transcripts``        — manual/non-standard layout

    Returns the first directory that exists **and** contains ``.txt`` files.
    Falls back to ``output_dir/transcripts-raw`` (may not exist — downstream
    code already handles missing dirs gracefully).
    """
    candidates = [
        output_dir / "transcripts-cooked",
        output_dir / "transcripts-raw",
        project_dir / "transcripts-raw",
        project_dir / "transcripts",
    ]
    for candidate in candidates:
        if candidate.is_dir() and any(candidate.glob("*.txt")):
            return candidate
    return output_dir / "transcripts-raw"


# ---------------------------------------------------------------------------
# Import logic
# ---------------------------------------------------------------------------


def import_project(db: Session, project_dir: Path) -> Project:
    """Import pipeline output into the database.

    Always re-imports to pick up pipeline re-runs (added/removed sessions).
    Stale data from deleted sessions is cleaned up; researcher state
    (starred, hidden, tags, edits, deleted badges) is preserved for quotes
    that survive the re-import.

    Args:
        db: SQLAlchemy database session.
        project_dir: Path to the project's input directory.
            Expected structure: ``project_dir/bristlenose-output/``
            with ``.bristlenose/intermediate/`` inside it.

    Returns:
        The Project row (created or existing).
    """
    output_dir = project_dir / "bristlenose-output"
    if not output_dir.is_dir():
        output_dir = project_dir  # Caller already pointed at the output dir

    intermediate = output_dir / ".bristlenose" / "intermediate"

    # --- Read metadata ---------------------------------------------------
    metadata_path = intermediate / "metadata.json"
    project_name = "Untitled"
    if metadata_path.exists():
        meta = json.loads(metadata_path.read_text(encoding="utf-8"))
        project_name = meta.get("project_name", "Untitled")

    # --- Find or create project ------------------------------------------
    project = (
        db.query(Project)
        .filter_by(input_dir=str(project_dir), output_dir=str(output_dir))
        .first()
    )

    if project is None:
        project = Project(
            name=project_name,
            slug=project_name.lower().replace(" ", "-")[:100],
            input_dir=str(project_dir),
            output_dir=str(output_dir),
        )
        db.add(project)
        db.flush()  # get project.id

    # --- Import timestamp ------------------------------------------------
    # Every entity touched during this import gets this timestamp.
    # After import, anything with an older last_imported_at is stale
    # (from a previous pipeline run with sessions that no longer exist).
    now = datetime.now(timezone.utc)

    # --- Read intermediate JSON ------------------------------------------
    screen_clusters_data: list[dict] = []
    sc_path = intermediate / "screen_clusters.json"
    if sc_path.exists():
        screen_clusters_data = json.loads(sc_path.read_text(encoding="utf-8"))

    theme_groups_data: list[dict] = []
    tg_path = intermediate / "theme_groups.json"
    if tg_path.exists():
        theme_groups_data = json.loads(tg_path.read_text(encoding="utf-8"))

    # --- Parse transcripts for session metadata --------------------------
    transcripts_dir = _find_transcripts_dir(project_dir, output_dir)
    session_meta = _parse_transcript_headers(transcripts_dir)

    # --- Build sessions from all data sources ----------------------------
    # Collect all session_ids from quotes, transcripts, etc.
    session_ids: set[str] = set()
    for cluster in screen_clusters_data:
        for q in cluster.get("quotes", []):
            session_ids.add(q.get("session_id", ""))
    for theme in theme_groups_data:
        for q in theme.get("quotes", []):
            session_ids.add(q.get("session_id", ""))
    for meta_sid in session_meta:
        session_ids.add(meta_sid)
    session_ids.discard("")

    # Create sessions
    session_map: dict[str, SessionModel] = {}  # session_id → SessionModel
    for sid in sorted(session_ids):
        meta = session_meta.get(sid, {})
        num = int(sid[1:]) if len(sid) > 1 and sid[1:].isdigit() else 0
        sess = (
            db.query(SessionModel)
            .filter_by(project_id=project.id, session_id=sid)
            .first()
        )
        if sess is None:
            sess = SessionModel(
                project_id=project.id,
                session_id=sid,
                session_number=num,
                session_date=meta.get("date"),
                duration_seconds=meta.get("duration_seconds", 0.0),
                has_media=False,
                has_video=False,
            )
            db.add(sess)
            db.flush()
        session_map[sid] = sess

    # --- Import source files ---------------------------------------------
    _import_source_files(db, session_map, session_meta, project_dir)

    # --- Scan for video thumbnails ---------------------------------------
    _import_thumbnails(session_map, output_dir)

    # --- Import transcript segments --------------------------------------
    _import_transcript_segments(db, session_map, transcripts_dir)

    # --- Import persons + session_speakers from transcript segments ------
    _import_speakers(db, session_map, transcripts_dir, output_dir)

    # --- Import quotes, clusters, themes ---------------------------------
    quote_map = _import_quotes_from_clusters(
        db, project, session_map, screen_clusters_data, now,
    )
    _import_quotes_from_themes(
        db, project, session_map, theme_groups_data, quote_map, now,
    )

    # --- Import topic boundaries (if available) --------------------------
    tb_path = intermediate / "topic_boundaries.json"
    if tb_path.exists():
        _import_topic_boundaries(db, session_map, tb_path)

    # --- Clean up stale data from previous pipeline runs -----------------
    _cleanup_stale_data(db, project, session_ids, now)

    # --- Mark project as imported ----------------------------------------
    project.imported_at = now
    db.commit()

    logger.info(
        "Imported project '%s': %d sessions, %d quotes, %d clusters, %d themes.",
        project_name,
        len(session_map),
        db.query(Quote).filter_by(project_id=project.id).count(),
        db.query(ScreenCluster).filter_by(project_id=project.id).count(),
        db.query(ThemeGroup).filter_by(project_id=project.id).count(),
    )
    return project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_transcript_headers(
    transcripts_dir: Path,
) -> dict[str, dict]:
    """Parse transcript file headers for session metadata.

    Returns a dict keyed by session_id with keys:
        date (datetime | None), duration_seconds (float), source (str).
    """
    result: dict[str, dict] = {}
    if not transcripts_dir.is_dir():
        return result

    for txt_file in sorted(transcripts_dir.glob("*.txt")):
        # Session ID from filename: "s1.txt" → "s1"
        sid = txt_file.stem
        header = txt_file.read_text(encoding="utf-8")[:500]  # only need header

        date_match = _HEADER_DATE_RE.search(header)
        dur_match = _HEADER_DURATION_RE.search(header)
        source_match = _HEADER_SOURCE_RE.search(header)

        result[sid] = {
            "date": _parse_date(date_match.group(1)) if date_match else None,
            "duration_seconds": (
                _parse_duration_to_seconds(dur_match.group(1)) if dur_match else 0.0
            ),
            "source": source_match.group(1).strip() if source_match else "",
        }

    return result


def _import_source_files(
    db: Session,
    session_map: dict[str, SessionModel],
    session_meta: dict[str, dict],
    project_dir: Path,
) -> None:
    """Import source file records from transcript metadata."""
    for sid, meta in session_meta.items():
        sess = session_map.get(sid)
        if not sess:
            continue
        source_name = meta.get("source", "")
        if not source_name:
            continue

        # Check if already imported
        existing = (
            db.query(SourceFile)
            .filter_by(session_id=sess.id)
            .first()
        )
        if existing:
            continue

        # Try to find the actual file
        source_path = project_dir / source_name
        file_type = _guess_file_type(source_name)

        # Update session media flags
        if file_type in ("video", "audio"):
            sess.has_media = True
            if file_type == "video":
                sess.has_video = True

        sf = SourceFile(
            session_id=sess.id,
            file_type=file_type,
            path=str(source_path),
            size_bytes=source_path.stat().st_size if source_path.exists() else 0,
            verified_at=datetime.now(timezone.utc) if source_path.exists() else None,
        )
        db.add(sf)


def _import_thumbnails(
    session_map: dict[str, SessionModel],
    output_dir: Path,
) -> None:
    """Set thumbnail_path on sessions that have a generated thumbnail on disk."""
    thumbnails_dir = output_dir / "assets" / "thumbnails"
    if not thumbnails_dir.is_dir():
        return
    for sid, sess in session_map.items():
        thumb_path = thumbnails_dir / f"{sid}.jpg"
        if thumb_path.exists():
            sess.thumbnail_path = f"assets/thumbnails/{sid}.jpg"


def _guess_file_type(filename: str) -> str:
    """Guess file type from filename extension."""
    ext = Path(filename).suffix.lower()
    video_exts = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
    audio_exts = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
    if ext in video_exts:
        return "video"
    if ext in audio_exts:
        return "audio"
    if ext == ".srt":
        return "subtitle_srt"
    if ext == ".vtt":
        return "subtitle_vtt"
    if ext == ".docx":
        return "docx"
    return "other"


def _import_transcript_segments(
    db: Session,
    session_map: dict[str, SessionModel],
    transcripts_dir: Path,
) -> None:
    """Import transcript segments from raw transcript files."""
    if not transcripts_dir.is_dir():
        return

    for txt_file in sorted(transcripts_dir.glob("*.txt")):
        sid = txt_file.stem
        sess = session_map.get(sid)
        if not sess:
            continue

        # Skip if segments already imported
        existing_count = (
            db.query(TranscriptSegment).filter_by(session_id=sess.id).count()
        )
        if existing_count > 0:
            continue

        content = txt_file.read_text(encoding="utf-8")
        segments = _SEGMENT_RE.findall(content)

        for i, (timecode, speaker_code, text) in enumerate(segments):
            start = _parse_timecode_to_seconds(timecode)
            # End time: use next segment's start, or start + duration estimate
            if i + 1 < len(segments):
                end = _parse_timecode_to_seconds(segments[i + 1][0])
            else:
                end = start + 10.0  # rough estimate for last segment

            seg = TranscriptSegment(
                session_id=sess.id,
                speaker_code=speaker_code,
                start_time=start,
                end_time=end,
                text=text.strip(),
                source="transcript",
                segment_index=i,
            )
            db.add(seg)


def _load_people_for_import(output_dir: Path) -> dict[str, dict[str, str]] | None:
    """Load ``people.yaml`` and return a flat mapping for the importer.

    Returns ``{speaker_code: {full_name, short_name, role, persona, notes}}``
    or ``None`` if no file exists.
    """
    people_path = output_dir / "people.yaml"
    if not people_path.exists():
        return None
    try:
        import yaml

        raw = yaml.safe_load(people_path.read_text(encoding="utf-8"))
        if not raw or "participants" not in raw:
            return None
        result: dict[str, dict[str, str]] = {}
        for pid, entry in raw["participants"].items():
            ed = entry.get("editable", {})
            result[pid] = {
                "full_name": ed.get("full_name", ""),
                "short_name": ed.get("short_name", ""),
                "role": ed.get("role", ""),
                "persona": ed.get("persona", ""),
                "notes": ed.get("notes", ""),
            }
        return result
    except Exception:
        logger.warning("Could not load people.yaml for import", exc_info=True)
        return None


def _import_speakers(
    db: Session,
    session_map: dict[str, SessionModel],
    transcripts_dir: Path,
    output_dir: Path,
) -> None:
    """Import speakers from transcript segments.

    Creates Person rows and SessionSpeaker join rows.  When a
    ``people.yaml`` exists in the output directory, populates
    Person fields (full_name, short_name, role_title, persona, notes)
    from the human-editable entries — so serve mode shows the same
    names as the pipeline/HTML report.

    On re-import, existing speakers are not duplicated, but their
    Person rows are updated from ``people.yaml`` if the YAML has data
    and the Person row is still empty (pipeline names fill empty fields
    only — never overwrite researcher edits made via the UI).
    """
    if not transcripts_dir.is_dir():
        return

    # Load people.yaml once for all sessions.
    people = _load_people_for_import(output_dir)

    for txt_file in sorted(transcripts_dir.glob("*.txt")):
        sid = txt_file.stem
        sess = session_map.get(sid)
        if not sess:
            continue

        # Check if speakers already imported
        existing_speakers = (
            db.query(SessionSpeaker).filter_by(session_id=sess.id).all()
        )
        if existing_speakers:
            # Speakers exist — update Person rows from people.yaml
            # (fill empty fields only, never overwrite).
            if people:
                _update_persons_from_people(db, existing_speakers, people)
            continue

        content = txt_file.read_text(encoding="utf-8")
        segments = _SEGMENT_RE.findall(content)

        # Collect unique speaker codes
        speaker_codes: list[str] = []
        for _, code, _ in segments:
            if code not in speaker_codes:
                speaker_codes.append(code)

        for code in speaker_codes:
            # Determine role from code prefix
            if code.startswith("m"):
                role = "researcher"
            elif code.startswith("o"):
                role = "observer"
            else:
                role = "participant"

            # Populate from people.yaml if available
            full_name = ""
            short_name = ""
            role_title = ""
            persona = ""
            notes = ""
            if people and code in people:
                full_name = people[code].get("full_name", "")
                short_name = people[code].get("short_name", "")
                role_title = people[code].get("role", "")
                persona = people[code].get("persona", "")
                notes = people[code].get("notes", "")

            person = Person(
                full_name=full_name,
                short_name=short_name,
                role_title=role_title,
                persona=persona,
                notes=notes,
            )
            db.add(person)
            db.flush()

            sp = SessionSpeaker(
                session_id=sess.id,
                person_id=person.id,
                speaker_code=code,
                speaker_role=role,
            )
            db.add(sp)


def _update_persons_from_people(
    db: Session,
    speakers: list[SessionSpeaker],
    people: dict[str, dict[str, str]],
) -> None:
    """Update existing Person rows from ``people.yaml`` (fill empty only).

    Never overwrites non-empty fields — researcher edits made via the
    browser UI take priority over pipeline-generated names.
    """
    for sp in speakers:
        yaml_data = people.get(sp.speaker_code)
        if not yaml_data:
            continue
        person = db.get(Person, sp.person_id)
        if not person:
            continue
        if not person.full_name and yaml_data.get("full_name"):
            person.full_name = yaml_data["full_name"]
        if not person.short_name and yaml_data.get("short_name"):
            person.short_name = yaml_data["short_name"]
        if not person.role_title and yaml_data.get("role"):
            person.role_title = yaml_data["role"]
        if not person.persona and yaml_data.get("persona"):
            person.persona = yaml_data["persona"]
        if not person.notes and yaml_data.get("notes"):
            person.notes = yaml_data["notes"]


def _get_or_create_quote(
    db: Session,
    project: Project,
    quote_data: dict,
    now: datetime,
) -> Quote:
    """Get or create a quote by stable key.

    Stable key: (project_id, session_id, participant_id, start_timecode).
    """
    session_id = quote_data.get("session_id", "")
    participant_id = quote_data.get("participant_id", "")
    start_timecode = float(quote_data.get("start_timecode", 0.0))

    # Try to find existing quote by stable key
    existing = (
        db.query(Quote)
        .filter_by(
            project_id=project.id,
            session_id=session_id,
            participant_id=participant_id,
            start_timecode=start_timecode,
        )
        .first()
    )
    if existing:
        # Update pipeline fields (upsert)
        existing.text = quote_data.get("text", existing.text)
        existing.end_timecode = float(quote_data.get("end_timecode", existing.end_timecode))
        existing.verbatim_excerpt = quote_data.get("verbatim_excerpt", existing.verbatim_excerpt)
        existing.topic_label = quote_data.get("topic_label", existing.topic_label)
        existing.quote_type = quote_data.get("quote_type", existing.quote_type)
        existing.researcher_context = quote_data.get(
            "researcher_context", existing.researcher_context
        )
        existing.sentiment = quote_data.get("sentiment", existing.sentiment)
        existing.intensity = int(quote_data.get("intensity", existing.intensity))
        existing.segment_index = int(quote_data.get("segment_index", existing.segment_index))
        existing.last_imported_at = now
        return existing

    # Create new quote
    q = Quote(
        project_id=project.id,
        session_id=session_id,
        participant_id=participant_id,
        start_timecode=start_timecode,
        end_timecode=float(quote_data.get("end_timecode", 0.0)),
        text=quote_data.get("text", ""),
        verbatim_excerpt=quote_data.get("verbatim_excerpt", ""),
        topic_label=quote_data.get("topic_label", ""),
        quote_type=quote_data.get("quote_type", ""),
        researcher_context=quote_data.get("researcher_context"),
        sentiment=quote_data.get("sentiment"),
        intensity=int(quote_data.get("intensity", 1)),
        segment_index=int(quote_data.get("segment_index", -1)),
        last_imported_at=now,
    )
    db.add(q)
    db.flush()
    return q


def _import_quotes_from_clusters(
    db: Session,
    project: Project,
    session_map: dict[str, SessionModel],
    screen_clusters_data: list[dict],
    now: datetime,
) -> dict[tuple, Quote]:
    """Import screen clusters and their quotes.

    Returns a quote_map keyed by (session_id, participant_id, start_timecode)
    for deduplication when the same quote appears in themes.
    """
    quote_map: dict[tuple, Quote] = {}

    for i, cluster_data in enumerate(screen_clusters_data):
        # Upsert cluster by label
        label = cluster_data.get("screen_label", f"Cluster {i + 1}")
        cluster = (
            db.query(ScreenCluster)
            .filter_by(project_id=project.id, screen_label=label)
            .first()
        )
        if cluster is None:
            cluster = ScreenCluster(
                project_id=project.id,
                screen_label=label,
                description=cluster_data.get("description", ""),
                display_order=cluster_data.get("display_order", i),
                created_by="pipeline",
                last_imported_at=now,
            )
            db.add(cluster)
            db.flush()
        else:
            cluster.description = cluster_data.get("description", cluster.description)
            cluster.display_order = cluster_data.get("display_order", cluster.display_order)
            cluster.last_imported_at = now

        # Import quotes
        for q_data in cluster_data.get("quotes", []):
            q = _get_or_create_quote(db, project, q_data, now)
            key = (q.session_id, q.participant_id, q.start_timecode)
            quote_map[key] = q

            # Create cluster_quote join if not exists
            existing_cq = (
                db.query(ClusterQuote)
                .filter_by(cluster_id=cluster.id, quote_id=q.id)
                .first()
            )
            if not existing_cq:
                cq = ClusterQuote(
                    cluster_id=cluster.id,
                    quote_id=q.id,
                    assigned_by="pipeline",
                )
                db.add(cq)

    return quote_map


def _import_quotes_from_themes(
    db: Session,
    project: Project,
    session_map: dict[str, SessionModel],
    theme_groups_data: list[dict],
    quote_map: dict[tuple, Quote],
    now: datetime,
) -> None:
    """Import theme groups and their quotes.

    Reuses quotes from quote_map if they already exist (from clusters).
    """

    for i, theme_data in enumerate(theme_groups_data):
        label = theme_data.get("theme_label", f"Theme {i + 1}")
        theme = (
            db.query(ThemeGroup)
            .filter_by(project_id=project.id, theme_label=label)
            .first()
        )
        if theme is None:
            theme = ThemeGroup(
                project_id=project.id,
                theme_label=label,
                description=theme_data.get("description", ""),
                created_by="pipeline",
                last_imported_at=now,
            )
            db.add(theme)
            db.flush()
        else:
            theme.description = theme_data.get("description", theme.description)
            theme.last_imported_at = now

        # Import quotes
        for q_data in theme_data.get("quotes", []):
            q = _get_or_create_quote(db, project, q_data, now)
            key = (q.session_id, q.participant_id, q.start_timecode)
            quote_map[key] = q

            # Create theme_quote join if not exists
            existing_tq = (
                db.query(ThemeQuote)
                .filter_by(theme_id=theme.id, quote_id=q.id)
                .first()
            )
            if not existing_tq:
                tq = ThemeQuote(
                    theme_id=theme.id,
                    quote_id=q.id,
                    assigned_by="pipeline",
                )
                db.add(tq)


def _import_topic_boundaries(
    db: Session,
    session_map: dict[str, SessionModel],
    tb_path: Path,
) -> None:
    """Import topic boundaries from JSON."""
    data = json.loads(tb_path.read_text(encoding="utf-8"))
    for item in data:
        sid = item.get("session_id", "")
        sess = session_map.get(sid)
        if not sess:
            continue

        tb = TopicBoundary(
            session_id=sess.id,
            timecode_seconds=float(item.get("timecode_seconds", 0.0)),
            topic_label=item.get("topic_label", ""),
            transition_type=item.get("transition_type", ""),
            confidence=float(item.get("confidence", 0.0)),
        )
        db.add(tb)


def _cleanup_stale_data(
    db: Session,
    project: Project,
    current_session_ids: set[str],
    now: datetime,
) -> None:
    """Remove data from previous pipeline runs that no longer exists.

    After a re-run where videos were added or removed, the intermediate
    JSON reflects the new state.  Entities touched during *this* import
    have ``last_imported_at == now``.  Anything older is stale.

    Researcher state (QuoteState, QuoteTag, QuoteEdit, DeletedBadge)
    is preserved for surviving quotes and deleted for stale quotes —
    a quote from a removed session is gone, so its tags are meaningless.
    """
    # --- Stale quotes (not touched in this import) -----------------------
    stale_quotes = (
        db.query(Quote)
        .filter(
            Quote.project_id == project.id,
            (Quote.last_imported_at < now) | (Quote.last_imported_at.is_(None)),
        )
        .all()
    )
    if stale_quotes:
        stale_quote_ids = [q.id for q in stale_quotes]
        logger.info(
            "Removing %d stale quotes from previous pipeline run.",
            len(stale_quote_ids),
        )

        # Delete researcher state for stale quotes
        db.query(QuoteState).filter(
            QuoteState.quote_id.in_(stale_quote_ids)
        ).delete(synchronize_session="fetch")
        db.query(QuoteTag).filter(
            QuoteTag.quote_id.in_(stale_quote_ids)
        ).delete(synchronize_session="fetch")
        db.query(QuoteEdit).filter(
            QuoteEdit.quote_id.in_(stale_quote_ids)
        ).delete(synchronize_session="fetch")
        db.query(DeletedBadge).filter(
            DeletedBadge.quote_id.in_(stale_quote_ids)
        ).delete(synchronize_session="fetch")

        # Delete join rows
        db.query(ClusterQuote).filter(
            ClusterQuote.quote_id.in_(stale_quote_ids)
        ).delete(synchronize_session="fetch")
        db.query(ThemeQuote).filter(
            ThemeQuote.quote_id.in_(stale_quote_ids)
        ).delete(synchronize_session="fetch")

        # Delete the quotes themselves
        db.query(Quote).filter(
            Quote.id.in_(stale_quote_ids)
        ).delete(synchronize_session="fetch")

    # --- Stale pipeline-created clusters ---------------------------------
    stale_clusters = (
        db.query(ScreenCluster)
        .filter(
            ScreenCluster.project_id == project.id,
            ScreenCluster.created_by == "pipeline",
            (ScreenCluster.last_imported_at < now)
            | (ScreenCluster.last_imported_at.is_(None)),
        )
        .all()
    )
    if stale_clusters:
        stale_cluster_ids = [c.id for c in stale_clusters]
        logger.info(
            "Removing %d stale clusters from previous pipeline run.",
            len(stale_cluster_ids),
        )
        db.query(ClusterQuote).filter(
            ClusterQuote.cluster_id.in_(stale_cluster_ids)
        ).delete(synchronize_session="fetch")
        db.query(ScreenCluster).filter(
            ScreenCluster.id.in_(stale_cluster_ids)
        ).delete(synchronize_session="fetch")

    # --- Stale pipeline-created themes -----------------------------------
    stale_themes = (
        db.query(ThemeGroup)
        .filter(
            ThemeGroup.project_id == project.id,
            ThemeGroup.created_by == "pipeline",
            (ThemeGroup.last_imported_at < now)
            | (ThemeGroup.last_imported_at.is_(None)),
        )
        .all()
    )
    if stale_themes:
        stale_theme_ids = [t.id for t in stale_themes]
        logger.info(
            "Removing %d stale themes from previous pipeline run.",
            len(stale_theme_ids),
        )
        db.query(ThemeQuote).filter(
            ThemeQuote.theme_id.in_(stale_theme_ids)
        ).delete(synchronize_session="fetch")
        db.query(ThemeGroup).filter(
            ThemeGroup.id.in_(stale_theme_ids)
        ).delete(synchronize_session="fetch")

    # --- Stale sessions --------------------------------------------------
    # Sessions that exist in the DB but not in the current pipeline output
    all_db_sessions = (
        db.query(SessionModel)
        .filter_by(project_id=project.id)
        .all()
    )
    stale_sessions = [s for s in all_db_sessions if s.session_id not in current_session_ids]
    if stale_sessions:
        stale_session_db_ids = [s.id for s in stale_sessions]
        stale_session_str_ids = [s.session_id for s in stale_sessions]
        logger.info(
            "Removing %d stale sessions: %s",
            len(stale_sessions),
            ", ".join(stale_session_str_ids),
        )
        # Delete child rows
        db.query(SourceFile).filter(
            SourceFile.session_id.in_(stale_session_db_ids)
        ).delete(synchronize_session="fetch")
        db.query(TranscriptSegment).filter(
            TranscriptSegment.session_id.in_(stale_session_db_ids)
        ).delete(synchronize_session="fetch")
        db.query(TopicBoundary).filter(
            TopicBoundary.session_id.in_(stale_session_db_ids)
        ).delete(synchronize_session="fetch")

        # SessionSpeaker + orphaned Person rows
        stale_speakers = (
            db.query(SessionSpeaker)
            .filter(SessionSpeaker.session_id.in_(stale_session_db_ids))
            .all()
        )
        stale_person_ids = [sp.person_id for sp in stale_speakers]
        db.query(SessionSpeaker).filter(
            SessionSpeaker.session_id.in_(stale_session_db_ids)
        ).delete(synchronize_session="fetch")

        # Only delete persons not referenced by other sessions
        if stale_person_ids:
            still_used = (
                db.query(SessionSpeaker.person_id)
                .filter(SessionSpeaker.person_id.in_(stale_person_ids))
                .all()
            )
            still_used_ids = {row[0] for row in still_used}
            orphan_ids = [pid for pid in stale_person_ids if pid not in still_used_ids]
            if orphan_ids:
                db.query(Person).filter(
                    Person.id.in_(orphan_ids)
                ).delete(synchronize_session="fetch")

        # Delete the sessions
        db.query(SessionModel).filter(
            SessionModel.id.in_(stale_session_db_ids)
        ).delete(synchronize_session="fetch")

    # --- Clean stale pipeline join rows ----------------------------------
    # If the pipeline reassigned a quote to a different cluster/theme,
    # old pipeline-assigned joins for surviving clusters may be stale.
    # Get all surviving pipeline clusters and their expected quote IDs.
    surviving_clusters = (
        db.query(ScreenCluster)
        .filter_by(project_id=project.id, created_by="pipeline")
        .all()
    )
    for cluster in surviving_clusters:
        # Get all pipeline-assigned joins for this cluster
        pipeline_cqs = (
            db.query(ClusterQuote)
            .filter_by(cluster_id=cluster.id, assigned_by="pipeline")
            .all()
        )
        for cq in pipeline_cqs:
            # If the quote no longer exists, remove the join
            quote = db.get(Quote, cq.quote_id)
            if not quote:
                db.delete(cq)

    surviving_themes = (
        db.query(ThemeGroup)
        .filter_by(project_id=project.id, created_by="pipeline")
        .all()
    )
    for theme in surviving_themes:
        pipeline_tqs = (
            db.query(ThemeQuote)
            .filter_by(theme_id=theme.id, assigned_by="pipeline")
            .all()
        )
        for tq in pipeline_tqs:
            quote = db.get(Quote, tq.quote_id)
            if not quote:
                db.delete(tq)
