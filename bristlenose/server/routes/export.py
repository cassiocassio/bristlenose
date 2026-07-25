"""Export endpoint — self-contained HTML report download.

Gathers all API data, embeds it as JSON in a self-contained HTML file
with the React SPA bundle inlined, and returns it as a file download.
Recipients can open the HTML in any modern browser without Bristlenose.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from starlette.responses import Response

from bristlenose.server.routes.health import build_health_payload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# ---------------------------------------------------------------------------
# Offline coverage contract
# ---------------------------------------------------------------------------
#
# Every GET read endpoint under /projects/{project_id}/… must be EITHER embedded
# in the export (listed here, and produced by export_report below) OR explicitly
# annotated ``openapi_extra={"x-bn-offline": "server-only"}`` on its route.  The
# coverage gate (tests/test_serve_export_coverage.py) fails the build on any GET
# read path that is neither — so a new feature is offline-by-default and dropping
# it from the export is a deliberate, reviewed act, not silent drift.
#
# These are OpenAPI path templates (with {project_id} etc.), matched directly
# against ``app.openapi()["paths"]``.  Dynamic per-item paths (transcripts,
# moderator-question) are templated here and expanded to one embed key per item
# at build time.
EMBED_PATH_TEMPLATES: frozenset[str] = frozenset(
    {
        "/projects/{project_id}/info",
        "/projects/{project_id}/dashboard",
        "/projects/{project_id}/sessions",
        "/projects/{project_id}/quotes",
        "/projects/{project_id}/codebook",
        "/projects/{project_id}/people",
        "/projects/{project_id}/video-map",
        "/projects/{project_id}/analysis/sentiment",
        "/projects/{project_id}/analysis/codebooks",
        "/projects/{project_id}/framework-states",
        "/projects/{project_id}/hidden-tag-groups",
        "/projects/{project_id}/transcripts/{session_id}",
        "/projects/{project_id}/quotes/{dom_id}/moderator-question",
    }
)

# GET read paths that are DELIBERATELY not available offline — server-compute
# (LLM/ffmpeg), live integrations, download endpoints, or write-mirror reads whose
# state is already baked into /quotes.  Their UI affordance is hidden offline via
# ``isExportMode()`` guards (see ExportDropdown/MiroExportPanel/AutoCode etc.).
# Adding here is the explicit, reviewed opt-out the coverage gate demands; a new
# GET read that is in NEITHER set fails the gate.
SERVER_ONLY_PATH_TEMPLATES: frozenset[str] = frozenset(
    {
        "/projects/{project_id}/analysis/tags",  # no SPA callers; server-compute
        "/projects/{project_id}/autocode/{framework_id}/proposals",
        "/projects/{project_id}/autocode/{framework_id}/status",
        "/projects/{project_id}/codebook/remove-framework/{framework_id}/impact",
        "/projects/{project_id}/codebook/tags/{tag_id}/builder",
        "/projects/{project_id}/codebook/templates",
        "/projects/{project_id}/deleted-badges",  # write-mirror; baked into /quotes
        "/projects/{project_id}/edits",  # write-mirror; baked into /quotes
        "/projects/{project_id}/export",  # the export endpoint itself
        "/projects/{project_id}/export/clips/status",
        "/projects/{project_id}/export/quotes.csv",
        "/projects/{project_id}/export/quotes.xlsx",
        "/projects/{project_id}/hidden",  # write-mirror; baked into /quotes
        "/projects/{project_id}/last-run",  # live run status
        "/projects/{project_id}/miro/auth-url",
        "/projects/{project_id}/miro/status",
        "/projects/{project_id}/starred",  # write-mirror; baked into /quotes
        "/projects/{project_id}/tags",  # write-mirror; baked into /quotes
    }
)


# ---------------------------------------------------------------------------
# Anonymisation
# ---------------------------------------------------------------------------

def _anonymise_data(endpoints: dict[str, Any]) -> None:
    """Strip participant names from all embedded data (shallow anonymisation).

    Keeps moderator (m*) and observer (o*) names.  Replaces participant
    (p*) full_name/short_name with empty strings.  Mutates ``endpoints`` in
    place; keys are relative API paths (see export_report).
    """
    # People map
    people = endpoints.get("/people") or {}
    for code, info in people.items():
        if code.startswith("p"):
            info["full_name"] = ""
            info["short_name"] = ""

    # Dashboard sessions — speaker names + featured quotes
    dashboard = endpoints.get("/dashboard") or {}
    for sess in dashboard.get("sessions", []):
        for spk in sess.get("speakers", []):
            if spk.get("speaker_code", "").startswith("p"):
                spk["name"] = ""
    for fq in dashboard.get("featured_quotes", []):
        if fq.get("participant_id", "").startswith("p"):
            fq["speaker_name"] = ""

    # Sessions list — speakers
    sessions = endpoints.get("/sessions") or {}
    for sess in sessions.get("sessions", []):
        for spk in sess.get("speakers", []):
            if spk.get("speaker_code", "").startswith("p"):
                spk["name"] = ""

    # Quotes — speaker names in sections and themes
    quotes = endpoints.get("/quotes") or {}
    for group_key in ("sections", "themes"):
        for group in quotes.get(group_key, []):
            for q in group.get("quotes", []):
                if q.get("participant_id", "").startswith("p"):
                    q["speaker_name"] = ""

    # Transcripts — speaker names (one embed key per session)
    for key, tx in endpoints.items():
        if not key.startswith("/transcripts/") or not isinstance(tx, dict):
            continue
        for spk in tx.get("speakers", []):
            if spk.get("code", "").startswith("p"):
                spk["name"] = ""

    # Project info (/info): project_name, session_count, participant_count are
    # fine — no PII.


def _strip_filesystem_paths(endpoints: dict[str, Any]) -> None:
    """Remove absolute filesystem paths from export data.

    Exported HTML is shared with stakeholders — leaking paths like
    ``/Users/cassio/interviews/sarah.mp4`` reveals the researcher's
    username and directory layout.  Replace ``path`` with ``filename``
    (already present) and blank out ``source_folder_uri``.  Mutates
    ``endpoints`` in place; keys are relative API paths.
    """
    # Sessions list — source_files[].path and source_folder_uri
    sessions = endpoints.get("/sessions") or {}
    for sess in sessions.get("sessions", []):
        for sf in sess.get("source_files", sess.get("sourceFiles", [])):
            if "filename" in sf:
                sf["path"] = sf["filename"]
            elif "path" in sf:
                sf["path"] = sf["path"].rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    # Blank the folder URI (absolute path as file:// URI)
    if "source_folder_uri" in sessions:
        sessions["source_folder_uri"] = ""
    if "sourceFolderUri" in sessions:
        sessions["sourceFolderUri"] = ""

    # Dashboard sessions — same structure
    dashboard = endpoints.get("/dashboard") or {}
    for sess in dashboard.get("sessions", []):
        for sf in sess.get("source_files", sess.get("sourceFiles", [])):
            if "filename" in sf:
                sf["path"] = sf["filename"]
            elif "path" in sf:
                sf["path"] = sf["path"].rsplit("/", 1)[-1].rsplit("\\", 1)[-1]


# ---------------------------------------------------------------------------
# Logo embedding
# ---------------------------------------------------------------------------

_LOGOS_DIR = Path(__file__).resolve().parent.parent.parent / "theme" / "images"


def _build_logo_data_uris() -> dict[str, str]:
    """Return base64 data URIs for the light and dark logos.

    Embedded in the export payload so the footer logo renders when the
    exported HTML is opened from ``file://`` (no server to serve images).
    """
    result: dict[str, str] = {}
    for variant, fname in [("light", "bristlenose.png"), ("dark", "bristlenose-dark.png")]:
        p = _LOGOS_DIR / fname
        if p.is_file():
            b64 = base64.b64encode(p.read_bytes()).decode("ascii")
            result[variant] = f"data:image/png;base64,{b64}"
    return result


# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------

def _toposort_chunks(
    all_js: dict[str, str],
    chunk_names: list[str],
) -> list[str]:
    """Return chunk names in dependency order (leaves first).

    Parses static ``from"./X.js"`` imports to build a dependency graph,
    then applies Kahn's algorithm.  Chunks with no dependencies come
    first so their blob URLs are available when dependents are processed.
    """
    # Build adjacency: chunk → set of chunks it imports
    deps: dict[str, set[str]] = {name: set() for name in chunk_names}
    chunk_set = set(chunk_names)
    for name in chunk_names:
        src = all_js[name]
        for other in chunk_set:
            if other != name and f'from"./{other}"' in src:
                deps[name].add(other)

    # Kahn's algorithm — in_degree = number of unprocessed dependencies
    in_degree = {name: len(d) for name, d in deps.items()}
    queue = [name for name in chunk_names if in_degree[name] == 0]
    result: list[str] = []
    while queue:
        node = queue.pop(0)
        result.append(node)
        for name, d in deps.items():
            if node in d:
                d.discard(node)
                in_degree[name] = len(d)
                if in_degree[name] == 0 and name not in result:
                    queue.append(name)
    # Append any remaining (circular deps — shouldn't happen with Vite)
    for name in chunk_names:
        if name not in result:
            result.append(name)
    return result


def _build_export_html(
    export_data: dict,
    theme_css: str,
) -> str:
    """Build a self-contained HTML file with embedded React app and data.

    All JS modules are loaded via blob URLs created in a classic bootstrap
    ``<script>``.  Chunks are processed in dependency order (leaves first)
    so that when a module is blob-URL'd, all its ``from"./X.js"`` imports
    have already been replaced with the actual blob URLs of their targets.
    The main bundle is loaded last via ``import(mainBlobUrl)``.
    """
    index_path = _STATIC_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(
            status_code=500,
            detail="Frontend build not found — run 'npm run build' first",
        )

    index_html = index_path.read_text(encoding="utf-8")

    # Collect JS files referenced in the index.html
    # Pattern: <script ... src="/assets/main-xxx.js">
    script_pattern = re.compile(r'src="/assets/([^"]+\.js)"')

    main_files: list[str] = []
    for m in script_pattern.finditer(index_html):
        main_files.append(m.group(1))

    # Read ALL JS files from assets/
    assets_dir = _STATIC_DIR / "assets"
    all_js: dict[str, str] = {}
    for fpath in sorted(assets_dir.glob("*.js")):
        all_js[fpath.name] = fpath.read_text(encoding="utf-8")

    chunk_names = [name for name in all_js if name not in main_files]
    ordered_chunks = _toposort_chunks(all_js, chunk_names)

    # Build the data injection script
    data_json = json.dumps(export_data, ensure_ascii=True, separators=(",", ":"))

    # Build the full HTML
    html_parts = [
        "<!doctype html>\n",
        '<html lang="en">\n',
        "<head>\n",
        '<meta charset="UTF-8" />\n',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0" />\n',
        '<meta name="color-scheme" content="light dark" />\n',
        # Google Fonts — degrades to system font stack when offline
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n',
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n',
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400..700'
        '&display=swap" rel="stylesheet">\n',
        "<title>Bristlenose Report</title>\n",
        # Theme CSS inlined
        "<style>\n",
        theme_css,
        "\n</style>\n",
        "</head>\n",
        '<body class="bn-export-mode">\n',
        '<div id="bn-app-root" data-project-id="1"></div>\n',
        # Embedded data (before app scripts so it's available at module load)
        "<script>\n",
        "window.BRISTLENOSE_EXPORT=",
        data_json,
        ";\n</script>\n",
    ]

    # Bootstrap: create blob URLs in dependency order, then load main bundle.
    #
    # Processing order: leaf chunks first (no local imports), then chunks
    # that import them, then finally the main bundle.  At each step we
    # use runtime string replacement to swap ``./X.js`` references with
    # the already-known blob URL of X.  This handles both static
    # ``from"./X.js"`` and dynamic ``import("./X.js")`` as well as
    # Vite's ``__vite__mapDeps`` preload paths (``assets/X.js``).
    #
    # The bootstrap runs as a classic <script> (not module) so it
    # executes synchronously before any modules load.  The final line
    # ``import(mainBlobUrl)`` kicks off the ES module graph.
    #
    # NOTE (file:// limitation): blob: URLs work when the export is *served*
    # (WKWebView / http origin — how it is consumed today) but are BLOCKED as
    # module scripts when the file is opened directly from disk (file://, an
    # opaque origin).  Making the artifact render from a raw file:// double-click
    # needs a dedicated single-file inline build, not a bootstrap tweak — see
    # e2e/tests/export-file-url.spec.ts and the tracker there.  Do not "fix" this
    # by switching to data: URLs: a data: module cannot resolve its own bare/
    # relative sub-imports, which regresses the served case too.
    html_parts.append("<script>\n")
    html_parts.append("(function(){\n")
    html_parts.append("var C={};\n")  # chunk name → blob URL

    # All chunk names that need URL rewriting
    all_chunk_names = ordered_chunks  # in dependency order

    # Emit a JS function that replaces ./X.js and assets/X.js references
    # in a source string with the actual blob URLs from C.
    html_parts.append("function R(s){\n")
    for chunk in all_chunk_names:
        # Replace from"./X.js" → from"<blobURL>" and "./X.js" → "<blobURL>"
        # and "assets/X.js" → "<blobURL>"
        # Use split+join for reliable string replacement in JS.
        js_chunk = json.dumps(f"./{chunk}")  # e.g. '"./SessionsTable-xxx.js"'
        js_assets = json.dumps(f"assets/{chunk}")  # e.g. '"assets/SessionsTable-xxx.js"'
        html_parts.append(
            f"s=s.split({js_chunk}).join(C[{json.dumps(chunk)}]);\n"
        )
        html_parts.append(
            f"s=s.split({js_assets}).join(C[{json.dumps(chunk)}]);\n"
        )
    html_parts.append("return s}\n")

    # Create blob URLs for chunks (dependency order — leaves first)
    for fname in all_chunk_names:
        escaped = json.dumps(all_js[fname], ensure_ascii=False)
        html_parts.append(
            f"C[{json.dumps(fname)}]=URL.createObjectURL("
            f"new Blob([R({escaped})],"
            '{type:"text/javascript"}));\n'
        )

    # Create blob URLs for main bundle(s)
    for fname in main_files:
        if fname in all_js:
            escaped = json.dumps(all_js[fname], ensure_ascii=False)
            html_parts.append(
                f"C[{json.dumps(fname)}]=URL.createObjectURL("
                f"new Blob([R({escaped})],"
                '{type:"text/javascript"}));\n'
            )

    # Load main bundle(s) via dynamic import
    for fname in main_files:
        if fname in all_js:
            html_parts.append(f"import(C[{json.dumps(fname)}]);\n")

    html_parts.append("})();\n")
    html_parts.append("</script>\n")

    html_parts.append("</body>\n</html>\n")

    return "".join(html_parts)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/export")
def export_report(
    project_id: int,
    request: Request,
    anonymise: bool = Query(default=False),
) -> Response:
    """Export the project as a self-contained HTML report.

    Gathers all API data, embeds it in the React SPA shell, and returns
    a downloadable HTML file.
    """
    from bristlenose.server.models import Quote
    from bristlenose.server.routes.analysis import (
        get_codebook_analysis as _get_codebook_analysis_handler,
    )
    from bristlenose.server.routes.analysis import (
        get_sentiment_analysis as _get_sentiment_analysis_handler,
    )
    from bristlenose.server.routes.codebook import get_codebook as _get_codebook_handler
    from bristlenose.server.routes.dashboard import (
        get_dashboard as _get_dashboard_handler,
    )
    from bristlenose.server.routes.dashboard import (
        get_project_info as _get_project_info_handler,
    )
    from bristlenose.server.routes.data import (
        get_framework_states as _get_framework_states_handler,
    )
    from bristlenose.server.routes.data import (
        get_hidden_tag_groups as _get_hidden_tag_groups_handler,
    )
    from bristlenose.server.routes.data import get_people as _get_people_handler
    from bristlenose.server.routes.quotes import _quote_dom_id
    from bristlenose.server.routes.quotes import (
        get_moderator_question as _get_moderator_question_handler,
    )
    from bristlenose.server.routes.quotes import get_quotes as _get_quotes_handler
    from bristlenose.server.routes.sessions import get_sessions as _get_sessions_handler
    from bristlenose.server.routes.transcript import (
        get_transcript as _get_transcript_handler,
    )
    from bristlenose.utils.text import slugify

    # --- Gather data by calling existing route handlers ---
    # Each handler manages its own DB session (opens + closes).  We embed the
    # handlers' OWN return values serialised through FastAPI's jsonable_encoder
    # (the exact serializer the HTTP path uses), so the offline shape can never
    # drift from what the SPA sees over the wire.

    project_info = _get_project_info_handler(project_id, request)
    dashboard = _get_dashboard_handler(project_id, request)
    quotes = _get_quotes_handler(project_id, request)
    codebook = _get_codebook_handler(project_id, request)
    people = _get_people_handler(project_id, request)
    framework_states = _get_framework_states_handler(project_id, request)
    hidden_tag_groups = _get_hidden_tag_groups_handler(project_id, request)

    # get_sessions uses Depends(_get_db) — call with explicit db
    db = request.app.state.db_factory()
    try:
        sessions = _get_sessions_handler(project_id, db=db)
    finally:
        db.close()

    # Sentiment analysis
    sentiment = _get_sentiment_analysis_handler(project_id, request, top_n=20)

    # Codebook analysis (async handler — call synchronously in this context)
    # The handler is async only because of optional LLM elaboration.
    # For export, we skip elaboration (elaborate=False) and call it in a
    # synchronous context.  FastAPI route handlers can call async functions
    # via asyncio.run() if needed, but get_codebook_analysis without
    # elaborate=True is effectively sync.
    import asyncio

    codebook_analysis = asyncio.run(
        _get_codebook_analysis_handler(project_id, request, top_n=20, elaborate=False)
    )

    # Transcripts — one embed key per session
    transcripts: dict[str, object] = {}
    for sess in dashboard.sessions:
        try:
            transcripts[sess.session_id] = _get_transcript_handler(
                request, project_id, sess.session_id
            )
        except HTTPException:
            logger.warning("Export: transcript not found for %s", sess.session_id)

    # Moderator questions — one embed key per quote that HAS a preceding
    # moderator utterance.  Absence (404) is legitimate, not a coverage gap.
    mod_db = request.app.state.db_factory()
    try:
        dom_ids = [
            _quote_dom_id(q)
            for q in mod_db.query(Quote).filter_by(project_id=project_id).all()
        ]
    finally:
        mod_db.close()
    moderator_questions: dict[str, Any] = {}
    for dom_id in dom_ids:
        try:
            moderator_questions[dom_id] = _get_moderator_question_handler(
                project_id, dom_id, request
            )
        except HTTPException:
            pass  # no preceding moderator segment — normal, skip

    # --- Assemble the path-keyed embed (keys = relative API paths the SPA calls) ---
    endpoints: dict[str, Any] = {
        "/info": jsonable_encoder(project_info),
        "/dashboard": jsonable_encoder(dashboard),
        "/sessions": jsonable_encoder(sessions),
        "/quotes": jsonable_encoder(quotes),
        "/codebook": jsonable_encoder(codebook),
        "/people": jsonable_encoder(people),
        "/video-map": None,
        "/analysis/sentiment": jsonable_encoder(sentiment),
        "/analysis/codebooks": jsonable_encoder(codebook_analysis),
        "/framework-states": jsonable_encoder(framework_states),
        "/hidden-tag-groups": jsonable_encoder(hidden_tag_groups),
    }
    for sid, tx in transcripts.items():
        endpoints[f"/transcripts/{sid}"] = jsonable_encoder(tx)
    for dom_id, mq in moderator_questions.items():
        endpoints[f"/quotes/{dom_id}/moderator-question"] = jsonable_encoder(mq)

    # --- Strip absolute filesystem paths (security: leaks username/dir structure) ---
    _strip_filesystem_paths(endpoints)

    # --- Anonymise if requested ---
    if anonymise:
        _anonymise_data(endpoints)

    export_data: dict[str, Any] = {
        "version": 2,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "health": build_health_payload(),
        "logos": _build_logo_data_uris(),
        "endpoints": endpoints,
    }

    # --- Read theme CSS ---
    project_dir: Path | None = getattr(request.app.state, "project_dir", None)
    theme_css = ""
    if project_dir:
        output_dir = project_dir / "bristlenose-output"
        if not output_dir.is_dir():
            output_dir = project_dir
        css_path = output_dir / "assets" / "bristlenose-theme.css"
        if css_path.is_file():
            theme_css = css_path.read_text(encoding="utf-8")
    if not theme_css.strip():
        # No per-project baked CSS — fall back to the bundled source so a
        # leave-behind is never shipped unstyled (parity with serve mode's
        # serve_theme_css_with_fallback).
        from bristlenose.stages.s12_render.theme_assets import load_default_css

        theme_css = load_default_css()

    # --- Build HTML ---
    html = _build_export_html(export_data, theme_css)

    # --- Filename ---
    project_name = project_info.project_name  # type: ignore[union-attr]
    slug = slugify(project_name) if project_name else "bristlenose"
    filename = f"{slug}-report.html"

    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
