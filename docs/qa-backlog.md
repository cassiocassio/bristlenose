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

---

## Warm-sidecar pool — project-switch edges (Phase A2)

**Date:** 21 Jun 2026
**Branch:** `warm-sidecar-pool` (commit `beaac38`)
**Context:** `switchProject` parks the outgoing serve sidecar and re-points to a warm one instead of teardown+restart. Single parked slot (Option B). Core path GUI-confirmed (rapid A↔B switch-back is fast and the report renders). These are the **unverified edges** — especially the silent-401 class the `.id`+port fix guards. Mechanism: `ServeManager.swift` (`switchProject`/`drainParked`/`dropParked`/`probeHealth`), `ParkedSidecar.swift`. Tiers + rationale: `docs/design-desktop-switch-performance.md`.

- [ ] **Warm switch-back renders DATA, not a blank/empty report** (the F1 silent-401 check): A→B→A, confirm A's quotes/sessions actually show — an *empty* report that loads fast is the failure, not just a spinner
- [ ] **≥3-project rapid switching** (A→B→C→A→B fast): no crash; the 3rd-project / evicted cases cold-start cleanly (they retain the pre-existing boot race by design — F13)
- [ ] **Prefs/provider change drains the pool** (F6): switch to A, switch to B, change provider/model in Settings, switch back to A → A **cold-starts fresh** (serves with the new config), does not re-point to a stale-env warm sidecar
- [ ] **Consent change drains the pool** (F7): with a warm slot, trigger a consent re-acknowledge → parked sidecar is torn down (no parked process serving under old consent)
- [ ] **Project removal drops its warm slot** (F16): switch to A then B (A parked), remove A from sidebar → A's sidecar is torn down, not left serving a removed project
- [ ] **Dead/wedged parked sidecar falls back to cold start, never blank** (F1/F3): if a parked sidecar dies while parked, switching back shows a real boot (`.starting`→`.running`) or failure, never a silent blank pane
- [ ] **Lifecycle log lines present**: `log stream --predicate 'subsystem == "app.bristlenose"'` shows `sidecar_parked` / `sidecar_repointed` / `sidecar_evicted` (+ `sidecar_parked_died` if one dies parked) at the matching moments
