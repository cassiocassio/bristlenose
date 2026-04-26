"""Health check endpoint."""

from __future__ import annotations

import os

from fastapi import APIRouter, Request

from bristlenose import __version__

router = APIRouter(prefix="/api")


DEFAULT_GITHUB_ISSUES_URL = "https://github.com/cassiocassio/bristlenose/issues/new"
DEFAULT_FEEDBACK_URL = "https://bristlenose.app/feedback.php"
DEFAULT_TELEMETRY_URL = "https://bristlenose.app/telemetry.php"
DEV_TELEMETRY_URL = "/api/dev/telemetry"


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
    return build_health_payload(dev=dev)
