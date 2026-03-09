# Codebook: Observing the User Experience (Kuniavsky)

_Mar 2026. Reference codebook derived from public sources about "Observing the User Experience: A Practitioner's Guide to User Research" (2nd ed., 2012) by Elizabeth Goodman, Mike Kuniavsky, and Andrea Moed. To be refined against the actual book text._

---

## Source

- **Book**: Observing the User Experience: A Practitioner's Guide to User Research
- **Authors**: Elizabeth Goodman, Mike Kuniavsky, Andrea Moed
- **Edition**: 2nd (2012), Morgan Kaufmann / Elsevier
- **ISBN**: 978-0-12-384869-7
- **Most relevant chapter**: Ch. 15 — Analyzing Qualitative Data

The 3rd edition (2024) reorganises the material — Ch. 15 becomes Ch. 9. The frameworks below are based on the 2nd edition structure since that's what we own.

## Why this codebook

Kuniavsky's book is the standard practitioner reference for user research methods. Unlike academic frameworks (Morville Honeycomb, Norman's design principles), it's grounded in what practitioners actually do when they sit down with a stack of interview transcripts. The codebook below maps to the analytical categories the book teaches — making it a natural fit for Bristlenose users who learned research from this text.

This sits at **Layer 2** (digital/tech-specific) in our codebook ecosystem (`docs/design-codebook-ecosystem.md`), with some codes bridging into Layer 1 (universal human).

## Their analysis method

The book teaches a 4-step bottom-up coding process:

1. **Highlight** — read through transcripts/notes, mark interesting, surprising, or relevant passages
2. **Code** — categorise highlighted sections (top-down with pre-defined codes, or bottom-up by clustering then naming)
3. **Group** — organise codes into higher-level themes
4. **Interpret** — draw findings and insights from grouped codes

They favour **affinity diagramming** (KJ method) — physically cut up transcripts, cluster on a wall, then name the clusters. This is essentially what Bristlenose's quote extraction + clustering pipeline automates.

## Codebook structure

### 1. Needs, desires & abilities

The book's core analytical lens. Every research finding maps to one of these.

| Code | Description |
|------|-------------|
| `unmet-need` | Functional requirement that nothing currently satisfies |
| `partially-met-need` | Need addressed but with gaps or friction |
| `well-served-need` | Need fully satisfied by current solution |
| `feature-request` | Explicit desire for new capability |
| `aesthetic-preference` | Preference about look, feel, tone |
| `emotional-desire` | Aspiration, delight, identity expression |
| `technical-proficiency` | User's skill level with technology |
| `domain-expertise` | User's knowledge of the subject matter |
| `constraint` | Physical, cognitive, or situational limitation |

### 2. Behavioral observations

What users actually do (vs. what they say).

| Code | Description |
|------|-------------|
| `task-sequence` | Steps user follows to accomplish a goal |
| `workaround` | User-invented solution to a gap in the product |
| `shortcut` | Efficiency behaviour — skipping steps, power usage |
| `abandonment` | User gives up on a task or flow |
| `tool-usage` | Which tools/products they use and how |
| `frequency` | How often a behaviour occurs |
| `trigger` | What prompts the user to act |

### 3. Context of use

The circumstances surrounding behaviour — essential for field visit and diary study data.

| Code | Description |
|------|-------------|
| `physical-environment` | Where the user is (office, commute, home) |
| `social-context` | Who else is present, collaboration dynamics |
| `time-pressure` | Urgency, deadlines, interruptions |
| `device-channel` | What device or channel they're using |

### 4. Attitudes & perceptions

What users think and feel — from interview and survey data.

| Code | Description |
|------|-------------|
| `satisfied` | Positive sentiment about current experience |
| `dissatisfied` | Negative sentiment about current experience |
| `expectation-met` | Experience matched what user anticipated |
| `expectation-violated` | Experience diverged from what user anticipated |
| `trust` | Confidence in the product/service/brand |
| `credibility` | Perceived reliability and authority |
| `preference` | Stated preference for one approach over another |

### 5. Usability findings

From usability test analysis (Ch. 11). The book explicitly categorises findings into four types.

| Code | Description |
|------|-------------|
| `positive-finding` | Something that works well — don't ignore these |
| `navigation-issue` | User can't find what they need |
| `comprehension-issue` | Labels, instructions, or concepts are unclear |
| `learnability-problem` | Hard to learn or remember how to use |
| `efficiency-barrier` | Task takes too many steps or too long |
| `error-prone` | Users frequently make mistakes here |
| `bug` | Technical defect discovered during research |

**On severity**: the book deliberately avoids fixed severity scales (like Nielsen's 0-4). They recommend letting stakeholders assign severity because only those with business context can judge relative priority. Bristlenose could adopt this by keeping severity as a user-assigned property rather than a fixed tag.

### 6. Mental models & information architecture

From card sorting and generative research (Ch. 8).

| Code | Description |
|------|-------------|
| `mental-model` | How the user thinks the system works |
| `terminology` | Words users naturally use (vs. product terminology) |
| `navigation-expectation` | Where users expect to find things |
| `categorisation` | How users group related concepts |

### 7. Research method markers

Not analytical codes per se, but useful for tracking data provenance.

| Code | Description |
|------|-------------|
| `verbatim-quote` | Direct participant statement |
| `observed-behaviour` | Action witnessed by researcher |
| `participant-artifact` | Something the participant created (drawing, card sort) |
| `spontaneous-reaction` | Unprompted response during a session |
| `story` | Narrative account or anecdote shared by participant |

## Object-based technique taxonomy (Ch. 8)

The book has a distinctive three-part taxonomy for non-verbal research:

- **Dialogic** — participant responds to prompts/stimuli (conversation-based)
- **Generative** — participant creates artifacts (collages, drawings, models) to externalise mental models
- **Associative** — participant organises/categorises items (card sorting) to reveal information architecture

## Deliverable taxonomy (Ch. 17)

Four types of insight representation, each capturing a different aspect:

| Deliverable | Represents | Example |
|-------------|-----------|---------|
| **Personas** | People | Fictional user archetypes |
| **Scenarios** | Situations | Narrative of persona + product + context |
| **Process diagrams** | Activities | Task flows, user journeys |
| **Experience models** | Systems | Holistic touchpoint maps |

## Interview structure (Ch. 6)

Six-phase model — useful for understanding where in an interview a quote came from:

1. **Introduction** — rapport building
2. **Warm-up** — ease into the topic
3. **General issues** — broad exploration
4. **Deep focus** — drill into specifics
5. **Retrospective** — reflect on what was discussed
6. **Wrap-up** — summarise and close

Question types: **behavioral** (what they do), **attitudinal** (what they think/feel), **follow-up probes** (reactions observed during session).

## Relationship to other Bristlenose codebooks

| Codebook | Focus | Overlap |
|----------|-------|---------|
| **UXR (built-in)** | Universal research codes | High — Kuniavsky's categories informed much of the UXR codebook |
| **Morville Honeycomb** | Experience quality facets | Moderate — Kuniavsky covers usable/findable/credible but from a research (not heuristic) angle |
| **Norman** | Design principles | Low — Norman is prescriptive; Kuniavsky is descriptive/observational |
| **This codebook** | Practitioner analysis workflow | Unique — the only one structured around the research process itself |

## TODO

- [ ] Cross-reference against the actual Ch. 15 text (we own the book)
- [ ] Check 3rd edition (2024) Ch. 9 for updated analysis guidance
- [ ] Decide: ship as a bundled codebook or leave as reference material?
- [ ] Map codes to Bristlenose's existing tag groups — identify gaps and overlaps
- [ ] Consider whether "research method markers" (section 7) belong in the codebook or are better handled as metadata
- [ ] Evaluate the severity-as-stakeholder-property idea for Bristlenose's UI

## Sources

Public web sources used to compile this (no copyrighted text extracted):

- [Elsevier — 2nd edition table of contents](https://shop.elsevier.com/books/observing-the-user-experience/goodman/978-0-12-384869-7)
- [Elsevier Educate — 3rd edition TOC](https://www.educate.elsevier.com/book/details/9780128155691)
- [O'Reilly — Ch. 15 section headings](https://www.oreilly.com/library/view/observing-the-user/9780123848697/xhtml/CHP015.html)
- [ACM SIGSOFT review](https://dl.acm.org/doi/10.1145/2439976.2439993)
- [ScenarioPlus book review](https://www.scenarioplus.org.uk/reviews/kuniavsky_vs_crabtree.htm)
- [GSU student review](https://sites.gsu.edu/tzhang23/2024/03/18/book-review-of-observing-the-user-experience-a-practitioners-guide-to-user-research/)
