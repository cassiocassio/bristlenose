---
status: partial
last-trued: 2026-08-31
trued-against: HEAD@main 8fee4ead on 2026-08-31
---

> **Truing status:** Partial — §1–4 and §6 are current. **§5 and §8 drifted with
> the v1 deletion on 31 Aug 2026** (`baa1aa0e`) and are corrected inline; the
> previous banner asserted §8 was current, which is the section the switch moved
> out from under. §7's "described (target)" deltas and §4a's deferred-fallback
> note are retained as the design record but have partly shipped since capture;
> see the dated notes inline and the changelog below.

## Changelog

- _2026-10-22_ — **per-session stamps replace the watermark** (RE#66, decisions
  #60–#67, owner). A session counts as coded by a codebook only when every one of
  its quotes was sent in a batch that answered (`autocode_session_stamps`,
  migration 022, backfilled from the old watermark so an upgraded project's next
  re-apply sends what it would have sent). A partial failure, at a first apply, a
  catch-up or a run's re-apply, moved `completed_at` past the sessions it never
  coded, and they were never coded by that codebook again; now they stay owed and
  the next run or re-enable codes them. `completed_at` now only means "applied at
  least once". What falls out of it: a stopped catch-up keeps the batches that
  answered (#60); a run's re-apply that leaves nothing owed clears a failed
  catch-up's error (#61); a run's re-apply reads the switch before each codebook
  and each batch (#62); a catch-up the serve's restart cut off is `failed`, not
  `completed` at zero (#63); Apply refuses a job with `completed_at`, whatever its
  status (#64); a Stop on a first apply leaves `completed_at` empty, so a stopped
  first apply is not maintained (#65); and the run's re-apply runs on its own
  task, so the event watcher never waits on it, and a codebook with a live
  catch-up holds only itself (#67). §4a rewritten.
- _2026-10-20_ — the on-enable catch-up's chip lost its producer with v1
  (`baa1aa0e`, 31 Aug): `CodebookPanel` added it, and the v2 navigator that took
  over the switch read `catchUp` from `PUT /framework-states` and dropped it, so
  from 0.29.0 re-enabling a codebook with new sessions spent on the LLM with no
  chip, and its tags arrived unannounced. `CodebookV2Sidebar` is the producer
  again (one chip per run, the codebook's last catch-up chip removed), and a
  reload restores a running catch-up as a catch-up chip
  (`ActivityStore.rehydrateActivityJobs`: a running job with `completed_at` set).
  Two server fixes the chip made visible: the re-apply now advances
  `processed_quotes` by the batches that answered (it grew `total_quotes` alone,
  so every catch-up that worked read as "some batches failed"), and a re-apply
  where every batch fails is a failure that leaves `completed_at` where it was,
  so the next catch-up codes those sessions (it said "completed" and skipped
  them for good). A partial failure still advances the watermark; that is the
  deferred per-session stamp below. Register: R12.
  Then two more (wave 5): switching a codebook off and on while its catch-up is
  still coding no longer starts a second catch-up on the same job
  (`_start_catch_ups` skips a framework whose catch-up task is still live, so
  the running one's chip stands; it asks the task, not the row, because a row
  can say `running` with no task behind it until a restart); and a failed catch-up records `failure_kind`, as
  `run_autocode_job` does, so its chip says which failure it was (out of
  credit, rate limited…) instead of the generic "Tagging failed.".
  And four more (wave 6). The chip judges a catch-up by its own counts,
  `catch_up_total` / `catch_up_processed` on the job (migration 020; zeroed when
  `_start_catch_ups` starts one, written when it completes): the cumulative
  `processed_quotes < total_quotes` keeps an earlier apply's shortfall for good,
  so once any apply had come up short every later catch-up that worked said
  "some batches failed". A run that finishes while a catch-up codes no longer
  re-applies the same codebook alongside it: both re-apply paths register their
  task in one registry (`autocode._REAPPLY_IN_FLIGHT`, which `routes/data.py`'s
  `_CATCH_UP_IN_FLIGHT` names), the run's re-apply waits for a live catch-up,
  and no catch-up starts over a run's (the loser of the race hit the
  `(job, quote)` unique constraint and rolled back). A catch-up that works
  clears the last failed one's `failure_kind` and `error_message`. And a Stop
  on a catch-up is honoured: it was never read, so the catch-up went on spending,
  wrote its tags, and wrote `completed` over the Stop. It now checks before each
  batch (as `run_autocode_job` does), keeps nothing it coded (its final write is
  one `UPDATE` a cancelled row refuses), and the Stop route sets `completed_at`
  only on a job that has none, so a stopped catch-up leaves the watermark where
  it was and the next catch-up or run codes those sessions. A catch-up that
  fails after a Stop leaves the job `cancelled` too.
- _2026-08-31_ — trued against the v1 deletion (`baa1aa0e`) and the A5 defect.
  **New §4b** records that `PUT /framework-states` is a full replacement, that
  absence means enabled, and that the two together make a partial body both a
  silent wipe and an unrequested spend — the omission the defect rode through.
  **§8's switch bullet inverted:** the control moved onto the navigator's rows and
  the status dot is gone, so the "sidebar is never a control" rule it stated is
  superseded; the v1 text is preserved as a blockquote because its reasoning is
  what a future move of that control should be weighed against. §4a's
  `source="human"` clause corrected — the guard is a bare pair-existence check with
  no source predicate. The header's "nothing here is built yet" and the truing
  banner's "§8 is current" were both false and are replaced. Register: A5.
- _2026-08-21_ — trued up: §2's **Tag provenance** glossary row named two
  `QuoteTag.source` values (`human` | `autocode`); it ships **four**. Added
  `pipeline` and `codebook-builder`, and a note under §3a that both arrive by
  paths the tag FSM does not model. The two-value model is what made the
  dashboard's "user tags" stat count machine sentiment tags as the
  researcher's: `== "human"` and `!= "autocode"` are only equivalent if
  `pipeline` does not exist. Anchors: `bristlenose/server/importer.py:1397`,
  `bristlenose/server/routes/codebook_builder.py:435`,
  `bristlenose/server/models.py:490`. No commit anchor: this landed inside a
  concurrently-running session's commit and had migrated between two of them
  within a minute, so any SHA here would be stale on arrival — use
  `git log -S'QuoteTag.source != "human"'` to find it.
- _2026-07-26_ — trued up: noted in §4a that the crash-orphaned-job edge (a job
  stranded `running`/`pending` by a serve crash) is now caught by startup
  reconciliation, distinct from the still-deferred per-session "coded" stamp;
  flagged that §7's A→C "off means off" + catch-up deltas shipped same-day.
  Anchors: `bristlenose/server/autocode.py` `reconcile_orphaned_jobs`,
  commit subjects "codebook: harden catch-up against crash-orphaning +
  false-success", "surface the on-enable catch-up as an activity chip",
  "true the 'disable is view-only' framing out of code + docs".
- _2026-07-26_ — initial draft (design capture).

# Codebook & tag state model — formal spec

**Status:** design capture, 26 Jul 2026. The "measure" before we cut. Consolidates a
long working session that untangled three controls that had been conflated. Companion
to [design-codebook-library.md](design-codebook-library.md) (the Library UI redesign)
and [design-autocode.md](design-autocode.md).

**Status, 31 Aug 2026:** this was written as a spec to validate before building,
and said so — *"nothing here is built yet beyond what §7 marks as current."* That
has been false since 26 Jul: §3b, §4 and §5 shipped, and the code now cites this
document as the authority (`bristlenose/server/autocode.py`, `reapply_active_frameworks`,
names §8). Read it as the behavioural spec of a shipped system.

Sections: 1 language · 2 tiers · 3 state machines · 4 data model + lifecycles ·
5 UX states & visibilities · 6 retention/cost gradient · 7 the three-way delta ·
8 settled vs open.

---

## 1. Language definitions

Precise words, because loose ones (mixing "hide" with "disable") caused the churn.

| Term | Definition |
|---|---|
| **Project codebook** (the *floor*) | The researcher's own hand-made tags (`framework_id IS NULL`). Always present — the minimum. Named by the project ("project-ikea2 tags"). |
| **Auto-generated codebook** | Sentiment + any framework (garrett, norman, …). Machine-provided, tag-producing, can drown you. *(A future codebook-lab is a disposable experiment for later — out of scope here.)* |
| **Add / Remove** | *Install axis.* Add = put a codebook into this project (from the Library). Remove = uninstall it — "I'm **done**." |
| **Enable / Disable** | *On/off axis*, auto-generated codebooks only. Disable = turn the whole codebook off but keep its results. "Set aside, might return." |
| **Apply (AutoCode)** | Spend the LLM to tag quotes with a codebook. The one deliberate cost. |
| **Hide / Show** (the *eye*) | *View axis*, per group, any codebook incl. the floor. Tactical, in-the-moment declutter. Reversible in a click; **auto-unhides** when you reach for a hidden tag. |
| **Tag provenance** | How a tag was applied — `QuoteTag.source`, **four** values: `human` (you typed or picked it; the column default), `autocode` (you accepted a suggestion), `pipeline` (the sentiment auto-import, one tag per quote carrying a sentiment), `codebook-builder` (the dynamic-codebook apply pass). Only `human` is researcher effort; the other three are machine-authored. |
| **Proposal disposition** | An autocode suggestion's state: `pending` / `accepted` / `denied`. Denied is retained (telemetry), just not shown. |

**The organising sentence:** *disable every auto-generated codebook and you're back to
your own private floor — the tags you can only hide/show. That floor is always there.*

---

## 2. The two tiers

**The dividing line is *who made the work, and how deliberately*:**

- **Hand-coding is expensive and deliberate** → protected. You can hide it, but you
  can't disable or remove your own labour.
- **Autocoding is cheap and profligate** → toggleable. Every machine-made codebook is
  a relief valve away, because piling them on is the whole overload risk.

*The asymmetry, concretely:* writing 20 good tags by hand might take an hour, and
applying them across 5 sessions can take **two days** — that's not something you
toggle off. Meanwhile, adding three codebooks and applying them to 20 sessions takes
**~20 minutes** and lands you with **~2,000 tags** to think about. So disable has to
exist — *and* it must keep the LLM's results, so turning the noise off never means
re-paying to bring it back.

1. **Floor — the project codebook (your hand-made tags).** Permanent. **Hide/show
   only.** Never enable/disable, never remove — it's your deliberate work.
2. **Toggleable — *every* auto-generated codebook.** The **Bristlenose UXR codebook**
   (the "house wine" — the recommended default pour), **sentiment**, and every
   framework (garrett/norman/… — "particular growers", yablonski — "a guest-edited
   encyclopedia"). All the same lifecycle: **Add/Remove · Enable/Disable · Apply**,
   plus hide/show on their groups.
   - uxr being the *default* only means it's the recommended pick from the menu (the
     **Add** axis) — not that it's permanent. It's toggleable like the rest, precisely
     because it autocodes.
   - *Sentiment* is pipeline-pre-tagged (no manual **Apply**) but is enable/disable-able
     and hide-able.

*(Resolved Q-A: uxr is toggleable, not floor.)*

---

## 3. State machines

### 3a. Tag instance (the only true FSM) — per (quote, tag)

```
                    ┌─ you type / pick it ─────▶ QuoteTag(source="human")      ← manual
(no tag on quote) ──┤
                    └─ autocode proposes ──────▶ ProposedTag("pending")
                                                     ├─ accept ─▶ QuoteTag(source="autocode")
                                                     └─ deny ───▶ ProposedTag("denied")   ← kept, hidden, telemetry
```

Provenance (`source`) is independent of the tag's *origin* (its group's `framework_id`).
"I hand-applied a Garrett tag" (`human`) ≠ "autocode applied a Garrett tag" (`autocode`).

**Two machine sources bypass this FSM entirely** — neither passes through
`ProposedTag`, so neither appears above: the sentiment auto-import writes
`source="pipeline"` on import (`importer.py:1397`, one tag per quote carrying a
sentiment) and the dynamic codebook builder writes `source="codebook-builder"`
on apply (`routes/codebook_builder.py:435`). Any code asking "did the researcher
do this?" must test `source == "human"` — **not** `source != "autocode"`, which
silently counts both of these as human work.

### 3b. Codebook lifecycle (toggleable tier) — per (project, codebook)

```
      Library                     ┌───────────────── hide/show groups (orthogonal, view only) ─────────────────┐
        │ Add                     │                                                                             │
        ▼                         ▼                                                                             ▼
   ┌─────────┐   Apply    ┌──────────────┐   Disable    ┌───────────────┐   Enable (catch-up delta)   ┌──────────────┐
   │ Added,  │──────────▶ │ Enabled       │ ───────────▶ │ Disabled       │ ──────────────────────────▶ │ Enabled       │
   │ not     │            │ (live; new    │ ◀─────────── │ (off; not      │                             │ (live again)  │
   │ applied │            │ sessions code)│              │ coding; kept)  │                             └──────────────┘
   └─────────┘            └──────┬───────┘              └───────┬────────┘
        ▲                        │ Remove                       │ Remove
        │ Add (re-install)       ▼                              ▼
        │                 ┌──────────────────────────────────────────┐
        └──────────────── │ Removed — no promise on accept/deny work  │
                          └──────────────────────────────────────────┘
```

The floor codebook has **no** version of this machine — only the hide/show overlay.

---

## 4. Data model & lifecycles

| Concept | Table / field | Grain |
|---|---|---|
| Installed? | `ProjectCodebookGroup` link | per (project, group) |
| Enabled? | `ProjectFrameworkState.enabled` | per (project, framework) |
| Group hidden? | `hidden_tag_groups.group_name` | per (project, group) |
| Applied tag | `QuoteTag(source)` | per (quote, tag) |
| Proposal | `ProposedTag(status, confidence, rationale)` | per (job, quote) |
| Apply job + stored cutoff/prompt | `AutoCodeJob(applied_*_threshold, prompt_version, completed_at)` | per (project, framework) |

**Lifecycle event → data change:**

| Event | What changes |
|---|---|
| Add codebook | insert `ProjectCodebookGroup` links (+ tag defs) |
| Apply | `AutoCodeJob` runs → `ProposedTag`s → accepted become `QuoteTag(autocode)`; cutoff/prompt stamped |
| Add sessions + re-run | *(described)* if codebook **enabled**: delta re-apply codes only the sessions it owes (no stamp, §4a), non-clobbering |
| Disable | set `enabled=false` — *(described)* stops the delta re-apply; results retained |
| Enable | set `enabled=true` — *(described)* one catch-up delta for the sessions owed (those added while off, and any a failed pass left) |
| Hide group | insert `hidden_tag_groups` |
| Remove | drop `ProjectCodebookGroup` links; **no promise** to keep `QuoteTag`/`ProposedTag` |

### 4b. Endpoint semantics — the switch is written by REPLACEMENT

Added 31 Aug 2026, after a defect shipped through the gap where this belonged.

`PUT /projects/{id}/framework-states` **replaces the entire stored map.**
`put_framework_states` deletes every `ProjectFrameworkState` row for the project
and re-inserts only what the request body carried. Three consequences, and they
compound:

1. **A partial body is a valid request and a silent wipe.** Sending only the
   framework whose switch moved deletes every other framework's row.
2. **Absence means enabled.** So the wiped rows do not read as missing — they
   read as *on*. There is no state that means "I did not mention this one."
3. **Absence is therefore indistinguishable from a deliberate re-enable**, and
   §4a's catch-up fires on it. A partial body does not merely lose state; it
   spends money, because each wiped row is handed to `_start_catch_ups`.

**So every client must send the whole disabled set on every write.** v1 did
(`setFrameworkDisabled`). The v2 navigator did not, and (2) and (3) together
turned a one-line payload bug into "only one codebook can be off at a time"
plus unrequested AutoCode runs — register row A5, shipped in 0.29.0, fixed in
0.29.1.

**A client cannot derive that set from `SidebarStore.disabledFrameworks`**,
which is hydrated once per session from `TagSidebar`'s mount alone and is empty
on a deep link straight to the codebook lens. The surface that owns the switch
owns the authoritative set, and mirrors it into the store rather than reading
its payload out of it.

### 4a. How re-enable knows what to code: per-session stamps

**A session is coded by a codebook when it carries that codebook's stamp**
(`autocode_session_stamps`: one row per job and session, migration 022). A pass,
whether the first apply, a catch-up or a run's re-apply, stamps a session when every quote it
sent from that session was in a batch that answered, in the same transaction as
the proposals. A session with at least one quote and no stamp is **owed**
(`autocode.owed_sessions`), and the next re-apply sends its quotes that have no
proposal on the job yet. A batch that failed, or that a Stop or a switch-off never
sent, leaves its sessions owed; a session with no quotes is never owed, so a
catch-up chip never says "Re-coded" over nothing. `completed_at` means only
"applied at least once": it gates maintenance, it is how the startup sweep tells
the two orphans apart, and Apply refuses a job that has it.

_Superseded 22 Oct 2026 (RE#66):_ until then scope was inferred from two
timestamps, a session's `first_imported_at` and the codebook's last
`completed_at`, which each re-apply advanced. The text below said a partial run
could not move it past uncoded sessions, and it could: a pass where some batches
failed (a rate limit on two of six) still advanced it, and those sessions were
never coded by that codebook again. That was the "normal-lifecycle partial-run
edge" this section's deferred fallback named. Migration 022 backfilled stamps for
what the watermark claimed (sessions first imported at or before `completed_at`,
and those with no import time), so nothing an upgraded project had paid for is
sent again, and what a past partial failure lost stays lost: nothing recorded
which batches failed.

The two jobs below still hold, with the stamp in the timestamp's place:

- **The stamp is a *cost gate*, not a correctness rule.** Its only job is to avoid
  re-spending the LLM on sessions we know are done. Erring broad (a quote the model
  left untagged, in a session whose other batch failed, is sent again) costs a
  little wasted work, never a double-code.
- **Correctness lives in the per-quote guard that already ships.** Before applying a
  tag the delta skips any `(quote, tag)` that already has a `QuoteTag`. A human tag
  survives because it **occupies the pair**, not because it is recognised: the guard
  has no source predicate (corrected 31 Aug 2026). It would stop protecting it the
  moment any path removes and re-applies a tag, or applies the same tag under a
  second `tag_definition_id`. And within an owed session a quote that already has a
  proposal on the job is not sent, so a half-coded session never breaks
  `(job, quote)`.

Disable stops the re-applies: new sessions pile up owed, and re-enable fires one
catch-up over them, unless that codebook's previous catch-up, or a finished run's
re-apply of it, is still running, in which case the re-enable starts nothing and
the running one codes them (20 Oct 2026). A run's re-apply reads the switch again
before each codebook and before each batch, so one switched off while the run
codes stops at the next batch (#62). _Open (RE#66):_ switched off and back on
while that run's re-apply still codes, the batches it skipped while off stay owed
until the next run or switch-on, since the switch-on started nothing over the
live re-apply. It waits for a live catch-up of the same
codebook, and codes every other codebook first, so a long catch-up holds only its
own; it runs on its own task, never inside the event watcher (#67).

**Stops and failures.** A Stop on a catch-up keeps the batches that answered and
their stamps; the job stays `cancelled` and the rest stays owed (#60). A Stop on a
first apply leaves `completed_at` empty: a stopped first apply is not an applied
one, and nothing maintains it (#65). A run's re-apply that leaves nothing owed sets
a `failed` or `cancelled` applied job back to `completed` and clears its error
(#61).

**Serve crash.** No job survives a restart. On startup `reconcile_orphaned_jobs`
(`bristlenose/server/autocode.py`) sweeps in-flight jobs: `completed_at IS NULL`
(initial apply never finished) → `failed`, retryable; `completed_at` set (a catch-up
the restart cut off) → `failed`, unclassified, so a chip still polling says
"Tagging failed." (#63). That catch-up wrote no stamps, so its sessions are owed
either way. Until 22 Oct 2026 it was restored to `completed` with its counts at
zero, and a surviving chip said "Re-coded" over nothing; `failed` was avoided then
because it invited a re-Apply that deleted the original proposals, which Apply now
refuses (#64). _(Sweep shipped 26 Jul 2026, "codebook: harden catch-up against
crash-orphaning + false-success".)_

---

## 5. UX states & visibilities (the consequences)

What each control does at each surface. ✅ = built today, △ = described/to-build.

| Surface | 👁 Hide/Show | ⊘ Disable | ✕ Remove |
|---|---|---|---|
| **Codebook lens** — section | (n/a) | △ folds (blue dot → grey) | gone (back to Library as **Add**) |
| **Tags sidebar** | title + **closed-eye stub stays** (bring-back) ✅ | △ **gone entirely** (bring-back is the slider) | gone |
| **Quote-card badges** | hidden ✅ | hidden ✅ | gone |
| **Autocomplete** | **suggest + auto-unhide** ✅ *(keep!)* | △ **excluded** | excluded |
| **Results kept** | yes | yes | **no promise** |

The load-bearing distinction: **Hide leaves it reachable (suggest + auto-unhide);
Disable takes it off the board (gone from sidebar + autocomplete).** Same badge-hide,
opposite reachability.

---

## 6. Retention & cost gradient

| | 👁 Hide/Show | ⊘ Enable/Disable | ✕ Add/Remove |
|---|---|---|---|
| Means | not thinking about it *now* | set aside, might return | **done** |
| Bring-back cost | free, instant | free if unchanged; delta catch-up if new sessions (Q-B) | free if no new sessions; maybe full re-run if new |

The UI must make the *promise* legible — a "remembers your stuff" slider must not read
like a "no promises" Remove. (The Library redesign's job.)

---

## 7. The three-way delta

> _Note (26 Jul 2026):_ the A→C reversal below (the "off means off" flip, catch-up on
> re-enable, drop-from-sidebar/autocomplete) **shipped the same day** — commit subjects
> "true the 'disable is view-only' framing out of code + docs", "split hide … from
> disable … in autocomplete", "drop disabled codebooks from tags sidebar", "surface the
> on-enable catch-up as an activity chip". Table kept as the design-decision record —
> read it for the _why_, not as an open to-do.

**(A) Current code** ↔ **(B) the plan we were mid-implementing** ↔ **(C) what we've now
described.**

| Aspect | (A) Current (built this session) | (B) Previous plan | (C) Described (target) | Delta A→C |
|---|---|---|---|---|
| Enable/disable persistence | `ProjectFrameworkState` **view-only** | "prerequisite; persist then gate on enabled" | persisted, **functional** | make it functional |
| Re-apply gate | **linked, NOT enabled** (Decision A, `601f4f94`) | *wanted* enabled; shipped linked as v1 stopgap | **linked AND enabled** | **flip the gate** (return to plan's intent) |
| Disable = ? | view-only (fold + badge hide); still in sidebar; still autocompletes | (n/a) | **off means off**: drop from sidebar, exclude autocomplete | remove from sidebar + autocomplete |
| Disabled + new sessions | keeps coding (Decision A) | "codebooks that are on" | **stops**; catch-up on enable | **reverse Decision A** (Q-B) |
| Hide autocomplete | suggest + auto-unhide | (n/a) | **unchanged — keep** | none (revert my stray edit) |
| Manual codebook | shown as "User tags"; no disable | (n/a) | **floor**, named by project; never disabled | rename; confirm no-disable |
| Badges (hide ∪ disable) | `effectiveHiddenGroups` unifies | (n/a) | keep unified for badges; **split** for sidebar/autocomplete | split the non-badge paths |
| Re-apply delta + dedup + cancelled-job re-run + firePut toast | ✅ built | in/around plan | keep | none |

**Headline:** the one real reversal is **Decision A**. Mid-session I made disable a
view-only flag that keeps maintaining disabled codebooks (gate on *linked*). The
refined model — and the original plan — say disable is **functional and off means
off** (gate on *enabled*, stop maintaining, catch up on re-enable). The stray
uncommitted `TagInput` edit over-corrected in the *other* direction (killing hide's
autocomplete) and should be reverted.

---

## 8. Settled vs open

**Settled**
- **The dividing principle:** hand-made = deliberate = protected (floor); machine-made
  = profligate = toggleable.
- Two tiers: manual **floor** (permanent, hide/show only, named by project) vs
  auto-generated **toggleable** — **including uxr** (Q-A resolved: toggleable).
- **Hide** keeps auto-unhide + autocomplete (do not dismantle).
- **Disable** = off means off (drop from sidebar + autocomplete; badges hidden; section
  folds). Gate re-apply on **enabled**.
- **Remove** = done, no preservation promise.
- **Where enable/disable lives.** _Superseded 31 Aug 2026 — the "later version" the
  original bullet anticipated arrived, so both halves inverted._ The switch now rides
  on **each row of the navigator sidebar** (`EnableControl`,
  `frontend/src/components/CodebookV2Sidebar.tsx`), and the dot is gone — both
  halves of it were deleted on 22 Sep 2026: `codebookDot.ts` (no non-test caller)
  and `.codebook-dot{,-on,-off}` in `theme/organisms/sidebar.css` (no emitter in
  the SPA, the frozen vanilla JS or the static templates). The
  floor still gets no switch. The v1 statement is kept below because its *reasoning*
  is the thing to weigh before moving a control onto a navigation row, and that
  reasoning was overridden deliberately, not forgotten:
  > **(v1, superseded)** the **big toggle in the codebook lens** is the control
  > (`.framework-toggle`, already built). The **codebook-lens sidebar** is **state +
  > navigation only** — a blue/grey status dot echoing the switch, never a control.
  > The floor gets no toggle. (Moving the control elsewhere is a later version.)

  `.framework-toggle` survives only in the sealed static-render CSS
  (`theme/organisms/codebook-panel.css`); the shipped control is the platform
  `<input type="checkbox" switch>` with `.sw` as the capability-detected fallback.

- **What the switch must write** (added 31 Aug 2026): the whole disabled set, every
  time — see §4b. A control on a navigation row is also further from the store the
  other lenses read, which is the second half of the same defect: the navigator
  persisted without mirroring, so badges, the Quotes tag sidebar and autocomplete
  went on showing a switched-off codebook until reload. "Off means off" is a claim
  about every surface, not the one holding the switch.
- Provenance/disposition already modelled.
- **Disabled + new sessions (Q-B resolved): don't code while off; catch up on
  re-enable.** Rationale: you might never re-enable, so never spend on a switched-off
  lens; and when you do re-enable, the LLM cost/time of coding the newly-added sessions
  is implicit and accepted (re-enable is an auto-tagged-codebook feature — the spend is
  inherent to the gesture). Mechanically: no re-apply stamps a session while the codebook is
  disabled, so re-enable fires one delta over every session it owes (§4a; a
  session-recency watermark until 22 Oct 2026).

**Open**
- **Q-C:** denial-ledger — a future "re-apply after codebook edit" would resurrect
  `denied` proposals unless the accept guard learns to respect them. Not on the
  critical path, but a real prerequisite for any path that revisits old quotes.
