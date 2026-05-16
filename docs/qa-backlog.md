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

---

## Sidebar 'analysing…' lie on re-open (drag-drop ingest)

**Date:** 16 May 2026
**Branch:** main (merge `bbc899b`)
**Context:** `ContentView.createProjectFromURLs` now branches on `LocateFlow.folderLooksAnalysed` — analysed-folder drops route to `pipelineRunner.scan` (manifest-derived state) instead of `.start` (auto-run). `PipelineRunner.scan` pre-sets `.scanning` to close the nil-state window. Rename-mode scoped to fresh-project drops only. Stricter than the original brief: marker present = no auto-run even for partial runs; existing Resume / Continue / Retry affordance is the entry point.

- [ ] Drop folder with complete `bristlenose-output/`: row shows no "Analysing…" subtitle; goes straight to ready state; **switching to another project does NOT trigger the cancel-confirmation modal**
- [ ] Drop folder with raw media, no `bristlenose-output/`: row shows "Analysing…" + auto-runs the pipeline; rename-mode TextField focuses (the auto-run path is unregressed)
- [ ] Drop folder with partial output (interrupted run — synthesise by Stop-ing a fresh run mid-flight, then Remove + re-drop): row resolves to `.partial` / `.stopped` / `.failed`; existing Resume / Continue / Retry affordance is the entry point; **no silent auto-run**
- [ ] Brief subtitle during scan reads localised `.scanning` text (a few frames on local SSD, longer on network mount). NOT "Analysing…" — if you see "Analysing…" briefly on the analysed-folder drop, the scan pre-set didn't take
