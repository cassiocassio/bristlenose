---
status: proposed
last-trued: 2026-10-27
---

# Durable Signal Snapshots and Refresh Lifecycle

## Decision in one sentence

Signals are a durable, project-scoped analysis artifact: a researcher always
reads the last completed snapshot, while a separate refresh service recomputes
only the affected analysis and narrative after evidence changes.

This replaces the current page-load elaboration stream. It does **not** change
what a signal means, its inputs, or the navigation hierarchy.

## Why this is needed

Today `GET /signals/codebooks` calculates cards live, then the Signals page
opens an SSE elaboration request. `generate_elaborations()` also returns before
reading `ElaborationCache` when no remote LLM is configured. Consequently a
saved signal title, claim and evidence summary can disappear merely because the
provider is unavailable. That is the wrong ownership boundary: the LLM writes
an analysis artifact; opening a lens should only read it.

The present cache is useful raw material, but it is not a snapshot. It has no
coherent card-set version, no recorded input state, and no lifecycle owner.

## Reader contract

The client receives a single `SignalSnapshot` response, never a calculation
plus a second request that gradually changes its prose.

- A `complete` snapshot is internally coherent: cards, metrics, quoted evidence,
  participant contribution cells, title, claim and evidence summary were made
  from one input revision.
- The latest complete snapshot remains readable without an LLM, without the
  internet, and while a successor is calculating or has failed.
- Snapshot metadata records whether the current project inputs have changed
  since it was made. The first delivery may keep that state invisible in the
  lens; the API and model retain it so a quiet freshness treatment can be added
  later without another migration.
- A project with no completed snapshot gets an explicit empty/calculating
  state. It must not substitute a Section or Theme name as invented finding
  text.
- A legacy project which has signal evidence but predates snapshots repairs
  itself when its desktop sidecar opens with a cloud model available. The
  sidecar writes the first snapshot in the background; the open lens rereads
  only while that specific repair is pending. This is deliberately invisible
  operational work, not a "Refresh signals" task for the researcher.

## Terms and card anatomy

Each persisted card preserves the visual hierarchy already agreed for the
Signals lens:

1. **Signal title** — concise, evidence-earned finding name (`signal_name`).
2. **Signal claim** — the main interpretive sentence.
3. **Evidence summary** — a lighter synthesis of the supporting quotes.
4. **Evidence quotes** — selected source excerpts, timecodes, tags, intensity
   and contributor distribution.

The hero chip is classification/score and the disclosure for its chart; it is
not a substitute title. The evidence summary and the claim continue to be
stored in the existing `elaboration` output format (`claim || summary`) at the
boundary, but are persisted as separate fields in a new snapshot so consumers
need not parse presentation punctuation.

## Architecture

```
project evidence + decisions
          │
          ▼
Signal invalidation service ──► per-project refresh coordinator
                                      │ (coalesce, scope, retry)
                                      ▼
                          snapshot builder (deterministic)
                                      │
                changed card evidence fingerprints only
                                      ▼
                         narrative service (remote LLM)
                                      │
                                      ▼
                     atomically publish SignalSnapshot
                                      │
                                      ▼
                         Signals reader endpoint / UI
```

### 1. Canonical active-analysis resolver

Create one small service that resolves the active framework/codebook groups for
a project. It must apply both `ProjectCodebookGroup` ordering and
`ProjectFrameworkState.enabled`. Every signals, autocode and lifecycle caller
uses this resolver.

This corrects the present split-brain behaviour: the Signals route currently
uses project group links but does not apply framework enable/disable state.
Framework-backed groups, including Sentiment where it is installed as a
framework, participate in this resolver. Custom groups remain deterministic
signal cards but have `narrative_not_applicable` until custom tags carry the
definitions required for grounded interpretation; they never receive invented
title/claim text just to satisfy the layout.

### 2. Deterministic snapshot builder

Extract the calculation presently embedded in `routes/signals.py` into a
server service with no HTTP or LLM dependency. Given a project and an active
analysis set, it returns the complete ordered card graph: locations, groups,
metrics, quote identifiers/excerpts, tags, and contribution strengths.

The builder assigns two fingerprints:

- **project input fingerprint** — active codebooks, analysis-eligible quotes,
  accepted/proposed tag decisions, relevant grouping and metric algorithm
  version. It says whether a snapshot reflects the project as a whole.
- **card evidence fingerprint** — the stable card identity plus only the
  evidence and interpretation inputs for that card. It decides whether that
  card's narrative can be reused.

Every signal-relevant mutation increments a transactionally-persisted project
`analysis_revision`; the snapshot records the revision it observed. The mutation
hot path does not synchronously reread all project evidence to hash it. Scoped
candidate selection is an optimisation, while card fingerprints are the
correctness check for narrative reuse. A reconciliation command can later run a
canonical full-input audit and report divergence.

### 3. Durable snapshot store

Add a migration with a snapshot header and card rows. Card identity uses stable
Section/Theme and group IDs plus source kind; labels are stored display data,
not keys. Rename retains identity; a structural move changes its location
identity and fingerprint.

| Record | Owns | Important fields |
|---|---|---|
| `SignalSnapshot` | one coherent published read model | project id, observed analysis revision, engine version, computed/published time, `complete`/`candidate_partial` status, refresh reason |
| `SignalCardSnapshot` | one card in that snapshot | stable card key, location/group refs and display text, metrics, evidence quote refs, contribution distribution, title, claim, evidence summary, validated evidence assertions, card fingerprint |
| `SignalRefreshAttempt` | operational history, not reader state | requested/started/finished time, scope/reason, outcome, retryability, correlation id, database lease/owner token |

Snapshots are immutable after publication. Retain the latest complete snapshot,
its immediate predecessor, and partial/attempt records for a bounded age; prune
the rest transactionally. This is a safe published read model, not an
unbounded historical-analysis product. Quote redaction, hard removal and
project deletion take a destructive-evidence path: affected snapshot excerpts
are tombstoned before the reader can expose them. The migration uses foreign
keys/cascades or a tested deletion service; retention must be enforceable, not
an operational promise. Export/import carries the latest complete snapshot
only, pending an explicit historical-analysis feature.

A refresh writes a successor in a
transaction and switches the project's `latest_complete_snapshot_id` only after
all deterministic cards and their narrative outcomes are present. Failed or
cancelled work never replaces the last complete snapshot.

The existing `ElaborationCache` remains a reusable narrative memo, but its
lookup must happen before provider/key availability checks. Its content hash is
expanded to include the template/codebook version, stable card identity,
location/group inputs, prompt version and narrative model policy. The completed
narrative is copied into the snapshot: cache eviction or provider loss cannot
change historical reader output.

Existing cache rows are legacy input version zero. Backfill can reuse one only
when the expanded fingerprint can be reconstructed and matches; otherwise it
seeds deterministic data as `candidate_partial`, never old prose falsely
asserted as current.

### 4. Refresh coordinator

Introduce a per-project, single-flight background coordinator. It accepts
`mark_signals_dirty(project_id, reason, scope)` calls, debounces bursts, merges
their scope and starts only when the originating data work has committed.

It has these rules:

- Never run an LLM in a request that renders the Signals lens.
- Do the deterministic build first. Reuse narrative for cards whose evidence
  fingerprint matches; send only new/changed cards to the LLM.
- If the provider is unavailable, retain the last complete reader snapshot and
  record a retryable `candidate_partial` calculation. It may contain reusable
  narratives where the card fingerprint matches; changed cards are explicitly
  `narrative_pending`, never stale prose presented as current.
- Require a per-card result manifest. Timeout/no-key, malformed output and an
  LLM response that omits a requested card have distinct outcomes; only
  transient provider failures retry automatically.
- Automatic external generation requires a persisted cloud-signal-refresh
  permission for the selected provider. With no consent, or a local provider,
  the calculation stays local and becomes `candidate_partial`.
- Bound concurrency across projects and record failures/backoff. A later input
  event supersedes an obsolete queued run.
- Refreshes started by a run wait for framework re-application to finish; they
  do not race it.

The coordinator is deliberately a service, not a frontend event listener or
route-local background task. Dirty state is written in the same transaction as
the evidence mutation (an outbox row plus the project revision), then drained
after commit. A worker claims work with a database lease/owner token and may
publish only if it still owns the current revision; a restart, second process
or late worker cannot overwrite newer evidence. Process restart leaves the last
snapshot intact and can resume durable dirty work.

### 5. Lifecycle event map

| Event | When to mark dirty | Initial scope | Why |
|---|---|---|---|
| Codebook run/import completes | after `reapply_active_frameworks` completes | new/changed sessions × active groups | new quotes and tags are now stable |
| Framework enabled/disabled or installed/uninstalled | after the database transaction | framework/project | changes eligible analytical vocabulary |
| Tag proposal accepted or denied; manual tag change | after decision commit | quote × group(s) containing its tag | evidence and strength changed |
| Quote hidden/unhidden, edited, or removed | after commit | quote × all active groups | alters eligible evidence |
| Section/theme or grouping edit | after commit | location/project | cards may move/merge/split |
| Signal metric/template/prompt version change | at deploy/config migration | project | semantic output contract changed |

These are domain events emitted by shared mutation services, not ad-hoc route
calls. Opening the Signals page is intentionally absent from this table. A histogram
slice is also absent: it is a reader filter. Accepting or denying a proposal
from that slice is a real evidence change and is present above.

Scopes select *candidate* cards and the background builder verifies their
versioned card fingerprints before reuse. A navigation-confusion tag therefore
does not buy a price-positioning LLM call. The analysis revision means an
obsolete scoped refresh cannot silently publish after later data changes.

### 6. Thin read APIs and frontend

Replace the route pair's calculate-then-stream contract with:

- `GET /projects/{id}/signals/snapshot` — latest complete snapshot and freshness
  metadata; read-only and provider-independent.
- `POST`/internal lifecycle entrypoint for dirty notifications — server-only;
  no public client calls.

`SignalsPage` adapts a snapshot into existing card components and compound
Section/Theme navigation. It removes `streamElaborations()` as a page-load
effect. The new card presentation work stays cosmetic; it receives the same
logical data with complete title/claim/evidence fields when available.

The endpoint is classified in the export contract and export serialises the
latest complete snapshot. An exported report therefore reads the same
last-computed signals offline and never depends on localhost or a provider.

## Component plans

### A. Models and migration

Create the three records above, immutable snapshot/card writes, indexes on
project + publication time and snapshot + card key, `analysis_revision` +
outbox/lease fields, and a project pointer to the latest complete snapshot.
Add a one-time backfill that creates no fake prose:
it can seed a snapshot only when all deterministic source data is available and
reuse valid cached narratives.

### B. Signal analysis service

Move pure aggregation, ranking, quote selection and contribution strength from
`routes/signals.py` into `server/signal_snapshot.py`. Keep a compatibility
adapter for existing route consumers while the read endpoint moves. Unit-test
the service without FastAPI, SSE or an LLM.

### C. Narrative service and cache

Refactor `server/elaboration.py` behind `get_or_generate_narratives()`. Read
the cache first, then decide if an external provider is needed. Persist title,
claim and evidence summary separately, retain the wire-format adapter during
migration, and never request a provider for an unchanged card.
All transcript- and tag-derived prompt values continue to pass exclusively
through `wrap_untrusted`; provider/model/reason is recorded without quote text.

### D. Refresh/invalidation service

Add `server/signal_refresh.py`: typed reasons/scopes, a coalescing task
registry, bounded retries and a durable attempt record. Wire it only at data
transaction boundaries listed above. Make reapply completion an awaited
lifecycle boundary before it marks signal data ready to refresh.

### E. Routes and UI

Make the snapshot route a simple reader. Migrate `SignalsPage` and its tests
off SSE elaboration. Keep the existing Section/Theme navigator's selection,
scroll and focus behaviour. The presentation adapter has explicit `complete`,
`first_calculation` and `narrative_pending` states; no null title/claim skeleton
may masquerade as content. First calculation/retry states have concise,
truthful accessible status text even if complete-snapshot freshness stays
visually quiet. Repair nested interactive controls while touching the card:
only actual controls are focusable; evidence inspection becomes an explicit
control or noninteractive selection treatment.

### F. Observability, recovery and deletion

Log refresh reason, scope, cache reuse/generation counts, duration and
provider failures without quote text. Durable attempt detail is limited to a
controlled failure kind, status class, retryability, timestamp and correlation
id; full exceptions stay in protected local logs, never in reader/admin/export
payloads. Add an admin/dev inspect view for the latest snapshot and attempt
history, and tests for deletion, redaction and export classification.

## Invariants and tests

1. Disabling a framework removes it from subsequent snapshots and all active
analysis callers agree on the same resolver result.
2. With LLM/network unavailable, the reader returns the last complete snapshot
unchanged; a page request does not initiate generation.
3. A changed card cannot inherit an old narrative unless its evidence
fingerprint matches exactly.
4. A failed refresh cannot replace a complete snapshot.
5. A run's snapshot cannot publish before framework re-application completes.
6. A single tag decision generates a narrow candidate scope and only changed
cards are sent to the provider.
7. Snapshot response order and card IDs remain stable enough for compound-page
navigation, focus and quote/evidence linking.
8. Provider, cache and refresh errors are observable and testable; none are
silently swallowed.
9. Duplicate dirty events, a mutation during an LLM call, a disable while
   queued, reapply failure, worker restart mid-write and provider recovery
   cannot publish an obsolete snapshot or leave an unreported state.

Use service-level fixtures for deterministic output, fake provider calls for
reuse/selective-generation assertions, migration tests, lifecycle integration
tests around run/reapply and framework toggles, and a controllable refresh
clock/task gate for those interleavings. Avoid browser tests for the
coordinator; retain one frontend contract test proving an offline complete
snapshot renders without SSE.

## Deliberately deferred

- The visual design for the quiet “evidence changed since computed” indication.
- A user-visible regenerate control and its cost/confirmation policy.
- Whether failed changed narratives are hidden, labelled pending, or retain
  previous wording in a compare view. The persisted state supports all three;
  the reader must never misrepresent stale wording as current.
- A project-wide recomputation UI/progress surface.

## Implementation sequence

1. Add the revision/outbox, lease, consent and snapshot schema. Move both
   Signals and autocode to the shared active resolver and pin the existing
   framework-disable/custom-group contracts with tests.
2. Extract the pure builder, version the cache identity before any backfill,
   then refactor cache-first narrative lookup with the existing prompt boundary.
3. Build the leased coordinator with a small per-card result manifest, consent
   gate and excerpt tombstoning/redaction path.
4. Wire import/run, framework, tag, quote and grouping mutation services to the
   durable invalidation event; add interleaving tests for each race boundary.
5. Share one snapshot serializer between reader endpoint and export payload;
   backfill only reconstructable cache entries and keep a narrow compatibility
   adapter until every eligible project has a complete snapshot or a truthful
   first-calculation state.
6. Move `SignalsPage` to snapshot reads; remove its elaboration stream only
   after the adapter, export and first-calculation paths are proven, while
   preserving compound navigation and card design.
7. Add operational inspection, reconciliation/backfill command and only then
   decide on a subtle freshness affordance.

The redaction guarantee applies to data in this app's live database, snapshots
and future exports. An already-downloaded or shared HTML export is a deliberate
copy outside the app's revocation boundary; the export flow should say so where
it already explains that copies may be shared.

## Key choices for the product owner

1. **Snapshot publication when the LLM is unavailable:** hold the old complete
   reader snapshot while recording a retryable `candidate_partial`
   calculation (recommended), or surface fresh metrics with
   `narrative_pending` cards.
2. **Narrative policy:** keep the current high-quality external provider for
   title/claim/evidence writing (recommended); deterministic signal maths stays
   local and offline.
3. **Freshness visibility:** retain the state now; decide later whether readers
   see it by default, only in the hero disclosure, or only in diagnostics.
