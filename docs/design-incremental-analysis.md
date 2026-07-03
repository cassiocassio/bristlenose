# Incremental analysis and codebook lock

**Status:** Thinking document. Not a spec. Post-TF design problem.
**Sibling docs:** `docs/methodology/tag-rejections-are-great.md`, `docs/methodology/consent-gradient.md`, `docs/design-research-methodology.md`, `docs/design-analysis-future.md`.
**Predecessor:** TF multi-project plan descoped #12 ("add new interviews to existing project") because this is its real shape — not a button to wire up, a methodology to design.

---

## The problem

A researcher with 3 transcripts runs Bristlenose. They get back themes, sections, quotes, sentiment patterns. They spend an hour starring quotes that matter, hiding ones that don't, adding their own tags ("compliance concern", "calls back to onboarding"). They write a Sprint 1 mid-study note for their stakeholder.

Three days later, two more interviews arrive. They want to add them to the project and re-analyse.

Naive answer: re-run the whole pipeline. Same prompts, more data, regenerate everything. Two problems:

1. **The user's work evaporates.** The starred quotes might not even exist anymore — quote extraction is non-deterministic and the re-run produces different boundaries. The tags they added are attached to phantom quotes. The hides come back unhidden.
2. **The structure shifts under them.** The "Homepage Performance" theme they referenced in the stakeholder note is now "Performance & First Load". The two quotes they were going to lead with have been re-clustered into different sections.

Both failures are real product failures and both come from the same root cause: **the pipeline treats every run as if it were the first**.

---

## The physical-stickies model (the grounding)

Before any system shape, the design needs to honour how researchers actually do this work by hand. The Sharpie-on-Post-It era gives us the design constraints, not the LLM era:

**1. Quotes are immutable artefacts.** Once you write a quote on a sticky, you never rewrite it. You might *demote* it, *move* it, *stack* it under a better one, *eventually peel it off the wall* — but the words stay the words. The quote IS its text.

**2. Subheadings (small clusters) are practically durable, not metaphysically fixed.** Once you've formed a sub-group of 4–6 related stickies, the *cost of resorting it* usually outweighs the analytical gain. With more data, the most common mutations are small and local: a better hero quote arrives and gets promoted, a weaker quote gets demoted into the fan, sometimes a mini-cluster that seemed important in the first 3 interviews becomes a *secondary point* once 3 more interviews reveal it was over-weighted in the small sample. Trim / expand / sharpen / demote — yes. Wholesale break-up — rare.

**3. Big headings (top-level themes) are editorial work.** AI suggests, human edits, human commits. These are chapter labels and they're meant to be re-written as the analysis matures — *"Onboarding friction"* might become *"First-week trust building"* once you see what's actually unifying the sub-clusters underneath. The labels are the user's editorial output; the system's job is to suggest decent first drafts and never overwrite an edit silently.

**3a. The persistent layer is the underlying meaning, not the labels.** This is the structurally important point: **the system needs to preserve the relational reasoning that produced clusters and themes** (which quotes go with which, which sub-clusters belong under which themes, the embedding-level similarities), so that when new data arrives, the system can *extend* the existing analytical structure rather than recompute it. Labels regenerate from this underlying meaning on demand. The user's edits to labels are independent edits on a presentation layer; the system's analytical work is a durable structure beneath.

**4. Quote demotion via stacking.** When you have multiple stickies saying the same thing, you don't delete the weaker ones. You pick the best articulation — the one you can read from across the room — and physically stack the others underneath. The result: at a glance you see one quote prominent + a fan of supporting quotes underneath. You can *tell the depth of evidence* without reading anything. This is a UX feature, not just an analysis output.

**5. Observer notes as separate input.** Standard ethnographic trick: researcher + 2 observers each write their top 5 takeaways per session. That's 15 stickies × 6 sessions = 90 human-generated stickies. Affinity-sort those 90. The resulting 7–12 groups become the report structure. *Then* the system fits the transcript-derived sub-clusters into those groups. Observer notes are a different kind of evidence than transcript quotes — they're already-interpreted, already-prioritised.

**6. The editorial constraint: reportable means 7–12.** This is the unspoken rule that disciplines all the rest, and it is *not* arbitrary. It's derived from the social and cognitive reality of how UR work gets delivered:

- **The reporting slot.** UR teams typically get a 60-minute window with the product team: ~35 minutes presentation + ~25 minutes discussion. The structure of the talk has to fit. Less than 4 themes leaves the audience asking "is that it?"; more than 12 and the deck becomes a parade nobody can hold in their head.
- **The audience size and attention span.** Briefings to 4–8 humans for an hour can engage with 7–12 distinct ideas, no more. This isn't a Bristlenose limit — it's a human cognition limit that any presentation methodology converges on.
- **The deck format.** A 35-minute presentation maps to ~10 substantive content slides plus framing/conclusion. Trying to deliver 30 themes means each gets 70 seconds — at which point you're not communicating, you're filibustering.
- **The acting threshold.** Beyond ~12 themes, product teams can't decide what to prioritise. They walk out with a list, not a direction. *That's the real failure mode.* Research that doesn't change a decision didn't earn the research budget.

This isn't theory — it's why 20 years of practitioner experience converges on 7–12 as the right zone, with 4–20 as the wider acceptable band. **The granularity of the data itself is often higher.** A Dovetail study can legitimately produce 60–100 tags. But you never open a slide deck with 100 slides, one per tag. You compress to chapters; the tags become evidence-density indicators within chapters.

Bristlenose isn't a faithful-output system; it's a **compression-with-drill-down** system:
- **Top level (7–12):** the report. Reportable, actionable, holdable-in-head.
- **Middle level (sub-clusters):** the evidence. Drill-down on each top-level theme to see the supporting clusters.
- **Bottom level (individual quotes):** the participant in their own words. Drill further to see the actual articulation.

Granularity is preserved at every level — the researcher can always get to all 100 tags or 200 quotes when they want to. But the *default presentation* respects the reporting constraint. The 7–12 is enforced where it matters (the report spine) and abandoned where it doesn't (tags, individual quotes, sub-cluster counts).

**Current prompt state (gap, not for fixing yet):** As of writing, neither `quote-clustering.md` nor `thematic-grouping.md` has an explicit count target. The LLM is free to return any number of themes — often 4 on a small corpus and 25 on a large one. This is captured here as a known design gap, not a TF action item. When prompt work is taken up post-TF, the constraint to encode is: aim 7–12, accept 4–20, surface concern outside that band. Soft, not hard — occasionally a project genuinely has 3 themes and forcing 7 invents noise; occasionally it has 15 distinct strands that really do all merit chapter status and forcing 12 conflates them.

### Different levels, different rules

A consequence of the reportable-7-12 framing is that **the three levels of output have different jobs and need different constraints**:

| Level | Job | Count discipline |
|---|---|---|
| **Tags** | Granularity. Search, filter, evidence indexing. | None. 60–100 is fine if the data supports it. Don't compress here. |
| **Sub-clusters** | Evidence groupings within a chapter. | Loose. 20–40 across the project is reasonable. |
| **Themes** | The report spine. Reportable, actionable, hold-in-head. | Tight. 7–12 target, 4–20 acceptable. |

Bristlenose's pipeline today applies similar "find what's there" logic at every level. After this redesign, each level should have its own constraint regime.

### Sections vs themes — a structural distinction worth surfacing

The two prompts above do different work and shouldn't share constraints:

- **`quote-clustering.md` (sections / screens):** structural. The number of sections is dictated by the *product being tested*. If a prototype has 8 screens, you cluster around 8. The count target is "whatever the product structure honestly contains" — usually small (≤12), but driven by the artefact, not by editorial judgement.
- **`thematic-grouping.md` (themes):** editorial. The number of themes is dictated by *what's reportable*. The count target is the 7–12 reportability band, regardless of how much data is underneath.

Today these produce similar-looking output and behave alike in the UI. After this redesign, they should probably look and behave differently — sections as product-structured navigation, themes as editorial chapters with the reportability constraint applied.

### The deeper stance: report fidelity over data fidelity

What this conversation has surfaced is that Bristlenose has been designed (so far) with a **data-fidelity bias** — surface everything the data honestly contains, let the researcher decide what to use. The pipeline's loyalty has been to the source material.

But the real product is **report fidelity** — give the researcher what they will be able to *deliver*. These pull in opposite directions:

- **Data fidelity says:** surface 56 distinct findings if the data supports them. Let the researcher compress.
- **Report fidelity says:** pre-compress to 7–12 deliverable themes. Let the researcher drill down when they need depth.

20 years of practitioner experience suggests report fidelity wins because **researchers under deadline don't have time to do the compression themselves.** That's the job they need help with. Data fidelity is a tool-builder's reflex (more output = more value); report fidelity is a practitioner's reality (less but better = more value).

This is a *stance*, not a feature. It explains why Bristlenose should be shaped differently from a faithful-summary tool. It probably deserves a sibling document in `docs/methodology/` alongside `tag-rejections-are-great.md` and `consent-gradient.md`:

- *Tag rejections are great* — take user negative signal seriously.
- *Consent gradient* — respect data sensitivity by design.
- *Report fidelity over data fidelity* — compress to deliverability, preserve drill-down. (Not yet written.)

---

## What's immutable (the rule)

User-declared meaning is sacred. Once a researcher has done deliberate cognitive work to mark something, that mark must survive every subsequent operation. Specifically:

- **Stars** — "this quote matters"
- **Hides** — "this quote doesn't belong in the report"
- **User tags** — researcher's own labels, distinct from auto-generated tags
- **Renames** — speaker code → display name; theme rename; section rename
- **Notes** (if/when we add them)

These are *meaning the researcher created*, not analysis the LLM produced. They never decay, never get re-derived, never get overwritten. The data model needs a `source` column at the table level that distinguishes `human` from `autocode`, and `human` rows pass through re-analysis untouched.

Crucially, these marks are not *provisional* — not weak early guesses awaiting statistical validation from later participants. The researcher is embedded with the product team and arrives with months or years of context; their session-1 tags are *informed*, while the system knows neither what's coming next nor the intrinsic meaning of what it's seen. See [the asymmetry argument](#what-the-ratio-rule-was-groping-toward-judgement-not-arithmetic) — it's why an early human mark outranks a later machine pattern, always.

This part is the easy part — it's a schema decision with a one-time migration. The hard part is everything else.

---

## What's fluid (the question)

The output of stages 9–12 of the pipeline (segmentation, quote extraction, clustering, theming) is what re-analysis would touch. The question is: **how fluid?**

This is where the answer depends entirely on the shape of the re-run, not a single global setting.

### Researcher's mental model of fluidity

Stated by the user in design conversation, paraphrased:

> *"If I have 6 interviews and add 1, I expect themes and signals to stay locked. If I have 3 and add 3, more fluidity is okay. If I have 2 and add 4, allowing a complete rework is fine."*

This is the **ratio rule.** Fluidity is proportional to how much new material there is relative to existing material. Concretely:

| Existing | New | Ratio | Behaviour |
|---|---|---|---|
| 6 | 1 | 17% | **Strict lock.** New material fits existing themes; only truly orphan quotes generate candidates for new themes. |
| 5 | 2 | 40% | **Soft lock.** Themes stable but boundaries may shift; new themes need a high threshold to land. |
| 3 | 3 | 100% | **Negotiation.** Existing themes survive if they still have signal in the combined corpus; new themes welcome. |
| 2 | 4 | 200% | **Rework.** Treat as a fresh analysis; honour user-declared meaning but let structure re-form. |

The thresholds are illustrative. The principle *felt* real: the size of the prior commitment determines how much of it should hold.

This is not how the pipeline works today. It's not even a parameter — it's a different mode of operation that needs to be picked at run time.

> **⚠ Update (research pass, Jul 2026): the ratio rule rests on the wrong governing variable.** A deep-research pass against the saturation literature directly tested this heuristic and it fails. Hennink, Kaiser & Marconi (2017) found *no* pattern of saturation by prevalence or interview count: concrete codes reached saturation at 4–9 interviews, conceptual codes at 16–24 *or never*. So there is no single count or count-ratio that governs when structure should hold across code types — a project of mostly-conceptual themes is still fluid at session 15, while one with concrete themes may be effectively locked by session 6. A rule keyed on existing:new **session count** (6:1 vs 3:3) is measuring the variable the evidence says does *not* predict lock-readiness.
>
> **What this changes:**
> - **Keep the ratio rule only as a coarse UX default / prompt** — cheap, makes no methodology claim, fine for guiding the TF cohort toward the right mode. It stays useful as a first-guess ("you've added a lot relative to what's here — want to rework?").
> - **Before Beta / strangers, gate lock-vs-fluid on a saturation *proxy*, not the count ratio.** The disciplined governor is saturation state, which is code-type-dependent. The literature points to the variable but gives no ready-made operational metric for an automated pipeline — so the design work is to find the cheapest per-re-run proxy Bristlenose can actually compute: e.g. rate of *new codes / new orphan-cluster candidates per added session*, ideally distinguishing concrete from conceptual themes. See [Open design questions](#open-design-questions).
> - **Don't hard-code the 9 / 16–24 numbers.** They come from a single homogeneous HIV-care dataset. The *code-vs-meaning distinction* generalises; the exact interview counts do not.

### What the ratio rule was groping toward: judgement, not arithmetic

The research pass says count isn't the governor — but the ratio rule wasn't nonsense. It was a proxy for something real that the saturation literature only half-captures, and naming the real thing matters, because the system's job is to *support* it, not automate it away.

**Research is a numbers game and a quality game at once.** Saturation is real — it's well known that beyond ~5 interviews you hit diminishing returns on *new* themes, and the literature's 4–9 for concrete codes matches practitioner experience. But "enough data" is only half of it; you also need *good* data, and the two don't arrive on the same schedule.

**Participants come on a quality curve.** A typical sample of five has roughly two quite-or-very articulate people, two with some interesting material, and one who's a bit annoying — sidetracked, but still good for a few usable quotes. That's a normal distribution of quality, and a mis-recruit (someone not actually qualified to comment on the designs, or holding strong but unrepresentative opinions) sits in the tail. A skilled researcher *extracts what's usable and discounts the rest* — that discounting is analytical work, and it's invisible to a system that treats every quote as equal evidence.

**In an ideal world, all the data is on the table on day 0.** You'd cluster and theme once, at maximum quality, with the whole corpus in view — so you'd *know*, from seeing it all at once, what was unrepresentative, what to discount, what didn't fit the main themes. That's the analytically correct way to do it. Real research never gets that luxury: interviews drip in, participants have busy calendars, the researcher is under time pressure. So you start analysing from interview 1 — starring the better quotes, laying down the first tags — and three days later interview 2 lands, and by Friday interview 3, tens of thousands of words in play. Crucially, *the team isn't waiting either*: they've watched the calls, sat in as observers, already started assigning meaning — sometimes already changing the designs. The researcher does not have the luxury of saying "I'm waiting for themes to stabilise at 4–9 users before I commit to anything."

**And here is the asymmetry the whole design turns on.** When the researcher lays down a tag or stars a quote on session 1, day 1, it is *not* a statistically-premature guess awaiting validation from later participants. The researcher has been embedded with the product, design, or engineering team for months — often years. They arrive with context, priors, and a working theory of what matters; their early commitments are *informed*, not speculative. Bristlenose holds the opposite position: it has **no idea what's coming next**, and **no idea of the intrinsic value, meaning, or context** of what it's already seen. This is why the human-declared layer is *authoritative from context*, not *provisional pending statistics* — and why the system must never treat an early human tag as a weak signal to be overwritten once the "real" pattern emerges. The machine is the one operating with partial information, not the researcher. (This is the practitioner grounding for the immutable rule above; it also sharpens the [two-layer split](#whats-immutable-the-rule) — the human layer isn't just *older*, it's *better-informed*.)

**So the mental model of fluidity is a chain of judgement calls, not an arithmetic ratio.** It rests on assessments only the researcher can make: *was participant 1 representative?* (if so, their early stars hold); *is participant 3 an outlier?* (if so, discount some of their quotes). New themes do tend to emerge and firm up by around four users — but the *best exemplar quote* for a theme might not arrive until user 4 or 5. So a great deal of incremental work is not new-theme discovery at all; it's **re-ranking within stable themes**: recognising most of what comes in, quietly un-starring an earlier quote that now reads as less compelling, and stacking it under a newly-arrived best articulation of the same point. The theme is stable; the hero quote moved. This is exactly the fan-of-evidence / hero-promotion behaviour in the [physical-stickies model](#quote-demotion--fan-of-evidence) — the incremental cadence is *when* it happens, and it argues the common re-run is a quiet within-theme reshuffle, not a structural upheaval.

**Implication for the fluidity governor** (extends the research-pass update above): a saturation proxy beats a count ratio, but it is still only a *prompt*. The actual lock / discount / re-rank decisions are the researcher's judgement calls, and the system's job is to make them cheap to express — star/un-star, promote/demote a hero, mark a participant as an outlier so their quotes weight down — not to make them automatically.

### Why this maps to actual research practice

Qualitative research has known this for decades. The framing is **inductive vs deductive coding**:

- **Inductive (open coding):** themes emerge from the data. Every run from scratch. Used in early-stage exploration when you don't know what you're looking for.
- **Deductive (closed coding):** themes given in advance from a codebook. Used in confirmatory studies or when extending established work.
- **Abductive / hybrid:** start inductive, lock the codebook once it's stable, classify new material against it. Most real-world research is here.

Bristlenose today is purely inductive. Every run is open coding. That's correct for the first analysis. It's wrong for every subsequent one.

**The register shifts *within* a single project, in both directions — and the system must not hard-code one as the default.** As findings stabilise, research often turns deliberately *deductive* for operational reasons: once "performance issue X" and "usability issue Y" are concrete enough that a designer or engineer has a work item against them, the researcher's job changes to *gathering all the evidence in that space* — every quote that bears on X, quantified, so the report can say what percentage of users the issue affects (the tag-count / pie-chart view). That's closed coding, and at that stage it's the *right* move. But the opposite programme is just as legitimate: the "unknown unknowns" study (Rumsfeld's phrase), where the researcher insists the product manager *not* set the framing yet — "we need to stay open to what we find." A system that silently pushes everything toward lock-and-classify would quietly kill the open programme; one that never lets the codebook firm up would fail the concrete one. Both, plus the transition, have to be first-class.

This is also the deeper reason **codebook re-use** matters (and why this doc is titled "…and codebook lock"). A codebook that has stabilised into a closed scheme is exactly the thing you want to carry into the *next* study on the same product — so the durable analytical layer is not just per-project state, it's a reusable asset. Projected direction: codebooks shareable across projects in the same project folder. The data model shouldn't preclude a codebook (tag definitions + learned prompts, which are already instance-scoped) being adopted as the *starting* codebook of a sibling project.

The codebook-lock pattern is what NVivo, Dovetail, Atlas.ti, and MAXQDA all support in some form. We need to research how — see [Prior art](#prior-art-to-research).

---

## The pacing reality

User research cadence:

- Interviews are hard to schedule and drip in over 1–4 weeks.
- Researchers can't wait until the end — the analysis effort needs to start with the first interview to fit any reasonable project timeline.
- But they also can't commit too early — the shape of the analysis genuinely changes as new participants reveal patterns the first three didn't.
- One brilliant late interview with a domain expert can spawn an entire annex of findings that has to be woven into the final report. (*"These were only fully articulated by that last participant, but I think they're important."*)

The implication: **the system needs to support both "incremental refinement" and "late-breakthrough disruption" within the same project**.

### What we'd expect to see in usage

Speculative usage pattern, worth validating with the TF cohort:

1. **Interview 1 lands.** Researcher runs Bristlenose mostly to see what the tool produces. Light engagement: stars a few quotes, maybe makes 1–2 speculative tags. Doesn't invest deeply because they know the analysis will shift.
2. **Interviews 2–3 land within a few days.** Researcher re-runs. Themes start to stabilise. More starring, first real tag taxonomy beginning to form. First "this is interesting" findings start to crystallise.
3. **Interviews 4–6 land over the next week.** Re-runs are now housekeeping. Researcher expects themes to *stay put* — they've cited them in mid-study notes by now. They want new material to settle into existing structure. Heavy investment in stars/tags/hides at this stage.
4. **Interview 7 (the breakthrough).** A new theme genuinely emerges that doesn't fit. Researcher wants to *promote* the orphan-quote cluster into a new theme — but explicitly, not by surprise. "This is interesting enough to add to the report."
5. **Final report writing.** Researcher exports, polishes, ships.

What the system needs to support:

- Step 1: don't punish exploratory engagement. Stars from this stage survive.
- Step 2: theme structure starts to stabilise but the researcher hasn't committed yet. Auto-detect when the codebook is "ready to lock" or let them mark it.
- Step 3: stability. The system actively *resists* renaming themes or reorganising sections without explicit researcher action.
- Step 4: the orphan-quote workflow. Detect material that doesn't fit; surface as a candidate; let researcher decide.
- Step 5: nothing — the file is the file.

This is a lifecycle, not a re-run button.

---

## Identity reconciliation problems

The deep computer-science problem hiding inside all of this: **when is X the same as X?** Two specific cases:

### Same quote?

After re-extraction, you have:
- Old quote (with user's star): *"The homepage is slow, especially on mobile."*
- New quote: *"The homepage is too slow, particularly on mobile devices."*

Are these the same quote? A human reading them says obviously yes, same idea, same participant, same moment in the transcript. Bristlenose needs to say yes too, and carry the star forward.

Possible approaches:

1. **Content hash.** Exact match only. Fails on every boundary shift.
2. **Edit distance / Levenshtein.** Works for small boundary changes; fragile beyond.
3. **Transcript-position match.** Two quotes are "the same" if they overlap by >X% in the source transcript at the same timecode. This is probably the right primitive — it's deterministic, cheap, and matches how a human thinks ("same moment in the interview").
4. **Embedding similarity.** Cosine similarity of sentence embeddings >0.85. Most expressive but introduces non-determinism into the merge step itself.
5. **Hybrid.** Position overlap as the primary key, embedding similarity as a tiebreaker.

The user's gut answer was *"that quote is the same quote because it has 80% overlap — consider it the same and reconcile"*. That's the position-overlap approach. Probably the simplest correct answer; needs validation against real re-extraction drift.

### Same section / theme?

This needs a two-level answer because, per the physical-stickies model, **subheadings and big headings behave differently**.

**Sub-clusters (small groupings, 4–8 quotes):** practically stable identity, locally mutable in defined ways. Identity is carried by quote-overlap signature — a sub-cluster is "the same" if most of its quotes are the same. The allowed local mutations:

- **Hero promotion/demotion:** the headline quote changes when a better articulation appears. Old hero stays in the fan. This is routine, every re-run.
- **Membership growth:** new quotes from new interviews that match the cluster's signature slide in.
- **Trimming:** a quote that no longer fits (perhaps because a sharper sub-cluster has emerged that pulls it away) gets reassigned. Should be rare and surfaced as a notification, not silent.
- **Demotion to secondary:** a cluster that *was* a top-level finding when the corpus was small might become a sub-point under a larger theme when more data reveals its proper scale. Surfaced explicitly to the researcher — never silent.
- **Splitting / merging:** rare structural mutation. Only happens with explicit researcher action OR with very strong new-data evidence that the previous cluster was conflating two distinct concepts. Default to "no" unless the system can articulate *why*.

**Top-level themes (chapter headings, 7–12 total):** the labels are editorial output, AI-suggested, user-owned. The *underlying theme-membership* (which sub-clusters belong under which theme) is the system's analytical responsibility. So:

- **Labels:** AI suggests; user edits; user's edits stick. Inline editing is already shipped — that's the right pattern. Re-runs propose new labels for unedited themes; never overwrite edited ones.
- **Membership:** new sub-clusters get suggested-into-theme based on their analytical fit. Existing sub-cluster theme-membership stays stable unless new data genuinely reveals a better grouping (and that gets surfaced to the researcher, not done silently).
- **Theme split / merge:** as with sub-clusters, rare and explicit. The system can *suggest* "the data now supports splitting this theme into two" with reasoning, but never does it silently.

The architecture this implies: **separate the analytical layer from the presentation layer.**

- **Analytical layer (durable, evolves incrementally):** quote embeddings, pairwise similarities, sub-cluster memberships, theme-membership assignments. This is the system's reasoning. It grows monotonically as new data arrives; existing assignments are stable unless new data forces re-evaluation, in which case the re-evaluation is *surfaced*, not silent.
- **Presentation layer (mutable, researcher-owned):** sub-cluster labels (system can suggest, researcher may edit), theme labels (system suggests, researcher edits and commits), hero quote selections (system picks defaults, researcher overrides), display order. The researcher's edits to this layer override the system's defaults forever.

Labels regenerate from the analytical layer on demand for any cluster/theme the researcher hasn't touched. The researcher's edits are an independent override that survives every re-run.

**Evidence base (research pass, Jul 2026).** This split isn't just an engineering convenience — both halves have independent backing, and they converge on the same seam:

- **The methodology says the codebook stabilises early while meaning keeps moving.** Hennink, Kaiser & Marconi (2017, *Qual Health Research*) separate *code saturation* — the point at which the codebook stops changing — from *meaning saturation* — full interpretive understanding. In their data, code saturation arrived at ~9 interviews (91% of all codes, 92% of high-prevalence codes, 92% of code-definition changes complete) while meaning saturation needed 16–24. That is the exact structural analogue of this split: the analytical layer (which quotes go together, cluster/theme membership) can reasonably be treated as a stable matching target early (Mode B), while the interpretive layer (labels, framing, hero-quote picks) legitimately keeps evolving. "Codebook stable" is *not* "analysis done" — which is precisely why themes stay editorial.
- **The CS says cheap incremental recompute is only correct when you separate the durable relations from the holistic re-aggregation.** Self-adjusting computation (Acar, CMU-CS-05-129) makes small-input-delta → small-output-delta achievable *only under a stability precondition* you must engineer in; incremental view maintenance (Koch et al., PODS 2016) proves that matching a new quote against a locked codebook is "efficiently incrementalizable" (cheap, delta-proportional) while a whole-corpus re-cluster is a holistic aggregate that *provably cannot* be cheaply incrementalized. That directly validates the decision that pipeline clusters/themes regenerate wholesale (Mode C) while `created_by != 'pipeline'` structures survive — the theory says you couldn't cheaply-and-correctly incrementalize a global re-cluster anyway.
- **The interpretive layer *should* be fluid — that's the epistemic point, not a defect.** Abductive analysis (Tavory & Timmermans, 2014) treats "analytic surprise" as the valued outcome and keeps theory formation unlocked, tacking between data and theory. The late-breakthrough interview that reframes a theme is the system working. Important qualifier the design already honours: abduction is *open to revision, not commitment-free* — surprise arises against an existing theoretical background, so the fluid layer is structured revision of a held position (surface splits/merges as candidates for explicit promotion), never silent reshuffling.

---

## Prior art to research

Before designing further, dig into how qualitative research software handles this. None of it will be a direct lift — research-grade tools assume a researcher who reads methodology textbooks — but the patterns are worth learning.

### NVivo

- "Codes" are the unit. Created manually or via auto-coding.
- Codes are explicitly persistent across sessions; the codebook is the document.
- Adding new transcripts doesn't touch existing codes; researcher applies them manually or invokes auto-coding which *suggests* against the existing codebook.
- Researcher can split/merge codes at any time; system tracks the lineage.

Worth understanding: their separation of "code" (atomic label) from "category" (grouping) — closer to our tag/group/theme distinction than our current model captures.

### Dovetail

- Closer to our shape: SaaS, designed for UX researchers, lighter-weight than NVivo.
- AI suggestions for tags but explicit "accept" gesture, never silent overwrites.
- Tags persist across "highlights" (≈ quotes) regardless of source transcript.
- Their re-run/incremental story is worth specifically understanding — they ship something closer to what we'd need.

### Atlas.ti

- Heavier methodology focus, common in academic qualitative research.
- "Hermeneutic units" — the project — explicitly track the analysis state separately from the data.
- Code co-occurrence and network views — different visual language we probably don't need but worth understanding the model.

### MAXQDA

- Similar shape to Atlas.ti; strong mixed-methods support.
- Their "Smart Coding Tool" is the AI feature — recent — worth seeing how they framed it for the methodologist audience.

### Reflexive thematic analysis (Braun & Clarke)

Underlying methodology framework that most of these tools target. The six-phase model:

1. Familiarisation
2. Generating initial codes
3. Searching for themes
4. Reviewing themes
5. Defining and naming themes
6. Producing the report

Phases 3–4 are exactly where "codebook lock" lives — themes are *reviewed* against the data, and once committed, the analysis continues against them. Bristlenose's pipeline today collapses all six phases into one pass. Recognising the distinction is half the design.

### Non-academic prior art

How do *engineers* handle "incremental classification against an established taxonomy"?

- **Email classification (Gmail labels, Apple Mail rules):** rule-based, stable, user-defined. No re-clustering.
- **Photos.app face recognition:** trains a model from user input; new photos classified against it. Researcher acknowledges face = label sticks; system suggests, researcher confirms.
- **Issue/ticket triage tooling:** human-curated labels, automatic suggestions, explicit accept.

The pattern across all of them: **AI suggests; human commits; commitments persist.** That's the shape Bristlenose needs to grow into.

---

## Sketch of an approach (not a spec)

A possible system shape, intentionally rough:

### Mode A: Open analysis (current behaviour)

First run. No prior codebook. Fully inductive. Themes emerge, sections form, quotes get clustered. Researcher engages.

### Mode B: Locked codebook (post-first-run, default)

Subsequent runs against a project with prior themes. Pipeline:

1. **Stages 1–8 per session:** cache hit on existing sessions (deterministic given inputs); fresh run on new sessions.
2. **Stage 9 (segmentation) per session:** same — cache existing, run new.
3. **Stage 10 (quote extraction) per session:** cache existing; run new. **Carry user edits forward** via position-overlap match.
4. **Stage 11 (clustering):**
   - For each new quote, attempt to match against existing themes (quote-overlap or embedding similarity).
   - Quotes that match an existing theme: attach to that theme. Theme's quote count grows; identity unchanged.
   - Quotes that don't match: hold in an `unassigned` bucket.
5. **Stage 11b (orphan clustering):**
   - Cluster the unassigned quotes among themselves.
   - If a cluster crosses some coherence + size threshold, promote to a **candidate theme**.
6. **Stage 12 (theming):**
   - Existing themes: untouched (labels, descriptions all stable). Their quote sets may have grown.
   - Candidate themes: surfaced to the researcher as *"X new patterns that didn't fit existing themes. Review?"*
   - Researcher promotes, dismisses, or merges into existing themes — explicit gesture.

### Mode C: Rework (researcher-initiated)

Researcher explicitly asks for a fresh analysis (e.g. *"I have very different data now"*). Old themes become "previous codebook" — preserved as a versioned artefact, not used to constrain the new run. User edits (stars, hides, tags) still carry forward by quote identity.

This is what `Rebuild Report` should mean post-redesign.

---

## What the ratio rule maps to

The user's intuition that *"6+1 is strict, 3+3 is negotiable, 2+4 is rework"* maps onto these modes as:

- **6+1 ratio = Mode B with high candidate-theme threshold.** New theme has to be supported by ≥3 quotes from the new interview, and demonstrably orthogonal to all existing themes, before it's even surfaced.
- **3+3 ratio = Mode B with normal candidate-theme threshold.** New themes emerge readily but existing themes still hold their structure.
- **2+4 ratio = automatic suggestion to enter Mode C.** *"You have 4 new interviews against 2 existing. Want to re-analyse fresh? Your stars and tags will carry over."*

The threshold isn't a number to tune; it's a behavioural pattern to design around. The researcher should rarely have to think about it — the system suggests the right mode based on the ratio, and the researcher accepts or overrides.

**But see the Jul 2026 update under [the ratio rule](#researchers-mental-model-of-fluidity):** the mode-suggestion should be driven by a *saturation proxy* (rate of new codes / orphan-cluster candidates per added session), not raw session count. The ratio survives only as a coarse first-guess default for the TF cohort; the count-to-mode mapping above is illustrative UX, not the committed governor.

---

## Two features that fall out of the stickies model

These aren't part of the incremental-analysis problem strictly, but they emerge from the same grounding and should be designed alongside.

### Quote demotion / fan-of-evidence

When the system finds multiple quotes saying substantially the same thing, it should pick the strongest articulation and **stack the others underneath visually**. The card shows the primary quote prominently; the supporting quotes are visible as a fan/stack underneath at lower visual weight (smaller, lower opacity, peek-of-text).

The researcher can:
- Read the top quote at a glance (it's the headline).
- Sense the depth of evidence without reading anything (fan thickness = number of supporting quotes).
- Click/expand to see all of them when they need to.
- Promote a different quote to "headline" if the auto-pick is wrong.
- Demote the headline to add a better one they found in a later interview.

This solves three problems at once:
1. **Reportability:** the top quote IS the citable artefact; the supporting quotes are evidence depth, not separate findings.
2. **Redundancy without loss:** near-duplicates aren't deleted, just demoted. Researcher's work in identifying them is preserved.
3. **Incremental insight:** when a new interview lands and produces a *better articulation* of an existing point, it can be promoted to headline — the prior headline gets demoted to support. The fan grows by one. No structural change to the section.

Mechanism is the same near-duplicate detection used for incremental quote-identity (position-overlap within session, embedding similarity across sessions). Threshold for "stack me" is lower than threshold for "same quote" — these are *related* quotes, not *identical* ones.

### Observer notes as a separate analysis input

The "observers each write their top 5" pattern is an excellent affinity-sorting input that's *complementary* to transcript-derived quote extraction. Different shape of data:

- Transcript quotes: verbatim, automatic, low-curation, high-volume.
- Observer takeaways: already-interpreted, deliberate, low-volume, high-quality.

If Bristlenose supports observer-note import (a `.csv` or `.json` of "observer X says they noticed Y in session Z"), the affinity-sort can run on the observer notes *first* to establish the report-structure spine, *then* fit transcript quotes underneath as evidence. This matches the manual workflow exactly.

It's also a way to inject *human cognitive work* into the analysis pipeline without manual coding — the observers do the interpretation cheaply during the session, the system does the aggregation.

This is post-post-TF, but the data model should not preclude it. A `Quote` and an `ObserverNote` are different entity types; they cluster the same way; they support each other in the evidence fan.

---

## Open design questions

1. **When is the codebook "locked"?** Automatic (after N runs?) or explicit (researcher gesture)? Most likely explicit, surfaced when stability is detected. **Post-research-pass sharpening:** the *detection* signal should be a saturation proxy, not a run count or the session-ratio — the saturation literature says count/prevalence doesn't predict lock-readiness. Open sub-question: what is the cheapest per-re-run proxy Bristlenose can actually compute? Candidate: rate of new codes / new orphan-cluster candidates per added session, ideally split concrete-vs-conceptual (concrete themes lock early ~4–9 sessions; conceptual ones stay fluid to 16–24 or never). The literature names the variable but gives no ready-made operational metric — this is design work.
2. **How do candidate themes get reviewed?** A modal, a sidebar section, a separate "review" mode? Where does the UX live?
3. **What happens to user tags on quotes that get re-clustered into different themes?** Probably: tags follow the quote, not the theme. The tag is the researcher's annotation of *the quote*, not of *the position in the analysis structure*.
4. **What does versioning look like?** Should every re-run produce a versioned snapshot, so researchers can roll back? "Show me yesterday's analysis"? This is real complexity but real value for methodological transparency.
5. **How does this interact with editing transcripts post-analysis?** A researcher fixes a misheard word in transcript 4. Does the system need to re-extract quotes from that segment? (Probably yes, surgically. Out of scope here.)
6. **Can two researchers' codebooks be merged?** Cross-researcher collaboration is post-post-TF, but worth not painting into a corner.
7. **What about completely new participants who don't fit any pattern?** The "outlier participant" — every project has one. Their material may not cluster with the others *at all*. Probably a feature: surface as "this participant's analysis stands apart" rather than forcing fit.

---

## Out of scope for TF

All of this. Repeating for clarity:

- TF ships "create a fresh project per wave of interviews" as the operational model.
- `Rebuild Report` (if it ships at all in Phase 4) means "re-run on the same material with edit preservation" — not incremental against new material.
- Add-interviews-to-existing-project: **not in TF**. Frame in user materials as "for now, create a new project for each wave; integrated incremental analysis is on the roadmap."

This is the right scope for TF feedback. The cohort will tell us how much they need this, what shape they need it in, and whether the ratio rule actually matches their workflow.

---

## Concrete implementation notes (rescued from TF planning)

When this work was briefly part of the TF multi-project plan (before being descoped), specific implementation decisions were made. They're captured here so the next pass doesn't redo the thinking. Treat as **draft spec for when this becomes a feature**, not committed design.

### Reference-in-place source media (post-TF, when disk becomes the friction)

TF ships Copy/Move at drop. For researchers with 5–10 hour-long interviews, Copy doubles a few tens of GB — acceptable. For researchers with 50–200 hour-long video interviews (or 4K recordings), Copy is no longer acceptable. That's when reference-in-place becomes necessary.

**The pattern (Final Cut Pro's model):**

- Source files stay in their original location on disk.
- Each source file gets its own security-scoped bookmark in `projects.json` (`SourceMedia.bookmarkData` per file, not per project).
- The project folder contains analysis artefacts (transcripts, JSON, `bristlenose-output/`) only — never source video.
- Playback resolves the per-file bookmark on demand. If the file's missing/moved, the session shows a "missing source" state with a Relink action (same affordance as #8+9, applied at the file level).
- Clip extraction needs the original to be reachable at the moment of extraction; if it isn't, prompt to Relink.
- Re-analysis only needs the cached transcripts (already in the project folder) — survives source-file moves entirely.

**Schema implications:**

`projects.json` schema v2 (post-TF) gains:

```json
{
  "id": "...",
  "sourceMedia": [
    {
      "id": "<uuid>",
      "originalName": "interview-acme-3.mov",
      "bookmarkData": "...",
      "resourceIdentifier": "...",
      "addedAt": "..."
    }
  ]
}
```

This is additive; v1 readers default `sourceMedia: []`. No breaking change.

**Trade-off acknowledged:**

The FCP-style *"missing media"* failure mode is the cost. A researcher moves their source files and a session breaks; they relink and it works again. This is well-understood by pros but a learning moment for first-time users. Acceptable cost for the use case it serves (large-project researchers who actively manage their media library).

**Why this can't be the TF default:**

- Per-file bookmark management is genuinely more code than the project-folder bookmark.
- The missing-source UX needs its own Relink flow (same shape as #8+9 but file-level granularity).
- Researchers with small projects (TF cohort) don't need it and shouldn't pay the complexity tax.

Ship Copy/Move for TF. Add Reference-in-place when a researcher reports the disk-doubling friction. The schema is already forward-compat.

---

### "New analysis…" — the stepping stone (post-TF, pre-full-incremental)

A useful intermediate before the full Mode-B-locked-codebook design lands. Honest about what it does, cheap because it exploits the cache.

**The pattern:**

- Researcher has added new interviews to an existing project folder (via the drop-files-on-existing flow shipped in TF) — files visible in sessions list with "not yet analysed" badge.
- Menu item: **"New analysis…"** (ellipsis = confirm sheet follows).
- Confirm sheet (NSAlert, destructive register):
  - messageText: *"Run a new analysis for `Project Ikea`?"*
  - informativeText: *"Transcripts will be reused (no re-transcription cost). All themes, sections, quote groupings, and AI-generated tags will be rebuilt from scratch. Your stars, hidden quotes, and your own tags will be kept."*
  - Buttons: **Run New Analysis** (destructive red) / Cancel.

**What it actually does:**

- Stages 1–7 (transcribe, identify speakers, merge): **cache-hit on existing sessions.** Run fresh on new sessions only. This is the cheap-and-honest part — Whisper is deterministic, transcripts don't re-cost.
- Stages 8–12 (PII, segmentation, quote extraction, clustering, theming): **full regen** across the combined corpus. Themes / sections / sub-clusters / hero quotes all re-derive.
- User edits (`source='human'` rows per the schema convention): carry forward by quote-identity match (position-overlap >70% within session). Stars, hides, user-tags, person renames survive.
- AI-generated tags, AI theme labels, AI section names: replaced entirely. This is the "destructive" part the confirm sheet warns about.

**Why this is a stepping stone, not the destination:**

It's still destructive at the theme/section level — researchers will see *"Slow performance"* become *"Performance & First Load"* without recourse, even if they'd cited the old name in stakeholder notes. The full Mode B (locked codebook + candidate-theme review) is what eventually solves that. But "New analysis…" with destructive-but-edits-preserved is far better than "full re-run, lose everything", and it ships months before the full design.

**What's needed before this can ship:**

- The `source` column convention across the 4 tables (see *Edit-preservation schema* below).
- Transcription-stage caching that's reliable enough to claim "no re-transcription cost" honestly (already mostly there — Whisper output is keyed by audio hash + model).
- The drop-files-on-existing flow (shipped in TF as data-only; this feature is what makes it analytically useful).
- The round-trip test for edit preservation.

**What it doesn't need:**

- Codebook lock, candidate-theme review, ratio-rule heuristics, identity reconciliation for themes/sections — all of which are full Mode B.

**Naming:**

- "New analysis…" reads as researcher-honest about the destruction (the *previous* analysis is gone, this is a *new* one).
- "Rebuild Report…" (the earlier TF-considered verb) reads as more of a refresh — too soft for what actually happens. Save it for when the full Mode B ships with a non-destructive incremental path.
- Distinction the menu should make eventually: **"New analysis…"** (destructive) vs **"Update analysis"** (incremental, Mode B). Two verbs, two costs, two outcomes.

---

### "Rebuild Report" — the simplest re-run case

A useful entry-point feature even before the full incremental design lands: *"re-run on the same interviews, preserve my edits"*. Not the same as the full incremental-with-new-material problem, but a real researcher need (try a different prompt, recover from a bad first run, refresh after editing transcripts).

**Verb:** *"Rebuild Report…"* (ellipsis = confirm sheet follows). Mac-native register; researcher-honest about the artefact. Not "Re-analyse" (sounds like a feature name, hyphen reads as translation).

**One verb only.** Don't expose granular re-extract / re-cluster / re-theme — researcher doesn't know the stage taxonomy. If granularity matters later, surface it through the confirm sheet (*"Only regenerate themes (cheaper, $0.05) or full rebuild ($0.40)?"*), not through three menu items.

**Confirm sheet (NSAlert two-line):**
- messageText: *"Rebuild Report for `Project Ikea`?"*
- informativeText: *"This will use approximately **$0.40** in Claude API credits. Your stars, tags, hidden quotes, and renamed people will be kept."* — use `NumberFormatter` for currency (locale-aware).
- Buttons: **Rebuild** / Cancel.
- Skip the cost line entirely if estimate < $0.01 (cached).

**Cost preview source:** extend `estimate_pipeline_cost()` in `bristlenose/llm/pricing.py` with a `skip_stages` param (currently sums all stage medians). For first cut, acceptable to use the existing function with a known 5–10% overestimate.

### Edit-preservation schema (the `source` column convention)

Every user-editable field needs a `source: 'human' | 'autocode'` discriminator. Re-runs never overwrite `source='human'` rows. One migration touches four tables (Rule of Three earns the convention):

- `QuoteTag.source` — already exists (Mar 2026 work). Pattern proven.
- `Quote.starred_source` — new column (or sibling table `QuoteStar(quote_id, source, set_at)` if multi-user becomes a thing).
- `Quote.hidden_source` — same shape as starred.
- `Person.renamed_source` — same.

When this work lands, audit also: theme labels (`Theme.label_source`), sub-cluster labels (`Cluster.label_source`), hero quote choices (`Cluster.hero_quote_id` + `hero_source`). The full presentation-layer mutability story (from the [analytical-vs-presentation layer split](#same-section--theme)) wants this column on every editable field.

### Quote identity / merge contract

**Position-overlap is the primary key.** Two quotes from the same session that share >70% of their character span are "the same quote" — carry edits forward. Reasoning: it's deterministic, cheap, and matches how a human thinks about quote sameness ("same moment in the interview").

**Embedding similarity as tiebreaker** for ambiguous cases (one quote split into two on re-run, or two merged into one). Cosine >0.85 on sentence embeddings.

**Failure mode acknowledged:** if a quote's boundary genuinely changes substantially (re-extraction picks a different chunk), the edit may not carry forward. Acceptable for alpha; document in the confirm dialog (*"In rare cases, edits may not carry forward if a quote's wording changes substantially."*).

**The approach is theoretically sound — the *thresholds* are the untested risk.** The research pass confirmed the direction: robust set reconciliation (Mitzenmacher & Morgan, PODS 2019) formalises exactly this problem — reconciling two sets of metric-space points so the result is "close under a distance" rather than exact-equal, with "databases with floating-point measurements" as a motivating case. That's the formal warrant for replacing the current fragile exact-float importer key with overlap+embedding matching. What it does *not* tell us is whether >70% / >0.85 are the right numbers for Bristlenose's own re-extraction drift.

**Validation — BLOCKING before Beta / strangers (not merely alpha-nice-to-have):** run extraction twice on the FOSSDA fixture, manually mark which quote pairs are "the same", measure recovery rate. Target ≥90% for the primary heuristic alone. This is the single load-bearing untested assumption in the whole design — if recovery is below target, the curation-preservation contract is broken in exactly the case (added-sessions re-extraction) the feature exists to serve.

**The embedding tiebreaker has its own reproducibility wrinkle** (research pass, Jul 2026). The cosine >0.85 fallback assumes embeddings are stable run-to-run — but embedding models are subject to the *same* batch-invariance nondeterminism as generative inference (Thinking Machines Lab, "Defeating Nondeterminism in LLM Inference", Sep 2025 — `temperature=0` does not make cloud endpoints reproducible because server load varies batch size and standard kernels aren't batch-invariant). So the tiebreaker itself may drift on a cloud embedding endpoint. The validation must therefore measure embedding stability directly (same text, repeated calls, same batch conditions) before relying on cosine as the disambiguator — or pin embeddings to a local/deterministic path. If neither holds, the position-overlap primary key has to carry the contract essentially alone, which raises the stakes on the ≥90% target above.

### Round-trip test (mandatory before feature unlock)

A single integration test that's the executable form of the edit-preservation contract:

1. Boot fixture project with N quotes
2. Apply manual edits: star 5 quotes, hide 3, add 4 tags, rename 2 people
3. Run Rebuild Report
4. Assert: exact same edits visible on the re-run output

Lives in `tests/test_rebuild_report.py`. If this test fails, the feature is broken — there is no "it passes most of the time" version of edit preservation.

### Why "add new interviews" needs the bigger design

When this work was scoped, William flagged the "full re-run with warning" approach for adding interviews as worse than either incremental or descope. The reasoning:

- One genuine call site (longitudinal cohort) that doesn't exist in the current user base
- Full re-run on add-one-interview reads as broken once researchers experience the cost ($X + 20 min for one new session)
- Incremental needs the LLM-response cache (existing perf-doc issue #34) — a separate, larger piece of work
- Better to ship "create a fresh project for each wave" cleanly than build a partial

The current doc is what supersedes that thinking — the full incremental design (Mode B locked codebook + Mode C rework) is what makes add-interviews actually work. Don't build add-interviews without the design lock.

### Cost-preview accuracy gap

Note for whoever does the work: `estimate_pipeline_cost()` currently assumes a full run. For Rebuild Report it overestimates by 5–10% (stages 1–7 are cached but counted). Acceptable for alpha; tighten when LLM-response cache lands and incremental analysis ships.

---

## Why this document exists now

The TF cohort will absolutely ask "can I add more interviews?". The right answer is "not yet, here's why, here's where it's going" — not a hand-wave. This doc is what to point at when that question comes up.

It's also future-proofing: every Phase 4 decision in the TF plan (edit preservation, content-hash merge, `source` column) should be made *consistent with this design's eventual shape*. Otherwise we'll ship Phase 4, then have to redo it when this design lands. Doing the thinking now, even without code, prevents that.

## Next steps (post-TF)

1. **Empirical pass through NVivo, Dovetail, Atlas.ti, MAXQDA.** A weekend of trying each on a real (or fixture) project, specifically testing the add-material workflow. Notes on what works and what's annoying.
2. **Literature pass on reflexive thematic analysis incremental coding.** Braun & Clarke have a 2022 update; methodology blogs on hybrid coding practices.
3. **Cohort interviews on the actual workflow.** The TF cohort will be living this — ask them.
4. **First sketch design doc upgrade.** This doc becomes a real spec after the empirical and literature work.
