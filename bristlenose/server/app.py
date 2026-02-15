"""FastAPI application factory."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from bristlenose.server.db import create_session_factory, get_engine, init_db
from bristlenose.server.routes.health import router as health_router
from bristlenose.server.routes.sessions import router as sessions_router

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"
# Repo root — two levels up from bristlenose/server/app.py
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


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
    # Recover project_dir and dev flag from env when called by uvicorn reload
    if project_dir is None:
        env_dir = os.environ.get("_BRISTLENOSE_PROJECT_DIR")
        if env_dir:
            project_dir = Path(env_dir)
    if not dev and os.environ.get("_BRISTLENOSE_DEV") == "1":
        dev = True
    app = FastAPI(title="Bristlenose", docs_url="/api/docs", redoc_url=None)

    engine = get_engine(db_url)
    init_db(engine)
    session_factory = create_session_factory(engine)

    # Store session factory in app state for dependency injection
    app.state.db_factory = session_factory

    app.include_router(health_router)
    app.include_router(sessions_router)

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

            if dev:
                # Dev mode: serve the report HTML with Vite script injected so
                # React islands (AboutDeveloper, SessionsTable, etc.) mount
                # into the static report page.  Non-HTML assets (CSS, images,
                # JS) are still served by StaticFiles.
                _mount_dev_report(app, output_dir)
            else:
                app.mount(
                    "/report", StaticFiles(directory=output_dir, html=True), name="report"
                )
        else:
            logger.warning("report mount skipped — %s does not exist", output_dir)

    if dev:
        _print_dev_urls()

    return app


def _print_dev_urls() -> None:
    """Print all dev-mode URLs on startup (Cmd-clickable in iTerm)."""
    port = int(os.environ.get("_BRISTLENOSE_PORT", "8150"))
    vite_port = 5173
    b = f"http://localhost:{port}"
    v = f"http://localhost:{vite_port}"
    logger.info(
        "\n"
        "  Dev URLs (Cmd-click to open):\n"
        "\n"
        "  Report:           %s/report/\n"
        "  Visual diff:      %s/visual-diff.html\n"
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
        b, v, b, b, b, b, b, b, b, b, b,
    )


def _build_dev_section_html() -> str:
    """Build the Developer + Design sections for injection into the About tab."""
    from bristlenose.server.db import _DB_PATH, Base

    port = int(os.environ.get("_BRISTLENOSE_PORT", "8150"))
    base = f"http://localhost:{port}"

    # --- Developer section ---
    dev_links = [
        ("Database Browser", f"{base}/admin/", "Browse and edit all tables (SQLAdmin)"),
        ("API Documentation", f"{base}/api/docs", "Interactive Swagger UI for all endpoints"),
        ("Sessions API", f"{base}/api/projects/1/sessions", "JSON sessions list"),
        ("Dev Info", f"{base}/api/dev/info", "System info endpoint"),
        ("Health Check", f"{base}/api/health", "System status and version"),
    ]
    dev_li = "\n".join(
        f'<li><a href="{url}" target="_blank" rel="noopener noreferrer">{label}</a>'
        f" &mdash; {desc}</li>"
        for label, url, desc in dev_links
    )
    table_count = len(Base.metadata.tables)

    # --- Design section — discover mockups, experiments, design system files ---
    design_dirs: list[tuple[str, str, Path]] = [
        ("Mockups", "/mockups", _REPO_ROOT / "docs" / "mockups"),
        ("Experiments", "/experiments", _REPO_ROOT / "experiments"),
        ("Design System", "/design-system", _REPO_ROOT / "docs" / "design-system"),
    ]
    design_parts: list[str] = []
    for heading, url_prefix, dir_path in design_dirs:
        if not dir_path.is_dir():
            continue
        html_files = sorted(dir_path.glob("*.html"))
        if not html_files:
            continue
        items = "\n".join(
            f'<li><a href="{base}{url_prefix}/{f.name}" target="_blank"'
            f' rel="noopener noreferrer">{_label_from_filename(f.name)}</a></li>'
            for f in html_files
        )
        design_parts.append(f"<h4>{heading}</h4>\n<ul>{items}</ul>")

    design_html = ""
    if design_parts:
        design_html = "<hr>\n<h3>Design</h3>\n" + "\n".join(design_parts) + "\n"

    return (
        "<hr>\n"
        "<h3>Developer</h3>\n"
        "<dl>\n"
        f"<dt>Database</dt><dd><code>{_DB_PATH}</code></dd>\n"
        f"<dt>Schema</dt><dd>{table_count} tables</dd>\n"
        "</dl>\n"
        "<h3>Developer Tools</h3>\n"
        f"<ul>{dev_li}</ul>\n"
        f"{design_html}"
    )


def _label_from_filename(name: str) -> str:
    """Turn 'mockup-codebook-panel.html' into 'Codebook panel'."""
    stem = Path(name).stem
    # Strip common prefixes
    for prefix in ("mockup-", "focus-", "dashboard-"):
        if stem.startswith(prefix):
            stem = stem[len(prefix):]
            break
    return stem.replace("-", " ").capitalize()


def _build_renderer_overlay_html() -> str:
    """Build the renderer overlay toggle: inline <style> + <script>.

    Dev-only feature. Injects a floating button that toggles pastel background
    tints on report regions by renderer origin (Jinja2 / React / vanilla JS).
    """
    return """\
<style>
/* --- Renderer overlay tints (dev-only) --- */
/* Jinja2 (static pipeline HTML) — pale blue */
body.bn-dev-overlay .bn-tab-panel,
body.bn-dev-overlay .bn-dashboard,
body.bn-dev-overlay .bn-session-grid,
body.bn-dev-overlay .toolbar,
body.bn-dev-overlay .toc,
body.bn-dev-overlay section,
body.bn-dev-overlay .bn-about,
body.bn-dev-overlay .report-header,
body.bn-dev-overlay .bn-global-nav,
body.bn-dev-overlay .footer { background: #eef4fe !important; }

/* React islands — pale green (higher specificity wins over parent blue) */
body.bn-dev-overlay #bn-sessions-table-root,
body.bn-dev-overlay #bn-about-developer-root { background: #e8fce8 !important; }

/* Vanilla JS rendered — pale amber (higher specificity wins over parent blue) */
body.bn-dev-overlay #codebook-grid,
body.bn-dev-overlay #signal-cards,
body.bn-dev-overlay #heatmap-section-container,
body.bn-dev-overlay #heatmap-theme-container { background: #fef6e0 !important; }

#bn-dev-overlay-toggle {
  position: fixed;
  top: 12px;
  right: 12px;
  z-index: 100000;
  font-family: system-ui, -apple-system, sans-serif;
  font-size: 12px;
  background: #1e293b;
  color: #e2e8f0;
  border: 1px solid #475569;
  border-radius: 8px;
  padding: 8px 12px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  user-select: none;
}
#bn-dev-overlay-toggle:hover { background: #334155; }
#bn-dev-overlay-toggle .bn-overlay-label { font-weight: 600; }
#bn-dev-overlay-toggle .bn-overlay-legend {
  display: none;
  gap: 4px;
  flex-direction: column;
  font-size: 11px;
  margin-top: 4px;
  padding-top: 4px;
  border-top: 1px solid #475569;
}
#bn-dev-overlay-toggle.active .bn-overlay-legend { display: flex; }
#bn-dev-overlay-toggle .bn-overlay-swatch {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  margin-right: 4px;
  vertical-align: middle;
}
</style>
<div id="bn-dev-overlay-toggle" title="Toggle renderer overlay (D)">
  <span class="bn-overlay-label">Renderers: off</span>
  <div class="bn-overlay-legend">
    <span><span class="bn-overlay-swatch" style="background:#93c5fd"></span>Jinja2</span>
    <span><span class="bn-overlay-swatch" style="background:#86efac"></span>React</span>
    <span><span class="bn-overlay-swatch" style="background:#fde68a"></span>Vanilla JS</span>
  </div>
</div>
<script>
(function() {
  var btn = document.getElementById('bn-dev-overlay-toggle');
  var label = btn.querySelector('.bn-overlay-label');
  function toggle() {
    document.body.classList.toggle('bn-dev-overlay');
    var on = document.body.classList.contains('bn-dev-overlay');
    label.textContent = 'Renderers: ' + (on ? 'on' : 'off');
    btn.classList.toggle('active', on);
  }
  btn.addEventListener('click', toggle);
  document.addEventListener('keydown', function(e) {
    if (e.key === 'd' && !e.ctrlKey && !e.metaKey && !e.altKey) {
      var tag = (e.target.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || e.target.isContentEditable) return;
      toggle();
    }
  });
})();
</script>
"""


def _mount_dev_report(app: FastAPI, output_dir: Path) -> None:
    """Mount the report with developer section injected into the About tab.

    In dev mode, the About tab gets a Developer section with links to the
    database browser, API docs, and other dev tools.  Rendered as plain HTML
    — no React or Vite dev server required.
    """
    report_html = output_dir / "index.html"
    if report_html.is_symlink():
        report_html = output_dir / os.readlink(report_html)

    dev_html = _build_dev_section_html()
    overlay_html = _build_renderer_overlay_html()

    @app.get("/report/")
    def serve_report_html() -> HTMLResponse:
        html = report_html.read_text(encoding="utf-8")
        # Inject developer section before the closing .bn-about marker
        html = html.replace("<!-- /bn-about -->", f"{dev_html}<!-- /bn-about -->")
        # Inject renderer overlay toggle before </body>
        html = html.replace("</body>", f"{overlay_html}</body>")
        return HTMLResponse(html)

    @app.get("/report")
    def redirect_report_to_slash() -> RedirectResponse:
        return RedirectResponse("/report/", status_code=301)

    # Non-HTML assets (CSS, images, JS from the pipeline) still served normally
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
