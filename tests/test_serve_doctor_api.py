"""Tests for the serve-mode ``GET /api/doctor`` system-health endpoint.

The endpoint runs the local (non-network) doctor checks in-process and returns
them as structured JSON for the desktop app's native Health window. These tests
mock the check aggregator so they don't depend on the CI machine's ffmpeg /
whisper / disk state — the contract under test is the JSON shape and auth, not
the check outcomes.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bristlenose import doctor as doctor_mod
from bristlenose.doctor import CheckResult, CheckStatus, DoctorReport
from bristlenose.server.app import create_app
from tests.conftest import AuthTestClient

_FAKE_REPORT = DoctorReport(
    results=[
        CheckResult(status=CheckStatus.OK, label="FFmpeg", detail="6.1.1"),
        CheckResult(
            status=CheckStatus.WARN,
            label="Disk space",
            detail="900 MB free",
            fix_key="low_disk_space",
        ),
        CheckResult(
            status=CheckStatus.FAIL,
            label="Serve mode",
            detail="missing: fastapi",
            fix_key="serve_deps_missing",
        ),
        CheckResult(
            status=CheckStatus.SKIP,
            label="PII redaction",
            detail="off (use --redact-pii to enable)",
        ),
    ]
)


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch):
    """A serve app whose doctor checks are mocked to a fixed report."""
    monkeypatch.setattr(doctor_mod, "run_local_checks", lambda _settings: _FAKE_REPORT)
    app = create_app(dev=True, db_url="sqlite://")
    # Non-None so the route doesn't call the env-dependent load_settings().
    app.state.settings = object()
    return app


@pytest.fixture()
def client(app) -> TestClient:
    return AuthTestClient(app)


def test_returns_structured_checks(client: TestClient) -> None:
    resp = client.get("/api/doctor")
    assert resp.status_code == 200
    body = resp.json()
    assert "checks" in body
    checks = body["checks"]
    assert len(checks) == 4
    for check in checks:
        assert set(check.keys()) == {"status", "label", "detail", "fix_key", "fix"}


def test_status_values_serialise_as_enum_values(client: TestClient) -> None:
    checks = client.get("/api/doctor").json()["checks"]
    statuses = [c["status"] for c in checks]
    # CheckStatus values: OK="ok", WARN="warn", FAIL="fail", SKIP="--".
    assert statuses == ["ok", "warn", "fail", "--"]


def test_labels_and_fix_keys_pass_through(client: TestClient) -> None:
    checks = client.get("/api/doctor").json()["checks"]
    by_label = {c["label"]: c for c in checks}
    assert by_label["Serve mode"]["fix_key"] == "serve_deps_missing"
    assert by_label["FFmpeg"]["detail"] == "6.1.1"
    # A check with no fix reports an empty string, not a missing key.
    assert by_label["FFmpeg"]["fix_key"] == ""
    assert by_label["FFmpeg"]["fix"] == ""
    # A fixable check resolves its slug to human-readable install-aware text.
    assert by_label["Serve mode"]["fix"] != ""
    assert by_label["Disk space"]["fix"] != ""


def test_requires_auth(app) -> None:
    """The endpoint is NOT auth-exempt (unlike /api/health)."""
    bare = TestClient(app)  # no bearer token injected
    resp = bare.get("/api/doctor")
    assert resp.status_code == 401


def test_health_endpoint_stays_auth_exempt(app) -> None:
    """Guard rail: /api/health must remain reachable without a token."""
    bare = TestClient(app)
    assert bare.get("/api/health").status_code == 200
