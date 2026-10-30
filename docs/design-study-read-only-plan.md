---
status: pending
updated: 2026-10-28
last-trued: 2026-10-28
trued-against: reviewed opt-in workspace producer/read/draft integration; automatic activation off
scope: provider-neutral sequential handover; revised after study-access POC
---

# Study access protection — implementation plan

This is the proposed implementation sequence following the iterated POC, not a
claim that production handover is implemented or ready to ship. The first package
below is concrete and buildable. Private writable storage is a proposed safety
mechanism supported by comparison tests, **not an approved wholesale storage
migration**. Its integration, durability and retention are explicit gates.

## Delivery reset — 28 October, owner request + William review

**UX approval gate (owner):** completely mock up, review and obtain explicit
owner approval for any UX change before implementing/activating it. Fit existing
patterns; invent no new UX features. Historical mocks do not approve new flows.

**Long-term planning authority:** `docs/private/100days.md` in the main checkout.
This document preserves design and evidence; consult 100days for current priority,
deferral and restart decisions. Update 100days first when those decisions change.

The [minimal safety sequence](design-study-recovery-guard.md) now has its first
two steps integrated on local `main`: machine-owned automatic recovery, then
refusal of ordinary writer startup for foreign/uncertain unfinished activity.
The third step, an optional immutable reader that remains read-only for its
lifetime, is owner-deferred to `100days`. This does not permit warning-only
enforcement or imply seamless transition/re-entry.

The rest of this document preserves the larger design and measured evidence,
not the prerequisites for the minimal patch. Park private writable migration,
automatic publication/pickup/adoption, unfinished-text recovery UI, automatic
replacement and editing re-entry in 100days. No prototype deletion. Reassess
review1–13 when the corresponding capability is selected; parked is not resolved.

## Current pickup — 28 October

Explicit producer/source fences, immutable core readers, bounded recovery,
terminal editor stop and same-workspace recovery discovery are built opt-in.
Latest `e34fe2fbd` adds fixed document/view labels and shared lens application
checks. Real Chromium/WebKit manual reload retains saved private B instead of
old A, with source unchanged; it does not implement automatic transition or native
UI. Working0 remains mutable; retained1 is immutable. Descriptor is expected
context, not proof of all rendered content. Full3,900frontend passes+2expectedfail,
177selected Python tests and types/builds/lint/budget pass (latest evidence below).
Next: direct application owners outside useLensRead; recovery UI/ownership/
retention; coherent automatic document replacement; full controls/current-policy/
media/native and safe incoming adoption/re-entry. Default activation OFF; original
whole-feature1–13 remain OPEN. Earlier dated checkpoints are historical.

## Package-1 implementation checkpoint — 27 Oct

The spike contains checkpoint publication/validation, durable announcement memory,
a shared local producer boundary, explicit server/ORM/route/job adapters and a
complete output-tree classification. Explicit local lifetime ownership and clean-
successor fencing plus the explicit owned CLI runner are implemented opt-in.
These are Python integration helpers;
CLI/native/default activation, managed private-store lifecycle, crash recovery
and read-only UX are not enabled. Explicit private identity and clean-stop edit
durability now have a tested Python pilot (see below). The [writer inventory](design-study-read-only-writers.md)
records exact coverage. Independent implementation review found eight pilot
issues; fixes/regressions and final verification are recorded in the spike's
FINDINGS and private review ledger. This is not completion of package 1 or
approval of the later stages.

**Next gate:** explicit Python predecessor/payload carry is implemented and
reviewed. Explicit private identity and clean-stop edit durability are now tested.
The explicit owned runner now has real socket/edit/clean-shutdown evidence
(see runner section). Completed edited-checkpoint return now has real owned A→B→C evidence (see
return proof below). Explicit confirmed-publication pickup now survives clean local restarts (see
latest section). Explicit source observation now fences owned writers (latest section). Next
incoming-version/dirty/draft handling, all-lens/policy-covered browsing and mutation
UX, exceptional recovery and normal re-entry; automatic observation remains gated. Do not attach an automatic
completion hook or expand storage infrastructure merely because hashes validate.
The explicit workspace pilot addresses the private-snapshot identity fork;
crash/draft durability and public/native/default integration remain package-2 blockers. Earlier dated counts below are historical runs.

## Document map and authority

- **Owner design and UX:** [design-study-read-only.md](design-study-read-only.md).
  This plan describes implementation; it does not supersede owner decisions.
- **Build sequence and acceptance gates:** this file, using the existing
  `design-<feature>-plan.md` convention (as for Discussion/curation persistence).
- **Initial complexity and narrowed scenarios:**
  [design-multi-mac-study.md](design-multi-mac-study.md), retained as design history.
- **Current reduced v1 visual draft:**
  [multi-mac-v1-guards.html](mockups/multi-mac-v1-guards.html). Review aid only;
  some historical comparisons remain and are not accepted release options.
- **Full N-Mac exploration:** [multi-mac-study.html](mockups/multi-mac-study.html).
  Historical future-scope exploration, not the v1 build target.
- **Deferred exceptional duplication:**
  [design-study-duplication.md](design-study-duplication.md); not part of this build.
- **POC code, tests and measured results:** `experiments/study-access-poc/` on the
  parked `codex/study-access-poc` branch, also preserved as an archive bundle and
  full private copy; see [BRANCHES.md](BRANCHES.md#codexstudy-access-poc).
  It is not on main. Do not follow a nonexistent main experiment path or copy
  the prototype gate into production. README is its entry point; HANDOVER
  describes the latest iteration; FINDINGS is the cumulative measured record;
  RESEARCH contains external background and the explicit cloud-policy correction.
- **Private pickup/review/backlog:** existing `docs/private/handoffs/`,
  `docs/private/reviews/study-read-only.md`, reliability decision record and
  `docs/private/100days.md`. Raw reviews remain private. TODO is the current
  pickup record, not another implementation specification.

In the spike, `HANDOFF.md` → `.claude/plans/study-access-poc.md` remains a pickup
brief mirrored from the canonical private handoff. It links here; it is not an
alternative spec. This plan is draft and has not had a new independent review.

## Product boundary

One researcher finishes at home, goes to the office, continues there, and later
returns home. Assume no further human work starts on the previous Mac after
handover. An old open instance can still have background work: the implementation
must fence its relevant writers, rather than interpreting “no human” as “no writes”.

Normal handover has no takeover/ownership confirmation, device limit, version
browser, merge, Duplicate shortcut or new cloud-management surface. Preserve the
existing report and all lenses while protection applies. Warning-only is not a
release. Existing owner decisions in `design-study-read-only.md` govern the status
line, popover, passive bottom-right lock + Read only cartouche and accessibility.

**Settled cloud policy:** `design-cloud-files.md`, `design-project-storage.md`
§§1/3, `design-copy-error-surfacing.md` §5. Treat the study as files in a folder.
Use existing bounded materialisation/read handling for the completion record and
required files. No new iCloud/FileProvider status integration, upload-complete
gate, coordinator remedy, cloud progress/advice or provider-specific behaviour.
Provider test probes are historical observations, not build dependencies.

## The normal flow to build

1. Finish this Mac's analysis/curation checkpoint at an actual writer boundary.
   Publish a completion record describing exactly those finished contents.
2. Opening on the next Mac reads available Bristlenose evidence. If it knows a
   newer checkpoint exists but its contents are incomplete, keep its last
   coherent report available and prevent changes. Do not diagnose the transport.
3. Stage copied contents, validate the record/hashes/database/required resources,
   then admit one complete generation. Normal sequential handover needs no user
   confirmation when no local edits or drafts conflict.
4. Protect newly accepted edits against incoming file replacement. The POC's
   demonstrated mechanism is a private working DB. A check followed by continued
   editing of the shared syncing DB does not provide that protection.
5. When this Mac finishes, publish its final saved curation too. A return trip
   uses the same contract; the protocol is not analysis-only.

“Complete version received” is a justified claim. “Globally latest everywhere”
is not. A wholly unseen later checkpoint cannot be inferred from silence. The
single-person assumption bounds expected use, not this information limit.

## Completion record contract

Proposed location: `<output>/.bristlenose/report-checkpoint.json`. This is a new
contract, not the existing `run_completed` event. Retain existing lifecycle events
for their present purposes; analysis completion does not order later curation.

| Field | Requirement |
| --- | --- |
| `schema` | Strict supported integer format version; unknown formats are not permission to repair or edit |
| `study_id` | Original study identity; a private working copy must not become a new study |
| `checkpoint_id` | Unique ID for this finished report/curation checkpoint |
| `previous_checkpoint_id` | Immediate predecessor or explicit legacy bootstrap; ordering uses ancestry, not clocks |
| `run_id` | Analysis provenance when available; not a substitute for checkpoint identity |
| `machine_id`, `machine_name` | Stable opaque producer identity plus optional friendly display name; display name never grants authority |
| `completed_at` | Human-readable evidence only; no lease, expiry or last-timestamp-wins rule |
| `files` | Exact required relative paths, sizes and SHA-256 hashes for the published checkpoint |

The POC's `producer_writers_stopped` Boolean is **not** a production safety
primitive. The producer must actually stop admission and drain/fence relevant
commits before producing the record. A claimed Boolean cannot prove that work.

Producer sequence:

- Stop accepting relevant writes; let bounded transactions finish or roll them
  back. Fence delayed requests and worker publication at the actual commit point.
- Capture SQLite using its backup API, not a naked DB/WAL copy. Capture other
  canonical report files under the same stable generation boundary.
- Validate staged output; hash only finished copied bytes. Publish staged content
  and replace the record locally as the final operation. Handle partial failure
  without destroying the previous usable report.
- Treat remote delivery as arbitrarily ordered. “Record written last” is not a
  claim it arrives last elsewhere. Scope the producer boundary to required report
  state, not incidental logs, which must not invalidate a checkpoint.

Inventory the real required file set in package 1. DB, transcripts, people/registry,
quote/theme/screen intermediates and policy-sensitive state must be classified,
not guessed from the tiny fixture. Derived caches and media require explicit
roles. Do not mandate duplicating or repeatedly hashing every large recording on
open; equally, do not silently read changed media as if it belonged to the pinned
report. Version pinning/unavailable-media behaviour remains an acceptance gate.

## Receiver and mutation contract

Internal states: checking, editable, locking, locked. They are not provider states.
The displayed generation is explicit and changes only at an admission boundary.

- Before writable logging/DB creation/import/migration/recovery/jobs, decide the
  permitted destinations. Protected originals receive no automatic repair writes.
- Read/copy through existing bounded file handling. Reject missing/torn/unsupported
  records, unsafe paths, hash mismatches and unusable DB/schema. Checksums alone
  do not establish database validity or cross-file semantic consistency.
- Persist the newest checkpoint announcement already observed. An older arriving
  record must not erase that knowledge or unlock an incomplete newer generation.
- Retain one coherent local reading baseline. Stage candidate bytes independently;
  never validate a path and later reopen unrelated replacement bytes as the result.
- Every mutation carries a non-repeating process/authority incarnation plus an
  access-transition epoch and displayed checkpoint. Validate inside the local
  commit/publication boundary, not just in the UI or request's early checks.
- Closing admission precedes draining. Do not run arbitrary callbacks or long I/O
  while holding a gate mutex; the earlier POC exposed deadlock and partial-write
  failures. A failure must not leave editing enabled over unknown partial state.
- Cover supported API, CLI, native and background writers, including filesystem
  outputs such as people.yaml, exports, derived caches and migrations. A relocated
  database alone is not the whole write barrier. Destination-specific policy may
  allow unrelated work; do not blanket-disable every action without classifying it.
- Persist/restore working generation, dirty edits/drafts and authority state across
  restart. Existing workspaces must not be treated as disposable caches. The POC
  currently refuses reuse to preserve bytes; real recovery is not yet implemented.

Private working storage is proposed because it passed the delayed-replacement
comparison. It must retain the original identity and source relationship, use
explicit destinations/participant-data retention, and fit current-policy exposure
rules. The importer currently remints an ordinary copied study when the original
exists; using that path unchanged is not acceptable for a private workspace.

## Exceptional flow and limits

| Situation | Required behaviour |
| --- | --- |
| Newer announcement, incomplete contents | Keep known report; block mutations; clear only from coherent matching evidence |
| Known older files/record arrive after a verified private generation | Do not overwrite local edits or roll back the remembered generation; no transport narration |
| Newer complete checkpoint arrives with no local changes/drafts | Stage and validate, switch coherently, invalidate old requests, resume editing |
| Previously unseen newer checkpoint arrives after local edits | Retain local edits and known report, close mutation admission, do not silently overwrite or merge; exact recovery UX is still a product gate |
| Unknown/foreign unfinished run or incompatible legacy state | No destructive recovery/takeover. Use known local report or existing cannot-open handling |
| Read bound fires | Existing ordinary retryable failure, not a new cloud wait/error state |
| Restart with unsent local work | Resume that work safely; never recreate the private DB over it |

No claim covers deliberate simultaneous offline authors or noncooperating old
builds. Do not build a revision archive, branch DAG service or automatic merge to
answer the normal one-person case. Those are future architectural choices.

## Build packages and stop gates

### 1. Real producer/receiver contract — integration pilot in progress

Create focused checkpoint and validation modules; connect the producer to actual
lifecycle/curation boundaries only after inventorying the writers. Reuse
`utils/fs.py`, run/machine identity and existing refusal/error conventions. Test
real DB backup plus actual required file capture with writes admitted before,
during and after publication. Add bounded-read failures for the done file itself,
not only media. Persist observed announcement state and test crash/torn updates.

**Gate:** evidence must demonstrate coherent capture, legacy bootstrap, curation
coverage and no false admission from partial/stale records. The fixture's stopped
producer assertion is insufficient. If safe capture requires a larger change,
return its measured cost and smallest alternatives before expanding implementation.

### 2. Small working-storage integration pilot

Run actual serve/import/lifespan and representative mutations against an isolated
working destination, keeping source study identity and current policy. Prove
restart/draft durability and returning edits through a final checkpoint. Measure
storage/capture cost on representative synthetic sizes; bound retention and
cleanup. Media stays subject to an explicit safe contract, not blanket copying.

**Gate:** no source writes, no identity fork, no lost local edits after restart or
late delivery, useful normal re-entry. This pilot does not authorise migrating
all projects or creating a new persistent PII store by default.

### 3. Actual all-writer barrier and existing UX

Wire shared authority through supported processes; trace GET/startup/background
writers as well as mutation routes. Integrate the existing sidebar/popover and
shared SPA cartouche after the barrier is real. Preserve pending input/focus
before controls disable; perform i18n/a11y using established apparatus.

**Release gate:** warning, enforcement, coherent browsing and usable re-entry
must ship together. No convincing lock badge over an unfenced writer. Resolve or
explicitly adjudicate the 13 existing review findings; this spec does not close
any of them. No new usual-suspects pass has reviewed this revision yet.

## Evidence backing this revision

POC branch: `codex/study-access-poc`, managed checkout
`/Users/cassio/.codex/worktrees/study-access-poc/bristlenose`.
Evidence is in `experiments/study-access-poc/`, principally HANDOVER.md,
FINDINGS.md, handover.py and its tests. These are experimental code, not product
implementation. The final combined POC run passed **28 checks in 23.11 seconds**.

| Evidence | Result | Boundary |
| --- | --- | --- |
| One-person home→office delivery | All 24 four-file orders admit complete B, preserve saved home curation and later office edits | Synthetic delayed deliveries; no actual remote provider ordering proved |
| Sequential return home | All 24 return orders preserve office edits in C | One A→B→C journey, no merging/general history |
| Record first, then stale record | Pending B remains pending; old A intent refused; fresh B edit succeeds | Experimental policy, not actual production fencing |
| Late replacement control | Saved edit in synced DB disappears after injected pre-edit replacement and clean reopen | Demonstrates replacement vulnerability; not proof a particular provider overwrites that way |
| Isolated office DB | Office edit survives late old contents in every tested order | Source identity/restart/all-file writes not integrated |
| Real startup/read pilot | Three scenarios, 63 successful read responses, original bytes unchanged; saved edit preserved | Real ASGI lifespan/import, synthetic data; decoding disabled; no signed native app |
| Existing DB copied for startup | Identity reminted with original present, retained with original absent | Exposes unresolved private-snapshot identity contract |
| Earlier hostile witnesses | Restart grant replay, partial failure, gate deadlock, independent writer, old complete generation, invalid metadata/database | Successful reproduction of limits, not claims those limits are fixed |

The 28 checks include witnesses asserting counterexamples. Green does not certify
production safety. Earlier real-volume operations and native status probes are
measurement history only; no provider-specific dependencies are in this spec.

## Next review decision

Review this bounded contract and package-1 tests first. Keep the private-working
pilot explicitly sized and gated; do not mistake the experiment for approval of
an immutable revision system or a wholesale storage migration. The remaining
unseen-newer-after-local-edit UX and durable restart/identity cases must be settled
before claiming the normal handover is shippable.

## Implementation pickup checklist

Start with owner design, this plan, cloud-file policy, current TODO, private
review/decision records and the POC README/HANDOVER. Inspect current diffs and
recent commits for every intended production path before implementing; a handoff
is context, not permission to override a later code decision.

| Order | Work and expected touchpoints | Done when |
| --- | --- | --- |
| 1 | Inventory canonical state/writers: `run_lifecycle.py`, `utils/output_backup.py`, `server/app.py`, `server/event_watcher.py`, `server/importer.py`, `server/db.py`, mutation/export routes and background jobs; native and CLI entry points | Explicit file/destination/writer matrix distinguishes canonical data, derived caches, private scratch and media; no assumed all-writer Boolean |
| 2 | Implement checkpoint serialization/publication and validation in focused new modules (names/location chosen to match nearby lifecycle helpers); reuse `utils/fs.py` and machine/study identity | Actual producer capture proves coherent bytes and curation, handles failure and legacy baseline; done-file reads are bounded |
| 3 | Persist observed checkpoint/epoch and staged candidate state | Partial/new then old arrivals cannot regress knowledge; crash/torn updates and unsupported records preserve prior usable state |
| 4 | Working-storage pilot through `server/app.py`, `server/db.py`, importer and route destination resolution; inspect `study_marker.py` and existing copy-remint code | Actual mutations, startup and shutdown preserve source bytes, original identity and local work across restart; storage/retention cost measured |
| 5 | Shared mutation admission at real local commit/file-publication boundaries, including supported CLI/native/background paths | Late requests, worker completion and independent-process writes are fenced; failure cannot leave a false editable state; ordinary handover resumes |
| 6 | Existing native status/popover + shared SPA access state/cartouche; established icons, i18n and accessibility | Real enforcement precedes “locked”; all lenses stay useful, drafts/focus are retained, both sidebar layouts and normal re-entry verified |

Rows are ordered dependencies, not claims every listed file must change. Extend
existing owners rather than creating parallel lifecycle/identity/error systems.
Do not invent new context-menu or titlebar controls.

**Repeatable laboratory check (run in the registered POC checkout):**

```sh
.venv/bin/python -m pytest experiments/study-access-poc/test_probe.py experiments/study-access-poc/test_adversarial.py experiments/study-access-poc/test_pinned_startup.py experiments/study-access-poc/test_handover.py -q
```

Existing result: 28 passed; not rerun just for this documentation refile. Meaningful
production regression tests belong under `tests/`, frontend behaviour under the
existing frontend test tree, native logic under the existing native test target.
Keep fault-injection tools under `experiments/`; do not move prototype witness
tests into the shipping suite unchanged or count them as feature acceptance.

For each implementation row record changed paths, actual tests/review scope and
remaining gates in TODO and the relevant private decision/review records. Run a
fresh review of the revised plan before treating old plan-review receipts as
approval of this version. Preserve the existing 13 open findings until explicitly
resolved or adjudicated. Commit only owned paths; this task has not committed,
pushed, released, or completed an end-session sign-off.

**27 Oct — shared producer boundary and file inventory, Codex:** The
`codex/study-access-poc` spike adds opt-in `study_producer.py`, `study_inventory.py`
and `server/producer.py`. Private local coordination serializes short writers,
registers long jobs without holding a lock across awaits, fences stale permits
across local reopen/processes, and protects final record publication. Explicit
server pilot covers factory startup, HTTP/ORM (including GET writes), people
DB+YAML/registry, importer, stage outputs, background jobs and settling helpers.
Every encountered output file is classified; unknown internal files refuse;
private/operational/user files are excluded. External recordings remain metadata
references, never blanket-fetched/hashed. See docs/design-study-read-only-writers.md
for adapter matrix, exact categories and activation gates. Tests include real
HTTP/YAML compound capture, stale independent process, partial failure, job awaits,
changed bytes/required set, refused pending flush and outer Host/auth ordering.
Automatic publication is OFF. Native/raw writers, actual CLI admission,
--clean predecessor carry, crashed-job/restart recovery, external-media pinning,
current privacy/cache policy and private snapshot identity remain open. Existing
13 review findings stay open; self-review only. No UI, cloud integration,
migration, commit, push or release. Verification: full free Python suite 8,928 passed, 46 skipped, 133 deselected,
9 xfailed, 474 warnings, 648.64s; final focused producer/checkpoint/read/WAL/POC
and Screens regressions 206 passed in 46.53s (no warnings). Full suite started
before the last reviewed guard/cache additions; final focused run covers those
final edits. Producer suite now 26 cases. Ruff on all bristlenose plus touched
tests clean; four new integration/checkpoint modules mypy clean; diff whitespace
clean. Native app not built/tested; independent review not rerun. Source hashes
and commands/results: spike out/package-1/producer-verification.json (ignored).

## Reviewed producer pilot close-out — 27 October

Verification: post-review full free Python suite 8,944 passed, 46 skipped,
133 deselected, 9 expected failures, 474 warnings (651.80s). Final focused suite
on the latest fixes: 353 passed without warnings (64.09s); covers 39 producer
and50 checkpoint cases, importer/WAL/read-policy/codebook/Screens and prior POC.
The full run began before the last follow-up edits; final focused tests cover
those edits. Whole-repo Ruff, four-module focused mypy, inventory/policy/proof
and ratchet gates pass (43 local mypy errors vs149 CI ceiling; not claimed
project-wide type-clean). Additional mockup-register gate has18 verified baseline
omissions unchanged by this work; both study mockups are registered. Native/UI
untested. No paid calls. Eight implementation findings fixed/rechecked, old13
feature findings open. Implementation committed `e23ae0e8a`; no push/merge/release.

The independent review covered Python primitives/adapters, not the full pending
native/read-only feature or historical HTML UX. Findings14–21 have regression
proof and rechecks; no old release gate is closed. The history/payload carry next-step instruction is superseded by the follow-up
below; restart/identity proof remains pending. No automatic publication hook
or wholesale working-store migration is enabled. Private raw results remain
ignored; source hashes and commands are in out/package-1/producer-verification.json.

## History and clean continuity — 27 October follow-up

The explicit Python producer pilot now archives immutable completion metadata at
`.bristlenose/records/<checkpoint-id>.json` before replacing the head. A legacy
head is archived unchanged; conflicting meanings of one id refuse publication.
Receivers remember a newly observed head before loading missing parent records.
They follow only its named ancestors and never erase unrelated remembered tips.

Metadata traversal is bounded to256records/16MiB and its read deadline includes
symlink/stat checks and bytes. Read-only workers inherit the run's existing
materialisation budget; timed-out workers cannot publish/delete/repair files.
These bounds can refuse long histories: compaction/retention policy remains an
activation gate, not permission to invent a root or silently drop old evidence.

Under explicit producer configuration, stash carries the current validated
payload and linked metadata into the fresh output, keeping its UUID. Older
payloads are not all recopied. The backup stays intact until the destination's
same captured head, lineage and copied bytes prove it is retained/superseded.
Missing head plus checkpoint artifacts is uncertainty, not a legacy exemption.
Restore refuses rolling a published B back to A before any rename. Shared failed-
tree deletion, PID-suffixed cleanup, spent/discarding cleanup and direct discard
all preserve continuity; export movement is followed by a final proof before
irreversible deletion. A failed carry raises and taints the producer rather than
returning the old ambiguous stash-None result. Ordinary unconfigured paths retain
legacy behavior.

Six usual-suspects lanes, compose and William reviewed this delta. Three concrete
findings were fixed and rechecked: missed cleanup/restore paths, mismatched
ancestry-vs-payload heads, and synchronous read metadata outside the deadline.
The shared deletion reproof was added after compose found the intervening-export
variant. Final focused run:186passed in26.71s, no warnings. Final source verification:8,979passed /46skipped /133deselected /9expected
failures /474warnings in654.17s (full free Python suite, final source, exit0).
Focused history/checkpoint/producer/backup/materialisation:186passed in26.71s,
no warnings. Whole-repo Ruff, four-module focused mypy, inventory/policy/proof
and ratchet gates pass (43local mypy errors versus149ceiling; not globally clean).
Implementation committed `fca24cfb0`; local only, no push/merge/release. Native/UI
untested. Earlier interrupted runs are explicitly not passing evidence.

Measured cost: a synthetic64MiB report required134ms settle and two proofs,
93ms in copying/validation. Both are retained because exports intervene; a test
corrupting the target during export carry proves the final proof is needed.
Representative slow-storage/large-study responsiveness remains an activation
check. Slow-stat reproduction now times out in21ms for20ms budget (formerly320ms).
Some legacy filesystem metadata/writes in clean itself are still synchronous;
this is not an OS-wide deadline or a distributed write fence.

Still unbuilt: process/crashed-job recovery, durable isolated working storage and
identity/re-entry, actual CLI/native admission, current privacy/media contract
and the approved lock UX. Original13whole-feature findings remain open. Main's
separate pendingR114guard must be preserved on integration. No provider-specific
calls, merge, easy Duplicate path, migration or release is enabled.

## Restart assumption witness — 27 October

`experiments/study-access-poc/test_restart_witness.py` starts a finite child,
kills and reaps its parent, then releases a gate. The child atomically writes
into the old working directory only after that gate. Standalone test passes;
Bach confirms the passing result proves post-parent-death file publication.
Startup IPC is bounded, and atomic file replacement avoids observing a partial
write. This is generic OS evidence, not a demonstrated Bristlenose launcher bug.

Next recovery proof must include child writers/launcher cleanup or fresh epoch-
scoped output isolation. Do not equate parent-PID absence or a released parent
lease with all writers gone; do not reset the coordinator into writable state
on that evidence alone. Preserve old mutable data for recovery. Existing native
kill/process-group behavior still needs inspection. No production recovery API,
private workspace migration or default activation has been added by this witness.

## Private workspace identity pilot — 27 October

Explicit `stage_workspace` / `load_workspace` and `create_app(workspace=...,
producer_boundary=...)` preserve the checkpoint StudyUID only for the exact
validated private root. Ordinary copies still remint. Real server startup,
HTTP saved edits and clean-stop restart are covered with the original present,
removed or changed; original source bytes remain untouched. A subprocess audit
refuses source writes/connections during startup and edit. This is Python audit
evidence, not a native sandbox proof. DB/WAL/SHM hardlinks are refused.

The private origin record retains the canonical protected boundary and base
fingerprint; loading does not probe an unavailable original. Staging failure
removes only its empty owned outer directory, allowing retry. Unexpected contents
and completed copies survive failure. A current edited DB need not hash to its
base checkpoint: the base is provenance, not a claim of freshness or edit authority.

Caller-owned private placement/exclusivity, sealed/crashed-job recovery, child
writers, incoming-version reconciliation, privacy/media admission and retention
remain gates. This proves clean-stop identity/edit durability, not managed-store
lifecycle or full re-entry. Default/CLI/native activation remains OFF.

Evidence: `tests/test_study_workspace.py` on the registered spike: **19 passed**;
combined checkpoint/identity/producer/workspace: **145 passed** in21.62s.
Full free Python suite: **8,998 passed,46 skipped,133 deselected,9 xfailed,474 warnings** in662.73s. Final focused producer/checkpoint/history/workspace/backup/materialisation: **211 passed** in34.36s. Whole-repo Ruff, focused three-module mypy, inventory/policy/proof and ratchet checks pass (43 mypy errors versus149 ceiling; not globally type-clean). No native/UI validation or default activation.

## Crash admission evidence and next lifecycle constraint — 27 October

`experiments/study-access-poc/test_producer_crash_witness.py` uses the real
ProducerBoundary in a subprocess. It commits a report DB change, signals that
commit, and is killed/reaped before the companion YAML write. Both cases leave
the DB new and YAML old. Without a registered long job, a new boundary currently
admits and seals this torn compound result. With a registered job, admit still
succeeds but seal refuses busy. These passing witness tests expose current limits;
they are not recovery acceptance tests or a new supported activation path.
Combined with the finite post-parent-death child witness:3 passed in6.90s.

The short coordinator transaction rolls back on death; it cannot serve as a
persistent dirty-lifetime marker. A job row protects capture, not admission.
Do not reset job rows or infer safe reopen from parent PID/lease absence.

**Pre-implementation lifecycle contract (implemented opt-in below; activation still gated):** acquire one machine-local private
workspace lifetime owner before factory/import writes; durably record active
before admitting any work; retain active/dirty after crashes or failed shutdown.
Only mark clean after request admission closes, background jobs are drained or
refused, the producer is sealed, and the matching local DB/files are safely
retained. Bind clean-close evidence to the workspace base, actor and producer
epoch. A subsequent owner must consume matching clean evidence under exclusivity,
advance the producer epoch, and keep the retired app/requests fenced. Missing,
corrupt, stale or active records refuse writable startup; no automatic takeover.
A failed clean-close write must leave the workspace unclean, not silently unlock.
This clean-lifetime path must be proved before defining exceptional crash recovery.

Launcher inspection: PipelineRunner Stop signals the process group; app Quit
signals without escalation. ServeManager contains parent-only SIGKILL paths.
Scene strips/stills decode to captured stdout then parent-written caches, while
clip backend can pass an output path directly to ffmpeg. This is call-site evidence,
not proof of an actual escaped Bristlenose child. Lifetime cleanliness must not
rely on generic parent death; preserve old output and use positive quiescence or
fresh epoch-scoped child output when implementing exceptional recovery.

## Explicit local lifetime implementation — 27 October

The preceding lifecycle contract now has an opt-in implementation in
`study_workspace_owner.py`: `own_workspace(workspace)` must enclose the whole
factory, requests and lifespan shutdown. It holds a nonblocking POSIX directory
flock, validates the private identity and base-bound lifetime record, persists
active before claiming the coordinator, and writes clean only after a matching
producer seal. Fresh staging initializes ready; missing/duplicate/corrupt/active
records refuse rather than repair. Existing unregistered private copies have no
automatic migration or clean assumption.

Clean successors consume matching seal evidence under the lock, advance epoch
and bind the durable open coordinator to their actor. Admission, writes and seal
respect that actor. The yielded boundary is terminally retired before releasing
the lifetime lock; queued transactions recheck retirement after obtaining their
SQLite transaction. A missing old job finalizer cannot taint a new owner.
Exceptions, busy jobs, tainted compounds, crashes and failed clean-record writes
leave active evidence. No PID test or automatic job-row deletion is involved.

`tests/test_study_workspace.py` includes actual owned factory/HTTP edit/clean
restart and independent-process exclusion/kill/refusal, plus metadata failures,
competing actors, post-close reuse and delayed transaction retirement. Final
combined workspace/producer/checkpoint/history:150 passed in26.82s. Whole-repo
Ruff passes. Full free suite:9,009 passed,46 skipped,133 deselected,9 xfailed,474 warnings in675.55s. This run began before the two final retirement concurrency fixes; the final150 focused tests in26.82s cover final source. Independent workspace recheck32 passed. Whole-repo Ruff, focused no-incremental3module mypy, inventory/policy/proofs/ratchet pass;43 mypy errors versus149ceiling, not globally type-clean. Do not conflate
previous 8,998-pass identity-only evidence with this lifetime delta.

This is explicit lifecycle integration, not default CLI/native activation,
managed private placement, exceptional crash recovery, full read-only UX or
re-entry. The lower-level identity-only `create_app(workspace=...)` remains a
trusted pilot API; it does not itself acquire lifetime ownership. Supported
activation must use the lifetime around every factory/request/background path;
that wiring remains a release gate. No existing feature findings1–13 close.

## Explicit CLI runner integration — 27 October

The internal `_start_server(..., workspace=...)` now uses
`server/workspace.py:workspace_application` to own the private workspace before
factory writes through the complete blocking Uvicorn runner. Both fixed-port and
kernel-assigned port paths consume that prepared app. No public flag, native
launch selection or default storage migration is enabled. Dev/reload, including
inherited dev environment, refuses before claiming the workspace.

A normal Uvicorn return is insufficient: the producer app records positive
lifespan startup and full teardown completion, reset per entry. The adapter
requires both receipts before its ownership context can seal and publish clean.
Missing receipts, startup/teardown failure (including errors Uvicorn logs and
swallows), or runner exceptions retain active/unclean state.

Tests include prepared fixed runner ownership, both normal-return-without-
lifespan paths, swallowed real lifespan errors, dev refusal without metadata
changes, and an actual dynamic loopback server: authenticated PATCH, competing
owner refusal, SIGTERM, clean close, saved DB edit and unchanged source study.
The permitted main test run proves real socket behavior; reviewer sandbox runs
could not bind loopback, so their socket failures are not reported as passes.
Combined runner/serve regressions: **138 passed in30.60s**, including the permitted parent's real socket PATCH/SIGTERM run. Whole-repo Ruff, isolated-cache focused two-module mypy, inventory/policy and ratchet checks pass. Prior9,009 broad tests do not cover this runner delta; no new full-suite claim. Earlier
whole-suite receipts belong to their dated source scopes, not this runner delta.

Supported native/default activation, policy/media admission, automatic completed-checkpoint publication/controller source observation and
uncertain-result recovery, exceptional crash recovery and locked UX/re-entry remain
pending. Identity-only `create_app` remains a lower-level trusted pilot API and
must not be activated as an alternative to the owned runner.

## Completed-edit checkpoint return proof — 27 October

Actual owned server/edit integration now proves A→B→C: stage A, save an HTTP
quote edit, publish B from the sealed private workspace, stage B into a second
owned workspace, verify/save its edit, publish C, then stage C and verify the
latest edit and complete predecessor chain. Source mutable DB bytes stay
unchanged: the new payload/head carry edits; a default legacy server opening the
old mutable DB is not an activated checkpoint consumer.

`publish(..., expected_predecessor=workspace.base)` and the forwarding
`publish_report` argument compare the complete predecessor record as well as
study/id before payload creation. Editing controllers must supply this evidence;
the optional legacy contract alone is not sufficient for workspace publication.
The publisher rereads the head inside the local final guard after archive work
before replacement. Tests preserve a newly delivered head at guard acquisition,
and preserve saved local edits/all source payloads when either same-id metadata
changes or a different newer head blocks publication.

Verification:162 checkpoint/producer/workspace/history tests pass in31.82s;
84 backup/discard/CLI-clean/materialisation tests pass in11.10s. Three review
lanes (code, silent-failure, security) report no new confirmed defects. Whole
Ruff and focused two-module mypy pass; repository gates recorded at close-out.
These are current focused results, not a new whole-suite receipt.

> These limitations describe the earlier return-proof stage. Explicit confirmed-publication pickup is implemented below; automatic controller/observation hooks and uncertain-result recovery remain pending.

This proves the sequential edited return through existing explicit APIs. It
adds no automatic shutdown publication, durable per-workspace publication/rebase
receipt, ambiguity/crash recovery, source DB overwrite, retention compaction,
policy/media admission, native/default activation or edit grant. Repeated local
editing after publishing still needs a durable controller pickup contract; do not
silently reset the base file over unsent work. Sync may still deliver another head
between the final read and rename; no distributed CAS claim is made.

## Durable confirmed-publication pickup — 27 October

The existing private lifetime record now stores the latest confirmed published
checkpoint, its active actor and pending-publication evidence. The immutable
staged base and origin fingerprint are not rewritten. `publish_workspace` requires
the actual owned boundary, validates it before coordinator mutation, restricts
the explicit destination to the registered protected study, and persists pending
before capture. Publication compares the latest confirmed record (or original
base for the first publish). Confirmation is stored under the producer seal.

Clean close rereads the active record under the same coordinator fence, retains
the confirmed checkpoint, and refuses pending results. A sticky actor uncertainty
latch also fences admission/queued/nested writes and clean close after any error
from publication, receipt replacement or guard exit. This covers a receipt that
was successfully replaced before reporting failure: the pending bit may already
be false, but the durable lifetime stays active and the actor cannot certify clean.
New ownership refuses active regardless of whether the caller caught the error.
No attempt is made to infer success or clear uncertainty automatically.

Tests prove repeated saved HTTP edit/publication across clean restarts of the
SAME workspace, exact predecessor chaining, unchanged base metadata, and receiver
retrieval of the latest edit. Faults before head replacement, after replacement,
before receipt and after receipt replacement retain saved edits and refuse clean
restart. Foreign-head arrival preserves that head and local work. The bounded
lifetime envelope allows one existing1MiB checkpoint plus4KiB lifecycle metadata,
while still rejecting an embedded checkpoint above its original1MiB limit.

Final combined workspace/producer/checkpoint/history/backup/discard/materialisation:
244 passed in42.41s. Whole-repo Ruff and focused three-module mypy/gates are
recorded at close-out. This is focused evidence, not a new whole-suite receipt.
One confirmed review finding (lost receipt acknowledgement) was fixed and rechecked.

This completes explicit confirmed-publication pickup across clean local lifetimes,
not an automatic controller. Default/native activation, automatic source observation hooks and source payload
adoption/incoming-version/dirty/draft handling, current policy/media admission, scheduled
or shutdown publication, exceptional crash/uncertain-result recovery, retention
and lock/re-entry UX remain gated. A confirmed cursor is provenance, not proof the
sync folder is latest or permission to overwrite an incoming study.

## Explicit source observation and write fencing — 27 October

`study_workspace_source.py:observe_workspace` now connects existing durable
announcement memory to an owned workspace. It records valid completion metadata
before payload arrival, compares against staged/confirmed provenance, and uses
bounded ancestry from both candidate and expected record. Current or provably
older delivery retains the existing epoch; it is not a fresh editing grant.
Multiple skipped self-publications, clean restart and first-observation older
head cases are covered without timestamps or a second lineage system.

Changed, unresolved, unreadable or invalid source/provenance evidence sets a
sticky refusal and closes the coordinator epoch, including while long jobs are
registered. Existing jobs and private saved edits remain; late permits/HTTP PATCH
refuse. A bounded diagnostic notice retains checkpoint fingerprint and friendly
machine name when known. Missing/corrupt private provenance is not reconstructed.
Coordinator/notice write failures still refuse admission and clean restart.
A newly observed head cannot be forgotten by later stale delivery.

A workspace controller lock serializes explicit observation, publication and
clean close, preventing an in-flight self-publication from appearing foreign.
It is separate from short writer coordination; controller entry inside a short
write refuses rather than invert lock order. Ordinary writes do not hold this
lock while source files are read.

Verification:261 combined workspace/producer/checkpoint/history/backup/discard/
materialisation tests pass in43.98s. Code/failure/fresh-eyes/security, compose and
William reviewed; three findings fixed/rechecked (expected ancestry gaps,
resolution RuntimeError, failed local provenance read). Focused three-module
mypy and whole Ruff/gates recorded at close-out. No new whole-suite receipt.

> The fenced writer still refuses all HTTP. The separate retained core reader
> is implemented in the following section; this observation-stage limitation
> is not a claim that retained core browsing is absent.

**Remaining:** this is an explicit observation operation, not an automatic poll
or runtime watcher. No source payload adoption, dirty/draft comparison, current
policy/media admission, read-only surface, native/default activation or re-entry
is implemented here. The existing pilot middleware currently refuses ALL HTTP
requests after fencing; normal browsing still requires the planned pinned read
surface. Data preservation is not a claim that the desired locked UX is delivered.
No user-facing cloud-status state or provider-specific API was added.

## Retained core report browsing — 27 October

Fresh explicit workspace staging now retains a second exact, hash-verified copy
of its initial validated report, before creating ready-lifetime evidence. It
copies report payload bytes only, never external recording references. A failed
retention leaves the completed working copy for investigation, without a ready
lifetime. There is one initial retained version per workspace; confirmed later
publications do not yet refresh it. This is opt-in, not a default storage migration.

`server/read_surface.py:create_read_app` uses the normal application/route handlers
with a validated immutable SQLite binding. It skips restore, migrations, importer,
watchers, background jobs, admin/dev labs, media mounting and MCP. The database is
opened mode=ro+immutable, query-only, with SQL write/attach/mutating-pragma refusal.
A connection marker prevents the normal global WAL initializer running on this
binding. Loaded Project output paths point only at retained report files, without
changing the DB. All retained files are hash checked; symlinks/shared inodes refuse.

The explicit core GET contract serves report info/dashboard, sessions, transcripts,
quotes, codebook, signals and mirrored researcher state. Unknown/side-effect
requests refuse; the outer existing Host/auth gates remain. Signals elaboration
query variants also refuse before DB/live generation. Retained sessions with
recording metadata omit the original-folder action and never resolve that folder.
Successful read responses identify the ACTUAL retained checkpoint in a header.
This can be older than the working edits or confirmed cursor; it is not silently
labelled as current. Working edits remain separate and untouched.

Tests use actual handlers after source fencing/removal; preserved local dirty DB,
unchanged retained bytes, raw SQL/ATTACH refusal, bad/hash/shared/symlink cache,
Host/auth, elaboration variants and original-path probe guards are covered.
285 focused workspace/producer/default serve/codebook/signals regressions pass
in56.65s;12 final retained checks pass in3.99s. Whole Ruff and seven-module mypy pass. Full rerun:9,059 passed,46 skipped,133 deselected,9 xfailed,474 warnings
in689.21s. This broad run predates the final read-only codebook precedence fix;
final focused285 tests pass in56.65s, plus12 final retained-reader checks in3.99s.
The initial full run remains recorded red (9,058pass/1restore-watcher timeout);
its actual delay remains unestablished despite passing repeated baseline/current
checks and a controlled baseline reproduction. No test timeout/gate was changed. Three review findings fixed and
rechecked; fresh-eyes/security/failure/code pass within this core scope.

Local synthetic performance (3 samples/size; zero-filled DB padding):64.1MiB
retain/hash/check81–87ms, open/hash/check47–52ms;240.3MiB retain280–371ms,
open162–174ms. Excludes preceding staging/app creation and does not represent
slow/remote storage. Existing512MiB payload cap means working+retained copies can
use approximately1GiB plus control/publication storage. Retention/placement remain
activation gates; no validation removed to improve these numbers.

**Still unbuilt:** this is core API plus HTML-shell proof, not a rendered all-lens
UX. Screens, recording playback, agents, downloads/live computation remain closed
pending explicit policy/capability work. No automatic switch from a fenced writer
to this reader, latest-published cache refresh, corrupt-working-store restart
loader, dirty/draft-safe adoption, frontend control disabling/cartouche, native
integration or re-entry is delivered here. The actual retained generation/age
still needs the agreed sidebar/popover indication before normal activation.

Retained-reader final review: code/failure/security/fresh-eyes plus compose and William complete; query capability, source-folder probe and default-group precedence fixed/rechecked. No all-lens/native/default activation.


## Quiet live fence: preserve saved local curation — 27 October

The initial immutable fallback can predate saved local edits. `capture_fenced_report`
now creates one additional private read generation after the actual live owner
has fenced admission and proved there are no active jobs. The proof is committed
under the producer transaction and retained only in that live actor's memory.
A busy, failed, retired, uncertain or unfinished producer cannot acquire this
permission; a job finishing later cannot upgrade an unproven fence. This grants
browsing only, never editing, adoption, remote publication or merge authority.

Capture reuses the complete publication inventory, finished-run checks, SQLite
backup and hash validation. It never changes the source head, confirmed cursor,
staged base, working edits or initial fallback. The immutable reader can explicitly
select this local generation and reports its actual checkpoint in the response
header. An incomplete capture is preserved and refuses automatic retry/repair.
This remains an explicit internal operation: no automatic reader switch or UI.

Verification:205 focused workspace/producer/checkpoint/history tests passed in
40.69s. Final strengthened fault tests:2 passed in1.80s. These inject included-file
mutation during capture and failure after payload rename before the final marker;
source, initial fallback and real saved quote edits survive, and retry refuses.
SQLite backup may create normal empty WAL/SHM sidecars; tests compare logical
backup bytes and saved SQL data as well as other files. Ruff and five-module mypy
pass. Usual-suspects code/failure/security/fresh-eyes and test/performance lenses
found no new production defect. Review requested the two fault proofs; both are
now covered. Feature-wide findings1–13 remain open. No new full-suite run here;
the earlier retained-reader full-suite result and its limits remain recorded.

Storage: one local read generation adds at most512MiB of retained payload under
the existing bound. Working+initial+local payloads can total about1.5GiB, excluding
control, publication history and transient capture/validation buffers. Copying,
validation and slow-storage placement remain activation concerns. No new cloud
provider APIs, paid runs, native UI or two-Mac validation were used.

Next: dirty/draft-safe incoming adoption, all-lens/media/current-policy capability
work, runtime handover, frontend/native status and enforced controls, and re-entry.
This slice does not clear those gates or activate the feature by default.


## Saved-work comparison before handover — 28 October

The no-edit real factory/lifespan probe (`/tmp/bn-handover-baseline-probe.log`)
proved that binary DB comparison is insufficient: startup changes projects'
input/output paths and imported_at, quotes' last_imported_at and screen_clusters'
last_imported_at. It changed no researcher input in that fixture, yet SQLite
backup bytes differed. The permanent restart tests reproduce that behaviour;
the temporary diagnostic dump is synthetic and is not a production log format.

`study_workspace_changes.compare_local_report` now compares two validated immutable
private generations against the original durable staged baseline. It compares all
required non-DB file paths/kinds/sizes/hashes, SQLite schema objects, application_id
and user_version, and all rows/columns in every table. Only relocated project
input/output paths and the explicit projects/quotes/screen_clusters/theme_groups
import timestamps are omitted. Created timestamps, privacy, identities and unknown
future tables/columns remain included. SQL rows are streamed in deterministic
binary column order; SQLite may still sort the full projected table. Validation,
errors and engine cleanup remain fail-closed; an error never means unchanged.

This is SAVED-WORK EVIDENCE, not adoption or editing permission. It cannot know
about unsent drafts, stop an old browser, prove a new source current, or switch a
runtime. It never resets the baseline on restart and never modifies source or
working files. Already-published local edits remain conservatively changed against
the original base pending a separately proved acknowledged-baseline policy. No
client, default launcher or native app calls it yet.

Verification:211 workspace/producer/checkpoint/history regressions pass in41.86s
before the final five test additions; final11 comparator cases pass in4.68s.
Cases include actual startup+clean restart, saved quote edits across restart,
privacy, created_at, transcript changes, changed schema, and same-schema unfamiliar
BLOB row update/delete/insert plus required-file insertion/deletion. Private/source
byte preservation is asserted. Ruff and one-module mypy pass. Usual-suspects
code/failure/security/fresh-eyes/test/performance reviews find no new production
bug; requested test strengthening is now covered. Prior feature-wide findings1–13
remain open. Full suite is not rerun for this unactivated module. Comparing full
snapshots and sorting tables has no realistic slow-storage measurement yet; that
remains an activation concern, with no default activation or editing grant.

Next handover work still requires draft retention/client generation identity,
validated incoming source/lineage, safe runtime switch and old-request invalidation.
All-lens/media/current-policy/native status and enforced controls remain open.


## Fixed report-document generation — 28 October

Explicit workspace writer apps now inject their actor generation into the report
HTML. The shared frontend API module captures it once for that document; delayed
callbacks cannot acquire a replacement server's generation from mutable global
state. Normal API requests carry a header; browser-managed report/CSV/XLSX/FigJam
download links carry the same fixed value as `bn_generation`. Settings' direct
Pipeline fetch and standalone experimental chat/codebook pages also carry it.

The inner producer middleware requires exactly one current value in each supplied
header/query channel, rejects missing/stale/duplicate/conflicting values before
producer admission, and retains existing outer Host/auth handling. Only exact
GET/HEAD /api/health is exempt, preserving unauthenticated discovery/embedded
readiness. No blanket GET exemption: lazy writers/download generators still need
context. Ordinary source apps and retained reader apps do not enable this pilot
guard; exports without workspace context retain their existing URL contract.

Tests cover actual owned clean restart with the same localhost credential:
previous-document PATCH/GET refuse, saved edits survive, current edits work, and
actual CSV download accepts current URL context and refuses stale, duplicated or
conflicting context. The real dynamic-socket runner now obtains context from its
served HTML rather than knowing a private actor out of band. Frontend tests keep
an old callback/module after a replacement module loads and verify old request
headers AND old navigation URLs retain old identity. This protects request
admission, not late response application, drafts, asset versioning or adoption.

Verification:168 workspace/producer/chat tests pass in45.60s;153 ordinary serving,
auth/Host/export/FigJam tests pass in17.22s. Full frontend:206files,3705passed,
2expectedfail in21.45s. Served+export production builds pass; existing export
large-chunk warning remains. Bundle gate unchanged:207,921bytes of222,000,
14,079bytes headroom. Four-module mypy and Ruff pass; frontend lint passes with
52warnings/0errors (existing allowed ceiling69). Initial frontend invocation had
no installed worktree dependencies; reused main's installed packages temporarily,
without package/lockfile change. Initial Python regression used a nonexistent
filename and ran no tests; corrected command produced the results above.

Usual-suspects code/failure/security/fresh-eyes and testing review found one new
compatibility defect (Finding37): unadapted fresh download/direct-fetch callers.
Caller inventory and generation-bound navigation fixed it; both lanes rechecked.
No new bypass found. Prior feature-wide findings1–13 remain open. Native direct
HTTP clients, unsupported workspace dev/reload surfaces, response/asset generation,
unsent draft recovery, all-lens policy, runtime switch and re-entry remain gates.
There is no automatic adoption, unlock, native/default activation or release here.


## Private draft recovery journal — 28 October

Tracing the real editor found that active EditableText typing lives only in the
DOM, while QuotesContext can roll back a failed save after the editor closes.
`study_workspace_drafts.py` now supplies the bounded private storage prerequisite;
**no HTTP/frontend editor calls it yet**, so typing-through-lock, draft focus,
UI recovery and safe handover are explicitly NOT delivered by this slice.

RecoveryDraft binds opaque document ID, actor generation, field, original text,
new text and revision. A put requires the exact prior revision; exact retries of
an active revision are idempotent. A save/discard acknowledgement removes only
that exact revision. Metadata-only cleared receipts prevent late initial requests
from resurrecting acknowledged/discarded text. A subsequent edit must advance
from that receipt; future clients must retain its predecessor or use a fresh
document ID on reload. read() returns active drafts only, never replay commands.
Nothing here proves a report save or grants editing/adoption authority.

Storage is intentionally beside the registered private workspace's saved working
copy, outside source/report/publication inventory, not in global browser storage.
It shares that workspace's retention lifecycle; no automatic expiry, cloud copy,
logging of participant text or report replay. Explicit limits:128active drafts,
4096document/field keys including cleared receipts,1MiB total encoded journal,
65536characters per original/new text. The byte limit also bounds Unicode payloads.
Full/invalid/ambiguous storage refuses rather than evicts unsaved work. Receipts
retain IDs/revisions only, not original/text. Validation diagnostics hide inputs.

A stable local nonblocking file lock serializes cooperating instances. Atomic
private replacement preserves existing recovery data on failure. Initialization
writes an empty valid journal, then an atomic started marker, then first payload:
failures at any first-write step can retry buffered text; an initialized missing
journal refuses instead of appearing empty. Corrupt/duplicate-key/wrong-generation,
symlink/shared-file state refuses. No PID, age or remote timing clears this state.
This proves process restart handling, not sudden power-loss durability or an
unbuilt UI recovery/cleanup policy. The API has no default/native activation.

Verification:211workspace/producer/checkpoint regressions pass in45.71s before
final initialization refinements;13 final journal cases pass in3.79s. Tests cover
separate-interpreter read, exact uncertain-replace retry, new typing vs old ack,
cleared-draft resurrection, metadata-only clear, all3first-initialization failure
windows, byte/count caps, busy lock, corrupt/missing data and symlink/hardlink
refusal, plus unchanged report/source bytes. Final Ruff and one-module mypy pass.
No full suite/native/UI/two-Mac test is implied. Usual-suspects code/failure/
security/testing and fresh-eyes found38(stale resurrection) and39(first-write
retry failure); both fixes are tested. Existing feature findings1–13 remain open.

Next: wire active edits and actual save acknowledgements to this journal without
false Saved announcements; preserve failed drafts and focus; expose a truthful
pending-draft gate before refresh. Then complete response/runtime generation
handover, all-lens/policy coverage, native status/cartouche and safe re-entry.


## Recovery API through a report fence — 28 October

The explicit workspace writer app now mounts GET/PUT/DELETE /api/workspace/drafts,
backed solely by its registered private journal. Existing outer auth/Host checks
and fixed document-generation admission apply. Only this exact path and those
methods bypass report-producer admission, allowing recovery storage after a source
fence without changing the report. POST/unknown paths still refuse. This is not
an editing grant and no endpoint replays or applies text to a report.

Bodies are streamed with a1MiB cap, strict fields/canonical UUIDs, duplicate-key
refusal and input-hidden validation. PUT body actor must match the app's actor.
GET returns authenticated pending recovery drafts; DELETE is an exact-revision
acknowledgement/discard operation, not proof that a report save succeeded. Corrupt
state and CAS mismatches return stable refusal; storage errors return503 without
participant text/validation details. No normal-source app or retained-reader app
mounts this pilot route yet.

Actual journal work runs in a worker under workspace_control, checking retirement
inside the worker, not only before body read/scheduling. Normal clean close waits
for that controller; a late body or retained old app cannot change evidence after
retirement. Exceptional shutdown continues to retain active/unclean evidence;
complete cancellation/thread recovery there is not proved or claimed.

Verification:232workspace/producer/auth/Host regressions pass in50.49s before
final UUID/lifecycle changes;4final API cases pass in2.92s against final code.
They exercise actual source fencing while recovery PUT/GET/old-revision DELETE
work, report mutation refusal, wrong Host/auth/header/body generation, oversized/
duplicate/malformed IDs, corrupt journal preservation, retained old app and a
request body delayed across actual normal owner retirement. Protected source and
report data remain byte-identical. Existing private HTTP operational log appends
are explicitly excluded from report-data equality (initial test caught that log
change); no source-log write was excluded. Ruff and3modulemypy pass.

Review found40(malformed UUID escapes as500) and41(retired actor journal access);
canonical request validators and worker-side lifecycle serialization fix them.
Fresh-eyes independently observed retired app409. No default/native activation,
UI draft capture, response generation handling, reader handover or unlock is
claimed. Existing feature-wide findings1–13 remain open. Next wire real DOM edits,
serialized persistence/retry and exact confirmed-save acknowledgements, then
truthful recovery and pending-draft refresh gate in the agreed status framework.


## Keyed editor recovery capture and exact save intent — 28 October

The workspace frontend now captures keyed contenteditable quote text and section/
theme titles/descriptions into the authenticated private journal. Active bracket
crop changes and computed crop commits have explicit recovery callbacks. Actual
Escape/no-op cancellation calls exact revision disposal from the real editor,
including quote handlers that stop event propagation. Non-keyed name/codebook/
other editors are NOT yet covered; their existing Saved feedback is preserved.

`reportContext.ts` holds the fixed document generation without coupling recovery
back through its API caller. One scheduled worker per field keeps the in-flight/
uncertain attempt plus latest unsent text, coalescing intermediate keystrokes.
Requests abort after10s; uncertain PUTs retry the exact revision before advancing.
A1000input delayed-response test emits2PUTs, not1001. A browser beforeunload guard
warns while recovery work remains pending; this is not native-close, abrupt-kill
or unacknowledged-last-keystroke durability. Text acknowledged by the server is
covered by the existing process-restart journal tests.

A report save first freezes/persists recovery, then issues its actual PATCH.
Strict workspace edit receipts require status=ok and a valid unresolved list;
unreadable/malformed200 answers retain drafts instead of certifying success.
Programmatic undo/revert or older request text never overwrites newer live typing.
Separate immutable `field:save:UUID` journal records protect unconfirmed report-save
intents: cancelling later B cannot delete earlier pending A if A then fails.
Only confirmed report saves acknowledge their intent and exact matching input
revision. Failed recovery cleanup retains pending evidence without falsely
rolling back a confirmed report save. There is no automatic replay/merge.

Pending-save capacity128 and field-key length are checked before scheduling save
promises; refusal never evicts existing work or issues an unprotected report write.
Acknowledged RAM buffers discard their original/text. Server128active/4096key/1MiB
limits still apply, including intent receipts; receipt/failed-intent cleanup and
long-session capacity/retention remain activation gates, not hidden auto-deletion.
One text gesture adds private-journal round trips; slow-store/real-browser latency
is not established by unit tests. No global browser participant-data cache added.

For supported keyed inline text, Saved waits for the exact commit token propagated
through store/API and confirmed receipt. A delayed first A in A→B→A cannot announce
the later A. Untracked codebook-style editors keep their existing path. English
existing announcements are reused; no new project chrome/cartouche is enabled.

Verification:full frontend208files,3727passed+2expectedfail in21.74s before final
capacity-preflight ordering change; final38focused recovery/widget/crop proofs
pass in1.17s. Final served/export builds and bundle gate pass209,398/222,000bytes
(12,602headroom), gate unchanged. Full lint52warnings/0errors passes; final changed-file lint8warnings/0errors
passes after the last preflight reorder. Real React
cases cover no-op blur, quote Escape propagation, exact Saved tokens and unkeyed
feedback; active crop callback, uncertain timeout retry, refused/malformed save,
cleanup failure and A-pending/B-cancel/A-fails are explicit regressions. Build
caught test Array.at target mismatch; replaced with indexed access. No broad
Python rerun for this frontend-only slice; prior draft API/store receipts remain
scoped. No real-browser/native/all-lens handover run is claimed.

Usual-suspects code/failure/security/testing/UX-accessibility lenses, independent
fresh-eyes, composed interaction review and William completed. Composition found
the pending-A cancellation loss and capacity-path rejected promises; fixed and
rechecked. William found the mechanisms proportionate to demonstrated loss cases.
Feature-wide1–13 remain open. This delivers capture/storage for the named editors,
NOT recovery UI, reload discovery, retained-reader integration, native/default
activation, all operation controls, coherent runtime switch or safe re-entry.


## Access facts and stable no-edit import — 28 October

The owned workspace app now exposes GET /api/workspace/access behind existing
Host/auth/fixed-generation checks. Facts serialize with controller operations:
actual write admission is writable, checking (temporary producer pause), or fenced.
A healthy publication seal stays checking and can use its existing explicit
reopen API; a status read does not turn it into a permanent lock. Failed base/
origin/lifetime provenance and recorded source/publication uncertainty establish
actual sticky refusal before a lock is reported. This decision uses structured
flags, never the display reason string. The producer-unavailable reason collision
is covered by an actual-app regression. Journal corruption alone is recovery
unknown, never empty. No status response grants adoption or re-entry.

The working base, last acknowledged source checkpoint and merely announced
checkpoint/device name are separate fields. Working edits mean the base cannot
be called the currently displayed immutable report: immutable_displayed_checkpoint
remains null for this writer app. report_requests_admitted is admission only, not
proof all lenses/media are available; after a source fence this writer refuses
report HTTP requests. A retained-reader/controller switch is still unbuilt.
recovery_pending=yes means retained recovery records exist, not proof every
record is unsaved (confirmed saves can leave cleanup evidence). No draft text
appears in this metadata response. No polling/native/popover consumer is wired.

A broad regression exposed real startup churn, not test flakiness: preserved DBs
showed cluster_quotes.assigned_at changing across00:54:50→51 on no-edit reopen.
The importer deleted/recreated pipeline memberships, so dirty comparison correctly
saw a changed value. Fix3544d3b0c preserves unchanged cluster/theme join IDs and
timestamps while deleting obsolete pipeline links, respecting researcher placement
and stranded pins. ORM deletion avoids a giant SQL NOT IN parameter list. The
forced2001timestamp/ID regression covers both join kinds without clock luck;
existing curation movement/exclusivity tests remain in the full run. No additional
columns were ignored and no dirty-comparison gate weakened.

Verification:initial access-focused238passed/1dirty-nonefailure in48.45s remains
recorded red; first fix-focused218passed39.29s. Final full FREE Python suite:
9141passed,8skipped,133deselected,9xfailed,474warnings in735.20s. Full suite used
final functional source; only stale importer comment wording changed afterward.
Ruff and scoped3API-module mypy pass. Four-module local mypy reports a missing
PyYAML stub at an existing importer import; alternate main-interpreter invocation
reports68errors across23files, not a clean receipt. No dependencies/type policy
were changed to hide these. Configured project ratchet passes with43mypyerrors
against CI149ceiling. Source/host/auth, source-fence, origin corruption, unknown
recovery, reason collision and temporary seal semantics are covered. No paid
calls, cloud-provider experiments, native/app-store build or all-lens UI claim.

Code/failure/security/testing and independent fresh-eyes reviewed the status and
importer changes; composition and William rechecked.50reason collision,51origin/
base classification,52no-op membership churn are fixed; prior1–13 remain open.
Next reachable recovery UI/reload discovery and pending-draft refresh gate,
non-keyed editors/retention, response/runtime/all-lens/current-policy/native
integration and safe re-entry. Default activation remains OFF.


## Recovery disclosure proposal — 28 October (not visually verified)

[Recovery popover mockup](mockups/multi-mac-draft-recovery.html) is a separate
PROPOSED artifact, not a replacement for the retained full/reduced Mac mocks or
owner approval. It uses current theme snapshots and the existing native-preview
shell: source specifies360pt/content height/320pt ceiling, fixed header, scrolling
body, ordinary diagnostic Copy and passive report lock cartouche. New disclosure
shows selectable recovery text; it has no Apply/Reopen/Unlock/Duplicate action row
and performs no replay. Main report content remains report content. English copy
is explicitly proposed outside the artifact, with a string plan for owner review.

Ordinary diagnostic Copy excludes draft text to avoid accidental participant
text disclosure in support reports. Recovery text requires explicit text selection/
copy. Scenarios distinguish journal-acknowledged storage, current-window-only
buffer, unknown journal, and unknown journal plus known RAM text (known text must
not disappear merely because storage is uncertain). Field labels need trusted
metadata or a generic label; no guessed match in a changed report. Record grouping,
retention and actual native/SPA integration remain gates.

Static HTML unique-ID/no-external-resource and Node syntax checks pass. Code/
compose review found the control/copy separation consistent with existing frames.
**Visual verification is NOT done:** browser security rejected the file:// URL;
no HTTP/alternate-browser/rendering workaround was attempted. This is not evidence
of pixel accuracy, wrapping, actual clipboard behavior, accessibility or native
layout. Keep the lifecycle marker PROPOSED/unverified until separately reviewed.


## Next bounded runtime integration — 28 October (working build spec)

Target the already-owned running actor: an explicit helper installs an inner
fenced-read dispatcher BEFORE ProducerRequestMiddleware and AFTER existing outer
Host/auth middleware. It is not enabled by CLI/default/native launchers. Healthy
requests keep the existing writer. Exact status/recovery control endpoints keep
their writer-side actor/context checks after a source fence. Other fenced report
requests use one validated private reader, preserving the original credential,
process discovery identity and document context. Unauthorized/foreign-Host requests
must not trigger expensive snapshot preparation.

On first fenced report request, a tracked/shielded lazy task attempts a quiet-live
local snapshot; busy/failed/unproven/unfinished or failed local capture selects
the validated initial fallback, recording that conservative selection. Invalid
fallback never becomes a blank successful report. One child reader lifespan is
owned by the parent app; normal shutdown waits for tracked preparation, closes
reader resources, then completes parent teardown. No detached task or new write
grant. Request cancellation cannot cancel the shared preparation. Exceptional
process death/restart recovery remains unproved and preserves existing unclean
lifetime evidence.

A response label records working epoch0 versus fenced epoch1, plus the retained
checkpoint on reader responses. This labels requests; it does NOT prove a browser
has discarded late old responses. Browser response-generation handling, active
editor/focus transition, all-lens/media/current-policy and native integration are
activation gates. Do not enable a browser switch/default flag on server tests
alone. Retained view selection must be exposed honestly in access facts; working
base/confirmed/announced/displayed generations remain distinct. Reader fallback
may exclude saved local work, whose working bytes and recovery records are kept.

Required proofs: real source fence+coreGETs+refusedPATCH, latest saved local text
when quiet versus old initial fallback when busy/failed, unchanged source/working
bytes, status/recovery still reachable, stable auth/discovery/HTML context despite
environment changes, concurrent first requests prepare once, cancellation and
positive parent/child shutdown, cache corruption refusal and no unauthorized
preparation. This is a server integration step, not v1 completion or re-entry.


## Explicit fenced-reader runtime — 28 October implementation evidence

`server/fenced_reads.py:enable_fenced_reads` now installs an explicit, server-only
owned-reader transition. No CLI/default/native launcher calls it. Outer Host/auth
and the same fixed document-generation gate apply before snapshot preparation;
unsupported paths/mutations refuse without preparing a reader. Existing health
GET/HEAD discovery, access facts and private recovery controls remain on the parent.
The child retains the original credential, discovery nonce and HTML document context,
independent of later environment changes; it registers no second handshake cleanup.

One shared owned task prepares the selected immutable view and enters/exits the
child lifespan in the same task (including ContextVar cleanup). Quiet-live capture
preserves saved curation; busy or failed capture selects a validated initial view.
Corrupt fallback returns503. A failed reader is terminal for that actor. Request
cancellation cannot cancel shared preparation. A separate owned shutdown drain
waits through outer cancellation and marks aborted teardown conservatively; it
never grants a writable successor. Abrupt process/loop death remains unproved.

Access facts distinguish selected reader checkpoint/status from a checkpoint
actually displayed by a browser (still unknown). Epoch0/1 labels describe dispatch;
a regression deliberately lets an old epoch0 response finish after the epoch1
reader is ready. Browser rejection of that late response remains mandatory.
No source adoption, re-entry, automatic observation, recovery UI, all-lens/media
policy or native activation is implied.

Final targeted runtime proofs:11passed/123deselected in4.16s
(`/tmp/bn-fenced-runtime-final-owned-proof.log`). Five changed server modules pass
focused mypy; Ruff passes those modules plus the workspace tests. Code and fresh
review rechecked the shutdown cancellation correction. One implementation finding
(53), so compose/William are omitted under the usual-suspects small-change rule.
Full Python run is separately recorded below when complete; it began before the
last failed-child reuse guard and its additional targeted test.


### Next boundary: browser responses and state (not implemented)

The runtime's delayed-read regression is the concrete starting test: a working
request starts, the source fence selects a reader, then the old request finishes.
The client must reject the old result even if its body finishes parsing after a
newer response. Checking only before `response.json()` is insufficient. Conversely,
a successful write acknowledged before a fence must not lose its recovery record
merely because the UI is transitioning: data delivery and durable save receipts
need distinct handling.

Inventory `utils/api.ts` generic JSON/text helpers, moderator-question direct
fetch, Signals streams and direct settings/chat calls before claiming coverage.
Recovery journal/control requests must retain their independent private-write
semantics. Reject missing/malformed epoch labels only under explicit owned-runtime
activation; ordinary served/exported reports must retain existing behavior.
The document actor and immutable-view epoch are different identities.

A monotonic client transition must notify mounted stores and active editors,
preserve typed text through the recovery path, and invalidate/refetch supported
lenses as one selected view. Discarding late data alone leaves previously loaded
working rows beside reader rows. Existing optimistic writes can also complete
late; do not replay them or infer save success from a refetch. A read-only
cartouche cannot be presented as enforcement until these paths are covered.

Required bounded proofs: late headers, late body parsing, failed/absent headers,
concurrent first reader results, old optimistic acknowledgement, pending/failed
recovery, component unmount and ordinary/export behavior. All-lens/media policy,
actual browser/native rendering and incoming coherent-version adoption remain
separate gates. Avoid global fetch monkeypatching: enroll explicit request paths
and record uncovered surfaces until they are refused or implemented.


Runtime broad verification receipt — 28 October: full FREE Python suite
9,151 passed, 8 skipped, 133 deselected, 9 xfailed, 474 warnings in 717.79s
(`/tmp/bn-fenced-runtime-full.log`, session49882). It started before the final
failed-child reuse guard and its additional during-lifetime test. Final targeted
runtime source: 11 passed, 123 deselected in 4.16s. Five-module focused mypy and
Ruff for changed server modules/workspace tests pass; git diff --check passes.
No paid calls, provider-folder experiment, native build or browser activation.


### Local latency probe and health identity correction — 28 October

The first timing attempt uncovered an actual regression in `ed512920c`: health
still returned200, but its lazy project-key decoration opened a ProducerSession
without admission, logged `producer_unadmitted` and returned a null key. Do not
count status200 as discovery-contract proof. Explicit workspace startup now primes
the existing canonical key under its admitted identity binding. Health uses that
per-app cache after a fence; failed startup decoration stays explicitly unknown,
with no later unadmitted database retry. Ordinary health's lazy behavior is unchanged.
Regression tests trap and COUNT database calls, including the unavailable-key case
(the helper catches exceptions, so a raising trap alone was not sufficient proof).
Discovery nonce stays stable; health never prepares a retained view.

`experiments/study-access-poc/runtime_latency.py` is a disposable, local-only timing
harness, bounded to10,000 synthetic quotes. It measures the first fenced core GET,
concurrent health/access requests, then a warm GET. It deliberately has no provider
folder activity or LLM invocation. It does NOT instrument source-write absence:
that proof belongs to the separate actual-runtime regression with byte comparisons.
Original experiment failed its response-shape assertion after revealing the health
log; that red log is `/tmp/bn-runtime-measure.log`, not a successful timing receipt.

One fixed-source run (single sample per size, warm filesystem, this machine):

| Synthetic quotes | DB bytes | First fenced GET | Concurrent health | Concurrent access | Warm GET |
| --- | ---: | ---: | ---: | ---: | ---: |
|100|352,256|178.64ms|41.90ms|163.36ms|7.58ms|
|10,000|6,979,584|754.90ms|42.73ms|310.61ms|407.46ms|

The large response was8,285,902bytes. This is a stress case, not a real-study
benchmark or cloud guarantee. Access facts serialize behind preparation's short
coordination ownership; health avoids that database/lock path. Real large caches,
cold/network-backed filesystem behavior, report size limits and native rendering
remain unmeasured. Don't infer a latency budget from these samples. Final harness
also smoke-runs100quotes after retention/format cleanup; exact receipts in `/tmp`.

Reproduce from repository root with the worktree environment:
`.venv/bin/python experiments/study-access-poc/runtime_latency.py --quotes 100 10000 --out /tmp/bn-runtime-latency.json`.

Health follow-up validation: shared server/auth/Host/MCP/Swift-contract tests
231passed in20.90s (before final negative-cache guard); final workspace runtime
13proofs cover that guard and zero-database-attempt assertions. Scoped Ruff and
two-module mypy pass. The earlier9,151full suite predates this health correction;
do not describe it as a full rerun of the final source.

The browser plan review also adds three mandatory requirements: guard at DATA
APPLICATION time (not only resolved helper delivery), explicitly choose a coherent
whole-document reload or report-root reset, and block any reload/reset while the
latest recovery text cannot be durably retained. Pending save receipts remain
separate from UI delivery. No auto-reload or transition UI is implemented here.


## Captured-buffer persistence barrier — 28 October

`reportDrafts.flushReportDrafts()` now waits for known recovery buffers and
independent pending-save intents, resampling changes that arrive during the wait.
It reuses serialized CAS/exact uncertain-revision retry; it does not replay report
writes, clear drafts, load other documents or reset the page. All selected attempts
settle before a failure is returned. Failure preserves RAM/journal evidence.
Returned immutable evidence contains document/field/revision identities, not
original/edited participant text. `isReportDraftFlushCurrent` rechecks at use time;
later typing or added/removed buffers invalidates it.

Independent review found a lost-DELETE-acknowledgement hole: a successful PUT is
not evidence that a revision remains in the journal after a later uncertain clear.
Track the clear target BEFORE sending DELETE. Pending/lost/malformed or ambiguous
current-revision clears invalidate existing evidence and refuse a new flush. Do
not resurrect the cleared revision. Conservative refusal remains until an actual
new capture/confirmed state supplies evidence; there is no reconciliation UI here.
The marker is revision-specific: an old exact clear cannot erase a newer revision.

A first attempted correction incorrectly reset the CAS predecessor to null and
changed the mock to drop revision history. Review caught the mismatch with the
real server: `WorkspaceDrafts.put` accepts a previous ACTIVE record OR a CLEARED
stamp as predecessor. Keep that revision after confirmed cleanup. The mock now
retains cleared versions and refuses resurrection, and a regression types B while
DeleteA is waiting, then requires B to name predecessorA. Existing Python journal
regression around test_study_workspace.py:1772 is the matching server contract.

Scope remains deliberately explicit: this does not scan the DOM for final input,
stop composition/untracked editors, inspect other documents/corrupt storage, provide
reload discovery/recovery UI, invalidate report-store data or grant reset/editing.
It proves acknowledged durability of KNOWN buffers at an instant, not whole-page
safety. Caller must capture/stop editors, handle unknown recovery and recheck at
application/reset time; no production reset path calls it yet. Beforeunload stays
conservative for pending work, including already durable recovery text.

Verification on final protocol-corrected source:27 focused recovery tests (919ms),
then3,737 frontend passes plus2 expected failures (208files,22.52s). Served/exported
TypeScript/Vite builds pass; changed-file eslint has no findings. Initial-download
budget209,425/222,000bytes passes. First root npm build invocation was invalid
(no root package), and an intermediate build caught unsupported Array.at in a test;
corrected invocation/array indexing passes. Intermediate green mock tests did not
prove the tombstone contract; only final corrected receipts support that claim.

Code/parsimony and independent fresh review applied. Findings55 (uncertain-clear
false evidence) and56 (introduced predecessor mismatch) are corrected/rechecked;
compose/William formal adjudication skipped for fewer than3 code-change findings.
Prior whole-feature1–13 remain open. No browser/native/default activation, cloud
provider work, paid model calls or safe re-entry claim.

The final composed regression also covers saveA waiting, type/cancelB, DeleteB
committing but losing its reply, then A succeeding and old DeleteA returningfalse.
An older ACK must neither overwrite nor clear B uncertainty. Set uncertainty only
for the current target; clear it only on a matching confirmed removal. The existing
capture API also refuses its same uncertain-cleared revision instead of returning
a stale PUT receipt. A genuinely new revision can advance from the retained stamp.
Final logs: `/tmp/bn-draft-flush-releaseproof-{full,build,lint,budget}.log`;
`/tmp/bn-draft-flush-final-recapture.log`. No test called this permission to reset.


### Editor transition inventory — 28 October static audit (not coverage proof)

A first React-source search found53 syntactic matches, including false positives
and development controls. Searching only `contentEditable=` missed QuoteCard's
boolean JSX prop and TranscriptPage's spread prop. Do not use that count as an
inventory of all writes, and do not globally disable every input/contenteditable.
The legacy JS, standalone chat/settings pages and native surfaces still need their
own enumeration. This table records inspected source, not behavior verification.

| Surface | Current recovery boundary | Required transition treatment |
| --- | --- | --- |
| QuoteGroup title/description, QuoteCard text | Stable edit keys; DOM input capture plus explicit crop callbacks | Final DOM/composition snapshot and capture ordering still needed before reset; keep selection/copy |
| SessionsTable speaker name (`EditableText`, around1137) | No edit key; `onNameCommit`, no known-buffer enrollment | Stable session+speaker identity, original text and exact save/cancel receipt enrollment; do not silently discard |
| CodebookAuthoring tag name, group subtitle/name (around258/354/573) | Three unkeyed EditableText call sites | Enroll with correct code/group identity and independent API save semantics; existing quote edit-key parser is not a general field protocol |
| PersonPicker existing/new name inputs (around516/585) | Local React draft state; no recovery key | Preserve original/typed name with intended operation and identity; pending new person may have no server ID |
| TagInput text (around317) | Local input; proposal/assignment behavior is separate from quote text | Decide/traverse exact commit semantics before enrollment; never replay tag creation automatically |
| TranscriptPage body (spread `contentEditable:true`, around1055) | Selectable caret host; raw words already refuse ordinary typing/cut/paste/drop | Keep cross-paragraph selection/copy/navigation. Refuse split/join/reassignment mutations under lock; do not treat entire recording as an unsent draft |
| SearchBox, TagSidebar search, Sessions zoom slider | Browsing controls | Keep usable; ordinary input presence does not mean report mutation |
| TagRow checkbox, CodebookV2Sidebar switch | Must trace exact selection vs persistence handlers | Do not infer mutation from checkbox appearance; separate browse filters from report writes |
| Settings appearance/locale/subtitle controls | Local preference paths; not study text | Preserve existing preference policy; not automatically blocked or journalled as analysis |
| Export/Miro/FigJam forms, Feedback textarea | Independent form drafts and side effects | Enumerate pending text/tasks and supported-route policy before root reset; current server reader refuses unsupported export/media/agent paths |
| Screens/Discussion view choices; development VisualDiff/ResponsivePlayground | View/development controls | Keep distinct from report curation; development-only surfaces are not release coverage |

Recommended next implementation order: first add a generic exact-field recovery
write adapter, preserving current quote semantics; then enroll speaker/codebook
text with commit/cancel tests against their actual API receipts. Existing
`preserveEditDrafts` derives quote/heading keys and must not be reused by inventing
`:title` suffixes for unrelated fields. Next snapshot/stop active keyed editors
without committing on blur, handle composition, and prove unknown active editors
block reset. Only then couple durable known buffers and recovery reload discovery
to a coherent browser reset. No global input-disable patch or auto-reload follows
from this audit. Current server mutation fence remains the authoritative write
refusal; UI enrollment must keep truthful content and normal browsing intact.


## Exact-field recovery write adapter — 28 October

`preserveFieldDraft<T>(field,text,write,saveToken)` now protects an exact enrolled
non-quote field and returns the real write callback's result. It shares the
existing private intent/CAS/acknowledgement worker with `preserveEditDrafts`;
quote/heading key mapping remains solely in the established quote wrapper.
Workspace calls without active captured original text refuse before the callback.
Ordinary documents keep the existing no-recovery path. Missing capture is never
replaced by guessing an original value from the proposed new text.

Tests cover exact speaker field identity (no invented `:text` suffix), typed result
and exact saved-event token, missing capture refusal, API validation failure with
retained live text/intent, later typing during a delayed save, and ordinary mode.
The worker still creates a separate pending-save intent before a real report write
and clears only exact confirmed revisions. This is an adapter, not UI enrollment:
a future callback MUST validate the actual API acknowledgement, not a resolved
optimistic dispatch/fire-and-forget operation. No caller currently uses it.

Further inspected enrollment boundary: SessionsTable.renameSlot draws an
optimistic name then calls `nameSpeaker`. That utility owns one serialized undo/
redo queue, rollback and PartlyWritten handling. Participant naming may write
`/people` THEN its session confirmation; moderator/observer uses a single slot
write. Merely wrapping a component callback would miss rollback when recovery
preflight refuses and could falsely clear recovery after a partial write. Put
recovery enrollment at the owned forward-write boundary, carry exact field/token
through the inline name commit, validate both actual acknowledgements and keep
undo/redo semantics. Picker new-person/role changes remain a separate operation
inventory; do not enroll them by inference from a text suffix or pretend this
adapter captures their local input.

Code/parsimony and fresh reviews rechecked the extraction and new adapter with
no findings. Formal compose/William skipped (zero new findings). This does not
satisfy editor capture/reset or any browser/native/default activation gate.
Verification receipt follows below; prior feature findings1–13 remain OPEN.

Exact-field adapter verification:32 focused recovery tests922ms, fullfrontend
3,742passed+2expectedfailures across208files22.37s. Final TypeScript served/export
builds pass, changed-file eslint clean, initial-download209,430/222,000bytes passes.
Logs `/tmp/bn-exactfield-{focused,full,build,lint,tsc,budget}.log`.
No Python source changed in this slice, no new Python/full-native/cloud/model test
claim. Temporary shared frontend dependency link removed before commit.


## Inline Sessions name recovery enrollment — 28 October

The inline Sessions name EditableText now has a session+slot exact field identity
and carries its commit token through renameSlot/nameSpeaker. Only this inline
text path enrolls; picker/native/new-person/role-choice entry without that token
keeps its prior path and is NOT covered by this work. No default lock activation.

Recovery protection lives at the owned forward-write boundary. Reserve a speaker
queue position synchronously, but invoke preserveFieldDraft immediately so its
immutable save intent exists BEFORE waiting for an unrelated speaker write.
A local prepared signal releases that reserved position after protection; refusing
preflight rejects/releases it, follows existing optimistic rollback/dropUndo and
reports failure. Observe prepared rejection immediately, even while a prior job
prevents its worker awaiting it. No detached rejection or reordered undo.

For enrolled forward writes `sendPutAcknowledged` requires explicit JSON
`status:"ok"` in addition to HTTP success. A10second AbortController covers request
and body parsing. Participant rename first reads people with the existing apiGet
10second timeout, then validates BOTH the people-map write and session-confirmation
write. Moderator/observer uses its existing single slot write. Partial participant
failure retains recovery and the established PartlyWritten undo semantics. Missing/
invalid/lost acknowledgement never emits Saved or clears recovery. Ordinary paths
keep prior behavior. This is not automatic retry/replay or a whole-operation10s
budget: each enrolled network step is bounded, and non-enrolled legacy paths still
need separate audit. Final active editor/composition reset handling remains unbuilt.

Independent review found/fixed:

-57 HIGH: protection inside speaker queue allowed prior-write wait, commitA,
  type/cancelB to erase A before its intent existed. Immediate intent reservation
  plus synchronous queue reservation protect text AND preserve undo order.
-58 MEDIUM: consuming an unbounded ACK body stalled the queue. Bound fetch/body;
  timeout preserves uncertain recovery and allows later explicit work.
-59 MEDIUM: prepared could reject before its queued await began. Immediate observer
  plus retained queued rejection handles blocked-prior/preflight-failure correctly.

Code/fresh recheck, independent compose check and formal William adjudication
complete. William:3real,0edge,0speculative, all fixes proportionate. Compose also
noted the inherited people-map prerequisite read; enrolled path now uses its
existing timeout, with a dedicated stalled-read regression and recheck.

Proofs include actual inline capture/token/Saved and Escape cancel, recovery
failure before API/rollback, invalid200ACK retention, both participant requests,
partial second-write failure, prior-job wait plus commitA/type/cancelB, immediate
undo during preflight, stalled ACK body then next name, failed preflight while
prior job blocks, and stalled people read then next name. These are jsdom/mocked
HTTP integration proofs, not native/WebKit or real-server transport verification.
Existing Python name routes return the validated status contract (routes/data.py).

Initial6integration cases passed; review-expanded run180pass/1canceltestfailure
was red because the mock reset its journal while reusing this document's s1
cleared predecessor. Isolate UI session IDs consistently, preserving mock tombstone
semantics. Initial TypeScript caught numeric projectId in test; corrected to the
existing string prop. Neither red receipt is final coverage.

Final focused183tests across5files4.47s; full/build/budget receipt follows below.
Prior whole-feature1–13 OPEN. Codebook/person-picker text, final DOM/composition
snapshot, recovery discovery/UI/retention, coherent browser reset, all-lens/media/
current-policy/native activation, automatic observation and coherent re-entry
remain gates. This does not complete the read-only feature.

Inline Sessions enrollment final receipt:3,754frontendpassed+2expectedfailures,
209files22.60s (`/tmp/bn-speaker-final-full.log`).183focusedpassed4.47s
(`/tmp/bn-speaker-final3-focused.log`). Final TypeScript served/exported builds
pass453/418ms Vite stages; changed-file eslint clean. Initial-download209,541/
222,000bytes passes. Logs `/tmp/bn-speaker-final-{build,lint2}.log` and
`/tmp/bn-speaker-budget.log`. No Python/native/provider/paid-model test claim.
Temporary dependency link removed before commit; no push/merge/release.


## Codebook inline text recovery — 28 October

The shared CodebookAuthoring components now enroll existing tag-name, group-name
and group-subtitle editors with exact field identities and commit tokens. Fields
are defined once in utils/codebookRecovery.ts and used by rendering and the owned
useCodebookAuthoring mutation handler. There is no codebook undo/write queue to
reuse; protection reserves its immutable intent immediately around the actual API
call. New-code TagInput text, merge/move/create/delete controls and picker/native
text are not enrolled by this change. No new UI surface or lock activation.

Group/tag update APIs can explicitly require bounded JSON statusok acknowledgements.
They reuse sendWrite's existing10s request/body deadline; strict status parsing
returns before the quote-curation unresolved-list parser, avoiding a second body
read. Named options separate acknowledgement validation from failure presentation.
Codebook errors stay owned by its existing hook: a real tag API409 retains the
name-clash dialog, while recovery storage/capacity/CAS409 is a save failure rather
than a duplicate name. Speaker acknowledgement behavior and legacy call paths stay
covered by regression tests. Group client-side name clashes retain existing UX.

A review found the rejected-empty tag branch had become a recovery no-op gap:
empty/whitespace commit closed the editor without API write or draft discard.
It now explicitly discards that exact field, matching the existing rejected-edit
semantics. Four real UI tests cover empty/whitespace crossed with Enter/blur;
valid failed edits continue retaining text and immutable intent. Empty subtitle
capture stores an empty original, never the translated placeholder.

Real component+hook+HTTP tests cover all3editors, explicit success receipts,
invalid200body retention, genuine tag409 versus recovery409, empty subtitle/cancel,
rejected-empty tag and stalled PATCH body. Invalid-ACK evidence waits for the
actual failure callback rather than merely observing a started request. These
are jsdom/mocked HTTP proofs, not native/WebKit or real-server browser behavior.
Code/fresh/parsimony reviews clean after finding60 fix; formal compose/William
skipped (fewer than3findings). Prior whole-feature1–13 remain OPEN.

Intermediate TypeScript rejected an overly broad vi.fn return type in the new
fixture; use Mock<()=>void>. Static lint caught a new missing callback dependency,
which is fixed. Changed-source lint now has only the existing render-time ref
warning in CodebookAuthoring; full warning ratchet is recorded with final receipt.
No compiler/lint assertion was disabled. No Python/native/paid/provider test claim.

### Transcript revisit test: observable state replaces timing guess

First broad codebook run:3,765passed,1failed,2expectedfailures across210files24.54s.
The failure was the unchanged TranscriptPage revisit assertion (1scroll vs2).
Its API module is entirely mocked, and its20ms sleep only followed read invocation,
not completion/render of session2. Original exact test passed in isolation114ms;
that does not erase the broad red result. The test now supplies actual session2
identity/number and waits for the visible Session2 label before navigating back.
It retains the exact two-scroll assertion. No production navigation code changed.
This strengthens the scenario's precondition instead of extending a sleep/timeout
or accepting one scroll. Focused7files191tests pass after this correction.

This is test hardening discovered during verification, not evidence that codebook
changes caused a production navigation bug. Keep its separate commit/provenance.
Final full/build/budget receipt follows; field capture, recovery discovery and
whole-page reset/re-entry gates remain open.

Codebook final receipt:3,766frontendpassed+2expectedfailures across210files24.46s
(`/tmp/bn-codebook-final-full.log`). Final focused191passed3.56s across7files.
Served/exported TypeScript/Vite builds pass600/523ms; configured lint passes with
52warnings/0errors, unchanged warning count. Initial-download209,646/222,000bytes
passes. Logs/tmp/bn-codebook-final-{full,build,full-lint,budget}.log. The original
broad red remains recorded; its timing cause is an inference, not a proven root
cause. The test's observable precondition is stronger without changing production
navigation. Source and test hardening use separate commits. No default activation,
provider experiment, paid call, Python/native/full-browser test or release claim.


## Browser person-picker recovery — 28 October

The Sessions picker and shared dashboard/transcript picker now enroll typed rename
and new-person names. Each opening receives a unique private field base carrying
session/slot context plus an openingUUID; rename and new-role inputs have distinct
fields. `ReportFieldCommit`/`captureFieldCommit` freeze accepted text synchronously
and forward its exact field/token through both real parents to the existing
protected speaker write queue. New-person text starts with an empty original;
rename records the displayed opening name. No action is replayed from recovery.

Unique opening identity prevents cancelling a new opening from clearing an earlier
failed submission for that same speaker. Explicit close/Escape/outside/badge/pencil
cancels only current-opening buffers, excluding submitted text awaiting actual ACK.
Role browsing and abandoning rename by Tab cancel the corresponding buffer. A real
Session→Paragraph scope change cancels name input; component/lens unmount alone is
NOT cancellation and retains known text. No effect cleanup silently deletes it.
Standalone/native pickers without an enrolled base keep existing behavior. Native
Swift picker typing is still uncovered and is an activation gate.

Reviewfinding62 HIGH: scope header invokes onScope even when its already-selected
Session option is clicked. Unconditional discard deleted the recovery record while
text stayed visible, so later unmount could lose it. Guard cancellation with an
actual scope change (`paragraph !== scope.paragraph`). The exact real-parent
regression types, clicks current Session, checks visible text+record, then unmounts
and checks retention. Fixed test passes; removing ONLY the guard makes it fail at
record-presence assertion. Source was restored after mutation, verified before
further tests. Logs/tmp/bn-picker-scope-{fixed,mutant}.log record the0/1exit results.

Coverage includes both actual parents, existing-name commit and new moderator
creation, correct originals, two-request participant ACKs, Escape/badge/outside/Tab,
role separation, actual scope change, scope no-op, unmount retention and failed-
submission/reopen cancellation. Initial19integration tests +193existing tests pass;
final focused205tests across6files4.53s. These are jsdom/mocked HTTP proofs, not
native/WebKit/real-server proof or a final DOM/composition-stop mechanism.

The openingUUID increases bounded journal-key use: existing128active/4096key and
byte/text limits still refuse rather than evict. Retention/reload discovery remains
required before activation; this slice adds no cleanup policy, reset authority or
native close/drain promise. TagInput/new-code/quote-tag text and final composition
capture, recovery UI, coherent browser/store reset, media/current policy and safe
re-entry remain gates. No global input disable, new UX words or default activation.

Code/parsimony and independent fresh review clean after62; formal compose/William
skipped (<3findings). Prior feature1–13 OPEN. Full/build/lint/budget receipt follows.

Browser picker final receipt:3,778frontendpassed+2expectedfailures across210files
22.74s (`/tmp/bn-picker-final-full.log`). Final focused205passed across6files
(`/tmp/bn-picker-final3-focused.log`); final served/exported TypeScript/Vite builds
pass536/435ms. Full configured lint52warnings/0errors passes; no new warning count.
Initial-download210,177/222,000bytes (34initial chunks) passes. First build caught
an unsupported test-only getByRole exact option; use an anchored name regex and
rerun final proofs/build instead of ignoring compiler. Logs/tmp/bn-picker-final-
{full,build}.log, picker-full-lint.log and picker-budget.log. No native/WebKit/
real-server/provider/paid-model verification claim. Dependency link removed before
commit. Default runtime/native activation, whole-page reset and re-entry stay OFF.


## 28 October — browser new-code and quote-tag recovery

TagInput now has an exact per-mount private recovery field in enrolled report
contexts. Raw typing and accepted suggestions are captured; submission freezes
accepted text and a separate save intent before actual API dispatch. Codebook
creation validates a bounded POST entity acknowledgement. Quote tags require a
valid status/unresolved receipt; partial or unreadable receipts retain recovery.
Both QuoteGroup and shared Screens/Discussion quote hosts forward ownership.
Explicit cancellation discards only its own field; unmount retains it.

Curation queues reserve ordering synchronously before recovery preflight and
also serialize acknowledged cleanup, so refused preflight or delayed cleanup
cannot release subsequent writes/undo early. No report-write replay. A selected
same-tag assignment still unanswered causes the new enrolled gesture to refuse
before changing any target, using existing save-refused copy and retaining text.
Confirmed duplicate no-ops can clear their own field.

Review found and fixed rapid Tab entry's existing ref-only key (state now
remounts immediately), stale delayed blur overwriting refocused typing (cancel
on focus/cleanup), and mixed-selection optimistic duplicate clearance (refuse
whole new gesture). The blur regression fails with focus cancellation removed.
New-code stalled-body test covers the 10-second POST timeout and retained text.
Fresh-eyes and independent composition review found no further concrete defect.
Final verification and commit identity are in the private pickup/review ledger.

This extends browser editor coverage only. Final DOM/composition capture,
recovery discovery/UI/retention, browser application-time response barrier and
coherent store reset, native integration, incoming adoption and safe re-entry
remain activation gates. Default runtime stays off; no native/provider/merge or
full-feature completion claim. No new source filesystem destination.


## 28 October — old-document report transport stop

`reportTransport.stopReportRequests()` is a sticky per-workspace-document latch.
Every utils/api fetch now checks it at actual dispatch. Work queued before stop
refuses afterward; no transient status can unlock the document. Private recovery
uses its separate bounded transport and may still persist/clear acknowledged
work. Health/control discovery outside utils/api is not globally intercepted.
There is deliberately no production caller or activation in this commit.

Review disproved a method-only stop: GET/signals/codebooks?elaborate=true starts
LLM/cache work and GET/codebook may create/migrate/link rows on a working server.
Hold ALL old-document helper requests rather than enumerate allegedly harmless
GETs. Retained-view browsing must belong to a fresh coherent document; this is a
transition prerequisite, not the steady-state read-only browser implementation.
The server remains the actual all-writer authority; external feedback/native/
other direct transports are not certified by a helper wrapper.

A refusal carries409 + stable report_transition_stopped reason. Plain409 meant
"duplicate code name" to existing handlers; actual hook tests now prove stopped
rename/create preserve raw+submitted intent without opening that dialog. Its
existing failure path requests refresh (onChanged); transition integration must
keep the known report visible rather than let refused refresh replace content.

Already dispatched requests are not aborted: an actual save ACK may still clear
only its protected private recovery. Conversely, an old GET result can resolve
after stop (explicit regression). Application-time response/store fencing is
still required. This does not stop DOM typing, composition, blur/layout cleanup,
native writes, or establish replacement/retention/re-entry permission. Next:
synchronous editor stop plus final DOM capture, unresolved composition refusal,
unknown-editor refusal, recovery discovery and coherent whole-document reset.

Verification:3,806 frontend passes+2expected failures/213files25.07s; served/export
builds, lint0errors51warnings,210,611/222,000byte initial34chunks. Then added an
explicit late-read limitation regression:14targeted pass (no source changes).
Fresh/code review, independent compose and William all checked final boundaries;
findings66–68 resolved by the transport design and reason. Earlier1–13 remain
OPEN; default activation OFF. Logs /tmp/bn-stop-{reviewed-*,final-targeted}.log.
Initial hook test incorrectly expected no onChanged on numeric refusal; source
already requests authoritative refresh, corrected test expects2. Not a product
regression or saved-success proof. No real browser/native/provider test claim.


### Next editor boundary — implementation contract (not built)

Audit evidence: QuoteCard's layout cleanup calls commitEdit while the DOM is
still present; EditableText and TagInput can commit on blur; PersonPicker and
TagInput capture controlled input values directly, whereas current document
capture only watches keyed contenteditables. Therefore neither blur nor unmount
is a safe way to stop editors, and flushReportDrafts alone is insufficient.

Implement a single per-document terminal editor-stop operation, composed with
stopReportRequests BEFORE editor teardown. It must capture actual DOM values
using existing field identities and trustworthy original baselines (value for
input/textarea, textContent for contenteditable), including a final value with no
input event. Keep roots/nodes/identities in currentness evidence; a new editor,
changed value, removed/replaced root or changed private revision invalidates it
at the actual replacement point. Unknown writable text controls refuse the
operation; do not invent a field/original or silently ignore them. Search and
other non-report controls need explicit ownership/inventory before an exemption.

Active IME composition must not be force-committed by blur or treated as final.
Track composition while the capture service is installed. Persist known
provisional text conservatively, but refuse replacement until composition is
finished and a fresh final snapshot succeeds. A timeout is refusal, not evidence
of completion. Browser/WebKit composition ordering remains an integration proof.

Stop edit events before changing DOM editability, avoiding React blur/Enter/
Escape handlers, timers and layout cleanup. Preserve native selection/copy;
blanket inert/disabled content is not the intended retained browsing experience.
Capture event interception is only a temporary old-document boundary; steady
read-only controls/cartouche remain a separate integration step. New report
requests are already held, but late callbacks must also be unable to discard or
overwrite the final recovery snapshot. Actual pre-stop save ACKs must still be
able to clear only their matching revision; do not retain stale text falsely or
abort an earned ACK. Final stop must be sticky until document replacement.

Failure keeps the old report and recovery evidence, with transport still held;
no automatic unlock, report-write replay or reload. This terminal failure path
needs the existing sidebar/popover coordinator, not a new report error surface.
Recovery discovery/retention is required before any automatic replacement.

Required direct proofs: DOM-only last keystroke; input+textarea+contenteditable;
provisional composition and compositionend; unknown editor/baseline refusal;
blur/Enter/Escape/layout cleanup cannot save/discard final text; copy still works;
typing/new editor/root replacement during persistence invalidates evidence;
storage failure/lost clear refuses; old valid saveACK/newer snapshot race; original
non-workspace/export documents unchanged. Actual component tests must include
QuoteCard crop cleanup, codebook and PersonPicker/TagInput rather than only DOM
fixtures. No production stop or replacement activation on these tests alone.


## 28 October — final DOM editor stop and private persistence

`stopAndFlushReportEditors(root)` now composes the sticky report transport stop
with a terminal editor snapshot and existing private-journal flush. It captures
actual input/textarea/contenteditable values even without an input event. Scope
is document-wide to include portaled pickers; the report root must stay connected
and unchanged as an anchor. Known originals come from captured entries, focus/
beforeinput baselines, or explicit data-edit-original on enrolled TagInput/
PersonPicker inputs (including unfocused new-person fields). No original/key is
invented. Duplicate identities, unknown controls or missing baselines refuse.

Edit event interception and readOnly/contenteditable=false preserve native
selection/copy paths rather than making the report inert. Raw capture/discard
and new save preflight are sealed before DOM editability changes; stale timers
and cleanup cannot overwrite/erase final text. EditableText, TagInput and crop
helpers also refuse late commit/cancel/entry. Actual pre-stop API acknowledgements
can still clear only their own intent/revision. An ACK for A cannot erase final
DOM B; it invalidates earlier revision evidence, requiring a fresh flush.

Composition is tracked independently of DOM membership. Known provisional text
is persisted but active/just-ended or detached unfinished composition refuses
final proof. A zero-delay task after compositionend only settles that event's
input sequence; it is not an active-composition timeout or proof of browser IME
behavior. Live Safari/WebKit ordering remains an activation gate. Detached
unfinished composition may conservatively remain refused; no force-finish,
assumed cancellation or automatic unlock. Such text remains accessible/recoverable.

Evidence is current only while exact nodes/keys/values/editability/root/body and
private revisions remain current, with no new writable editor or composition.
Changed/detached/unknown DOM never grants replacement. A failed storage attempt
may retry its exact journal revision against the same frozen DOM; cached rejected
promises are not treated as permanent failure. Unknown DOM-only text also keeps
beforeunload guarded even with no journal entries (not a native-close proof).
Beforeunload cancellation itself is not proof that a browser displays a dialog.

Verification: final3,829frontend passes+2expectedfail/215files25.41s; builds pass;
lint0errors51warnings; initial211,768/222,000bytes34chunks.22new direct+actual
component proofs include DOM-only last text, input/textarea/contenteditable,
unknown/duplicate/missing original, active/end/orphan composition, known+unknown
portals, storage503retry, mutated/replaced DOM, copy/select events, old saveACK
versus newer final text, and real quote/heading/new-code/portaled-person editors.
The actual quote blur is scheduled BEFORE stop,170ms allowed to pass, then real
layout unmount must not commit. Removing final-discard guard or crop commit-stop
guard separately makes the corresponding regression fail (both restored).
Logs/tmp/bn-editor-{final-*,discard-mutant,cleanup-mutant}.log.

Fresh-eyes, repository-context code/silent-failure/UX/a11y/performance/Bach,
independent compose and proportion review rechecked final source. Orphan IME and
unknown-journal unload holes fixed (69–70). A reviewer briefly observed the
intentional temporary missing-guard mutant; recheck retracted it, not a separate
source defect. Baseline ref-to-state change avoids a new React render-ref warning.

No production caller/default activation, recovery discovery/UI/retention,
application-time old-response barrier, coherent replacement, all-lens/current-
policy/native integration or re-entry grant. Unknown search/feedback/other text
controls deliberately refuse until ownership/exemptions are audited. Copy event
proof is synthetic, not live clipboard or native accessibility certification.
Prior whole-feature1–13 remain OPEN. Existing stale-status and all-lens report
behavior must not be replaced by a main-content error surface on integration.


## 28 October — read-only recovery discovery across document restart

`reportRecovery.readReportRecovery()` reads exact private GET/workspace/drafts
with fixed document actor headers, no-store and redirect refusal. It remains
available after old report transport stops. It validates the complete200JSON
response before exposing any record:1MiB decompressed streaming UTF8 bound,
10-second fetch/body abort, canonical IDs,128records, exact fields, unique
(document_id,field), Python-compatible codepoint bounds and well-formed Unicode.
Outputs are frozen. Older document/generation records and separate same-text
buffer/save-intent records remain intact. No filtering, adoption, replay, delete,
report writes or automatic UI mounting. Empty is valid only after successful
complete validation; all failed/unavailable/malformed reads reject as unknown.

Fresh review found native JSON.parse discards duplicate members and could turn
{"drafts":[record],"drafts":[]} into apparent empty recovery. After native syntax
validation, a bounded nonrecursive lexical pass compares decoded object keys,
skips complete escaped strings and rejects duplicates/discarded invalid nested
objects. The contract only contains envelope + draft objects. The actual Python
JSONResponse cannot emit this fault; this is defensive client contract enforcement,
not a demonstrated backend serializer defect. Four raw duplicate regressions fail
when the guard call is removed; restored guard and quoted-key-like text test pass.
Errors do not include participant content. GET responses now carry no-store too.

`recoveryCoversReportFlush` proves exact document/generation/field/revision record
coverage only. It does NOT prove currentness, discovery UI visibility, lifecycle
ownership/retention, new report coherence or reload/re-entry permission. An old
read may immediately become stale; caller must separately recheck final editor
and private revision evidence at use. Cross-workspace/base adoption discovery is
not provided by this endpoint: it reads the current registered private workspace.

A shared tests/fixtures/workspace-recovery-contract.json pins real Python GET and
TypeScript parsing. The actual API reads its older-generation records through two
successive server actors, byte-identical journal and unchanged source. TS module/
document restart discovers retained text without importing it into active draft
state, and no replay/clear requests. This proves same-workspace restart discovery,
not real browser visibility, source-change adoption or native recovery UI.

Verification:44focused discovery tests;19Python draft/API/restart regressions;
Ruff clean; mypy workspace_drafts1file clean. Fullfrontend3,873pass+2expectedfail/
216files24.91s, both builds/lint0errors51warnings,211,768/222,000bytes34chunks.
Then a stricter two-toast-copy assertion passes its focused test; source unchanged.
First full run had all assertions pass but one unhandled React window teardown
error and is NOT a green receipt (/tmp/bn-recovery-final-full.log). Existing
codebook transition test used a detached real toast root;02e857cfe mocks only
that rendering boundary, keeps real refusal/copy selection, waits both handlers
inside act and asserts both messages. This avoids outstanding test UI work;
timing-specific root causation remains an inference, not an isolated repro.
Final green log /tmp/bn-recovery-reviewed-full.log; duplicate guard mutant log
/tmp/bn-recovery-duplicate-mutant.log. No paid/provider/native/browser runs.

Fresh/context security/silent-failure/perf/Bach/proportion and independent compose
reviews clean after fixes.71duplicate-wire validation and72test-lifecycle follow-up
resolved. Earlier whole-feature1–13 remain OPEN. Defaults OFF, no production
caller or new approved popover/copy. Recovery disclosure proposal remains visually
unverified; no alternate browser/mock rendering workaround was attempted.


## 28 October — fixed view binding and shared lens application boundary

Owned runtime SPA HTML now declares its actual app view: working epoch0/null,
or retained epoch1/checkpointUUID. Declaration happens at response time because
the explicit runtime attaches after HTML construction; a delayed parent answer
still declares0, never guesses its later child's state. Production and main HMR
SPA paths include context. Unowned standalone reader/prototype contexts remain
outside this browser contract. ReadSurface labels1/checkpoint; the outer runtime
replaces epoch labels rather than duplicating them. Real responses have one label
of each kind. Auth/fixed actor admission remains separate and authoritative.

`reportContext` copies/validates explicit metadata once. Absence is the legacy
opt-out; malformed presence is refusal, never an opt-out. Successful report GETs
must match the document's exact epoch/checkpoint before body parsing. An unread
mismatch is cancelled and stops old-document dispatch. Epoch1 non-GET report
requests refuse locally without stopping pinned browsing; this matches the core
server pilot contract, not proof that every GET is passive or every native write
is covered. Already-dispatched mutation ACKs retain their earned cleanup path.
Private control/recovery stays separate. No automatic reload or transition caller.

JSON/text/moderator bodies recheck after await. Moderator404 is semantic data
(null), so it explicitly validates view labels too; skipping all non-OK responses
would silently accept another view's "no question" (73). Stream callbacks check
at each actual item, including two frames in one chunk. `useLensRead` checks before
read and at application/error/retry boundaries; an already-resolved value cannot
reach its drawn lens after stop. Malformed initial context reaches the existing
first-read error path instead of silent loading (74, red→green regression).
Direct callbacks/stores outside this owner, prototypes, native messages and media
remain an explicit inventory/activation gate. This is not all-client certification.

Actual browser experiment: Chromium and WebKit render A in working documents.
An authenticated private edit saves B without changing the full original source
tree. After a synthetic source announcement/fence, both OLD documents still show
A. Manual reload creates retained documents; both render saved private B and
exactly match the same immutable checkpoint/epoch1. Original source tree remains
unchanged by retained browsing. No page exceptions/external browser requests;
reader prepared/closed/teardown receipts true. This tests real SPA/server paths,
not a mockup, and proves neither automatic handover nor disabled edit affordances,
native WebView/IME, playback, every lens or re-entry. Desktop rendering profile is
used; no font-network dependency. No provider folders or LLM operation requested.

Reproduce with existing Node24, Python dev and E2E/browser dependencies:

```sh
.venv/bin/python experiments/study-access-poc/browser_view.py --out /tmp/bn-browser-view-new
```

Output directory must be new. `--e2e-root /path/to/another/checkout/e2e` reuses
installed dependencies; no installation/default launcher activation. Lab always
seeds a disposable synthetic study, binds an ephemeral loopback port, guards
server identity, owns/closes both headless browsers and server, and removes its
synthetic working data after retaining receipts. It never accepts a real study.
Browser ownership is registered before context/page startup; all close attempts
run, and exceptional Python termination has bounded terminate→kill fallback (75).
Positive closure is not a guarantee for every OS/process failure or editing re-entry.

Verification:3,900frontend pass+2expectedfail/219files27.67s;56focused;177selected
Python runtime/SPA/auth regressions; Ruff clean; mypy app/fenced_reads/read_surface
3files clean; both builds/lint0errors51warnings. Initial212,307/222,000bytes34chunks.
Three separate mutants (epoch, semantic404, application check) fail expected tests;
restored56focused pass. Full suite/build completed BEFORE mutations and source
was restored byte-for-byte. Final generic browser lab exit0 in
/tmp/bn-view-owned-close-final/{result,closed}.json; both engines oldA→retainedB,
source unchanged, zero external browser requests. Source/full logs
/tmp/bn-view-final-*.log; targeted /tmp/bn-view-restored-targeted.log; Python
/tmp/bn-view-server-regressions.log. Earlier single-browser timeout used an unused
_DESKTOP env spelling; correct BRISTLENOSE_PLATFORM=desktop removes the CDN font.
Exact first-timeout cause was not captured, so font causality is inferred. First
repro wrapper failed only writing a shadowed output variable after browser checks;
corrected rerun and final cleanup rerun pass. Failed logs retained, not green proofs.
No recovery mock was rendered or its blocked visual workflow bypassed.

Fresh/context/proportion and independent compose reviews clean after73–75 fixes.
Original whole-feature1–13 remain OPEN. Default activation OFF; no released lock,
push, merge or new UI approval. A coherent whole-document replacement still needs
recovery visibility/retention/ownership, full controls/policy/media/native support
and safe incoming adoption/re-entry. Direct-store audit starts with supplementary
Sessions tapestry/quality/people callbacks, CodebookV2Sidebar, TagSidebar and
LensSubtitleSync. Sessions PRIMARY read already uses useLensRead; do not refactor
it based on an obsolete assumption that its machinery is wholly separate.

## Background report pollers — 28 October

ConditionStore and LastRunStore now use the fixed-view report transport and
recheck after JSON parsing before applying data, refreshing lenses, announcing
completion or posting lens availability to the native host. A sticky stop also
prevents project resets, visibility resume and further timer scheduling. Already
queued native messages are not revoked by this browser-side guard.

Four focused regressions exercise delayed body parsing and mismatched view labels
for both pollers. Existing polling lifecycle tests remain green:27 focused tests.
Full frontend:3,904 passed plus2 expected failures/220files24.37s. Served/export
builds pass; lint0errors/51warnings;212,335/222,000bytes. Fresh independent review clean. No new read-only route capability,
automatic transition, launcher or default activation is provided. The retained
reader still refuses condition/last-run routes; their supported snapshot/control
policy remains part of the unfinished capability work. Next audit: Sessions
supplemental reads, sidebars, subtitle bridge and remaining direct stores.
Logs:/tmp/bn-polling-{focused,full,build,lint,budget}.log.

## Sidebar hydration and subtitle stop — 28 October

SidebarStore rejects post-stop server group/framework hydration, including the
failed-read retry state, without freezing local widths/open state or altering
mutation ACK bookkeeping. LensSubtitleSync guards codebook dispatch, late read
adoption and route/store-triggered title/native subtitle/filter posts. Previously
queued native bridge messages still require the separate native generation gate.

Independent fresh review clean.114focused tests pass; final test explicitly checks
positive native subtitle posting then absence of subtitle/filter posts after stop
and route change. Full frontend3,906pass+2expectedfail/220files23.90s (before the
final bridge-assertion addition; final114focused rerun passes). Served/export
builds pass; lint0errors/51warnings;212,378/222,000bytes. No activation, editing
re-entry, read-only affordance or every-client certification. Next direct reads:
Sessions supplemental data, CodebookV2Sidebar, TagSidebar and remaining stores.
Logs:/tmp/bn-sidebar-stop-{full,final-focused,build,lint,final-types}.log.

## Supplemental Sessions and navigator reads — 28 October

Sessions supplemental tapestry/quality/people reads check document application
permission, strip polling checks before dispatch, and post-speaker-write view
refresh checks after the acknowledged-write queue settles. The queue itself is
unchanged. CodebookV2Sidebar guards dispatch, Promise.all success and error-view
application. TagSidebar guards mount/event codebook reads and project-name
application, sharing one cancelled mount/event lifetime. No write ACK or local
browsing preference was globally frozen.

Fresh review clean;122focused tests pass. Three independently removed application
guards (people, tag book, navigator book) each caused the matching DOM assertion
to fail; sources restored byte-for-byte and122focused rerun green. Fullfrontend:
3,909passed+2expectedfail/220files25.22s. Served/export builds pass; lint0errors/
51warnings;212,400/222,000bytes. Logs:/tmp/bn-supplemental-*.log. Tests prove
bounded callback behavior, not queued React/native commit cancellation or full
read-only UX. Default activation OFF; no automatic replacement/re-entry provided.
Next audit: direct global data adoption (SignalStore, screensCount, QuotesContext)
and remaining view callbacks before transition-controller integration.

## Incoming quote and Signals adoption — 28 October

QuotesContext guards initFromQuotes (including floor and quotesLoadCount) and
initHeadingEdits before applying incoming report data. Search/local selection
and earned mutation ACK bookkeeping remain separate. SignalsPage checks before
fetch/stream dispatch and at late sentiment/codebook success/error, each streamed
finding and stream-finally application. SignalStore and screensCount deliberately
remain usable: they project local browsing into the sidebar/subtitle and are not
the network adoption boundary. Freezing them would break normal locked browsing.

121focused tests pass: stopped quote/floor/heading/load-counter adoption, retained
search use, late Signals success/failure, stream findings/completion and project
refetch. Fullfrontend3,913passed+2expectedfail/220files25.35s; served/export builds
pass; lint0errors/51warnings;212,409/222,000bytes. Logs:/tmp/bn-global-adoption-*.log.
Independent bounded review clean in fallback lane after fresh-lane capacity failure.
Owner now requests a whole-plan William simplification review; no further expansion
of this architecture pending that review.
This is not automatic transition or full all-client protection. Next: transcript
reads, Screens data/arrangement imports, search/native callbacks and controller
composition. Default activation remains OFF.
