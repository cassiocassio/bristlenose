# Manual re-assignment (Phase 0) — design

**Status:** Write path built (Jul 2026); picker UI is the remaining piece. Crisp-first; expand a section when it's the one being built.

**Built so far (server + persistence):** the read-only Uncategorised floor (render + API), and the manual-reassignment **write path** — `POST /projects/{id}/reassign` (move quote(s) into a section/theme as an `assigned_by="researcher"` join, exclusive on that axis, bulk-capable), the importer **suppression rule** (a researcher-owned quote never gets a competing pipeline join re-added → placement survives every re-analysis for free), and **freeze-on-move** (§5.2 decided = **yes**; a move mints durable id + frozen form and extends the pin predicate, so a committed placement isn't swept when a later run drops the quote). Contract: `tests/test_curation_roundtrip.py::TestManualReassignment` + `test_serve_data_api.py::TestReassign`. **Remaining: the picker UI** — its open decisions are §5 below.
**Parent:** [`design-curation-persistence.md`](design-curation-persistence.md) — the "Hard dependency" paragraph names this as a prerequisite. **Sibling:** [`design-incremental-analysis.md`](design-incremental-analysis.md).
**Not this doc:** [`design-sidebar-drop-behaviour.md`](design-sidebar-drop-behaviour.md) is Finder→sidebar *project* import — a different gesture on a different surface.

## Why this exists (one paragraph)

The researcher is the analyst; the machine's grouping is a *draft*. Manual re-assignment is the gesture that lets them overrule the draft — move a quote into the section/theme where it belongs — and have that stick. It earns its keep three ways: (1) it fixes a **fresh** analysis's mis-groupings today (no incremental needed); (2) it is the **commit gesture** every "machine suggests, human commits" rule in the curation model depends on — a surfaced *"move this starred quote?"* has nowhere to land without it; (3) it is where an **orphaned/uncategorised** pinned quote gets a home. Without it, the surfacing model is decorative.

---

## 1. User needs

- **Correct a misplacement.** "This quote is under the wrong section/theme — put it where it belongs."
- **Bulk-correct.** After a re-analysis reshuffle (or a fresh run), fix several at once, not one-by-one.
- **Rescue an orphan.** Place a pinned quote that the current analysis left with no group (the "uncategorised" floor) into a real group.
- **Trust it sticks.** A move must survive re-analysis — the machine must not silently undo the researcher's placement.
- **Ratify a suggestion.** When the machine surfaces *"this looks like a better fit for X — move it?"*, accepting it is the same move.

Out of scope for Phase 0: create-a-new-group, merge/split groups, rename (rename already ships). Those are V2.

## 2. Jobs to be done

| When… | I want to… | So that… | Type |
|---|---|---|---|
| the machine puts a quote in a group I disagree with | move it to the right group in one gesture | my report reflects **my** reading, not the model's draft | functional |
| I've decided where a quote lives | that placement to hold as I add interviews | I never lose curation I already did | emotional (control/trust) |
| a re-run strands a starred quote with no home | drop it into a group (or keep it as a deliberate singleton) | a committed insight isn't silently lost | functional |
| the machine flags a possible better home | accept or dismiss with one action | I stay in control; the machine advises, I decide | emotional |
| I'm cleaning up after a fresh analysis | re-file a batch of mis-grouped quotes quickly | I get to a report I'd present without fighting the tool | functional |

**The deeper job:** "make *my* analysis legible" — the tool is hired to render the researcher's judgement, not impose its own. Every design choice below defers to that.

## 3. UX — options & recommended outline

Two gestures were named in the parent doc: **send-to** (multi-select) and **drag-and-drop**. They are not either/or on effort — send-to is also the required keyboard/accessible path, so it comes first regardless.

| Option | What | Pros | Cons |
|---|---|---|---|
| **A — Send-to (recommended first)** | Select quote(s) → "Move to…" action → pick a section/theme from a list | Reuses the built multi-select (`FocusContext.selectedIds`); accessible by default; covers single + bulk + orphan-rescue; *is* the landing place for a surfaced suggestion (accept → move-to) | Less spatial than dragging; a long target list needs search |
| **B — Drag-and-drop** | Drag a quote card onto a section/theme (heading or TOC target) | Direct, matches the "spatial memory of my report" mental model | Net-new infra (no DnD lib today); needs a keyboard alternative anyway (= you build A too); drop-target ergonomics on long, scrolling pages |
| **C — Both** | A as baseline, B as a power gesture on top | Best of both | B's cost lands for incremental ergonomic gain |

**Recommendation: build A (send-to) first; treat B (drag) as a later enhancement.** A is cheaper (selection exists), is the accessibility baseline you owe regardless, and is the same code path a surfaced suggestion's "accept" calls.

### Send-to flow (outline)

1. **Select** — reuse existing quote selection (click, shift-range, the `selectedIds` set). Single quote = a per-card action; many = a selection action.
2. **Invoke** — a "Move to…" affordance (per-card menu item and/or a selection action bar). Same entry point the surfaced-suggestion "accept" uses.
3. **Pick target** — a list of the project's sections and themes, grouped and labelled (show the *displayed* name — `edited_label ?? screen_label`). Searchable once the list is long. Include the current group (disabled) so the picker reads as "where it is → where it goes." Optionally include **Uncategorised** as a target (un-place).
4. **Commit** — optimistic move in the view; one API call. Exclusivity: the quote leaves its old group as it enters the new one.
5. **Feedback / undo** — TBD (see open decisions). Note the native-idiom caveat: in the desktop shell, web-style toasts are discouraged — favour an in-place, quiet confirmation.

### Uncategorised interaction

The floor is both a *source* (drag/send an orphan out into a group) and possibly a *target* (send a quote to "uncategorised" = deliberately un-place). Phase 0's orphan-rescue job depends on the floor being rendered.

**Shipped (this branch): the read-only floor exists, and now the re-file *write path*.** `GET /quotes` returns an `uncategorised` bucket — pinned quotes the current analysis leaves in no group — the `UncategorisedFloor` island renders it, and the importer exempts *named* groups from retirement so a human-owned container never dissolves (see [`design-curation-persistence.md`](design-curation-persistence.md) §6/§12). The `POST /reassign` endpoint now makes any quote — orphan or mis-grouped — *re-fileable*, and the placement sticks (suppression + freeze, above). **The remaining piece is the picker UI** — the affordance that calls `reassign` (per-card "Move to…" + selection action bar, reusing `FocusContext.selectedIds`).

## 4. Engineering & data issues

### Persistence — mostly already there

- `ClusterQuote.assigned_by` / `ThemeQuote.assigned_by` exist (`models.py:427,448`, default `"pipeline"`). A manual move = **create the join with `assigned_by="researcher"`** and remove the quote's existing join.
- The importer rebuild deletes only `assigned_by="pipeline"` joins (`importer.py:952,1079`), so a **researcher join already survives every re-analysis for free** — the "it sticks" need is met by the existing model. This is the big lever; Phase 0 is mostly a *write path*, not a schema change.

### The real issue — pipeline must yield to a researcher placement

Today the rebuild re-adds a pipeline join for whatever group the pipeline emits a quote in. If a quote has a **researcher** join in group B and the next run's pipeline emits it in group A, the importer would add a `pipeline` join to A → the quote is in **two** groups (breaks quote-exclusivity).

**Rule to add:** a quote with any `assigned_by="researcher"` join is *researcher-owned* for placement — the importer must **not** add a pipeline join for it (skip it in both cluster and theme import). This is the placement analogue of the theme-naming model (`project_theme_naming_commitment_model`: a human-committed placement wins over the machine's draft). It's a small importer change but it's the load-bearing correctness rule — build it *with* the write path, not after.

### Other issues / decisions embedded in the data

- **Exclusivity on move** — one join per quote. Moving is delete-old (any `assigned_by`) + add-new (`researcher`), in one transaction, server-side.
- **Does a move freeze the quote?** A manual re-assignment is researcher effort/commitment. Options: (a) it pins (extends the pin predicate `starred ∨ edited ∨ human-tagged` to include "researcher-placed") — consistent with "a committed placement is human investment"; (b) it doesn't pin, placement alone doesn't guarantee the quote survives a pipeline drop. **Lean (a)** — moving something signals it matters — but it widens `_pinned_quote_ids`; decide explicitly.
- **Composition with the strand fix** — the Phase-2 strand logic preserves a *pinned* quote's *pipeline* join in a reused group. A researcher join is a separate row; the researcher-owned suppression rule above must take precedence so the two don't fight.
- **API** — a `PUT`/`POST` reassignment endpoint on `routes/data.py` (project-scoped, `_resolve_quote` for the DOM-id → row, target = a durable `cluster_id`/`theme_id`). Bulk = a list. Mirror the existing state-sync endpoints.
- **Frontend** — send-to reuses `selectedIds`; needs a target-picker component and the move action wired through the quotes store (optimistic update + API). Drag (option B) is net-new (no DnD dependency today; HTML5 draggable or a small lib + a keyboard fallback).
- **Multi-project / scope** — `ClusterQuote`/`ThemeQuote` are project-scoped through their group; no scope concern.

## 5. Open decisions (for the user)

1. **Send-to first, drag later** — confirm the sequencing (recommended), or build drag up front. _(Still open — gates the picker.)_
2. ~~**Move = freeze?**~~ **Decided: yes.** A manual placement extends the pin predicate (`importer._pinned_quote_ids` placement arm) and mints durable id + frozen form. Implemented with the write path.
3. **Undo** — quiet in-place confirmation only, a time-boxed undo, or none? (native-idiom caveat in the desktop shell.) _(Still open — picker behaviour.)_
4. **Uncategorised as a target** — can a researcher deliberately un-place a quote, or is the floor source-only? _(Still open — the endpoint currently accepts only section/theme targets, so "un-place" is not yet reachable.)_
5. **Surfaced-suggestion coupling** — design "accept a suggestion" as literally a send-to call, so the two share one path. _(Later — no suggestion surface exists yet.)_

## 6. Group lifecycle — future (surfaced by the persistence work)

Once orphans surface in Uncategorised and re-assignment ships, a named-but-drained group has a lifecycle the researcher drives. Two journeys — both expressible as the *existing* primitives (**move** + **rename**) plus exactly one net-new affordance:

- **Journey A — "that grouping wasn't real."** The researcher drags the last starred quote out of a drained named group into a newly-emerged one (a **move**). The named group is now empty. Net-new: **deleting an empty named group.** Rule (straight from the commitment model): an empty *un-named* group evaporates silently (machine-owned); an empty *named* group needs the researcher's confirmation — you named it, only you bury it.
- **Journey B — "no, this grouping *should* live."** The researcher renames the drained group to something better and drags other quotes into it from elsewhere (**rename** + **move**). It becomes doubly anchored — named **and** researcher-populated (`assigned_by="researcher"` already survives every re-analysis for free) — effectively permanent.

The through-line: **destruction escalates with human investment.** Machine group → silent sweep. Named group → confirmed delete. Named + populated → effectively permanent. Same ladder as the pin model, one level up (containers, not quotes).

Two open UX decisions (deferred — *not* needed for the read-only floor):
- **When** the empty-named-group prompt fires — the instant the last quote is dragged out, quietly at next analysis, or batched. (Lean: **not** the instant — a 0-member named group is a valid resting state, so deleting it is a separate deliberate gesture, not an interruption mid-drag.)
- **Whether it's a blocking Y/N** at all — on the desktop shell a modal confirm cuts against the native idiom; a quiet remove-with-undo may read better for something the researcher can always re-make. (Native-idiom call — defer.)

Nothing here changes the architecture: it's `move` + `rename` + one "named-and-empty" delete, riding machinery that already exists.

## Scope boundaries

- **In (Phase 0):** move existing quote(s) between existing sections/themes; rescue from uncategorised; researcher placement survives re-analysis; the importer yields to it.
- **Out (V2+):** create/merge/split groups; move quotes across projects; drag-and-drop polish; the confidence/"surfacing bar" for machine-initiated move suggestions (that's the curation doc's open question).
