"""The HTML export's download filename, in CI.

Lives apart from ``test_serve_export_api.py``, which is skipped without a
frontend build — and CI's pytest job has none, so a reverted header (a 500 on
any name outside Latin-1) would have passed CI. The route only reads
``app.js`` and ``app.css`` from the build, so stubs stand in for it here.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from bristlenose.server.models import Project
from bristlenose.server.routes import export
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    (tmp_path / "app.js").write_text("// stub", encoding="utf-8")
    (tmp_path / "app.css").write_text("/* stub */", encoding="utf-8")
    monkeypatch.setattr(export, "_EXPORT_STATIC_DIR", tmp_path)
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    return AuthTestClient(app)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        # Outside Latin-1: a bare filename="…" header is a 500.
        ("駅の調査", "駅の調査-report-pl.html"),
        # Letters the old slug dropped ("Łódź" became "odz").
        ("Badanie Łódź", "Badanie Łódź-report-pl.html"),
        # Nothing visible survives: falls back rather than "-report-pl.html".
        ("???", "bristlenose-report-pl.html"),
        ("​", "bristlenose-report-pl.html"),
    ],
)
def test_the_filename_keeps_the_name_in_any_script(
    client: TestClient, name: str, expected: str
) -> None:
    db = client.app.state.db_factory()  # type: ignore[attr-defined]
    try:
        db.get(Project, 1).name = name
        db.commit()
    finally:
        db.close()
    resp = client.get("/api/projects/1/export?locale=pl")
    assert resp.status_code == 200
    disposition = resp.headers["content-disposition"]
    assert disposition.isascii()
    assert unquote(disposition.split("filename*=UTF-8''", 1)[1]) == expected
