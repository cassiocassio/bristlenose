"""The server compresses at level 1, not Starlette's default 9.

It only binds loopback, so the ratio buys nothing; the time does cost. Measured on
the real responses at 1,500 quotes (4 Nov 2026, zlib, median of 30): /quotes
10.7 ms at level 9 and 2.5 ms at level 1, /tapestry 12.7 ms and 1.8 ms. The wire
size rises from 68 KB to 96 KB on /quotes, which on loopback is memory.
"""

from __future__ import annotations

from starlette.middleware.gzip import GZipMiddleware

from bristlenose.server.app import create_app


def test_gzip_runs_at_level_one() -> None:
    app = create_app(db_url="sqlite://")
    gzip = [m for m in app.user_middleware if m.cls is GZipMiddleware]
    assert len(gzip) == 1
    assert gzip[0].kwargs["compresslevel"] == 1
