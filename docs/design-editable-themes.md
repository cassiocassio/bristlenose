# Editable themes & sections — design

**Status:** Design-only (Jul 2026). No code yet. This doc extends [`design-manual-reassignment.md`](design-manual-reassignment.md) (Phase 0 — *move* built, *rename* shipped) into full **researcher-owned structure**: create / delete / reorder groups, drag-to-reorder, drag quotes between groups, and a persistent order that survives incremental re-analysis. Interactive prototype: [`mockups/editable-themes-prototype.html`](mockups/editable-themes-prototype.html) — a behavioural toy that fast-forwards incremental sessions to reveal the consequences.
**Parents:** [`design-curation-persistence.md`](design-curation-persistence.md) (which human signals survive a re-run, and the identity machinery), [`design-incremental-analysis.md`](design-incremental-analysis.md) (adding interviews to a finished project), [`design-manual-reassignment.md`](design-manual-reassignment.md) (the move/rename write path this builds on).
**Sibling:** [`design-quote-filtering.md`](design-quote-filtering.md) — the *filter* half of the same Quotes-lens View menu; this doc owns *sort / arrange*.
**Grounding:** a Jul 2026 deep-research pass on automatic-sort-vs-manual-order patterns (Airtable, macOS Finder, macOS Photos, Figma/LexoRank fractional indexing) — cited in the Appendix — plus a code audit of the live data model (`server/models.py`, `server/importer.py`, `server/routes/{data,quotes}.py`). Empirical constants reused from the parent: **section** membership is stable run-to-run (**ARI ~0.96**); **theme** membership churns (**ARI ~0.43**); a **~9% fragile tail** of quotes no matcher recovers.

---

## Why this exists (one paragraph)

The machine's grouping and ordering are a *draft*. A researcher holds insight the text analysis can't reach — they know a theme the model missed, they know their study was a linear funnel or a self-directed whirlpool, they know which quote is the money quote and what order tells the story. Today they can *rename* a group and *move* a quote (Phase 0); they cannot **create** a group the machine missed, **delete** one that isn't real, or **arrange** groups and quotes into the sequence their readout needs — and have any of it survive the next batch of interviews. This doc specifies that: the researcher owns structure and order; the machine proposes and, on re-analysis, only *adds* — it never silently overwrites a human commitment.

---

## 1. Scope — the operations

**In scope (this doc):**

| Operation | Axis | Notes |
|---|---|---|
| Create a group | section / theme | mints `created_by="researcher"`; the machine never touches it |
| Delete a group | section / theme | researcher-created: clean delete, quotes → Uncategorised floor. Machine group: "empty it" (see §8) |
| Rename a group | both | **already ships** (`HeadingEdit`) — listed for completeness |
| Move a quote between same-axis groups | within section-pool / within theme-pool | backend **already built** (`POST /reassign`); needs UI |
| Reorder groups | both | new — the ordering model, §4–§6 |
| Reorder quotes within a group | both | new — same rank machinery, one level down (§8) |
| Drag quotes across the section↔theme boundary | cross-axis | re-classification, not a move — later (§8, Phase E) |

**Out of scope:** merge/split as *explicit user gestures* (the pipeline still splits/merges on its own — §7); multi-section membership (the exclusivity invariant forbids it — §3); collaborative/concurrent reorder (Bristlenose is local-first single-user — the CRDT interleaving problem is inert, see Appendix).

**The through-line:** every operation above is *the same mechanism applied to a different field*. That's §2.

## 2. The spine — one ownership pattern, four fields

The codebase already carries two "researcher owns this" discriminators. This design adds a third and a fourth. All four obey one rule:

> **The importer only ever *adds*. It rebuilds the machine's own output and appends what's new. It never rewrites, reorders, or deletes anything a researcher touched.**

| Field | On | Means | Status |
|---|---|---|---|
| `assigned_by="researcher"` | `ClusterQuote` / `ThemeQuote` join | this quote's placement is human-owned; the importer won't add a competing pipeline join | **built** (`models.py:427,448`; importer skip `importer.py:1067`) |
| `created_by="researcher"` | `ScreenCluster` / `ThemeGroup` | this whole group is human-made; the retire sweep and membership matcher skip it | **column exists** (`models.py:377,403`), documented contract, **no write path yet** |
| `rank` (fractional string) | `ScreenCluster` / `ThemeGroup` (and later the join rows) | explicit sequence position; §6 | **new** |
| `sort_key` (nullable) | per-axis, per-project | binary: the axis's single machine order on, or `null` = *committed manual* (§4, §6) | **new** |

The importer already implements this rule for joins and containers ([`design-manual-reassignment.md`](design-manual-reassignment.md) §4). Extending it to `rank` and `sort_key` is the same idea: *human-owned order is a commitment the machine must not overwrite.* No new architecture — a new field and the existing discipline.

## 3. Hard invariants (do not break these)

1. **Quote exclusivity — every quote appears in exactly one group** (`stages/CLAUDE.md:106`). Single-membership, *not* immutable: a move is a delete-old-join + add-new-join in one transaction. `POST /reassign` already does this atomically.
2. **Two disjoint pools.** A quote is `SCREEN_SPECIFIC` (→ exactly one *section*) or `GENERAL_CONTEXT` (→ exactly one *theme*), never both. So "drag between sections" and "drag between themes" are two *within-axis* operations; dragging **across** the boundary re-classifies `quote_type` and is a heavier, later operation (§8 Phase E).
3. **The importer yields to a researcher placement** — the load-bearing correctness rule ([`design-manual-reassignment.md`](design-manual-reassignment.md) §4). A quote with any `assigned_by="researcher"` join must never receive a competing pipeline join, or exclusivity breaks. Every new write path must honour this.

## 4. The interaction model — "Keep Sorted By" (a modeless mode)

The precedent that fits us exactly is **macOS Photos albums** — because an album is a *curated narrative subset* the user arranges, which is what our report grid is. (The Library, always auto-sorted, is the Photos analogue of a future triage/list view — see "View = intent" below.) Airtable and Finder are close cousins; Photos has the cleanest grammar and, crucially, the same shape of problem.

**The grammar (binary — one machine order per axis).** There is exactly **one** machine order per axis (§5), *not* a menu of sort keys, so the control is one checkmarked item per axis: **"Keep Themes Sorted by Strength of Evidence"** and **"Keep Sections Sorted by Most Common Sequence."**

- **Ticked → automatic**: the list is held in that order; new items sort in.
- **Dragging a group unticks it** → **manual**: items stay where you put them; the current arrangement becomes the manual baseline (your drag = the machine order *plus your move*, not a reset).
- **Re-ticking** → an explicit, undoable re-sort that discards the manual arrangement and returns to autopilot.
- **Manual is the *absence* of the tick** — there is no "Manual" item and no "you are now in manual mode" announcement.

**The verb is load-bearing: "Keep … Sorted by", never "Sort by".** A checkmark on the imperative "Sort" is a category error — a tick means "this state is on," but "Sort" reads as "a thing I press," so its absence would read as *unsorted/broken*. "*Keep* … Sorted by" is a durable state: the tick reads right, and its absence reads as "no longer keeping it sorted" = you arranged it. Don't let it shorten to `sort.themes` when the locale key is written.

This is the whole model, and its elegance is the point: the auto/manual state is *real* but never a **noun** the user has to learn. It's expressed through two concrete things the user already looks at — *is there a tick?* and *are the items where I left them?* — Tesler's "don't mode me in" satisfied by making the mode legible in the objects, not by removing it. Two tick-or-not items; no mental model to teach beyond "my stuff stays where I put it, and I can ask for an order back."

**The one rule under the hood that keeps this honest:** `sort_key = null` (no tick) must be a **committed, durable state**, never "unset → fall back to default." If `null` is read as "no preference, apply the default sort," an unrelated event (a re-analysis, a reload) silently re-sorts the researcher's arrangement — the exact failure documented at Adobe Bridge (Appendix). The invisible state must be the *most explicit* thing in the schema precisely because the UI hides it.

**View = intent (the grid/list split).** Form is free legibility: a table's columns *are* its sort menu (you predict alpha/date/size without checking); a canvas's emptiness *is* its "just where I put them" signal. Our masonry card grid advertises *neither* — its form reads "a structured document, read me," and is silent on sort/arrange. So the card grid is the **album** (manual-first, drag = reorder, the narrative surface); if we later want a sort/triage surface it should take a **list/table form** (the Library — always sorted, columns do the legibility for free), rather than bolting signage onto an ambiguous grid. Photos ships exactly this Library-vs-Album split.

**The chrome — where the control lives** (settled against a native-macOS review):
- **Primary, both surfaces:** a **block-header caption** — *"Arranged by strength of evidence"* in auto, **absent** in manual (the missing caption mirrors the missing tick) — plus a **right-click toggle on the block header**. The caption is the persistently-visible label a menu checkmark can't be; it delivers "the researcher sees *why* it's ordered this way."
- **macOS also mirrors it in the View menu**, next to the existing `All Quotes / Starred Quotes Only` filter and `Show Heatmap` — because every command must be menu-bar-reachable. **Two checkmarked items, not a submenu** (one order per axis). The menu is the *mirror*, not the home.
- **Web (serve):** the same caption + an in-content toolbar control (no menu bar).
- **Dim vs. omit:** the menu-bar item **dims** when its axis is absent (a whirlpool study with no sections greys "Keep Sections Sorted…", like `Show Heatmap` does); the caption and context menu simply **omit** it.
- **Not the toolbar** — sort is set-once, so it doesn't earn toolbar prominence; *filter* does ([`design-quote-filtering.md`](design-quote-filtering.md) §5).

## 5. What "automatically" means — one machine order per axis ("What Bristlenose thinks")

v1 offers **one** machine order per axis, *not* a menu of keys — a single honestly-labelled opinion the researcher accepts or overrides. (Breadth / contention / intensity as *selectable* lenses were considered and dropped for v1; a possible v2, or never.)

**Themes → "Strength of evidence."** Broad + strong + *aligned* — reach weighted by agreement, plus intensity. Naming it "Strength of evidence" is what makes it honest: the label says *opinion*, not neutral fact, so Bristlenose is licensed to use its best blended judgement (the same maths behind the Analysis lens's Signal, but **not** branded "Signal" here) without claiming objectivity. Its known bias: it **leads with well-corroborated consensus and pushes contested themes down** — a defensible "lead with what's defensible" philosophy, and safe because it's overridable *and* because the algorithm can improve underneath (toward contention-awareness) with **zero UI change and zero migration** — there's no user-facing sort key to commit to.

**Sections → "Most common sequence."** The order the most participants actually followed — computed **empirically from per-participant traversals**, not from an LLM guess at "logical product flow" (which confabulates for self-directed whirlpools). "Most common sequence" is honest for both linear and whirlpool studies (there is always a modal ordering, however weak); the name enforces the empirical computation. Today's `display_order` is the LLM's flow guess — so this is a correctness improvement, not just a rename.

Both are **axis-appropriate**: sections are *sequential*, themes are *evidential*. "What Bristlenose thinks" is the honest umbrella; the researcher never needs to know the internals differ.

**Quotes within a group** keep a machine default order but get **no toggle** (§8). The atom is a **run or a singleton** (a run = one participant's consecutive quotes, adjacent `segment_index` via `detectSequences()`); within a run, order is **always time**; between atoms it's **time** for sections (local timeline) and **strength** for themes (no shared timeline). `Quote.intensity` (1–3, `models.py:281`, *"kept for future use"*) is where strength graduates. **Starred quotes float above all.**

## 6. Data structure — fractional string ranks

The research is unanimous (Appendix): **integer position columns cascade** (moving item 10→2 = 9 writes, O(n)); **sparse-integer gaps exhaust** (~100 inserts); **float midpoints exhaust IEEE-754 precision** (~50 bisections at one spot). The production-proven answer is **fractional indexing with sortable *string* keys** — Figma (base-95 strings), Atlassian LexoRank — where insert-between is a single write and a string can *always* be found between any two distinct strings, with effectively unlimited headroom (occasional rebalance when keys grow long; at our scale — dozens of groups — deferrable indefinitely).

**Concretely:**
- Add a `rank` string column to `ThemeGroup` (has nothing today) and `ScreenCluster` (migrate its int `display_order`, or run `rank` alongside). One migration. Render `ORDER BY rank`.
- Add `sort_key` (nullable) per axis per project: `set` (the axis's single machine order on — `strength` for themes, `sequence` for sections) or `null` = committed manual. Effectively boolean; the *order* is computed, not chosen from a menu.
- Reorder = compute a rank between the drop neighbours; **one write**. No renumber.
- Interleaving (the one unsolvable-in-general fractional-index problem) is **collaborative-only** — inert for a local-first single-user tool. Use plain fractional indexing (rocicorp-style `generateKeyBetween`); do **not** add CRDT machinery. (Two windows on one serve process is the only edge; a per-client suffix on the key is cheap insurance if ever needed — not v1.)

## 7. New-item policy — it falls out of the mode

The hardest question — *where do newly-emerged groups from re-analysis go in a manually-arranged list?* — the research says **no surveyed app solves**, because none re-ingests data that regenerates the structure behind the user. Photos answers the *shape* of it, and the answer is: **the mode decides.**

- **Automatic (`sort_key` set):** new groups **sort in** by that key. Correct, because the researcher *delegated* order to the machine — there is no manual commitment to protect.
- **Manual (`sort_key = null`):** new groups **append** to the end and carry the existing green **New** badge; the arranged sequence is untouched.

This is exactly consistent with "never silently reshuffle a human commitment": in auto mode there *is* no commitment. So we don't invent or A/B the core rule — Photos proved it reads correctly to millions.

**The invariant that is genuinely ours** (the bit past Photos): a re-analysis must **never flip `sort_key`** and **never re-sort a `null` (manual) axis** — it appends and flags New. This is the same "importer only appends" rule from §2, now covering `rank` and `sort_key`.

**Append vs. staging tray.** Append + New badge is v1 (one list, reuses the badge). A distinct "new / unplaced" tray (like the existing read-only Uncategorised floor, one level up) is the escalation if new-group *volume* per ingestion proves annoying. Because insertion is a *render* over one storage (ranks + New flag), all three placements — append, tray, machine's-best-slot — are A/B-testable without schema churn.

**How new items behave across the operations** (walking the cases the prototype exercises):
- New theme (below the 0.5 membership / anchor threshold) → new id → append (manual) or sort-in (auto) → **New** badge. ✅
- Renamed/human-created theme → id preserved by the anchor matcher / never machine-touched → stays put. ✅
- **Split** (importer keeps the id on the majority child) → majority keeps rank & stays; the shard is a new id → appends as New. ✅
- **Delete + resurrection** (accepted risk) → a resurrected theme is a *new* id → appends at the end as New, maximally non-intrusive; the researcher spots it and re-dismisses. No tombstones in v1. ✅
- **Merge** → the survivor inherits one existing id's rank; the other id empties. If it was renamed/reordered it persists as a **0-member husk** at its old rank (surface "merged into X", let the researcher delete it). **This is the one genuine sharp corner** (§11).

## 8. Per-operation feasibility & phasing

| Phase | Operation | Cost | Notes |
|---|---|---|---|
| **A** | **Send-to move** | 🟢 UI only | `/reassign` + `reassignQuotes()` client wrapper **built, uncalled**. Wire to the existing multi-select. The single highest-value slice; the designed Phase-0 picker |
| **B** | **Create + delete researcher containers** | 🟡 | mint/delete routes (`created_by="researcher"`); "New theme from selection"; delete-with-confirm; orphans → Uncategorised floor. Ship the **theme `rank` migration here** so themes have an order the moment humans can create them |
| **C** | **Drag quotes (within axis)** | 🟠 | add a DnD layer (dnd-kit — keyboard-operable, tree-shakeable; no DnD lib today). Drag calls the same `/reassign`. Cosmetic upgrade to A |
| **D** | **Reorder groups + the "Keep Sorted By" model** | 🟠 | `rank` + `sort_key` + the two checkmarked "Keep … Sorted by" items + block-header caption + drag-to-manual. The full ordering model. Heaviest, but the payoff |
| **E** | **Cross section↔theme move** | 🟠 | researcher-owned `quote_type` (a third ownership field, same pattern) + cross-table move. **Instrument the crossing rate** — frequent crossing is a signal the two-pool taxonomy isn't matching how researchers think |

**Reorder quotes within a group** rides Phase D's rank machinery (ranks on the join rows instead of containers). The one design problem is coexistence with sequence detection: **the draggable atom is a detected run *or* a singleton** — you reorder runs and singletons; inside a run, order stays time. Do not allow a drag to shatter a detected run (that's not researcher freedom, it's losing a feature). It gets **no auto/manual toggle** — dragging a quote makes that group's quote-order manual; a quiet *Reset order* restores the machine default. The per-group manual state is a data flag (protected by the same importer rule), not a menu tick.

**Build sections before themes** throughout: section identity is stable (ARI ~0.96), a section's `New` is trustworthy, and sections already have the order column. Themes (ARI ~0.43) make both "is it new?" and "where does it go?" genuinely harder — prove the loop on the easy axis first, same code.

**Everything is export-gated.** New controls must respect `isExportMode()` at all three layers (store mutator bails, affordance hidden, API no-ops) and consider `isEmbedded()` for the native shell. The offline export is read-only by contract.

## 9. Mental-model arc — why this phasing (the part that rots first)

Our audience is UR veterans; their priors are **affinity mapping / card sorting** (Miro, FigJam) and **spreadsheets**. Two distinct things:

- **What they bring on arrival:** the grouped-cards-under-headings form reads as a **structured report** — first instinct is *read & judge*, not touch. The **affinity/card-sort** reflex fires on first *touch*.
- **What the task grows into** (the reach-for order): filter/star (triage) → move a mis-grouped quote (fix) → make my own group (cluster) → reorder for the story (synthesis) → re-tidy (arrange-by). *This is the phasing above, arrived at independently.*

**The one dangerous mismatch:** the strongest prior (Miro free-canvas, spatial permanence) is the single model our masonry grid *can't* honour — it reflows, so there is no stable XY. A drag therefore means **reorder in the sequence (ordinal), not pin to a pixel** — which is the only thing it *can* mean, and exactly what fractional ranks store. Teach it through the drag feedback: an **insertion line between cards, neighbours parting** — so the gesture reads "insert into sequence" at the moment the Miro reflex fires.

**The reframe that dissolves the risk:** the quotes grid is a **synthesis surface, not an exploration surface**. Free-canvas affinity is the *clustering* phase — and the machine already did that. The human's job here is the *next* phase, synthesising clusters into a narrative, which is inherently ordinal. The ordinal model meets the *later stage* of the researcher's own method rather than fighting it.

## 10. Failure modes to design against (from the research)

Real, documented bugs in shipped software — each is a thing our design explicitly prevents:

- **Adobe Bridge: renaming a collection silently reset the manual sort to filename order.** An *unrelated operation* destroying manual order — literally our re-analysis hazard. Prevented by: `sort_key=null` is a committed state, and the importer never re-sorts it (§4, §7).
- **PrimeFaces / MUI-DataTables: after a data refresh the header still *showed* a sort the data no longer had.** A lying mode indicator. Prevented by: after re-analysis the tick must still reflect reality; the indicator is the sole mode signal, so it must never lie.
- **Insomnia: manual order silently reverted to default on restart.** Persistence-of-mode is the most-complained-about failure. Prevented by: `rank` + `sort_key` persist and survive re-runs as rigorously as joins/edits already do.

## 11. Open questions (to decide / to test)

1. ~~Theme default order~~ — **resolved:** one machine order, *Strength of evidence* (§5); no selectable-lens menu in v1. Selectable lenses (contention, intensity…) are a possible v2.
2. **The merge husk** — surface "merged into X" and let the researcher delete the empty group (recommended), or auto-retire a human-owned group once fully merged away (violates the commitment model — no). §7. *Decide.*
3. **New-item placement in manual mode** — append vs. a staging tray. Render-level, so A/B-testable on one storage. §7. *Test.*
4. **The re-proposed-structure reconciliation** — when a full re-analysis re-proposes *both* grouping and order, is manual authoritative (machine order applies only to net-new — our answer) or does the researcher want a reconcile/merge view? *No surveyed app handles this — genuinely novel — prototype and test.* This is what [`mockups/editable-themes-prototype.html`](mockups/editable-themes-prototype.html) is for.

---

## Appendix A — decision log (the settled spine)

1. Researcher-created containers: **yes** (`created_by="researcher"`) — they hold insight the text analysis can't reach.
2. Order persists — object permanence + storytelling; a manual arrangement is a commitment.
3. **One** ordering system for both axes and both sources (machine / human) — no per-axis fork.
4. Order-ownership: **importer only appends, never rewrites a touched rank** (mirrors researcher joins).
5. **Fractional-index string keys** (Figma/LexoRank) — not floats (they exhaust), not integers (they cascade).
6. Interaction: **Photos "Keep Sorted By"** — **binary, one machine order per axis** (not a key menu); tick-or-not; drag → manual (inherits current order); re-tick → resort. Manual = the unticked absence. No named modes. Verb is **"Keep … Sorted by"**, never "Sort by".
7. `sort_key = null` is a **committed, durable manual state** — never "unset → default".
8. New-item policy **falls out of the mode**: auto sorts in, manual appends + New.
9. Machine order is **live until first touch, then frozen + append-only**.
10. Within a group: **run-atomic, time inside the run**; between runs, time (sections) / strength (themes); starred floats up. `Quote.intensity` finally does a job. Quote reordering gets **no toggle** — modeless drag + *Reset order*.
11. **View = intent / form = legibility:** card grid = album (manual-first); a future list view = library (always sorted).
12. Cross-axis move and reorder-quotes-in-group are **in scope but later** (Phases E, D+), same ownership pattern.
13. Everything **export-gated** (`isExportMode()` / `isEmbedded()`).
14. Interleaving/CRDT concerns are **out of scope** (local-first single-user).
15. **Build sections first, themes second** (stable identity, existing order column, trustworthy New).
16. The two machine orders: **themes → "Strength of evidence"** (reach × agreement + intensity; leads with consensus, buries contention, overridable, improvable-without-UI-change); **sections → "Most common sequence"** (empirical from per-participant traversals, replacing the LLM flow guess).
17. Chrome: **block-header caption** (auto only) + **block-header right-click** are the primary control on both surfaces; **macOS mirrors two checkmarked items in the View menu**; menu **dims** when an axis is absent, caption/context **omit**. Sort is *not* in the toolbar (filter is).
18. Only **reordering groups** unticks, and only that axis. Moving a quote (same-axis or cross-axis) is membership and unticks nothing.
19. **Filter is a sibling** ([`design-quote-filtering.md`](design-quote-filtering.md)): the other half of the Quotes-lens View menu; sort = View submenu (set-once), filter = toolbar popover (frequent).

## Appendix B — research citations (Jul 2026 deep-research pass)

- **Airtable** — "Automatically sort records" toggle; auto-on disables drag, off demotes sort to on-demand: <https://support.airtable.com/docs/sorting-records-in-airtable-views>
- **Figma** — fractional indexing as base-95 strings, average-of-neighbours insert, chosen to avoid float precision loss: <https://www.figma.com/blog/realtime-editing-of-ordered-sequences/>
- **Atlassian LexoRank** — lexicographic string ranks, single-write reorder, 3-bucket rebalance: <https://medium.com/@muhebollah.diu/lexorank-the-string-trick-that-replaces-thousands-of-database-writes-2da4ef21e38a>
- **Fractional indexing** (integer cascade / float exhaustion / string keys): <https://yasoob.me/posts/how-to-efficiently-reorder-or-rerank-items-in-database/>, <https://madebyevan.com/algos/crdt-fractional-indexing/>
- **Interleaving is collaborative-only** (inert for single-user): <https://www.bartoszsypytkowski.com/non-interleaving-lseq/>, Kleppmann et al. PaPoC '19, Fugue (arXiv 2305.00583)
- **Failure modes** — Adobe Bridge rename-resets-sort; Insomnia sort-lost-on-restart; PrimeFaces/MUI lying-sort-indicator (issue trackers, verified during the research pass)
