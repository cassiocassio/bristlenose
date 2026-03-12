"""Sentiment visualisation — histogram, sparkline, and friction/rewatch list."""

from __future__ import annotations

from bristlenose.models import (
    EmotionalTone,
    ExtractedQuote,
    QuoteIntent,
    format_timecode,
)
from bristlenose.stages.s12_render.html_helpers import (
    _display_name,
    _esc,
    _session_sort_key,
    _split_badge_html,
    _tc_brackets,
)
from bristlenose.stages.s12_render.theme_assets import _jinja_env

# ---------------------------------------------------------------------------
# Sparkline (tiny inline bar chart for session table)
# ---------------------------------------------------------------------------

# Bar order: positive → neutral → negative (left to right).
# NOTE: React version (SessionsTable.tsx) uses negative → positive order.
# This file is legacy — design updates go to React only. See CLAUDE.md.
_SPARKLINE_ORDER = [
    "satisfaction", "delight", "confidence",
    "surprise",
    "doubt", "confusion", "frustration",
]
_SPARKLINE_MAX_H = 20  # px
_SPARKLINE_MIN_H = 2   # px — non-zero counts are always visible
_SPARKLINE_BAR_W = 5   # px
_SPARKLINE_GAP = 2     # px
_SPARKLINE_RADIUS = 1  # px (top corners only)
_SPARKLINE_OPACITY = 0.8


def _render_sentiment_sparkline(counts: dict[str, int]) -> str:
    """Return HTML for a tiny sentiment bar chart, or &mdash; if empty."""
    max_val = max((counts.get(s, 0) for s in _SPARKLINE_ORDER), default=0)
    if max_val == 0:
        return "&mdash;"
    bars: list[str] = []
    for s in _SPARKLINE_ORDER:
        c = counts.get(s, 0)
        if c > 0:
            h = max(round(c / max_val * _SPARKLINE_MAX_H), _SPARKLINE_MIN_H)
        else:
            h = 0
        bars.append(
            f'<span class="bn-sparkline-bar" style="'
            f"height:{h}px;"
            f"background:var(--bn-sentiment-{s});"
            f'opacity:{_SPARKLINE_OPACITY}">'
            f"</span>"
        )
    return (
        f'<div class="bn-sparkline" style="'
        f"gap:{_SPARKLINE_GAP}px"
        f'">'
        + "".join(bars)
        + "</div>"
    )


# ---------------------------------------------------------------------------
# Sentiment histogram
# ---------------------------------------------------------------------------


def _build_sentiment_html(quotes: list[ExtractedQuote]) -> str:
    """Build a horizontal-bar sentiment histogram.

    Positive sentiments on top (largest first), divider, negative below
    (smallest at top so the worst clusters near the divider).
    Each label is styled as a badge tag.  The chart is placed inside
    a ``sentiment-row`` wrapper together with a JS-rendered user-tags chart.

    Uses the new sentiment field (v0.7+). Falls back to deprecated
    intent/emotion fields for backward compatibility with old intermediate JSON.
    """
    from collections import Counter

    from bristlenose.models import Sentiment

    # New sentiment categories (v0.7+)
    negative_sentiments = {
        Sentiment.FRUSTRATION,
        Sentiment.CONFUSION,
        Sentiment.DOUBT,
    }
    positive_sentiments = {
        Sentiment.SATISFACTION,
        Sentiment.DELIGHT,
        Sentiment.CONFIDENCE,
    }
    # Sentiment.SURPRISE is neutral — not counted in histogram

    # Deprecated emotion/intent mappings (backward compat)
    negative_labels_legacy = {
        EmotionalTone.CONFUSED: "confused",
        EmotionalTone.FRUSTRATED: "frustrated",
        EmotionalTone.CRITICAL: "critical",
        EmotionalTone.SARCASTIC: "sarcastic",
    }
    positive_labels_legacy = {
        EmotionalTone.DELIGHTED: "delighted",
        EmotionalTone.AMUSED: "amused",
        QuoteIntent.DELIGHT: "delight",
    }

    neg_counts: Counter[str] = Counter()
    pos_counts: Counter[str] = Counter()
    surprise_count = 0

    for q in quotes:
        # New sentiment field takes priority
        if q.sentiment is not None:
            if q.sentiment in negative_sentiments:
                neg_counts[q.sentiment.value] += 1
            elif q.sentiment in positive_sentiments:
                pos_counts[q.sentiment.value] += 1
            elif q.sentiment == Sentiment.SURPRISE:
                surprise_count += 1
            continue

        # Backward compat: fall back to deprecated fields
        if q.emotion in negative_labels_legacy:
            neg_counts[negative_labels_legacy[q.emotion]] += 1
        if q.emotion in positive_labels_legacy:
            pos_counts[positive_labels_legacy[q.emotion]] += 1
        if q.intent == QuoteIntent.DELIGHT and q.emotion != EmotionalTone.DELIGHTED:
            pos_counts["delight"] += 1
        if q.intent == QuoteIntent.CONFUSION and q.emotion != EmotionalTone.CONFUSED:
            neg_counts["confused"] += 1
        if q.intent == QuoteIntent.FRUSTRATION and q.emotion != EmotionalTone.FRUSTRATED:
            neg_counts["frustrated"] += 1

    if not neg_counts and not pos_counts and surprise_count == 0:
        return ""

    # Badge-colour CSS class mapping
    badge_class_map: dict[str, str] = {
        # New sentiments (v0.7+)
        "frustration": "badge-frustration",
        "confusion": "badge-confusion",
        "doubt": "badge-doubt",
        "surprise": "badge-surprise",
        "satisfaction": "badge-satisfaction",
        "delight": "badge-delight",
        "confidence": "badge-confidence",
        # Deprecated (backward compat)
        "confused": "badge-confusion",
        "frustrated": "badge-frustration",
        "critical": "badge-frustration",
        "sarcastic": "",
        "delighted": "badge-delight",
        "amused": "badge-delight",
    }

    # Bar colour mapping
    colour_map = {
        # New sentiments (v0.7+)
        "frustration": "var(--bn-sentiment-frustration)",
        "confusion": "var(--bn-sentiment-confusion)",
        "doubt": "var(--bn-sentiment-doubt)",
        "surprise": "var(--bn-sentiment-surprise)",
        "satisfaction": "var(--bn-sentiment-satisfaction)",
        "delight": "var(--bn-sentiment-delight)",
        "confidence": "var(--bn-sentiment-confidence)",
        # Deprecated (backward compat) — use old token names
        "confused": "var(--colour-confusion)",
        "frustrated": "var(--colour-frustration)",
        "critical": "var(--colour-frustration)",
        "sarcastic": "var(--colour-muted)",
        "delighted": "var(--colour-delight)",
        "amused": "var(--colour-delight)",
    }

    all_counts = list(neg_counts.values()) + list(pos_counts.values())
    max_count = max(all_counts) if all_counts else 1
    max_bar_px = 180

    def _make_bar(label: str, count: int) -> dict[str, str | int]:
        width = max(4, int((count / max_count) * max_bar_px))
        colour = colour_map.get(label, "var(--colour-muted)")
        badge_cls = badge_class_map.get(label, "")
        label_cls = f"sentiment-bar-label badge {badge_cls}".strip()
        return {
            "label": _esc(label), "count": count,
            "width": width, "colour": colour, "label_cls": label_cls,
        }

    # Positive bars: sorted descending (largest at top)
    pos_bars = [_make_bar(lbl, c) for lbl, c in
                sorted(pos_counts.items(), key=lambda x: x[1], reverse=True)]

    # Surprise bar (neutral — between positive and negative)
    surprise_bar = _make_bar("surprise", surprise_count) if surprise_count > 0 else None

    # Negative bars: sorted ascending (smallest at top, worst near divider)
    neg_bars = [_make_bar(lbl, c) for lbl, c in
                sorted(neg_counts.items(), key=lambda x: x[1])]

    tmpl = _jinja_env.get_template("sentiment_chart.html")
    return tmpl.render(
        max_count=max_count,
        pos_bars=pos_bars,
        surprise_bar=surprise_bar,
        neg_bars=neg_bars,
    ).rstrip("\n")


# ---------------------------------------------------------------------------
# Friction points / rewatch list
# ---------------------------------------------------------------------------


def _has_rewatch_quotes(quotes: list[ExtractedQuote]) -> bool:
    """Check if any quotes would appear in the rewatch list (friction points)."""
    from bristlenose.models import Sentiment

    for q in quotes:
        # New sentiment field (v0.7+)
        if q.sentiment in (Sentiment.FRUSTRATION, Sentiment.CONFUSION, Sentiment.DOUBT):
            return True
        # Backward compat: deprecated fields
        if q.intent in (QuoteIntent.CONFUSION, QuoteIntent.FRUSTRATION):
            return True
        if q.emotion in (EmotionalTone.FRUSTRATED, EmotionalTone.CONFUSED):
            return True
        if q.intensity >= 3:
            return True
    return False


def _build_rewatch_html(
    quotes: list[ExtractedQuote],
    video_map: dict[str, str] | None = None,
    display_names: dict[str, str] | None = None,
) -> str:
    """Build the rewatch list (friction points) as HTML."""
    from bristlenose.models import Sentiment

    flagged: list[ExtractedQuote] = []
    for q in quotes:
        # New sentiment field (v0.7+)
        if q.sentiment in (Sentiment.FRUSTRATION, Sentiment.CONFUSION, Sentiment.DOUBT):
            flagged.append(q)
            continue
        # Backward compat: deprecated fields
        is_rewatch = (
            q.intent in (QuoteIntent.CONFUSION, QuoteIntent.FRUSTRATION)
            or q.emotion in (EmotionalTone.FRUSTRATED, EmotionalTone.CONFUSED)
            or q.intensity >= 3
        )
        if is_rewatch:
            flagged.append(q)

    if not flagged:
        return ""

    flagged.sort(key=lambda q: (_session_sort_key(q.session_id), q.start_timecode))

    # Group items by participant_id for template rendering
    groups: list[dict[str, object]] = []
    current_pid = ""
    current_items: list[dict[str, str]] = []
    for q in flagged:
        if q.participant_id != current_pid:
            if current_pid:
                _name = _display_name(current_pid, display_names)
                groups.append({
                    "pid": _split_badge_html(
                        current_pid, _name if _name != current_pid else None,
                    ),
                    "entries": current_items,
                })
            current_pid = q.participant_id
            current_items = []
        tc = format_timecode(q.start_timecode)
        # Determine reason label
        if q.sentiment is not None:
            reason = q.sentiment.value
        elif q.intent in (QuoteIntent.CONFUSION, QuoteIntent.FRUSTRATION):
            reason = q.intent.value
        else:
            reason = q.emotion.value
        snippet = q.text[:80] + ("\u2026" if len(q.text) > 80 else "")

        if video_map and q.participant_id in video_map:
            tc_html = (
                f'<a href="#" class="timecode" '
                f'data-participant="{_esc(q.participant_id)}" '
                f'data-seconds="{q.start_timecode}" '
                f'data-end-seconds="{q.end_timecode}">{_tc_brackets(tc)}</a>'
            )
        else:
            tc_html = f'<span class="timecode">{_tc_brackets(tc)}</span>'

        # Snippet links to transcript page with yellow flash highlight
        sid_esc = _esc(q.session_id) if q.session_id else _esc(q.participant_id)
        anchor = f"t-{sid_esc}-{int(q.start_timecode)}"
        snippet_html = (
            f'<a href="#" class="speaker-link" '
            f'data-nav-session="{sid_esc}" '
            f'data-nav-anchor="{anchor}">'
            f'&ldquo;{_esc(snippet)}&rdquo;</a>'
        )

        current_items.append({
            "tc_html": tc_html, "reason": reason, "snippet_html": snippet_html,
        })
    if current_pid:
        _name = _display_name(current_pid, display_names)
        groups.append({
            "pid": _split_badge_html(
                current_pid, _name if _name != current_pid else None,
            ),
            "entries": current_items,
        })

    tmpl = _jinja_env.get_template("friction_points.html")
    return tmpl.render(groups=groups).strip("\n")
