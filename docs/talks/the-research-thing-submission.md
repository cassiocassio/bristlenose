# The Research Thing — speaker submission

**Research in the AI Era: Stories of experimentation, operationalisation,
successes and failures · Wednesday 4 Nov 2026 · Google, 6 Pancras Square,
London · doors 6:30pm, talks from 7pm, networking until 9pm.**

Paste-ready answers for the Google Form, and nothing else. The run sheet, the
rig, the three cuts and the slides are in
[`the-research-thing.md`](the-research-thing.md).

_Written 28 Sep 2026 against the LinkedIn post and the form, read that morning._

**Deadline: end of September 2026.** Shortlisted speakers are contacted by
early October. Speakers must attend in person.

---

## The brief, verbatim, because the answers are shaped by it

> We want to hear real stories from researchers and research-adjacent
> practitioners navigating AI in their work — not just polished success
> stories.
>
> Talks should ideally:
> - Be 15–20 minutes (excluding time for questions)
> - Share real-world stories detailing how you worked with AI to solve
>   specific product challenges and the value it delivered.
> - Evolving research roles and challenges: how has AI changed the way you're
>   working or the challenges you're solving
> - Celebrate Learning from Failures: we want to hear about the experiments
>   that didn't go as planned, the happy accidents and what you learnt from
>   them.
> - Focus on practical AI workflows rather than specific tools, highlighting
>   methods that attendees can realistically apply using widely available AI
>   capabilities in their own day-to-day work.

Two consequences. **The talk is a story with a demo in it, not a demo.** The
tool is the vehicle; the thing on offer is the rules that came out of building
it, every one of which works with the AI the audience already has. And **the
failures are the content, not the caveats** — the calibration that ran on data
too thin to mean anything (`docs/design-signal-card.md` §5a), the transcriber
that hears "Thank you." in silence (0.31.4), and the four things the tool was
told it must never do.

---

## The form's fields

**Your full name** — Martin Storey

**Current Role and Organisation** — not in the tree; yours to fill. The shape
that fits the brief: *User researcher, ‹organisation› · maker of Bristlenose
(open source)*.

**Your contact details (email address)** — as entered.

## Talk title

**I got frustrated with my AI, so I made it show its working**

Completes the line already typed into the form. Two alternates, if that one
reads as too much of a slogan on the night's programme:

- **I got frustrated with my transcripts, so I built the tool I wanted** — the
  origin story, plainer, says less about AI.
- **I got frustrated with my AI, so I taught it when to say "I don't know"** —
  sharper and narrower; it is the one rule on slide 6, not the whole talk.

## Short description for your talk

> I'm a practising user researcher, and the two days after fieldwork are the
> part I dread: a folder of recordings, a deadline, and an AI that will happily
> write my findings for me if I let it. So over the last year I built
> Bristlenose, an open-source tool that turns that folder into a report I edit
> and own — and made the AI show its working.
>
> This is the story of what went wrong on the way — a calibration run on data
> too thin to mean anything, a transcriber that hears "Thank you" in silence, a
> model that hedges when it should commit — and the rules that came out of it:
> which quote earns a slot, when to name a feeling, what to refuse to decide.
>
> None of it needs my tool. Every rule works with the AI you already have.

## What attendees will learn from your talk

> - A workflow for the two days after fieldwork that keeps the researcher in
>   charge: the AI proposes, every quote lands in exactly one place, and every
>   proposal is yours to overrule.
> - Editorial rules for AI-cleaned quotes you can paste into any prompt —
>   filler out and the cut marked, self-corrections kept, every added word in
>   brackets — so participants sound like themselves on a good day without a
>   word being changed.
> - How to make an AI claim show its working: a ratio rather than a count,
>   naming a feeling on the amount of evidence rather than the balance, and
>   holding one of four quotes for the person who disagreed.
> - What went wrong and what it taught: calibrate on data shaped like your real
>   studies rather than fixtures, expect a transcriber to invent politeness in
>   silence, and decide up front what the AI must never do — for me, synthesis,
>   ranking, recommendations and statistical claims.

## Availability

> Yes — I can attend in person on Wednesday 4 November, 6:30pm, at Google,
> 6 Pancras Square.

---

## What this changes in the run sheet

- **Length.** The brief says 15–20 minutes excluding questions; the run sheet
  is built for twelve with 80 seconds of slack. The map slide, *What's in the
  report*, comes back first (it was cut for time and the sheet says so), and
  the story beats the description promises — the wrong-regime calibration and
  the silent-audio "Thank you." — need a home, most naturally under slides 6
  and 2. Re-time after shortlisting, not before.
- **Frame.** The brief asks for methods over tools. The demo stays; the script
  around it changes from *here is what it does* to *here is the rule, and here
  is what it looks like when it runs*. Every slide already carries a rule, so
  this is a rewording of the scripts, not a restructure.

## Superseded

The first draft of this file (same day, before the post and the form were
read) titled the talk *Show your working* and pitched it as a demo. It is in
git history; the title survives as the second half of the one above.
