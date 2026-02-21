"""FastAPI application factory."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from bristlenose.server.db import create_session_factory, db_url_for_project, get_engine, init_db
from bristlenose.server.routes.analysis import router as analysis_router
from bristlenose.server.routes.autocode import router as autocode_router
from bristlenose.server.routes.codebook import router as codebook_router
from bristlenose.server.routes.dashboard import router as dashboard_router
from bristlenose.server.routes.data import router as data_router
from bristlenose.server.routes.health import router as health_router
from bristlenose.server.routes.quotes import router as quotes_router
from bristlenose.server.routes.sessions import router as sessions_router
from bristlenose.server.routes.transcript import router as transcript_router

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"
# Repo root — two levels up from bristlenose/server/app.py
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
# JS source directory — for live-reloading in dev mode
_THEME_DIR = _REPO_ROOT / "bristlenose" / "theme"

# Marker that render_html.py writes at the start of the concatenated JS block.
# In dev mode we replace everything from this marker to </script> with fresh
# JS read from the source files — so editing a .js file and refreshing the
# browser picks up the change instantly, no re-render needed.
_JS_MARKER = "/* bristlenose report.js — auto-generated from bristlenose/theme/js/ */"
# React mount point injected in place of the Jinja2 session table at serve time
_REACT_SESSIONS_MOUNT = (
    "<!-- bn-session-table -->"
    '<div id="bn-sessions-table-root" data-project-id="1"></div>'
    "<!-- /bn-session-table -->"
)
# React mount point for dashboard (Project tab)
_REACT_DASHBOARD_MOUNT = (
    "<!-- bn-dashboard -->"
    '<div id="bn-dashboard-root" data-project-id="1"></div>'
    "<!-- /bn-dashboard -->"
)
# React mount points for quote sections and themes
_REACT_QUOTE_SECTIONS_MOUNT = (
    "<!-- bn-quote-sections -->"
    '<div id="bn-quote-sections-root" data-project-id="1"></div>'
    "<!-- /bn-quote-sections -->"
)
_REACT_QUOTE_THEMES_MOUNT = (
    "<!-- bn-quote-themes -->"
    '<div id="bn-quote-themes-root" data-project-id="1"></div>'
    "<!-- /bn-quote-themes -->"
)
# React mount point for codebook panel (Codebook tab).
# Must preserve the .bn-tab-panel wrapper so vanilla JS tab switching can find it.
_REACT_CODEBOOK_MOUNT = (
    "<!-- bn-codebook -->"
    '<div class="bn-tab-panel" data-tab="codebook" id="panel-codebook"'
    ' role="tabpanel" aria-label="Codebook">'
    '<div id="bn-codebook-root" data-project-id="1"></div>'
    "</div>"
    "<!-- /bn-codebook -->"
)
# React mount point for analysis page.
# Must preserve the .bn-tab-panel wrapper so vanilla JS tab switching can find it.
_REACT_ANALYSIS_MOUNT = (
    "<!-- bn-analysis -->"
    '<div class="bn-tab-panel" data-tab="analysis" id="panel-analysis"'
    ' role="tabpanel" aria-label="Analysis">'
    '<div id="bn-analysis-root" data-project-id="1"></div>'
    "</div>"
    "<!-- /bn-analysis -->"
)
# React mount point for transcript page (replaces back link + heading + transcript body).
# The {session_id} placeholder is filled at serve time from the filename.
_REACT_TRANSCRIPT_MOUNT = (
    "<!-- bn-transcript-page -->"
    '<div id="bn-transcript-page-root" data-project-id="1"'
    ' data-session-id="{session_id}"></div>'
    "<!-- /bn-transcript-page -->"
)


def _extract_bundle_tags() -> str:
    """Extract <script> and <link> tags from the Vite-built index.html.

    Returns the tags with paths rewritten from ``/assets/`` to
    ``/static/assets/`` for injection into report pages served by FastAPI.
    Returns an empty string if the build output doesn't exist.
    """
    index_path = _STATIC_DIR / "index.html"
    if not index_path.is_file():
        return ""
    html = index_path.read_text(encoding="utf-8")
    tags: list[str] = []
    for match in re.finditer(r"<script[^>]*\ssrc=\"(/assets/[^\"]+)\"[^>]*></script>", html):
        tags.append(match.group(0).replace(match.group(1), "/static" + match.group(1)))
    for match in re.finditer(r"<link[^>]*\shref=\"(/assets/[^\"]+)\"[^>]*>", html):
        tags.append(match.group(0).replace(match.group(1), "/static" + match.group(1)))
    return "\n".join(tags)


def _transform_report_html(html: str, project_dir: Path | None) -> str:
    """Apply shared HTML transformations for serve mode (dev and production).

    Rewrites video URIs, swaps Jinja2 comment markers for React mount divs,
    and injects the API base URL script.
    """
    if project_dir is not None:
        html = _rewrite_video_map_uris(html, project_dir)
    html = re.sub(
        r"<!-- bn-dashboard -->.*?<!-- /bn-dashboard -->",
        _REACT_DASHBOARD_MOUNT, html, flags=re.DOTALL,
    )
    html = re.sub(
        r"<!-- bn-session-table -->.*?<!-- /bn-session-table -->",
        _REACT_SESSIONS_MOUNT, html, flags=re.DOTALL,
    )
    html = re.sub(
        r"<!-- bn-quote-sections -->.*?<!-- /bn-quote-sections -->",
        _REACT_QUOTE_SECTIONS_MOUNT, html, flags=re.DOTALL,
    )
    html = re.sub(
        r"<!-- bn-quote-themes -->.*?<!-- /bn-quote-themes -->",
        _REACT_QUOTE_THEMES_MOUNT, html, flags=re.DOTALL,
    )
    html = re.sub(
        r"<!-- bn-codebook -->.*?<!-- /bn-codebook -->",
        _REACT_CODEBOOK_MOUNT, html, flags=re.DOTALL,
    )
    html = re.sub(
        r"<!-- bn-analysis -->.*?<!-- /bn-analysis -->",
        _REACT_ANALYSIS_MOUNT, html, flags=re.DOTALL,
    )
    api_base_script = (
        "<script>window.BRISTLENOSE_API_BASE = '/api/projects/1';</script>\n"
    )
    html = html.replace("</body>", f"{api_base_script}</body>")
    return html


def _transform_transcript_html(
    html: str, session_id: str, project_dir: Path | None,
) -> str:
    """Apply shared HTML transformations for transcript pages."""
    if project_dir is not None:
        html = _rewrite_video_map_uris(html, project_dir)
    mount_html = _REACT_TRANSCRIPT_MOUNT.replace("{session_id}", session_id)
    html = re.sub(
        r"<!-- bn-transcript-page -->.*?<!-- /bn-transcript-page -->",
        mount_html, html, flags=re.DOTALL,
    )
    api_base_script = (
        "<script>window.BRISTLENOSE_API_BASE = '/api/projects/1';</script>\n"
    )
    html = html.replace("</body>", f"{api_base_script}</body>")
    return html


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

    # Store session factory and DB URL in app state for dependency injection
    app.state.db_factory = session_factory
    app.state.db_url = db_url or ""

    app.include_router(health_router)
    app.include_router(analysis_router)
    app.include_router(autocode_router)
    app.include_router(codebook_router)
    app.include_router(dashboard_router)
    app.include_router(sessions_router)
    app.include_router(quotes_router)
    app.include_router(transcript_router)
    app.include_router(data_router)

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
                _mount_dev_report(app, output_dir, project_dir)
            else:
                _mount_prod_report(app, output_dir, project_dir)
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


def _build_dev_section_html(db_url: str) -> str:
    """Build the Developer + Design sections for injection into the About tab."""
    from bristlenose.server.db import Base

    port = int(os.environ.get("_BRISTLENOSE_PORT", "8150"))
    base = f"http://localhost:{port}"

    # Extract path from sqlite:///... URL for display
    db_display = db_url.removeprefix("sqlite:///") if db_url else "(in-memory)"

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
        f"<dt>Database</dt><dd><code>{db_display}</code></dd>\n"
        f"<dt>Schema</dt><dd>{table_count} tables</dd>\n"
        "<dt>Renderer overlay</dt>"
        "<dd>Press <kbd>D</kbd> to colour-code regions by renderer "
        "(blue&nbsp;=&nbsp;Jinja2, green&nbsp;=&nbsp;React, "
        "amber&nbsp;=&nbsp;Vanilla&nbsp;JS)</dd>\n"
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
/* Uses ::after pseudo-elements to paint a translucent colour overlay.
   This avoids clobbering child backgrounds (sparklines, thumbnails, etc.)
   which a `background !important` approach would destroy.

   Key trick: Jinja2 containers that *directly hold* a React or Vanilla JS
   region suppress their own ::after (via :not(:has(...))) so the nested
   region's colour isn't hidden under a blue overlay. */

/* All tinted regions need position:relative for the ::after to anchor to */
body.bn-dev-overlay .bn-tab-panel,
body.bn-dev-overlay .bn-dashboard,
body.bn-dev-overlay .bn-session-grid,
body.bn-dev-overlay .toolbar,
body.bn-dev-overlay .toc,
body.bn-dev-overlay section,
body.bn-dev-overlay .bn-about,
body.bn-dev-overlay .report-header,
body.bn-dev-overlay .bn-global-nav,
body.bn-dev-overlay .footer,
body.bn-dev-overlay #bn-dashboard-root,
body.bn-dev-overlay #bn-sessions-table-root,
body.bn-dev-overlay #bn-about-developer-root,
body.bn-dev-overlay #bn-quote-sections-root,
body.bn-dev-overlay #bn-quote-themes-root,
body.bn-dev-overlay #bn-codebook-root,
body.bn-dev-overlay #bn-transcript-page-root,
body.bn-dev-overlay #codebook-grid,
body.bn-dev-overlay #signal-cards,
body.bn-dev-overlay #heatmap-section-container,
body.bn-dev-overlay #heatmap-theme-container { position: relative; }

/* Jinja2 (static pipeline HTML) — pale blue overlay + outline.
   :not(:has(#bn-...)) suppresses the overlay on containers that hold
   React/Vanilla JS regions so those regions' own colour shows through.
   Elements *inside* React mount points are also excluded — React renders
   <section>, <table>, etc. that would otherwise match generic selectors. */
body.bn-dev-overlay .bn-tab-panel:not(:has(#bn-dashboard-root, #bn-sessions-table-root, #bn-about-developer-root, #bn-quote-sections-root, #bn-quote-themes-root, #bn-codebook-root, #codebook-grid, #signal-cards, #heatmap-section-container, #heatmap-theme-container)),
body.bn-dev-overlay .bn-dashboard:not(:has(#bn-dashboard-root)),
body.bn-dev-overlay .bn-session-grid:not(:has(#bn-sessions-table-root)),
body.bn-dev-overlay .toolbar,
body.bn-dev-overlay .toc,
body.bn-dev-overlay .bn-about:not(:has(#bn-about-developer-root)),
body.bn-dev-overlay .report-header,
body.bn-dev-overlay .bn-global-nav,
body.bn-dev-overlay .footer {
  outline: 3px solid rgba(147, 197, 253, 0.5);  /* blue outline — Jinja2 */
  outline-offset: -3px;
}
body.bn-dev-overlay .bn-tab-panel:not(:has(#bn-dashboard-root, #bn-sessions-table-root, #bn-about-developer-root, #bn-quote-sections-root, #bn-quote-themes-root, #bn-codebook-root, #codebook-grid, #signal-cards, #heatmap-section-container, #heatmap-theme-container))::after,
body.bn-dev-overlay .bn-dashboard:not(:has(#bn-dashboard-root))::after,
body.bn-dev-overlay .bn-session-grid:not(:has(#bn-sessions-table-root))::after,
body.bn-dev-overlay .toolbar::after,
body.bn-dev-overlay .toc::after,
body.bn-dev-overlay section:not(:has(#bn-dashboard-root, #bn-sessions-table-root, #bn-about-developer-root, #bn-quote-sections-root, #bn-quote-themes-root, #bn-codebook-root, #codebook-grid, #signal-cards, #heatmap-section-container, #heatmap-theme-container))::after,
body.bn-dev-overlay .bn-about:not(:has(#bn-about-developer-root))::after,
body.bn-dev-overlay .report-header::after,
body.bn-dev-overlay .bn-global-nav::after,
body.bn-dev-overlay .footer::after {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(147, 197, 253, 0.15);  /* pale blue — Jinja2 */
  pointer-events: none;
  z-index: 9999;
}

/* Cancel Jinja2 tint on elements INSIDE React/Vanilla JS mount points.
   React renders <section class="bn-session-table"> etc. that would match
   generic Jinja2 selectors above.  Override those descendants' ::after
   with display:none so no blue leaks through.  Uses ID selectors (high
   specificity) to beat the class-based Jinja2 rules above. */
body.bn-dev-overlay #bn-dashboard-root section::after,
body.bn-dev-overlay #bn-dashboard-root .bn-dashboard::after,
body.bn-dev-overlay #bn-sessions-table-root section::after,
body.bn-dev-overlay #bn-about-developer-root section::after,
body.bn-dev-overlay #bn-quote-sections-root section::after,
body.bn-dev-overlay #bn-quote-themes-root section::after,
body.bn-dev-overlay #bn-codebook-root section::after,
body.bn-dev-overlay #bn-transcript-page-root section::after,
body.bn-dev-overlay #codebook-grid section::after,
body.bn-dev-overlay #signal-cards section::after,
body.bn-dev-overlay #heatmap-section-container section::after,
body.bn-dev-overlay #heatmap-theme-container section::after {
  display: none;
}
/* Cancel Jinja2 tint on the Project tab panel itself.
   Unlike Sessions (which has .bn-session-grid as intermediate wrapper),
   #bn-dashboard-root sits directly inside #panel-project — target by ID. */
body.bn-dev-overlay #panel-project {
  outline: none;
}
body.bn-dev-overlay #panel-project::after {
  display: none;
}
/* Cancel Jinja2 outline on .bn-dashboard rendered by React inside mount point */
body.bn-dev-overlay #bn-dashboard-root .bn-dashboard {
  outline: none;
}

/* React islands — pale green overlay + outline.
   Uses both ::after tint AND outline for visibility — the outline is
   always visible even if ::after is occluded by content stacking. */
body.bn-dev-overlay #bn-dashboard-root,
body.bn-dev-overlay #bn-sessions-table-root,
body.bn-dev-overlay #bn-about-developer-root,
body.bn-dev-overlay #bn-quote-sections-root,
body.bn-dev-overlay #bn-quote-themes-root,
body.bn-dev-overlay #bn-codebook-root,
body.bn-dev-overlay #bn-transcript-page-root {
  outline: 3px solid rgba(34, 197, 94, 0.6);  /* green outline */
  outline-offset: -3px;
  background: rgba(134, 239, 172, 0.08) !important;  /* subtle green wash */
}
body.bn-dev-overlay #bn-dashboard-root::after,
body.bn-dev-overlay #bn-sessions-table-root::after,
body.bn-dev-overlay #bn-about-developer-root::after,
body.bn-dev-overlay #bn-quote-sections-root::after,
body.bn-dev-overlay #bn-quote-themes-root::after,
body.bn-dev-overlay #bn-codebook-root::after,
body.bn-dev-overlay #bn-transcript-page-root::after {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(134, 239, 172, 0.15);  /* pale green — React */
  pointer-events: none;
  z-index: 9999;
}

/* Vanilla JS rendered — pale amber overlay + outline */
body.bn-dev-overlay #codebook-grid,
body.bn-dev-overlay #signal-cards,
body.bn-dev-overlay #heatmap-section-container,
body.bn-dev-overlay #heatmap-theme-container {
  outline: 3px solid rgba(234, 179, 8, 0.6);  /* amber outline */
  outline-offset: -3px;
  background: rgba(253, 230, 138, 0.08) !important;  /* subtle amber wash */
}
body.bn-dev-overlay #codebook-grid::after,
body.bn-dev-overlay #signal-cards::after,
body.bn-dev-overlay #heatmap-section-container::after,
body.bn-dev-overlay #heatmap-theme-container::after {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(253, 230, 138, 0.15);  /* pale amber — Vanilla JS */
  pointer-events: none;
  z-index: 9999;
}

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


def _build_vite_dev_scripts() -> str:
    """Vite backend-integration scripts for dev-mode React HMR.

    Injects three blocks so React islands mount and hot-reload when browsing
    the report at localhost:8150/report/ (served by FastAPI, not the Vite
    dev server):

    1. React Fast Refresh preamble (required by @vitejs/plugin-react)
    2. Vite HMR client (websocket, error overlay)
    3. App entry point (src/main.tsx — mounts islands into existing DOM)
    """
    vite = "http://localhost:5173"
    return (
        '<script type="module">\n'
        f"  import RefreshRuntime from '{vite}/@react-refresh'\n"
        "  RefreshRuntime.injectIntoGlobalHook(window)\n"
        "  window.$RefreshReg$ = () => {}\n"
        "  window.$RefreshSig$ = () => (type) => type\n"
        "  window.__vite_plugin_react_preamble_installed__ = true\n"
        "</script>\n"
        f'<script type="module" src="{vite}/@vite/client"></script>\n'
        f'<script type="module" src="{vite}/src/main.tsx"></script>\n'
    )


def _load_live_js() -> str:
    """Read JS source files from disk — called on every request in dev mode.

    Imports ``_JS_FILES`` from ``render_html`` (the canonical dependency-order
    list) and concatenates the raw files.  No caching — edits are picked up
    instantly on browser refresh.
    """
    from bristlenose.stages.render_html import _JS_FILES

    parts: list[str] = [_JS_MARKER + "\n\n"]
    for name in _JS_FILES:
        path = _THEME_DIR / name
        parts.append(f"// --- {name} ---\n")
        parts.append(path.read_text(encoding="utf-8").strip())
        parts.append("\n\n")
    return "".join(parts)


def _replace_baked_js(html: str) -> str:
    """Replace the baked-in JS block with freshly-read source files.

    Finds the marker written by ``render_html.py`` and replaces everything
    from there to the IIFE closing ``})();`` with live JS.  The IIFE wrapper
    ``(function() { ... })();`` is part of the Jinja2 template, not the JS
    files, so we must preserve the closing.
    """
    marker_idx = html.find(_JS_MARKER)
    if marker_idx < 0:
        return html  # no marker found — report rendered without JS (shouldn't happen)
    # Find the IIFE closing })(); before </script>.  The template wraps
    # both data variables and JS modules in (function() { ... })();
    end_script = html.find("</script>", marker_idx)
    if end_script < 0:
        return html
    # Look for })(); just before </script> — that's the IIFE close
    iife_close = html.rfind("})();", marker_idx, end_script)
    if iife_close > 0:
        # Replace marker..iife_close with live JS, keeping })();\n</script>
        live_js = _load_live_js()
        return html[:marker_idx] + live_js + "\n" + html[iife_close:]
    # Fallback: no IIFE wrapper (shouldn't happen with current renderer)
    live_js = _load_live_js()
    return html[:marker_idx] + live_js + "\n" + html[end_script:]


def _rewrite_video_map_uris(html: str, project_dir: Path) -> str:
    """Rewrite file:// URIs in BRISTLENOSE_VIDEO_MAP to /media/ HTTP paths.

    The renderer bakes ``file://`` URIs into the video map which work when
    the report is opened directly from disk.  In serve mode the page is
    loaded over HTTP, so browsers block ``file://`` access.  This function
    converts those URIs to ``/media/`` paths served by StaticFiles.
    """
    import json
    from urllib.parse import quote, unquote

    # Match the JS variable assignment
    pattern = r"(var BRISTLENOSE_VIDEO_MAP\s*=\s*)(\{[^}]*\})(;)"
    match = re.search(pattern, html)
    if not match:
        return html

    try:
        video_map = json.loads(match.group(2))
    except json.JSONDecodeError:
        return html

    prefix = project_dir.resolve().as_uri()  # file:///abs/path/to/project
    rewritten = {}
    for key, uri in video_map.items():
        if uri.startswith(prefix):
            # Strip file:// prefix and project dir, URL-decode then re-encode
            rel = unquote(uri[len(prefix):].lstrip("/"))
            rewritten[key] = "/media/" + quote(rel, safe="/")
        else:
            rewritten[key] = uri

    return html[:match.start()] + (
        match.group(1) + json.dumps(rewritten) + match.group(3)
    ) + html[match.end():]


def _mount_dev_report(
    app: FastAPI, output_dir: Path, project_dir: Path | None = None,
) -> None:
    """Mount the report with dev-mode features injected.

    Layers dev-only features (live JS reload, renderer overlay, Vite HMR,
    developer section) on top of the shared HTML transformations that are
    common to both dev and production serve.
    """
    report_html = output_dir / "index.html"
    if report_html.is_symlink():
        report_html = output_dir / os.readlink(report_html)

    dev_html = _build_dev_section_html(app.state.db_url)
    overlay_html = _build_renderer_overlay_html()
    vite_scripts = _build_vite_dev_scripts()

    @app.get("/report/")
    def serve_report_html() -> HTMLResponse:
        html = report_html.read_text(encoding="utf-8")
        # Dev-only: live-reload JS from source files
        html = _replace_baked_js(html)
        # Shared: video URI rewrite, React mount points, API base URL
        html = _transform_report_html(html, project_dir)
        # Dev-only: inject developer section before the closing .bn-about marker
        html = html.replace("<!-- /bn-about -->", f"{dev_html}<!-- /bn-about -->")
        # Dev-only: inject renderer overlay + Vite dev scripts before </body>
        html = html.replace("</body>", f"{overlay_html}{vite_scripts}</body>")
        return HTMLResponse(html)

    @app.get("/report")
    def redirect_report_to_slash() -> RedirectResponse:
        return RedirectResponse("/report/", status_code=301)

    @app.get("/report/sessions/{filename}")
    def serve_transcript_html(filename: str) -> HTMLResponse:
        """Serve transcript pages with React island injection.

        Only intercepts transcript_*.html files — other session assets
        (if any) fall through to StaticFiles.
        """
        if not filename.startswith("transcript_") or not filename.endswith(".html"):
            from starlette.exceptions import HTTPException as StarletteHTTPException

            raise StarletteHTTPException(status_code=404)

        sessions_dir = output_dir / "sessions"
        page_path = sessions_dir / filename
        if not page_path.is_file():
            raise HTTPException(status_code=404, detail="Transcript page not found")

        sid = filename.removeprefix("transcript_").removesuffix(".html")
        page_html = page_path.read_text(encoding="utf-8")
        # Shared: video URI rewrite, React mount point, API base URL
        page_html = _transform_transcript_html(page_html, sid, project_dir)
        # Dev-only: inject renderer overlay + Vite dev scripts before </body>
        page_html = page_html.replace(
            "</body>", f"{overlay_html}{vite_scripts}</body>"
        )
        return HTMLResponse(page_html)

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


def _mount_prod_report(
    app: FastAPI, output_dir: Path, project_dir: Path | None = None,
) -> None:
    """Mount the report with React islands in production serve mode.

    Like ``_mount_dev_report`` but without dev-only features (Vite HMR,
    renderer overlay, live JS reload, developer section).  Injects the
    pre-built React bundle from ``server/static/assets/``.

    Falls back to plain ``StaticFiles`` if no React bundle is found.
    """
    bundle_tags = _extract_bundle_tags()
    if not bundle_tags:
        logger.warning(
            "React bundle not found at %s — serving static HTML without React "
            "islands. Run 'npm run build' in frontend/ to build the bundle.",
            _STATIC_DIR,
        )
        app.mount(
            "/report", StaticFiles(directory=output_dir, html=True), name="report"
        )
        return

    report_html_path = output_dir / "index.html"
    if report_html_path.is_symlink():
        report_html_path = output_dir / os.readlink(report_html_path)

    @app.get("/report/")
    def serve_report_html_prod() -> HTMLResponse:
        html = report_html_path.read_text(encoding="utf-8")
        html = _transform_report_html(html, project_dir)
        html = html.replace("</head>", f"{bundle_tags}\n</head>")
        return HTMLResponse(html)

    @app.get("/report")
    def redirect_report_to_slash_prod() -> RedirectResponse:
        return RedirectResponse("/report/", status_code=301)

    @app.get("/report/sessions/{filename}")
    def serve_transcript_html_prod(filename: str) -> HTMLResponse:
        """Serve transcript pages with React island injection (production)."""
        if not filename.startswith("transcript_") or not filename.endswith(".html"):
            from starlette.exceptions import HTTPException as StarletteHTTPException

            raise StarletteHTTPException(status_code=404)

        sessions_dir = output_dir / "sessions"
        page_path = sessions_dir / filename
        if not page_path.is_file():
            raise HTTPException(status_code=404, detail="Transcript page not found")

        sid = filename.removeprefix("transcript_").removesuffix(".html")
        page_html = page_path.read_text(encoding="utf-8")
        page_html = _transform_transcript_html(page_html, sid, project_dir)
        page_html = page_html.replace("</head>", f"{bundle_tags}\n</head>")
        return HTMLResponse(page_html)

    # Non-HTML assets (CSS, images, JS from the pipeline) still served normally
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
