---
status: partial
last-trued: 2026-10-04
trued-against: HEAD@main on 2026-10-04
---

> **Trued 4 Oct 2026 — partly built.** The report now has one undo stack, and four
> groups below are on it: speaker names (7), quote curation (2: star, hide, text
> edit, revert), tags (3: add, remove) and headings (6: titles, descriptions).
> The 28 Jul inventory, constraints and opinion below are kept as written, with
> dated corrections where the build answered or overturned them. The
> as-built record is [`design-people.md`](design-people.md) §B10.
>
> _Original banner (28 Jul 2026):_ **Pending / stub catalog.** An inventory, not a plan. Nothing here is decided or
> built. Written 28 Jul 2026 from a full read of the shipped mutation surface; the
> "what exists" and "constraints" sections are verified against code, the
> **value speculation is opinion** and is marked as such. The scope call this
> feeds is still open in [`design-undo-debt.md`](design-undo-debt.md) §Open.

## Changelog

- _2026-10-04_ — trued against the build: status `partial`; the 28 Jul "what exists" table kept beside a 4 Oct one; the substrate section records that deltas shipped instead of snapshots; the divide's points 1–4 and the open questions annotated with what was decided. New finding recorded under point 2: a pending sidebar removal shadows the whole report stack, indefinitely.
- _2026-10-04_ — built: the report stack (`contexts/UndoStore.ts`, `components/UndoSync.tsx`, the `undo-state` channel live both ways with named Undo and Redo), first for speaker names, then star/hide/tag, then text edits.
- _2026-07-28_ — created. Companion to `design-undo-debt.md`, which owns the *sidebar* register and the "nothing confirms, everything ⌘Z's" principle. This doc owns the **full** mutable-state inventory (five ownership domains, ~50 mutations), the candidate history stacks, and the Swift↔Python boundary problems that doc explicitly declines to cover ("the report's own undo domain… Don't conflate the two").

# Undo — catalog of the history stacks we'd need

## Why this doc

[`design-undo-debt.md`](design-undo-debt.md) sets the principle — *nothing confirms,
everything ⌘Z's* — and registers the seven sidebar actions. It then draws a
boundary and stops:

> "React report edits (hide / edit quote, edit heading, tag ops) live in the SPA —
> the report's own undo domain, not this `NSUndoManager`. Don't conflate the two."

That boundary is correct as an *implementation* seam and wrong as a *product*
seam: the user has one ⌘Z key. This doc catalogues what's on the far side of it,
so the scope call can be made with the whole surface visible rather than half.

## What exists today (verified)

**As of 4 Oct 2026:**

| Context | ⌘Z owner | Depth | Durable? |
|---|---|---|---|
| Text field / contenteditable focused (`isEditing`) | WebKit's native text undo | WebKit's own | ❌ lost on blur/commit |
| Native inline rename in sidebar | AppKit field editor | field-local | ❌ lost on commit |
| Project removal pending | `UndoableRemovalStore` | 1 batch, **no expiry** since 19 Aug | ❌ in-memory |
| The report (Sessions + Quotes lenses) | `contexts/UndoStore.ts`, via `undo-state` on the Mac and `UndoSync.tsx`'s keys in the browser | 100 | ❌ page-scoped — ends on reload, Mac project switch, new run |
| ⇧⌘Z | the report stack's redo, named ("Redo Star") | 100 | ❌ same |

What the three facts below became: (1) still true, and now settled — §B10 chose
the bridge over `NSUndoManager`; (2) false — the channel is live both ways and
`getState()` reads the store; (3) false since 19 Aug (`5598bd39`, "five toasts
and a fuse removed") — no undo toast ships. Also learned building it: WebKit
fires no `focusout` when a focused editor is removed, so `isEditing` needs a DOM
re-check or Edit ▸ Undo stays hidden after an inline edit (`desktop/CLAUDE.md`).

**28 Jul 2026 survey, kept as written:**

| Context | ⌘Z owner | Depth | Durable? |
|---|---|---|---|
| Text field / contenteditable focused (`isEditing`) | WebKit's native text undo | WebKit's own | ❌ lost on blur/commit |
| Native inline rename in sidebar | AppKit field editor | field-local | ❌ lost on commit |
| Project removal pending | `UndoableRemovalStore` | **1 batch**, 8 s | ❌ in-memory; lost on crash |
| Everything else | *nothing* | 0 | — |
| ⇧⌘Z (redo), anywhere | *nothing, ever* | 0 | — |

Three facts worth carrying into any design:

1. **`NSUndoManager` is used nowhere.** The shipped store explicitly rejected it
   ("avoids braiding removal-undo with whatever responder chain happens to hold
   focus"). `design-undo-debt.md` names `NSUndoManager` as the target mechanism
   without acknowledging that precedent — **an unreconciled contradiction**, flag
   it before building.
2. **The `undo-state` bridge channel is dead on both ends.** Swift has a `case
   "undo-state"` handler; nothing in the frontend ever posts that message, and
   `bridge.ts` `getState()` hard-codes `canUndo: false, canRedo: false` with
   "Stubs — wired when undo store ships." So Edit ▸ Redo is permanently disabled
   and Edit ▸ Undo's web branch is unreachable.
3. **The one shipped undo affordance is a toast** — which `design-undo-debt.md`
   §Corollaries bans outright ("No undo toasts"). Three other design docs also
   still propose toast-based undo. **Second unreconciled contradiction.**

## The five ownership domains

There is no shared transaction and no shared clock between any of these.

| | Store | Owner | Writable by |
|---|---|---|---|
| **A** | `projects.json` | Swift | Swift only — Python never reads it |
| **B** | `UserDefaults` | Swift | Swift; reaches Python as env vars at sidecar launch |
| **C** | Keychain | Swift | Swift + two server routes (Miro connect/disconnect) |
| **D** | SQLite (`<output>/.bristlenose/bristlenose.db`) | Python | **Python only** — Swift opens it `READONLY ?immutable=1` |
| **E** | `localStorage` | SPA | SPA only; **ephemeral on desktop** (`nonPersistent()` data store) |

Plus a sixth, sideways: `<output>/people.yaml`, dual-written with the `persons`
table by `PUT /people`, best-effort, no rollback if the two disagree.

## Candidate history stacks

Ten groups. "Inverse available?" is the question that decides how hard each is.

| # | Stack | Mutations | Scope | Store | Inverse available? |
|---|---|---|---|---|---|
| 1 | **Sidebar / project chrome** — add, remove, rename, move, icon, reorder, folder CRUD | ~11 | instance | A | ✅ trivially (all metadata) |
| 2 | **Quote curation** — star, hide, edit text, revert, badge delete | 6 | project | D + SPA | ✅ prior full map |
| 3 | **Tags on quotes** — add, remove, accept/deny proposal, accept-all, deny-all, bulk assign | 7 | project | D + SPA | ✅ prior full map |
| 4 | **Codebook structure** — group ×3, tag ×3, merge, import-template, remove-framework, framework toggle | 10 | project DB | D | ⚠️ **partly — deletes cascade** |
| 5 | **Prompt cultivation** — synthesize, manual edit, decisions+refine | 3 | project DB | D | ❌ overwrites in place, no history |
| 6 | **Headings / placement** — section title, theme description, reassign to section/theme | 3 | project | D | ✅ prior value |
| 7 | **Speaker / participant names** | 1 (bulk) | project DB **+ file** | D + YAML | ✅ but two targets |
| 8 | **Settings / credentials** | ~19 keys + N provider keys | instance | B + C | ⚠️ side effect: restarts the sidecar |
| 9 | **View state** — widths, collapse, zoom, filter ticks, badge dismissal | many | per-WebView | E | n/a — shouldn't be undoable |
| 10 | **Transcript text / speaker splitting** | 0 shipped | — | — | design docs only |

_On the stack as of 4 Oct 2026:_ group 7 (speaker names, from the Sessions grid
and the person picker); group 2's star, hide, text edit and revert; group 3's
add and remove (bulk add is now one write, `addTagToQuotes`); group 6's section
and theme titles and descriptions. _Not on it:_ badge delete, proposal
accept/deny and accept-all/deny-all, reassign to section/theme, and groups 1
(the Swift removal store excepted), 4, 5 and 8.

### The accidental substrate

Six endpoints are **delete-all-then-reinsert** with a full map body (`/edits`,
`/tags`, `/deleted-badges`, `/hidden-tag-groups`, `/framework-states`, plus
`/hidden` and `/starred` which iterate every quote).

That shape is *accidentally close to ideal* for undo: the previous full map **is**
a complete inverse, replayable in one call. Groups 2, 3 and 6 could get
snapshot-and-replay undo without any new server vocabulary.

> **Shipped instead, 4 Oct 2026: deltas.** Each gesture records its inverse as
> the same store call with recording off, over only the quotes or keys it
> changed (`QuotesContext.tsx`, the comment above `toggleStar`). A replayed
> snapshot would also revert whatever changed since by a path not on the stack —
> an AutoCode accept, a refetch. The writes are still the full-map PUTs below,
> so the server shape is unchanged, and the first caveat holds: the delta is
> computed from store state, and `firePut` still never reverts (it toasts on
> failure). Accepted at localhost stakes, as that caveat proposed.

Two caveats that stop it being free:

- **No endpoint returns pre-mutation state, an inverse, or a revision token.**
  Most return `{"status": "ok"}`. So the snapshot has to be taken client-side
  *before* mutating.
- **The SPA store is a divergent copy, not a cache.** `firePut` is optimistic and
  never reverts on failure (by deliberate policy — localhost, not cloud). So a
  client-side snapshot can record a value the server never actually held. Undo
  built on store state can therefore *write a fiction back*. Fixing this properly
  wants a revision token; accepting it is probably fine at localhost stakes, but
  it should be an explicit decision, not an accident.

### Where the inverse genuinely doesn't exist

- **Cascading deletes.** `DELETE /codebook/tags/{id}` hard-deletes every
  `quote_tags` row for that tag before removing the definition;
  `remove-framework` does the same across a whole framework; `merge-tags`
  hard-deletes the source and records nothing. The *definition* is recoverable
  from a snapshot; **the coding labour is not**, unless the snapshot captures
  every affected join row.
- **Pin minting is one-way.** Starring a quote mints `durable_id` + `frozen_form`
  (first-touch-wins, idempotent). Un-starring does *not* unmint them — that only
  happens at the next import. So star→unstar lands in a state that neither
  preceded nor followed the action. _(4 Oct 2026: this is now reachable by
  Undo — undoing a star, an edit or a human tag does not unmint either.)_ `frozen_form` is also flagged in-code as a
  re-identification key, so this isn't cosmetic.
  _Corrected 28 Jul 2026: the pin predicate has **four** arms, not three —
  `starred ∨ edited ∨ human-tagged ∨ researcher-placed` (`assigned_by ==
  "researcher"` on a section or theme join). `importer.py:1409`'s docstring
  **headline** lists only the first three while its own body documents the fourth;
  that error propagated into this doc and into
  [`design-curation-persistence.md`](design-curation-persistence.md). Undo of a
  manual re-assignment therefore also un-pins, which the earlier text missed._
- **Spent tokens.** Autocode *proposals* can be discarded; the LLM call that
  produced them cannot be un-made. Already settled doctrine in
  `design-pipeline-resilience.md`: "There's no 'undo' for an LLM call."
- **Off-device effects.** `POST /miro/export` creates a board on Miro's servers.
- **Re-analyse.** See below — it's a different problem shape entirely.

## Speculation — where the value is

**Opinion, not decision.** Ranked by *loss avoided per unit of build*, not by
frequency.

1. **Codebook structural deletes (group 4) — highest value.** One click behind a
   confirm dialog destroys coding labour across the whole project, and the dialog
   is the only guard. The mockup copy is honest about it: *"This cannot be undone."*
   This is the one place where the current answer is a dialog **and the dialog
   isn't enough** — exactly the case `design-undo-debt.md` argues confirmations
   handle badly.
2. **Bulk tag operations (group 3) — close second.** Accept-all / deny-all across
   hundreds of quotes is the same shape: enormous blast radius, single gesture,
   no way back. Unlike group 4 the inverse *is* cheaply available (prior full map),
   so the value-to-effort ratio is the best on the list.
3. **Quote curation (group 2) — cheapest meaningful win.** Highest frequency by
   far, and the total-replacement PUT means undo is nearly free to implement.
   Individually low-stakes (you can just re-star), so it buys *fluency* rather
   than *safety* — but fluency in the core loop is what makes the tool feel
   Mac-native rather than web-form-like.
4. **Sidebar chrome (group 1) — lowest stakes, already specced.** Rename, move
   and icon are trivially redoable by hand; folder delete is the only sharp edge.
   It's first in `design-undo-debt.md` because it's *legible* and Swift-only, not
   because it's where the loss is. Worth being honest about that: doing group 1
   first optimises for a demonstrable ⌘Z, not for the user's worst day.
5. **Prompt cultivation (group 5) — high value, blocked.** `_upsert_prompt`
   overwrites in place with no history, and the decisions table keeps only a
   version *hash*, not the text. Undo here needs a schema change first, so it's
   sequenced behind everything else regardless of value.

**The re-analyse exception.** The single most destructive action in the product
isn't on this list, because an undo *stack* is the wrong instrument. `--clean`
`rmtree`s `bristlenose-output/` — and both the SQLite DB and the event log live
*inside* that tree. It deletes the undo substrate itself. Even without `--clean`,
a normal re-import hard-deletes stars, hidden quotes, tags, edits, badges,
proposals and placements for stale sessions. The right instrument is a
**snapshot before the destructive act** (copy the DB aside, offer "restore
previous analysis"), not a history stack. Worth stating plainly so nobody tries
to solve it with ⌘Z. *(Related: `design-codebook-library.md` already argues
incremental re-analyse must become additive rather than destructive — that would
shrink this problem at source.)*

## The Swift ↔ Python divide

The hard part, and the reason this can't be one `NSUndoManager`.

1. **Swift physically cannot write the report's truth.** SQLite is opened
   `READONLY` with `?immutable=1`. There is no Swift write path and adding one
   would fight the single-writer model. So *all* report-side undo must route
   Swift menu → bridge → SPA → HTTP → Python. That is precisely the `undo-state`
   channel that is currently inert on both ends. _(4 Oct 2026: live both ways —
   that is the route the report stack takes.)_

2. **Two stacks, one key, and no shared order.** Remove a project (Swift/A), then
   hide a quote (Python/D). ⌘Z should undo the hide first. Nothing today gives the
   two domains a common sequence — they don't share a clock, a transaction, or a
   counter. A merged ⌘Z needs an **undo coordinator** that owns chronological
   order across domains and asks each side "what's your top entry, and when?".
   The menu label (`undoLabel`) needs the same answer to say "Undo Hide Quote"
   rather than a generic verb.

   _4 Oct 2026: shipped as two stacks and no coordinator._ The Edit menu ORs
   them and a pending removal always wins (`MenuCommands.swift`,
   `UndoRedoMenuContent`). Since the 19 Aug fuse removal a pending removal never
   expires, and the store is app-wide — so after any sidebar removal, ⌘Z and
   Edit ▸ Undo in every window undo that removal, and the report's stack is out
   of reach from the menu and the key until it is undone or superseded. This
   paragraph's own example (remove, then hide, then ⌘Z) undoes the removal
   first. **Open, found while truing; not fixed in 0.33.0.** Labels are solved:
   whole per-language strings (`UndoStore.ts`).

3. **Asymmetric durability.** The Swift stack is in-memory (a crash inside the 8 s
   window loses the project). _(4 Oct 2026: no 8 s window since 19 Aug, and the
   report stack is page-scoped too — neither half survives quit, so the product
   promises session-scoped undo throughout.)_ SQLite is durable. A user cannot be expected to know
   which half of ⌘Z survives a crash — so either the Swift stack gains durability,
   or the product promises only session-scoped undo and says so.

4. **The SPA cannot hold the report stack.** On desktop each project's WebView
   gets a fresh `WKWebsiteDataStore.nonPersistent()` partition, and the warm-sidecar
   work keys the WebView on `project.id + port` — so a project switch **remounts**
   and `localStorage` evaporates. A React-resident undo stack would silently reset
   every switch. **Conclusion: report undo has to persist server-side, which makes
   it a Python feature with a React trigger, not a React feature.** This is
   probably the single most consequential constraint in this doc.

   _4 Oct 2026: accepted rather than solved._ The stack is React-resident and
   page-scoped by design (`UndoStore.ts`'s header): a reload, a Mac project
   switch or a new run ends it, which matches a Mac document's undo ending when
   it closes. Persisting it server-side remains the route if that ever proves
   wrong.

5. **The event-log tease.** `pipeline-events.jsonl` looks like a ready-made undo
   substrate and isn't: it's run-level only (five event types — started, progress,
   completed, cancelled, failed), single-writer, and deleted by `--clean`.
   `design-pipeline-resilience.md` Phase 4a proposes extending it with human-edit
   events (`quote_hidden`, `tag_renamed`, …) and explicitly lists "**Undo/redo**:
   drop the last N events and rebuild" as a payoff. **That is the principled
   version of this whole doc** — every stack below becomes a projection over one
   log. It's also unbuilt, and it would want the log to move *outside* the tree
   `--clean` removes.

6. **Two copies of speaker names.** `PUT /people` writes both the `persons` table
   and `people.yaml`, non-transactionally. Any name undo has two targets and can
   half-succeed.

7. **Settings undo restarts a process.** Undoing a provider or typography change
   tears down and relaunches the serve sidecar. Reversible, but not *quiet* — this
   group probably shouldn't be on the ⌘Z stack at all.

## Open questions (for whoever picks this up)

_Answered 4 Oct 2026, inline below; the questions are kept as asked._

- One ⌘Z or two? A merged coordinator is the honest product answer and the
  expensive one. Per-domain undo is cheap and will read as arbitrary.
  → **One key, two stacks, no coordinator** — and the removal-first precedence
  under §divide point 2 is the arbitrary reading this predicted.
- Does undo survive quit? (Decides in-memory vs SQLite-backed, and answers §3.)
  → **No.** Page-scoped.
- Does it survive re-analyse? (Almost certainly not — see the exception above.)
  → **No.** A new run clears the stack (`UndoSync.tsx`).
- Depth: 1 is the current answer everywhere. The original bridge spec called
  proper depth a P1 gap.
  → **100** on the report stack; the Swift removal store is still 1.
- Redo at all? ⇧⌘Z has never done anything; shipping undo without redo is
  defensible but should be deliberate.
  → **Shipped**, named for the act ("Redo Rename Moderator").
- Reconcile the two contradictions in `design-undo-debt.md` (NSUndoManager vs the
  shipped rejection; toasts banned vs the shipped toast) **before** building.
  → Both closed: the toast went on 19 Aug; §B10 chose the bridge, not
  `NSUndoManager`.

## References

- [`design-undo-debt.md`](design-undo-debt.md) — the principle, the sidebar register, and the open scope call
- [`design-pipeline-resilience.md`](design-pipeline-resilience.md) — event sourcing; Phase 4a is the principled substrate
- [`design-quote-editing.md`](design-quote-editing.md) — the shipped all-or-nothing revert, and why partial undo was declined
- [`design-transcript-editing.md`](design-transcript-editing.md) — a *deliberate* rejection of a history stack, with the competitive scan
- [`design-codebook-library.md`](design-codebook-library.md) — additive-not-destructive re-analyse
- [`design-incremental-analysis.md`](design-incremental-analysis.md) — what a re-run replaces "without recourse"
