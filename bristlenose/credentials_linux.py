"""Linux credential storage using Secret Service (GNOME Keyring / KDE Wallet).

Uses the `secret-tool` CLI (from libsecret-tools) to interact with the
Secret Service D-Bus API. Falls back to environment variables if Secret
Service is unavailable (headless servers, minimal installs).
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess

from bristlenose.credentials import CredentialStore, FileCredentialStore
from bristlenose.providers import credential_service_name

logger = logging.getLogger(__name__)

#: GLib's own log lines, `(secret-tool:1234): GLib-GIO-WARNING **: …`. A healthy
#: keyring can emit one on a lookup; it is not secret-tool saying it failed.
_GLIB_LOG_LINE_RE = re.compile(r"^\(.+:\d+\): \S+-(?:WARNING|CRITICAL|Message|INFO|DEBUG) \*\*")


class LinuxCredentialStore(CredentialStore):
    """Store credentials using secret-tool (libsecret).

    Credentials are stored with attributes:
    - application: "bristlenose"
    - key: provider name (e.g., "anthropic")
    - label: Human-readable description
    """

    def get(self, key: str) -> str | None:
        """Retrieve a credential from Secret Service."""
        try:
            result = subprocess.run(
                [
                    "secret-tool",
                    "lookup",
                    "application", "bristlenose",
                    "key", key,
                ],
                capture_output=True,
                text=True, encoding="utf-8",
                check=True,
            )
            value = result.stdout.strip()
            return value or None
        except subprocess.CalledProcessError:
            # Not found or Secret Service unavailable
            return None

    def set(self, key: str, value: str) -> None:
        """Store a credential in Secret Service.

        The secret is passed via stdin to avoid it appearing in process listings.
        """
        # Same name Keychain Access would show on a Mac — one table, `CREDENTIALS`.
        label = credential_service_name(key)
        subprocess.run(
            [
                "secret-tool",
                "store",
                "--label", label,
                "application", "bristlenose",
                "key", key,
            ],
            input=value,
            text=True, encoding="utf-8",
            check=True,
        )

    def delete(self, key: str) -> None:
        """Remove a credential from Secret Service.

        No-op if the credential doesn't exist.
        """
        subprocess.run(
            [
                "secret-tool",
                "clear",
                "application", "bristlenose",
                "key", key,
            ],
            check=False,  # Ignore errors if not found
        )


def _is_secret_service_available() -> bool:
    """Check if Secret Service is available and responding.

    Returns True if secret-tool is installed and can communicate with
    the Secret Service daemon.
    """
    # Check if secret-tool is installed
    if not shutil.which("secret-tool"):
        return False

    # Try a lookup to verify Secret Service is running. This fails quickly when
    # there is no daemon or no session bus (SSH, WSL, a headless box).
    try:
        probe = subprocess.run(
            ["secret-tool", "lookup", "application", "bristlenose-availability-check"],
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            timeout=2,
        )
        # The exit code alone cannot tell them apart: a healthy keyring exits 1
        # for a key that is not stored, and so does a missing session bus. Only
        # the second says anything (libsecret prints its own errors and nothing else;
        # GLib's `(prog:pid): … **:` log lines are not those), so a lookup that
        # exited non-zero with an error is a keyring that cannot be used, and the
        # config file is the store that works (N202).
        errors = [
            line for line in (probe.stderr or "").splitlines()
            if line.strip() and not _GLIB_LOG_LINE_RE.match(line)
        ]
        logger.info(
            "secret_tool_probe | returncode=%s | error=%r",
            probe.returncode, errors[0][:200] if errors else None,
        )
        return probe.returncode == 0 or not errors
    except subprocess.TimeoutExpired:
        # D-Bus hung — Secret Service not properly configured
        return False
    except FileNotFoundError:
        # secret-tool not found (shouldn't happen after which() check)
        return False


def get_linux_store() -> CredentialStore:
    """Get the appropriate Linux credential store.

    Returns LinuxCredentialStore if Secret Service is available,
    otherwise falls back to the persisting FileCredentialStore.
    """
    if _is_secret_service_available():
        return LinuxCredentialStore()

    # No Secret Service (headless server, minimal install) — persist to a file
    # so `configure` still leaves the user configured.
    return FileCredentialStore()
