"""Credential storage abstraction.

Provides secure storage for API keys using native system keychains where available,
with a persisting file fallback so `bristlenose configure` always leaves the user
configured — even on a headless box with no keyring.

Two readers, two orders — name which you mean:

- The settings pipeline (``config._populate_keys_from_keychain``) fills a field
  only if env/.env left it empty: environment variable → .env file → store.
  The sandboxed desktop depends on that order — the Swift host injects
  ``BRISTLENOSE_*_API_KEY`` and it must win.
- ``get_credential()`` below, used by the Miro route, is the reverse: store
  first, then environment.

Stores: macOS login Keychain, Linux Secret Service, or a 0600 user-level
config .env (~/.config/bristlenose/.env, also loaded by pydantic-settings via
``config._find_env_files()``). Credential names come from one table,
``bristlenose.providers.CREDENTIALS``.
"""

from __future__ import annotations

import logging
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path

from bristlenose.providers import CREDENTIALS

logger = logging.getLogger(__name__)


def user_config_dir() -> Path:
    """Directory for Bristlenose's user-level config (the fallback key file lives here).

    Honours ``$SNAP_USER_COMMON`` (the snap's writable, backup-surviving area) and
    ``$XDG_CONFIG_HOME``; otherwise ``~/.config/bristlenose``. Mirrors the
    doctor-sentinel directory logic in ``cli.py`` so both land in the same place.
    """
    snap_common = os.environ.get("SNAP_USER_COMMON")
    if snap_common:
        return Path(snap_common)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "bristlenose"
    return Path.home() / ".config" / "bristlenose"


def user_config_env_path() -> Path:
    """Path to the user-level ``.env`` where the file fallback persists keys."""
    return user_config_dir() / ".env"


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


def set_verified(store: CredentialStore, key: str, value: str) -> bool:
    """Store a credential and read it back. True only if it round-tripped.

    ``CredentialStore.set`` is not a promise. ``MacOSCredentialStore.set``
    swallows every subprocess failure *by design* — under App Sandbox
    ``/usr/bin/security`` is not reachable, so the write is a silent no-op and
    a clean return says only that nothing raised, never that anything was
    written. The Swift side has the same shape one layer over:
    ``KeychainHelper.serviceNames`` is an allowlist, and an unregistered key
    writes false and reads nil, which is how ``CloudGrantStore`` shipped
    persisting nothing at all with no error anywhere. Verify, don't assume.

    A read-back returning a *different* value counts as failure too: an
    environment variable shadows both the file and keychain reads, so the value
    just stored is then not the value that will be used.

    ``NotImplementedError`` from a store that cannot write at all (a bare
    :class:`EnvCredentialStore`) propagates: that is a different condition from
    a write that did not land, and callers say different things about it.
    """
    store.set(key, value)
    try:
        stored = store.get(key)
    except Exception:  # a store that cannot answer cannot prove anything
        stored = None
    if stored != value:
        logger.warning(
            "%s did not round-trip the credential store (%s) — not persisted",
            key, type(store).__name__,
        )
        return False
    return True


class EnvCredentialStore(CredentialStore):
    """Fallback that reads from environment variables only.

    This is a read-only store — it can retrieve credentials from env vars
    but cannot persist new ones.
    """

    # Derived, never listed here: `bristlenose/providers.py` `CREDENTIALS` is
    # the one table of credential names.
    ENV_VAR_MAP = {key: spec.env_var for key, spec in CREDENTIALS.items()}

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


class FileCredentialStore(EnvCredentialStore):
    """Persisting fallback backed by a user-level ``.env`` file.

    Used when no system keyring is available (headless Linux without Secret
    Service, Windows, etc.). Unlike :class:`EnvCredentialStore` it can *write*, so
    ``bristlenose configure`` actually leaves the user configured instead of
    printing an ``export …`` line and punting persistence back to the user.

    Read precedence matches the priority order in the module docstring: a real
    environment variable wins over the file. The file it writes
    (``BRISTLENOSE_ANTHROPIC_API_KEY=…`` lines) is the same one pydantic-settings
    loads via ``config._find_env_files()``, so a key stored here is picked up on
    the next run with no further action. Written with mode ``0o600`` — it holds
    secrets.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or user_config_env_path()

    def _var_name(self, key: str) -> str:
        """Full ``BRISTLENOSE_``-prefixed variable name for a provider key."""
        bare = self.ENV_VAR_MAP.get(key, key.upper())
        return f"BRISTLENOSE_{bare}"

    def get(self, key: str) -> str | None:
        """Environment variable first (bare or prefixed), then the config file."""
        value = super().get(key)
        if value:
            return value
        return self._read_file().get(self._var_name(key)) or None

    def set(self, key: str, value: str) -> None:
        """Upsert ``BRISTLENOSE_<KEY>=value`` in the config .env (mode 0o600)."""
        self._upsert(self._var_name(key), value)

    def delete(self, key: str) -> None:
        """Remove the key's line from the config .env. No-op if absent."""
        self._remove(self._var_name(key))

    def has_in_file(self, key: str) -> bool:
        """True when the key is persisted in the file itself (not just an env var)."""
        return self._var_name(key) in self._read_file()

    # -- .env file plumbing ------------------------------------------------

    @staticmethod
    def _parse_line(raw: str) -> tuple[str, str] | None:
        line = raw.strip()
        if not line or line.startswith("#"):
            return None
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            return None
        name, _, val = line.partition("=")
        name = name.strip()
        if not name:
            return None
        return name, val.strip().strip('"').strip("'")

    def _read_file(self) -> dict[str, str]:
        if not self.path.is_file():
            return {}
        result: dict[str, str] = {}
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            parsed = self._parse_line(raw)
            if parsed:
                result[parsed[0]] = parsed[1]
        return result

    def _write(self, lines: list[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(lines) + "\n" if lines else ""
        # O_CREAT|O_TRUNC with 0o600; chmod again in case the file pre-existed
        # with looser perms (umask only applies to newly-created files).
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.chmod(self.path, 0o600)

    def _upsert(self, var: str, value: str) -> None:
        existing = (
            self.path.read_text(encoding="utf-8").splitlines()
            if self.path.is_file()
            else []
        )
        out: list[str] = []
        replaced = False
        for raw in existing:
            parsed = self._parse_line(raw)
            if parsed and parsed[0] == var:
                out.append(f"{var}={value}")
                replaced = True
            else:
                out.append(raw)
        if not replaced:
            out.append(f"{var}={value}")
        self._write(out)

    def _remove(self, var: str) -> None:
        if not self.path.is_file():
            return
        out = [
            raw
            for raw in self.path.read_text(encoding="utf-8").splitlines()
            if not ((parsed := self._parse_line(raw)) and parsed[0] == var)
        ]
        self._write(out)


# -- User-level preferences (non-secret) -------------------------------------
#
# The same user-level ``.env`` that persists keys on no-keyring platforms also
# carries non-secret preferences — currently ``BRISTLENOSE_LLM_PROVIDER``, the
# "current provider" written by `bristlenose configure` and `bristlenose use`.
# pydantic-settings loads this file via ``config._find_env_files()`` (lowest
# priority), so a preference stored here is picked up on the next run with no
# further plumbing, and a real env var or project-local ``.env`` deliberately
# overrides it. Desktop-hosted processes never read it (`_find_env_files`
# returns nothing under hosting) — the GUI owns provider choice there.


def read_user_config_var(var: str) -> str | None:
    """Read a ``BRISTLENOSE_*`` variable from the user-level config .env only."""
    return FileCredentialStore()._read_file().get(var) or None


def write_user_config_var(var: str, value: str) -> None:
    """Upsert a ``BRISTLENOSE_*`` variable in the user-level config .env."""
    FileCredentialStore()._upsert(var, value)


def get_credential_store() -> CredentialStore:
    """Get the appropriate credential store for this platform.

    Returns:
        MacOSCredentialStore on macOS
        LinuxCredentialStore on Linux (if Secret Service available)
        FileCredentialStore as the persisting fallback (no keyring)
    """
    if sys.platform == "darwin":
        from bristlenose.credentials_macos import MacOSCredentialStore

        return MacOSCredentialStore()
    elif sys.platform.startswith("linux"):
        from bristlenose.credentials_linux import get_linux_store

        return get_linux_store()
    else:
        # Windows, etc. — no native keyring wired yet; persist to the config file.
        return FileCredentialStore()


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
    Other → "config file" (persisting .env fallback)
    """
    if sys.platform == "darwin":
        return "Keychain"
    if sys.platform.startswith("linux"):
        from bristlenose.credentials_linux import _is_secret_service_available

        if _is_secret_service_available():
            return "Secret Service"
        return "config file"
    return "config file"


def get_credential_source(provider: str) -> str | None:
    """Determine where a credential is stored.

    Returns:
        "keychain" if in system keychain
        "file" if in the user-level config .env
        "env" if in an environment variable
        None if not found
    """
    store = get_credential_store()
    if store.get(provider):
        # An env var always wins the read, so report it as "env" first.
        if EnvCredentialStore().get(provider):
            return "env"
        if isinstance(store, FileCredentialStore):
            return "file"
        if isinstance(store, EnvCredentialStore):
            return "env"
        return "keychain"

    return None
