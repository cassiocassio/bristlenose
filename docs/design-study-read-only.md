---
status: pending
last-trued: 2026-10-30
trued-against: recovery guard and startup refusal integrated; optional reader and lock remain deferred
---

# Study access protection — enforced lock v1

**Review pass:** Enforced lock v1 plan-review, 26 Oct 2026.
**Scope:** cause warning + enforced write barrier + coherent browsing + passive
access cartouche, as one shippable capability. **No warning-only release.**
Duplication, merge, cloud coordination and new project menus are excluded.

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

## Implementation and supporting artifacts — 28 Oct

[Implementation plan](design-study-read-only-plan.md) holds the post-POC build
sequence, file/writer inventory task, acceptance gates and evidence map. This
file remains the owner design/UX authority. The whole feature remains proposed. An opt-in Python producer/receiver pilot
now covers coherent publication, private identity/lifetimes, explicit owned runners
and source fencing; focused retained-core proof and a full-suite rerun pass (exact source scopes and
the earlier timing-sensitive failure are recorded in the implementation plan). Automatic
control, full policy-covered browsing, dirty/draft-safe adoption, native/default
activation, re-entry and the user-facing enforced lock remain unbuilt.
The opt-in workspace frontend now covers quote/heading/crop, inline names,
codebook and picker/tag text with private recovery ownership, final DOM/editor
stop, read-only same-workspace recovery discovery, fixed view binding and shared
lens application guards. Controlled Chromium/WebKit manual reload is proven;
automatic replacement, direct-store coverage, recovery UI/retention and native/
default activation remain unbuilt. See the
[writer inventory](design-study-read-only-writers.md) for exact coverage.

- [Recovery disclosure proposal](mockups/multi-mac-draft-recovery.html): new selectable-text disclosure, diagnostic Copy excludes drafts; PROPOSED and visually unverified.
- [Reduced v1 visual draft](mockups/multi-mac-v1-guards.html): current review aid;
  historical warning-only comparisons do not authorise a warning-only release.
- [Initial full N-Mac mockup](mockups/multi-mac-study.html) and
  [full/narrowed scenario design](design-multi-mac-study.md): preserve earlier
  complexity for future work; not the normal v1 implementation target.
- [Deferred duplication](design-study-duplication.md): separate future operation.
- POC code/results live in `experiments/study-access-poc/` on the
  [parked spike branch](BRANCHES.md#codexstudy-access-poc), not on main.
  Its README is the experiment entry point. Raw generated reports stay ignored.

## Owner decisions and current state

- One person using a home Mac and laptop on one synced study is expected use,
  not a licence/device-limit problem. Optimise sequential use, not collaboration.
- Warning-only is insufficient: automatic/background writes still happen and a
  returning connection can deliver a partially updated study. “Please don't edit”
  is not safety. The warning must be backed by enforcement before it ships.
- Keep the ordinary severity glyph and factual cause in the existing sidebar
  subtitle/popover. **Changed on another Mac** is for observed changes; an
  unresolved foreign attempt does not prove that Mac is currently open/running.
- Show the consequence as a tiny passive **lock + Read only** cartouche at the
  report viewport's bottom right, across lenses. No action, dismissal or toggle.
  This is the explicit narrow exception to keeping management out of content.
- On entering the enforced lock, a brief one-shot warning-tint emphasis may
  settle to neutral. Respect reduced motion; no repeat on lens navigation.
- Existing report browsing remains normal wherever coherent data exists.
  No new warning page in place of an available report, no fabricated empty data.
- No Duplicate offer in the popover, recovery advice or normal handover flow.
  Independent duplication is a later exceptional operation with no merge promise.
- English first in the existing localisation structure; translate with the
  existing suite after wording/behaviour settle, before normal release gates.

The **immediate R114 recovery guard and conservative startup admission** are
integrated on local `main`: new run markers contain a namespaced machine ID;
automatic restore/delete requires matching local machine and run identity;
foreign or uncertain unfinished activity refuses ordinary writable startup.
Legacy/unknown attempts are preserved. This does not make shared SQLite safe,
provide the immutable reader illustrated below, or approve automatic handover.

Earlier N-Mac exploration is retained in `design-multi-mac-study.md`; menu/copy
feasibility is `design-study-duplication.md`. Earlier draft history was saved in
`docs/private/read-only-design-history-2026-10-26.md`. Where they differ, the
owner decisions and scope above govern. The current HTML's warning-only picker
is a historical comparison, not an accepted delivery stage.

## Safety contract and limits

1. Once access becomes uncertain or a newer foreign activity/generation is
   observed, stop admitting study writes. Every cooperating Bristlenose mutation
   path must obey the same policy, including automatic work.
2. An “enforced lock” is published only when existing writers cannot later
   commit/publish to the protected study. UI controls alone are not enforcement.
3. Locked browsing uses one validated, machine-local report generation outside
   the synced study. Do not keep reading a changing shared DB/WAL as a shortcut.
4. Never delete/restore/remint/import/migrate the protected original to make it
   readable. Local logs/caches/drafts may be written outside the original study.
5. Missing, corrupt, legacy, partially arrived or contradictory evidence is not
   permission to repair, unlock or replace. No idle-time expiry or forced takeover.
6. Finishing a foreign run, quitting its app, a quiet directory, elapsed travel
   time or a successful database integrity check alone is not proof that the
   entire current study generation is locally complete or safe to edit.

**Not a distributed lock:** iCloud/file sync does not carry local locks or
atomically publish all study files. Both Macs can write before evidence arrives;
this plan cannot promise zero conflict in that interval. Old applications,
external writers and noncooperating instances are outside the barrier. Neither
warning nor cartouche is a claim that another Mac has stopped. Preventing this
undetectable interval requires a separately selected ownership/publication
architecture; do not disguise that as a marker-field fix.

The first build package must establish whether the scoped protection is useful
and feasible without that larger architecture. If coherent capture, detecting
relevant curation changes, or safely re-entering editing cannot be established,
stop at the feasibility report rather than ship a convincing but false lock.

## User-visible states

| Observed situation | Existing sidebar cause | Browsing and consequence |
|---|---|---|
| Known editable study | Existing ordinary status; no extra badge | All lenses and ordinary edits |
| A later foreign generation/session is established | Warning + **Changed on another Mac** | Validated earlier report remains visible; lock cartouche after write barrier is established |
| Unfinished analysis attributed to another Mac | Warning + **Started on another Mac** | Last coherent local report if available; no claim the remote process is alive |
| Ownership/activity cannot be established | Warning + **Activity not confirmed** | Same conservative barrier; no guessed owner |
| No coherent report is available here | Existing cannot-open/report-unavailable framework | No fake report, blank successful lens or destructive recovery |
| New facts arrive while locked | Keep honest cause and protection | Stage and validate a whole candidate before any generation switch; drafts retained |

Popover stays the existing 360pt/content-height envelope with its ordinary Copy
control; no new action row. Draft wording, subject to product review:

- Changed: “This study changed on Cassio’s Mac Studio. You’re viewing an earlier
  report. Changes are blocked in this window. You can still browse the report.”
- Foreign attempt: “Analysis started on Cassio’s Mac Studio. Changes are blocked
  in this window. The report shown here may be out of date.”
- Unknown: “This Mac could not confirm where the analysis started. Changes are
  blocked in this window. You can still browse this report.”
- If a draft exists, add “Your unsaved changes are still in this window.” Only
  say this when retention is real; never imply it has saved into the study.

Normal responses are browsing while work completes or arranging to stop work on
the other Mac. Do not advise quitting as proof of safe unlock or narrate sync.
No “waiting for iCloud”, provider progress, download advice, ETA or network guess.
No new Reopen/Check Again/Unlock control in this scope. Re-entry is an engineering
acceptance question below, not a magic button to paper over missing evidence.

### Icon/type and scope details

Native warning glyph follows MessageKind, not a new lock severity. Preserve the
user-chosen leading project icon and the subtitle's shared glyph/text hit region.
Native symbols render through system NSImage/Image configuration; the app does
not bundle/pin the installed SF Symbols 27 catalogue. Existing leading icons
use 16pt regular; subtitle glyphs use caption1 point size regular via
`ProjectCellSpec`. Neither defines a new body overlay automatically.

The cartouche borrows caption type / 0.3em icon-word spacing from
`docs/mockups/codebook-catalogue-install-on-page.html` `.cat-installed` /
`.cat-installed-word` (4456–4460). Floating envelope is new owner-directed work.
A SPA cartouche uses the existing Lucide Icon boundary (new `lock` concept),
including in WKWebView; a native overlay would use SF `lock`, regular, monochrome.
Choose the shared SPA path unless feasibility finds a specific reason against it.
No emoji, private-use symbol font or bespoke icon path. Keep it quiet and passive;
announce the access transition once through the established accessibility path.

Anchor to the main reading viewport, not document end. Reserve reachable space
so the last content/control is not hidden; check both sidebars, minimap/inspector,
video/player overlays, scrolling, narrow views, 200% text and VoiceOver. The mock
1.4s tint is a review value; do not flash on each mount, poll or lens navigation.

Friendly names are display-only `machine_name`, separate from stable machine ID.
Candidate Apple API: SCDynamicStoreCopyComputerName (validate in actual sandbox).
Source Mac publishes its own name; no remote discovery or Apple-account check.
Missing name says “another Mac”, never a prettified DNS hostname. Escape/bound
Unicode names and handle renaming/collisions without changing ownership.

## Implementation packages — internal checkpoints, not partial releases

### A. Establish the source/publication and write-access contract first

Deliver an inventory with **every mutation entry and its commit/publication
boundary**, existing controls and proposed guard. Include startup, request,
background, shutdown, native direct writes and spawned processes. Do not declare
the census complete from route verbs alone. Decide one access-policy owner per
local study and how all of its windows, sidecar, pipeline and separately started
supported CLI writers observe it. The app sandbox/container boundary must be
proved; a file flag only one process can read is not a shared local barrier.
Do not promise protection against arbitrary old/noncooperating versions.

Establish the minimum evidence for: (a) foreign activity; (b) a later curation
change even when no analysis runs; (c) a whole coherent report generation;
(d) returning safely to editable. Existing run completions do not order all
curation edits. Define the manifest/version/source contract and failure behaviour
before choosing fields. Avoid a full remote job/version service in this scope.

**Feasibility gate:** demonstrate capture and generation recognition across the
actual DB, WAL, transcripts/registry/JSON and needed assets. A SQLite backup
protects a DB snapshot; it does not make several independently synced files one
generation. Integrity checks do not prove currency. If this needs a much larger
publication change, report the smallest alternatives and tradeoff before building
B–E. Locking forever is safe preservation, not a completed normal handover design.

### B. Coherent local browsing and conservative bootstrap

Build/retain a last-known-readable report snapshot outside synced storage while
the source is proven safe, before it is needed by a later lock. Use SQLite backup
for DB consistency and an explicit matching asset/source contract from A. Never
blindly copy a DB/WAL bundle during replacement; do not use immutable=1 as a
promise about a source that can still change. Do not derive missing data by
writing back into the protected original.

Decide access before create_app's setup_logging, db_url_for_project mkdir,
init_db/migrations, importer and job startup. Unknown/foreign bootstrap opens a
validated existing snapshot if present; otherwise existing cannot-open behaviour.
Reads in all lenses resolve to the selected generation; a source recording being
materialised is bounded by existing cloud-file policy. Distinguish unavailable
media from an empty session or missing researcher data.

Use real SQLite read-only protection for the browsing DB, bypass writable WAL
pragmas/startup hooks. Local scratch/logging must have explicit destinations and
retention consistent with the existing participant-data policies; no new durable
PII store by accident. Preserve useful curation and drafts. Existing HTML export
is not the shortcut: its read contract omits some lenses/media.

### C. Enforce mutation admission and publication

A typed study access policy has internal checking, editable, locking and locked
states with reason/owner/displayed-generation data. Default uncertain access is
non-writable; checking is not an enabled editing window. Close admission first
when uncertainty appears. Abort/rollback staged DB transactions and block final
file publication using a policy-generation check inside the shared local write
coordination boundary. Do not hold a write lock across LLM/network/long file I/O.

Already-running jobs must stop or be fenced before each commit/publication; a
cancel request is not proof they stopped. Inventory uninterruptible writes and
subprocess termination/drain behaviour. Emit “locked” only when the barrier is
true. Report partial writes or failure honestly and preserve the last coherent
snapshot; do not silently resume editing because stopping work failed.

Guard API mutation dependencies and actual DB/filesystem boundaries, pipeline
run/re-analyse/clean/recovery, native direct writes, importers, identity remint,
watcher reimports, codebook sync, AutoCode/builders, scene/turn-frame/screens
jobs, lazy GET caches, export staging, preference writes and shutdown saves.
MCP tools are currently read-only but their helpers still need inspection.
Requests sent outside the UI must be refused too. An HTTP method block or
SQLAlchemy read-only connection alone is not the whole write barrier.

### D. Surface the state together with enforcement

Expose one server/access-policy answer through existing project API and native
bridge/status model. Native menus, SPA stores/edit affordances, undo/redo,
optimistic requests and background retries obey it. Never push a pending edit
from an older generation into a newer one. Preserve the draft outside the
protected study, and define recovery after process death before promising it.

Keep navigation, searching, text selection/copy, existing playback and inspection.
A view preference normally persisted into the study becomes visit-local/app-local
while locked. Exports remain only if output/staging avoids the protected source
and external side effects are explicitly classified. Do not make all POSTs fail
without checking which requests are read operations; do not allow GET writers.

Install the existing sidebar warning/popover and the passive cartouche only when
backed by C. Collapse repeated access announcements; flash once per access
transition, not remount. English keys first, translations and locale gates before
release. Do not modify the global MessageKind icon or add toolbar/menu chrome.

### E. Safe generation refresh and re-entry

Observe facts quietly. Validate a candidate outside the original; switch all
readers together at a generation boundary. Existing drafts prevent a destructive
refresh; retain them without silently writing or merging them. Re-entry to editing
requires the source/evidence contract proved in A, the correct original/identity,
no unresolved foreign activity and no in-flight old-generation writes. A remote
quit, reconnect, completion line or quiet time alone does not satisfy it.

The implementation must specify a usable transition out of the lock under the
ordinary home→office journey, and preserve rather than overwrite on unsupported
cases. If that cannot be proved within A's minimal contract, bring that limitation
back for a product/architecture decision before implementation claims handover.
No forced takeover, unlock button, duplicate shortcut or inferred sync completion.

## Existing seams to inspect during A (starting census, not proof of coverage)

| Area | Entry points / risk |
|---|---|
| Serve startup and run watcher | server/app.py create_app, startup import/codebook sync, _install_event_watcher reattach/reimport/reapply; logging setup |
| DB | server/db.py directory creation, WAL pragmas, init_db/migrations; importer.py upserts, remint/checkpoint |
| API/jobs | routes/data.py, autocode/codebook_builder, transcript/person updates, screens arrangements, chat history, exports |
| Derived files | scene_strips.py, screen_text_job.py, turn_frames, stale-index purges, stills and media caches |
| Pipeline | cli.py, run_lifecycle.py, utils/output_backup.py, stages and their write helpers |
| Native | ContentView/WindowCommand routing, ProjectIndex/StudyMarker, folder/drop/copy/import paths, preferences and local/server process lifetimes |
| Client | QuotesContext/UndoStore/optimistic queues, api helpers, lens caches, existing isExportMode guards (reference only), accessibility announce/AnnounceRegion |

## Acceptance and review evidence required before release

- **Original untouched under lock:** byte snapshots + write tracing across every
  inventoried mutation path; also rejected external API/CLI commands, all lenses,
  reconnect, shutdown, lazy caches, missing/corrupt identity and old markers.
- **No late writer:** deterministic barriers for job admitted before lock,
  transaction/file publish racing lock, uninterruptible subprocess and rollback
  failure. Assert DB/files, not only a 403/409 response or cancellation flag.
- **Partial-sync schedule:** delay/reorder/remove marker, terminus, DB/WAL,
  transcripts/registry/assets independently; offline edits then reconnect; PID
  collision; local crash; app/CLI/two-window state disagreement. Use normal
  temp-file tests, real DBs and controlled operations, not a real iCloud account
  as the only proof. A two-Mac manual check supplements the deterministic tests.
- **Coherent reads:** every lens stays on one generation; media/path mapping,
  curation, pagination/search and exports never silently mix old/new sources.
  No snapshot or failed bounded read uses the existing unavailable framework.
- **Drafts/undo:** rejected save creates no phantom undo, no retry replay across
  generations; draft survives lock and process restart where promised; no silent
  discard on recheck, refresh, close or interrupted recovery.
- **Re-entry:** representative completed home→office handover passes A's evidence
  contract; unknown/old/lost-origin/incomplete cases do not auto-unlock. Capture
  the supported and unsupported cases as an executable table.
- **Native/browser UX:** glyph/subtitle contract and priority, friendly Unicode/
  missing/long/renamed/colliding names, cartouche placement across all lenses and
  sidebars, keyboard/VoiceOver, 200% text, reduce motion, no duplicate offer.
- **Cost:** avoid full-tree hash/poll or per-keystroke snapshot; measure startup,
  snapshot refresh, long-session memory/disk/PII retention and first-load bundle
  against existing gates. Use targeted meaningful tests, not brittle source pins.

Run relevant Python/frontend/native suites and existing locale/bundle gates for
actual changes. Human native/Mac/real-provider checks cover what those tests do
not. No full suite is claimed for this design-only pass.

## Review continuity

Usual-suspects findings live in `docs/private/reviews/study-read-only.md`;
owner dispositions remain there. Source history and previous ruling summaries
are in TODO / 100days. First pass for this doc: no existing review log.

### Review status — partial, 26 Oct

Plan SHA-256 at review: `dde7ca90515b9f4d3a5cabe8cef48d5cbf8ed7a7a253673dad303000c4a2e054`.
Two usual-suspects lanes completed (code and security). Silent-failure lane hit
an account usage limit; remaining lanes, independent compose-check and William
have not run. Five findings/questions are recorded open in the review log:
read-epoch fencing, legacy bootstrap, current privacy versus stale content,
quiescence/capture ordering and cache/draft retention. They have not been silently
applied or marked resolved. This is not a complete usual-suspects sign-off.

### Review continuation completed — 26 Oct

The previously interrupted usual-suspects pass is now complete: ten primary
lanes, independent compose-check and William Mode A. Findings 1–5 were carried,
6–13 are new; all remain open for owner triage in the existing review log. The
substantive plan was not silently amended or marked implementation-ready.

The review requires generation continuity for both reads and delayed editing
intents; usable legacy bootstrap; current privacy/observer-authority health;
proper capture ordering; draft recovery/retention/focus; and integration with
existing native/browser capabilities and accessibility. Performance/testing/i18n
introduced no additional speculative subsystem or test-suite requirement.
William grouped the work into capture boundary, baseline/generation/admission,
policy exposure, draft lifecycle and existing-UI integration. First prove the
minimal source/publication, legacy baseline and usable re-entry contract before
building the rest. Full annotations and candidate (unapplied) amendments are in
the review directory. No production code changed or tests run in this pass.


## 27 Oct owner scope clarification and POC evidence

V1 explicitly targets a single person handing a study between Macs, with no new
human work on the previous Mac after handover. Do not expand the initial work to
concurrent editing, merging or global distributed ownership. Existing broader
scenarios remain useful future reference, not mandatory v1 scope. Relevant old
background writers and delayed cloud delivery still need safety guards.

The managed codex/study-access-poc worktree's experiments/study-access-poc/HANDOVER.md
records the iterative tests: 24 forward + 24 return schedules, actual database
edits retained with private working storage, final checkpoint admission, and native
Foundation status/coordination observations on all three provider folders. This
is prototype evidence only, not an implemented or approved production design.
A synced-DB delayed-replacement fault still loses an edit with no new home work.
An unseen newer completion after office edits requires retaining those edits and
a protected pause; no automatic merge or routine duplicate path is proposed.
Producer quiescence, restart durability, identity, all actual writers and signed
two-Mac behaviour remain unproved. The existing read-only/status/cartouche design
and review ledger are not marked complete by these experiments.

### Cloud policy reaffirmed by owner, 27 Oct

The handover/done-file work is provider-neutral. Existing cloud-file policy is
settled in design-cloud-files.md; it is not reopened by the multi-Mac scenario.
The POC's native provider status/coordination probes are observations only; the
recommendation to use them as a new production integration was retracted.
Reuse the existing bounded read path for the done file and required report files.
Validate Bristlenose's own generation/completion/content facts; do not create
cloud states, cloud narration, upload-complete gates or provider-specific behaviour.
The cloud-specific concern here is file arrival/replacement/readability, tested
without making Bristlenose responsible for the sync service.


27 Oct follow-on: saved local curation can now be retained as a separate immutable
read generation after a proven quiet live actor fence. No busy/failed/crashed
inference grants it; initial fallback and working data remain intact. See
[implementation evidence](design-study-read-only-plan.md#quiet-live-fence-preserve-saved-local-curation--27-october).
Runtime handover/adoption/all-lens policy/UI/re-entry remain activation gates.
