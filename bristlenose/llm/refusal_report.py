"""Tell the macOS host when an LLM call the serve sidecar made was refused.

A run reports through the events log and an AutoCode chip through the bridge, but a call
the sidecar makes on its own (a signal refresh, the re-apply after a run) reported to
neither, so a dead key or an empty account lit nothing. ``LLMClient.analyze`` calls
:func:`report_refusal` from its one failure path; the serve app registers a sink at
startup. A ``bristlenose run`` subprocess never registers one, so it prints nothing here
(its refusals travel in the events log, and a JSON line in its output would be read by the
host's stderr patterns as if it were an error message).

The line is ``[bristlenose] llm-refusal: {json}``, flushed, one line, well under the
512-byte pipe write that is atomic, and carries codes only: the kind, the provider slug,
the HTTP status, a coarse phase, whether the reply was the provider's own, and the
exception class name. Never ``str(exc)`` and never a body: a provider's error string can
echo the participants' words (``stages/CLAUDE.md``), and the key must not appear either.
Mirrored in Swift by ``LLMRefusalLine`` (``desktop/Bristlenose/Bristlenose``).
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)

LINE_PREFIX = "[bristlenose] llm-refusal: "
_MAX_LINE_BYTES = 480
#: The same (provider, kind) is said once in this many seconds: a re-apply that fans out
#: over twenty batches would otherwise print twenty lines for one dead key.
_REPEAT_WINDOW_S = 10.0

_sink: Callable[[str], None] | None = None
_last: dict[tuple[str, str], float] = {}


def set_refusal_sink(sink: Callable[[str], None] | None) -> None:
    """Register where a refusal line goes (the serve app), or ``None`` to stop."""
    global _sink
    _sink = sink
    _last.clear()


def _chain(exc: BaseException) -> list[BaseException]:
    seen: list[BaseException] = []
    todo: list[BaseException | None] = [exc]
    while todo and len(seen) < 8:
        cur = todo.pop(0)
        if cur is None or any(cur is s for s in seen):
            continue
        seen.append(cur)
        todo += [getattr(cur, "original_exception", None), cur.__cause__, cur.__context__]
    return seen


def phase_of(exc: BaseException, status: int | None) -> str:
    """Where the call died: ``http`` (a reply came), else ``dns``, ``tls``, ``connect``,
    ``response`` or ``unknown``. The most specific cause anywhere down the chain wins:
    httpx raises ``ConnectError`` for a name that won't resolve and for a refused
    certificate alike, so the outer class alone would mislabel both."""
    if status is not None:
        return "http"
    import socket
    import ssl

    chain = _chain(exc)
    if any(isinstance(e, ssl.SSLError) or "SSL" in type(e).__name__ for e in chain):
        return "tls"
    if any(isinstance(e, socket.gaierror) for e in chain):
        return "dns"
    names = {type(e).__name__ for e in chain}
    if names & {"ConnectError", "ConnectTimeout", "APIConnectionError"}:
        return "connect"
    if names & {"ReadTimeout", "WriteTimeout", "PoolTimeout", "ReadError", "WriteError",
                "RemoteProtocolError", "APITimeoutError"}:
        return "response"
    return "unknown"


def build_payload(provider: str, exc: BaseException) -> dict[str, object]:
    from bristlenose.llm.failure_classifier import (
        _extract_status,
        classify_exception,
        extract_provider_signature,
    )

    status = _extract_status(exc)
    payload: dict[str, object] = {
        "v": 1,
        "kind": classify_exception(provider, exc).value,
        "provider": provider,
        "http_status": status,
        "phase": phase_of(exc, status),
        "provider_signature": extract_provider_signature(exc, status),
        "error_class": type(exc).__name__[:60],
    }
    return payload


def report_refusal(provider: str, exc: BaseException) -> None:
    """Print the refusal line if a sink is registered. Never raises."""
    if _sink is None:
        return
    try:
        payload = build_payload(provider, exc)
        key = (provider, str(payload["kind"]))
        now = time.monotonic()
        if now - _last.get(key, -1e9) < _REPEAT_WINDOW_S:
            return
        _last[key] = now
        line = LINE_PREFIX + json.dumps(payload, separators=(",", ":"))
        if len(line.encode()) > _MAX_LINE_BYTES:
            payload.pop("error_class", None)
            line = LINE_PREFIX + json.dumps(payload, separators=(",", ":"))
        _sink(line)
    except Exception:
        logger.debug("llm refusal report failed", exc_info=True)
