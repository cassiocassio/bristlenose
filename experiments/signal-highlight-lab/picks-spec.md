# What reads well: a spec reversed from the owner's picks

91 bullets, one favourite each, picked blind (variant names hidden, order shuffled) on
30 Oct 2026. Counts below are over those 91 picks. The picks themselves are in the
gitignored `data/picks.tsv`.

## What the picks show

| measure | picks | for comparison |
|---|---|---|
| median length | **8 words**, 31% of the bullet | shipped today: 12 words, 45% |
| range | 5 to 11 words in 81 of 91; 2 to 17 overall | |
| over half the bullet | 10 (all short bullets) | shipped: 35 |
| chose the shortest option offered | 23 | |
| chose something longer than a shorter option it contains | 58 | |
| chose something shorter than a longer option that contains it | 77 | |
| leaves out the trailing outcome clause ("leaving...", "causing...", "which...") | **39 of 39** bullets that had one | |
| begins with "a participant" or a reporting verb ("said", "expressed") | **1** of 91 | |
| contains a verb (what the product did or failed to do) | 80 of 91 | |
| contains a feeling word | 7 of 91 | |

Variant win rate (picks that match a variant's answer / bullets where that variant gave a
usable answer): distinct 51%, phrase25 48%, tight1 48%, tight 43%, cap6 41%, current 34%,
twostep 34%, combined 28%, **stored (today) 14%**. No one picked "no highlight".

## The pattern

1. **Goldilocks, not minimal.** The favourite is neither the shortest nor the longest
   option. Too short loses (`combined`, a 4-word cap, was picked least of the shortened
   variants; 23 times the shortest option was 3 words or fewer and was passed over). Too
   long loses (today's wording, 14%).
2. **A small self-contained claim.** Usually the thing and what happened to it: the
   product as subject, a verb, and the specific object or qualifier ("withheld X and Y
   until Z", "could not find K as a category option"). The qualifier that says *where* or
   *when* usually stays; picks that were longer than a shorter option mostly added it.
3. **Stop before the consequence.** Every time the bullet continued into an outcome
   clause, the pick ended before it.
4. **Start after the subject.** Never "A participant ...", never a reporting verb. The
   highlight begins at the product's behaviour (or the thing), not the person.
5. **The mechanism, not the feeling.** Feeling words appear in 7 picks, almost all because
   the verb itself was "confused" or "frustrated" and the product subject came with it.
6. **Bullet-relative, with a ceiling.** On a short bullet the pick can be most of it (up
   to 70%); on a long bullet it stays about a third. The ceiling that matched the picks is
   about 12 words.

## Spec for the prompt (replaces the 5-word and quarter rules in `recommended-prompt.diff`)

- The highlight is the shortest span that works as a small, self-contained claim about the
  product: what it did or failed to do, with the specific thing it was done to and, if it
  matters, when or where.
- Aim for 6 to 10 words; never more than 12, and normally no more than about a third of the
  assertion. On a very short assertion it may be most of it.
- Begin where the product's behaviour begins: not at "a participant", not at a reporting
  verb ("said", "found that", "expressed").
- End before the outcome or reaction that follows ("leaving ...", "causing ...", "which ...",
  "so ...").
- Characters must really be in the assertion's text; the participant's own words are usually
  not.
- A feeling word alone is never the highlight.

## Consequences for the earlier recommendation

- **The scratch `quote_fragment` step can probably go.** The picks' length (8 words) is where
  `tight1` and `phrase25` land without it, and `tight1` was picked 48% of the time against
  43% for `tight`. The five-word cap was the thing the two-step existed to enforce, and the
  owner does not want five words. This removes the schema change.
- **Not tested yet:** wording written from this spec. The picks say what reads well from
  existing candidates; whether a new prompt reproduces it needs one more replay (about
  £0.10) and then the joint bullet-plus-highlight check on the production model.

## Replay from the spec (30 Oct 2026, later)

Wording written from the spec (`spec`, `spec_ex`, then `mid`: the same rules plus a 6 to 9
word length and three invented examples), no scratch step, scored against the 91 picks.
The owner's own reading of it: the hard part is "just enough meaning"; what matters is
precise **start and end points**, and whether a researcher wants to read the highlight at
all. So boundaries are scored, not only length.

| variant (model) | located | words median | 4 or fewer | over 12 | over half | same start as pick | same end as pick | both |
|---|---|---|---|---|---|---|---|---|
| `tight1` (Haiku) | 88 | 8 | 8 | 7 | 6 | 67 | 56 | 43 |
| `mid` (Haiku) | 87 | 10 | 0 | 21 | 19 | 52 | 41 | 26 |
| `spec` (Haiku) | 86 | 11 | 1 | 34 | 31 | 50 | 45 | 30 |
| `tight1` (Sonnet 4.6) | 91 | 5 | 27 | 0 | 0 | 43 | 38 | 19 |
| `mid` (Sonnet 4.6) | 91 | 9 | 0 | 10 | 8 | 51 | 35 | 25 |
| `spec` (Sonnet 4.6) | 88 | 10 | 2 | 22 | 17 | 48 | 42 | 28 |

- **Length is model-dependent.** Told "5 words, a quarter", Haiku overshoots to a median
  of 8 (the picked length) and Sonnet obeys, giving 5 (27 of 91 at four words or fewer, a
  length the picks rejected). Wording tuned on one model is wrong on the other, and the
  production default is Sonnet.
- **Wording written from the spec overshoots on both models** unless the number is stated
  hard: "6 to 10 words, never more than 12" gave a median of 11 on Haiku. `mid` (6 to 9,
  a third) is the best of the Sonnet wordings on length (no highlight of 4 or fewer, 10
  over 12), at the cost of still running long on a fifth of bullets.
- **No wording reproduces the picked boundaries on Sonnet more than about a third of the
  time** (both ends match on 25 to 28 of 91). An exact match is a harsh test, since two
  good highlights can differ by a word, so the second blind round (`lab.py round2`,
  `data/viewer-round2.html`) puts Sonnet's candidates, Haiku's best and the owner's
  round-1 pick side by side on the 90 bullets where they differ.
- **The regenerated `recommended-prompt.diff`** is built on `mid`'s rules (start where the
  product's behaviour begins, end before the outcome, 6 to 9 words and at most a third,
  no feeling word alone). It has no scratch field and no schema field, only two
  description edits in `structured.py`. It is not yet tested on the production model
  writing bullet and highlight together.

Spend on this thread: 78 + 39 + 78 + 39 further calls (Haiku and Sonnet 4.6), about $0.65
in all; lab total about $1.9, roughly £1.5.

## Round 3: does giving the model the card's claim help? (30 Oct 2026)

Owner's round-2 reading: 22 of 30 changed picks got shorter ("not ruthless enough the first
time"), 8 got longer ("too short and you are meaningless"); whether a tail such as
"until postcode entry" is crucial depends on what the reader already knows, so it cannot be
a rule. Idea tested: the highlight is read under the card's claim, so show the replay that
claim and tell it to skip what the claim already says. Scored against the owner's FINAL pick
per bullet (round 2 where made, else round 1), Sonnet 4.6, 91 bullets:

| variant | words median | start | end | both | F1 |
|---|---|---|---|---|---|
| `mid` (6 to 9 words) | 9 | 54 | 40 | 34 | 0.71 |
| `mid58` (5 to 8 words, control) | 9 | 51 | 45 | 33 | 0.72 |
| `claim` (`mid58` + the card's claim) | 9 | 47 | 40 | 27 | 0.69 |
| `tight1` (5 words, 25%) | 5 | 56 | 47 | 32 | 0.71 |
| Haiku `tight1` | 8 | 66 | 57 | 46 | 0.85 |

The claim **did not help**. It differed from the control on 22 bullets, and where it
differed it mostly moved the highlight to a *different part* of the bullet (the part the
claim does not cover) instead of trimming the same part, which is not what the owner picks.
Shortening the range from 6-9 to 5-8 made no measurable difference either: Sonnet reads a
range as "about 9". Haiku with a nominal 5-word cap still matches the owner best (46 of 91
exact), because it overshoots to the picked length.

Open option, not built: a separate cheap highlight step (Haiku) after the bullet is written,
instead of asking the bullet-writing model for both. Costs one extra small call per card.
