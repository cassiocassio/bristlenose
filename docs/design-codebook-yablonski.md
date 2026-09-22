---
status: active
opened: 2026-09-22
---

# Yablonski's *Laws of UX* — codebook design and decision register

**What this is.** Why `bristlenose/server/codebook/yablonski.yaml` says what
it says: which law each tag carries, in the sense lawsofux.com states it;
every wording decision, numbered, with evidence; and the fixture that proves
it. Sibling of `design-codebook-norman.md`, which holds the shared method.
The audit that produced 2.0 is `docs/codebook-audits/2026-09-22-yablonski.md`.

**The reopening rule.** A decision here is reopened by a witness quote that
fails in `tests/fixtures/codebook-golden/yablonski.json`, never by a hunch.

**Scope rule (Y-01).** Every tag is a law lawsofux.com states, in the sense
he states it. The six groups and the "Surname: effect" tag prefix are
Bristlenose's conventions — the site files entries only as theory or
psychology, and the book (ten law chapters in both editions) has none.

## Changelog

- _2026-09-22_ — register opened; **2.0** landed: 24 laws, two of them
  added because participants say them aloud, one removed because it is not
  on the site.

## Concept map

| Group | Tag | Kind | lawsofux.com entry |
|---|---|---|---|
| Choice and decision | Choice overload | R | choice-overload (v1: "Hick: choice paralysis") |
| | Hick: decision simplicity | A | hicks-law |
| | Von Restorff: option salience | A | von-restorff-effect |
| Expectation and convention | Jakob: convention expectation | A | jakobs-law |
| | Jakob: transfer confusion | A | jakobs-law |
| | Postel: input intolerance / input forgiveness | A | postels-law (narrowed to input) |
| | Carroll: active user paradox | A, new | paradox-of-the-active-user |
| Memory and experience | Kahneman: peak moment / ending effect | A | peak-end-rule |
| | Zeigarnik: unfinished pull | A | zeigarnik-effect |
| | Hull: completion momentum | A | goal-gradient-effect |
| | Working memory: overload | R | working-memory (v1: "Miller: memory overload") |
| Perception and aesthetics | Kurosu: beauty trust / aesthetic forgiveness | A | aesthetic-usability-effect |
| | Gestalt: grouping confusion / grouping clarity | A | law-of-proximity, -similarity, -common-region, -uniform-connectedness |
| | Selective attention: overlooked | A, new | selective-attention |
| Effort and complexity | Tesler: complexity burden / complexity absorbed | A | teslers-law |
| | Fitts: target difficulty | A | fitts-law |
| | Sweller: cognitive overload | A | cognitive-load |
| Speed and responsiveness | Doherty: instant response / waiting frustration | A | doherty-threshold |

Retired: Thaler: default acceptance (not on the site; Nielsen `remembered for
me` / `risky default` own the behaviour).

## Decision register

- **Y-01 · scope · settled** — his laws, his senses; our groups and prefix,
  said so in the preamble. *E4; owner's decision 22 Sep 2026.*
- **Y-02 · mechanism · settled** — `version:`; `renamed_from:`.
- **Y-03 · Hick: choice paralysis → Choice overload · settled** — Hick's Law
  is decision *time*; being overwhelmed and abandoning is his Choice
  Overload entry (Toffler 1970). Hick keeps the decision-simplicity pole and
  each not-this names the other. *E4 lawsofux.com/choice-overload; E1.*
- **Y-04 · Miller: memory overload → Working memory: overload · settled** —
  v1 rested on 7±2, which his own first takeaway says not to use as a limit;
  Working Memory is the right parent. *E4 lawsofux.com/working-memory; E1.*
- **Y-05 · Thaler retired · settled** — not on the 30-entry index. *E4; E1
  trap.*
- **Y-06 · Von Restorff reworded · settled** — a memory effect ("most likely
  to be remembered"), not attention→choice. *E4; E1.*
- **Y-07 · Prägnanz dropped from the Gestalt list · settled** — "simplest
  form possible" is not a grouping law. *E4.*
- **Y-08 · pointers · settled** — four not-this named Nielsen tags that never
  existed ("error situation", "loss-of-control issue", "error recovery
  issue"), two named "findability" (a Morville group is `Findable`), three
  named the tag's own stale pre-rename self; all repointed, gated by
  `test_cross_references_name_real_tags`. *Mechanical.*
- **Y-09 · two laws added · settled** — Paradox of the Active User and
  Selective Attention, both his and both said aloud in think-alouds ("I never
  read those", "I thought that was an ad"). *E4; E1.*
- **Y-10 · header · settled** — bio no longer places him at Google (GM in the
  2020 bio, Mixpanel now); "in 2017" dropped as unverifiable; "not all 21
  laws from the book" replaced by the true counts (ten in the book, thirty
  on the site); "Hick's Law (choice paralysis)" corrected in the
  description; O'Reilly link points at the 2nd-edition page. *E4.*

## Results

Measured 22 Sep 2026, `claude-sonnet-4-6`, the real autocode prompt, one run,
fixture of 24 golden, 1 trap, 1 out-of-scope (tests/fixtures/codebook-golden/yablonski.json). Structural gates
green. Live layer (`tests/test_codebook_registers.py::TestLiveRegistered`):
golden floor passed (≥ 80% of one-quote-per-tag golden rows correct at the
first run), no out-of-scope quote reached 0.4, no retired-tag trap reached
0.7. Two trap quotes were re-homed after the first run because the model's
reading was defensible in the author's own terms (see the fixture notes). The
golden set echoes the wording and is a floor, not a gate: what this codebook
needs next is the same as Norman's — real, task-driven speech
(`design-codebook-norman.md` § What the next iteration needs).

## Related files

- `bristlenose/server/codebook/yablonski.yaml`; v1 archived at
  `bristlenose/server/codebook/archive/yablonski_2026-09-22_v1-before-audit.yaml`
- `docs/codebook-audits/2026-09-22-yablonski.md`
