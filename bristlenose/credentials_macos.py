"""macOS Keychain integration using the security CLI.

Uses the `security` command-line tool that ships with macOS to store and
retrieve credentials from the system Keychain. Entries appear in Keychain
Access.app with human-readable names.

**Sandbox note:** this module is the happy path for CLI Mac users (Homebrew,
pip). Inside the sandboxed desktop sidecar it is never reached in practice —
the Swift host fetches keys from Keychain at launch and injects them as
BRISTLENOSE_*_API_KEY env vars, which pydantic-settings reads before this
module's fallback runs. Exception handling is broadened (vs. raising out)
specifically so that if Swift injection is ever bypassed under sandbox, the
`/usr/bin/security` denial surfaces as the existing "No API key configured"
error rather than an unhandled traceback.
"""

from __future__ import annotations

import logging
import subprocess

from bristlenose.credentials import CredentialStore

logger = logging.getLogger(__name__)


class MacOSCredentialStore(CredentialStore):
    """Store credentials in macOS Keychain using the security CLI.

    Credentials are stored as generic passwords with:
    - Service: Human-readable name (e.g., "Bristlenose Anthropic API Key")
    - Account: "bristlenose" (identifies our app)
    - Password: The actual API key
    """

    ACCOUNT = "bristlenose"

    # Map internal key names to human-readable Keychain service names
    SERVICE_NAMES = {
        "anthropic": "Bristlenose Anthropic API Key",
        "openai": "Bristlenose OpenAI API Key",
        "azure": "Bristlenose Azure API Key",
        "google": "Bristlenose Google Gemini API Key",
        "miro": "Bristlenose Miro Access Token",
    }

    def _service_name(self, key: str) -> str:
        """Get the Keychain service name for a key."""
        return self.SERVICE_NAMES.get(key, f"Bristlenose {key.title()} API Key")

    def get(self, key: str) -> str | None:
        """Retrieve a credential from Keychain.

        If the Keychain is locked, macOS will prompt for the password via GUI.
        In headless environments without GUI, this will fail and return None.

        Exception handling is broadened for App Sandbox compatibility: if
        `/usr/bin/security` is not reachable (sandbox denial, SIP tampering,
        MDM policy blocking exec, a genuinely broken macOS install), surface
        as None rather than an unhandled traceback. The debug log preserves
        diagnostics for CLI users running with `-v`.
        """
        try:
            result = subprocess.run(
                [
                    "security",
                    "find-generic-password",
                    "-a", self.ACCOUNT,
                    "-s", self._service_name(key),
                    "-w",  # Output password only
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            PermissionError,
            OSError,
        ) as exc:
            # Key not found (exit code 44), Keychain locked/inaccessible, or
            # subprocess-exec blocked (sandbox, SIP, MDM). Fall through to
            # None so the caller's "no API key configured" error path runs.
            logger.debug("keychain read via security CLI failed for %s: %s", key, exc)
            return None

    def set(self, key: str, value: str) -> None:
        """Store a credential in Keychain.

        If an entry already exists, it is deleted first then re-added.
        The -U flag on add-generic-password should handle updates, but
        delete-then-add is more reliable across macOS versions.

        No-op if subprocess-exec is blocked (sandbox, SIP, MDM).
        """
        service = self._service_name(key)

        # Delete existing entry first (ignore errors if not found)
        try:
            subprocess.run(
                [
                    "security",
                    "delete-generic-password",
                    "-a", self.ACCOUNT,
                    "-s", service,
                ],
                capture_output=True,  # Suppress output
                check=False,  # Ignore "not found" errors
            )
        except (FileNotFoundError, PermissionError, OSError) as exc:
            logger.debug("keychain delete-before-set via security CLI failed for %s: %s", key, exc)
            return

        # Add new entry
        try:
            subprocess.run(
                [
                    "security",
                    "add-generic-password",
                    "-a", self.ACCOUNT,
                    "-s", service,
                    "-w", value,
                    "-U",  # Update if exists (belt and suspenders)
                ],
                check=True,
            )
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            PermissionError,
            OSError,
        ) as exc:
            logger.debug("keychain add via security CLI failed for %s: %s", key, exc)

    def delete(self, key: str) -> None:
        """Remove a credential from Keychain.

        No-op if the credential doesn't exist or subprocess-exec is blocked.
        """
        try:
            subprocess.run(
                [
                    "security",
                    "delete-generic-password",
                    "-a", self.ACCOUNT,
                    "-s", self._service_name(key),
                ],
                capture_output=True,
                check=False,  # Ignore "not found" errors
            )
        except (FileNotFoundError, PermissionError, OSError) as exc:
            logger.debug("keychain delete via security CLI failed for %s: %s", key, exc)
