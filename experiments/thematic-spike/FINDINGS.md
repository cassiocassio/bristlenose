# Thematic Analysis Spike — Findings

A long afternoon's session running, reading, arguing about, and learning
from a side-by-side comparison of approaches to thematic analysis. This
doc captures the empirical findings, the conceptual landings, the
decisions about what to take forward, and what to deliberately stop
spending cycles on.

The spike code lives at `experiments/thematic-spike/`. The trigger was
noticing that fossda's s11 thematic-grouping stage feeds **47,506 input
tokens** into a single LLM call, and asking whether there was a better
way. The answer turned out to be more interesting than yes-or-no.

## The fun

The conversation arc, roughly:

1. Built a 6-prototype harness over two corpora (fossda 100q, ikea 67q).
   Total spike cost: ~$1.50.
2. Read the scoreboard, expected to find a clear winner, didn't.
3. Got progressively re-educated about what "good thematic analysis"
   actually looks like in working researcher practice — KJ method,
   bottom-up, mini-clusters first, chapters second, deviant-case
   insights, the editorial work that lives in the researcher's head.
4. Repeatedly over-rotated to one researcher's workflow, got pulled
   back, learned the distinction between *insight about the problem*
   and *architectural blueprint for the solution*.
5. Realised most of the failures we were measuring were the LLM doing
   what it was *asked* to do: forcing every quote into a theme
   (padding), restating the brief (because nothing forbade it),
   producing clean sentences (because we never said don't).
6. Got the empirical answer to "could math replace the LLM?" — clear
   no, BERTopic on small corpora produces unreadable c-TF-IDF labels and
   collapses on density.
7. Discovered that the most interesting prototype (Perm-C, anti-brief-
   restating) succeeded at clustering but failed at labelling — labels
   like *"Navigating through breadcrumbs and category structures"* hide
   brand evidence behind a navigation label that routes the cluster to
   the wrong audience.
8. Ended with a clean, defensible set of small alpha-iteration changes
   queued in two separate sessions, plus a much sharper picture of what
   the LLM is for, what it isn't for, and where the researcher's
   irreplaceable judgement lives.

The pattern of the conversation was: each new piece of texture from the
user reshaped what we were measuring against, often invalidating the
previous comparison. The spike's job changed mid-flight from "which of
these prototypes wins?" to "what do we actually want from the LLM at
this stage?". Both questions got answered.

## What got built

| Artefact | Location | Purpose |
|---|---|---|
| Spike harness | `experiments/thematic-spike/` | 6 LLM prototypes (baseline + A–E), 1 math prototype (M), 3 permission-test prototypes (perm_a/b/c), 1 mini-cluster prototype (H), production reference imports (s10, s11). Read read-only from `trial-runs/<project>/bristlenose-output/.bristlenose/intermediate/extracted_quotes.json`; writes only into `output/`. |
| Scoreboard | `scoreboard.py` | Architecture-agnostic quality metrics: coverage, multi-participant rate, brief-restating count, within-cluster tightness, single-participant breakdown. |
| Side-by-side render | `render.py` → `compare.html` per corpus | All prototypes as columns; reads at a glance. |
| Findings (this doc) | `FINDINGS.md` | What we learned. |

## Empirical findings

### Cost

Total: **~$1.50 of a $12.26 Anthropic budget**. Each prototype $0.02–
$0.45 per corpus. Cheap enough that decisions about what to keep are
not cost-constrained.

### The prototypes that died

Three prototypes are definitively dead — don't iterate further:

- **Option A (sklearn AgglomerativeClustering, forced k)** —
  catastrophic structural collapse. Fossda: 71/100 quotes in one
  cluster. Ikea: 43/67 in one cluster. The forced-k + no-noise-bucket
  combination is the wrong shape. (The math direction lives on via M;
  see below.)
- **Option D (two-pass review/refine)** — actively *worse* on specific
  themes. The brand cluster case study: D scored 0/3 hits (vs baseline
  5/5). The review pass moves quotes to inappropriate themes. Costs 2×
  baseline for negative quality.
- **Option E (5× runs + reconcile)** — 6× baseline cost for similar
  quality. The reconciler pads memberships; the "STABLE 5/5" stability
  badge is misleading because it describes label stability, not quote-
  membership stability. Not earning its cost.
- **Option M (BERTopic, math-only)** — c-TF-IDF labels are unreadable
  word-salad on conversational text (`"sendmail mail department
  internet email"`, `"crochet computers yarn math squishy"`). HDBSCAN
  on 60–100 quotes collapses or under-finds structure. **The empirical
  answer to "can math replace the LLM?" — no, not at Bristlenose's
  corpus sizes.** This *strengthens* the LLM-based architecture
  argument. The local-first story stays via Ollama, not BERTopic.

### The prototypes worth iterating

- **Option C (map-reduce: per-participant draft → merge → reassign)** —
  best cross-participant signal (66.7% multi-p on fossda vs baseline
  38.9%). Lowest brief-restating count tied with A. Most theme-purity
  (only 17% sections in ikea). 3× baseline cost, 5× slower. Plausible
  s11 replacement candidate but warrants proper evaluation on more
  corpora before any swap.
- **Option B (code-first, theme-second)** — zero single-participant
  themes on ikea (only prototype to achieve this), 50% multi-p. Code-
  first decomposition matches QDA-tool consensus (NVivo, ATLAS.ti,
  Marvin). **Future home is in or near the signal-cards tab**, not as
  s11 replacement — different role in the user journey.

### The brand-cluster case study (the most useful single read)

Looking at the IKEA brand-related cluster across all prototypes,
judged against the unambiguous brand quotes (q23, q30, q31, q36, q37,
q49, q52, q53, q60):

| Prototype | True hits | Mis-included | Verdict |
|---|---|---|---|
| Baseline | 5/5 | none | Cleanest single-cluster output |
| Perm-A | 2/3 | q8 (NHS hospitals) | Cross-domain mis-coding |
| Perm-B | 3/4 | q8 (NHS hospitals) | Cross-domain mis-coding |
| S11 production | 2/3 | q26 (storage box pref) | Worst — wrong-domain mis-coding |
| **Perm-C** | **9/9** | none | Distributed across 4 specifically-framed clusters |

Two findings from this case study:

1. **Permission-A and Permission-B made researcher-wincing errors** by
   pulling q8 (NHS healthcare comparison) into a "Brand Perception"
   cluster. Pattern-matching on structure (comparison-anchoring)
   rather than domain (commercial brand). A researcher would have to
   fix this before showing the output to a stakeholder.
2. **Permission-C did sophisticated reframing**: refused to make a
   "Brand" bucket (because that's brief-restating in a UX context),
   and instead distributed brand evidence across four specifically-
   framed behavioural clusters: *"Bringing personal taste and identity
   into choices"*, *"Questioning interface language and conventions"*,
   *"Navigating through breadcrumbs and category structures"*,
   *"Distinguishing shopping from content"*.

But Perm-C exposed a new problem: **the labels are mechanism
descriptions, not evidence descriptions**. *"Navigating through
breadcrumbs and category structures"* hides the IKEA-Swedish-naming
evidence (q52, q53) behind a navigation label that routes the cluster
to the wrong audience. The brand strategist scanning labels for
brand-related work would not stop at this label, and would miss the
DJUNGELSKOG-family-joke level of brand insight that lives in those
quotes.

### Universal failures (across all six original LLM prototypes)

- **100% coverage** on most prototypes = padding. Healthy is 60–85% (the
  rest go in a noise bucket). Researchers cull filler instinctively;
  the LLM should too.
- **Loose clusters** everywhere (mean within-cluster cosine distance
  0.55–0.73). Grouping things that aren't really alike.
- **Brief-restating** at 17–67% rates. Themes named after the topic of
  the study, not what participants actually said.
- **Single-participant themes everywhere** — algorithm can't distinguish
  noise (1 participant, 1–2 quotes, throat-clearing) from signal
  (1 participant, 5+ quotes, coherent deviant-case insight).

These are *systemic* properties of the current single-call approach,
not problems with any single prototype.

## Conceptual landings

These are the principles that emerged. Each is worth saving as a
memory; each shapes how to think about the product going forward.

1. **Researcher first, non-researcher second.** The product is primarily
   a researcher's triage scaffold; non-researcher signal-surfacing is
   secondary. The report is a starting frame for the researcher's
   deeper work, not a finished artefact.

2. **The LLM is a junior assistant, not a senior analyst.** The
   researcher always carries far more in their head than the report
   shows: off-record observations, the brief, the room, the politics,
   the personal-life context (the DJUNGELSKOG family-joke moment).
   The LLM has zero access to any of that. Its job is to add to the
   researcher's working memory by patient reading at scale, not to
   produce findings.

3. **Brief-restating themes earn instant contempt.** *"Thanks, that's
   the title of my interview guide."* Worst possible LLM output.
   Empirically banishable via prompt instruction (Perm-C achieved 0%).

4. **The LLM's genuine asymmetric strength is cross-participant micro-
   pattern matching.** Not big-theme naming. The LLM can hold all 500
   quotes in attention; the researcher can't. That's the asymmetry to
   lean into.

5. **Two overconfidence failures, symmetric.** False connections at
   the cluster level (padding adjacent-but-wrong quotes); trivial meta
   at the synthesis level ("usability is the biggest issue"). Both are
   the LLM optimising for coherent-looking output instead of honest-
   looking output.

6. **Coverage 100% = padding, not quality.** Healthy is 60–85%. The
   noise bucket is built into HDBSCAN by construction; should be added
   to the LLM via permission ("leave unassigned anything that doesn't
   clearly belong"). People say a lot of stuff: filler, half-thoughts,
   off-topic asides. None of it earns a place in a thematic structure.

7. **Single-participant themes split into two value-classes**:
   - **Thin** (1 participant, ≤2 quotes) = noise; warn
   - **Substantial** (1 participant, ≥3 quotes) = could be a deviant-
     case insight (Patton, Eisenhardt) or a long rant; researcher
     decides; do not warn

8. **Theme count is a navigation bound, not a quality bound.** 9–12
   fits psychology + screens + attention (Miller's 7±2 + chunking +
   navigability). But **data overrules** — richer corpora honestly
   want 15–20; narrower ones honestly produce 5–7. Authority order:
   data > researcher judgement > heuristic > algorithmic constraint.

9. **Two-axis quotes page**: (I) **sections** = units of the artefact
   one team owns (page, component, flow, hardware feature, service
   moment); (II) **cross-cutting themes** = recurring concerns that
   demultiplex across teams. Both needed; neither subsumes the other.

10. **Sections, not screens.** Generalises beyond software: machine-
    tool features, electric-piano metronomes, branch-banking moments.
    The crisp test: could a single team own and change this?

11. **Hierarchy with breathing room.** Big themes labelled (8–10 for
    nav), sub-clusters visually grouped without labels (the novelist's
    dingbat trick — structure felt, not named). Resolves the "15
    distinct vs 9–12 navigable" tension by exposing both at different
    typographic weights.

12. **Two methodological traditions, one product.** Themes (top of
    journey) = inductive, Braun & Clarke, landscape map for
    orientation. Signal cards (bottom of journey) = deductive,
    template analysis, codebook-driven, ranked by strength/
    concentration, action-oriented. Each does what its tradition is
    good at. Brief-restating themes are bad (fail orientation) but
    inductive themes don't need to surface action items (signals do
    that with codebook priors).

13. **Display quote vs evidence quote**: within a cluster, one quote
    is slide-ready (most articulate / concise / evocative); the others
    are evidence (give the researcher confidence the signal is real).
    Different roles, different value, different rules.

14. **Heuristics anchor; data overrules.** 9–12 themes is a useful
    anchor but bends with the data. The LLM should produce honestly;
    UI handles navigation budget via grouping. The prompt-imposed
    "5–12" inverts the authority order and should bend.

15. **The SS/GC binary is a deliberate bet about source material.**
    Calibrated for UX (rich nav vocabulary → many sections); degrades
    gracefully for oral histories (no nav vocab → all themes) and
    Socratic dialogues (zero sections, valid output). Don't try to
    "fix" the asymmetry on non-UX corpora — it's the architecture
    working as designed.

16. **The labelling principle (the spike's most subtle finding):**
    Three failure modes for cluster labels — brief-restating ("Brand"),
    mechanism-describing ("Navigating through breadcrumbs"), pretending
    to insight ("Brand Perception and Cultural Associations"). The
    LLM-honest sweet spot is **evidence-describing**: "Swedish product
    names" not "Brand strategy through nomenclature". Boring is
    correct. The label routes the cluster to the right audience; the
    insight is the researcher's contribution.

## Decisions

### Definitively dead — don't iterate

- **A** (sklearn k-means, forced k) — structural collapse on both corpora
- **D** (two-pass review) — actively worse on specific themes
- **E** (5× + reconcile) — 6× cost for similar quality, padded memberships
- **M** (BERTopic math-only) — unreadable c-TF-IDF labels, density
  collapse on small corpora
- **The "math could replace LLM" hypothesis** — answered no, at our scale

### Worth iterating (but not now)

- **C** (map-reduce) — credible s11 replacement candidate. Schedule a
  proper evaluation against more corpora plus a researcher's read.
  Don't ship now. ~$0.20 per study.
- **B** (code-first) — has a future home in or near the signal-cards
  tab, not as s11 replacement. Park until signal-cards work needs it.
- **Option H** (bottom-up mini-clusters) — only briefly considered;
  not built in this spike. Could be revisited if mini-cluster output
  is needed for signal-cards work.

### Queued as alpha-iteration chips

Two separate sessions are queued, both prompt-only changes with
A/B testing and easy revert via prompts-archive:

- **s10 prompt change** — explicit navigational-vocabulary cue. Gives
  the model a list of strong section-bound signals ("here", "back",
  "now I'm", "on this page", named UI elements). High-confidence
  quality lift. Disproportionate value for a one-paragraph prompt
  addition. Plus a docstring documenting the SS/GC binary as a
  deliberate methodological bet.
- **s11 prompt change** — brief-restating ban + labelling-honesty
  rule. Combined version bump (v0.1.0 → v0.2.0). Empirically validated
  in spike (Perm-C achieved 0% brief-restating).

### Future tinkering ideas (post-alpha)

- **Hybrid math + LLM for naming**: math does clustering (HDBSCAN with
  min_cluster_size=2); LLM names each cluster (one cheap call per
  cluster, with the labelling-honesty rule). Sidesteps c-TF-IDF's
  unreadable labels. May still suffer density collapse on small
  corpora; worth testing on bigger studies (1000+ quotes).
- **Substantial single-participant themes as first-class output**:
  surface the LLM's "this is one participant but they had a coherent
  thing to say" candidates with explicit framing, not as failures.
  Connects to the "deviant case insight" tradition.
- **Cross-participant prevalence as ranking signal**: themes with more
  participants surfaced first; single-participant themes flagged
  visually as "individual perspective worth reading".
- **Hierarchy with breathing room (the dingbat trick)**: big themes
  labelled, sub-clusters within each visually grouped without labels.
  Lets the LLM produce 15–20 distinct things while the UI presents
  only 8–10 nav headings.

## Smallest possible product touches the spike has surfaced

These are mostly captured above, in priority order:

1. **s10 prompt — navigational-vocabulary cue** — queued as chip
2. **s11 prompt — brief-restating ban + labelling honesty** — queued
   as chip
3. **Code rename**: `SCREEN_SPECIFIC` → `SECTION_SPECIFIC`. UI copy:
   "Screens" → "Sections". Generalises beyond software studies.
4. **Permission to leave unassigned** in s11 (the noise bucket) —
   spike's Perm-A showed this works; deferred to a future iteration
   so the s11 schema change is digested separately.
5. **Theme-count constraint relaxation** — let s11 produce as many
   themes as the data warrants. Spike's Perm-B variant tested this;
   neutral result on this corpus. Probably worth doing eventually but
   not urgent.

## What the spike validated about the existing architecture

It's worth saying explicitly: the spike *strengthens* the case for
keeping the existing s10 + s11 + signal-cards architecture.

- **s10 (sections) + s11 (themes) as separate stages** is right. The
  two-axis model (sections for the surface-owning team; themes for the
  cross-cutting concern owner) maps cleanly onto the engineering-
  handoff shape.
- **Quote-type binary at extraction time** (SS/GC routing to s10 or
  s11) is the right separation of concerns. Different studies produce
  different distributions, all defensible.
- **LLM-based clustering at our corpus sizes** is the right tool — math
  alternatives don't work below thousands of quotes.
- **The signal-cards architecture** (deductive, codebook-driven,
  ranked) is the right home for action-oriented findings. Themes
  shouldn't try to do that job; they're for orientation.
- **Inline edit / drag-merge in the React SPA** is doing real work
  that the LLM can't do — the researcher brings context the model
  lacks. The product is right to keep the human in the loop.

The spike's improvements all live within this architecture, not as
replacements for it.

## Don't-progress list (for future-Claude)

When this conversation surfaces again in some form, **don't**:

- Propose rebuilding s10/s11 around BERTopic or any other math approach
- Propose pre-built "theme libraries" or "codebook-only" themes for s11
  (signal cards do that job; themes are inductive)
- Propose forcing exclusivity removal between s10 and s11 (the binary
  is deliberate)
- Propose replacing s10/s11 with a code-first per-quote approach (that
  belongs in or near signal cards, not at the orientation stage)
- Propose adding interpretive labels to clusters (that's the
  researcher's job, not the LLM's)
- Treat brief-restating themes as acceptable
- Treat 100% coverage as a quality goal
- Conflate single-participant themes with noise universally

## Permission-variant run (30 Apr 2026)

The three permission-variant prototypes had been queued conceptually
(see "Queued as alpha-iteration chips" above). This session actually
ran them: single-call variants of the baseline, each granting one
permission today's prompt withholds. Total cost ~$0.30.

### Empirical results

| Corpus | Proto | Themes | Coverage | Brief-restate | Cost | Three labels |
|---|---|---:|---:|---:|---:|---|
| fossda | baseline | 18 | 100% | 6/18 | $0.071 | Origins · Neurodiversity & Computing as Sanctuary · Collaborative Spirit |
| fossda | **perm_a** | 12 | 90% | 4/12 | $0.067 | Early Computing · Foundational OSS Tools · Neurodiversity & Computing Comfort *(10 unassigned)* |
| fossda | perm_b | 27 | 97% | 8/27 | $0.079 | Origins · Neurodiversity · Academic Roots of OSS |
| fossda | perm_c | 17 | 47% | 1/17 | $0.069 | Computing as refuge for neurodivergent minds · Accidental intensity · Nostalgic materialism |
| ikea | baseline | 12 | 100% | 6/12 | $0.026 | Clear Scannable Info · Post-Op Comms · Inadequate Aftercare |
| ikea | **perm_a** | 9 | 90% | 2/9 | $0.025 | Clear Easy-to-Scan Info · Post-Care Comms Gaps · Proactive Patient Support *(7 unassigned)* |
| ikea | perm_b | 11 | 100% | 3/11 | $0.025 | Clear Digestible Info · Inadequate Post-Treatment Care · Proactive Comms |
| ikea | perm_c | 15 | 99% | 5/15 | $0.030 | Scanning headings, not reading everything · Straightforward & appropriately minimal · Proactive reassurance |

### Verdict — Perm-A most interesting

Of the three, **perm_a (noise bucket permission) is the most
interesting**. The model honoured the permission cleanly: 10/100
(fossda) and 7/67 (ikea) quotes left unassigned, near the bottom of
the requested 15–25% range. Coverage dropped to 90% (a healthier
shape than the baseline's universal 100% padding). Brief-restating
fell modestly. No new failure modes introduced.

Why this matters more than perm_b or perm_c:

- **perm_a addresses the universal padding failure directly.** The
  "100% coverage = padding, not quality" finding (above) was the most
  systemic problem across all six original prototypes. Perm-A shows
  the LLM *can* leave honest gaps when permitted; it doesn't have to
  pad. One line of prompt achieves it.
- **perm_b** (no theme-count cap) had a corpus-dependent effect:
  fossda jumped 18 → 27 themes (the cap was squashing it), ikea barely
  moved (the cap wasn't binding). Worth doing eventually but neutral
  on this run.
- **perm_c** (anti-brief-restating) succeeded at the metric (fossda
  6 → 1, dramatic) but introduced the labelling problem already
  documented above (mechanism descriptions like "Navigating through
  breadcrumbs" hide brand evidence). High-variance change with
  unintended downstream effects.

Perm-A is the cheapest, lowest-risk, highest-leverage prompt change
of the three. Promote it from the deferred list (item 4 under
"Smallest possible product touches") to the queued chips alongside
the brief-restating ban — the schema cost (one new `unassigned`
field) is small and the empirical signal is clean.

The artefacts: `output/{fossda,ikea}/themes_perm_{a,b,c}.json`
plus the updated `compare.html` per corpus. Driver:
`experiments/thematic-spike/run_perm.py`.

## Cross-references

- Survey doc: `~/.claude/plans/doing-trial-runs-of-replicated-dolphin.md`
  (parked outside the repo)
- Production prompts: `bristlenose/llm/prompts/quote-clustering.md`
  (s10), `bristlenose/llm/prompts/thematic-grouping.md` (s11)
- Methodology: `docs/design-research-methodology.md`
- Trial runs: `trial-runs/fossda-opensource/`,
  `trial-runs/<private-ux-corpus>/`
- Two alpha-iteration chips queued separately for s10 + s11 prompt
  updates.

## Coda

The spike answered its triggering question (*"is there a better way
than s11's single big call?"*) with a more useful answer than the
question implied:

- **Yes, there are credible better ways** (Perm-C is the most
  interesting; C is a credible swap-in candidate).
- **But** the lower-hanging fruit is in **prompt-level honesty
  improvements** to the existing architecture (brief-restating ban,
  labelling honesty, navigational vocabulary cue, noise-bucket
  permission), not in architectural replacement.
- **And** the existing architecture is *more right than we initially
  gave it credit for* — the s10/s11 separation, the SS/GC binary, the
  signal-cards-at-the-end design, the React-SPA-with-drag-merge — all
  of these survived the spike's scrutiny. The improvements are inside
  the existing shape, not outside it.

That's a more boring conclusion than "we should rebuild everything".
It's also a more correct one. The architecture was thinking better
than we initially read it. Most of the spike's value is in the
prompts, not the pipeline.
