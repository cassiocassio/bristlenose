"""Export endpoint — self-contained HTML report download.

Gathers all API data, embeds it as JSON in a self-contained HTML file
with the React SPA bundle inlined, and returns it as a file download.
Recipients can open the HTML in any modern browser without Bristlenose.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from starlette.responses import Response

from bristlenose.server.routes.health import build_health_payload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


# ---------------------------------------------------------------------------
# Anonymisation
# ---------------------------------------------------------------------------

def _anonymise_data(data: dict) -> dict:
    """Strip participant names from all embedded data (shallow anonymisation).

    Keeps moderator (m*) and observer (o*) names.  Replaces participant
    (p*) full_name/short_name with empty strings.
    """
    # People map
    people = data.get("people") or {}
    for code, info in people.items():
        if code.startswith("p"):
            info["full_name"] = ""
            info["short_name"] = ""

    # Dashboard sessions — speaker names
    dashboard = data.get("dashboard") or {}
    for sess in dashboard.get("sessions", []):
        for spk in sess.get("speakers", []):
            if spk.get("speaker_code", "").startswith("p"):
                spk["name"] = ""

    # Dashboard featured quotes
    for fq in dashboard.get("featured_quotes", []):
        if fq.get("participant_id", "").startswith("p"):
            fq["speaker_name"] = ""

    # Sessions list — speakers
    sessions = data.get("sessions") or {}
    for sess in sessions.get("sessions", []):
        for spk in sess.get("speakers", []):
            if spk.get("speaker_code", "").startswith("p"):
                spk["name"] = ""

    # Quotes — speaker names in sections and themes
    quotes = data.get("quotes") or {}
    for group_key in ("sections", "themes"):
        for group in quotes.get(group_key, []):
            for q in group.get("quotes", []):
                if q.get("participant_id", "").startswith("p"):
                    q["speaker_name"] = ""

    # Transcripts — speaker names
    transcripts = data.get("transcripts") or {}
    for _sid, tx in transcripts.items():
        for spk in tx.get("speakers", []):
            if spk.get("code", "").startswith("p"):
                spk["name"] = ""

    # Project info
    # (project_name, session_count, participant_count are fine — no PII)

    return data


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
    data_json = json.dumps(export_data, ensure_ascii=False, separators=(",", ":"))

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
    from bristlenose.server.routes.data import get_people as _get_people_handler
    from bristlenose.server.routes.quotes import get_quotes as _get_quotes_handler
    from bristlenose.server.routes.sessions import get_sessions as _get_sessions_handler
    from bristlenose.server.routes.transcript import (
        get_transcript as _get_transcript_handler,
    )
    from bristlenose.utils.text import slugify

    # --- Gather data by calling existing route handlers ---
    # Each handler manages its own DB session (opens + closes).

    project_info = _get_project_info_handler(project_id, request)
    dashboard = _get_dashboard_handler(project_id, request)
    quotes = _get_quotes_handler(project_id, request)
    codebook = _get_codebook_handler(project_id, request)
    people = _get_people_handler(project_id, request)

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

    # Transcripts — one per session
    transcripts: dict[str, object] = {}
    for sess in dashboard.sessions:
        try:
            tx = _get_transcript_handler(request, project_id, sess.session_id)
            transcripts[sess.session_id] = tx
        except HTTPException:
            logger.warning("Export: transcript not found for %s", sess.session_id)

    # --- Serialize to dicts ---
    def _to_dict(obj: object) -> object:
        """Convert Pydantic model or plain dict to serializable dict.

        Uses ``by_alias=True`` so camelCase alias generators are respected —
        the embedded JSON must match the shape that FastAPI would return over
        HTTP, which is what the React frontend expects.
        """
        if hasattr(obj, "model_dump"):
            return obj.model_dump(by_alias=True)  # type: ignore[union-attr]
        if isinstance(obj, dict):
            return {k: _to_dict(v) for k, v in obj.items()}
        return obj

    export_data: dict = {
        "version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "project": _to_dict(project_info),
        "health": build_health_payload(),
        "dashboard": _to_dict(dashboard),
        "sessions": _to_dict(sessions),
        "quotes": _to_dict(quotes),
        "codebook": _to_dict(codebook),
        "analysis": {
            "sentiment": _to_dict(sentiment),
            "codebooks": _to_dict(codebook_analysis),
        },
        "transcripts": {
            sid: _to_dict(tx) for sid, tx in transcripts.items()
        },
        "people": _to_dict(people),
        "videoMap": None,
    }

    # --- Anonymise if requested ---
    if anonymise:
        export_data = _anonymise_data(export_data)

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
