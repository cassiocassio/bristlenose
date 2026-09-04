# Copy-error surfacing — diagnosis

**Status: diagnosis. No fix applied.** Probes pinned in
`desktop/Bristlenose/BristlenoseTests/CopyErrorSurfacingTests.swift`; the defect
is annotated at its site in `ContentView.swift`. Written 4 Sep 2026 after a
three-arm review trial flagged "CopyError isn't `LocalizedError`" and the
maintainer asked for the scenarios, the cause, the size, the test, the
evidence, and a proof plan — before any change.

Every claim below is labelled **MEASURED** (a test or command run on this
machine, output quoted), **VERIFIED** (read in code or git history), or
**INFERRED** (reasoned, not observed). Two claims made in conversation before
this doc turned out wrong when checked against the measured record; they are
kept in §7 so they are not re-derived.

---

## 1. The defect, precisely

The three review arms all said: *"`CopyError` doesn't conform to
`LocalizedError`, so it surfaces as Foundation's placeholder string."* That is
true and it is not the bug. The bug is narrower and worse: **the same error
renders two different strings depending on which gesture the researcher used.**

`CopyMachinery.copy()` has two callers in `ContentView.swift`, written two
months apart, and their catch blocks diverge — **VERIFIED**, `git blame`:

| Site | Gesture | Written | Handles `.underlying`? |
|---|---|---|---|
| 1 | loose files dragged to the sidebar → save panel → new project | `0ac2136d`, 10 Jul 2026 | **No** — falls to `catch { toast.show(error.localizedDescription) }` |
| 2 | files dropped onto an existing project row | `51c6cb45`, 15 May 2026 | Yes — `catch .underlying(let msg) { toast.show(msg) }` |

Site 1 was written whole, in one commit, without the arm. It is an omission,
not a decision — nothing in the commit body discusses it.

**MEASURED** — the same `.underlying` error, as each site renders it
(`CopyErrorSurfacingTests`, output captured to the sandboxed host's
`temporaryDirectory`, 4 Sep 2026):

```
site2.underlying: “P07.mp4” couldn’t be copied because you don’t have permission
                  to access “copy-error-probe-B497C376-…”.
site1.underlying: The operation couldn’t be completed.
                  (Bristlenose.CopyMachinery.CopyError error 1.)
site1.inFlight:   The operation couldn’t be completed.
                  (Bristlenose.CopyMachinery.CopyError error 1.)
```

Site 2 shows Foundation's sentence: it names the file, the folder, and the
reason. Site 1 shows an opaque integer. The wrapped reason — the one useful
thing `.underlying` carries — is discarded. And the hardcoded English
`"Another copy is already in flight."` is discarded the same way, so at site 1
the researcher gets neither the English nor a localised string.

(The integer is `1`, not the `2` predicted from declaration order. Recorded
because the prediction was wrong; do not rely on that number for anything.)

## 2. Every path through `copy()`, and what each site shows

**VERIFIED** from `CopyMachinery.swift` throw sites and both catch blocks.
Rows marked ✓ are designed and correct; the divergence rows are the defect;
the last row is not an error path at all.

| Trigger | Thrown | Site 1 shows | Site 2 shows | Verdict |
|---|---|---|---|---|
| Disk-space precheck fails (cross-volume only) | `.insufficientDiskSpace` | dedicated alert, localised, byte counts | same | ✓ designed |
| User cancels via the row ring | `CancellationError` | nothing (pill rolled back) | same | ✓ designed |
| Nothing survives the extension filter | `.noItemsAfterFiltering` | **enum-index string** | silent ("should not happen — we filtered above") | site 1 wrong; site 2 has the comment, site 1 has the toast |
| Permission denied on destination (EPERM/EACCES) | `.underlying(msg)` | **enum-index string** | Foundation sentence — **MEASURED** | **divergence** |
| Disk fills mid-copy (same-volume non-APFS skips the precheck) | `.underlying(msg)` | **enum-index string** | Foundation ENOSPC sentence | **divergence**; also the `insufficientDiskSpace` alert exists and is unreachable from here |
| Source vanishes / unreadable mid-copy | `.underlying(msg)` | **enum-index string** | Foundation sentence | **divergence** |
| Case-collision on a case-insensitive volume (`fileExists` missed it) | `.underlying(msg)` | **enum-index string** | Foundation "already exists" | **divergence** |
| A second drop while one copy runs | `.underlying("Another copy is already in flight.")` | **enum-index string** — **MEASURED** | the English literal, in all 21 locales | **divergence** + unlocalised |
| Source is cloud-evicted (dataless) | **nothing — `copyItem` hangs** | — | — | **not a surfacing problem**; see §5 |

Three of the divergence rows carry a second problem: the `.underlying(String)`
wrapper flattens the error at `CopyMachinery.swift:123`
(`error.localizedDescription`), so the domain and code are gone before either
site sees it. The mid-copy ENOSPC row is the concrete cost — a dedicated,
localised disk-space alert exists for exactly this failure and cannot be reached
because the call site can no longer tell ENOSPC from anything else.

## 3. Cause

Two independent causes, both **VERIFIED** in history:

1. **The omission.** Site 1 (`0ac2136d`) was written two months after site 2
   (`51c6cb45`) and did not copy its `.underlying` arm. Nothing shared the
   mapping, so nothing could keep them aligned.

2. **The un-reviewed survivor.** The toast surface was deliberately culled on
   19 Aug 2026 — six `desktop.toast.*` strings, four drop refusals, the
   undo-toast fuse (`5598bd39`, `3acfcef0`; rationale in
   `design-sidebar-drop-behaviour.md` §"Why we're revisiting" and the
   anti-pattern in `design-pipeline-diagnostic-popover.md`). The closing commit
   says in terms: *"Nine `toast.show(` call sites remain in other flows
   (feedback, **copy errors**, cloud import) — untouched, and not reviewed
   here."* Copy-error surfacing is therefore the one part of the toast story
   that never had the design treatment the rest got. It is not that a decision
   was made and this is it; it is that the decision was explicitly deferred.

A third fact bears on the size of any fix. The taxonomy doc's own "adding a new
message" flowchart says *"A new toast surface needs `ToastStore.show(_, kind:)`."*
**VERIFIED**: `ToastStore.show` takes a `String` and a duration. There is no
`kind:` parameter. The doc describes an API that does not exist.

## 4. How we know it is real — and what we don't know

**Known, measured:** the strings in §1, from a real permission failure driven
through `copy()` under the sandboxed test host. The `withKnownIssue` wrapper
records the defect on every suite run without reddening `main`; if someone
fixes the enum, Swift Testing reports "known issue did not occur" and the test
demands updating. That is the intended tripwire.

**Known, verified:** zero tests exercised `copy()` before this — all 16
existing tests cover the pure helpers (`planItems`, `resolveDestinations`,
`appendCount`, `sourcesShareVolume`). No error path had ever been executed under
test.

**Not known, and honestly unmeasurable today:**

- **How often researchers hit it.** There is no telemetry on copy failures, and
  this machine's `projects.json` holds zero projects, so nothing can be
  measured locally. The scenarios in §2 are real code paths; their frequency is
  **INFERRED** to be low-but-non-zero (permissions, full disks, mid-copy
  vanishing are all ordinary Mac events). Do not cite a frequency.
- **Whether site 1's gesture is common.** It is the loose-files-to-empty-sidebar
  path — a first-run gesture. **INFERRED** that a first-run researcher is more
  likely than most to hit a permission or space problem and less able to
  interpret an enum index.

## 5. What this is *not* — three things that got conflated

**The dataless-source hazard is not a surfacing problem, and it is not new.**
The trial credited its out-of-the-box arm with "discovering" that `copyItem`
on a cloud-evicted file blocks. `desktop/CLAUDE.md` has carried that as a
gotcha since **19 Jun 2026**, **MEASURED** with `sample <pid>` showing the
`libcopyfile → com.apple.CloudDocs` frames: `copyItem` **hangs forever with no
error, no partial file, no sandbox denial**, and `Task.cancel()` cannot break it
because cancellation is only checked between files. `inFlight` never clears; the
app needs a force-quit. A fix brief exists in the maintainer's private handoffs
(`copy-evicted-source.md`). Neither catch site ever sees an error, so no
surfacing change touches it. It was a rediscovery, and the trial artifact now
says so.

**The axis is not read-vs-copy. It is the caller's materialisation policy.**
This section was first written on the wrong axis and corrected the same day
after a research pass measured the kernel behaviour on this machine.

The kernel decides what happens when any syscall touches a dataless file by a
per-process I/O policy, `IOPOL_TYPE_VFS_MATERIALIZE_DATALESS_FILES`, inherited
across spawn:

| Policy | `read(2)` / `Data(contentsOf:)` | `FileManager.copyItem` |
|---|---|---|
| **ON** (2) | blocks until the provider delivers the bytes, then succeeds | blocks the same way, then copies |
| **OFF** (0/1) | fails instantly, `EDEADLK` = **errno 11** on macOS | fails instantly, `NSCocoaErrorDomain 512` / POSIX 11 |

Reads and copies behave **identically** within a policy state. What differed
between the project's two earlier measurements was not the operation but the
process: the 19 Jun "hangs forever" gotcha was measured in the app (ON); the
28 Jul "`EDEADLK`" finding came from tools listed without an OS, carries
**Linux's** errno number (35 is `EAGAIN` on macOS — SDK header, verified), and
a research pass traced its phrasing to a measurement inside an Ubuntu VM. That
attribution I could not confirm from the commit history, which cites no source;
the number being wrong for macOS I could.

**MEASURED, 4 Sep 2026, inside the sandboxed test host** (`APP_SANDBOX_CONTAINER_ID
= app.bristlenose`, `DatalessPolicyProbeTests`):

```
dataless.policy.process: 2   ← ON
dataless.policy.errno.EDEADLK: 11
dataless.policy.errno.EAGAIN: 35
```

A shell-launched Python on the same machine reads `process=2 thread=0` too
(**MEASURED**, `ctypes` → `getiopolicy_np`), so the app is not special-cased —
it inherits the user-session default like every other GUI process.

So **Bristlenose runs with materialisation ON** (MEASURED). That the sidecar
it spawns does too is **INFERRED** — from the kernel's documented inheritance of
this policy across spawn (`P_VFS_IOPOLICY_INHERITED_MASK`) — and **corroborated**
by the project's own 29 Jul reproduction: `ffprobe` under the sidecar *timed out
after 30 s* on evicted Dropbox files, which is ON-shaped blocking; an OFF
process would have failed instantly with errno 11. Not measured directly in a
spawned sidecar. Consequences:

- The app never sees `EDEADLK` under normal launch. That path belongs to
  launchd jobs lacking `MaterializeDatalessFiles`, processes that opt out, and
  VM bridges. It is real; it is not ours.
- The hazard the app actually has is the **blocking** one: `copyItem` on an
  evicted source waits in `msleep(… PVFS|PCATCH …)` with no timeout,
  interruptible only by a signal. No progress, no partial file, and
  `Task.cancel()` cannot reach a synchronous call. That is the force-quit hang,
  and the 29 Jul `ffprobe` 30-second timeouts on Dropbox are the same mechanism
  seen from the sidecar.
- **`NSFileCoordinator` is not the fix for this app.** Under ON, a coordinated
  read materialises exactly as an uncoordinated one does — it changes neither
  the blocking nor the cancellability. Coordination matters for OFF-policy
  callers and as a fence against the sync daemon; the storage doc's "the fix
  is `NSFileCoordinator`" was written against the wrong policy state.
- The non-blocking shape every shipping app converges on is: detect
  (`SF_DATALESS` via `st_flags`, or `ubiquitousItemDownloadingStatus` — both
  work cross-provider, files and folders) → `startDownloadingUbiquitousItem`
  (returns in 1–3 ms) → poll with a wall-clock bound → then copy. **The sidecar
  already does this**: `bristlenose/utils/fs.py` carries `SF_DATALESS`,
  `is_dataless()`, and `ensure_materialised()` with `MATERIALISE_TIMEOUT_SECONDS`.
  The desktop copy path at `CopyMachinery.swift:107` does not, and should mirror
  it rather than invent a third pattern.
- `brctl download` / `brctl evict` **no longer exist** on 26.4.1 (verified —
  both fall through to usage). `startDownloadingUbiquitousItem` /
  `evictUbiquitousItem` are the surviving API. Any recipe or fix note naming
  `brctl` is stale.

**`.inCloud` is unreachable for evicted media, and that is documented.**
`ProjectAvailability` short-circuits on `fileExists(atPath: path)` — the project
*folder* — before any location check. An evicted folder still exists, so it
resolves `.ready` and holds a lease. The chain "cloud state → no lease → EPERM
on copy" is therefore false; the storage doc said so on 29 Jul. The lease fix
landed on 3 Sep (`84c823ea`) stands on the contract in `ProjectBookmarkLease`,
not on that chain, and its reachable population is projects with a path but no
bookmark data (prevalence unmeasured) plus the 51st-onward project.

## 6. Size of the fix — three tiers, and they must not be bundled

The trial's "CopyError redesign" was one item. It is three, of very different
weight, and only the first is a bug fix. The other two are design decisions the
toast cull explicitly deferred, and they should be taken as such.

### Tier 0 — the bug fix: one shared mapping (small; do this)

Extract a single function both sites call —

```
CopyError → (presentation: alert | toast | silent, text: String)
```

— and make the two catch blocks one line each. This is the **durable** shape,
not the one-line patch (adding an `.underlying` arm at site 1) that fixes the
symptom and leaves the two sites free to diverge again the next time one is
edited. A pure function is also what the probes can target: the
`withKnownIssue` tests in `CopyErrorSurfacingTests` currently pin the enum's
`localizedDescription`, because view code is not unit-testable; rewrite them
against the mapping and they become real assertions instead of tripwires.

Touches: `ContentView.swift` (two catch blocks), one new pure function, the
test file. No enum change, no locale change, no toast change. Behaviour at site
2 is unchanged; site 1 becomes identical to it.

**Proof:** the rewritten tests assert both sites produce Foundation's sentence
for the permission case, and the silent/alert cases route correctly. The
"known issue did not occur" signal from the current tests is the confirmation
that the enum path is no longer reached.

### Tier 1 — hygiene (small, separable)

- Conform `CopyError` to `LocalizedError` with an `errorDescription` per case,
  so any *future* caller that forgets the mapping still gets a sentence. Four
  sibling enums already conform (`CloudDownloadError`, `SidecarResolveError`,
  `ZoomOAuthError`, `MicrosoftOAuthError`); this one is the outlier.
- Route `"Another copy is already in flight."` through a locale key — one key,
  21 full locales (not `zh-Hant-HK`). It is the only user-facing string in the
  file with no key.
- Decide what `.noItemsAfterFiltering` means at site 1, where it is reachable
  in principle and currently renders the enum index.

### Tier 2 — the deferred design (real work; a decision first)

- Carry the original `Error` in `.underlying`, not a `String`, so a call site
  can recognise `NSFileWriteOutOfSpaceError` mid-copy and raise the existing
  disk-space alert. Touches the enum shape and both call sites.
- **Whether a copy failure should be a toast at all.** The cull's rationale —
  toasts aren't HIG; state already on screen shouldn't be re-announced —
  applies less cleanly here: a failed copy leaves *no* state on screen (the
  files are simply absent and the pill has gone). But the anti-pattern says
  "don't reach for a toast," and the honest answer is that this case was never
  drawn. Per that doc's own rule, the review happens on the mockup: draw the
  failure state before deciding the surface.
- If a toast survives that decision, `ToastStore.show(_, kind:)` has to be
  built — the flowchart cites it, the code lacks it.

## 7. Claims retracted while writing this

Recorded so they are not re-derived:

1. *"Cloud state triggers the lease bug."* Wrong — §5. Reasoned from code
   without reading the storage doc, which had measured the opposite.
2. *"copyItem on a dataless file fails with EDEADLK."* Wrong — §5. And the
   first correction of it, *"reads get EDEADLK, copies hang"*, was **also**
   wrong: it put the difference on the operation when it is on the caller's
   policy. Committed in an earlier revision of this doc and fixed the same
   day once the policy was measured in-process.
3. *"The dataless finding was the trial's highest-value discovery."* It was
   a rediscovery of a documented, briefed defect.

The shape shared by all three: reasoning from code and a doc *summary* when the
*measured record* already existed and said otherwise. The record for this
subsystem lives in `desktop/CLAUDE.md` (gotchas) and
`design-project-storage.md` §3 (reproduced end to end). Read those before
reasoning about cloud files.

## 8. Evidence — the research pass, 4 Sep 2026

A research pass gathered first-hand accounts and ran its own probes on this
Mac (macOS 26.4.1). Items marked ✓ were independently re-verified here; the
rest are the pass's findings with their sources. The pass disclosed that its
probes materialised five of the maintainer's own cloud files by ≤2 bytes total
and evicted them back with `evictUbiquitousItem` — net state unchanged.

| Claim | Status | Source |
|---|---|---|
| macOS `EDEADLK` = 11; 35 = `EAGAIN` | ✓ SDK `errno.h` | — |
| Sandboxed app runs materialisation policy **ON** (2) | ✓ measured in-process | `DatalessPolicyProbeTests` |
| `brctl evict` / `download` gone on 26.4 | ✓ | — |
| Sidecar already has detect + bounded-materialise | ✓ `fs.py:108–200` | — |
| Under OFF, `copyItem` → `NSCocoaErrorDomain 512` / POSIX 11 instantly | pass measured | probe sources in session scratchpad |
| Under ON, `Data(contentsOf:)` blocks ~2 s and materialises (Dropbox) | pass measured | same |
| Coordinated read materialises even under OFF, iCloud and Dropbox | pass measured | same |
| `startDownloadingUbiquitousItem` returns in 1–3 ms, file lands ~750 ms later, works on Dropbox | pass measured | same |
| Kernel wait is `msleep(… PVFS\|PCATCH …)`, no timeout, signal-interruptible; resolver give-up → `ETIMEDOUT` | documented | XNU `vfs_syscalls.c` |
| Apple's own words: opt out and "handle any EDEADLK errors" | documented | TN3150 §Option 2 |
| `coordinateAccessWithIntents:` and coordinated *writes* do **not** force download — only coordinated reads | DTS-confirmed bug | Apple Forums 764270, Oct 2024 |
| Sonoma moved iCloud from `.icloud` stubs to File Provider dataless files | first-hand | Oakley, Bombich, Oct 2023 |
| **26.3+: sandboxed app can lose all FP-backed access mid-session** (`NSFileProviderErrorDomain -2001`); coordinated reads don't help; only relaunch recovers; DTS engaged, unresolved | first-hand, FB22547671 | Apple Forums 823369, Apr 2026 |
| 26.4.1: writes into iCloud Drive can silently never upload (stale QUIC session in `nsurlsessiond`) | first-hand, FB22476701 | Apple Forums 822534 |
| Time Machine skips dataless files; Arq renders EDEADLK as "Cloud file contents not present on disk"; CCC downloads-copies-evicts in batches | first-hand | vendor docs and release notes, 2023–26 |
| `fileExists` / `listdir` return true for placeholders — they lie | documented + this repo | TN3150; `design-cloud-import.md` |

**What the pass could not verify:** materialisation behaviour *under* App
Sandbox beyond the policy value (its own probes were unsandboxed); whether the
26.3 access-loss bug reaches `copyItem` mid-flight (reports cover enumeration
and extension issuance, not copies); native OneDrive / Google Drive behaviour
on 26.x (all reports are 2022–25 and mostly OneDrive).

**Bearing on the fix.** Tier 2 in §6 gains a required component: the desktop
copy path must detect-then-bounded-materialise before `copyItem`, mirroring
`fs.py`, or the hang stays regardless of how errors are surfaced. And the
26.3 access-loss bug is a new scenario for §2 — a copy that fails with a
File Provider error mid-session because the sandbox extension vanished —
which no catch site can distinguish today because `.underlying` flattens the
domain.
