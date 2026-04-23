# Consent gradient for feedback telemetry

*A data-governance note for Bristlenose. Pre-beta draft. Companion to `tag-rejections-are-great.md`.*

## Why this doc exists

Bristlenose's value compounds with a corpus of researcher judgements about AI-suggested tags. Collecting that corpus responsibly is not a single yes/no decision — it's a gradient of levels, each with its own sensitivity, utility, and consent requirement. This note lays the gradient out explicitly so future decisions about what to collect, when to offer it, and how to ask for consent are made against a written position rather than invented on the fly.

The gradient maps directly onto the data architecture: each level is additive, each has a distinct consent surface, and the levels should be unlocked sequentially as the product matures and as the consent UX earns the trust required to ask for more.

## The sensitivity shape of UXR data

Interview transcripts carry three kinds of sensitivity, and they're not uniform:

- **Participant speech.** Almost always under a participant consent form that says something like "your words may be used in research outputs" and very rarely says "your words may be used to train third-party software tooling." This is the tight constraint.
- **Researcher judgement.** The researcher's own reasoning about the quote. This is the researcher's IP and professional reputation, legally less thorny but professionally sensitive.
- **Study context.** The product being studied, the client, the stakeholder interests. Almost always under NDA.

A reason-only signal ("rejected: workaround not problem") tells you almost nothing about the participant or the client. A fact-only signal tells you even less. The quote is where the real privacy surface lives. The gradient is designed around that asymmetry.

## The gradient

### Level 0 — Fact only

Code suggest/accept/reject/edit events, with four fields: code ID, prompt version, event type, researcher ID. No content, no reason, no timestamp, no study ID. See `tag-rejections-are-great.md` for the canonical field list; if these two docs disagree, that one is authoritative.

- **Sensitivity:** extremely low.
- **Consent:** opt-in. Presented at first launch as a one-click "yes, help improve Bristlenose" with a plain-English summary visible before the toggle, and never pre-ticked above Level 0. Opt-out telemetry from a paid professional tool is not defensible under UK GDPR Article 6 for non-essential data, and "it's just facts" does not carry the argument — `researcher_id` remains personal data under Recital 26 even when pseudonymous. The signal loss from self-selection bias is recoverable via Experiment 3 (researcher-variance).
- **Utility:** prompt-level quality telemetry; A/B signal when iterating prompts; drift detection as performance degrades over time. This is the minimum viable signal and a lot can be done with it.
- **Unlocks:** alpha. See `tag-rejections-are-great.md` for the alpha experiments that live at this level.
- **Controller:** Bristlenose is sole data controller for the researcher's events at this level. No sub-processors involved; events land in Bristlenose-operated storage.

### Level 1 — Fact + structured reason

Adds a reason-from-fixed-list to each decision event. Choices like "wrong scope," "workaround not problem," "participant joking," "outside study frame." Optional free-text escape hatch off by default at this level.

- **Sensitivity:** still very low. "Rejected: participant joking" contains no participant data.
- **Consent:** opt-in at study setup, to build the norm. Could be opt-out later once trust is established.
- **Utility:** the pattern-of-reasons corpus. Lets you cluster rejection types per tag, which is the input needed for evidence-based prompt iteration.
- **Unlocks:** post-alpha, once Level 0 telemetry has proven the loop works and structured reason categories have been informed by informal "why" conversations during alpha.

### Level 2 — Fact + structured reason + free-text reason

Adds open-ended reason text. Researcher can write whatever they want.

- **Sensitivity:** medium. Free text from researchers can accidentally contain participant quotes, client names, or identifying context ("rejected because P7 was clearly talking about the Acme dashboard, not our product").
- **Required infrastructure:** a PII/entity scrubbing pass at submission time that runs **entirely on the researcher's device** (Presidio + spaCy, optionally a local Ollama model). No hosted LLM API is permitted at this level — routing researcher free-text through OpenAI/Anthropic/Azure would be a restricted international transfer of un-scrubbed content and would collapse the local-first posture at the exact point the gradient is designed to protect. Model hashes pinned; scrubber-regression tests run in CI against a `pii_horror_transcript.txt` fixture.
- **Consent:** opt-in, per study, with a preview of what's actually sent after scrubbing. For the first N submissions in each study the researcher actively types/selects a confirmation rather than clicking a default-primary button — "previewed and confirmed" must not be clickthrough-able while the UX is bedding in.
- **Utility:** richer reason corpus than Level 1's fixed list, captures judgements the taxonomy doesn't yet have categories for. Also feeds back into taxonomy evolution.
- **Unlocks:** once the PII scrubbing pass has been prototyped and tested on real UXR transcripts and false-positive/false-negative rates are empirically understood; and once a published DPIA covers this level.
- **Controller:** Bristlenose is sole controller for researcher-generated free text. No sub-processors.

### Level 3 — Fact + reason + anonymised quote

Adds the actual quote text, passed through the same PII scrubbing pass as Level 2.

- **Sensitivity:** high. This is the most valuable data by a wide margin — it lets you build exemplar-cluster memory and do proper prompt regression testing. (See §Purpose limitation for the explicit scope of use.)
- **Required infrastructure:** on-device PII scrubbing as at Level 2, but more stringent because quotes are participant speech; per-study opt-in (never per-researcher blanket); a **verified-consent upload step** at study setup where the researcher attaches or references their participant consent form, rather than a plain attestation checkbox; an automated rejection path that refuses obviously non-compliant consent claims (e.g. consent forms dated before 2020 that make no mention of third-party tooling); a `participant_reference` token (opaque to Bristlenose, researcher-owned) carried on every Level 3 record so erasure requests can be honoured without the researcher identifying the participant to us; a deletion SLA of ≤30 days for participant-initiated erasure routed via the researcher.
- **Special-category (Article 9) gate:** at submission time, the researcher must confirm the quote does not reveal health, sexuality, religion, political opinion, ethnicity, trade-union membership, or biometric data. If they cannot confirm, the quote cannot be submitted at Level 3. A separate Level 3-special tier with UK Schedule 1 Part 1 safeguards may be designed later; it's not in scope for the initial Level 3 opening.
- **Consent:** opt-in, per study, with preview, with verified consent upload, with the Article 9 gate. This is the consent surface that actually deserves the word "informed" — everything lower is consent-lite by comparison.
- **Utility:** exemplar clusters per code; regression test corpus; evidence of boundary cases for prompt iteration. See §Purpose limitation for what the corpus will and will not be used for.
- **Unlocks:** all of the following together: Level 2 has been operating stably for long enough that scrubbing quality is empirically defensible; written UK legal advice has been obtained in advance, not after; a DPIA covering Level 3 is published; a verified-consent upload flow exists and has been reviewed by that legal advisor; PI insurance covering data-protection claims is in place.
- **Controller:** At Level 3 Bristlenose and the researcher's employer become **joint controllers** over participant personal data under Article 26. A joint-controller arrangement template must be countersigned by the researcher's employer before Level 3 is enabled for that researcher, and a DPA is offered to the employer. Bristlenose publishes its sub-processor list (which at this level is none — scrubbing and storage are in-house and on-device respectively).

### Level 4 — Quote + reason + study metadata

Adds sector, company size, stakeholder type, etc.

- **Will not be offered.** This is a permanent commitment, not a "not yet." The marginal value over Level 3 is small and the re-identification risk spikes — re-identification from "series of quotes about a fintech onboarding flow for an early-stage consumer lending product in the UK" is a short path. Bristlenose commits publicly, in the governance doc, never to collect this combination.

## Purpose limitation

The corpus collected across Levels 0–3 is used to improve the quality of code-suggestion prompts and to inform the evolution of the codebook. It is **not** used to train general-purpose AI models, and the consent language presented to researchers will say so in plain English. If a future Bristlenose product ever wants to use this data as training corpus, that product requires fresh consent under a new purpose and is not an extension of what's described here.

This reconciles a tension that would otherwise recur: the long-arc documents elsewhere in the repo describe a ten-year ratcheting mechanism, and that mechanism could in principle be framed as "training." It isn't. Prompt-improvement — hand-tuning, evidence-driven rewriting, exemplar-cluster-informed boundary adjustment — is a narrower purpose than model training and is what consent here authorises. The gap matters legally (purpose limitation under Article 5(1)(b)) and reputationally (the Hollywood-writers'-strike framing is not a fight worth having when the actual use is narrower than the fight assumes).

## Consent UX principles

The consent surface is as load-bearing as the technical infrastructure. Three principles worth committing to in writing, because they'll be under constant pressure as the product grows.

**Default to professional norms, not tech norms.** Tech defaults to "share everything, opt out if you care." Research defaults to "share nothing, opt in with informed consent for each use." Bristlenose's defaults should read as the latter even where commercial pressure pushes towards the former. Your users are people who professionally ask participants for informed consent. They will spot and resent the cookie-banner pattern.

**Separate the consent moment from the tagging moment.** Ask once, at study setup, with the researcher able to see exactly which levels are enabled and change them per study. Don't ask at tag-time — it's cognitive load in the middle of analysis and people will click through blindly or disable in frustration. Study-level consent also naturally aligns with the per-study participant consent the researcher has already negotiated.

**Give researchers something back for contributing.** If they're opted-in at Level 2 or above, they should get aggregated rejection patterns for their codebook, cross-study consistency analysis, and personal calibration against the global corpus. Contribution becomes a feature, not an extraction. This also normalises the data flow — the researcher sees what's being collected because they're using the same aggregations themselves.

## Data-governance policy as a public artefact

The governance policy should be published in plain English on the public website before it's needed commercially. "Here's exactly what we collect at each level. Here's what we do with it. Here's what we don't. Here's how to withdraw." The researchers we want are going to read this carefully and would rather see it before they sign up than be surprised later.

Treating data governance as a first-class design artefact rather than a legal afterthought is itself a differentiator from Dovetail-class tools. It's also how the methodological credibility of Bristlenose is built publicly — the Substack pieces about governance are as important as the ones about analysis findings.

## Known hard problems

A few things that don't have clean answers and won't be solved by engineering alone.

**Participant re-consent.** A lot of UXR runs under light-touch consent forms that predate any thought of third-party software tooling. A maximally rigorous reading says even Level 3 with PII scrubbing doesn't meet the spirit of what participants agreed to. This won't be solved perfectly — nobody in the industry has — but the governance doc should be honest about where the edges are. Researchers who want to be bulletproof will get updated consent language from Bristlenose that they can fold into their own recruiting scripts. That's a community good; it also happens to be a defensible differentiator.

**GDPR and the UK equivalent are asymmetric threats.** The worst-case isn't a privacy-conscious researcher declining to opt in; it's a privacy-conscious researcher's participant later finding out their words trained a commercial tool and filing a complaint with the ICO. Structure the Level 3 consent so the researcher attests that their participant consent permits this use — it puts the product in a much better position if challenged. Worth actual UK legal advice before turning Level 3 on, not after.

**Training-data framing.** See §Purpose limitation — the tension between "improve code-suggestion quality" and "train AI models" is resolved by binding Bristlenose's actual use of the corpus to the former, not by choosing language cleverly. The consent language matches the actual scope.

**Acceptance vs rejection asymmetry.** Accepted tags are a weaker signal than you'd think — people accept by default rather than by conviction, especially deep into an afternoon. Rejections carry more information per event because they require effort against the default. Making acceptance require a tiny bit of effort (a confirm tap, not a ticked-by-default box) meaningfully improves the signal-to-noise ratio without being annoying. Worth doing; not urgent.

## Sequencing commitment

This doc commits to sequencing, not to any particular timeline. Level N+1 doesn't unlock until Level N has been operating cleanly and the consent UX, scrubbing quality, and legal posture required for N+1 are genuinely in place. If Level 1's reason taxonomy isn't converging, Level 2 waits. If Level 2's PII scrubbing has a false-negative rate that's higher than researchers would tolerate seeing in production, Level 3 waits.

The sequencing discipline is what makes the whole gradient defensible. Racing ahead because the corpus would be "so much more useful" at Level 3 is the move that gets Bristlenose written up in a way that makes the rest of the arc impossible.
