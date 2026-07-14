"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import secrets
import traceback
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from bristlenose.server.db import create_session_factory, db_url_for_project, get_engine, init_db
from bristlenose.server.middleware import AUTH_COOKIE_NAME, BearerTokenMiddleware
from bristlenose.server.routes.analysis import router as analysis_router
from bristlenose.server.routes.autocode import router as autocode_router
from bristlenose.server.routes.clips_export import router as clips_export_router
from bristlenose.server.routes.codebook import router as codebook_router
from bristlenose.server.routes.codebook_builder import (
    router as codebook_builder_router,
)
from bristlenose.server.routes.dashboard import router as dashboard_router
from bristlenose.server.routes.data import router as data_router
from bristlenose.server.routes.export import router as export_router
from bristlenose.server.routes.health import router as health_router
from bristlenose.server.routes.miro import router as miro_router
from bristlenose.server.routes.pipeline import router as pipeline_router
from bristlenose.server.routes.quotes import router as quotes_router
from bristlenose.server.routes.quotes_export import router as quotes_export_router
from bristlenose.server.routes.runs import router as runs_router
from bristlenose.server.routes.sessions import router as sessions_router
from bristlenose.server.routes.transcript import router as transcript_router
from bristlenose.server.status_page import detect_status, render_page

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
        dev: When True, enable dev features (playground, admin, dev routes).
             When the Vite dev server is running (``serve --dev``), also uses
             HMR HTML instead of the built bundle.
        db_url: Override database URL (e.g. "sqlite://" for in-memory tests).
        verbose: When True, terminal handler shows DEBUG-level messages.

    In ``serve --dev`` mode uvicorn calls this factory with no arguments on
    reload.  The CLI stashes ``project_dir`` in ``_BRISTLENOSE_PROJECT_DIR``
    so the factory can recover it.
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

    # HMR mode: serve --dev uses uvicorn reload with a factory pattern.
    # When the _BRISTLENOSE_DEV env var is set, the Vite dev server should be
    # running alongside — use HMR HTML.  When dev=True is passed directly
    # (e.g. from run --dev), use the built bundle with the dev flag injected.
    hmr = os.environ.get("_BRISTLENOSE_DEV") == "1"

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

    # Surface tracebacks for unhandled exceptions — FastAPI's default 500
    # handler swallows them.  Always logs to bristlenose.log; returns the
    # traceback in the response body only when BOTH dev=True AND
    # BRISTLENOSE_DEBUG_500=1 (debugging sandbox / packaging issues).  The
    # double gate stops a stale env var in a shipping sidecar from leaking
    # tracebacks.  See docs/design-desktop-asset-serving.md and SECURITY.md.
    _debug_500 = dev and os.environ.get("BRISTLENOSE_DEBUG_500") == "1"

    @app.exception_handler(Exception)
    async def _log_unhandled(request: Request, exc: Exception) -> PlainTextResponse:
        tb = traceback.format_exc()
        logger.error(
            "unhandled %s on %s\n%s", type(exc).__name__, request.url.path, tb
        )
        if _debug_500:
            return PlainTextResponse(tb, status_code=500)
        return PlainTextResponse("Internal Server Error", status_code=500)

    # --- Localhost access control token ---
    # Defence-in-depth: stops opportunistic local-process API scraping.
    # Not an authentication boundary — see SECURITY.md.
    # Recover existing token on uvicorn reload, or generate a fresh one.
    auth_token = os.environ.get("_BRISTLENOSE_AUTH_TOKEN") or secrets.token_urlsafe(32)
    os.environ["_BRISTLENOSE_AUTH_TOKEN"] = auth_token
    app.state.auth_token = auth_token
    # Print BEFORE the "Report:" readiness line so ServeManager.swift
    # has the token before transitioning to .running.
    print(f"[bristlenose] auth-token: {auth_token}", flush=True)

    # Cache-Control: no-store on /api/projects/* — defence-in-depth for the
    # desktop multi-project switch. WKWebView is torn down on project change
    # (SwiftUI `.id(project.id)` reset), but a stale HTTP cache entry could
    # still leak project A's data into project B's first paint. no-store
    # prevents any cache layer (WKWebView HTTP cache, intermediate proxy,
    # browser back/forward cache) from holding /api/projects/* responses
    # across the switch. See `desktop/Bristlenose/Bristlenose/ServeManager.swift`
    # `switchProject(to:)` for the Swift side.
    @app.middleware("http")
    async def _no_store_for_project_api(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/api/projects/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    # Bearer token middleware — must be added before CORS so it runs after CORS
    # in the middleware stack (Starlette processes middleware in reverse order).
    app.add_middleware(BearerTokenMiddleware)

    # Block cross-origin requests — serve mode is localhost-only, no reason for
    # any other origin to call the API.  Same-origin requests are unaffected.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # GZip: compresses text responses (JSON, HTML, CSS, JS).  Added after
    # CORS/auth so it wraps outermost (compresses the final response).  BREACH
    # is not a concern — no user input is reflected in token-bearing responses.
    app.add_middleware(GZipMiddleware, minimum_size=500)

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
    app.state.dev = dev

    app.include_router(health_router)
    app.include_router(analysis_router)
    app.include_router(autocode_router)
    app.include_router(clips_export_router)
    app.include_router(codebook_router)
    app.include_router(codebook_builder_router)
    app.include_router(dashboard_router)
    app.include_router(export_router)
    app.include_router(quotes_export_router)
    app.include_router(runs_router)
    app.include_router(sessions_router)
    app.include_router(quotes_router)
    app.include_router(transcript_router)
    app.include_router(data_router)
    app.include_router(miro_router)
    app.include_router(pipeline_router)

    # Codebook lab — the dynamic-codebook-builder experiment. Gated on a feature
    # flag (default ON) rather than --dev, so it ships in the bundled desktop
    # sidecar and plain `serve` for cohort testing; disable with
    # BRISTLENOSE_EXPERIMENTAL_CODEBOOK_LAB=0. The page is served outside /api so
    # a plain browser nav isn't blocked by the bearer-token middleware; it embeds
    # the token for its own fetches. The lab endpoints ride codebook_lab_router
    # (same /api/dev prefix), so only those dev-prefixed paths exist in prod.
    from bristlenose.config import load_settings

    # Read through the app.state.settings-or-load_settings seam (per
    # server/CLAUDE.md) so an injected settings object is honoured.
    _settings = getattr(app.state, "settings", None) or load_settings()
    if _settings.experimental_codebook_lab:
        from bristlenose.server.routes.dev import (
            build_codebook_lab_html,
            codebook_lab_router,
        )

        app.include_router(codebook_lab_router)

        @app.get("/codebook-lab", include_in_schema=False)
        def _codebook_lab() -> HTMLResponse:
            return HTMLResponse(build_codebook_lab_html(app.state.auth_token))

    # Dev API router (/api/dev/*, incl. the Run Inspector). Mounted under
    # `serve --dev` OR when `_BRISTLENOSE_DEV_ENDPOINTS=1` — the latter is set
    # by the DEBUG desktop build's sidecar so its native Run Inspector window
    # can reach /api/dev/run without flipping the whole app into Vite/HMR dev
    # mode. The Release desktop build never sets it, so production stays clean.
    # Heavier dev surfaces (SQLAdmin, playground) stay gated on real `dev`.
    if dev or os.environ.get("_BRISTLENOSE_DEV_ENDPOINTS") == "1":
        from bristlenose.server.routes.dev import router as dev_router

        app.include_router(dev_router)

    # SQLAdmin database browser. Mounted under full `serve --dev` (browser
    # contributor, full CRUD) OR when `_BRISTLENOSE_ADMIN_PANEL=1` — the latter
    # set by the desktop host's non-App-Store beta channels so a bundled
    # sidecar can serve a *read-only* /admin from the Debug menu. Never mounted
    # in the App Store build (the env var is never set there).
    if dev or os.environ.get("_BRISTLENOSE_ADMIN_PANEL") == "1":
        from sqladmin import Admin as SQLAdmin

        from bristlenose.server.admin import register_admin_views

        sqladmin_app = SQLAdmin(app, engine, base_url="/admin")
        register_admin_views(sqladmin_app, read_only=not dev)

    # Import project data into SQLite on startup
    if project_dir is not None:
        _import_on_startup(session_factory, project_dir)
        _install_event_watcher(app, session_factory, project_dir)

    # Serve the React islands bundle (built by Vite).
    # In HMR mode the Vite dev server handles these.
    #
    # Custom byte-reading routes instead of StaticFiles: under macOS App
    # Sandbox the bundled sidecar's StaticFiles mount returns 500 for every
    # existing file (Starlette streams via aiofiles/sendfile, the syscall is
    # blocked by the sandbox).  Plain bytes-in-memory `read_bytes()` works.
    # Bundle chunks are <1 MB each so memory cost is negligible.
    # See docs/design-desktop-asset-serving.md (Plan A).
    if not hmr and _STATIC_DIR.is_dir():
        _register_static_routes(app, _STATIC_DIR)

    # Serve media files (video/audio) from the project input directory so the
    # popout player can load them over HTTP instead of file:// URIs.
    # Extension allowlist prevents serving .env, .git, .db, etc.
    if project_dir is not None:
        _mount_media_route(app, project_dir)

    # Serve the report SPA from the Vite build output
    if project_dir is not None:
        output_dir = project_dir / "bristlenose-output"
        if not output_dir.is_dir():
            output_dir = project_dir  # Caller already pointed at the output dir
        if output_dir.is_dir():
            if hmr:
                _mount_dev_report(app, output_dir)
            else:
                _mount_prod_report(app, output_dir, dev=dev)
        else:
            logger.warning("report mount skipped — %s does not exist", output_dir)

    if hmr:
        _print_dev_urls()

    return app


def _register_static_routes(app: FastAPI, static_dir: Path) -> None:
    """Serve the React bundle from ``static_dir`` via in-memory ``read_bytes``.

    Replaces ``StaticFiles`` because Starlette's streaming path (sendfile /
    aiofiles) returns 500 under macOS App Sandbox.  Mounts:

    - ``GET /static/{path}`` — the bundle root (index.html, chunks under
      ``assets/``, plus any non-asset siblings)
    - ``GET /assets/{path}`` — alias for ``static/assets/`` so Vite's lazy-load
      runtime, which resolves chunks against base ``/``, finds them without
      requiring HTML rewrites inside the JS

    Both routes apply a path-traversal guard.
    """
    resolved_root = static_dir.resolve()

    @app.get("/static/{path:path}")
    async def _serve_static(path: str) -> Response:
        return await _read_bundle_file(resolved_root, path)

    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        resolved_assets = assets_dir.resolve()

        @app.get("/assets/{path:path}")
        async def _serve_assets(path: str) -> Response:
            return await _read_bundle_file(resolved_assets, path)


async def _read_bundle_file(root: Path, path: str) -> Response:
    """Resolve ``path`` under ``root`` and return its bytes, with guards.

    Uses ``asyncio.to_thread`` to keep the event loop responsive while
    reading from disk.  Vite-hashed chunks get a one-year ``immutable``
    cache header; ``index.html`` (not content-hashed) gets ``no-cache`` so
    bundle updates take effect immediately.
    """

    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise HTTPException(status_code=403)
    if not target.is_file():
        raise HTTPException(status_code=404)
    media_type, _ = mimetypes.guess_type(target.name)
    cache_control = (
        "no-cache"
        if target.name == "index.html"
        else "public, max-age=31536000, immutable"
    )
    content = await asyncio.to_thread(target.read_bytes)
    return Response(
        content=content,
        media_type=media_type or "application/octet-stream",
        headers={"Cache-Control": cache_control},
    )


_MEDIA_EXTENSIONS = frozenset({
    # Video
    ".mp4", ".mov", ".webm", ".avi", ".mkv", ".m4v",
    # Audio
    ".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".wma",
    # Subtitles
    ".srt", ".vtt",
    # Transcripts (docx ingestion)
    ".docx", ".txt",
    # Images (thumbnails)
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
})


def _mount_media_route(app: FastAPI, project_dir: Path) -> None:
    """Register a /media/ route with extension allowlist and path-traversal guard."""
    resolved_root = project_dir.resolve()

    @app.get("/media/{path:path}")
    async def serve_media(path: str) -> FileResponse:
        full = (resolved_root / path).resolve()
        # Path traversal guard — must stay inside project_dir
        if not full.is_relative_to(resolved_root):
            raise HTTPException(status_code=403, detail="Forbidden")
        # Extension allowlist
        if full.suffix.lower() not in _MEDIA_EXTENSIONS:
            raise HTTPException(status_code=403, detail="Forbidden")
        if not full.is_file():
            raise HTTPException(status_code=404, detail="Not found")
        resp = FileResponse(full)
        # Prevent GZipMiddleware from compressing pre-compressed media codecs
        # (wastes CPU, breaks Range/byte-seek for video playback).
        resp.headers["Content-Encoding"] = "identity"
        return resp


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


def _html_root_attrs() -> str:
    """Build extra attributes for the <html> element.

    Reads platform, palette, and typography from environment:
    - BRISTLENOSE_PLATFORM: "desktop" when launched from the macOS app
    - BRISTLENOSE_PALETTE: colour-palette name (e.g. "edo", "default"). The
      canonical name; BRISTLENOSE_COLOR_THEME is the deprecated alias, still set
      by older desktop builds (grep desktop/). The internal attribute stays
      data-color-theme — only the user-facing env/CLI name was renamed.
    - BRISTLENOSE_TYPOGRAPHY: "inter" opts the desktop app back to the web/Inter
      type scale. SF Pro is the default and is implied by the attribute's
      absence (CSS gates on :not([data-typography="inter"])); SF Pro is licensed
      for Apple platforms only.

    Desktop defaults to "edo" palette if no explicit palette is set.
    """
    parts: list[str] = []
    platform = os.environ.get("BRISTLENOSE_PLATFORM", "")
    palette = os.environ.get("BRISTLENOSE_PALETTE") or os.environ.get(
        "BRISTLENOSE_COLOR_THEME", ""
    )
    typography = os.environ.get("BRISTLENOSE_TYPOGRAPHY", "")
    if platform:
        parts.append(f'data-platform="{platform}"')
    if not palette and platform == "desktop":
        palette = "edo"
    if palette:
        parts.append(f'data-color-theme="{palette}"')
    if typography:
        parts.append(f'data-typography="{typography}"')
    return " ".join(parts)


def _build_spa_html(
    output_dir: Path, *, dev: bool = False, auth_token: str = ""
) -> str:
    """Read the Vite-built index.html and prepare it for serving.

    - Rewrites ``/assets/`` paths to ``/static/assets/`` (bundle served via StaticFiles)
    - Injects ``<link>`` for the theme CSS (from the pipeline output dir)
    - Injects platform/theme attributes on ``<html>``
    - Injects auth token for API access control
    - When *dev* is True, injects ``window.__BRISTLENOSE_DEV__ = true`` so the
      responsive playground loads (without requiring the Vite dev server)
    """
    import re

    index_path = _STATIC_DIR / "index.html"
    html = index_path.read_text(encoding="utf-8")
    # Rewrite bundle asset paths: /assets/ → /static/assets/
    html = re.sub(r'((?:src|href)=")/assets/', r'\1/static/assets/', html)
    # Inject platform/theme attributes on <html>
    extra = _html_root_attrs()
    if extra:
        html = html.replace("<html", f"<html {extra}", 1)
    # Inject theme CSS before </head> — served from output dir at /report/assets/
    theme_link = '<link rel="stylesheet" href="/report/assets/bristlenose-theme.css">'
    html = html.replace("</head>", f"{theme_link}\n</head>")
    # Auth token for localhost API access control (json.dumps for safe serialisation)
    if auth_token:
        token_script = (
            "<script>window.__BRISTLENOSE_AUTH_TOKEN__"
            f" = {json.dumps(auth_token)}</script>"
        )
        html = html.replace("</head>", f"{token_script}\n</head>")
    # Dev flag — enables responsive playground without Vite HMR
    if dev:
        dev_script = "<script>window.__BRISTLENOSE_DEV__ = true</script>"
        html = html.replace("</head>", f"{dev_script}\n</head>")
    return html


def _spa_response(html: str, auth_token: str) -> HTMLResponse:
    """Return the SPA HTML with the auth cookie attached.

    The same token already lives in ``window.__BRISTLENOSE_AUTH_TOKEN__`` for
    JS-side ``fetch()`` calls; the cookie covers plain navigations (e.g. the
    export ``<a download>`` anchor click). CORS middleware blocks all
    cross-origin requests, so CSRF is out of scope.
    """
    response = HTMLResponse(html)
    if auth_token:
        response.set_cookie(
            key=AUTH_COOKIE_NAME,
            value=auth_token,
            httponly=True,
            secure=False,  # localhost only — never traverses the network
            samesite="strict",
            path="/",
        )
    return response


def _build_dev_html(output_dir: Path, *, auth_token: str = "") -> str:
    """Build a self-contained dev HTML page with Vite HMR scripts.

    No baked HTML reading, no regex surgery.  Includes:
    - React Refresh preamble (required by @vitejs/plugin-react)
    - Vite HMR client
    - App entry point (src/main.tsx)
    - Theme CSS from the pipeline output dir
    """
    vite = "http://localhost:5173"
    extra = _html_root_attrs()
    html_open = f'<html lang="en" {extra}>\n' if extra else '<html lang="en">\n'
    return (
        "<!doctype html>\n"
        f"{html_open}"
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
        + (f"  window.__BRISTLENOSE_AUTH_TOKEN__ = {json.dumps(auth_token)}\n"
           if auth_token else "")
        + "  window.__BRISTLENOSE_DEV__ = true\n"
        "</script>\n"
        f'<script type="module" src="{vite}/@vite/client"></script>\n'
        f'<script type="module" src="{vite}/src/main.tsx"></script>\n'
        "</body>\n"
        "</html>\n"
    )


def _maybe_status_response(app: FastAPI, output_dir: Path) -> HTMLResponse | None:
    """Return a server-rendered status page when the SPA can't render.

    Intercepts the SPA catch-all route when the project has no completed
    run, or the latest run failed / was cancelled. ``None`` lets the SPA
    handle the request as today. See ``status_page.detect_status`` for the
    decision matrix.
    """
    last_run = getattr(app.state, "last_run", None)
    status = detect_status(
        output_dir,
        last_run,
        platform=os.environ.get("BRISTLENOSE_PLATFORM", ""),
    )
    if status is None:
        return None
    from bristlenose.server.routes.health import (
        DEFAULT_HELP_URL,
        build_health_payload,
    )

    # Single source of truth: the status page's feedback config is the same
    # config /api/health exposes (URL, enabled flag, version) — so the inline
    # browser form, the native sheet (which reads /api/health), and the React
    # modal all agree. Help is the docs site; "report a bug" (GitHub) is a
    # separate footer affordance, not Help.
    health = build_health_payload(dev=bool(getattr(app.state, "dev", False)))
    feedback = health["feedback"]  # type: ignore[index]
    help_url = os.environ.get("BRISTLENOSE_HELP_URL", DEFAULT_HELP_URL)
    html_str = render_page(
        status,
        feedback_url=str(feedback["url"]),  # type: ignore[index]
        feedback_enabled=bool(feedback["enabled"]),  # type: ignore[index]
        help_url=help_url,
        version=str(health["version"]),  # type: ignore[index]
        html_root_attrs=_html_root_attrs(),
    )
    # Match the SPA response's cookie contract — every /report/* HTML response
    # sets the auth cookie so subsequent /api/* fetches from the same origin
    # work even if/when the SPA mounts (e.g. user reruns and reloads).
    return _spa_response(html_str, app.state.auth_token)


def _mount_dev_report(app: FastAPI, output_dir: Path) -> None:
    """Mount the report SPA in dev mode with Vite HMR.

    Serves a self-contained HTML page with Vite dev scripts.  No baked HTML
    reading or regex surgery — React renders everything (header, nav, content,
    footer).  Data comes from API endpoints.
    """
    dev_html = _build_dev_html(output_dir, auth_token=app.state.auth_token)

    # Live CSS: re-read theme source files on every request (no caching).
    # Defined before the catch-all so it takes priority.
    @app.get("/report/assets/bristlenose-theme.css")
    def serve_live_theme_css() -> Response:
        """Dev only: concatenate CSS from source on every request."""
        from bristlenose.stages.s12_render.theme_assets import load_default_css

        return Response(
            load_default_css(),
            media_type="text/css",
            headers={"Cache-Control": "no-store"},
        )

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

        status_resp = _maybe_status_response(app, output_dir)
        if status_resp is not None:
            return status_resp
        return _spa_response(dev_html, app.state.auth_token)

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


def _mount_prod_report(app: FastAPI, output_dir: Path, *, dev: bool = False) -> None:
    """Mount the report SPA in production serve mode.

    Reads the Vite-built index.html once at startup, rewrites asset paths,
    and injects theme CSS.  When *dev* is True, injects
    ``window.__BRISTLENOSE_DEV__`` so the responsive playground loads without
    the Vite dev server.

    **Fail-loud contract (C3 post-mortem, 21 Apr 2026):** if the React bundle
    is missing from ``static/``, this mount refuses to serve — it returns 500
    with a clear error page explaining the bundle is broken. The previous
    behaviour silently fell back to serving the static-rendered HTML from the
    output dir, which looked like the app was working but had no data APIs,
    no video playback, no React islands. That fallback masked bundle-
    packaging bugs (BUG-3 in the C3 smoke test) and is not a valid
    degradation path.

    The static render (``bristlenose/stages/s12_render/``) remains a
    first-class product for CLI users via ``bristlenose render`` and the
    on-disk HTML report written by ``bristlenose run``. It is deliberately
    **never** served by ``bristlenose serve``.
    """
    index_path = _STATIC_DIR / "index.html"
    if not index_path.is_file():
        logger.error(
            "React bundle not found at %s — serve mode refusing to start. "
            "Run 'npm run build' in frontend/, OR if this is a bundled "
            "sidecar, the .app is incomplete (BUG-3 class). See "
            "docs/walkthroughs/c3-smoke-test results.md.",
            _STATIC_DIR,
        )

        @app.get("/report")
        @app.get("/report/{path:path}", response_model=None)
        def serve_bundle_error(path: str = "") -> Response:
            html = (
                "<!doctype html><html><head>"
                "<meta charset=\"utf-8\"><title>Bristlenose — build incomplete</title>"
                "<style>body{font-family:ui-sans-serif,system-ui,sans-serif;"
                "max-width:640px;margin:4rem auto;padding:0 1rem;color:#ddd;"
                "background:#1a1a1a;line-height:1.5}code{background:#333;"
                "padding:.1em .3em;border-radius:.2em}h1{color:#fff}"
                ".detail{color:#999;font-size:.9em;margin-top:2rem}</style>"
                "</head><body>"
                "<h1>Build incomplete</h1>"
                "<p>The Bristlenose React bundle is missing from this build. "
                "Serve mode refuses to start without it.</p>"
                "<p>If you are running the desktop app, this build is broken — "
                "reinstall or report a bug.</p>"
                "<p>If you are a developer: run <code>npm run build</code> in "
                "<code>frontend/</code> and restart <code>bristlenose serve</code>. "
                "If running from the PyInstaller sidecar, check that "
                "<code>bristlenose/server/static/</code> is in the spec's "
                "<code>datas</code>.</p>"
                "<p class=\"detail\">BUG-3 class — see the C3 smoke test "
                "post-mortem for context.</p>"
                "</body></html>"
            )
            return HTMLResponse(html, status_code=500)

        return

    spa_html = _build_spa_html(output_dir, dev=dev, auth_token=app.state.auth_token)

    @app.get("/report")
    def redirect_report_to_slash_prod() -> RedirectResponse:
        return RedirectResponse("/report/", status_code=301)

    # Theme CSS fallback: brand-new projects that haven't been through the
    # pipeline yet have no `<output_dir>/assets/bristlenose-theme.css`. Without
    # this route the SPA's <link> 404s and the whole UI renders unstyled.
    # Mirror dev mode's `load_default_css()` behaviour: prefer the project's
    # rendered CSS if it exists (so per-project theme tweaks still win), fall
    # back to the cached bundled source otherwise. The cache is process-scoped
    # so the 47-file disk read happens at most once per server process.
    _theme_cache_headers = {"Cache-Control": "public, max-age=3600"}

    @app.get("/report/assets/bristlenose-theme.css")
    def serve_theme_css_with_fallback() -> Response:
        per_project = output_dir / "assets" / "bristlenose-theme.css"
        if per_project.is_file():
            return FileResponse(
                per_project,
                media_type="text/css",
                headers=_theme_cache_headers,
            )
        from bristlenose.stages.s12_render.theme_assets import get_default_css

        return Response(
            get_default_css(),
            media_type="text/css",
            headers=_theme_cache_headers,
        )

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

        status_resp = _maybe_status_response(app, output_dir)
        if status_resp is not None:
            return status_resp
        return _spa_response(spa_html, app.state.auth_token)

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


def _make_run_completed_handler(
    app: FastAPI,
    session_factory: object,
    project_dir: Path,
):
    """Build the watcher callback: re-import THEN publish ``last_run``.

    Extracted to module level so the race ordering (import before
    ``last_run`` assignment) is testable without standing up a full
    server lifecycle. SPA polling is keyed off ``run_id``; flipping the
    key before the DB is fresh would race the refetch and show stale or
    empty data.
    """
    from bristlenose.events import RunCompletedEvent
    from bristlenose.server.importer import import_project

    def _reimport_sync() -> None:
        db = session_factory()  # type: ignore[operator]
        try:
            import_project(db, project_dir)
        except Exception:
            logger.exception(
                "Re-import after run_completed failed for %s", project_dir,
            )
        finally:
            db.close()

    async def _on_run_completed(ev: RunCompletedEvent) -> None:
        await asyncio.to_thread(_reimport_sync)
        app.state.last_run[1] = {
            "run_id": ev.run_id,
            "outcome": ev.outcome.value,
            "completed_at": ev.ended_at,
        }

    return _on_run_completed


def _install_event_watcher(
    app: FastAPI,
    session_factory: object,
    project_dir: Path,
) -> None:
    """Tail ``pipeline-events.jsonl`` and re-import on ``run_completed``.

    Without this, a pipeline run that completes *while* serve is running
    leaves SQLite empty until the next serve restart — the React UI shows
    "0 sessions / 0 quotes" despite full data on disk. Wired via
    FastAPI's lifespan so the polling task is started at app startup and
    cancelled cleanly on shutdown.
    """
    from contextlib import asynccontextmanager

    from bristlenose.events import (
        EventTypeEnum,
        events_path,
        read_events,
    )
    from bristlenose.server.event_watcher import run_event_watcher

    output_dir = project_dir / "bristlenose-output"
    if not output_dir.is_dir():
        output_dir = project_dir
    events_file = events_path(output_dir)

    # Per-project last-run map. Single project (id=1) for now; the dict
    # shape carries forward to multi-project without an API change. Each
    # entry is populated AFTER the SQLite re-import completes — the
    # endpoint's correctness contract is "if last_run.run_id is set, the
    # DB has data from that run".
    app.state.last_run = {}

    # Seed from any existing terminus on disk so the SPA's first poll
    # sees a non-null run_id and can reconcile against its own (null)
    # baseline. Startup import has already loaded that data into SQLite.
    # Includes failed and cancelled terminus events so the server-rendered
    # status page (status_page.detect_status) can surface them on restart
    # without re-reading the events log on every catch-all request.
    if events_file.exists():
        termini = (
            EventTypeEnum.RUN_COMPLETED,
            EventTypeEnum.RUN_FAILED,
            EventTypeEnum.RUN_CANCELLED,
        )
        for ev in reversed(read_events(events_file)):
            if ev.event in termini:
                app.state.last_run[1] = {
                    "run_id": ev.run_id,
                    "outcome": getattr(ev, "outcome").value,
                    "completed_at": getattr(ev, "ended_at"),
                }
                break

    _on_run_completed = _make_run_completed_handler(
        app, session_factory, project_dir,
    )

    @asynccontextmanager
    async def _lifespan(_: FastAPI):
        task = asyncio.create_task(
            run_event_watcher(events_file, _on_run_completed),
            name="bristlenose-event-watcher",
        )
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    app.router.lifespan_context = _lifespan
