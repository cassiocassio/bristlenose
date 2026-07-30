---
status: draft
---

# MCP server — connecting a project or folder to an assistant

_Design note. Nothing built. July 2026._

> **Status: Draft.** No code. This doc fixes the scope model, the object surface,
> the read/write posture, and the transport before any of it is built. The
> sequencing in §9 assumes single-project first; folder scope lands with the
> instance-level project index from [`design-multi-project.md`](design-multi-project.md).

## Changelog

- _30 Jul 2026_ — initial draft.

---

## Context — this is a loop closing, not a new direction

The workflow this serves predates Bristlenose and is the reason it exists:

1. Drag transcripts into an assistant. Hit a hard ceiling — Copilot on a work
   account caps at three.
2. Write prompts to find themes and common findings across sections.
3. Start saving the prompts.

Bristlenose industrialised all three. Step 2 is `bristlenose/llm/prompts/`
(twelve of them: `thematic-grouping.md`, `quote-clustering.md`,
`topic-segmentation.md`, `route-quotes-to-territories.md`, …). Step 3 is the
codebook — `TagPrompt` carries a code's `definition` / `apply_when` / `not_this`,
is instance-scoped so a boundary travels between studies, is versioned by content
hash, and is refined through accept/reject.

An MCP server returns the researcher to the chat surface they left, with the two
things that drove them out of it fixed: the context ceiling, and the amnesia
about their own codes.

### The pitch is leverage, not privacy

Copilot's three-transcript limit is a context limit. The pipeline is a
compression function — hours of media → a few hundred curated quotes → sections,
themes, signals. The same context budget that bought three raw transcripts buys a
folder of studies through Bristlenose's objects, and the tokens it does spend go
on quotes a human already judged worth keeping rather than on filler.

**Measure the actual ratio against the fossda corpus before this claim goes
anywhere near marketing copy.** It is currently an argument, not a number.

### The privacy position, stated correctly

The counterfactual is not "nothing leaves the laptop." It is "an unredacted
`.docx` gets dragged into a chat window." Against *that* baseline an MCP
connection is better on every axis: curated quotes instead of full transcripts,
anonymisable in transit, scoped by tool signature rather than by whatever
happened to get dropped in, and legible after the fact.

So privacy is the **second** sentence, not the first, and it is a claim of
improvement rather than a warning: *and it sends less of your participants' data
than you are sending today.*

Corollary — **no consent ceremony.** A staged gradient modal in front of an
action whose alternative is dragging a raw transcript into a chat box is theatre,
and reads as condescending to a researcher who has been doing the raw version for
a year. One plain line at connect time: what goes, what doesn't, how to turn on
real names. The gradient in
[`methodology/consent-gradient.md`](methodology/consent-gradient.md) governs
*telemetry to the vendor* and does not apply here — this is researcher-initiated
egress to an assistant they chose.

---

## 1. Build an MCP server, not a Claude integration

MCP is a protocol. VS Code, Copilot's agent surfaces, and whatever else lands in
enterprise catalogues speak it too.

This matters because of the case that does *not* improve. A researcher whose
employer approved Copilot has a DPA behind it; the same person's personal Claude
Desktop does not. For them, routing research data to a new assistant is a
regression in approvability even as it is an improvement in data minimisation.

If the server is vendor-neutral, the enterprise story is "point your approved
assistant at your own machine" instead of "get a new vendor approved." That costs
nothing at build time provided nothing in the server assumes one client's
behaviour: no client-specific tool naming, no reliance on a particular sampling
or elicitation extension, no assumption that the host renders Markdown a
particular way.

---

## 2. Scope model — the folder is the authorisation boundary

**Rule: if you can see the folder, you are qualified to see everything in it.**
A Bristlenose folder holds multiple studies for the same product, client, or user
base. Access control is inherited from the filesystem and from the researcher's
explicit choice of what to connect. Bristlenose does not re-implement
authorisation on top of that.

**Rule: there is no "connect Bristlenose" grant.** Three scopes, all explicit:

| Scope | What it reaches | Chosen how |
|---|---|---|
| **Project** | one project directory | the project the assistant was pointed at |
| **Folder** | every project under one folder | the folder the assistant was pointed at |
| ~~Instance~~ | **never** | — |

An "all my research" default is wrong on the merits, not merely risky: a folder
is exactly where the one NDA'd study sits beside four harmless ones, and the
researcher's mental model of "what did I just hand over" has to stay small enough
to hold in one thought.

### Cross-folder similarity is the point, not an edge case

Within a folder the studies share a product and a user base, so semantic overlap
is expected and worth exploiting: the same code applied across studies, a
finding that recurs, a contradiction between last quarter's participants and this
quarter's. `TagDefinition` and `TagPrompt` are already instance-scoped, so a
code's boundary is shared across the folder for free.

### Unresolved: "folder" means two different things

The shipped desktop concept is a **label** — `design-multi-project.md` §Folders
design rule 3 states explicitly that folders are index groupings, not filesystem
directories, and that the app should teach that distinction.

But the authorisation principle above is a *filesystem* intuition: seeing the
directory is what qualifies you. Those come apart. A label can group projects
from four different volumes with four different access stories.

Two ways out, and this needs deciding before the folder phase is built:

- **(a) Scope by filesystem directory.** `bristlenose mcp ~/Research/Acme` reaches
  every project directory beneath it. Authorisation is genuinely inherited; the
  principle holds literally. Ignores the desktop index entirely.
- **(b) Scope by index folder, with the label treated as a deliberate grouping.**
  Matches the desktop UI, allows cross-volume grouping, but the authorisation
  claim weakens to "you chose these, on your own machine" — which is still true,
  just not filesystem-derived.

**Leaning (a) for the server, with the desktop offering (b) as a convenience that
resolves to a concrete list of project paths at connect time.** The server should
only ever receive an explicit list of directories; how the human picked them is
the client's problem.

---

## 3. The objects to expose

Mostly already modelled. Grounded in `bristlenose/server/models.py`:

| Concept | Tables | Notes |
|---|---|---|
| Project, session | `Project`, `Session`, `SourceFile` | |
| Humans | `Person`, `SessionSpeaker` | instance-scoped; speaker code + role |
| Quotes | `Quote` | the atom; carries sentiment |
| Sections | `ScreenCluster`, `ClusterQuote` | |
| Themes | `ThemeGroup`, `ThemeQuote` | |
| Tags | `TagDefinition`, `QuoteTag`, `CodebookGroup` | |
| Frameworks | `ProjectFrameworkState`, codebook templates (garrett, norman, uxr, plato) | |
| Code boundaries | `TagPrompt` (`definition`/`apply_when`/`not_this`) | instance-scoped, content-hash versioned |
| Signals | **not stored** — computed in `bristlenose/analysis/` | concentration × agreement × intensity |
| Transcript | `TranscriptSegment`, `TopicBoundary` | |

Two additions not on the original list, both high value:

**The curation layer** — `QuoteState` (starred / hidden), `QuoteEdit`,
`HeadingEdit`, `DismissedSignal`. This is the researcher's *judgement*, and it is
what separates "summarise my study" from "summarise a pile of quotes." *Draft a
top-line from the starred quotes only* is the prompt that justifies the whole
feature.

**`TagPrompt` as a resource** — exposing the codebook's `apply_when` / `not_this`
boundaries is the single highest-leverage item here. It is what makes the
assistant reason in the researcher's taxonomy instead of inventing a parallel one
on the fly.

### Invariants belong in the server `instructions`

Without these the assistant will get the arithmetic wrong:

- **Quote exclusivity** — every quote appears in exactly one report section
  (`bristlenose/stages/CLAUDE.md`). Do not sum across sections and expect the
  corpus size.
- **Tag-analysis double-counting** — a quote tagged from multiple groups counts
  in each group column, inflating `grand_total`. Signal strengths are comparable
  *within* one analysis only. Already stated as `_TRADE_OFF_NOTE` in
  `bristlenose/server/routes/analysis.py`; restate it to the model.
- **Person rows are not deduped across projects** — two "Sarah" rows in two
  studies is correct, not a bug. Cross-study *people* questions are unreliable
  until `person_links` exists (§9).

---

## 4. Surface — resources and a small tool budget

There are ~70 project GET routes. Mirroring them into 70 tools destroys the
model's ability to choose. Strava ships eight. Budget accordingly.

**Resources** (stable, enumerable, cheap to hold in context):

- `bristlenose://codebook` — groups, tags, and each code's `apply_when`/`not_this`
- `bristlenose://frameworks` — active frameworks and their definitions
- `bristlenose://people` — participants and roles, per project
- `bristlenose://projects` — the inventory in scope, with session counts

**Tools** (parameterised, potentially large — all summarise-first, all with hard
limits):

| Tool | Purpose |
|---|---|
| `list_projects` | what's in scope, with size hints |
| `get_project_overview` | sections, themes, counts, top signals — the cheap orienting call |
| `search_quotes` | by tag / sentiment / person / section / theme / `starred_only`; paginated, capped |
| `get_signals` | computed concentration/agreement/intensity, with elaboration where cached |
| `get_themes` | theme groups with representative quotes |
| `get_session_journey` | per-participant journey with timecode anchors |
| `get_transcript` | one session, range-bounded — never whole-corpus |
| `compare_projects` | folder scope: shared codes, recurring findings, divergence |

**The three-transcript ceiling is the design constraint.** If `search_quotes` can
return 400 rows unbounded, the ceiling has been rebuilt inside our own server.
Every tool needs a default limit, a hard cap, and a cheaper aggregate sibling —
the `get_activity_performance` vs `get_activity_streams` split is the pattern.

---

## 5. Read-only for v1; writes go through the proposal queue

Writes are the obvious want — *tag these forty quotes with the Norman framework*
— and the machinery already exists. AutoCode and the dynamic codebook builder
both propose into an accept/deny review queue with rejection telemetry.

**A write tool must land as `ProposedTag`, never as a direct `QuoteTag` insert.**
Direct mutation loses the audit trail and corrupts the rejection-telemetry ratchet
that [`methodology/tag-rejections-are-great.md`](methodology/tag-rejections-are-great.md)
depends on.

This also happens to solve the unpaid tax on the saved-prompts workflow: you get
a good themes list in a chat window and then retype it into your analysis by hand.
Assistant proposes → researcher accepts in the SPA → it lands in the codebook with
provenance. That is the step the original workflow never had.

Ship read-only. Add writes as a second phase, as proposals only.

---

## 6. Transport and auth

**Recommendation: mount `/mcp` (streamable HTTP) on the existing FastAPI serve.**
Reuses the bearer token and the block-all CORS policy, keeps a single writer
against the per-project SQLite, and matches how the desktop app already runs a
sidecar. A `bristlenose mcp <path…>` CLI command is the nicer ergonomic and can
spawn or proxy to a serve.

Two things that will bite:

- **The auth token is per-instance.** `create_app()` mints a fresh
  `secrets.token_urlsafe(32)` on every start, so any client config file holding
  the token breaks on every restart. Needs a stable per-project token or a
  handshake file the client reads. Decide before shipping, not after the first
  support thread.
- **Local MCP over HTTP is a DNS-rebinding footgun.** Origin validation and
  localhost binding are both required; the existing CORS block-all helps but is
  not sufficient on its own.

Folder scope means multiple project DBs. Either one serve per project with the
MCP layer fanning out, or a read-only aggregating reader — note the
`?immutable=1` / WAL-checkpoint gotcha in
[`../bristlenose/server/CLAUDE.md`](../bristlenose/server/CLAUDE.md) before
choosing the second.

---

## 7. Hard exclusions

`.bristlenose/` holds re-identification keys: `pii_summary.txt` (every original
PII value with timecodes) and `llm-calls.jsonl` (session ids, prompt shas, timing
fingerprints).

**MCP exposure is an explicit allowlist, never a filesystem resource.** There is
no MCP tool that takes a path. Anonymisation defaults on, reusing the export
anonymisation boundary; real names are a per-connection opt-in.

---

## 8. Anti-drift, mechanically

Copy the export pattern. `tests/test_serve_export_coverage.py` reads
`app.openapi()` and fails if any project GET read is unclassified. Do the same
here: every project route must be classified `MCP_EXPOSED` or `MCP_DENIED`, and
a new unclassified route fails the build.

That is what makes "adding a route is private-by-default" true rather than
aspirational — the same reason it works for export.

---

## 9. Sequencing

| Phase | Scope | Depends on |
|---|---|---|
| **1** | Single project, read-only, `/mcp` on serve | nothing new |
| **2** | Folder scope — cross-project themes, codes, signals | project index / instance DB (`design-multi-project.md` §1) |
| **3** | Writes as proposals | `ProposedTag` review UI already shipped |
| **4** | Cross-project *people* questions | `person_links` (`design-multi-project.md` §2) |

**Put `project_id` in every tool signature from day one** so folder scope is not a
breaking change — the same discipline as the `apiBase()` rule in
`bristlenose/server/CLAUDE.md`. Phase 1 passes a single id; nothing about the
signature changes at phase 2.

Note the asymmetry across phases 2 and 4: folder-level questions about *themes and
codes* work as soon as folder scope exists, because `TagDefinition` and `TagPrompt`
are instance-scoped. Folder-level questions about *people* stay weak until
`person_links` lands, because person rows are deliberately not deduped. Do not let
a demo imply otherwise.

---

## 10. Open questions

1. **Folder = filesystem directory or index label?** §2. Leaning filesystem for the
   server, with the desktop resolving its label to a path list at connect time.
2. **Stable token or handshake file?** §6. Blocks phase 1 shipping.
3. **One serve per project, or an aggregating reader, for folder scope?** §6.
4. **What is the actual compression ratio** on a real corpus? §Context. Needed
   before the leverage claim is made publicly.

---

## Related docs

- [`design-multi-project.md`](design-multi-project.md) — project index, folders,
  person identity. Phase 2 and 4 depend on it.
- [`../bristlenose/server/CLAUDE.md`](../bristlenose/server/CLAUDE.md) — data API,
  auth middleware, multi-project scope rules, WAL gotchas.
- [`design-autocode.md`](design-autocode.md) — the proposal queue phase 3 writes into.
- [`design-dynamic-codebook-builder.md`](design-dynamic-codebook-builder.md) —
  `TagPrompt` lifecycle.
- [`design-export-html.md`](design-export-html.md) — the anonymisation boundary
  reused in §7, and the `openapi()` classification test copied in §8.
- [`methodology/tag-rejections-are-great.md`](methodology/tag-rejections-are-great.md)
  — why writes must be proposals.
- [`design-board-integrations.md`](design-board-integrations.md) — prior MCP
  assessment (Figma's write path, and why it was a no-go).
