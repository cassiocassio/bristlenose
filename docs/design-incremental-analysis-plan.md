# Incremental analysis — build plan (Level 2: add sessions + reprocess non-destructively)

**Status:** Reviewed build plan (8 Jul 2026 — self-critique + William/scope + Bach/test-layer). **Scope = level 2 only:** add a new interview to an already-analysed project, reprocess (cache-hit existing, fresh on the new one), and researcher curation (stars, named themes/sections, tags, edits) survives. **Not** level 3 (saturation surfacing / smart theme-recompute / locked codebook), **not** the reassignment "Move to" UI.
**Parent (the what/why):** [`design-incremental-analysis.md`](design-incremental-analysis.md) — thinking doc. This is the *how*, grounded in a code trace.
**Why now:** the cohort call protocol makes incremental add the **spine of the TF experience** — each call adds a session; "sees own quotes fold in, stars intact" is the beat. So level 2 is TF-relevant, not just Beta.

## Headline

The non-destructive data layer is **done and tested at the importer seam.** The whole beat collapses to **one desktop button + one completion message + one mocked test + one written-down caveat.**

## Already built (trace verdicts, 8 Jul 2026)

- **Pipeline reprocess ✅** — the 4 costly per-session stages (transcribe, speaker-id, topic-seg, quote-extraction) cache-hit existing sessions via `get_completed_session_ids` (`bristlenose/pipeline.py`); the new session runs fresh. Extract-audio / merge / PII re-run wholesale but are cheap/local (**no LLM re-cost on existing sessions**); clustering/theming re-run over the full corpus by design.
- **Re-import + curation survival ✅ (tested)** — `import_project` is idempotent; freeze (`_pinned_quote_ids`), section-identity-by-membership, star-anchor named-theme identity, strand protection (`bristlenose/server/importer.py`). Proven by `tests/test_serve_importer.py::TestReimportAddedSession` (stars s1, adds s2 → star survives **and** new quote appears).
- **Observability + SPA refresh ✅** — `sessions_new`/`sessions_cached` telemetry, the uncategorised-floor completion surface, and `LastRunStore.ts` polling `last-run` → islands refetch → stars persist from the DB.
- **CLI path ✅ complete** — re-running `bristlenose run <folder>` after dropping a file cache-hits existing + processes new. This is the demoable beat *today*.

## Descoped, with an explicit boundary

**Star-anchor re-extraction robustness (the 94.6% / ~9% fragile-tail finding) is OUT of level 2.** It is a *re-extraction* concern; the add path cache-hits existing sessions so their quotes are **byte-identical** and stars sit on unchanged anchors (`design-incremental-analysis.md:594` — a quote's boundaries depend only on its own transcript; you can *see* there's no drift, not merely trust it).

**Boundary decision (written down, per the scope review):** if the researcher **edits a transcript** before adding, that session's cache invalidates → it re-extracts → the fragile tail reappears *for that session*. This is accepted/deferred; `design-incremental-analysis.md:435, 583` already carry the confirm-dialog caveat copy. **Not covered — the note is the coverage.** Do not claim "stars always carry losslessly" without this qualifier.

## Workstreams (reviewed)

- **A — Prove the beat via the CLI (free; do first).** The CLI path is complete, so the beat is observable now: `bristlenose run <folder>` (2 interviews) → `bristlenose serve <folder>`, star ~3 quotes + name a theme → drop a 3rd interview into the folder → `bristlenose run <folder>` again (watch `(cached)` on old sessions, `(N new sessions)` on the new) → refresh: new quotes fold in, named theme keeps its name, stars intact, any drained-theme star lands in the Uncategorised floor. This is the gap-finder and the demo.
- **D — Wire the desktop "Update analysis" action (the only new capability).** Point `NewFilesSheet` (and/or the drop-on-analysed path) at the existing `PipelineRunner.start` (`bristlenose run <folder> --no-serve`); resume computes the delta itself. **No `--files` flag** — speculative generality for one caller when `get_completed_session_ids` already owns the delta (Rule of Three). **Don't let a cost-preview sheet creep in — the button *is* the beat; the price tag is polish.** Fold E in here.
- **F — Verb + completion message (minimal; already specced).** "Update analysis" + a "+N sessions added, your curation kept" completion. Lighter than the old destructive-register "New analysis…" NSAlert — curation now genuinely survives. Translate `design-incremental-analysis.md:554`, don't relitigate.
- **C — One mocked-LLM pipeline round-trip test (owed, not creep — commit `a8126ffb`'s own message names "a mocked-Whisper integration test asserting new_sessions==1 on a real incremental run" as the deliberate remaining gap).** It's the right layer (the invariant is "the ~6 stage-wiring call sites in `pipeline.py` compose correctly," which requires driving `pipeline.py`). Bach's tightest version:
  - Feed **pre-existing transcripts** for both sessions (ingest accepts transcripts → no Whisper mock needed). Mock **only** the 4 LLM call sites at `LLMClient.analyze()` — reuse the `tests/test_pipeline_abandon.py` pattern, don't invent a harness.
  - **Assert (1):** the old session's `extracted_quotes.json` entries are **byte-identical run1→run2**, and the LLM mock is **not called** for the old session on run 2 (the real behavioural claim — this is the resume→importer join that stars ultimately depend on, and nothing else proves it).
  - **Assert (2):** `sessions_new == 1` / `sessions_cached == N` + `reflow_scope` on the **real emitted events**, not hand-called ones.
  - **Don't** assert wall-clock/timing (tautology), and **don't** assert clustering/theming output stability — stages 10/11 rerun over the full corpus by design (`_cg_input_hashes` includes the new quote), so their output *should* drift.
- **E — folded into D** as one add-fails-mid-run assertion. The dangerous half (silently loading corrupt cache) is already defended (`_load_cached_json` tolerance + `test_cache_skip_fails_when_stage_running`). A SIGINT-mid-add corruption test is a **named ticket if the cohort hits it**, not a blocker.

## Sequencing

A (today) → C (lock the seam) → D (+E) → F.

## Scope boundary

- **In:** add + reprocess + curation survives; desktop-triggered and CLI-triggered.
- **Out:** star re-extraction robustness (a Rebuild-Report concern); level-3 saturation surfacing / smart theme-recompute / locked codebook; the reassignment "Move to" UI; a SIGINT-mid-add corruption test (ticket only).

## Review provenance

Self-critique + `what-would-william-of-ockham-say` (scope: descope upheld with the written-down caveat; C trimmed from live to mocked; D parsimonious; E folded; watch cost-sheet creep) + `what-would-james-bach-say` (test layer: C is the right layer *and* pre-agreed per `a8126ffb`; exact tightest assertions above; clustering-determinism would be the wrong invariant). 8 Jul 2026.
