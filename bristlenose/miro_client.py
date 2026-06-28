"""Miro REST API v2 client.

Thin synchronous httpx wrappers for OAuth and board/frame/sticky/text creation,
plus rate-limit backoff. Token stored in the system keychain via the credentials
module. Higher-level orchestration (IR -> Miro calls) lives in
`bristlenose.server.miro_export`.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
import urllib.parse

import httpx

BASE_URL = "https://api.miro.com/v2"
OAUTH_AUTHORIZE = "https://miro.com/oauth/authorize"
OAUTH_TOKEN = "https://api.miro.com/v1/oauth/token"
SCOPES = "boards:read boards:write"


class MiroError(RuntimeError):
    """A Miro API call failed (non-2xx after retries)."""


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
    none = {"user_name": None, "team_name": None, "org_name": None}
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
                             code_verifier: str) -> dict:
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
    return resp.json()


def refresh_access_token(client_id: str, refresh_token: str) -> dict:
    """Rotate an expiring access token using the refresh token."""
    resp = httpx.post(OAUTH_TOKEN, data={
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }, timeout=30)
    if resp.status_code != 200:
        raise MiroError(f"token refresh failed: {resp.status_code} {resp.text[:200]}")
    return resp.json()


# ---------------------------------------------------------------------------
# REST helpers + board/frame/sticky/text creation
# ---------------------------------------------------------------------------


def _request(method: str, token: str, path: str, json: dict | list | None = None,
             *, retries: int = 4) -> dict | list:
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
            raise MiroError(f"{method} {path} -> {resp.status_code} {resp.text[:300]}")
        if attempt < retries:
            time.sleep(delay)
            delay *= 2
    raise MiroError(f"{method} {path} failed after rate-limit retries")


def create_board(token: str, name: str, description: str = "") -> dict:
    """Create a board. Returns the board object (id, viewLink, ...)."""
    return _request("POST", token, "/boards", {"name": name[:60], "description": description[:300]})


def create_frame(token: str, board_id: str, title: str, x: float, y: float,
                 width: float, height: float) -> dict:
    """Create a named frame. Position is the frame CENTRE (Miro convention)."""
    return _request("POST", token, f"/boards/{board_id}/frames", {
        "data": {"title": title[:255], "format": "custom", "type": "freeform"},
        "position": {"x": x, "y": y},
        "geometry": {"width": width, "height": height},
    })


def bulk_create_items(token: str, board_id: str, items: list[dict]) -> list[dict]:
    """Create up to 20 mixed items in one call (POST .../items/bulk)."""
    if not items:
        return []
    if len(items) > 20:
        raise ValueError("bulk_create_items accepts at most 20 items per call")
    result = _request("POST", token, f"/boards/{board_id}/items/bulk", items)  # type: ignore[arg-type]
    return result.get("data", []) if isinstance(result, dict) else result


def create_text(token: str, board_id: str, content: str, x: float, y: float,
                width: float, font_size: int = 18) -> dict:
    """Create a free text item (real fontSize/colour, unlike a sticky)."""
    return _request("POST", token, f"/boards/{board_id}/texts", {
        "data": {"content": content},
        "position": {"x": x, "y": y},
        "geometry": {"width": width},
        "style": {"fontSize": str(font_size)},
    })
