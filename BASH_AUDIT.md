# Shell Portability Audit — Stock macOS Baseline

**Date:** 31 May 2026
**Scope:** Read-only audit. No files modified.
**Baseline:** A clean, stock macOS install — system bash **3.2.57** (2007, GPLv2-frozen) and **BSD** coreutils (NOT GNU). Assumes **no Homebrew bash** and **no GNU coreutils** on PATH.

**Why this baseline:** Testers so far almost certainly have Homebrew bash 5.x and GNU coreutils (`gsed`, `ggrep`, `gdate`, …) on their PATH, which masks every portability bug below. A "works on my machine" report from such a tester proves nothing. This audit ignores those machines and asks only: *does a clean-install user hit a real problem?*

**Checks applied to every script / inline-shell site:**
- **CHECK 1** — bash 4+ features missing from 3.2 (`declare -A`/`local -A`, `mapfile`/`readarray`, `${var^^}`/`${var,,}` case conversion, globstar `**`, `coproc`, `wait -n`, negative array index `${arr[-1]}`, `declare -g`, case fall-through `;&`/`;;&`, `&>>` append).
- **CHECK 2** — GNU vs BSD coreutils (`sed -i` with no backup arg, `date -d`/`--date`, `readlink -f`, `grep -P`, `find -printf`/`-regextype`, `stat -c`, `timeout`, `xargs -r`/`-d`, `cp --parents`, `sort -h`, `numfmt`, `tac`, and direct `gsed`/`ggrep`/`gdate`/`gtimeout`/`greadlink`/`gawk` calls).
- **CHECK 3** — runtime PATH / exec assumptions (`/opt/homebrew/bin` or `/usr/local/bin` on PATH, hardcoded non-system tool paths, missing existence checks before optional binaries).

**Severity definitions:**
- **BLOCKER** — fails for a clean-install END USER on their own Mac.
- **WARNING** — fragile; breaks for a contributor / release engineer on a stock Mac, or silently degrades.
- **NOTE** — hygiene only; no live break.

> **Critical framing for severity:** the single most important fact in this audit is *who runs the code*. The shell scripts (`desktop/scripts/`, `scripts/`, `.claude/hooks/`) and CI inline shell are **build / sign / dev / release / CI** tools. **A clean-install end user never executes any of them.** End users run only (a) the shipped Python package and (b) the signed Swift desktop app. Those two surfaces are the only places an end-user BLOCKER can live — and CHECK 1 and CHECK 2 are **completely clean** there.

---

## Headline result

| Check | End-user findings |
|---|---|
| **CHECK 1** (bash 4+ in shipped code) | **0** |
| **CHECK 2** (GNU coreutils flags in shipped code) | **0** |
| **CHECK 3** (PATH / exec assumptions in shipped code) | **2 Swift sites — but a sandbox-exec issue, not a bash/BSD-coreutils issue** (see caveat) |

For the literal shell-portability question this audit was scoped to — **bash 3.2 vs 4+, BSD vs GNU coreutils, PATH** — the shipped Python runtime is clean: every coreutils-adjacent shell-out uses argv-list form, invokes stock-macOS binaries (`security`, `sysctl`, `system_profiler`, `ffmpeg` via the bundled-binary mitigation), and contains no `sed -i` / `date -d` / `readlink -f` / `grep -P` / bash-4 syntax. No `/opt/homebrew` or `/usr/local` hardcoding in runtime code. No `gsed`/`ggrep`/`gdate` anywhere in the repo.

The two BLOCKER-class Swift sites are a **macOS App Sandbox exec ban** on `/bin/ps`, not a coreutils-flavour or bash-version problem. They are real and they affect the alpha TestFlight build, so they are reported below — but flagged honestly as adjacent to the strict CHECK 1/2/3 scope.

---

## CHECK 1 — Bash 4+ features missing from 3.2

### 1.1 — `desktop/scripts/check-bundle-manifest.sh:146` — `mapfile` unguarded — **WARNING** (dev only)

```bash
mapfile -t covered_paths < <(echo "$covered_paths_raw" | sort -u | grep -v '^$' || true)
```

`mapfile` is bash **4.0+**, absent from 3.2. There is **no `BASH_VERSINFO` guard** in this file. On a stock-Mac contributor (no Homebrew bash), `mapfile` is `command not found` → `covered_paths` stays empty → the coverage loop at line 179 reports *every* runtime-data file as `UNCOVERED` and the gate exits 1 with misleading output, even when the bundle spec is fine. It runs inside `build-all.sh` step 1b, so it would block a clean-Mac build with a confusing (not a clean "needs bash 4") error.

- **End-user impact:** none — dev/release build script.
- **Contrast (the right pattern):** `desktop/scripts/sign-sidecar.sh:43` guards its bash-4.3 `wait -n` correctly (see 1.2). The fix here is the same guard, or a `while IFS= read -r` loop (3.2-safe).

### 1.2 — `desktop/scripts/sign-sidecar.sh:158,166` — `wait -n` — **NOTE** (correctly guarded — gold-standard pattern)

```bash
# line 43 — version guard up front
if (( BASH_VERSINFO[0] < 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] < 3) )); then
    echo "error: bash 4.3+ required (got $BASH_VERSION)." >&2
    echo "  brew install bash  # then restart your shell" >&2
    exit 1
fi
# line 158 — the actual bash-4.3 feature
if wait -n; then :; else FAILED=$((FAILED + 1)); fi
```

`wait -n` is bash **4.3+**. This is the **only** script that does it right: it detects old bash up front and exits cleanly with an actionable `brew install bash` message rather than limping. Model for the others. No live break.

> No other CHECK-1 features (`declare -A`, `${var^^}`/`${var,,}`, globstar, `;&`/`;;&`, negative-index arrays, `declare -g`, `&>>`, `coproc`) appear anywhere in the repo's shell scripts, CI inline shell, package.json scripts, or `bash -c`/`sh -c` strings in application code. Parameter expansions seen across the scripts (`${var//a/b}`, `${var#prefix}`, `${var:0:80}`) are all bash-3.2-safe — none are the bash-4 case-conversion forms.

---

## CHECK 2 — GNU vs BSD coreutils

### 2.1 — `.github/workflows/homebrew-tap/update-formula.yml:68-70` — `sed -i` with no backup arg — **NOTE** (Linux-runner only)

```bash
sed -i "s|url \".*\"|url \"${{ steps.pypi.outputs.url }}\"|" Formula/bristlenose.rb
sed -i "s|sha256 \".*\"|sha256 \"...\"|" Formula/bristlenose.rb
sed -i "s|version \".*\"|version \"${VERSION}\"|" Formula/bristlenose.rb
```

The classic GNU-vs-BSD divergence: on BSD/macOS `sed`, `-i` consumes the **next arg** as the backup suffix, so this form mangles or fails. **But it runs exclusively on `ubuntu-latest` (GNU sed)** in the tap repo's own CI — never on an end-user machine or a macos runner. The only way it bites is a copy-paste into a Mac context. Listed as the single clearest GNU idiom in the repo; effectively a hygiene note. (Portable form would be `sed -i.bak '…' file && rm file.bak`, or a Python one-liner.)

### 2.2 — `.claude/hooks/block-checkout.sh:15,18,23,28` — `grep -E '\s'` PCRE-ism on BSD ERE — **WARNING** (dev safety net, fails open)

```bash
if echo "$COMMAND" | grep -qE '(^|\s*&&\s*|;\s*)git\s+(checkout|switch)\s'; then
```

`-E` (ERE) is BSD-safe — the trap here is `\s`, which is a **GNU/PCRE escape, not POSIX ERE**. BSD `grep -E` does not reliably honour `\s` as "whitespace" (often matches a literal `s`). On a stock-BSD-grep Mac these patterns can fail to match `git checkout`, so the PreToolUse hook **silently fails open** — feature-branch checkouts in the main repo would no longer be blocked. The failure is invisible (no error; lost protection). POSIX fix: `[[:space:]]` instead of `\s`.

- **End-user impact:** none — a Claude Code dev hook, hardcoded to one developer's path (`/Users/cassio/Code/bristlenose`), never shipped.

### 2.3 — `desktop/scripts/reset-sandbox-state.sh:79` — BSD-sed `\?` in `--help` text — **WARNING** (cosmetic)

```bash
sed -n '2,30p' "$0" | sed 's/^# \?//'
```

`\?` (optional quantifier) is a GNU sed BRE extension; BSD sed may treat it literally. Only affects the leading `# ` strip in `--help` output — cosmetic, may leave a stray space. Dev tool; no end-user impact.

> **Everything else under CHECK 2 is clean.** No `sed -i` without backup in any Mac-run script, no `date -d`/`--date` (all `date` usage is format-only `-u +FMT`), no `readlink -f`, no `grep -P`, no `find -printf`/`-regextype` (the scripts explicitly pipe `find … | grep -E` and comment on avoiding `-regextype` — see `check-bundle-manifest.sh:154`), no `stat -c`, no `numfmt`/`tac`/`sort -h`, no `xargs -r`/`-d`. **No direct `gsed`/`ggrep`/`gdate`/`greadlink`/`gawk` calls anywhere in the repo** — a strong signal the authors did not test with Homebrew coreutils aliased onto bare names. The shipped Python code uses argv-list `subprocess` calls only (no `shell=True` with coreutils, no GNU flags).

---

## CHECK 3 — Runtime PATH / exec assumptions

### 3.1 — `desktop/Bristlenose/.../EventLogReader.swift:211-214` — unguarded `/bin/ps` exec under App Sandbox — **BLOCKER** (alpha bundled `.app`)

```swift
proc.executableURL = URL(fileURLWithPath: "/bin/ps")
proc.arguments = ["-o", "lstart=", "-p", String(pid)]
```

Called from `pythonOwnedRunIsAlive(at:)` (PID-reuse defeat via start-time match). **Not** `#if DEBUG`-guarded — runs in Release/TestFlight builds. `desktop/CLAUDE.md` states plainly that App Sandbox blocks `Process()` exec of system binaries like `/bin/ps` at the sandbox-launch boundary regardless of the binary's own permissions. Under the shipped sandboxed `.app`, `try proc.run()` throws → `psLstart` returns `nil` → a live Python-owned run is reported **dead** (silent mis-detection of run liveness).

### 3.2 — `desktop/Bristlenose/.../PipelineRunner.swift:440-441,451-452` — unguarded `/bin/ps` exec under App Sandbox — **BLOCKER** (alpha bundled `.app`)

```swift
runCapturing(executable: "/bin/ps", arguments: ["-p", String(pid), "-o", "uid="])
runCapturing(executable: "/bin/ps", arguments: ["-p", String(pid), "-o", "args="])
```

Called from `aliveOwnedRunPID(for:)` to verify an orphaned `bristlenose run` subprocess (uid-ownership + argv match before re-attaching). Same root cause. Under sandbox both guards always fail → a genuinely-alive owned run is treated as foreign/stale, the PID file is deleted, and the run can't be re-attached after an app restart. The `#if DEBUG` block at line 967 guards only env-var reads, not these execs.

**Important caveat on these two (honesty about scope):**
- These are a **macOS App Sandbox exec ban**, not a bash-3.2 or BSD-vs-GNU-coreutils problem. The BSD `ps -o lstart=/uid=/args=` flag syntax is itself correct for stock macOS. They fall under CHECK 3 ("runtime exec assumptions") only loosely.
- They are **invisible in the current dev build** because sandbox is off (`ENABLE_APP_SANDBOX = NO`). They only manifest once the TestFlight build flips sandbox on — so they won't appear in normal Cmd+R testing. Needs a targeted check against a signed, sandboxed archive.
- The team already solved this exact class once: the Python side (`run_lifecycle.py`) was migrated from `/bin/ps` to `proc_pidinfo`/libproc. **The equivalent Swift sites were not migrated.** Fix direction: mirror the Python migration with narrow libproc syscalls (`proc_pidpath`, `proc_pidinfo(PROC_PIDTBSDINFO)`). CLAUDE.md's own "Rule of Three" note anticipates a Swift-side libproc extraction; these are needs #4 and #5.

### 3.3 — Shipped Python runtime PATH handling — **NOTE** (correctly mitigated, no gap found)

- `bristlenose/utils/{audio,video}.py`, `server/clip_backend.py`, `doctor.py` resolve ffmpeg/ffprobe via `bundled_binary_path("ffmpeg") or "ffmpeg"` then argv-list `subprocess.run`. The `prepend_bundled_to_path()` / `bundled_binary_path()` mitigation handles the sandbox + bare-name-shellout case (including transitive bare-`ffmpeg` from `mlx_whisper`/`faster_whisper`). **Verified there are no other bare-name media-tool shellouts** (`sox`, `mediainfo`, etc.) that bypass the mitigation.
- `credentials_macos.py` (`/usr/bin/security`), `hardware.py` (`sysctl`, `system_profiler`, `nvidia-smi` guarded), `run_lifecycle.py:207` (`/bin/ps` in the **non-Darwin branch only**) — all stock-macOS tools, exception-guarded, sandbox paths handled by host env-var injection. `ollama.py:264` (`sh -c "curl … | sh"`) is POSIX-only, opt-in, exception-wrapped. `cli.py:1666` (`npx vite`) is dev-only — `frontend/` is not shipped in the wheel or sidecar bundle.
- `ServeManager.swift:160` / `PipelineRunner.swift:1019` spawn the sidecar by **absolute in-bundle path** (not bare-name PATH lookup) — the correct sandbox-safe pattern.

### 3.4 — Dev-script PATH dependencies with existence checks — **NOTE**

- `desktop/scripts/build-sidecar.sh:33` hard-depends on `python3.12` but guards with `command -v python3.12` and prints `brew install python@3.12`. Clear failure, dev-only.
- `.claude/hooks/block-checkout.sh:6` depends on `jq` (not stock-macOS) with no guard — but only ever runs inside Claude Code on the configured dev machine. NOTE.
- Build/sign scripts call stock system paths (`/usr/libexec/PlistBuddy`, `/usr/bin/python3`, `/usr/bin/security`) — **no `/opt/homebrew` or `/usr/local/bin` PATH assumptions anywhere** in the shell scripts. Optional Homebrew tools (`brew`, `create-dmg`) are existence-checked before use.

---

## Per-area summary

| Area | Files audited | BLOCKER | WARNING | NOTE | End-user exposure |
|---|---|---|---|---|---|
| `desktop/scripts/*.sh` (11) | all read | 0 | 2 (`mapfile`, cosmetic `\?`) | rest | none (build/sign/dev) |
| `desktop/v0.1-archive/scripts/*.sh` (5) | all read | 0 | 0 | all (archived) | none |
| `scripts/*.sh` (4) + `scripts/*.py` | all read | 0 | 0 | minor | none (perf/research) |
| `.claude/hooks/block-checkout.sh` | read | 0 | 1 (`\s` fails open) | — | none (dev hook) |
| `.github/workflows/*.yml` + tap | all read | 0 | 0 (1 Linux-only `sed -i`) | minor | none (CI runners) |
| `frontend`/`e2e` `package.json` + `pyproject.toml` + pre-commit | all read | 0 | 0 | 0 | none |
| **Shipped Python runtime** (`bristlenose/`) | shell-out sites | **0** | 0 | mitigated | **YES — clean** |
| **Shipped Swift app** (`desktop/Bristlenose/`) | `Process()` sites | **2** (`/bin/ps`, sandbox) | 0 | rest | **YES — sandbox build** |

---

## Counts by severity

- **BLOCKER:** 2 sites / 1 class — both Swift `/bin/ps` `Process()` execs (`EventLogReader.swift:211`, `PipelineRunner.swift:440/451`), blocked under App Sandbox in the alpha bundled `.app`. *Caveat: a sandbox-exec ban, not a bash-3.2 / BSD-coreutils break.*
- **WARNING:** 3 — `check-bundle-manifest.sh:146` unguarded `mapfile` (dev build); `block-checkout.sh` `grep -E '\s'` fails open (dev hook); `reset-sandbox-state.sh:79` BSD-sed `\?` cosmetic (dev tool). **None affect end users.**
- **NOTE:** all others — including the correctly-guarded `wait -n` in `sign-sidecar.sh`, the Linux-only tap `sed -i`, and the fully-mitigated ffmpeg/bundled-binary runtime path.

---

## Verdict

**For the literal shell-portability question (bash 3.2 vs 4+, BSD vs GNU coreutils, PATH): NO — a clean-install macOS end user does not hit a real problem.** The shipped Python runtime is clean (argv-list shell-outs, stock-macOS tools, ffmpeg routed through the bundled-binary mitigation, zero GNU flags, zero bash-4 syntax). Every bash-4 / BSD-coreutils finding lives in dev / build / CI scripts that end users never run, and even those amount to one unguarded `mapfile` and two fails-open dev-hook regexes.

**The one genuine end-user-facing risk is adjacent, not coreutils-shaped:** two unguarded `/bin/ps` `Process()` execs in the Swift desktop app that the macOS **App Sandbox** blocks in the shipped TestFlight build — silently mis-detecting run liveness and breaking run re-attach after an app restart. **Worst of it: `desktop/Bristlenose/.../PipelineRunner.swift:440-452` and `EventLogReader.swift:211-214`.** It's invisible in dev because sandbox is off; it needs a check against a signed sandboxed archive, and the fix is the libproc migration the team already did on the Python side.
