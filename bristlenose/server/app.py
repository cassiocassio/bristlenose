"""FastAPI application factory."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from bristlenose.server.db import create_session_factory, get_engine, init_db
from bristlenose.server.routes.health import router as health_router
from bristlenose.server.routes.sessions import router as sessions_router

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    project_dir: Path | None = None,
    dev: bool = False,
    db_url: str | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        project_dir: Path to a project's bristlenose-output/ directory.
                     When provided, serves the report files.
        dev: When True, skip mounting static files (Vite dev server handles them).
        db_url: Override database URL (e.g. "sqlite://" for in-memory tests).

    In ``--dev`` mode uvicorn calls this factory with no arguments on reload.
    The CLI stashes ``project_dir`` in ``_BRISTLENOSE_PROJECT_DIR`` so the
    factory can recover it.
    """
    # Recover project_dir from env when called by uvicorn reload (no args)
    if project_dir is None:
        env_dir = os.environ.get("_BRISTLENOSE_PROJECT_DIR")
        if env_dir:
            project_dir = Path(env_dir)
    app = FastAPI(title="Bristlenose", docs_url="/api/docs", redoc_url=None)

    engine = get_engine(db_url)
    init_db(engine)
    session_factory = create_session_factory(engine)

    # Store session factory in app state for dependency injection
    app.state.db_factory = session_factory

    app.include_router(health_router)
    app.include_router(sessions_router)

    # Import project data into SQLite on startup
    if project_dir is not None:
        _import_on_startup(session_factory, project_dir)

    # Serve the React islands bundle (built by Vite)
    if not dev and _STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    # Serve the existing HTML report and assets from the project output dir
    if project_dir is not None:
        output_dir = project_dir / "bristlenose-output"
        if not output_dir.is_dir():
            output_dir = project_dir  # Caller already pointed at the output dir
        if output_dir.is_dir():
            # The report filename includes the project slug (e.g.
            # bristlenose-project-ikea-report.html).  Create an index.html
            # symlink so StaticFiles(html=True) can serve /report/.
            _ensure_index_symlink(output_dir)
            app.mount("/report", StaticFiles(directory=output_dir, html=True), name="report")
        else:
            logger.warning("report mount skipped — %s does not exist", output_dir)

    return app


def _ensure_index_symlink(output_dir: Path) -> None:
    """Create an index.html symlink to the main report file if needed.

    The report filename includes the project slug (e.g.
    ``bristlenose-project-ikea-report.html``), so there's no ``index.html``
    for ``StaticFiles(html=True)`` to find.  A relative symlink keeps the
    output directory portable.
    """
    index = output_dir / "index.html"
    if index.exists():
        return
    report_files = list(output_dir.glob("*-report.html"))
    if not report_files:
        return
    # Relative symlink so the output dir stays self-contained
    index.symlink_to(report_files[0].name)


def _import_on_startup(
    session_factory: object,
    project_dir: Path,
) -> None:
    """Import project data into SQLite during app startup."""
    from bristlenose.server.importer import import_project

    db = session_factory()  # type: ignore[operator]
    try:
        import_project(db, project_dir)
    except Exception:
        logger.exception("Failed to import project from %s", project_dir)
    finally:
        db.close()
