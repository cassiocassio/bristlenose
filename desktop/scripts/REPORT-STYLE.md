# desktop/scripts — build report style

The shared look-and-protocol for build-script CLI output, so every script in this
folder renders as **one system** and adding a new one raises no design questions.

Prototype: `build-all.sh` first (see the Rich mock referenced at the bottom). The
rules below are the frozen decisions; siblings (`build-sidecar.sh`, `sign-sidecar.sh`,
`check-*`, `ensure-sidecar.sh`) **adopt** them without redesign.

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

## Adopting the style in a new / sibling script

1. `source "$SCRIPT_DIR/report.sh"` (once written) and replace bare `echo "==> …"`
   lines with `bn_step` / `bn_check` / `bn_bar` calls.
2. Pick the **phase** and a **`tag`** (reuse the script's existing numeric index).
3. Redirect the noisy subprocess to `desktop/build/<name>.log`; pass its path in
   `detail=` so the renderer can tail it on failure.
4. Add a one-line **narrative** only if the step is slow or opaque.
5. If the work has a real count, emit `@bn bar`; otherwise let it spin.
6. Verify the failure path: force a non-zero exit and confirm the red footer names
   the right step and shows the log tail. Nothing downstream should render.

## See also

- Prototype renderer + canned frames: `build_report_mock.py` (run `--frame`,
  `--fail`, `--svg <path>`; bare in a terminal to see it animate).
- Glyph/colour source of truth: [`bristlenose/ui_kinds.py`](../../bristlenose/ui_kinds.py).
- CLI output canon: [clig.dev](https://clig.dev) — human-first, honest progress,
  colour off when not a TTY.
- [`README.md`](README.md) — the per-script index this style applies to.
