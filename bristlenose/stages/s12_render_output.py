"""Stage 12: Render the final Markdown deliverable and write all output files."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from bristlenose.models import (
    EmotionalTone,
    ExtractedQuote,
    InputSession,
    PeopleFile,
    QuoteIntent,
    ScreenCluster,
    ThemeGroup,
    format_timecode,
)
from bristlenose.utils.markdown import (
    BOLD,
    DESCRIPTION,
    EM_DASH,
    HEADING_1,
    HEADING_2,
    HEADING_3,
    HORIZONTAL_RULE,
    format_finder_date,
    format_friction_item,
    format_participant_range,
    format_quote_block,
)

logger = logging.getLogger(__name__)


def _session_sort_key(sid: str) -> tuple[int, str]:
    """Sort key that orders session IDs numerically (s1 < s2 < s10)."""
    import re

    m = re.search(r"\d+", sid)
    return (int(m.group()) if m else 0, sid)


def render_markdown(
    screen_clusters: list[ScreenCluster],
    theme_groups: list[ThemeGroup],
    sessions: list[InputSession],
    project_name: str,
    output_dir: Path,
    all_quotes: list[ExtractedQuote] | None = None,
    display_names: dict[str, str] | None = None,
    people: PeopleFile | None = None,
) -> Path:
    """Generate the final Markdown report file.

    Args:
        screen_clusters: Screen-specific quote clusters.
        theme_groups: Thematic quote groups.
        sessions: All input sessions (for the appendix).
        project_name: Name of the research project.
        output_dir: Output directory.
        all_quotes: All extracted quotes (used for rewatch list).
        display_names: Mapping of participant_id → display name.
        people: People file data for enriched participant table.

    Returns:
        Path to the written Markdown file.
    """
    from bristlenose.output_paths import OutputPaths

    paths = OutputPaths(output_dir, project_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = paths.md_report

    lines: list[str] = []

    # Header
    lines.append(HEADING_1.format(title=project_name))
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d')}")
    if people and people.participants:
        _n_p = sum(1 for k in people.participants if k.startswith("p"))
    else:
        _n_p = len(sessions)
    if people and people.participants:
        _p_ids = sorted(
            (k for k in people.participants if k.startswith("p")),
            key=lambda c: int(c[1:]) if c[1:].isdigit() else 0,
        )
    else:
        _p_ids = [s.participant_id for s in sessions]
    lines.append(
        f"Participants: {_n_p} ({format_participant_range(_p_ids)})"
    )
    lines.append(f"Sessions processed: {len(sessions)}")
    lines.append("")
    lines.append(HORIZONTAL_RULE)
    lines.append("")

    # Sections
    if screen_clusters:
        lines.append(HEADING_2.format(title="Sections"))
        lines.append("")

        for cluster in screen_clusters:
            lines.append(HEADING_3.format(title=cluster.screen_label))
            lines.append("")
            if cluster.description:
                lines.append(DESCRIPTION.format(text=cluster.description))
                lines.append("")

            for quote in cluster.quotes:
                dn = display_names.get(quote.participant_id) if display_names else None
                lines.append(format_quote_block(quote, display_name=dn))
                lines.append("")

        lines.append(HORIZONTAL_RULE)
        lines.append("")

    # Themes
    if theme_groups:
        lines.append(HEADING_2.format(title="Themes"))
        lines.append("")

        for theme in theme_groups:
            lines.append(HEADING_3.format(title=theme.theme_label))
            lines.append("")
            if theme.description:
                lines.append(DESCRIPTION.format(text=theme.description))
                lines.append("")

            for quote in theme.quotes:
                dn = display_names.get(quote.participant_id) if display_names else None
                lines.append(format_quote_block(quote, display_name=dn))
                lines.append("")

        lines.append(HORIZONTAL_RULE)
        lines.append("")

    # Friction Points — timestamps where confusion/frustration/error_recovery detected
    if all_quotes:
        rewatch_items = _build_rewatch_list(all_quotes, display_names=display_names)
        if rewatch_items:
            lines.append(HEADING_2.format(title="Friction points"))
            lines.append("")
            lines.append(
                DESCRIPTION.format(
                    text="Moments flagged for researcher review \u2014 confusion, "
                    "frustration, or error-recovery detected."
                )
            )
            lines.append("")
            for item in rewatch_items:
                lines.append(item)
            lines.append("")
            lines.append(HORIZONTAL_RULE)
            lines.append("")

    # User Journeys
    if screen_clusters:
        task_summary = _build_task_outcome_summary(
            screen_clusters, all_quotes or [], display_names=display_names,
        )
        if task_summary:
            lines.append(HEADING_2.format(title="User journeys"))
            lines.append("")
            for item in task_summary:
                lines.append(item)
            lines.append("")
            lines.append(HORIZONTAL_RULE)
            lines.append("")

    # Appendix: Session Summary
    lines.append(HEADING_2.format(title="Appendix: Session summary"))
    lines.append("")

    now = datetime.now()
    # Build session_id → sorted speaker codes from people entries.
    _session_codes: dict[str, list[str]] = {}
    if people and people.participants:
        _prefix_order = {"m": 0, "p": 1, "o": 2}
        for code, entry in people.participants.items():
            sid_key = entry.computed.session_id
            if sid_key:
                _session_codes.setdefault(sid_key, []).append(code)
        for codes in _session_codes.values():
            codes.sort(key=lambda c: (
                _prefix_order.get(c[0], 3) if c else 3,
                int(c[1:]) if len(c) > 1 and c[1:].isdigit() else 0,
            ))

    lines.append("| Session | Speakers | Start | Duration | Source file |")
    lines.append("|---------|----------|-------|----------|-------------|")
    for session in sessions:
        sid = session.session_id
        session_num = sid[1:] if len(sid) > 1 and sid[1:].isdigit() else sid
        codes = _session_codes.get(sid, [session.participant_id])
        speakers = ", ".join(codes)
        duration = _session_duration(session, people)
        start = format_finder_date(session.session_date, now=now)
        source = session.files[0].path.name if session.files else EM_DASH
        lines.append(
            f"| {session_num} "
            f"| {speakers} "
            f"| {start} "
            f"| {duration} "
            f"| {source} |"
        )

    lines.append("")

    content = "\n".join(lines)
    md_path.write_text(content, encoding="utf-8")
    logger.info("Wrote final report: %s", md_path)

    return md_path


def write_intermediate_json(
    data: object,
    filename: str,
    output_dir: Path,
    project_name: str = "",
) -> Path:
    """Write intermediate data as JSON for debugging/resumability.

    Args:
        data: Any Pydantic model or list of models, or a plain dict.
        filename: Filename (e.g. "extracted_quotes.json").
        output_dir: Output directory.
        project_name: Project name (for OutputPaths; optional for back-compat).

    Returns:
        Path to the written file.
    """
    from bristlenose.output_paths import OutputPaths

    if project_name:
        paths = OutputPaths(output_dir, project_name)
        intermediate_dir = paths.intermediate_dir
    else:
        # Legacy fallback for callers not passing project_name
        intermediate_dir = output_dir / ".bristlenose" / "intermediate"
    intermediate_dir.mkdir(parents=True, exist_ok=True)
    path = intermediate_dir / filename

    from pydantic import BaseModel

    if isinstance(data, list):
        json_data = [
            item.model_dump(mode="json") if isinstance(item, BaseModel) else item
            for item in data
        ]
    elif isinstance(data, BaseModel):
        json_data = data.model_dump(mode="json")
    else:
        json_data = data

    path.write_text(
        json.dumps(json_data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    logger.info("Wrote intermediate: %s", path)
    return path


def write_pipeline_metadata(
    output_dir: Path,
    project_name: str,
) -> Path:
    """Write pipeline metadata JSON so render can recover the project name.

    Written once at the start of run/analyze. The file lives alongside
    the intermediate JSON (e.g. ``.bristlenose/intermediate/metadata.json``).

    Returns:
        Path to the written file.
    """
    from bristlenose.output_paths import OutputPaths

    paths = OutputPaths(output_dir, project_name)
    intermediate_dir = paths.intermediate_dir
    intermediate_dir.mkdir(parents=True, exist_ok=True)
    path = intermediate_dir / "metadata.json"
    path.write_text(
        json.dumps({"project_name": project_name}, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def read_pipeline_metadata(output_dir: Path) -> dict[str, str]:
    """Read pipeline metadata JSON from intermediate directory.

    Returns an empty dict if the file doesn't exist or can't be parsed.
    """
    for intermediate_dir in (
        output_dir / ".bristlenose" / "intermediate",
        output_dir / "intermediate",
    ):
        path = intermediate_dir / "metadata.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
    return {}


def _participant_range(sessions: list[InputSession]) -> str:
    """Format participant range: 'p1\u2013p8'."""
    ids = [s.participant_id for s in sessions]
    return format_participant_range(ids)


def _session_duration(
    session: InputSession,
    people: PeopleFile | None = None,
) -> str:
    """Get formatted duration for a session."""
    # Prefer PersonComputed.duration_seconds (works for VTT — derived
    # from last segment end_time in merge_transcript.py).
    if people and people.participants:
        for entry in people.participants.values():
            if (entry.computed.session_id == session.session_id
                    and entry.computed.duration_seconds > 0):
                return format_timecode(entry.computed.duration_seconds)
    # Fallback: InputFile.duration_seconds (audio/video with real timecodes).
    for f in session.files:
        if f.duration_seconds is not None:
            return format_timecode(f.duration_seconds)
    return EM_DASH


def _dn(pid: str, display_names: dict[str, str] | None) -> str:
    """Resolve participant_id to display name."""
    if display_names and pid in display_names:
        return display_names[pid]
    return pid


def _build_rewatch_list(
    quotes: list[ExtractedQuote],
    display_names: dict[str, str] | None = None,
) -> list[str]:
    """Build a list of timestamps worth rewatching.

    Flags moments where participants showed confusion or frustration
    — these are high-value for researchers.
    """
    flagged: list[ExtractedQuote] = []
    for q in quotes:
        is_rewatch = (
            q.intent in (QuoteIntent.CONFUSION, QuoteIntent.FRUSTRATION)
            or q.emotion in (EmotionalTone.FRUSTRATED, EmotionalTone.CONFUSED)
            or q.intensity >= 3
        )
        if is_rewatch:
            flagged.append(q)

    if not flagged:
        return []

    # Sort by session number then timecode
    flagged.sort(key=lambda q: (_session_sort_key(q.session_id), q.start_timecode))

    lines: list[str] = []
    current_pid = ""
    for q in flagged:
        if q.participant_id != current_pid:
            current_pid = q.participant_id
            lines.append(BOLD.format(text=_dn(current_pid, display_names)))
        tc = format_timecode(q.start_timecode)
        reason = (
            q.intent.value
            if q.intent in (QuoteIntent.CONFUSION, QuoteIntent.FRUSTRATION)
            else q.emotion.value
        )
        lines.append(format_friction_item(tc, reason, q.text))

    return lines


def _build_task_outcome_summary(
    screen_clusters: list[ScreenCluster],
    all_quotes: list[ExtractedQuote],
    display_names: dict[str, str] | None = None,
) -> list[str]:
    """Build a per-participant summary of user journey through screen clusters.

    Derives each participant's journey from screen cluster membership —
    which report sections contain their quotes, ordered by the product's
    logical flow (display_order).
    """
    if not screen_clusters:
        return []

    ordered = sorted(screen_clusters, key=lambda c: c.display_order)

    # participant -> list of screen labels (in display_order)
    participant_screens: dict[str, list[str]] = {}
    # participant -> session_id (first seen)
    participant_session: dict[str, str] = {}
    for cluster in ordered:
        for q in cluster.quotes:
            pid = q.participant_id
            if pid not in participant_screens:
                participant_screens[pid] = []
            if pid not in participant_session:
                participant_session[pid] = q.session_id
        pids_in_cluster = {q.participant_id for q in cluster.quotes}
        for pid in pids_in_cluster:
            if cluster.screen_label not in participant_screens[pid]:
                participant_screens[pid].append(cluster.screen_label)

    if not participant_screens:
        return []

    sorted_pids = sorted(
        participant_screens.keys(),
        key=lambda pid: _session_sort_key(participant_session.get(pid, "")),
    )

    lines: list[str] = []
    lines.append("| Session | Participant | Journey |")
    lines.append("|---------|------------|----------------------|")

    for pid in sorted_pids:
        sid = participant_session.get(pid, "")
        session_num = sid[1:] if sid.startswith("s") else sid
        journey_str = " \u2192 ".join(participant_screens[pid])
        lines.append(
            f"| {session_num} | {_dn(pid, display_names)} | {journey_str} |"
        )

    return lines
