# Consequence storyboarding — reviewing a plan's *consequences*, not just its logic

> **Status: exploratory proposal, PARKED.** Not a committed feature. Captured 16 Jun 2026
> from the `background-runs-view-switch` (A1) review session, to pick up later. Describes a
> *method* (and a possible future agent/skill), not shipped behaviour — do not true against
> code.

## One line

A way to review the **consequences** of a plan — how its logic plays out across *sequence*
and *state* — rather than only auditing the plan's logic in the abstract. The user's framing,
verbatim: *"feels more like a real review of the **consequences** of a plan."*

## Origin

The vignette that prompted it (user's words, lightly preserved): the lost UX practice of
storyboarding on a whiteboard — *designers drawing out what they think the user should see and
want and expect, engineers shouting out problems with the sequence diagram that's forming in
their head, someone building a state engine, and everyone realising it's more complicated than
they first imagined.* The user's diagnosis of why it faded: **remote working + the
sub-specialisation of the tools** ("leave me alone, I need to migrate this to TypeScript";
"leave me alone, I need to create all the Figma tokens for this system").

What sparked capturing it: during the A1 review we built a hand-authored **state storyboard**
([docs/mockups/background-runs-view-switch-storyboard.html](mockups/background-runs-view-switch-storyboard.html)).
Authoring the *fixed* track of the rapid-switch race **frame-by-frame** surfaced that the
planned Step 2.5 fix was a no-op — `.cancel()` was being swallowed by `shutdown()`'s
`try? await Task.sleep`. A real concurrency bug caught **at plan stage, before any Swift was
written**. That is the proof of concept: the discipline of *following the sequence* revealed
what *asserting the logic* ("store + cancel the Task — done") had hidden.

Reframed: `/usual-suspects` reviews a plan's **logic** (does each finding hold?).
Consequence storyboarding reviews a plan's **consequences** (what actually unfolds, step by
step, across all the states). They compose — and together they're an async, single-person
reconstruction of that lost whiteboard room: the storyboard author plays the designer, the
review agents are the engineers shouting "but what about the race?", William is the parsimony
voice.

## The four objectives (user's words)

These were stated as one wish but are really **four different tools at increasing rigour and
cost** — keeping them separate is the whole game:

1. **Visualise engineering assumptions** so a human can check the **UX and the human
   psychology** — does the sequence match what a person expects and wants?
2. **Reveal, by following sequences, things that are not obvious when simply asserting logic**
   — the depth-on-one-path payoff.
3. **Force a rendering of all the combination states in the state machine** so a human can see
   how they'd actually render.
4. **Formally, exhaustively walk all the possible paths** to catch edge cases and race
   conditions.

The user's own note: *"it's a lot"* — yes, and the four don't collapse into one artifact.

## Objectives → the computer-science prior art

| # | Objective | What it is, formally | Prior art / term | Cost |
|---|-----------|----------------------|------------------|------|
| 1 | Check UX/psychology against assumptions | Narrated screen-flow + intent | **Design studio / event storming** (Brandolini); Cockburn use-case flows (main + alternate + exception) | Cheap, human |
| 2 | Sequence reveals what assertion hides | One **trace** through time | **Sequence diagram** (the dual of the state machine) | Cheap — *this is where our storyboard already paid off* |
| 3 | Render all combination states | The machine that *generates* all traces | **Statecharts** (Harel, 1987) — hierarchy + orthogonal regions; **XState** to run one. The "more complicated than imagined" wall has a name: **state explosion** | Medium |
| 4 | Exhaustively walk all paths | Search the full reachable state space for an invariant-violating trace | **Model checking** — Lamport's **TLA+**, Jackson's **Alloy**, SPIN/Promela; **model-based testing** (XState `@xstate/test`) | High — real formal methods |

Key relationships:
- **Sequence diagram ⟷ state machine are duals.** A sequence diagram is *one* path; the state
  machine is the *generator of all* paths; model checking is exhaustively walking the generator
  to find the path that breaks an invariant.
- The **rapid-switch race is the canonical model-checking target** — concurrent processes
  interleaving in an order a human didn't picture. Lamport built TLA+ precisely because humans
  are bad at this. We rediscovered, by hand, the bug class the field built a formalism for.

## The trap to never forget

Objectives 1–3 are achievable by **authoring** (human or LLM). Objective 4 — *exhaustive* — is
**not** achievable by an LLM "speedrunning paths": it enumerates only the paths it thinks of,
which is the exact limitation of a hand-authored storyboard, now wearing a costume of
completeness → **false confidence**. What caught our bug was **depth on one path + reading the
real code**, not breadth.

Therefore:
- Want **genuine** exhaustiveness (obj 4)? **Adopt prior art** — a ~40-line TLA+ spec of the
  subsystem, Alloy, or XState + `@xstate/test`. Steal the mechanism; don't rebuild a worse
  model checker.
- Want the **forcing-function** (objs 1–3, the part that actually paid off)? A bespoke
  agent/skill is defensible — but its job is "force rigorous, code-grounded authoring of the
  *concurrent/failure* paths," explicitly **non-exhaustive and labelled as such**. It must not
  cosplay as a checker.

## The recipe (the reproducible asset — the discipline, not the HTML)

1. **Author the success path frame-by-frame**, don't assert it as a sentence.
2. **Make the invisible state explicit at every transition** — selection, process states, PIDs,
   generation/epoch counters, in-flight async tasks, which sidecar is live.
3. **At every `await`/suspension point, stop and read the real code** and ask: *"does the thing
   I'm assuming actually hold here?"* (This is where obj-2 reveals hide — it's how we found the
   swallowed cancellation.)
4. **Cite `file:line` for every transition** so it's grounded, not vibes.
5. **Render the inconsistent/failure states as first-class frames**, not afterthoughts — they
   are where the *consequences* live.

The HTML scaffold (schematic UI left, invisible-state panel right, commentary + refs below,
step nav) is reproducible from these five lines. The discipline is the asset.

## Build decision (parked, with a calibration trigger)

Split the ambition in two and resist crystallising either yet:

- **(a) A skill that *builds* the storyboards** — premature at **n=1**, and the format isn't
  settled. Rule of Three not met. Capture the *recipe* (above) instead; the scaffold follows
  from it.
- **(b) An agent/engine that *runs + breaks* them** — that's model checking, and an LLM is a
  bad one (see "the trap"). Adopt prior art for real obj-4; bespoke only for the
  forcing-function.

**Trigger to revisit:** hand-run the storyboard on the next **1–2 features with real
concurrency or failure branching**. If by **n=3** we're copy-pasting the same scaffold and the
same prompts, *that's* the signal to crystallise a skill — and by then we'll know whether it
should wrap a real checker (TLA+/XState) or just be the forcing-function.

**Calibration question to answer by n=3:** which of the four objectives is each instance
actually delivering? (Working hypothesis: 1–2 pay off every time and cheaply; 3 sometimes; 4
≈never without real formal-methods tooling.)

## Open questions for later

- Does obj-4 ever justify standing up TLA+/Alloy for a Bristlenose subsystem? Candidate
  invariant-rich surfaces: the serve **switch choreography**; **pipeline resume / event
  sourcing** (`docs/design-pipeline-resilience.md`); **quote exclusivity** (every quote in
  exactly one section). Each is a place an exhaustive interleaving/constraint check could pay.
- Is **XState** worth adopting in the frontend regardless? The SPA already has ad-hoc state
  machines; if they were XState, objs 3–4 become nearly free for web flows (visualiser +
  `@xstate/test`).
- If we build the bespoke agent: input = a plan + state-machine sketch; output = authored
  frame-by-frame traces for the **concurrent/failure** paths only, every transition
  code-grounded, **flagged non-exhaustive**. Sibling to the `/usual-suspects` agents (this one
  reviews *consequences*; they review *logic*).
- Naming: "consequence storyboarding" is a working title.

## Artifacts from the originating session

- Plan: [.claude/plans/background-runs-view-switch-implementation.md](../.claude/plans/background-runs-view-switch-implementation.md)
- Review ledger: the branch's gitignored `/usual-suspects` review log (Finding 1 + the 16 Jun
  Step 2.5 refinement — the bug this method caught)
- Storyboard prototype: [docs/mockups/background-runs-view-switch-storyboard.html](mockups/background-runs-view-switch-storyboard.html)
  (rapid-switch race: current vs fixed)
