"""Miro REST API v2 client.

Thin synchronous httpx wrappers for OAuth and board/frame/sticky/text creation,
plus rate-limit backoff. Token stored in the system keychain via the credentials
module. Higher-level orchestration (IR -> Miro calls) lives in
`bristlenose.server.miro_export`.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
import urllib.parse
from typing import Any

import httpx

BASE_URL = "https://api.miro.com/v2"
OAUTH_AUTHORIZE = "https://miro.com/oauth/authorize"
OAUTH_TOKEN = "https://api.miro.com/v1/oauth/token"
SCOPES = "boards:read boards:write"


class MiroError(RuntimeError):
    """A Miro API call failed (non-2xx after retries).

    `reason` is the discriminator a client can localise; the message stays
    English and forensic. Same shape as `Cause.reason` and `CloudFetchFailure`
    — a client cannot pattern-match an English sentence, and every attempt to
    do so is a bug waiting for the sentence to be reworded.

    `None` means a wire diagnostic (HTTP status plus response text) that is
    correctly English: it goes to a log, not to a researcher.
    """

    def __init__(self, message: str, *, reason: str | None = None,
                 vars: dict[str, str] | None = None, status: int | None = None) -> None:
        super().__init__(message)
        self.reason = reason
        self.vars = vars or {}
        #: Miro's HTTP status when it answered with one; None for a network failure.
        self.status = status


def validate_miro_token(token: str) -> tuple[bool | None, str | None]:
    """Validate a Miro access token by calling GET /v2/boards?limit=1.

    Returns:
        (True, None) if valid
        (False, error_message) if invalid
        (None, error_message) if network/other error
    """
    try:
        resp = httpx.get(
            f"{BASE_URL}/boards",
            params={"limit": "1"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            return True, None
        if resp.status_code == 401:
            return False, "invalid or expired token"
        if resp.status_code == 403:
            return False, "token lacks required scopes (needs boards:read)"
        return None, f"unexpected status {resp.status_code}"
    except httpx.HTTPError as exc:
        return None, f"network error: {exc}"


def get_token_info(token: str) -> dict[str, str | None]:
    """Fetch the account/workspace identity for a token (best-effort).

    Calls Miro's token-introspection endpoint GET /v1/oauth-token, which needs
    NO specific scope (so our boards:read+write token can call it). Returns the
    account holder's display name and the team (workspace) new boards land in —
    so the user can confirm WHICH of several Miro accounts they're about to
    create a board in. Identity is a safety nicety, never a gate: any failure
    returns {user_name: None, team_name: None} rather than raising.

    Response shape (relevant fields):
        {"user": {"name": "..."}, "team": {"id": "...", "name": "..."},
         "organization": {"id": "...", "name": "..."}, ...}

    `organization` is Enterprise-plan only — absent for personal/free accounts, so
    `org_name` is None there and the caller collapses to "user · team". For
    Enterprise it disambiguates a team within a company ("Design team · BigCorp").
    Parsed defensively; an unexpected shape just yields None, never raises.
    """
    none: dict[str, str | None] = {"user_name": None, "team_name": None, "org_name": None}
    try:
        resp = httpx.get(
            "https://api.miro.com/v1/oauth-token",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code != 200:
            return none
        data = resp.json()
        user = data.get("user") or data.get("createdBy") or {}
        team = data.get("team") or {}
        org = data.get("organization") or {}
        return {
            "user_name": user.get("name") or None,
            "team_name": team.get("name") or None,
            "org_name": org.get("name") or None,
        }
    except (httpx.HTTPError, ValueError):
        return none


# ---------------------------------------------------------------------------
# OAuth 2.0 + PKCE
# ---------------------------------------------------------------------------


def generate_pkce() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for an OAuth PKCE flow (S256)."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(40)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def build_authorize_url(client_id: str, redirect_uri: str, state: str,
                        code_challenge: str) -> str:
    """The Miro consent URL to open in the user's browser."""
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{OAUTH_AUTHORIZE}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(client_id: str, code: str, redirect_uri: str,
                             code_verifier: str) -> dict[str, Any]:
    """Exchange an authorization code for access + refresh tokens (PKCE — no secret)."""
    resp = httpx.post(OAUTH_TOKEN, data={
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }, timeout=30)
    if resp.status_code != 200:
        raise MiroError(f"token exchange failed: {resp.status_code} {resp.text[:200]}")
    # RFC 6749 §5.1: a 200 token response is a JSON object.
    tokens: dict[str, Any] = resp.json()
    return tokens


def refresh_access_token(client_id: str, refresh_token: str) -> dict[str, Any]:
    """Rotate an expiring access token using the refresh token."""
    resp = httpx.post(OAUTH_TOKEN, data={
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }, timeout=30)
    if resp.status_code != 200:
        raise MiroError(f"token refresh failed: {resp.status_code} {resp.text[:200]}")
    # RFC 6749 §5.1: a 200 token response is a JSON object.
    tokens: dict[str, Any] = resp.json()
    return tokens


# ---------------------------------------------------------------------------
# REST helpers + board/frame/sticky/text creation
# ---------------------------------------------------------------------------


def _request(method: str, token: str, path: str, json: dict[str, Any] | list[Any] | None = None,
             *, retries: int = 4) -> dict[str, Any] | list[Any]:
    """Call the Miro REST API with exponential backoff on 429 only.

    We retry ONLY on 429 (rate limit). Creation POSTs (board/frame/sticky) are
    not idempotent and have no idempotency key, so retrying a 5xx or a dropped
    response could create a duplicate board or batch. 5xx and network errors
    fail fast — the caller surfaces the error (and any partial board URL).
    """
    url = path if path.startswith("http") else f"{BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    delay = 1.0
    for attempt in range(retries + 1):
        try:
            resp = httpx.request(method, url, headers=headers, json=json, timeout=30)
        except httpx.HTTPError as exc:
            raise MiroError(f"{method} {path} network error: {exc}") from exc
        if resp.status_code < 300:
            return resp.json() if resp.content else {}
        if resp.status_code != 429:
            raise MiroError(f"{method} {path} -> {resp.status_code} {resp.text[:300]}",
                            status=resp.status_code)
        if attempt < retries:
            time.sleep(delay)
            delay *= 2
    raise MiroError(f"{method} {path} failed after rate-limit retries")


def _request_object(method: str, token: str, path: str,
                    json: dict[str, Any] | list[Any] | None = None) -> dict[str, Any]:
    """``_request`` for endpoints that answer with one object, not a list."""
    result = _request(method, token, path, json)
    if not isinstance(result, dict):
        raise MiroError(f"{method} {path} -> expected an object, got {type(result).__name__}")
    return result


def create_board(token: str, name: str, description: str = "") -> dict[str, Any]:
    """Create a board. Returns the board object (id, viewLink, ...)."""
    return _request_object("POST", token, "/boards", {"name": name[:60], "description": description[:300]})


#: How long to keep asking for a frame Miro answers 500 to (seconds between tries).
FRAME_RETRY_DELAYS = (5.0, 10.0, 15.0, 20.0, 30.0)


def create_frame(token: str, board_id: str, title: str, x: float, y: float,
                 width: float, height: float, *,
                 retry_delays: tuple[float, ...] = FRAME_RETRY_DELAYS) -> dict[str, Any]:
    """Create a named frame. Position is the frame CENTRE (Miro convention).

    Measured 17 Oct 2026: a board refuses frames with a bare 500 ("Internal error occurred") for
    about half a minute after it is created, and now and then later, while stickies and images go
    through. A refused frame was never found on the board afterwards. Even so, before each retry
    the board is searched for a frame with this title at this spot, so a 500 that did create one
    cannot produce two."""
    body = {"data": {"title": title[:255], "format": "custom", "type": "freeform"},
            "position": {"x": x, "y": y}, "geometry": {"width": width, "height": height}}
    for attempt in range(len(retry_delays) + 1):
        try:
            return _request_object("POST", token, f"/boards/{board_id}/frames", body)
        except MiroError as exc:
            if exc.status != 500 or attempt == len(retry_delays):
                raise
            time.sleep(retry_delays[attempt])
            found = _find_frame(token, board_id, title[:255], x, y)
            if found is not None:
                return found
    raise AssertionError("unreachable")


def _find_frame(token: str, board_id: str, title: str, x: float, y: float,
                retry_delays: tuple[float, ...] = (2.0, 5.0, 10.0)) -> dict[str, Any] | None:
    cursor: str | None = None
    while True:
        params = f"?type=frame&limit=50{f'&cursor={cursor}' if cursor else ''}"
        # The board that refuses a frame with a 500 can refuse this read the same way (measured
        # 17 Oct 2026: code 3.0016 on the items list straight after a refused frame). A read is safe
        # to repeat, so it is, before anything is decided from it.
        for attempt in range(len(retry_delays) + 1):
            try:
                page = _request("GET", token, f"/boards/{board_id}/items{params}")
                break
            except MiroError as exc:
                if exc.status is None or exc.status < 500 or attempt == len(retry_delays):
                    raise
                time.sleep(retry_delays[attempt])
        if not isinstance(page, dict):
            # Not knowing is not "absent": retrying the POST on a misread could make two.
            raise MiroError(f"GET /boards/{board_id}/items -> unexpected body")
        for item in page.get("data", []):
            pos = item.get("position") or {}
            if ((item.get("data") or {}).get("title") == title
                    and abs(float(pos.get("x", 1e9)) - x) < 1 and abs(float(pos.get("y", 1e9)) - y) < 1):
                return item
        cursor = page.get("cursor")
        if not cursor:
            return None


def bulk_create_items(token: str, board_id: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create up to 20 mixed items in one call (POST .../items/bulk)."""
    if not items:
        return []
    if len(items) > 20:
        raise ValueError("bulk_create_items accepts at most 20 items per call")
    result = _request("POST", token, f"/boards/{board_id}/items/bulk", items)
    return result.get("data", []) if isinstance(result, dict) else result


def upload_image(token: str, board_id: str, jpeg: bytes, filename: str, *, title: str,
                 x: float, y: float, width: float, parent_id: str | None = None,
                 retries: int = 4) -> dict[str, Any]:
    """Upload a JPEG as an image item (POST .../images, multipart).

    Measured 17 Oct 2026: the settings go in a ``data`` part sent as a plain form field with a JSON
    content type. Sent as an attached file (with a filename) Miro answers 500, "Failed to convert
    'data'". With ``parent_id`` the position is the image's centre from the frame's top-left, and
    the frame carries it when dragged. Miro keeps the aspect from ``width``. There is no lock: every
    lock field is refused (code 2.0703). Retries on 429 only, like ``_request``."""
    data: dict[str, Any] = {"title": title[:255], "position": {"x": x, "y": y},
                            "geometry": {"width": width}}
    if parent_id:
        data["parent"] = {"id": parent_id}
    path = f"/boards/{board_id}/images"
    delay = 1.0
    for attempt in range(retries + 1):
        try:
            resp = httpx.post(f"{BASE_URL}{path}", headers={"Authorization": f"Bearer {token}"},
                              files={"resource": (filename, jpeg, "image/jpeg"),
                                     "data": (None, json.dumps(data), "application/json")},
                              timeout=60)
        except httpx.HTTPError as exc:
            raise MiroError(f"POST {path} network error: {exc}") from exc
        if resp.status_code < 300:
            out = resp.json()
            if not isinstance(out, dict):
                raise MiroError(f"POST {path} -> expected an object")
            return out
        if resp.status_code != 429:
            raise MiroError(f"POST {path} -> {resp.status_code} {resp.text[:300]}", status=resp.status_code)
        if attempt < retries:
            time.sleep(delay)
            delay *= 2
    raise MiroError(f"POST {path} failed after rate-limit retries")


def create_group(token: str, board_id: str, item_ids: list[str]) -> dict[str, Any]:
    """Group items so they move as one (POST .../groups): the parts of one split quote.
    Measured 17 Oct 2026 on a sample board: six sets grouped, six answered 201."""
    return _request_object("POST", token, f"/boards/{board_id}/groups", {"data": {"items": item_ids}})


def create_text(token: str, board_id: str, content: str, x: float, y: float,
                width: float, font_size: int = 18) -> dict[str, Any]:
    """Create a free text item (real fontSize/colour, unlike a sticky)."""
    return _request_object("POST", token, f"/boards/{board_id}/texts", {
        "data": {"content": content},
        "position": {"x": x, "y": y},
        "geometry": {"width": width},
        "style": {"fontSize": str(font_size)},
    })
