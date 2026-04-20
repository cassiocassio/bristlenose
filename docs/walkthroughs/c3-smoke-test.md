# Walkthrough — C3 smoke test

## Context

C3 landed 9 commits last night (`a8dc3cb..832a2d8` on `sidecar-signing`). Build green, tests pass, lint clean. One step needs you: the manual Debug smoke test (Step 6 of `c3-closeout.md`) — GUI-bound, so an autonomous run couldn't do it.

This walkthrough is the at-the-keyboard companion. ~20 min wall-clock, two passes. Goal: prove that Swift→env→Python key injection works end-to-end by making a real Anthropic API call from the running desktop app.

## Pre-flight (5 min, one-time)

### Ingredients

You'll need a **throwaway Anthropic key** — not your production key, because the smoke test involves `ps ewww` output which lands in shell scrollback and history.

1. Open https://console.anthropic.com/settings/keys in a browser
2. Create key → name it `bristlenose-c3-smoke-2026-04-20`
3. **Set a $5 hard spend cap** on the key (per-key usage limit setting)
4. Copy the key into a scratch note — you'll paste it into Settings, not a shell

### Target project

You need a Bristlenose project that's been through transcription already — the smoke test exercises autocode, which is downstream of transcription and needs a completed codebook to run against.

1. Open Finder → navigate to `/Users/cassio/Code/bristlenose/trial-runs/`
2. Pick a project where:
   - `bristlenose-output/` exists with a full set of stages completed (you've run `bristlenose run` against it recently)
   - The Codebook tab will have at least one imported framework (Garrett, Norman, etc.)
3. If you're not sure, `project-ikea` is the canonical choice (per CLAUDE.md). Verify with:
   ```bash
   ls "/Users/cassio/Code/bristlenose/trial-runs/project-ikea/bristlenose-output/.bristlenose/" 2>/dev/null
   # expect: bristlenose.db, bristlenose.log, pii_summary.txt, etc.
   ```
4. If no suitable project exists, run `bristlenose run trial-runs/project-ikea` once first (separate task, 10–15 min with a real key — but use a *different* real key you're already paying for, or skip this smoke test for now).

### Window layout

Three windows. Get them all open before starting so you can glance between them:

- **Xcode** — the project at `desktop/Bristlenose/Bristlenose.xcodeproj`. Scheme set to "Bristlenose" (default, not the dev-sidecar variants). Console visible at the bottom — this is where `ServeManager` logs go and where you'll read the redacted sidecar output.
- **Terminal 1 — "the watchers"** — for `ps`, `pgrep`, `log stream`, and grepping the per-project log file. Plain zsh in the worktree:
  ```bash
  cd "/Users/cassio/Code/bristlenose_branch sidecar-signing"
  ```
- **Terminal 2 — "the browser"** — for opening the `.app` target's project folder and revoking keys at the end. Same directory.

### Branch check

You're operating against last night's commits. Before starting:
```bash
cd "/Users/cassio/Code/bristlenose_branch sidecar-signing"
git status --short                  # expect: clean or only pre-existing noise
git log --oneline 80fddb8..HEAD     # expect: 9 C3 commits
```

## Pass A — redactor sanity with a fake malformed key (8 min)

Goal: prove that when Python echoes an API key back in an error (auth-failure traceback), the Swift-side redactor masks it before it lands in `outputLines`.

### A1. Launch the app under Xcode Debug

1. In Xcode, **Cmd+R** (build + run)
2. Wait for the app to launch. Your sidebar shows an empty state or last-opened project.
3. Watch the Xcode console. Within a second or two you should see:
   ```
   Mode: bundled, path=/Users/.../Bristlenose.app/Contents/Resources/bristlenose-sidecar/bristlenose-sidecar
   ```
   Confirms the bundled scheme is active (not dev-sidecar or external-server).

### A2. Open the test project in the app

1. In the app's sidebar, drag your chosen trial-runs project folder onto the sidebar to add it (or click into an existing entry if it's already listed).
2. Click the project. The app launches its sidecar (`ServeManager.start(projectPath:)`), polls for readiness, loads the React report in WKWebView.
3. Xcode console should show one log line per injected key from `overlayAPIKeys`. You'll see **zero** on this pass because no key is configured yet — that's expected. What matters is the absence of crashes.

### A3. Enter a fake malformed key

1. **Cmd+,** to open Settings
2. Click **LLM** in the Settings sidebar
3. Click **Claude** in the provider list
4. In the API Key field, paste exactly this (pattern-valid but invalid — will never match a real Anthropic key):
   ```
   sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
   ```
   (`sk-ant-api03-` + 95 × `A`)
5. Click the Save button (or tab out — save-on-blur currently fires)
6. Close Settings

### A4. Trigger autocode

1. In the app window (WKWebView), navigate to the **Codebook** tab
2. Find an imported framework in the Codebook view (e.g. "Garrett" or "Norman")
3. Click the **"✦ AutoCode quotes"** button on that framework
4. The job starts. Within ~5 seconds it will fail because the fake key is rejected by Anthropic.
5. You'll see a toast or inline error in the UI.

### A5. Verify the redactor fired

Two checks — one Swift side, one Python side.

**Xcode console (Swift side):**

Scroll the Xcode console back through the failure output. Python's stderr traceback is piped through Swift's `handleLine` → redactor → `outputLines`. The anthropic SDK's error message usually includes the key.

Look for either:
- `***REDACTED***` appearing in the traceback output → ✅ redactor fired
- Raw `sk-ant-api03-AAAA...` substring appearing → ❌ redactor missed it

If ❌, stop here. Something's wrong with the regex; let me know before proceeding.

**Per-project Python log file (on-disk — the redactor doesn't touch this):**

```bash
# Terminal 1
LOGFILE="$(ls -t trial-runs/project-ikea/bristlenose-output/.bristlenose/bristlenose.log | head -1)"
grep -c "sk-ant-api03-AAA" "$LOGFILE"
# expect: 0 ideally. Non-zero = Python on-disk log contains the fake key.
```

**If the on-disk log has the key:** that's a real finding — the Swift-side redactor only masks what's published to `outputLines`, not what Python writes directly to its log file. This is known: `docs/design-desktop-python-runtime.md` "Credential flow → Residual risks" calls out "log redaction is defence-in-depth," not absolute. Note the result for the session notes; not a blocker for C3 (the primary invariant is "no disk persistence via Bristlenose," and the per-project log is ephemeral per run anyway).

### A6. Clean up Pass A before Pass B

1. **Cmd+,** → LLM → Claude → delete the fake key from the field → Save
2. **Quit the app** (Cmd+Q) — fresh sidecar launch for Pass B

## Pass B — happy path with real throwaway key (10 min)

Goal: prove that a real key from Keychain gets injected as an env var into the sidecar, and the autocode call to Anthropic succeeds.

### B1. Enter the real throwaway key

1. **Cmd+R** in Xcode to relaunch
2. Click your test project in the sidebar
3. **Cmd+,** → LLM → Claude
4. Paste your real throwaway key (the one you generated in Pre-flight, not the fake)
5. Save
6. Close Settings

### B2. Verify Swift-side env injection

In Xcode console, look for:
```
injected API key for provider=anthropic
```
Exactly one such line per sidecar launch. No key value — just the provider name. This is the `Logger.info` from `overlayAPIKeys`.

### B3. Verify env var is actually on the sidecar process

In Terminal 1:
```bash
# Find the sidecar PID
PID=$(pgrep -fn bristlenose-sidecar)
echo "sidecar PID: $PID"

# Presence check — should print exactly 1
ps ewww "$PID" | tr ' ' '\n' | grep -c '^BRISTLENOSE_ANTHROPIC_API_KEY='

# Length check — should print a number > 90 (real Anthropic keys are ~108 chars)
ps ewww "$PID" | tr ' ' '\n' | grep '^BRISTLENOSE_ANTHROPIC_API_KEY=' | awk -F= '{print length($2)}'
```

**Do not pipe this to `cat` or let the raw env line hit your screen.** The commands above are specifically designed to print only the count and the length — not the key itself — so your scrollback stays clean.

### B4. Trigger autocode (happy path)

1. Back to the app — Codebook tab
2. Click **"✦ AutoCode quotes"** on a framework
3. Job runs. Takes 10–60 seconds depending on project size.
4. Success = proposals appear in the UI, no error toast, no "No API key configured" message.

If Anthropic returns an error (rate limit, invalid cap, etc.), that's not a C3 failure — that's an Anthropic account issue. Check the key at console.anthropic.com.

### B5. Final redactor cross-check

The redactor should NEVER mask a valid in-use key because the happy path doesn't echo the key anywhere. But a final sanity check against the per-project log file:

```bash
# Pick the first 10 chars of your real throwaway key (memorise, then type here)
# Expect: 0 hits
grep -c "<first-10-chars-of-your-real-key>" "$LOGFILE"
```

If this returns non-zero you have a real-key leak on disk — stop and investigate.

## Cleanup (critical — do this immediately after)

### C1. Revoke the throwaway key

1. https://console.anthropic.com/settings/keys
2. Find `bristlenose-c3-smoke-2026-04-20`
3. Click **Revoke**

This is important because the key is now in:
- The app's Keychain (you can delete from Settings → LLM → Clear, or leave it — it's scoped to your account)
- Your shell scrollback if you typed it anywhere (you shouldn't have — the `ps ewww` commands were designed to avoid this)
- Any screen recording if you happened to have one running

Revoking at the Anthropic side makes all of the above moot.

### C2. Clear scrollback

```bash
# In Terminal 1 (and Terminal 2 if used)
clear && printf '\e[3J'
```

Or Cmd+K in Terminal.app (clears both visible buffer and scrollback).

### C3. Delete fake + real keys from Keychain (optional)

The app's Settings UI has a Clear button per provider. Or just quit the app — the fake key is revoked-by-shape anyway (never was real), and the real key is revoked at Anthropic.

### C4. Record the outcome

Open `docs/private/c3-session-notes.md`, go to "What works (proven by tests + build)" section, append one line:

```markdown
- Manual Debug smoke test (20 Apr 2026): Pass A redactor fired [✅/❌].
  Pass B env injection + autocode happy path [✅/❌]. On-disk Python
  log audit: [no fake key / contained fake key]. Throwaway key revoked.
```

## Troubleshooting

- **"Mode: bundled" doesn't appear in Xcode console.** Scheme may be set to "Bristlenose (Dev Sidecar)" or "Bristlenose (External Server)". Check the scheme selector next to the Run button.
- **`pgrep -fn bristlenose-sidecar` returns nothing.** Sidecar didn't launch. Check Xcode console for errors from `ServeManager.start`. Most common: bundle layout wrong (C1 issue, shouldn't happen post-C3) or sidecar binary not present in `Contents/Resources/bristlenose-sidecar/`.
- **Autocode button absent from Codebook tab.** Project doesn't have an imported framework. Import one via the Codebook UI first (if there's an import path) or pick a different project.
- **Autocode fails with "No API key configured" in Pass B.** Env injection didn't fire. Check: `Logger.info` line in Xcode console? `ps ewww $PID` shows the env var? Either of those missing = something's off with `overlayAPIKeys`.
- **`log stream` doesn't show anything useful.** Python's sidecar output goes through the Swift pipe, NOT unified logging. Swift's own `Logger` calls from `ServeManager` do hit unified logging. So `log stream --predicate 'subsystem == "app.bristlenose"'` shows Swift-side; Python stderr/stdout shows in Xcode console only.

## Time budget

- Pre-flight: 5 min
- Pass A: 8 min
- Pass B: 10 min
- Cleanup: 2 min
- **Total: ~25 min** wall-clock

## References

- `~/.claude/plans/c3-closeout.md` §Step 6 — the procedural source this walkthrough expands
- `~/.claude/plans/c3-keychain-in-sandbox.md` — the design plan
- `docs/private/c3-session-notes.md` — where you'll record outcome
- `docs/design-desktop-python-runtime.md` — "Credential flow" section with residual-risk framing
- `desktop/Bristlenose/Bristlenose/ServeManager.swift:375-470` — `handleLine` + `redactKeys` + `overlayAPIKeys`
- `bristlenose/server/routes/autocode.py` — the endpoint the autocode button hits
