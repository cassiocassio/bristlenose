"""Miro integration API endpoints — connection, token management, export."""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
from collections.abc import Callable
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from bristlenose import miro_client
from bristlenose.board_progress import BoardCancelledError, BoardProgress, default_history_dir
from bristlenose.config import load_settings
from bristlenose.credentials import (
    CredentialStore,
    get_credential,
    get_credential_source,
    get_credential_store,
    set_verified,
)
from bristlenose.miro_client import validate_miro_token
from bristlenose.server import miro_export
from bristlenose.server.export_core import project_display_name
from bristlenose.server.models import Project

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# OAuth in-flight state (in-memory; a local single-process server). Lost on
# restart, which only aborts an in-progress connect — acceptable. Maps
# state token -> (pkce_verifier, project_id).
_OAUTH_STATES: dict[str, tuple[str, int]] = {}


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class MiroStatusResponse(BaseModel):
    connected: bool
    user_name: str | None = None
    team_name: str | None = None  # the workspace new boards are created in
    org_name: str | None = None  # company/organization (Enterprise only)


class MiroConnectRequest(BaseModel):
    token: str


class MiroExportRequest(BaseModel):
    board_name: str | None = None
    quote_ids: list[str] | None = None  # scope; None = all non-hidden
    colour_by: str = "none"
    clips_base: str = ""  # opt-in clip-link folder base URL
    # The board is a deliverable, so its chrome follows the caller's UI
    # language. Unknown or absent falls back to English inside `t_in`, which is
    # what every caller sent until 22 Sep 2026.
    locale: str = "en"
    #: Break a long quote into up to three stickies at sentence ends, grouped (on by default; the
    #: panel's checkbox says so, so the researcher arriving at the board knows why).
    split_long_quotes: bool = True
    #: Rectangle by default on Miro (dense, a quote in longer lines); the dialog offers square.
    sticky_shape: Literal["rectangle", "square"] = "rectangle"


class MiroExportResponse(BaseModel):
    board_id: str
    board_url: str
    stickies: int


class MiroPreviewResponse(BaseModel):
    html: str


class BoardBuild(BaseModel):
    """How far a board build has got (`BoardProgress.snapshot`), shared by both Miro boards.

    ``phase`` says what the line counts: ``preparing`` (screengrabs, no call yet), ``opening``
    (the board and its first frames — no fraction or estimate claimed), then ``quotes``,
    ``groups`` or ``screens``. ``fraction`` is the share of all the board's calls made;
    ``eta_seconds`` is None until every kind of call still to come has an earned rate, from this
    build or kept from earlier ones."""

    phase: str
    done: int
    total: int
    count_done: int
    count_total: int
    waiting: bool
    fraction: float | None
    eta_seconds: float | None


class MiroBoardStart(BaseModel):
    status: str  # "started"


class MiroBoardStatus(BaseModel):
    status: str  # idle | running | completed | failed | cancelled
    board_url: str | None
    stickies: int
    reason: str | None
    vars: dict[str, str]
    build: BoardBuild | None


class MiroAuthUrlResponse(BaseModel):
    url: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_db(request: Request) -> Session:
    db: Session = request.app.state.db_factory()
    return db


def _check_project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _store_token_verified(store: CredentialStore, key: str, value: str) -> bool:
    """Store a credential and read it back — ``credentials.set_verified``.

    The one thing this route adds: a store that cannot write at all (a bare
    ``EnvCredentialStore``) is reported as not persisted rather than raised,
    because the route has an in-session fallback either way and the page says
    which of the two happened.
    """
    try:
        return set_verified(store, key, value)
    except NotImplementedError:
        logger.warning("No writable credential store — %s not persisted", key)
        return False


# ---------------------------------------------------------------------------
# GET /projects/{id}/miro/status — check if Miro token is configured
# ---------------------------------------------------------------------------


def _miro_token(request: Request) -> str | None:
    """The active Miro token.

    Persisted store first (Keychain on CLI Mac; on the sandboxed desktop the
    Swift host writes Keychain via the `store-miro-token` bridge message and
    injects it as `BRISTLENOSE_MIRO_ACCESS_TOKEN` on the NEXT sidecar launch,
    read here via env). Falls back to the in-session cache that `connect` sets,
    which covers the very first paste under App Sandbox — before that env-injected
    token exists. See docs/design-miro-bridge.md "macOS native entry".
    """
    return get_credential("miro") or getattr(request.app.state, "miro_session_token", None)


@router.get("/projects/{project_id}/miro/status")
def miro_status(project_id: int, request: Request) -> MiroStatusResponse:
    """Check whether a Miro access token is configured and valid."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        token = _miro_token(request)
        logger.info("miro_token_trace event=status persisted_source=%s", get_credential_source("miro"))
        if not token:
            return MiroStatusResponse(connected=False)
        # Identity (account holder + destination team) — cached on app.state so
        # status stays cheap. Cold (env-injected token after restart, never
        # connected this session) fetches once. Best-effort: nil on any failure.
        account = getattr(request.app.state, "miro_account", None)
        if account is None:
            account = miro_client.get_token_info(token)
            request.app.state.miro_account = account
        return MiroStatusResponse(
            connected=True,
            user_name=account.get("user_name"),
            team_name=account.get("team_name"),
            org_name=account.get("org_name"),
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /projects/{id}/miro/connect — store and validate a Miro token
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/miro/connect")
def miro_connect(
    project_id: int,
    body: MiroConnectRequest,
    request: Request,
) -> MiroStatusResponse:
    """Validate a Miro access token and store it in the system credential store."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)
    finally:
        db.close()

    token = body.token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="Token is required")

    # Validate against Miro API
    is_valid, error = validate_miro_token(token)

    if is_valid is False:
        raise HTTPException(status_code=401, detail=f"Invalid Miro token: {error}")
    if is_valid is None:
        raise HTTPException(
            status_code=502, detail=f"Could not validate Miro token: {error}"
        )

    # Store in credential store, and read back rather than trusting the write.
    store = get_credential_store()
    persisted = _store_token_verified(store, "miro", token)

    # In-session fallback: under App Sandbox the Python keychain write above is a
    # silent no-op, and the durable token (Swift writes Keychain via the
    # `store-miro-token` bridge message) is only env-injected on the NEXT sidecar
    # launch. Cache the validated token on app.state so THIS session's
    # status/export work right after a fresh paste. Cleared on disconnect and
    # naturally gone on restart (the Keychain/env path takes over by then).
    request.app.state.miro_session_token = token

    # Fetch + cache the account/workspace identity so the sheet can show which
    # Miro account this token belongs to (and where boards will land). Cleared
    # on disconnect. Best-effort — never blocks a valid connect.
    account = miro_client.get_token_info(token)
    request.app.state.miro_account = account

    # token-trace (temporary): persisted_source reflects PERSISTENCE only
    # (keychain/env/none) — the in-session cache is separate. Source only; never
    # the token value. "keychain"/"env" = survives restart; "none" = relies on
    # the desktop Keychain (bridge) for cross-restart persistence.
    logger.info(
        "miro_token_trace event=connect_stored store=%s persisted_source=%s "
        "verified=%s session_cache=set",
        type(store).__name__, get_credential_source("miro"), persisted,
    )

    return MiroStatusResponse(
        connected=True,
        user_name=account.get("user_name"),
        team_name=account.get("team_name"),
        org_name=account.get("org_name"),
    )


# ---------------------------------------------------------------------------
# POST /projects/{id}/miro/disconnect — remove Miro token
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/miro/disconnect")
def miro_disconnect(project_id: int, request: Request) -> MiroStatusResponse:
    """Remove the stored Miro access token."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)
    finally:
        db.close()

    store = get_credential_store()
    try:
        store.delete("miro")
        store.delete("miro_refresh")
    except NotImplementedError:
        pass
    # Clear the in-session cache too, else status would still read "connected"
    # from memory after a disconnect. (The durable Keychain copy is removed
    # natively — disconnect from the panel does not reach Swift's KeychainHelper;
    # that's the parallel to LLM-key removal living in Settings. See design doc.)
    request.app.state.miro_session_token = None
    request.app.state.miro_account = None

    return MiroStatusResponse(connected=False)


# ---------------------------------------------------------------------------
# POST /projects/{id}/miro/preview — creds-free SVG/HTML preview
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/miro/preview")
def miro_preview(project_id: int, body: MiroExportRequest, request: Request) -> MiroPreviewResponse:
    """Render exactly what would be pushed, without needing a Miro token."""
    db = _get_db(request)
    try:
        project = _check_project(db, project_id)
        name = (body.board_name or "").strip() or project_display_name(project)
        html = miro_export.build_preview_html(
            db, project_id, name, body.quote_ids,
            colour_by=body.colour_by, clips_base=body.clips_base, locale=body.locale,
            split=body.split_long_quotes, shape=body.sticky_shape,
        )
        return MiroPreviewResponse(html=html)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /projects/{id}/miro/export — push a new board
# ---------------------------------------------------------------------------


# `response_model` explicitly, because the annotation below has to admit the
# JSONResponse the 502 path returns and FastAPI would otherwise infer the
# schema from the union (or refuse to). The documented shape is unchanged.
@router.post("/projects/{project_id}/miro/export", response_model=MiroExportResponse)
def miro_export_board(project_id: int, body: MiroExportRequest,
                      request: Request) -> MiroExportResponse | JSONResponse:
    """Create a new Miro board from the project's (optionally scoped) quotes."""
    db = _get_db(request)
    try:
        project = _check_project(db, project_id)
        token = _miro_token(request)
        logger.info("miro_token_trace event=export persisted_source=%s", get_credential_source("miro"))
        if not token:
            raise HTTPException(status_code=400, detail="Not connected to Miro")
        name = (body.board_name or "").strip() or project_display_name(project)
        try:
            result = miro_export.push_to_miro(
                token, db, project_id, name, body.quote_ids,
                colour_by=body.colour_by, clips_base=body.clips_base, locale=body.locale,
                split=body.split_long_quotes, shape=body.sticky_shape,
            )
        except miro_client.MiroError as exc:
            # `detail` stays English and forensic — it is what a bug report
            # wants, and what an older client already reads.
            #
            # `reason` is the addition: a discriminator the clients localise,
            # because a client cannot pattern-match an English sentence and
            # every attempt to do so breaks the day somebody rewords it. The
            # name is deliberately the one the SPA already documents for this
            # job — `api.ts`: "Stable refusal code … Localise from this" —
            # rather than a parallel sibling that means the same thing.
            #
            # It is None for the six wire diagnostics (HTTP status plus Miro's
            # response text), which are correctly English: they go to a log,
            # not to a researcher, and the client falls back to `detail` there
            # exactly as before.
            logger.warning("Miro export failed: reason=%s %s", exc.reason, exc)
            return JSONResponse(
                status_code=502,
                content={
                    "detail": f"Miro export failed: {exc}",
                    "reason": exc.reason,
                    "vars": exc.vars,
                },
            )
        return MiroExportResponse(**result)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /projects/{id}/miro/board — the same push as a job, with progress and Stop
# ---------------------------------------------------------------------------

#: One build per project, in the screens board's shape (`routes/screens_export.py`). The task is
#: held here, so the loop's weak reference cannot let it be collected mid-build.
_board_jobs: dict[int, dict[str, Any]] = {}


def build_snapshot(job: dict[str, Any]) -> BoardBuild | None:
    tracker = job.get("tracker")
    return BoardBuild(**tracker.snapshot()) if isinstance(tracker, BoardProgress) else None


def _run_board_sync(job: dict[str, Any], db_factory: Callable[[], Session], project_id: int,
                    name: str, token: str, body: MiroExportRequest) -> None:
    db = db_factory()
    try:
        result = miro_export.push_to_miro(
            token, db, project_id, name, body.quote_ids,
            colour_by=body.colour_by, clips_base=body.clips_base, locale=body.locale,
            split=body.split_long_quotes, shape=body.sticky_shape, progress=job["tracker"],
            cancelled=lambda: job["status"] == "cancelled",
            on_board=lambda url: job.__setitem__("board_url", url),
        )
        job["stickies"] = result["stickies"]
        job["board_url"] = result["board_url"]
    finally:
        db.close()


async def _run_board(job: dict[str, Any], *args: Any) -> None:
    try:
        await asyncio.to_thread(_run_board_sync, job, *args)
        # The push returned whole: a Stop that arrived during its last call was too late, and
        # the board is finished — say so, with its link, rather than "cancelled".
        job["status"] = "completed"
    except BoardCancelledError:
        pass  # the status already says cancelled; the board keeps what it has
    except miro_client.MiroError as exc:
        logger.warning("Miro board failed: reason=%s %s", exc.reason, exc)
        if job["status"] != "cancelled":  # a cancel stays a cancel, whatever the call in hand did
            job["status"] = "failed"
            # Miro refusing the token has no reason of its own at the raise (a wire diagnostic);
            # the clients have a sentence for it, so it is named here rather than shown as
            # "check your connection".
            job["reason"] = exc.reason or ("token_rejected" if exc.status in (401, 403) else None)
            job["vars"] = dict(exc.vars)
    except Exception:
        logger.exception("Miro board failed")
        if job["status"] != "cancelled":
            job["status"] = "failed"
            job["reason"] = "board_incomplete" if job.get("board_url") else None
            job["vars"] = {"url": job["board_url"]} if job.get("board_url") else {}
    await asyncio.to_thread(job["tracker"].remember)


# `response_model` explicitly, for the same reason as `miro_export_board`: the annotation admits
# the JSONResponse the not-connected refusal returns.
@router.post("/projects/{project_id}/miro/board", response_model=MiroBoardStart)
async def start_miro_board(project_id: int, body: MiroExportRequest,
                           request: Request) -> MiroBoardStart | JSONResponse:
    """Build a new Miro board from the project's (optionally scoped) quotes, as a job.

    Read its progress at ``…/miro/board/status``; ``…/miro/board/cancel`` stops it after the call
    in hand. Failures carry the same ``reason`` and ``vars`` as ``POST …/miro/export``."""
    existing = _board_jobs.get(project_id)
    if existing and existing.get("status") == "running":
        raise HTTPException(status_code=409, detail="A Miro board is already being built")
    # A cancelled build finishes the call in hand, which can be a minute of Miro's retries; a
    # second build meanwhile would share the token's rate limit with it.
    task = existing.get("task") if existing else None
    if task is not None and not task.done():
        raise HTTPException(status_code=409, detail="The last Miro board is still stopping")
    db = _get_db(request)
    try:
        project = _check_project(db, project_id)
        name = (body.board_name or "").strip() or project_display_name(project)
    finally:
        db.close()
    token = _miro_token(request)
    if not token:
        # A reason beside the English `detail`, as the 502 above sends: both clients localise it
        # (R94), and an older one still reads `detail`.
        return JSONResponse(status_code=400, content={
            "detail": "Not connected to Miro", "reason": "not_connected", "vars": {}})
    job: dict[str, Any] = {"status": "running", "board_url": None, "stickies": 0, "reason": None,
                           "vars": {}, "tracker": BoardProgress("quotes", history_dir=default_history_dir())}
    _board_jobs[project_id] = job
    job["task"] = asyncio.create_task(
        _run_board(job, request.app.state.db_factory, project_id, name, token, body))
    return MiroBoardStart(status="started")


@router.get("/projects/{project_id}/miro/board/status")
async def miro_board_status(project_id: int) -> MiroBoardStatus:
    job = _board_jobs.get(project_id) or {}
    return MiroBoardStatus(
        status=job.get("status", "idle"), board_url=job.get("board_url"),
        stickies=job.get("stickies", 0), reason=job.get("reason"), vars=job.get("vars", {}),
        build=build_snapshot(job),
    )


@router.post("/projects/{project_id}/miro/board/cancel")
async def cancel_miro_board(project_id: int) -> dict[str, Any]:
    """Stop after the call in hand; a board already begun stays, with what it has."""
    job = _board_jobs.get(project_id)
    if job is None or job.get("status") != "running":
        raise HTTPException(status_code=404, detail="No Miro board being built")
    job["status"] = "cancelled"
    return {"cancelled": True}


# ---------------------------------------------------------------------------
# OAuth 2.0 + PKCE — the one-click Connect path (paste-token is the fallback)
# ---------------------------------------------------------------------------


def _client_id() -> str:
    return os.environ.get("MIRO_CLIENT_ID") or load_settings().miro_client_id


def _redirect_uri(request: Request) -> str:
    return f"{str(request.base_url).rstrip('/')}/api/miro/callback"


@router.get("/projects/{project_id}/miro/auth-url")
def miro_auth_url(project_id: int, request: Request) -> MiroAuthUrlResponse:
    """Return the Miro consent URL to open in the browser (PKCE)."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)
    finally:
        db.close()
    client_id = _client_id()
    if not client_id:
        raise HTTPException(
            status_code=400,
            detail="OAuth not configured (set MIRO_CLIENT_ID). Paste a token instead.",
        )
    verifier, challenge = miro_client.generate_pkce()
    state = secrets.token_urlsafe(24)
    _OAUTH_STATES[state] = (verifier, project_id)
    url = miro_client.build_authorize_url(client_id, _redirect_uri(request), state, challenge)
    return MiroAuthUrlResponse(url=url)


@router.get("/miro/callback")
def miro_callback(request: Request, code: str = "", state: str = "") -> HTMLResponse:
    """OAuth redirect target. Authenticates via the same-origin auth cookie."""
    entry = _OAUTH_STATES.pop(state, None)
    if not entry or not code:
        return HTMLResponse(
            "<h2>Miro connection failed</h2><p>Invalid or expired request. "
            "Close this tab and try again.</p>", status_code=400,
        )
    verifier, _pid = entry
    try:
        tokens = miro_client.exchange_code_for_tokens(
            _client_id(), code, _redirect_uri(request), verifier,
        )
    except miro_client.MiroError as exc:
        logger.warning("Miro OAuth token exchange failed: %s", exc)
        return HTMLResponse(
            "<h2>Miro connection failed</h2><p>Could not complete the connection. "
            "Close this tab and try again.</p>", status_code=502,
        )
    store = get_credential_store()
    access = tokens.get("access_token")
    if not access:
        # A malformed 200 (no access_token) would otherwise KeyError → 500.
        logger.warning("Miro token exchange returned no access_token")
        return HTMLResponse(
            "<h2>Miro connection failed</h2><p>Could not complete the connection. "
            "Close this tab and try again.</p>",
            status_code=502,
        )
    persisted = _store_token_verified(store, "miro", access)
    if tokens.get("refresh_token"):
        _store_token_verified(store, "miro_refresh", tokens["refresh_token"])

    # In-session fallback — `miro_connect` has had this since the sandbox work
    # and this path never did, which is the whole bug. A store that no-ops left
    # the token in NO store at all: this tab said "connected" while status,
    # export and Settings ▸ Accounts all said otherwise, with nothing anywhere
    # to explain the contradiction. Cache the identity too, for the same reason
    # `miro_connect` does — so the sheet can name the account.
    request.app.state.miro_session_token = access
    request.app.state.miro_account = miro_client.get_token_info(access)

    logger.info(
        "miro_token_trace event=callback_stored store=%s persisted_source=%s "
        "verified=%s session_cache=set",
        type(store).__name__, get_credential_source("miro"), persisted,
    )

    if persisted:
        return HTMLResponse(
            "<h2>Connected to Miro ✓</h2><p>You can close this tab and return to "
            "Bristlenose.</p><script>setTimeout(function(){window.close()},800)</script>"
        )

    # Not a 502: the token is valid and now cached, so this session genuinely is
    # connected and refusing it would discard a working connection. What must
    # not happen is the bare ✓, which claims a durable copy that does not exist.
    # Unlike the paste path there is no `store-miro-token` bridge to write the
    # Keychain natively — that message comes from the SPA and this page is a
    # browser tab — so on the sandboxed desktop the token dies with the sidecar
    # too. No auto-close: a page that shuts itself cannot be read.
    return HTMLResponse(
        "<h2>Connected to Miro — but not saved</h2><p>The connection works now. "
        "Bristlenose could not write to the system credential store, so you will "
        "have to connect again after restarting.</p><p>You can close this tab and "
        "return to Bristlenose.</p>"
    )
