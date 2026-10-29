---
status: proposed
last-trued: 2026-10-28
depends-on:
  - docs/design-signal-snapshot-lifecycle.md
  - docs/research/signal-evidence-fragment-calibration.md
consumed-by:
  - docs/design-signal-card-narrative-evidence.md
---

# Signal evidence assertions: data and prompting

## Decision

For each persisted signal card, the narrative generator may create up to four
**evidence assertions**. Each is a compact playback of one participant's
evidence, with one optional **intervention fragment**: a contiguous phrase
which identifies the product/system property, behaviour, or omission that
explains the signal and could plausibly be preserved or changed.

This document owns the data model, prompt, validation and persistence. It does
not prescribe type, colour, spacing, highlighter rendering or interactions;
those belong to `design-signal-card-narrative-evidence.md`.

## Why this is a separate analysis artifact

The fragment is not “the strongest words”, a sentiment label, or a generic
emotion. It is the concise warrant a researcher would use in a client report:
the reason this evidence belongs in this signal, and often the thing a team
would alter to improve the experience.

The deciding test is counterfactual:

- **negative evidence:** if this property/behaviour/absence were corrected,
  would the user’s experience plausibly improve?
- **positive evidence:** if this property were removed or weakened, would the
  reported benefit plausibly diminish?

If neither is true, no fragment is emitted. A participant mistake (“did not
check the material”) or a bare result (“abandoned the order”) is evidence, but
not an intervention fragment until the source identifies the system mechanism
behind it.

## Reader-facing contract

The reader receives persisted, validated `evidence_assertions` as part of a
complete signal-card snapshot. Reading the Signals lens never invokes an LLM.

- Assertions are optional; 0 is valid.
- Each V1 assertion cites exactly one source quote and one participant.
- The narrative text may be a concise grounded playback rather than a raw
  transcript quotation, but it may not add facts, motives or causal claims
  absent from the cited source.
- A highlighted fragment is optional. When present it occurs once, is a
  contiguous range in the assertion text, and is accompanied by a source
  excerpt for audit.
- A legacy card with only `evidence_summary` remains readable as an ordinary,
  unlinked summary. The client must not guess a fragment or participant.

## Durable schema

Add `evidence_assertions` to `SignalCardSnapshot` as an ordered JSON array (or
normalised child rows if snapshot query needs make that worthwhile). It is part
of the immutable published snapshot, alongside title, claim and evidence
summary.

```ts
type SignalEvidenceAssertion = {
  id: string;                         // stable within the snapshot/card
  ordinal: number;                    // 0..3, reading order
  text: string;                       // e.g. “One participant was … p1.”
  sourceQuoteId: string;              // durable quote ID, belongs to this card
  participantId: string;              // must equal the quote's participant
  sourceExcerpt: string;              // exact contiguous substring of raw quote
  interventionFragment?: {
    start: number;                    // Unicode-safe offsets in `text`
    end: number;                      // one non-empty contiguous range
    text: string;                     // exactly text.slice(start, end)
    rationale: "negative_actionable_cause" | "positive_enabling_cause";
  };
};
```

`sourceExcerpt` is not necessarily rendered in the assertion; it is evidence
for validation, code review and future audit UI. It must be copied verbatim
from the stored source quote after normalising only Unicode and whitespace for
comparison. The quote ID, not displayed text or array index, is the authority
for the assertion-to-quote connection.

The first version intentionally does not allow a multi-quote or multi-person
assertion. It prevents a statement such as “one participant” pointing at a
plural set, keeps the inline badge unambiguous, and makes validation cheap.
Support that later as an explicit schema version, not an array quietly smuggled
into a singular field.

## Generator inputs

The existing high-quality narrative call receives the deterministic card
material. Extend that call rather than issuing another model request:

- stable signal-card identity and current codebook/group definitions;
- generated title and claim task inputs;
- selected candidate quotes: durable ID, participant ID, timecode, tag/group
  evidence, intensity and transcript excerpt;
- the card’s existing selected quote IDs, so an assertion cannot cite a quote
  that will not be available in the card;
- a bounded maximum of four assertions.

Quote text is untrusted input and remains enclosed by the existing
`wrap_untrusted` prompt boundary. Instructions contained in an interview can
never become instructions to the narrative provider.

## Prompt behaviour

The prompt must request structured JSON only. It should tell the provider:

```text
For each useful source quote, you may create one short evidence assertion.

An assertion is a faithful playback of one participant’s evidence for this
signal. It must cite exactly one supplied quote ID and that quote’s participant
ID. Do not infer facts, intent, frequency, causality, or consensus not stated
by the source.

Optionally mark one intervention fragment inside the assertion text. Select it
only when it is a single contiguous, intelligible causal unit naming the
product/system property, behaviour, or omission that explains why the evidence
supports this signal.

For negative evidence, ask: if this quality were corrected, would the user’s
experience plausibly improve? For positive evidence, ask: if this quality were
removed, would the benefit plausibly diminish? If the answer is not supported
by the source, omit the fragment.

Prefer the underlying mechanism over generic emotion, participant intention,
or a later outcome. Do not select only an adjective or a tag word. Keep the
verb/relation needed to make the fragment intelligible. Do not split the
fragment, and do not use more than one fragment.

Return the exact quote substring that supports the assertion. Return JSON
matching the supplied schema, with character offsets for the fragment.
```

Calibration examples live in
`docs/research/signal-evidence-fragment-calibration.md`. They must be converted
to few-shot examples only after the marked set is reviewed; do not embed an
unreviewed worksheet as prompt truth.

## Deterministic validation

The provider's output is a candidate, never a publishable assertion by itself.
Before snapshot publication, validate:

1. JSON parses and conforms to the schema; length and assertion count are
   bounded.
2. `sourceQuoteId` is one of the card’s selected quote IDs and has not been
   redacted.
3. `participantId` equals the durable participant ID for that quote.
4. `sourceExcerpt` normalises to a non-empty contiguous substring of that raw
   quote.
5. The fragment range is in bounds; `text.slice(start, end)` equals the
   supplied fragment; it is one non-empty contiguous range.
6. The fragment is not only punctuation, a tag name, a participant identifier,
   or a generic sentiment label.
7. The assertion does not duplicate another assertion’s quote ID in V1.

Validation cannot fully prove semantic entailment. The high-quality generator
is responsible for grounded paraphrase; deterministic checks establish
provenance and protect the reader from stale/mismatched records. On validation
failure, discard that assertion only. Do not fail a complete card merely
because it has fewer evidence assertions. A bounded repair retry can be added
after measurement, but V1 must not silently spend another provider call.

## Publication and lifecycle

Evidence assertions share the title/claim/evidence narrative lifecycle:

- generation occurs only during a signal-card refresh, after deterministic
  card evidence and quote selection are complete;
- the new card is published atomically with its assertions, title, claim and
  metrics;
- unchanged card fingerprints reuse the prior narrative, including assertions;
- provider/network failure retains the prior complete snapshot under the
  snapshot-lifecycle policy; opening the lens never regenerates it;
- a changed card may not inherit assertions from a previous card fingerprint.

The narrative cache key/version must include this prompt/schema version so a
future calibrated prompt cannot reuse records from an incompatible contract.

## Test matrix

- negative actionable cause is marked: “the warning did not name which items
  were unavailable”;
- positive enabling cause is marked: “the price update immediately beside the
  configuration”;
- generic emotion alone is unmarked: “felt frustrated”;
- participant behaviour alone is unmarked: “did not check the material”;
- a complete causal unit remains one fragment: “discovered at checkout that
  selected items could not actually be collected together”;
- an assertion with a cross-card quote, different participant, altered source
  excerpt, invalid offsets, duplicate V1 quote or redacted quote is rejected;
- a legacy summary renders without fabricated fragment or attribution;
- offline reading returns saved assertions and makes no provider request.

## Implementation sequence

1. Finalise marked calibration examples and derive reviewed few-shot cases.
2. Add the schema, serializer and migration to durable card snapshots.
3. Extend the existing narrative prompt/output parser with schema-versioned
   assertions and deterministic validation.
4. Persist and reuse valid assertions through the refresh coordinator.
5. Expose the read-only assertion contract to the client.
6. Implement the separate visual treatment and interaction spec.
