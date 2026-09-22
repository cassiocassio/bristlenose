---
status: active
opened: 2026-09-22
---

# Nielsen's 10 Usability Heuristics — decision register

**What this is.** The wording decisions behind
`bristlenose/server/codebook/nielsen.yaml`, numbered, with evidence, and the
fixture that proves them. The *adaptation analysis* — why expert-inspection
heuristics can be applied to participant speech at all, heuristic by
heuristic — is the older `design-nielsen-codebook.md` and stays canonical
for that question. This file is the sibling of `design-codebook-norman.md`,
which holds the shared method. The audit that produced 2.0 is
`docs/codebook-audits/2026-09-22-nielsen.md`.

**The reopening rule.** A decision here is reopened by a witness quote that
fails in `tests/fixtures/codebook-golden/nielsen.json`, never by a hunch.

**Scope rule (NL-01).** The heuristics are Nielsen's; the sub-tags are
Bristlenose's participant-side reading of each. 31 of the 36 v1 tags traced
to NN/g text; the register says which are his words, which his concepts
under our labels, and which are deliberate adaptation. This codebook was in
far better shape than the others: the defects were a bio fact, seven
silently compressed group names, two tags that were not his, one misfiled,
one misnamed, and five pointers left dangling by the Norman rewording.

## Changelog

- _2026-09-22_ — register opened; **2.0** landed: 34 tags under his 2020
  titles.

## Decision register

- **NL-01 · scope · settled** — his heuristics, our sub-tags, adaptation
  recorded. *E4; owner's decision 22 Sep 2026.*
- **NL-02 · mechanism · settled** — `version:`; `renamed_from:` on renamed
  tags and groups.
- **NL-03 · group names → the 2020 titles · settled** — v1 compressed seven
  of ten ("Status visibility" for *Visibility of System Status*) and nowhere
  recorded compressing them. Sentence-cased house style; H9 carries its full
  title. *E4, the NN/g article.*
- **NL-04 · mode confusion retired · settled** — Norman's term (1983; DOET),
  absent from every NN/g H1 text, and a duplicate of `norman.yaml`'s mode
  error. `opaque status` now points there. *E4; E1 witness: the edit-mode
  quote reads as status here and mode error in Norman.*
- **NL-05 · context loss retired · settled** — in no H6 text; wayfinding,
  not memory. Rescued to UXR 2.2 as `lost my place` with a not-this to
  Morville `navigation clarity`. *E4; E1 trap.*
- **NL-06 · destructive action moved H3 → H5 · settled** — H3 is about the
  exit; permanence of consequences is H5 ("present users with a
  confirmation option before they commit", "prevent high-cost errors
  first"). *E4; E1.*
- **NL-07 · helpful default → remembered for me · settled** — NN/g files
  defaults under H5 ("Choose Good Defaults"); what it puts under H6 is
  "History and Recently Visited Content", suggestions, "easily retrievable",
  which is what the definition always described. *E4; E1.*
- **NL-08 · guardrail reworded · settled** — anchored on his words, "helpful
  constraints and good defaults", "a confirmation option before they
  commit"; its pointer to Norman's retired `confirmation` now names
  `safeguard`. *E4; E1.*
- **NL-09 · pointers · settled** — grouping → natural mapping; learned
  behaviour → prior experience (UXR); findability → content discoverability;
  efficiency → ease of use; feature gap → feature request (UXR); aesthetic
  quality → emotional design; cognitive accessibility → cognitive overload
  (Yablonski); discoverability → hidden feature. Gated by
  `test_cross_references_name_real_tags`. *Mechanical.*
- **NL-10 · bio · settled** — nine heuristics in 1990, the tenth in
  *Usability Engineering* (1993); "one of the most cited researchers"
  dropped as unverifiable. *E4, CACM 1990.*
- **NL-11 · H5 adaptation stated · settled** — the preamble now says that
  hesitation and near miss observe the participant-side symptom by design,
  which the design doc had recorded and the shipped text had not. *E4, the
  design doc.*

## Results

Measured 22 Sep 2026, `claude-sonnet-4-6`, the real autocode prompt, one run,
fixture of 36 golden, 1 out-of-scope (tests/fixtures/codebook-golden/nielsen.json). Structural gates
green. Live layer (`tests/test_codebook_registers.py::TestLiveRegistered`):
golden floor passed (≥ 80% of one-quote-per-tag golden rows correct at the
first run), no out-of-scope quote reached 0.4, no retired-tag trap reached
0.7. Two trap quotes were re-homed after the first run because the model's
reading was defensible in the author's own terms (see the fixture notes). The
golden set echoes the wording and is a floor, not a gate: what this codebook
needs next is the same as Norman's — real, task-driven speech
(`design-codebook-norman.md` § What the next iteration needs).

## Related files

- `bristlenose/server/codebook/nielsen.yaml`; v1 archived at
  `bristlenose/server/codebook/archive/nielsen_2026-09-22_v1-before-audit.yaml`
- `docs/design-nielsen-codebook.md` — the adaptation analysis (its overlap
  table uses the 22 Sep names)
- `docs/codebook-audits/2026-09-22-nielsen.md`
