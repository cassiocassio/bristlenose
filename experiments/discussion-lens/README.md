# Discussion lens — Phase 1a spike

The serious spike that `docs/design-discussion-lens-plan.md` §7 puts before any
change under `bristlenose/`. It builds the four-step design for real, outside the
package, and measures it against an answer key. Nothing here is imported by the
product; it reuses `LLMClient` and `wrap_untrusted` only.

| File | What |
|---|---|
| `synthetic/make_corpus.py` | Writes an invented study — a guide, three sessions, and `gold.json`, the answer key — from one script, so transcripts and labels cannot drift. No participant data. |
| `prompts/` | The four spike prompts: parse the guide, classify one session's turns, consolidate the unplanned residue across sessions, route quotes to sections. |
| `structure.py` | The deterministic half: labels → sections, the promotion rule, ordering, flow placement, the conversational anchor, the route decision. Pure functions. |
| `test_structure.py` | One test per rule (17); three were proved to fail when their rule is broken. |
| `spike.py` | Runs the four steps and writes one JSON per run in the **lens data contract** (`version: 1`) — the shape the SPA lens reads. |
| `score.py` | Scores runs against the key and against each other; checks the Phase 1a exit criteria. |
| `replay_consolidate.py` | Re-runs only the consolidate step on saved labels — isolates its variance at a cent a call. |
| `runs/` | The measured runs (synthetic data only) and their scores. `runs/synthetic/run-1.json` is the UI fixture. |

```bash
.venv/bin/python -m pytest experiments/discussion-lens/test_structure.py -q
python3 experiments/discussion-lens/synthetic/make_corpus.py
.venv/bin/python experiments/discussion-lens/spike.py --corpus experiments/discussion-lens/synthetic --runs 3 --out experiments/discussion-lens/runs/synthetic
.venv/bin/python experiments/discussion-lens/score.py --gold experiments/discussion-lens/synthetic/gold.json experiments/discussion-lens/runs/synthetic/run-*.json
```

## The four steps

1. **Parse** the guide into a frozen spine — sections and planned items, ids
   assigned by code in guide order. Once per guide; later runs reuse it.
2. **Classify** each session's moderator turns against the spine, one call per
   session: planned item *N* / ad-lib in section *X* / new topic / instruction /
   chat. Then **consolidate** the unplanned residue across sessions in one small
   call: which unplanned questions are the same question, and one name per new
   topic.
3. **Structure**, in code: invalid ids counted and degraded; a new topic becomes
   a section only if it **recurs — ≥2 sessions and ≥3 asks**; new sections
   ordered by median relative time among the planned ones; a tangent placed by
   flow (or standalone on a split vote).
4. **Route** each quote two ways — the **anchor** (the last question asked before
   it in its session, within 240 s; code) and the **topic** (one batched call) —
   and combine them (`decide_route`).

## What the synthetic corpus plants

A weekly-food-shop study: 51 moderator turns (27 planned, 12 unplanned, 12 not
questions), 38 quotes. A planned item nobody asks (`g2.3`); session 2 run out of
guide order; ad-libs on topic; **budget** — a new line of enquiry in all three
sessions (must be promoted); **recipes** — a three-question tangent in one session
(must not be); chit-chat, consent, logistics; and one answer that drifts to budget
right after an app question (anchor and topic disagree on purpose).

## Results — 3 Oct 2026, Claude Sonnet 4.6

Final prompts, three runs, guide parsed once (`runs/synthetic/score.txt`):

| | run 1 | run 2 | run 3 |
|---|---|---|---|
| turn kind (planned / unplanned / not a question) | 1.00 | 1.00 | 0.98 |
| planned item matched | 1.00 | 1.00 | 1.00 |
| unplanned share (gold 30.8%) | 30.8% | 30.8% | 28.2% |
| never-asked item kept as planned | 1/1 | 1/1 | 0/1 |
| budget promoted, recipes not | ✓ | ✓ | ✓ |
| turn → section, pairwise F1 | 1.00 | 1.00 | 1.00 |
| same question merged across sessions, pairwise F1 | 1.00 | 1.00 | 1.00 |
| quote → section, final | 0.94 | 0.94 | 0.94 |
| quote → section, anchor only | 0.97 | 0.97 | 0.97 |
| quote → section, topic only | 0.94 | 0.94 | 0.94 |
| cost | $0.12 | $0.10 | $0.10 |

Between runs: section agreement 0.957–1.000, one section signature in all three.
**All four Phase 1a exit criteria pass on synthetic data.** About $0.11 a run for
three ~7-minute sessions (7 calls, ~13k tokens in, ~5k out).

### What the measurements changed

- **The promotion rule counts asks, not distinct questions.** Counting distinct
  questions made promotion hostage to how finely the model merges them: the same
  budget topic came back as 4, 2, and 2 + 2 items, and was promoted in one run of
  three. How often a topic was *asked* is a fact of the transcripts.
- **Consolidation is told the planned sections' titles, for scale.** Without
  them it split "budget" from "rising prices" in some runs and merged them in
  others. Replaying that one step on fixed labels: budget as exactly one
  section in 9 of 9 with the hint, against 1 of 3 full runs before.
- **Topics before items** in the consolidate schema, so the model settles the
  lines of enquiry first.

These three were tuned against this corpus, so its scores flatter them. The
gold-labelled real sessions are the honest test.

### What is still wrong

- **The topic override costs more than it saves.** Anchor alone: 0.97; anchor
  with a confident topic overriding it: 0.94. On this corpus the conversation's
  position is the better signal. Before Phase 2, either raise the threshold or
  make the anchor decisive, and keep the topic as corroboration only — measure
  on the real sessions, not here.
- **One consistent semantic slip.** "Do you ever share recipes with your
  flatmate?" was matched to the planned "Who else has a say in what gets
  bought?" in one run of the final three (all three before the last change), so
  the never-asked item read as asked.
- **No-guide mode builds a different, coherent structure** — five emergent
  sections (About you, Delivery issues, Shopping habits, Budget & spend, App &
  ordering), quote agreement 0.71 against the *guide's* sections. The key has no
  right answer without a guide; scoring this mode needs its own labels.

### What this does not show

Synthetic transcripts are clean: one moderator, one participant, no
mis-attribution, no crosstalk, ~7-minute sessions. Real sessions measured in
July and October gave 60% unplanned questions and an anchor that agreed with
the topic on 69 of 101 quotes. **The exit criteria have to be met on the
gold-labelled real sessions before Phase 2** — that needs the labelling pass on
the workbook.

Paid spend for the whole spike, including tuning: about $1.26 (≈ £0.97), 45 calls.
