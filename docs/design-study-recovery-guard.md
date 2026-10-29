---
status: partial
last-trued: 2026-10-29
trued-against: working tree on codex/study-recovery-guard, 2026-10-29
updated: 2026-10-29
scope: R114 / reliability 179; machine-owned recovery and fresh-start refusal
---

# Synced-study safety — smallest useful delivery

> **29 October reconciliation:** backend admission and approved native refusal
> presentation are implemented locally. Retry preserves running documents.
> Native suite limitations below remain explicit; no release or merge claimed.

Owner requested a William of Ockham reset on 28 October: deliver the simplest
implementation providing most of the safety benefit, step by step. Later work
is planned in `docs/private/100days.md`, the source of truth for long-term
scope, priority, deferral and restart decisions. Preserve previous thinking and
experiments as supporting evidence.

## Current implementation — 29 October

Owner finished mock feedback and explicitly resumed implementation. Revised copy:
Started on another Mac / Activity not confirmed; friendly Apple computer name
and source start time when available; separate “This study cannot be viewed or
edited here.” paragraph. Main panes Retry only, even on repeat; Copy details in
popover only. Read-only browsing remains deferred in main 100days. Typography
pushOut/pretty-wrap is a separate future100days item, not this patch.

Backend guards now precede CLI run/transcribe/analyze/serve, factory logging/DB,
and direct lifecycle writes. CLI run carries its already-checked status across
its deliberate stash/setup gap; no other unowned gap is admitted. Review found
and fixed the initial double-check regression. Real CLI and factory tests assert
protected output/backup bytes do not change; normal --clean tests use actual
schema-valid lifecycle records. Refusal uses exit 75 and the existing @-line
convention for optional JSON facts; native must refuse safely even without facts.
Apple ComputerName is captured by scutil, never DNS fallback; time/name are not
admission authority. A late factory refusal takes the same dedicated exit path.

Final backend regression receipt:289 passed / 2 expected failures in39.72 s across startup,
other-Mac, clean reanalysis, identity, lifecycle, server-lifecycle, backup/discard
and portability.37 portability tests independently pass with normal host access.
Earlier restricted attempts aborted in Metal and are not passing evidence.
Logs:/tmp/bn-startup-python-final.log,/tmp/bn-startup-portability-host.log.
Mypy CLI has three pre-existing errors reproduced against HEAD (account_name
and render legacy-argument types); final scoped recheck reports the same three. No unrelated
production fixes made. Previous typecheck attempt also caught a new wrapper
return annotation, corrected to NoReturn; do not count that failed run as green.

Native presentation is wired: typed refusal facts travel through the existing
failure model to the approved main pane, both sidebar implementations and the
popover. Exit75 wins over old completion/Stop and never writes a failure log.
Byte-based process line framing preserves optional Unicode names across pipe
chunks. Retry never launches analysis. A running server uses a separate hidden
`serve --check-startup-only` probe, returning before settings or any writer; it
does not restart the server or unmount either window's WebView. Review caught
and corrected an earlier restart path that could discard unsent editor text.
Probe errors/timeouts keep the refusal; superseded completions cannot clear it.

First native build needed the standard GeneratedBuildInfo generator; a normal
app build then hit missing frontend dependencies at the sidecar freshness gate.
The repository unit-test script bypasses that gate by design. Three subsequent
full Swift runs built successfully and passed the refusal tests, but each was
red on existing PoolStarvationTimeoutTests. Cause is not established; unchanged
test source does not prove baseline equivalence. The final exact-source run,
including the Retry probe, built and passed 2,831 tests with one pool-timeout
failure. A focused run of all new suites plus both pool tests passed 20 tests
with the existing expected saturation issue. Logs: /tmp/bn-startup-native-probe/
and /tmp/bn-startup-focused.log. Untouched f61205a11 checkpoint full suite passed
2,814 tests. The combined-run failure therefore cannot be called a proven
baseline failure. All 2,814 existing tests also passed against changed production
code when the five new suites ran separately. The focused run covers all new
suites and both pool tests. Every test therefore has passing split-run evidence,
but no combined native green is claimed. Existing-suite log/result:
`/tmp/bn-startup-existing-suite.log`, `/tmp/bn-startup-existing-suite.xcresult`.
The remaining verification limitation is combined-suite executor isolation;
review found no concrete new blocker/global mutation, but did not establish a
root cause. Keep this explicit at integration; do not weaken the timeout test or
present the split run as the normal all-suite gate. Backend commit b9f60812f;
native commit 032b3fcfc.
No manual native UI/DOM verification, no push/merge/release. Existing running-sidecar reuse is NOT a
fresh startup: preserve multi-window no-restart rules; do not silently expand this
into live-transition protection. Reassess any cold-opening/warm-reuse claims in
native review and tests rather than restarting another window's active server.

## UX gate — explicit owner instruction, 28 October

Any UX change requires a complete mockup, review and explicit owner approval
before implementation or activation. Reuse existing patterns; do not invent new
UX features, controls, navigation, dialogs or status surfaces. Reusing a pattern
does not waive approval for new copy, states, actions or visible behavior.

Step 2 changes the user's opening/analysis flow: first inspect existing native
and CLI failure/status machinery, then mock every relevant state and transition,
including copy and existing actions, review it and obtain approval. Backend-only
preparation/tests may proceed separately; do not wire an unapproved user flow.
Step 3 has the same gate. Historical mocks and earlier discussions do not count
as approval of the reduced delivery. Existing recovery mock remains unverified.
Use the repository bn-mockup skill when producing native-style HTML mockups.

## Delivery sequence

| Step | Benefit | Boundary and acceptance |
| --- | --- | --- |
| 1. Machine-owned recovery | Opening on this Mac cannot automatically restore/delete another Mac's unfinished analysis. | Require stable local machine and exact run identity under existing local settle lock. Foreign, missing, legacy, malformed and mismatched identity preserve output and backup; positive local crashes still recover. |
| 2. Conservative startup admission | An uncertain unfinished study cannot start ordinary writers here. | Refuse server/importer/jobs and analysis/reanalysis before opening writable state. Existing unavailable/status UI explains the cause. Test actual CLI/native entry points and source bytes. |
| 3. Optional fixed reader | Read a known complete report while editing is refused. | Start from validated immutable local contents; read-only for the entire reader lifetime. No automatic adoption or editing re-entry. Unsupported resources/policy mean unavailable, never fallback to changing source. |

Step 1 is a destructive-recovery fix, not a study-wide lock. Ordinary startup
still writes a log/database after recovery. Explicit `run` still has separate
recovery paths. Do not advertise those paths as protected until step 2 is proven.
No marker provides a distributed lock, proves unseen cloud changes have arrived,
or makes live shared SQLite safe. Missing ownership is uncertainty, not a crash.

## Step 1 implementation

`machine_identity.py` derives a namespaced hash from OS machine identity, not
hostname, study contents or PID. Unknown/unavailable identity returns None.
New run.pid includes machine_id. Automatic reclaim checks positive local
machine ownership and matching latest run_id before entering destructive
reclaim under the same existing local settle lock. Legacy local crashes no
longer recover automatically; preserving uncertain work is the intentional cost.

Tests cover foreign/unknown markers byte-for-byte, known-local recovery, marker
writing and supported identity discovery/error handling. A factory-boundary test
executes real create_app through recovery and stops at its first writer, proving
only the pre-write recovery boundary. Existing lifecycle tests exercise full
same-machine server startup. Neither is proof that all foreign startup writes
are refused; that is step 2.

## Step 1 receipt — 28 October

Commit `e83c68c79`, branch codex/study-recovery-guard, based on main4e8cc854a.
Final regression200passed/3deselected/2expectedfail in32.81s; Ruff clean.
Independent runtime review found malformed Windows registry type could raise;
fixed with explicit type check and valid/int/None/invalid regression cases,
then rechecked clean. Logs:/tmp/bn-r114-final-{regressions,ruff}.log.
Two earlier main-checkout attempts aborted during optional native MLX hardware
imports in known-open CLI tests; not passing evidence. Explicit-run tests remain
out of this step's scope; these are among the deselected cases. No real study,
cloud provider or paid pipeline operation was tested. No push/merge/release.

## Preserved future work

The larger prototype remains on `codex/study-access-poc`, worktree
`/Users/cassio/.codex/worktrees/study-access-poc/bristlenose`. Its design owner is
`docs/design-study-read-only.md`; implementation/evidence map is
`docs/design-study-read-only-plan.md`; experiments are under
`experiments/study-access-poc/` (README, FINDINGS, HANDOVER, RESEARCH).
Long-term planning authority is `docs/private/100days.md` in the main checkout.
This design describes implementation and evidence; it does not set backlog
priority or independently authorise deferred work. Review evidence remains in
`docs/private/reviews/study-read-only.md`.

Park seamless handover, private writable-storage migration, automatic incoming
publication/adoption, unfinished-text recovery UI, editing re-entry and all-lens
parity. Keep immutable reader/checkpoint validation and writer inventory as
reusable tested work. Do not delete code, tests or research merely because they
are no longer prerequisites for this release. Reassess old review findings
against the capability actually selected; do not mechanically carry obligations
for removed capabilities into the minimal fix.

Consult the current 100days item before resuming the larger design; its priority
and restart criteria govern. Update that item when decisions change, rather than
maintaining a separate roadmap here. Duplication/merge and cloud-provider APIs stay outside
this delivery.

## Step 2 preparation — 28 October (not activated)

> Historical preparation receipt, superseded by the29October current section.

`utils/study_startup.py:startup_refusal` reads evidence without writing. New/empty
studies and terminal attempts follow the existing flow; unfinished attempts need
usable local machine/run/process markers. Foreign or unverified activity refuses.
An output-to-backup start gap refuses. Unknown/torn/NUL/invalid-UTF8 history cannot
hide behind an older completion: admission reads strict raw evidence, leaving the
existing tolerant display reducer unchanged. This can conservatively refuse a
historically damaged log; no repair/override UI is provided by this helper.

No production caller exists yet. This is not step2 completed: CLI/native/server
entry wiring and proof before every relevant startup writer remain undone.
No watcher, live-transition fence, shared-SQLite safety claim or retained reader.

A related step1 review correction validates positive non-boolean PID and nonempty
start token before automatic local recovery, and treats invalid-UTF8 PID markers
as unavailable. Both preserve uncertain files instead of destructive recovery.

Verification:238passed/3deselected/2expectedfail in35.35s across admission,
identity, other-Mac, backup/discard, lifecycle, portability and server lifecycle
scenarios. Ruff clean. Mypy helper+backup clean; including run_lifecycle reports
its pre-existing line224 list[Signals]/list[int] mismatch, reproduced against
unchanged HEAD source. Logs:/tmp/bn-startup-{final-regressions,helper-mypy,baseline-mypy}.log.
Runtime review found damaged-tail false admission and malformed local process
markers; regressions added and reviewer rechecked both resolved.

[Complete startup-refusal mock source](mockups/study-startup-refusal.html) reuses
existing sidebar/popover, BootView, RunCoverPane and CLI error structure.
Source review corrected the refused-analysis headline and details toggle; final
source review clean. **Visual review and owner approval pending.** User approved
local inspection, but the browser's independent file-protocol policy still
rejected opening and forbids alternate rendering routes. No workaround attempted.
JavaScript syntax checked; that is not pixel/interaction verification.

Next: obtain the requested concrete UX approval, then wire pre-write admission
and existing refusal presentation, prove actual CLI/native/server paths preserve
protected bytes, review/fix. Long-term optional reader and full benefit remain
prioritised only by main100days; no hidden dependency on the parked architecture.

Mock register check: new proposal is registered. Whole-tree register check still
reports18 pre-existing unregistered mockups (none is study-startup-refusal.html);
not claimed as a passing gate and not broadened into unrelated documentation work.
Receipt:/tmp/bn-startup-mock-register.log. Runtime/helper preparation commits:
2ad06751d (malformed recovery), ed0e8456b (inactive admission); mock/source-review
checkpoint56902958a. Explicit UX approval is still pending, not inferred from
permission to inspect the file or approval of the reduced safety scope.
