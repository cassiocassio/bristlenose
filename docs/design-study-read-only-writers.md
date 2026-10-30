---
status: partial
updated: 2026-10-30
last-trued: 2026-10-30
trued-against: recovery guard and startup admission integrated; prototype reader remains parked and default off
scope: package-1 producer boundary; not proof every syscall/writer is covered
---

# Study access protection — state and writer inventory

Companion to [owner design](design-study-read-only.md) and
[implementation plan](design-study-read-only-plan.md). Current code work is in
the parked `codex/study-access-poc` branch. Main's machine-owned recovery and
startup-admission guards are a smaller, integrated safety boundary; the pilot is
not activated by them. This matrix records located owners, not an all-writer
certification. Explicit pilot adapters are wired only on that parked branch;
default reader activation and automatic checkpoint emission remain OFF. There
is no released read-only UX.

## Canonical state and destinations

| State/destination | Located owners | Capture/protection requirement |
| --- | --- | --- |
| `.bristlenose/bristlenose.db`, WAL and SHM | `server/db.py`, `server/models.py`, importer, API routes and jobs | Back up committed DB state through SQLite; never treat a raw DB copy or a read-only URI on the source as a private snapshot |
| Researcher names/roles in DB and `people.yaml` | `server/routes/data.py:patch_people`, `_write_through_people_yaml`; pipeline people output | DB commit and YAML replace are separate; YAML failure currently logs best-effort. Capture must account for both canonical outputs and failure, not certify at the first commit |
| Speaker recodes and reanalysis pins, `.bristlenose/sessions.json` and carried starts | `session_registry.py`, `pipeline.py`, `server/routes/data.py` | Shared generation boundary across DB and registry publication; pins must not be lost during concurrent import/run saves |
| Raw/cooked transcripts and intermediate quote/theme/screen/topic/speaker metadata | Pipeline/stage writers; `server/importer.py` readers | Freeze the actual required inventory; file hashes alone cannot tell whether the producer assembled mixed generations |
| Study identity and beacon | `study_marker.py`, importer `_remint_if_a_copy`, native `StudyMarker.swift` and `ProjectIndex` | Private staging must retain original study identity, not enter the ordinary duplicate-study remint path |
| Run PID/events/manifest and restore/stash trees | `run_lifecycle.py`, `utils/output_backup.py`, CLI/pipeline | Lifecycle metadata is evidence, not the whole report checkpoint. Carry predecessor/identity evidence across `--clean`, stash, restore and reanalysis; do not fabricate a new root after losing the old head |
| Current MCP/Screen privacy settings and sensitive cached results | DB settings/grounding, screen jobs/routes/index purge logic | Known current policy must constrain a frozen report; a copied older preference is not permission to re-expose data |
| Derived scene strips, hover frames and screen-text indexes/stills | `server/scene_strips.py`, `server/screen_text_job.py`, associated routes and caches | Classify as derived state with explicit destinations and retention; a producer does not quiesce simply because analysis ended |
| Recording bytes and other user inputs | Importer SourceFile paths, media route, pipeline decoders; native copy/import | Reference/pin the correct version, bound needed reads using existing policy; no blanket copy/hash of all large media on each open |
| Clip/still/export folders | `routes/clips_export.py`, `routes/screens_export.py`, export jobs/helpers | Destination-specific capabilities; do not overwrite protected study output after lock, but do not prohibit safe unrelated exports by HTTP verb alone |
| Logs, scratch, caches and workspace bookkeeping | startup logging, temp helpers, derived jobs, new checkpoint metadata ledger | Explicit private destinations; no accidental source writes or new uncontrolled PII store. Logs are not part of the report's content hash |
| New checkpoint record and sealed payloads | opt-in `study_checkpoint.py`; machine-local `study_checkpoint_state.py` | Publisher requires caller-owned coherent staging and inventory; consumer produces a copied version, not an editable grant. Observation state must be outside protected source |

## Writer entry points to integrate

1. **Before server factory setup:** `create_app` can reclaim output, create logs,
   mkdir/open the DB, initialise schema/migrations, import/cleanup data, mint/remint
   study identity and reconcile jobs. Deciding access after this sequence is late.
2. **Importer and event watcher:** whole/progressive imports and reattachment can
   update DB state without a human API mutation. The existing pool-attachment
   baseline was deliberately moved before import in recent N133 fixes; preserve
   that ordering while adding any access decision.
3. **GET can write:** `routes/codebook.py:get_codebook` ensures the default group
   and project link, then commits. A read-only HTTP-method allowlist is insufficient.
4. **Ordinary data routes:** edits/tags/stars/visibility/headings/layouts/framework
   settings and people recoding all persist state. Some also publish YAML/registry
   files after DB commits. They need the same generation boundary.
5. **Codebook and background proposal jobs:** codebook, AutoCode and codebook-builder
   routes/jobs commit independently. A cancel request is not a commit fence.
6. **Other lens mutations and exports:** transcript and Screens routes persist
   edits/layout; export tasks continue after admission and can publish files later.
7. **CLI lifecycle and restore:** run/analyze/transcribe, stash/restore/reclaim and
   signal/backstop paths are separate from the report server. Existing settle
   `_settling` only coordinates settle/reclaim/stash, uses a folder flock where
   available, and can run unlocked on Windows. It is not the shared report-writer
   barrier and must not be presented as one.
8. **Native host:** StudyMarker/ProjectIndex identity/copy handling, CopyMachinery,
   run/server spawning and availability/bookmark leases are separate owners.
   Do not infer a remote Mac's state from local PID liveness or an app left open.

A static scan of server/stages plus pipeline, lifecycle, registry, identity and
output-backup files located **262 candidate mutation calls across 42 files from
116 scanned files**. The ignored `out/package-1/writer-candidates.json` in the spike
records those calls. This is a navigation aid: aliases, write helpers, SQL executed
through other methods, subprocesses and native effects are not a complete census.

## Implemented opt-in producer pilot — 27 October

The spike now includes `study_producer.py`, `study_inventory.py` and
`server/producer.py` in addition to the checkpoint publisher/receiver and durable
announcement ledger. Automatic lifecycle publication remains OFF. This is a
Python integration pilot, not the released all-writer/read-only feature.

| Participating owner | Boundary in the pilot |
| --- | --- |
| Explicit `create_app(..., producer_boundary=...)` | Factory setup runs inside admission/write scope before recovery, logging, schema and import; root/database mismatch refused before startup |
| HTTP routes, including GET that writes | Existing Host/auth middleware stays outside admission; fixed request permit reaches worker threads; ProducerSession fences execute/flush/commit and rolls back refused pending changes |
| People and speaker routes | Compound scope covers DB plus YAML/registry publication; best-effort YAML failure taints the producer, preventing a false complete checkpoint |
| Importer, schema, identity, manifests, registry, raw/cooked/render output | Short compound/leaf adapters participate when called inside an explicit operation |
| Pipeline, AutoCode, codebook builder, clip/still exports | Long jobs register until completion across awaits; they do not hold the short-write lock during model/network work |
| Scene-strip and screen-text workers; on-demand still cache | Spawning thread copies the operation context; whole passes and on-demand still decoding/cache writes register as jobs |
| Settle/stash/restore helper | Existing settling scope also takes the local boundary when explicitly configured; bounded payload/ancestry carry and destructive cleanup proofs are implemented; native/CLI/default activation remains pending |

The boundary uses a separate private SQLite coordination database outside the
study. Short writers serialize; sealing drains them and refuses active long jobs.
Epoch changes invalidate admitted old requests/sessions across reopen and across
processes. Competing SQLite writes in pilot sessions explicitly refuse and roll
back rather than waiting while holding coordination; ordinary sessions retain
their five-second timeout, including after pooled pilot connections return.
This safe refusal is not a completed transparent queuing/retry user flow. Publication checks its seal again under the final local record guard.
Partial leaf/job failure closes the producer. Clean route validation precedes
job registration; async registration/finalization runs off the event loop and
waits for workers even during cancellation. Required role-pin creation and undo
preparation failures block certification. Failed capture stays sealed; only
the same live owner can retrieve its seal and explicitly reopen. Crashed jobs
remain busy: no expiry, forced takeover or restart recovery has been invented.

### Complete output-tree classification

`study_inventory.inventory` classifies every encountered file, rather than
relying on an example list. It deliberately prunes checkpoint history and temp
subtrees, recording those subtree exclusions. Unknown internal files refuse
capture. Directory enumeration errors refuse rather than silently omitting a
subtree. Required symlinks refuse capture. Categories are:

| Category | Contents and treatment |
| --- | --- |
| Database | Canonical DB captured through SQLite backup; WAL/SHM are operational, never copied as independent payload |
| Report | Study identity/beacon, people YAML, session registry/carried starts, finished manifest, transcripts, session pages, main report HTML/Markdown and intermediate JSON |
| Resource | Assets allowed by the existing report-serving extension contract; known scene-strip/turn-frame/screen-text resources |
| Operational | Run metadata, logs, resume manifest, checkpoint record/ancestry/payload history, scratch, legacy index alias and OS metadata; excluded |
| Private | PII summary, LLM diagnostics and hidden asset files; excluded |
| User file | Other output-folder files and unsupported asset types; classified but excluded |
| External input reference | SourceFile path/type/recorded size from a private DB backup; recordings/documents are neither fetched nor hashed |

Consumer staging pins the trusted database path and role before durable
observation; aggregate byte accounting refuses before the next payload write.
Capture requires completed report lifecycle evidence, seals admission, validates
JSON syntax/study identity and people YAML using the existing reader, captures
required files, then rescans the required set and compares current bytes with the
captured hashes before final record publication. Changed required set/content
refuses publication. The source stays sealed on either success or failure.
Resources still need their reader-specific format/current-privacy policy checks;
classification does not imply that every cache is safe to expose.

## Activation gates still open

- Explicit confirmed-publication pickup and source observation/fencing are tested;
  automatic observation, all-lens/policy-covered browsing, incoming-version/dirty/draft handling
  and uncertain-result recovery remain pending.

- The internal explicit workspace runner owns fixed/dynamic startup through
  teardown. Public/native/default selection and supported activation remain
  pending; native/raw SQL/DBAPI/subprocess writers can bypass the Python boundary.
- Predecessor/payload carry is now tested in the explicit producer path; native/CLI
  activation and retention/compaction remain open.
- Establish restart recovery for sealed/failed owners and crashed job rows.
- Prove pending ORM transaction/flush behavior under contention; method-level
  fencing must not be described as a drained session lifetime.
- Pin external input versions and enforce current privacy/resource policy in the
  private read surface. No blanket recording copy/hash is proposed.
- Explicit identity, lifetime ownership and internal CLI runner are tested; prove
  public/native/default integration, managed placement, exceptional crash/child
  recovery and safe re-entry before activation.

The final comparison detects tested bypass schedules; it is not an OS fence
against an uncooperative native writer between checks. Local final publication is
not distributed compare-and-swap. No UI/read-only mode has shipped and none of
the 13 plan-review findings is closed by these implementation experiments.

## Verification — 27 October

Full free Python run: 8,928 passed, 46 skipped, 133 deselected, 9 expected
failures and 474 warnings in 648.64 seconds; command exited successfully.
Final focused run after the last guard/cache changes: 206 passed without warnings
in 46.53 seconds, including 26 producer cases and existing Screens regressions.
Ruff is clean across `bristlenose/` and touched tests; the four new integration/
checkpoint modules pass focused mypy. Self-review only; native app untested.
See spike `experiments/study-access-poc/FINDINGS.md` and ignored
`out/package-1/producer-verification.json` for scope and source hashes.

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


Quiet live fence read capture: memory-only positive proof under the coordinator; no jobs, healthy prior open/sealed phase. Private snapshot publication rechecks exact fence and full inventory; does not reopen any writer. See design-study-read-only-plan.md, 27 Oct quiet-fence evidence.


Saved-work comparison (28 Oct): `study_workspace_changes.py` reads validated immutable initial/local generations only; narrow importer bookkeeping omissions, every other schema/table/column/required file compared. No baseline reset, draft knowledge or editing grant. See plan evidence.


28 Oct document context: workspace API admission checks fixed actor generation (header or generation-bound download query) before permit creation; exact GET/HEAD health discovery exempt. Frontend captures generation once per loaded module/document. Native direct calls and response/draft/asset fencing remain gates; see plan evidence.


28 Oct private recovery destination: `study_workspace_drafts.py` writes only bounded journal/lock/initialization metadata beside registered private workspace, never report/source/publication. Revision receipts prevent stale clear/replay. No HTTP/editor integration yet; future UI must not claim draft retention before actual writes/acks and recovery policy. See plan evidence.


28 Oct recovery API exception: exact GET/PUT/DELETE /api/workspace/drafts may write bounded private journal while report actor is source-blocked; auth/Host/document-generation remain mandatory, all report routes retain producer gate. Actual journal work is serialized with normal owner retirement and refuses retired actors. No reader/native/default mount yet; see plan evidence.


28 Oct keyed-editor destinations: focus/input capture plus explicit crop/cancel callbacks write private recovery only. Exact saveToken and validated PATCH receipt gate clears; separate field:save:UUID intent survives later active-buffer cancellation. Coalesced input/10s transport bound, pending-intent cap128, no replay. Non-keyed editors, cleanup policy, native closing/reload recovery and draft-aware refresh remain gates. See plan evidence.


28 Oct status facts: exact GET /api/workspace/access bypasses report admission only after auth/Host/document context; it can establish an actual fence for provenance/recorded uncertainty, and reads private recovery without exposing text. Temporary healthy seal remains checking. No re-entry grant or immutable-view claim; working base/confirmed/announced data stay separate. Importer reconciliation preserves unchanged link identity/time while retaining deletion/researcher/pin rules. See plan/full-suite evidence.


28 Oct frontend recovery coverage: exact field/token enrollment now includes
inline Sessions names and codebook tag/group name/subtitle, alongside quote/
heading/crop buffers. Immediate immutable intent and bounded validated API receipts
protect acknowledged clears. Known-buffer flush is not whole-page reset permission;
picker/new-tag text, final DOM/composition capture, recovery discovery/UI/retention
and coherent response/store transitions remain gates. These are private journal
writes plus existing report APIs, no new source destination. API statusok certifies
its existing route contract, not atomicity of historical best-effort auxiliary
writes (notably name write-through YAML). No default/native/re-entry activation.
Latest exact verification in implementation plan/FINDINGS. Earlier dated entries
are checkpoint history, not current claims that all editor integration is absent.


28 Oct browser picker coverage: both browser parents pass exact opening-scoped
text/token to the owned speaker queue. Per-opening cancellation never means
unmount; submitted text waits for route ACK. A current scope click is a no-op,
not draft discard (62mutation proof). New-role names have empty originals.
Native Swift picker, TagInput, composition/reset/reload discovery/retention remain
activation gates. Opening UUIDs use existing bounded journal keys with refusal,
not eviction. No new source/report destination; default runtime remains off.


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
