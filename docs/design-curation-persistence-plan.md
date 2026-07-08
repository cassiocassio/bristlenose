# Curation persistence — implementation plan

**Status:** Implementation plan, evidence-backed (Jul 2026). _Phases 1–3 (Freeze, Section identity, Themes + "New" flag), the named-group retire-exemption, the read-only Uncategorised floor (render + API), and Phase 0's **write path** (reassign endpoint + importer researcher-owned suppression + freeze-on-move; `test_curation_roundtrip.TestManualReassignment`) are **built and green** on this branch. Remaining: Phase 0's **picker UI** — its UX decisions are `design-manual-reassignment.md` §5._
**Model doc:** [`design-curation-persistence.md`](design-curation-persistence.md) — the *what/why* (state engine, principles, rules). This doc is the *how*: phasing, code-grounded steps against the live serve stack, and the build/review process.
**Parent:** [`design-incremental-analysis.md`](design-incremental-analysis.md).
**Evidence:** the Jul 2026 experiment thread (stats-only summaries in the parent). Load-bearing findings: sections converge (ARI 1.0 under growth), themes diverge (ARI ~0.4, never saturate — not a count artefact), freeze de-scopes the recovery gate, and the incremental "what's new" summary is a *new-material gate + one semantic pass* (below).

---

## Decisions carried in (condensed)

1. **Freeze-on-human-state is the core.** `starred ∨ edited ∨ tagged` → durable ID + frozen verbatim form; never re-derived. Uniformly, no mark-triage. Frozen form = the words.
2. **Hide = best-effort suppression** (not a pin). Accept ~5% reappearance.
3. **Membership is identity for sections** (they converge) — durable machine-side identity worth building. **Themes get best-effort labels only** (they diverge) — the only durable handle is human commitment.
4. **Presence (human, absolute) vs prominence (machine, fluid).** Never silently reshuffle a commitment; surface it. Object permanence beats theoretical accuracy.
5. **"What changed after an incremental run" = new-material gate (M3) + one semantic LLM pass (M1).** Reliable for *sections*, *new quotes*, *anchored themes*; **not** for narrating fluid-theme identity.
6. **Count target (7–12) is reportability, not stability** — a separate prompt fix.
7. **Manual re-assignment is the prerequisite commit-gesture** (independently valuable; already on the board).

---

## Phasing

| Phase | Delivers | Depends on | Code weight |
|---|---|---|---|
| **0 — Manual re-assignment** | Drag / multi-select send-to section&theme | — | medium (mostly UI) |
| **1 — Freeze** | Marked work (star/edit/tag) never vanishes across re-runs | — | **medium — self-contained, highest leverage** |
| **2 — Section identity** | Renamed sections survive label drift; new/updated detectable | 1 | **high — the migration** |
| **3 — Themes + "New!"** | Best-effort labels; snapshot-on-rename; incremental "what's new" flags | 1 (+ 0 for surfacing) | low–medium |
| **Separate** | 7–12 count target · skim-efficiency family | — | low · out of scope |

Phases 0 and 1 are independent (parallelisable). 1 delivers the promise on its own. 2 is the real engineering. 3 is deliberately small.

---

## Phase 1 — Freeze

**Status: implemented (Jul 2026).** Data model, importer exemption, minting, migration 003, and the round-trip contract are built and green (full suite passes). Two refinements surfaced during the build — see **Build notes** at the end of this section. Deferred (rendering, not the persistence contract): the **frontend render** of the "uncategorised" floor — the read-only API bucket + named-group retire-exemption shipped later on this branch (see model doc §6/§12), so orphans are surfaced by `GET /quotes`; only the React section that displays them remains — and preferring `frozen_form` at display time. Below is the plan as built.

**Goal:** any quote the researcher touches **continues to exist** across re-runs — durable ID, frozen form, guaranteed present. Phase 1 promises *survival*, not *location* (see the boundary note below). This alone delivers the core promise and de-scopes the "≥90% recovery" gate (the matcher stops governing marked quotes).

**Survives ≠ stays where they put it (the phase boundary).** Object permanence has two guarantees, and Phase 1 delivers only the first:
- **Survives** (Phase 1): a quote with any human work is *present in its frozen form after every re-run*, full stop. This is the cleanup pin-exemption below.
- **Stays where they put it** (Phases 2 + 3): keeping that quote *in the section/theme the researcher associates it with* is a separate problem. Sections converge, so Phase 2's membership-based identity holds it in place; themes diverge, so a starred quote's theme only persists once the theme itself is committed (Phase 3's snapshot-on-rename). Absent those, Phase 1 still guarantees the quote *exists* — a reshuffled fluid theme may leave it on the quotes page as "uncategorised" (the floor).

Don't let Phase-1-alone read as "my quotes stay in their themes." It keeps them *alive*; staying *in place* is the later work.

**Data model** (`bristlenose/server/models.py`):
- `Quote.durable_id` — **project-scoped** UUID, minted on first human touch (never cross-project; a project-scoped table per multi-project rules).
- `Quote.frozen_form` — verbatim text captured at pin time (**a re-identification key** — must be excluded from the export/anonymisation boundary, like `pii_summary`).
- **`is_pinned` is derived at query time, never stored.** `is_pinned = is_starred ∨ is_edited ∨ has_tag` (human tag: `QuoteTag.source = "human"`, not a proposed tag). The **only** new stored columns are `durable_id` + `frozen_form`; there is no physical `is_pinned` column. Reuse the existing `source` / `assigned_by = "researcher"` vocabulary — do **not** invent a third discriminator.
- **Why derive, not store:** deriving makes un-pinning automatic and correct. Protection lasts exactly as long as human work exists on the quote — revert the edit, unstar, strip the tags, and the next read computes `is_pinned = false` with no flag to clear. A stored flag that only ever flips *true* would pin an un-starred quote forever. Two keys must turn before a quote is reclaimed: **the human let go** *and* **the machine didn't re-emit it**. Neither alone reclaims it.

**The urgent mechanism — pin-exemption in stale-cleanup** (`importer.py` `_cleanup_stale_data`, ~:1063; delete predicate ~:1084):
- Today it deletes any `Quote` with `last_imported_at < now`, cascading to `QuoteState`/`QuoteTag`/`QuoteEdit`. A frozen quote the pipeline doesn't re-emit looks stale → **gets deleted with its star.** Exempt pinned quotes from the delete. Since `is_pinned` is derived, this is a `NOT EXISTS`/`LEFT JOIN` against `QuoteState` (`is_starred`), `QuoteEdit`, and human `QuoteTag` — **not** a literal `is_pinned` column compare (don't add one by reflex). *This is the first thing to build and the round-trip test's first assertion.*

**Minting site** (`bristlenose/server/routes/data.py`): the `PUT /starred`, `/edits`, `/tags` handlers mint `durable_id` + snapshot `frozen_form` on first human touch. (Note the current `_resolve_quote` DOM-id range-match — minting must attach to the resolved quote row, then that row becomes matcher-independent.)

**Matcher role flips:** for pinned quotes the position-overlap/text matcher runs only to **dedup** a re-extracted near-duplicate against the frozen copy (worst case: a transient duplicate, benign). For fluid quotes it's best-effort carry (unchanged stakes). No blocking recovery-rate gate.

**Hide:** best-effort re-match on re-import; accept the ~5% reappearance (documented). No freeze.

**Quotes-page floor:** a pinned quote with no current section/theme surfaces on the quotes page ("uncategorised") — falls out of freeze for free; nothing to build beyond not-filtering-it-out. *Verify this before trusting it:* confirm the `quotes.py` grouping actually surfaces unassigned quotes rather than dropping them. If it filters them out, that's a small API/frontend touch Phase 1 must include, not assume.

**Migration:** two additive columns only — `durable_id` + `frozen_form` — backfilled for quotes already touched (a `QuoteState.is_starred` / `QuoteEdit` / human `QuoteTag` row exists). No `is_pinned` column to add or backfill — it's derived. Mind the Alembic gotcha (server/CLAUDE.md): `create_all()` + `stamp("head")` skips data transforms on fresh DBs — guard the backfill.

**Test — the round-trip (the executable contract):** star N / edit M / tag K / hide J → re-import with drifted boundaries → assert every pinned quote present in frozen form with its marks; hidden still hidden (documented miss-rate asserted separately). Lives in `tests/test_curation_roundtrip.py`. No "passes most of the time." Migration backfill has its own file-based test in `tests/test_curation_migration.py` (the in-memory path stamps head and never runs `upgrade()`).

### Build notes (what the code does, and two refinements found while building)

1. **The pin tag-arm is "genuinely manual" only — and sentiment tags were a landmine.** Tags come in three provenance tiers, and only the last is researcher commitment:
   - **Sentiment** — automatic LLM output, on by default, never chosen (`source="pipeline"`). *Doesn't pin.*
   - **Framework picked + reviewed via the histogram** (AutoCode, codebook-builder) — the researcher chose the framework and ratified applications, but tentatively, machine-proposed (`source="autocode"` / `"codebook-builder"`). *Doesn't pin* — ratifying a suggestion isn't authoring.
   - **Genuinely manual** — hand-typed/applied (e.g. "User prefers design B"), `source="human"`. *Pins.*

   The predicate is `source == "human"`, so it lands exactly on the manual tier; the middle tier falls out for free because AutoCode/codebook-builder stamp their own source. The landmine: `importer._auto_tag_from_sentiment_field` created sentiment `QuoteTag` rows with the column-default `source="human"`, so a naive predicate would pin *almost every quote*. Fix shipped: (a) the importer now writes sentiment tags as `source="pipeline"`; (b) migration 003 relabels existing mislabelled rows; (c) `_pinned_quote_ids` *also* excludes the sentiment framework by join (`framework_id != "sentiment"` OR NULL) — belt-and-suspenders for old DBs, and it encodes the deliberate call that sentiment is the automatic tier *as a whole* (even a hand-applied sentiment tag doesn't pin). The derived pin set is `starred ∨ edited ∨ human-non-sentiment-tag`.

2. **Freeze protects against re-extraction drift, NOT against session removal (governance boundary).** The exemption is scoped to quotes whose **session is still present** in the import. If a whole interview is removed from the folder (deleted recording, **consent withdrawal**), its quotes — pinned or not — are deleted, because the source is gone and governance requires it. This preserves the existing "removed session → state cleaned" contract *and* the Freeze guarantee: same session + drifted quote → protected; session gone → removed. Asserted by `test_freeze_does_not_survive_session_removal`.

Both refinements are consistent with the model doc's principles (uniform freeze on human-state; consent-gradient governance). The `is_pinned = derived` decision (see Data model) makes un-pin automatic and is what lets #2 be a clean session-membership check rather than a stored-flag reconciliation.

---

## Phase 2 — Section identity

**Goal:** a renamed section keeps its name through label drift, and we can classify each section new/updated. Sections converge (ARI 1.0), so membership-based identity is trustworthy.

**The bug (confirmed):** section identity is the *label*. `importer.py:785` upserts clusters by `(project_id, screen_label)`; `HeadingEdit.heading_key = "section-{slug}:title"` (slug from label, `models.py:508`); the frontend re-derives the anchor from the label (`QuoteSections.tsx:212`) while *holding* `cluster_id` (`:215`) and discarding it. Label drifts → new `cluster_id` → orphaned rename. **The "cheap re-key on cluster_id" does not work** — `cluster_id` is itself label-derived.

**The fix — membership-based section identity:**
1. **Importer upsert by membership, not label** (`importer.py` cluster import, ~:783). Match an incoming cluster to an existing one by majority quote-overlap (≥ threshold); keep the existing `cluster_id`; update the label. Sections converge, so this is a clean majority match almost always. Splits/merges (rare at 0.96): majority child keeps the id; surface a merge conflict.
2. **Re-key `HeadingEdit` on `cluster_id`/`theme_id`** (the durable id), now that the id is stable across drift. Data-migrate existing slug-keyed rows where reconstructable; for already-drifted projects that can't be reconstructed, accept a one-time loss (documented).
3. **Frontend:** stop deriving the anchor from the label — use the `cluster_id`/`theme_id` the payload already carries (`QuoteSections.tsx`, `QuoteThemes.tsx`; API already returns them, `quotes.py:391,414`).
4. **Custom-name carry** rides for free: the name is a `HeadingEdit` on the durable id.

**Migration (6 coordinated touches):** (a) `HeadingEdit` re-key + data migration; (b) importer membership-upsert; (c) frontend anchor derivation (2 islands); (d) `PUT /edits` heading branch (`data.py:377`); (e) the Phase-1 `is_pinned` columns (shared); (f) the exact-float→overlap quote key if not already done in Phase 1's matcher. Each data step needs the fresh-DB Alembic guard.

**Test:** rename a section → re-import with the label drifted → assert the custom name still shows on the same section; a genuinely new section (mostly new quotes, no predecessor) classified new.

---

## Phase 3 — Themes: best-effort + snapshot-on-rename + the "New!" flag

Themes diverge (ARI ~0.4, count 9→21, unfixed by a count cap) — so **no durable machine-side theme identity.** Three small pieces:

**3a. Best-effort labels.** Themes regenerate each run; labels are the machine's, disposable. No membership tracking (proven futile).

**3b. Snapshot-on-rename (name persistence).** When a researcher renames a theme *or* stars a quote in it, **snapshot the theme's quote-set as its anchor** and bind the custom name to it. The theme becomes a human-owned island: its committed set (and especially its frozen star-anchors) stay together; new similar quotes are *suggested* in; the machine re-themes *around* it; a genuine split is *surfaced*, never silent. Substrate is **targeted** — a snapshot fires only on the rare human-commitment event, *not* a full clustering-history log. (Evidence: un-anchored, a renamed 14-quote theme shatters across 3–4 unrelated themes within one ingestion; anchored, it holds.)

**3c. The "New!" flag — incremental "what's new" (this run's finding).** After an incremental run, flag themes for the researcher's attention. UX **TBD**; the *data* mechanism is settled and validated:

- **M3 — new-material gate (deterministic, `session_id`).** Per theme, fraction of quotes from the *added* interview(s). **This is the gate.** `M3 ≈ 0` → the theme is old content re-formed → **quiet**, regardless of label change. *(This kills the "new shiny label, familiar inside" false positive — no new material, nothing new.)*
- **M1 — semantic classifier (one LLM pass).** For themes above the gate, compare current vs previous theme set (labels + sample quotes) → `new_concept` | `restates(prior)`. *(This kills the second false positive — "new quotes, similar ground" → `restates` → grew, not new.)*
- **Combine → three states:**

  | M3 (new material) | M1 (semantic) | flag |
  |---|---|---|
  | high | new concept | **"New!"** — the added interview opened this ground |
  | high | restates | **"Grew +N%"** — existing theme, more evidence |
  | low | any | *quiet* — old content, re-labelled/re-grouped, ignore |

- **Validated (P8→P9):** with M3 as the gate the summary is exactly right — flags "Apache Software Foundation" (50% new + new concept), marks "Non-code contributions" and "Future of open source" as grown, and correctly stays quiet on the 18 re-labelled-old-content themes. *(A first cut with M2/concentration as the trigger came out backwards — it flagged zero-new-material churn as "new" and vetoed the real one; the experiment corrected the measure. M2/concentration is at most a weak tie-breaker, not the trigger.)*

**Data-feasibility rider (a constraint, not new work):** the "what changed" summary is derivable and honest for **new quotes** (`session_id`), **sections** (converge → clean new/updated), and **anchored themes** (snapshot = identity). It is **not** honest for narrating new-vs-updated on the machine's fluid themes — so the summary says *"11 new quotes from Heather Meeker; 6 sections updated; theme 'Apache…' is new; 'Non-code…' grew"* and does **not** assert identity on ungoverned themes.

**Cost:** one extra LLM call per incremental run (the M1 pass); M3 is free.

---

## Separate / parallel items

- **Count target (7–12)** — add the reportability rule to `thematic-grouping.md` (s11 has none). Ships independently; not a stability lever.
- **Skim-efficiency family** (ranking / triage / lost-quotes) — the *other* half of the economics ("make the skim efficient"); its own track, out of this plan.

## Still open (non-blocking)

- Fluid/dedup matcher thresholds (overlap ≥70% + text tiebreaker) — must *work*, no longer a blocking gate.
- Embedding stability for "suggest into an anchored theme by similarity" — un-probed; may need a local/deterministic path.
- The surfacing/flag UX (Phase 0 must exist for the commit gesture).

---

## Build & review process

**Branch strategy.** This is substantial, multi-slice, multi-file work touching Python + SQLite + TS — a genuine case for the worktree exception. Use `/new-branch curation-persistence` (never a hand-rolled worktree). The handoff brief for it = this doc + the model doc.

**Sequence (each phase is its own reviewable chunk):**
1. **Plan review first (plan twice, implement once).** Run `/usual-suspects` on *this doc* (correctness, william-of-ockham, james-bach for the test shape, security for the frozen-text/export boundary, i18n for any new strings). Triage: fix mechanical, park architectural. Then start.
2. **Phase 1 (Freeze).** Build the stale-cleanup pin-exemption + columns + minting **first**; write `test_curation_roundtrip.py` as you go (it's the contract). Then `/usual-suspects` on the diff; the round-trip test is the merge gate. This ships value alone.
3. **Phase 0 (re-assignment)** can proceed in parallel (independent; also unblocks fresh-analysis fixes today).
4. **Phase 2 (Section identity).** The migration is the risk — build the membership-upsert + `HeadingEdit` re-key behind the fresh-DB Alembic guard; extend the round-trip test with a rename-through-drift assertion; `/usual-suspects` (weight security/data-migration + silent-failure-hunter on the cleanup predicates).
5. **Phase 3 (Themes + New!).** Small: snapshot-on-rename + the M3-gate/M1-pass summary; unit-test M3 (deterministic) and pin M1's prompt with a fixture; `/usual-suspects` light.

**Testing spine.** The round-trip test is the executable contract and the per-phase merge gate. The experiment harness (private) provides FOSSDA/section fixtures for the M3 gate and section-convergence assertions; keep those tests deterministic (hand-placed drift, not live re-extraction — CI has no keys).

**Review cadence per phase:** `/usual-suspects` on the phase's diff before merge; fix HIGHs one at a time; final sweep. For the frozen-text and stale-cleanup work specifically, run `silent-failure-hunter` and `security-review` (re-identification-key surface).

**Ship discipline.** Phase 1 is releasable on its own (marked work survives). Don't gate it on 2/3. The count target and Phase 0 ship whenever ready — neither waits on the persistence migration.
