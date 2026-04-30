---
status: partial
last-trued: 2026-04-30
trued-against: HEAD@first-run on 2026-04-30
---

> **Truing status:** Partial — the original design (§Design Decisions, §Module Structure, §CLI Commands) shipped and remains the canonical CLI/serve-mode credential path, with provider-list expansion (2→5). The Track C sandboxed-desktop deployment ships a different credential path (Swift reads Keychain, injects env vars; Python never touches Keychain) — documented in the new §"Desktop (sandboxed) credential path" section. Inline Python source (§Module Structure) is the pre-ship plan; see `bristlenose/credentials.py` + `credentials_macos.py` for current.

## Changelog

- _2026-04-29_ — confirmed still current after Beat 3 (desktop SwiftUI round-trip credential validation, `LLMValidator.swift`). Beat 3 added a new validation surface in Swift Settings that reads the Keychain key briefly to authenticate against the provider's API, but does NOT change the storage or injection architecture this doc describes — the Swift→env-var→Python flow on sidecar launch is unchanged. The verdict cache (UserDefaults: SHA-256 hash prefix + status + timestamp) is opaque metadata, not secret material; threat shape unchanged. See `design-desktop-settings.md` §"Validation flow (Beat 3)" for the validator details.
- _2026-04-21_ — trued up: expanded provider list from 2 (anthropic, openai) to 5 (anthropic, openai, azure, google, miro); updated `bristlenose configure` samples to use product names (`claude`, `chatgpt`); marked Snap section as shipped via env-var fallback; added new §"Desktop (sandboxed) credential path" for the Track C Swift→env-var→Python architecture (load-bearing invariant for alpha); added §"Secret-leak defences" covering runtime log redactor + `check-logging-hygiene.sh` CI gate. Anchors: `bristlenose/credentials.py:53-58`, `bristlenose/credentials_macos.py:42-44`, `bristlenose/cli.py:1613-1727`, `desktop/Bristlenose/Bristlenose/ServeManager.swift:183-197,356-383,409-473`, `desktop/Bristlenose/Bristlenose/KeychainHelper.swift`, `desktop/scripts/check-logging-hygiene.sh`, commits "inject keychain api keys as env vars", "runtime log redactor for api key shapes", "tests for env injection, redactor", "CI grep gate for Swift logging hygiene". Preserved: inlined Python source in §Module Structure as pre-ship plan record.

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

Examples (expanded from original 2 providers to 5 shipped):
- `Bristlenose Anthropic API Key`
- `Bristlenose OpenAI API Key`
- `Bristlenose Azure API Key`
- `Bristlenose Google API Key`
- ~~`Bristlenose Miro API Key`~~ (Miro board-bridge descoped from alpha — `KeychainHelper` and `ServeManager.overlayAPIKeys()` iterate only the four cloud providers `anthropic / openai / azure / google`. Re-add this row when Miro integration ships.)

See `bristlenose/credentials_macos.py:42-44` for the shipped service-name table.

**Rationale:** Users search their keychain for "anthropic" and should find something clearly labelled. Anthropic has other credentials (console password, etc.) — the "API Key" suffix disambiguates.

Keychain fields:
- **Service:** `Bristlenose Anthropic API Key` (what shows in Keychain Access)
- **Account:** `bristlenose` (identifies our app)
- **Password:** the actual API key

### 3. CLI interface

**Decision:** One provider at a time via `bristlenose configure <provider>`.

```bash
bristlenose configure claude
# Prompts for key, validates, stores in Keychain

bristlenose configure chatgpt
# Same flow

# Also: azure, gemini, miro
```

**Shipped note:** command takes **product names** (`claude`, `chatgpt`, `gemini`) in user-facing flags, not internal names (`anthropic`, `openai`, `google`). See `bristlenose/cli.py:1613-1727`. Internal storage still keys on internal names.

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

> **Post-script (2026-04-21):** Snap shipped with env-var fallback. `bristlenose configure` detects snap context and prints an `export ANTHROPIC_API_KEY=...` message for the user to add to their shell profile. Encrypted-file approach was not needed — env vars are sufficient for snap users who are already comfortable with shell. See `docs/design-doctor-and-snap.md:872-877` for shipped behaviour.

---

## Desktop (sandboxed) credential path

**Shipped in Track C (Apr 2026).** This is a distinct deployment from the CLI/serve-mode path above. When Bristlenose runs embedded in the macOS desktop app (sandboxed, signed, TestFlight/App Store bound), the credential flow inverts: **Swift reads Keychain via Security.framework; Python never touches Keychain.**

> **Beat 3 addition (2026-04-29).** A new component, `LLMValidator.swift`, reads the Keychain key inside Swift Settings to do round-trip authentication against the provider's API. It does NOT change the flow below — the env-var injection on sidecar launch is unchanged. See `design-desktop-settings.md` §"Validation flow (Beat 3)" for the validator details (verdict cache, TTL, offline survival).

### The flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. User sets API key in SwiftUI Settings → LLM tab              │
│    → LLMSettingsView writes via KeychainHelper (Security.framework) │
│    → Keychain entry: access group scoped to app bundle ID       │
│                                                                 │
│ 2. User starts analysis                                         │
│    → ServeManager boots the sidecar subprocess                  │
│    → Before exec: overlayAPIKeys() reads all keychain entries   │
│    → Injects BRISTLENOSE_<PROVIDER>_API_KEY env vars            │
│                                                                 │
│ 3. Python sidecar starts                                        │
│    → config.py reads env vars (EnvCredentialStore path)         │
│    → Never calls `security` CLI, never links Security.framework │
└─────────────────────────────────────────────────────────────────┘
```

**Anchors:**
- `desktop/Bristlenose/Bristlenose/ServeManager.swift:356-383` — `overlayAPIKeys(into:)` iterates providers, reads keychain, injects env vars
- `desktop/Bristlenose/Bristlenose/KeychainHelper.swift` — Security.framework-based store (no shell-out to `security` CLI)
- `desktop/Bristlenose/Bristlenose/LLMSettingsView.swift` — SwiftUI Settings UI that calls KeychainHelper
- `desktop/Bristlenose/Bristlenose/ServeManager.swift:183-197` — subprocess boot that applies the overlay
- Commit: "inject keychain api keys as env vars" (a8dc3cb)

### Why this split

The sandboxed desktop context adds constraints that change the optimal design:

- **Sandbox entitlements.** Giving the Python sidecar `keychain-access-groups` would require additional entitlements and complicate the sandbox profile. Reading Keychain from Swift (the app's sandbox principal) and passing credentials via process env vars is simpler.
- **PyInstaller bundle size.** Linking Security.framework from Python via PyObjC or similar adds weight to a bundle that's already 644 MB. The `security` CLI shell-out wouldn't work from the sandboxed Python subprocess either.
- **Separation of concerns.** The Swift side owns all OS-integration concerns (Keychain, notifications, unified logging). Python focuses on the analysis pipeline.

### Threat-model rationale

Env-var-over-keychain-access-groups has a small but non-zero residual risk: env vars are visible to anyone with the same UID via `ps -E`. The trade-off:

- An attacker with same-UID code execution on the machine can already call `SecItemCopyMatching` directly against the same keychain entries the app uses. Net delta from env-var exposure is small.
- The sandbox protects against *other* UIDs and untrusted cross-app actors. Both `security` CLI and Security.framework rely on the same sandbox boundary.
- Clear documentation ("same-UID threat not mitigated") is honest; hiding the env vars in Keychain access groups would be security theatre against the actual threat model.

See the comment block at `desktop/Bristlenose/Bristlenose/ServeManager.swift:366-371` for the in-code rationale.

### Testability

`ServeManager` takes `any KeychainStore` as a protocol, with `InMemoryKeychain` as a test shim. Swift-side tests exercise the env-var injection path without touching the real keychain. See `desktop/Bristlenose/BristlenoseTests/` and `desktop/CLAUDE.md` §Testability refactors.

## Secret-leak defences

Shipped alongside the desktop credential path in Track C (Apr 2026). Two layers, both defence-in-depth against API-key-shaped substrings leaking into sidecar stdout / unified logging.

### Layer 1: Runtime log redactor (Swift side)

Every line of sidecar stdout passes through a regex-based redactor before forwarding to unified logging. Recognises the shape of known provider API keys and replaces with `<REDACTED>`.

- Anchors: `desktop/Bristlenose/Bristlenose/ServeManager.swift:409-473` (redactor implementation), `desktop/Bristlenose/BristlenoseTests/HandleLineRedactorTests.swift` (tests)
- Commits: "runtime log redactor for api key shapes" (8a41f60), "tests for env injection, redactor" (5dc971f)

Why runtime and not just source-time? Python logging is out of our control — third-party libraries, error messages, subprocess output. A runtime filter catches leaks the source-time gate can't.

### Layer 2: Source-time CI grep gate (Swift side)

`desktop/scripts/check-logging-hygiene.sh` — CI gate that greps Swift source for `print`/`os_log`/`Logger` calls that interpolate secret-shaped values. Fails the build if a developer writes `os_log("key: \(apiKey)")` or similar.

- Anchor: `desktop/scripts/check-logging-hygiene.sh`
- Commit: "CI grep gate for Swift logging hygiene" (c17954d)

Why both layers? Source-time catches the easy mistake before it ships. Runtime catches the hard case (library output, error messages, future code paths) where source inspection can't reach.

### What's not covered

- **Python-side logging.** The Python operational log (`.bristlenose/bristlenose.log`) is governed by `design-logging.md`'s PII policy. Not redacted at runtime — assumption is that Python-side code already avoids logging keys.
- **Shell process inspection (`ps -E`).** Same-UID attackers can read env vars. See §"Threat-model rationale" above.

---

> **Historical:** the sections below (Module Structure through Implementation Order) describe the pre-ship plan. The approach shipped with expansion (5 providers instead of 2, Swift-side store for desktop context) but the Python-side structure is substantively as planned. Inlined source is the plan-version; see `bristlenose/credentials.py`, `credentials_macos.py`, `credentials_linux.py` for current.

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
