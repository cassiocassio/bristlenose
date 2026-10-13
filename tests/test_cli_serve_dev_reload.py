"""``serve --dev``'s reloader watches the package, not the working directory."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

import bristlenose
from bristlenose import cli

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


@pytest.fixture(autouse=True)
def _restore_environ():
    """The dev path stashes ``_BRISTLENOSE_PROJECT_DIR``, ``_BRISTLENOSE_DEV`` and the
    port in ``os.environ`` for uvicorn's factory. Left behind, every later
    ``create_app()`` in the same worker recovers this test's project and imports
    it — ``test_empty_db_is_honest`` and the debug-500 test failed by order."""
    import os

    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    p = tmp_path / "input"
    shutil.copytree(_FIXTURE_DIR, p)
    return p


class _NoProc:
    """Stands in for the Vite subprocess: never spawned, already exited."""

    def __init__(self, *a: object, **k: object) -> None: ...

    def poll(self) -> int:
        return 0


def test_dev_reloader_watches_the_package_only(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """From the repo root uvicorn's default watches everything, and a sidecar rebuild under
    desktop/Bristlenose/Resources/ restarted the dev server dozens of times (12 Oct 2026)."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(cli, "_auto_render", lambda p: None)
    monkeypatch.setattr(cli, "_print_mcp_connect", lambda port: None)
    monkeypatch.setattr(subprocess, "Popen", _NoProc)
    import uvicorn

    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: calls.append(dict(k, app=a[0] if a else k.get("app"))))

    result = CliRunner().invoke(cli.app, ["serve", str(project), "--dev", "--no-open", "--port", "8199"])
    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    kw = calls[0]
    assert kw["reload"] is True
    package_dir = Path(bristlenose.__file__).resolve().parent
    assert kw["reload_dirs"] == [str(package_dir)]
    # The repo root (and so desktop/, trial-runs/, frontend/) is not watched.
    assert str(package_dir.parent) not in kw["reload_dirs"]


def test_a_mac_build_does_not_restart_the_dev_server(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The sidecar build writes bristlenose/_build_info.py at the start of every Xcode
    build; uvicorn's own file filter, configured as serve --dev configures it, must
    ignore that file and still see the code (13 Oct 2026)."""
    from uvicorn.config import Config
    from uvicorn.supervisors.watchfilesreload import FileFilter

    calls: list[dict[str, object]] = []
    monkeypatch.setattr(cli, "_auto_render", lambda p: None)
    monkeypatch.setattr(cli, "_print_mcp_connect", lambda port: None)
    monkeypatch.setattr(subprocess, "Popen", _NoProc)
    import uvicorn

    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: calls.append(k))
    result = CliRunner().invoke(cli.app, ["serve", str(project), "--dev", "--no-open", "--port", "8199"])
    assert result.exit_code == 0, result.output
    kw = calls[0]
    watched = FileFilter(Config(
        "bristlenose.server.app:create_app", reload=True, factory=True,
        reload_dirs=kw["reload_dirs"], reload_excludes=kw.get("reload_excludes"),
    ))
    package_dir = Path(bristlenose.__file__).resolve().parent
    assert not watched(package_dir / "_build_info.py")
    assert watched(package_dir / "cli.py")

