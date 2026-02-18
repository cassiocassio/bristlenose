# The Poodle Grooming Problem

## Bristlenose Codebook Feature — When Should UX Frameworks Stay Quiet?

---

## The Problem

Bristlenose offers pre-built codebooks based on established UX theory (Garrett's Elements, Norman's Design of Everyday Things, Morville's Honeycomb, etc.). These frameworks are designed to analyse how users interact with designed artefacts — websites, apps, services, interfaces.

But not every research transcript involves a designed artefact. Researchers study domains: rock climbing, poodle grooming, beekeeping, parenting, chronic illness management, amateur astronomy. These interviews produce rich qualitative data full of motivations, barriers, learning processes, community dynamics, and emotional experiences — none of which map to UX-specific frameworks.

When UX codebooks are applied to domain-only transcripts, three things can happen:

1. **The system returns NO FIT on most quotes.** Honest but useless — the researcher wasted time importing a codebook that had nothing to say.
2. **The system forces tags.** It finds superficial analogies ("a poodle clipper guard that doesn't stay on = Norman's feedback concept") and produces plausible-sounding but analytically empty tags. This is the worst outcome — it looks like the system is working when it isn't, and it erodes trust.
3. **The system correctly identifies the rare genuine hit.** A poodle groomer evaluating the PetSmart website, or a climber complaining that climbing apps are all social networks. These moments deserve framework tags — but they're needles in a haystack of domain talk.

The meta-level question: **how does Bristlenose know whether to offer UX framework codebooks at all, and if so, which parts of the transcript they should apply to?**

This document is named after the test case: if a researcher uploads seven transcripts of poodle groomers discussing coat types, blade maintenance, drying techniques, and client handling — and the system confidently tags "Poodle coat texture assessment" as Garrett Surface — something has gone very wrong.

---

## Evidence: The Climbing Stress Test

We applied the Garrett and Norman codebooks to seven rock climbing research transcripts. Results:

- **14 quotes analysed** across 5 sessions
- **64% received NO FIT** — neither framework had anything to contribute
- **29% received forced tags** — every one required a warning caveat; rationales read as apologetic justifications
- **7% received genuine tags** — a single quote where a participant evaluated climbing apps

The forced tags were the revealing failure. You *can* make Norman's "feedback" apply to a cam shifting under load on a cliff face. You *can* call shoe fit a "constraints" issue. But these applications add fancy labels to obvious observations without generating any analytical value. A researcher seeing "Feedback: cam shifted under load" learns nothing they didn't already know from the quote itself.

The single genuine hit — Ren Takahashi saying "I've tried dedicated climbing apps but they're all trying to be social networks and I just want a logbook" — lit up Garrett Scope, Garrett Strategy, and Norman Conceptual Model immediately and confidently. Because it was the only moment anyone evaluated a designed product.

---

## The Two-Halves Problem

Many usability studies have two phases in each session:

1. **Context/background** — the participant's experience, history, setup, motivations
2. **Product evaluation** — the participant uses or reacts to a specific designed thing

The fishkeeping transcripts demonstrated this perfectly. Yuki Tanaka spent 9 minutes discussing angelfish breeding, tank setups, and community — then 17 minutes evaluating the Abyss Aquatics website. The codebooks only applied to the second half. Background quotes about pair bonding and genetics would have been force-tagged or returned NO FIT.

A real solution needs to handle this boundary — not just at the project level ("is this a usability study?") but at the session level or even the quote level.

---

## Proposed Approaches

### 1. Researcher Declares It (Manual Toggle)

**How:** A toggle at project or session level: "Does this study involve evaluation of a product, service, or interface?"

**Pros:** Zero engineering complexity. Completely reliable. Researcher stays in control.

**Cons:** Binary at the project level — doesn't handle two-halves sessions. Requires the researcher to remember to set it. Doesn't scale to mixed-method studies where some sessions are contextual and others are evaluative.

**Verdict:** Good default. Should exist regardless of what else we build.

---

### 2. Researcher Marks the Boundary Per Session

**How:** A marker in the transcript timeline: "Product evaluation starts here." Everything before is context-only. Everything after is eligible for framework codebooks.

**Pros:** Handles the two-halves problem precisely. Low engineering cost — Bristlenose already has sections/tasks as an organising concept. The marker is just a special-purpose section boundary.

**Cons:** Manual effort per session. Researcher needs to watch/read each transcript to know where the boundary falls. (But they're probably doing this anyway.)

**Verdict:** High value, low cost. Natural extension of existing section model.

---

### 3. Keyword/Pattern Detection (Lightweight, Automated)

**How:** Scan the transcript for vocabulary that signals a designed artefact is under discussion.

**Artefact-present vocabulary:**
- Interface terms: site, app, page, screen, button, link, menu, navigation, homepage, search, filter, dropdown, tab, modal, notification, layout, checkout, login
- Evaluative phrases: "let me click," "I would expect," "where would I find," "it says here," "this doesn't work," "I can't find," "it takes me to," "the design," "the interface"
- Product references: brand/product names, URLs, "the site," "the app"

**Artefact-absent vocabulary:**
- Personal history: "I started," "when I was growing up," "I got into it"
- Domain activity: physical actions, techniques, processes described in domain language
- Community/social: "the community," "my group," "we share"
- Emotional/experiential: feelings, motivations, identity statements

**Detection logic:** Calculate artefact-indicator density as a percentage of participant utterances.

| Density | Action |
|---------|--------|
| Below 10% | Suppress UX codebooks. Clearly artefact-free. |
| 10–30% | Ambiguous. Escalate to LLM check (Approach 4). |
| Above 30% | Offer UX codebooks confidently. |

**Pros:** Cheap. Fast. No LLM tokens. Gets 80% of cases right.

**Cons:** Struggles with edge cases: physical product evaluation ("the clipper guard doesn't stay on"), service evaluation ("the groomer was rough with my dog"), or metaphorical language that borrows interface terms.

**Verdict:** Good first filter. Should not be the only filter.

---

### 4. LLM Pre-Pass Classification (More Expensive, More Accurate)

**How:** Before attempting any tag application, run a lightweight classification prompt against the transcript (or a representative sample of it).

**Proposed prompt (~100 words):**

> You are about to apply UX framework tags to a research transcript. Before tagging, assess whether this transcript involves a participant evaluating, using, navigating, or reacting to a specific designed product, service, or digital interface.
>
> If the transcript is primarily about the participant's personal experiences, domain expertise, community, physical activities, or life context without reference to a designed artefact, respond SKIP.
>
> If the participant evaluates a designed product during part of the session, respond PARTIAL and identify the approximate timecode or section where evaluation begins.
>
> If the session is primarily product evaluation, respond PROCEED.

**Pros:** Handles the two-halves problem. Distinguishes digital from physical product evaluation. Can identify the boundary timecode for PARTIAL cases. Relatively cheap — small prompt, single classification call, could run on the cheapest available model.

**Cons:** Adds a processing step and token cost before any tagging begins. May over-index on casual product mentions ("I use the Wahl Bravura") and incorrectly signal PARTIAL when the mention is incidental rather than evaluative.

**Refinement needed:** The prompt should distinguish between:
- **Digital product evaluation** — website, app, software (Garrett and Norman fully apply)
- **Physical product evaluation** — equipment, tools, devices (Norman partially applies, Garrett mostly doesn't)
- **Service evaluation** — human-delivered service experience (Morville's honeycomb partially applies, others less so)
- **No artefact** — pure domain/context research (suppress all UX frameworks)

This classification would also inform *which* codebooks to offer, not just whether to offer any.

**Verdict:** The most accurate single approach. Worth the token cost.

---

### 5. Tag Confidence Threshold (Reactive, Not Predictive)

**How:** Don't try to predict. Let the engine attempt tags, but track the confidence score on each application. If average confidence across a transcript falls below a threshold, surface a message:

> "These framework tags aren't finding much to grip on in this transcript. This data may not involve product evaluation. Consider domain-agnostic themes instead."

**Pros:** Zero upfront detection. Adapts to the data as it processes. Works as a backstop even if other detection methods miss something.

**Cons:** Burns tokens attempting tags that were never going to work. Fine for a small study, wasteful at scale. The researcher sees a sea of low-confidence suggestions before the system figures out the codebook doesn't fit — potentially annoying.

**Verdict:** Good backstop. Should not be the primary mechanism.

---

### 6. Hybrid (Recommended)

**How:** Layer approaches in sequence, cheapest first.

```
Step 1: Check researcher's manual declaration (Approach 1)
        → If "no product evaluation" → suppress UX codebooks. Done.

Step 2: Run keyword density scan (Approach 3)
        → If density < 10%  → suppress UX codebooks. Done.
        → If density > 30%  → offer UX codebooks. Go to Step 4.
        → If 10–30%         → proceed to Step 3.

Step 3: Run LLM pre-pass classification (Approach 4)
        → SKIP    → suppress UX codebooks. Done.
        → PARTIAL → offer codebooks with boundary marker. Go to Step 4.
        → PROCEED → offer UX codebooks. Go to Step 4.

Step 4: Apply tags with confidence tracking (Approach 5)
        → If avg confidence < threshold after N quotes → alert researcher.
```

**Why this order:**
- Step 1 costs nothing and catches deliberate researcher choices.
- Step 2 costs nothing (string matching) and catches the easy cases: pure poodle grooming, pure climbing, pure beekeeping.
- Step 3 costs minimal tokens and resolves ambiguous cases: sessions that mention products casually, sessions with a late shift into evaluation, service-design research where the vocabulary is less distinctive.
- Step 4 catches anything the earlier steps missed and provides ongoing quality feedback.

---

## Additional Considerations

### The Physical Product Edge Case

A poodle groomer evaluating a specific grooming table, a climber assessing a belay device, a fishkeeper reviewing a heater controller — these are genuine product evaluations but of physical objects, not digital interfaces.

Garrett's planes mostly don't apply (there's no skeleton or navigation in a grooming table). Norman's principles partially apply (a clipper guard that doesn't stay on is a real constraints/feedback issue). Morville's honeycomb partially applies (a grooming table can be assessed for usability, reliability, and desirability).

**Implication:** The LLM pre-pass classification (Step 3) should output not just SKIP/PARTIAL/PROCEED but also a product type: digital, physical, service, or none. This determines which codebooks are offered, not just whether any are.

### The Incidental Mention Problem

Participants mention products all the time without evaluating them. "I use the Wahl Bravura" is not an evaluation. "The Wahl Bravura guard keeps falling off and I've burned two dogs" is an evaluation. The keyword scan (Step 2) can't distinguish these. The LLM pre-pass (Step 3) can — but needs to be prompted to look for evaluative stance, not just product references.

### The Gradual Shift Problem

Some sessions don't have a clean two-halves boundary. A participant might weave product comments throughout a contextual discussion: grooming philosophy for five minutes, then "speaking of which, the new blade set from Andis is terrible," then back to technique talk. The LLM classification might return PARTIAL but there's no single boundary timecode — there are scattered evaluation moments.

**Implication:** The system may need to operate at the quote level, not just the session level. Each quote gets a micro-classification: is this utterance about a designed artefact? Only artefact-related quotes receive framework tags. This is more expensive but more accurate for messy real-world data.

### Researcher Override

Whatever automated detection exists, the researcher must be able to override it. "Yes, I know this looks like domain research, but I specifically want to see if Norman's concepts illuminate anything about how groomers interact with their tools. Apply the codebook." The system should comply — with a note that confidence may be low — and let the researcher judge the results.

---

## The Poodle Grooming Litmus Test

The ultimate test for any detection mechanism: upload seven transcripts of poodle groomers discussing coat types, blade angles, drying techniques, show grooming standards, client management, and continental clips. The correct system behaviour is:

1. **Keyword scan** detects very low artefact-indicator density. No mentions of screens, buttons, pages, or navigation.
2. **UX codebooks are suppressed** with a clear message: "These transcripts don't appear to involve evaluation of a designed product. UX framework codebooks may not be useful here. Consider domain-agnostic qualitative themes instead."
3. **If the researcher overrides**, tags are attempted but confidence is tracked. After the first few quotes produce low-confidence or NO FIT results, the system gently reiterates its suggestion.
4. **If one groomer says** "I tried booking through the PetSmart website and I couldn't find the breed-specific grooming option anywhere" — that single quote gets tagged confidently with Garrett Structure, Norman Discoverability, and possibly Morville Findable. The rest stay untagged.

That's the behaviour we're designing for.

---

## Open Questions

- What's the right confidence threshold for Step 4 to trigger an alert? Needs empirical testing across diverse transcript types.
- Should quote-level classification (the gradual shift solution) be default or opt-in? It's more accurate but significantly more expensive.
- How do we handle service design research? A participant evaluating a hospital discharge process or a banking experience is evaluating a designed service — but the vocabulary is very different from digital product evaluation.
- Should the keyword vocabulary list be extensible by the researcher? A climbing researcher might want to add "app," "route-finding tool," "beta spray app" to the artefact-indicator list for their specific domain.
- What domain-agnostic codebooks should Bristlenose offer as alternatives when UX frameworks are suppressed? This is a separate design problem with its own document.

---

## Status

This is a design thinking document, not a specification. The hybrid approach (Section 6) is the recommended direction. Next steps are to prototype the keyword density scan against both the fishkeeping and climbing transcript sets to calibrate the threshold, and to draft the LLM pre-pass classification prompt for testing.
