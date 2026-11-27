# Ollama quality and speed against Claude — 27 Nov 2026

One study, one Mac, each local model against Claude, measured for the docs page
`bristlenose.app/docs/set-up-ollama.html` (card `w-ollama-docs`). Raw run folders
were kept in the session scratchpad and not committed. They are reproducible
from the method below.

## Machine and versions

| | |
|---|---|
| Mac | Apple M2 Max, 32 GB, macOS 27.0 |
| Bristlenose | 0.49.0, CLI from the main checkout (`b61ec183a` for the Claude run, `19b8117a8` for the later ones; no change to the analysis between them) |
| Ollama | Homebrew. 0.20.7 at the start; upgraded to **0.40.18** (current, released 24 Nov 2026) mid-session with the owner's agreement. Every local result below is on 0.40.18, except where it says 0.20.7 |
| Ollama service settings | The Homebrew service sets `OLLAMA_FLASH_ATTENTION=1` and `OLLAMA_KV_CACHE_TYPE=q8_0` (not Ollama's defaults; f16 KV would use more memory) |
| Claude | Sonnet 4.6, the CLI default |
| Llama 3.2 3B | `llama3.2:3b`, digest `a80c4f17acd5`, 2.02 GB, Q4_K_M. Same build as the registry today |
| Gemma 4 E4B | See "Gemma builds" below: today's Mac build cannot run Bristlenose at all, so quality was measured on the earlier GGUF build |

The Mac was not otherwise idle: other Claude sessions were working in the same
checkout, and a signed Xcode build ran 18:35–19:25 UTC, overlapping the second
half of the abandoned 3B run (its failures had started before that window).

## Study and method

- **Study:** Talismanic, three moderated sessions (18, 36 and 38 minutes; 3,137,
  4,611 and 5,507 words). It is the public test study used on the About page,
  with the participants' agreement. Participants are shown here by code only.
- **Input:** the existing transcripts (`transcripts-raw/s1–s3.txt` from a
  previous run), copied to a scratch folder per run, so no transcription was
  timed and no real project was touched.
- **Runs:** `bristlenose analyze transcripts-raw --llm claude`, and
  `--llm local` with `BRISTLENOSE_LOCAL_MODEL` set. Local runs one at a time,
  nothing else loaded in Ollama. Wall-clock from `/usr/bin/time`, per stage from
  the CLI's own lines, calls from `.bristlenose/llm-calls.jsonl`, context and
  load from `ollama ps` every 10–20 s and Ollama's server log.
- **16 GB Mac stand-in:** a second Ollama server on port 11435 with
  `OLLAMA_CONTEXT_LENGTH=4096` and the same flash-attention / KV settings.
  Ollama documents a 4k default below 24 GiB of GPU memory (32k from 24 GiB,
  256k from 48 GiB; docs.ollama.com/context-length). This Mac got 32768
  (`total_vram="25.0 GiB"` in the server log); a 16 GB Mac's Metal working set
  is about 11 GiB, so it gets 4096.
- **Verbatim check:** each quote's text (or `verbatim_excerpt` where the model
  filled it) is split on `...` and paragraph breaks, `[inserted words]` dropped,
  fillers the extraction prompt allows the model to remove (um, uh, like, you
  know, kind of…) stripped from both sides, then: **exact** = every fragment
  found in the transcript; **joined** = ≥90% of its 5-word runs found (turns
  joined across a moderator interjection); **altered** = 50–90%; **invented** =
  under 50%. Script: `compare.py` here (`python3 compare.py <runs-dir> claude gemma …`);
  `run-local.sh` is the sequential runner (its scratch path is hard-coded).
- **Cost:** the Claude run cost **$0.95** (the CLI's own figure from token
  counts; it estimated ~$0.26 beforehand). Local runs cost nothing.

## Results

| | Claude Sonnet 4.6 | Gemma 4 E4B (GGUF build) | Llama 3.2 3B, 3 sessions | Llama 3.2 3B, 1 session (s1, 18 min) |
|---|---|---|---|---|
| Finished | yes | yes | **no: abandoned after 89 min** (at concurrency 1: stopped unfinished at 81 min) | yes |
| Wall-clock | **5 min 10 s** | **37 min 19 s** | 89 min, then failed | 1 min 30 s |
| Topic segmentation | 10.7 s | 2 min 01 s | 30 min 01 s (one call timed out) | 15.8 s |
| Quote extraction | 3 min 28 s | 15 min 42 s | did not finish | 36.8 s |
| Sections + themes | 17.3 s | 3 min 19 s | — | 5.4 s |
| Questions-asked placement | 1 min 12 s | 16 min 15 s | — | 31.0 s |
| Quotes | 85 | 95 (92 distinct) | — | 15 (13 distinct) |
| Verbatim: exact / joined / altered / invented | 75 / 8 / 2 / 0 | 71 / 18 / 6 / 0 | — | 8 / 4 / 0 / 3 |
| Quotes with a sentiment | 54 | 71 | — | 4 |
| Sections (by screen) | 13 | 6 | — | 1 (14 of 15 quotes) |
| Themes | 8 (one "Uncategorised") | 6 (one "Uncategorised", one catch-all) | — | 1 ("Uncategorised") |
| LLM calls / failed or cancelled | 16 / 0 | 13 / 1 (a 570 s deadline, split and retried) | 23 / 15 | 6 / 0 |
| Largest prompt | 11,749 tokens | 10,484 tokens | 9,777 tokens | 7,279 tokens |
| Tokens in / out | 102,104 / 42,694 | 101,284 / 76,950 | — | 19,994 / 5,780 |

### Memory, as loaded (32k context, q8_0 KV)

| Model | File on disk | `ollama ps` | Resident (RSS of the runner) |
|---|---|---|---|
| Llama 3.2 3B | 2.0 GB | 4.3 GB (0.40.18); 5.6 GB (0.20.7) | — |
| Gemma 4 E4B, GGUF build | 9.6 GB | 1.2 GB (undercounts) | **4.7 GB** |
| Gemma 4 E4B, today's Mac build | 9.5 GB | 9.4 GB | not measured (no run possible) |

Gemma's GGUF file is large because of a per-layer embedding table that Ollama
memory-maps and reads sparsely (5.4 GB "CPU_Mapped" in the log), so its
working set is about half the file. With macOS, a browser and Bristlenose
itself, that fits a 16 GB Mac and leaves an 8 GB Mac very little room; an 8 GB
Mac also gets Ollama's 4k context (see below).

## What went wrong, with evidence

1. **Today's Gemma 4 E4B cannot run a Bristlenose analysis on a Mac with Homebrew's Ollama.** On
   Ollama 0.40.18, `ollama pull gemma4:e4b` on Apple silicon fetches an
   `nvfp4` build (digest `eb2177adf764`, 9.46 GB, needs Ollama ≥ 0.31.0) that
   runs on Ollama's **MLX** runner. That runner refuses structured output in
   every form: `/v1/chat/completions` with `response_format` `json_object` or
   `json_schema`, and native `/api/chat` with `format: "json"`, each return
   **501 "structured output is unavailable"**; a request with no format works.
   Bristlenose always asks for structured output and doesn't treat this 501 as a
   refusal, so the run ends in 8 s: `✗ Segmented 0 topic boundaries`,
   `⚠ structured output is unavailable`, `✗ Local (Ollama) had a server error.`
   Reproduced at 32k and 4k. **Cause (found by the ollama-catalog session,
   checked here): Homebrew's Ollama package.** Ollama's log at the first call:
   `Structured output is unavailable … xgrammar library not found at
   /opt/homebrew/Cellar/ollama/0.40.18/libexec/lib/ollama/mlx_metal_v3/libollama_xgrammar.dylib`
   (grammar.go:74); the file is absent from the keg. Ollama's official build
   ships it (open upstream report: Homebrew/homebrew-core#302645). So this
   holds for a Homebrew install; the official Ollama app from ollama.com,
   where the Mac app's Get Ollama… leads, was **not tested**. The CLI's
   first-run installer on macOS uses Homebrew. (The registry's non-Mac manifest for the same tag
   is a 6.58 GB Q4_K_M GGUF with a projector, which needs Ollama ≥ 0.30.9; on
   0.20.7 the pull fails with HTTP 412 "requires a newer version of Ollama".)
   Quality above was therefore measured on the earlier GGUF build of the same
   model still on this Mac (`gemma4:latest`, digest `c6eb396dbd59`, Q4_K_M,
   llama.cpp runner).
2. **At a 4k context the prompt is cut, silently.** Bristlenose doesn't set
   Ollama's context size. With `OLLAMA_CONTEXT_LENGTH=4096` the server logs
   `truncating input prompt limit=2051 prompt=6419 keep=5 new=2051` and returns
   200; every topic-segmentation call reported exactly 2,051 input tokens
   against 6,000–10,000 sent. What survives is the first 5 tokens and the last
   2,046: the instructions and schema (which come first) and most of the
   transcript are gone. Results of that run: see "4k run" below.
3. **Llama 3.2 3B on 0.40.18 runs away.** One topic-segmentation call generated
   about 21,000 tokens (cached prompt grew to 30,344) until the 30-minute client
   timeout; on 0.20.7 the same request returned 684 tokens in 34 s. Ollama's new
   llama-server runner logs `repeat_penalty = 1.000`; older Ollama defaulted to
   1.1 (a plausible cause, not tested). The local path sends `max_tokens`
   64,000, so nothing stops a loop sooner.
4. **Three sessions at once overrun the deadline.** Ollama answers one request
   at a time (`n_slots = 1`) and Bristlenose submits every session's extraction
   together; the 570 s pass deadline counts time spent queued. On both Ollama
   versions the 3B's queued sessions were cancelled at 570 s, split and retried,
   and on 0.40.18 the run stopped: `Stopping quote extraction early — 3
   consecutive failures`, then `run_abandoned … category=network` and
   **`✗ Couldn't reach Local (Ollama). Check your network connection.`** Ollama
   was reachable throughout; the failures were deadlines
   (`PassDeadlineError(TimeoutError)`, `bristlenose/stages/s09_quote_extraction.py:618`).
   Alone, one 18-minute session finished in 90 s. At concurrency 1
   (`BRISTLENOSE_LLM_CONCURRENCY=1`, all three sessions, no queueing) the
   3B **did not finish in 81 min** and was stopped at a set limit (21:45
   London): topic segmentation timed out at 30 min on two of three sessions
   (runaway replies again), s1's quotes came back in 115 s, and s2's
   extraction was cancelled twice at 570 s. So the queue makes it worse, but
   the runaways alone are enough to sink a full-length study.
5. **The 3B's output is not usable for analysis even when it finishes.** On the
   one session it finished on 0.20.7 (s2, 36 min), 29 of its 34 quotes were the
   same sentence ("I'm kind of interested both in the bed linen…") stamped at
   29 timecodes: 4 distinct quotes, no sentiment, no themes, 30 of 34 in one
   section. On s1 alone (0.40.18): every quote at 0:00, so transcript links
   don't land; the first "quote" is the moderator's recording preamble,
   attributed to the participant; one line ("I've got to spend 10 pounds. More
   than 15." plus a clause that isn't in the transcript) three times; one
   section, one theme ("Uncategorised").

## Reading the results as a researcher

**Claude** reads like a competent first pass. Themes a researcher would keep:
*Cherished objects with emotional heritage* (p2's inherited Alessi kettle, and the
identical one a spouse later gave them), *Form vs. function tension*, *Navigating
IKEA's forced store journey* (p3 enters through the exit "if I'm really on a
mission"), *IKEA as a family and life-stage ritual*. Thirteen sections track the
screens of the shopping task (configurator, bag, delivery, checkout). The two
altered quotes are joins across a moderator line.

**Gemma 4 E4B** finds about as many quotes, nearly all verbatim, covering the
same minutes of each session, with more sentiment tags than Claude. The
weakness is synthesis:
- themes are plausible but loosely fitted: the inherited kettle sits under
  *High-Value Customization & Expertise*, p1's family trip to IKEA under
  *Physical Shopping Journey & Overwhelm*, the air-fryer warm-up under
  *Appreciation for Timeless Design*;
- one theme is a catch-all (*General Context & Procedural Observations*);
- the heritage and family-ritual themes Claude found have no counterpart;
- six sections instead of thirteen: the configurator, the bag and the delivery
  steps are merged;
- one quote includes the moderator's question inside the participant's words
  (s2, 33:14: "What are the moments that have caused you trouble?");
- housekeeping kept as quotes (s3: "How do I unmute? … Can you hear me?",
  "Is it the bathroom free…");
- **four quotes placed under two themes each** (s3 at 11:52, 12:31, 13:09,
  14:20): 52 placements, 48 distinct quotes. That breaks Bristlenose's rule
  that a quote appears in exactly one section (Claude: 30 placements, 30
  distinct).

The verbatim check matches against the whole transcript, moderator turns
included, so "exact" means "found word for word", not "the participant's own
words": the 3B's moderator-preamble quote counts as exact.
Usable as a starting point if you expect to regroup the themes yourself;
seven times slower than Claude on this Mac.

**Llama 3.2 3B** confirms that local analysis runs, on one short session, and
nothing more: repeated quotes, broken timecodes, moderator words as a
participant's, one section, no real themes. On three real-length interviews on
current Ollama it did not finish.

## 4k run (16 GB Mac stand-in)

Gemma 4 E4B (GGUF build), `OLLAMA_CONTEXT_LENGTH=4096`, otherwise as the 32k
run. **Failed after 10 minutes: `✗ All quote extraction calls failed.`**

- Topic segmentation "succeeded" on the cut prompts: 13 boundaries (21 at
  32k), each call reporting exactly 2,051 input tokens, `outcome: ok`. Nothing
  told the user.
- Every quote-extraction call: 2,051 tokens in, 2,045 out, `finish_reason:
  length`: the reply filled what was left of the 4,096. Bristlenose split each
  session in halves and tried again; every half failed the same way; it
  stopped after three consecutive failures.
- The error text blames the wrong limit: `LLM response truncated at the model
  output cap (provider=local, model=gemma4:latest, max_tokens=64000)`. The cap
  was Ollama's context, not `max_tokens`.
- Ollama's server log: 15 `truncating input prompt limit=2051 …` warnings.

At 32k the same model on the same transcripts finished. Gemma's KV cache at
32k is 272 + 32 MiB (q8_0), so a 16 GB Mac can afford a larger context; the
fix for a user is `OLLAMA_CONTEXT_LENGTH` (or the Ollama app's context slider),
and for the product, sending `num_ctx` (not tested here).

## Product findings (not fixed in this card)

- `OllamaCatalog` (`desktop/Bristlenose/Bristlenose/LLMProvider.swift:363`) says
  Gemma 4 E4B is a 3 GB download; it is 9.5 GB on a Mac today (9.6 GB for the
  earlier build). The docs page said ~3 GB too.
- Structured output on Homebrew's Ollama with the MLX build (finding 1): the
  recommended model for 15–35 GB Macs fails at the first call; the CLI's
  macOS installer uses Homebrew. Official app untested.
- No `num_ctx`: prompts are truncated silently at 4k, which is Ollama's
  default on a 16 GB Mac; Gemma 4 E4B's analysis then fails at quote
  extraction (finding 2, "4k run"). The failure message names `max_tokens`
  64,000, not the context.
- `max_tokens` 64,000 on local calls lets a looping small model run until the
  timeout (finding 3).
- Pass deadline counts queue time against a one-slot server (finding 4).
- A deadline is reported to the user as "Check your network connection"
  (finding 4). Evidence, `llama/.bristlenose/bristlenose.log` and the CLI:
  `quote_extraction_pass_deadline | session=s2 | depth=3 | segments=77 |
  deadline_s=570`, then `Stopping quote extraction early — 3 consecutive
  failures`, `run_abandoned run_id=01M8F1WA7BXWHF2G1P8TADHZ82
  category=network`, and on screen `✗ Couldn't reach Local (Ollama).` /
  `Check your network connection.` (`bristlenose/cli.py:1296`).
- Quote exclusivity breaks with Gemma 4 E4B: four quotes in two themes each.
- The CLI's first-run offer downloads `llama3.2:3b` (`bristlenose/cli.py:769`)
  and the desktop's `ollamaNoModels` message tells Mac users to
  `ollama pull llama3.2:3b`: both steer new users to the model whose report is
  not usable.
- The CLI's pre-run estimate for Claude was ~$0.26; the run cost $0.95.
