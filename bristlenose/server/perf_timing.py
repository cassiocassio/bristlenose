"""Server-Timing for the moment timer: how long a request took, and how much of it was SQL.

One half of the shared perf vocabulary (the Mac side is signposts, the page side is
``performance.mark``): the page reads ``PerformanceResourceTiming.serverTiming`` and the
Network panel shows it, so a click, its request and its render can sit on one timeline.

Off unless asked for (``serve --dev``, or ``BRISTLENOSE_SERVER_TIMING=1``), so a shipped
build sends nothing new. ``bn`` is the time to the first byte of the response (not the
whole body), ``db`` the time inside SQL cursors with the statement count in ``desc``.
Pure ASGI rather than ``BaseHTTPMiddleware``: it must not add the cost it measures.
"""

from __future__ import annotations

import contextvars
import os
import time
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from starlette.types import ASGIApp, Message, Receive, Scope, Send

ENV_VAR = "BRISTLENOSE_SERVER_TIMING"

_acc: contextvars.ContextVar[dict[str, float] | None] = contextvars.ContextVar(
    "bn_server_timing", default=None
)
_listening = False


def enabled(dev: bool) -> bool:
    """The env var wins both ways; unset, ``--dev`` turns it on."""
    raw = os.environ.get(ENV_VAR)
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return dev


def _install_sql_listeners() -> None:
    global _listening
    if _listening:
        return
    _listening = True

    @event.listens_for(Engine, "before_cursor_execute")
    def _before(conn: Any, cursor: Any, statement: Any, parameters: Any, context: Any,
                executemany: Any) -> None:
        if _acc.get() is not None:
            context._bn_t0 = time.perf_counter()

    @event.listens_for(Engine, "after_cursor_execute")
    def _after(conn: Any, cursor: Any, statement: Any, parameters: Any, context: Any,
               executemany: Any) -> None:
        acc = _acc.get()
        started = getattr(context, "_bn_t0", None)
        if acc is not None and started is not None:
            acc["db_ms"] += (time.perf_counter() - started) * 1000
            acc["queries"] += 1


class ServerTimingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        _install_sql_listeners()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        acc: dict[str, float] = {"db_ms": 0.0, "queries": 0}
        token = _acc.set(acc)
        started = time.perf_counter()

        async def send_with_timing(message: Message) -> None:
            if message["type"] == "http.response.start":
                total = (time.perf_counter() - started) * 1000
                value = (
                    f'bn;dur={total:.1f}, db;dur={acc["db_ms"]:.1f};'
                    f'desc="{int(acc["queries"])} queries"'
                )
                headers = list(message.get("headers", []))
                headers.append((b"server-timing", value.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_timing)
        finally:
            _acc.reset(token)
