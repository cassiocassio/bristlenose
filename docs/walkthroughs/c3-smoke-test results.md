# C3 smoke test — findings log

Companion to [`c3-smoke-test.md`](c3-smoke-test.md). Live notes on what happens during the run, what's surprising, what's a bug, what's a walkthrough improvement.

**Project under test:** `~/Code/bristlenose/trial-runs/foo` (three short videos)
**Date:** 20 Apr 2026
**Operator:** Martin
**Build:** `sidecar-signing` HEAD = `e1129b2` (last commit before smoke test started)

## Pre-flight

### Walkthrough corrections needed before reading

- **Spend cap section** — initial draft claimed "set per-key cap" (wrong), then "set workspace cap" (also wrong: workspaces don't have spend limits in the individual tier). Landed on "turn off auto-recharge, note balance, revoke after." Two correction commits: `c3be5d4`, `e1129b2`. Walkthrough now matches reality. Saved as memory `reference_anthropic_spend_controls.md` so future sessions don't repeat the mistake.

- **Worktree clarity** — the walkthrough assumes you've opened the **sidecar-signing** worktree's Xcode project. It's possible to open the main-branch project by accident — telltale: a "Bristlenose default" scheme (which exists only on main; sidecar-signing has three: `Bristlenose`, `Bristlenose (Dev Sidecar)`, `Bristlenose (External Server)`). **Walkthrough should add an explicit "open this exact path" sanity check at the top of A1.**

- **Trial-runs are per-worktree** — `trial-runs/` is gitignored, so `project-foo` only exists in the main worktree (`~/Code/bristlenose/trial-runs/`). The desktop app takes any absolute path though, so dragging from `~/Code/bristlenose/trial-runs/foo/` works even when the build comes from `sidecar-signing`. Walkthrough mentions `trial-runs/` without disambiguating which worktree — worth a clarifying line.

## At launch

### Keychain access prompt — expected, and a positive C3 signal

- macOS Keychain prompt appeared: *"Bristlenose wants to use your confidential information stored in 'Bristlenose Anthropic API Key' in your keychain. To allow this, enter the 'login' keychain password."*
- Why: Debug builds get a fresh ad-hoc signature on every build. Keychain ACLs are bound to a specific code signature, so a re-signed binary loses access until granted again. Anthropic key was already in Keychain from a prior session; first launch with the new C3 binary triggered the gate.
- This is **proof that C3's `KeychainHelper.get()` is firing** — the app is reaching `SecItemCopyMatching` and macOS is gating it. Good first signal even before any pipeline action.
- Choices: "Always Allow" (trust this signature persistently — useful for the dev session, but invalidated next rebuild), "Allow" (one-shot), "Deny" (would break injection).
- Choice during this run: **[record what you picked]**.
- **Walkthrough enhancement**: this prompt isn't mentioned in A1. It will absolutely appear on first launch after a rebuild if any provider key already exists in Keychain. Worth pre-warning so it doesn't look alarming.

## Opening the project

### "Project Already Exists" dialog (drag from Finder)

- Dragged `~/Code/bristlenose/trial-runs/foo/` onto the sidebar.
- Modal appeared: *"A project for this folder already exists: 'foobar'. You can open the existing project or create a new one."*
- Three buttons rendered: **Open Existing**, **Create Anyway**, **`common.cancel`** (raw key — see BUG-1 below).
- Choice: **Open Existing** (correct call; preserves prior pipeline state, avoids re-burning API credit).

### BUG-1: `common.cancel` i18n key leaks raw to UI

- **Location**: `desktop/Bristlenose/Bristlenose/ContentView.swift:316`
- **Code**: `Button(i18n.t("common.cancel"), role: .cancel) {}`
- **Why broken**: I18n key paths use the `<file>.<nested-keys>` format (per `I18n.swift:8` docstring example: `common.nav.quotes`). The actual key in `bristlenose/locales/en/common.json` is at `buttons.cancel`, so the lookup needs `common.buttons.cancel`. Using `common.cancel` resolves to nothing and the I18n implementation falls through to returning the raw key string as the label.
- **Severity**: cosmetic, but visible to every user who adds a duplicate folder. Embarrassing on first-impression for alpha testers.
- **Fix**: one-character change, `"common.cancel"` → `"common.buttons.cancel"`.
- **Other instances?** Initial grep showed only this site uses the wrong path; other `i18n.t("common.…")` callers haven't been audited yet — worth a quick sweep when fixing.
- **Status**: deferred — not C3 work, captured here for cleanup pass.

## Pass A — fake-key redactor sanity

[fill in as it goes]

## Pass B — happy path with real throwaway key

[fill in as it goes]

## Cleanup

[fill in]

## Net assessment

[fill in at end — summary of what worked, what didn't, walkthrough patches to roll back]

## Walkthrough patches to roll back into `c3-smoke-test.md`

Running list of corrections to fold back in once the smoke test completes (single editing pass at the end, not commit-by-commit):

1. Add explicit absolute-path sanity check for the Xcode project at the top of A1 (`open "/Users/cassio/Code/bristlenose_branch sidecar-signing/desktop/Bristlenose/Bristlenose.xcodeproj"`).
2. Clarify that `trial-runs/` is per-worktree and that the data folder can live in any worktree (the desktop app takes any absolute path).
3. Pre-warn about the Keychain access prompt on first launch after rebuild — explain why it appears, that "Always Allow" is fine for dev sessions, and that seeing it is positive (proves `KeychainHelper.get` is firing).
4. (If BUG-1 isn't fixed by the time smoke completes) note the `common.cancel` button label as a known-cosmetic-issue when reaching the duplicate-folder path.
