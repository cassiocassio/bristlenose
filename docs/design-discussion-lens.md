---
status: pending
last-trued: 2026-07-26
trued-against: HEAD on 2026-07-26
---

<!-- Trued 2026-07-26 (/true-the-docs --doc): Archetype P (pending/aspirational).
     Authored + consolidated this session; the feature is unbuilt (design + mockups
     + a routing spike only), so there is no shipped reality to reconcile against —
     the doc IS the current design intent. Full agent audit deliberately skipped
     (doc is at HEAD; volume-as-success avoided). Re-true once Phase A/B ship. -->

# Discussion lens — the researcher's guide, answered by the evidence

*Design doc for a new macOS-app report lens that takes the researcher's own
discussion guide and re-projects the extracted quotes onto it — organising
findings by the researcher's **own domain model** instead of emergent themes.
Sibling to the Quotes and Analysis lenses; reuses the quotes-page card, editing,
and sequence machinery wholesale.*

Status: **straw man, consolidated 26 Jul 2026** after a long design conversation
and a usual-suspects review. Findings and their disposition live in the
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

A sixth tab, **Discussion**, in the macOS app's NavBar next to Quotes /
Codebook / Analysis. It reads like the Quotes lens — same quote cards, badges,
inline editing, sequence treatment — but its **navigation is the researcher's
guide** (the ~5–12 territories) and its grouping comes from routing quotes onto
those territories.

The proposition, in one line: **you hand the researcher their own domain map
back, populated with the evidence that emerged and ordered to show the balanced
spread.** Legible in a way emergent themes are not — it's the thinking they did,
answered by reality.

## Surface & packaging — macOS desktop only

**The Discussion lens ships only in the bundled macOS app (`bn.app`), not in the
open-source CLI / served SPA.** Product rationale: it's a **paid-tier lever** for
researchers who work from a structured guide; the CLI/Linux crowd skews less
formal about guide structure and the cost (parse + route + cluster) isn't
warranted there.

Mechanics (a gate, not a fork): the desktop app **is** the React SPA in a
WKWebView, so the lens, its route, and the tab are present only under
`__BRISTLENOSE_EMBEDDED__`, mirroring the existing `ct()`/`dt()` platform-text
forking. The CLI report and exported HTML never mount it. *(Note: the repo is
AGPL, so the code stays visible even though the feature is packaged
desktop-only — a distribution decision, not a code-visibility one.)*

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
| Argument-run visual | `quote-sequences` `seq-*` left-rule treatment (generalise out of `.signal-card-quotes`) | `organisms/analysis.css` |
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
  guide" (never the empty state); parsed OK → the lens.
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

## Open decisions

1. **Routing mechanism** — batched-LLM-classify for v1 (no new infra, ~1–3× the
   existing call budget) vs embeddings (near-free at runtime, but net-new infra).
   *Rec: batched for v1; embeddings a v2 cost win.* **Gates the spike.**
2. **Fresh router vs parameterise `s11`** (which already routes quotes to buckets
   with cross-session voting). *Rec: fresh router for v1 — decoupled.*
3. **Spike corpus** — a real project with a guide + transcripts (ideal), or
   synthesize one (pair transcripts with a plausible guide). Run privately.
4. **Splitting heavy territories** (a Walkthrough-sized area may exceed ~5 min and
   want splitting into two) — let the model decide from the heuristic; watch in the
   spike.

## Sequencing

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

- **UX** is mockup-proven: `docs/mockups/mockup-discussion-lens.html` (the lens,
  incl. a deliberately dense territory, signal bars, run brackets, accurate
  PersonBadge/timecode/sentiment markup, native-empty-state toggle).
- **Distillation** is proven on real guides:
  `docs/mockups/mockup-discussion-guide-distillation.html` (two US-federal
  public-domain 18F guides, verbatim → territories), plus a private, gitignored
  local run against a real, richly-structured 40-question government guide — the
  extreme case, including a safeguarding block that must not become data. The
  bucket model held. Routing is what Phase A proves.
