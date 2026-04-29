# Framework arc quarterly review

*A template and a discipline for Bristlenose. To be run quarterly from beta onwards.*

## Why this doc exists

Bristlenose is a ten-year arc wrapped around a six-month product. The arc is the real asset — an accumulated corpus of professional coding decisions that eventually supports a framework distilled from observed practice rather than textbook theory. The six-month product is the scaffolding that earns the right to build it.

These two timelines live in genuine tension. That tension shows up not as a big strategic choice made once, but as small decisions forced on the project weekly: feature requests that would pull towards Dovetail-likeness at the expense of framework posture; commercial pressures that would harden the product into a shape the corpus can't inhabit; natural energy that wants to sprint when the arc rewards pacing.

Keeping the long arc visible as a written document, reviewed on a fixed cadence, is what makes those judgement calls consistent. A quarterly review is the right rhythm — long enough that signal has accumulated, short enough that drift doesn't calcify.

This doc is both a template for the review and an explicit record of the arc it's reviewing against.

## The arc, stated

Bristlenose aims, over roughly a ten-year horizon, to:

- Publish and version each tag's operational prompt transparently, inviting scrutiny from users and framework authors.
- Accumulate a corpus of accept / reject / edit decisions made by professional researchers, with structured reasons and (at Level 3) anonymised quote exemplars.
- Use that corpus to iteratively sharpen each tag's operational boundary — the "ratchet" described in `tag-rejections-are-great.md`.
- Observe, over years, how the operational meaning of classical codebook tags actually evolves in the hands of working researchers.
- Eventually publish a framework grounded in that observed evidence — not replacing classical frameworks, but extending and refining them the way ICD-11 extends medical consensus.
- Hold the posture of "operationally transparent qualitative coding" as a distinctive and defensible methodological stance.

The arc is not a marketing claim. It's a commitment device. Foregrounding it in launch marketing would scare off the 80% of researchers who just want a Dovetail replacement that's cheaper and faster. The framework emerges for them gradually: first as "here are exemplars other researchers accepted," then as "here's what the corpus suggests about edge cases in your study," eventually as "here's a framework distilled from ten years of professional practice."

## What compounds, and at what pace

The corpus and the community compound; most other things don't. Naming this explicitly prevents metric drift towards the things that don't matter.

**Compounds:**

- **Exemplar corpus per tag.** Roughly doubles each time the active researcher base doubles, assuming opt-in rates hold. Most directly improves user experience.
- **Rejection-reason taxonomy.** Grows logarithmically — the first thousand rejections reveal most categories; the next hundred thousand refine frequencies and discover boundary cases.
- **Cross-study coding consistency data.** Meaningful only with 50+ studies where the same tag has been applied with different researchers — probably year 2 or 3 post-launch.
- **Community norms and trust.** Slowest and most important. The researchers who become advocates in year 3 are the ones who had a good experience in year 1.

**Does not compound in the way founders sometimes hope:**

- **The codebase.** Most of the 2036 code is not written yet. The 2026 code is scaffolding, not foundation. Treat it as disposable at the right moments.
- **Feature count.** Doesn't matter much. Dovetail will always have more. The advantage is shape, not volume.
- **Users-per-month.** Meaningful for runway; not for the arc. A researcher who deeply uses Bristlenose across five studies with opt-in feedback contributes more than fifty who tried it once.

## Quarterly review template

The review is a written artefact, produced each quarter, filed in `docs/methodology/reviews/YYYY-QN.md`. Roughly an hour to write; reads in ten minutes. The discipline is answering each section honestly, even when the honest answer is "nothing happened here this quarter."

### Section 1 — Corpus state

- Active researchers this quarter.
- Studies run through Bristlenose this quarter.
- Tag-decision events logged (Level 0 count).
- Distribution across Levels 1 / 2 / 3 if applicable.
- Any new exemplars or canonical rejected near-misses added to tag definitions.
- Any new structured reason categories added to the taxonomy.

### Section 2 — Prompt iterations

- Which tags had prompts iterated this quarter.
- For each iteration: before / after rejection rates, what changed, whether it was a hand-tune or an evidence-driven rewrite.
- Any prompts that were iterated but didn't improve — these are more interesting than the successful ones.
- Any prompts that are overdue for attention based on rejection rate but weren't iterated, with a reason.

### Section 3 — Framework movement

- Any observed operational drift in classical tags ("this quarter the corpus suggests X's boundary is sitting noticeably differently from Y's textbook definition, which is interesting because…").
- Any candidates for new tags or tag bifurcations that the data is starting to suggest but that aren't yet concrete enough to act on.
- Any conversations with framework authors or academic methodologists.
- Any published artefacts this quarter — Substack, paper drafts, conference talks, repo docs.

### Section 4 — Governance

- Any changes to the consent gradient or levels offered.
- Any incidents, complaints, withdrawals, or data-deletion requests.
- Any legal advice sought.
- Any governance-doc updates or republications.

### Section 5 — Commercial reality check

- Revenue this quarter.
- Burn this quarter.
- Runway at current burn.
- Commercial signals: pilots started, pilots converted, pilots churned, notable feedback from paying users.
- Any commercial decisions that were in tension with the arc, and how they were resolved.

### Section 6 — The arc check

Three questions answered honestly:

1. **Is the infrastructure : traction ratio healthy this quarter?** The arc rewards pacing, not sprinting, but if quarter after quarter is all infrastructure and no commercial traction, the arc is being used to rationalise slow progress. If it's all commercial traction and no corpus / framework work, the arc is being abandoned quietly. Neither should run for two consecutive quarters without naming it.
2. **Is the "full-time moment" still at the right distance?** The decision to go full-time on Bristlenose should be made against a substrate check — enough pilot revenue or grant funding to cover dedicated founder time for 24 months, with a clear corpus-growth trajectory — not against the emotional pull of momentum. If the answer has drifted, name the drift.
3. **Am I still interested in this?** Ten years is a long time to care about one thing. The UXR-wonk problems (coding meaning, framework emergence) sustain interest differently from the commercial-operator problems (pricing, onboarding, churn). If year-N you has mentally finished the interesting problems while the business has six years of grinding left, that's worth catching early, not late.

### Section 7 — Decisions and commitments for next quarter

Three to five concrete things. Not a backlog — a commitment. Each item should be either specific enough to verify next quarter ("ship Level 1 structured reasons") or explicit that it's a continuing commitment ("keep PII scrubbing false-positive rate below 2%"). Vague aspirations get rewritten as either specifics or dropped.

## Signs the arc is quietly going wrong

Written here so they're catchable.

- **Feature requests that pull towards Dovetail-likeness start winning repeatedly.** Individually defensible, collectively erosive. The product starts looking like an incumbent; the framework posture becomes harder to claim.
- **Corpus growth flattens.** Opt-in rates falling, or active-researcher base stalling. The compounding stops compounding. Worth distinguishing from seasonal dips, but two consecutive quarters of flat corpus is a signal, not noise.
- **Prompt iteration stops producing rejection-rate improvements.** Either the prompts have reached the limit of hand-tuning (in which case it's time for the evidence-driven iteration the arc is designed to unlock) or the iteration discipline has lapsed.
- **Governance work is always "next quarter."** The gradient exists because each level's consent needs design work. If Level 2's PII scrubbing has been "next quarter" for three quarters running, something is off.
- **Framework authors never get engaged.** The plan relies on academic credibility accumulating through genuine collaboration. If no framework author has ever reviewed a prompt, commented on a methodology piece, or been invited to a conversation, the academic side of the arc is a fiction.
- **Commercial decisions stop being written down.** The tension between commercial pressure and arc posture is real and constant. If the quarterly review stops documenting how that tension was resolved, it's because it's being resolved badly.

## What the review is not

It's not a roadmap, a backlog, or a status report. Those live elsewhere (`TODO.md`, `docs/ROADMAP.md`, `docs/private/road-to-alpha.md`). The review is a check against the arc, deliberately above day-to-day execution, written to be readable in a decade as a record of how decisions were made over time.

It's also not a document to share externally. Some of its honest answers — about commercial reality, about founder energy, about what didn't work — shouldn't be published. Its value is internal: a commitment device, a drift detector, and an archive of decisions made with the arc explicitly in view.

## First review

The first review should be written at the end of the quarter in which beta launches. Prior to that, the alpha checkpoints in `docs/private/road-to-alpha.md` are doing the equivalent job at the right granularity.
