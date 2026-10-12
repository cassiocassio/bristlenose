---
status: proposal
date: 12 Oct 2026
---

# Transcription quality: per-session numbers, a diagnostics row, opt-in telemetry

Proposal, not built. It comes out of the style-prompt and skipped-window work
(`docs/design-whisper-style-prompts.md`, `docs/design-transcript-readability.md`):
stage 5 now knows several things about how well a recording transcribed, and
throws them away after logging them.

## One record per session, numbers only

Stage 5 writes `.bristlenose/intermediate/transcription-quality/<sid>.json`.
It holds **no words, names or timestamps of speech**, only counts and levels.

| Group | Measure | Source today |
|---|---|---|
| Audio | duration; noise floor (dBFS, the quietest tenth); share of 100 ms windows with sound; peak level; share of clipped samples | the signal gate's levels (computed, discarded) |
| Recognition | backend and model; language detected or set; style prompt on or off; decode steps the prompt reached | logged per file |
| Recognition | windows that fell back to sampling (Whisper's temperature fallback) | in mlx's segments, not kept |
| Recognition | mean word confidence; share of words under 0.5 | in the word timings, not summarised |
| Repair | silent-stretch segments dropped; prompt echoes dropped; repeats collapsed | logged as counts, or not counted |
| Repair | skipped stretches found and recovered (count, seconds, words) | logged per file |
| Text | words; words a minute; sentence ends per 100 words; longest unpunctuated run; fillers per 100 words | not computed |
| Speakers | how speakers were separated (voice and text, text only, platform labels); voice centroid distance | already cached in `speaker-info/<sid>.json` |
| Later | `[inaudible]` marks; overlapping speech, once the voice pass can see it | not built |

**Overlap is the measure that matters most, and the one we can't count yet.**
People talking over each other is the first cause of lost speech in real
sessions, and Whisper hides it: it writes one voice at a normal pace and drops
the other, so neither the audio level nor the word rate notices. Counting it needs
the voice pass to report stretches where two voices are active, which is a separate
piece of work.

## A diagnostics row in the Sessions grid

**Who sees it.** Off by default; on when the user's diagnostics preference is on
(on the Mac, `showDiagnosticsMenu`, Tier U in `docs/design-feature-flags.md`; the
web needs the same preference in Settings). It is for the researcher who wants to
know why a transcript looks thin, and for us during the TestFlight period. It is
not a quality score in everyone's face.

**Where.** Inside the slice that already opens under a session's row, below the
session timeline: one more line per session, so the grid itself stays as it is.

**What it says.** Plain numbers in the muted text style, grouped as above, with at
most one plain sentence when something is outside what was measured as normal.
For example: *"Speech may be missing in 3 places (47 s). Listen at 8:00, 12:30,
14:30."* The timecodes are clickable, like every other timecode. No red and no
traffic lights (content owns colour). A flag that turns out wrong is worse than
none, so each flag's threshold comes from measurement, not from a guess.

| Flag | Shown when (to be calibrated) |
|---|---|
| Speech may be missing | skipped stretches found and not recovered |
| Hard to hear | mean word confidence low, or noise floor high |
| Whisper struggled | many windows fell back to sampling |
| Little punctuation | sentence ends per 100 words far below the language's norm |

**What it is not:** an accuracy score. None of these numbers knows what was
actually said. They are signs that a transcript deserves a listen.

## Opt-in telemetry

The same record, sent only with consent, would show what real projects look like:
how often speech is skipped, how much punctuation each language gets, where
prompts help, which audio conditions break transcription. It carries no words, but
it is still data about participants' recordings (durations, languages, how much
they hesitate). So it sits under the consent gradient
(`docs/methodology/consent-gradient.md`): opt-in, shown to the user before it is
sent, the record fixed and documented, and nothing that could re-identify a
session. It belongs with the alpha telemetry phases already planned after the
first cohort.

## Order

1. Write the record locally (stage 5 already has every number except fillers and
   text measures). No UI. Useful immediately for our own trials.
2. The diagnostics row, gated by the preference, with no flag sentences yet.
3. Calibrate the flags on real projects, then show them.
4. Telemetry, under consent, when the alpha telemetry work resumes.
