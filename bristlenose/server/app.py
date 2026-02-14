"""FastAPI application factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from bristlenose.server.db import get_engine, init_db
from bristlenose.server.routes.health import router as health_router

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
    """
    app = FastAPI(title="Bristlenose", docs_url="/api/docs", redoc_url=None)

    engine = get_engine(db_url)
    init_db(engine)

    app.include_router(health_router)

    # Serve the React islands bundle (built by Vite)
    if not dev and _STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    # Serve the existing HTML report and assets from the project output dir
    if project_dir is not None:
        output_dir = project_dir / "bristlenose-output"
        if not output_dir.is_dir():
            output_dir = project_dir  # Caller already pointed at the output dir
        if output_dir.is_dir():
            app.mount("/report", StaticFiles(directory=output_dir, html=True), name="report")

    return app
