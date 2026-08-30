"""Machine-readable reasons for a refused request.

A refusal carries two things: an English sentence for anything that reads the
wire directly (the CLI, a log, a test), and a stable ``reason`` code the UI
localises from.  Same split as ``Cause.reason`` on the pipeline events — see
``bristlenose/refusals.py`` -- and for the same reason: prose drifts, and a
client that greps a sentence to decide what to show breaks the first time
someone improves the wording.

The wire shape is additive.  ``detail`` stays the string it has always been, so
every existing reader keeps working; ``reason`` is a sibling key next to it.
That is why this needs a handler rather than a bare ``HTTPException`` — FastAPI
serialises ``HTTPException`` as ``{"detail": ...}`` and nothing else.
"""

from __future__ import annotations

from enum import Enum

from fastapi import Request
from fastapi.responses import JSONResponse


class RefusalReason(str, Enum):
    """Why a request was refused.  Values are the locale-key suffix."""

    # AutoCode pre-flight — nothing was spent and no job exists.
    TEMPLATE_MISSING = "template_missing"
    ALREADY_RUNNING = "already_running"
    ALREADY_APPLIED = "already_applied"
    NO_QUOTES = "no_quotes"
    PROVIDER_AMBIGUOUS = "provider_ambiguous"
    PROVIDER_LOCAL = "provider_local"
    NO_API_KEY = "no_api_key"


class RefusalError(Exception):
    """A refusal that names itself.

    Raised instead of ``HTTPException`` where the client needs to say something
    specific to the researcher.  ``message`` is the English wire text and is
    **not** what the UI displays -- the UI keys off ``reason``.
    """

    def __init__(self, status_code: int, reason: RefusalReason, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.reason = reason
        self.message = message


async def refusal_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Serialise a :class:`RefusalError` as ``{"detail": str, "reason": str}``."""
    assert isinstance(exc, RefusalError)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "reason": exc.reason.value},
    )
