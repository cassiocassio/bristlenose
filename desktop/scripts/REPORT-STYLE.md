# desktop/scripts — build report style

The shared look-and-protocol for build-script CLI output, so every script in this
folder renders as **one system** and adding a new one raises no design questions.

**Status (Jul 2026): shipped.** `report.sh` (emitter helpers) + `build_report.py`
(Rich renderer) are wired into `build-all.sh` (validated on a real signed build that
delivered a TestFlight `.pkg`) and the standalone gates `check-release-binary` /
`check-bundle-manifest` / `check-logging-hygiene`. Remaining siblings
(`sign-sidecar.sh` — the bar showcase — `build-sidecar.sh`, `ensure-sidecar.sh`,
`fetch-ffmpeg.sh`, `sign-ffmpeg.sh`) adopt the recipe below without redesign.

## Split of responsibilities

- **Scripts stay dumb about presentation.** A script emits *events* (structured
  sentinel lines) and redirects its noisy tool output (`xcodebuild`, PyInstaller,
  `codesign`) to a per-step log file under `desktop/build/`, exactly as today.
- **One renderer owns the look** — `build_report.py` (Rich). It reads the event
  stream on stdout, draws the report, and passes non-event lines through only in
  `--verbose`. Nothing else formats glyphs, bars, or panels.
- **Degrades to plain.** Non-TTY / `NO_COLOR` / `TERM=dumb` → no colour, no
  animation (the resting frame, still readable). Renderer never writes ANSI into
  the redirected log files. (clig.dev: don't animate a non-terminal.)

## The event protocol (the contract siblings adopt)

Scripts source `report.sh` and call its helpers, which echo sentinel lines. The
renderer parses lines beginning `@bn ` and maps them 1:1 onto the schema below.

```
@bn step   id=<tag> phase=<Phase> name="…" status=start|ok|skip|fail \
           elapsed=<sec> detail="…" narrative="…"
@bn check  parent=<tag> label="…" result=ok|warn|fail evidence="…"
@bn bar    parent=<tag> done=<n> total=<n> label="…"
@bn gate   id=<a> desc="…" result=ok|skip|fail evidence="…"
@bn art    key="…" value="…"
@bn done   status=ok|fail
```

- `tag` is the **script index** (`5`, `2a`) — kept for log grepping; the renderer
  assigns the human `1…N` display number itself.
- A step with no known count omits `@bn bar` and shows a spinner + elapsed. A step
  with a real count (per-file signing) emits `@bn bar` for a determinate bar.
  **Never fake a fraction we don't have.**
- On non-zero exit a script emits `status=fail` with the failing step; the renderer
  shows the step's log tail inside its block and a red footer. Scripts still
  `set -euo pipefail`; the report is a view, not the control flow.

## The three section schemas

| Section | Fields |
|---|---|
| **Step** | `tag, phase, name, status, elapsed, detail, narrative, checks[], bar?` |
| **Check** (leaf under a step) | `label, result, evidence` |
| **Gate** (final readiness battery) | `id, desc, result, evidence` |

Plus a **header panel** (build identity: target, identity, bundle, team, logs) and a
**footer panel** (artifact + size + signed + next action, green on success / red on
fail).

## Rendering rules

1. **Glyph vocabulary is fixed and shared** — `✓ ℹ ⚠ ✗ —` from
   `bristlenose/ui_kinds.py`. Never invent a new glyph; map new states onto these.
   Colour only for state (green ok · yellow warn · red fail · dim skip/detail),
   used sparingly.
2. **Phases group the steps** — `PRE-FLIGHT · BUILD · PACKAGE · VERIFY` headers
   with a per-phase step count; live mode also shows an `[n/N]` counter. A new
   script slots its steps into an existing phase before inventing one.
3. **Human numbering, script tag retained** — display `1…N`; show the script index
   as a dim right-aligned `[5]` / `[2a]` so both first-timers and log-greppers win.
4. **Narrative for the heavy/opaque steps** — one dim italic line saying *what it
   does and why it's slow*. Skip it for the trivially self-evident steps.
5. **Detail on the indented line**, not crammed inline — evidence (`220 binaries
   signed`, `flags=0x10000(runtime)`) sits under the step at the 8-col indent.
6. **Append-only, not a redrawing tree** — each step prints its final line when it
   completes (cargo/uv style). Spinners/bars are transient *during* a step, then
   resolve to a static line. This keeps `tail -f` on the log files sane and CI
   capture clean.
7. **Airy leaders** — spaced `· · ·` between name and the right cluster, not a
   solid dotted run.
8. **Width** — target 92 cols; wrap narrative to width−indent; right cluster
   (`[tag]  elapsed`) is right-aligned.

## Adopting the style in a sibling script (the recipe)

`report.sh` centralises the wrapper, so adoption is a fixed preamble — no per-script
boilerplate to get wrong:

```bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"   # many scripts already set this
source "$SCRIPT_DIR/report.sh"
bn_autowrap "$0" "$@"      # re-execs self piped through build_report.py if standalone
trap '_ec=$?; [ "$_ec" -ne 0 ] && bn_trap_fail' EXIT   # any abort → red footer
bn_meta title="…" done_title="✓ … clean"
bn_step_start 1 <Phase> "<Step name>" narrative="…" log="$SOME_LOG"
#   … the script's real work, UNCHANGED …
bn_step_ok 1 detail="…"    # or the trap fires on a nonzero exit
bn_done ok
```

- **Light-touch is fine for gates.** Wrap the whole check as one step; leave the
  script's internal `echo`s alone — the renderer suppresses them when pretty, and
  they reappear under `BN_REPORT=0`. Don't convert every line.
- **`bn_autowrap` handles every mode**: standalone → wraps + renders; nested under a
  rendering parent → silent (parent narrates); `BN_REPORT=0` or no python → plain
  `==>` output.
- **Redirect a noisy/opaque subprocess** to `desktop/build/<name>.log` and pass
  `log=<path>` on `bn_step_start`; the renderer shows "tail `<basename>`" while it
  runs and points there on failure.
- **Numbering**: reuse the script's own step index as the `tag`; the renderer
  assigns the human `1…N`.

## Portability & nesting (the two traps)

1. **bash 3.2 — `report.sh` MUST stay 3.2-safe.** `ensure-sidecar.sh` and the Xcode
   "Ensure Sidecar Fresh" build phase run under `/bin/bash` 3.2. So `report.sh` uses
   NO associative arrays (`local -A`), NO `mapfile`, NO `${var,,}` — only string ops,
   `case` globs, `printf %q`, `PIPESTATUS`. `_bn_field` replaces the assoc-array
   lookup. (A script that needs bash 4+ for its OWN logic — `sign-sidecar.sh`'s
   `wait -n`, `check-bundle-manifest.sh`'s `mapfile` — may require it; it's
   `report.sh` that must run anywhere. Verified against real `/bin/bash 3.2.57`.)
2. **Nesting — a child never starts a second renderer.** `bn_autowrap` exports
   `_BN_ACTIVE=1`; a child seeing it does not wrap, and its `bn_*` calls emit nothing
   (only the non-exported `_bn_owner=1`, set in the render owner, enables emission).
   So `build-all.sh` calling `check-*` produces ONE report — the gate's own narration
   is suppressed and build-all narrates the step.

## Level 2 — determinate bars (next enhancement)

The showcase is a real per-file progress bar. `sign-sidecar.sh` signs ~220 Mach-Os in
a `wait -n` job pool; emitting `@bn bar parent=<tag> done=<n> total=220` from the
completion loop renders a determinate bar under that step. Deferred for now
(instrumenting a parallel-signing loop in the critical signing path is intricate); the
renderer's `@bn bar` path is ready and its parser is hardened (`_int` clamps untrusted
counts — a bad `done=`/`total=` must not crash the report). **Never emit a bar for
work without a real count** — opaque steps spin (rule 6).

## See also

- Implementation: `build_report.py` (renderer — `--demo` / `--demo-fail` self-tests)
  + `report.sh` (emitter helpers + `bn_autowrap`). `build_report_mock.py` is the
  original static design mock (`--frame`, `--fail`, `--svg <path>`).
- Glyph/colour source of truth: [`bristlenose/ui_kinds.py`](../../bristlenose/ui_kinds.py).
- CLI output canon: [clig.dev](https://clig.dev) — human-first, honest progress,
  colour off when not a TTY.
- [`README.md`](README.md) — the per-script index this style applies to.
