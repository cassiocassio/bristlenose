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
        sections.append("Recent log:\n" + log_tail.strip())
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
                short="No interviews to analyse yet.",
                long="Drop a folder of interviews here to start.",
                details=None,
            )
        return StatusInfo(
            kind=MessageKind.INFO,
            short="Nothing to see here, yet.",
            long="$ bristlenose run interviews/",
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
            short="Last run was cancelled.",
            long="Re-run when ready.",
            details=details,
        )

    if outcome == OutcomeEnum.FAILED.value:
        long_msg = cause.message if (cause and cause.message) else None
        return StatusInfo(
            kind=MessageKind.ERROR,
            short="Last run failed.",
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
      <a href="{feedback_url}" target="_blank" rel="noopener noreferrer">Send feedback</a>
      <a href="{help_url}" target="_blank" rel="noopener noreferrer">Help</a>
    </nav>
  </main>
</body>
</html>
"""


def render_page(
    status: StatusInfo,
    *,
    feedback_url: str = "https://bristlenose.app/feedback.php",
    help_url: str = "https://bristlenose.app/",
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
            '<summary>Show details</summary>'
            f'<pre>{html.escape(status.details)}</pre>'
            '</details>'
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
        feedback_url=html.escape(feedback_url, quote=True),
        help_url=html.escape(help_url, quote=True),
    )
