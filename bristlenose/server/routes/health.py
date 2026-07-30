"""Health check endpoint."""

from __future__ import annotations

import os
import time

from fastapi import APIRouter, Request

from bristlenose import __version__

router = APIRouter(prefix="/api")


DEFAULT_GITHUB_ISSUES_URL = "https://github.com/cassiocassio/bristlenose/issues/new"
DEFAULT_FEEDBACK_URL = "https://bristlenose.app/feedback.php"
DEFAULT_HELP_URL = "https://bristlenose.app/docs/"
DEFAULT_TELEMETRY_URL = "https://bristlenose.app/telemetry.php"
DEV_TELEMETRY_URL = "/api/dev/telemetry"

#: Tool-call freshness that still counts as "an agent is connected now".
#: Wider than the desktop's 20s poll so thinking gaps between tool calls
#: don't flicker the sidebar badge.
MCP_ACTIVE_WINDOW_SECONDS = 120


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def build_health_payload(*, dev: bool = False) -> dict[str, object]:
    feedback_enabled = _bool_env("BRISTLENOSE_FEEDBACK_ENABLED", True)
    feedback_url = os.environ.get("BRISTLENOSE_FEEDBACK_URL", DEFAULT_FEEDBACK_URL)
    telemetry_enabled = _bool_env("BRISTLENOSE_TELEMETRY_ENABLED", True)
    telemetry_default = DEV_TELEMETRY_URL if dev else DEFAULT_TELEMETRY_URL
    telemetry_url = os.environ.get("BRISTLENOSE_TELEMETRY_URL", telemetry_default)
    github_issues_url = os.environ.get(
        "BRISTLENOSE_GITHUB_ISSUES_URL",
        DEFAULT_GITHUB_ISSUES_URL,
    )
    return {
        "status": "ok",
        "version": __version__,
        "links": {
            "github_issues_url": github_issues_url,
        },
        "feedback": {
            "enabled": feedback_enabled,
            "url": feedback_url,
        },
        "telemetry": {
            "enabled": telemetry_enabled,
            "url": telemetry_url,
        },
    }


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    """Return server status and version."""
    dev = bool(getattr(request.app.state, "dev", False))
    payload = build_health_payload(dev=dev)
    # MCP status for the desktop host. `mounted` lets the Connect Agent sheet
    # say "not available in this build" instead of handing out an address
    # that 404s — the mount is optional (the `mcp` extra), and only the
    # server knows whether the import succeeded. `active` is "an MCP agent
    # called a tool within the last two minutes" — the sidebar's antenna
    # badge reads it on a poll. A bare bool, not a timestamp: /api/health is
    # auth-exempt, and elapsed seconds would hand any local process a
    # 1s-resolution timeline of the researcher's agent usage. Monotonic
    # under-counts across sleep (mach_absolute_time pauses), so the badge
    # can linger up to the window after wake — acceptable only while the
    # sole consumer is this ≤2-minute freshness bool; a future "last active
    # N min ago" label must NOT reuse this clock.
    last_call = getattr(request.app.state, "mcp_last_tool_call", None)
    payload["mcp"] = {
        "mounted": bool(getattr(request.app.state, "mcp_mounted", False)),
        "active": (
            last_call is not None
            and (time.monotonic() - last_call) <= MCP_ACTIVE_WINDOW_SECONDS
        ),
    }
    return payload
