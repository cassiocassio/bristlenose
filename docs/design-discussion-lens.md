---
status: shipped-beta
last-trued: 2026-10-04
trued-against: HEAD@main on 2026-10-04
---

<!-- 2026-10-03: shipped for beta on both channels — the stage on by default, the
     lens in the web nav, the Mac rail and the HTML export. This doc stays the
     design intent; what was built, and how it departs from the plan, is in the
     banner of design-discussion-lens-plan.md. The 26 Jul note below ("the
     feature is unbuilt") is history. -->

<!-- 2026-10-04 (/true-the-docs --topic discussion lens): sections describing the
     July straw man that v1 did not build are marked so in place — the native
     empty-state page, territory/stance parse, the data structures, the signal
     bars and the IA — with their bodies kept as the design reasoning. Shipped
     facts added: the guide tabs, the key, the no-guide mid dot, guide_file, the
     routing rule, the decided open decisions, the mockups. -->

<!-- Resurrected 2026-09-27. Phase A spike run for the first time, on real
     interviews; the design gained a RECONCILE step (the guide as planned ⋈ the
     questions actually asked). Read "Revision 27 Sep 2026" first — it
     supersedes the parse-only model below where they disagree. Stale names
     trued (Analysis → Signals; the macOS lens picker is the native `Tab` enum,
     not the web NavBar). Reuse map re-verified symbol by symbol at HEAD. -->

<!-- Trued 2026-07-26 (/true-the-docs --doc): Archetype P (pending/aspirational).
     Authored + consolidated this session; the feature is unbuilt (design + mockups
     + a routing spike only), so there is no shipped reality to reconcile against —
     the doc IS the current design intent. Full agent audit deliberately skipped
     (doc is at HEAD; volume-as-success avoided). Re-true once Phase A/B ship. -->

# Discussion lens — the researcher's guide, answered by the evidence

> **Building it?** The implementation plan — every registration point, the
> silent-failure traps, and the phases — is [design-discussion-lens-plan.md](design-discussion-lens-plan.md).

*Design doc for a new macOS-app report lens that takes the researcher's own
discussion guide and re-projects the extracted quotes onto it — organising
findings by the researcher's **own domain model** instead of emergent themes.
Sibling to the Quotes and Signals lenses; reuses the quotes-page card, editing,
and sequence machinery wholesale.*

*Status as of 4 Oct 2026: shipped for beta — see the banner above and the plan's
banner. The paragraph below is the July status, kept as history.*

Status: **straw man, consolidated 26 Jul 2026** after a long design conversation
and a usual-suspects review; **resurrected 27 Sep 2026** with a spike run on
real interviews and a reconcile step — see "Revision 27 Sep 2026". Findings and their disposition live in the
gitignored review log for this doc. The distillation step is proven on real
guides (see "Proof"); routing is the remaining unknown, to be de-risked by a
backend spike (see "Sequencing"). Two product calls are still open: the routing
mechanism and the spike corpus.

---

## What a discussion guide actually is (read this first)

A good discussion guide is **not a script**. It is the researcher's **externalised
thinking** — a domain map that aligns the team (observers, notetakers,
stakeholders) on what's in the researcher's head, and immerses the researcher so
they can follow any thread fluently instead of reading questions out like a
"script bunny". Consequences that drive the whole design:

- **It is deliberately over-prepared.** A real guide is *too long on purpose* —
  most of its questions are never asked verbatim.
- **Its backbone is ~5–12 top-level intentions** ("territories"). The arithmetic:
  a 60-min interview − 5 min warm-up − 5 min thanks ≈ 50 min ÷ ~5 min per area ≈
  **8–12 territories**. (Soft heuristic, tied to session length — not a template.)
- **It is richly, irregularly structured**: a thematic **spine** (the territories),
  **big questions** hanging off the spine, **follow-up questions/probes** hanging
  off those, plus parenthetical watch-fors and a non-spine preamble. Three-plus
  levels deep. Registers are mixed (ALL-CAPS markers, Title-Case blocks, numbered
  lists, bullets) and vary guide to guide.
- **Evidence lands at the territory level, not the question level.** Each ~5-min
  territory gets discussed; individual prepared questions mostly don't. And a
  participant's answer is rarely a 1:1 response to any written question — it's a
  reply to an ad-libbed follow-up that's *in the territory* but was never in the
  guide.

**The load-bearing correction:** do not treat the guide as a checklist to grade
coverage against, and do not expect a clean `moderator asks Q → participant
answers Q` pairing. Both would disappoint. The guide is a **semantic scaffold**;
the lens hangs evidence on it, and most fine-grained nodes stay empty — which is
the *normal, correct* state, not a shortfall.

## What it is

A sixth lens, **Discussion**, in the macOS app's toolbar lens picker next to
Quotes / Codebooks / Signals. It reads like the Quotes lens — same quote cards, badges,
inline editing, sequence treatment — but its **navigation is the researcher's
guide** (the ~5–12 territories) and its grouping comes from routing quotes onto
those territories.

The proposition, in one line: **you hand the researcher their own domain map
back, populated with the evidence that emerged and ordered to show the balanced
spread.** Legible in a way emergent themes are not — it's the thinking they did,
answered by reality.

## Surface & packaging — macOS desktop only

> **Superseded 3 Oct 2026.** The lens ships on **both** channels — the Mac app
> and the CLI's SPA, plus exported HTML read-only. The free/paid line is the
> CLI versus multi-project, not individual lenses. Everything is the same
> webview code; the web adds a NavBar entry, the export embed and its
> anonymisation. See [design-discussion-lens-plan.md](design-discussion-lens-plan.md) §0.
> The section below is kept as the July reasoning.

**The Discussion lens ships only in the bundled macOS app (`bn.app`), not in the
open-source CLI / served SPA.** Product rationale: it's a **paid-tier lever** for
researchers who work from a structured guide; the CLI/Linux crowd skews less
formal about guide structure and the cost (parse + route + cluster) isn't
warranted there.

Mechanics (a gate, not a fork): the desktop's lens picker is **native** —
`enum Tab` in `desktop/Bristlenose/Bristlenose/Tab.swift` (five cases today, raw
values keyed to `window.switchToTab` in `frontend/src/shims/navigation.ts`) — so
the lens is desktop-only by construction: a sixth `Tab` case, its ⌘6 View
command in `MenuCommands.swift`, `common.nav.discussion*` keys in all 21 full
locales, and a `TAB_ROUTES` key. The React route ships in the SPA bundle with no
web-NavBar entry and is gated on `isEmbedded()`, so the CLI report and exported
HTML never reach it. *(Trued 27 Sep: this said "the macOS app's NavBar", which is
the web NavBar the desktop does not show.)* *(Note: the repo is
AGPL, so the code stays visible even though the feature is packaged
desktop-only — a distribution decision, not a code-visibility one.)*

> **Not built (4 Oct 2026).** No native empty-state page and no drop target.
> With no guide, the SPA's second tab, **Add your guide**, shows the upload copy
> and a button: on the Mac it opens the native open panel (`DiscussionGuide.swift`,
> `ContentView.chooseDiscussionGuide`), copies the file into the project's
> "Discussion guide" folder and starts Analyse; in a browser it says where the
> file goes. See the plan's §3 and §4.

**Two surfaces, one seam.** The **no-guide empty state is a native SwiftUI page**
— it reuses the Welcome page's pattern (`WelcomeHomeView` + `WelcomeIllustrations`)
and drop target (`.dropDestination(for: URL.self)`) plus File ▸ Add Files…
(`NSOpenPanel`), i.e. the same import path interviews use (`ContentView` /
`DropRouting` / `SidebarDrop`). Once a guide is parsed, the **loaded lens is the
normal HTML/CSS SPA** in the WKWebView — the same native→webview handoff the app
already performs (WelcomeHomeView → project report). No new drop machinery, no
webview upload UI.

## The routing model — aggregation by territory

The obvious model is temporal (find where the moderator asks question X, take the
quotes until the next question). Four facts about real interviews break it:
questions get asked **out of order**; participants **jump forward**; the moderator
**ad-libs** on the same topic; the moderator **says things not in the guide at
all**. So evidence for a topic is **scattered** through the session, and the unit
of aggregation is the **territory** (the top-level intention), not the sentence
that preceded a quote.

**Route each quote to the territory whose field it belongs to.** The match target
is a **rich semantic field** — the whole territory: its intent + all its folded
scaffold (big questions, follow-ups, watch-fors). A quote that is "in the
territory" of AWARENESS but answers an ad-libbed follow-up still lands there, even
though it answers no written question. Routing at territory granularity (~10
targets) is **truer, more robust, and cheaper** than per-question routing (~30
targets, false precision, most-UNROUTED).

Settled scope decisions:
- **The lens is a filter, not a partition.** A quote that matches no territory
  doesn't appear here — it stays in the Quotes lens. So the router is
  **conservative**: route confident matches, else `UNROUTED`. Omission is safe;
  mis-attribution isn't.
- **Display order is guide order** (the spine) — full stop. Quotes appearing "out
  of order" vs the session is correct; the guide supplies order precisely because
  the interview didn't.
- **No 1:1 question→answer expectation.** The conversational anchor
  (preceding-moderator-turn) is retired from the model — it's the wrong tool for
  territory routing. v1 is intent/field-match only.

## Ingest + parse

> **As built (v1):** the `bristlenose/discussion/` package (guide, moderator,
> structure, stage, models). The guide is a file in a "Discussion guide" folder
> beside the recordings — copied there by the Mac's open panel or put there by
> hand; no drag-drop — and the record keeps only its file name (`guide_file`,
> blanked in an anonymised export). Where this section and "Data structures"
> say the guide is stored in `.bristlenose/`, read the folder above. No
> territory or stance parse shipped; see the plan's §1.

A late analysis stage under `bristlenose/stages/` (Pydantic; needs the stage
cache/resume machinery). Runs **after quote extraction (s09)**; it routes
*existing* quotes, so a guide added after analysis triggers routing only — no
re-transcription. Steps:

1. **Ingest.** The guide is added the same way interviews are — native
   `NSOpenPanel` + drag-drop, reusing the existing import path. **Formats:**
   `.docx` (reuses the s04 docx parser), `.md`, `.txt`. **PDF is net-new** (no PDF
   text extraction today — s03 subtitles + s04 docx only); recommend docx/md/txt
   for v1.
2. **Parse → territories.** One LLM pass turns the raw guide into the
   `DiscussionGuide`. The prompt (`bristlenose/llm/prompts/parse-discussion-guide.md`,
   markdown) instructs the model to:
   - **Discover the guide's own top-level intentions** (~5–12, session-length
     tied) — never assume section names, never impose a template. These are the
     **territories/buckets**.
   - **Fold everything below** — big questions, follow-ups, probes, parenthetical
     watch-fors — into the territory as `scaffold`; do not promote it to top-level
     or make it its own bin. Each scaffold item gets a **terse sub-label** (for
     on-disclosure nav) and keeps its **verbatim** text (hidden match material).
   - Emit per territory: `terse` (nav label), `intent` (the territory's whole
     field — internal, for routing), `kind`, `stance_axis`, `scaffold`. **Every
     displayed string is terse** — the distilled guide is a ≤2-screen sidebar,
     never verbatim questions.
   - **Quarantine welfare / safeguarding / distress-protocol blocks** as
     `instruction`, never a routable territory (a "Do you feel safe?" line is
     care, not data — surfaced by a real guide).
   - Preserve the guide's real order and irregular structure.
   - **Fail loud, never open**; the human edit is a **diff against the source**,
     so a dropped territory is *visible*, not something to notice is absent.
3. **Route quotes → territories.** Match each quote against each territory's field
   (intent + scaffold); route to the best above a confidence floor + margin, else
   `UNROUTED`. Mechanism = open decision (batched-LLM-classify for v1 vs
   embeddings). Emits `discussion_route | quotes=Y | routed=X | unrouted=Z`; a
   near-total collapse is a fail-loud condition, never a calm empty lens.
4. **Stance-cluster per populated territory** (skipped when `stance_axis == none`,
   and only for territories that caught evidence). Cluster the routed runs into
   `ResponseGroup`s (majority + variants) with visible counts.
5. **Aggregate** into the lens model (precomputed, baked into the report JSON;
   the view never recomputes clustering on render).

## Data structures (straw man)

> **Not built in v1.** The shipped models are in `bristlenose/discussion/models.py`
> — spine sections and items, turn labels, consolidation, routes and the
> `DiscussionRecord` — with no stance clusters, response groups or evidence
> strength. Kept as the July design.

```
DiscussionGuide                 # one per project
  source_file                   # stored in .bristlenose/ (re-id key) — NOT the output root
  fingerprint                   # guide hash; edits invalidate derived routing
  territories: list[Territory]  # 5–12; ordered — display order is guide order

Territory                       # the top-level intention / bucket — the nav unit
  id, order
  nav_terse                     # ≤18 chars — SIDEBAR row (orientation); compress hard, never wraps
  heading                       # ≤40 chars — CONTENT heading, the researcher's fuller phrasing
  intent                        # ≤100 chars — CONTENT one-line descriptor; matching = intent + scaffold verbatim
  kind: questions | task | instruction   # instruction => opening/safeguarding, never routed
  stance_axis: opinion | pattern | none
  scaffold: list[ScaffoldItem]  # folded big-Qs + probes

ScaffoldItem
  terse                         # ≤24 chars — SIDEBAR disclosure sub-label (orientation); never verbatim
  verbatim                      # the question/probe as written — hidden MATCH MATERIAL, never displayed in nav
  # Researcher overrides (terse labels) are stored as an override layer,
  # never mutating the parsed source (fingerprint diff stays valid).

QuoteRouting                    # one per quote
  quote_id, session_id
  territory_id | UNROUTED
  confidence, margin            # sub-margin ties → UNROUTED, not a confident misfile

TerritoryNode                   # per territory, across all sessions (the lens reads this)
  evidence_strength             # signal-bar level (how much routed here) — density, not a score
  response_groups: list[ResponseGroup]   # majority first, then variants (populated territories only)

ResponseGroup
  kind: majority | variant
  axis: opinion | pattern
  label                         # "Most found it obvious" — "most" GATED on min share (auditable)
  n_participants, n_runs        # visible counts
  runs: list[ArgumentRun]       # strongest-first

ArgumentRun                     # the SORT ATOM (visual = reused seq-* left-rule)
  participant
  quote_ids: list[str]          # original sequence, NEVER reordered
  strength                      # peak quote; ranks the run within its group
```

## The lens view / information architecture

> **Superseded by what shipped (4 Oct 2026).** The navigator is `.toc` rows with
> provenance marks and a key, beside a session column of questions and quotes
> joined by wires; no signal bars, scaffold disclosure, response groups or inline
> label editing, and no minimap. The plan's §3 is the as-built description. Kept
> as the July design.

Reuses the Quotes page almost entirely — `QuoteCard`, `QuoteGroup`, badges,
editing, and the `seq-*` run treatment. What changes is the **navigation** (the
guide's territories) and the **grouping key** (territory, then response spread).

**What "distill" means, and the two densities (settled — Option B, 26 Jul).** The
distilled guide renders at two densities from one structure: the **sidebar is
orientation** (can you get to the right place?) and the **content area is where
the work happens**. The sidebar — the whole navigable guide — must fit **≤2
screens, narrow**, so it is terse throughout: `nav_terse` territory labels
(≤18 chars) and terse disclosed sub-labels (≤24 chars), **never verbatim
questions**. The content carries the researcher's fuller phrasing: a `heading`
(≤40 chars) + a one-line `intent` (≤100 chars) + the evidence. Verbatim scaffold
text is hidden match material only. *(Option A — one shared label for both
surfaces — was considered and rejected: the sidebar is pure orientation, so it
should compress past the content heading. Rendered both ways in
`docs/mockups/mockup-discussion-heading-options.html`.)*

**IA (settled):**
- **Nav = the ~5–12 territories** (the spine), in a GuideSidebar mirroring
  `TocSidebar` — each row a **`nav_terse`** label (≤18 chars, orientation) + a
  **signal-bar** evidence indicator (not a fraction).
- **The scaffold is progressive disclosure — terse.** Expanding a territory
  reveals its **terse sub-labels** (≤24 chars, never verbatim), behind a collapsed
  `<details>` ("what I explored here ▸"), reusing the coverage-details idiom —
  collapsed by default so the nav stays under two screens.
- **Within a territory (content area):** the **`heading`** (the researcher's fuller
  phrasing) + a one-line **`intent`** descriptor, then the **response-groups** (the
  balanced spread — majority / variants) with their quote runs. Response-groups are
  the emergent second level — *not* the guide's sub-questions. (This absorbs the old
  per-question paraphrase gallery; a "how it was actually asked" view can live inside
  the disclosure as a v1.x add — not load-bearing.)

**Depth stays legible** because interior levels use different visual channels:
response-group = a horizontal typographic lead-in (muted, emphasis-weight, count
inline — *not* a filled box); argument-run = a vertical left-rule (the reused
`seq-*` treatment). Never nested filled boxes. Proven in the mockup on a
deliberately dense territory.

**Inline editing** — the researcher can edit each territory's terse label (and,
via the disclosure, its scaffold) exactly as Section/Theme headings are edited on
the Quotes page (`EditableText` + `edit-pencil`), stored as an override layer.
Editing a display label never re-routes evidence.

**Lens-template row** (`docs/design-lens-template.md`): GuideSidebar · minimap ✓ ·
no tags · no inspector · body scroll. h1 scheme: each territory is a
`.section-heading` zone; response-groups and runs are **not** headings.

## Evidence, not coverage

> **Signal bars not built in v1.** The no-coverage-score principle holds.

The guide is a thinking map, not a checklist — so **there is no coverage/
completeness score.** A territory answered thinly isn't a gap; a prepared question
never asked isn't a failure.

- **Signal bars carry evidence density at the territory level** (where evidence
  reliably lands). Neutral, monochrome, ascending-height ("good flow of data here")
  — deliberately *not* the codebook's blue on/off state dot, and *not* a fraction
  (which reads as a grade). Density genuinely varies across territories; that
  variance is the signal worth seeing.
- **Empty / thin territories recede** — dim, never flagged or shamed. Absence is
  information (`feedback_absence_is_information`; no craft coaching).

**Ordering within a territory** (the balanced read) is a lexicographic priority,
atom = the argument-run (never fractured to hoist a single quote):
1. Group by response position — inviolable (all evidence for a position together).
2. Majority group first, then variants, each strongest-first.
3. Within a group, rank runs by strength (run strength = peak quote).
4. Within a run, preserve original sequence.

**Honest consensus, not manufactured.** The conservative router drops thin-wording
quotes (often the dissenters), so a naïve "majority" can be a biased subsample —
self-defeating in an anti-bias lens. Guards: `ResponseGroup` carries visible
counts; "most" wording is gated on a minimum share; experiential territories
(`stance_axis == none`) skip clustering and render as a plain ordered list.

## Reuse map

**Real reuse — take it:**

| Need | Reuse | Where |
|---|---|---|
| Quote cards, badges, hidden/star, inline heading + text editing | `QuoteCard`, `QuoteGroup`, `EditableText` | `frontend/src/islands/`, `molecules/editable-text.css` |
| Argument-run visual | `quote-sequences` `seq-*` left-rule treatment (generalise out of `.signal-card-quotes`) | `organisms/signals.css` |
| Off-screen render skip | `content-visibility: auto` per card | `organisms/blockquote.css` |
| Progressive-disclosure idiom (the scaffold) | `.coverage-details` `<details>` pattern | `organisms/coverage.css` |
| Embedded-JSON XSS-safe serialisation | centralised escaped `endpoints` embed | `server/routes/export.py` |
| Re-identification-key quarantine (the guide file) | `.bristlenose/` hidden dir | `s07_pii_removal.py`, `llm/telemetry.py` |
| OS-metadata filtering at the guide scan site | `is_os_metadata()` | `utils/fs.py` |
| Native empty-state page + drop target | `WelcomeHomeView` / `WelcomeIllustrations` / `.dropDestination` / `NSOpenPanel` | `desktop/` |
| Stage cache / resume | manifest + `SessionRecord` | `stages/` |
| Lens geometry / variants / keylines | lens-page template | `docs/design-lens-template.md` |

**Net-new (build honestly):** the guide parser; the quote router (territory-level);
per-territory stance clustering; a backend "run-membership" computation (the
frontend `detectSequences()` is JS-only, timecoded-only); an **evidence-bars atom**;
a **response-group-label molecule**; the run-bracket generalisation. No embeddings
infra exists today (net-new if chosen). Three small token-only design fragments in
total; everything else grounds to an existing atom/organism.

## Fail-loud, privacy, invariants

- **Parser + router fail loud, never open.** Three tab states: no guide → native
  empty state; guide added but parse degenerate → fail-loud "couldn't read your
  guide" (never the empty state); parsed OK → the lens. *As built:* the record's
  status (`not_run`, `stale`, `ready`, `partial`, `failed`) each says what it
  means; a guide that is there but unread carries `guide_problem` and says why;
  with no guide the lens shows the questions asked and an **Add your guide** tab.
- **A4 stage invariants** (`stages/CLAUDE.md`): `Cause.message` from structured
  fields only, never `str(exc)` (prompts echo transcript text →
  `pipeline-events.jsonl` is a re-id surface); abandon-check before
  `mark_stage_complete`; `StageFailure` at the LLM call site before any fallback.
- **Privacy.** Raw guide → `.bristlenose/`, never the output root or any export.
  Guide + any surfaced moderator wording route through the centralised escaped
  export embed (regression test with a `</script>` payload) and respect the
  anonymise toggle (make the export anonymiser allowlist fail-closed for new embed
  keys). `is_os_metadata()` at the guide scan site. Transparency copy names the
  guide as LLM egress; Ollama keeps it local.

---

## Revision 27 Sep 2026 — the guide as planned *and as run*

**The shift.** The July design took the guide as the spine and routed quotes
onto it. Running it on real interviews showed that is half the picture: in
the sessions the researcher asks relevant questions *in context*, and most of
them were never written down. So the lens's navigation becomes **one very
tight summary of the guide as planned and as run** — planned questions and
the questions actually asked, merged into logical thematic groups — and the
lens groups quotes by **research question and intent**: what the team is
trying to find out, and what the answers were. Not by section, not by theme.
It is another lens over the same quotes; most of it exists already.

### Decided 3 Oct 2026 — v1 shows a record, never a new guide

**The lens's left pane shows one of two things: the researcher's own guide
(Planned), or the merged guide (Merged).** *On screen (4 Oct):* **Your guide**
and **Normalised questions**; with no guide the second tab reads **Add your
guide** and is where one is added. Nothing else. We are not in the
discussion-guide-writing business; the job is to track the structure of the
questions the researcher chose to ask in the moment, offer that structure as
navigation, and connect it to the verbatim wording of what was asked, so
planned and actual can be compared and reflected on.

- **Merged is a record of what was asked, not a proposed guide.** Its wording
  and framing must never say or imply "here is your new guide".
- **Some asked questions belong to one person on one day.** "Did you have
  trouble getting here — the tube strike?" is a real question in that session
  and not one to put to anyone else. Folding such questions into something
  presented as reusable is a judgement the researcher makes, not one the model
  makes for them.
- **No LLM-authored guide content in v1.** The "detailed guide" used in the
  spike (a synthetic expansion of the real guide) stays as test material only.
  Offering an expanded guide after the first few interviews, built from the
  researcher's plan plus what they actually asked and never imposed, is a
  separate post-v1 idea, parked in the maintainer's planning notes.

### Measured on real interviews (27 Sep)

Corpus: the maintainer's own IKEA/"favourite object" guide (27 lines) and a
three-session trial project, both kept outside the repo — s1 (18 min, English
site), s2 (36 min, UK site, screen-share trouble), s3 (38 min, the German IKEA
site). 148 moderator turns ≥ 3 words, 101
quotes. Claude Sonnet 4.6, `scripts/spike_discussion_routing.py --transcripts`.

- **About 60% of the research questions actually asked are nowhere in the
  guide.** 31 of the 51 question-turns the model assigned are ad-libs; per
  session 60% / 64% / 57%. The merged guide is two-thirds retcon: 20 ad-lib
  items against 10 planned-and-asked. A hand correction for turns the model
  missed (≈5 planned re-askings such as `s3@16:53`, ≈5 ad-libs such as
  `s3@22:40` "pros and cons of each context") leaves it at ~59%.
- **Every planned item was asked by somebody.** None came out `○ never asked`.
- **The ad-libs are the good questions** — "delivery info gaps", "accidental
  impulse buys", "guest vs login", "is there a price trade-off for a narrower
  window?". A guide-only lens would have no place to put what they found.
- **The model slotted every ad-lib under a planned parent and promoted none.**
  The miss is delivery: 5 of 8 "Try to buy" items are about fulfilment (cost,
  minimum order, delivery vs collect, window, unavailable), the guide said
  *stop at the credit card*, and "Try to buy" was the heaviest territory (46
  of 101 quotes). That is a new top-level group the researcher would draw by
  hand — see the promotion rule below.
- **Routing: 100–101 of 101 quotes routed**, and the hand-check reads right.
  Built from what was asked, the guide absorbs nearly all the evidence;
  UNROUTED becomes rare rather than the conservative default.
- **Speaker attribution is an input risk.** In s2 many turns labelled `m1` are
  the participant narrating their own browsing, and one turn fuses both
  speakers. The asked signal is only as
  good as the moderator/participant split (s05b).
- **Parse instability** (the parse-only prompt): the same guide gave 4, 6 and
  5 territories on three runs. The reconcile runs gave 8 and 8, with item
  lists that differed in detail. See the hierarchy rules — structure should be
  decided by code from the LLM's items, not re-drawn by the LLM each time.
- **Cost:** reconcile + route for 101 quotes ≈ 26k in / 7k out tokens ≈ $0.18.

### The hierarchy — topic-led, time-ordered

Two levels, as before: **territory** (a research question/intent) → **item**
(a question, planned and/or asked). Every item carries a provenance mark,
which is the whole "planned vs retconned" story at a glance:

| mark | meaning |
|---|---|
| ● | planned, and asked (in N sessions) |
| ○ | planned, never asked — shown, dimmed; absence is information, not a failure |
| + | asked, never planned — an ad-lib |
| · (faint) | no guide uploaded: a normalised question, nothing said about planned or not (4 Oct) |

The key sits at the top of the navigator, in its box, and lists only the marks
the current view uses; its "not asked in this session" line is in the rows' own
grey (4 Oct).

Rules — the LLM proposes items with their `turns`; **code** decides structure,
so it is repeatable:

1. **Planned territories come from the guide's own spine**, in guide order.
2. **An ad-lib slots under the planned item it follows in time.** For each
   ad-lib, find the planned item whose turns most often immediately precede it
   across sessions; it goes directly after that item. Topic decides the
   territory, time decides the position inside it.
3. **An ad-lib cluster is promoted to its own territory** when it is asked in
   **≥ 2 sessions**, has **≥ 3 items**, and its routed evidence is at least the
   median territory's. Delivery passes all three; a one-session tangent (s3's
   "pros and cons of online vs in-store") stays folded. The LLM names the
   cluster; the rule, not the LLM, decides whether it stands alone.
4. **A promoted territory is placed by time**: at the median relative session
   position of its turns (delivery lands straight after "Try to buy").
5. **Moderator technique is not a question.** "Play back themes" (the
   researcher summarising back) and nudges are dropped from the items; they
   are method, not enquiry.
6. **Persist, then re-reconcile incrementally.** A new session adds asked
   turns; re-reconcile slots them into the persisted structure rather than
   redrawing it, so the researcher's edits and the sidebar do not reshuffle.

### Which quotes answer which question — two signals

1. **Semantic field match (primary).** Batched LLM classification against each
   territory's whole field: intent + planned wording + *the moderator's actual
   wording* for every asked item. The asked wording is what makes this work on
   ad-libs.
2. **Conversational anchor (corroboration).** The last reconciled question asked
   before the quote in the same session. This is the anchor the July design
   retired — rightly, when it pointed at single guide questions the moderator
   did not follow. Pointed at territories rebuilt from what was actually asked,
   it is a real second signal, and its machinery exists (`get_moderator_question`,
   built for the parked moderator-question pill).

Measured: the two **agree on 69 of 101** quotes. Of the 32 disagreements, 18
are s1, where the moderator spoke 8 times and the participant ran
the whole site task unprompted — the anchor was minutes stale and the semantic
route right every time. Most of the rest sit at task boundaries (replace ↔ buy
↔ reflect), where participants keep talking about the step they just left.

*Shipped rule (`structure.py` `decide_route`):* where anchor and topic agree,
that; where they disagree, the topic wins only at confidence ≥ 0.75 or with no
fresh anchor (240 s). The July rule, kept as reasoning:

**Rule:** semantic decides the territory. The anchor corroborates only while
fresh — within a few minutes and not across an s08 topic boundary. Agreement →
confident; semantic alone → routed; semantic against a fresh anchor → routed,
marked low-confidence for review. **Item level** (which question a quote
answers) comes from a fresh anchor only, as a disclosure — never as the
grouping.

### Reuse — what already exists

| Need | Existing mechanism | Where |
|---|---|---|
| Who asked what, and when | speaker codes `m*`/`p*` (role detection) + timecoded turns | s05b; `transcripts-raw/*.txt` (`session_segments.json` carries no speaker codes) |
| The preceding moderator question for a quote | `get_moderator_question` | `server/routes/quotes.py` (pill parked, machinery live) |
| Time segmentation of each session | s08 topic boundaries, incl. `screen_change` transitions | `topic_boundaries.json` |
| Cross-session routing of quotes to buckets | s11 thematic grouping | `stages/s11_*` (open decision 2) |
| Guide ingest | s04 docx parser; `.md`/`.txt` direct; native drop + `NSOpenPanel` | `stages/`, `desktop/` |
| LLM call, structured output, cost | `LLMClient.analyze`, `load_settings()`, `estimate_cost` | `llm/` |
| Quote cards, groups, editing, runs | `QuoteCard`, `QuoteGroup`, `EditableText`, `seq-*` | `frontend/src/islands/`, `organisms/signals.css` |
| Lens slot, nav, shortcuts | `enum Tab` + `TAB_ROUTES` + `MenuCommands` | `desktop/`, `frontend/src/shims/navigation.ts` |
| Adding sessions without redoing work | incremental analysis | `docs/design-incremental-analysis.md` |

### Innovations — what is genuinely new

1. **Reconcile** — guide ⋈ moderator turns → merged items with provenance and
   `turns`. Prompt written: `bristlenose/llm/prompts/reconcile-discussion-guide.md`.
2. **Structure by code** — time-slotting of ad-libs, the promotion rule,
   time-placement of promoted territories, persistence and incremental
   re-reconcile (rules 2–6 above). Deterministic; this is also the answer to
   parse instability.
3. **The two-signal router** with anchor freshness.
4. **The provenance glyphs** (● ○ +) in a terse two-screen sidebar, plus the
   evidence-bars atom and response-group molecule already listed.
5. **Guide as an input** — a project artefact that is not a recording, stored
   under `.bristlenose/` with a fingerprint.

### Across the guide spectrum — v2, 27 Sep (evening)

Reconcile prompt v0.2.0: every asked question gets one of five fates —
**asked as planned** (●), **ad-lib on topic** (+), **new section** (✦),
**placed by flow** (↦), or **standalone** (·) — plus a role, **opener** (⌃) or
**closer** (⌄), for questions that belong to a moment rather than a topic.
The model judges meaning and sorts questions into those buckets; code
(`structure()` in the spike) applies the new-section rule, orders sections by
median relative time, and places homeless questions by flow: the section the
session was in when it was asked, an opener taking the next section and a
closer the previous one. A question the timeline cannot place is standalone.

| guide | sections | asked as planned | ad-lib on topic | new section | by flow | unplanned share |
|---|---|---|---|---|---|---|
| none (trial project) | 4 ✦ | — | — | 25 items | 9 | 100% by definition |
| terse, run a | 7 | 11 | 11 | 0 | 1 | 46% |
| terse, run b | 6 | 8 | 24 | 0 | 3 | 58% |
| detailed † | 6 | 21 (+14 ○) | 3 | 0 | 4 | 15% † |
| none (Rockclimbing, 7 synthetic sessions) | 8 ✦ | — | — | 33 items | 3 | 100% by definition |

† The detailed guide is a synthetic expansion of the real one, **written after
reading these transcripts** — it anticipates "store vs online" and "delivery vs
collect". It proves the mechanics (sub-questions kept, 14 planned items visibly
never asked), not the share. A detailed guide written *before* the sessions is
still the missing input.

What this shows:

- **No guide works.** From the questions alone the model recovered the study's
  real spine (object → trip → site task → checkout) on the trial project, and a
  clean eight-section guide on Rockclimbing, where closing questions formed
  their own "Closing" section and a stray IKEA recording in that project
  contributed nothing (its quotes stayed UNROUTED, correctly).
- **Flow placement catches junk as well as homeless questions.** With no guide,
  "Transcript editing idea", "Mask personal data" and "Scope creep: tea towels" —
  chatter and mis-attributed participant speech — were filed as homeless
  questions and placed by flow. The filter for *not a research question* has to
  run before placement, or flow placement becomes a junk drawer.
- **The structure is still not stable.** Two runs of the same guide gave 7 and 6
  sections, 23 and 36 items, and an unplanned share of 46% and 58%. Code now
  decides order and placement, but the model still re-draws the *planned spine*
  and the item granularity each run. **Next step: freeze the spine.** Parse the
  guide once into planned sections and items and persist them; then classify
  each asked *turn* against that fixed spine (matches planned item N / ad-lib in
  section X / new-cluster label / not a question). Structure then changes only
  when the guide or the sessions do.
- **Delivery was never promoted.** On every real run the model kept the delivery
  ad-libs inside "Try to buy" — defensible, since delivery is part of buying.
  Whether it is a new top-level section or a **sub-group within** "Try to buy"
  is a researcher's call; the gold labels will say which.
- **One over-long label must not sink a run.** The detailed guide failed twice on
  a 35-character label against a 34-character cap. Labels over budget are now
  clipped and counted, not fatal.
- **The timing anchor agrees more when sections are broader**: 69/101 (7
  sections), 77 (6), 79 (detailed), 83 (4, no guide).
- Cost: ≈ $0.15–0.21 per reconcile + route run.

**Gold labels.** A pre-filled workbook (kept with the guide, outside the repo:
it holds participant speech) asks the researcher to label each of the 148
moderator turns (kind, planned question, section or `NEW:` or `STANDALONE`,
opener/closer) and each of the 101 quotes (section). A Results sheet computes the
researcher's unplanned share next to the model's, and section agreement for
turns and quotes, with live formulas.

### Synthetic data — the evaluation plan

Real data gave the direction; a labelled corpus is what makes the rules
measurable. Two tracks:

- **Gold-label the real corpus once.** Hand-label the trial project's 148 moderator
  turns: planned item / ad-lib / technique / chatter / mis-attributed speaker.
  About half an hour, and it turns the 60% figure and item recall from model
  estimates into measurements.
- **Generate a labelled synthetic corpus** with `docs/testing/test-data-generation.md`,
  extended so ground truth is written *before* the dialogue. Per session a run
  sheet decides, for each guide item: asked verbatim / reworded / split /
  out of order / skipped; plus scripted ad-libs, including **one planted
  cross-session theme** (must be promoted) and **one single-session tangent**
  (must not be). Every moderator turn and every answer span carries its gold
  territory and item. **Write the guide to a file beside the VTTs.** The existing
  synthetic sets (`trial-runs/Fishkeeping`, `trial-runs/Rockclimbing`) have no
  guide at all, so they can stand in only for the no-guide case.
  Variants: a clean-attribution set; the same set with ~15% of turns given the
  wrong speaker (the s2 failure); a non-English set.
- **Metrics:** ad-lib share error; item recall over asked turns; promotion
  precision/recall; quote routing precision/recall at territory level; anchor
  agreement and the freshness window that maximises it.

## Open decisions

1. **Routing mechanism** — batched-LLM-classify for v1 (no new infra, ~1–3× the
   existing call budget) vs embeddings (near-free at runtime, but net-new infra).
   *Rec: batched for v1; embeddings a v2 cost win.* **Spike ran batched (27 Sep):
   ≈ $0.18 for reconcile + route of 101 quotes.** Nothing measured argues for
   embeddings in v1; ready to take. **Decided: batched, built in
   `bristlenose/discussion/` (3 Oct).**
2. **Fresh router vs parameterise `s11`** (which already routes quotes to buckets
   with cross-session voting). *Rec: fresh router for v1 — decoupled.* **Decided:
   fresh router.**
3. **Spike corpus** — a real project with a guide + transcripts (ideal), or
   synthesize one (pair transcripts with a plausible guide). Run privately.
   **Answered 27 Sep:** the real one exists (the private trial project + the IKEA
   guide) and a synthetic one is planned — see "Synthetic data".
4. **Splitting heavy territories** (a Walkthrough-sized area may exceed ~5 min and
   want splitting into two) — let the model decide from the heuristic; watch in the
   spike.

## Sequencing

*4 Oct 2026: Phases A and B shipped (the plan's §7); the native empty-state page
did not, and per-territory stance clustering, signal bars and embeddings are not
built.*

- **Phase A — routing spike (backend, no UI).** On one real project: parse guide →
  route existing quotes to territories (chosen mechanism, intent/field-only) →
  report `routed X of Y` + per-territory buckets + a hand-checked precision sample
  + real token cost. This de-risks the only real unknown. Blocked on decisions 1 &
  3.
- **Phase B — the lens in bn.app** (Phase A green first): native empty-state page +
  webview Discussion tab (GuideSidebar, signal bars, territory → response-groups,
  scaffold disclosure), reusing `QuoteGroup` / `EditableText` / `seq-*`.
- Then: per-territory stance clustering polish; terser distillation; the "how it
  was actually asked" disclosure; embeddings routing.

## Proof

- **As built**, mocked first: `docs/mockups/discussion-lens-layout.html` (what
  gives way as the window narrows) and `docs/mockups/discussion-guide-tabs.html`
  (the tabs and the guide column with and without a guide).
- **UX** is mockup-proven: `docs/mockups/mockup-discussion-lens.html` (the lens,
  incl. a deliberately dense territory, signal bars, run brackets, accurate
  PersonBadge/timecode/sentiment markup, native-empty-state toggle).
- **Distillation** is proven on real guides:
  `docs/mockups/mockup-discussion-guide-distillation.html` (two US-federal
  public-domain 18F guides, verbatim → territories), plus a private, gitignored
  local run against a real, richly-structured 40-question government guide — the
  extreme case, including a safeguarding block that must not become data. The
  bucket model held. Routing is what Phase A proves.
