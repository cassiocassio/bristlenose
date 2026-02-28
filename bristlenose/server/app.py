"""FastAPI application factory."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from bristlenose.server.db import create_session_factory, db_url_for_project, get_engine, init_db
from bristlenose.server.routes.analysis import router as analysis_router
from bristlenose.server.routes.autocode import router as autocode_router
from bristlenose.server.routes.codebook import router as codebook_router
from bristlenose.server.routes.dashboard import router as dashboard_router
from bristlenose.server.routes.data import router as data_router
from bristlenose.server.routes.health import router as health_router
from bristlenose.server.routes.miro import router as miro_router
from bristlenose.server.routes.quotes import router as quotes_router
from bristlenose.server.routes.sessions import router as sessions_router
from bristlenose.server.routes.transcript import router as transcript_router

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"
# Repo root — two levels up from bristlenose/server/app.py
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def create_app(
    project_dir: Path | None = None,
    dev: bool = False,
    db_url: str | None = None,
    verbose: bool = False,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        project_dir: Path to a project's bristlenose-output/ directory.
                     When provided, serves the report files.
        dev: When True, skip mounting static files (Vite dev server handles them).
        db_url: Override database URL (e.g. "sqlite://" for in-memory tests).
        verbose: When True, terminal handler shows DEBUG-level messages.

    In ``--dev`` mode uvicorn calls this factory with no arguments on reload.
    The CLI stashes ``project_dir`` in ``_BRISTLENOSE_PROJECT_DIR`` so the
    factory can recover it.
    """
    # Recover project_dir, dev, and verbose flags from env when called by uvicorn reload
    if project_dir is None:
        env_dir = os.environ.get("_BRISTLENOSE_PROJECT_DIR")
        if env_dir:
            project_dir = Path(env_dir)
    if not dev and os.environ.get("_BRISTLENOSE_DEV") == "1":
        dev = True
    if not verbose and os.environ.get("_BRISTLENOSE_VERBOSE") == "1":
        verbose = True

    # Persistent log file — writes to <output_dir>/.bristlenose/bristlenose.log
    # alongside the per-project SQLite DB.  Controlled by BRISTLENOSE_LOG_LEVEL
    # (default INFO).  Terminal verbosity is separate (-v on the CLI).
    if project_dir is not None:
        _output_dir = project_dir / "bristlenose-output"
        if not _output_dir.is_dir():
            _output_dir = project_dir  # Already pointing at the output dir
        if _output_dir.is_dir():
            from bristlenose.logging import setup_logging

            setup_logging(output_dir=_output_dir, verbose=verbose)

    app = FastAPI(title="Bristlenose", docs_url="/api/docs", redoc_url=None)

    # Per-project DB: derive path from project_dir unless explicitly overridden
    if db_url is None and project_dir is not None:
        db_url = db_url_for_project(project_dir)

    engine = get_engine(db_url)
    init_db(engine)
    session_factory = create_session_factory(engine)

    # Store session factory, DB URL, and project dir in app state for dependency injection
    app.state.db_factory = session_factory
    app.state.db_url = db_url or ""
    app.state.project_dir = project_dir

    app.include_router(health_router)
    app.include_router(analysis_router)
    app.include_router(autocode_router)
    app.include_router(codebook_router)
    app.include_router(dashboard_router)
    app.include_router(sessions_router)
    app.include_router(quotes_router)
    app.include_router(transcript_router)
    app.include_router(data_router)
    app.include_router(miro_router)

    if dev:
        from bristlenose.server.routes.dev import router as dev_router

        app.include_router(dev_router)

        # SQLAdmin database browser (dev-only)
        from sqladmin import Admin as SQLAdmin

        from bristlenose.server.admin import register_admin_views

        sqladmin_app = SQLAdmin(app, engine, base_url="/admin")
        register_admin_views(sqladmin_app)

    # Import project data into SQLite on startup
    if project_dir is not None:
        _import_on_startup(session_factory, project_dir)

    # Serve the React islands bundle (built by Vite)
    if not dev and _STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    # Serve media files (video/audio) from the project input directory so the
    # popout player can load them over HTTP instead of file:// URIs.
    if project_dir is not None:
        app.mount("/media", StaticFiles(directory=project_dir), name="media")

    # Serve the report SPA from the Vite build output
    if project_dir is not None:
        output_dir = project_dir / "bristlenose-output"
        if not output_dir.is_dir():
            output_dir = project_dir  # Caller already pointed at the output dir
        if output_dir.is_dir():
            if dev:
                _mount_dev_report(app, output_dir)
            else:
                _mount_prod_report(app, output_dir)
        else:
            logger.warning("report mount skipped — %s does not exist", output_dir)

    if dev:
        _print_dev_urls()

    return app


def _print_dev_urls() -> None:
    """Print all dev-mode URLs on startup (Cmd-clickable in iTerm)."""
    port = int(os.environ.get("_BRISTLENOSE_PORT", "8150"))
    b = f"http://localhost:{port}"
    logger.info(
        "\n"
        "  Dev URLs (Cmd-click to open):\n"
        "\n"
        "  Report:           %s/report/\n"
        "  Database browser: %s/admin/\n"
        "  API docs:         %s/api/docs\n"
        "  Sessions API:     %s/api/projects/1/sessions\n"
        "  Sessions HTML:    %s/api/dev/sessions-table-html?project_id=1\n"
        "  Dev info:         %s/api/dev/info\n"
        "  Health:           %s/api/health\n"
        "\n"
        "  Design:\n"
        "  Mockups:          %s/mockups/\n"
        "  Experiments:      %s/experiments/\n"
        "  Design system:    %s/design-system/\n",
        b, b, b, b, b, b, b, b, b, b,
    )


def _build_spa_html(output_dir: Path) -> str:
    """Read the Vite-built index.html and prepare it for serving.

    - Rewrites ``/assets/`` paths to ``/static/assets/`` (bundle served via StaticFiles)
    - Injects ``<link>`` for the theme CSS (from the pipeline output dir)
    """
    import re

    index_path = _STATIC_DIR / "index.html"
    html = index_path.read_text(encoding="utf-8")
    # Rewrite bundle asset paths: /assets/ → /static/assets/
    html = re.sub(r'((?:src|href)=")/assets/', r'\1/static/assets/', html)
    # Inject theme CSS before </head> — served from output dir at /report/assets/
    theme_link = '<link rel="stylesheet" href="/report/assets/bristlenose-theme.css">'
    html = html.replace("</head>", f"{theme_link}\n</head>")
    return html


def _build_dev_html(output_dir: Path) -> str:
    """Build a self-contained dev HTML page with Vite HMR scripts.

    No baked HTML reading, no regex surgery.  Includes:
    - React Refresh preamble (required by @vitejs/plugin-react)
    - Vite HMR client
    - App entry point (src/main.tsx)
    - Theme CSS from the pipeline output dir
    """
    vite = "http://localhost:5173"
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="UTF-8" />\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
        '<meta name="color-scheme" content="light dark" />\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400..700'
        '&display=swap" rel="stylesheet">\n'
        '<link rel="stylesheet" href="/report/assets/bristlenose-theme.css">\n'
        "<title>Bristlenose</title>\n"
        "</head>\n"
        "<body>\n"
        '<div id="bn-app-root" data-project-id="1"></div>\n'
        '<script type="module">\n'
        f"  import RefreshRuntime from '{vite}/@react-refresh'\n"
        "  RefreshRuntime.injectIntoGlobalHook(window)\n"
        "  window.$RefreshReg$ = () => {}\n"
        "  window.$RefreshSig$ = () => (type) => type\n"
        "  window.__vite_plugin_react_preamble_installed__ = true\n"
        "</script>\n"
        f'<script type="module" src="{vite}/@vite/client"></script>\n'
        f'<script type="module" src="{vite}/src/main.tsx"></script>\n'
        "</body>\n"
        "</html>\n"
    )


def _mount_dev_report(app: FastAPI, output_dir: Path) -> None:
    """Mount the report SPA in dev mode with Vite HMR.

    Serves a self-contained HTML page with Vite dev scripts.  No baked HTML
    reading or regex surgery — React renders everything (header, nav, content,
    footer).  Data comes from API endpoints.
    """
    dev_html = _build_dev_html(output_dir)

    @app.get("/report")
    def redirect_report_to_slash() -> RedirectResponse:
        return RedirectResponse("/report/", status_code=301)

    @app.get("/report/{path:path}", response_model=None)
    def serve_report_spa(path: str = "") -> Response:
        """SPA catch-all: serve dev HTML for all /report/* paths.

        Paths with file extensions (CSS, images, thumbnails, player HTML)
        are served from the output directory.
        """
        from pathlib import PurePosixPath

        if PurePosixPath(path).suffix:
            asset_path = output_dir / path
            if asset_path.is_file():
                return FileResponse(asset_path)
            raise HTTPException(status_code=404, detail="Asset not found")

        return HTMLResponse(dev_html)

    # Non-HTML assets (CSS, images, thumbnails, player HTML) from the output dir
    app.mount("/report", StaticFiles(directory=output_dir), name="report")

    # Serve design artifacts (mockups, experiments, design system)
    design_mounts = [
        ("/mockups", _REPO_ROOT / "docs" / "mockups"),
        ("/experiments", _REPO_ROOT / "experiments"),
        ("/design-system", _REPO_ROOT / "docs" / "design-system"),
    ]
    for url_path, dir_path in design_mounts:
        if dir_path.is_dir():
            app.mount(url_path, StaticFiles(directory=dir_path, html=True), name=url_path[1:])


def _mount_prod_report(app: FastAPI, output_dir: Path) -> None:
    """Mount the report SPA in production serve mode.

    Reads the Vite-built index.html once at startup, rewrites asset paths,
    and injects theme CSS.  Falls back to plain StaticFiles if no Vite build
    exists.
    """
    index_path = _STATIC_DIR / "index.html"
    if not index_path.is_file():
        logger.warning(
            "React bundle not found at %s — serving static HTML without React "
            "islands. Run 'npm run build' in frontend/ to build the bundle.",
            _STATIC_DIR,
        )
        _ensure_index_symlink(output_dir)
        app.mount(
            "/report", StaticFiles(directory=output_dir, html=True), name="report"
        )
        return

    spa_html = _build_spa_html(output_dir)

    @app.get("/report")
    def redirect_report_to_slash_prod() -> RedirectResponse:
        return RedirectResponse("/report/", status_code=301)

    @app.get("/report/{path:path}", response_model=None)
    def serve_report_spa_prod(path: str = "") -> Response:
        """SPA catch-all (production): serve SPA HTML for all /report/* paths.

        Paths with file extensions (CSS, images, thumbnails, player HTML)
        are served from the output directory.
        """
        from pathlib import PurePosixPath

        if PurePosixPath(path).suffix:
            asset_path = output_dir / path
            if asset_path.is_file():
                return FileResponse(asset_path)
            raise HTTPException(status_code=404, detail="Asset not found")

        return HTMLResponse(spa_html)

    # Non-HTML assets (CSS, images, thumbnails, player HTML) from the output dir
    app.mount("/report", StaticFiles(directory=output_dir), name="report")


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
