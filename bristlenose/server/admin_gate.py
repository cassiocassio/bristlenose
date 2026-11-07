"""Access to ``/admin`` on a bundled beta build (T21, owner call 7 Nov 2026).

``/admin`` is the read-only database browser the Developer-ID beta mounts for the Debug menu. It
sits outside ``/api/``, so the bearer middleware never covered it, and a browser opening it cannot
send an ``Authorization`` header. Instead the app asks an authenticated endpoint for a single-use
code, opens ``/admin/?t=<code>``, and the server swaps that code for a short cookie scoped to
``/admin``. A process that can reach the port but holds neither the server token nor a fresh
code gets a 401.

Not mounted at all on ``serve --dev`` (the contributor's browser stays one click); this gate is
built only when the panel is mounted by ``_BRISTLENOSE_ADMIN_PANEL`` without ``--dev``.
"""

from __future__ import annotations

import hmac
import secrets
import threading
import time

ADMIN_COOKIE_NAME = "bristlenose_admin"
NONCE_TTL_SECONDS = 60.0


class AdminGate:
    """Single-use codes in, one session secret out. One per app; lives and dies with serve."""

    def __init__(self, ttl: float = NONCE_TTL_SECONDS) -> None:
        self._ttl = ttl
        self._lock = threading.Lock()
        self._codes: dict[str, float] = {}
        self.session = secrets.token_urlsafe(32)

    def issue(self) -> str:
        """A fresh code, good once for ``ttl`` seconds."""
        code = secrets.token_urlsafe(24)
        now = time.monotonic()
        with self._lock:
            self._codes = {c: t for c, t in self._codes.items() if t > now}
            self._codes[code] = now + self._ttl
        return code

    def redeem(self, code: str) -> bool:
        """True once per issued, unexpired code; the code is spent either way."""
        now = time.monotonic()
        with self._lock:
            held = None
            for known in self._codes:
                if hmac.compare_digest(known.encode(), code.encode()):
                    held = known
            expires = self._codes.pop(held, 0.0) if held is not None else 0.0
        return held is not None and expires > now

    def accepts_cookie(self, value: str | None) -> bool:
        if not value:
            return False
        return hmac.compare_digest(value.encode(), self.session.encode())
