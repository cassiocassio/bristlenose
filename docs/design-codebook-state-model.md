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
| Add sessions + re-run | *(described)* if codebook **enabled**: delta re-apply codes only new sessions' quotes (`first_imported_at > completed_at`), non-clobbering |
| Disable | set `enabled=false` — *(described)* stops the delta re-apply; results retained |
| Enable | set `enabled=true` — *(described)* one catch-up delta for sessions added while off (watermark froze) |
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

### 4a. How re-enable knows what to code (no explicit "coded" flag)

There is **no per-session "this session was coded by codebook X" marker.** Re-apply
scope is inferred from two timestamps: a session's `first_imported_at` and the
codebook's last `completed_at`. **These do two separate jobs — don't conflate them:**

- **The timestamps are a *cost gate*, not a correctness rule.** "Session came in after
  the codebook last finished → probably uncoded → go look." Their only job is to avoid
  re-spending the LLM on sessions we're confident are done.
- **Correctness lives in the per-quote guard that already ships.** Before applying a
  tag the delta skips any `(quote, tag)` that already has a `QuoteTag`. So the
  timestamp erring **too broad** costs a little wasted work (re-examine, skip) — it
  can **never** double-code or clobber a decision. _Corrected 31 Aug 2026: this
  read "and never touches `source="human"`", which describes the effect as though
  it were the mechanism. The guard has no source predicate — it is a bare
  pair-existence check. A human tag survives because it **occupies the pair**, not
  because it is recognised. The outcome is the same today; it would stop being the
  same the moment any path removes and re-applies a tag, or applies the same tag
  under a second `tag_definition_id`._

The only way the timestamp could *miss* (skip genuinely-uncoded quotes) is a codebook
that stamped `completed_at` while its run was actually incomplete. In the normal
lifecycle that can't happen — `completed_at` only advances on a **completed** run;
failed/cancelled runs leave the watermark where it was, so those sessions get picked up
next time. Disable simply freezes the watermark (the codebook stops running), new
sessions pile above the line, and re-enable fires one delta over everything above it.

The one abnormal path where the watermark *could* lie — a **serve crash** mid-run
that strands a job `running`/`pending` — is handled separately, not by the deferred
stamp below. On startup `reconcile_orphaned_jobs` (`bristlenose/server/autocode.py`)
sweeps in-flight jobs (none survive a serve restart): a job with `completed_at IS NULL`
(initial apply never finished) → `failed`, so the watermark never advanced and the delta
re-codes those sessions next time; a job with `completed_at` set (only the transient
on-enable catch-up chip-flip was interrupted) → restored to `completed`. So the watermark
stays honest across crashes without the per-session flag. _(Shipped 26 Jul 2026 — commit
"codebook: harden catch-up against crash-orphaning + false-success".)_

**Bulletproof fallback (deferred):** if a *normal-lifecycle* partial-run edge ever forces
the issue, the robust answer is the explicit per-session (or per-quote) "coded by
framework X" stamp. More bookkeeping; not worth it for v1, where watermark-scope +
per-quote-guard + the crash reconciliation above is correct for the real lifecycle.
Recorded here so the reasoning isn't re-derived.

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
  `frontend/src/components/CodebookV2Sidebar.tsx`), and the dot is gone —
  `codebookDot.ts` has no non-test caller and `.codebook-dot` no JSX consumer. The
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
  inherent to the gesture). Mechanically: the session-recency watermark froze while
  disabled, so re-enable fires one delta over everything added since.

**Open**
- **Q-C:** denial-ledger — a future "re-apply after codebook edit" would resurrect
  `denied` proposals unless the accept guard learns to respect them. Not on the
  critical path, but a real prerequisite for any path that revisits old quotes.
