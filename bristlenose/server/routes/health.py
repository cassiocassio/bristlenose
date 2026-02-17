"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from bristlenose import __version__

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    """Return server status and version."""
    return {
        "status": "ok",
        "version": __version__,
    }
