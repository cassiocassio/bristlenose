# Discussion lens: classify-turns prompt 1.1.0 against 1.0.0 (27–28 Nov 2026)

Does the proposed `discussion-classify-turns` 1.1.0 (same definitions; `kind`
and `role` numbered apart, each with its allowed words on one line, one worked
example) stop small local models without a grammar writing `role`'s `core`
into `kind`, without moving Claude's labels for the worse?

Not shipped. The owner decides from a turn-by-turn comparison page kept in the
maintainer's private notes (it quotes real moderator turns).

## Method

- **Inputs, frozen once** (`build_inputs.py`): the stage's own turns (same
  loader as `analyze`, same moderator check, turn ids and askable-length
  filter as `stage.py` step 2a) and spine. Talismanic s2 comes out at 57
  askable turns, the session tonight's Gemma failure was measured on.
- **Arms** (`run_arm.py`): the stage's own `_classify` (system prompt,
  language steer, untrusted envelopes, `SessionLabelsOut`, the real client)
  with only the prompt FILE swapped (`prompts/v1.0.0` is byte-identical to the
  shipped file: same sha as Talismanic's telemetry). Every attempt's raw reply
  is recorded before validation, so a first-attempt failure the salvage hides
  is still counted. Sessions one at a time; a local arm waits while another
  `bristlenose analyze` or `ollama pull` runs (by binary path: a shell that
  only mentions the words, such as another session's `pgrep` heartbeat,
  matches `pgrep -f "bristlenose analyze"` forever).
- **Checks** (`check.py`): first-attempt validity; out-of-set values per
  field and the kind/role swaps by name; each turn once, no unknown ids;
  item/section ids that exist and fit `kind`; `terse` length (read from the
  raw reply, before the model's 30-character clip) and presence; cluster-name
  variants; attempts and salvage; agreement with Claude 1.0.0 per field
  (percent and Cohen's kappa over every turn sent, a missing label counted as
  a disagreement); kind against hand-labelled gold on the synthetic corpus;
  and a replay of the last reply through the product's own last resort, as
  is and with JSON nulls in the string fields read as `""`.
- **Noise floor**: Claude 1.0.0 run twice. A prompt's difference from the
  reference means something only beyond Claude's own run-to-run difference.

## Data

Only one real study on this Mac has a discussion guide (Talismanic).
"IKEA with uxfriends" and `speaker-split/p3-run` are the same recordings
diarised differently, so they are not further studies.

| Study | What | Sessions · turns |
|---|---|---|
| `talismanic` | real, its own guide, the owner moderating (public test data) | 3 · 134 |
| `talismanic-noguide` | the same turns without the guide (the measured failure's condition) | 3 · 134 |
| `fossda` | real, no guide, FOSSDA oral histories, several interviewers (public); sessions under 5 moderator turns dropped (diarisation folded the interviewer in) | 6 · 242 |
| `rockclimbing` | synthetic, no guide | 7 · 64 |
| `synthetic-gold` | synthetic, guide, hand-labelled gold (`experiments/discussion-lens/synthetic`) | 3 · 51 |

## Run

`EVAL_DIR` is a gitignored folder: it receives turn text and raw replies.

    .venv/bin/python experiments/discussion-prompt-eval/build_inputs.py EVAL_DIR
    .venv/bin/python experiments/discussion-prompt-eval/run_arm.py EVAL_DIR claude-v100 --prompt 1.0.0 --llm anthropic
    experiments/discussion-prompt-eval/run_local.sh EVAL_DIR      # the local arms, in turn
    .venv/bin/python experiments/discussion-prompt-eval/check.py EVAL_DIR

## Results (28 Nov 2026)

Arms: Claude Sonnet 4.6 on 1.0.0 (reference), 1.0.0 again (noise floor),
1.1.0 and 1.1.0b (the example in words, no braces; three studies); Gemma 4 E4B
on Ollama's MLX runner (no grammar: the 501 path) on 1.0.0, 1.1.0 and 1.1.0b,
with repeats of 1.0.0 and 1.1.0 on Talismanic; Qwen 3.5 4B on the MLX runner
(also no grammar) on 1.0.0 and 1.1.0, three studies. qwen3.5:9b was removed
from the Mac mid-night by another session and not re-pulled. Claude spend
$2.17.

**As written, 1.1.0 cannot run.** The worked example's braces raise
`KeyError` in `str.format`: 22 of 22 sessions failed before a call. Doubled
braces render as one (that is what was measured as 1.1.0), but
`test_no_double_braces` forbids them, so the shippable form is 1.1.0b.

**Gemma 4 E4B, the target.** Over every attempt, `kind = "core"` 157 under
1.0.0, 0 under 1.1.0, 1 under 1.1.0b; role words in `kind` overall 183 → 40.
Sessions lost 4 of 22 → 1 of 22. Talismanic s2 without the guide (the measured
failure) failed in all three 1.0.0 runs (32, 33, 33 bad kinds), in one of two
1.1.0 runs, and not in the one 1.1.0b run. Kind against the synthetic gold 72.5% →
82.4%. New under 1.1.0: `closing` in `kind` stays (37), a reverse swap
`role = "chat"` (16; none under 1.1.0b), and JSON nulls in `section_id` (88).
The one session 1.1.0 lost was lost to nulls; replayed with null read as `""`
it keeps 54 of 57 labels (1.0.0's lost sessions are real bad kinds, which the
coercion does not rescue). Under both prompts, with no guide, Gemma labels
most turns `planned`/`adlib` against items that do not exist and agrees with
Claude on kind for 6–31% of turns.

**Claude.** Both prompts mechanically clean (22/22 first replies valid,
nothing out of set). 1.0.0 against itself: kind 93–99.6%. 1.1.0 against
1.0.0 sits inside that except on Talismanic with its guide (kind 78%, κ 0.71)
and role on FOSSDA (90% against 96%) and Rockclimbing (86% against 94%): more
`instruction` (the tech set-up the definitions call `chat`) and more
`opening`. 1.1.0b: Talismanic kind 88%. Kind against gold 94.1% for 1.0.0,
1.1.0 and 1.1.0b (the 1.0.0 re-run 90.2%).

**Qwen 3.5 4B.** No drift under either prompt; every first reply valid.
Quality mixed at one run (Talismanic kind 51% → 58%, gold 71% → 65%).

**Also seen.** Gemma sometimes writes malformed JSON on a long reply
(`"item_id "",`, the colon dropped), under every prompt; Claude writes `terse`
over 24 characters on a quarter to a third of unplanned turns under both
prompts (the model's 30-character clip catches it).

Verdict: the owner's call (not shipped).
