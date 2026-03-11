"""Transcript page rendering — standalone HTML pages and inline transcript divs."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from bristlenose.models import (
    ExtractedQuote,
    FullTranscript,
    InputSession,
    PeopleFile,
    ScreenCluster,
    ThemeGroup,
    format_timecode,
)
from bristlenose.stages.render.html_helpers import (
    _document_shell_open,
    _esc,
    _footer_html,
    _report_header_html,
    _resolve_speaker_name,
    _split_badge_html,
    _tc_brackets,
)
from bristlenose.stages.render.theme_assets import (
    _get_transcript_js,
    _jinja_env,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Quote annotation data
# ---------------------------------------------------------------------------


class _QuoteAnnotation:
    """Annotation data for a single quote mapped to transcript segments."""

    __slots__ = (
        "quote_id", "participant_id", "start_tc", "end_tc",
        "verbatim_excerpt", "label", "label_type", "sentiment",
    )

    def __init__(
        self,
        quote_id: str,
        participant_id: str,
        start_tc: float,
        end_tc: float,
        verbatim_excerpt: str,
        label: str,
        label_type: str,
        sentiment: str,
    ) -> None:
        self.quote_id = quote_id
        self.participant_id = participant_id
        self.start_tc = start_tc
        self.end_tc = end_tc
        self.verbatim_excerpt = verbatim_excerpt
        self.label = label
        self.label_type = label_type
        self.sentiment = sentiment


# Keyed by session_id, contains list of annotations for that session.
_QuoteMap = dict[str, list[_QuoteAnnotation]]


def _build_transcript_quote_map(
    all_quotes: list[ExtractedQuote] | None,
    screen_clusters: list[ScreenCluster] | None,
    theme_groups: list[ThemeGroup] | None,
) -> _QuoteMap:
    """Build a mapping of quotes to their section/theme assignments.

    Returns a dict keyed by session_id, each value a list of
    _QuoteAnnotation objects for quotes in that session.
    """
    if not all_quotes:
        return {}

    # Build quote_id → (label, label_type) lookup from clusters/themes
    assignment: dict[str, tuple[str, str]] = {}
    for cluster in screen_clusters or []:
        for q in cluster.quotes:
            qid = f"q-{q.participant_id}-{int(q.start_timecode)}"
            assignment[qid] = (cluster.screen_label, "section")
    for theme in theme_groups or []:
        for q in theme.quotes:
            qid = f"q-{q.participant_id}-{int(q.start_timecode)}"
            assignment[qid] = (theme.theme_label, "theme")

    result: _QuoteMap = {}
    for q in all_quotes:
        qid = f"q-{q.participant_id}-{int(q.start_timecode)}"
        label, label_type = assignment.get(qid, ("", ""))
        ann = _QuoteAnnotation(
            quote_id=qid,
            participant_id=q.participant_id,
            start_tc=q.start_timecode,
            end_tc=q.end_timecode,
            verbatim_excerpt=q.verbatim_excerpt,
            label=label,
            label_type=label_type,
            sentiment=q.sentiment.value if q.sentiment else "",
        )
        result.setdefault(q.session_id, []).append(ann)
    return result


# ---------------------------------------------------------------------------
# Standalone transcript pages (sessions/ subdirectory)
# ---------------------------------------------------------------------------


def render_transcript_pages(
    sessions: list[InputSession],
    project_name: str,
    output_dir: Path,
    video_map: dict[str, str] | None = None,
    color_scheme: str = "auto",
    display_names: dict[str, str] | None = None,
    people: PeopleFile | None = None,
    transcripts: list[FullTranscript] | None = None,
    all_quotes: list[ExtractedQuote] | None = None,
    screen_clusters: list[ScreenCluster] | None = None,
    theme_groups: list[ThemeGroup] | None = None,
) -> list[Path]:
    """Generate per-participant transcript HTML pages in sessions/.

    If ``transcripts`` is provided, uses those directly. Otherwise reads
    transcript segments from ``transcripts-cooked/`` (if present) or
    ``transcripts-raw/``.

    Returns the list of written file paths.
    """
    from bristlenose.output_paths import OutputPaths

    paths_helper = OutputPaths(output_dir, project_name)
    paths_helper.sessions_dir.mkdir(parents=True, exist_ok=True)

    # Use provided transcripts, or load from disk
    if transcripts is None:
        from bristlenose.pipeline import load_transcripts_from_dir

        # Prefer cooked (PII-redacted) transcripts, fall back to raw
        cooked_dir = paths_helper.transcripts_cooked_dir
        raw_dir = paths_helper.transcripts_raw_dir
        if cooked_dir.is_dir() and any(cooked_dir.glob("*.txt")):
            transcripts_dir = cooked_dir
        elif raw_dir.is_dir() and any(raw_dir.glob("*.txt")):
            transcripts_dir = raw_dir
        else:
            logger.info("No transcript files found — skipping transcript pages")
            return []

        transcripts = load_transcripts_from_dir(transcripts_dir)

    if not transcripts:
        return []

    # Build quote annotation data for transcript pages
    quote_map = _build_transcript_quote_map(
        all_quotes, screen_clusters, theme_groups
    )

    paths: list[Path] = []
    for transcript in transcripts:
        page_path = _render_transcript_page(
            transcript=transcript,
            project_name=project_name,
            output_dir=output_dir,
            video_map=video_map,
            color_scheme=color_scheme,
            people=people,
            quote_map=quote_map,
        )
        paths.append(page_path)
        logger.info("Wrote transcript page: %s", page_path)

    return paths


def _render_transcript_page(
    transcript: object,  # FullTranscript or PiiCleanTranscript (avoid circular import)
    project_name: str,
    output_dir: Path,
    video_map: dict[str, str] | None = None,
    color_scheme: str = "auto",
    people: PeopleFile | None = None,
    quote_map: _QuoteMap | None = None,
) -> Path:
    """Render a single participant transcript as an HTML page in sessions/."""
    from bristlenose.models import FullTranscript as _FullTranscript
    from bristlenose.output_paths import OutputPaths
    from bristlenose.utils.text import slugify

    assert isinstance(transcript, _FullTranscript)
    pid = transcript.participant_id
    sid = transcript.session_id

    # Set up paths (session pages are in sessions/ subdirectory)
    paths = OutputPaths(output_dir, project_name)
    slug = slugify(project_name)

    # Collect all speaker codes present in the transcript (stable insertion order)
    seen_codes: dict[str, None] = {}
    for seg in transcript.segments:
        code = seg.speaker_code or pid
        if code not in seen_codes:
            seen_codes[code] = None
    speaker_codes = list(seen_codes)

    # Sort: m-codes first, then p-codes, then o-codes
    def _code_sort_key(c: str) -> tuple[int, int]:
        prefix_order = {"m": 0, "p": 1, "o": 2}
        order = prefix_order.get(c[0], 3) if c else 3
        num = int(c[1:]) if len(c) > 1 and c[1:].isdigit() else 0
        return (order, num)

    speaker_codes.sort(key=_code_sort_key)

    # Build heading: "Session 1: m1, p1, p2" or with names
    # Extract session number — "s1" → "1", legacy "p1" → "1"
    session_num = sid[1:] if len(sid) > 1 and sid[0] in "sp" and sid[1:].isdigit() else sid

    # Plain-text labels for <title>: "m1 Sarah Chen, p5 Maya, o1"
    code_labels: list[str] = []
    for code in speaker_codes:
        name = _resolve_speaker_name(code, people, None)
        if name != code:
            code_labels.append(f"{code} {name}")
        else:
            code_labels.append(code)

    # HTML spans for <h1> — each code gets its own data-participant span
    code_spans: list[str] = []
    for code in speaker_codes:
        name = _resolve_speaker_name(code, people, None)
        if name != code:
            label = f"{_esc(code)} {_esc(name)}"
        else:
            label = _esc(code)
        code_spans.append(
            f'<span class="heading-speaker" data-participant="{_esc(code)}">'
            f"{label}</span>"
        )

    # Build HTML
    parts: list[str] = []
    _w = parts.append

    title = f"Session {_esc(session_num)}: {', '.join(_esc(lb) for lb in code_labels)}"
    _w(_document_shell_open(
        title=f"{title} \u2014 {_esc(project_name)}",
        css_href="../assets/bristlenose-theme.css",
        color_scheme=color_scheme,
    ))

    # Header (same layout as report) — logos at ../assets/
    meta_parts: list[str] = []
    if transcript.source_file:
        meta_parts.append(_esc(transcript.source_file))
    if transcript.duration_seconds > 0:
        meta_parts.append(format_timecode(transcript.duration_seconds))
    t_meta_right = (
        f'<span class="header-meta">'
        f"{' &middot; '.join(meta_parts)}"
        f"</span>"
    ) if meta_parts else None
    _w(_report_header_html(
        assets_prefix="../assets",
        has_logo=paths.logo_file.exists(),
        has_dark_logo=paths.logo_dark_file.exists(),
        project_name=_esc(project_name),
        doc_title="Session transcript",
        meta_right=t_meta_right,
    ))

    # Global navigation — tabs link back to the report at the correct hash
    report_filename = f"bristlenose-{slug}-report.html"
    _w(_jinja_env.get_template("global_nav.html").render(
        report_url=f"../{report_filename}",
        active_tab="sessions",
    ))

    # Participant heading
    _w("<!-- bn-transcript-page -->")
    heading_html = f"Session {_esc(session_num)}: {', '.join(code_spans)}"
    _w(f"<h1>{heading_html}</h1>")

    # Transcript segments
    _w('<section class="transcript-body">')
    has_media = video_map is not None and sid in (video_map or {})

    # Build quote coverage lookup for this session
    session_annotations = (quote_map or {}).get(sid, [])

    for seg in transcript.segments:
        tc = format_timecode(seg.start_time)
        anchor = f"t-{int(seg.start_time)}"
        code = seg.speaker_code or pid
        is_moderator = code.startswith("m")

        # Check if this segment is covered by any quote (timecode range overlap)
        seg_quotes = [
            a for a in session_annotations
            if a.start_tc <= seg.start_time <= a.end_tc
            and a.participant_id == code
        ]
        is_quoted = bool(seg_quotes) and not is_moderator

        # Build CSS classes
        classes = ["transcript-segment"]
        if is_moderator:
            classes.append("segment-moderator")
        if is_quoted:
            classes.append("segment-quoted")
        cls_str = " ".join(classes)

        # Data attributes for glow sync (player.js) and annotation JS
        data_attrs = (
            f' data-participant="{_esc(code)}"'
            f' data-start-seconds="{seg.start_time}"'
            f' data-end-seconds="{seg.end_time}"'
        )
        if is_quoted:
            qids = " ".join(a.quote_id for a in seg_quotes)
            data_attrs += f' data-quote-ids="{_esc(qids)}"'

        _w(f'<div class="{cls_str}" id="{anchor}"{data_attrs}>')
        if has_media:
            _w(
                f'<a href="#" class="timecode" '
                f'data-participant="{_esc(pid)}" '
                f'data-seconds="{seg.start_time}">{_tc_brackets(tc)}</a>'
            )
        else:
            _w(f'<span class="timecode">{_tc_brackets(tc)}</span>')
        _w(
            f'<span class="segment-speaker" data-participant="{_esc(code)}">'
            f'{_split_badge_html(code)}</span>'
        )
        _w('<div class="segment-body">')

        # Render segment text with inline quote highlights
        seg_text = seg.text
        if is_quoted:
            seg_text = _highlight_quoted_text(seg_text, seg_quotes)
            _w(seg_text)  # already HTML-escaped inside _highlight_quoted_text
        else:
            _w(_esc(seg_text))

        _w("</div></div>")
    _w("</section>")
    _w("<!-- /bn-transcript-page -->")

    _w("</article>")
    _w(_footer_html(assets_prefix="../assets"))

    # JavaScript (player + name propagation + annotations)
    _w("<script>")
    _w("(function() {")
    _w("var BRISTLENOSE_PLAYER_URL = '../assets/bristlenose-player.html';")
    if has_media:
        _w(f"var BRISTLENOSE_VIDEO_MAP = {json.dumps(video_map)};")
    else:
        _w("var BRISTLENOSE_VIDEO_MAP = {};")

    # Quote annotation data for margin rendering (Phase 2/3)
    report_filename = f"bristlenose-{slug}-report.html"
    _w(f"var BRISTLENOSE_REPORT_URL = '../{report_filename}';")
    if session_annotations:
        qmap: dict[str, dict[str, object]] = {}
        for ann in session_annotations:
            qmap[ann.quote_id] = {
                "label": ann.label,
                "type": ann.label_type,
                "sentiment": ann.sentiment,
                "pid": ann.participant_id,
            }
        _w(f"var BRISTLENOSE_QUOTE_MAP = {json.dumps(qmap)};")
    else:
        _w("var BRISTLENOSE_QUOTE_MAP = {};")

    # Expose globals for React (PlayerContext reads from window.*).
    _w("window.BRISTLENOSE_VIDEO_MAP = BRISTLENOSE_VIDEO_MAP;")
    _w("window.BRISTLENOSE_PLAYER_URL = BRISTLENOSE_PLAYER_URL;")

    _w(_get_transcript_js())
    _w("initPlayer();")
    _w("initTranscriptNames();")
    if session_annotations:
        _w("initTranscriptAnnotations();")
    _w('_applyAppearance(_settingsStore.get("auto"));')
    _w("})();")
    _w("</script>")

    _w("</body>")
    _w("</html>")

    # Write to sessions/ subdirectory
    page_path = paths.transcript_page(transcript.session_id)
    page_path.write_text("\n".join(parts), encoding="utf-8")
    return page_path


# ---------------------------------------------------------------------------
# Highlight quoted text in transcript segments
# ---------------------------------------------------------------------------


def _highlight_quoted_text(
    segment_text: str,
    annotations: list[_QuoteAnnotation],
) -> str:
    """Wrap quoted portions of segment text in <mark> tags.

    Uses verbatim_excerpt from each annotation to find the exact substring
    in the raw segment text.  Falls back to highlighting the entire segment
    if no verbatim_excerpt is available or the substring isn't found.

    Returns HTML-safe string (all text is escaped, <mark> tags are injected).
    """
    if not annotations:
        return _esc(segment_text)

    # Collect all (start, end, quote_id) ranges to highlight
    ranges: list[tuple[int, int, str]] = []
    has_any_match = False

    for ann in annotations:
        excerpt = ann.verbatim_excerpt
        if not excerpt:
            continue
        # Simple case-insensitive substring search
        idx = segment_text.lower().find(excerpt.lower())
        if idx >= 0:
            ranges.append((idx, idx + len(excerpt), ann.quote_id))
            has_any_match = True

    if not has_any_match:
        # No verbatim excerpts matched — highlight entire segment as fallback
        qid = annotations[0].quote_id
        return (
            f'<mark class="bn-cited" data-quote-id="{_esc(qid)}">'
            f"{_esc(segment_text)}</mark>"
        )

    # Sort ranges by start position, merge overlaps
    ranges.sort(key=lambda r: r[0])
    merged: list[tuple[int, int, str]] = []
    for start, end, qid in ranges:
        if merged and start <= merged[-1][1]:
            # Overlapping — extend the previous range
            prev_start, prev_end, prev_qid = merged[-1]
            merged[-1] = (prev_start, max(prev_end, end), prev_qid)
        else:
            merged.append((start, end, qid))

    # Build output with <mark> tags around matched ranges
    parts: list[str] = []
    pos = 0
    for start, end, qid in merged:
        if pos < start:
            parts.append(_esc(segment_text[pos:start]))
        parts.append(
            f'<mark class="bn-cited" data-quote-id="{_esc(qid)}">'
            f"{_esc(segment_text[start:end])}</mark>"
        )
        pos = end
    if pos < len(segment_text):
        parts.append(_esc(segment_text[pos:]))

    return "".join(parts)


# ---------------------------------------------------------------------------
# Inline transcript rendering (for Sessions tab)
# ---------------------------------------------------------------------------


def _render_inline_transcripts(
    sessions: list[InputSession],
    project_name: str,
    output_dir: Path,
    video_map: dict[str, str] | None,
    people: PeopleFile | None,
    display_names: dict[str, str] | None,
    transcripts: list[FullTranscript] | None,
    all_quotes: list[ExtractedQuote] | None,
    screen_clusters: list[ScreenCluster] | None,
    theme_groups: list[ThemeGroup] | None,
) -> list[str]:
    """Render transcript content as inline divs for the Sessions tab panel.

    Returns a list of HTML strings (one per transcript) to be appended
    inside the Sessions tab panel, after the session grid.
    """
    if not transcripts:
        return []

    quote_map = _build_transcript_quote_map(all_quotes, screen_clusters, theme_groups)
    parts: list[str] = []

    for transcript in transcripts:
        html = _render_inline_transcript(
            transcript=transcript,
            video_map=video_map,
            people=people,
            quote_map=quote_map,
        )
        parts.append(html)

    return parts


def _render_inline_transcript(
    transcript: FullTranscript,
    video_map: dict[str, str] | None,
    people: PeopleFile | None,
    quote_map: _QuoteMap | None,
) -> str:
    """Render a single transcript as an inline HTML div (not a standalone page)."""
    pid = transcript.participant_id
    sid = transcript.session_id

    # Collect speaker codes
    seen_codes: dict[str, None] = {}
    for seg in transcript.segments:
        code = seg.speaker_code or pid
        if code not in seen_codes:
            seen_codes[code] = None
    speaker_codes = list(seen_codes)

    def _code_sort_key(c: str) -> tuple[int, int]:
        prefix_order = {"m": 0, "p": 1, "o": 2}
        order = prefix_order.get(c[0], 3) if c else 3
        num = int(c[1:]) if len(c) > 1 and c[1:].isdigit() else 0
        return (order, num)

    speaker_codes.sort(key=_code_sort_key)

    session_num = sid[1:] if len(sid) > 1 and sid[0] in "sp" and sid[1:].isdigit() else sid

    # Build label for sub-nav
    code_labels: list[str] = []
    for code in speaker_codes:
        name = _resolve_speaker_name(code, people, None)
        if name != code:
            code_labels.append(f"{code} {name}")
        else:
            code_labels.append(code)
    session_label = f"Session {_esc(session_num)}: {', '.join(_esc(lb) for lb in code_labels)}"

    # HTML spans for heading
    code_spans: list[str] = []
    for code in speaker_codes:
        name = _resolve_speaker_name(code, people, None)
        label = f"{_esc(code)} {_esc(name)}" if name != code else _esc(code)
        code_spans.append(
            f'<span class="heading-speaker" data-participant="{_esc(code)}">'
            f"{label}</span>"
        )

    p: list[str] = []
    w = p.append

    heading_html = f"Session {_esc(session_num)}: {', '.join(code_spans)}"
    w(
        f'<div class="bn-session-page" data-session="{_esc(sid)}" '
        f'data-session-label="{_esc(session_label)}" style="display:none">'
    )
    w(f"<h1>{heading_html}</h1>")

    # Transcript segments
    w('<section class="transcript-body">')
    has_media = video_map is not None and sid in (video_map or {})
    session_annotations = (quote_map or {}).get(sid, [])

    for seg in transcript.segments:
        tc = format_timecode(seg.start_time)
        anchor = f"t-{sid}-{int(seg.start_time)}"
        code = seg.speaker_code or pid
        is_moderator = code.startswith("m")

        seg_quotes = [
            a for a in session_annotations
            if a.start_tc <= seg.start_time <= a.end_tc
            and a.participant_id == code
        ]
        is_quoted = bool(seg_quotes) and not is_moderator

        classes = ["transcript-segment"]
        if is_moderator:
            classes.append("segment-moderator")
        if is_quoted:
            classes.append("segment-quoted")
        cls_str = " ".join(classes)

        data_attrs = (
            f' data-participant="{_esc(code)}"'
            f' data-start-seconds="{seg.start_time}"'
            f' data-end-seconds="{seg.end_time}"'
        )
        if is_quoted:
            qids = " ".join(a.quote_id for a in seg_quotes)
            data_attrs += f' data-quote-ids="{_esc(qids)}"'

        w(f'<div class="{cls_str}" id="{anchor}"{data_attrs}>')
        if has_media:
            w(
                f'<a href="#" class="timecode" '
                f'data-participant="{_esc(pid)}" '
                f'data-seconds="{seg.start_time}">{_tc_brackets(tc)}</a>'
            )
        else:
            w(f'<span class="timecode">{_tc_brackets(tc)}</span>')
        w(
            f'<span class="segment-speaker" data-participant="{_esc(code)}">'
            f'{_split_badge_html(code)}</span>'
        )
        w('<div class="segment-body">')

        seg_text = seg.text
        if is_quoted:
            seg_text = _highlight_quoted_text(seg_text, seg_quotes)
            w(seg_text)
        else:
            w(_esc(seg_text))

        w("</div></div>")

    w("</section>")
    w("</div>")  # .bn-session-page
    return "\n".join(p)
