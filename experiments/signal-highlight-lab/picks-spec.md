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
