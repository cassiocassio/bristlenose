---
status: partial
last-trued: 2026-09-20
trued-against: HEAD@main on 2026-09-20 (835cde98)
---

> **Status: Partial (trued 2026-09-20)** — the backend engine + API are shipped and
> verbatim-current; the production Build-panel React UI is **still not built**. Two
> things changed under this doc since the June pass and neither is in the body
> below: **the lab's entry point is gone** (the "Codebook lab" button went with the
> v1 lens, so `/codebook-lab` is now reachable only by typing the URL), and **a
> graduation gate has been breached** — see §"Lab graduation gates", which now
> carries the detail and an open question for a human.
>
> _The previous front-matter read `trued-against:
> HEAD@claude/dynamic-codebook-builder-67r2fa` — a branch that no longer exists, so
> that evidence trail was unreproducible. A `last-trued`-driven sweep would have
> read this doc as recently verified against nothing._

## Changelog

- _2026-09-20_ — trued up: re-pointed front-matter at `main` (the cited branch is
  deleted); recorded that `codebook.codebookLab` now has **zero call sites** while
  21 locale files still carry the string, so the lab entry point described
  throughout is gone; corrected "all 7 locales" → 21; flagged the breached
  public-release gate. Every backend claim (§Data model, §Engine, §API, §Testing)
  was re-verified field-by-field and is **unchanged** — `TagPrompt` and
  `TagPromptDecision` match `models.py:100-162` exactly, all five `/builder`
  endpoints match `routes/codebook_builder.py:203,231,272,314,380`, and
  `MIN_EXAMPLES_FOR_SYNTHESIS = 3` holds. Added a note that `TagPrompt` is now read
  by the MCP surface (`bristlenose/server/mcp_server.py:726`), which postdates the
  June privacy discussion. Anchors: `bristlenose/config.py:222`,
  `bristlenose/server/app.py:247`, `tests/test_codebook_builder.py:585-597`,
  commit "codebook v2 becomes the codebook lens: v1 deleted, the icon back, and
  the i18n graduated".

- _2026-06-27_ — trued up: verified data-model / engine / API / testing sections current against the branch code; marked "Frontend — staged" as not-yet-built (only the lab button + project-tags header shipped); confirmed the lab is now flag-gated (`experimental_codebook_lab`, default-on) with a Codebook-tab entry point. Anchors: `frontend/src/islands/CodebookPanel.tsx:976`, `bristlenose/server/routes/dev.py` `codebook_lab_tags`, commits "ship behind … flag", "add entry point", "apply /usual-suspects review fixes".
- _25 Jun 2026 (cloud)_ — initial draft (backend engine + API + lab sandbox).

# Dynamic codebook builder — cultivating a tag into a code

_Design note. Backend foundation + an ugly experiment sandbox shipped (flag-gated,
on by default, reaches the TestFlight cohort); product UX deferred to Figma. June 2026._

> **Direction (revised after the product conversation).** The near-term surface
> is deliberately small and **manual**: surface a tag's `definition` /
> `apply_when` / `not_this` as an **editable, framework-YAML-shaped entry** the
> researcher sees and edits directly, with a **"Process again"** button that
> re-scans the corpus. "Rejecting" a proposed quote isn't a primitive — you
> *edit the entry* (tighten `apply_when`, extend `not_this`) and reprocess to
> watch the proposal drop out. Manual tags stay the default; the machine never
> auto-proposes or auto-applies. **Synthesis from exemplars is an optional
> starting draft, not the headline** — from 50-word fragments it can only guess
> surface commonalities, and the researcher's own context (boss's meeting, team
> channel, post-interview chat) is the gold the machine can't see. The
> **reject-with-reasons → LLM-refine** loop below is the *future automatic
> ratchet* (`docs/methodology/tag-rejections-are-great.md`), kept out of the
> near-term surface. The richer `TagPrompt`/`TagPromptDecision` persistence and
> `/builder` endpoints exist as a staged layer; only the experiment sandbox
> (`/codebook-lab`) is live — now behind the default-on `experimental_codebook_lab`
> flag (ships in plain `serve` + the desktop sidecar for cohort testing, not just
> `--dev`), reached from a "Codebook lab" button in the Codebook tab. It writes nothing.
>
> _20 Sep 2026: that button no longer exists. `codebook.codebookLab` has zero call
> sites in `frontend/`, `bristlenose/` or `desktop/` — it went with the v1 lens —
> while all 21 locales still carry the string as an orphan key. `/codebook-lab` is
> reachable only by typing the URL._

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

> **The prompt text now leaves the app (added 20 Sep 2026).** `TagPrompt` is read
> by the MCP surface — `_tool_get_framework`, `bristlenose/server/mcp_server.py:726`
> — so a bearer-scoped external agent can retrieve the cultivated
> definition / apply_when / not_this for a tag. This postdates the privacy
> discussion below and is worth reading alongside it. The **reasons** in
> `TagPromptDecision` are *not* exposed by that path; only the prompt is. That
> distinction is the one the methodology cares about, so the posture holds — but it
> now holds by a narrower margin than when it was written.

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
layer. Nothing here changes what `SECURITY.md` enumerates as leaving the
machine — the decision log is written to disk and read from disk, and adds no
sixth egress path to that list of five.

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

> **Not yet built (re-confirmed 2026-09-20).** This is the *intended* design, not
> shipped code — verified: zero frontend references to `/builder`, `apply_when`,
> `not_this` or `TagPrompt`.
>
> The June note said "the only React surface that exists today is the lab entry
> point — a 'Codebook lab' button + '&lt;project&gt; tags' header on the Codebook tab
> (`CodebookPanel.tsx`)". **That is now less than it was:** `CodebookPanel.tsx` was
> deleted in 0.29.0 and took the button with it. Only the header survives, at
> `frontend/src/components/TagSidebar.tsx:330` and `CodebookV2Sidebar.tsx:234`. The
> per-tag Build panel below is unbuilt; see "Lab graduation gates".

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
centred modals), `data-testid` from day one, i18n keys in every locale (21 full
locales as of Sep 2026, not the 7 of June; `zh-Hant-HK` inherits). The
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

## Lab graduation gates

`/codebook-lab` ships to the cohort as a *flagged experiment*
(`experimental_codebook_lab`, default-on). To graduate it from experiment to a
real feature, roughly in order:

- **Build the production Build-panel React UI** (see "Frontend — staged" above)
  — the lab's bare HTML is a validation stand-in, not the product.
- **Retire or polish the throwaway page** — it currently ships English-only
  inline CSS. Until it's on `theme/` + i18n (or replaced by the React UI), flip
  the flag default → `False` before any *public* (non-cohort) release.

  > **This gate is breached, and it needs a decision rather than a doc edit
  > (20 Sep 2026).** `experimental_codebook_lab: bool = True`
  > (`bristlenose/config.py:222`), and the router mounts on a plain non-dev
  > `serve` whenever the flag is on (`bristlenose/server/app.py:247`). 0.29.0 and
  > 0.29.1 shipped to PyPI, Homebrew, Snap and Fedora Copr on 31 Aug 2026 — public,
  > non-cohort channels — with the flag on and the page still English-only inline
  > CSS (`build_codebook_lab_html`, `routes/dev.py`).
  >
  > **The gate cannot be quietly honoured, because a test asserts the breach.**
  > `tests/test_codebook_builder.py:585-597` (`test_lab_mounts_without_dev`)
  > asserts `/codebook-lab` returns 200 with `dev=False`, and its docstring gives
  > the reason: the desktop sidecar and plain `serve` both run non-dev, so
  > TestFlight needs exactly this. Flipping the default turns that test red by
  > design. So the real question is not "was the flag forgotten?" but **"does
  > 'public release' still mean what it meant in June, now that the same binary
  > goes to both the cohort and PyPI?"** — the doc's framing predates there being
  > any non-cohort channel at all.
  >
  > Scope, so the risk is not overstated: the page is served outside `/api` with
  > no auth, but the API endpoints behind it are auth-scoped, and `serve` is a
  > localhost server. The exposure is an unpolished English-only surface on a
  > researcher's own machine, not a data path. Recorded, not changed — flipping a
  > shipped flag is a product call.
- **i18n glossary pass on the seed translations** — the non-en `codebookLab` /
  `projectTagsHeading` values are reasonable seeds (fr/cs aligned to the
  glossary's canonical "codebook" term; es kept as a defensible shortening) but
  want a native-reviewer / Weblate pass before the surface is non-experimental.
  _Confirmed future item, 27 Jun 2026._
- **Rename the `/api/dev/codebook-lab/*` endpoints** off the `dev` prefix (kept
  now only to avoid churning the page's fetch URLs + tests).
