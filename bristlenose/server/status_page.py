"""Server-rendered status page for runs the SPA can't render.

When the project has no terminus event yet, or the latest run failed or was
cancelled, the catch-all ``/report/*`` route serves this page instead of the
React SPA. The SPA's invariant becomes: it only mounts when there is a
completed run with renderable data.

See ``.claude/plans/generic-failure-surface.md`` (the branch handoff) for the
architectural rationale and ``docs/design-pipeline-diagnostic-popover.md`` for
the canonical ``MessageKind`` taxonomy this page mirrors.
"""

from __future__ import annotations

import html
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from bristlenose.events import (
    AnyEvent,
    Cause,
    EventTypeEnum,
    OutcomeEnum,
    RunCancelledEvent,
    RunFailedEvent,
    events_path,
    read_events,
)
from bristlenose.i18n import t
from bristlenose.ui_kinds import CLI_GLYPH, MessageKind

logger = logging.getLogger(__name__)

# Tail size for ``bristlenose.log`` shown inside the <details> block. Kept
# small so the page stays under a single TCP packet for cold loads.
_LOG_TAIL_BYTES = 4096


@dataclass(frozen=True)
class StatusInfo:
    """What to render. ``None`` from :func:`detect_status` means: let the SPA render."""

    kind: MessageKind
    short: str
    long: str | None
    details: str | None  # cause + log tail (pre-formatted plain text)
    long_is_mono: bool = False


def _read_last_terminus(events_file: Path) -> AnyEvent | None:
    if not events_file.exists():
        return None
    try:
        events = read_events(events_file)
    except Exception:  # noqa: BLE001 — corrupt events file shouldn't 500 serve
        logger.exception("Failed to read events file %s", events_file)
        return None
    for ev in reversed(events):
        if ev.event in (
            EventTypeEnum.RUN_COMPLETED,
            EventTypeEnum.RUN_FAILED,
            EventTypeEnum.RUN_CANCELLED,
        ):
            return ev
    return None


def _tail_log(log_file: Path, max_bytes: int = _LOG_TAIL_BYTES) -> str:
    """Return the last ``max_bytes`` of ``log_file`` (whole-line aligned)."""
    if not log_file.exists():
        return ""
    try:
        size = log_file.stat().st_size
        with log_file.open("rb") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
                f.readline()  # drop partial first line
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _format_cause(cause: Cause | None) -> str:
    if cause is None:
        return ""
    parts: list[str] = [f"category: {cause.category.value}"]
    if cause.code:
        parts.append(f"code: {cause.code}")
    if cause.stage:
        parts.append(f"stage: {cause.stage}")
    if cause.provider:
        parts.append(f"provider: {cause.provider}")
    if cause.message:
        parts.append("")
        parts.append(cause.message)
    return "\n".join(parts)


def _build_details(cause: Cause | None, log_tail: str) -> str | None:
    sections: list[str] = []
    cause_text = _format_cause(cause)
    if cause_text:
        sections.append(cause_text)
    if log_tail.strip():
        sections.append(t("server.statusPage.recentLog") + "\n" + log_tail.strip())
    return "\n\n".join(sections) if sections else None


def detect_status(
    output_dir: Path,
    last_run: dict[int, dict[str, object]] | None,
    *,
    platform: str = "",
) -> StatusInfo | None:
    """Decide whether to intercept the SPA route.

    Returns ``None`` when the SPA should render (latest run completed, OR
    unknown/unexpected state where intercepting would manufacture a cause we
    don't have). Returns a :class:`StatusInfo` for the page to render in
    every other case.

    The current data signal is :attr:`FastAPI.state.last_run` populated by
    :func:`_install_event_watcher`. That dict is empty before the first
    terminus event lands and grows from then on. We deliberately do NOT
    re-read events here for the happy path — the watcher already did.
    """
    desktop = platform == "desktop"
    entry = (last_run or {}).get(1) if last_run is not None else None

    if entry is None:
        if desktop:
            return StatusInfo(
                kind=MessageKind.INFO,
                short=t("server.statusPage.noRunDesktopShort"),
                long=t("server.statusPage.noRunDesktopLong"),
                details=None,
            )
        return StatusInfo(
            kind=MessageKind.INFO,
            short=t("server.statusPage.noRunCliShort"),
            long="$ bristlenose run interviews/",  # literal command, not localised
            details=None,
            long_is_mono=True,
        )

    outcome = entry.get("outcome")
    if outcome == OutcomeEnum.COMPLETED.value:
        return None

    # Failed / cancelled / unknown — read the terminus event for the cause.
    terminus = _read_last_terminus(events_path(output_dir))
    cause: Cause | None = None
    if isinstance(terminus, (RunFailedEvent, RunCancelledEvent)):
        cause = terminus.cause
    log_tail = _tail_log(output_dir / ".bristlenose" / "bristlenose.log")
    details = _build_details(cause, log_tail)

    if outcome == OutcomeEnum.CANCELLED.value:
        return StatusInfo(
            kind=MessageKind.WARNING,
            short=t("server.statusPage.cancelledShort"),
            long=t("server.statusPage.cancelledLong"),
            details=details,
        )

    if outcome == OutcomeEnum.FAILED.value:
        long_msg = cause.message if (cause and cause.message) else None
        return StatusInfo(
            kind=MessageKind.ERROR,
            short=t("server.statusPage.failedShort"),
            long=long_msg,
            details=details,
        )

    logger.warning("Unknown last-run outcome %r — not intercepting", outcome)
    return None


_PAGE_TEMPLATE = """<!doctype html>
<html lang="en"{html_attrs}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bristlenose — {title}</title>
<link rel="stylesheet" href="/report/assets/bristlenose-theme.css">
</head>
<body class="bn-status-page">
  <main class="bn-status" data-status-kind="{kind}">
    <div class="bn-status-glyph kind-{kind}" aria-hidden="true">{glyph}</div>
    <h1 class="bn-status-short">{short}</h1>
    {long_block}
    {details_block}
    <nav class="bn-status-footer">
      {feedback_trigger}
      <a href="{help_url}" target="_blank" rel="noopener noreferrer">{help}</a>
    </nav>
  </main>
  {feedback_overlay}
</body>
</html>
"""


# value → (emoji, common.feedback.* key). Mirrors the React modal + feedback.js.
_FEEDBACK_SENTIMENTS = [
    ("hate", "\U0001F620", "sentimentHate"),
    ("dislike", "\U0001F615", "sentimentDislike"),
    ("neutral", "\U0001F610", "sentimentNeutral"),
    ("like", "\U0001F642", "sentimentLike"),
    ("love", "\U0001F60A", "sentimentLove"),
]

# Self-contained, interpolation-free feedback script for the degraded (SPA-down)
# status page. On desktop (WKWebView) it hands the click to the native feedback
# sheet via the navigation bridge; in a browser it opens the inline modal and
# POSTs the same {version, rating, message} payload as the React modal and the
# native sheet — with the SAME strict success predicate (HTTP 200 + JSON
# {"ok": true}); anything else falls back to the clipboard. Config (endpoint
# URL, version, localised strings) arrives via window.__BN_FB__.
_FEEDBACK_SCRIPT = """<script>
(function () {
  var cfg = window.__BN_FB__ || {};
  var trigger = document.getElementById('bn-fb-trigger');
  var overlay = document.getElementById('bn-fb-overlay');
  if (!trigger || !overlay) return;
  var card = overlay.querySelector('.feedback-modal');
  var sents = document.getElementById('bn-fb-sentiments');
  var msg = document.getElementById('bn-fb-message');
  var sendBtn = document.getElementById('bn-fb-send');
  var cancelBtn = document.getElementById('bn-fb-cancel');
  var rating = '';

  function embedded() {
    return !!(window.webkit && window.webkit.messageHandlers &&
              window.webkit.messageHandlers.navigation);
  }
  function open() {
    if (embedded()) {
      try {
        window.webkit.messageHandlers.navigation.postMessage(
          { type: 'project-action', action: 'open-feedback' });
        return;
      } catch (e) { /* fall through to the web form */ }
    }
    overlay.classList.add('visible');
    overlay.setAttribute('aria-hidden', 'false');
    setTimeout(function () { if (msg) msg.focus(); }, 50);
  }
  function close() {
    overlay.classList.remove('visible');
    overlay.setAttribute('aria-hidden', 'true');
  }
  function finish(text) {
    if (card) {
      var h = document.createElement('h2');
      h.textContent = text;
      card.innerHTML = '';
      card.appendChild(h);
    }
    setTimeout(close, 1600);
  }
  function clipboard() {
    var body = 'Bristlenose feedback (v' + (cfg.version || 'unknown') + ')\\n' +
               'Rating: ' + rating + '\\n' +
               (msg && msg.value.trim() ? 'Message: ' + msg.value.trim() + '\\n' : '');
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(body).then(
        function () { finish(cfg.copied || 'Copied to clipboard.'); },
        function () { finish(cfg.copyFailed || 'Could not send feedback.'); });
    } else {
      finish(cfg.copyFailed || 'Could not send feedback.');
    }
  }

  trigger.addEventListener('click', function (e) { e.preventDefault(); open(); });
  trigger.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); }
  });
  if (sents) {
    sents.addEventListener('click', function (e) {
      var b = e.target.closest('.feedback-sentiment');
      if (!b) return;
      var all = sents.querySelectorAll('.feedback-sentiment');
      for (var i = 0; i < all.length; i++) all[i].classList.remove('selected');
      b.classList.add('selected');
      rating = b.getAttribute('data-value');
      if (sendBtn) sendBtn.disabled = false;
    });
  }
  if (cancelBtn) cancelBtn.addEventListener('click', close);
  overlay.addEventListener('click', function (e) { if (e.target === overlay) close(); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && overlay.classList.contains('visible')) close();
  });
  if (sendBtn) {
    sendBtn.addEventListener('click', function () {
      if (!rating) return;
      sendBtn.disabled = true;
      var payload = { version: cfg.version || 'unknown', rating: rating,
                      message: msg ? msg.value.trim() : '' };
      var isHttp = location.protocol === 'http:' || location.protocol === 'https:';
      if (cfg.url && isHttp) {
        fetch(cfg.url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        }).then(function (resp) {
          var ct = (resp.headers.get('Content-Type') || '').toLowerCase();
          if (resp.status === 200 && ct.indexOf('application/json') !== -1) {
            resp.json().then(function (j) {
              if (j && j.ok === true) { finish(cfg.sent || 'Feedback sent \\u2014 thank you!'); }
              else { clipboard(); }
            }, function () { clipboard(); });
          } else { clipboard(); }
        }).catch(function () { clipboard(); });
      } else {
        clipboard();
      }
    });
  }
})();
</script>"""


def _build_feedback_html(
    feedback_url: str, feedback_enabled: bool, version: str
) -> tuple[str, str]:
    """Build the (footer trigger, hidden overlay + script) HTML for feedback.

    Returns ``("", "")`` when feedback is disabled — absence is information, so
    no affordance is rendered at all (mirrors the web footer's visibility gate).
    """
    if not feedback_enabled:
        return "", ""

    trigger = (
        '<a role="button" tabindex="0" id="bn-fb-trigger" class="bn-status-feedback">'
        f'{html.escape(t("server.statusPage.sendFeedback"))}</a>'
    )

    sentiments = "".join(
        f'<button type="button" class="feedback-sentiment" data-value="{value}">'
        f'<span class="feedback-sentiment-face" aria-hidden="true">{emoji}</span>'
        f'<span class="feedback-sentiment-label">'
        f'{html.escape(t(f"common.feedback.{key}"))}</span></button>'
        for value, emoji, key in _FEEDBACK_SENTIMENTS
    )

    heading = html.escape(t("common.feedback.heading"))
    config = json.dumps(
        {
            "url": feedback_url,
            "version": version,
            "sent": t("common.feedback.sent"),
            "copied": t("common.feedback.copiedToClipboard"),
            "copyFailed": t("common.feedback.copyFailed"),
        },
        ensure_ascii=True,
    ).replace("</", "<\\/")

    overlay = (
        '<div class="bn-overlay feedback-overlay" id="bn-fb-overlay" aria-hidden="true">'
        f'<div class="bn-modal feedback-modal" role="dialog" aria-label="{heading}">'
        f"<h2>{heading}</h2>"
        f'<div class="feedback-sentiments" id="bn-fb-sentiments">{sentiments}</div>'
        f'<label class="feedback-label" for="bn-fb-message">'
        f'{html.escape(t("common.feedback.helpUsImprove"))}</label>'
        '<textarea class="feedback-textarea" id="bn-fb-message" rows="3" '
        f'placeholder="{html.escape(t("common.feedback.placeholder"), quote=True)}">'
        "</textarea>"
        '<div class="feedback-actions">'
        '<button type="button" class="feedback-btn feedback-btn-cancel" id="bn-fb-cancel">'
        f'{html.escape(t("common.buttons.cancel"))}</button>'
        '<button type="button" class="feedback-btn feedback-btn-send" id="bn-fb-send" disabled>'
        f'{html.escape(t("common.feedback.send"))}</button>'
        "</div>"
        f'<p class="bn-modal-footer">{html.escape(t("common.feedback.anonymous"))}</p>'
        "</div></div>"
        f"<script>window.__BN_FB__ = {config};</script>"
        f"{_FEEDBACK_SCRIPT}"
    )
    return trigger, overlay


def render_page(
    status: StatusInfo,
    *,
    feedback_url: str = "https://bristlenose.app/feedback.php",
    feedback_enabled: bool = True,
    help_url: str = "https://bristlenose.app/docs/",
    version: str = "",
    html_root_attrs: str = "",
) -> str:
    """Render the status page to a self-contained HTML string."""
    long_block = ""
    if status.long:
        cls = " is-mono" if status.long_is_mono else ""
        long_block = (
            f'<p class="bn-status-long{cls}">{html.escape(status.long)}</p>'
        )
    details_block = ""
    if status.details:
        details_block = (
            '<details class="bn-status-details">'
            f'<summary>{html.escape(t("server.statusPage.showDetails"))}</summary>'
            f'<pre>{html.escape(status.details)}</pre>'
            '</details>'
        )
    feedback_trigger, feedback_overlay = _build_feedback_html(
        feedback_url, feedback_enabled, version
    )
    html_attrs = f" {html_root_attrs}" if html_root_attrs else ""
    return _PAGE_TEMPLATE.format(
        html_attrs=html_attrs,
        title=html.escape(status.short),
        short=html.escape(status.short),
        long_block=long_block,
        details_block=details_block,
        kind=status.kind.value,
        glyph=html.escape(CLI_GLYPH[status.kind]),
        feedback_trigger=feedback_trigger,
        feedback_overlay=feedback_overlay,
        help_url=html.escape(help_url, quote=True),
        help=html.escape(t("server.statusPage.help")),
    )
