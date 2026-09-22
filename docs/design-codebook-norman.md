---
status: active
opened: 2026-09-22
---

# Norman's *The Design of Everyday Things* — codebook design and decision register

**What this is.** The record of why `bristlenose/server/codebook/norman.yaml`
says what it says: which of Norman's concepts each tag carries, with the page
in the 2013 revised edition it comes from; every wording decision, numbered,
with the evidence that drove it; and the harness that proves the wording
against quotes. It is the sibling of `design-nielsen-codebook.md`.

**Why it exists.** Prompts get iterated after a handful of mis-tags in one
project, and the same three arguments get re-run each time. A decision here is
reopened by a **witness quote that fails**, never by a hunch or by a few
proposals that looked wrong in one study. If you want to change a tag, find its
`N-xx` entry, add or change the witness in the fixture, watch it fail, then
change the words and bump `version:` in the YAML.

**Scope rule (N-01).** The codebook reflects the book as Norman set it out. We
do not fix him, extend him, or borrow from NN/g articles or the *Interactions*
essays; researchers who want a different lens run a second codebook and compare
signals. Every tag is marked **R** (his term, restored or kept), **A** (his
concept, in the book but not among the seven principles), or **P** (a
practitioner convenience that is not his at all).

## Changelog

- _2026-09-22_ — register opened from the audit of v1 (the 20 Feb 2026 text,
  unchanged since). v2, v2.1, v2.2 and v2.3 drafted and measured the same day;
  **v2.3 landed** as `norman.yaml` version 2.3, with `codebook_sync` (N-20)
  so instances that imported v1 are renamed in place. See §Results and
  §What the next iteration needs.

## Evidence policy — when the data cannot be cited

Every decision carries at least one evidence class. When the original quote
cannot be committed, a **synthetic twin** goes into the fixture and the entry
says so: the twin is the reproducible witness, the original is the provenance.

| Class | What | How it is cited | Committed? |
|---|---|---|---|
| **E1** | Fixture quote, written by us | fixture id | yes, `tests/fixtures/codebook-golden/norman.json` |
| **E2** | Public corpus | source URL + licence; local copy under a gitignored dir | only if the licence allows; otherwise twin |
| **E3** | Private project on this machine | project slug, run date, n; paraphrase, never the quote | never; twin |
| **E4** | The text itself | page number, 2013 edition | n/a |

Public corpora used so far (all E2): Steve Krug's *Rocket Surgery Made Easy*
demo test, Zipcar, 2020 (publicly posted, licence unstated — local only);
Wikimedia Usability Initiative 2009 highlight clips (CC BY-SA 3.0, transcribed
locally); Davies, Turner and Udell, Instagram think-aloud corpus, Figshare
21195811 (CC BY 4.0).

## Concept map — what each tag carries, and where it comes from

| Group | Tag | Kind | Norman's term and page |
|---|---|---|---|
| Discoverability | visible action | R | discoverability, p. 3, p. 10 |
| | hidden feature | R | discoverability failure, p. 3 |
| | exploration | **P** | not his |
| | first-time use | **P** | not his |
| | knowledge in the world | A | ch. 3, pp. 75–77, "precise behaviour from imprecise knowledge" |
| Feedback | clear feedback | R | p. 23, immediate and informative |
| | no feedback | R | p. 23, the elevator button |
| | delayed feedback | R | p. 23, "even a tenth of a second" |
| | uninformative feedback | R | p. 24, "worst of all" |
| | excessive feedback | R | p. 24, the 3 a.m. dishwasher |
| Conceptual model | user mental model | R | p. 31 |
| | system image | R | p. 31 (v1 said "system model", not his) |
| | model mismatch | R | designer's model ≠ user's model, p. 31 |
| | learned behaviour | R | conventions, p. 145 |
| Affordances and signifiers | affordance | R | pp. 11–13, what the thing permits; anti-affordance p. 19 |
| | clear signifier | R | pp. 13–19 |
| | misleading signifier | R | p. 18, his word |
| | missing signifier | R | pp. 13–19; jargon as system-image failure, p. 31 |
| Mapping | natural mapping | R | pp. 20–22 |
| | arbitrary mapping | R | stove burners, pp. 113–115 |
| | spatial correspondence | R | p. 21, his phrase |
| | grouping | R | p. 22 (v1 said "logical layout", not his) |
| Constraints | physical constraint | R | p. 125; forcing functions pp. 141–144 |
| | cultural constraint | R | pp. 128–131, conventions p. 145 |
| | semantic constraint | R | p. 129 |
| | logical constraint | R | p. 130 |
| Slips and mistakes | action slip | R | pp. 171, 173–175 (capture, description-similarity) |
| | memory lapse | R | pp. 171–172, both sides |
| | mode error | A | p. 177, a slip type |
| | rule-based mistake | R | p. 171 |
| | knowledge-based mistake | R | p. 171 |
| | safeguard | R | ch. 5, designing for error (v1: "confirmation" under Feedback) |

Not carried, by decision: feedforward (p. 72) and the gulfs (p. 38) are
diagnostic framing rather than codes; the visceral/behavioural/reflective
levels (ch. 2) are in the book but are an explanatory layer, not a principle,
and would be a second codebook.

## Decision register

Format: **id · kind · status** — decision. *Evidence.* Reopen when.

- **N-01 · scope · settled** — Reflect the book only; no NN/g, no essays, no
  improvements. *E4; owner's decision, 22 Sep 2026.* Reopen: never on evidence;
  only by the owner.
- **N-02 · mechanism · settled** — `version:` in the YAML is bumped on every
  accepted wording change; `TagPrompt.prompt_version` (a hash of the three
  prompt fields) attributes stored proposals to the wording that produced
  them. *Existing mechanism, `codebook_builder.prompt_version`.*
- **N-03 · description · settled** — v1 claimed "seven fundamental
  principles" and listed seven groups that were not his seven (Affordances
  missing, Slips vs Mistakes added). The description now names his seven and
  says the error taxonomy is the extra. *E4, pp. 71–73.*
- **N-04 · tests · settled** — v1 had no Norman quotes in the discrimination
  harness; the only assertion was that "Apply when:" appears. The golden
  fixture is the mechanical memory of this register: each entry that changed
  an outcome names a witness. *Audit, 22 Sep 2026.*
- **N-05 · rename · settled** — system model → system image. *E4, p. 31.*
- **N-06 · feedback set · settled** — system response → clear feedback;
  ambiguous → uninformative; no feedback and excessive feedback added. v1's
  delayed and ambiguous not-this fields each sent the "no response at all"
  case to the other. *E4, pp. 23–25; E1 witnesses: "no spinner, should I press
  it again", "genuinely can't tell whether it's on", "went back to the
  homepage, did that go through".* Note: several quotes v1 called ambiguous
  now read as no feedback; both are defensible, his term wins.
- **N-07 · affordance vs signifier · settled** — v1's affordance apply-when
  described a signifier ("looks pressable"), the exact misuse the 2013
  chapter corrects. affordance narrowed to what the thing permits; clear
  signifier added as the positive case; perceived affordance retired
  (p. 18: a kind of signifier); false → misleading. *E4, pp. 13–19; E1
  witnesses: ridged dial → clear signifier, Norman door → misleading.*
- **N-08 · mapping · settled** — logical layout → grouping, valence-neutral;
  spatial correspondence's not-this separates "beside" from "arranged like".
  *E4, pp. 20–22; E1 witnesses: "filters on the left, results on the right"
  (v1: spatial correspondence 0.80, wrong), "too many steps to change the
  address" (v1: logical layout 0.60, a complaint under a praise tag).*
- **N-09 · committed errors · settled** — an error that was made is coded in
  Slips and mistakes; model mismatch is the cause, not the code. v1's
  learned-behaviour and model-mismatch not-this fields routed the error away
  from the error group. *E4, pp. 170–172; E1 witness: "I swiped to go back
  and it deleted the row" (v1: model mismatch 0.85; v2: rule-based mistake
  0.95).*
- **N-10 · reading a cue before trying · settled in v2.1** — retiring
  perceived affordance left "looks like I can drag it... let me try" homeless
  and it went to exploration at 0.82 in v2. clear signifier's apply-when now
  covers reading a cue whether or not it has been tried. *E1 witnesses: the
  drag-up quote, "I'd guess this spins".*
- **N-11 · jargon is a signifier failure, not feedback · settled in v2.1** —
  a label, abbreviation, unit or format that presumes the designer's
  vocabulary is the system image failing to carry the designer's model to the
  user (p. 31). It happens before any action, so it is not feedback. v1 coded
  Krug's "rates shown for EVP $50" as ambiguous feedback at 0.70. *E4, p. 31;
  E2 witness: Krug EVP; E1 twin in the fixture.*
- **N-12 · knowledge in the world · settled in v2.2** — v2's wording ("it
  tells you as you go") matched reading information off the page: Krug's
  price narration went there at 0.60 and it took four of Krug's placeholder
  tags. Narrowed to the participant not having to remember or learn; not-this
  says reading a price is not this. *E2, Krug; E1 witnesses: wifi sticker
  (positive), price read-aloud (must not).*
- **N-13 · constraints · settled** — colour and symbol conventions are
  cultural, not semantic (v1 filed "red means danger" under semantic and the
  model followed it at 0.88). Physical constraint names forcing functions;
  greyed-out controls are a stretch of p. 125 and the definition says so.
  *E4, pp. 125–131, 141–144; E1 witness: "red's obviously stop".*
- **N-14 · adjacency misclicks are slips · settled** — "remove next to save
  for later, I binned it" is an action slip (description-similarity), not
  arbitrary mapping (v1: 0.85). *E4, p. 175; E1 witness.*
- **N-15 · mode error · settled in v2.2** — kept. Its wording matched: canon
  0.97, Wikipedia "two tabs, don't know where I'm editing" 0.65, no false
  positives across three corpora. v1 sent the canon case to ambiguous
  feedback at 0.70, above the accept line. *E4, p. 177; E1 + E2.*
- **N-16 · confirmation → safeguard · settled** — moved from Feedback to the
  error group with undo and sensibility checks. *E4, ch. 5.*
- **N-17 · exploration and first-time use · open** — both are ours, not his.
  Kept because researchers use them and they cost nothing on the traps. The
  standing question is whether a codebook under his name should carry tags
  he did not write. Reopen: by the owner, not by evidence.
- **N-19 · read-aloud is not system image · OPEN, measured in v2.3** — restoring
  knowledge in the world with "reading a price is just reading, no tag from
  this group" pushed read-aloud narration into system image (Krug: prices
  0.55, the FAQ answer 0.60) and took the EVP quote with it (0.55, twice).
  system image's not-this now says reading out the page is not system image
  and takes no tag at all; missing signifier keeps the cannot-read case.
  *E2, Krug, two runs; E1 twin: price read-aloud must take no tag above 0.4.*
  v2.3 result: the not-this did **not** move it — price read-aloud stayed
  system image 0.55 and the Krug EVP chunk stayed 0.55. The Krug chunk is
  mixed (jargon confusion, then reading the plan), so it is a poor witness;
  the clean twin "'Click and collect' and 'Collect from store', what's the
  difference?" reached missing signifier 0.85 in v2.3 (v1: ambiguous
  feedback 0.72), which is the N-11 witness that holds. Next lever is the
  system image apply-when, not its not-this.
- **N-20 · renames reach installed rows · settled** — AutoCode sends the
  YAML's names to the model and resolves its answers against the project's
  `TagDefinition` rows, keeping only names present in both
  (`autocode.build_tag_name_map`). A rename in the YAML alone would make every
  proposal for that tag resolve to nothing, on every instance that imported
  v1, with only a log warning. So a renamed tag or group carries
  `renamed_from:` in the YAML, and `server/codebook_sync.py` renames the row
  **in place** (ids, applied tags and proposals survive; `confirmation` moves
  group as `safeguard`), creates what is new, and removes a retired tag only if
  nothing references it. Runs before AutoCode builds its map, on the relink
  path of `import_template`, and at serve startup so the UI shows the new
  names before any run. Researcher-authored groups are never touched. *Pinned
  by `tests/test_codebook_sync.py`, which installs the literal v1 rows.*
- **N-18 · the placeholder problem · open, not this codebook's** — the shared
  autocode prompt says "always return a tag"; the preamble says "apply no
  tag". The model complies by assigning an attractor at 0.10, which differs
  by corpus (v1: user mental model, logical layout, exploration; v2.x:
  knowledge-based mistake, visible action) and feeds Signals at that weight
  with no floor. Fix belongs in the autocode prompt or the Signals weighting.
  *E2 + E3, all three corpora and the rock-climbing project.*

## Harness

`scripts/codebook-harness.py`: loads a shipped codebook or a draft YAML
through the real parser, builds the real taxonomy and prompt, batches at
`BATCH_SIZE`, and writes tag, confidence and rationale per quote; `--compare`
diffs two result files quote by quote. The fixture is
`tests/fixtures/codebook-golden/norman.json`; the tests are
`tests/test_norman_codebook.py` (structural, CI-safe; and the live layer under
`-m slow`). Fixture sets: golden
(two per tag), boundary pairs (one quote each side of every sibling seam),
messy (think-aloud register, no keyword echoes), canon (the book's own
examples), traps (everyday uses of tag words), and the three public corpora.

Tests carried (live ones slow-marked):

1. Golden: every tag reachable at ≥ 0.7 (the floor; it echoes the wording).
2. Pairs: assert per pair, so a regression names its seam.
3. Krug's top three: EVP, the rate discrepancy, buried availability each
   reach 0.7 under the register's tag.
4. Traps: all under 0.4, and no single attractor takes more than a third.
5. Stability: two runs, nothing crosses 0.7.
6. Valence: no complaint resolves above 0.6 to a positive-only tag.
7. Canon, including the two that v1 failed (mode error, knowledge in the
   world).
8. Register integrity (fast, no LLM): every `N-xx` marked settled with an E1
   witness names a fixture id that exists, and every fixture quote names an
   entry that exists.

## Results

Measured 22 Sep 2026, `claude-sonnet-4-6`, the real autocode prompt and
`BATCH_SIZE`, one run per cell unless stated. "Correct" means the tag is in
the witness's accept set after normalising renames.

| Set | n | Metric | v1 | v2 | v2.1 | v2.2 | v2.3 |
|---|---|---|---|---|---|---|---|
| golden + canon + traps | 78 | correct, all scored | 64/64 | 61/64 | 62/64 | 62/64 | 62/64 |
| boundary pairs + messy | 45 | correct, all scored | 37/43 | 40/43 | 39/43 | 39/43 | 40/43 |
| Krug Zipcar (E2) | 75 | at or above 0.7 | 5 | 2 | 7 | 6 | 6 |
| Wikipedia editing (E2) | 52 | at or above 0.7 | 0 | 2 | 2 | 2 | 6 |
| Instagram browsing (E2) | 40 | at or above 0.7 | 0 | 0 | 0 | 0 | 0 |

The golden set is a floor, not a gate: v1's 64/64 is the wording echoing
itself, and the three v2.x "misses" there are the affordance/signifier split
scored against v1's accept list (N-07) plus one read-a-cue quote (N-10). Where
the versions genuinely differ is the pairs (v1 wrong on N-09, N-13, N-14,
N-08's two witnesses; v2.x right) and Krug.

Watch-list, tag @ confidence, v1 → v2 → v2.1 → v2.2 → v2.3 (v2.3 equals v2.2 unless shown):

- mode error canon: ambiguous feedback 0.70 → mode error 0.97 → action slip 0.88 → mode error 0.97
- knowledge in the world canon: physical constraint 0.30 → 0.97 → visible action 0.55 → 0.97
- price read-aloud (must not be knowledge in the world): system response 0.50 → knowledge in the world 0.60 → system image 0.55 → system image 0.55
- Krug EVP jargon: ambiguous feedback 0.70 → knowledge in the world 0.45 → missing signifier 0.72 → system image 0.55 → 0.55 (see N-19; the clean twin holds at missing signifier 0.85)
  **Read across all chunks, not one:** the EVP problem spans 8 caption chunks. Chunks at or above 0.7, v1 → v2 → v2.1 → v2.2 → v2.2 again → v2.3: 1 (ambiguous feedback ×1) → 0 (none) → 5 (missing signifier ×5) → 4 (missing signifier ×4) → 2 (missing signifier ×2) → 4 (missing signifier ×4). v1 surfaced it once, as feedback, which it is not; v2.3 surfaces it three times as missing signifier.
- Krug rate discrepancy: model mismatch in all four, 0.72 to 0.75
- Krug availability buried in FAQ: hidden feature 0.60 → knowledge in the world 0.55 → visible action 0.50 → system image 0.60
- swipe-to-delete: model mismatch 0.85 → rule-based mistake 0.95 / 0.92 / 0.92
- red is stop: semantic 0.88 → cultural 0.95 / 0.93 / 0.95
- too many steps: logical layout 0.60 → grouping 0.80 / 0.82 / 0.82
- "I'd guess this spins? Let's see": perceived affordance 0.88 → exploration in all four v2.x (0.78 to 0.82) — the open residual of N-10
- Wikipedia "two tabs": memory lapse 0.55 → mode error 0.65 → knowledge-based mistake 0.60 → mode error 0.65 → 0.72

Placeholder attractor on Krug (N-18), the tag the sub-0.4 quotes fall into:
v1 exploration 19 of 35; v2 knowledge-based mistake 21; v2.1 user mental model
23; v2.2 knowledge-based mistake 29. A negative error tag as the noise floor
is worse than a neutral one, and the choice moves with wording that has
nothing to do with those quotes. The fix is the prompt's "always return a
tag", not this file.

Stability: v1 golden twice, 72/78 same tag, none crossed 0.7. v2.2 on Krug twice, **57/75** same tag, at or above 0.7 went 6 → 4: the corpus is 40-word caption chunks with no punctuation and most confidences sit at 0.45–0.60, so it flips readily; treat Krug counts as ±2. The EVP quote was system image 0.55 on both v2.2 runs against missing signifier 0.72 on v2.1, so that move is wording (N-12's not-this sent read-aloud to the next group), fixed in v2.3 (N-19).


## What the next iteration needs: more and richer real data

Every wording decision above was checked against one task-driven public
transcript — Krug's twenty-minute Zipcar demo, in 40-word caption chunks with
no punctuation — plus a 2009 Wikipedia highlight reel transcribed by ASR and
an Instagram *browsing* corpus that, correctly, produces almost nothing.
That is thin. The synthetic sets prove the codebook is self-consistent and
that the sibling seams discriminate; only real speech proves it surfaces
what a researcher would mark, and on Krug two runs of the identical file
agreed on 57 of 75 tags. Several of the calls recorded here (N-10's residual,
N-19, the exact confidence the EVP chunks reach) are decided by a margin
smaller than that noise. We are dancing on pinheads.

Before the next wording pass, the corpus should grow, in this order:

1. **Our own moderated think-alouds**, run through the real pipeline so the
   quotes are extracted the way AutoCode receives them, not chunked by word
   count. Two or three sessions on two different products would already
   outweigh everything above. E3: cite by slug and date, twin what matters.
2. **More public task-driven sessions.** The Wikimedia Usability Initiative's
   full interview videos (15 × 45–60 min, CC) are referenced but not linked on
   the current wiki; an Internet Archive snapshot of usability.wikimedia.org
   from 2009–2010 may still carry them. Penn State's Canvas think-aloud
   report has verbatims. Krug's second demo is offline.
3. **Physical products**, which Norman's examples mostly are and which none of
   the corpora touch: a kitchen appliance, a car, a thermostat. Even one
   session would test the affordance and constraint groups on the kind of
   thing the book is about.

Until then, treat a change that moves one or two Krug chunks as unproven, and
require a fixture twin for anything a real quote is claimed to show.

## Related files

- `bristlenose/server/codebook/norman.yaml` — the codebook; every changed tag
  carries a dated `# N-xx` comment pointing here, and renamed ones carry
  `renamed_from:`
- `bristlenose/server/codebook_sync.py` — the in-place rename (N-20)
- `scripts/codebook-harness.py`, `tests/fixtures/codebook-golden/norman.json`,
  `tests/test_norman_codebook.py`, `tests/test_codebook_sync.py`
- `docs/codebook futures/bristlenose-codebook-prompts-garrett-norman.md` — the
  Feb 2026 origin of v1, one tag per principle
- `docs/design-nielsen-codebook.md` — the sibling adaptation analysis
- `docs/codebook-defects.md` — code-versus-doc defects; wording lives here, not
  there
