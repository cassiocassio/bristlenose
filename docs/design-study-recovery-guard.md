---
status: current
last-trued: 2026-10-29
trued-against: combined recovery/status source on codex/sidebar-status-separated, 2026-10-29
updated: 2026-10-29
scope: R114 / reliability 179; machine-owned recovery and fresh-start refusal
---

# Synced-study safety — smallest useful delivery

> **29 October reconciliation:** backend admission and approved native refusal
> presentation are implemented locally. Retry preserves running documents.
> Full native gate and native visual review pass; no release or merge claimed.

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

**Owner QA follow-up, 29 October:** the first study's row fell back to red “Run
failed” after selecting a second study. ContentView tears down the outgoing
serve, and its process-state reset had erased the confirmed refusal used by the
sidebar. Commit d8b5c8c51 retains that display-only cause through idle/starting;
admission or a newly confirmed startup refusal replaces it. An unrelated sidecar
failure is not evidence that the protected study became safe, so it preserves the
more specific refusal. This does not affect admission
authority or add persistence to disk. New fleet/manager regressions cover switching
and clearing. An initial full run caught duplicate observer notifications; the
cache now changes only inside the already-published state observer, preserving
the existing one-notification contract. Follow-up8a7aabcd6 also keeps the
late-output enrichment predicate tied to the current attempt's confirmed failure,
not the retained display cache. The actual parser/PID/exit regression proves that
new output cannot fail a starting attempt until its own exit75. Final full gate:2,836pass/0fail, log
`/tmp/bn-startup-row-retention-exit-final-runner.log`. Both QA studies/backups remain
byte-identical. The QA launcher app is rebuilt for owner retest; earlier static
visual checks did not cover this transition. No visible UX redesign was made.

**Sidebar status truth invariant:** a project row is a projection of the most
specific, best-supported current fact known for that project — never of whether
it is selected, whether its sidecar is currently alive, or which pane happens to
have focus. A confirmed startup refusal therefore continues to read **Started on
another Mac** (or **Activity not confirmed**) through the outgoing sidecar's
idle/starting lifecycle. Selection changes and process teardown are not evidence
that the underlying foreign/uncertain attempt ended. A newly admitted serve or a
new confirmed startup refusal may supersede the retained cause; an unrelated
sidecar-start error cannot. Ordinary sidebar
precedence still lets an unavailable folder win. The regression must assert the
rendered AppKit sidebar text and warning glyph after switching away, not only the
manager cache, so a future state-owner change cannot reintroduce the generic
**Run failed** fallback.

## Merge-readiness verification — 29 October

**Combined recovery/status review, 29 October:** the isolated
`codex/sidebar-status-separated` source combines the reduced guard with retained
sidebar-cause precedence. Source review checked that selection/teardown and generic
sidecar failure cannot erase the confirmed cause, readiness clears it, replacement
metadata requires the current owned attempt's exit75, and display retention grants
no admission authority. This pass was coordinator self-review; earlier independent
reviews remain recorded separately. No new UX or reader activation.

Fresh official native gate: **2,836 passed, zero failed**, exit0;
`/private/tmp/bn-recovery-status-combined-native-final-runner.log` and xcresults in
`/private/tmp/bn-recovery-status-combined-native-final/`. Fresh-worktree first build
failed to discover generated build info; standard generation/rebuild resolved it.
A sidebar session's independently started native gate overlapped the run; both
completed green in separate DerivedData. No failed tests were excluded.

Expanded combined Python selection: **343 passed, 2 expected failures**, exit0,
57.33s; `/private/tmp/bn-recovery-status-python-final.log`. Covers startup, other-Mac,
identity, lifecycle, clean reanalysis, CLI paths/dev reload, serve degradation,
runner contract, backup/discard, backup CLI wiring and server lifecycle. The broader
backup wiring run initially exposed five schema-invalid/ownerless fixtures. They
now use valid lifecycle records and positive local ownership for recovery; a new
ownerless-gap test explicitly asserts exit75, no pipeline call and byte preservation.
The shared invoke helper rejects accidental startup refusal, avoiding vacuous
report-preservation passes. Production admission was not weakened. Scoped Ruff,
shell syntax and git whitespace checks pass. Full Python suite and fresh native
visual QA were not repeated; prior approved native visuals remain the presentation
receipt, supplemented here by the actual row text/glyph transition regression.

Integration is owner-authorized through a clean checkout of main. The original
shared Signals checkout, other isolated lanes and the deferred reader pilot must
remain untouched. Merge is local only, not push/release.


The latest full repository entry point is green: **2,836 native tests passed, zero
failed** (`/tmp/bn-startup-row-retention-exit-final-runner.log`). The earlier pre-owner-QA
receipt was2,834passed in `/tmp/bn-startup-native-ready-runner.log`. It builds once, runs the
general suite, then runs `PoolStarvationTimeoutTests` in a separate process.
Both results and independent nonempty checks are required. Both xcresults are
retained in `/tmp/bn-startup-native-ready/`; no failed test was excluded.

The failure was an executor-isolation problem: these tests intentionally block the
shared Swift executor. Their `.serialized` trait orders only their own cases;
it does not reserve that executor from other suites. Earlier runs either could
not start a read within five seconds or missed the three-second control deadline.
The isolated control passes; saturation still records its existing known issue.
No single new test was identified as the trigger. Isolation removes competing
work rather than lengthening limits. No production timeout, test assertion or
deadline changed. Seven runner contract
cases prove that either phase failing, crashing or running no tests removes the
old receipt and cannot produce green. Final Python regression: **296 passed,
two expected failures**, 41.62 s (`/tmp/bn-startup-ready-python.log`).

Native visual review uses actual BootView, RunCoverPane, ProjectDiagnosticPopover,
ProjectRow and SidebarOutlineController views, with real English resources.
The opt-in presentation test passed and produced 33 light/dark captures covering
named/time, missing metadata, unverified activity, long names and a narrow pane.
The body contributes to popover intrinsic height; Retry and Copy details resolve
to real labels. Parent and independent reviewer inspected the rendered copy,
emphasis, wrapping and available controls; no product layout fix was needed.

AppKit vibrant selection cannot be certified by a view bitmap. Actual light and
dark QA windows were therefore inspected via CUA, including a selected dark row
and its accessibility text/glyph. A separate QA bundle identity avoided the
user's running app. Computer-use attachment initially timed out/selected a
duplicate QA process; that duplicate was stopped, startup allowed to finish,
and the actual test-host window was inspected successfully. No real study was
opened by the fixture. No interactive multi-Mac handover or two-window editor
DOM test is claimed.

Native visual result: `/tmp/bn-startup-native-cua-review.xcresult` (test passed).
Standalone captures are retained in main
`docs/private/reviews/study-recovery-guard-native-2026-10-29/`; invalid AppKit
vibrancy bitmaps are deliberately excluded. See the private review log for
review dispositions and evidence limits. `StudyStartupPresentationTests` is
opt-in and runs separately from the normal gate; use
`TEST_RUNNER_BN_STARTUP_VISUAL=1` with only that suite. The optional `_HOLD` flag
holds real QA windows for inspection, without adding product UX.

Historical comparison receipts remain useful: the original combined run was
2,831 pass / one pool timeout; untouched f61205a11 passed 2,814; changed production
also passed all 2,814 old tests separately; focused new suites plus pool passed
20 checks. These were diagnostic split runs, not the final green gate above.
Initial presentation-fixture captures lacked a background/locale setup and one
zero-width row failed; fixture setup was corrected before visual approval.
A fresh normal app build also hit the missing frontend/sidecar freshness gate;
the standard unit-test bypass was used. No signed release-package proof claimed.

Backend commit b9f60812f; native commit 032b3fcfc; runner/visual follow-up a1718744f.
No push, merge or release. Existing live/warm-sidecar reuse is not fresh admission:
no live-transition fence, shared-SQLite guarantee, retained reader or auto-unlock
has been added. Main100days remains authoritative for deferred scope. Preserve
unrelated uncommitted main work when integrating this branch.

## Completion audit — reduced delivery

Audited against current source, real test receipts and the owner's later scope
decisions, rather than treating the original larger prototype as the goal.

| Requirement | Current evidence | Result |
| --- | --- | --- |
| Preserve another machine's unfinished analysis and backup | Exact machine/run/process checks in output_backup; foreign, uncertain, malformed and positive-local recovery cases in test_run_on_another_mac | Complete |
| Refuse fresh writable startup before protected writes | CLI command/alias byte comparisons, direct lifecycle guard and real create_app first-writer test; healthy/clean reanalysis controls | Complete |
| Honest native cause, optional Apple name/time, unknown fallback | Typed exit75/facts path, native refusal/Unicode/Stop tests, actual light/dark view and AppKit window inspection | Complete |
| Approved existing UX only | BootView/RunCoverPane, both existing sidebar renderers and diagnostic popover; main Retry only, popover Copy details only; owner approval before wiring | Complete |
| Retry does not start analysis or discard live documents | Non-writing probe CLI tests, native process/state identity and superseded-result tests, bounded failure/timeout handling; fresh source review | Complete |
| Review, fix and verify findings | Runtime, fresh native and William review dispositions in private review log; full native gate2,834pass/0fail and Python296pass/2xfail | Complete |
| Keep future work and Claude pickup clear | Main100days explicit deferrals, retained codex/study-access-poc ref, current design/TODO/CLAUDE/handoff/review and native evidence archive | Complete |
| Explain the result and practical limits | Current implementation/verification sections and private review record; detailed owner close-out | Complete |

Read-only browsing, live fencing/re-entry, duplication/merge and cloud-project
infrastructure are explicitly deferred by the owner, not unfinished requirements
of this delivery. Actual merge/push/release was not requested by “ready to merge”.
Tracked-main merge-tree check is clean; integration must preserve main's unrelated
uncommitted work. No code changed during this completion audit.

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
as approval of the reduced delivery. The older full-recovery mock is not approval
of this scope; the revised startup-refusal mock was approved before wiring.
Use the repository bn-mockup skill when producing native-style HTML mockups.

## Delivery sequence

| Step | Benefit | Boundary and acceptance |
| --- | --- | --- |
| 1. Machine-owned recovery — implemented | Opening on this Mac cannot automatically restore/delete another Mac's unfinished analysis. | Require stable local machine and exact run identity under existing local settle lock. Foreign, missing, legacy, malformed and mismatched identity preserve output and backup; positive local crashes still recover. |
| 2. Conservative startup admission — implemented | An uncertain unfinished study cannot start ordinary writers here. | Refuse server/importer/jobs and analysis/reanalysis before opening writable state. Existing unavailable/status UI explains the cause. Test actual CLI/native entry points and source bytes. |
| 3. Optional fixed reader — owner deferred to main100days | Read a known complete report while editing is refused. | Start from validated immutable local contents; read-only for the entire reader lifetime. No automatic adoption or editing re-entry. Unsupported resources/policy mean unavailable, never fallback to changing source. |

Step 1 alone is a destructive-recovery fix, not a study-wide lock. Step 2 now
guards fresh startup before ordinary log/database and analysis/reanalysis writes.
Admitted startup retains its normal writable behavior after that point.
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
