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
from pathlib import Path
from uuid import UUID


def machine_id() -> str | None:
    """Return an OS-backed identity, or None when it cannot be established."""
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
        if not name or len(name) > 256 or any(ord(c) < 32 or ord(c) == 127 for c in name):
            return None
        return name
    except (OSError, UnicodeError, subprocess.SubprocessError):
        return None
