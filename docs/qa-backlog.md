# QA Backlog

Manual QA steps waiting to be confirmed. Per-item — say "QA done for X" to check off.

---

## macOS localisation — menu bar, Settings, and the failure surfaces

**Date:** 21 Sep 2026
**Branch:** main (`9c200e6b`..`cc4a4573`, 17 commits)
**Context:** Roughly 700 translated values across 21 locales, plus two mechanisms
that only take effect at launch. Every item below is something **no test can
see** — the `.lproj` work is a bundle property, the menu bar is built once per
process, and the chip grid is a measured layout.

**Do items 1–3 after a RELAUNCH** (⇧⌘K then ⌘R if the build looks stale).

- [ ] **Apple's own menus are localised.** Set Settings ▸ Appearance ▸ Language to Türkçe, relaunch, and check `File / Edit / View / Window / Help` read `Dosya / Düzen / Görünüm / Pencere / Yardım` — and the items inside them (Minimize, Zoom, Bring All to Front, Cut/Copy/Paste, Enter Full Screen). These come from AppKit now that the app declares 22 `.lproj`; we translated none of them.
- [ ] **Our four menus follow too** — `Proje / Kodlar / Alıntılar / Video`. `Diagnostics` stays English by decision.
- [ ] **Nothing regressed for an existing install.** A profile that already had a language set should come up in it, not in English: the private `language` key still wins over the new `Bundle.preferredLocalizations` fallback.
- [ ] **Sentiment chips at 14".** Welcome ▸ the "Seven sentiments" card in **tr** — `Kafa karışıklığı` is +24% on the widest row, past the screen's documented +20% budget. The grid scales to fit; check it shrinks rather than clipping or colliding with the text beside it. Then check **ja/zh-Hant**, which are 35–49% *narrower*, do not look lost.
- [ ] **Settings language switch stays put.** Change language with Settings open: the six tabs flip AND the window stays on Appearance (it used to snap to General).
- [ ] **A failed cloud-import row speaks the language.** Easiest via Diagnostics ▸ Cloud Import ▸ a partial-failure fixture: the red rows should read e.g. `Dosyanın yalnızca bir kısmı ulaştı.`, not `Only part of the file arrived`.
- [ ] **A sign-in failure speaks the language.** Start a cloud sign-in and cancel it — expect the translated sentence. Microsoft/Zoom refusals that carry the provider's *own* reason are supposed to stay in the provider's words; that is not a bug.
- [ ] **A drag-and-drop refusal speaks the language.** Drop a folder containing nothing importable → translated toast.

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

---

## Dev Run Inspector — visual render (run / llm / timing)

**Date:** 28 Jun 2026
**Branch:** `claude/debug-menu-instrumentation-4r9npy` (merge `252c1ce3`)
**Context:** Dev-only Run Inspector (`/api/dev/run`) is client-rendered (JS `JSON.parse` + DOM build), so the pytest/curl coverage only proves data + template are sound — the rendered surfaces need a real browser. Data + escaping + endpoint gating already verified against a real analysed project (≈18 captured LLM calls, OpenAI/gpt-4o). Native entry: **Debug ▸ Run Inspector** (⌃⌘R) in the DEBUG desktop build. Browser path: load `http://localhost:8150/report/` FIRST (sets the `bristlenose_auth` cookie), then `http://localhost:8150/api/dev/run`.

- [ ] **Run tab** renders the provenance header with real values (run_id ULID, status=completed, true wall-clock duration — NOT the stage-sum fallback) and the cost donut shows `—` for a null-cost run (an OpenAI run captures no cost), not a misleading `$0.00`
- [ ] **LLM tab** lists the per-call rows (provider/model/elapsed) for a run with a real `llm-calls.jsonl` (≈18 calls)
- [ ] **Timing tab** chart renders (calibration curve empty on real data today is expected — no timing-history store yet)
- [ ] **Native window** (Debug ▸ Run Inspector, ⌃⌘R) loads the same page authenticated via cookie — no 401, no blank pane
- [ ] **Live Diagnostic-fixtures submenu** applies a scenario to the selected project without relaunch
