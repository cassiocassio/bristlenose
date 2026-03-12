"""Quote card HTML formatting — blockquote rendering and badge generation."""

from __future__ import annotations

from bristlenose.models import EmotionalTone, ExtractedQuote, QuoteIntent, format_timecode
from bristlenose.stages.s12_render.html_helpers import (
    _display_name,
    _esc,
    _session_anchor,
    _split_badge_html,
    _timecode_html,
)
from bristlenose.stages.s12_render.theme_assets import _jinja_env


def _format_quote_html(
    quote: ExtractedQuote,
    video_map: dict[str, str] | None = None,
    display_names: dict[str, str] | None = None,
) -> str:
    """Render a single quote as an HTML blockquote."""
    quote_id = f"q-{quote.participant_id}-{int(quote.start_timecode)}"
    tc_html = _timecode_html(quote, video_map)
    tc = format_timecode(quote.start_timecode)

    # Speaker split badge → navigates to Sessions tab → session drill-down
    pid_esc, sid_esc, anchor = _session_anchor(quote)
    name = _display_name(quote.participant_id, display_names)
    speaker_link = _split_badge_html(
        quote.participant_id,
        name if name != quote.participant_id else None,
        nav_session=sid_esc,
        nav_anchor=anchor,
    )

    tmpl = _jinja_env.get_template("quote_card.html")
    return tmpl.render(
        quote_id=quote_id,
        timecode=_esc(tc),
        participant_id=_esc(quote.participant_id),
        emotion=_esc(quote.emotion.value),
        intent=_esc(quote.intent.value),
        researcher_context=_esc(quote.researcher_context) if quote.researcher_context else "",
        tc_html=tc_html,
        quote_text=_esc(quote.text),
        speaker_link=speaker_link,
        badges=_quote_badges(quote),
    ).rstrip("\n")


def _quote_badges(quote: ExtractedQuote) -> str:
    """Build HTML badge span for the quote's sentiment (if any).

    Uses the new sentiment field (v0.7+). Falls back to deprecated
    intent/emotion fields for backward compatibility with old intermediate JSON.
    """

    # New sentiment field takes priority
    if quote.sentiment is not None:
        css_class = f"badge badge-ai badge-{quote.sentiment.value}"
        return (
            f'<span class="{css_class}" data-badge-type="ai">'
            f"{_esc(quote.sentiment.value)}</span>"
        )

    # Backward compatibility: fall back to deprecated intent/emotion fields
    badges: list[str] = []
    if quote.intent != QuoteIntent.NARRATION:
        css_class = f"badge badge-ai badge-{quote.intent.value}"
        badges.append(
            f'<span class="{css_class}" data-badge-type="ai">'
            f"{_esc(quote.intent.value)}</span>"
        )
    if quote.emotion != EmotionalTone.NEUTRAL:
        css_class = f"badge badge-ai badge-{quote.emotion.value}"
        badges.append(
            f'<span class="{css_class}" data-badge-type="ai">'
            f"{_esc(quote.emotion.value)}</span>"
        )
    # Note: intensity badges removed — intensity is stored but not displayed
    return " ".join(badges)
