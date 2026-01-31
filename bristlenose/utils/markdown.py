"""Markdown style template — single source of truth for all markdown formatting.

This module defines every markdown formatting convention used by Bristlenose.
If you want to change how quotes, headings, transcripts, or metadata are
formatted in any `.md` or `.txt` output, **change it here** and the rest of
the codebase will follow.

Organisation:
    1. Typographic characters (smart quotes, dashes, ellipsis)
    2. Structural format strings (headings, rules, blockquotes, tables)
    3. Transcript format strings (headers and segment lines for .txt and .md)
    4. Formatter functions (compose the constants into final output)

Every constant has a docstring showing its purpose and an example of the
rendered output.  Formatter functions document their return value with a
concrete example in the docstring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bristlenose.models import ExtractedQuote


# ═══════════════════════════════════════════════════════════════════════════
# 1. Typographic characters
# ═══════════════════════════════════════════════════════════════════════════

LQUOTE = "\u201c"
"""Left (opening) smart double quote: \u201c
Wraps participant speech.  Example: \u201cI couldn\u2019t find the button\u201d"""

RQUOTE = "\u201d"
"""Right (closing) smart double quote: \u201d
Closes participant speech.  Example: \u201cI couldn\u2019t find the button\u201d"""

EM_DASH = "\u2014"
"""Em dash: \u2014
Attributes a quote to a participant.  Example: \u201ctext\u201d \u2014 p1"""

EN_DASH = "\u2013"
"""En dash: \u2013
Joins a range of participant IDs.  Example: p1\u2013p8"""

ELLIPSIS_MARKER = "..."
"""Appended when a text snippet is truncated to SNIPPET_MAX_LENGTH."""

SNIPPET_MAX_LENGTH = 80
"""Maximum character length for truncated text snippets (e.g. friction list)."""


# ═══════════════════════════════════════════════════════════════════════════
# 2. Structural format strings — report sections
# ═══════════════════════════════════════════════════════════════════════════
#
# These are Python format strings with named placeholders.  Call them with
# .format(key=value) or use the formatter functions below.

HEADING_1 = "# {title}"
"""Top-level heading.
Example: # User Research Project"""

HEADING_2 = "## {title}"
"""Section heading (Sections, Themes, Friction points, User journeys, Appendix).
Example: ## Themes"""

HEADING_3 = "### {title}"
"""Subsection heading for individual screens or themes.
Example: ### Dashboard"""

DESCRIPTION = "_{text}_"
"""Italic description placed under a subsection heading.
Example: _Participants struggled to locate the export button._"""

HORIZONTAL_RULE = "---"
"""Horizontal rule separating major sections."""

BOLD = "**{text}**"
"""Bold text.  Used for participant IDs in friction lists and metadata keys.
Example: **p1**"""

ITALIC = "_{text}_"
"""Italic text.  Used for friction-point reasons.
Example: _confusion_"""

CODE_SPAN = "`{text}`"
"""Backtick code span.  Used for metadata badges (intent, emotion, intensity).
Example: `confusion` `frustrated` `intensity:strong`"""

BLOCKQUOTE_LINE = "> {content}"
"""A single line of a markdown blockquote.
Example: > [05:23] \u201cI couldn\u2019t find the button\u201d \u2014 p1"""


# ═══════════════════════════════════════════════════════════════════════════
# 3. Transcript format strings — .txt and .md files
# ═══════════════════════════════════════════════════════════════════════════

# --- Plain-text (.txt) transcripts ----------------------------------------

TRANSCRIPT_HEADER_TXT = "# {key}: {value}"
"""A single header line in a .txt transcript file.
Lines are prefixed with ``#`` so they read as comments.
Example: # Transcript: p1"""

TRANSCRIPT_SEGMENT_RAW_TXT = "[{timecode}] [{participant_id}]{speaker} {text}"
"""A segment line in a raw .txt transcript.
Uses the participant code (e.g. ``p1``) so researchers always know who is
speaking, even when quotes are copied into other tools.
Speaker label is optional — omitted when None.
Example: [00:16] [p1] (Speaker B) Yeah I\u2019ve been using this..."""

TRANSCRIPT_SEGMENT_COOKED_TXT = "[{timecode}] [{participant_id}] {text}"
"""A segment line in a cooked (PII-cleaned) .txt transcript.
Uses the participant code rather than a generic role label.
Example: [00:16] [p1] [NAME] has been using this..."""

# --- Markdown (.md) transcripts -------------------------------------------

MD_TRANSCRIPT_HEADING = "# {label}: {participant_id}"
"""H1 heading in a .md transcript file.
Example: # Transcript: p1"""

MD_TRANSCRIPT_META = "**{key}:** {value}"
"""A metadata line in a .md transcript.  Key is bold, value is plain.
Example: **Source:** interview_01.mp4"""

MD_TRANSCRIPT_SEGMENT_RAW = "**[{timecode}] {participant_id}**{speaker} {text}"
"""A segment in a raw .md transcript.  Timecode and participant code are bold.
Speaker label (in parentheses) is optional.
Example: **[00:16] p1** (Speaker B) Yeah I\u2019ve been using this..."""

MD_TRANSCRIPT_SEGMENT_COOKED = "**[{timecode}] {participant_id}** {text}"
"""A segment in a cooked .md transcript.  Timecode and participant code are bold.
Example: **[00:16] p1** [NAME] has been using this..."""


# ═══════════════════════════════════════════════════════════════════════════
# 4. Formatter functions
# ═══════════════════════════════════════════════════════════════════════════


def format_quote_block(
    quote: ExtractedQuote,
    display_name: str | None = None,
) -> str:
    """Format a single quote as a Markdown blockquote with metadata badges.

    Composes the researcher-context line (if present), the main quote line
    with smart quotes and em-dash attribution, and a badge line showing
    non-default intent, emotion, and intensity.

    Args:
        quote: The extracted quote to format.
        display_name: Optional display name to use instead of participant_id.

    Returns:
        Multi-line string ready to insert into a markdown document.

    Example::

        > [When asked about the settings page]
        > [05:23] \u201cI couldn\u2019t find the button\u201d \u2014 p1
        > `confusion` `frustrated` `intensity:strong`
    """
    from bristlenose.models import EmotionalTone, QuoteIntent, format_timecode

    tc = format_timecode(quote.start_timecode)
    name = display_name if display_name else quote.participant_id
    parts: list[str] = []

    # Optional researcher context prefix
    if quote.researcher_context:
        parts.append(BLOCKQUOTE_LINE.format(content=f"[{quote.researcher_context}]"))

    # The quote itself with timecode and attribution
    body = f"[{tc}] {LQUOTE}{quote.text}{RQUOTE} {EM_DASH} {name}"
    parts.append(BLOCKQUOTE_LINE.format(content=body))

    # Metadata badges — only show non-default values to keep output clean
    badges: list[str] = []
    if quote.intent != QuoteIntent.NARRATION:
        badges.append(CODE_SPAN.format(text=quote.intent.value))
    if quote.emotion != EmotionalTone.NEUTRAL:
        badges.append(CODE_SPAN.format(text=quote.emotion.value))
    if quote.intensity >= 2:
        intensity_label = "moderate" if quote.intensity == 2 else "strong"
        badges.append(CODE_SPAN.format(text=f"intensity:{intensity_label}"))

    if badges:
        parts.append(BLOCKQUOTE_LINE.format(content=" ".join(badges)))

    return "\n".join(parts)


def format_friction_item(timecode: str, reason: str, snippet: str) -> str:
    """Format a single friction-point list item.

    Truncates the snippet to :data:`SNIPPET_MAX_LENGTH` characters and
    appends :data:`ELLIPSIS_MARKER` if truncated.

    Args:
        timecode: Formatted timecode string (e.g. ``05:23``).
        reason: The friction reason (e.g. ``confusion``).
        snippet: The quote text to display.

    Returns:
        A markdown list item string.

    Example::

        - [05:23] _confusion_ \u2014 \u201cWhy is that not working?\u201d
    """
    if len(snippet) > SNIPPET_MAX_LENGTH:
        snippet = snippet[:SNIPPET_MAX_LENGTH] + ELLIPSIS_MARKER
    return (
        f"- [{timecode}] {ITALIC.format(text=reason)}"
        f" {EM_DASH} {LQUOTE}{snippet}{RQUOTE}"
    )


def format_participant_range(participant_ids: list[str]) -> str:
    """Format a range of participant IDs joined by an en-dash.

    Args:
        participant_ids: List of participant ID strings.

    Returns:
        Formatted range string, or ``'none'`` if empty.

    Examples::

        []           -> 'none'
        ['p1']       -> 'p1'
        ['p1', 'p8'] -> 'p1\u2013p8'
    """
    if not participant_ids:
        return "none"
    if len(participant_ids) == 1:
        return participant_ids[0]
    return f"{participant_ids[0]}{EN_DASH}{participant_ids[-1]}"


# ---------------------------------------------------------------------------
# Transcript header and segment formatters
# ---------------------------------------------------------------------------


def format_transcript_header_txt(
    participant_id: str,
    source_file: str,
    session_date: str,
    duration: str,
    *,
    label: str = "Transcript",
    extra_headers: dict[str, str] | None = None,
) -> str:
    """Build the ``#``-comment header block for a ``.txt`` transcript file.

    Args:
        participant_id: Session ID (e.g. ``p1``).
        source_file: Original filename.
        session_date: Formatted date string.
        duration: Formatted duration string.
        label: Header label — ``'Transcript'`` for raw,
            ``'Transcript (cooked)'`` for PII-cleaned.
        extra_headers: Additional key-value pairs to append
            (e.g. ``{'PII entities redacted': '5'}``).

    Returns:
        Multi-line header string ending with a blank line.

    Example::

        # Transcript: p1
        # Source: interview_01.mp4
        # Date: 2026-01-10
        # Duration: 00:45:00
    """
    lines = [
        TRANSCRIPT_HEADER_TXT.format(key=label, value=participant_id),
        TRANSCRIPT_HEADER_TXT.format(key="Source", value=source_file),
        TRANSCRIPT_HEADER_TXT.format(key="Date", value=session_date),
        TRANSCRIPT_HEADER_TXT.format(key="Duration", value=duration),
    ]
    if extra_headers:
        for key, value in extra_headers.items():
            lines.append(TRANSCRIPT_HEADER_TXT.format(key=key, value=value))
    return "\n".join(lines)


def format_transcript_header_md(
    participant_id: str,
    source_file: str,
    session_date: str,
    duration: str,
    *,
    label: str = "Transcript",
    extra_headers: dict[str, str] | None = None,
) -> str:
    """Build the heading + metadata block for a ``.md`` transcript file.

    Uses an H1 heading followed by bold-key metadata lines and a
    horizontal rule.

    Args:
        participant_id: Session ID (e.g. ``p1``).
        source_file: Original filename.
        session_date: Formatted date string.
        duration: Formatted duration string.
        label: Header label — ``'Transcript'`` for raw,
            ``'Transcript (cooked)'`` for PII-cleaned.
        extra_headers: Additional key-value pairs to append
            (e.g. ``{'PII entities redacted': '5'}``).

    Returns:
        Multi-line header string ending with a horizontal rule.

    Example::

        # Transcript: p1

        **Source:** interview_01.mp4
        **Date:** 2026-01-10
        **Duration:** 00:45:00

        ---
    """
    lines = [
        MD_TRANSCRIPT_HEADING.format(label=label, participant_id=participant_id),
        "",
        MD_TRANSCRIPT_META.format(key="Source", value=source_file),
        MD_TRANSCRIPT_META.format(key="Date", value=session_date),
        MD_TRANSCRIPT_META.format(key="Duration", value=duration),
    ]
    if extra_headers:
        for key, value in extra_headers.items():
            lines.append(MD_TRANSCRIPT_META.format(key=key, value=value))
    lines.append("")
    lines.append(HORIZONTAL_RULE)
    return "\n".join(lines)


def format_raw_segment_txt(
    timecode: str,
    participant_id: str,
    speaker: str | None,
    text: str,
) -> str:
    """Format a single segment line for a raw ``.txt`` transcript.

    Args:
        timecode: Formatted timecode (e.g. ``00:16``).
        participant_id: Participant session code (e.g. ``p1``).
        speaker: Optional speaker label (e.g. ``Speaker B``).
        text: Segment text.

    Returns:
        Single-line string.

    Example::

        [00:16] [p1] (Speaker B) Yeah I\u2019ve been using this...
    """
    speaker_part = f" ({speaker})" if speaker else ""
    return TRANSCRIPT_SEGMENT_RAW_TXT.format(
        timecode=timecode, participant_id=participant_id,
        speaker=speaker_part, text=text,
    )


def format_raw_segment_md(
    timecode: str,
    participant_id: str,
    speaker: str | None,
    text: str,
) -> str:
    """Format a single segment line for a raw ``.md`` transcript.

    Timecode and participant code are bold; speaker label and text are plain.

    Args:
        timecode: Formatted timecode (e.g. ``00:16``).
        participant_id: Participant session code (e.g. ``p1``).
        speaker: Optional speaker label (e.g. ``Speaker B``).
        text: Segment text.

    Returns:
        Single-line string.

    Example::

        **[00:16] p1** (Speaker B) Yeah I\u2019ve been using this...
    """
    speaker_part = f" ({speaker})" if speaker else ""
    return MD_TRANSCRIPT_SEGMENT_RAW.format(
        timecode=timecode, participant_id=participant_id,
        speaker=speaker_part, text=text,
    )


def format_cooked_segment_txt(
    timecode: str, participant_id: str, text: str,
) -> str:
    """Format a single segment line for a cooked ``.txt`` transcript.

    Args:
        timecode: Formatted timecode (e.g. ``00:16``).
        participant_id: Participant session code (e.g. ``p1``).
        text: Segment text (PII already redacted).

    Returns:
        Single-line string.

    Example::

        [00:16] [p1] [NAME] has been using this...
    """
    return TRANSCRIPT_SEGMENT_COOKED_TXT.format(
        timecode=timecode, participant_id=participant_id, text=text,
    )


def format_cooked_segment_md(
    timecode: str, participant_id: str, text: str,
) -> str:
    """Format a single segment line for a cooked ``.md`` transcript.

    Timecode and participant code are bold; text is plain.

    Args:
        timecode: Formatted timecode (e.g. ``00:16``).
        participant_id: Participant session code (e.g. ``p1``).
        text: Segment text (PII already redacted).

    Returns:
        Single-line string.

    Example::

        **[00:16] p1** [NAME] has been using this...
    """
    return MD_TRANSCRIPT_SEGMENT_COOKED.format(
        timecode=timecode, participant_id=participant_id, text=text,
    )
