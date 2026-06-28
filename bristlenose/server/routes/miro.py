"""Miro integration API endpoints — connection, token management, export."""

from __future__ import annotations

import logging
import os
import secrets

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from bristlenose import miro_client
from bristlenose.config import load_settings
from bristlenose.credentials import (
    get_credential,
    get_credential_source,
    get_credential_store,
)
from bristlenose.miro_client import validate_miro_token
from bristlenose.server import miro_export
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
    colour_by: str = "sentiment"
    clips_base: str = ""  # opt-in clip-link folder base URL


class MiroExportResponse(BaseModel):
    board_id: str
    board_url: str
    stickies: int


class MiroPreviewResponse(BaseModel):
    html: str


class MiroAuthUrlResponse(BaseModel):
    url: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_db(request: Request) -> Session:
    return request.app.state.db_factory()


def _check_project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


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

    # Store in credential store
    store = get_credential_store()
    try:
        store.set("miro", token)
    except NotImplementedError:
        # EnvCredentialStore — can't persist, but token is valid
        logger.warning("No system credential store available — token not persisted")

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
        "miro_token_trace event=connect_stored store=%s persisted_source=%s session_cache=set",
        type(store).__name__, get_credential_source("miro"),
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


def _project_name(project: Project) -> str:
    return getattr(project, "name", None) or getattr(project, "project_name", None) or "Research"


# ---------------------------------------------------------------------------
# POST /projects/{id}/miro/preview — creds-free SVG/HTML preview
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/miro/preview")
def miro_preview(project_id: int, body: MiroExportRequest, request: Request) -> MiroPreviewResponse:
    """Render exactly what would be pushed, without needing a Miro token."""
    db = _get_db(request)
    try:
        project = _check_project(db, project_id)
        name = body.board_name or _project_name(project)
        html = miro_export.build_preview_html(
            db, project_id, name, body.quote_ids,
            colour_by=body.colour_by, clips_base=body.clips_base,
        )
        return MiroPreviewResponse(html=html)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /projects/{id}/miro/export — push a new board
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/miro/export")
def miro_export_board(project_id: int, body: MiroExportRequest,
                      request: Request) -> MiroExportResponse:
    """Create a new Miro board from the project's (optionally scoped) quotes."""
    db = _get_db(request)
    try:
        project = _check_project(db, project_id)
        token = _miro_token(request)
        logger.info("miro_token_trace event=export persisted_source=%s", get_credential_source("miro"))
        if not token:
            raise HTTPException(status_code=400, detail="Not connected to Miro")
        name = body.board_name or _project_name(project)
        try:
            result = miro_export.push_to_miro(
                token, db, project_id, name, body.quote_ids,
                colour_by=body.colour_by, clips_base=body.clips_base,
            )
        except miro_client.MiroError as exc:
            raise HTTPException(status_code=502, detail=f"Miro export failed: {exc}") from exc
        return MiroExportResponse(**result)
    finally:
        db.close()


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
    try:
        store.set("miro", access)
        if tokens.get("refresh_token"):
            store.set("miro_refresh", tokens["refresh_token"])
    except NotImplementedError:
        logger.warning("No system credential store — Miro token not persisted")
    return HTMLResponse(
        "<h2>Connected to Miro ✓</h2><p>You can close this tab and return to "
        "Bristlenose.</p><script>setTimeout(function(){window.close()},800)</script>"
    )
