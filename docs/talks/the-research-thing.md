# The Research Thing — Research in the AI Era

**4 Nov 2026, 6:30pm — Google, 6 Pancras Square, London.**
Applied via the call for speakers; **application deadline: _(October — fill this in from the LinkedIn post)_**.

_Started 20 Sep 2026._

Twelve minutes, demo-led. Community event — no pricing, no business model, no
"get in touch". The crowd does this by hand and in Dovetail and is AI-native, so
every point lands once and moves on. Nothing in here is explained twice, and the
scripts are written to be said at pace.

---

## The application

The form wants four things. Drafts below — pick, cut, make them yours.

**Talk title.** Three options, in order of how much I would back them:

1. **Show your working** — short, memorable, and literally a feature: every
   signal card opens to the numbers behind it. Reads as a position in an AI-era
   lineup without being contrarian for its own sake.
2. **What it refuses to decide** — stronger position, slightly cryptic alone.
   Needs the description to carry it.
3. **The two days after the interviews** — names the audience's actual problem.
   Warmest of the three, least distinctive.

**Short description for your talk** (~100 words)

> A folder of interview recordings goes in. What comes out is a browsable report
> — quotes, themes, and the places where feeling concentrated — that you edit,
> hand over, and keep as a file.
>
> This is a working demo of Bristlenose, built over the last year for
> researchers under deadline. It runs the analysis through a frontier model, and
> the interesting design problems turned out to be the limits rather than the
> capability: what to show on a card, which quote earns the fourth slot, and the
> four things the tool will not decide for you.
>
> Mostly live. Some of it is even finished.

**What attendees will learn**

> - What a report looks like when the tool commits to one answer per quote and
>   lets you overrule it, rather than hedging across every possible reading.
> - A concrete method for surfacing where sentiment concentrates in a study, and
>   why the ratio matters more than the count.
> - How the editorial rules for cleaning a quote were written — what gets
>   removed, what is never touched, and why "dignity without distortion" is a
>   design constraint rather than a slogan.
> - Where the honest limits are: what runs on your machine, what goes to a
>   model, and the four things this tool deliberately will not do.

**Availability** — 4 Nov, yes.

---

## The build runway

Six weeks to 4 Nov. One slide describes logic that is **designed and measured,
not shipped**: slide 6, *How a card decides*. As of 20 Sep 2026 the card shows
one quote, orders quotes by participant and clock, and labels the sentiment chip
`Sentiment`.

`docs/design-signal-card.md` §0 names four generations of the card: **the app
ships generation 3, and slide 6 describes generation 4.** §9 has the build plan,
and **Tier 1 — the seven frontend changes carrying no open questions — is in
flight now.** Tier 1 alone changes what the demo looks like: the fused stack,
the heading owning the location, and four quotes open instead of one.

What slide 6 actually *argues* is Tier 2's **J** (the label rule — already
written and validated in `label_rule.py`, needing a server-side port so the
label is on the wire) and **I** (editorial quote selection, which depends on J
for sentiment cards). So the runway question is not Tier 1, which is happening;
it is whether J and I land.

- **J and I land.** Slide 6 becomes present tense, the status box comes off, and
  move 23 shows the real thing. Worth aiming at — J is a port of validated code,
  not new logic.
- **They don't.** Tier 1 still lands, so the card on screen looks right and
  shows four quotes; only the *selection* and the *label* are the old ones.
  Slide 6 stays as reasoning-in-progress, and you say so at move 23.

**Take a view by mid-October**, not in the week of the talk, because the
rehearsal depends on which card is on screen — and because the difference is one
sentence in the script, not a restructure.

> **⚠️ Status check before you present.** If J and I have not landed, slide 6 is
> design, not behaviour. Check `docs/design-signal-card.md` §9 for
> what has landed since, and say so at the signal-card beat. Every other slide
> describes behaviour that ships today.

---

## The rig

Slides and the app live on separate Spaces and you move between them all night.
Get this wrong and the talk dies in a way no amount of content rescues.

**Five Spaces, left to right, in demo order:**

| Space | What | Why it is its own Space |
|---|---|---|
| 1 | Slides | Keynote **in a window, fullscreened** — not presenter mode (see below) |
| 2 | Browser | the website, then Miro, then the exported report |
| 3 | **BN-A** — fresh install, no projects | the install payoff and the drag-and-drop |
| 4 | **BN-B** — a completed study, Quotes lens | the cut from "analysis started" to "analysis done" |
| 5 | **BN-C** — same study, Codebook lens, already run | the cut from "codebook running" to admit/deny |

BN-B and BN-C are **two windows of the same app on the same project**, seeded to
different lenses. The app supports this natively — `WindowGroup(id: "main", for:
WindowSeed.self)` in `BristlenoseApp.swift:144`, and ⌥⌘N carries a project and
lens seed. Open both before you start and fullscreen each one.

**Finder is not a Space.** Keep one Finder window floating over Space 3 with the
prepared session files in it, and drag from that window straight onto the app —
which is how a researcher actually does it, so the demo is more honest as well
as one Space shorter.

**Four settings to change before the night.**

1. **Turn off "Automatically rearrange Spaces based on most recent use"** —
   System Settings ▸ Desktop & Dock ▸ Mission Control. This is the one that ends
   demos. Leave it on and macOS reorders your Spaces as you use them, so the
   Space that was on your left is somewhere else by the third swipe and your
   muscle memory is now wrong in front of an audience.
2. **Enable Ctrl+1 … Ctrl+5** — System Settings ▸ Keyboard ▸ Keyboard Shortcuts
   ▸ Mission Control ▸ Switch to Desktop N. They are off by default past the
   first couple. Jumping to a numbered Space beats swiping three Spaces to the
   left, every time.
3. **Slides in a window, not presenter mode.** Keynote's presentation mode takes
   over a display and makes Space switching behave differently depending on how
   the projector is configured. Play in Window, then fullscreen that window, and
   it is just Space 1 like everything else — predictable, and Ctrl+1 always
   works.
4. **Rehearse with the projector attached.** "Displays have separate Spaces"
   changes Space behaviour, and you cannot discover that on the night. If you
   can, rehearse in the room.

**The Excel beat: use Quick Look.** Select the exported `.xlsx` in the Finder
window and press space. It renders the sheet in about a second and costs you no
Space and no app launch. Opening Excel is a 6th Space, a bouncing dock icon, and
whatever that machine's Excel decides to do about licensing in front of ninety
people.

---

## The three cuts

The demo starts three things that take minutes and shows you the finished
version of each. That is the only way this fits, and it is a completely standard
demo move — as long as you say so.

| Cut | You start | You swipe to | Skips |
|---|---|---|---|
| 1 | the install | Space 3, installed | a download and a first launch |
| 2 | drag and drop, analysis begins | Space 4, a completed study | minutes of transcription and analysis, and the model spend |
| 3 | run a codebook | Space 5, codebook already run | an AutoCode pass |

**Say "here's one I prepared earlier" every time.** A cut costs four words and
nobody minds. Being caught having skipped one silently costs the room.

**Never run a live analysis on stage.** Minutes of wall clock, real money, and a
network you do not control. Cut 2 exists precisely so you never have to.

---

## Ready by end of October

The talk is the soft launch. Three channels live with a "try now", a website
that stands up to a researcher clicking through it, sample data worth showing,
and the deck nailed. Everything below lands by **31 Oct** — with one deliberate
exception that must land *later*.

| Workstream | Done by | Note |
|---|---|---|
| Signal-card build decision | **10 Oct** | Tier 1 + J + I, or not. The demo rehearsal depends on which card is on screen |
| Sample data — a purpose-built demo study | **17 Oct** | see below; this is the long pole |
| Website spruce, three install paths visible | **24 Oct** | separate private repo; the rsync deploy is manual and needs agent access |
| TestFlight build uploaded | **24 Oct** | 90-day clock from upload — comfortably covers 4 Nov |
| Deck built from this file, visuals made | **28 Oct** | eight faces, eight visuals |
| Full rehearsal on the rig, with projector | **31 Oct** | the whole thing, clocked, twice |
| **Notarised `.dmg` built** | **1–3 Nov** | **deliberately last — see below** |

**The `.dmg` expiry is a trap and it is worth setting an alarm over.** The alpha
`.dmg` expires **30 days from the build**, not from the download. Build it during
the October readiness push and it dies in the first week of November — which is
exactly when a room of researchers who just watched the demo go home and try it.
Build it in the two or three days before the talk. TestFlight runs on a
different clock entirely (90 days from upload), so that one is safe to do early
and should be, because App Store Connect processing is not something to discover
under deadline. Both clocks are mapped in `docs/release-channels.md`.

**The sample data is the long pole, and the obvious candidates do not fit.** The
demo needs a study that is UX-shaped (so it produces sections *and* themes, and
the Quotes lens reads as a journey), large enough that signal cards concentrate
honestly, free of client and participant confidentiality, and stable enough to
rehearse against for two weeks. The fossda corpus is ten sessions but oral
history — it produces many themes and few sections, which is the tool working as
designed and the wrong shape for this demo. The two-session demo fixtures
concentrate nothing. **Budget real time for building a study you are happy to
put on a projector at Google**, because a thin corpus makes the Signals lens
look like it is not working, and that is the beat the whole back half rests on.

**What "try now" means on the night.** Three paths, and the website has to make
the choice obvious rather than complete: the Mac app via TestFlight, the
notarised `.dmg` for people who will not do TestFlight, and the CLI via PyPI,
Homebrew, Snap or Fedora Copr. The CLI is already live on all four and needs
nothing but accurate install copy. Remember the Homebrew trust wording — the
fully-qualified `brew install cassiocassio/bristlenose/bristlenose`, never the
short name, which is refused for exactly the people being told to run it.

---

## The run sheet

Twelve minutes. Seven slides and eighteen demo moves, interleaved. Print this.

Slides are `##` headings below, in delivery order, each with its face, its
visual, a script budgeted in seconds, and backup for the questions.

| # | Space | Move | Dur | Clock |
|---|---|---|---|---|
| 1 | 1 Slides | **S1 — What you start with** | 0:20 | 0:20 |
| 2 | 2 Browser | the website | 0:25 | 0:45 |
| 3 | 2 Browser | start the install | 0:20 | 1:05 |
| — | → **cut 1** | *"here's one I prepared earlier"* | — | — |
| 4 | 3 BN-A | installed, no projects | 0:15 | 1:20 |
| 5 | 1 Slides | **S2 — Where the words go** | 0:20 | 1:40 |
| 6 | 3 Finder | the prepared session files | 0:20 | 2:00 |
| 7 | 3 BN-A | drag and drop — analysis begins | 0:30 | 2:30 |
| — | → **cut 2** | *"and here's that one, finished"* | — | — |
| 8 | 4 BN-B | a completed study | 0:15 | 2:45 |
| 9 | 1 Slides | **S3 — Dignity without distortion** | 0:25 | 3:10 |
| 10 | 4 BN-B | quotes, by section and theme | 0:35 | 3:45 |
| 11 | 4 BN-B | add a manual tag | 0:30 | 4:15 |
| 12 | 4 BN-B | show previously tagged quotes | 0:20 | 4:35 |
| 13 | 4 BN-B | run a codebook | 0:25 | 5:00 |
| — | → **cut 3** | *"same study, already run"* | — | — |
| 14 | 5 BN-C | the pre-run codebook | 0:15 | 5:15 |
| 15 | 5 BN-C | admit and deny | 0:45 | 6:00 |
| 16 | 5 BN-C | quotes filtered by tag | 0:30 | 6:30 |
| 17 | 5 BN-C | export, with anonymise | 0:30 | 7:00 |
| 18 | 3 Finder | Quick Look the spreadsheet | 0:25 | 7:25 |
| 19 | 2 Browser | the quotes in Miro | 0:25 | 7:50 |
| 20 | 2 Browser | the exported report, `file://` in the bar | 0:20 | 8:10 |
| 21 | 1 Slides | **S4 — Why the report is a file you own** | 0:25 | 8:35 |
| 22 | 1 Slides | **S5 — What a signal is** | 0:25 | 9:00 |
| 23 | 5 BN-C | signal cards, open the working | 0:40 | 9:40 |
| 24 | 1 Slides | **S6 — How a card decides** | 0:35 | 10:15 |
| 25 | 1 Slides | **S7 — What we don't do** | 0:25 | 10:40 |

**10:40, so 80 seconds of slack in twelve minutes.** That is a real margin
rather than a rounding error, and it exists because the scripts are written to
be said at pace with no point made twice. Spend the slack on the demo, not on
the slides — if a script feels rushed in rehearsal, cut a clause rather than
borrowing time from a move.

**The cut ladder, in order, when you are behind.** Decide these now, not on
stage. Drop move 12 (show previously tagged, −0:20). Then move 19 (Miro, −0:25)
— it is the most impressive twenty-five seconds and the most expendable, because
the spreadsheet already made the point. Then shorten move 15 (admit and deny) to
0:30. That is 1:10 recovered without losing a slide or an argument.

**What is deliberately not in here.** *What's in the report* — a map slide
naming the four lenses — was written and cut. With the demo touring every lens
in order, it spends thirty seconds telling the audience something the next eight
minutes shows them. It would slot at move 2 if the slot ever grows past twelve
minutes, and it is the first thing to add back for a longer version of this talk.

**Two moves that carry the most risk.** Move 7 is a live drag and drop; if the
window is not where you expect, you are hunting for it on stage. And move 17 is
a real export writing a real file to disk, which move 18 then opens — so if 17
silently fails, 18 has nothing to show. Rehearse both from a cold app.

---

## What you start with

A folder of recordings and a deadline.

Audio, video, subtitles, or transcripts you already have.

**What you end with is a report you can edit, hand over, and keep as a file.**

**Visual** — a Finder window, full-bleed, the prepared session files listed.
Nothing else. No arrow to a report; that is move 20's job.

**Script — 0:20**

> A folder of recordings and a deadline. The fieldwork is not the hard part —
> the two days after it are.
>
> This reads that folder: audio, video, subtitles, or transcripts you already
> have. What comes back is a report you edit, hand over, and keep.

**Backup**

Formats: the usual audio and video containers, `.srt`, `.vtt`, `.docx`. An
existing transcript skips transcription.

**"How many sessions?"** Three to fifteen. Under three, nothing concentrates and
slide 5 stops meaning anything.

---

## Where the words go

**Transcription runs on your machine.**

**The analysis is a call to Claude, ChatGPT, Azure OpenAI or Gemini** — your
account, your key.

Redaction runs before that call, if you turn it on.
Consent and retention stay your job.

**Visual** — two equal boxes. Left *your machine*: waveform becoming text. Right
*the model*: text becoming quotes and themes. One arrow labelled **the
transcript**. Equal sizes — a bigger left box is an argument this slide is not
making.

**Script — 0:20**

> Where the words go. Transcription runs on your machine — the audio does not
> leave. The analysis is an API call to Claude, ChatGPT, Azure OpenAI or Gemini.
> Your account, your key.
>
> Optional redaction before that call. Consent and retention are still yours.

**Backup**

Whisper-class model locally; frontier model for the analysis. **Ollama** is
supported — slower, wants a capable machine, real quality gap on quote
extraction. An option, not the better choice.

**Redaction** is opt-in, off by default: Presidio over the transcript before the
call, removing names, emails, phone numbers. Convenience, not a guarantee.

**"Is this training the model?"** No — standard API calls. If pushed: that is
the provider's contractual commitment, not something the tool enforces from your
laptop.

**Retention** is not managed and does not pretend to be.

---

## Dignity without distortion

Participants should look articulate without having their words changed.

**Gone:** um, uh, filler "like", filler "you know"
**Kept:** self-corrections, `[laughs]`, `[sighs]`, the tone
**Bracketed:** every word the participant did not say

> The participant sounds like themselves on a good day.

**Visual** — the one worth the most effort. One real quote twice, stacked: raw
transcript line on top with filler struck through in grey, cleaned quote below
at full contrast, `[bracketed]` insertion in the accent colour. Two build beats
if the deck allows.

**Script — 0:25**

> Does it change what people said? No.
>
> Filler out, and it marks the cut. Self-corrections stay — "no wait, I mean the
> other one" is the data. Meaning and tone untouched. Anything the participant
> did not say is in brackets.
>
> The rule: they sound like themselves on a good day.

**Backup**

Seven rules. Filler becomes an ellipsis so the cut is visible. Clarifying words
bracketed: "the thing" → "the [settings page]".

**The limit.** Same model does the cleanup, so it can get one wrong. Every quote
is editable inline against the transcript, timecode beside it — one click from
the quote.

---

## Why the report is a file you own

One HTML file. Any browser. No login, no account, no Bristlenose.

**You edit in the app. You export what you hand over.**

The export is read-only, and can travel without participant names.

**Visual** — the exported report in a browser, address bar showing
`file:///Users/…/Downloads/`, legible from the back. Circle it. No diagram, no
cloud icons.

**Script — 0:25**

> A spreadsheet, a Miro board, and that — one HTML file. Any browser, off a
> disk, offline. Nobody installs anything.
>
> You edit in the app, you export what you send. Read-only on purpose: what a
> participant said should not drift after you have signed it off. And the names
> can come off on the way out.

**Backup**

Self-contained HTML, data embedded. Drops into SharePoint or Drive like any
document.

**Anonymisation** strips participant names from labels, metadata and filenames,
leaving p1, p2. Moderators and observers keep theirs. **Names spoken inside a
quote are not removed** — a narrative control, not a safety one.

**If asked what it costs or how to get it** — one factual sentence, then move.

---

## What a signal is

Frustration is 12% of everything said in this study.
In Checkout it is 38%.

**Three times what you would expect. That is the signal.**

**Who?** — eight people, or one person eight times
**How hard?** — a murmur, or a shout

**Visual** — two horizontal bars on one axis. Top pale, *the whole study — 12%*.
Bottom in the frustration colour, three times as long, *Checkout — 38%*. No
axis, no gridlines, no legend.

**Script — 0:25**

> Across the study, frustration is twelve per cent of everything said. In
> Checkout, thirty-eight. Three times what you would expect — that is the
> signal.
>
> Then: who? Eight people, or one person eight times. That is agreement. And how
> hard — a murmur or a shout. Intensity.
>
> Concentration, agreement, intensity. Here is what that looks like.

**Backup**

**Substitute real numbers.** Use the card from move 23 — the audience sees that
figure forty seconds later and it should match.

**Agreement** is Simpson's diversity index. **Intensity** is the mean on a 1–3
scale. Both open under the disclosure at move 23.

**Why a ratio, not a count.** A count rewards whichever section had the most
talking.

**"Is this significance testing?"** No. Descriptive, no p-value, no inference —
which is one of the four on the last slide.

---

## How a card decides

**The name.** It is the *amount* of feeling that decides, not the balance.

Three negative to one positive, on a handful → **Mixed sentiments**
Eighteen to twelve, across a lot of them → **Frustration**

**The quotes.** Four shown, of up to fifty.
Three that carry the finding. One held back for someone who disagreed.

**Visual** — one card, large, two annotations: a line to the chip reading *the
name*, a line to the fourth quote reading *the dissenter*. Card from
`docs/mockups/signal-card-design-a.html` §4; `signal-card-rules.html` draws both
rules firing. Grey the first three quotes so the fourth reads as different.

**Script — 0:35**

> Two decisions there, and both are counterintuitive.
>
> The name: it is the amount of feeling that decides, not the balance. Three to
> one on four quotes is a coincidence — we call that mixed sentiments. Eighteen
> to twelve across fifty is a finding, and we call it frustration.
>
> And the quotes: four of maybe fifty. Three that carry the finding, one held
> back for someone who disagreed and said it with force. A card that only agrees
> with itself is a card you stop reading.

**Backup**

**Check the status box before delivering this.** If J and I have not shipped,
this is the design — Tier 1 alone gives the right-looking card with the old
label and old selection — and you say so at move 23.

**Why refuse.** "Mixed sentiments" means *inconsistent, worth investigating*,
not *the numbers were close*. A named feeling is actionable, so the card names
one where it honestly can.

**Why a small minority does not flip it.** In ten interviews two or three people
are confused about something whatever you build. Friction inside a good result
is the normal condition.

**What it replaces.** Participant-and-clock order, which is not neutral: on a
fifty-quote card you saw whatever the first participant said early.

**Measured.** Cards with no visible quote supporting the label: 3 → 0. Cards
showing a dissenting voice: 13 → 16.

**How we know.** Fitted to 27 judgements on real cards, label hidden. Small, and
mostly short test sessions. The shape is right; the cut-off will move.

**Open.** The dissenter is picked on force, because force is the only thing
measured per quote. Clarity is what we would rather use.

**"What about surprise?"** Neither good nor bad, so it never makes a card mixed.

**"Can I see the rest?"** Yes — four at rest, the whole set one click away.

---

## What we don't do

**No synthesis.** It organises quotes. It does not write your findings.
**No ranking.** Nothing is ordered by importance. You decide what matters.
**No recommendations.** It shows what people said, not what to build.
**No statistical claims.** "Four of six mentioned this" is an observation.

> One best guess, with its working shown, and every guess yours to overrule.

**Visual** — text only. Four lines, generous leading, the closing line set
apart. Every other slide earned a picture; this one is a statement.

**Script — 0:25**

> What it will not do. It will not synthesise — you write the findings. It will
> not rank, because importance depends on your questions. It will not recommend.
> And it makes no statistical claims: four of six is an observation about six
> people.
>
> One best guess, working shown, every guess yours to overrule.

**Backup**

Non-goals, not a backlog.

**The fourth is the sharp one.** Counts and percentages are descriptive — an
observation about six people, not an inference about a population. Which is why
slide 5 is a ratio rather than a test.

**The permanent one, if there is breath.** Quotes combined with study metadata —
sector, company size, client type — will never be collected. Re-identification
from that is a short walk. Level 4 in `docs/methodology/consent-gradient.md`,
written as "will not be offered".

---

## Still outstanding

- **The CFP deadline.** The form does not state one and the LinkedIn post is
  behind a login. Fill it in at the top of this file, and apply well before it.
- **Sample data — the long pole.** A UX-shaped study, big enough to concentrate,
  free of client confidentiality, stable enough to rehearse against. Neither
  fossda (oral history) nor the two-session fixtures will do. Target 17 Oct.
- **Real numbers on slide 5.** The 12% / 38% are illustrative; substitute the
  card you will actually show at move 23.
- **The visuals are specified, not made.** Eight descriptions, no assets. Slide
  3's before/after quote and slide 4's `file://` address bar carry the most
  weight; the rest degrade acceptably to text.
- **Slide 6's tense**, which follows the build decision due 10 Oct.
- **A clocked rehearsal on the real rig.** The scripts are written at 140 words
  a minute and the run sheet has 25 seconds of slack. Both are assumptions until
  you have run it twice with the projector attached.
