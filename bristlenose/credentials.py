"""Credential storage abstraction.

Provides secure storage for API keys using native system keychains where available,
with fallback to environment variables.

Priority order:
1. System keychain (macOS Keychain, Linux Secret Service)
2. Environment variable (BRISTLENOSE_* prefix or bare)
3. .env file (loaded into environment by pydantic-settings)
"""

from __future__ import annotations

import os
import sys
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class CredentialStore(ABC):
    """Abstract base for credential storage backends."""

    @abstractmethod
    def get(self, key: str) -> str | None:
        """Retrieve a credential. Returns None if not found."""
        ...

    @abstractmethod
    def set(self, key: str, value: str) -> None:
        """Store a credential. Raises NotImplementedError if storage not supported."""
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove a credential. No-op if not found."""
        ...

    def exists(self, key: str) -> bool:
        """Check if a credential exists."""
        return self.get(key) is not None


class EnvCredentialStore(CredentialStore):
    """Fallback that reads from environment variables only.

    This is a read-only store — it can retrieve credentials from env vars
    but cannot persist new ones.
    """

    ENV_VAR_MAP = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "azure": "AZURE_API_KEY",
        "google": "GOOGLE_API_KEY",
        "miro": "MIRO_ACCESS_TOKEN",
    }

    def get(self, key: str) -> str | None:
        """Get credential from environment variable."""
        env_var = self.ENV_VAR_MAP.get(key)
        if not env_var:
            return None
        # Check both BRISTLENOSE_ prefixed and bare
        value = os.environ.get(f"BRISTLENOSE_{env_var}") or os.environ.get(env_var)
        return value or None

    def set(self, key: str, value: str) -> None:
        """Cannot persist to environment — this is read-only."""
        raise NotImplementedError(
            "Cannot store credentials in environment. Use system credential store or .env file."
        )

    def delete(self, key: str) -> None:
        """Cannot delete from environment."""
        raise NotImplementedError("Cannot delete credentials from environment.")


def get_credential_store() -> CredentialStore:
    """Get the appropriate credential store for this platform.

    Returns:
        MacOSCredentialStore on macOS
        LinuxCredentialStore on Linux (if Secret Service available)
        EnvCredentialStore as fallback
    """
    if sys.platform == "darwin":
        from bristlenose.credentials_macos import MacOSCredentialStore

        return MacOSCredentialStore()
    elif sys.platform.startswith("linux"):
        from bristlenose.credentials_linux import get_linux_store

        return get_linux_store()
    else:
        # Windows, etc. — env-only for now
        return EnvCredentialStore()


def get_credential(provider: str) -> str | None:
    """Get an API key, checking keychain first then environment.

    This is the main entry point for credential lookup. It checks:
    1. System keychain (if available)
    2. Environment variables (BRISTLENOSE_* prefix or bare)

    Args:
        provider: Provider name (anthropic, openai)

    Returns:
        API key string, or None if not found
    """
    # Try keychain first
    store = get_credential_store()
    key = store.get(provider)
    if key:
        return key

    # Fall back to environment
    env_store = EnvCredentialStore()
    return env_store.get(provider)


def get_credential_store_label() -> str:
    """Return a user-facing label for the current platform's credential store.

    macOS → "Keychain" (matches Keychain Access app)
    Linux → "Secret Service" (matches GNOME Keyring / KDE Wallet)
    Other → "environment" (env vars / .env fallback)
    """
    if sys.platform == "darwin":
        return "Keychain"
    if sys.platform.startswith("linux"):
        from bristlenose.credentials_linux import _is_secret_service_available

        if _is_secret_service_available():
            return "Secret Service"
        return "environment"
    return "environment"


def get_credential_source(provider: str) -> str | None:
    """Determine where a credential is stored.

    Returns:
        "keychain" if in system keychain
        "env" if in environment variable
        None if not found
    """
    # Check keychain
    store = get_credential_store()
    if store.get(provider):
        # Distinguish between keychain and env-only store
        if isinstance(store, EnvCredentialStore):
            return "env"
        return "keychain"

    # Check environment
    env_store = EnvCredentialStore()
    if env_store.get(provider):
        return "env"

    return None
