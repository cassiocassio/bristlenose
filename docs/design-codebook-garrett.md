---
status: active
opened: 2026-09-22
---

# Garrett's *The Elements of User Experience* — codebook design and decision register

**What this is.** Why `bristlenose/server/codebook/garrett.yaml` says what it
says: which of Garrett's elements each tag carries, with the chapter and page
in the 2nd edition (New Riders, Dec 2010, © 2011); every wording decision,
numbered, with evidence; and the fixture that proves it. Sibling of
`design-codebook-norman.md`, which holds the shared method (evidence classes,
the reopening rule, the harness). The audit that produced 2.0 is
`docs/codebook-audits/2026-09-22-garrett.md`.

**The reopening rule.** A decision here is reopened by a witness quote that
fails in `tests/fixtures/codebook-golden/garrett.json`, never by a hunch. Find
the `G-xx`, change the witness, watch it fail, change the words, bump
`version:`.

**Scope rule (G-01).** The codebook reflects the book as Garrett set it out:
five planes, each dependent on the one below, and two sides on every plane
(product as functionality, product as information). Every tag is one of his
elements or one of his chapter sub-headings. The February 2026 design had one
tag per plane in his words; the extraction commit padded every plane to four,
inventing where the book ran out. 2.0 is 18 tags, uneven because the book is.

## Changelog

- _2026-09-22_ — register opened; **2.0** landed. Eight of v1's 20 tags were
  his words, seven his concepts under our labels (two on the wrong plane),
  five not from the book. The description had said "mutually exclusive" and
  "top-down", both the reverse of chapter 2.

## Concept map

| Plane | Tag | Kind | Garrett's term and place |
|---|---|---|---|
| Strategy | user need | R | User Needs, ch. 3 p. 42; diagram "externally derived goals" |
| | product objective | R | Product Objectives, ch. 3 p. 37 (v1: "business objective", one of its three sub-heads) |
| | success metric | R | Success Metrics, ch. 3 p. 39; "make strategic goals quantifiable", ch. 4 |
| | brand identity | A | Brand Identity, ch. 3 pp. 38–39 (v1: "brand alignment" at Surface) |
| Scope | functional requirement | R | Functional Specifications, ch. 4 p. 68; "functional requirements" ~p. 70; diagram "feature set" |
| | content requirement | R | Content Requirements, ch. 4 p. 71 |
| | requirement priority | R | Prioritizing Requirements, ch. 4 p. 74 |
| | scope creep | R | "the dreaded 'scope creep'", ch. 4 |
| Structure | interaction design | R | ch. 5 p. 81; diagram "application flows to facilitate user tasks" |
| | information architecture | R | ch. 5 p. 88 |
| | error handling | A | ch. 5 p. 86, a sub-head of interaction design |
| Skeleton | interface design | R | ch. 6 p. 114 (v1 split it into "interface layout" + "component placement") |
| | navigation design | R | ch. 6 p. 118 (v1: "navigation pattern", filed on Structure) |
| | information design | R | ch. 6 p. 124 (v1: "wireframe issue", with this definition) |
| | convention | R | Convention and Metaphor, ch. 6 p. 110 |
| Surface | visual design | R | 1st-ed. ch. 7; 2nd-ed. Vision p. 136, Color Palettes and Typography p. 145 |
| | contrast and uniformity | A | ch. 7 p. 139; Follow the Eye p. 137 |
| | consistency | A | Internal and External Consistency, ch. 7 p. 143 |

Retired: value proposition (not in the book; Morville's Valuable), task flow
(not in the book; inside interaction design), component placement (half of
interface design), sensory experience (his phrase for the whole Surface output,
not a sub-category; mood is Morville's emotional design), aesthetic reaction
(not in the book; Morville / Yablonski). Not carried: conceptual model (ch. 5
p. 83), because it names the *designer's* chosen model and would collide with
Norman's user mental model / system image at every quote; a future register
entry may add it with a not-this to both.

## Decision register

Format: **id · kind · status** — decision. *Evidence.* Reopen when.

- **G-01 · scope · settled** — the book only; two axes; uneven planes. *E4;
  owner's decision 22 Sep 2026.*
- **G-02 · mechanism · settled** — `version:` bumped per accepted change;
  `renamed_from:` on every rename.
- **G-03 · user need · settled** — kept; carries the participant's own
  success criteria that v1 had mis-filed under success metric. *E4 ch. 3
  p. 42; E1.*
- **G-04 · business objective → product objective · settled** — his element;
  business goals are one of its three sub-heads and the diagram says
  "business, creative, or other internally derived goals". *E4 ch. 3 p. 37;
  E1.*
- **G-05 · success metric reworded · settled** — v1 defined it as the
  participant's personal criteria, a user need under his name. His metrics
  are the organisation's quantified indicators; the tag now asks for
  behaviour such a metric would count. *E4 ch. 4; E1.*
- **G-06 · brand alignment → brand identity, moved to Strategy · settled** —
  a Strategy objective in the book, delivered at Surface through external
  consistency. Judgement call: the quotes arrive at Surface; we follow the
  book. *E4 ch. 3 pp. 38–39, ch. 7 p. 143; E1.*
- **G-07 · feature requirement → functional requirement · settled** — his
  term. Not-this distinguishes UXR feature request (the wish) from the plane
  it lands on. *E4 ch. 4; E1.*
- **G-08 · content requirement · settled** — kept. *E4 ch. 4 p. 71.*
- **G-09 · priority → requirement priority · settled** — his heading; the
  participant-side ranking kept. *E4 ch. 4 p. 74; E1.*
- **G-10 · scope creep · settled** — his phrase, cited. *E4 ch. 4.*
- **G-11 · interaction design not-this reworded · settled** — multi-step
  flows stay here (the diagram's "application flows"); v1 sent them to the
  invented task flow. *E4 diagram, ch. 5 p. 81; E1.*
- **G-12 · information architecture · settled** — kept. *E4 ch. 5 p. 88.*
- **G-13 · error handling · settled** — added; his sub-head. Not-this to
  Norman's error taxonomy and Nielsen H9. *E4 ch. 5 p. 86; E1.*
- **G-14 · interface layout + component placement → interface design · settled** — one element, cut in two by the padding. *E4 ch. 6 p. 114, ch. 2;
  E1.*
- **G-15 · navigation pattern → navigation design, moved to Skeleton · settled** — a Skeleton element in the book. *E4 ch. 6 p. 118; E1.*
- **G-16 · wireframe issue → information design · settled** — the definition
  was already his; only the name was wrong. *E4 ch. 6 p. 124, diagram; E1.*
- **G-17 · convention · settled** — kept; styling norms now route to Surface
  consistency. *E4 ch. 6 p. 110.*
- **G-18 · visual design · settled** — kept, both editions cited. *E4.*
- **G-19 · contrast and uniformity · settled** — added; his sub-head; "I
  almost missed the button" at the surface. *E4 ch. 7 p. 139; E1.*
- **G-20 · consistency · settled** — added; his sub-head. *E4 ch. 7 p. 143;
  E1.*
- **G-21 · five retired · settled** — value proposition, task flow, component
  placement, sensory experience, aesthetic reaction (see concept map). The
  sync removes their rows when unreferenced and keeps them when a researcher
  has used them. *E4 (absent from TOC and index); E1 traps in the fixture.*
- **G-22 · header · settled** — "mutually exclusive" and "top-down" removed
  (ch. 2 "Building from Bottom to Top"; planes "dependent"); the duality
  named; bio brought to 2026; dead `jjg.net` replaced by
  jessejamesgarrett.com. *E4 S3 pp. 23–26, 34; S5, S6, S8.*

## Results

Measured 22 Sep 2026, `claude-sonnet-4-6`, the real autocode prompt, one run,
fixture of 25 golden, 1 trap, 1 out-of-scope (tests/fixtures/codebook-golden/garrett.json). Structural gates
green. Live layer (`tests/test_codebook_registers.py::TestLiveRegistered`):
golden floor passed (≥ 80% of one-quote-per-tag golden rows correct at the
first run), no out-of-scope quote reached 0.4, no retired-tag trap reached
0.7. Two trap quotes were re-homed after the first run because the model's
reading was defensible in the author's own terms (see the fixture notes). The
golden set echoes the wording and is a floor, not a gate: what this codebook
needs next is the same as Norman's — real, task-driven speech
(`design-codebook-norman.md` § What the next iteration needs).

## Related files

- `bristlenose/server/codebook/garrett.yaml`; archive of v1 at
  `bristlenose/server/codebook/archive/garrett_2026-09-22_v1-before-audit.yaml`
- `docs/codebook-audits/2026-09-22-garrett.md` — the audit
- `docs/codebook futures/bristlenose-codebook-prompts-garrett-norman.md` — the
  Feb 2026 origin, one tag per plane
