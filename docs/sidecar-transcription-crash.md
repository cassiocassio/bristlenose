# The bundled sidecar crashes at transcription — SIGILL in llvmlite

**Status: OPEN.** Measured 30 Aug 2026. Reproduced twice, minutes apart, on two
different projects. Root cause **not** established; this note exists so the next
session starts from the evidence rather than from my first guess, which was
wrong and is recorded below as ruled out.

## What the researcher sees

A run started from the macOS app dies seconds in. The sidebar row shows **Run
failed**, and the diagnostic popover says *"Something went wrong during
analysis. Category: Failed"* — which names nothing, because the classifier had
nothing to classify.

Then two knock-on symptoms that look like separate bugs and are not:

- **Every lens in that project is dead.** The run wrote no terminus event, so
  `detect_status` intercepts and the SPA never mounts. Clicking any lens —
  Quotes, Codebook, Codebook v2 — appears to do nothing. This is what sent me
  looking at the v2 lens for half an hour; it is not a v2 problem.
- **`GET /dashboard 500`** on a project that had data before. The run printed
  `Cleaned <output_dir>` *before* it crashed, so the previous good output is
  gone and the endpoint is looking at a 4 KB empty database.

## Reproduction

Any run that reaches transcription, from the Debug `.app`. Both observed runs
died at the same point: preflight green, ingest and audio-extract complete,
then dead as `s05_transcribe` initialises MLX.

```
17:56:27  folder-of-horrors  run_started → run_progress → (no terminus)
17:57:38  project-ikea       run_started → run_progress → (no terminus)
```

Build under test: `v0.28.0 · faee6de8 · Debug · sandbox=on HR=off ·
sidecar=bundled`, sidecar built 15:30 the same day.

## The evidence

**It is a hard crash, not an error path.** `last-run-failure.log` records
`category=unknown status=4`. That **4 is a signal number, not an exit code** —
`PipelineRunner.captureFailureLog` logs `Process.terminationStatus` without
consulting `terminationReason`, so a signalled death is written as if it were a
clean exit. Signal 4 is SIGILL.

**The crash reports name the frame**, two of them, one per run:

```
~/Library/Logs/DiagnosticReports/bristlenose-sidecar-2026-08-30-175634.ips
~/Library/Logs/DiagnosticReports/bristlenose-sidecar-2026-08-30-175742.ips
```

Both identical: `EXC_BAD_INSTRUCTION (SIGILL)`, faulting frame
`llvm::InstCombinerImpl::visitOr` inside `libllvmlite.dylib`, reached through
`LLVMPY_RunNewFunctionPassManager` → libffi → `_ctypes` → Python. That is numba
JIT-compiling, which is what `mlx-whisper` pulls in for word-level timestamps.

**The same library JIT-compiles fine outside the bundle.** In the repo venv —
numba 0.66.0, llvmlite 0.48.0, numpy 2.4.6 — an `@njit` function compiles and
returns. So the difference is the environment the sidecar runs in, not the
library.

**The crashing process was ad-hoc signed.** Both reports show `csTeam` empty and
an auto-derived `csID`.

## Ruled OUT — do not re-derive this

**The dylib is not damaged, stripped, or truncated.** I spent a cycle on this
and it was wrong, so it is written down: the bundled `libllvmlite.dylib` looks
734 KB smaller than the venv's, and `strip` has its own crash report from the
minute the sidecar was built (`strip-2026-08-30-153045.ips`), which together
read like a smoking gun. They are not. **That size delta is signature, not
content.** With signatures removed from both:

| | unsigned content |
|---|---|
| venv | 128,476,032 |
| bundled | 128,476,128 |

96 bytes apart, and the difference is load commands — PyInstaller drops an
`LC_RPATH /usr/lib`. `otool -L` and the install name are identical. Replacing
the bundled dylib with the venv's changes nothing that matters; I tried it, and
have since restored the bundle to its as-built content.

**The general lesson:** comparing two signed Mach-Os by file size compares their
signatures as much as their code. Strip signatures before drawing a conclusion
from a byte count.

## Leading hypothesis, and why it is not yet a conclusion

`desktop/bristlenose-sidecar.entitlements` documents this exact area in its own
header — 7 Jun 2026, numba/llvmlite JIT-compiling under Hardened Runtime,
surfacing as *"Run failed (no terminus event) / unknown"*, crash reports at the
same path. The fix then was `cs.allow-jit` +
`cs.allow-unsigned-executable-memory`, and the shipped sidecar binary **does**
still carry both (verified by dumping entitlements off the binary in the app).

The open question is whether those exceptions are *honoured* here. Restricted
`com.apple.security.cs.*` entitlements are treated differently on an ad-hoc
signature than on an Apple-issued one, and this sidecar is ad-hoc: `SIGN_IDENTITY`
is exported only by `build-dmg.sh`, never by the Xcode build phase. If that is
the mechanism, it is the June failure wearing a different signal.

**What weakens it:** Debug sidecars have *always* been ad-hoc, so if
transcription has ever worked from a Debug build, ad-hoc alone is not
sufficient. Something else changed too — a macOS update tightening ad-hoc JIT is
the obvious candidate and is unverified. Worth establishing early: **has anyone
transcribed successfully from a Debug `.app` recently?** That one answer splits
the hypothesis space in half.

## The next experiment

Re-sign the sidecar tree under a real identity and re-run one project:

```bash
SIGN_IDENTITY="Apple Development: Martin Storey (9Y4JDA9M3K)" desktop/scripts/sign-sidecar.sh
```

If transcription then completes, the entitlements-on-ad-hoc reading is right and
the fix belongs in the Xcode build phase, not in a script anyone has to remember
to run.

The tempting alternative — running the bundled sidecar straight from a terminal
to compare sandboxed against not — **is not a clean control**: the sidecar
declares `com.apple.security.inherit`, and a nested helper with `inherit` and no
sandboxed parent can abort for reasons of its own. A negative result there would
prove nothing.

## Three defects worth fixing whatever the root cause turns out to be

1. **A signalled run is reported as an exit code.** `status=4` reads as "exited
   4" and sends you looking for an exit-code table that does not exist. It was
   SIGILL. `captureFailureLog` should consult `terminationReason` and say
   `signal=SIGILL`, which would also give the classifier something better than
   `unknown` — and the popover something better than *"Something went wrong."*
   A crash report existed at a known path the whole time and nothing pointed at
   it.
2. **Clean-then-crash destroys the previous good output.** Both runs wiped the
   output directory and then died, leaving projects with neither their old
   report nor a new one. The clean should not be irreversible before the run has
   demonstrated it can get past its first real stage.
3. **`/dashboard` 500s on an empty project** instead of rendering an empty
   state, and the SPA surfaces the raw `GET /dashboard 500` in error red — the
   same class the 20 Aug corpus pass was written to catch.

Defect 1 is the one that cost the most time here: the popover, the failure log
and the classifier all said "unknown" while the operating system had already
written down the exact faulting frame.
