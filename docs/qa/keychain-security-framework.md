# QA Script — Keychain Migration to Security.framework

**Branch:** `main`
**Date:** 24 Mar 2026

Verify that `KeychainHelper.swift` uses native Security.framework instead of `/usr/bin/security` CLI.

---

## 1. Automated checks

```bash
cd /Users/cassio/Code/bristlenose

# Xcode Debug build (no SECURITY #6 warning)
cd desktop/Bristlenose && xcodebuild build -scheme Bristlenose -configuration Debug -destination "platform=macOS" 2>&1 | grep "SECURITY #6"
# Expected: no output (warning removed)

# Python tests (unaffected — Swift-only change)
cd /Users/cassio/Code/bristlenose
.venv/bin/python -m pytest tests/ -q
```

## 2. Key persistence round-trip

1. Open Bristlenose in Xcode → `Cmd+R`
2. Go to **Settings → LLM** (brain tab)
3. Select a provider (e.g. Claude) and enter a test API key
4. Quit the app (`Cmd+Q`)
5. Relaunch (`Cmd+R`)
6. Verify the key is still there in Settings → LLM

## 3. No subprocess spawned

While the app is running:

1. Open Terminal
2. Enter a new API key in Settings → LLM
3. During the save, run: `ps aux | grep security`
4. Expected: no `/usr/bin/security add-generic-password` process visible

## 4. CLI interop (backward compat)

After saving a key via the app:

```bash
security find-generic-password -a bristlenose -s "Bristlenose Anthropic API Key" -w
```

Expected: prints the API key you entered. Confirms native `SecItemAdd` and CLI `security` read the same Keychain entries.

## 5. Xcode console (DEBUG logging)

With the app running in Xcode, check the console output during key operations. Normal operations should produce no `[KeychainHelper]` error lines. If you see one, it includes the `OSStatus` code and human-readable message.
