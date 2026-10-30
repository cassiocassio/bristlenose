# Signal highlight lab

Owner feedback, 30 Oct 2026: on a Signals card each evidence bullet colours a span of its
text, and there is too much colour. This lab measured it, replayed Step 6 of
`signal-elaboration.md` under different wordings, and had the owner pick by eye, blind.

**Status: ongoing experiment, nothing adopted.** The shipped prompt, schema, frontend and
CSS are untouched. `recommended-prompt.diff` is the proposed edit; it applies cleanly to
`main` (`git apply --check -p1`) and has not been applied. The owner decides.

## The short version

- Today's highlight is long (median 45% of a bullet, 12 words) and every bullet has one,
  so a card is about 45% coloured and a page 46%.
- What reads well, from the owner's 91 blind picks, is a small self-contained claim of
  about 7 words that **starts where the product's behaviour begins and ends before the
  outcome**. Too long is a block of ink; too short is meaningless and the reader bounces.
- Two levers cut the colour: **shorter highlights** (page 46% to 33%) and a **colour
  budget** of at most two highlighted bullets per card (to 24%, 14 coloured words per card
  against 27). The diff has both.
- The production model (Sonnet) does not reproduce the owner's boundaries more than about a
  third of the time with any wording tried. The end-to-end test, with the model writing the
  bullet and the highlight together, has **not** been done. Do not adopt before it.

## Files

| file | what |
|---|---|
| `extract.py` | reads stored assertions and claims read-only (no LLM call), writes `data/assertions.json`, prints the baseline |
| `lab.py` | `plan`, `run`, `report` (table and the radio viewer), `round2`, `cards` (card-level viewer) |
| `recommended-prompt.diff` | the proposed edit to `signal-elaboration.md` and `structured.py`, not applied |
| `picks-spec.md` | the spec reversed from the owner's picks, and the round 3 result |
| `data/` | **gitignored**: assertions, model answers (`results.json` Haiku, `results-sonnet.json` Sonnet), the owner's picks (`picks.tsv`, `picks-round2.json`), viewers, call log. These hold participants' words |

Run: `extract.py` once, then `lab.py plan`, `lab.py run` (paid; `LAB_MODEL`, `LAB_RESULTS`,
`LAB_VARIANTS` select model, file and variants), `lab.py report`.

## Data

The Beauty-function card is in the "ikea research videos" study under `~/Documents`, not in
`trial-runs/project-ikea`. The pool reads four project databases on this Mac, read-only,
and keeps the **latest snapshot's** bullet per card and quote: **91 bullets on 39 cards**
that carry a stored highlight (median bullet 26 words, median 2 bullets per card, 4 at most).

## 1. Baseline (what ships today)

| | median | p90 | max | over 50% |
|---|---|---|---|---|
| highlight share, by words | 45% | 68% | 95% | 35 of 91 |

Median highlight 12 words. The longest are whole clauses, because the current Step 6 asks for
"one contiguous, intelligible causal unit" and to "keep the verb/relation needed to make the
fragment intelligible", and its own second example is eight words. Worst ten:
`data/worst.md`.

## 2. What was tried

Replay of Step 6 only: bullet text fixed, the model returns just the highlight, every answer
goes through the product's `_validated_fragment`. Models: Claude Haiku 4.5 (cheap, most
rounds) and Claude Sonnet 4.6 (the production default).

| round | what | finding |
|---|---|---|
| 1 | ten wordings (cap, phrase, distinctive, two-step, combined...) on Haiku; owner picks blind, 91 picks | median pick 7 words; ends before the outcome; never starts at "a participant"; shortest option passed over 23 times (3 words or fewer) |
| 2 | wording written from the spec; Sonnet and Haiku; second blind round (90 bullets) | length is model-dependent: "5 words" gives 8 on Haiku but 5 on Sonnet (27 of 91 at four words or fewer); owner kept own pick 60 of 90, and of 30 changes 22 got shorter ("not ruthless enough the first time") and 8 longer ("too short and you are meaningless") |
| 3 | give the replay the card's claim and ask it to skip what the claim says | no gain (both ends match 27 against 33 for the control): it moved the highlight to a different part of the bullet instead of trimming the same part |
| 4 | the ink budget: shorter wording, then at most two highlighted bullets per card | below |

Owner's note on round 2: whether a tail such as "until postcode entry" matters depends on
what the reader already knows, so it cannot be a rule; the prompt says to keep it when it
gives the why or where and the claim does not.

## 3. Round 4: how much colour (Sonnet 4.6, 39 cards)

| variant | bullets highlighted | per card | words median | share of a card's text coloured (median / worst) | whole page | coloured words per card | both ends = owner's final pick |
|---|---|---|---|---|---|---|---|
| today | 91 | 2.3 | 12 | 45% / 85% | 46% | 27 | 15 of 91 |
| `mid` (6 to 9 words) | 91 | 2.3 | 9 | 36% / 54% | 37% | 22 | 34 of 91 |
| `len57` (5 to 7 words, floor) | 91 | 2.3 | 8 | 33% / 51% | 33% | 20 | 33 of 91 |
| `budget` (`len57` + two per card) | 67 | 1.7 | 8 | 27% / 41% | 24% | 14 | 25 of 67 |

- Shortening alone takes the page from 46% to 33%. The budget takes it to 24%.
- The owner's own final picks, on every bullet, would still colour 29% of the page.
- `budget` left 24 bullets uncoloured and **broke its own cap on 1 card of 39** (3 on a card
  of 4), so a server-side backstop (keep the first two fragments per signal) is cheap
  insurance. Not in the diff.
- Which bullets `budget` chose is a judgement against the card's claim; on the cards I read
  the choices were plausible, but it left uncoloured at least one bullet I would have
  coloured (the strongest single example on its card). Judge with `data/viewer-cards.html`
  (today, shorter, and shorter plus budget, side by side, whole cards).

"Matches the owner's pick" is a harsh yardstick: two good highlights can differ by a word.
Haiku with a nominal 5-word cap matches best (46 of 91) because it overshoots to the picked
length; no Sonnet wording does.

## 4. The recommended edit

`recommended-prompt.diff` (prompt 0.5.0 to 0.6.0, plus two description edits in
`structured.py`; no new field). In short:

1. **Colour is a budget:** at most two assertions per signal carry a fragment, chosen by how
   directly they show the claim; `null` on the rest (the assertion stays).
2. The fragment is a pointer: the shortest span that is a small self-contained claim about
   the product.
3. **Length** 5 to 7 words, never more than 10, normally no more than a quarter of the
   assertion; below 5 only when the short span stands alone; never so short it points at nothing.
4. **Start** where the product's behaviour begins (not "a participant", not a reporting
   verb); **end** before the outcome or reaction; keep a trailing "until ..." only when the
   claim does not already say it; a feeling word alone is never the fragment.
5. Characters must really be in the assertion's text.
6. Drops "keep the verb/relation needed to make the fragment intelligible" and the sentence
   that every assertion should carry a fragment, and shortens the third example.

Per `bristlenose/llm/CLAUDE.md`, adopting it is a minor bump: archive 0.5.0 to
`bristlenose/llm/prompts-archive/` first.

## 5. Not done, and open questions

1. **Joint generation is untested.** Everything here holds the bullet fixed. The production
   model writes the bullet and the highlight in one reply, and the rules may change the
   bullet. One paid run on a project (3 or 4 cards, Sonnet, about £0.30) judged in the card
   viewer is the check to run before adopting.
2. **The budget needs eyes.** Is it right that two of three or four bullets go uncoloured? Is
   "most directly shows the claim" the right choice rule? (`viewer-cards.html`)
3. **A backstop in the server?** Cap fragments per signal at two, and optionally drop any
   fragment over about half its assertion. Deterministic, and it makes the prompt's budget a
   hope, not a guarantee, only where the model ignores it (1 card in 39 here).
4. **Existing cards keep their long highlights.** The elaboration cache is keyed on the quote
   texts, tags and references, not the prompt version, so a new prompt only affects cards
   that are regenerated. Decide whether to invalidate on adoption.
5. **A separate small highlight step** (Haiku, after the bullet) matched the owner best of
   anything tried. It costs one extra cheap call per card. Not built; the owner decided to stop
   at this point.
6. **How strong the colour looks** (CSS, intensity) is the third lever on the page's ink and
   was out of scope.
7. **Where the click lands.** The highlight must locate in the bullet text (the product's
   rule), and the click then reveals the source quote by `source_quote_id`. Kept as is.
8. One reader scored quality in round 1 (the same model family as the answers); the owner's
   picks are the real signal.

## Cost

822 model calls, **$3.45 (about £2.76)** in total, from the call log
(`data/run/.bristlenose/llm-calls.jsonl`): Haiku 549 calls $1.34, Sonnet 4.6 273 calls $2.11.
My running estimates ran low throughout, and I passed the £1 line (the policy for a paid
proof) without stopping to ask in round 2.
