# Bristlenose: Codebook Feature — Strategy & Design

## Theory-Backed Codebooks for UXR Thematic Analysis

---

## Part 1: The Proposition

### Why This, Why Now

Existing tools (e.g. Dovetail) attempt auto-tagging based on the researcher's own tags, but with no conceptual grounding the LLM is essentially doing autocomplete on vibes. A tag called "Navigation" with three manually applied examples gives the model almost nothing to discriminate with. It guesses badly, researchers find it annoying, and trust erodes.

Bristlenose can offer something different: pre-built codebooks based on established UX/design theory where we control the prompt quality. The frameworks are well-defined, academically stable, and the discrimination boundaries are knowable in advance. We're not trying to read the researcher's mind — we're applying established theory. That's a much more tractable problem.

### How Bristlenose Currently Works

Quotes are assigned either to a **page/section/task** (tactical, screen-specific findings like *"this sneaker list doesn't have Nike"*) or to a **general theme** (cross-cutting patterns like *"I really love Nike"* surfacing in a Brands theme).

The gap: some findings are neither purely tactical nor purely thematic — they're structural or conceptual. *"I would have expected sneakers to be under apparel"* is an information architecture finding that doesn't belong in either bucket without a framework-aware codebook.

### Architecture: Bottom-Up First, Frameworks Second

**Pass one — pure emergence (current approach, stays clean).** The engine extracts themes bottom-up from transcript data with no theoretical framing. Clusters of quotes around observed patterns, frictions, behaviours, sentiments. Works identically whether the research is about fish tanks or flight controls.

**Pass two — framework overlay (optional, researcher-activated).** Once themes have emerged, the researcher imports a codebook and either applies tags manually or asks the LLM to suggest applications. The framework becomes a structuring tool for existing findings, not a discovery tool.

This preserves bottom-up integrity while giving researchers the vocabulary and structure they need for deliverables. It matches how experienced researchers actually work — fieldwork with open eyes, then theory to explain and organise what you saw.

---

## Part 2: The Tagging Pipeline

### How Tags Arrive, In What Order

The order matters enormously. Each layer builds on what came before, and the sequence determines what the system knows by the time framework codebooks are considered.

```
INTERVIEWS
    ↓
ENGINE (pass 1: bottom-up)
    ↓
┌─────────────┐    ┌──────────────┐
│  SECTIONS   │    │   THEMES     │
│  (specific) │    │  (cross-cut) │
└──────┬──────┘    └──────┬───────┘
       ↓                  ↓
SENTIMENT TAGS (automatic, universal)
       ↓
RESEARCHER'S OWN TAGS (manual, from outside the data)
       ↓
FRAMEWORK CODEBOOKS (optional, researcher-activated)
```

### Layer 1: Sections

**What they are:** Quotes grouped by a specific object, task, screen, topic, or subject under discussion. A section has a clear referent — "the homepage," "the checkout flow," "blade maintenance," "tank setup," "the Fluval heater range."

**Key design decision:** A section boundary occurs when the conversation shifts its direct object. The participant stops talking about one thing and starts talking about another. This is not a theme — it's a concrete focus of attention.

**Examples from the fishkeeping data:**
- Section: "Abyss Aquatics homepage"
- Section: "Livestock browsing / angelfish listings"
- Section: "Heaters and temperature control"
- Section: "Live plants"
- Section: "Shipping and delivery"

**Examples from the climbing data:**
- Section: "Getting into climbing"
- Section: "Training and progression"
- Section: "Fear and risk management"
- Section: "Gear and equipment"
- Section: "Community and social"

**What sections tell us downstream:** The section labels already contain strong signal about what's being discussed. "Abyss Aquatics homepage" is clearly about a product. "Fear and risk management" is clearly not. This matters later when we consider whether framework codebooks are appropriate for the data.

### Layer 2: Themes

**What they are:** Cross-cutting patterns that emerge across multiple sections and often across multiple participants. A theme is an insight, a tension, a recurring concern — not a location in the transcript but a thread that runs through it.

**Key distinction from sections:** A section says "they were talking about X." A theme says "across multiple conversations, we keep seeing Y."

**Examples from the fishkeeping data:**
- Theme: "Specialist vs generalist — expert users feel underserved by mainstream retailers"
- Theme: "Trust signals — own photography, physical shop, transparent shipping"
- Theme: "Content gaps — care parameters, compatibility nuance, breeding info"
- Theme: "Brand loyalty to specific equipment manufacturers"
- Theme: "Misinformation anxiety — experts frustrated by bad advice online"

**Examples from the climbing data:**
- Theme: "Fear as information, not obstacle"
- Theme: "Community as accelerator — learning through social connection"
- Theme: "Indoor-to-outdoor transition as identity shift"
- Theme: "The body as instrument — technique over strength"
- Theme: "Progression addiction — the draw of measurable improvement"

**What themes tell us downstream:** Themes are where framework codebooks may add most value. A theme like "content gaps" maps naturally to Garrett's Scope. A theme like "trust signals" maps to Morville's Credible. But a theme like "fear as information" maps to nothing in any UX framework — it's a human experience theme that needs domain-agnostic coding.

### Layer 3: Sentiment Tags

**What they are:** Automatic emotion/affect tags applied to individual quotes. Frustration, delight, confusion, confidence, anxiety, pride, anger, resignation, surprise.

**Key property: universal.** These apply to all humans with emotions, regardless of whether they're evaluating a website, grooming a poodle, or describing a near-fall on a cliff face. A frustrated poodle groomer is as legitimately frustrated as a frustrated website user. Sentiment has no applicability problem.

**What they tell us downstream:** Sentiment clusters within a section signal friction or delight hotspots. A theme that consistently carries anxiety across participants is worth investigating. Sentiment doesn't need a framework to be useful — it's pre-theoretical.

**Design note:** Sentiment tags should look and feel different from framework tags. They're a separate visual layer — not colour-coded badges from a codebook but an ambient signal. Perhaps a subtle background tint or an icon rather than a label. The researcher should see sentiment without it competing visually with their analytical tags.

### Layer 4: Researcher's Own Tags

**What they are:** Tags that come from the researcher's knowledge, not from the transcript. They represent concerns, contexts, and criteria that exist outside the data:

- **Product knowledge:** "This relates to the feature we're shipping in Q3"
- **Organisational politics:** "This supports the case for the redesign that stakeholders are resisting"
- **Client brief:** "This answers the client's question about onboarding drop-off"
- **Personal methodology:** "I always tag for learnability moments"
- **Cross-study patterns:** "I've seen this same issue in three previous studies"
- **Competitive context:** "This is something [competitor] does better"
- **Stakeholder concerns:** "The VP of Product specifically asked about this"
- **Standards and compliance:** "This is an accessibility failure under WCAG 2.1"

**Key property: invisible to the engine.** The LLM cannot generate these tags because the information needed to apply them doesn't exist in the transcript. Only the researcher knows that this particular finding about navigation confusion is politically significant because the nav was the CEO's pet project.

**Design implication:** The tag creation and application UX must be frictionless. These tags are the researcher's primary analytical tool. Every second of friction in creating, naming, colouring, and applying a custom tag is a second the researcher could spend thinking.

### Layer 5: Framework Codebooks (AutoTag)

**What they are:** Pre-built tag sets from established research authorities (Garrett, Norman, Morville, Holtzblatt, etc.) with hidden discrimination prompts that allow the LLM to suggest applications.

**When they arrive:** Last. After everything else.

**This is critical.** By the time the researcher considers applying a framework codebook:

1. **Sections are established** → the system already knows what objects/tasks are under discussion
2. **Themes are established** → the system already knows what cross-cutting patterns exist
3. **Sentiment is tagged** → emotional hotspots are visible
4. **Researcher's own tags are applied** → the researcher's analytical lens is already in place

The framework codebook is therefore not discovering anything new. It is **re-describing existing findings through a theoretical lens.** This is exactly how experienced researchers use theory — not as a discovery tool but as a structuring and communication tool. You find the insight first, then you reach for the framework that helps you explain it to stakeholders.

---

## Part 3: The Poodle Grooming Problem

### When Should UX Frameworks Stay Quiet?

Not every research transcript involves a designed artefact. Researchers study domains: rock climbing, poodle grooming, beekeeping, parenting, chronic illness management, amateur astronomy. These interviews produce rich qualitative data full of motivations, barriers, learning processes, community dynamics, and emotional experiences — none of which map to UX-specific frameworks.

When UX codebooks are applied to domain-only transcripts, three things can happen:

1. **The system returns NO FIT on most quotes.** Honest but useless — the researcher wasted time importing a codebook that had nothing to say.
2. **The system forces tags.** It finds superficial analogies ("a poodle clipper guard that doesn't stay on = Norman's feedback concept") and produces plausible-sounding but analytically empty tags. This is the worst outcome — it looks like the system is working when it isn't, and it erodes trust.
3. **The system correctly identifies the rare genuine hit.** A poodle groomer evaluating the PetSmart website, or a climber complaining that climbing apps are all social networks. These moments deserve framework tags — but they're needles in a haystack of domain talk.

The meta-level question: **how does Bristlenose know whether to offer UX framework codebooks at all, and if so, which parts of the transcript they should apply to?**

This is named after the test case: if a researcher uploads seven transcripts of poodle groomers discussing coat types, blade maintenance, and drying techniques — and the system confidently tags "Poodle coat texture assessment" as Garrett Surface — something has gone very wrong.

### Evidence: The Climbing Stress Test

We applied the Garrett and Norman codebooks to seven rock climbing research transcripts. Results:

- **14 quotes analysed** across 5 sessions
- **64% received NO FIT** — neither framework had anything to contribute
- **29% received forced tags** — every one required a warning caveat; rationales read as apologetic justifications
- **7% received genuine tags** — a single quote where a participant evaluated climbing apps

The forced tags were the revealing failure. You *can* make Norman's "feedback" apply to a cam shifting under load on a cliff face. You *can* call shoe fit a "constraints" issue. But these applications add fancy labels to obvious observations without generating any analytical value.

The single genuine hit — Ren Takahashi saying "I've tried dedicated climbing apps but they're all trying to be social networks and I just want a logbook" — lit up Garrett Scope, Garrett Strategy, and Norman Conceptual Model immediately and confidently. Because it was the only moment anyone evaluated a designed product.

### The Two-Halves Problem

Many usability studies have two phases in each session:

1. **Context/background** — the participant's experience, history, setup, motivations
2. **Product evaluation** — the participant uses or reacts to a specific designed thing

The fishkeeping transcripts demonstrated this perfectly. Yuki Tanaka spent 9 minutes discussing angelfish breeding, tank setups, and community — then 17 minutes evaluating the Abyss Aquatics website. The codebooks only applied to the second half.

A real solution needs to handle this boundary — not just at the project level ("is this a usability study?") but at the session level or even the quote level.

### How the Pipeline Helps

The pipeline sequence partially dissolves the poodle grooming problem. By the time framework codebooks are offered (Layer 5), the system has already built sections (Layer 1). Those section labels contain strong signal about what's being discussed:

| Section label | Contains designed artefact? |
|---|---|
| "Abyss Aquatics homepage" | Yes — website |
| "Livestock browsing" | Yes — website section |
| "Angelfish breeding background" | No |
| "Blade angle technique" | No |
| "PetSmart website booking" | Yes — website |
| "Coat type assessment" | No |
| "The Wahl Bravura clipper" | Maybe — physical product |

The section labels from Layer 1 already contain signal about whether framework codebooks are likely to be useful. How we use that signal — whether codebooks are applied selectively, whether the system warns the researcher, or whether we build logic to filter automatically — is a design decision for later. The important point is that the information exists by the time it's needed.

### Detection Approaches (For Future Consideration)

Several mechanisms could help the system decide when to apply or suppress UX framework codebooks:

**Manual declaration:** A researcher toggle at project level — "Does this study involve evaluation of a product?" Zero engineering, completely reliable, but doesn't handle mixed sessions.

**Session boundary markers:** The researcher marks "product evaluation starts here" in the transcript timeline. Handles the two-halves problem precisely. Natural extension of the existing section model.

**Keyword/pattern detection:** Scan transcripts for artefact-indicator vocabulary (site, app, page, screen, button, "I would expect," "I can't find"). Calculate density. Below 10% = likely artefact-free. Above 30% = likely product evaluation. Middle ground = ambiguous. Cheap and fast but struggles with edge cases.

**LLM pre-pass classification:** A lightweight prompt asking "does this transcript involve evaluation of a designed product?" with responses of SKIP / PARTIAL / PROCEED. More accurate than keyword scan, handles two-halves sessions, costs minimal tokens. Could also classify artefact type (digital / physical / service / none) to determine which codebooks are relevant.

**Confidence tracking backstop:** Let the engine attempt tags but track confidence. If average confidence falls below a threshold, alert the researcher that the codebook may not be a good fit. Good safety net regardless of other mechanisms.

**Pipeline-based inference:** Use the section labels already produced in Layer 1 to infer whether framework codebooks are appropriate — the work has already been done.

The right answer is likely some combination of these. The exact mechanism, and whether codebooks apply to all sections vs. selectively, needs further design work and testing against real data.

### The Poodle Grooming Litmus Test

Whatever detection mechanism is built, the test case is this: upload seven transcripts of poodle groomers discussing coat types, blade angles, drying techniques, show grooming standards, and client management. The correct system behaviour:

1. UX codebooks are either suppressed or the researcher is warned they may not be useful.
2. If the researcher overrides and applies them anyway, confidence is tracked and low-confidence results are flagged.
3. If one groomer says "I tried booking through the PetSmart website and I couldn't find the breed-specific grooming option" — that single quote gets tagged confidently. The rest stay clean.

### Edge Cases

**Physical products:** A groomer evaluating a grooming table, a climber assessing a belay device, a fishkeeper reviewing a heater controller. These are genuine product evaluations but of physical objects. Garrett's planes mostly don't apply. Norman's principles partially do. Morville's honeycomb partially does.

**Incidental mentions:** "I use the Wahl Bravura" is not an evaluation. "The Wahl Bravura guard keeps falling off" is. Detection needs to distinguish between referencing and evaluating.

**Gradual shifts:** Some sessions weave product comments throughout domain discussion rather than having a clean two-halves boundary. The system may eventually need quote-level rather than session-level awareness.

**Service evaluation:** A participant evaluating a hospital discharge process or a banking experience uses very different vocabulary from digital product evaluation but is still evaluating a designed thing.

**Researcher override:** Whatever automated detection exists, the researcher must be able to override it and apply any codebook they choose.

---

## Part 4: The Prompt Architecture

### Tag Names Aren't Enough

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

## Part 5: Tag Visual Hierarchy

With five layers of tags potentially present on a single quote, visual design matters enormously. The tags need to be visually distinguishable by type without overwhelming the quote they're attached to.

**Proposed visual hierarchy (most ambient → most prominent):**

| Layer | Visual treatment | Rationale |
|---|---|---|
| Sentiment | Subtle icon or background tint | Always present, should not dominate. Ambient signal. |
| Section membership | Shown by position/grouping, not a badge | The quote is *in* the section — it doesn't need a tag saying so. |
| Researcher's own tags | Solid colour badges, researcher-chosen colours | Primary analytical layer. Most prominent. |
| Framework tags (confirmed) | Solid colour badges, codebook-assigned colours | On par with researcher tags once confirmed. |
| Framework tags (suggested, unconfirmed) | Pale/ghost version of codebook colours | Visually tentative. Clearly distinct from confirmed. Invites action. |

The suggested-but-unconfirmed framework tags should feel like a gentle nudge, not a confident assertion. Pale colours, perhaps dashed borders, with a one-line rationale visible on hover. The researcher glances, confirms or dismisses, and moves on.

---

## Part 6: Candidate Frameworks

### Prioritised for Testing

**Priority 1: Jesse James Garrett — The Elements of User Experience**

Five mutually exclusive planes: **Strategy → Scope → Structure → Skeleton → Surface**. Clean discrimination boundaries, maps well to usability session quotes, widely known among UX researchers. Best first test of whether the approach works at all.

**Priority 2: Don Norman — The Design of Everyday Things**

Core concepts: discoverability, feedback, conceptual models, affordances, signifiers, mapping, constraints. His seven stages of action (forming goals → planning → specifying → performing → perceiving → interpreting → comparing) pinpoint where in the action cycle breakdowns occur. Distinction between slips (execution failures at the right goal) and mistakes (goal-formation failures) is analytically powerful. Harder discrimination problem than Garrett but higher payoff.

**Priority 3: Peter Morville — The User Experience Honeycomb**

Seven facets: useful, usable, desirable, findable, accessible, credible, valuable. Broader and softer than the first two, but "credible" and "findable" surface constantly in e-commerce and content research and rarely get tagged explicitly.

**Deferred: Karen Holtzblatt — Contextual Design**

Five work models: flow, sequence, artifact, cultural, physical. Designed for contextual inquiry specifically and needs richer observational data than typical usability transcripts. Save for when field research transcripts are available to test against. Worth noting that Holtzblatt is the one UX framework that *does* apply to non-product contexts — her work models describe how people work, not how they use an interface. This gives it a different applicability trigger entirely.

### Full Framework Landscape (Reference)

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

## Part 7: Common UXR Thematic Categories (Independent of Framework)

These are recurring theme types that emerge bottom-up in most UXR studies, whether or not a product is being evaluated. They represent the domain-agnostic qualitative coding that would work equally well for fishkeeping, rock climbing, or poodle grooming research:

- **Behavioural patterns** — what users do vs what they say; workarounds; error recovery
- **Pain points and friction** — confusion, hesitation, abandonment; ranked by frequency and severity
- **Unmet needs and latent desires** — not explicitly requested but emerged from behaviour or context
- **Expectations and mental models** — how users conceptualise the system or domain; where expectations diverge from reality
- **Motivations and goals** — underlying jobs-to-be-done; contexts driving usage
- **Trust, confidence, and emotional response** — feelings at key decision/commitment points
- **Environmental and contextual factors** — interruptions, device switching, social influence, time pressure
- **Learning and skill acquisition** — how people build competence; what accelerates or blocks learning
- **Community and social dynamics** — how people connect, share knowledge, build identity through the domain
- **Identity and self-concept** — how the activity or domain relates to who the person sees themselves as

These could form the basis of a domain-agnostic codebook — a complement to the UX-specific frameworks for studies that don't involve product evaluation.

---

## Part 8: Phased Implementation

### Phase 1: Pre-Built Codebooks as Tag Sets

Offer codebooks per-theorist with two levels of hierarchy only — **groups** and **tags** — in distinct colours, for the researcher to browse and manually apply. No LLM assistance. The researcher reads the tags, understands the framework, and applies them by hand. This tests whether the frameworks have value as organising structures before investing in automation.

### Phase 2: LLM-Assisted Suggestions

After importing a codebook, the researcher can ask the LLM to suggest tag applications. Suggestions appear in a **pale, tentative manner** — visually distinct from researcher-confirmed tags — and must be confirmed or dismissed by the researcher. Each suggestion carries a one-line rationale.

### Phase 3: Detection and Guidance

Build the mechanism (or combination of mechanisms) that helps the system assess whether UX framework codebooks are appropriate for the data. Whether that's manual toggles, keyword detection, LLM pre-pass, pipeline inference, or some hybrid — the exact approach needs further design work and empirical testing.

### Researcher's Own Codebooks (All Phases)

Every good researcher will create their own per-product, per-project, per-client, or personal methodology codebook. The pre-built options serve as starting points and learning scaffolds, not replacements. When researchers build their own, the system can auto-generate hidden discrimination prompts from the tag names and let the researcher refine them.

---

## Part 9: Prototype Results

### Test 1: Fishkeeping Transcripts (Abyss Aquatics Evaluation)

Applied Garrett and Norman codebooks to 13 quotes from the website evaluation portion of S1 (Yuki Tanaka). Results were encouraging:

- Scope was the most frequently applied Garrett tag (7 of 13 quotes), expected for an expert evaluating a generalist retailer
- Structure vs Skeleton discrimination worked well — species-level browsing received both tags for genuinely distinct observations
- Norman's Discoverability picked up a different signal than Garrett's Skeleton — the frameworks complement rather than duplicate
- Feedback appeared in trust-related quotes, correctly identifying photography and physical shop presence as trust signals
- Conceptual Model was applied sparingly (2 of 13), correctly — most comments were evaluative rather than model-mismatch
- Some quotes received tags from both codebooks, describing different dimensions of the same observation

**Verdict:** The discrimination prompts work when the data involves product evaluation. Tags felt accurate and the rationales were defensible.

### Test 2: Climbing Transcripts (No Product Under Test)

Applied the same codebooks to 14 quotes across 5 climbing sessions. Results were poor:

- **64% NO FIT** — neither framework had anything to contribute
- **29% forced tags** — every one required a warning caveat
- **7% genuine fit** — a single quote about climbing apps

The forced tags demonstrated the core failure mode: you *can* make Norman's concepts apply metaphorically to any human-thing interaction, but the applications are analytically empty. Calling a cam shift "feedback" doesn't help a researcher understand their data.

**Verdict:** The frameworks correctly fail when there's no designed artefact. The question is how to prevent the system from attempting (and forcing) tags on inappropriate data.

---

## Open Questions

- How and when should the system determine whether UX framework codebooks are appropriate? Manual toggle, automated detection, pipeline inference, or some combination?
- Should codebooks apply globally or selectively (per-section, per-theme, per-quote)? This is a significant design decision with implications for both UX and token cost.
- What's the right confidence threshold for alerting researchers that a codebook isn't fitting the data?
- How do we handle Holtzblatt's work models? They apply to contextual observation of work practices — explicitly not product evaluation — so they need a different applicability trigger.
- What domain-agnostic codebooks should Bristlenose offer as alternatives when UX frameworks aren't appropriate?
- How do we handle service design research? Evaluating a hospital discharge process uses very different vocabulary from digital product evaluation but is still evaluation of a designed thing.
- Should the keyword vocabulary list for artefact detection (if built) be extensible by the researcher?
- What happens when a researcher creates a custom framework codebook for domain-specific concepts (e.g. "Poodle Grooming Standards")? These should bypass any artefact detection since they aren't UX frameworks.

---

## Next Steps

1. Draft full hidden prompt layers for Garrett and Norman codebooks
2. Test LLM-assisted suggestions against additional transcripts from both studies
3. Prototype one or more detection mechanisms against the fishkeeping and climbing data
4. Design the domain-agnostic qualitative codebook as a complement to UX frameworks
5. Evaluate whether suggestions feel helpful or annoying in practice across diverse transcript types
6. Iterate prompt language based on false positive/negative patterns

---

## Status

Strategy and pipeline design are established. Two prototype tests completed (fishkeeping = positive, climbing = correctly negative). The core design question remaining is the detection/guidance mechanism for when to apply UX frameworks — this needs further empirical testing before committing to an approach.
