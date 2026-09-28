"""Bearer token middleware for localhost API access control.

Defence-in-depth measure against opportunistic local-process scraping.
Not an authentication boundary — see SECURITY.md for honest threat framing.
"""

from __future__ import annotations

import json

from starlette.datastructures import Headers
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

# Paths that do not require a bearer token.
# /api/health: version/status only, no project data — desktop needs it pre-auth.
# /api/docs: Swagger UI (dev convenience).
_AUTH_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/api/health",
    "/api/docs",
    "/openapi.json",
)

# Paths that require bearer token validation.
# NOTE: /media/ is NOT included — <video> and <audio> elements cannot send
# Authorization headers.  Media files are protected by the path-traversal
# guard, extension allowlist, and localhost binding instead.
# /mcp is included UNCONDITIONALLY (fail closed even when the mount was
# skipped because the mcp extra isn't installed).
_AUTH_REQUIRED_PREFIXES: tuple[str, ...] = (
    "/api/",
    "/mcp",
)

_UNAUTHORIZED_BODY = json.dumps({"detail": "Unauthorized"}).encode()

# Cookie name carrying the same token as the Bearer header.  Set on the SPA
# HTML response so plain browser navigations (e.g. the export `<a download>`
# anchor click) can authenticate without JS adding the header.  CORS
# middleware blocks all cross-origin requests, so CSRF is not in scope — and
# LoopbackHostMiddleware refuses a DNS-rebound page, which CORS cannot see
# because to the browser it is same-origin.
AUTH_COOKIE_NAME = "bristlenose_auth"

# Hostnames serve answers to.  serve binds 127.0.0.1 only, and every
# legitimate client names it by one of these: the WKWebView and every Swift /
# .mcpb fetch use http://127.0.0.1:<port>, the CLI prints that URL, and the
# `serve --dev` Vite proxy forwards the browser's localhost:5173.
_LOOPBACK_HOSTNAMES: frozenset[str] = frozenset({"127.0.0.1", "localhost", "::1"})


def is_loopback_host(host: str) -> bool:
    """True iff a ``Host`` header names loopback, on any port.

    Parses the bracketed IPv6 form itself: Starlette's TrustedHostMiddleware
    splits on the first ``:``, so ``[::1]:8150`` reads as ``[`` there.
    """
    if host.startswith("["):
        end = host.find("]")
        if end == -1:
            return False
        name, rest = host[1:end], host[end + 1 :]
        if rest and not rest.startswith(":"):
            return False
    else:
        name = host.partition(":")[0]
    return name.lower() in _LOOPBACK_HOSTNAMES


class LoopbackHostMiddleware:
    """Refuse any request whose ``Host`` is not loopback — the DNS-rebinding gate.

    A rebinding page (``http://rebind.attacker.example:8150`` re-resolved to
    127.0.0.1) is same-origin with serve as far as the browser knows, so CORS
    never fires and ``/report/`` would hand it the auth token in the SPA HTML
    plus the auth cookie. The ``Host`` header still carries the attacker's
    name, and a page cannot forge it. Pure ASGI, outermost, so nothing —
    routing, auth, the MCP mount, /admin — runs for a foreign Host.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket") and not is_loopback_host(
            Headers(scope=scope).get("host", "")
        ):
            if scope["type"] == "websocket":
                # Close before accept: the server answers the handshake 403.
                await send({"type": "websocket.close", "code": 1008})
            else:
                await PlainTextResponse("Invalid host header", status_code=400)(
                    scope, receive, send
                )
            return
        await self.app(scope, receive, send)


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

        is_mcp = path.startswith("/mcp")
        if is_mcp and request.method == "GET":
            # A naive browser click on the terminal's MCP link: the mounted
            # explainer page is deliberately unauthenticated (no project
            # data, no token — same exemption class as /api/health). MCP
            # protocol GETs ask for text/event-stream, never text/html.
            accept = request.headers.get("accept", "")
            if "text/html" in accept and "text/event-stream" not in accept:
                return await call_next(request)

        # /mcp validates against the MCP-scoped token, everything else
        # against the server token. The two are the same value unless the
        # host injected a separate _BRISTLENOSE_MCP_TOKEN (the macOS app
        # does — its durable Keychain token). Scoping matters because the
        # MCP token is the one credential that deliberately leaves the
        # trust boundary (pasted into another vendor's config file): it
        # must open the read-only /mcp tools and nothing else — never
        # /api/* writes or the persons endpoints.
        if is_mcp:
            expected = getattr(request.app.state, "mcp_token", None) or getattr(
                request.app.state, "auth_token", None
            )
        else:
            expected = getattr(request.app.state, "auth_token", None)
        if expected is None:
            # No token configured (e.g. tests that opt out) — allow through.
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if auth_header == f"Bearer {expected}":
            return await call_next(request)

        # Cookie fallback for plain browser navigations (e.g. export anchor
        # clicks) that don't carry the Authorization header. /mcp is
        # bearer-only: MCP clients always send the header, and keeping the
        # cookie out closes the same-host-different-port ride-along.
        if not is_mcp and request.cookies.get(AUTH_COOKIE_NAME) == expected:
            return await call_next(request)

        return Response(
            content=_UNAUTHORIZED_BODY,
            status_code=401,
            media_type="application/json",
        )
