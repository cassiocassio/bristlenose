"""Export the Screens lens's stills as a folder (routes/screens_export.py)."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest

from bristlenose.server.app import create_app
from tests.conftest import AuthTestClient
from tests.test_serve_screens import (  # noqa: F401
    _give_s1_a_video,
    _needs_ffmpeg,
    _out,
    _write_index,
    project,
)

_BASE = "/api/projects/1/export/screens"


def _finish(client: AuthTestClient) -> dict:
    deadline = time.time() + 30
    while time.time() < deadline:
        body = client.get(f"{_BASE}/status").json()
        if body["status"] != "running":
            return body
        time.sleep(0.05)
    raise AssertionError("the export never finished")


def _width(jpg: Path) -> int:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width", "-of", "csv=p=0", str(jpg)], capture_output=True, text=True)
    return int(out.stdout.strip())


@_needs_ffmpeg
def test_each_still_is_written_full_size_and_replaces_the_last_export(
        project: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    monkeypatch.setenv("BRISTLENOSE_SCREEN_TEXT", "1")
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    _give_s1_a_video(app, project, real=True)
    _write_index(app, project, [{"text": "Your basket", "box": [0.4, 0.5, 0.3, 0.04]}], 1, 8)
    folder = _out(project) / "screens"
    folder.mkdir(parents=True)
    (folder / "p1-07.jpg").write_bytes(b"from an earlier export")
    (folder / ".screens_manifest.json").write_text(json.dumps({"files": ["p1-07.jpg"]}))
    (folder / "notes.txt").write_text("the researcher's own")
    with AuthTestClient(app) as client:
        x0, _, x1, _ = client.get("/api/projects/1/screens").json()["screens"][0]["tabs"][0]["crop"]
        assert client.post(_BASE).json() == {"status": "started", "total": 1}
        body = _finish(client)
    assert body["status"] == "completed" and body["files"] == ["p1-01.jpg"]
    jpg = folder / "p1-01.jpg"
    assert jpg.read_bytes()[:3] == b"\xff\xd8\xff"
    # The page's crop at the recording's own size (320 px wide), not scaled as the lens asks.
    assert abs(_width(jpg) - (x1 - x0) * 320) <= 2
    assert not (folder / "p1-07.jpg").exists()  # named by the last manifest: removed
    assert (folder / "notes.txt").exists()  # not named: left alone
    assert json.loads((folder / ".screens_manifest.json").read_text())["files"] == ["p1-01.jpg"]


def test_nothing_is_exported_while_screens_are_off(project: Path,  # noqa: F811
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRISTLENOSE_SCREEN_TEXT", raising=False)
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    assert AuthTestClient(app).post(_BASE).status_code == 404


def test_a_study_with_no_screens_says_so(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    monkeypatch.setenv("BRISTLENOSE_SCREEN_TEXT", "1")
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    assert AuthTestClient(app).post(_BASE).json() == {"status": "no_screens", "total": 0}
