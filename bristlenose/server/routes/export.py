"""Export endpoint — self-contained HTML report download.

Gathers all API data, embeds it as JSON in a self-contained HTML file
with the React SPA bundle inlined, and returns it as a file download.
Recipients can open the HTML in any modern browser without Bristlenose.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from starlette.responses import Response

from bristlenose.i18n import SUPPORTED_LOCALES, locale_resources
from bristlenose.server.routes.health import build_health_payload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# Dedicated single-file export build (frontend/vite.export.config.ts) — one JS
# chunk + one CSS, inlined by _build_export_html so the artifact renders from
# file://.  Separate from the code-split serve build the SPA uses at runtime.
_EXPORT_STATIC_DIR = Path(__file__).resolve().parent.parent / "static-export"

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
        "/projects/{project_id}/agent-settings",  # MCP-surface switch; no agents offline
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
    (p*) full_name/short_name/role with empty strings.  Mutates ``endpoints``
    in place; keys are relative API paths (see export_report).

    The boundary is the *participant* line, not team membership: the ethics of
    anonymisation apply to research subjects, not to colleagues and
    collaborators, so a client-side observer is named and a participant is not
    (docs/design-people.md §E decision 2).  ``/sessions``' top-level
    ``moderator_names``/``observer_names`` are deliberately untouched for the
    same reason.
    """
    # People map
    people = endpoints.get("/people") or {}
    for code, info in people.items():
        if code.startswith("p"):
            info["full_name"] = ""
            info["short_name"] = ""
            # role is the LLM-extracted job title.  SECURITY.md names
            # job-title-plus-employer as the canonical indirect identifier and
            # design-export-html.md decided it is removed when anonymised; it
            # renders nowhere in the SPA, so it was invisible in the UI and
            # present in View Source.
            info["role"] = ""

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

    # Source filenames can carry participant names ("jane-doe.mov") — a recording
    # name re-carries the identity we just stripped from the speaker fields, so an
    # "anonymised" export would still name the participant in the Sessions view.
    # Neutralise to "<session_id><ext>" (keeps the media-type signal, drops name).
    def _neutralise_filename(sid: str, fn: str) -> str:
        if not sid:
            return ""
        ext = "." + fn.rsplit(".", 1)[1] if fn and "." in fn else ""
        return f"{sid}{ext}"

    for group in (sessions, dashboard):
        for sess in group.get("sessions", []):
            sid = sess.get("session_id", "")
            for sf in sess.get("source_files", []) or []:
                sf["filename"] = _neutralise_filename(sid, sf.get("filename", ""))
                if "path" in sf:
                    sf["path"] = sf["filename"]
            if "source_filename" in sess:
                sess["source_filename"] = _neutralise_filename(
                    sid, sess.get("source_filename", "")
                )

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

# The namespaces the web report actually renders from.  The SPA's own loader
# asks for exactly these three; `desktop`, `cli`, `doctor`, `preflight`,
# `server` and `pipeline` are unreachable from a browser report and used to
# ship anyway — 1,802 KB of a 3.38 MB export, including Czech text for a
# --whisper-model flag.  See docs/design-export-locale.md.
_EXPORT_NAMESPACES = ("common", "settings", "enums")


def _build_export_html(
    export_data: dict[str, Any],
    theme_css: str,
) -> str:
    """Build a self-contained HTML file with the SPA + data inlined.

    The SPA is a dedicated single-file build (``static-export/app.js`` +
    ``app.css`` — one module, no cross-chunk imports; see
    ``frontend/vite.export.config.ts``).  Everything is inlined into ONE HTML so
    the artifact renders when opened directly from disk (``file://``): the older
    code-split bundle loaded chunks via ``blob:`` URLs, which browsers block as
    module scripts from an opaque file:// origin, and data: URL modules can't
    resolve their own sub-imports.  One inline ``<script type="module">``
    sidesteps both — and also works when served.
    """
    app_js_path = _EXPORT_STATIC_DIR / "app.js"
    app_css_path = _EXPORT_STATIC_DIR / "app.css"
    # Both are single outputs of the same build — a missing app.css means the
    # build is incomplete, and shipping a styleless-but-200 artifact is worse
    # than failing loud (asymmetric with the app.js check would hide it).
    if not app_js_path.is_file() or not app_css_path.is_file():
        raise HTTPException(
            status_code=500,
            detail=(
                "Export build not found or incomplete — run the single-file export "
                "build (frontend/vite.export.config.ts) first"
            ),
        )
    app_js = app_js_path.read_text(encoding="utf-8")
    app_css = app_css_path.read_text(encoding="utf-8")

    # Inline <script> safety: a literal </script> in the bundle would close the
    # inline element early.
    app_js = app_js.replace("</script>", "<\\/script>")

    # Build the data injection script.
    #
    # SECURITY: the embedded data includes UNTRUSTED content (transcript text from
    # third-party files, participant/tag/project names). ensure_ascii escapes only
    # code points > 127 — '<' '>' '&' are ASCII and pass through UNCHANGED, so a
    # '</script>' inside any embedded string would break out of the data <script>
    # and inject arbitrary markup/JS into the shared leave-behind (stored XSS).
    # Escape the HTML-significant ASCII to their \uXXXX JSON forms — valid inside a
    # JSON string literal and inert inside <script>. (U+2028/U+2029, the JS line
    # separators, are already \u-escaped by ensure_ascii since they are > 127.)
    data_json = json.dumps(export_data, ensure_ascii=True, separators=(",", ":"))
    data_json = (
        data_json.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )

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
        # Theme CSS (tokens/atoms) + the SPA's own bundled CSS, both inlined.
        "<style>\n",
        theme_css,
        "\n</style>\n",
        "<style>\n",
        app_css,
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

    # The whole SPA as ONE inline module — no external or blob: module scripts,
    # so it loads from a file:// (opaque) origin.  Vite's single-file build has
    # already resolved every cross-chunk import into this one chunk.
    html_parts.append('<script type="module">\n')
    html_parts.append(app_js)
    html_parts.append("\n</script>\n")

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
    locale: str = Query(default=""),
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
        except HTTPException as exc:
            # 404 = legitimately no transcript for this session (skip it). Any
            # other status is a real failure — don't swallow it into a session
            # that's silently absent from the embed and RouteErrors when the
            # recipient clicks it offline.
            if exc.status_code != 404:
                raise
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
        # The researcher's UI language at export time — the SPA inits i18n from
        # this offline so the report reads in the language it was written in,
        # not the recipient's browser language.
        "locale": locale or None,
        # The chrome strings for that language and everything it falls back to,
        # embedded rather than bundled.  The export build no longer inlines any
        # locale JSON, so this is the only copy the offline report has — see
        # locale_resources() for why it is the whole chain and never the leaf.
        "localeResources": locale_resources(
            locale or "en", _EXPORT_NAMESPACES
        ),
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
    project_name = project_info.project_name
    slug = slugify(project_name) if project_name else "bristlenose"
    # The language is part of what this file IS now, not a rendering choice the
    # reader can undo, so it belongs in the name — otherwise a researcher
    # exporting fr/de/it for a Swiss client gets three identical filenames in
    # Downloads.  The locale token rather than the native language name because
    # the rest of this filename is a slug; "acme-research-report (Deutsch).html"
    # would be two naming conventions in one string.
    lang = locale if locale in SUPPORTED_LOCALES else "en"
    filename = f"{slug}-report-{lang}.html"

    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
