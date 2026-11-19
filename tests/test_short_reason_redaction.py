"""A stage warning printed to the terminal never carries a key.

``_short_reason`` prints the first error of a failed stage (speaker roles, quotes,
themes) after an em dash. Those errors are ``str(exc)`` of a provider error, and a
proxy or gateway that echoes the request's headers puts the key in that text.
Every other way provider text leaves Python is masked (``redact_keys``); this one
was not until 19 Nov 2026.
"""

from __future__ import annotations

from bristlenose.pipeline import _short_reason


def test_a_key_in_a_stage_error_is_masked() -> None:
    key = "sk-proj-" + "Zz9_" * 13
    msg, _ = _short_reason([f"Error code: 401 - echoed header api-key: {key}"])
    assert key not in msg
    assert "Zz9_Zz9_" not in msg


def test_the_message_is_otherwise_kept() -> None:
    msg, _ = _short_reason(["Error code: 429 - Rate limit is exceeded."])
    assert msg == "Error code: 429 - Rate limit is exceeded."
