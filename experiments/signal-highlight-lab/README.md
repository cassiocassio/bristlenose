# Signal highlight lab

Owner feedback, 30 Oct 2026: on a Signals card each evidence bullet colours a span of
its text, and the span is far too long. The colour should be a pointer to the evidence,
not a block of ink. This lab measures how long the spans are, replays Step 6 of
`signal-elaboration.md` under different wordings, and recommends an edit.

**Status: experiment only.** Nothing here changes the shipped prompt, schema, frontend or
CSS. The recommended edit is `recommended-prompt.diff`, which applies cleanly to `main`
(`git apply --check -p1`) and has not been applied. The owner decides.

## Files

| file | what |
|---|---|
| `extract.py` | reads stored assertions read-only (no LLM call), writes `data/assertions.json`, prints the baseline |
| `lab.py` | `plan` (cost estimate), `run` (paid replay), `report` (table and `data/viewer.html`) |
| `recommended-prompt.diff` | proposed edit to `signal-elaboration.md` and `structured.py`, not applied |
| `data/` | **gitignored**: assertions, model answers, the side-by-side viewer, the worst-ten list, the call log. These hold participants' words, so they stay off the public repo |

Open `data/viewer.html` to see old and new highlights side by side, with coverage per bullet.

## Data

The owner's Beauty-function card is not in `trial-runs/project-ikea`: it is in the
"ikea research videos" study under `~/Documents`. The pool therefore reads four project
databases on this Mac, read-only (`mode=ro`): `trial-runs/project-ikea`, the "ikea research
videos" study and two copies of the Talismanic study. Each Signals snapshot keeps the
wording of its time, so for each card and quote the **latest** snapshot's bullet is used.
Older snapshots and cache rows pre-date highlights in most Talismanic cards, so only
bullets that carry a stored highlight are replayed: **91 bullets on 39 cards**
(project-ikea 18, ikea videos 36, Talismanic 36, one more). Median bullet length: 26 words.

## 1. Baseline (what ships today)

Highlight share of the bullet, over the 91 bullets that have one:

| | median | p90 | max | over 50% | over 25% |
|---|---|---|---|---|---|
| by words | 45% | 68% | 95% | **35 of 91 (38%)** | 82 of 91 |
| by characters | 44% | 72% | 97% | 30 of 91 | |

The median highlight is 12 words. By study: project-ikea median 66% (13 of 18 over half),
ikea videos 45% (14 of 36), Talismanic 39% (8 of 36). The two bullets the owner called out
measure 58% and 63% by words in the stored data. The worst ten are in `data/worst.md`
(the top three highlight 92 to 95% of the bullet: the whole sentence bar the article).

The longest highlights share one shape: they are a **whole clause** (subject, verb,
object, and often the outcome) because the current prompt asks for "one contiguous,
intelligible causal unit" and says to "keep the verb/relation needed to make the fragment
intelligible". Its own second example is eight words.

## 2. Variants

Replay of Step 6 only. The **bullet text is held fixed**; the model (Claude Haiku 4.5,
the cheapest adequate) is shown the card's quotes and bullets and returns only the
highlight, as text. Offsets are withheld so every answer goes through the product's own
`_validated_fragment` (located by its text, unique match, rationale check). Null is always
allowed.

| variant | wording |
|---|---|
| `stored` | what the real run produced (not a replay) |
| `none` | control: no highlight at all |
| `current` | today's Step 6 rule, replayed (checks the replay is faithful) |
| `cap6` | hard cap: at most 6 words |
| `phrase25` | one noun phrase or verb phrase, never a clause; at most 25% of the words and 8 words |
| `distinct` | prefer the distinctive words, 2 to 5 of them, no reporting verbs |
| `twostep` | pick the shortest quote fragment first (a scratch field), then the bullet span that says the same |
| `combined` | two-step, 5-word cap, 25%, distinctive words, no subject or outcome |
| `tight` | two-step, 5-word cap, 25%, **and** "the highlight must be characters really in the bullet, never words from the quote", plus three invented worked examples |
| `tight1` | `tight` without the scratch step (needs no schema change) |

## 3. Results

Share of the bullet by words, over highlights that located:

| variant | n | highlighted | null | unlocatable | frag words (median) | share by words: median / p90 / max | over 50% | over 25% | chars median |
|---|---|---|---|---|---|---|---|---|---|
| stored | 91 | 91 | 0 | 0 | 12 | 45% / 68% / 95% | 35 | 82 | 44% |
| none | 91 | 0 | 91 | 0 | 0 | 0% / nan% / 0% | 0 | 0 | 0% |
| current | 91 | 82 | 1 | 8 | 11 | 42% / 74% / 94% | 29 | 74 | 42% |
| cap6 | 91 | 80 | 0 | 11 | 7 | 27% / 45% / 64% | 4 | 50 | 28% |
| phrase25 | 91 | 89 | 1 | 1 | 8 | 31% / 52% / 86% | 11 | 63 | 31% |
| distinct | 91 | 82 | 1 | 8 | 8 | 30% / 52% / 86% | 9 | 53 | 30% |
| twostep | 91 | 90 | 0 | 1 | 7 | 28% / 48% / 100% | 6 | 54 | 28% |
| combined | 91 | 86 | 1 | 4 | 5 | 20% / 33% / 48% | 0 | 27 | 21% |
| tight | 91 | 91 | 0 | 0 | 6 | 25% / 37% / 61% | 3 | 42 | 24% |
| tight1 | 91 | 88 | 1 | 2 | 8 | 31% / 45% / 86% | 6 | 65 | 31% |

"unlocatable" means the model returned text that is not a unique substring of the bullet;
the product would drop that highlight (and keep the bullet), so it counts as lost.

**What the numbers say**

- The replay is faithful: `current` gives a 42% median against 45% stored.
- Every shortening wording works on length. A hard word cap (`cap6`) alone cuts the
  median to 27% and over-half cases from 29 to 4, but 11 of 91 answers do not locate.
- **Why they do not locate:** told to be short, the model reaches for the participant's own
  words ("that's clever", "quite confusing"). The bullet is a paraphrase, so those words are
  not in it, and the product validates against the bullet, not the quote. Naming this in the
  rule and showing three examples (`tight`) takes unlocatable from 11 to **0**.
- **The scratch step earns its place.** `tight` (25% median, 3 over half) against `tight1`,
  the same rules without it (31%, 6 over half, median 8 words despite a "5 words" rule).
  A model asked to cap length without first picking the evidence ignores the cap.
- `combined` is the shortest (20% median, nothing over 48%) but it chooses the wrong part
  more often (below).
- `none` is the zero-ink control. A null answer was rare (0 to 1 of 91 per variant), so the
  prompt is not producing "no highlight" where one would be better; see open question 4.

**Quality, by reading.** I read 23 bullets (every fourth in the pool, not picked) with their
quotes and scored each highlight 2 (names the evidence), 1 (partly, or the context rather
than the cause) or 0 (misses it or fails to locate). One reader, the same family of model as
the one that wrote the answers, so treat it as a sanity check, not a measurement.

| variant | score of 46 | where it loses |
|---|---|---|
| `combined` | 35 | picks the feeling or the participant's reaction over the product ("surprised a participant positively", "questioning the terminology"), loses the referent ("unable to change it"), one unlocatable |
| `tight` | **42** | partial on 4 bullets (a fragment that names half of a two-part claim) |

The stored highlights I did not score; they carry the claim, and their problem is length
alone. All the shorter variants keep the verb where it matters ("withheld delivery cost and
timing", "could not find king size"), and drop the subject, the outcome and the reporting
verb, which is the ink the owner objected to.

Where `tight` is still long (7 bullets over 40%) the bullet is itself short or the cause
fills it. Examples are in `data/worst.md`.

## 4. Recommended edit

`recommended-prompt.diff` (prompt `0.5.0` to `0.6.0`, plus two field descriptions and one
optional field in `structured.py`). In short:

1. The fragment is "a pointer, not a summary": the shortest phrase naming the mechanism.
2. At most 5 words and at most a quarter of the assertion; one noun phrase or one verb
   phrase, never a clause; leave out the subject, reporting verbs, connecting words and the
   outcome; keep a verb only when the noun phrase alone would not say what the product did.
3. It must be characters really in the assertion's `text`.
4. A scratch field `quote_fragment` (at most 5 words from the participant's quote), written
   before the fragment, never stored or shown.
5. The second example drops "until postcode entry" so the examples no longer teach eight
   words; the sentence "Keep the verb/relation needed to make the fragment intelligible"
   is removed, since it is what asks for clauses.

Per CLAUDE.md, adopt by archiving `signal-elaboration.md` 0.5.0 to
`bristlenose/llm/prompts-archive/` first (a minor bump).

## 5. Open questions for the owner

1. **Is a median of 6 words (25%) short enough?** `combined`-style wording gets 5 words and
   20% at a real loss in accuracy; a 4-word cap sits between. Say if you want it tighter.
2. **Schema change.** The recommendation adds an unstored optional `quote_fragment` to
   `SignalEvidenceAssertion`. Without it (`tight1`) the highlights are about a third longer
   and ignore the cap. The validator reads fields with `getattr`, so an extra field is
   harmless to it, but this is still a contract change you should approve.
3. **Not yet tested jointly.** The lab holds the bullet fixed. In production the model writes
   the bullet and the fragment in one reply, and a rule about the fragment may change the
   bullet. One paid end-to-end run on the production model (Sonnet, a few cards) is the
   proof I would want before adopting; I did not do it because you asked for a replay.
4. **A server-side backstop?** `_validated_fragment` could drop any highlight over 50% of the
   bullet words (3 of 91 under `tight`; 35 of 91 today). A bullet with no colour is a
   legitimate outcome. Not proposed in the diff; your call.
5. **Existing cards keep their long highlights.** The elaboration cache is keyed on the quote
   texts, tags and quote references (`compute_content_hash`), not on the prompt version, so a
   new prompt only affects cards that are regenerated. Decide whether to bust the cache.
6. **Where the click lands.** The brief said the fragment must "locate in the quote text".
   The product locates it in the **bullet** text, and the click then reveals the source
   quote by `source_quote_id`. I kept that. If you want the participant's own words
   highlighted, the bullet would have to quote them.

## Cost

432 Haiku calls in total over the whole lab (two baseline passes of 120 and 234 calls, as
the pool grew when I switched to the latest snapshot per quote, then the two later
variants): **$1.05, about £0.85**. My up-front estimate ($0.38 for the main pass) ran about
2.5 times low because I undercounted the quote text; the actual figure came in under the £1
line. Every call is logged by `LLMClient` to `data/run/.bristlenose/llm-calls.jsonl`. Re-running
`lab.py run` costs nothing for answers already stored (they are keyed by card and bullet text).
