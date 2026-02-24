"""Miro REST API v2 client.

Handles board creation, sticky notes, frames, tags, and rate limiting.
Uses httpx for async HTTP. Token stored in system keychain via credentials module.
"""

from __future__ import annotations

import httpx

BASE_URL = "https://api.miro.com/v2"


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
