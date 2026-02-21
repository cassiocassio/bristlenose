# Codebook Ecosystem — Strategy & Vision

_Feb 2026. Captures the design thinking behind the UXR codebook v2 rewrite and the broader codebook layering vision._

---

## The five layers of tags

Researchers don't use one codebook. They use several simultaneously, each serving a different analytical purpose. A single quote can carry tags from multiple layers:

| Layer | Example | Scope | Lifetime |
|-------|---------|-------|----------|
| **1. Universal human** | friction, mental model, trigger | Any domain, any study | Ships with Bristlenose (UXR codebook) |
| **2. Digital/tech-specific** | device/channel, error recovery | Digital products and services | Ships with Bristlenose (partially in UXR, fully in Norman/Garrett) |
| **3. Org/brand** | brand-trust, FooBank-tone, premium-feel | All studies for one company | Shared across studies, maintained by research ops |
| **4. Study-specific** | checkout-v2, gold-card-recognition, baseline, variant-A | One study only | Created per project, dies when the study is done |
| **5. Personal/house style** | what-Sarah-always-codes-for, boss's-pet-category | One researcher's practice | Carried between studies, reflects individual judgement |

Layers 1–2 are what Bristlenose ships. Layers 3–5 are what researchers create. The system needs to support all five stacking on the same data.

### Layer 3 in detail: org/brand codebooks

A research ops team at FooBank wants tags that persist across studies so they can build baselines:

- **Company-level tags** — brand perception, regulatory friction, trust signals specific to financial services
- **Product-level tags** — GoldFooCard recognition, mobile banking satisfaction
- **Feature-level tags** — tags for the new feature being tested this sprint

These shared tags make cross-study comparison possible. "Brand trust went up after the redesign" requires the same tag definition across both studies.

### Layer 5 in detail: personal style

Every researcher develops their own coding instincts. Some always code for information-decision-needs (a piece of information the user needs to make a decision — universal to any information space, from websites to gospels written on goatskin). Some always look for power dynamics in interviews. Some have a boss who insists on "house style" tags.

This is art and science. The system should support it without judging it.

---

## The framework codebooks (Norman, Garrett)

These exist for two reasons:

1. **Credentialing** — they signal to fellow practitioners that the tool was built by someone who knows the canon. Real researchers have grown up on these texts as the field emerged from HCI, cognitive psychology, library science, and ethnography in the early 2000s.

2. **Analytical precision** — they work well as codebooks precisely because they're coherent theoretical frameworks with clear boundaries. A researcher opts in knowing they're applying a specific lens. Norman tells you _what interaction principle_ is being violated; Garrett tells you _where in the design stack_ the issue lives.

Zero practitioners say they're taking a "Don Norman purist approach" to a study. But they recognise the concepts and reach for them when they fit. The framework codebooks are tools in the toolbox, not ideologies.

---

## The UXR codebook: design principles

The default Bristlenose UXR codebook (v2, Feb 2026) sits in layer 1 — universal human patterns. Design decisions:

### Practitioner vocabulary, not academic taxonomy

Tags should be the words researchers actually write on sticky notes: "workaround," "friction," "aha moment," "feature request." Not "compensatory behaviour" or "identity signal."

### No false precision

If an LLM can't reliably distinguish two tags from a quote fragment, they shouldn't be separate tags. "Primary goal" vs "secondary goal" requires understanding the participant's whole life context — collapsed to just "goal."

### Domain-agnostic

Works for fishkeeping, fintech, healthcare, rock climbing. These are universal patterns of human experience: how people learn, what frustrates them, what they want, how they make decisions. A piece of information someone needs to make a decision is the same whether they're searching a website or reading scripture.

### Full discrimination prompts

Every tag has three fields that the LLM uses for auto-tagging:

- **definition** — what this concept means (1–2 sentences)
- **apply_when** — what kind of participant utterance fits, with example phrases
- **not_this** — what adjacent tags this could be confused with, and how to disambiguate

The "not_this" field is the most important. Without it, the LLM over-applies popular/abstract tags and under-applies precise ones.

### Testable against real transcripts

Tags and definitions need iterative refinement — testing different definitions against known transcript sets, A/B comparing versions. The codebook archive system (see below) supports this.

---

## Discrimination prompts as open-source advantage

Dovetail, Marvin, and other SaaS tools hide their tagging prompts. Users can't see _why_ a tag was applied, can't fix bad definitions, can't share working definitions with their team. They can only learn from positive examples (what the user tagged), never from "not_this" — which is the most important disambiguation signal.

Bristlenose's advantage: the definitions are in plain YAML, version-controlled, forkable, and transparent. A researcher can:

1. Read exactly why AutoCode tagged a quote a certain way
2. Fork the codebook, tweak definitions, immediately get different results
3. Share their refined codebook with colleagues (email a .yaml file)
4. Contribute back improved definitions to an open ecosystem

Being open about definitions is both the ethical position (AGPL) and the competitive moat (network effects from shared definitions). Dovetail and Marvin are not going to open-source their tagging prompts. Bristlenose can build an ecosystem around shared, community-refined tag definitions that closed-source tools cannot replicate.

---

## Codebook versioning & archive

Codebook templates are versioned and archived using the same pattern as pipeline prompts (`bristlenose/llm/prompts-archive/`).

**Archive directory:** `bristlenose/server/codebook/archive/`

**Naming convention:** `{codebook-id}_YYYY-MM-DD_description.yaml`

**Version field in YAML:**
```yaml
id: uxr
version: "2.0"
title: Bristlenose UXR Codebook
```

Before any codebook template change, copy the current version to the archive. This supports:

- Tracking what changed between versions
- A/B testing different definitions against the same transcript set
- Rolling back if a new version performs worse
- Future: displaying version in the codebook page UI

---

## Future: tag display modes

_Not implemented. Design direction for v2 of tag filtering._

### Two distinct operations

1. **Show/hide tag display** — toggle the _visibility_ of tags from a whole codebook, like guides in Figma or "show invisibles" in a text editor. The tags are still applied to quotes; you're just choosing whether to see them. One-click per codebook.

2. **Filter quotes by tags** — toggle which quotes appear or disappear based on tag checkboxes. This changes what you _see_, not what exists.

These are different operations and should have different UI:

- **Display toggles** live in the codebook panel — a visibility icon per codebook (eye open/closed). Click to light up or dim all tags from that codebook across the report.
- **Quote filters** live in the toolbar — checkboxes that show/hide quotes based on tags.

### Why this matters

Researchers will apply several codebooks simultaneously — their own, the built-in ones, codebooks crafted by colleagues. They need to:

- See what turns up in the signal cards from each lens
- Zoom out on a big screen with small signal cards in a grid and look for coloured patterns across codebooks
- Toggle codebook visibility to focus on one analytical layer at a time
- One day: stack analysis grids on top of each other to see overlaid meanings — same data, different codebook lenses, layered like geological strata

The small participant badges (`.p-box` in `.participant-grid`) on signal cards already demonstrate this pattern — compact presence indicators showing which participants contributed to each signal. The same density principle applies to codebook tag badges: small enough that 5–15 participants or multiple codebooks don't overwhelm the card, but visible enough to spot patterns at a glance.

---

## Related files

- `bristlenose/server/codebook/uxr.yaml` — the default UXR codebook (v2)
- `bristlenose/server/codebook/norman.yaml` — Don Norman framework codebook
- `bristlenose/server/codebook/garrett.yaml` — Jesse James Garrett framework codebook
- `bristlenose/server/codebook/archive/` — versioned codebook archive
- `bristlenose/server/codebook/__init__.py` — YAML loader and dataclass definitions
- `bristlenose/server/autocode.py` — AutoCode engine (uses discrimination prompts)
- `docs/codebook futures/bristlenose-codebook-strategy-and-design.md` — original codebook strategy
- `docs/codebook futures/bristlenose-codebook-prompts-garrett-norman.md` — Garrett/Norman prompt design
- `docs/design-research-methodology.md` — analytical decisions behind current codes
- `docs/design-analysis-future.md` — analysis page vision (grid layering, two-pane design)
