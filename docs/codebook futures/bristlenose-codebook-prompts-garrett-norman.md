# Bristlenose AutoTag Codebook Prompts

## The Discrimination Prompts Used in the Fishkeeping & Climbing Prototype Tests

These are the hidden prompt layers that sit behind each tag. The researcher sees only the tag name and colour. The LLM sees the full prompt when deciding whether to apply a tag to a quote.

---

## Schema

Each tag has three fields:

| Field | Purpose | Length |
|-------|---------|--------|
| **Definition** | What this concept means — one sentence | ~15–25 words |
| **Apply when** | What kind of participant utterance fits — 1–2 sentences | ~25–50 words |
| **Not this** | What adjacent tags this could be confused with — one sentence | ~20–35 words |

The **"Not this"** field is the most important. Without it, the LLM over-applies abstract/popular tags and under-applies precise ones.

---

## Codebook 1: Jesse James Garrett — The Elements of User Experience

### Preamble (sent once before all tags)

> The following tags describe five layers of a designed product or interface, from abstract to concrete. The layers are mutually exclusive — a finding belongs on one plane, not multiple. When a quote could arguably sit on two planes, choose the one that best describes what the participant is reacting to: the conceptual organisation, or the specific interface element. If the participant is not discussing a designed product, interface, or service, do not apply any tag from this codebook.

### Tags

**Strategy**

- **Definition:** Whether the product is solving the right problem for the right users — the alignment between user needs and business objectives.
- **Apply when:** The participant questions the fundamental purpose or audience of the product, expresses that the product isn't aimed at them or their segment, or identifies a mismatch between what the product offers and what they actually need at a strategic level.
- **Not this:** If the participant is pointing to a specific missing feature or content gap, that's Scope. Strategy is about whether the whole proposition is right, not whether a specific thing is absent.

**Scope**

- **Definition:** What features and content the product includes or excludes — the functional and content requirements.
- **Apply when:** The participant identifies something that's missing (a feature, product category, content type, or information), notes that a feature exists but is inadequate, or comments on feature bloat or unnecessary functionality. Look for "they don't have," "I'd want to see," "there's no," "it would be useful if."
- **Not this:** If the participant is questioning who the product is for or whether the whole approach is wrong, that's Strategy. If they're confused about where existing content is organised, that's Structure. Scope is about what exists and what doesn't, not about how it's arranged.

**Structure**

- **Definition:** How the product organises information and interaction flows at a conceptual level — the architecture of categories, paths, and relationships between content.
- **Apply when:** The participant expresses confusion about where something belongs, expects content in a different location or category, describes the logical organisation of the product, or comments on how things are grouped conceptually. Look for "I would have expected X to be under Y," "why is this here," "the way they've organised this."
- **Not this:** If the participant is reacting to a specific button, link placement, menu position, or visual element, that's Skeleton. If they're questioning whether the content should exist at all, that's Scope. Structure is about conceptual organisation — the categories and relationships — not the interface controls that expose them.

**Skeleton**

- **Definition:** The arrangement of interface elements — navigation design, layout, information design, and the placement of controls, labels, and interactive components.
- **Apply when:** The participant comments on where a specific element is placed, whether navigation controls work, how easy or hard it is to move through the interface, or the layout of a particular page or screen. Look for "I can find things," "the menu is," "this is buried," "the layout."
- **Not this:** If the participant is commenting on visual aesthetics, colours, typography, or imagery, that's Surface. If they're confused about the conceptual grouping of content rather than the placement of a specific control, that's Structure. Skeleton is about the arrangement of interface elements, not their visual treatment or the conceptual model behind them.

**Surface**

- **Definition:** The visual and sensory design — what the product looks and feels like, including colour, typography, imagery, and aesthetic quality.
- **Apply when:** The participant comments on visual quality, photography, aesthetics, brand feel, the look of the interface, or their immediate sensory/emotional response to how something appears. Look for "it looks," "the photos are," "the design is," "it feels."
- **Not this:** If the participant is commenting on where elements are placed or how navigation works, that's Skeleton. If they're talking about what the images communicate about trustworthiness or product quality rather than how they look aesthetically, consider Feedback (Norman) or Credible (Morville). Surface is about visual treatment, not about what visual elements communicate.

---

## Codebook 2: Don Norman — The Design of Everyday Things

### Preamble (sent once before all tags)

> The following tags describe principles of interaction design. They describe the relationship between a person and a designed thing — how the design communicates what's possible, what's happening, and what went wrong. These tags apply to designed products, interfaces, and services. If the participant is describing personal experiences, physical activities, domain expertise, or life context without reference to a designed artefact, do not apply any tag from this codebook. Do not stretch these concepts metaphorically — "feedback" means a designed system communicating the result of an action, not any situation where a person learns something from their environment.

### Tags

**Discoverability**

- **Definition:** Whether the user can figure out what actions are possible and how to perform them.
- **Apply when:** The participant can't find a feature they expect to exist, doesn't realise a capability is available, or struggles to figure out how to start a task. Also applies when the participant easily discovers something — positive discoverability. Look for "I can't find," "where would I," "I didn't know you could," "is there a way to."
- **Not this:** If the participant found the feature but it didn't respond clearly to their action, that's Feedback. If they found it but the visual cue wasn't clear enough, that's Signifiers. Discoverability is about whether the user knows something exists and how to access it, not about what happens after they find it.

**Feedback**

- **Definition:** Whether the system communicates the results of an action clearly and immediately to the user.
- **Apply when:** The participant is uncertain whether an action worked, doesn't understand what happened after an interaction, receives confirmation that builds confidence, or comments on how the system communicates status. Also applies to trust signals where the system (or product presentation) communicates reliability or authenticity. Look for "did it work," "I'm not sure if," "that tells me," "how do I know."
- **Not this:** If the participant can't figure out how to perform the action in the first place, that's Discoverability. If the visual cue that should indicate the result is missing or unclear, that's Signifiers. Feedback is about the system's response to a completed action, not about finding or initiating the action.

**Conceptual Model**

- **Definition:** Whether the user's understanding of how the system works matches how it actually works.
- **Apply when:** The participant reveals a mental model of the product that differs from reality, expresses surprise at how something behaves, makes assumptions about the system that are wrong, or demonstrates a correct understanding that the design has successfully communicated. Look for "I thought it would," "I expected," "that's not what I assumed," "oh, so it works like."
- **Not this:** If the participant simply can't find something, that's Discoverability. If they understand the model but a specific control doesn't look like what it does, that's Signifiers. Conceptual Model is about the user's overall understanding of how the system is structured and behaves, not about individual interface elements.

**Signifiers**

- **Definition:** Whether visual, auditory, or physical cues correctly indicate where and how to interact.
- **Apply when:** The participant correctly or incorrectly interprets a visual cue about what an element does, comments on whether something looks clickable/tappable, or notes that a label or icon communicates clearly or misleadingly. Look for "it looks like," "I assumed this was," "the label says," "this icon."
- **Not this:** If the participant is commenting on overall visual aesthetics rather than communicative function, that's Surface (Garrett). If they understand what the element does but it doesn't respond when they use it, that's Feedback. Signifiers are about what design elements communicate about their function, not about their aesthetic quality or their response to interaction.

**Mapping**

- **Definition:** Whether the relationship between controls and their outcomes feels natural and predictable.
- **Apply when:** The participant comments on the relationship between an action and its result feeling natural or unnatural, notes that the layout of controls reflects the layout of what they affect, or finds a navigation structure that matches how they think about the content. Look for "it makes sense that," "naturally I'd go to," "this logically leads to."
- **Not this:** If the participant is commenting on the conceptual organisation of content rather than the relationship between controls and outcomes, that's Structure (Garrett). Mapping is specifically about the felt relationship between an action and its effect — does operating this control produce the expected outcome?

**Constraints**

- **Definition:** Whether designed limitations guide users toward correct actions and prevent errors.
- **Apply when:** The participant encounters a restriction that helps them (e.g., a form that prevents invalid input, a process that enforces a safe order of operations), or encounters the absence of a constraint that would have prevented an error. Look for "it wouldn't let me," "I wish it had stopped me," "the system forces you to."
- **Not this:** If the participant is describing a limitation in the product range or feature set, that's Scope (Garrett). Constraints in Norman's sense are designed guardrails within an interaction, not business decisions about what to include or exclude.

**Slip vs Mistake**

- **Definition:** Whether an error was a slip (correct goal, wrong execution — e.g., clicking the wrong button) or a mistake (wrong goal — e.g., misunderstanding what a feature does).
- **Apply when:** The participant makes an error during interaction and you can identify whether they had the right intent but executed poorly (slip) or had a wrong understanding of what they should be doing (mistake). Look for accidental clicks, typos, and misdirected actions (slips) versus fundamental misunderstandings of purpose or function (mistakes).
- **Not this:** If the participant hasn't made an error but is simply confused about how something works, that's Conceptual Model. Slip vs Mistake specifically applies to observed errors — things that went wrong — and classifies the type of error to inform the design response.

---

## Usage Notes

### Applying Both Codebooks Simultaneously

Garrett and Norman describe different dimensions of the same observation. A single quote can legitimately receive tags from both codebooks without contradiction:

- A quote about poor navigation can be Skeleton (Garrett) + Discoverability (Norman)
- A quote about missing product info can be Scope (Garrett) + Feedback (Norman)
- A quote about confusing categories can be Structure (Garrett) + Conceptual Model (Norman)

The two codebooks are complementary: Garrett tells you *where in the design stack* the issue lives, Norman tells you *what interaction principle* is being violated.

### Confidence and Refusal

The LLM should refuse to apply a tag rather than force a weak application. A quote with no applicable tag is more useful than a quote with a wrong tag. If no tag from either codebook fits a quote, the correct output is no tag — not a stretched application with an apologetic rationale.

### Rationale Requirement

Every suggested tag must include a one-line rationale (15–30 words) explaining why this tag and not an adjacent one. The rationale should reference the specific words or behaviour in the quote that triggered the tag. Bad rationale: "participant discusses the product." Good rationale: "participant expected angelfish listings to include water parameters — content gap in species detail."
