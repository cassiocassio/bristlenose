"""Stable, opaque machine identity for conservative synced-folder recovery.

Never fall back to a hostname, PID, MAC address or study-local random ID.
Unavailable identity means ownership cannot be proved. The OS identifier is
hashed with an application namespace before it is written to a study.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from uuid import UUID

_cached: str | None = None


def machine_id() -> str | None:
    """Return an OS-backed identity, or None when it cannot be established.

    A good answer is kept for the life of the process, and a failure is retried
    once and never kept. The value is written into a run's marker for its whole
    life, so one slow ``ioreg`` under load must not leave the user's own live
    run marked as unverifiable.
    """
    global _cached
    if _cached is not None:
        return _cached
    for _ in range(2):
        value = _read_machine_id()
        if value is not None:
            _cached = value
            return value
    return None


def _read_machine_id() -> str | None:
    try:
        if sys.platform == "darwin":
            result = subprocess.run(
                ["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, encoding="utf-8", check=True, timeout=2,
            )
            match = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', result.stdout)
            if match is None:
                return None
            raw = UUID(match.group(1)).hex
        elif sys.platform.startswith("linux"):
            raw = Path("/etc/machine-id").read_text(encoding="ascii").strip().lower()
            if not re.fullmatch(r"[0-9a-f]{32}", raw):
                return None
        elif sys.platform == "win32":
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography",
                0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            ) as key:
                value, _ = winreg.QueryValueEx(key, "MachineGuid")
            if not isinstance(value, str):
                return None
            raw = UUID(value).hex
        else:
            return None
        if raw == "0" * 32:
            return None
        return hashlib.sha256(("bristlenose-machine-v1:" + raw).encode("ascii")).hexdigest()
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        return None


def has_unsafe_display_character(text: str) -> bool:
    """True for control and invisible format characters (bidi overrides, zero-width).

    A machine name read back from a synced file is shown in a refusal, so text
    that can reorder or hide what a person reads is refused, not displayed.
    """
    return any(unicodedata.category(c) in ("Cc", "Cf") for c in text)


def friendly_machine_name() -> str | None:
    """Apple's ComputerName for display only; never fall back to a DNS name."""
    if sys.platform != "darwin":
        return None
    try:
        result = subprocess.run(
            ["/usr/sbin/scutil", "--get", "ComputerName"],
            capture_output=True, text=True, encoding="utf-8", check=True, timeout=2,
        )
        name = result.stdout.strip()
        if not name or len(name) > 256 or has_unsafe_display_character(name):
            return None
        return name
    except (OSError, UnicodeError, subprocess.SubprocessError):
        return None
