# Active Feature Branches

This document tracks active feature branches to help multiple Claude sessions coordinate without conflicts.

**Updated:** 7 May 2026 (merged `pipeline-summary-events` into main as `efe4064`)

---

## Branch Kinds (merge intent)

Every branch declares a **Kind** that encodes what it's *for* and what should happen to it at end of life:

| Kind | What it produces | End-of-life |
|------|------------------|-------------|
| **feature** | Code intended for main | Merge / PR-and-squash |
| **diagnostic** | Inventory, reports, reproductions — fixes happen in *other* branches | **Discard** when narrow-fix children land. The branch itself never merges; its useful output already left via siblings |
| **spike** | Exploratory throwaway — proves or disproves an approach | Discard. Cherry-pick selectively if a commit's worth keeping |
| **chore** | Small ephemeral work (release tooling, doc reconciliation, dep bumps) | Merge or discard, low ceremony |
| **parked** | On hold; may resume later | Stays on disk + remote until revived or formally retired |

When opening a new branch, declare its Kind in the table below. When closing one, the Kind tells you whether to merge or just `/close-branch`.

## Worktree Convention

Each active feature branch gets its own **git worktree** — a full working copy in a separate directory. This lets multiple Claude sessions work on different features simultaneously without interfering.

**Directory pattern:** `/Users/cassio/Code/bristlenose_branch <name>`

| Directory | Branch | Kind | Purpose |
|-----------|--------|------|---------|
| `bristlenose/` | `main` | — | Main repo, releases, hotfixes |
| `bristlenose_branch responsive-signal-cards/` | `responsive-signal-cards` | feature | Responsive signal cards (worktree never opened — BRANCHES entry is a placeholder) |
| `bristlenose_branch symbology/` | `symbology` | parked | § ¶ ❋ Unicode prefix symbols (see Historical experiments) |
| `bristlenose_branch highlighter/` | `highlighter` | parked | Highlighter feature (see Historical experiments) |
| `bristlenose_branch living-fish/` | `living-fish` | parked | Animated logo (see Historical experiments) |
| `bristlenose_branch drag-push/` | `drag-push` | parked | Sidebar push-mode drag (see Historical experiments) |
| `bristlenose_branch pipeline-summary-events/` _(merged)_ | `pipeline-summary-events` | feature | Structured per-stage failure summaries; abandon path for empty-data runs; new Cause categories — merged 7 May 2026 (`efe4064`) |
| `bristlenose_branch pipeline-diagnostic-pill/` | `pipeline-diagnostic-pill` | feature | Two new pill states (.completed_partial, .failed_with_diagnostic) with rich popover bodies showing per-session failure causes; consumes the structured PipelineSummary from Branch 1 |





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
| `sandbox-debug` _(closed)_ | _removed 2 May 2026_ | local only — diagnostic, never pushed |
| `bundled-binary-helper` _(closed)_ | `bristlenose_branch bundled-binary-helper/` _(detached, on disk)_ | local only — code on main as `670a002` |
| `bundled-tls-config` _(merged)_ | `bristlenose_branch bundled-tls-config/` _(detached, on disk)_ | merged to main on 2 May 2026 (`7240675`) |
| `pipeline-runner-sidecar-mode` _(merged)_ | `bristlenose_branch pipeline-runner-sidecar-mode/` _(detached, on disk)_ | merged via PR #96 (`0e0157e`) on 2 May 2026 |
| `responsive-signal-cards` | `bristlenose_branch responsive-signal-cards/` | local only |
| `i18n-llm-settings` _(merged)_ | `bristlenose_branch i18n-llm-settings/` _(detached, on disk)_ | merged to main 5 May 2026 (`c023f7d`) |
| `symbology` _(parked)_ | `bristlenose_branch symbology/` | `origin/symbology` |
| `highlighter` _(parked)_ | `bristlenose_branch highlighter/` | `origin/highlighter` |
| `living-fish` _(parked)_ | `bristlenose_branch living-fish/` | `origin/living-fish` |
| `drag-push` _(parked)_ | `bristlenose_branch drag-push/` | local only |
| `pipeline-summary-events` _(merged)_ | `bristlenose_branch pipeline-summary-events/` _(detached, on disk)_ | merged to main 7 May 2026 (`efe4064`) |
| `pipeline-diagnostic-pill` | `bristlenose_branch pipeline-diagnostic-pill/` | local only |




---

## Active Branches

---

### `pipeline-diagnostic-pill`

**Kind:** feature — code lands on main; consumes structured PipelineSummary from `pipeline-summary-events`
**Status:** Just started
**Started:** 7 May 2026
**Worktree:** `/Users/cassio/Code/bristlenose_branch pipeline-diagnostic-pill/`
**Remote:** local only (push when ready)

**What it does:** Two new pill states (`.completed_partial`, `.failed_with_diagnostic`) with rich popover bodies showing per-session failure causes; consumes the structured `PipelineSummary` from Branch 1 (`pipeline-summary-events`).

**Files this branch will touch:**
- `desktop/Bristlenose/Bristlenose/PipelineSummary.swift`
- `desktop/Bristlenose/Bristlenose/PipelineRunner.swift`
- `desktop/Bristlenose/Bristlenose/EventLogReader.swift`
- `desktop/Bristlenose/Bristlenose/PipelineActivityItem.swift`
- `desktop/Bristlenose/Bristlenose/ProjectRow.swift`
- `desktop/Bristlenose/BristlenoseTests/EventLogReaderTests.swift`

**Potential conflicts with other branches:**
- `pipeline-summary-events` — direct upstream dependency. This branch consumes the `PipelineSummary` type that branch produces; coordinate merge order (Branch 1 first) and expect overlap on `PipelineSummary.swift` / `EventLogReader.swift`.
- Other active branches — no overlap (desktop Swift surface only).

---

### `pipeline-summary-events` (merged)

**Kind:** feature _(merged)_
**Status:** Merged 7 May 2026 as `efe4064` (4 commits FF onto main)
**Started:** 7 May 2026
**Worktree:** `/Users/cassio/Code/bristlenose_branch pipeline-summary-events/` _(still on disk for backup; close via `/close-branch` when ready)_
**Remote:** local only — never pushed

**What shipped:** Python half of the failure-taxonomy / diagnostic-pill effort. New `Cause` categories (`MISSING_INPUT`, `MISSING_BINARY`); `StageFailure` / `StageOutcome` / `PipelineSummary` Pydantic models on terminus events with backward-compatible decode; `PipelineAbandonedError` so empty-data runs no longer write a fake-empty report; `RunHandle.set_summary()` mirroring `set_cost()`; `_dominant_cause` helper picks the most common failure category with non-retryable tie-breakers; abandon checkpoints after s05 (every transcription failed) and s09 (every quote-extraction LLM call failed); soft-stage at s11 (themes failure recorded but never abandons); `MISSING_BINARY` categorisation rule for bare-name `FileNotFoundError`. Plus three review-fix commits: explicit cache-hit `_cached_q_count` (drops a brittle `dir()` reflection), path sanitiser in `categorise_exception` so audio filenames don't leak to `pipeline-events.jsonl`, and `STAGE_FAILED_MAX = 10` truncation at write time keeping terminus lines under Swift's 64 KB read window. After a /usual-suspects review and a fixture-v3 reconciliation pass, `duration_ms` populated on every `StageOutcome`; eight new contract round-trip tests in `test_events.py` covering all four scenarios in `tests/fixtures/pipeline-summary-contract.json`.

**Why it mattered:** Cleared the silent-empty-report failure mode that surfaced during the 7 May desktop sandbox walk; locked the Python emitter side of the schema contract that the Swift `pipeline-diagnostic-pill` branch consumes.

**Files touched:**
- `bristlenose/events.py` (+131) — models + truncation writer
- `bristlenose/run_lifecycle.py` (+97) — abandon catch + path sanitiser + categoriser extension
- `bristlenose/pipeline.py` (+255) — abandon checks + `_summary` accumulator + `_dominant_cause` + `duration_ms` plumbing
- `bristlenose/models.py` (+5) — `PipelineResult.summary`
- `bristlenose/cli.py` (+5) — `set_summary` plumbing in run / analyze / transcribe-only
- `bristlenose/stages/s05_transcribe.py` (+38), `s09_quote_extraction.py` (+38), `s11_thematic_grouping.py` (+21) — `(results, StageOutcome)` tuple returns
- `tests/test_pipeline_abandon.py` (NEW, 225 lines, 6 cases)
- `tests/test_events.py` (+322, 50 cases incl. 8 contract round-trip)
- `tests/test_run_lifecycle.py` (+70)
- `tests/test_llm_concurrency.py` (+6) — tuple-unpack updates for refactored callers
- `docs/design-pipeline-resilience.md` (+15) — 2026-05-07 changelog entry
- `CHANGELOG.md` (+1) — Unreleased bullet

**Potential conflicts with other branches:**
- No active branches currently touch `events.py`, `run_lifecycle.py`, or pipeline stages — clean territory.
- `bundled-binary-helper` (already merged via `670a002`) is conceptually adjacent (binary discovery) but file-disjoint.

**Follow-up branches** (Session 1 hand-off):
- `cli-message-kinds` (planned, ~30 min) — refactor `_print_step` family in `bristlenose/pipeline.py` to consume `MessageKind` from `bristlenose/ui_kinds.py` (added on main as `1ab06bf`); audit ad-hoc tinted `console.print()` calls in `bristlenose/cli.py`. Originally Session 2's §0 ask for this branch; punted to its own branch to keep this one's narrative tight. Doesn't block any other work — CLI keeps emitting `[green]✓[/green]` regardless. Handoff prompt in the gitignored handoffs area.

---

### `pipeline-runner-sidecar-mode` (merged)

**Kind:** feature _(merged)_
**Status:** Merged 2 May 2026 via PR #96 (`0e0157e`)
**Started:** 1 May 2026
**Worktree:** `/Users/cassio/Code/bristlenose_branch pipeline-runner-sidecar-mode/` (still on disk for backup; close via `/close-branch` when ready)
**Remote:** branch deleted by GitHub on merge

**What shipped:** `PipelineRunner.spawn()` migrated to `SidecarMode.resolve(...)` (same path as `ServeManager`); `findBristlenoseBinary()` deleted from `BristlenoseShared.swift` (zero remaining callers); bundled sidecar (`desktop/sidecar_entry.py`) accepts `run` as a third subcommand alongside `serve` and `doctor`, gated on env var `_BRISTLENOSE_HOSTED_BY_DESKTOP=1` (confused-deputy mitigation, belt-and-braces post-A2). 5 new pytest cases in `tests/test_sidecar_entry.py`.

**Why it mattered:** Cleared the last engineering blocker for the sandbox-triage checkpoint. Beats 6→13 now reachable under sandbox-on Debug for the first time. Next session picks up from the gitignored handoff prompt in the sandbox-debug worktree.

---

### `bundled-binary-helper`

**Kind:** feature — code already on main as `670a002` (and review-park `677755a`); worktree pending close
**Status:** Just started
**Started:** 2 May 2026
**Worktree:** `/Users/cassio/Code/bristlenose_branch bundled-binary-helper/`
**Remote:** local only (push when ready)

**What it does:** S2 Track A narrow branch — fix the ffprobe/ffmpeg PATH-stripped sandbox blocker that surfaced in the fossda pipeline log. Under the macOS sandbox, the bundled sidecar can't find Homebrew binaries on the inherited PATH; needs a bundled-binary helper / explicit resolution path so video probing and audio extraction work end-to-end.

**Files this branch will touch:**
- `bristlenose/utils/video.py` (likely — ffmpeg/ffprobe invocation site)
- Possibly `desktop/bristlenose-sidecar.spec` (bundled binary datas)
- Possibly `bristlenose/doctor.py` (PATH/binary discovery checks)
- TBD as work progresses

**Potential conflicts with other branches:**
- `sandbox-debug` — adjacent territory (sandbox triage); likely complementary, not conflicting
- Other active branches (`responsive-signal-cards`, parked experiments) — no overlap

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
