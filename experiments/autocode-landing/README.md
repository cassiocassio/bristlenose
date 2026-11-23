# AutoCode landing lab

A replay of a real AutoCode run in which tags land on the quotes, the tag sidebar, the codebook page and the confidence histogram while you watch, with every setting of the proposal as a handle. It exists to judge the feel of live landing before anything is planned or built (owner, 23 Nov 2026). The status-line wording for each moment is a separate, design-system-accurate page: `docs/mockups/autocode-progress-states.html`.

```bash
.venv/bin/python experiments/autocode-landing/lab.py
open experiments/autocode-landing/landing-lab.html
```

## Files

| File | What it is |
|---|---|
| `lab.py` | Reads a study's quotes and one AutoCode job's proposals (confidence, tag, group colour), and every answered AutoCode call time in the private trial runs' `llm-calls.jsonl` logs; inlines the shipped tokens, type, badge, shimmer and activity-chip CSS |
| `template.html` | The lab: simulation, playback queue, pacing controllers, display rules |
| `landing-lab.html` | The generated page |

## Data

- **Proposals:** one private trial run of the Talismanic recordings, 112 quotes and 109 UXR proposals. All three of its sessions match the public Talismanic quotes (checked 23 Nov 2026), so its quotes may appear in tracked files. Participant codes only; no names or file names are read. **Any other study carries real participants: pass `-o` to a private folder.**
- **Call times:** 52 answered AutoCode calls, median 29.8 s, 1 in 10 at 50 s or more. Nine logged calls with no output tokens are refusals of under a second and are left out; with them the median read 28 s.

## What is measured and what is assumed

- **Measured:** the call times, the batch size of 25, three calls at once (`llm_concurrency`), and the quote order the job sends today (stored order, roughly session by session).
- **Assumed:** how call time scales with batch size (the "share" handle, default 75%). The logs hint that it follows reply length: about 350 output tokens took 8 to 25 s, and about 2,400 took 28 to 54 s. One paired run settles it.
- **Assumed:** that shuffling the quotes leaves the confidence scores unchanged. Also one paired run.
- **Biased low:** the replayed call times include calls from smaller batches (catch-up passes), so "replay logged calls" gives a full batch of 25 a shorter call than it would really take. "Median + slow tail" at 30 / 50 s is the fairer setting for a full batch.
- **Not modelled:** the real Mac app's web view (whether it keeps your scroll position while content is added above you), throttling in a hidden window, two codebooks running at once.

## Presets

- **Today: everything at the end.** Proposals are saved when the whole job finishes, and everything lands in one burst.
- **The brief: per batch, predicted pace.** Batches of 25, with the pace set to empty the queue as the next batch is due.
- **Small first batch, pace by queue.** Batches of 5, 10, then 25, quotes shuffled, pace set by queue size with gradual changes, still dashed tentative tags, grow-only scales.

## Reading the timeline

The top lanes are the server: one bar per batch, one lane per concurrent call. The tick row is the screen: one tick per tag as it lands (green accepted, amber tentative, grey excluded, red a tag that changed class). The purple line is the queue and the green line the pace. The stats beside it give the time to the first tag, the server's and the screen's finish, and the longest stretch with nothing landing.
