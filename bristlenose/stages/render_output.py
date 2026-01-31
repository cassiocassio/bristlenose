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
    format_friction_item,
    format_participant_range,
    format_quote_block,
)

logger = logging.getLogger(__name__)


def render_markdown(
    screen_clusters: list[ScreenCluster],
    theme_groups: list[ThemeGroup],
    sessions: list[InputSession],
    project_name: str,
    output_dir: Path,
    all_quotes: list[ExtractedQuote] | None = None,
) -> Path:
    """Generate the final research_report.md file.

    Args:
        screen_clusters: Screen-specific quote clusters.
        theme_groups: Thematic quote groups.
        sessions: All input sessions (for the appendix).
        project_name: Name of the research project.
        output_dir: Output directory.
        all_quotes: All extracted quotes (used for rewatch list).

    Returns:
        Path to the written Markdown file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / "research_report.md"

    lines: list[str] = []

    # Header
    lines.append(HEADING_1.format(title=project_name))
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append(
        f"Participants: {len(sessions)} ({_participant_range(sessions)})"
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
                lines.append(format_quote_block(quote))
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
                lines.append(format_quote_block(quote))
                lines.append("")

        lines.append(HORIZONTAL_RULE)
        lines.append("")

    # Friction Points — timestamps where confusion/frustration/error_recovery detected
    if all_quotes:
        rewatch_items = _build_rewatch_list(all_quotes)
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
    if all_quotes and sessions:
        task_summary = _build_task_outcome_summary(all_quotes, sessions)
        if task_summary:
            lines.append(HEADING_2.format(title="User journeys"))
            lines.append("")
            for item in task_summary:
                lines.append(item)
            lines.append("")
            lines.append(HORIZONTAL_RULE)
            lines.append("")

    # Appendix: Participant Summary
    lines.append(HEADING_2.format(title="Appendix: Participant summary"))
    lines.append("")
    lines.append("| Session | Date | Start | Duration | Source file |")
    lines.append("|---------|------|------|----------|-------------|")

    for session in sessions:
        duration = _session_duration(session)
        source = session.files[0].path.name if session.files else EM_DASH
        lines.append(
            f"| {session.participant_id} "
            f"| {session.session_date.strftime('%d-%m-%Y')} "
            f"| {session.session_date.strftime('%H:%M')} "
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
) -> Path:
    """Write intermediate data as JSON for debugging/resumability.

    Args:
        data: Any Pydantic model or list of models, or a plain dict.
        filename: Filename (e.g. "extracted_quotes.json").
        output_dir: Output directory.

    Returns:
        Path to the written file.
    """
    intermediate_dir = output_dir / "intermediate"
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


def _participant_range(sessions: list[InputSession]) -> str:
    """Format participant range: 'p1\u2013p8'."""
    ids = [s.participant_id for s in sessions]
    return format_participant_range(ids)


def _session_duration(session: InputSession) -> str:
    """Get formatted duration for a session."""
    for f in session.files:
        if f.duration_seconds is not None:
            return format_timecode(f.duration_seconds)
    return EM_DASH


def _build_rewatch_list(quotes: list[ExtractedQuote]) -> list[str]:
    """Build a list of timestamps worth rewatching.

    Flags moments where participants showed confusion, frustration,
    or were in error-recovery — these are high-value for researchers.
    """
    from bristlenose.models import JourneyStage

    flagged: list[ExtractedQuote] = []
    for q in quotes:
        is_rewatch = (
            q.intent in (QuoteIntent.CONFUSION, QuoteIntent.FRUSTRATION)
            or q.emotion in (EmotionalTone.FRUSTRATED, EmotionalTone.CONFUSED)
            or q.journey_stage == JourneyStage.ERROR_RECOVERY
            or q.intensity >= 3
        )
        if is_rewatch:
            flagged.append(q)

    if not flagged:
        return []

    # Sort by participant then timecode
    flagged.sort(key=lambda q: (q.participant_id, q.start_timecode))

    lines: list[str] = []
    current_pid = ""
    for q in flagged:
        if q.participant_id != current_pid:
            current_pid = q.participant_id
            lines.append(BOLD.format(text=current_pid))
        tc = format_timecode(q.start_timecode)
        reason = (
            q.intent.value
            if q.intent in (QuoteIntent.CONFUSION, QuoteIntent.FRUSTRATION)
            else q.emotion.value
        )
        lines.append(format_friction_item(tc, reason, q.text))

    return lines


def _build_task_outcome_summary(
    quotes: list[ExtractedQuote],
    sessions: list[InputSession],
) -> list[str]:
    """Build a per-participant summary of journey stages observed.

    This gives researchers a quick overview of how far each participant
    progressed through the user journey.
    """
    from collections import Counter

    from bristlenose.models import JourneyStage

    # Ordered stages representing a typical e-commerce flow
    stage_order = [
        JourneyStage.LANDING,
        JourneyStage.BROWSE,
        JourneyStage.SEARCH,
        JourneyStage.PRODUCT_DETAIL,
        JourneyStage.CART,
        JourneyStage.CHECKOUT,
    ]

    # Group quotes by participant
    by_participant: dict[str, list[ExtractedQuote]] = {}
    for q in quotes:
        by_participant.setdefault(q.participant_id, []).append(q)

    lines: list[str] = []
    lines.append("| Participant | Stages | Friction points |")
    lines.append("|------------|----------------------|-----------------|")

    pids = sorted(by_participant.keys())
    for pid in pids:
        pq = by_participant[pid]
        stage_counts = Counter(q.journey_stage for q in pq)

        # Stages observed (exclude OTHER)
        observed = [s for s in stage_order if stage_counts.get(s, 0) > 0]
        observed_str = (
            " \u2192 ".join(s.value for s in observed) if observed else "other"
        )

        # Count friction points (confusion + frustration)
        friction = sum(
            1 for q in pq
            if q.intent in (QuoteIntent.CONFUSION, QuoteIntent.FRUSTRATION)
            or q.emotion in (EmotionalTone.FRUSTRATED, EmotionalTone.CONFUSED)
        )

        lines.append(f"| {pid} | {observed_str} | {friction} |")

    return lines
