---
status: partial
last-trued: 2026-09-12
trued-against: HEAD@main on 2026-09-12 (fbd8f4f3 landed Tier 0; f54f9861)
---

> **Truing status:** Partial — trued 12 Sep 2026. §5, §6 (Tiers 1–2), §7 and §8 are
> current; §1, §2 and §4 are the 4 Sep 2026 measurement of a defect closed by
> `fbd8f4f3` and carry per-section banners saying so — read them as the record the
> fix was judged against, not as the state of the tree. See the changelog and the
> inline banners.

## Changelog

- _2026-09-12_ — trued up after Tier 0 landed: retitled; status line rewritten; §2 and §4
  banners added (§1's existed); the flatten claim (§2), the `CopyMachinery` anchors (§2,
  §5), the §8 "cannot distinguish" clause and the §8 `fs.py` range corrected; Tier 0's
  body put in past tense with its locale debt stated; Tier 1 rewritten (three unkeyed
  literals, not one; `.noItemsAfterFiltering` now spoken at site 1); the measured-record
  pointer gained its public twin; §8 gained the back-reference to
  `design-cloud-wait-label.md`. Anchors: commits "a failed drag-in copy now says why,
  whichever gesture started it", "copy-error doc: the §8 brctl row pointed at §7";
  `CopyMachinery.swift` `enum CopyError`, `ContentView.swift` both catch sites,
  `CopyErrorSurfacingTests.swift`.
- _2026-09-04_ — initial draft (diagnosis; the second research pass was appended the same day).

# Copy-error surfacing — diagnosis, fix, and what remains

**Status: Tier 0 fixed 12 Sep 2026 (`fbd8f4f3`); Tiers 1–2 open.** The defect below is
the 4 Sep measurement; the probes in `CopyErrorSurfacingTests.swift` are now positive
assertions, and the site comment in `ContentView.swift` describes the fix. Written 4 Sep 2026 after a
three-arm review trial flagged "CopyError isn't `LocalizedError`" and the
maintainer asked for the scenarios, the cause, the size, the test, the
evidence, and a proof plan — before any change.

Every claim below is labelled **MEASURED** (a test or command run on this
machine, output quoted), **VERIFIED** (read in code or git history), or
**INFERRED** (reasoned, not observed). Three claims made in conversation before
and during this doc turned out wrong when checked against the measured record —
one of them twice; they are kept in §7 so they are not re-derived.

---

## 1. The defect, precisely

> **Fixed 12 Sep 2026.** `CopyError` is `LocalizedError` with `.underlying(Error)` and an
> `.alreadyInFlight` case; both catch sites render one sentence, and the `withKnownIssue`
> probes became positive assertions (`CopyErrorSurfacingTests`, four tests, green in the
> Swift suite). This section describes the defect as measured on 4 Sep. Tiers 1–2
> are tracked in `TODO.md` § Ideas.

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

> **As measured 4 Sep 2026; closed by `fbd8f4f3`.** Every "shows" below is the 4 Sep
> rendering and every "Thrown" cell the 4 Sep payload (`.underlying(String)`). Since
> 12 Sep both sites render `errorDescription` — site 1's six "enum-index" cells now read
> the same sentence as site 2's — and the in-flight literal is `.alreadyInFlight`. Kept
> verbatim as the measurement the fix was judged against.

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

Three of the divergence rows carried a second problem: until `fbd8f4f3` the
`.underlying(String)` wrapper flattened the error (`error.localizedDescription`),
so the domain and code were gone before either site saw it. `.underlying(Error)`
now carries the error whole (the throw in `copy()`'s catch, `CopyMachinery.swift`),
so the mid-copy ENOSPC row's cost is no longer that the call site *cannot* tell
ENOSPC apart — it is that nothing yet does (Tier 2): the dedicated, localised
disk-space alert exists for exactly this failure and is still not reached from
`.underlying`.

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

> **As measured 4 Sep 2026.** The `withKnownIssue` tripwire described below fired as
> intended when Tier 0 landed and was rewritten into four positive assertions (`fbd8f4f3`).

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
  is `NSFileCoordinator`" was written against the wrong policy state (and has
  since been struck there).
- The non-blocking shape every shipping app converges on is: detect
  (`SF_DATALESS` via `st_flags`, or `ubiquitousItemDownloadingStatus` — both
  work cross-provider, files and folders) → `startDownloadingUbiquitousItem`
  (returns in 1–3 ms) → poll with a wall-clock bound → then copy. **The sidecar
  already does this**: `bristlenose/utils/fs.py` carries `SF_DATALESS`,
  `is_dataless()`, and `ensure_materialised()` with `MATERIALISE_TIMEOUT_SECONDS`.
  The desktop copy path (`CopyMachinery.copy()`, the blind `copyItem` in its
  per-file loop) does not, and should mirror
  it rather than invent a third pattern.
- `brctl download` / `brctl evict` are **hidden, not gone** on 26.4.1. The
  morning's claim that they "no longer exist" came from running them with *no
  argument*, which prints the usage — the usage omits them, but given a path both
  work (measured later the same day on a 608-byte placeholder: `download` returns
  0 at once and the file lands ~12 s later, asynchronously; `evict` prints
  `evicted content of '…'`). Undocumented, so still nothing to build on:
  `startDownloadingUbiquitousItem` / `evictUbiquitousItem` are the API. The
  measured record for the whole area — policy inheritance (launchd agents run
  **OFF**, GUI-spawned processes **ON**), the per-operation table, the openrsync
  source path — lives in the backup tool's repo
  (`~/Code/code-backup/docs/design-dataless-files.md`) and its public twin,
  `github.com/cassiocassio/iCloud-wizzard-behind-the-curtain`; correct those first,
  then this.

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

### Tier 0 — the bug fix: put the text on the type — **landed 12 Sep 2026**

`CopyError` conforms to `LocalizedError` and carries the original `Error` in
`.underlying` rather than a `String` (`fbd8f4f3`):

```swift
enum CopyError: LocalizedError {
    case underlying(Error)
    // …
    var errorDescription: String? {
        switch self {
        case .underlying(let error): return error.localizedDescription  // Foundation's sentence
        // …
        }
    }
}
```

That is the whole fix for §1. `localizedDescription` on a Swift error resolves
through `errorDescription` once the type conforms (SE-0112 — the same bridging
that renders an *un*-conformed enum as "The operation couldn't be completed.
(CopyError error 1.)"), so site 1 stopped showing the enum index **without its
catch block changing**. Site 2's `.underlying(let msg)` arm was redundant and
went; a site that wants the domain destructures the error (Tier 2).
`CancellationError` is not a `CopyError` and stays silent at both sites — as
`presentError` itself does with `NSUserCancelledError`, and as CotEditor does
with `CancellationError`.

**Why this, and not a shared mapping function.** The first draft of this tier
proposed one function both sites call, returning `(alert | toast | silent,
text)`. That is a view-model, and the second research pass (§8) found no
Apple API and no shipping Mac app that builds one. Apple's shape has three
separated parts: text on the error; a central hook that maps an error to
*another error* — `willPresentError` / `application(_:willPresentError:)`,
keyed on domain and code, the documented place to customise (overriding
`presentError` is "not recommended"); and delivery — `presentError`,
`NSAlert(error:)`, `.alert(isPresented:error:)` (macOS 12+, inside the 15.0
floor). NetNewsWire and CotEditor each have a shared function, and it is thin
and at the *delivery* seam (`ErrorHandler.present`, `presentErrorAsSheet`);
the text lives on the type, and for file operations both show Foundation's
sentence verbatim. The tuple would have moved the text off the type and fixed
the divergence by adding a third place for it to live.

Touched: the enum (conformance, one payload type, one new case), site 2's one
arm, and the tests. No toast change, no delivery change — which surface shows
the sentence is Tier 2's question and is not pre-empted here. No locale *key*
was added, so the three sentences on the type are English literals — Tier 1's
debt grew from one string to three. The
`LocalizedError` item and the `.underlying(Error)` item moved up from Tiers 1
and 2 because the idiom makes them the fix rather than hygiene around it; four
sibling enums already conform (`CloudDownloadError`, `SidecarResolveError`,
`ZoomOAuthError`, `MicrosoftOAuthError`), so this one was the outlier.

**Proof, as it went:** the `withKnownIssue` probes were rewritten as positive
assertions on `errorDescription` per case — every case renders a sentence and
never the enum-index fallback; `.underlying` returns the wrapped error's words
verbatim; a real permission failure reads identically through both sites'
paths; `inFlight` clears on failure. The `.underlying(String)` literal for the
in-flight guard became its own case, since a `String` no longer fits the
payload. Site 2's redundant arm was deleted; site 1 changed only its comment.

### Tier 1 — hygiene (small, separable)

- Route the three English literals on the type — `.insufficientDiskSpace`,
  `.noItemsAfterFiltering`, `.alreadyInFlight` (`.underlying` inherits Foundation's
  localised sentence) — through locale keys, 21 full locales (not `zh-Hant-HK`).
  Before Tier 0 there was one unkeyed string; putting the text on the type made
  it three.
- Decide what `.noItemsAfterFiltering` means at site 1. It is reachable there —
  site 1 passes unfiltered drops, site 2 pre-filters — and since Tier 0 it toasts
  its sentence ("None of the dropped items is a file Bristlenose can import.")
  where site 2 stays silent ("should not happen — we filtered above"). Both
  silent or both spoken; pick.

### Tier 2 — the deferred design (real work; a decision first)

- With `.underlying(Error)` landed in Tier 0, *use* it: recognise
  `NSFileWriteOutOfSpaceError` mid-copy and raise the existing disk-space
  alert, and the File Provider `-2001` case from §8 — by domain and code,
  never by matching the description (Apple's rule for `willPresentError`).
- **Whether a copy failure should be a toast at all.** The cull's rationale —
  toasts aren't HIG; state already on screen shouldn't be re-announced —
  applies less cleanly here: a failed copy leaves *no* state on screen (the
  files are simply absent and the pill has gone). But the anti-pattern says
  "don't reach for a toast," and the honest answer is that this case was never
  drawn. Per that doc's own rule, the review happens on the mockup: draw the
  failure state before deciding the surface. The second pass (§8) found
  evidence on one side and none on the other: the HIG says an error is an
  alert, not a notification; NetNewsWire and CotEditor both present file
  errors as an alert or a document sheet; no source examined argues for an
  error toast. NetNewsWire's suppression rule — alert on a manual refresh,
  log on an automatic one — is the nearest precedent for a failure the user
  did not directly ask for. None of that draws the state; it narrows what
  the drawing is choosing between.
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
| Sandboxed app runs materialisation policy **ON** (2) — as does every GUI-descended process (Terminal, the test host); a launchd agent with no `MaterializeDatalessFiles` key measures OFF (1) and gets `EDEADLK` instead of a hang, so a probe run by hand and one run under launchd disagree and neither lies | ✓ measured in-process; spawn-dependence measured the same evening | `DatalessPolicyProbeTests`; `desktop/CLAUDE.md` copyItem gotcha |
| `brctl download` / `evict` **hidden, not gone** on 26.4.1 — a bare invocation prints a usage that omits them; given a path both work (`download` returns at once and the file lands ~12 s later; `evict` prints `evicted content of '…'`). Undocumented, so still nothing to build on | ✓ re-measured the same day (§5) | — |
| Sidecar already has detect + bounded-materialise | ✓ `fs.py:19–26, 108–208` | — |
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
which no catch site distinguishes yet — since `fbd8f4f3` `.underlying` carries
the domain, so the discrimination (Tier 2) is what remains unbuilt.

### Second pass, same day — presentation idiom and cloud-wait practice

Asked what Apple's documentation, headers and sample code say about a shared
error → presentation mapping, and what indie Mac developers who ship against
iCloud actually do. First-hand where marked: Apple's archived guide and live
DocC read directly; seven Apple sample zips fetched and grepped; NetNewsWire
and CotEditor cloned; vendor docs and release notes read on the vendors' own
sites. The pass ran 142 tool calls and left its clones, zips and stripped
guide chapters in the session scratchpad under `research/`.

| Claim | Status | Source |
|---|---|---|
| Apple's customisation hook is `willPresentError` / `application(_:willPresentError:)`, and it returns a *new error*; overriding `presentError` is "not recommended"; discriminate by domain and code, never by the description | documented | Error Handling Programming Guide (archived, rev. Jan 2011); live `NSResponder` DocC |
| `NSAlert(error:)` maps description / recovery suggestion / recovery options → message / informative text / buttons; `presentError` silently drops `NSUserCancelledError` | documented | `NSAlert.init(error:)` DocC; the guide |
| `.alert(_:isPresented:error:actions:)` and `.alert(error:actions:)` are macOS 12+; Apple nowhere positions them as *the* way; no Apple sample uses them | documented; sample zips | SwiftUI DocC; WWDC21 10018 transcript |
| Across seven Apple samples (Landmarks, document-based app, Great Mac App, Backyard Birds, Food Truck, Destination Video, multiple windows): 0 `presentError`, 0 `NSAlert`, 0 `.alert(error:)`, one `LocalizedError` reaching a screen; the Great-Mac-App sample's file write sits in an **empty `catch`** | first-hand, source grepped | sample zips in scratchpad |
| NetNewsWire: 22 `presentError` sites; Foundation errors pass through unmodified; `ErrorHandler.present` is the one thin seam; `RecoverableError` used for *domain* errors ("Open System Settings"); connection errors suppressed on automatic refresh, shown on manual | first-hand, clone | `Mac/ErrorHandler.swift` (Jul 2026); issue #729 (2019) |
| CotEditor: `presentErrorAsSheet` on `NSDocument` / `NSViewController`; every file-browser operation shows the raw `FileManager` error in a sheet; `CancellationError` dropped; the SwiftUI side wraps any `Error` for `.alert(isPresented:error:)` | first-hand, clone | `FileBrowserViewController.swift` (Aug 2026); `View+Alert.swift` |
| HIG: an error is an alert, not a notification; the Mail-style passive indicator is for *informational* status; no source examined argues for error toasts | documented | HIG Alerts (rev. Feb 2024), Notifications, Feedback |
| **No shipping Mac app shows a "fetching from iCloud…" state or a per-file cancel for a dataless read.** CCC and Arq materialise silently and log; Hazel makes it a per-folder policy; Finder alone shows progress (the pie) | first-hand | Bombich KB (Apr 2024) + notes 6.1.7–7.1.6; Arq docs + notes 7.21–7.44.1; Noodlesoft forum (Oct 2025) |
| Finder's own failure wording: "The item couldn't be downloaded. Please check your internet connection, then try again." | user report | Apple Community, May 2022 |
| TN3150 carries no UI guidance for a dataless wait; two developer questions on monitoring download progress have no Apple answer | documented; first-hand | TN3150; Forums 690124; Clement via mjtsai, May 2023 |
| Foundation's sentence can be wrong — a copy reported the *source* "doesn't exist" when the *destination* directory was missing | first-hand | Lapcat, Nov 2023 |

**What this pass could not verify:** Quinn's forum thread on dataless
detection (808635) returned 403 from the research environment and has no
archive copy — unread; Hazel's exact option labels for cloud-only files
surfaced only in a search index, not on any Noodlesoft page.

**Bearing on the fix.** Three things. (1) Tier 0 is reshaped above: text on
the type, the mapping tuple withdrawn — that is what the idiom and both
shipping apps do. (2) Delivery is an alert or a sheet on every precedent and
the HIG says so; Tier 2's toast question now has evidence on one side and
none on the other, and still goes to the mockup. (3) The cloud-wait finding
bears on the open question recorded in `design-cloud-wait-label.md` (which
superseded the argument between `design-sidebar-activity-indicators.md` and
`design-project-storage.md`):
shipping practice is *no label* — hydrate, bound it, log — which is the
posture set on 4 Sep 2026. It does not settle whether Bristlenose says
anything; it establishes that nobody else does.
