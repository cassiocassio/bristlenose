# QA Backlog

Manual QA steps waiting to be confirmed. Per-item — say "QA done for X" to check off.

---

## Keychain Security.framework migration

**Date:** 24 Mar 2026
**Branch:** main
**Context:** Rewrote `KeychainHelper.swift` from `/usr/bin/security` CLI to native `SecItemAdd`/`SecItemCopyMatching`/`SecItemDelete`. Same public API, backward-compatible with existing Keychain entries.
**Full QA script:** `docs/qa/keychain-security-framework.md`

- [ ] Key persistence round-trip: enter key in Settings → LLM, quit, relaunch, verify it's still there
- [ ] No subprocess: `ps aux | grep security` during key save — no `/usr/bin/security` process
- [ ] CLI interop: `security find-generic-password -a bristlenose -s "Bristlenose Anthropic API Key" -w` returns the key saved from the app
- [ ] Xcode console: no `[KeychainHelper]` error lines during normal key operations
