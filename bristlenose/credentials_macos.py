"""macOS Keychain integration using the security CLI.

Uses the `security` command-line tool that ships with macOS to store and
retrieve credentials from the system Keychain. Entries appear in Keychain
Access.app with human-readable names.
"""

from __future__ import annotations

import subprocess

from bristlenose.credentials import CredentialStore


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
        except subprocess.CalledProcessError:
            # Key not found (exit code 44), or Keychain locked/inaccessible
            return None

    def set(self, key: str, value: str) -> None:
        """Store a credential in Keychain.

        If an entry already exists, it is deleted first then re-added.
        The -U flag on add-generic-password should handle updates, but
        delete-then-add is more reliable across macOS versions.
        """
        service = self._service_name(key)

        # Delete existing entry first (ignore errors if not found)
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

        # Add new entry
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

    def delete(self, key: str) -> None:
        """Remove a credential from Keychain.

        No-op if the credential doesn't exist.
        """
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
