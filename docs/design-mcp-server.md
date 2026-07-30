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

- _30 Jul 2026_ — added §3b: longitudinal querying by code is the real cross-study capability. Records the silent-under-reporting failure mode, `merge-tags` as the reconciliation primitive (and its undocumented instance-wide reach), the nullable `session_date` fallback chain, and the denominator trap. Sharpens the phase-2 dependency from "project index" to "shared codebook store". §3a softened: deliberate recurrence (panel, diary, follow-up wave) is real and meaningful — the rule is inference versus declaration, not identity versus no identity.
- _30 Jul 2026_ — added §3a and dropped phase 4. Cross-study person identity is not a deferred capability but a misread of research practice: recurrence is rare, and where unintended it is a liability the researcher already handles socially. `person_links` is no longer a dependency of this doc. (Superseded in part the same day — see the §3a softening above.)
- _30 Jul 2026_ — added §5a: user-authored frameworks as first-class objects (read / discover / author), refining §5's write rule to "corpus mutations go through the proposal queue, artifact authoring writes a reviewable file". Records the user-codebook directory, three loader traps, and the trust surface.
- _30 Jul 2026_ — added §Positioning (glue not chatbot; the Figma-/design-system analogy, what the position must defend, framework YAML as the ecosystem artifact) and its consequences in §5, §9, §10.
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

## Positioning — glue, not a chatbot

The rejected alternative was a **chat lens inside Bristlenose**: a conversational
surface in the report, and beyond it a robot that interrogates participants
directly — the Dovetail / Marvin shape, where the vendor owns the whole loop from
interview to insight.

The chosen position is the one Bristlenose already took with Miro: **be the glue
between the best tools.** One well-modelled object graph, many consumers. The
board integrations doc landed on an IR plus per-board renderers rather than
building a whiteboard; the MCP server is the third instance of the same pattern,
not a new one.

### The Figma analogy is exact, and it is the argument

Figma did not build a code generator. It exposed the **design system** — variables,
components, tokens — as structured objects, and the ecosystem wrote the last mile
as skills and project rules. Figma's value went *up* because its objects were
legible, not because it shipped a chat box.

Bristlenose's analogue of the design system is the **codebook**: `TagPrompt`
carrying each code's `definition` / `apply_when` / `not_this`, content-hash
versioned, refined by reject-with-reasons, instance-scoped so a boundary travels
between studies. That is the thing that is worth connecting to, and the thing an
assistant cannot invent for you.

### Where the AI actually lives

The position is **not** "no AI in the product" — AutoCode, the dynamic codebook
builder, and signal elaboration all call LLMs from serve mode today. The line is
sharper than that and worth stating in exactly these terms:

> **Specific jobs with a review queue happen in-app. Open-ended conversation
> happens in the assistant.**

Tagging a corpus against a framework is a specific job; it gets a proposal queue,
a diff, and an accept/deny trail. "What are we learning across these five studies"
is not a specific job, and building a worse chat surface inside the report to host
it is the mistake.

### What this position has to defend

A glue position only holds if you own an object nobody can regenerate. Ask what
survives a competitor who has the raw transcripts and a good prompt:

| Object | Regenerable from transcripts? |
|---|---|
| Quotes, sections, themes, sentiment | **Yes** — table stakes, not a moat |
| Transcription, speaker ID, PII removal | Yes, but expensive and fiddly |
| The curation layer (`QuoteState`, `QuoteEdit`, `DismissedSignal`) | **No** — accumulated human judgement |
| The codebook with its rejection history (`TagPrompt` + `TagPromptDecision`) | **No** — a trained artifact |

The two defensible rows are precisely the two the object surface calls
highest-value in §3. That convergence is not luck, and it should drive emphasis:
**lead with the codebook and the curation layer; treat extraction as table
stakes.** It is also the answer to "what if the assistant's context window grows
until it can just eat the transcripts" — that absorbs extraction, and touches
neither defensible row.

### The ecosystem artifact is the framework YAML, not the skill

The format already exists and was already designed for publication. Nine templates
ship in `bristlenose/server/codebook/` (garrett, norman, nielsen, morville,
yablonski, plato, uxr, sentiment, cli-ux), and the schema carries `author`,
`author_bio`, `author_links`, `preamble`, and `description` — third-party
authorship fields, not internal config. `cli-ux.yaml` goes further and encodes an
analytical *register*, instructing how the resulting report should read for a DX
audience. That is a design system, in the Figma sense: a portable, authored,
opinionated stance.

So what an agency publishes is **their house framework as YAML, plus a skill that
drives it** — their methodology, versionable in git, runnable by whoever they hand
it to. That combination is the unit of exchange, and Bristlenose already ships
half of it.

**Concrete gap:** `import_template` resolves ids against the built-in registry only
(`get_template` → `_TEMPLATES_DIR.glob("*.yaml")` in
`bristlenose/server/codebook/__init__.py`). **There is no path today to import a
YAML file the researcher wrote.** Bring-your-own-framework is a prerequisite for
the ecosystem story, not a nice-to-have, and it is small.

### The cost of this position, stated honestly

An in-app chatbot is discoverable; a user who never connects an assistant gets
nothing from any of this. The glue position needs the researcher to already have
an assistant and to complete a setup step. That is a narrower funnel than
Dovetail's, and it is a real trade — worth accepting because the cohort that wires
up Figma MCP is the same cohort that will publish frameworks, but not worth
pretending away.

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
- **Person rows are not deduped across projects, and must not be correlated** —
  two "Jim Smith" rows in two studies is correct, and joining them is not a
  deferred feature but a *methodological error*. See §3a. This one has to be an
  explicit anti-instruction, because a model will attempt the join unprompted.

### 3a. Cross-study person identity is not wanted — this is not a gap

An earlier draft listed cross-project *people* questions as a later phase blocked
on `person_links`. **That was wrong, and it was wrong in a specific way worth
recording so it isn't re-derived.** It imported a computer-science instinct — same
name, same entity, therefore join — into a field where the person is not the unit
of analysis across studies.

What is actually true of research practice:

- **Recurrence is rare.** Participants are overwhelmingly unique across studies.
  The join has almost no rows to operate on.
- **Unintended recurrence is a liability, not an asset.** Serial volunteers know
  the product and the process too well. They skew strongly-minded, over-focused,
  and prone to advocating on behalf of "all users" rather than reporting their
  own experience. Researchers recognise the usual suspects and decline to
  re-recruit them — handled socially, not a problem waiting for software.
- **Deliberate recurrence is real and meaningful — and already known.** A panel,
  a diary study, a follow-up wave with the same cohort: there the connection
  matters and you would want to make it strongly. But the researcher *designed*
  that. It is a fact they hold before the data exists, not something to be
  discovered by matching name strings.
- **Incidental recurrence rarely rewards reading across.** Two studies typically
  interrogate different facets of the product, so correspondence between the same
  person's quotes in each is not a finding — it is a coincidence of sampling.

The honest summary is not "identity across studies is irrelevant" but **"it is
much rarer and much less analytically significant than a data model would lead
you to guess"** — and in the case where it *is* significant, it is already known.

**Cross-study value lives in codes, themes and findings — not in people.** That is
already where folder scope delivers it, because `TagDefinition` and `TagPrompt` are
instance-scoped. No additional phase is required, and nothing about the folder
story needs hedging.

Two consequences for the build:

1. **`person_links` is not a dependency of anything here.** It stays a roadmap
   item in `design-multi-project.md` §2 on its own merits; this doc does not want
   it, and not in 2027 either.
2. **The line is inference versus declaration.** A *declared* link — "this is
   wave 2 of the same panel" — is cheap, honest, and the researcher already holds
   the fact. An *inferred* link, fuzzy-matched from name strings, is the thing to
   refuse. Worth carrying back to `design-multi-project.md` §2, which currently
   anticipates a "suggestion algorithm": the domain argues for building the
   declaration and skipping the suggester.
3. **The server must actively discourage the inference.** Dropping the feature is
   not sufficient — an assistant handed two projects will match "Jim Smith" to
   "Jim Smith" by itself. The `instructions` field has to say plainly that person
   identity does not cross project boundaries *unless declared*, and that
   correspondence between same-named participants is not, on its own, signal.
   This is the one place the server needs an anti-instruction rather than a
   capability.

Within a single study, people remain first-class and important — who said what,
role, journey, whose experience diverges. It is only the cross-study join that has
no value.

### 3b. Longitudinal querying by code is the real cross-study capability

What a researcher actually wants across a folder is a **durable concept traced
over time**: *perception of cost*, *frustrations with getting started*, *brand
loyalty*. Concepts that recur study after study, where the interesting question is
how the answer moved — not who gave it.

This is a long way ahead of person reconciliation in value, and it is worth being
explicit that the reconciliation problem is **real but at the wrong object**.
Matching `p3` in one study to `p7` in another buys nothing (§3a). Matching *"cost
concerns"* to *"price sensitivity"* is the entire capability.

### The failure mode is silent under-reporting

Nothing forces two studies to use the *same* code. A researcher coding study A
creates "cost concerns"; six months later, study B gets "price sensitivity". Both
are ordinary `TagDefinition` rows. A longitudinal query for either one returns a
confident, partial answer with no indication that half the corpus used the other
label.

That is worse than a gap, because it looks like a finding. Two consequences:

- **The surface must expose near-duplicate codes**, so the assistant can say "you
  have two labels that look like the same concept" rather than quietly answering
  from one of them.
- **`merge-tags` is the reconciliation primitive and already exists**
  (`POST /projects/{id}/codebook/merge-tags`). Worth recording a non-obvious
  property: despite the project-scoped route path, it reassigns **every**
  `QuoteTag` row for the source tag with no project filter and then deletes the
  instance-scoped `TagDefinition`. For longitudinal work that is exactly right —
  healing a split concept should heal every study at once — but it is surprising
  enough that it needs a test pinning the behaviour before folder scope makes it
  observable.

### The actual blocker is the per-project database, not the project index

`TagDefinition` and `TagPrompt` carry no `project_id`, which the server rules
describe as instance-scoped. **Today that is aspirational.** Each project gets its
own SQLite file at `<output_dir>/.bristlenose/bristlenose.db`, so a code does not
in fact travel between studies — it is a different row in a different database
with a coincidentally identical name.

So the phase-2 dependency is sharper than "the project index": longitudinal
querying needs a **shared codebook store** — the instance DB at
`~/.config/bristlenose/bristlenose.db` that `design-multi-project.md` anticipates,
or an equivalent. Without it, cross-study code queries cannot be right, only
lucky. This should be stated as the dependency rather than the index, because a
project index alone would ship a folder mode that under-reports.

### Two traps in the time axis itself

- **`Session.session_date` is nullable** (`datetime | None`, default `None`).
  "Over time" needs a documented fallback chain — `session_date` →
  `first_imported_at` → `Project.created_at` — and the tool must **return which
  one it used**. Otherwise a folder of undated studies silently sorts by import
  order and presents it as chronology.
- **Denominators.** Five participants in one study and twenty in the next makes
  raw counts across time actively misleading — *"mentions of cost tripled"* when
  the sample tripled. Every longitudinal result carries its per-study denominator,
  and the `instructions` say plainly not to compare raw counts across studies of
  different sizes. Same family as the existing `_TRADE_OFF_NOTE`, and an assistant
  will fall into it unprompted.

---

## 4. Surface — resources and a small tool budget

There are ~70 project GET routes. Mirroring them into 70 tools destroys the
model's ability to choose. Strava ships eight. Budget accordingly.

**Resources** (stable, enumerable, cheap to hold in context):

- `bristlenose://codebook` — groups, tags, and each code's `apply_when`/`not_this`
- `bristlenose://frameworks` — every framework available, built-in *and*
  user-authored, with `preamble` and full per-tag boundaries (§5a)
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
| `trace_code` | folder scope: one code across studies over time, with per-study denominators and the date basis used (§3b) |
| `find_duplicate_codes` | near-duplicate labels across the folder — the silent under-reporting guard (§3b) |
| `get_framework` | one framework in full — the stance, not just the tag list (§5a) |
| `draft_framework` | write a YAML to the user codebook dir; authoring, not applying (§5a) |

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

**The ecosystem position raises the stakes on batch review.** If a published skill
proposes 200 tags and accepting them is 200 clicks, the skill is worse than
useless and the ecosystem story dies at the first demo. `accept-all` / `deny-all`
already exist (`routes/autocode.py:515,595`) but were built as a convenience;
under this positioning they become load-bearing infrastructure and need the
review affordances to match — group by code, preview the diff, accept a subset.
Worth designing before the first third-party skill exists rather than after.

---

## 5a. Frameworks as first-class objects

A researcher's own framework is not just something to *import* — it is an object
the assistant should be able to read, reason in, and help author. Three
capabilities, in increasing order of ambition:

1. **Read** — the full framework, not just tag names: `preamble`, per-tag
   `definition` / `apply_when` / `not_this`, group structure, and any register
   instruction. This is what makes the assistant reason in the researcher's
   taxonomy instead of a parallel invented one.
2. **Discover** — which frameworks exist (built-in *and* user-authored), which are
   applied to which project, and for a given tag in this project, whether it came
   from a framework or was hand-rolled.
3. **Author** — draft a framework from how the researcher already codes. This is
   the dynamic-codebook-builder loop (`synthesize` from exemplars → boundary
   fields) raised from single-tag to whole-framework granularity. The engine and
   the `codebook-synthesize.md` prompt already exist.

### This refines the write rule in §5

"All writes are proposals" was too blunt. The right split:

> **Corpus mutations go through the proposal queue. Artifact authoring writes a
> file the researcher reviews as a file.**

A framework YAML is a *document*, not a change to anyone's coded data — git diffs
it, the researcher reads it, nothing has been recoded. **Applying** that framework
to a corpus is a separate action and still goes through `ProposedTag`. That
separation is what makes authoring safe to hand to an assistant, and it matches
how design-system work with Figma actually goes: you edit the tokens file, you
don't silently restyle the app.

### Where user frameworks live

**`user_config_dir()/codebooks/*.yaml`** — the XDG-aware helper already exists
(`bristlenose/credentials.py:22`, honouring `$XDG_CONFIG_HOME`, else
`~/.config/bristlenose`). Instance-level rather than project-local, for the same
reason `TagDefinition` and `TagPrompt` are instance-scoped: a framework is a
property of how you work, not of one study. Plus an explicit-path import for
one-offs and for a framework checked into a client's repo.

### Three traps in the current loader

Discovery is already `_TEMPLATES_DIR.glob("*.yaml")`, so adding a second directory
is small — but:

- **`load_all_templates` is `@cache`d.** A YAML dropped into the user directory
  will not appear until the process restarts. Either invalidate on directory mtime
  or scope the cache to the built-in dir only. This will otherwise present as
  "my framework didn't show up," which is exactly the first-run experience an
  ecosystem cannot afford.
- **`_VALID_COLOUR_SETS` is a closed frozenset** (`ux`, `emo`, `task`, `trust`,
  `opp`, `sentiment`). A user YAML naming anything else must degrade to a default
  with a warning, never crash the picker — a third-party file is untrusted input
  in a way the bundled nine never were.
- **`id` collisions.** A user framework with `id: garrett` needs a precedence rule
  and a visible indication of which one won. Namespacing user ids is the cheap
  answer.

Validation belongs in `bristlenose doctor`, mirroring the existing
`Bundle: locales` check — malformed YAML in the user codebook directory should be
reported by name at the point the researcher goes looking, not swallowed.

### Trust surface

A framework's `preamble` steers both the analysis and the report's register —
`cli-ux.yaml` uses it to instruct voice for a DX audience. That is the feature, and
it is also the risk: a framework is executable methodology, not inert
configuration. A framework the researcher drafted with their assistant is in a
different trust position from one fetched off a registry, and §10 Q5 (distribution
model) has to be answered before authors are invited.

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
| **2** | Folder scope — longitudinal code queries across studies | **a shared codebook store**, not just the project index (§3b) |
| **3** | Writes as proposals | `ProposedTag` review UI already shipped; batch review hardened (§5) |

**Bring-your-own-framework YAML is a phase-1 sibling, not a later phase.** It is
independent of everything above, it is small, and without it the ecosystem
argument in §Positioning has no artifact to trade. Ship it alongside the read-only
server.

Note that this makes phase 1 not-quite-read-only, and deliberately so: `read` and
`discover` from §5a are phase 1, and `author` (`draft_framework`) can be too,
because writing a YAML file mutates no coded data. The proposal queue still gates
everything that touches the corpus. The §5a split is what lets the useful half of
authoring land early without waiting on phase 3.

**The tool signatures are a public contract from day one.** If people write skills
against this, the tool surface is no longer an internal API that can be reshaped
between releases — it needs versioning, a deprecation posture, and documentation
outside the codebase. That is a cost of the glue position and should be accepted
deliberately rather than discovered when the first published skill breaks.

**Put `project_id` in every tool signature from day one** so folder scope is not a
breaking change — the same discipline as the `apiBase()` rule in
`bristlenose/server/CLAUDE.md`. Phase 1 passes a single id; nothing about the
signature changes at phase 2.

**Three phases, not four.** An earlier draft carried a fourth phase for
cross-project people questions; §3a explains why that was a misread of research
practice rather than a deferred capability. Folder scope delivers the cross-study
value in full at phase 2, because the objects that carry it — `TagDefinition`,
`TagPrompt` — are already instance-scoped. Nothing about the folder story needs a
caveat.

---

## 10. Open questions

1. **Folder = filesystem directory or index label?** §2. Leaning filesystem for the
   server, with the desktop resolving its label to a path list at connect time.
2. **Stable token or handshake file?** §6. Blocks phase 1 shipping.
3. **One serve per project, or an aggregating reader, for folder scope?** §6.
4. **What is the actual compression ratio** on a real corpus? §Context. Needed
   before the leverage claim is made publicly.
5. **Where do third-party frameworks come from?** §Positioning. A local file path
   is the minimum. A published directory (git-installable, or a gallery in the
   desktop app) is the version that creates the ecosystem — but it also creates a
   trust surface, since a framework YAML carries `preamble` text that steers
   analysis and report register. Decide the distribution model before inviting
   authors.
6. **Is the tool surface versioned per release or independently?** §9. Affects
   whether a Bristlenose upgrade can break a published skill.

---

## Related docs

- [`design-multi-project.md`](design-multi-project.md) — project index, folders,
  person identity. Phase 2 depends on the project index; the person-identity
  work there is explicitly *not* a dependency of this doc (§3a).
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
