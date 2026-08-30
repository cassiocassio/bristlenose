# The bundled sidecar crashed at transcription — SIGILL from a corrupt dylib

**Status: SOLVED, 30 Aug 2026.** Root cause found, fixed, and gated. The
investigation ran across two sessions; the first established the evidence and
ruled out a wrong lead, the second found the cause. Both halves are kept, because
the wrong lead is instructive and the way it misled is a trap anyone here can
fall into again.

## The answer, in one paragraph

PyInstaller shells out to `strip` for every collected binary and **never checks
its exit status**. On 30 Aug 2026 `strip` died of SIGBUS inside `writeout_to_mem`
partway through rewriting `llvmlite/binding/libllvmlite.dylib` (128 MB), having
already created its output file. PyInstaller collected the result: a dylib of
exactly the right size, correctly signed afterwards, with **16,384 bytes of zeros
at offset 0x02b20000 — inside `__TEXT,__text`**. On arm64 an all-zero word decodes
as `udf #0`, permanently undefined. The first numba JIT compilation to execute
into that page raised `EXC_BAD_INSTRUCTION`. Nothing in the build was red.

## What the researcher saw

A run started from the macOS app died seconds in. The sidebar row showed **Run
failed**, and the diagnostic popover said *"Something went wrong during analysis.
Category: Failed"* — which named nothing, because the classifier had nothing to
classify.

Then two knock-on symptoms that look like separate bugs and are not:

- **Every lens in that project was dead.** The run wrote no terminus event, so
  `detect_status` intercepts and the SPA never mounts. Clicking any lens — Quotes,
  Codebook, Codebook v2 — appeared to do nothing. This cost the first session half
  an hour of reading the v2 lens; it was never a v2 problem.
- **`GET /dashboard 500`** on a project that had data before. The run printed
  `Cleaned <output_dir>` *before* it crashed, so the previous good output was gone
  and the endpoint was looking at a 4 KB empty database.

## The evidence

**It was a hard crash, not an error path.** `last-run-failure.log` recorded
`category=unknown status=4`. That **4 was a signal number, not an exit code** —
`PipelineRunner.captureFailureLog` logged `Process.terminationStatus` without
consulting `terminationReason`, so a signalled death was written as if it were a
clean exit. Signal 4 is SIGILL. **Fixed** — see "What was changed" below.

**The crash reports named the frame**, identically in every occurrence:
`EXC_BAD_INSTRUCTION (SIGILL)`, faulting in `llvm::InstCombinerImpl::visitOr`
inside `libllvmlite.dylib`, reached through `LLVMPY_RunNewFunctionPassManager` →
libffi → `_ctypes` → Python. That is numba JIT-compiling, which `mlx-whisper`
pulls in for word-level timestamps — specifically `dtw_cpu` in
`mlx_whisper/timing.py`, which is `@numba.jit(nopython=True, parallel=True)`. The
`parallel=True` matters: it runs the far heavier ParallelAccelerator pipeline, and
`InstCombine` is in it. A plain `@njit` probe compiles fine and proves nothing.

## How it was found — the reproduction that settled it

The first session believed the sandbox or the entitlements were implicated, and
noted that running the bundled sidecar from a terminal is not a clean control
because it declares `com.apple.security.inherit`. That is true of **the copy
inside the `.app`**. It is not true of a copy you sign yourself:

```bash
cp -Rc "<App>/Contents/Resources/bristlenose-sidecar" /tmp/sc-nosandbox
codesign --force --sign - /tmp/sc-nosandbox/bristlenose-sidecar   # adhoc, no runtime, NO entitlements
_BRISTLENOSE_HOSTED_BY_DESKTOP=1 /tmp/sc-nosandbox/bristlenose-sidecar run /tmp/tiny-audio-folder
```

`run` is a passthrough command in `desktop/sidecar_entry.py`, gated on that env
var, so the frozen binary drives a real pipeline from a terminal. It exited
**132** — 128 + 4, SIGILL — with **no sandbox, no hardened runtime and no
entitlements at all**. That killed the signing hypothesis outright and moved the
search to the file itself.

Replacing the one dylib and re-running the same probe completed the whole
pipeline in 18.7s. That is the proof.

## Ruled OUT — do not re-derive these

**Signing, entitlements, the sandbox, and the ad-hoc signature.** Reproduced with
all of them absent (above). Two independent facts agreed: transcription had
succeeded from the desktop app on **27 Aug** (`hosted_by_desktop=True`, five
sessions, 89.35s of real MLX work, in `IKEA with uxfriends`) and Debug sidecars
have *always* been ad-hoc; and macOS had not been updated since **6 Apr 2026**
(`SystemVersion.plist` mtime; 26.4.1 / 25E253), so no OS tightening happened in
the window.

**The numba/llvmlite version bump.** The 29 Aug `.venv-sidecar` recreate did move
numba 0.66.0 → 0.67.0 and llvmlite 0.48.0 → 0.49.0, and that is a real and
suspicious coincidence — but both versions compile `dtw_cpu` correctly outside the
bundle, and the repaired bundle runs 0.49.0 fine. **No pin is needed**, and adding
one would have been cargo cult.

**The dylib being "stripped or truncated".** The first session's conclusion here
was right for the wrong reason, and the reason is the trap:

> **`THE SIDECAR IS NOT BUILT FROM `.venv`.** It is built from a dedicated
> **`.venv-sidecar`** (`build-sidecar.sh:45`), carrying only
> `.[serve,apple,desktop,mcp]`. The two have different contents — on 30 Aug,
> different numba, llvmlite and mlx versions.

Comparing the bundle against `.venv` therefore compares two *different libraries*
and the result means nothing. It produced a 96-byte delta attributed to an
`LC_RPATH` difference, and the conclusion "the dylib is fine". Against the correct
source the sizes are **identical** and the **hashes differ** — 14,893 bytes across
1,326 runs, and the big cluster is a solid 16 KB of zeros in executable code.

**The general lesson stands and is worth keeping:** comparing two signed Mach-Os
by file size compares their signatures as much as their code. Strip signatures
before drawing any conclusion from a byte count. **And compare against the source
the artefact was actually built from.**

## What was changed

1. **`strip=False`** in `desktop/bristlenose-sidecar.spec` (both `EXE` and
   `COLLECT`), with the incident recorded inline. The trade it was making,
   measured on the same bundle: across a 14-binary sample `strip` saved **48 KB of
   a 479 MB bundle**, because wheels already ship stripped binaries — and it saved
   **exactly zero bytes** on `libllvmlite`, the one file it destroyed. Turning it
   off cost ~1 MB (479M → 480M).

2. **`desktop/scripts/check-bundle-integrity.py`** — a gate that walks every
   Mach-O in the bundle and fails if `__TEXT,__text` contains a zero run of ≥4096
   bytes. Validated both ways: it flags the corrupt dylib at exactly
   0x02b20000, and clears **1 of 224** files on the damaged bundle with no false
   positives. ~4s. Wired into `build-sidecar.sh` on every real invocation — not
   only when layer P rebuilds, because a bundle that was already corrupt when
   cached would otherwise be skipped forever.

3. **`ProcessOutcome`** (`desktop/Bristlenose/Bristlenose/ProcessOutcome.swift`)
   — `Process.terminationStatus` cannot tell an exit code from a signal number;
   only `terminationReason` can. Logs and `last-run-failure.log` now read
   `signal=SIGILL(4)` rather than `status=4`, and a signalled death additionally
   emits the path where the OS wrote the crash report. Pinned by
   `ProcessOutcomeTests`, whose first test is the exact regression.

## Still open — two defects this incident exposed, neither yet fixed

1. **Clean-then-crash destroys the previous good output.** `cli.py:1200`
   `shutil.rmtree(output_dir)` runs after preflight and before the pipeline, so
   both crashed runs wiped their project and left nothing. project-ikea's data is
   still gone; restoring it needs a real run with LLM spend.

   The obvious fix — rename to a dot-prefixed sibling instead of deleting, and
   remove it on success — is safe from re-ingestion (`s01_ingest.py:200` skips all
   dot-prefixed entries) but is **not crash-safe on its own**: a SIGILL runs no
   cleanup, so the restore has to happen at the *next* start, alongside the
   existing stranded-run reconciliation. That placement is a design decision, not
   a patch.

2. **`/dashboard` 500s on an empty project** instead of rendering an empty state,
   and the SPA surfaces the raw `GET /dashboard 500` in error red — the same class
   the 20 Aug corpus pass was written to catch. The obvious suspect is not it: the
   percentage division at `routes/dashboard.py:344` is already guarded by
   `if total_words > 0`. This one needs a reproduction, not a reading.

## The meta-lesson

Every gate in the build was green on a bundle whose executable code had a hole in
it. `codesign -v --strict` passes, because the damage happened *before* signing.
The size looks right. `otool -L` and the install name are unchanged. The tests all
pass, because they run against `pip install -e .`, not the bundle.

The only evidence was a crash report, and the one surface that could have pointed
at it rendered the signal as an exit code. **A build that produces an artefact
should assert something about the artefact**, which is what
`check-bundle-integrity.py` now does — in four seconds, against the class of
failure rather than this instance of it.
