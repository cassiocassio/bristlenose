# Perceived waiting: what cues would help, where, and how we would know

Status: discovery, 4 Nov 2026. Nothing here is built, and nothing here is a spec. The owner picks.

This is the companion to `docs/design-perf-ledger.md`. The ledger measures how long moments take. This document asks how a wait feels, including the waits that cannot be shortened (cloud LLM calls, transcription). It reads the code and docs read-only; it changes no product file.

Every claim is labelled. **Verified** means a second, independent reader opened the primary text. **Search-level** means only a search summary or an abstract page was seen. **Memory** means nobody checked. **Audit** means read from our own code at HEAD `c2f81f4a5` plus a dirty tree, not observed in a running app.

## Summary (two minutes)

**The finding that matters most:** the evidence for "cues make waits feel shorter" is real but thin, and almost all of it comes from waits of seconds, with people who only wait. Nothing I could find studies a professional who starts a 20 to 60 minute job and walks away. So the evidence tells us which *mechanisms* are worth trying. It cannot tell us the size of any effect on Bristlenose. That is why section 6 is a measurement plan and not an afterthought.

**What the evidence does support, honestly:**
- A wait with a visible, truthful sense of progress is preferred to a blank one (Myers 1985, 48 people; Apple HIG; Nielsen). Real, old, and about waits of a few seconds.
- Partial results shown as they arrive keep people as effective as instant results and beat "nothing until done" (Zgraggen 2017, 24 students, 6 to 12 s). But partial results carry a risk: people anchor on early patterns that later change (Procopio 2022).
- Showing real work can raise the value people assign to a result (the labor illusion, Buell and Norton 2011), but it backfires when the result is poor, and the authors themselves call deliberate fakery an ethical boundary.
- Remaining-time displays raised frustration compared with elapsed-time displays, in waits of 10 to 60 s (Tan and Nov, CHI 2026, N=425). That is a caution about our "~N min left", not a verdict.

**What the evidence does not support, and the repo currently says it does:**
- `docs/design-llm-call-telemetry.md` cites Harrison et al. for "users hate upward revisions." Neither Harrison paper studies revised time estimates. They study the *pace and look of a bar* on waits of about 5 s. No peer-reviewed experiment I could find randomises upward against downward revision of a displayed estimate.
- The same note cites Myers 1985 for "users will tolerate longer delays if a progress indicator is shown." That sentence is not in the paper.
- `docs/design-motion.md` (line 20) says Harrison 2010 shows animation makes waits feel "10-15% shorter." The paper shows about 11% for specific pulsing or ribbed progress bars, on waits of about 5 s, in three experiments of 20, 10 and 16 people. It is not a general result about animation or fades.

None of these needs the design to change. They need the *reasons* corrected, and the design decisions they supported (hold the number, pad it, never revise upward) re-labelled as untested hypotheses, which the telemetry note's own hypothesis table already half-admits.

**What Bristlenose already does well.** Sessions appear as they become readable. One shimmer says "working." The status line carries stage, "N of M", "K readable" and "~N min left". Many of the cues a survey would suggest are shipped. The honest gaps are narrower than the brief assumed.

**The gaps the audit found** (all audit, none observed live):
1. The "~N min left" figure is only rewritten at stage boundaries (confirmed on a recorded run, section 4.4; on that run it was also 2 to 5 times too long). During transcription, the longest stage, it sits at the opening figure for the whole stage while the count moves. That is a stale number presented as live.
2. The Quotes lens fills session by session and says nothing about being partial. A researcher reading quotes from 3 of 8 sessions has no sign that more are coming. That is a research-validity problem as much as a feeling.
3. Nothing marks "this run has finished and everything is now safe to read" for someone who has been reading a progressive report. The repo already lists this as a known open race.
4. The worst wait on record (a 30-minute truncated quote call in the FOSSDA run) looked identical to a 7-second call.
5. The web report has no run-progress channel at all; only the Mac app carries run words.

**Ranked candidates** (section 5; detail there):

| # | Cue | Wait it targets | Evidence for the mechanism | Size |
|---|---|---|---|---|
| A | **Tell the researcher when the run is done, or failed, when they have left the app** (owner suggestion, 4 Nov); not a push of "about N min" | Run, minutes to an hour, walk-away | None found for notifications themselves; the argument is logical (the one cue that works at any length) | Recorded as post-TestFlight direction; the failure case is new |
| 1 | Mark the partial report as partial, and say when it is complete | Run, minutes to an hour | Medium (lab, seconds) plus a validity argument that needs no psychology | Small: a header line, ~3 strings |
| 2 | Make "~N min left" honest between stage boundaries (re-derive it as sessions complete, or show its age) | Run, minutes to an hour | Weak and contested; Apple HIG is the strongest statement | Medium; first confirm it is really frozen |
| 3 | Lens click: keep the heading while the chunk loads; hold back "Loading…" until it has lasted about 200 ms | Lens click, under 1 s | Practice only, no peer-reviewed measure | Small, but measure first; may need nothing |
| 4 | Elapsed time in the status line's tooltip | Run | Weak (Tan and Nov, 10 to 60 s) | Small |
| 5 | A "found so far" count in the status line ("112 quotes") | Run | Medium for the mechanism, with a known backfire | Small, but reopens a recorded decision |
| 6 | A "taking longer than usual" line for a call that is far outside its normal length | Run, worst case | Practitioner guidance only | Medium; new event |

**On the owner's example, themes appearing on the timeline as they are found:** it does not match how the pipeline works. Themes are made by one or two calls at the end of the run (27 s on the FOSSDA corpus), after all quotes exist. There is no trickle to show. Per-session *topics* are made earlier, and could be drawn, but they are not themes and must not be called that. See section 5, candidate 7, and question 4.

**Rejected on honesty grounds, though research says they work:** accelerating progress bars, invented percentages, deliberate delays, rotating verbs with no data behind them, and skeletons on minute-long waits.

**Biggest limit on this report:** the prior-art survey (section 3) is mostly from memory. Only Final Cut Pro's Background Tasks window and the shape of ChatGPT Deep Research were checked. I found no documented evidence that researchers using analysis tools complain about waiting; the loud complaints are about transcript accuracy. Build on honesty and the ability to leave, not on "researchers hate waiting."

---

## 1. The evidence, graded

Grades: **lab** (controlled experiment), **meta** (meta-analysis), **essay** (argument from experience), **guidance** (platform or practitioner advice), **blog**. Transfer is to a professional desktop tool where the wait is minutes to an hour and the user may do other work: high, medium, low, none.

### 1.1 Waiting in general

| Claim, in our words | Source | Grade and check | Transfer |
|---|---|---|---|
| Eight propositions about waits (occupied time feels shorter; uncertain, unexplained and unfair waits feel longer; and so on). Maister himself says they rest on common experience and are hypotheses. | Maister, "The Psychology of Waiting Lines" (1985), https://davidmaister.com/articles/5/52/index.html | Essay. **Verified** (his own page). Popular summaries present it as research; it is not. | Medium. Queues of people, not software. |
| Across 129 studies (38,967 people), reactions depend on the stage of the wait, what the person knows, regret and importance. Subjective time drives anxiety during a wait; acceptability shapes judgement after. | Lin and Agarwal, DOI 10.1177/10946705261453760 | Meta. **Verified from an aggregator page only**; I did not read the paper, and the journal and year are inferred. | Medium. Nearly all service queues. |
| Progress information is preferred to none. 86.1% of 48 people "liked progress indicators"; ratings were higher with them at response times averaging about 8.6 s. The paper argues, but did not measure, reduced anxiety, and did not support its hypothesis that indicators change feelings about variable response times. | Myers, "The importance of percent-done progress indicators" (CHI 1985), https://www.cs.cmu.edu/~bam/papers/percentdoneCHI85.pdf | Lab, mostly CS graduate students. **Verified** (scan read by OCR). The common gloss "tolerate longer delays" is **not in it**. | Medium for the direction. |
| For short waits, duration information and queue information changed little; for intermediate waits duration information beat queue information; the advantage shrank for long waits. Acceptability and affect mediated, perceived duration did not. | Hui and Tse, J. Marketing 60(2), 1996 | Lab. **Search-level only.** | Medium. Direction: information matters most in the middle band. |
| Delay hurts through uncertainty and anger. | Taylor, J. Marketing 58(2), 1994 | **Search-level**; the abstract was not opened. | Medium. |
| In four computer experiments, waits did not always lower evaluations, and managing the wait could neutralise the harm. | Dellaert and Kahn, 1999 (abstract only) | Lab. **Search-level.** | Medium-high on kind, low on length (short waits). |
| "Tolerable waiting time" for web pages is lengthened by feedback. The famous "2 seconds" is one study's number for page retrieval. | Nah, 2004 | Lab. **Search-level.** | Low for the number, medium for the direction. |
| A message that finishing later than a quoted time lowers satisfaction, while finishing earlier does not reliably help. | Pavlov, Mogre, Lennon Olsen, SSRN 4744367 (working paper, 2024) | Online experiment (MTurk). **Search-level only**; both pages returned 403. A related talk abstract claims early finishing can disappoint, which conflicts. | Medium-high on kind, low on evidence quality. |
| On the revision of a displayed estimate: **no peer-reviewed experiment found** that randomises upward against downward revision. | Searched; see verification note | **Not found.** Nearest work answers other questions (a 2023 retailing paper found that with a displayed estimate the usual "late hurts more than early helps" asymmetry reverses; seen as a search summary). | n/a |

### 1.2 Progress bars, pacing, response times

| Claim | Source | Grade and check | Transfer |
|---|---|---|---|
| Of nine bar behaviours with identical real duration, accelerating bars were judged faster; bars that pause or slow near the end were judged slower. **It says nothing about revised time estimates.** | Harrison, Amento, Kuznetsov, Bell, UIST 2007 | Lab, 22 people, seconds. **Verified** (PDF). | Low. And it rewards manipulating the display, which section 7 rejects. |
| Pulsing or ribbed bar textures cut perceived duration about 11%. | Harrison, Yeo, Hudson, CHI 2010, https://www.figlab.com/research/2010/faster-progress-bars | Lab, three experiments (20, 10, 16 people), about 5 s. **Verified.** | Low. |
| Over 32 survey experiments, a constant progress bar did not reduce drop-out; a bar that began fast and slowed did; one that began slow and sped up raised it. The outcome is quitting, not felt time. | Villar, Callegaro, Yang, Social Science Computer Review 31(6), 2013 | Meta. **Verified** (record page). | Low. |
| Remaining-time displays raised frustration compared with elapsed-time displays; no timer at all felt longer and more ambiguous. Neither changed later task performance. | Tan and Nov, "Counting the Wait", CHI 2026, https://arxiv.org/abs/2602.04138 | Lab, N=425, waits of 10, 30, 60 s. **Verified** (abstract; body read by a second agent). | Medium. The closest controlled test of our "~N min left", and the longest wait it covers is one minute. |
| More, smaller steps feel faster than fewer larger ones. | Ziat et al., 2022 | Lab, 11 to 21 students per experiment, 3 to 14 s. **Search-level.** | Low-medium. |
| Apple's own guidance: prefer determinate; keep the pace even ("90 percent in five seconds and the last 10 percent in 5 minutes" can "feel deceptive"); keep it moving; offer Cancel, and Pause if cancelling has side effects; on macOS prefer a spinner for background work and do not label it vaguely. | Apple HIG, Progress indicators, https://developer.apple.com/design/human-interface-guidelines/progress-indicators | Guidance. **Verified** (read in full). | High. It is our platform's rule. |
| Past about 10 s give feedback; when the total is unknown, report absolute work done (items finished) in preference to a percentage. | Nielsen, "Response Times: The 3 Important Limits"; "Powers of 10" | Guidance, citing Miller 1968, Card 1991, Myers 1985. Page read via search summary. Miller and Card **not opened**. | Medium. |
| The "400 ms Doherty threshold". | Doherty and Thadhani, IBM report, 1982 | **Not confirmed**: the primary copy is dead. Search summaries suggest the report is about sub-second gains and "400 ms" is a later popular gloss. Do not cite as measured. | Low. |

### 1.3 Skeletons, spinners, shimmer

The evidence is thin and contradictory, and all of it is web loading of a few seconds.

- Viget's 2017 test (136 people, split 39/39/58 across spinner, skeleton and blank; **GIFs, not live loading; no significance tests**): "loaded quickly" was agreed by 74% for the spinner, 66% for blank, 59% for the skeleton. Perceived wait 2.41, 2.29 and 2.82 s. The skeleton did worst. **Verified.** https://viget.com/articles/a-bone-to-pick-with-skeleton-screens
- Mejtoft and colleagues (2018, small) reportedly rated the skeleton higher for perceived speed and navigation. **Not opened**, search summary only. NN/g's recommendation to use skeletons for waits over a second cites this and otherwise rests on judgement. https://www.nngroup.com/articles/skeleton-screens/
- Honest reading: a skeleton is a **layout and orientation device**. Nothing supports it as a way to shorten a minutes-long wait. On a long wait it also implies "nearly here," which is untrue.
- No study of shimmer or pulse speed was found. WCAG 2.3.3 (animation from interactions) is AAA; practitioners disagree on a static placeholder against a slow pulse under Reduce Motion. Our shimmer already honours both Reduce Motion and the "Show animation while analysing" setting.
- Delay-before-showing a spinner and a minimum display time (library defaults of 150 to 500 ms and 200 to 1000 ms) are **practice only**; I found no peer-reviewed measurement.

### 1.4 Transparency, labor, and the honesty line

| Claim | Source | Grade and check | Transfer |
|---|---|---|---|
| Showing real work during a 10 to 60 s wait raised perceived value over a blind wait (Exp 1: 5.36 against 4.96, N=266). Perceived effort and reciprocity carried it. | Buell and Norton, Management Science 57(9), 2011 | Lab, five experiments. **Verified** (full text). | Medium for the mechanism, low for the size. |
| **It backfires.** With an unfavourable result, transparency was *worse than an instant answer* at both 15 s (2.47 against 3.24) and 30 s (2.10). With favourable results, neither version beat instant at 30 s. Value fell as waits lengthened, with or without transparency. | Same, Exp 5 (N=280) | **Verified.** An earlier note of ours had said "neither beat instant at 30 s" without the qualifier; that was wrong. | High, as a caution. |
| The authors write that being able to induce the illusion does not mean firms should; it moves "closer to an ethical boundary." | Same | **Verified.** | The strongest primary backing for our honesty rule. |
| A 2 s first-token delay made a GPT-4o reply read as *less thoughtful* than 9 or 20 s (5.76 against 6.09 and 6.11). Trust did not change. About 31% of those who noticed read the delay as deliberation. | Tan, Messerschmidt, Yin, Nov, CHI 2026, https://arxiv.org/html/2604.06183v1 | Lab, N=240 analysed (343 completed). **Verified.** | Low on size; medium as a warning that people over-read pauses as thought. |
| Progressive partial results matched instant results on insight and coverage; blocking did worse. | Zgraggen et al., IEEE TVCG 23(8), 2017 | Lab, 24 students, 6 and 12 s. **Verified.** | Medium. |
| A false pattern shown early in a progressive display hurt accuracy more than one shown late. | Procopio et al., IEEE TVCG 28(9), 2022 | Lab, MTurk. **Verified.** | High as a caution: our partial Quotes lens is a progressive display. |
| Partial results should look like final ones; constant visual change distracts; prefer subtle ambient cues and refresh-on-demand. | Stolper, Perer, Gotz, IEEE TVCG 20(12), 2014 | Design study. **Verified.** | High. |

### 1.5 Peak-end, completion, "is it stuck?"

- Retrospective judgement of an experience tracks its peak and end more than its length (Kahneman and colleagues). A 2022 meta-analysis of 174 effect sizes found peak-end r=0.58 and duration "essentially nil", **but** the simple average predicted about as well. Alaybek et al., *Organizational Behavior and Human Decision Processes* 170, 2022. **Verified** (abstract). Mostly short episodes. The first-hand Kahneman papers were **not opened**. Take-away: the end matters, but do not build a theory of the end moment; make it clear and unremarkable.
- "Looped spinner cannot be told from a hang," and determinate indicators are advised beyond about 10 s: NN/g and Microsoft Fluent guidance (https://fluent2.microsoft.design/wait-ux). Guidance only, seconds scale.
- Completion notification for long jobs, and whether it helps or annoys: I found **no study**. Practice is convention.
- Secondary tasks while waiting shortened perceived waits in a crowd-sourced study (HCOMP 2021, N=930, abstract only). It supports giving users something real to do, which for us means making leaving safe.

### 1.6 Gaps

- No evidence at the minute-to-hour scale with a user who is free to leave. This is our case.
- No study of revised estimates (above).
- No study of researchers' waiting frustration with analysis tools.
- Attentional-gate theory (Zakay and Block) and the Larson, Osuna, Katz queue papers were **not retrieved**.

## 2. What transfers to a minutes-long professional tool, and what does not

**Transfers, as direction (not size):**
1. *Say what is happening, with real counts.* Nielsen, Myers, HIG and Buell and Norton all point the same way. The strongest form is the one that is also true: absolute work done.
2. *Show results as they arrive, in their final form, and mark them provisional.* Zgraggen, Stolper and Procopio agree on the benefit and the hazard.
3. *Make leaving safe.* The user's best "occupied time" is their own other work. The job of the tool is to say, truthfully, that nothing needs watching and to say plainly when it is done. This is an inference from Maister's occupied-time proposition and the HCOMP result, not a tested result at our scale.
4. *Avoid a number that stops moving.* HIG: keep it moving, explain stalls. This is guidance, but it is also simply a question of whether the display is true.

**Does not transfer, or only weakly:**
- Every effect size. All measured waits are 3 to 60 s; ours run to an hour.
- Pacing tricks. They work, on 5 s bars, by manipulating the display.
- Skeletons as "makes it feel faster."
- The labor illusion as a *recipe*. Its experiments used simulated searches of 10 to 60 s on consumer sites. It is a risk here.
- Peak-end as a design lever for hour-long waits. Untested there.

## 3. Prior art

**Read this first:** only two entries below were checked against a source. Everything marked *memory* was written from recall and should be confirmed by hand by anyone who relies on it. The owner has met most of these products; their own recollection is a better check than mine.

| Product | What it does | Why it works, or does not | Assumes | Honest? | Check |
|---|---|---|---|---|---|
| **Final Cut Pro, Background Tasks** (Cmd-9) | One window lists each background job with a percentage, and per-task pause, resume, cancel. Tasks pause automatically while you work. | The heavy work is out of the way but inspectable; state is named in words. | Each task has a measurable percentage; user stays in the app. | Yes. | **Verified** (Apple support guide, via search). |
| **ChatGPT Deep Research** | Proposes an editable plan first, then a live activity and sources panel, can be interrupted; reportedly notifies on completion. | The plan sets expectations; the sources list is proof of real work; you can leave. No percentage. | Number of steps unknown. | Yes: a log of real activity. | **Verified** from OpenAI help; the completion notice is from a third-party report. |
| **Lightroom, Capture One import** | Thumbnails appear as each file is processed; the grid is usable at once; a small count line beside it. | The unit of progress is the unit the user cares about; first output is early. | Items independent. | Yes. | Memory. |
| **Xcode** | One status line in the toolbar ("Building", "Indexing"); issues stream into the navigator as found. | One stable place; findings arrive live. Indexing is vague and users report it stalls. | | Yes, vague. | Memory. |
| **Photos "Analysing"** | A status line with a count; results appear over days; pauses on battery or when you work. | Counts age better than time estimates. | | Yes. | Memory. |
| **GitHub Actions, CI** | Step list with tick, spinner or cross; live log per step; leave and get an email. | Steps are the real workflow units. No overall percentage. | | Yes. | Memory. |
| **cargo, uv** | Resolve the plan first, then count against it ("n/N"). | A count against a known plan. | Plan knowable up front. | Yes. | Memory. |
| **Claude Code and agent UIs** | Rotating verbs, elapsed time and token count, Esc to interrupt; some agents list each step as a log. | The *counters* are real; the *verbs* are decoration. | | Mixed: real numbers beside friendly theatre. | Memory. |
| **Docs "Saving…", Dropbox, iCloud status** | A tiny persistent state: saving, saved, offline, syncing N files. | Quiet, truthful, never blocking. | | Yes. | Memory. |
| **Zoom, Teams transcripts** | "Transcript will be available after the meeting"; arrives later with a notification. | Expectation plus closure. No progress. | Users expect the delay. | Yes, uninformative. | Memory. |
| **Linear, Superhuman, Things, Arc** | Local data, optimistic updates, no spinners. | Work is off the interaction path. | Small operations, a local replica. Does not transfer to a cloud pipeline of minutes. | Yes. | Memory. |
| **Spotify, Netflix, Figma** | Skeleton rows; prefetch; shell first. | Reserves layout for sub-5 s waits. On minutes it implies false imminence. | | | Memory. |
| **Dovetail, Condens** | Not examined. Reviews (anecdotal, vendor-adjacent aggregators) call Dovetail's AI features "somewhat slow" and praise Condens for speed. | | | | Reviews only; no evidence of a waiting-specific complaint. |

**Patterns that recur, and the condition under which each fails:**
1. *Items appear as ready, in the unit the user cares about* (Lightroom, Deep Research sources). Fails when an item only makes sense after a later stage, or when it later changes and the reader has already acted on it. Needs a provisional marker.
2. *A plan, then ticking against it* (Deep Research, cargo, CI). Fails when the plan is not knowable. Add rows as they appear.
3. *Stage name plus a real count, no invented percentage* (Photos, uv). Fails when units are unequal (a 5-minute and a 90-minute recording) and the count gets read as time.
4. *Put it somewhere inspectable, and let the user leave* (Final Cut, CI). Fails if leaving costs finished work.
5. *A persistent quiet state line* (Docs, Dropbox). Fails if it says "Working" for 40 minutes.
6. *Reserve layout.* Fails on long waits.
7. *Interruptible, with a polite pause.* Fails if stop discards finished work. (Ours keeps finished sessions: audit.)
8. *Failure shown on the object, not the run* (CI, one failed session). Fails if the summary hides it.
9. *Decorative motion only beside real numbers.* Otherwise theatre.

Bristlenose already implements patterns 1, 3, 5 and 7 in some form.

## 4. The map of waits in Bristlenose today

All from the audit. "Length" is measured only where the ledger or a corpus run gives a number; otherwise estimated. Strings are verbatim from the locale files.

### 4.1 During a run (the long waits)

The corpus: FOSSDA, 10 interviews, 490 minutes of audio, M2 Max, 36 min 48 s total. Transcribe 17 m 21 s, quotes 17 m 30 s (inflated by one truncated session), everything else under a minute. The file is private; the numbers are measured but not shareable.

| Stage | Length | What the row and subtitle say | The report body | Silent |
|---|---|---|---|---|
| Queued | unbounded | "Queued · position N" | not mounted | what it waits behind |
| Start, preflight | 1 to 10 s (est.) | "Analysing…" with a spinner | a decorative flock of words, or "Analysing interviews" | which step |
| Model download (first run) | minutes, once | "Downloading speech model", ring fills from bytes | as above | bytes and speed as words |
| **Transcribe** | **minutes to an hour** | "Transcribing · 3 of 8 · 2 readable · ~12 min left" | Sessions lens: rows readable, one "processing" (filename shimmers), others greyed | **Inside a long file on the default Apple Silicon backend: one blocking call, no heartbeat.** The figure "~N min left" is rewritten only at stage boundaries (audit). |
| Per-session chain | seconds to a minute | "readable" count rises | quotes appear one session at a time | which session; quote counts |
| Identify speakers, topics | 10 s to 1 min | "Identifying speakers · 6 of 10 …", "Finding topics · n of M" | as above | which session |
| **Find quotes** | **minutes** | "Finding quotes · n of M" | Quotes lens fills session by session | **Quotes found so far. A truncation or retry: the 30-minute call looked like a 7-second one.** |
| Group themes | 10 s to 1 min (27 s measured) | "Grouping themes" (no count, deliberately) | Signals lights at the end; its first card headlines pulse as a grey bar for 3 to 5 s | number of themes forming |
| Render | 1 to 10 s | "Building report" | | |
| After the run | | row returns to idle (a clean run shows no status line, by design) | Sessions tapestry strips arrive by a silent poll | **That the run finished and the report is now complete** |

Other facts that shape any cue:
- Progressive display applies to a **first analysis only**. A re-analyse shows the old report.
- Codebook and Project lenses stay off for the whole run, by owner decision. Export is disabled until the run ends.
- **Only the Mac app carries run words.** A browser or CLI-serve user sees a static "Analysing interviews" page until the first session is readable. The CLI prints its estimate twice at the start and nothing as stages finish (`cli.py:1352-1354`, deliberately).
- **The ETA needs at least 4 earlier runs** before it shows, and a range after 8. A new user's first run has no estimate. When the estimate is wrong, the ring creeps to 0.92 and holds; nothing says so.
- The running popover described in `docs/design-pipeline-diagnostic-popover.md` does not exist in code (drift). The five-kind `MessageKind` has no "running" kind by design ("pending/running → status, not a kind").
- Data that exists during the run and is not shown: run and stage elapsed time (`run_progress.elapsed_seconds` is "not yet read Swift-side"), quote counts per session, section and theme counts, cached against new session counts. LLM retries, tokens and truncation exist only in `llm-calls.jsonl`, a re-identification-key file that must never reach the UI or an export.

### 4.2 In the app (the short, frequent waits)

| Moment | Frequency | Length | What shows | Silent or unmeasured |
|---|---|---|---|---|
| Click a lens, first visit | many a day | under 1 s (unmeasured) | **A blank pane**: every route-level `Suspense` fallback is `null` (`AppLayout.tsx:1037`) | everything, until the chunk loads |
| Click a lens, revisit | many a day | under 1 s (the `/quotes` read is 87 ms of server time at n=1,500; the lens read about 180 ms on that fixture) | The heading, then a grey "Loading quotes…" line, on every visit because lenses remount | no distinction needed; loading and empty are separate branches in most lenses (Codebook unverified) |
| Type in search | many a day | 150 ms debounce | the field echoes; results change after the debounce | no "searching" cue, and none is needed |
| Open or switch a study | daily | 2.2 to 3.2 s measured | A centred indeterminate bar, 240 pt wide, **no words, by decision** | the sidebar row is the only text |
| First timecode click | daily | 1 to 10 s (unmeasured) | the main window shows nothing; a separate player window opens | the player is frozen vanilla JS with no loading text |
| Analyse, Stop | daily | under 100 ms | immediate "Stopping…", "Queued", "Analysing…" | nothing; already fine |
| HTML export | rare | 3.5 s measured | the dialog closes; the study row says "Exporting…" | on the web no cue |
| Scene strips arriving | background | seconds to minutes | stripes appear inside fixed-height clips by a silent poll | **by design** |
| Hover thumbnail | occasional | 700 ms delay | nothing until frames load | **by design** ("show nothing until ready") |

### 4.3 Decisions that constrain any cue

- **Cloud-file waits: no label, glyph, advice, progress or ETA.** Settled; re-proposed five times; not reopened (`docs/design-cloud-files.md`).
- The ledger's **declined list** stands (previous view dimmed on lens switch, prefetch on hover, streaming export, hidden player window, and others).
- The shimmer is text-only, replaces a spinner, is never shown beside a progress bar, and is gated by Reduce Motion and the animation setting.
- "Not needy," "absence is information," "expected outcomes get plain words," "man bites dog," "no promises."
- **Beta means almost no new features.** Anything below that adds a surface is a feature and waits; anything that is a copy or truthfulness fix may not be.
- Any new string means all 21 full locales.
- A **background run-complete notification** (banner, one informational Dock bounce) is already recorded as direction, post-TestFlight (`docs/macos-ux-checklist.md`). I do not re-propose it; there is no notification code in the Mac app today.
- The earlier decision "no new in-progress messages" (`docs/design-progressive-lenses.md`, section 2) was relaxed once, for the readable count. Candidate 5 asks to relax it again.

### 4.4 Observed: what the estimate does during a run (4 Nov 2026)

Method: no live Mac session. I read the event stream of a recorded run (`pipeline-events.jsonl`, counts and timings only, no participant text) and the Swift code that turns it into the subtitle. The run is a 3-session synthetic trial, 98 s end to end. The table carries each estimate forward until the next one arrives, which is what the Mac does, and compares it with the true time left once the run's end is known.

| Elapsed | Stage | Figure the Mac holds | True time left | Held figure ÷ true |
|---|---|---|---|---|
| 0 s | start | 332 s ("~6 min left") | 98 s | 3.4 |
| 13 s | transcribe, 2 of 3 | 332 s, unchanged | 85 s | 3.9 |
| 19 s | speakers entered | 216 s | 79 s | 2.7 |
| 33 s | quotes entered | 170 s | 65 s | 2.6 |
| 54 s | quotes, 2 of 3 | 170 s, unchanged | 44 s | 3.8 |
| 66 s | quotes done | 70 s | 32 s | 2.2 |
| 98 s | render | 57 s, still shown | 0 | n/a |

What this shows:
- **Confirmed: within a stage the figure does not move.** Of the 24 progress events, every one that carries a session count (`sessions_complete`) has no estimate. The estimate arrives only at stage entry and stage end. The Mac keeps the last one and never subtracts elapsed time. In the quotes stage the figure sat at 170 s for 33 s while the true remainder fell from 65 s to 32 s.
- **New: on this run the level was wrong too, by a factor of 2 to 5, always too long.** The first figure promised about six minutes for a job that took 98 s. The estimator does not pad (`timing.py` uses the mean), so this is not deliberate padding; the cause is unknown. I did not inspect this machine's timing history, and one run says nothing about how large the error is in general.
- **The run ended with a stale figure on screen.** The last estimate (57 s) stood through the render stage, which ended the run.

Limits: one short run, 3 sessions, synthetic. It cannot show what an hour-long transcription looks like, only that the mechanism that would freeze it is real. The FOSSDA corpus has only start and end events, so no longer run was available. Nothing here was seen on a live Mac window.

What to do with it: candidate 2's option (a) fits this directly, since a per-session event already exists on every line that lacks an estimate. The level error is a separate question for whoever owns `timing.py` and is worth checking on a second run before any design relies on the figure.

## 5. Candidate cues, ranked

Ranking is frequency a day times how much it is felt, then cost. The run happens less often than a lens click but is felt far more, so it leads. Every good-enough number below is a proposal, **not measured**.

### A. Tell them when it is done or has failed, wherever they are (owner suggestion, 4 Nov 2026)

Ranked by value this belongs at or near the top; it is lettered because it came after the ranking and because it is already recorded as post-TestFlight, which is a scheduling fact and not a judgement of worth.

- **Wait:** any run long enough to walk away from, which is most of them (about 37 minutes on FOSSDA).
- **Mechanism:** the research cannot shorten a cloud-bound wait, but the one thing a tool can do at any length is release the person from watching it. Occupied time with their own work shortens perceived waits (Maister, essay; a crowd-sourced study found secondary tasks did, HCOMP 2021, abstract only), and a clear end closes the wait (peak-end evidence is weak here: 1.5). The strongest argument is not empirical: it is what the evidence gap in 1.6 leaves as the honest answer for a user who leaves.
- **Evidence for notifications themselves:** none found. It is convention (Zoom and Teams transcripts, CI email, Deep Research reportedly).
- **What is already decided** (`docs/design-desktop-nav-toolbar-rearrangement.md` section 10.4, post-TestFlight): when the app is not frontmost at completion, a Notification Centre banner with sound (click opens the project) plus one informational Dock bounce; no badge; opt-in or sensible default; only on genuine completion; gate on `NSApp.isActive`; VoiceOver announces completion. There is no notification code in the Mac app today.
- **Owner direction, 6 Nov 2026 (supersedes the content-free and opt-in rules I first proposed for the Mac banner):** the text should be useful, because it is a notification on the researcher's own Mac and the risk is low; it is **on by default**, with a way to mute it in the **General** tab of Settings; and no "about 10 min" figure. The content-free rule now applies only to anything that leaves the Mac (route 1 below).
  - **Also decided, 6 Nov 2026:** if Bristlenose is the frontmost app there is no banner, whichever project is on screen. The researcher is in the app and has the sidebar, so a run finishing in another project shows there as it does today. A closed sidebar is a wrinkle to play with once it is built.
  - **Decided, 6 Nov 2026:** the project name is in the banner by default. The researcher is on their own Mac and already knows their client names; the screen-share and lock-screen worry in (a) below is not a reason to leave it out.
  - **Settle before wording is fixed:** (a) *Confidentiality at the edges.* Project names often carry a client's name, and a banner can appear on a lock screen or while the researcher shares their screen. macOS lets the researcher hide previews, and has its own setting for notifications while the display is shared or mirrored; I believe both are off or hideable by default but have not checked either, so verify before relying on it. The in-app mute is the researcher's own control. (b) *Default-on still asks once.* macOS will not deliver a banner until the researcher has allowed it, so "on by default" means asking for permission at the first run, in context, not silently. (c) *The switch should read positively*, for example "Notify when an analysis finishes or stops", on by default; a switch called "mute alerts" turns the double negative into the label. Wording is mine, not a shipped key. (d) *On a failure, give the reason only if the classifier already knows it* (the app already distinguishes things like a rejected key or no credit); otherwise say it did not finish and stop there.
  - **Mockup, state diagram and architecture diagram:** `docs/mockups/perceived-wait-run-banner.html`. **Parked by the owner, 6 Nov 2026:** the idea of the web report asking its platform to send the alert is not being pursued for now. It also answers whether the web report could ask its platform to send the alert: in principle yes, but the Swift side is what knows a run has ended, so the page would only add a hop (search-level on what a web view's own notification API does).
  - **Illustrative text, not copy to ship** (synthetic project): finished: "Analysis finished", "Checkout study · 8 sessions"; failed: "The analysis didn't finish", "Checkout study · Claude couldn't be reached". Whether a quote count belongs in the finished line is the same question as candidate 5, and I would leave it out until that is decided.
- **What the owner's suggestion adds, and my view of each part:**
  - **"Done": yes.** A real, terminal state. It is news.
  - **"Failed": yes, and it is the more valuable half.** A provider failure is fail-stop (a decided rule), so a researcher who left will otherwise come back to a stopped run and lost time. Reuse the shipped wording ("The analysis didn't finish"); it is not decided whether the banner also says why.
  - **"Will be done in 10 minutes": not as a push, not yet.** Three reasons. The recorded run in 4.4 showed the held figure 2 to 5 times too long, so a pushed number would be a promise we cannot yet keep. A push cannot be corrected: the in-window figure can change, a banner already delivered cannot, and a second banner to fix the first is exactly the needy pattern. And it is not news: it restates the status line. If the estimate becomes trustworthy (candidate 2) it could be reconsidered as a single optional heads-up; I would not design it now.
  - **Phone and Watch:** researched 4 Nov 2026; the answer is below ("Reaching the phone and Watch"). Short form: Apple does not forward a Mac app's banner to either, so each route needs something built or set up.
- **Honesty check:** fires only on terminal states that are true when sent. Plain words. No countdown, no progress, no cheer.
- **Constraints:** a new feature under the beta rule and a permission prompt (one more first-run question; an opt-in keeps it from being needy). A new string or two in 21 locales. A banner must not fire for a run the researcher is watching.
- **How we would know it helps:** this is the easiest cue to measure because it has a behavioural outcome. Take the gap between run end and the researcher's next return to the app, locally and never as telemetry, with the banner off then on; and in the diary question ask whether they left, and whether they came back too early or too late. Good enough, proposed and unmeasured: median return within 5 minutes of a finished run for researchers who left. The danger to look for is the opposite: banners for runs they were watching.

#### Reaching the phone and Watch: what Apple actually does (researched 4 Nov 2026)

Method: two research agents (Apple documentation; implementation routes), then a third that tried to break their conclusions, with particular attention to anything new in macOS, iOS and watchOS 27. Sources are Apple documentation, Apple support pages and the App Review Guidelines where marked; everything else is labelled.

**The straight answer: there is no out-of-the-box path.** No Apple mechanism I could find, in macOS 26 and 27, iOS 27 or watchOS 27, forwards a third-party Mac app's notification to the user's iPhone or Apple Watch. This is "not found" across a bounded search, not a proof that none exists; I did not open every WWDC 2026 session, or Apple's "Manage iPhone notifications on Mac" page.
- **Apple's Watch rule is verified** (Apple support, support.apple.com/en-gb/108369): a notification goes to the iPhone *or* the Watch, never both. iPhone unlocked: iPhone; iPhone locked or asleep: Watch, unless the Watch is locked. It never mentions a Mac.
- **Apple's developer document on notification forwarding** lists three sources only: an iOS app, a watchOS app, or your server. No Mac row. **Verified.**
- **The cross-device features Apple has added run the other way.** macOS 15 shows iPhone notifications on the Mac (third-party coverage; Apple's page not retrieved). macOS 26 and 27 show an iPhone's Live Activity on the Mac menu bar, the Watch Smart Stack and CarPlay; in WWDC 2026 session 223 the iPhone is the origin, and I found nothing that lets a Mac start one. **Verified for session 223.**
- **So your hunch is half right.** It is a real ecosystem gift once *an iPhone app is the sender*: its alerts then reach the Watch and the Mac for free. The missing piece is an iPhone-side sender.

**Routes, in the order I would try them.** "Quit, sleep" means: does it still work if the Mac app has quit, or the Mac is asleep or the lid is closed.

| Route | What the researcher sets up | What we build | Quit, sleep | What leaves the Mac | Status |
|---|---|---|---|---|---|
| **1. A push service the researcher chooses** (ntfy, Pushover, Pushcut, a webhook) | Install that service's iPhone app; paste a topic or token into Bristlenose | One HTTP request on completion; the network-client entitlement | Needs a live process on an awake Mac | A fixed, content-free message to that service | Cheapest and most reliable. Reaches the Watch by the ordinary iPhone mirroring (inference for ntfy; the Watch rule above is verified). |
| **2. A Reminder or Calendar alarm** (EventKit) | Grant Reminders (full access) or Calendar (write-only) | Create an item with an alarm; delete it on success | A pre-set alarm at the estimated finish plus a margin would fire if the Mac sleeps; a dynamic "done" needs a live process | An item in the researcher's own iCloud | Zero-install, but **weakly evidenced**: one third-party test (macOS 26.3.1) saw an absolute-date alarm alert an iPhone and iPad; Watch untested; the "alarm a few seconds ahead" case and latency not found. Test by hand before relying on it. |
| **3. A CloudKit subscription** | Sign in to iCloud; install our iPhone app | Mac writes a record to the researcher's private database; a subscription with an alert body pushes it; plus an iPhone app | Same as 1 | A record in their private iCloud | No server and no third party, but **it needs an iPhone app** from us (Apple's docs say the push goes to devices that use the app; the "needs the app" reading is an inference, with no counter-evidence found). A notification-only app risks a minimum-functionality review. |
| **4. Our own push relay** | Install our iPhone app | A server, a push key, an iPhone app | Same as 1 | A message through our server | Parked by decision; heaviest. |
| Messages to self | | | | | **Rejected:** a sandboxed app needs scripting entitlements that the Mac App Store generally refuses, and a message sent to yourself does not alert your other devices (forum reports). |
| Shortcuts | | | | | **Not a route:** a Mac Shortcut's notification stays on the Mac. It is a way for a researcher to wire route 1 themselves. |
| A Mac app starting a Live Activity on the iPhone | | | | | **Not possible as documented:** starts are in-app, scheduled or by push. |

Facts behind the table (**verified against Apple text unless marked**):
- Reminders need **full** access on macOS 14 and later (no write-only); Calendar offers write-only. The sandbox entitlement is `com.apple.security.personal-information.calendars` (verified for Calendar; for Reminders forum reports only).
- A locally scheduled notification (`UNTimeIntervalNotificationTrigger`) is delivered by the system whether or not the app is running (Apple's scheduling doc), but it appears **on the Mac only**, and only knows the estimated time, not the outcome.
- `SMAppService` (macOS 13 and later) registers login items and helper agents, subject to user approval. App Review 2.4.5(iii) requires consent for auto-launch and for processes that outlive the app; 2.4.2 bans only unrelated background processes; 4.5.4 says push must not be required for the app to work and must not carry sensitive or confidential data. An opt-in, content-free alert fits all three.
- **ntfy** (docs and FAQ): free, no sign-up, a topic name is the only secret unless access control is set; a short rate limit; paid tiers from $5 a month. iPhone delivery goes through ntfy's server and Apple's push service, which carries a generic "New message" and the app then fetches the text. **Pushover**: $4.99 one-time after a 30-day trial. **Pushcut**: a free tier and a paid one (price table hard to read). Prices as of 4 Nov 2026.
- Do not offer a free-form shell command field in the app. It is a review risk and an injection surface; a URL or a service token is enough.

**What I would do, if the owner decides to go ahead:**
1. **A Mac banner for done and failed first** (already recorded direction). It stays on the Mac: nothing I found makes it reach the Watch, so do not promise that.
2. **Route 1 as the opt-in way off the Mac.** The researcher picks a service; Bristlenose sends one fixed sentence: "Analysis finished." or "The analysis didn't finish." No project name, no counts, no quotes.
3. **Test route 2 by hand once** (a fifteen-minute test on the owner's own devices), because if it works it is the only route that needs nothing installed.
4. **Hold route 3 until an iPhone app is wanted for its own sake.** A companion app that only forwards a ping is a poor reason to ship one; a companion that reads the study is a different product decision.

**The 15-minute test for route 2** (needs the owner's iPhone and Watch, nothing built): on the Mac, make a Reminder with an alert two minutes from now using the Reminders app, then lock the iPhone and watch whether it and the Watch alert. Repeat with the Mac asleep and with iCloud Reminders turned off, to learn the failure behaviour. This answers the three unknowns the research could not: latency, Watch delivery and the Mac-asleep case. It does not test our app's permission flow, which is the part reviewers will look at.

**Not established:** anything specific to macOS 27 beyond the release notes and one WWDC session; real latency for any route; whether any alarm reaches the Watch; behaviour with the Mac asleep; review precedent for using Reminders as a notification channel.

### 1. Mark a progressive report as partial, and say when it is complete

- **Wait:** a first analysis, minutes to an hour, for a researcher who has started reading.
- **Mechanism:** a known, finite wait feels better than an open one (Maister, essay); partial results are safe to read only if they are labelled (Procopio, Stolper). Beyond feelings, a researcher reading 3 of 8 sessions' quotes can mistake that for the full set. That is a validity risk, and it justifies the cue without any psychology.
- **Evidence:** medium for the principle (lab, seconds, students and MTurk). The validity argument stands on its own.
- **What appears:** one line in the Quotes lens header while a first run is live, in the voice of the existing status line: the count of sessions in, of the total. When the run completes, the line goes, and the lenses that were off light up; the same fact is said once, plainly, at that moment. The Sessions lens already shows partialness through greyed rows. Quotes does not.
- **Look:** an existing muted caption under the lens heading, reusing `sessionsCount` ("{{complete}} of {{total}}") rather than inventing a phrase. No new glyph or colour. See the mockup.
- **Honesty check:** the count is real (readable sessions from the lens-readiness data). It states what is true now and disappears when it stops being true. It does not predict. It is **not** an explanation of empty space, so it does not break "absence is information"; it states provisional status, which is news.
- **Cost and constraint:** about three new strings (21 locales), and the web page must learn the readable and total counts. The Sessions read already carries session states; whether the Quotes lens can use it without a new route is **unconfirmed**. Whether it counts as "trivial" under beta is question 1.

### 2. Make "~N min left" honest between stage boundaries

- **Wait:** transcription, the longest stage.
- **Mechanism:** HIG's "keep it moving; explain stalls" and "be as accurate as possible"; the general finding that people infer a hang from a display that stops changing (guidance only).
- **Evidence:** weak and contested. Tan and Nov found remaining-time displays raised frustration compared with elapsed time (10 to 60 s). No study tests revision direction. HIG is the strongest statement and it is guidance.
- **Observed 4 Nov 2026 (section 4.4): the figure is frozen between stage events, and on that run it was also 2 to 5 times too long.** The Mac passes the last received figure straight to the subtitle and never counts it down (`RunProgressMath.swift:186`; `SidebarSubtitleText.swift:99`), and the per-session events carry no estimate at all. A recorded 3-session run shows the displayed figure unchanged for up to 33 s while the true remaining time fell by half. One short run, not a long transcription; see the limits in 4.4.
- **Three honest options, in order of cost. My recommendation is (a), because the per-session events already exist and only the estimate is missing from them; (b) and (c) are fallbacks if (a) shows the figure jittering:** (a) re-emit the estimate each time a session completes (the data exists); (b) hold the figure but let it age visibly ("about 12 min left when transcription began"), which is true but clumsy; (c) drop "~N min left" during the stage and keep the count. The repo's `docs/design-progress-layer.md` (a proposal, not built) already designs hold, pad and ladder rules; this fits there.
- **Honesty check:** the current behaviour risks a number that is accurate at one instant and presented as live. The repair is a truth fix before it is a feel fix.
- **Owner of the code:** the Mac app and `timing.py` belong to other sessions. This is a pointer, not a patch.

### 3. Lens click: keep the heading while the chunk loads; delay the "Loading…" line

- **Wait:** click a lens, many a day, under a second.
- **Mechanism:** orientation, and avoiding a flash of text on reads that finish in 100 ms.
- **Evidence:** practice only. Under about 0.1 s nothing needs showing (Nielsen, citing Miller and Card, **not opened**). The "delay then show" pattern is common in libraries and unmeasured in the literature.
- **What appears:** the lens's own heading in the `Suspense` fallback instead of `null`, so the first visit is no longer blank; and the existing "Loading…" paragraph appears only if the read has lasted about 200 ms. Revisits that finish quickly show no loading line at all.
- **Honesty check:** nothing is invented; absence is the truth when the wait is short. The ledger's own instruction applies: baseline first (revisit p90 under 100 ms, first visit under 200 ms). If the baseline already passes, **do nothing**; this candidate then closes as "no cue needed", which is a valid result.
- **Related, already in the ledger:** a last-answer cache in `useLensRead` if the read dominates. That is an engineering change; show-the-last-answer is only honest while `data_version` is unchanged.
- **Constraint:** the ledger declines "keeping the previous web view dimmed" for the native lens switch, because that old view is torn down. This candidate does not revive it.

### 4. Elapsed time in the status line's tooltip

- **Wait:** the run.
- **Mechanism:** knowing how long it has been, without a promise about the future. In Tan and Nov, elapsed time frustrated less than remaining time (10 to 60 s).
- **Evidence:** weak; the scale is a minute.
- **What appears:** the existing tooltip, which already shows the full ladder, gains "running for 23 min." No new surface. Data exists (`run_progress.elapsed_seconds`, not yet read Swift-side).
- **Honesty check:** a fact, not a forecast. Cheap to be wrong about: low.
- Strings: one.

### 5. A "found so far" count in the status line

- **Wait:** quote extraction, the second longest stage.
- **Mechanism:** operational transparency in its honest form: real work shown as a count (Buell and Norton; Nielsen's "absolute work done").
- **Evidence:** medium for the mechanism. **Known backfire:** transparency lowered ratings when results were unfavourable (Exp 5). An early "9 quotes" from the first session could read as poor. Counts of unequal units can also be read as time.
- **What appears:** "Finding quotes · 4 of 8 · 112 quotes" in the status line, replacing "readable" at that stage or beside it.
- **Honesty check:** the count is real and the quotes are in the database. It does not predict. The risk is how it is read, not whether it is true.
- **Constraint:** reopens "no new in-progress messages", which the owner relaxed once for the readable count. Question 3.

### 6. A "taking longer than usual" line for an outlier call

- **Wait:** the worst case. The FOSSDA run had one 30-minute truncated quote call; LLM request p95 was 374 s against a median of 7 s.
- **Mechanism:** a stall explained is more tolerable than a stall unexplained (Maister, essay; HIG "explain stalls").
- **Evidence:** practitioner guidance only.
- **What appears:** only when a single call far exceeds its normal range: "Still finding quotes for one session." Nothing otherwise.
- **Honesty check:** true only if the signal is. It needs an event that carries a count or a timing and no session id (events are "counts and timings only"). Retry and truncation facts live in the privacy-restricted `llm-calls.jsonl`, which must not be the source.
- **Risk:** this is the most "needy" candidate. It passes "man bites dog" only because the normal case is silent. Rank low and decide only after seeing how often it fires.

### 7. Themes or topics on the timeline as they are found (the owner's example)

- **Finding:** **themes cannot honestly stream.** They are produced by one or two calls at the end of the run (27 s on FOSSDA) from all quotes. There is no earlier moment at which a theme exists.
- **What can be shown earlier:** per-session *topic boundaries*, made at stage 8 before quotes. They could be drawn as ticks on a session's tapestry strip as that session becomes readable.
- **Honesty check:** call them topics, never themes; do not imply that they will become the themes. Whether the tapestry has room and whether the topic data is stable enough to draw are **unchecked**.
- **Constraint:** a new feature, which beta advises against. I list it because the owner raised it, not because I recommend it now.

### Not a candidate: the 3 s study open

The boot bar has no words by decision. The measured wait is 3.1 to 3.2 s, within the window where HIG says a spinner is enough. Adding words was tried and removed ("the confusing text was removed"). Leave it.

## 6. How to measure whether a cue helps

The point is measure, change, measure. Perceived time is measurable, with caveats: this is formative work with a handful of people, to catch failures and compare variants. It is **not** statistics.

### 6.1 What to count, by wait

| Wait | Measure | Method | Good enough (proposed, unmeasured) |
|---|---|---|---|
| Lens click | Time to the lens's content, first visit and revisit | `interaction-profile.mjs`, prod bundle, two fixtures (already the ledger's step 1) | Revisit p90 ≤ 100 ms, first visit ≤ 200 ms. If met, no cue is needed. |
| The run, "is it working?" | Confidence it is working, 1 to 7, asked at fixed times | A prompt at minute 2 and minute 6 of a replayed run, two variants, within-subject | Median ≥ 6 at minute 6 in the cue variant, and not lower than today's |
| The run, "can I leave?" | Does the participant leave, and when do they return? | Observed; screen recording | The number of "check the screen" returns is no higher with the cue |
| Partial report (candidate 1) | **Comprehension**: after reading the Quotes lens mid-run, "Is this every quote that will be found?" | One question, yes/no/unsure | At least 4 of 5 answer correctly with the cue; the same question without it sets the baseline (expected: most say yes) |
| Duration judgement | Estimated minus actual, as a ratio | Ask at the end without a clock in view | Within ±25%. Report it, but weight it low: the literature on retrospective duration (Hui and Tse: perceived duration did not mediate reactions) says it is the weakest signal. |
| ETA (candidate 2) | Is the displayed figure within a stated band of what happens? | Log displayed figure each minute against actual remaining on 5 real runs | Never wrong by more than the larger of 25% or 2 min after the first third of the stage. Today's value is unknown; **this is the baseline to take first.** |

### 6.2 Procedure

1. **Baseline observation first (one hour).** Run a real 6 to 8 session job on this Mac. Record the status text every minute. Answers candidate 2's central question without any participants.
2. **Five-person think-aloud, two variants, counterbalanced.** Use a short fixture whose real run takes 6 to 8 minutes. `docs/mockups/progressive-lenses-replay.html` already replays real runs and can supply a stimulus. Participants are working researchers, ideally from the alpha cohort. Ask the same four questions in both variants: confidence at minute 2; whether they would leave; the Quotes comprehension question; what they think is happening.
3. **A diary question for the alpha cohort**, already proposed in `docs/design-llm-call-telemetry.md`: "the last long run: what did you do, did you check on it, did the estimate match?" Cheap, real, and at the real length.
4. **Do not ask about "speed."** Ask about knowing: do you know what it is doing, whether it is stuck, whether you can leave, whether you can trust what is on screen.

### 6.3 What would make a cue a failure

A cue fails if: confidence is lower than today's; participants look at the screen more; a participant says the number was wrong or it was "trying to look busy"; or the comprehension question is still answered wrongly. Any of these overrides a good duration estimate.

Five people can catch a cue that confuses. They cannot show that it works. The honest claim at the end is "no one was misled, and most knew," not "it felt 12% shorter."

## 7. Considered and rejected

| Idea | Why it is attractive | Why not |
|---|---|---|
| A progress bar that speeds up near the end | Harrison 2007: accelerating bars are judged faster | Dishonest pacing; HIG calls uneven pacing potentially "deceptive." |
| Invented percentages, or a smooth fake ring | Familiar and calming | The UI must tell the truth. The existing ring already creeps on overrun and caps at 0.92 for the same reason. |
| A deliberate delay so results "feel earned" | Labor-illusion work suggests perceived effort raises value | It is exactly the deception the authors flag, and it backfires on poor results. |
| Rotating verbs, a spinner with no data | Friendly | Theatre unless real counters sit beside it. |
| Skeleton screens for lenses | Common | Evidence mixed; they imply imminence; our lens waits are either too short to need them or too long for them. |
| A fade between loading and loaded (200 ms) | `design-motion.md` M7 lists it as not done | The doc's justification (Harrison 2010) does not support it. A fade may still be nice; the reason must be something else. |
| Dimming the previous lens during a switch | Continuity | Declined in the ledger: the old view is torn down. |
| A wait label for cloud-backed files | Researchers hit it | Settled and not reopened. |
| Words on the study-open bar | More explanation | Tried and removed. |
| An in-app chat lens with streaming | Streaming is the best-evidenced "proof of life" | Parked 4 Oct 2026; no UI exists. |
| A push of "about N min left" | The owner suggested it; useful for planning | An uncorrectable promise on top of an estimate that was 2 to 5 times off on the one run observed; see candidate A. Done and failed are in; this one is out until the estimate is trustworthy. |
| ChatGPT-style "thinking" summaries | Plausible in an LLM tool | We have no reasoning stream to show, and a summary we write would be invented. |
| A run view in the web report | Browser users see nothing | The product is the Mac app; question 6. |

## 8. Open questions for the owner

1. **Candidate 1:** is a one-line "N of M sessions" caption on the Quotes lens during a first run a trivial change under the beta rule, or a feature that waits? And is the validity argument (a researcher reading partial quotes as complete) enough on its own to justify it?
2. **Candidate 2:** the freeze is confirmed on a recorded run (4.4). Do you want option (a), re-emit the estimate at each session, which I recommend; or to age the figure; or to drop it during the stage? And should someone check the level error on a second run first?
3. **Candidate 5:** do you want to reopen "no new in-progress messages" for a quote count, knowing transparency can backfire when early counts are low?
4. **Candidate 7:** is a topic tick on the tapestry worth considering after beta? And is "topics, not themes" the right word?
5. **Candidate A:** done and failed on the Mac are recorded as post-TestFlight. You asked for them sooner, with phone and Watch reach. The research says there is no free forwarding; the cheapest route is a push service the researcher picks (route 1). Do you want the Mac banner pulled forward, and route 1 as the opt-in way off the Mac? I recommend both, no "about N min" push, and a fifteen-minute hands-on test of the zero-install Reminders route (route 2) on your own devices first.
6. **Web report:** a browser or CLI-serve user has no run progress. Is that out of scope, or should the status page carry the same line as the sidebar?
7. **Corrections to existing docs.** The claims in `docs/design-llm-call-telemetry.md` (upward revisions, Myers's tolerance) and `docs/design-motion.md` (Harrison 10 to 15%) are not supported by the papers. I did not edit them. Do you want a truing pass, with the design decisions kept and the reasons relabelled as hypotheses?
8. **Who runs the five-person comparison, and when?** The alpha cohort is the natural pool, and the replay mockup is a usable stimulus.
9. **Prior art.** Most entries were written from memory. Which, if any, do you want checked properly before they are cited anywhere else?

## Appendix: method and what was not verified

- Research: three agents each took a slice (waiting psychology; progress and response times; transparency and partial results); a fourth surveyed prior art; two read the code (run waits; in-app waits); a fifth, independent of the others, checked 19 claims against primary text (PDFs read with the macOS PDF text layer; scanned Myers by OCR).
- Not verified: Hui and Tse and Taylor beyond abstracts; Mejtoft 2018; Pavlov and colleagues (403); the Lin and Agarwal paper itself; Larson, Osuna, Katz, Zakay and Block; Doherty and Thadhani; Kahneman's original peak-end papers; Dellaert and Kahn and Nah beyond abstracts; Miller and Card; most prior art.
- The code audit is of HEAD plus a dirty tree. Its claims about runtime behaviour (a frozen estimate, a stalled-looking transcription, layout when a waiting row becomes readable) are from reading, not observation.
- Participant data: none used. Examples are synthetic.
- Mockup: `docs/mockups/perceived-wait-partial-report.html`. For scrutiny, not a spec.
