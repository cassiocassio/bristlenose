---
status: active
opened: 2026-09-22
---

# Morville's User Experience Honeycomb — codebook design and decision register

**What this is.** Why `bristlenose/server/codebook/morville.yaml` says what it
says: which of Morville's facets each tag carries, with the sentence of the
essay ("User Experience Design", Semantic Studios, 21 June 2004) or the book
it comes from; every wording decision, numbered, with evidence; and the
fixture that proves it. Sibling of `design-codebook-norman.md`, which holds
the shared method. The audit that produced 2.0 is
`docs/codebook-audits/2026-09-22-morville.md`.

**The reopening rule.** A decision here is reopened by a witness quote that
fails in `tests/fixtures/codebook-golden/morville.json`, never by a hunch.

**Scope rule (M-01).** The source is a one-page essay with seven facets and
no sub-facets. A sub-tag exists only where his paragraph, his books (Rosenfeld
& Morville; *Ambient Findability*) or the source he cites by name (Stanford's
credibility guidelines) supports it; every other distinction lives in
`apply_when` as examples. v1 had 7 × 4 = 28 tags, 17 of them from Nielsen,
Fogg, Microsoft, Cialdini, Tristan Harris and elsewhere. 2.0 is 15, uneven.

## Changelog

- _2026-09-22_ — register opened; **2.0** landed. The Valuable facet, which
  v1 had inverted from sponsor-side to user-side, is rebuilt from his three
  clauses; Accessible is scoped back to disabilities; Findable kept whole.

## Concept map

| Facet | Tag | Kind | Morville's words |
|---|---|---|---|
| Useful | usefulness | R | "whether our products and systems are useful" |
| Usable | ease of use | R | "Ease of use remains vital" |
| Desirable | brand and identity | R | "image, identity, brand" |
| | emotional design | R | "other elements of emotional design" (Norman 2004) |
| Findable | navigation clarity | A | "design navigable web sites"; AF "supports navigation and retrieval" |
| | search effectiveness | A | AF "retrieval"; R&M "search systems"; *Search Patterns* |
| | content discoverability | A | "locatable objects"; AF "easy to discover or locate" |
| | labelling | A | R&M "labeling systems" |
| Accessible | accessibility | R | "accessible to people with disabilities" |
| Credible | trustworthiness | R | "trust and believe what we tell them"; Stanford 3, 4 |
| | content accuracy | A | Stanford 1, 8 |
| | transparency | A | Stanford 2, 5, 9 |
| Valuable | customer satisfaction | R | "improve customer satisfaction" |
| | bottom line | R | "contribute to the bottom line" |
| | mission | R | "advance the mission" |

Retired (13): relevance, utility, problem-solution fit, feature gap;
learnability, efficiency, error tolerance; emotional appeal, aesthetic quality,
engagement; inclusive design, assistive compatibility, cognitive accessibility,
situational access; social proof; worth it, competitive value, time well spent,
return intent. Where they came from and where they went is in the register.

## Decision register

- **M-01 · scope · settled** — the essay only, plus his books and the source
  he cites; no sub-facet without a sentence behind it. *E4; owner's decision
  22 Sep 2026.*
- **M-02 · mechanism · settled** — `version:`; `renamed_from:` on every
  survivor that absorbed a name.
- **M-03 · Useful → usefulness · settled** — his paragraph is one thought;
  v1's four tags were four ways of saying it (utility is Nielsen's,
  problem-solution fit is lean startup, feature gap is UXR `unmet need` /
  `feature request`). *E4; E1.*
- **M-04 · Usable → ease of use · settled** — his words. learnability,
  efficiency and error tolerance are Nielsen's 1993 attributes imported into
  the facet he was explicitly deferring to HCI methods; rescued to UXR
  `learning curve` and Nielsen H7 / H3 / H5 / H9. The Credible pointer on
  error tolerance was wrong (anticipatory worry is UXR `anxiety` or Nielsen
  `hesitation`). *E4; E1.*
- **M-05 · brand perception → brand and identity · settled** — his words.
  *E4; E1.*
- **M-06 · emotional appeal + aesthetic quality + engagement → emotional design · settled** — his phrase, citing Norman 2004; engagement had no
  source. *E4; E1.*
- **M-07 · Findable kept whole · settled** — every v1 tag traceable to the
  essay or his books. *E4.*
- **M-08 · Accessible → accessibility · settled** — his sentence is
  disabilities, with the "more than 10%" figure. "and contexts" was
  Microsoft's persona spectrum; cognitive accessibility's definition was
  cognitive load (Yablonski `Sweller: cognitive overload`); situational
  access is UXR `device/channel`. *E4; E1.*
- **M-09 · Credible · settled** — trustworthiness kept (Stanford 3, 4);
  content accuracy kept (Stanford 1, 8); transparency re-rooted in Stanford
  2, 5, 9 instead of 2010s privacy vocabulary; social proof (Cialdini) is UXR
  `social influence`. *E4, the guidelines he cites; E1.*
- **M-10 · Valuable rebuilt · settled** — his facet is sponsor-side, three
  clauses: advance the mission, contribute to the bottom line, improve
  customer satisfaction. v1 inverted it to user-side cost-benefit (worth it,
  competitive value, time well spent — Harris 2013 — return intent). The
  participant-side evidence for the sponsor's value is what they say they
  would pay, switch, recommend, or came away with. `mission` is new and is
  what makes the honeycomb usable for public-sector and clinical research.
  *E4; E1.*
- **M-11 · header · settled** — description states his purposes (beyond
  usability, define priorities, each facet a looking glass) instead of
  "particularly strong at"; preamble says facets, not quality dimensions,
  and that the honeycomb sets priorities rather than demanding all seven.
  *E4.*
- **M-12 · inbound pointers · settled** — ten Morville tag names were
  load-bearing in Nielsen's and Yablonski's not-this text; all repointed the
  same day, and `tests/test_codebook_registers.py` now refuses a pointer to a
  tag that does not exist. *Mechanical.*

## Results

Measured 22 Sep 2026, `claude-sonnet-4-6`, the real autocode prompt, one run,
fixture of 20 golden, 2 traps, 1 out-of-scope (tests/fixtures/codebook-golden/morville.json). Structural gates
green. Live layer (`tests/test_codebook_registers.py::TestLiveRegistered`):
golden floor passed (≥ 80% of one-quote-per-tag golden rows correct at the
first run), no out-of-scope quote reached 0.4, no retired-tag trap reached
0.7. Two trap quotes were re-homed after the first run because the model's
reading was defensible in the author's own terms (see the fixture notes). The
golden set echoes the wording and is a floor, not a gate: what this codebook
needs next is the same as Norman's — real, task-driven speech
(`design-codebook-norman.md` § What the next iteration needs).

## Related files

- `bristlenose/server/codebook/morville.yaml`; v1 archived at
  `bristlenose/server/codebook/archive/morville_2026-09-22_v1-before-audit.yaml`
- `docs/codebook-audits/2026-09-22-morville.md`
