# CLI Session Matching — Design Note

**Phase 2 of 2** — deferred until Phase 1 (the cli-ux codebook +
analysis register) has shipped and been validated against a real
cohort. Do not start on this before Phase 1 has produced reports
the audience finds useful; the session-matching layer is an
amplifier on a working codebook, and amplifying a codebook that
hasn't earned its keep is wasted effort. See
`docs/design-cli-analysis-register.md` for Phase 1.

**Status:** Idea capture, post-TestFlight.
**Companion to:** `bristlenose/server/codebook/cli-ux.yaml`.

## Problem

In research on command-line tools, what the participant *says* and what
the participant *does* are two streams of evidence, and the second is
unusually legible: every keystroke, every flag, every exit code is text.
Bristlenose today only ingests the first stream (speech via transcript).
A speech-only codebook can flag "the participant sounded confused"; it
can't see that the participant ran `man rsync` and then `rsync --help`
within thirty seconds and then gave up — which is a specific
documentation-discovery failure, not a generic confusion.

The bonus idea on the CLI-UX codebook branch is to close that gap:
ingest a terminal-session recording alongside the interview audio,
align them in time, and let codebook tags fire on observed behaviour
as well as on speech.

## The 90% research format

The dominant shape of CLI-tool research, today and in the foreseeable
future, is a remote video call:

- **Researcher** (or PM, or DX engineer) joins from their machine.
- **Participant** joins from theirs — a prospective user of the tool
  under study (Bristlenose, juju, a developer-tool, a CLI in beta).
- The call is over Teams, Meet, or Zoom. The researcher records the
  call from their side. Modern conferencing tools already produce the
  video, the audio, and often a live transcript.
- The participant runs the tool *on their own machine*, typically
  sharing their screen so the researcher can see the terminal.
- After the call the participant emails over an artifact of what they
  did at the prompt — sometimes a cut-and-paste of their terminal
  scrollback, sometimes (in the ideal world) an asciinema `.cast`.

So Bristlenose's input here is already what it ingests today (the call
recording) plus *one optional companion file per session*: either a
plain-text terminal log or a `.cast`. The researcher drops the
companion next to the audio/video in the project folder; nothing
needs to be installed on the participant's machine unless they
themselves want to send a `.cast`.

## Capture layers

| Layer | What it captures | Source |
|---|---|---|
| **Call recording** (video + audio) | Speech, faces, and — if the participant shared their screen — visual footage of the terminal and any browser tabs. | Researcher side, Teams / Meet / Zoom. Already standard. |
| **Call transcript** | Time-aligned speech text. | Conferencing tool's auto-transcript, or Bristlenose's own. |
| **asciinema `.cast`** (ideal-world companion) | Character-perfect typed commands, output, and per-event timing. | Participant emails after the call. |
| **Cut-and-paste terminal log** (common companion) | Character-perfect commands and output. No timing — just sequence. | Participant emails after the call. |

Most sessions will have call recording + transcript + paste log.
Sessions where the participant is technical enough to run `asciinema
rec` get the upgrade to timed events. Bristlenose accepts whichever
arrives and degrades gracefully when fields are missing.

### asciinema `.cast` format

[asciinema](https://asciinema.org) records terminal sessions to a
small JSON-lines file (v2):

```
{"version": 2, "width": 120, "height": 30, "timestamp": 1715420400, ...}
[0.012, "o", "$ "]
[1.348, "i", "g"]
...
[2.412, "o", "On branch main\r\nnothing to commit, working tree clean\r\n"]
```

A header object, then one JSON array per event: `[relative_seconds,
"o"|"i", payload]`. `"o"` is output written to the terminal, `"i"` is
input from the user (only present if recorded with `--stdin`).

### Cut-and-paste log

Plain text: the participant's terminal scrollback, copied into an
email or pasted into a chat. No timing, but character-perfect
commands and output — including prompts, exit indicators (if PS1
shows them), and anything the participant did at the keyboard.

Less rich than `.cast` but available from *every* participant by
default. The cost is one sentence at the end of the call: "Could you
paste your terminal session into an email and send it over?"

## Time alignment

The call recording has the researcher's clock; the participant's
`.cast` has the participant's clock; the cut-and-paste log has no
clock at all. We need a way to map the companion artifact onto the
call's timeline.

**Two-way anchor for `.cast`:**

At the start of the session, the participant runs `date`. The output
("Sun May 11 17:42:03 BST 2026") lands in the `.cast` stream stamped
at, say, t=8.4s into the recording. The participant says "running
date now" in the call — visible in the transcript at t=00:00:14 into
the call. Subtraction: cast t=0 corresponds to call t=00:00:05.6. One
ritual, fully sufficient. Works equally well for asciinema's relative
clock and any future timed format.

**For cut-and-paste:** no timing on the artifact itself, but the call
recording gives us *visual* timing if the participant shared their
screen. Each command in the paste log can be located in the screen
share by matching the prompt text (`$ git status` shows up at
t=00:04:22 in the screen video). This is fuzzy — relies on the
participant sharing the relevant terminal, OCR or careful eyeballing
to find each command — but every command is at least *ordered*, and
in practice the major moments are easy enough to spot.

A nicer-than-anchor design would have the call host run a brief
sync helper that emits "bristlenose-mark <epoch>" into the
participant's terminal at session start (a shell command they paste,
not anything we install on them). The unique string is trivially
greppable in both cast and paste log, and the timestamp is the
mapping. Worth doing if the bare `date` ritual turns out to be
fragile or easy to forget.

A nicer-than-pragmatic anchor would be to have a small companion tool
that emits a known phrase at recording start ("bristlenose-mark
17:42:03.291") — easy to grep in the cast and easy to find in the
transcript. Worth doing if the pragmatic version turns out to be
fragile.

## Ingestion shape

Not a new pipeline stage. A new optional companion file alongside the
call recording in the input folder. Two accepted shapes:

```
interviews/
  alex-2026-05-11.mp4              ← call recording (existing)
  alex-2026-05-11-people.yaml      ← existing
  alex-2026-05-11.cast             ← optional, ideal world
  alex-2026-05-11-terminal.txt     ← optional, common world
```

The pipeline detects whichever is present. Both feed into the same
internal event list — the `.cast` parser populates per-event timing,
the paste parser populates ordering only (and, where the call
recording's screen share allows, the time-alignment pass fills in
approximate timestamps by matching prompt text against the video).

Parsers live in `bristlenose/utils/`:

- `bristlenose/utils/asciinema.py` — `.cast` v2 reader.
- `bristlenose/utils/terminal_paste.py` — parses a free-form
  scrollback into `(prompt, command, output, exit_indicator)`
  tuples. Heuristic but tractable: most shells have a small set of
  prompt shapes (`$ `, `❯ `, `% `, `# `, `[user@host dir]$ `).

Both emit the same typed record:

```python
class CliEvent(BaseModel):
    call_seconds: float | None      # interview-clock seconds, post-alignment.
                                    # None if only paste log is available and
                                    # the screen-share alignment pass couldn't
                                    # find a match.
    sequence: int                    # always present — monotonic index
    kind: Literal["command", "output", "input"]
    command: str | None = None       # parsed command line (for "command")
    exit_code: int | None = None     # if known (PS1 hook, or visible in paste)
    stdout_excerpt: str | None = None
    source: Literal["cast", "paste"] # which artifact this came from
```

Command parsing reuses `shlex` for tokenisation. Exit codes come from
a PS1 hook (`PROMPT_COMMAND='__bn_exit=$?'`) when the cast is
generated with one, or from a visible exit indicator in the paste
log otherwise — most commonly absent, in which case the field is
omitted. The Pydantic model degrades gracefully when fields are
missing.

## Surfacing in the UI

What would a researcher actually expect when they open a session that
has a terminal companion? Three patterns are worth considering, and
the right answer is probably "all three at different zoom levels"
rather than one of them.

**1. Inline in the transcript — the default.** This is the natural
home for terminal events because Bristlenose's primary session
surface is already the transcript, time-axed. A command turn looks
like a speech turn but visually distinct: monospace block, prompt
glyph at the left margin, command line, optional output excerpt
under a fold. Speech and commands interleave in chronological order:

```
00:04:18  alex   So I'll just check what's there…
00:04:22  $      ls -la interviews/
                 total 16
                 drwxr-xr-x  4 alex  staff   128  6 May 17:42 .
                 […]
00:04:31  alex   OK so I can see the project folder.
```

For cast-sourced events, the timestamp is precise. For paste-sourced
events, the timestamp is the position-matched approximation (the
event is anchored to the nearest transcript turn, not to a precise
second), shown without the colon — `00:04:~` or similar — so the
researcher knows it's a soft alignment.

**2. Timeline strip beneath the player — the orientation layer.**
A thin horizontal strip below the existing player showing command
markers, colour-coded by inferred friction (`man-page-friction`,
`error-message-illegible`, etc.). Hover for the command; click to
jump the player. This is for "where in this session did things
happen?" — useful before the researcher decides where to dig in.

**3. Side-by-side research view — the deep-dive opt-in.** A toggle on
the session detail page that splits the pane: call video left,
terminal artifact right (paste log rendered as text, cast rendered
with asciinema's player). Scrubbing the video advances the marker in
the terminal pane. This is for the researcher who specifically wants
to study the command stream in detail — not the default, but
expected for a power user analysing a developer-tool study.

A **full-screen toggle** between video and terminal (one or the
other, nothing else visible) is the wrong frame for Bristlenose,
which is transcript-first. The researcher's mental anchor is "what
did the participant say at this moment, and what were they doing?"
— that wants the streams visible *together*, not as alternatives.

**Recommendation, in order of build effort:** transcript inlining
(1) first — it's the cheapest and reuses the existing time axis;
the timeline strip (2) second; the side-by-side research view (3)
last and only if researcher feedback says they want it. Each tier
adds zero coupling to the next.

## Behavioural tag inference

This is where the codebook earns its keep. With a stream of `(time,
command, exit_code)` triples, codebook tags can fire on pattern matches
across the trace, separate from LLM-driven speech tagging.

Rules fall into three precision tiers based on what's needed:

| Pattern | Needs | Tag |
|---|---|---|
| `man X` then `X --help` (any order within session) | paste | `man-page-friction` |
| `sudo …` followed by the same command without `sudo` | paste | `sudo-hesitation` |
| `--dry-run` followed by same command without `--dry-run` | paste | `dry-run-usage` |
| `kubectl config use-context` mid-session | paste | `prod-vs-sandbox-confusion` |
| `curl ... \| sh` present in scrollback | paste | `script-from-internet-risk` |
| Three consecutive `<up-arrow>` then `Enter` | cast | `history-reuse` |
| `man X` then `X --help` within 60s | cast | `man-page-friction` (tightened) |
| Non-zero exit code followed by ≥10s pause | cast | `error-message-illegible` candidate |
| Speech "let me check the docs" + next command pasted from outside | transcript + paste | `copy-paste-from-docs` |
| Speech mentions an error message verbatim followed by a different command shape | transcript + paste | `error-message-illegible` (confirmed) |
| Speech "I'll just google that" + subsequent shape-shift in commands | transcript + paste | `search-engine-fallback` |
| Speech "let me ask Claude/ChatGPT" + subsequent shape-shift | transcript + paste | `llm-as-docs` |

The paste-only rules fire on every session that emails a scrollback —
which is the realistic floor. The cast-only rules add temporal
precision when the participant runs asciinema. The transcript-paired
rules exploit the strongest signal we already have today (the spoken
transcript) and let it interpret the new evidence (the commands)
without needing per-command timing.

This last tier is the unlock. Bristlenose already has the transcript
with timecodes. Matching "I'll just google that" at 04:32 to the
command shape change visible in the paste log at the corresponding
position in the session gives most of the value of full alignment for
none of the alignment cost. The `.cast` upgrade is gravy.

Inference is rule-based, not LLM-mediated — cheap, transparent,
auditable. The rules live in `bristlenose/stages/cli_inference.py`
(future) and each one is a small `BaseInferenceRule` subclass with a
`match(events) -> list[InferredTag]`.

When a tag is inferred from the trace rather than the speech, the
provenance is recorded (alongside the existing `QuoteTag.source` of
`"human"` / `"autocode"` — add `"trace"` as a third value). The UI
shows the source on hover.

## Privacy

The terminal artifact — `.cast` or paste log — is at least as
sensitive as the transcript. It can contain:

- API keys pasted into env vars
- Passwords typed (or pasted) into prompts
- File paths revealing project structure
- Customer identifiers in queries
- Internal hostnames and URLs

### Primary control: the research protocol

Bristlenose's users are professional researchers, not random people.
The expected control here is the same one used in research on
clinical records systems, banking systems, government tooling, and
anything else with serious data-sensitivity baseline: the participant
works in a disposable environment with throwaway credentials, set up
by the researcher before the session.

The recommended protocol:

- Spin up a disposable VM, devcontainer, or cloud sandbox for the
  session.
- Provision API keys / tokens that have read-only or strictly-scoped
  permissions, and that the researcher revokes immediately after the
  call ends.
- Use a fresh, empty test-data set rather than the participant's
  real working environment.
- The participant performs the study in that environment; the
  artifact emailed afterwards is from there, not from their daily
  driver.

This is a normal part of the job for researchers in regulated
domains. Bristlenose should *document* this protocol prominently
(researcher onboarding, study-setup checklist, a short "how to
prepare for a CLI-tool session" page) the same way ethics-board-
aware tools document IRB-compatible workflows. The right primary
defence is procedural, not algorithmic.

### Secondary control: redaction as defence-in-depth

The PII-removal stage (`bristlenose/stages/s07_pii_removal.py`)
extends to terminal events as a backstop — for the day when a
researcher forgets, a participant goes off-script, or a test
environment turns out to have less isolation than assumed.

Two categories worth implementing:

- **Token-shaped strings** — `AKIA...`, `ghp_...`, `sk-...`, JWT
  triples, hex strings of high entropy. Conservative regex matching;
  redact aggressively.
- **Prompt-following plaintext** — anything typed in the line
  immediately after a known password prompt (`Password:`, `Enter
  passphrase:`, `2FA code:`).

Both have known false-positive and false-negative surfaces (token
regexes confuse git SHAs and UUIDs; prompt strings vary by tool and
locale). A short spike on a real-looking corpus is worth doing
before we lean on them — measure precision/recall, tune — but the
urgency is lower than it would be if redaction were the primary
control. If the spike shows both layers work reasonably well, ship
them as belt-and-braces. If they don't, the protocol is still
sound.

Redaction happens before the events touch the database. The original
artifact is treated like the original audio — never copied into the
shareable output root; lives in `.bristlenose/`.

Additional consideration for the emailed paste log: it has arrived in
the researcher's inbox as a plain-text email body. Researchers should
be reminded — as part of the same protocol page — that the email
itself is now a copy of session material and should be handled
accordingly (delete after import; don't forward; don't archive into
shared mail).

## Open questions

1. **Getting the artifact in the first place — graceful degradation.**
   When the participant ends the call and forgets to email anything,
   the session falls back to call-recording-only — i.e. exactly what
   Bristlenose handles today. Nothing breaks, no feature regresses;
   the session just doesn't get the command-stream enrichment. So
   the missing-artifact case is *fine*. A friction-killer is still
   worth having (a templated end-of-call ask, or a `mailto:` link
   the researcher posts in chat at wrap-up), but it's an
   optimisation, not a load-bearing piece.
2. **Paste-log parser robustness.** Scrollbacks are messy — wrapped
   long lines, ANSI colour escapes, mixed prompts, control
   characters from arrow-key edits, line continuations. The
   parser will need a robust tolerance pass and a "we couldn't
   confidently parse this" fallback that still lets the researcher
   read it inline.
3. **Researcher friction at analysis time.** Today a researcher
   looks at quotes and tags. Adding a behavioural stream is more
   data to sift. The codebook should drive the inference, not the
   other way round — inferred tags surface in the same panels, not
   a new panel.
4. **Tag attribution UX.** Should "this tag came from the terminal
   artifact" be visually distinct on the quote card? Probably yes
   (small glyph), but worth user-testing before shipping.
5. **Privacy of the emailed artifact.** Participants who email a
   scrollback may include tokens they pasted into the terminal,
   internal hostnames, paths revealing customer names. Same PII
   pass as for `.cast` (next section). Researchers should be
   prompted to redact the artifact before importing — or trust
   the redaction pipeline to do it.
6. **Multi-session alignment.** Some studies span multiple sessions
   per participant. Independent alignment per session is simpler;
   defer cross-session modelling until a real study needs it.
7. **No-screenshare sessions.** When the participant doesn't share
   their screen, the call recording's only signal about terminal
   activity is speech. The paste log becomes load-bearing rather
   than corroborating. Worth measuring how common that is in
   practice once we have any data.

## Scope and sequencing

This is post-TestFlight work. The codebook (the sibling YAML) ships
first and lets researchers manually tag behaviour they observe in the
transcript. Session matching is the same codebook, automated, on a
richer evidence base.

Build order, if it ships:

1. `bristlenose/utils/terminal_paste.py` — paste-log parser + tests
   with real scrollback fixtures from internal cohort calls. The
   cheapest, highest-leverage starting point — every session has
   one of these in the ideal world.
2. `bristlenose/utils/asciinema.py` — `.cast` v2 parser + tests.
   Same `CliEvent` output, with timing fields populated.
3. Pipeline integration — optional discovery of either artifact
   alongside the call recording, parsed in a new lightweight stage.
4. PII pass extended to cover terminal events.
5. Transcript-paired inference rules — the most-bang-per-buck tier,
   since it reuses the call transcript Bristlenose already produces.
6. Timeline strip in the session detail page (option (b) above),
   driven by whichever artifact is present.
7. Cast-only inference rules — finer-grained patterns that exploit
   per-event timing.
8. Provenance + tag-source UI.

Step 1 alone (paste parser + fixture corpus from real Bristlenose
internal-TF sessions) is a sandpit-sized week and could be done
before TestFlight if it would materially improve the Bristlenose-on-
Bristlenose dogfood loop. Steps 2–8 are full-feature territory and
should get their own design notes before implementation.
