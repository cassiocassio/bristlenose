"""Linux credential storage using Secret Service (GNOME Keyring / KDE Wallet).

Uses the `secret-tool` CLI (from libsecret-tools) to interact with the
Secret Service D-Bus API. Falls back to environment variables if Secret
Service is unavailable (headless servers, minimal installs).
"""

from __future__ import annotations

import shutil
import subprocess

from bristlenose.credentials import CredentialStore, EnvCredentialStore


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
                text=True,
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
        label = f"Bristlenose {key.title()} API Key"
        subprocess.run(
            [
                "secret-tool",
                "store",
                "--label", label,
                "application", "bristlenose",
                "key", key,
            ],
            input=value,
            text=True,
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

    # Try a lookup to verify Secret Service is running
    # This will fail quickly if the daemon isn't available
    try:
        subprocess.run(
            ["secret-tool", "lookup", "application", "bristlenose-availability-check"],
            capture_output=True,
            timeout=2,
        )
        # Exit code doesn't matter — if it ran without timeout, Secret Service is there
        return True
    except subprocess.TimeoutExpired:
        # D-Bus hung — Secret Service not properly configured
        return False
    except FileNotFoundError:
        # secret-tool not found (shouldn't happen after which() check)
        return False


def get_linux_store() -> CredentialStore:
    """Get the appropriate Linux credential store.

    Returns LinuxCredentialStore if Secret Service is available,
    otherwise falls back to EnvCredentialStore.
    """
    if _is_secret_service_available():
        return LinuxCredentialStore()

    # Fall back to environment variables
    return EnvCredentialStore()
