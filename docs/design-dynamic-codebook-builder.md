# Dynamic codebook builder — cultivating a tag into a code

_Design note. Backend foundation shipped; React surface staged. June 2026._

## The idea

Today the manual codebook (`docs/design-codebook-island.md`) lets a researcher
make groups of tags. A tag is just a name — a stamp. You apply it to quotes by
hand, one at a time, and the codebook is a tidy filing cabinet of those stamps.

The pre-built frameworks (Garrett, Norman, UXR) are richer: each tag carries a
**discrimination prompt** — a `definition`, an `apply_when` (inclusion), and a
`not_this` (exclusion). Those prompts are what `AutoCode`
(`docs/design-autocode.md`) reads to suggest a framework's tags across a whole
corpus. But they're hand-authored by an expert and frozen in YAML. A
researcher's *own* tags never get them.

The dynamic codebook builder closes that gap. It turns a manually-applied tag
into a **code**: an entry with operational boundaries the researcher
*understands and owns*, learned from their own judgements rather than authored
in the abstract.

The loop, in the researcher's words:

> I've coded five quotes "prescription cost." Look at what they share. Propose
> what this code means and when it applies. Then go find more like it. I'll tell
> you which of your finds are great — and _why_ — and reject the rest, with
> reasons. Use my reasons to sharpen the definition. Show me the prompt; let me
> edit it directly and watch the set of matching quotes move. By the end, the
> codebook entry isn't a stamp — it's a small framework with a point of view.

## How it relates to what exists

| Surface | What it does | Prompt source |
|---|---|---|
| Manual codebook | Group/name tags, apply by hand | none |
| Pre-built frameworks | Expert taxonomy, fixed boundaries | hand-authored YAML |
| **AutoCode** | Apply a *whole framework* to *all* quotes, one pass | framework YAML |
| **Dynamic builder (this doc)** | Grow *one of the researcher's own tags* into a code, iteratively | _synthesised from the researcher's coded examples, refined by their reasons_ |

AutoCode is "apply this expert codebook." The dynamic builder is "help me build
*my* codebook." They share the same discrimination-prompt vocabulary
(`definition` / `apply_when` / `not_this`) so a tag cultivated here could later
feed an AutoCode-style whole-corpus pass.

## The loop

```
        ┌─────────────────────────────────────────────────────┐
        │  Researcher hand-codes ≥3 quotes with a tag          │
        └───────────────────────────┬─────────────────────────┘
                                     │ synthesize
                                     ▼
        ┌─────────────────────────────────────────────────────┐
        │  PromptDraft: summary · definition · apply_when ·    │
        │  not_this   (one LLM call over the exemplars)        │
        └───────────────────────────┬─────────────────────────┘
              edit ▲ (direct)        │ find candidates
                   │                 ▼
        ┌──────────┴──────────────────────────────────────────┐
        │  Ranked candidates from the uncoded pool             │
        │  (confidence + rationale per quote)                  │
        └───────────────────────────┬─────────────────────────┘
                                     │ review: accept / reject
                                     │ each WITH A REASON
                                     ▼
        ┌─────────────────────────────────────────────────────┐
        │  Accepted → tag applied (new exemplar)               │
        │  Reasons  → refine PromptDraft (one LLM call)        │
        └───────────────────────────┬─────────────────────────┘
                                     │  (repeat until the boundary holds)
                                     ▼
                          A code with a point of view
```

The crucial move is **reject-with-reasons**. An accepted suggestion is a weak
positive (rubber-stamping is easy); a *reasoned rejection* is a strong negative
— it tells the system exactly where the boundary is wrong. That asymmetry is the
thesis of `docs/methodology/tag-rejections-are-great.md`, applied locally and
per-tag. Each reason is a tiny gradient step on the prompt.

## Data model

Two new tables, both additive. Nothing in the existing codebook / AutoCode
schema changes.

### `TagPrompt` — the learned prompt (one per tag)

Instance-scoped, like `TagDefinition` — a code's boundaries are a property of
the concept, reusable across projects.

| Field | Notes |
|---|---|
| `tag_definition_id` | unique FK — one prompt per tag |
| `summary` | one plain sentence: what the exemplars share (researcher-facing) |
| `definition` | what the concept is |
| `apply_when` | inclusion criteria |
| `not_this` | exclusion criteria |
| `version` | `sha256(definition\napply_when\nnot_this)[:8]` |
| `status` | `draft` \| `active` |
| `example_count` | how many exemplars produced the current draft |

`version` is a **content hash**, mirroring the methodology doc's versioning
discipline: the version can never drift from the wording it labels, and a
decision records the exact version it was made against.

### `TagPromptDecision` — each accept/reject, with its reason

Project-scoped via `quote_id`.

| Field | Notes |
|---|---|
| `tag_definition_id`, `quote_id` | what was judged |
| `decision` | `accept` \| `reject` |
| `reason` | free text, **local only** |
| `prompt_version` | the prompt the decision was made against |

**Privacy posture.** The free-text `reason` and the quote it refers to **never
leave the device.** They feed the *local* refinement loop only. This is fully
consistent with `docs/methodology/tag-rejections-are-great.md`, which permits
only opt-in *aggregate rejection rates* off-device — never reasons, never quote
content. The decision log is the per-researcher seed of the documented ten-year
"cultivation ratchet"; the off-device aggregate is a separate, later, consented
layer. `SECURITY.md`'s "nothing leaves your laptop" posture holds unchanged.

## Engine — `bristlenose/server/codebook_builder.py`

Pure helpers (no LLM, unit-tested directly):

- `prompt_version(definition, apply_when, not_this)` — the content hash.
- `build_example_block` / `build_candidate_batch` — numbered quote text, same
  shape as `autocode.build_quote_batch`.
- `format_tag_prompt(draft)` — renders def / apply_when / not_this in the same
  layout AutoCode uses per tag.
- `rank_candidates(verdicts, quotes, min_confidence)` — keep positive matches at
  or above threshold, sort by confidence.

LLM orchestration (one call each, mockable):

- `synthesize_prompt(tag_name, examples, settings, *, current, accepted, rejected)`
  — initial synthesis from exemplars; with `current` + feedback it becomes the
  refine pass. One template (`codebook-synthesize.md`) handles both.
- `find_candidates(tag_name, draft, quotes, settings, min_confidence)` — batches
  the uncoded pool (25/call, bounded by `llm_concurrency`), scores each quote
  yes/no + confidence + rationale (`codebook-candidates.md`), returns ranked
  matches. Per-batch errors are counted, not fatal.

Both prompts wrap untrusted quote text via `wrap_untrusted(...)` and carry the
`<untrusted_*>` system preface, registered in `tests/test_prompt_boundary.py`.

## API — `bristlenose/server/routes/codebook_builder.py`

All under `/api/projects/{id}/codebook/tags/{tag_id}/builder`.

| Method | Path | Purpose |
|---|---|---|
| GET | `…/builder` | state: prompt, coded count, `ready_to_synthesize` |
| POST | `…/builder/synthesize` | infer the prompt from coded exemplars (needs ≥3) |
| PUT | `…/builder/prompt` | direct researcher edits; recomputes `version` |
| POST | `…/builder/candidates` | scan the uncoded pool; ranked preview (no writes) |
| POST | `…/builder/decisions` | record accept/reject + reasons; apply tags; refine |

`/candidates` is a **non-destructive preview** — it never writes. This is what
powers "edit the prompt and watch the set move": edit via `/prompt`, re-scan via
`/candidates`. `/decisions` is the only writing step (it creates `QuoteTag`s for
accepts, logs `TagPromptDecision`s, and optionally refines the prompt in the
same call).

Candidates and decisions speak the same DOM quote-id (`q-{participant}-{tc}`)
the rest of the data API uses, resolved via `routes/data.py` helpers.

## Frontend — staged

Backend-first, exactly as AutoCode shipped. The React surface is a per-tag
"Build" affordance on a codebook tag, opening a panel with three zones:

1. **Prompt editor** — four editable fields (`summary` / `definition` /
   `apply_when` / `not_this`) via `EditableText`. Editing + "Re-scan" calls
   `/prompt` then `/candidates`; the candidate list below updates. This is the
   "see and directly edit the prompts and see the changes to a set of quotes"
   requirement made literal.
2. **Candidate list** — ranked quotes with confidence + rationale. Each row has
   accept / reject, and reject opens a one-line reason field (accept's reason is
   optional). "Refine from my decisions" posts the batch to `/decisions`.
3. **Provenance strip** — `example_count`, `version`, `status` (draft/active),
   and a count of decisions made. Promoting to `active` is the researcher
   declaring the boundary trustworthy.

Design rules carried from the codebook island: contextual confirmation (not
centred modals), `data-testid` from day one, i18n keys in all 7 locales. The
reject-reason field deliberately costs a little effort — per the methodology, we
don't want frictionless judgements.

## Why ≥3 exemplars

Fewer than three coded quotes and the inferred boundary is noise — you can't
generalise a concept from one or two examples without over-fitting to their
wording. `MIN_EXAMPLES_FOR_SYNTHESIS = 3` gates synthesis; the UI shows
"code N more to build this" until the gate clears.

## Testing

`tests/test_codebook_builder.py` — pure-helper unit tests (hashing, formatting,
ranking) plus API tests with a mocked `LLMClient` (`app.state.settings`
override, no network): synthesis persists and gates on exemplar count; direct
edits recompute the version; candidate scan respects `min_confidence` and the
uncoded pool; accept applies the tag + logs the decision + refines; reject logs
without applying. Migration `002` is exercised on the real
existing-DB-without-the-tables upgrade path in `tests/test_migrations.py`.

## Open questions (post-alpha)

- **Whose reasons count more, and how to avoid averaging toward mediocrity** —
  the year-3/4 questions from the methodology doc apply once decisions
  aggregate across researchers. At single-researcher local scale they don't bite.
- **Whole-corpus apply from a cultivated tag** — once a tag has an `active`
  prompt, an AutoCode-style one-pass over all quotes is a natural follow-on
  (the discrimination vocabulary already lines up).
- **Surfacing decision history** — the `TagPromptDecision` log could show the
  researcher how a code's boundary moved over time. Out of scope for the MVP.
