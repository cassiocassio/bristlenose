# Bristlenose: Theory-Backed Codebooks for UXR Thematic Analysis

## The Problem

Existing tools (e.g. Dovetail) attempt auto-tagging based on the researcher's own tags, but with no conceptual grounding the LLM is essentially doing autocomplete on vibes. A tag called "Navigation" with three manually applied examples gives the model almost nothing to discriminate with. It guesses badly, researchers find it annoying, and trust erodes.

## The Proposition

Offer pre-built codebooks based on established UX/design theory where Bristlenose controls the prompt quality. The frameworks are well-defined, academically stable, and the discrimination boundaries are knowable in advance. We're not trying to read the researcher's mind — we're applying established theory. That's a much more tractable problem.

## How Bristlenose Currently Works

Quotes are assigned either to a **page/section/task** (tactical, screen-specific findings like *"this sneaker list doesn't have Nike"*) or to a **general theme** (cross-cutting patterns like *"I really love Nike"* surfacing in a Brands theme).

The gap: some findings are neither purely tactical nor purely thematic — they're structural or conceptual. *"I would have expected sneakers to be under apparel"* is an information architecture finding that doesn't belong in either bucket without a framework-aware codebook.

## Architecture: Bottom-Up First, Frameworks Second

**Pass one — pure emergence (current approach, stays clean).** The engine extracts themes bottom-up from transcript data with no theoretical framing. Clusters of quotes around observed patterns, frictions, behaviours, sentiments. Works identically whether the research is about fish tanks or flight controls.

**Pass two — framework overlay (optional, researcher-activated).** Once themes have emerged, the researcher imports a codebook and either applies tags manually or asks the LLM to suggest applications. The framework becomes a structuring tool for existing findings, not a discovery tool.

This preserves bottom-up integrity while giving researchers the vocabulary and structure they need for deliverables. It matches how experienced researchers actually work — fieldwork with open eyes, then theory to explain and organise what you saw.

## Phased Implementation

### Phase 1: Pre-Built Codebooks as Tag Sets

Offer codebooks per-theorist with two levels of hierarchy only — **groups** and **tags** — in distinct colours, for the researcher to browse and manually apply.

### Phase 2: LLM-Assisted Suggestions

After importing a codebook, the researcher can ask the LLM to suggest tag applications. Suggestions appear in a **pale, tentative manner** — visually distinct from researcher-confirmed tags — and must be confirmed or dismissed by the researcher.

### Researcher's Own Codebooks

Every good researcher will create their own per-product, per-project, per-client, or personal methodology codebook. The pre-built options serve as starting points and learning scaffolds, not replacements.

---

## The Prompt Problem: Tag Names Aren't Enough

A bare tag label gives the LLM nothing to disambiguate with in ambiguous cases — and most real research is ambiguous.

Example: *"I kept going back to the homepage because I couldn't figure out where I was."* Is that Structure (IA), Skeleton (navigation), Surface (visual wayfinding), or a Norman feedback gap? The tag name alone can't resolve this.

### What Each Tag Needs: A Hidden Discrimination Prompt

Each tag carries a short prompt layer (2–4 sentences) invisible to the researcher:

| Field | Purpose | Example (Garrett → Structure) |
|-------|---------|-------------------------------|
| **Definition** | One sentence: what this concept means | How the product organises information and interaction flows at a conceptual level — the architecture of categories, paths, and relationships. |
| **Apply when** | 1–2 sentences: what kind of utterance fits | The participant expresses confusion about where something belongs, expects content in a different location, or describes the logical organisation of the product rather than specific UI elements. |
| **Not this** | One sentence: distinguishing from adjacent tags | If the participant is reacting to a specific button, link placement, or visual element, that's Skeleton. If they're questioning whether the feature should exist at all, that's Scope. |

The **"Not this"** field does enormous work. Without it, the LLM over-applies popular/abstract tags and under-applies subtle ones.

### Estimated Prompt Weight Per Codebook

| Codebook | Tags | Hidden prompt total |
|----------|------|---------------------|
| Garrett's Planes | 5 | ~500 words |
| Norman's Principles | 7–8 | ~700 words |
| Morville's Honeycomb | 7 | ~600 words |
| Holtzblatt's Work Models | 5 | ~500 words |
| Walter's Hierarchy | 4 | ~350 words |
| Hassenzahl Pragmatic/Hedonic | 4–5 | ~400 words |

None expensive in token terms. Two or three codebooks can be loaded simultaneously well within context window budgets.

### LLM Suggestion Presentation

Each suggestion should include a **one-line rationale**, not just the tag name:

> *Suggested: Structure — participant describes expecting a different category organisation*

This lets researchers evaluate without re-reading the full quote, builds trust (or healthy scepticism), and serves as implicit learning — a junior researcher seeing "this is Structure not Skeleton because the issue is about conceptual categories, not element placement" twenty times across a study is learning the framework through their own data.

### Custom Codebooks

When researchers build their own, they'll create tag names and groups without writing discrimination prompts. The system can auto-generate the hidden prompt layer by inferring definitions and boundaries from the tag names and group structure, then let the researcher review and edit.

---

## Candidate Frameworks: Prioritised for Testing

### Priority 1: Jesse James Garrett — The Elements of User Experience

Five mutually exclusive planes: **Strategy → Scope → Structure → Skeleton → Surface**. Clean discrimination boundaries, maps well to usability session quotes, widely known among UX researchers. Best first test of whether the approach works at all.

### Priority 2: Don Norman — The Design of Everyday Things

Core concepts: discoverability, feedback, conceptual models, affordances, signifiers, mapping, constraints. His seven stages of action (forming goals → planning → specifying → performing → perceiving → interpreting → comparing) pinpoint where in the action cycle breakdowns occur. Distinction between slips (execution failures at the right goal) and mistakes (goal-formation failures) is analytically powerful. Harder discrimination problem than Garrett but higher payoff.

### Priority 3: Peter Morville — The User Experience Honeycomb

Seven facets: useful, usable, desirable, findable, accessible, credible, valuable. Broader and softer than the first two, but "credible" and "findable" surface constantly in e-commerce and content research and rarely get tagged explicitly.

### Deferred: Karen Holtzblatt — Contextual Design

Five work models: flow, sequence, artifact, cultural, physical. Designed for contextual inquiry specifically and needs richer observational data than typical usability transcripts. Save for when field research transcripts are available to test against.

---

## Full Framework Landscape (Reference)

Beyond the priority candidates, these frameworks offer additional codebook potential:

- **Aarron Walter** — Hierarchy of user needs (functional → reliable → usable → pleasurable). Severity framework: functional failures trump everything.
- **Kim Goodwin / Alan Cooper** — Goal-directed design. Experience goals (how they want to feel), end goals (what they want to accomplish), life goals (aspirational identity).
- **Jared Spool** — Knowledge gap between current and target knowledge. Experiential qualities: "cool" features discovered with delight vs "essential" features whose absence causes rage.
- **Whitney Quesenbery** — The 5 Es: effective, efficient, engaging, error-tolerant, easy to learn. Good for comparative/benchmarking studies.
- **Marc Hassenzahl** — Pragmatic vs hedonic qualities. Explains "good usability scores, low NPS" situations.
- **Indi Young** — Mental model diagrams mapping problem space independently of solutions. User mental spaces on top, product support underneath — visualises gaps.
- **Lucy Suchman** — Plans and situated actions. People improvise rather than follow plans. Findings about workarounds, creative misuse, adaptive behaviour.
- **Nardi & O'Day / Activity Theory** — Subjects, tools, objects, rules, community, division of labour. For enterprise/collaborative tool research where individual usability isn't the whole story.

### Multi-Framework Synthesis

These frameworks can layer as complementary dimensions:

- **Garrett's planes** → where in the design stack
- **Norman's action stages** → when in the interaction cycle
- **Morville's honeycomb** → what quality dimension is affected
- **Walter/Hassenzahl** → what level of need is at stake
- **Holtzblatt's work models** → what aspect of context is relevant
- **Young's mental models** → whether the problem space itself is understood

---

## Common UXR Thematic Categories (Independent of Framework)

These are recurring theme types that emerge bottom-up in most UXR studies:

- **Behavioural patterns** — what users do vs what they say; workarounds; error recovery
- **Pain points and friction** — confusion, hesitation, abandonment; ranked by frequency and severity
- **Unmet needs and latent desires** — not explicitly requested but emerged from behaviour or context
- **Expectations and mental models** — how users conceptualise the system; where expectations diverge from reality
- **Motivations and goals** — underlying jobs-to-be-done; contexts driving usage
- **Trust, confidence, and emotional response** — feelings at key decision/commitment points
- **Environmental and contextual factors** — interruptions, device switching, social influence, time pressure

---

## Next Steps

1. Draft full hidden prompt layers for Garrett and Norman codebooks
2. Test against real transcript data to assess hit rate and discrimination accuracy
3. Evaluate whether suggestions feel helpful or annoying in practice
4. Iterate prompt language based on false positive/negative patterns
