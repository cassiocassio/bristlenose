"""Each clip and screens export has its own id, said by its start and by every status read.

A window carries its chips across a reload (RE#38, decision #36); the id is how a carried chip
knows the server's one export of that kind is still the export it started, and not a newer one
another window began meanwhile (a Copy Screens must never copy someone else's export).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from bristlenose.server.app import create_app
from bristlenose.server.routes import clips_export, screens_export
from tests.conftest import AuthTestClient

_FIXTURE = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


@pytest.fixture(autouse=True)
def _no_jobs() -> Any:
    clips_export._jobs.clear()
    screens_export._jobs.clear()
    yield
    clips_export._jobs.clear()
    screens_export._jobs.clear()


async def _nothing(*_a: Any, **_k: Any) -> None:
    return None


def test_each_clip_export_has_its_own_id_and_the_status_says_it(tmp_path: Path) -> None:
    app = create_app(project_dir=_FIXTURE, dev=True, db_url="sqlite://")
    media = ({"s1": (tmp_path / "s1.mp4", False)}, {"s1": 120.0})
    with AuthTestClient(app) as client, \
            patch.object(clips_export.FFmpegBackend, "check_available", return_value=(True, "")), \
            patch.object(clips_export, "_load_session_media", return_value=media), \
            patch.object(clips_export, "_resolve_output_dir", return_value=tmp_path), \
            patch.object(clips_export, "_run_clip_extraction", _nothing):
        assert client.get("/api/projects/1/export/clips/status").json()["job_id"] is None
        first = client.post("/api/projects/1/export/clips", json={"ids": ["q-p1-10"]}).json()
        assert isinstance(first["job_id"], str) and first["job_id"]
        assert client.get("/api/projects/1/export/clips/status").json()["job_id"] == first["job_id"]
        clips_export._jobs[1]["status"] = "completed"
        second = client.post("/api/projects/1/export/clips", json={"ids": ["q-p1-10"]}).json()
        assert second["job_id"] != first["job_id"]
        assert client.get("/api/projects/1/export/clips/status").json()["job_id"] == second["job_id"]


def test_each_screens_export_has_its_own_id_and_the_status_says_it(tmp_path: Path) -> None:
    app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
    shot = {"filename": "p1-01.jpg", "session_id": "s1", "t": 1.0, "crop": [0, 0, 1, 1]}
    with AuthTestClient(app) as client, \
            patch.object(screens_export, "screens_enabled", return_value=True), \
            patch.object(screens_export, "derive_project_screens",
                         return_value=({"screens": []}, {})), \
            patch.object(screens_export, "shot_list", return_value=[shot]), \
            patch.object(screens_export, "video_sessions", return_value={}), \
            patch.object(screens_export, "_run", _nothing):
        assert client.get("/api/projects/1/export/screens/status").json()["job_id"] is None
        first = client.post("/api/projects/1/export/screens").json()
        assert first["status"] == "started"
        assert isinstance(first["job_id"], str) and first["job_id"]
        assert client.get("/api/projects/1/export/screens/status").json()["job_id"] == first["job_id"]
        screens_export._jobs[1]["status"] = "completed"
        second = client.post("/api/projects/1/export/screens").json()
        assert second["job_id"] != first["job_id"]
        assert client.get("/api/projects/1/export/screens/status").json()["job_id"] == second["job_id"]


def test_a_study_with_no_screens_starts_no_job_and_names_none(tmp_path: Path) -> None:
    app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
    with AuthTestClient(app) as client, \
            patch.object(screens_export, "screens_enabled", return_value=True), \
            patch.object(screens_export, "derive_project_screens",
                         return_value=({"screens": []}, {})), \
            patch.object(screens_export, "shot_list", return_value=[]), \
            patch.object(screens_export, "video_sessions", return_value={}):
        body = client.post("/api/projects/1/export/screens").json()
    assert body["status"] == "no_screens" and body["job_id"] is None


def test_a_cancel_naming_another_export_is_refused_and_stops_nothing() -> None:
    """A chip cancels only its own export: the cancel names it, and a newer one another window
    started since is left running (RE#38). Without a name the route stops what is running."""
    app = create_app(project_dir=_FIXTURE, dev=True, db_url="sqlite://")
    with AuthTestClient(app) as client:
        for kind, jobs in (("clips", clips_export._jobs), ("screens", screens_export._jobs)):
            jobs[1] = {"job_id": "newer", "status": "running"}
            stale = client.post(f"/api/projects/1/export/{kind}/cancel", json={"job_id": "older"})
            assert stale.status_code == 409, kind
            assert jobs[1]["status"] == "running", kind
            own = client.post(f"/api/projects/1/export/{kind}/cancel", json={"job_id": "newer"})
            assert own.status_code == 200 and jobs[1]["status"] == "cancelled", kind
            jobs[1] = {"job_id": "newer", "status": "running"}
            bare = client.post(f"/api/projects/1/export/{kind}/cancel")
            assert bare.status_code == 200 and jobs[1]["status"] == "cancelled", kind
