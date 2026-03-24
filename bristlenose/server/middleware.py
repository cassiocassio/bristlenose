"""Bearer token middleware for localhost API access control.

Defence-in-depth measure against opportunistic local-process scraping.
Not an authentication boundary — see SECURITY.md for honest threat framing.
"""

from __future__ import annotations

import json

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# Paths that do not require a bearer token.
# /api/health: version/status only, no project data — desktop needs it pre-auth.
# /api/docs: Swagger UI (dev convenience).
_AUTH_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/api/health",
    "/api/docs",
    "/openapi.json",
)

# Paths that require bearer token validation.
_AUTH_REQUIRED_PREFIXES: tuple[str, ...] = (
    "/api/",
    "/media/",
)

_UNAUTHORIZED_BODY = json.dumps({"detail": "Unauthorized"}).encode()


class BearerTokenMiddleware(BaseHTTPMiddleware):
    """Validate ``Authorization: Bearer <token>`` on API and media routes.

    The token is generated per server instance by ``create_app()`` and stored
    on ``app.state.auth_token``.  The same token is injected into the SPA HTML
    and printed to stdout for the desktop app to capture.

    Returns a fixed 401 JSON body for all auth failures — no distinction
    between missing/wrong token, no hints about expected format.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # Fast path: only check paths that need auth.
        if not any(path.startswith(p) for p in _AUTH_REQUIRED_PREFIXES):
            return await call_next(request)

        # Exempt paths within /api/.
        if any(path.startswith(p) for p in _AUTH_EXEMPT_PREFIXES):
            return await call_next(request)

        expected = getattr(request.app.state, "auth_token", None)
        if expected is None:
            # No token configured (e.g. tests that opt out) — allow through.
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if auth_header == f"Bearer {expected}":
            return await call_next(request)

        return Response(
            content=_UNAUTHORIZED_BODY,
            status_code=401,
            media_type="application/json",
        )
