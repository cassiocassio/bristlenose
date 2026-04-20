# C3 smoke test — findings log

## TL;DR for morning review

C3 itself (Keychain → env-var injection) is **verified working end-to-end** through the desktop app. The smoke test incidentally uncovered three separate bugs of the same class in the PyInstaller sidecar bundle (BUG-3/4/5 — runtime data files in source not included in `datas`). All three fixed. Post-mortem + regression gate (BUG-6) below.

**Commits landed on `sidecar-signing` while you slept** (not pushed):
- `5aae47c` — BUG-3 fix (React SPA `static/` in datas)
- `08a0664` — BUG-4/5 fix (codebook YAMLs + llm/prompts in datas)
- `dadf2e9` — initial qa-backlog follow-ups
- (bundle-completeness commits to land below)

**What still needs you over coffee:** review the reviews + post-mortem + BUG-6 gate, confirm the Xcode Debug build still runs clean, approve pushing.

---

## Post-mortem — how did we ship a sidecar that didn't work?

Worth writing down while it's fresh. BUG-3/4/5 are all the same failure mode:

> Source code paths at `bristlenose/<x>/<y>/*.{md,yaml,json,...}` → imports work via `pip install -e .` in dev → PyInstaller's Analysis doesn't pick up non-`.py` files → bundle ships without them → runtime `FileNotFoundError` or silent fallback to deprecated path.

### The three instances

| # | Missing dir | Symptom | Detected by |
|---|---|---|---|
| BUG-3 | `bristlenose/server/static/` (React SPA) | Deprecated static-render HTML served instead of React SPA | Operator noticing layout looked wrong |
| BUG-4 | `bristlenose/server/codebook/*.yaml` | "Browse Codebooks" modal empty | Following up on BUG-3 fix |
| BUG-5 | `bristlenose/llm/prompts/*.md` | Would have crashed every LLM call with `FileNotFoundError` | Filetree audit during post-BUG-3 investigation — caught BEFORE a real user hit it |

### Why it slipped through

**1. Unit tests don't exercise the bundle.** Tests run with `pip install -e .` where data files live at their real paths and `Path(...).read_text()` works. PyInstaller is a fundamentally different runtime shape (bytecode archives + explicit datas manifest). The entire CLI + server test suite passed while the bundle was broken.

**2. C0/C1 built the bundling machinery but never exercised a realistic end-to-end scenario.** C0 was an entitlement spike (does the Python runtime start under Hardened Runtime?). C1 resurrected `build-sidecar.sh` and proved it produces a runnable binary. Neither step opened the app, clicked through to a real LLM-using feature, and verified the bundle was functionally complete. **"It boots" was the implicit exit criterion. "It works" wasn't tested.**

**3. Each new bundle-datas entry was added reactively, one UI symptom at a time.** `theme/`, `data/`, `locales/`, `alembic/` are all in the spec because someone hit the specific failure that prompted each one. `static/`, `codebook/`, `prompts/` weren't — not because they weren't needed, but because no one had clicked far enough to find the absence.

**4. The React migration deprecated the static render but didn't delete it.** Per `CLAUDE.md`, the static-render path is intentionally kept as a "frozen snapshot" fallback for offline HTML export. In the bundled sidecar with no `static/` dir, the `_mount_dev_report` pathway falls back to serving static-rendered HTML instead of erroring. That fail-open is user-hostile in this case — **the bundle appeared to work** (showed a report, let you navigate tabs, looked like Bristlenose) but was missing most of the modern UI. Without the operator knowing what the React SPA is supposed to look like, it could have shipped to alpha testers without anyone noticing.

**5. No CI gate compares what's in `bristlenose/` source against what's in the spec's `datas`.** This is BUG-6 — the process-level gap — and the primary outcome of this track.

### What we got right

- **Fail-closed architecture meant no silent data misbehaviour.** Even though the bundle was broken, the failure modes were loud (empty UI sections, "Cannot play this format" misdiagnosis, would-be crashes on LLM calls). No participant transcript ever reached the wrong LLM, no partial redaction shipped silently. The blast radius was "doesn't work," not "works wrong." Local-first really helps here — a SaaS tool with this class of bug might have routed data to the wrong region for hours before detection.

- **The C3 smoke test walkthrough itself was the audit tool.** Trying to drive the app through a realistic flow (enter key → open project → click through Codebook → trigger autocode) was what made each gap visible. The walkthrough was written as "help the human do a manual smoke test" but ended up functioning as "integration test run by a careful human."

- **The "WebView ready message not received" warning was the canary.** Per `desktop/CLAUDE.md`, that log line explicitly names the "main branch build served by serve won't post ready messages" case. The warning had been staring at us for at least a session before anyone connected it to BUG-3. Take the obvious hints seriously.

### Lessons for alpha and beyond

1. **Bundle CI gate** (BUG-6, landing in this session): source-vs-spec manifest check. Runs in `build-all.sh` pre-flight, fails the build if a runtime data dir isn't covered by `datas`. ~1s cost, no network, pure shell + Python AST.

2. **Post-build smoke test** (deferred — D3 from the plan, filed as a follow-up): spawn the bundled sidecar, hit representative endpoints, assert no 5xx from FileNotFoundError-class. Covers the next-class bug — "spec entry present but PyInstaller silently dropped files." ~30s cost, needs a real Anthropic key so either the alpha-testers-key-with-spend-cap pattern or a mocked provider.

3. **"First real use" milestone as explicit gate for every Cn track.** Don't close a track on "builds" or "code reviewed." Close it on "I successfully did the thing the track was about, end-to-end, as a user." C0 established the pattern; this smoke test was the first real use of the bundled sidecar, which is why three bugs surfaced at once.

4. **Deprecated paths should error under a flag, not fall open.** When the static render is deliberately kept as a frozen snapshot but the SPA is missing, that's a bug not a fallback. Consider a `BRISTLENOSE_REQUIRE_SPA=1` mode for production builds that 500s if the React SPA isn't available, rather than silently serving the deprecated HTML.

5. **Per CLAUDE.md's "WebView ready message" gotcha:** the warning existed specifically because this exact failure mode had been seen before. The fact that it took this smoke test to rediscover it suggests the gotcha documentation needs promotion — not buried in a 600-line CLAUDE.md, but surfaced in `design-desktop-python-runtime.md` or similar where someone packaging the desktop app is guaranteed to see it. Filing as a docs task.

### Generalisation

This failure mode is generic to every PyInstaller-bundled Python app. The Python packaging ecosystem has a documented gap: editable installs (`pip install -e .`) and frozen bundles (`pyinstaller`) disagree about how non-`.py` files are reachable. Anyone shipping a PyInstaller app with runtime data files hits this sooner or later. **Worth a public blog post** (post-alpha) — it's the kind of write-up that signals maturity to procurement evaluators and helps other indie Mac devs.

---

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

## Console noise observed at startup (pre-existing, not C3)

These appeared in Xcode console alongside the expected `Mode: bundled, path=...` line. Both pre-date C3, both worth noting for someone doing a console-cleanup pass.

- **SQLite probing `/private/var/db/DetachedSignatures`:**
  ```
  cannot open file at line 51040 of [f0ca7bba1c]
  os_unix.c:51040: (2) open(/private/var/db/DetachedSignatures) - No such file or directory
  ```
  SQLite's macOS VFS includes a code-signing integrity hook that touches that path. The file is normally absent on macOS and SQLite logs the failure but proceeds. Well-known noise across Apple-platform SQLite consumers. **Cosmetic, not actionable.**

- **SwiftUI PreferenceKey redundant write warning:**
  ```
  Bound preference FolderFramePreferenceKey tried to update multiple times per frame.
  Bound preference RowFramePreferenceKey tried to update multiple times per frame.
  ```
  Comes from the sidebar's `SidebarDropDelegate` hit-testing pattern (`GeometryReader` + per-row `PreferenceKey` for hit-test frames; see `desktop/CLAUDE.md` "ALL tap gestures on List rows break selection on macOS 26" gotcha). Pre-existing pattern, real SwiftUI warning about redundant layout work, **not a C3 regression**. Worth filing as a low-priority "investigate redundant preference writes in sidebar" if a perf pass happens.

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

## Project loaded — observations

Project opened cleanly. Stats from Project tab confirm a fully-processed prior state: 3 sessions, 9 min of video, 871 words, **42 quotes with sentiment tags, 2 themes, 7 sections, 27 AI tags**. The presence of AI tags means a working Claude key was used in a prior pipeline run on this project — good baseline, autocode has something to chew on.

### OBS-1: project name mismatch between sidebar and report header

- Sidebar entry reads `foobar`
- Report header reads `Bristlenose foo` (the "foo" being the per-project title)
- Two different name sources: probably the desktop app's `Project.name` (in `projects.json`) vs. the pipeline's `project.json` `name` field inside the project folder.
- **Severity**: cosmetic but jarring on first impression. Worth aligning sources or at least surfacing both consistently.

### OBS-2: orphan sidebar entries

- Two sidebar items show "Locate…" status: `more interviews` and `Screen Recording 2026-…`
- Means the desktop app's `projects.json` retains records for paths it can no longer resolve (folder moved, deleted, or unmounted).
- Pre-existing recovery UI; not C3-related. Worth flagging as an alpha-tester confusion source — they'll hit this whenever they reorganize project folders.

## C3 happy-path signals confirmed at startup

Two `injected API key for provider=anthropic` log lines observed (one per sidecar launch). Auth-token parser working, ports allocated. **C3's `overlayAPIKeys` is firing as designed.** This is the primary signal we hoped to see, observed even before triggering autocode.

## More pre-existing macOS noise (already not actionable)

Beyond the two earlier (SQLite DetachedSignatures, SwiftUI PreferenceKey), additional macOS noise observed:

- `Unable to obtain a task name port right for pid …` — Xcode debugger task-port noise.
- `kDragIPCCompleted` reentrancy — NSDragging internal.
- `AFIsDeviceGreymatterEligible` — Apple Intelligence eligibility check.
- `flock failed to lock list file … errno = 35` — Metal shader cache lock contention (EAGAIN); cosmetic when multiple Metal-using processes start near-simultaneously.
- `precondition failure: unable to load binary archive for shader library: …IconRendering.framework…` — macOS framework's own metallib failure.
- `No URL for Apple ID Authorization` — we don't use Apple ID.
- `WebContent[…] Unable to hide query parameters from script` — WKWebView noise.

None are us. Filing as "macOS console floor" — won't go away no matter how clean our code is.

### OBS-3: `[WebView] ready message not received — showing content anyway`

Real symptom worth a follow-up. Per `desktop/CLAUDE.md` ("Bridge code on main vs feature branch"): the React bundle served by the sidecar doesn't post the `ready` message the WKWebView listens for; a `didFinish` fallback fires after a 2s timeout and shows content anyway.

Implication: the React build inside `Contents/Resources/bristlenose-sidecar/_internal/bristlenose/server/static/` is missing the bridge-ready emit, OR the bridge isn't being installed in the bundled-static path. Not C3-blocking (report renders), but the structured handshake is broken — Swift can't tell when the SPA is genuinely interactive.

Probable causes:
- The React bundle inside the sidecar is stale (not rebuilt against current `frontend/src/shims/bridge.ts`).
- Bridge shim only mounts when running through the frontend dev server, not when served from `static/`.
- Branch difference — the bridge code lives on `macos-app` and not `main` per the CLAUDE.md note; the sidecar might be packaging from main.

**Worth filing as a frontend/desktop coordination bug** — separate from C3.

## Multi-provider injection observed (additional C3 happy-path signal)

Console showed both `injected API key for provider=anthropic` AND `injected API key for provider=openai` after Settings changes. **`overlayAPIKeys` iterates the full provider list correctly** — every provider with a key in Keychain gets a `BRISTLENOSE_<PROVIDER>_API_KEY` env var. Restart-on-prefs-change wiring (`bristlenosePrefsChanged` → `restartIfRunning` → `start` → `overlayAPIKeys`) verified.

Bonus: `port 9131 already in use, trying next` confirmed the port-collision recovery loop in `start()` works (lingering sidecar from prior launch on the same project).

### OBS-4: dual activation control confusion (settings UX)

While entering the fake key for Pass A:
- Sidebar showed Claude with blue radio-check (selected)
- Detail pane "Use this provider" toggle was OFF
- Status dot still read "Online" (presence-only, not actually-active)

This is the [feedback_settings_modal_vs_panel] + Gruber review concern manifesting in practice during the smoke test: it's not obvious that the toggle is what determines *which provider gets used* — the radio looks like activation. Operator (me) had to call out: "you'll need to flip the toggle on for Claude, otherwise autocode will use whichever provider IS active." Already in qa-backlog as alpha-blocker-class.

### Empty-key skip observed (C3 Step 2a invariant verified in the wild)

Mid-Settings tinkering, one restart cycle showed:
```
preferences changed — restarting serve
injected API key for provider=openai
captured auth token (prefix=OQYg226v)
port 9131 is accepting connections
```
Only `provider=openai` injected — no `provider=anthropic`. This was the moment the Anthropic key was empty/cleared in Keychain. The next restart (after re-saving) had both back. **Confirms the `skip nil AND empty` guard in `overlayAPIKeys` is doing the right thing in production** — empty values are not injected as `BRISTLENOSE_ANTHROPIC_API_KEY=""` (which would have triggered the exact failure mode C3 set out to prevent).

## BUG-3: React SPA not bundled into the sidecar — bundled sidecar serves the deprecated static render

**Severity:** major. Affects everything UI-visible in the bundled-sidecar mode. Independent of C3.

### Diagnosis

The user noticed the running app's Quotes view was the deprecated static-render HTML, not the React SPA. Telltales:
- 3-column "Sections / Themes / Analysis" dashboard at top of Quotes (a static-render frozen-snapshot layout, replaced by the SPA's sidebar+TOC layout)
- No left/right sidebars
- Thin Codebook tab (just "+ New group", no browse-frameworks UI — see BUG-2)
- `[WebView] ready message not received` in console (no SPA bridge handshake firing because there's no SPA)

### Root cause

1. Vite React build output is `bristlenose/server/static/`
2. That directory is **gitignored** (`.gitignore` line: `bristlenose/server/static/` — labelled "Frontend build artifacts (regenerated by npm run build)")
3. The current worktree doesn't have a built `static/` (no recent `npm run build`)
4. `desktop/bristlenose-sidecar.spec` has **zero references to `static/`** — PyInstaller wasn't told to bundle it as a `datas` entry even if it existed
5. Bundled sidecar at `Contents/Resources/bristlenose-sidecar/_internal/bristlenose/server/` has no `static/`
6. FastAPI's SPA mounting fails silently and the legacy static-render path serves whatever HTML is on disk

### Confirms two things

- **BUG-2** ("no UI path to import codebooks") is probably a symptom of BUG-3 — the React `CodebookPanel` likely *does* expose framework import; we were looking at the deprecated thin version. Verify by re-testing once BUG-3 is fixed.
- **`[WebView] ready message not received`** earlier was the right hint: there's no SPA emitting the bridge handshake.

### Fix (estimated 10 min)

1. `cd frontend && npm run build` — populates `bristlenose/server/static/`
2. Add a `Tree('bristlenose/server/static', prefix='bristlenose/server/static')` (or equivalent) to the `datas` list in `desktop/bristlenose-sidecar.spec`
3. `desktop/scripts/build-sidecar.sh`
4. Re-launch the desktop app under Xcode Debug (re-signs automatically)

### Why this is a C1 gap, not a C3 gap

C3 is pure Python credential plumbing. The React SPA's absence has no effect on `overlayAPIKeys`, `KeychainHelper`, or pydantic-settings. **C3 itself is verified by the Logger evidence regardless of which frontend is rendering.** The bundle gap blocks the autocode-via-UI test path, but does not invalidate the C3 invariants we've already observed.

### Additional BUG-3 telltale: video player "Cannot play this format"

Operator opened a session video — popout window appeared with red error banner: **"Cannot play this format — try converting to .mp4"**, and a play-button-with-slash icon over a black video area.

**This is the canonical misdiagnosis pattern.** Per `bristlenose/server/CLAUDE.md` and memory `feedback_media_auth_exempt`:

> "Cannot play this format" almost always means a **401 on `/media/`**, not a real codec problem. HTML `<video>`/`<audio>` can't send custom headers, so they get 401'd if `/media/` is in `_AUTH_REQUIRED_PREFIXES`. This has been misdiagnosed as a format problem three times before — would be #4 if not caught.

**Why this is another symptom of BUG-3:** the static-render `player.js` has no auth-token injection logic; the React `PlayerContext` does. When the deprecated render is being served instead of the SPA, the legacy player tries to fetch `/media/...` without the auth bearer, the server may 401 it (depending on whether `/media/` is currently exempted), and the user sees the misleading "Cannot play this format" message.

**Verify in Web Inspector:** right-click in popout → Inspect Element → Network tab → reload → look at `/media/...` request status. Expected: 401 (confirming auth not codec). If 200 then the codec really is unsupported and it's a different bug.

**Fix:** same as BUG-3 — bundle the React SPA, the SPA's `PlayerContext` handles `/media/` correctly.

## ~~BUG-2~~ — withdrawn

Initially filed as "no UI path to import bundled codebook frameworks." On reflection: not a real finding. We were looking at the deprecated static-render `CodebookPanel`, not the React SPA's. Per the deprecation policy in CLAUDE.md, the static render ships correct data but does not receive design updates — so the absence of a framework-import button there says nothing about what the React `CodebookPanel` exposes.

Re-test once BUG-3 is fixed and the React SPA is being served. If the React `CodebookPanel` still lacks framework-import UI, THEN file as a real bug. Until then: no signal, no finding.

## Pivoted verification — what's load-bearing for C3

C3's primary invariants are verified by the evidence already in the console output without needing autocode to fire:

| Invariant | Evidence | ✅/❌ |
|---|---|---|
| C3 reads Keychain | `Logger.info("injected API key for provider=anthropic")` × many | ✅ |
| Multi-provider injection | both `provider=anthropic` and `provider=openai` injected | ✅ |
| Empty-skip works | one restart cycle showed `openai` only while `anthropic` was momentarily empty | ✅ |
| Restart-on-prefs-change | many `preferences changed — restarting serve` cycles, env re-injected each time | ✅ |
| Port collision recovery | `port 9131 already in use, trying next` → `9132` | ✅ |
| Redactor regex correctness | `BristlenoseTests/HandleLineRedactorTests.swift` (positive + negative cases against pattern-valid fakes) | ✅ |
| Redactor doesn't false-positive on real logs | pre-commit `rg -P` against `pipeline-run.log` returned zero hits | ✅ |
| Env var actually present on sidecar process | **`ps ewww $PID` count + length check** | [pending] |

The redactor's runtime test (Pass A as originally designed) is unblocked-but-unrun. Unit tests + log audit cover its correctness without it. Filed as a future follow-up if anyone wants belt-and-braces.

## BUG-4: codebook YAMLs not bundled (same class as BUG-3)

**Severity:** alpha-blocker. The "Browse codebooks" modal in React `CodebookPanel` opens correctly, but the "CODEBOOK FRAMEWORKS" section is empty. Researcher cannot import any of the five bundled frameworks (garrett, morville, norman, uxr, plato).

**Root cause:** `bristlenose/server/codebook/*.yaml` (five frameworks + an `archive/` subdir) was missing from the PyInstaller spec's `datas`. Bundled sidecar's `_internal/bristlenose/server/` had only `alembic/` and `static/`.

**Fix:** committed alongside BUG-5 in `08a0664` — added `bristlenose/server/codebook` to the spec's `datas`.

## BUG-5: llm/prompts/*.md not bundled — every LLM call would crash

**Severity:** critical. Every LLM-using stage and endpoint would have crashed with `FileNotFoundError` before reaching the provider.

**Root cause:** `bristlenose/llm/prompts/*.md` (8 markdown prompt templates: autocode, quote-extraction, quote-clustering, signal-elaboration, speaker-identification, speaker-splitting, thematic-grouping, topic-segmentation) is loaded at runtime by `_load_prompt()` in `bristlenose/llm/prompts/__init__.py` via `Path(...).read_text()`. Every stage call to `get_prompt("name")` is a file read. None were in the bundle.

**Implication for C3 smoke test:** if I'd told the user to run Pass A by clicking AutoCode on the Sentiment framework earlier, it would have crashed on a missing prompt file, not reached Anthropic, and the redactor would never have seen a key-shaped substring to mask. The redactor test would have been blocked by a different bug than autocode's usual error path.

**Fix:** committed with BUG-4 in `08a0664` — added `bristlenose/llm/prompts` to spec's `datas`.

## BUG-6: missing CI gate — RESOLVED ✅

Landed overnight after plan + /usual-suspects review (`673ddee`): `desktop/scripts/check-bundle-manifest.sh` runs as step 1b of `build-all.sh` pre-flight. Walks `bristlenose/` for runtime-data dirs (files matching the extension whitelist), parses the spec's `datas` list via Python AST (fail-closed on unparseable), diffs. Exits 1 on any uncovered dir OR parse error. ~60ms.

Allowlist governance: `desktop/scripts/bundle-manifest-allowlist.md` with `BMAN-<N>` markers (same pattern as `logging-hygiene-allowlist.md` and `e2e/ALLOWLIST.md`).

**The deferred complement, spec→bundle runtime smoke test** (D3 from the plan): filed in qa-backlog with the security-review hardening notes (127.0.0.1 pinning, `trap` cleanup, ephemeral `HOME`, random token, hard timeout). Addresses "spec entry present but PyInstaller silently dropped files" class — orthogonal to BUG-3/4/5's source→spec class.

### Original BUG-6 text (kept for history)

**Severity:** process-level. BUG-3, BUG-4, BUG-5 are all the same class of bug: "data file present in source, absent from bundle." Unit tests cannot catch this because they run against source with `pip install -e .` where data files live at their real paths. There is no post-build integration test.

**Proposed gates (pick one or both):**
- **(a) Datas manifest check**: small script that walks `bristlenose/` looking for runtime-needed subdirs (by whitelist or by extension heuristic — `.yaml`, `.md`, `.json`, `.html`, `.css`, `.js` that aren't in `__pycache__`) and asserts each has a corresponding `datas` entry in the spec. Runs in <1s, catches missing-datas bugs at commit time.
- **(b) Post-build smoke test**: after `build-sidecar.sh`, spawn the bundled binary, hit representative endpoints (`/api/health`, `GET /api/projects/1/codebook/templates`, a dry `POST /api/projects/1/autocode/<id>`), assert no 5xxs from FileNotFoundError-class failures. Slower (~30s) but finds real runtime breakage including import paths.

Both belong in `desktop/scripts/build-all.sh` before the notarisation step. Filing in qa-backlog.

## Full datas audit (authoritative)

After BUG-3/4/5 fixes, the complete list of runtime data dirs in `bristlenose/` is:

| Source dir | Runtime? | In spec? | Notes |
|---|---|---|---|
| `bristlenose/data` | ✅ | ✅ | Man page, etc. |
| `bristlenose/llm/prompts` | ✅ | ✅ (BUG-5 fix) | 8 .md templates |
| `bristlenose/llm/prompts-archive` | ❌ | — | Archive only (README) |
| `bristlenose/locales/*` | ✅ | ✅ | i18n json |
| `bristlenose/server/codebook` | ✅ | ✅ (BUG-4 fix) | 5 .yaml frameworks |
| `bristlenose/server/codebook/archive` | ❌ | — | Archive only |
| `bristlenose/server/static` | ✅ | ✅ (BUG-3 fix) | React SPA build |
| `bristlenose/theme/*` | ✅ | ✅ | CSS, JS, images, templates |

No other missing runtime data dirs found. The unshipped Python packages (`analysis/`, `utils/`, `stages/`, `llm/`, `server/routes/`) contain only `.py` files, which PyInstaller handles via bytecode compilation — they're functionally present in the bundle despite not appearing as `_internal/bristlenose/...` directories.

## BUG-3 fix verified — React SPA serving

After committing the spec change, running `npm install` + `npm run build` in `frontend/`, and re-running `desktop/scripts/build-sidecar.sh`, the sidecar bundle now includes `bristlenose/server/static/`. Cmd+R in Xcode launched the new build.

**Quotes tab now shows the React SPA layout:**
- Left sidebar with Contents → Sections / Themes TOC (replaces the deprecated 3-column dashboard)
- Right minimap rail
- Tag rail with icon top-right
- Proper React toolbar (search, Tags filter, All quotes, sidebar toggles)
- Quote cards have inline `+` for adding tags
- "more interviews" and "Screen Recording 2026-…" sidebar entries no longer show "Locate…" status — resolved properly
- Project header reads just "Bristlenose" (not "Bristlenose foo") — **resolves OBS-1 (project name mismatch); was a deprecated-render artefact, not a real data bug**

**Other bugs/observations now resolved as side-effects of BUG-3 fix:**
- ~~OBS-1~~ project name mismatch — gone
- ~~OBS-3~~ `[WebView] ready message not received` — verify in next launch's console; should be gone
- ~~BUG-2~~ already withdrawn; expected to be fully resolved (verify by checking Codebook tab now exposes framework-import UI)
- Video player "Cannot play this format" — expected to resolve (verify by re-trying the popout)

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
