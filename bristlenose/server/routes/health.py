"""Health check endpoint."""

from __future__ import annotations

import logging
import os
import time

from fastapi import APIRouter, Request

from bristlenose import __version__

logger = logging.getLogger(__name__)
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


def _project_key_or_none(request: Request) -> str | None:
    """This serve's project key, or None before a project is loaded."""
    factory = getattr(request.app.state, "db_factory", None)
    if factory is None:
        return None
    try:
        from bristlenose.server.mcp_server import _project_key
        from bristlenose.server.models import Project

        db = factory()
        try:
            project = db.query(Project).first()
            return _project_key(project) if project is not None else None
        finally:
            db.close()
    except Exception:  # health must never fail on a decoration
        logger.exception("health_project_key_failed")
        return None


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
        # Fresh per serve start — a proxy compares it with its handshake
        # before transmitting the bearer, so a stale file cannot hand a
        # durable credential to whatever now owns that ephemeral port.
        "instance_id": getattr(request.app.state, "mcp_instance_id", None),
        # The stable per-project key, computed HERE and nowhere else. The
        # desktop carries it into the handshake rather than deriving its own:
        # two implementations of one digest is a divergence waiting to break
        # every citation that spans the two languages. Opaque by construction
        # — a digest is not a path — so it is safe on this auth-exempt route.
        "project_key": _project_key_or_none(request),
        "active": (
            last_call is not None
            and (time.monotonic() - last_call) <= MCP_ACTIVE_WINDOW_SECONDS
        ),
    }
    return payload


@router.get("/agent-activity")
def agent_activity(request: Request) -> dict[str, int]:
    """Monotonic count of MCP tool calls this serve has answered.

    Deliberately NOT part of the ``/api/health`` payload. That route is
    auth-exempt, and a counter is precisely the activity timeline health
    refuses to publish — its ``active`` bool is coarse *on purpose*, so no
    local process can derive when the researcher's agent was working. This
    route sits behind the bearer, so only the desktop host (which already
    holds the token) can read it.

    A counter rather than a timestamp, for two reasons: the host only needs
    the *edge* (any increment → animate the sidebar antenna), and an integer
    cannot be skewed by the monotonic clock's sleep pause the way an elapsed
    reading can.

    Resets to 0 when the serve restarts. The host treats a DECREASE as a new
    serve, not as activity — see ``ServeInstance.agentCallCount``.
    """
    return {"calls": int(getattr(request.app.state, "mcp_tool_calls", 0) or 0)}


@router.put("/agent-scope")
def set_agent_scope(request: Request, body: dict[str, bool]) -> dict[str, bool]:
    """Put this serve in or out of agent scope. Desktop host only.

    Scope is a permission; serve lifetime is a cache. They must not share a
    predicate. ``ServeReaping`` keeps a sidecar warm for 90 s after its last
    window closes so ⌘W-then-Dock-click is free — but a project whose window
    just closed must stop being readable *now*, not in 90 s, and not merely
    because a well-behaved proxy re-read the handshake and stopped routing.
    An agent that already holds the port and bearer must be refused at the
    door.

    Authed, like everything under ``/api/`` that is not ``/api/health``.
    """
    readable = bool(body.get("readable", True))
    request.app.state.agent_readable = readable
    return {"readable": readable}
