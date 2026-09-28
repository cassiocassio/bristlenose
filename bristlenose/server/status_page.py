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
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from bristlenose.events import (
    Cause,
    KindEnum,
    RunCancelledEvent,
    RunFailedEvent,
    events_path,
    read_events,
)
from bristlenose.i18n import t
from bristlenose.run_condition import Condition, RunStateEnum
from bristlenose.ui_kinds import CLI_GLYPH, MessageKind

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class StatusInfo:
    """What to render. ``None`` from :func:`detect_status` means: let the SPA render."""

    kind: MessageKind
    short: str
    long: str | None
    # The structured cause (pre-formatted plain text) — never the log. This
    # page is served unauthenticated on /report/*, and bristlenose.log carries
    # absolute paths (the username), input filenames (often participant names)
    # and provider exception text that can echo prompt fragments. The log tail
    # was shown here until 28 Sep 2026.
    details: str | None
    # Document identity for the desktop shell — the fixed vocabulary posted by
    # ``_IDENTITY_SCRIPT`` ("no-run" / "in-progress" / "failed" / "cancelled" /
    # "stranded"). Deliberately
    # required, no default: a new status-page variant must declare what it is,
    # because the shell's lens availability follows this field. Mirrored by
    # ``StatusPageOutcome`` in desktop DocumentState.swift; pinned by
    # tests/test_status_page_identity_parity.py.
    outcome: str
    long_is_mono: bool = False


class ReportPolicy(str, Enum):
    """What the report surface shows when the latest analysis did not finish.

    The one open product decision in docs/design-project-condition.md (D4):
    ``LATEST_ATTEMPT`` shows the failure page over an older good report
    (today's startup behaviour, the default); ``LAST_GOOD_REPORT`` keeps
    serving the report and leaves the failure to a banner. Until 28 Sep 2026 the
    server did both — the startup seed gave the first, the running watcher gave
    the second by accident — so the same project looked different depending on
    whether the serve had restarted.
    """

    LATEST_ATTEMPT = "latest-attempt"
    LAST_GOOD_REPORT = "last-good-report"


_warned_policy: set[str] = set()


def policy_from_env() -> ReportPolicy:
    raw = os.environ.get("_BRISTLENOSE_REPORT_POLICY", "")
    try:
        return ReportPolicy(raw) if raw else ReportPolicy.LATEST_ATTEMPT
    except ValueError:
        if raw not in _warned_policy:  # once per value, not once per request
            _warned_policy.add(raw)
            logger.warning(
                "Unknown _BRISTLENOSE_REPORT_POLICY %r — using latest-attempt", raw,
            )
        return ReportPolicy.LATEST_ATTEMPT


_OUTCOME_FOR_STATE = {
    RunStateEnum.IN_PROGRESS: "in-progress",
    RunStateEnum.FAILED: "failed",
    RunStateEnum.CANCELLED: "cancelled",
    RunStateEnum.STRANDED: "stranded",
}


def page_for(
    condition: Condition,
    policy: ReportPolicy = ReportPolicy.LATEST_ATTEMPT,
    *,
    importing: bool = False,
    has_data: bool = True,
) -> str | None:
    """The status-page outcome to show, or ``None`` to let the SPA render.

    Pure: the condition, the policy, and two facts only the server knows —
    whether a re-import is in flight and whether the database holds any run
    yet. The table it implements is docs/design-project-condition.md §3.5.
    """
    if not condition.decodable:
        # Fail closed on the *condition*, not on the reader: intercepting would
        # manufacture a cause we don't have, and the report may be fine.
        logger.warning("events log does not decode — not intercepting")
        return None
    latest, report = condition.latest, condition.report
    if latest is None:
        # No run in the log — but a project analysed before the log existed
        # still has its report (the manifest vouches for it).
        return None if report is not None else "no-run"
    if latest.kind == KindEnum.TRANSCRIBE_ONLY:
        # A transcription run neither makes nor replaces a report — and after
        # one, the SPA's Sessions and transcript routes are the useful surface
        # (a "transcribed" page was tried in the POC and hid them).
        if report is not None or latest.state == RunStateEnum.COMPLETED:
            return None
        return _OUTCOME_FOR_STATE[latest.state]
    if latest.state == RunStateEnum.COMPLETED:
        # Completed on disk, but the database may not hold it yet.
        return "in-progress" if importing and not has_data else None
    if latest.state in (RunStateEnum.IN_PROGRESS, RunStateEnum.STRANDED):
        # Neither ever hides the report: a re-run in progress will replace it,
        # and a stranded run did not touch it (an incremental run leaves the
        # report in place; a --clean one stashes the log with the report, so a
        # stranded --clean run has report=None here anyway). Liveness can also
        # be wrong in the "can't tell" direction — not a reason to hide a report.
        return None if report is not None else _OUTCOME_FOR_STATE[latest.state]
    if report is not None and policy == ReportPolicy.LAST_GOOD_REPORT:
        return None
    return _OUTCOME_FOR_STATE[latest.state]


def _terminus_cause(output_dir: Path, run_id: str) -> Cause | None:
    """The forensic cause of ONE run's terminus — matched by ``run_id``.

    The page used to take its outcome from one place (the cached ``last_run``)
    and its cause from another (the file's last terminus), so a cancel after a
    failure rendered "Last run failed." over the cancellation's cause.
    """
    events_file = events_path(output_dir)
    if not events_file.exists():
        return None
    try:
        events = read_events(events_file)
    except Exception:  # noqa: BLE001 — a corrupt log must not 500 the page
        logger.exception("Failed to read events file %s", events_file)
        return None
    for ev in reversed(events):
        if ev.run_id == run_id and isinstance(ev, (RunFailedEvent, RunCancelledEvent)):
            return ev.cause
    return None


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


def _build_details(cause: Cause | None) -> str | None:
    return _format_cause(cause) or None


def detect_status(
    output_dir: Path,
    condition: Condition,
    *,
    platform: str = "",
    policy: ReportPolicy = ReportPolicy.LATEST_ATTEMPT,
    importing: bool = False,
    has_data: bool = True,
) -> StatusInfo | None:
    """Decide whether to intercept the SPA route, from the project's condition.

    Returns ``None`` when the SPA should render; a :class:`StatusInfo`
    otherwise. The decision is :func:`page_for`; this builds the page for it,
    reading the cause of the *same* run the decision was about.
    """
    outcome = page_for(condition, policy, importing=importing, has_data=has_data)
    if outcome is None:
        return None
    latest = condition.latest

    if outcome == "no-run":
        if platform == "desktop":
            return StatusInfo(
                kind=MessageKind.INFO,
                short=t("server.statusPage.noRunDesktopShort"),
                long=t("server.statusPage.noRunDesktopLong"),
                details=None,
                outcome="no-run",
            )
        return StatusInfo(
            kind=MessageKind.INFO,
            short=t("server.statusPage.noRunCliShort"),
            long="$ bristlenose run interviews/",  # literal command, not localised
            details=None,
            outcome="no-run",
            long_is_mono=True,
        )
    if outcome == "in-progress":
        return StatusInfo(
            kind=MessageKind.INFO,
            short=t("server.statusPage.inProgressShort"),
            long=None,
            details=None,
            outcome="in-progress",
        )
    if outcome == "stranded":
        return StatusInfo(
            kind=MessageKind.WARNING,
            short=t("server.statusPage.strandedShort"),
            long=t("server.statusPage.strandedLong"),
            details=None,
            outcome="stranded",
        )

    assert latest is not None
    cause = _terminus_cause(output_dir, latest.run_id)
    details = _build_details(cause)
    if outcome == "cancelled":
        return StatusInfo(
            kind=MessageKind.WARNING,
            short=t("server.statusPage.cancelledShort"),
            long=t("server.statusPage.cancelledLong"),
            details=details,
            outcome="cancelled",
        )
    # failed
    long_msg = cause.message if (cause and cause.message) else None
    return StatusInfo(
        kind=MessageKind.ERROR,
        short=t("server.statusPage.failedShort"),
        long=long_msg,
        details=details,
        outcome="failed",
    )


_PAGE_TEMPLATE = """<!doctype html>
<html lang="en"{html_attrs}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bristlenose — {title}</title>
<link rel="stylesheet" href="/report/assets/bristlenose-theme.css">
</head>
<body class="bn-status-page">
  {identity_script}
  <main class="bn-status" data-status-kind="{kind}" data-condition="{condition_key}">
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
  {refresh_script}
</body>
</html>
"""


# Document identity for the desktop shell. The WKWebView derives lens
# availability from *what document is actually showing*: the React SPA posts
# `{type: "ready"}` when it mounts, so this page posts its own identity the
# same way, at parse time, before anything else runs. Without it the shell
# could only predict from run state — and the prediction drifting from
# `detect_status` is exactly how five lit lens rows ended up sitting over a
# page that could answer none of them. Interpolation-free except the outcome
# (a fixed vocabulary, JSON-encoded, substituted via token — no str.format,
# so the JS braces stay untouched). Swift mirror: `StatusPageOutcome` in
# desktop/Bristlenose/Bristlenose/DocumentState.swift; parity pinned by
# tests/test_status_page_identity_parity.py.
_IDENTITY_SCRIPT = """<script>
(function () {
  if (window.webkit && window.webkit.messageHandlers &&
      window.webkit.messageHandlers.navigation) {
    try {
      window.webkit.messageHandlers.navigation.postMessage(
        { type: 'status-page', outcome: __BN_OUTCOME__ });
    } catch (e) { /* bridge torn down mid-navigation — nothing to tell */ }
  }
})();
</script>"""


# The page refreshes itself when the condition it describes changes. It polls
# its own URL (served without a token, like this page) and compares the
# ``data-condition`` key; only a change reloads, so a steady page never
# flickers and a stale one never outlives the run it describes. Before this,
# a status page stayed on whatever run was current when it loaded until
# something else reloaded it — the Mac's one-shot 1.5 s reload, or nothing.
_REFRESH_SCRIPT = """<script>
(function () {
  var main = document.querySelector('main.bn-status');
  if (!main) return;
  var mine = main.getAttribute('data-condition');
  if (!mine) return;
  var re = /data-condition="([^"]*)"/;
  function tick() {
    if (document.hidden) return;
    fetch(location.pathname + location.search, { cache: 'no-store', credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (t) {
        if (!t) return;
        var m = re.exec(t);
        var theirs = m ? m[1] : '__spa__';
        if (theirs !== mine) location.reload();
      })
      .catch(function () {});
  }
  setInterval(tick, 3000);
})();
</script>"""


def condition_key(condition: Condition) -> str:
    """A short fingerprint of what a status page is describing."""
    latest = condition.latest
    report = condition.report
    return "|".join([
        f"{latest.run_id}:{latest.state.value}" if latest else "-",
        report.run_id if report else "-",
        "1" if condition.decodable else "0",
    ])


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
    condition_key: str = "",
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
    # json.dumps for quoting; `</`-escaped so a future outcome value can never
    # close the script element (same discipline as the feedback config above).
    outcome_json = json.dumps(status.outcome, ensure_ascii=True).replace("</", "<\\/")
    identity_script = _IDENTITY_SCRIPT.replace("__BN_OUTCOME__", outcome_json)
    html_attrs = f" {html_root_attrs}" if html_root_attrs else ""
    return _PAGE_TEMPLATE.format(
        html_attrs=html_attrs,
        identity_script=identity_script,
        condition_key=html.escape(condition_key, quote=True),
        refresh_script=_REFRESH_SCRIPT if condition_key else "",
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
