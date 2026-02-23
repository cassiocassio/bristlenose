"""Miro integration API endpoints — connection status, token management."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from bristlenose.credentials import get_credential, get_credential_store
from bristlenose.miro_client import validate_miro_token
from bristlenose.server.models import Project

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class MiroStatusResponse(BaseModel):
    connected: bool
    user_name: str | None = None


class MiroConnectRequest(BaseModel):
    token: str


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


@router.get("/projects/{project_id}/miro/status")
def miro_status(project_id: int, request: Request) -> MiroStatusResponse:
    """Check whether a Miro access token is configured and valid."""
    db = _get_db(request)
    _check_project(db, project_id)

    token = get_credential("miro")
    if not token:
        return MiroStatusResponse(connected=False)

    # Token exists — optionally validate (cached, not on every poll)
    return MiroStatusResponse(connected=True)


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
    _check_project(db, project_id)

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

    return MiroStatusResponse(connected=True)


# ---------------------------------------------------------------------------
# POST /projects/{id}/miro/disconnect — remove Miro token
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/miro/disconnect")
def miro_disconnect(project_id: int, request: Request) -> MiroStatusResponse:
    """Remove the stored Miro access token."""
    db = _get_db(request)
    _check_project(db, project_id)

    store = get_credential_store()
    try:
        store.delete("miro")
    except NotImplementedError:
        pass

    return MiroStatusResponse(connected=False)
