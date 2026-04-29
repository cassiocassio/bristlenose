# Desktop UX iteration — backlog from port-v01-ingestion

**Status:** captured 26 Apr 2026 from QA findings during the ingestion port (`port-v01-ingestion` branch). Most items were observed during 20–25 Apr QA on Bristlenose.app dev builds while testing the end-to-end ingestion flow — and explicitly **deferred** because the goal of branch B was "verify ingestion works", not "polish the desktop app".

**Source.** `~/.claude/plans/gentle-brewing-penguin.md` (Followups + QA findings sections, 1100+ lines). This doc is the **scannable, themed extract** — for the full diagnosis with file:line refs, spindumps, and conversation transcripts, see the source.

**When this gets done.** Next desktop UX iteration. User flagged "needs to happen sooner rather than later" — likely between alpha (mid-May) and public beta (Jun). Pairs naturally with Sprint 5 (visual design + a11y) per `100days.md`.

**Not in scope here.**
- Anything fixed in `port-v01-ingestion` — multi-select delete (`a152d6e`), false-`.ready` after crash (`f30d8fc`), Stop-mid-run lands in `.idle` (committed inline 23 Apr), terminus-event log (Phase 1f Slices 1–4).
- Resume / Retry / Re-analyse… **verb wiring** — data layer landed in Slice 4 (state cases + `is_retryable`); UI wiring (context menu + Project menu + destructive modal) is the explicit Slice 4 carry-over and goes here as **§3**.

---

## 1. Activity pill — broken at default widths

**Severity: blocker.** The pill's whole purpose is to surface failure/progress at-a-glance. Today it's invisible at default window widths — collapsed into the `>>` toolbar overflow menu. Only appears when the window is dragged "ridiculously wide". Confirmed 20 Apr 2026 QA.

**Fix direction (single coordinated change):**
- Move pill from `.primaryAction` (rightmost, after Search) to `ToolbarItem(placement: .principal)` immediately after the segmented Picker. That's where Xcode's actual activity area lives.
- Drop the custom `Color.secondary.opacity(0.08)` capsule background entirely (Xcode-faithful) or use `.background(.thinMaterial, in: Capsule())` for vibrancy. Current chrome reads as a custom widget grouped with Search.
- Higher placement priority means it's the LAST item to collapse into overflow, not the first.

**Pairs with §2** — they're the same redesign moment.

**Other pill polish carried from gruber review:**
- `Stop` button is `.destructive` (renders red) — should be plain. Stopping preserves committed-stage work; HIG `.destructive` = unrecoverable. Optionally add `.confirmationDialog` when elapsed > 5 min.
- Double-shrink spinners — both pill (`.scaleEffect(0.6)`) and ProjectRow (`.scaleEffect(0.7)`) on top of `.controlSize(.small)`. Drop the scale; use `.controlSize(.mini)` if needed. (Note: pill `.scaleEffect(0.6)` was the source of the popover-disclosure freeze — already removed in this branch's QA-fix batch.)
- 1-second ticker runs even when popover closed. Cheap to gate on `showPopover`.
- VoiceOver label currently reads "Stage 3 · Transcribing, button" with "middle dot" verbalised. Add `.accessibilityLabel("Pipeline running, stage 3 of 12, transcribing")`.
- Failure pill secondary glyph (`arrow.clockwise` next to "Network error", `key` next to "API key problem") — signals at-a-glance that clicking offers an action.

---

## 2. Failure surfaces — drop redundancy, trust the content area

**Two red exclamations for the same failure.** Sidebar row glyph + toolbar pill glyph, both `exclamationmark.circle.fill`, both red. Confirmed 20 Apr 2026 — user triage: *"if we show the error state in the left hand side under the project that's being ingested do we also need to show it top right?"*

**Detail view ignores pipeline state (BUG).** A `.failed` project shows the ServeManager "Loading report…" spinner indefinitely instead of a contextual failure card. The detail view's switch cascade goes `availability → empty path → inputFiles != nil → ServeManager state` — missing branch is `pipeline state`. Logged 20 Apr 2026.

**Combined direction (one coherent slice):**
1. Detail view respects pipeline state. Add explicit branches for `.failed` (failure card with action), `.stopped` (resume card), `.partial` (analyse card), `.ready` (existing serve+WebView). Empty state for `.idle`.
2. With detail view carrying the failure signal, drop the toolbar pill when the project is selected AND the sidebar row is visible. Pill stays for sidebar-hidden / scrolled-off cases.
3. `"Loading report…"` overpromises — replace with bare `ProgressView()` until honest progress states exist. Drop `desktop.chrome.startingServer` and `desktop.chrome.loadingReport` keys.

**Failure popover collapse.** Currently three buttons (Retry / Copy error / Change provider). User triage: *"is it ever the case that retry will work? perhaps just 'Open LLM settings' to take the user to the place they can do something about it?"* Per-category single CTA mapping:

| Category | CTA | Reasoning |
|---|---|---|
| `.auth` | **Open LLM Settings** | Retry meaningless — same key fails the same way |
| `.network` | **Retry** | Transient — single button |
| `.quota` | **Open LLM Settings** | Switch provider; rate limits don't clear instantly |
| `.disk` | **Show in Finder** | Point at the project folder so the user can free space |
| `.whisper` | **Open Settings** | Whisper backend / model lives there |
| `.missingDep` *(new)* | **Run Doctor** | Doctor preflight tells them what to install |
| `.userSignal` *(new)* | n/a — render as `.stopped`, not `.failed` | |
| `.apiRequest` / `.apiServer` *(new)* | **Retry** | Provider-side, usually transient |
| `.unknown` | **Retry** | Honest fallback |

`Copy error details` moves into the technical-details disclosure (a Copy button at the bottom of the log ScrollView, Console.app pattern).

**Failure popover overflow.** Disclosure expansion makes log lines visibly run past the rounded-corner clip. Workaround landed (`.frame(width: 360, height: 320)` fixed envelope) but creates whitespace when collapsed. Proper fix: either height-adaptive popover that doesn't trigger NSPopover animated resize, OR move "Show technical details" to a separate sheet/window button so the popover stays compact and the log gets a real window with copy/save affordances.

**Failure category copy** (from gruber review):
- `"Provider key issue"` → `"API key problem"` (matches plan's auth-category copy)
- `"Network error"` → `"Can't reach provider"` (Mail's idiom)
- `"Your LLM provider key isn't working."` → `"Your {provider} key isn't working."` with interpolation (`anthropic` → "Claude", `openai` → "ChatGPT", `azure` → "Azure OpenAI", `google` → "Gemini", `local` → "Ollama"). Apply to all six failure categories — `humanSummary` is the single source.

**Multi-fault doctor output.** Categoriser regex hits `401` first → `.auth` label → user thinks key is the only problem. But doctor preflight had `✗ FFmpeg not found` AND `✗ API key rejected`. Fix paths: (1) parse doctor preflight block directly, synthesise multi-cause summary; (2) introduce `PipelineFailureCategory.multiple([...])` so popover renders a per-item checklist; (3) structured CLI output (`--json-progress`).

---

## 3. Run-trigger UX — Resume / Retry / Re-analyse… verbs

**Carried over explicitly from Phase 1f Slice 4.** The data layer landed (`PipelineState` cases `.partial(kind, stagesComplete)` and `.stopped(stagesComplete)`; `is_retryable(category)` rule; `EventLogReader` deriving honest state from the events log). UI wiring deferred for HIG attention.

**State × trigger matrix today** (from 23 Apr 2026 inventory):

| State | Pill Retry | Menu Re-analyse | Drop-on-row | Drop-to-empty (dup) |
|---|---|---|---|---|
| `.idle` | n/a | disabled | parked | ✅ creates duplicate |
| `.stopped` | ⚠ unknown | disabled | parked | ✅ creates duplicate |
| `.failed` | ✅ | disabled | parked | ✅ creates duplicate |
| `.ready` | n/a | disabled | parked | ✅ creates duplicate |

**For idle/stopped/ready states, users genuinely cannot re-trigger analysis today without duplicate-creating hacks.** Pill Retry covers only `.failed`. Project menu > Re-analyse is `.disabled(true)` with a "Future — Phase 2+" comment.

**Ship in this iteration:**
- Context menu on project row, guarded by state:
  - `.idle` → "Analyse"
  - `.stopped` → "Resume" (default)
  - `.failed` → "Retry" (default)
  - `.partial(transcribe-only)` → "Continue (Analyse)"
  - `.ready` → "Re-analyse…" (with confirmation modal)
- Project menu (MenuCommands.swift:317–415) — same verb set, mirroring context menu state-guarding.
- Re-analyse… confirmation modal copy (agreed 23 Apr):
  > **Re-analyse this project?**
  > Discards all your edits, tags, stars, and hidden quotes. Runs a fresh analysis.
  > [Cancel] [Re-analyse]
  > Default button: Cancel (HIG destructive-action pattern).
- Pill popover Retry currently only for `.failed` — extend to `.stopped` (route to Resume), `.partial` (route to Continue).

---

## 4. Stop affordance — local + truthful

**Today: only way to stop a running pipeline is pill → popover → Stop.** Three interactions, requires hunting away from the sidebar row where the user's attention is. From 23 Apr 2026:

**Add (low effort, high value):**
1. Right-click on project row → context menu "Stop" (visible only when state is `.running`).
2. Tiny × button on row itself, visible only during run, like Mail's download-cancel or Finder's copy-progress cancel. Hover-reveal acceptable.

**Redundancy is the point.** Sidebar-focused / detail-focused / muscle-memory toolbar — different contexts, different stop affordances. Keep the pill popover Stop too.

**Stop-is-a-lie on attached orphan (BUG, alpha-blocker — not yet fixed).** From 23 Apr 2026 — `PipelineRunner.cancel()` orphan path re-verifies via `aliveOwnedRunPID`. If the file is missing or the check fails, SIGINT is **silently skipped** but state still transitions to `.idle` and PID file is removed. UI clears as if Stop worked. Subprocess keeps running (API burn, Whisper CPU, no visibility).

**Fix:** remove the re-verification. If `attachedOrphanPIDs[project.id]` says we attached to pid N, SIGINT pid N. `kill()`'s own ESRCH/EPERM is the only signal needed. Never unconditionally clear state — only clear when the kill is confirmed. Surface EPERM as a toast.

**Owned-process signal escalation.** Today only orphan-path cancel escalates SIGINT → SIGTERM → SIGKILL. Owned-process `cancel()` uses `proc.interrupt()` (SIGINT only) — same wedge risk during whisper model load. Mirror the orphan-path escalation (~20 lines). Carry-over from earlier batches.

---

## 5. Pipeline progress — surface what the CLI already knows

**Today the Mac app surfaces `"Stage N · stage_name"` in the pill, elapsed in the popover. The CLI has way more:**

- Stage checkmarks + per-stage timing
- Welford ±stddev duration estimate (`bristlenose/timing.py`)
- Per-stage ETA recalculation
- Per-session progress (stages 4–7) — *"Speakers: 7/10 sessions"*
- Cached stage skip indication (*"✓ stage_name (cached)"*)
- Resume summary (*"Resuming: 7/10 sessions have quotes, 3 remaining"*)

`PipelineProgress` even has `sessionsComplete` / `sessionsTotal` fields that `StdoutProgressParser` doesn't populate. We're discarding ~80% of the signal.

**Three paths (rank order):**

1. **Manifest polling for live runs.** Per-stage `status`, `started_at`, `completed_at`, per-stage `sessions` dict are already on disk (and Phase 1f added the events log). Poll periodically during a run, not just for orphan-attach. No CLI change. Probably the fastest path to richer pill copy.
2. **`bristlenose run --json-progress`.** Structured CLI output, one JSON event per stage transition (stage_start, stage_progress with sessions x/y, stage_complete with cached flag, eta_update). New `JsonLinesProgressParser` populates the existing struct. Robust; CLI change required.
3. **Richer stdout regex.** Cheap, brittle; explicitly flagged as fragile. Skip.

**Concrete pill copy upgrades:**
- `"Stage 3 of 12 · Transcribing · Sessions 7/10 · ~3 min remaining"` (was `"Stage 3 · Transcribing"`)
- `"Queued · waiting for "Project A""` (was `"Queued · 1"`)
- Cached stages indicated in popover timeline (Mail's *"12 of 47, 35 remaining"* pattern)
- Resume header: *"Resuming: 7/10 sessions completed previously"* before the live stage updates begin

**Stage counter conflation.** Pill shows *"Stage 15 · Rendered report"* — but the pipeline has 9 stages. Parser increments on every `✓` line, including doctor preflight (`✓ Disk space`, `✓ API key`, etc.) and per-session sub-checks. Cheap fix: filter ✓ lines to canonical stage-name list. Pairs with the *"Stage N of 9"* denominator.

**Attached-orphan pill shows stale "Starting up" for minutes.** Attach path polls manifest, but doctor preflight + early bootstrap don't write manifest checkpoints. Pill displays placeholder until first real stage commits. Real stdout is gone (dead parent pipe). Fix: tail `<output>/.bristlenose/bristlenose.log` and surface last N lines as `progress.lastLine`. Also: change placeholder copy from *"Starting up — loading models"* to *"Resuming analysis (reconnected after app restart)"* so user knows it's a continuation.

---

## 6. Settings / dev-mode rough edges

**SwiftUI Toggle reads as OFF when window not key.** Toggle in Settings → LLM rendered grey/desaturated when Settings window wasn't frontmost. Misled both user and AI into diagnosing pipeline failure as toggle-off (it was actually the API key). AppKit `NSSwitch` doesn't have this — uses `controlAccentColor` regardless. Fix: wrap binding to read window key state and explicitly tint when inactive, OR replace with a custom button unambiguous in both states.

**Settings status check is misleading.** LLM Settings → Claude shows "Status: Online" with green dot. Pipeline immediately fails 401 Unauthorized. Status check probably tests (a) key non-empty, (b) `api.anthropic.com` reachable — does NOT test that the key authenticates. Fix: real auth-validating call (e.g. `POST /v1/messages` with `max_tokens: 1`), debounced on key change, OR surface the doctor `✗ API key` line directly in the Settings status row.

**Keychain re-prompts during run.** Multiple `security` prompts within a single pipeline run. Pre-existing — `MacOSCredentialStore` shells out to `/usr/bin/security` per credential read; "Always Allow" ACL not persisted, or each subprocess invocation treated as new requester. **Track C C3 retires this** (Swift fetches once, caches in-process, injects via env var to Python sidecar). Until then: power through, or `"Allow all applications"` in Keychain Access during dev.

**Dev port + no dev server = silent WebView spin.** When `BRISTLENOSE_DEV_PORT=8150` is set in Xcode scheme but no terminal-side `bristlenose serve` is running there, WebView spins on `"Loading report…"` indefinitely with `NSURLErrorDomain code=-1004` errors in console. Real fix: ServeManager fail-fast with clear error in detail view — *"Dev server expected on port 8150 but nothing is listening — start `bristlenose serve --dev` in a terminal, or unset BRISTLENOSE_DEV_PORT."*

**Xcode-launched app doesn't inherit shell PATH.** `brew install ffmpeg` succeeds but doctor reports `✗ FFmpeg not found` because Xcode-launched apps get minimal PATH. Bundled sidecar (Track C C1) ships its own ffmpeg, retiring this. Until then: 1-line `PATH` prepend (`/opt/homebrew/bin:/usr/local/bin`) in `BristlenoseShared.buildChildEnvironment()` to unstick first run.

---

## 7. UnsupportedSubsetView — empty state needs work

- **Headline declarative not problem-stating.** Restructure to `"This project can't be analysed"` (title) + `"Bristlenose analyses folders, but this project was created from individual files."` (body).
- **Left-stranded on wide windows.** `maxWidth: 640 .top` flush-left looks wrong on big monitors. Centre or wrap in HStack with Spacers.
- **No recovery action.** Photos / Mail empty states always offer a button. Options:
  - (a) `Button("Create Project from Folder…")` opens NSOpenPanel scoped to `chooseDirectories`, creates a new project, deletes the file-subset one. Needs project-surgery semantics that don't exist yet.
  - (b) `Button("Show Containing Folder")` if all `inputFiles` share a parent dir. Lighter; was implemented then reverted as "UX decision for later".

---

## 8. Mac-native polish (gruber findings — review #2)

These are the items from the post-Slice 7 review that user explicitly deferred ("all UX decisions for later"). Most are 1–2 line fixes.

- **`showSettingsWindow:` selector** is the AppKit-private path — replace with `@Environment(\.openSettings)` env action (macOS 14+; deployment target is 15.0). Currently works but fails silently if Apple rotates the selector.
- **DisclosureGroup copy + Copy button** — `"Show technical details"` → `"Show Details"` + add explicit Copy button at bottom of the log ScrollView (Console.app pattern).
- **Elapsed time format breaks past 1 h** — `"%d:%02d"` (M:SS) renders wrongly at 60+ minutes. Use `Duration.UnitsFormatStyle` or branch to `H:MM:SS`.
- **250 ms scan-indicator delay creates synchronised wave** — all rows hit +250 ms together. Stagger by row index, or only show spinner when scan exceeds 1 s.
- **Failure card row glyph** — switch row to `exclamationmark.triangle` (Photos pattern) so it's distinguishable from the pill's `circle.fill`. Pairs with §2's drop-pill-when-detail-view-shows-failure direction.

---

## 9. Sidebar polish carry-over

- **`foobar` row stays in inline-rename mode** across pill clicks, popover open/close. Pre-existing v0.2 bug — rename mode should dismiss on focus loss outside the field.
- **Drop-on-row parked** (List-gesture breakage on macOS 26 — already documented in `desktop/CLAUDE.md` as the all-tap-gestures-break-selection issue). Workaround currently shipped via `SidebarDropDelegate` for Finder file drops. Verify add-files-by-drop-on-row still works on the row, and surface a clear toast confirmation. (Toasts already added: *"Adding extra interviews to an analysed project isn't supported yet."* etc. — needs reconsideration once incremental re-analysis lands.)
- **Incremental re-analysis** — *must for alpha* per 23 Apr 2026 user triage. Currently dropping more files onto a `.ready` project surfaces *"Adding extra interviews to an analysed project isn't supported yet"*. Design doc `docs/design-project-sidebar.md:246` promises *"Added 3 interviews to Mobile Banking Pilot"* with Undo. Gap is pipeline-side: needs (a) detect new sessions via manifest, (b) re-run stages 1–7 for new sessions only, (c) re-run stages 8–11 globally (corpus-scoped), (d) `bristlenose run --incremental` flag or auto-detect. Pipeline-resilience design (`docs/design-pipeline-resilience.md`) is the prereq. **This iteration ships the UX shell; the pipeline plumbing is its own slice.**

---

## 10. i18n debts

**Toast strings live as English literals in Swift.** From `port-v01-ingestion`:
- `"Finish or stop the current run before adding more."`
- `"Adding extra interviews to an analysed project isn't supported yet."`
- `"Use Retry on the toolbar to try this run again."`
- `"This project's folder isn't reachable right now."`

Plus all the Mac-native polish copy in §8 above.

Move all to `bristlenose/locales/*/desktop.json` per `docs/design-i18n.md` in the i18n pass.

---

## 11. Documentation debts (low priority — log only)

**Trust-center talking points** the orphan-recovery + Phase 1f resilience slice enables (write up in SECURITY.md when it becomes the right time):
- *"API keys never appear in `env` or `ps` output — kept in Keychain."*
- *"Pipeline runs are argv-invoked, never shell-invoked — injection via filename or project name is structurally impossible."*
- *"All participant data writes are confined to `<project>/bristlenose-output/`; erasure is `rm -rf`."*
- *"Single-slot FIFO queue means there's never more than one `bristlenose run` consuming the user's API budget."*

**`copyErrorDetails` leaks `/Users/<name>/...` paths in tracebacks.** Currently strips `project.path` only. Add a second pass: `replacingOccurrences(of: NSHomeDirectory(), with: "~")` and a regex for `/Users/<anything>/`.

---

## What's NOT here (already shipped or out of scope)

- Multi-select delete (`a152d6e`) — done
- False-`.ready` after crash (`f30d8fc`) — done; Phase 1f Slice 4 makes it more robust via events log
- Stop-mid-run lands in `.idle` not `.failed` (committed inline 23 Apr) — done
- Phase 1f event-log + cost — done across Slices 1–4
- Sandbox / TestFlight signing rough edges — Track C C0–C5 (separate)
- Multi-project advanced UX (folders, drag-reorder, smart folders) — Sprint 3

---

## Suggested grouping for the iteration

**Pass 1 (1–2 days):** §1 pill + §3 verbs. Both are visibility / discoverability fixes that unblock everything else. Can ship without touching the failure popover redesign.

**Pass 2 (2–3 days):** §2 failure surfaces + detail view. Bigger redesign; ties together popover, pill, sidebar row, and detail card. Best done as a coherent design pass, not piecemeal.

**Pass 3 (1 day):** §4 stop affordance + §6 dev-mode rough edges. Plumbing work, low risk.

**Pass 4 (parallel-track):** §5 progress richness. Pairs with a CLI change (`--json-progress` or manifest polling), so own slice + branch.

**Pass 5 (cleanup):** §7 + §8 + §9 + §10 + §11. Nibbles. Could be done by an agent in one sweep with review.
