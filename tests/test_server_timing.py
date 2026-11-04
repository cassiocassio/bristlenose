"""Server-Timing is the server half of the perf moment timer (docs/design-perf-ledger.md).

Off by default, so a shipped build sends nothing new; on with ``--dev`` or
``BRISTLENOSE_SERVER_TIMING=1``. It reports time to first byte and the SQL share.
"""

from __future__ import annotations

import re

import pytest

from bristlenose.server.app import create_app
from bristlenose.server.perf_timing import ENV_VAR, enabled
from tests.conftest import AuthTestClient


def _timing(monkeypatch: pytest.MonkeyPatch, value: str | None, path: str) -> str | None:
    if value is None:
        monkeypatch.delenv(ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(ENV_VAR, value)
    client = AuthTestClient(create_app(db_url="sqlite://"))
    return client.get(path).headers.get("server-timing")


def test_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _timing(monkeypatch, None, "/api/health") is None


def test_on_reports_total_and_sql_share(monkeypatch: pytest.MonkeyPatch) -> None:
    header = _timing(monkeypatch, "1", "/api/health")
    assert header is not None
    assert re.fullmatch(r'bn;dur=\d+\.\d, db;dur=\d+\.\d;desc="\d+ queries"', header), header


def test_a_route_that_touches_the_database_counts_at_least_one_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV_VAR, "1")
    app = create_app(db_url="sqlite://")
    client = AuthTestClient(app)
    seen = [
        int(m.group(1))
        for path in ("/api/projects/1/sessions", "/api/projects/1/quotes")
        if (m := re.search(r'desc="(\d+) queries"', client.get(path).headers.get("server-timing", "")))
    ]
    assert seen and all(n >= 1 for n in seen), f"expected at least one counted query, got {seen}"


@pytest.mark.parametrize(
    ("raw", "dev", "expected"),
    [(None, False, False), (None, True, True), ("0", True, False), ("1", False, True),
     ("off", True, False), ("yes", False, True)],
)
def test_enabled_env_wins_both_ways(
    monkeypatch: pytest.MonkeyPatch, raw: str | None, dev: bool, expected: bool
) -> None:
    if raw is None:
        monkeypatch.delenv(ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(ENV_VAR, raw)
    assert enabled(dev) is expected
