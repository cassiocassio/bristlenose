# Keychain Integration

Secure credential storage for API keys using native system keychains.

---

## Goal

Store API keys in the macOS Keychain (and Linux Secret Service where available) instead of `.env` files. This is:

1. **More secure** — encrypted at rest, not plain text on disk
2. **More convenient** — one keychain entry works across all projects
3. **Expected by users** — Mac users expect credentials in Keychain Access

---

## Design Decisions

### 1. Native CLI, not shim libraries

**Decision:** Use `security` CLI on macOS, `secret-tool` CLI on Linux. No `keyring` Python library.

**Rationale:** Cross-platform shim libraries (like `keyring`) provide the lowest common denominator on every platform. They don't integrate well with native tooling — entries created by `keyring` often have weird names in Keychain Access, and the abstraction leaks when things go wrong.

Instead:
- **macOS:** Shell out to `security` CLI. It's been stable for 20+ years, ships with every Mac, and entries appear properly in Keychain Access.app
- **Linux:** Shell out to `secret-tool` CLI (part of `libsecret-tools`). If Secret Service isn't available (headless servers, minimal installs), fall back to env vars with a clear message

### 2. Credential naming

**Decision:** Human-readable service names with "API Key" suffix.

Examples:
- `Bristlenose Anthropic API Key`
- `Bristlenose OpenAI API Key`

**Rationale:** Users search their keychain for "anthropic" and should find something clearly labelled. Anthropic has other credentials (console password, etc.) — the "API Key" suffix disambiguates.

Keychain fields:
- **Service:** `Bristlenose Anthropic API Key` (what shows in Keychain Access)
- **Account:** `bristlenose` (identifies our app)
- **Password:** the actual API key

### 3. CLI interface

**Decision:** One provider at a time via `bristlenose configure <provider>`.

```bash
bristlenose configure anthropic
# Prompts for key, validates, stores in Keychain

bristlenose configure openai
# Same flow
```

**Not** a wizard that configures everything at once — that's rare and over-engineered.

### 4. No migration from `.env`

**Decision:** Don't offer to migrate existing `.env` keys to Keychain.

**Rationale:**
- Migration is a one-time event affecting few users (early adopters)
- Those users are technical enough to run `bristlenose configure anthropic` themselves
- Auto-migration risks confusing users ("where did my key go?")
- Simpler implementation

### 5. Credential lookup priority

**Decision:** Keychain first, then env var, then `.env` file.

```
1. Keychain (secure, user-managed)
2. Environment variable (explicit override, CI/CD)
3. .env file (legacy, less secure)
```

**Rationale:** Keychain is the preferred storage — check it first. Env vars are explicit overrides (useful in CI or when testing different keys). `.env` is the fallback for users who haven't migrated.

### 6. Validation before storing

**Decision:** Validate API keys with a cheap HTTP call before storing in Keychain.

**Rationale:** Easy to copy-paste a truncated key. Better to catch it immediately than have a confusing failure later during a pipeline run.

### 7. Snap confinement

**Decision:** Handle Snap later. For now, Snap users use env vars.

**Rationale:** Snap runs in a sandbox and may not have Keychain access. We'll figure out the right fallback (encrypted file in `$SNAP_USER_COMMON`?) when we get there. Don't let it block the macOS implementation.

---

## Module Structure

```
bristlenose/
├── credentials.py           # CredentialStore protocol + get_store()
├── credentials_macos.py     # MacOSCredentialStore (security CLI)
└── credentials_linux.py     # LinuxCredentialStore (secret-tool) + EnvFallback
```

### `credentials.py` — Protocol and factory

```python
"""Credential storage abstraction."""

from __future__ import annotations

import os
import sys
from abc import ABC, abstractmethod


class CredentialStore(ABC):
    """Abstract base for credential storage backends."""

    @abstractmethod
    def get(self, key: str) -> str | None:
        """Retrieve a credential. Returns None if not found."""
        ...

    @abstractmethod
    def set(self, key: str, value: str) -> None:
        """Store a credential."""
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove a credential. No-op if not found."""
        ...

    def exists(self, key: str) -> bool:
        """Check if a credential exists."""
        return self.get(key) is not None


class EnvCredentialStore(CredentialStore):
    """Fallback that reads from environment variables only."""

    ENV_VAR_MAP = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
    }

    def get(self, key: str) -> str | None:
        env_var = self.ENV_VAR_MAP.get(key)
        if not env_var:
            return None
        # Check both BRISTLENOSE_ prefixed and bare
        return os.environ.get(f"BRISTLENOSE_{env_var}") or os.environ.get(env_var) or None

    def set(self, key: str, value: str) -> None:
        # Can't persist to env — this is read-only
        raise NotImplementedError("Cannot store credentials in environment. Use Keychain or .env file.")

    def delete(self, key: str) -> None:
        raise NotImplementedError("Cannot delete credentials from environment.")


def get_credential_store() -> CredentialStore:
    """Get the appropriate credential store for this platform."""
    if sys.platform == "darwin":
        from bristlenose.credentials_macos import MacOSCredentialStore
        return MacOSCredentialStore()
    elif sys.platform.startswith("linux"):
        from bristlenose.credentials_linux import get_linux_store
        return get_linux_store()
    else:
        # Windows, etc. — env-only for now
        return EnvCredentialStore()
```

### `credentials_macos.py` — macOS Keychain via `security` CLI

```python
"""macOS Keychain integration using the security CLI."""

from __future__ import annotations

import subprocess

from bristlenose.credentials import CredentialStore


class MacOSCredentialStore(CredentialStore):
    """Store credentials in macOS Keychain using the security CLI."""

    ACCOUNT = "bristlenose"

    # Map internal key names to human-readable Keychain service names
    SERVICE_NAMES = {
        "anthropic": "Bristlenose Anthropic API Key",
        "openai": "Bristlenose OpenAI API Key",
    }

    def _service_name(self, key: str) -> str:
        """Get the Keychain service name for a key."""
        return self.SERVICE_NAMES.get(key, f"Bristlenose {key.title()} API Key")

    def get(self, key: str) -> str | None:
        """Retrieve a credential from Keychain."""
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
            # Key not found, or Keychain locked
            return None

    def set(self, key: str, value: str) -> None:
        """Store a credential in Keychain."""
        service = self._service_name(key)

        # Delete existing entry first (security add-generic-password fails if exists)
        # Using -U (update) flag instead would be cleaner but requires the old password
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
        """Remove a credential from Keychain."""
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
```

### `credentials_linux.py` — Linux Secret Service via `secret-tool`

```python
"""Linux credential storage using Secret Service (GNOME Keyring / KDE Wallet)."""

from __future__ import annotations

import shutil
import subprocess

from bristlenose.credentials import CredentialStore, EnvCredentialStore


class LinuxCredentialStore(CredentialStore):
    """Store credentials using secret-tool (libsecret)."""

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
            return result.stdout.strip() or None
        except subprocess.CalledProcessError:
            return None

    def set(self, key: str, value: str) -> None:
        """Store a credential in Secret Service."""
        subprocess.run(
            [
                "secret-tool",
                "store",
                "--label", f"Bristlenose {key.title()} API Key",
                "application", "bristlenose",
                "key", key,
            ],
            input=value,
            text=True,
            check=True,
        )

    def delete(self, key: str) -> None:
        """Remove a credential from Secret Service."""
        subprocess.run(
            [
                "secret-tool",
                "clear",
                "application", "bristlenose",
                "key", key,
            ],
            check=False,
        )


def get_linux_store() -> CredentialStore:
    """Get the appropriate Linux credential store."""
    # Check if secret-tool is available
    if shutil.which("secret-tool"):
        # Check if Secret Service is running (D-Bus query)
        try:
            subprocess.run(
                ["secret-tool", "lookup", "application", "bristlenose-test"],
                capture_output=True,
                timeout=2,
            )
            return LinuxCredentialStore()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # Fall back to environment variables
    return EnvCredentialStore()
```

---

## CLI Commands

### `bristlenose configure <provider>`

Interactive command to set up a provider's API key.

```
$ bristlenose configure anthropic

Enter your Claude API key: ········
Validating...
✓ API key is valid
✓ Stored in Keychain as "Bristlenose Anthropic API Key"

You can now run: bristlenose run ./interviews
```

If validation fails:

```
$ bristlenose configure anthropic

Enter your Claude API key: ········
Validating...
✗ Invalid API key — check you copied the full key

Enter your Claude API key:
```

If Keychain is unavailable (Linux without Secret Service):

```
$ bristlenose configure anthropic

Enter your Claude API key: ········
Validating...
✓ API key is valid

No system keychain available.
Add this to your .env file or shell profile:

  export ANTHROPIC_API_KEY=sk-ant-...

(The key is not stored anywhere — you'll need to save it yourself)
```

### Implementation

```python
# In cli.py

@app.command()
def configure(
    provider: Annotated[
        str,
        typer.Argument(help="Provider to configure: anthropic, openai"),
    ],
) -> None:
    """Set up API credentials for an LLM provider."""
    from bristlenose.credentials import get_credential_store
    from bristlenose.doctor import validate_api_key  # Reuse existing validation

    provider = provider.lower()
    if provider not in ("anthropic", "openai"):
        console.print(f"[red]Unknown provider: {provider}[/red]")
        console.print("Available: anthropic, openai")
        raise typer.Exit(1)

    # Prompt for key (masked input)
    display_name = "Claude" if provider == "anthropic" else "ChatGPT"
    key = typer.prompt(f"Enter your {display_name} API key", hide_input=True)

    if not key.strip():
        console.print("[red]No key entered[/red]")
        raise typer.Exit(1)

    # Validate
    console.print("Validating...", end=" ")
    is_valid, error = validate_api_key(provider, key.strip())

    if is_valid is False:
        console.print(f"[red]✗ {error}[/red]")
        raise typer.Exit(1)
    elif is_valid is None:
        console.print(f"[yellow]! Could not validate: {error}[/yellow]")
        console.print("Storing anyway...")
    else:
        console.print("[green]✓ API key is valid[/green]")

    # Store
    store = get_credential_store()
    try:
        store.set(provider, key.strip())
        service_name = f"Bristlenose {display_name} API Key"
        console.print(f'[green]✓ Stored in Keychain as "{service_name}"[/green]')
    except NotImplementedError:
        # EnvCredentialStore — can't persist
        console.print()
        console.print("[yellow]No system keychain available.[/yellow]")
        console.print("Add this to your .env file or shell profile:")
        console.print()
        env_var = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
        console.print(f"  export {env_var}={key.strip()}")
        console.print()
        console.print("[dim](The key is not stored anywhere — you'll need to save it yourself)[/dim]")

    console.print()
    console.print("You can now run: [bold]bristlenose run ./interviews[/bold]")
```

---

## Integration Points

### 1. Config loading (`config.py`)

Update `load_settings()` to check Keychain before env vars:

```python
def _resolve_api_key(provider: str, env_value: str) -> str:
    """Get API key from Keychain, env var, or .env file."""
    from bristlenose.credentials import get_credential_store

    # 1. Keychain
    store = get_credential_store()
    key = store.get(provider)
    if key:
        return key

    # 2. Env var / .env (already loaded into env_value by pydantic-settings)
    return env_value
```

### 2. Doctor command

Update the API key check to show source:

```
  API key        ok   Claude (Keychain)
  API key        ok   ChatGPT (env var)
```

Or with suggestion to upgrade:

```
  API key        !!   Claude (.env file — consider using Keychain)
                      Run: bristlenose configure anthropic
```

### 3. First-run prompt (existing Ollama flow)

When prompting for Claude/ChatGPT, direct users to `bristlenose configure`:

```
  [2] Claude API (best quality, ~$1.50/study)
      Run: bristlenose configure anthropic
```

---

## Testing

### Unit tests (`tests/test_credentials.py`)

```python
"""Tests for credential storage."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from bristlenose.credentials import EnvCredentialStore


class TestEnvCredentialStore:
    def test_get_with_prefix(self, monkeypatch):
        monkeypatch.setenv("BRISTLENOSE_ANTHROPIC_API_KEY", "test-key")
        store = EnvCredentialStore()
        assert store.get("anthropic") == "test-key"

    def test_get_without_prefix(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        store = EnvCredentialStore()
        assert store.get("anthropic") == "test-key"

    def test_get_prefers_prefix(self, monkeypatch):
        monkeypatch.setenv("BRISTLENOSE_ANTHROPIC_API_KEY", "prefixed")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "bare")
        store = EnvCredentialStore()
        assert store.get("anthropic") == "prefixed"

    def test_get_missing(self):
        store = EnvCredentialStore()
        assert store.get("anthropic") is None

    def test_set_raises(self):
        store = EnvCredentialStore()
        with pytest.raises(NotImplementedError):
            store.set("anthropic", "key")


class TestMacOSCredentialStore:
    @pytest.fixture
    def store(self):
        from bristlenose.credentials_macos import MacOSCredentialStore
        return MacOSCredentialStore()

    def test_get_calls_security(self, store):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="test-key\n", returncode=0)
            result = store.get("anthropic")

            assert result == "test-key"
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "security"
            assert "find-generic-password" in args
            assert "Bristlenose Anthropic API Key" in args

    def test_get_not_found(self, store):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(44, "security")
            result = store.get("anthropic")
            assert result is None

    def test_set_deletes_then_adds(self, store):
        with patch("subprocess.run") as mock_run:
            store.set("anthropic", "new-key")

            assert mock_run.call_count == 2
            # First call: delete
            assert "delete-generic-password" in mock_run.call_args_list[0][0][0]
            # Second call: add
            add_args = mock_run.call_args_list[1][0][0]
            assert "add-generic-password" in add_args
            assert "new-key" in add_args
```

### Integration test (macOS only, skipped in CI)

```python
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
class TestMacOSKeychainIntegration:
    """Real Keychain tests — run manually, not in CI."""

    def test_roundtrip(self):
        from bristlenose.credentials_macos import MacOSCredentialStore
        store = MacOSCredentialStore()
        test_key = "test-integration-key-12345"

        try:
            store.set("test-provider", test_key)
            assert store.get("test-provider") == test_key
        finally:
            store.delete("test-provider")
            assert store.get("test-provider") is None
```

---

## Edge Cases

### 1. Keychain locked

On macOS, if the Keychain is locked, `security find-generic-password` prompts for the user's password via a GUI dialog. This is fine — it's the expected macOS behaviour.

If running headless (SSH session without GUI), the command fails and we fall back to env vars.

### 2. Multiple keychains

macOS users may have multiple keychains. `security` uses the default keychain by default, which is correct for our use case.

### 3. Key rotation

Users can run `bristlenose configure anthropic` again to replace an existing key. The implementation deletes-then-adds, so this works.

### 4. Keychain sync (iCloud)

If the user's default keychain syncs via iCloud, the API key will sync across their Macs. This is probably fine — same user, same credentials. Document it as a "feature" (use across all your Macs).

---

## Not Doing

1. **`keyring` library** — adds a dependency, provides lowest-common-denominator UX
2. **Migration from `.env`** — rare, users can do it manually
3. **Windows Credential Manager** — out of scope for now (Windows isn't a target platform)
4. **Snap Keychain access** — handle later when we understand the sandbox constraints
5. **`bristlenose configure --list`** — not needed yet, `doctor` shows this info

---

## Files to Create/Modify

```
bristlenose/
├── credentials.py           # NEW: CredentialStore protocol, EnvCredentialStore, get_store()
├── credentials_macos.py     # NEW: MacOSCredentialStore
├── credentials_linux.py     # NEW: LinuxCredentialStore, get_linux_store()
├── config.py                # MODIFY: use credentials module in load_settings()
├── cli.py                   # MODIFY: add `configure` command
└── doctor.py                # MODIFY: show credential source in API key check

tests/
├── test_credentials.py      # NEW: unit tests for all stores
└── test_cli.py              # MODIFY: test `configure` command
```

---

## Implementation Order

1. **`credentials.py`** — protocol and env fallback
2. **`credentials_macos.py`** — macOS implementation
3. **`credentials_linux.py`** — Linux implementation with fallback detection
4. **`cli.py`** — add `configure` command
5. **`config.py`** — integrate with settings loading
6. **`doctor.py`** — show credential source
7. **Tests**

Estimated effort: ~4 hours
