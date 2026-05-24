# Active Feature Branches

This document tracks active feature branches to help multiple Claude sessions coordinate without conflicts.

**Updated:** 24 May 2026 (closed `llm-error-distinguishability`)

---

## Branch Kinds

Every branch declares a **Kind** — a one-word descriptor of what the branch is for. Kind is metadata for human readers of this file; it doesn't gate skill behaviour (merge target comes from `**Forked from:**`; merge-or-abandon is asked at `/close-branch` time regardless of Kind).

| Kind | Description | Typical end-of-life |
|------|-------------|---------------------|
| **feature** | New capability or surface | Merge to main |
| **bugfix** | Corrective change to existing behaviour | Merge to main |
| **refactor** | Same behaviour, cleaner internals | Merge to main |
| **docs** | Documentation-only (design docs, user manual, READMEs) | Merge to main; trivial fixes go direct |
| **ci** | Build / release / test-infra | Merge to main |
| **chore** | Small ephemeral work (dep bumps, doc reconciliation, release tooling) | Merge or discard, low ceremony |
| **spike** | Exploratory throwaway — proves or disproves an approach | Usually discarded; cherry-pick if a commit's worth keeping. If it turns out unexpectedly great, just merge it. |
| **diagnostic** | Inventory / reports / reproductions — fixes happen in *other* branches | Discarded when narrow-fix children land; the branch itself never merges, its useful output already left via siblings |
| **parked** | On hold; may resume later | Stays on disk + remote until revived or formally retired |

Pick the Kind that best describes what you're doing. Don't agonise — Kind is descriptive, not normative. If two fit, pick either.

## Worktree Convention

Each active feature branch gets its own **git worktree** — a full working copy in a separate directory. This lets multiple Claude sessions work on different features simultaneously without interfering.

**Directory pattern:** `/Users/cassio/Code/bristlenose_branch <name>`

| Directory | Branch | Kind | Purpose |
|-----------|--------|------|---------|
| `bristlenose/` | `main` | — | Main repo, releases, hotfixes |
| `bristlenose_branch tower-of-hanoi/` | `tower-of-hanoi` | spike | Bristlenose workflow thought experiment — Tower of Hanoi solver, full /usual-suspects + William-only loop, i18n stipulated |
| `bristlenose_branch responsive-signal-cards/` | `responsive-signal-cards` | feature | Responsive signal cards (worktree never opened — BRANCHES entry is a placeholder) |
| `bristlenose_branch symbology/` | `symbology` | parked | § ¶ ❋ Unicode prefix symbols (see Historical experiments) |
| `bristlenose_branch highlighter/` | `highlighter` | parked | Highlighter feature (see Historical experiments) |
| `bristlenose_branch living-fish/` | `living-fish` | parked | Animated logo (see Historical experiments) |
| `bristlenose_branch drag-push/` | `drag-push` | parked | Sidebar push-mode drag (see Historical experiments) |
| `bristlenose_branch pipeline-view-v1-5/` | `pipeline-view-v1-5` | feature | Extend Pipeline view with per-stage Alternatives (✓/✗ eligibility + one-line reasons) — data-model rung for v2 resolver / v3 overrides |
| `bristlenose_branch llm-error-distinguishability-all-providers/` | `llm-error-distinguishability-all-providers` | feature | Extend preflight error classification to Azure, Gemini, Ollama using structured error.code/error.status fields; switch OpenAI's substring branches to structured fields |





**Creating a new feature branch worktree:**

```bash
# From the main repo:
cd /Users/cassio/Code/bristlenose

# Create the branch (if it doesn't exist) and the worktree in one go:
git branch my-feature main
git worktree add "/Users/cassio/Code/bristlenose_branch my-feature" my-feature

# Or if the branch already exists:
git worktree add "/Users/cassio/Code/bristlenose_branch my-feature" my-feature
```

**Each worktree needs its own venv** to run tests:

```bash
cd "/Users/cassio/Code/bristlenose_branch my-feature"
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

**Listing worktrees:** `git worktree list` (from any worktree)

**Removing a worktree** (after merging to main):

**Important:** Always `cd` to the main repo *before* removing a worktree. If a Claude session or terminal has its CWD inside the worktree directory, removing it will break that shell — every subsequent command fails with "path does not exist" and the session is unrecoverable.

```bash
# 1. Switch to main repo FIRST (never remove a worktree from inside it)
cd /Users/cassio/Code/bristlenose

# 2. Remove the worktree and branch
git worktree remove "/Users/cassio/Code/bristlenose_branch my-feature"
git branch -d my-feature

# 3. If the directory was already deleted (rm -rf or Finder):
git worktree prune          # cleans stale worktree refs
git branch -d my-feature    # delete the branch

# 4. If also on remote:
git push origin --delete my-feature
```

**Rules:**
- `bristlenose/` always stays on `main` — never check out a feature branch there
- Each Claude session should confirm which worktree it's operating in at session start
- Commits made in any worktree are immediately visible to all others (shared `.git`)
- Don't run `git checkout` to switch branches inside a worktree — that defeats the point

---

## How to Use This File

When starting a new Claude session on a feature branch:
1. Check this file to see what other branches are active
2. Confirm you're in the right worktree directory
3. Note which files other branches are touching
4. Avoid editing those files unless necessary
5. Update this file when you create/complete a branch

When merging back to main:
1. Read the merge plan for your branch
2. Check for conflicts with other branches
3. Update this file to mark your branch as merged
4. Remove the worktree

---

## Backup Strategy

Feature branches are pushed to GitHub for backup without triggering releases (only `main` triggers releases). Use `git push origin <branch-name>` to back up.

| Branch | Local worktree | GitHub remote |
|--------|---------------|---------------|
| `main` | `bristlenose/` | `origin/main` (push via `origin/main:wip` until release time) |
| `tower-of-hanoi` | `bristlenose_branch tower-of-hanoi/` | local only |
| `multi-project-drag-onto` _(merged)_ | `bristlenose_branch multi-project-drag-onto/` _(detached, on disk)_ | local only — merged to main 15 May 2026 |
| `multi-project-switch` _(merged)_ | `bristlenose_branch multi-project-switch/` _(detached, on disk)_ | local only — merged to main 14 May 2026 (`baf1896`) |
| `ci-version-pinning` _(merged)_ | `bristlenose_branch ci-version-pinning/` _(detached, on disk)_ | local + remote deleted — merged to main 14 May 2026 (`e1c8083`) |
| `tf-multi-project` _(merged)_ | `bristlenose_branch tf-multi-project/` _(detached, on disk)_ | local only — merged to main 14 May 2026 (`e73de11`) |
| `sandbox-debug` _(closed)_ | _removed 2 May 2026_ | local only — diagnostic, never pushed |
| `bundled-tls-config` _(merged)_ | `bristlenose_branch bundled-tls-config/` _(detached, on disk)_ | merged to main on 2 May 2026 (`7240675`) |
| `responsive-signal-cards` | `bristlenose_branch responsive-signal-cards/` | local only |
| `i18n-llm-settings` _(merged)_ | `bristlenose_branch i18n-llm-settings/` _(detached, on disk)_ | merged to main 5 May 2026 (`c023f7d`) |
| `symbology` _(parked)_ | `bristlenose_branch symbology/` | `origin/symbology` |
| `highlighter` _(parked)_ | `bristlenose_branch highlighter/` | `origin/highlighter` |
| `living-fish` _(parked)_ | `bristlenose_branch living-fish/` | `origin/living-fish` |
| `drag-push` _(parked)_ | `bristlenose_branch drag-push/` | local only |
| `cli-message-kinds` _(closed)_ | `bristlenose_branch cli-message-kinds/` _(detached, on disk)_ | local only — code on main as `0a0c8d5` |
| `pipeline-view-v1-5` | `bristlenose_branch pipeline-view-v1-5/` | local only |
| `llm-error-distinguishability-all-providers` | `bristlenose_branch llm-error-distinguishability-all-providers/` | local only |




---

## Active Branches

---

### `llm-error-distinguishability-all-providers`

**Kind:** feature — extends preflight error classification across all LLM providers, intended to merge to main
**Status:** Just started
**Started:** 24 May 2026
**Worktree:** `/Users/cassio/Code/bristlenose_branch llm-error-distinguishability-all-providers/`
**Remote:** local only (push when ready)

**What it does:** Extend preflight error classification to Azure, Gemini, and Ollama using structured `error.code` / `error.status` fields where available; switch OpenAI's substring branches to read structured fields; keep the 4-bucket `error_class` vocabulary. Builds on the just-closed `llm-error-distinguishability` (Anthropic-only `billing_empty`) by generalising the approach across all providers. See `HANDOFF.md` for the full brief.

**Files this branch will touch:**
- `bristlenose/preflight/api_key.py`
- `bristlenose/llm/billing_hints.py`
- `bristlenose/locales/`
- `tests/test_preflight_api_key.py`

**Potential conflicts with other branches:**
- None expected — preflight + billing_hints surface is not touched by other active branches. Locale changes likely confined to preflight-namespaced keys; use targeted text-replace (never `json.dump` round-trip) per the i18n gotcha.

---

### `pipeline-view-v1-5`

**Kind:** feature — code intended for main; extends the v1 Pipeline view with a per-stage Alternatives column. Ends in merge or PR-and-squash.
**Status:** Just started
**Started:** 18 May 2026
**Worktree:** `/Users/cassio/Code/bristlenose_branch pipeline-view-v1-5/`
**Remote:** local only (push when ready)

**What it does:** Extend the read-only Pipeline view (v1) with a per-stage "Alternatives" surface — for every stage, render the other backends that *could* run it on this host, with ✓/✗ availability flags and a one-line reason on ✗. Read-only; quality ratings (●/○/⚠/✗) deferred to v1.9, auto-pick to v2, per-stage overrides to v3. **The point is the data-model rung:** v1.5 encodes the full eligibility space per stage (catalogue of `BackendOption` + `Requirement` predicates against `HostFacts` + `BristlenoseSettings`) that the v2 resolver and v3 overrides will both consume. When Apple FM ships a research-viable on-device model post-WWDC, the work is "edit one catalogue cell + verify a host predicate," not "build a resolver from scratch." See `HANDOFF.md` for the full brief.

**Files this branch will touch:**
- New: `bristlenose/pipeline_view/eligibility.py` — `check_requirement` + `evaluate_backend` pure functions
- Modified: `bristlenose/pipeline_view/catalogue.py` — add `Requirement`, `BackendOption`, populate `viable_backends`
- Modified: `bristlenose/pipeline_view/host.py` — add `os_version`, `installed_packages` fields + probes
- Modified: `bristlenose/pipeline_view/render.py` — `BackendAvailability` type, `alternatives` field, sort logic
- Modified: `bristlenose/pipeline_view/cli.py` — Alternatives sub-line rendering
- Modified: `frontend/src/components/SettingsModal.tsx` `PipelineSection` — alternatives list render
- Modified: `bristlenose/theme/organisms/settings.css` — `.bn-pipeline-alternatives` styling
- Modified: `tests/fixtures/pipeline-view-contract.json` — schema v1 → v2 (additive)
- New: `tests/pipeline_view/test_eligibility.py`, `test_alternatives.py`
- Modified: 6 locale files — `pipeline.alternatives` heading only

**Potential conflicts with other branches:**
- `pipeline-view-v1` — direct parent; v1.5 lives in the same `bristlenose/pipeline_view/` package and edits files v1 introduces. Don't start v1.5 work until v1 merges, or be ready to rebase.
- `pipeline-subtitle-i18n` — touches the 6 `common.json` locale files. Keep keys distinct (`pipeline.alternatives.*`) and use targeted text-replace, never `json.dump` round-trip.

---

### `tower-of-hanoi`

**Kind:** spike — exploratory throwaway, won't merge to main; cherry-pick selectively if anything earns its keep
**Status:** Just started
**Started:** 12 May 2026
**Worktree:** `/Users/cassio/Code/bristlenose_branch tower-of-hanoi/`
**Remote:** local only (push when ready)

**What it does:** Bristlenose workflow thought experiment — Tower of Hanoi solver, full /usual-suspects + William-only loop, i18n stipulated. Self-contained prototype under `experiments/tower-of-hanoi/` (auto-discovered by `bristlenose serve --dev` in the Design section). The point is not the solver — it's walking the full plan → `/usual-suspects` → William-only → implement → `/usual-suspects` → William-only loop on a toy, and observing how the agent loop behaves. i18n is stipulated in scope; any William objection to it is recorded verbatim and overruled in `.claude/plans/tower-of-hanoi-decisions.md`.

**Files this branch will touch:**
- `experiments/tower-of-hanoi/` (all new — solver, theme-primitive consumption, six locale files)

**Potential conflicts with other branches:**
- None expected — `experiments/` is excluded from `ruff check` (per `pyproject.toml`) and no other active branch touches that subtree. Locale files live under `experiments/tower-of-hanoi/locales/`, **not** `bristlenose/locales/`, so the i18n surface is isolated from any other branch's locale edits.

---

### `sandbox-debug` (closed — diagnostic, discarded)

**Kind:** diagnostic — never intended to merge; produced inventory that fanned out into narrow children
**Status:** Closed 2 May 2026. Children all landed: credentials (Track C v0.15.1), TLS (`bundled-tls-config`), `network.server` (A2), sandbox-native lifecycle (A6), FFmpeg/ffprobe paths (`bundled-binary-helper` → `670a002` on main). `git diff main...sandbox-debug` was empty at close time — nothing to rescue.
**Started:** 29 Apr 2026

**What it did:** S2 Track A — macOS app sandbox violation triage. A1 spike: turn sandbox on in Debug, walk §1a flow, capture every `deny(1)` line, output a violation inventory. By design produced **no fixes itself** — fixes happened in narrow per-violation branches and merged to main directly.

**Lesson:** This is the canonical example of a `diagnostic` Kind branch. Its useful output (the inventory) flowed out via siblings; the branch itself was always destined for `/close-branch`, not merge.

---

### `responsive-signal-cards`

**Kind:** feature
**Status:** Just started
**Started:** 15 Mar 2026
**Worktree:** `/Users/cassio/Code/bristlenose_branch responsive-signal-cards/`
**Remote:** local only (push when ready)

**What it does:** Responsive layout for signal/analysis cards across screen sizes.

**Files this branch will touch:**
- TBD — will be filled in as work progresses

**Potential conflicts with other branches:**
- `symbology` — low risk (touches render/template files, not signal card layout)
- `drag-push` — low risk (sidebar CSS, not signal cards)

---

## Historical experiments (parked — unlikely inside 100 days)

These branches/worktrees are kept on disk as a record of nice ideas that aren't on the critical path to alpha. Don't treat them as active; don't propose work on them unless explicitly asked. Some may resurface post-TestFlight.

Marked parked: 1 May 2026.

### `symbology` — started 12 Feb 2026

**Worktree:** `/Users/cassio/Code/bristlenose_branch symbology`
**Remote:** `origin/symbology`

**Idea:** Consistent Unicode prefix symbols (§ Section, ¶ Quote, ❋ Theme) across all user-facing surfaces — navigation, headings, dashboards, analysis, tooltips, text output. Likely touches `render_html.py`, `s12_render_output.py`, `theme/templates/*`, `theme/js/{analysis,transcript-annotations,codebook}.js`.

### `highlighter` — started 13 Feb 2026

**Worktree:** `/Users/cassio/Code/bristlenose_branch highlighter`
**Remote:** `origin/highlighter`

**Idea:** Highlighter feature (scope was never fully defined).

### `living-fish` — started 26 Feb 2026

**Worktree:** `/Users/cassio/Code/bristlenose_branch living-fish/`
**Remote:** `origin/living-fish`

**Idea:** Animated "living portrait" bristlenose logo for serve mode — AI-generated video loop (WebM VP9 alpha + MOV HEVC alpha) with subtle breathing/gill/fin movement, plus a dark-mode logo fix that drops the `mix-blend-mode: lighten` hack via a transparent-background PNG. Touches `bristlenose/server/app.py`, `theme/report_header.html`, `theme/atoms/logo.css`, `theme/images/`, possibly a React header component.

### `drag-push` — started 14 Mar 2026

**Worktree:** `/Users/cassio/Code/bristlenose_branch drag-push/`
**Remote:** local only

**Idea:** Sidebar rail drag-to-open uses push mode (grid column resize) instead of overlay (position: fixed). Mouseover overlay on left rail unchanged — dragging treated as a sizing commitment so the user can preview layout impact on center content. Touches `theme/organisms/sidebar.css` and `frontend/src/hooks/useDragResize.ts`.

---

## Cloud-session branches (rescued, kept stale)

Cloud-session `claude/<adjective>-<noun>-<hash>` branches that have been verified rescued (work landed on `main` via different SHAs per `feedback_cloud_local_divergence_warning.md`) get renamed to `stale/claude-<name>-rescued-<date>` rather than deleted. Keeps them on local disk per the insurance principle, but the prefix makes them obviously no-action so we don't rediscover them.

| Stale name | Original | Rescued | Verified |
|---|---|---|---|
| `stale/claude-fervent-wing-rescued-2026-04-29` | `claude/fervent-wing-5e5c8c` | telemetry slice a+b, security.md, true-the-docs cost-forecast | 6/6 subjects on `main` (`9f56d41`, `515668b`, `d82d6dc`, `29e4de0`, `952c332`, `d7358ec`) |
| `stale/claude-sweet-feynman-rescued-2026-04-29` | `claude/sweet-feynman-edf8da` | usual-suspects review-log + 4 same as fervent-wing | 5/5 subjects on `main` (`aa2f0dc` + same 4) |
| `stale/claude-objective-banzai-rescued-2026-04-29` | `claude/objective-banzai` | quote editing redesign (24 Feb) | Production code on main (`35ba109` trim handles + `50117a5` enter-fix); `docs/design-quote-editing.md` evolved 8 lines since branch; mockup HTML + integration prompt scaffolding not carried (one-shot artefacts) |

---

## Completed Branches (for reference)

### `llm-error-distinguishability` — merged 24 May 2026

Distinguish LLM provider failure root causes so users see the right recovery action instead of a misleading "change your model" message. Headline fix: Anthropic credit-exhausted (`400 invalid_request_error` with `"credit balance"` in `error.message`) now classifies as `billing_empty` rather than falling through to `model_unavailable`. Merged via `c3b21c0` (single commit `4eed191`).

### `multi-project-folder-watcher` — merged 16 May 2026

Phase 2 #14 — NSFilePresenter folder watcher: detect Finder-added files in a project folder, surface as Mail-style sidebar count pill + NewFilesSheet (detect-and-surface only; no auto-process). Wires `ProjectBookmarkLease` into `ProjectIndex`, lands the SQLite ingested-set foundation with `immutable=1` read path, session count + subtitle-delta row layout, Schema A dates, semantic state colours. Merged via `fdd0a1e`. Acceptance walk closed 16 May (5 of 8 steps verified; 2 deferred for design reasons; Step 7 re-mount regression filed as a chip — later closed by `cantfind-remount-recovery`). `NewFilesSheet` marked as TF scaffolding for SPA migration post-incremental-processing.

### `pipeline-subtitle-i18n` — merged 15 May 2026

Translated ProjectRow `pipelineSubtitle` and locale-aware date formatters across all 6 locales (en/es/fr/de/ko/ja) using `dt()` desktop overrides where the register diverges from CLI. Sidebar in-flight pipeline subtitles (Transcribing… / Extracting quotes… / Clustering themes…) now render in the user's locale instead of English-only. Merged via `b935f8d`. Translations matched against the Apple glossary where possible.

### `pipeline-view-v1` — merged 21 May 2026

Read-only Pipeline view: new `bristlenose pipeline` CLI verb (stage → backend → model table) and matching read-only Settings tab in the React SPA. Validates the mixture-of-models mental model with the cohort before any per-stage choice machinery earns its place. Per-stage overrides, `bristlenose use <provider>`, and `bristlenose config` namespace remain parked in `docs/design-cli-improvements.md` pending cohort signal. Contract fixture `tests/fixtures/pipeline-view-contract.json` locks the schema for the v1.5 follow-on.

### `sidebar-list-not-rendering` — merged 21 May 2026

Fix: macOS 26 SwiftUI List dropped Section content when the composition was Section + Button + ForEach.onMove + conditional Text and `projects.isEmpty == true`. Moved Button AND empty-state Text out of the Section (Section now contains only the ForEach + .onMove). Tightened empty-state condition to `projects.isEmpty && folders.isEmpty` — folders-only is intentional setup state, not empty. Merged via cherry-pick (4 commits) on top of `sidebar-drop-folder-row`'s work. Forked from and effectively stacked on `sidebar-drop-folder-row`.

### `sidebar-drop-folder-row` — merged 21 May 2026

Close V1 design-doc gap: Finder content dropped on a project-sidebar folder row now creates a new project *inside* the folder (folderId set). Replaced stacked `.dropDestination(for: T.self)` modifiers with a single `SidebarDrop` wrapper Transferable exposing multiple `ProxyRepresentation`s (Apple's canonical pattern — FB12980427). Introduced `ProjectDragID` typed Transferable with custom UTType `app.bristlenose.project-id` (`conformingTo: .data`) so internal project drags don't get auto-coerced to URL on the pasteboard. Row hit region extended into the inter-row gap via `.padding(.vertical, 2)`. Merged via cherry-pick (4 commits).

### `unify-failure-popover` — merged 20 May 2026

Unified the two failure popovers (legacy `.failed` and new `.failedWithDiagnostic` / `.completedPartial`) into a single SwiftUI view in `PipelineActivityItem.swift`. Degrades gracefully when structured data is missing (orphan `run_started`, killed sidecar, older sidecars with `summary == nil`) — same chrome, same Retry/Copy, with one explanatory line.

### `foundation-models-corpus` — merged 19 May 2026

Parameterised HIG scraper into multi-corpus scraper (`scrape-hig.py` → `scrape-apple-corpus.py` with `--corpus {hig,fm}`), scraped Foundation Models corpus to `~/.local/share/foundation-models-corpus/` (20 pages, 304 KB), and trued `design-pluggable-llm-routing.md` / `design-stage-backends.md` / `design-modularity.md` against the corpus. Phase 0 + 1 + 1b complete; Phase 2 (MLX-Swift) + Phase 3 (MLX Python) + Phase 4 (agent) explicitly deferred. Re-scrape trigger: WWDC 2026 keynote, then macOS 27 GA. Two commits merged via `cea008a`. Worktree detached and tagged orange on disk; local + remote branch deletion pending user push.

### `release-pipeline-actually-broken` — merged 19 May 2026

Restored PyPI publishing (stuck on v0.15.3 since ~10 May) by fixing the `ci/perf-gate` CI failure blocking every release tag since v0.15.5. Root cause: the status-page interceptor returns "Nothing to see here, yet." when `app.state.last_run[1]` has no terminus event, and the Playwright smoke fixture never carried `pipeline-events.jsonl`. Fix is test-only — pytest `TestSmokeFixtureMountsSPA`, Playwright `spa-mounts.spec.ts`, browser-console capture in `perf-gate.spec.ts`, plus CLAUDE.md release-flow doc edit. Four commits merged via `a3abd9d`. Worktree detached and tagged orange on disk; local and remote branches deleted.

### `pipeline-diagnostic-popover-swift` — merged 19 May 2026

Swift half of the pipeline diagnostic popover (branch 2 of `docs/design-pipeline-diagnostic-popover.md`). Two new pill states (`.completedPartial`, `.failedWithDiagnostic`) and the popover view consuming `PipelineSummary` fixture v5. Pill label derives from `dominantCategory()` precedence (AUTH > MISSING_BINARY > QUOTA > NETWORK > UNKNOWN); DisclosureGroup hierarchy (≤2 inline, ≥3 collapsible); Copy/Email plaintext following Xcode "Copy Issue" pattern. Debug-only fixture-injection harness for reproducing diagnostic states. Merged via `5e2ff68`. Worktree detached and tagged orange on disk; local branch deleted; remote was never pushed.

### `multi-project-cloud-evicted` — merged 19 May 2026

Phase 3 #10 — collapsed the iCloud-evicted case into a single sidebar state (cloud-arrow glyph in the trailing slot, subtitle qualifier) instead of overloading the `.cantFind` path. Includes a ride-along fix for the re-mount regression where the `cantFind` reason flipped back to `.moved` after a volume came back. Merged via `5876152`. Worktree detached and tagged orange on disk; local branch deleted; remote was never pushed.

### `dev-keychain-signing-fix` — merged 16 May 2026

Switched Debug signing config to Apple Development so Keychain "Always Allow" persists across Cmd+R rebuilds. Two commits (`e5d0e5c`, `0cfab23`) merged via `db3a0f9`. Worktree detached and tagged orange on disk; local branch deleted; remote was never pushed.

### `cantfind-remount-recovery` — merged 16 May 2026

Re-insert ejected volume returns row to `.ready` without regressing `CantFindReason` from `.unmountedVolume` to `.moved`. Single commit (`ceb7366`) merged as `f824e92`. Worktree detached and tagged orange on disk; local branch deleted; remote was never pushed.

### `cantfind-glyphs` — merged 16 May 2026

Specialised the sidebar `cantFind` glyph per `CantFindReason` — distinct glyphs for unmounted volume vs unreachable network vs moved folder. Touched `ProjectAvailability.swift` and `ProjectRow.swift`. Single commit (`a6a164a`) merged as `35272b8`. Worktree detached and tagged orange on disk; local branch deleted; remote was never pushed.

### `keychain-touch-id` — merged 16 May 2026

Biometric ACL on Keychain writes (`KeychainHelper.swift` + `credentials_macos.py`) so subsequent reads offer Touch ID instead of the login-keychain password prompt. Single commit (`68a7eaf`) merged as `15528c1`. Worktree detached and tagged orange on disk; local branch deleted; remote was never pushed.

### `hig-corpus` — merged 16 May 2026

Mirrored Apple HIG locally for agent reference and wired citation discipline into review agents (what-would-gruber-say, ux-critique, a11y-review, what-would-james-bach-say). Added scraper at `scripts/scrape-hig.py`.

### `sidebar-analysed-honesty` — merged 15 May 2026

Gate sidebar "Analysed N min ago" on disk evidence, not pipeline exit code. `PipelineRunner.handleTermination` now derives terminal state from `readManifestState` / `EventLogReader.deriveState` rather than sidecar exit code or log-tail heuristics; `LocateFlow.outputArtefacts` tightened to require `manifest.json` rather than just the `.bristlenose/` directory. Added `PipelineRunnerTerminationTests` coverage. Two commits (`626cca7`, `33c16f2`) merged as `8c83544`. Worktree detached and tagged orange on disk; local branch deleted; remote was never pushed.

### `multi-project-drag-onto` — merged 15 May 2026

Phase 2 item #11 of tf-multi-project — sidebar drag-onto-row adds files to existing project; drag-to-empty-space path remains for the new-project create. Extended `SidebarDropDelegate` hit-test to distinguish row vs empty-space, added `CopyMachinery` (same-volume `clonefile(2)` via `FileManager.copyItem`, cross-volume real copy with progress + Cancel + rollback), title-bar progress pill with ETA, disk-space precheck, drop-affordance highlighting; auto-opens NewFilesSheet on completion. `CopyMachineryTests` pin collision-rename and folder-name preservation behaviour. Built on `multi-project-switch` (merged 14 May). Worktree detached and tagged orange on disk; local branch deleted; remote was never pushed.

### `multi-project-switch` — merged 14 May 2026

Phase 2 core of the desktop multi-project effort: sidebar→server project switch via sidecar restart (#1), verify create-new-project bookmark capture (#2), verify #3 falls out. `ServeManager.switchProject(to:)` orchestrator with escalating `shutdown(timeout:)`, in-flight-run confirm sheet, `Cache-Control: no-store` middleware, and `ProjectBookmarkLease` foundation. Also picked up sidebar drop hit-test work (per-row `.dropDestination` native pattern, drag-onto-project reject for self-drops, toast over alert), the pipeline-failure-trust-UX `outputExists` category + Re-analyse CTA, and a QA pass on `common.cancel` key path plus the "Choose Icon" menu ellipsis trim. 14 commits merged as `baf1896`. Worktree detached and tagged orange on disk; local branch deleted; remote was never pushed.

### `b1-long-audio-quality` — merged 14 May 2026

Whisper hallucination band-aids + speaker propagation surfaces for long audio. Pre-implementation diagnostic against preserved IKEA artefacts showed two of the three originally-reported bugs were not reproducing on current main (role inversion absent; pct_words 0/100 is by-design); the third (mid-stream speaker decay) is architectural — LLM splitter forward-propagates from a 5–8 min sample window. Landed: mlx-whisper params to break the autoregressive loop (`condition_on_previous_text=False`, raised `no_speech_threshold`/`compression_ratio_threshold`), `collapse_adjacent_repeats()` post-processor with natural-doubling protection, INFO log when `split_single_speaker_llm` forward-propagates past the sample window, stale-doc correction in `design-speaker-splitting.md`, regression pins on word-asymmetry + pct_words moderator-exclusion, and a `stages/CLAUDE.md` gotcha on mlx-vs-faster Whisper VAD asymmetry. Single commit (`972821e`) merged as `98ed5a2`. Worktree detached and tagged orange on disk; local branch deleted; remote was never pushed.

### `session-handoff-sentinels` — merged 14 May 2026

Bridge the visibility gap between `/new-feature`, `/end-session`, and `/close-branch`. `/end-session` writes `.claude/last-end-session.json` on successful close-out (carrying `head_sha` for drift detection); `/close-branch` reads it and prompts before archiving a branch that was never end-sessioned or has drifted since. Single commit (`0054fea`) merged as `07506dc`. Worktree detached and tagged orange on disk; local branch deleted; remote was never pushed.

### `ci-version-pinning` — merged 14 May 2026

Single source of truth for Node + Python primary versions via `.tool-versions` at repo root. Replaced 12 hardcoded `python-version: "3.12"` / `node-version: "24"` pins across 5 workflow files with `python-version-file` / `node-version-file` references read natively by `actions/setup-python@v5` and `actions/setup-node@v4`. Closes the drift class that caused v0.15.4/5/6 release failures (Node 20 vs 24 zlib gzip-measurement mismatch). The test matrix in `ci.yml` stays multi-version. Two commits merged as `e1c8083`. Worktree detached and tagged orange on disk; local + remote branches deleted.

### `no-red-ci-merges` — closed 14 May 2026

Two-part chore that landed without using the branch itself. The `CONTRIBUTING.md` "Don't merge red CI" policy bullet went direct-on-main as `c9d1c81` before the branch was started; the GitHub branch-protection rule on `main` was applied via the Settings UI on 14 May (after an earlier attempt didn't save). Required status checks: `ci / lint`, `ci / test (3.10–3.13, ubuntu-latest)`, `ci / frontend-lint-type-test`; Snap / macOS / Release-to-PyPI correctly excluded; admin-bypass escape hatch retained. Worktree detached and tagged orange on disk.

### `tf-phase-1-ux-wins` — merged 14 May 2026

TF alpha phase 1 UX wins — undoable Remove-from-Sidebar (toast + undo) and locate-flow polish, plus a test-philosophy design doc and the `what-would-james-bach-say` reviewer agent. Two commits (`256e8d0`, `958cca5`) merged as `bb54010`. Worktree detached and tagged orange on disk.

### `tf-multi-project` — merged 14 May 2026

Desktop multi-project for TF alpha, Phase 0 only: `projects.json` schema v1 with mandatory `bookmarkData` + `schemaVersion`, `ProjectAvailability` enum + (state, copy, icon, action) triple, ContentView/ProjectIndex/ProjectRow rewired against the new model, new locale keys across all six `desktop.json`, design-doc CLAUDE update, and `ProjectIndexTests` covering the schema-lock contract. Phases 1–3 (Remove-from-Sidebar + Undo, unified can't-find affordance, sidebar→server project switch via sidecar restart, create-new-project with bookmark capture, drag-onto-existing-project, folder watching, cloud-evicted state) remain unshipped — pick up in a fresh branch. Single commit (`60d0e4f`) merged as `e73de11`. Worktree detached and tagged orange on disk.

### `a4-stage-cache-honesty` — merged 12 May 2026

Reorder abandon-check before `mark_stage_complete` so the manifest only records completion when a stage produced usable output. Closes the fake-success-feedback class for s08–s11: a stage that fails to extract any quotes (or themes) no longer caches as "complete" and short-circuits re-runs with stale empty state. Single commit (`0381a06`) merged as `9d2cd2e`. Touched `pipeline.py`, `manifest.py`, `run_lifecycle.py`, `events.py`, s08/s10/s11 stage files, `SECURITY.md`, and three test files plus the pipeline-summary contract fixture. Worktree detached and tagged orange on disk.

### `a2-install-doctor-checks` — merged 12 May 2026

Doctor hard error for missing `[serve]` extras (`check_serve_deps()` in `bristlenose/doctor.py`), install-method-aware fix message (brew vs pipx vs pip) with single-quoted `'bristlenose[serve]'` so zsh doesn't glob the brackets. README gained a "Python 3.10+ required" line plus anaconda caveat. Latent Rich-markup bug fixed at three `console.print` sites that were silently dropping `[serve]` from `_install_hint()` and the fix messages alike. Fix 3 (anaconda runtime detection) dropped as unreachable under `requires-python = ">=3.10"`. Single commit (`ea8162f`) merged as `f10b68e`. Worktree detached and tagged orange on disk.

### `generic-failure-surface` — merged 11 May 2026

Server-rendered HTML status page served by FastAPI for incomplete / failed / cancelled / no-usable-data runs. Single surface for both `bristlenose serve` (CLI browser) and the desktop WKWebView: SPA only mounts when there's renderable data; otherwise the backend intercepts `GET /report/` and serves a state-specific glyph + short + long copy + progressive disclosure. Spun out of `pipeline-completion-trust-ux` review (Findings 7a + 7b). Single commit (`488952d`) merged as `00698f0`. Worktree detached and tagged orange on disk.

### `cli-just-works` — merged 11 May 2026

First-run CLI UX shipped as v0.15.5: preflights (Whisper, ffmpeg, API-key billing, spaCy lazy fetch) all fire between ingest and audio extraction, ending with a "No more questions" line after which no prompt fires for the rest of the run. New `--no-fetch` flag plus `bristlenose doctor --fetch` for offline pre-warm; `BRISTLENOSE_SKIP_PREFLIGHT=1` defence-in-depth env escape; `state.json` (mode 0600) at `~/Library/Application Support/Bristlenose/` caching API-key validation for 24h. New `bristlenose/preflight/` package, `bristlenose/llm/billing_hints.py` registry, and a `preflight.*` i18n namespace in all six locales. Documentation pass: design doc Status table, SECURITY.md preflight bullet + "What Bristlenose writes to your machine" appendix + HF Hub LFS-hash integrity caveat, and the man page (now `mandoc -Tlint` clean) documents the new flags + `state.json` under FILES + exit code 2. Ten commits merged as `372a0aa`. Worktree detached and tagged orange on disk.

### `fix-new-feature-skill` — merged 11 May 2026

Patched four bugs in the `/new-feature` skill discovered during the whos-afraid debug run: moved desktop-binaries probe from Step 8 to Step 9 (no longer reports "skipped" on fresh worktrees), chained `mkdir/ln/echo` with `&&` so failed symlinks don't print "✓", added `hash -r` to the shell preamble to invalidate zsh's cached command lookups after PATH fixes, and added a node-health pre-check to Step 7 so dyld errors surface as actionable remediation instead of a doomed `npm install`. Single commit (`74e59b8`); FF-merged as `9bed5fd`.

### `pipeline-completion-trust-ux` — merged 10 May 2026

Trust-UX layer on top of the auto-refetch correctness slice — refresh button (`RefreshButton.tsx` + test), refetching skeleton overlay (`useRefetching` hook + button/toolbar CSS), post-zero-quotes empty-state messaging across QuoteSections / QuoteThemes / SessionsTable / Dashboard, and cross-island Vitest coverage in `QuotesTab.test.tsx`. Two commits (`9e173e2`, `4f3714e`) merged as `823a801`. Worktree detached and tagged orange on disk. The follow-on `generic-failure-surface` branch picks up the server-rendered failure/empty-state surface flagged in this branch's review (Findings 7a + 7b).

### `sandbox-export-savepanel` — merged 10 May 2026

Routed file-writing exports through `WKDownloadDelegate` + `NSSavePanel` so the sandboxed desktop app actually delivers files; collapsed the React Export modal on desktop in favour of a native accessory view.

### `pipeline-silent-skip-raw-video2` — merged 10 May 2026

Second attempt at making the pipeline fail-soft on raw (non-transcoded) video files. Surfaced structured cause from the events log in the desktop failure pill, added a `Pipeline.run` integration test for the transcribe-all-fail abandon path, plus review fixes (pytest.raises, copy-button feedback, human category label). Three commits (`37e5049`, `d93e5e0`, `4f31b31`) merged as `0804eda`. Worktree detached and tagged orange on disk.

### `spa-pipeline-completion-refetch` — merged 10 May 2026

React SPA auto-refetches project content (quotes, sessions, codebook) when a pipeline run completes, removing the tab-away-and-back workaround. Single commit `7136890` on the branch; merged to main as `82c8b45`. Worktree detached and tagged orange on disk; correctness slice that `pipeline-completion-trust-ux` _(merged 10 May 2026)_ built on.

### `pipeline-silent-skip-raw-video` — closed 8 May 2026

Intended to make the pipeline fail-soft on raw video files. Branch was created on 8 May 2026 but no commits were ever made — closed same-day as part of routine cleanup. Worktree detached and tagged orange on disk; no work to rescue.

### `pipeline-runner-sidecar-mode` — merged 2 May 2026

`PipelineRunner.spawn()` migrated to `SidecarMode.resolve(...)` (same path as `ServeManager`); `findBristlenoseBinary()` deleted from `BristlenoseShared.swift`. Bundled sidecar (`desktop/sidecar_entry.py`) gained a `run` subcommand alongside `serve`/`doctor`, gated on `_BRISTLENOSE_HOSTED_BY_DESKTOP=1` (confused-deputy mitigation). 5 new pytest cases in `tests/test_sidecar_entry.py`. Merged via PR #96 (`0e0157e`); cleared the last engineering blocker before the sandbox-triage checkpoint.

### `bundled-binary-helper` — closed 2 May 2026

S2 Track A narrow branch — fix the ffprobe/ffmpeg PATH-stripped sandbox blocker. Under the macOS sandbox the bundled sidecar couldn't find Homebrew binaries on the inherited PATH; bundled-binary helper / explicit resolution path so video probing and audio extraction work end-to-end. Code landed direct-on-main as `670a002` (plus review-park `677755a`); branch itself was behind main at close time, nothing to rescue. Tests at `tests/test_bundled_binary.py`.

### `cli-message-kinds` — closed 7 May 2026

Refactor of `_print_step` family in `pipeline.py` and ad-hoc tinted `console.print()` calls in `cli.py` to consume `MessageKind` from `bristlenose/ui_kinds.py` — glyph + colour now come from the canonical 5-kind table (`SUCCESS / INFO / WARNING / ERROR / SKIPPED`) rather than being hardcoded per-call site. Aligned CLI with popover and toast vocabulary; no user-visible behaviour change. Code landed direct-on-main as `0a0c8d5` (preceded by `1ab06bf` MessageKind taxonomy + duration_ms in summary contract).

### `pipeline-diagnostic-pill` — closed 7 May 2026

Started for the Swift side of the diagnostic-pill feature (two new pill states + popover bodies consuming `PipelineSummary`). What actually shipped via this branch: preparatory contract work — `MessageKind` taxonomy, `design-pipeline-diagnostic-popover.md`, fixture-v3 truncation-marker lock, fixture-v4 session_id realignment. Tip `913a480` reachable on main; the Swift pill states themselves were not implemented on this branch (deferred / moved on).

### `pipeline-summary-events` — merged 7 May 2026

Python half of the failure-taxonomy / diagnostic-pill effort: structured `StageFailure` / `StageOutcome` / `PipelineSummary` Pydantic models on terminus events; new `Cause` categories (`MISSING_INPUT`, `MISSING_BINARY`); `PipelineAbandonedError` for empty-data runs (s05/s09 abandon checkpoints, s11 soft-stage); path sanitiser in cause messages; `STAGE_FAILED_MAX = 10` truncation at write time; `duration_ms` populated on every outcome; 8 contract round-trip tests against `tests/fixtures/pipeline-summary-contract.json`. Locked the Python emitter side of the schema contract consumed by `pipeline-diagnostic-pill`. FF merged as `efe4064` (4 commits).

### `serve-importer-reimport-on-completion` — merged 7 May 2026

Re-import on pipeline `run_completed` event in serve mode so the UI updates from 0/0 once the pipeline finishes. Single commit `02daeee`; merge commit `7eae1c0`.

### `sandbox-mlx-whisper-ffmpeg-path` — merged 7 May 2026

Prepend bundled FFmpeg dir to `PATH` in `bristlenose/__init__.py` so `mlx_whisper`'s internal subprocess shell-out resolves `ffmpeg`/`ffprobe` under the macOS App Sandbox.

### `locale-system-delegation` — merged 5 May 2026

Delete in-app language picker on desktop; delegate locale to System Settings → Apps → Bristlenose (`Bundle.preferredLocalizations` + `UIPrefersShowingLanguageSettings`). Web/CLI serve picker unchanged.

### `i18n-text-sweep` — merged 5 May 2026

Sweep up English literals missed by `i18n-llm-settings`: LLMProvider helpers, TranscriptionSettingsView, BuildInfoSheet Close, default New Project name.

### `sandbox-mimetypes-init` — merged 6 May 2026

Empty `mimetypes.knownfiles` in `bristlenose/__init__.py` so CPython's lazy `mimetypes.init()` skips `/etc/apache2/mime.types` and friends under the macOS App Sandbox. Real fix for the `/static/*.js` 500 the earlier `sandbox-staticfiles-fix` addressed at the wrong layer. Python 3.12.13's `init()` does `files = knownfiles + list(files)` when `files` is non-None, so `init([])` doesn't help — emptying `knownfiles` itself is the only escape hatch. Verified end-to-end under sandbox-on Debug.

### `sandbox-staticfiles-fix` — merged 5 May 2026

Unblock desktop alpha — fixed StaticFiles 500 under sandbox by serving the React bundle via in-memory `read_bytes` instead of mmap.

### `sandbox-ps-libproc-swap` — merged 5 May 2026

Unblock desktop alpha — replaced `/bin/ps` subprocess in `bristlenose/run_lifecycle.py` with libproc `proc_pidinfo` (2nd of 2 sandbox blockers).

### `bundle-trim-s1-s2` — merged 4 May 2026

S1 + S2 of the sidecar bundle audit: excluded `mlx_whisper.torch_whisper` from the PyInstaller spec and rebuilt with a dedicated `.venv-sidecar/` on every build, keeping contributor-venv drift out of the bundle. 771 MB → 645 MB; C0 baseline restored. Deeper torch eviction deferred to S3. Merge commit `801065b`.

### `i18n-llm-settings` — merged 5 May 2026

Extracted hardcoded English from `LLMSettingsView.swift` + `OllamaSetupSheet.swift`; filled `desktop.json` across all 6 locales (en/es/fr/de/ko/ja). Single commit (`9c69f59`); merge commit `c023f7d`.

### `bundle-trim-s3` — merged 4 May 2026

S3 of the sidecar PyInstaller bundle audit — evicted torch + onnxruntime + transitive helpers (`huggingface_hub.serialization._torch`, `huggingface_hub.hub_mixin`, `scipy._lib.array_api_compat.torch`, `torchgen`, `torchvision`, `functorch`) via PyInstaller `excludes`. Bundle 645 → 427 MB (−218 MB). Surfaced and fixed two pre-existing mlx packaging bugs (libjaccl.dylib + mlx.metallib, mlx_whisper/assets/) via `collect_all("mlx")` and `collect_all("mlx_whisper")`. End-to-end transcription smoke green in the bundled sidecar. Merge commit `5fbc6aa`.

### `bundled-tls-config` — merged 2 May 2026

S2 Track A narrow branch — redirected the bundled sidecar's TLS to certifi under sandbox, addressing an A1c sandbox-violation finding. Single commit (`aa6111f`) touching `BristlenoseShared.swift`, `PipelineRunner.swift`, `ServeManager.swift`, plus `SslEnvironmentTests.swift`. Merge commit `7240675`.

### `track-c-c1-bundled-sidecar` — merged 18 Apr 2026 (initial), retest 29 Apr, closed 1 May 2026

S2 Track C C1 — PyInstaller bundling pipeline for the macOS app sidecar. Restored `fetch-ffmpeg.sh` and `build-sidecar.sh` (adapted from `desktop/v0.1-archive/`), verified `bristlenose-sidecar.spec` datas, wired `check-bundle-manifest.sh` into `build-all.sh`, added Xcode "Copy Sidecar Resources" Build Phase, updated `SidecarMode.resolve` default branch to return `.bundled(...)` with fail-loud error card. Fresh-worktree retest 29 Apr (commit `f0d1ee2`) confirmed end-to-end green and closed two ergonomic gaps: declared `pyinstaller` as a `[desktop]` extra, quietened the Xcode "no-outputs" warning. Three doc edits from the retest recovered to main on close (commit `b40b178`).

### `track-a-a2-network-server` — merged 1 May 2026

S2 Track A A2 — granted `com.apple.security.network.server` (via `ENABLE_INCOMING_NETWORK_CONNECTIONS = YES` in Debug pbxproj) so the bundled sandboxed sidecar can `bind()` 127.0.0.1. Side-effect: `desktop/scripts/reset-sandbox-state.sh` dev helper for libsecinit/secinitd EXC_BREAKPOINT recovery. Three design docs trued. Merged via PR #94 (commit `63fbf0a`) alongside A6 (sandbox-native sidecar lifecycle, commit `39f39c0`).

### `first-run` — merged 1 May 2026

S2 Track B Branch 1 — first-run experience for the macOS app (cold-open → AI disclosure → API key → empty-state). Beat 1 (`BootView.swift` + `WelcomeView.swift` two-variant pattern, worktree-aware locale loading), Beat 3 (round-trip API key validation in `LLMSettingsView`), Beat 3b (`OllamaSetupSheet` state machine for local AI install), CSS fall-back fix for projects with no rendered assets (`_mount_prod_report`), plus design-doc truing pass and 5 HIGH review fixes. 14 commits. Merge commit `b4cc95c`.

### `japanese-translation` — merged 1 May 2026

Finished the Japanese (`ja`) locale: bulk-translated ~614 stub strings across 8 namespace files in `bristlenose/locales/ja/`, seeded `glossary.csv` with 83 `ja` rows, and added 11 i18n keys to the tag sidebar across all 6 locales. Alpha gate cleared. 10 commits.

### `sidecar-signing` — merged 28 Apr 2026

S2 Track C — PyInstaller sidecar codesigning + Hardened Runtime, plus the C2/C3/C4/C5 alpha-readiness work that grew out of it: sandbox-safe API-key injection (Swift Keychain → env vars, no Python `/usr/bin/security` exec), libproc-based zombie cleanup (`proc_listpids` + `proc_pidfdinfo` + `proc_pidpath` — replaces `lsof`/`/bin/ps`, sandbox-blocked), `os.Logger` throughout, key-shape stdout redaction, `SidecarMode.resolve` + dev escape-hatch env vars, three Xcode schemes, privacy manifests for host + sidecar, supply-chain provenance (`THIRD-PARTY-BINARIES.md` + auto-regen script), bundle completeness gates (`check-bundle-manifest.sh`, `bristlenose doctor --self-test`), and the full doc reconciliation across C2/C3/C4/C5 via `/true-the-docs`. 59 commits. Merge commit `a9e5450`.

### `cost-and-time-forecasts` — merged 28 Apr 2026

LLM call telemetry + data-driven pipeline cost forecast. Slice A: telemetry schema (`bristlenose/llm/telemetry.py`), append-only JSONL writer, prompt frontmatter. Slice B: contextvars + `record_call` wired into pipeline hot path and serve-mode autocode/elaboration. Slice C: data-driven cost forecast replacing prior heuristic estimates, with `cohort-baselines.json` + `cohort_normalise.py`. Sibling design doc `design-llm-pricing-fetch.md` for keeping price estimates current (followup PR). Merge commit `98df507`.

### `alpha-telemetry` — merged 26 Apr 2026

Phase 1 plumbing only for Level 0 tag-rejection telemetry — TestFlight alpha groundwork. Added `telemetry.php` (PHP endpoint patterned on `feedback.php`, deployed alongside it on DreamHost — both live in the separate `bristlenose-website` private repo as of 2 May 2026), extended `/api/health` with telemetry payload, dev stub endpoint `POST /api/_dev/telemetry`, `DEFAULT_TELEMETRY_URL` and extended `HealthResponse` in `frontend/src/utils/health.ts`. Phases 2–4 (event emission, SQLite buffer, SwiftUI sheets, Settings Privacy screen, prompts/versions.jsonl) deferred to post-TestFlight. Spec: [`docs/methodology/tag-rejections-are-great.md`](methodology/tag-rejections-are-great.md). Merge commit `c5a7f61`.

### `port-v01-ingestion` — merged 26 Apr 2026

S2 Track B — re-introduced pipeline invocation (`bristlenose run`) into the v0.2 multi-project desktop shell. New `PipelineRunner.swift` (sibling to `ServeManager`) with state enum, generation counter, orphan cleanup; `PipelineProgressView` in-project UI; drop→run wiring; serve-when-ready policy. Also landed Phase 1f / 4a-pre — append-only `pipeline-events.jsonl`, structured `Cause` (10 categories), honest cost estimates, stranded-run reconciliation, desktop `EventLogReader`. Shipped as v0.15.0. Merge commit `e781ebe`.

### `ci-cleanup` — merged 18 Apr 2026

S2 Step 0 — CI cleanup. Cleared the three P3 e2e regressions parked during v0.14.5 release-unblock (autocode 404 allowlisted, codebook 404 allowlisted as deferred-fix [S3], `_BRISTLENOSE_AUTH_TOKEN` wired into the main e2e workflow) and flipped the e2e gate back to blocking. First CI run post-flip passed green in 19m44s. Bonus: Analysis page "Show all N quotes" `<a>`→`<button>` fix, `playwright.config.ts` shell-quoting fix, `e2e/ALLOWLIST.md` register (3 categories, 4 entries, `// ci-allowlist: CI-A<N>` code markers), `SECURITY.md` auth-token honesty update, new `bristlenose doctor` env-bleed check. Two follow-ups deferred with reminders: Option B auth-token gate (16 May) and Python floor bump to 3.12 (9 May). Squash-merged as `0a8345b` via PR #86. 4 commits → 1 squash commit.

### `languages` — merged 24 Mar 2026

Full i18n activation: wired `useTranslation()` across all React components, added ~100 new keys to all 5 locale files (en, es, fr, de, ko), plus Japanese stubs. Weblate integration, glossary, CI validation, translator guide, machine translation QA checklist, en→en-GB locale mapping. Replaced ~180 hardcoded English strings in JSX with `t()` calls. 15 commits.

### `macos-app` — merged 22 Mar 2026

Native macOS desktop app — SwiftUI shell wrapping the React SPA in a WKWebView. Two-column NavigationSplitView, native toolbar and menu bar (~89 items), bridge protocol (Swift ↔ React), `bristlenose serve` subprocess lifecycle, app icon with Liquid Glass layered artwork, Settings window (Appearance, LLM, Transcription tabs), provider icons. v0.1 desktop app archived to `desktop/v0.1-archive/`. 11 commits.

### `analysis-matrices-heatmaps-pane` — merged 20 Mar 2026

DevTools-style collapsible bottom inspector panel in the Analysis tab. Heatmap matrices (section × sentiment, theme × sentiment, codebook group matrices) in a resizable bottom pane. Collapsed by default with grid-icon handle bar; opens via click, drag, or `m` shortcut. Signal card selection syncs with inspector source tabs. Tooltip flips above when near viewport bottom. New files: `InspectorPanel.tsx`, `InspectorStore.ts`, `useVerticalDragResize.ts`, `inspector.css`. 4 commits.

### `settings-modal` — merged 18 Mar 2026

Settings modal dialog (⌘, / gear icon) with sidebar nav. Help modal with genericised ModalNav organism. WCAG 2.1 AA accessibility audit for quotes page. About tab section components (AboutSection, CodebookSection, ContributingSection, DesignSection, DeveloperSection, SignalsSection). Phase 1 modal shell and General page. Reusable `ModalNav` component for future modals.

### `render-refactor` — merged 11 Mar 2026

Break up `render_html.py` (2,903 lines) into `bristlenose/stages/s12_render/` package with 8 submodules: `theme_assets.py`, `html_helpers.py`, `quote_format.py`, `sentiment.py`, `dashboard.py`, `transcript_pages.py`, `standalone_pages.py`, `report.py`. Added `DeprecationWarning` to `render_html()`. Updated all imports (3 production, 11 test files) and ~99 doc references across 34 files. No behaviour change — pure structural refactor.

### `responsive-playground` — merged 10 Mar 2026

Responsive layout playground and sidebar overlay mode. Responsive CSS grid for quote cards, sidebar TOC overlay with hover-trigger, minimap component, dev-only responsive playground (FAB toggle, device presets, type scale previews, HUD). New components: `Minimap`, `PlaygroundFab`, `PlaygroundHUD`, `ResponsivePlayground`, `TypeScalePreview`. New hook: `useTocOverlay`. New store: `PlaygroundStore`. Design docs: `design-sidebar-playground.md`, `design-minimap.md`, mockup `mockup-minimap.html`. Rollback tag: `pre-responsive-playground-merge`.

### `sentiment-tags` — merged 10 Mar 2026

Unify sentiment badges (frustration, confusion, doubt, surprise, satisfaction, delight, confidence) into the codebook framework system. Sentiment framework YAML, auto-import on first serve, auto-tagging from pipeline sentiment field. Deduplicates 4 overlapping tags from UXR codebook. Adds "sentiment" colour set. Suppresses legacy AI badge when codebook tag exists.

### `shall-we-try-it` — merged 3 Mar 2026

Throwaway branch to test the improved `/new-feature` and `/close-branch` skills after reliability fixes. No code changes.

### `sidebar` — merged 1 Mar 2026

Dual-sidebar layout for the Quotes tab. Left sidebar: TOC with scroll-spy (sections + themes). Right sidebar: tag filter with codebook tree, eye toggles for badge hiding (persisted to localStorage), drag-to-resize with snap-close. 5-column CSS grid, keyboard shortcuts (`[`, `]`, `\`, `⌘.`). Quotes-tab-only scope — other tabs unaffected. 3 feature commits + merge-from-main conflict resolution (AppLayout.tsx: SidebarLayout + ExportDialog coexistence). New files: 2 CSS organisms, 6 components, 2 hooks, 1 store, 1 design doc. 845 Vitest tests (60 files), 1856 Python tests.

### `stabilise-ci` — merged 1 Mar 2026

Frontend CI hardening. Added `frontend-lint-type-test` job to GitHub Actions (ESLint, TypeScript typecheck, Vitest on Node 20). ESLint step is `continue-on-error: true` pending fix of 84 pre-existing lint errors. Also added `CODEX.md` working agreement.

### `react-router` — merged 28 Feb 2026

React migration Steps 5–9. Step 5: React Router SPA with pathname-based routing, `AppLayout` (NavBar + Outlet), 8 page wrappers, backward-compat navigation shims. Step 6: `PlayerContext` with popout window lifecycle, `seekTo`, glow sync. Step 7: `FocusContext` with j/k navigation, multi-select, bulk actions, `useKeyboardShortcuts` hook. Step 8: Vanilla JS modules stripped from serve path (17 modules frozen, `main.js` boot array no-ops). Step 9: Full React app shell — `Header`, `Footer`, `HelpModal`, `AppLayout`; serve mode serves SPA directly, no more `_transform_report_html()` marker substitution. Also: video player links on sessions page and dashboard, importer source-path subdirectory fix, speaker name sizing, word-level timing plumbing. 17 commits, 85 files, +6063/−1066 lines, 717 Vitest tests (55 files), 1813 Python tests.

### `react-settings-about` — merged 25 Feb 2026

Settings panel and About panel migrated from vanilla JS to React islands (React migration steps 1 & 2). `SettingsPanel.tsx` and `AboutPanel.tsx` islands, QuotesStore module-level store with `useSyncExternalStore`, comment-marker injection in `render_html.py` and `app.py`.

### `split-badge` — merged 24 Feb 2026

Two-tone split speaker badges (Treatment E). Left half = speaker code in mono on badge-bg, right half = participant name in body font on quote-bg. Settings toggle (code+name / code-only). Em-dash removed from quote attribution. Always-on sticky transcript header with session selector. Serve mode: inline Jinja2 transcripts stripped, session links navigate to React transcript pages instead of vanilla JS drill-down.

### `context-expansion` — merged 24 Feb 2026

Quote context expansion on the quotes page. Hover over a quote's timecode to reveal chevron arrows (⌃/⌄); click to progressively disclose surrounding transcript segments inside the quote card. Speaker badge conditionally hidden when context segment is same speaker. New components: `ContextSegment`, `ExpandableTimecode`. CSS atom: `context-expansion.css`. Expansion state managed via reducer in `QuoteGroup`, transcript cache wired through `QuoteSections`/`QuoteThemes`.

### `serve` — merged 17 Feb 2026

`bristlenose serve` command — FastAPI + SQLite + React islands architecture. 22-table domain schema, data sync API, sessions/quotes/dashboard/codebook endpoints. 16 React primitives (182 Vitest tests), 5 React islands (SessionsTable, Dashboard, QuoteSections, QuoteThemes, CodebookPanel). Full codebook CRUD with drag-and-drop, inline editing, merge, delete. Desktop app scaffold (SwiftUI macOS shell, sidecar architecture). 330+ Python serve tests across 8 files.

### `project-dashboard` — merged 13 Feb 2026

At-a-glance project dashboard redesign. Clickable stats, featured quotes, session rows, cross-tab navigation. Compact layout with paired stats, slim session table, linked sections/themes. Non-scrolling single-viewport design for the Project tab.

### `analysis` — merged 11 Feb 2026

Analysis page with signal cards ranked by composite score (concentration × agreement × intensity), section × sentiment and theme × sentiment heatmaps with adjusted standardised residuals, dark mode support. Full pipeline integration: Python math module (`bristlenose/analysis/`), standalone `analysis.html` with injected JSON, client-side JS rendering. 97 tests across 4 files. Future phases in `docs/design-analysis-future.md`.


### `codebook-tag-filter` — merged 11 Feb 2026

Tag filter dropdown uses codebook colours and hierarchy. Tags grouped into tinted sections matching codebook page. Badge-styled labels via `createReadOnlyBadge()` in `badge-utils.js`. Search matches both tag names and group names.

### `navigation` — merged 11 Feb 2026

Global tab bar navigation for the HTML report. 7 tabs (Project, Sessions, Quotes, Codebook, Analysis, Settings, About). Sessions tab with grid → inline transcript drill-down. Project tab dashboard with stats, featured quotes, sections/themes tables, sentiment chart. Speaker cross-navigation from quote cards to session timecodes. Full ARIA/accessibility. `global-nav.js`, `global-nav.css`, `global_nav.html`, `session_table.html` added; `render_html.py` extended with ~800 lines; `main.js` boot refactored to `_bootFns` array.

### `jinja2-migration` — merged 9 Feb 2026

Phase 1 Jinja2 template extraction: footer, document shell, report header, quote card. Adds `jinja2>=3.1` dependency, comparison script (`scripts/compare-render.sh`), 12 parity tests. `render_html.py` reduced by ~170 lines. Output byte-identical. Phase 2+ (toolbar, sentiment chart, coverage, player) tracked in `docs/jinja2-migration-plan.md`.

### `transcript-annotations` — merged 9 Feb 2026

Transcript page annotations: quote highlighting with margin labels, tag badges, span bars for quote extent, citation toggle. Also: badge abstraction (`badge-utils.js`), delete circle restyle (white floating chip), design-system reference docs (`docs/design-system/`).

### `codebook` — merged 7 Feb 2026

Interactive codebook page with tag taxonomy management. Phases 1–3: OKLCH colour tokens, toolbar redesign, standalone `codebook.html` with drag-and-drop, inline editing, group CRUD, cross-window sync. Also: shared `escapeHtml()`, `showConfirmModal()`, `toggle()` in modal infrastructure.

---

## Coordination Notes for Claude Sessions

### Reading this file

Before making changes, run:
```bash
git fetch origin
cat docs/BRANCHES.md
```

### Conflict-prone files

These files are frequently edited by multiple features. Take extra care:

| File | Why it's hot |
|------|-------------|
| `bristlenose/stages/render_html.py` | All UI features touch this |
| `bristlenose/theme/js/main.js` | Boot sequence for all JS modules |
| `bristlenose/cli.py` | All new commands land here |
| `TODO.md` | Everyone updates it |
| `CLAUDE.md` | Everyone updates it |

### Safe editing patterns

1. **New files are safe** — if your feature adds a new module (`export.js`, `help-overlay.css`), no conflict risk
2. **Append-only changes are safe** — adding a new function to an existing file rarely conflicts
3. **Structural changes are risky** — refactoring existing code will conflict with parallel work

### When you encounter a conflict

1. Don't resolve it yourself — note it in the merge plan
2. Ask the user which version to keep
3. Or wait for the other branch to merge first, then rebase

### Communication pattern

If you need to signal something to a future Claude session:
1. Add a note to this file under your branch
2. Or create a `docs/notes-{branch-name}.md` for longer notes
3. Reference it in `CLAUDE.md` under "Reference docs"
