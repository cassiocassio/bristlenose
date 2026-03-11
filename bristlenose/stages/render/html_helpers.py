"""Low-level HTML helper functions for the rendered report.

Document shell, header/footer, escaping, timecodes, speaker badges,
video map, and session sorting.
"""

from __future__ import annotations

import logging
from html import escape
from pathlib import Path

from bristlenose.models import (
    ExtractedQuote,
    FileType,
    InputSession,
    PeopleFile,
    format_timecode,
)
from bristlenose.stages.render.theme_assets import _jinja_env

logger = logging.getLogger(__name__)


def _document_shell_open(
    title: str, css_href: str, color_scheme: str = "auto"
) -> str:
    """Return the opening document shell (DOCTYPE through <article>)."""
    data_theme = color_scheme if color_scheme in ("light", "dark") else ""
    tmpl = _jinja_env.get_template("document_shell_open.html")
    return tmpl.render(title=title, css_href=css_href, data_theme=data_theme)


def _report_header_html(
    *,
    assets_prefix: str,
    has_logo: bool,
    has_dark_logo: bool,
    project_name: str,
    doc_title: str,
    meta_right: str | None = None,
) -> str:
    """Return the report header block (logo, title, doc type, meta)."""
    tmpl = _jinja_env.get_template("report_header.html")
    return tmpl.render(
        assets_prefix=assets_prefix,
        has_logo=has_logo,
        has_dark_logo=has_dark_logo,
        project_name=project_name,
        doc_title=doc_title,
        meta_right=meta_right,
    )


def _footer_html(assets_prefix: str = "assets") -> str:
    """Return the page footer with logo, version, feedback links, and keyboard hint.

    Args:
        assets_prefix: Path prefix for logo images. Use ``"assets"`` for pages
            at the output root (report, codebook) and ``"../assets"`` for pages
            in subdirectories (transcript pages in ``sessions/``).
    """
    from bristlenose import __version__

    tmpl = _jinja_env.get_template("footer.html")
    return tmpl.render(version=__version__, assets_prefix=assets_prefix)


def _esc(text: str) -> str:
    """HTML-escape user-supplied text."""
    return escape(text)


def _tc_brackets(tc: str) -> str:
    """Wrap timecode digits in muted-bracket markup: [00:42]."""
    return (
        f'<span class="timecode-bracket">[</span>{tc}'
        f'<span class="timecode-bracket">]</span>'
    )


def _timecode_html(
    quote: ExtractedQuote,
    video_map: dict[str, str] | None,
) -> str:
    """Build timecode HTML — clickable link if video exists, plain span otherwise."""
    tc = format_timecode(quote.start_timecode)
    if video_map and quote.participant_id in video_map:
        return (
            f'<a href="#" class="timecode" '
            f'data-participant="{_esc(quote.participant_id)}" '
            f'data-seconds="{quote.start_timecode}" '
            f'data-end-seconds="{quote.end_timecode}">{_tc_brackets(tc)}</a>'
        )
    return f'<span class="timecode">{_tc_brackets(tc)}</span>'


def _session_anchor(quote: ExtractedQuote) -> tuple[str, str, str]:
    """Return (pid_esc, sid_esc, anchor) for a quote's session navigation."""
    pid_esc = _esc(quote.participant_id)
    sid_esc = _esc(quote.session_id) if quote.session_id else pid_esc
    anchor = f"t-{sid_esc}-{int(quote.start_timecode)}"
    return pid_esc, sid_esc, anchor


def _display_name(
    pid: str, display_names: dict[str, str] | None
) -> str:
    """Resolve participant_id to display name."""
    if display_names and pid in display_names:
        return display_names[pid]
    return pid


def _split_badge_html(
    code: str,
    name: str | None = None,
    *,
    href: str | None = None,
    nav_session: str | None = None,
    nav_anchor: str | None = None,
) -> str:
    """Render a two-tone split speaker badge.

    Left half shows the speaker code (e.g. p2), right half shows the name
    (e.g. Sarah).  When name is absent or matches code, only the code half
    renders (with full border-radius via CSS :last-child).

    Optional linking: *nav_session* + *nav_anchor* produce a data-nav link
    (session drill-down); *href* produces a plain anchor.
    """
    code_esc = _esc(code)
    name_part = ""
    if name and name != code:
        name_part = f'<span class="bn-speaker-badge-name">{_esc(name)}</span>'
    badge = (
        f'<span class="bn-person-badge">'
        f'<span class="bn-speaker-badge--split">'
        f'<span class="bn-speaker-badge-code">{code_esc}</span>'
        f"{name_part}</span></span>"
    )
    if nav_session:
        return (
            f'<a href="#" class="speaker-link" '
            f'data-nav-session="{_esc(nav_session)}" '
            f'data-nav-anchor="{_esc(nav_anchor or "")}">{badge}</a>'
        )
    if href:
        return f'<a href="{_esc(href)}" class="speaker-link">{badge}</a>'
    return badge


def _oxford_list(names: list[str]) -> str:
    """Join names with Oxford commas: 'A', 'A and B', 'A, B, and C'."""
    if len(names) <= 1:
        return names[0] if names else ""
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def _participant_range(sessions: list[InputSession]) -> str:
    if not sessions:
        return "none"
    ids = [s.participant_id for s in sessions]
    if len(ids) == 1:
        return ids[0]
    return f"{ids[0]}\u2013{ids[-1]}"


def _session_duration(
    session: InputSession,
    people: PeopleFile | None = None,
) -> str:
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
    return "&mdash;"


def _build_video_map(sessions: list[InputSession]) -> dict[str, str]:
    """Map session_id → file:// URI of their video (or audio) file.

    Also adds entries keyed by participant_id for quote-level lookups.
    """
    video_map: dict[str, str] = {}
    for session in sessions:
        # Prefer video, fall back to audio
        for ftype in (FileType.VIDEO, FileType.AUDIO):
            for f in session.files:
                if f.file_type == ftype:
                    uri = f.path.resolve().as_uri()
                    video_map[session.session_id] = uri
                    video_map[session.participant_id] = uri
                    break
            if session.session_id in video_map:
                break
    return video_map


def _write_player_html(assets_dir: Path, player_path: Path) -> Path:
    """Write the popout video player page to assets/."""
    assets_dir.mkdir(parents=True, exist_ok=True)
    tmpl = _jinja_env.get_template("player.html")
    player_path.write_text(tmpl.render(), encoding="utf-8")
    logger.info("Wrote video player: %s", player_path)
    return player_path


def _resolve_speaker_name(
    pid: str,
    people: PeopleFile | None,
    display_names: dict[str, str] | None,
) -> str:
    """Resolve speaker name for transcript segments.

    Priority: short_name → full_name → pid.
    """
    if people and pid in people.participants:
        entry = people.participants[pid]
        if entry.editable.short_name:
            return entry.editable.short_name
        if entry.editable.full_name:
            return entry.editable.full_name
    return pid


def _session_sort_key(sid: str) -> tuple[int, str]:
    """Sort key that orders session IDs numerically (s1 < s2 < s10)."""
    import re

    m = re.search(r"\d+", sid)
    return (int(m.group()) if m else 0, sid)
