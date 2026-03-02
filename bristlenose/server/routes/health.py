"""Health check endpoint."""

from __future__ import annotations

import os

from fastapi import APIRouter

from bristlenose import __version__

router = APIRouter(prefix="/api")


DEFAULT_GITHUB_ISSUES_URL = "https://github.com/cassiocassio/bristlenose/issues/new"
DEFAULT_FEEDBACK_URL = "https://cassiocassio.co.uk/feedback.php"


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def build_health_payload() -> dict[str, object]:
    feedback_enabled = _bool_env("BRISTLENOSE_FEEDBACK_ENABLED", True)
    feedback_url = os.environ.get("BRISTLENOSE_FEEDBACK_URL", DEFAULT_FEEDBACK_URL)
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
    }


@router.get("/health")
def health() -> dict[str, object]:
    """Return server status and version."""
    return build_health_payload()
