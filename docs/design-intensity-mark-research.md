# The intensity mark: what it is, and the space around it

Status: **decided 5 Nov 2026: the gentle cone (§8). Exploration began 30 Oct 2026.** The owner's brief: the three circles
beside a quote are too close to carousel dots, and should be "a bit more graphically interesting
and readable". The instruction for this stage: explore the space first, don't jump to solutions.
This note defines the thing being drawn, catalogues analogues in the world, and states the
questions a drawing has to answer. A mockup of directions follows only once the owner has read it.

## 1. What "intensity" is in Bristlenose

**A per-quote grade of how strongly the speaker expresses the feeling already named.** The LLM
assigns it at quote extraction, `1` mild, `2` moderate, `3` strong
(`bristlenose/llm/prompts/quote-extraction.md:65`; stored as `intensity: int` on the quote,
`models.py:425`). Four properties follow, and each constrains the drawing.

1. **It modifies a sentiment; it is not a sentiment.** "Frustration" is the label; intensity says
   how hard. A quote with no emotional content has no intensity. So the mark is a *companion* to
   the sentiment badge, never a stand-alone fact, and it carries no valence: a 3 can be delight
   or frustration. The mark must therefore stay neutral in hue (it takes `--dot-colour`, muted in
   paragraphs) and must not borrow the red/green of good and bad.
2. **It is ordinal, three levels, and low-resolution on purpose.** The model grades coarsely
   because a transcript is weak evidence of how strongly someone felt. Anything that draws a
   fourth distinction (a smooth gradient, a 0 to 100 gauge) claims precision the data lacks.
3. **There is no zero.** The scale starts at 1 (mild), not 0. "Mild" is still a feeling. A row of
   three that can show all-empty would suggest a level 0 that does not exist. The one-of-three
   state must read as *something*, not as *nearly nothing*.
4. **Aggregates are real numbers.** The chart's "Emotional intensity" metric is a *mean* over a
   signal's quotes (`Signal.mean_intensity`, `docs/design-finding-weight.md`), so it takes values
   like 1.4 or 2.6, drawn today to the nearest half. And "intensity" is one factor in signal
   strength (concentration x agreement x intensity), so the same mark appears at two scales:
   a single quote's whole number, and a signal's mean.

### What it is *not*: the wording trap

In the research literature "intensity" is used for at least three different things, and a
researcher reading our mark will import whichever they know:

- **Arousal / activation** (Russell's circumplex, valence on one axis, arousal on the other).
  Often glossed as "the intensity of the state", but the literature does not agree that intensity
  *is* arousal: a stimulus can be intense because it is high-arousal or because it is extremely
  positive or negative. Our grade is closest to a *vector* reading, the magnitude of the feeling
  whichever way it points (see the vector-versus-circumplex finding below).
- **Intensity as magnitude within an emotion family** (Plutchik: serenity, joy, ecstasy;
  annoyance, anger, rage; always three steps from the rim to the centre). **This is the closest
  prior art to our scale**, three named steps per family, and it is a useful reminder that the
  steps are *qualitatively different words*, not three amounts of one thing. "Annoyed" and
  "furious" differ in kind of expression, not just quantity.
- **Frequency or volume of a theme** (how many people said it). That is *concentration* in our
  vocabulary, a different metric. The user-research habit of tagging themes High/Medium/Low
  "intensity" alongside frequency is the nearest practitioner convention, and it separates the
  two.

How a working researcher hears the word, then: *"how strongly did they feel it"*, not *"how much
of it was there"*. The glossary and tooltip should keep to the first. The tooltip key is
`signals.intensityTooltip`, "Intensity {{value}}/3".

### Questions the mark has to answer

Stated as design constraints, not as solutions.

- **Q1. Which of three?** Can a reader tell 1 from 2 from 3 at a glance, at about 46 x 12 px
  beside 15 px body text, in WebKit and Chromium, light, dark and the Edo palette?
- **Q2. More than, or just different?** Is the order obvious without a legend (a bigger / fuller
  / taller thing is more) or does it rely on convention?
- **Q3. Is it one thing or three things?** Three separate shapes read as a *set of three
  objects*, which is exactly what a pager is. One continuous gesture (a bar that grows, a wave
  that swells) reads as *one quantity*.
- **Q4. What does 1 look like?** Mild must not look like empty, absent or disabled.
- **Q5. How does a half value draw** without a new element, for the chart mean?
- **Q6. Is it quiet?** It is a secondary mark, not a control, and ghosts in focus mode.
- **Q7. Does it survive a glance sideways?** The words flow around it at the top right of a
  paragraph; it has to be recognisable as a unit and not as punctuation or a bullet.

## 2. The collision, stated precisely

The page indicator is the strongest, most learned pattern for "a short row of small identical
circles with one or some different". Two concrete sources in this repo:

- The Welcome rotator's indicator, five capsules (`WelcomeDegradationLab.swift:569`): the current
  one is long and bright, the others short and faint.
- The generic carousel dots users meet everywhere (iOS page control, web sliders).

What makes the pattern read as a *pager* is (a) several identical shapes, (b) in one row, (c)
at roughly the same size, (d) with **position, not amount**, marked by the one-different item.
Our circles satisfy (a) to (c) and invert (d): *how many* are filled is the value. The collision
is not the circle itself; it is the **identical-shapes-in-a-row-with-one-state-flag** grammar,
which holds for a ring of three squares or three pills just as well. That distinction matters for
the exploration: swapping circles for squares moves the shape but not the grammar.

The things that break the grammar are (i) shapes that are not identical (graded in size, height or
angle), (ii) one connected form rather than three, (iii) a glyph with its own meaning.

## 3. Prior art: the signal-strength family

### Signal bars (cellular, and the many things that borrow them)

- Bars are a display of *received signal strength* (RSSI, measured in decibels, a logarithmic
  scale), a physical quantity squeezed into a handful of steps. Similar indicators appeared on
  radio receivers in the 1930s; the phone convention came with the first mass-produced handsets
  in the 1980s ([A Little History of the Wireless Icon](https://medium.com/palais-des-beaux-arts-wien/a-little-history-of-the-wireless-icon-b50741b01da6)).
- **What bars do well:** *height itself encodes the order* (taller = more), the shape is one
  recognisable gestalt (a rising staircase), unfilled bars stay visible as the ceiling, and it is
  among the most-seen icons on earth, so "more bars = better/stronger" needs no legend.
- **Caveats the field itself documents:** the mapping from reading to bar count is arbitrary and
  has been changed by vendors (Apple remapped it between iOS releases; thresholds are ours to
  choose, e.g. 1 bar for -90 to -110 dBm). The icon says *quantity of signal* and people read it
  as *quality*. The Wi-Fi fan, by contrast, mostly shows the *presence* of a network. Both are
  reminders that a familiar glyph imports its meaning ("good connection") along with its shape.
- **The big risk for us:** signal bars connote *more is better*. Intensity is valence-free:
  a three-bar frustration quote is "bad", and the glyph would suggest "good".
- Convention for state: solid when active, muted outline when unavailable
  ([Colossal on tech symbols](https://old.thisiscolossal.com/tech-symbols-explained-a-guide-to-icons-and-their-meanings),
  secondary).

### The same idea in other interfaces

| Cue | Where | What it encodes | Worth borrowing | Watch out for |
|---|---|---|---|---|
| Signal bars | phone status bar | strength, 4 to 5 steps | height as order, one gestalt | "more = better" valence |
| Wi-Fi fan | status bar | strength by arcs | concentric, directional | arcs are hard at 12 px |
| Battery | status bar | capacity | a container that fills; ceiling visible | reads as *remaining*, a depleting quantity |
| Volume / speaker waves | OS, media | loudness | *loudness is the closest metaphor to emotional intensity* | speaker glyph carries its own icon meaning |
| Level indicator (discrete) | macOS | capacity / rating / relevance | segments fill whole, never partially ([Apple HIG, gauges](https://developer.apple.com/design/human-interface-guidelines/gauges.md)) | Apple warns discrete segments for large ranges; 3 is ideal |
| Rating indicator | macOS, App Store | rating as stars | known, whole values | stars mean *quality*; HIG rounds to whole symbols |
| Equaliser / VU meter | audio | level per band | bars of varying height as energy; rises and falls | needs several bars to read |
| Waveform | audio, voice memos | amplitude over time | **it is literally the amplitude of speech**; resonates with a transcript | looks like audio playback, may suggest a clip |
| Harvey ball | consulting slides | 0 to 4 completion/fit | one glyph, quarters; legible in greyscale ([overview](https://www.insightsoftware.com/encyclopedia/harvey-balls/)) | angle/area judgement is weak (below) |
| Pain faces | clinical | self-reported pain, 6 faces | non-verbal, fast ([Wong-Baker overview](https://carepatron.com/templates/faces-pain-scale)) | faces add valence; clinical register |
| Fire diamond | hazard placards | 0 to 4 per hazard | a fixed code a stranger learns once ([NFPA 704](https://en.wikipedia.org/wiki/NFPA_704)) | one of four co-located codes |
| Wind barbs | weather charts | speed; barbs and half-barbs | **tally logic**: half-barb = 5, full = 10; halves are native ([AMS glossary](https://glossary.ametsoc.org/wiki/barb/)) | needs the code taught |
| Beaufort force | marine | 0 to 12 named steps, one scale | each step *has a name* (like Plutchik) | scale is long |
| Chilli ratings / Scoville | menus | heat, 1 to 3 chillis | the food-menu "1 to 3 of a small glyph" is exactly our scale | cute, cultural, valence-free yet playful |
| Difficulty grades | ski pistes, climbing | 3 to 4 named levels, colour + shape | graded *and* named; piste maps use shape too (circle, square, diamond) | colour carries the grade, which we cannot do |
| GitHub contribution squares | web | 4 shades of one hue | single-hue ramp for amount | many cells; the ramp only works in a field |
| Rotary/knob position | audio, hardware | level by angle | a pointer reads fast | too complex at 12 px |
| Fitness rings | Apple Watch | progress to goal, closed ring | arcs that fill | progress-to-goal semantics, not intensity |
| Plutchik wheel | psychology | intensity by *radius and saturation*; centre is strongest ([overview](https://www.simonwhatley.co.uk/writing/plutchik-wheel-of-emotion/)) | **three steps per family, mild to strong; saturation as intensity** | a wheel, not a mark |

Further sources worth reading in full before drawing: Russell, *A Circumplex Model of Affect*
([PDF](https://researchgate.net/profile/James_Russell24/publication/235361517_A_Circumplex_Model_of_Affect/links/585912f608aeffd7c4fcd880/A-Circumplex-Model-of-Affect.pdf)); Feldman (1995) on
perceived arousal ([PDF](https://www.affective-science.org/pubs/1995/FeldmanPSPB1995.pdf)); the
Duke vector-versus-circumplex study found via the same search
([DukeSpace](https://dukespace.lib.duke.edu/server/api/core/bitstreams/4d339f83-dbcb-48b3-9a78-3c49a385744e/content)).

## 4. What perception research says about the channel

Cleveland and McGill's ranking of how accurately people judge a quantity: position on a common
scale, then length, then angle and slope, then area, then volume and colour/intensity. Their own
caveat is that it is a framework, not a prescription, and newer crowdsourced work finds the
ranking depends on the task ([overview of the ranking](https://flowingdata.com/2010/03/20/graphical-perception-learn-the-fundamentals-first)).
Implications for a three-level mark:

- **Length and position beat angle and area.** Ascending bars (length) and tally strokes (count
  of marks, which is a different, even easier channel: *numerosity*, subitizable up to about
  four) should be read more accurately than a pie wedge (angle/area) or a fill shade. For three
  levels, though, accuracy is not the bottleneck; *speed and non-ambiguity* is.
- **Numerosity is nearly free for 1 to 3.** People count up to about four marks without counting.
  That is why circles work at all, and why tally strokes, wind barbs and chevrons are at least as
  fast: the value is "how many things", with no area judgement.
- **Colour or opacity alone is the weakest carrier**, and we cannot use hue anyway (valence-free,
  four palettes, two modes). Ghosted ceilings help legibility but cost contrast; the shipped
  mark's unfilled state is drawn at 35% opacity, a large part of why 1 of 3 can look "disabled".
- **Greyscale and colour-vision robustness:** the fill amount must be readable without colour,
  which is true of every candidate below since we carry no hue.
- The Harvey-ball evidence is thin: no study tests it directly, so what is said of it is
  inference from the ranking.

## 5. Axes for classifying directions (the design space)

Rather than listing options, name the axes a mark can vary on. Any candidate is a point in this
space, and the owner's complaint is about one axis in particular.

1. **Unit count.** 3 units (value = how many are on), or 1 glyph (value = how full), or a
   continuous form (value = how large).
2. **Unit identity.** Identical units (pager grammar) versus graded units (each differs in size,
   height or weight, so the mark is order-bearing even before any is filled).
3. **State carrier.** What distinguishes "on": fill, outline-to-solid, opacity, height, weight,
   or presence/absence (tally).
4. **Ceiling.** Is the full extent always visible (ghosted), or only the value drawn?
   Ceiling-visible helps "how much out of what"; ceiling-absent is lighter and calmer.
5. **Metaphor.** None (abstract), strength (signal), loudness (volume, waveform), heat
   (flame, chilli), weight (stroke weight), force (barbs, chevrons), fill (container, ring).
   Each imports connotations: signal says *good*, heat says *danger/spicy*, loudness says *voice*,
   which is closest to the truth, since the data is what people *said*.
6. **Axis of growth.** Horizontal row (matches reading order and the pager), vertical rise (bars,
   waveform), radial (ring, pie), diagonal (steps).
7. **Footprint.** Fills the 46 x 12 box, or a smaller glyph right-aligned inside it. The box must
   not grow; it may be under-filled.
8. **Half-step grammar.** Continuous forms get halves free (a bar half-height, a wedge sixth).
   Unit-based marks need a rule (half fill of one unit). The chart mean is the only place this
   matters; it can use its own, larger size.

The owner's complaint maps to axes 1 and 2: three identical units in a row.

## 6. Where the real risk lies

- **Valence leakage.** Signal bars and ratings say "good"; flames and warning glyphs say "bad".
  Intensity is neutral between delight and frustration; a neutral abstract form or a *loudness*
  metaphor is safest.
- **Mild must not look like off.** Whatever the form, level 1 needs enough ink to read as a real
  value and not a disabled control.
- **Pager grammar** survives a change of shape. Test candidates against it directly.
- **Size.** About 12 px tall. Hairline strokes and 4 px gaps disappear in WebKit at 1x; every
  candidate has to be measured, not judged by eye.
- **Dark and Edo.** The mark takes `--dot-colour`; ghost opacities that work on light grey can
  vanish on the dark quote background.
- **No new bespoke CSS, no new strings.** Everything is drawn in the component; the tooltip key
  already exists.

## 7. Method before anything is built

1. Owner reads this note and says which of the axes and metaphors feel right and which are out
   (for example: "no heat or signal metaphors", "must be one connected form").
2. Mockup of 5 to 8 directions *chosen from the surviving region of the space*, shown at both
   sizes, light and dark, in a quote paragraph, against the pager.
3. Measure each at 1x and 2x in WebKit and Chromium: changed-pixel area between adjacent values,
   thinnest feature, contrast of level 1 against ground, and a pager-likeness check.
4. Shortlist with a recommendation, owner chooses, then build behind the existing API.

## 8. Outcome

The owner steered from the signal-bars idea (too like a histogram) to **three circles that grow**,
on one centre line, so the tangents converge like a cone and the mark is one rising quantity, not
three equal objects with one flagged (the pager grammar, §2). Measured in WebKit and Chromium at 1x
and 2x, light and dark (mockup `docs/mockups/intensity-graded-circles.html`):

- Fill is cumulative (value 2 lights circles 1 and 2), so ink adds up. Equal circles give ink
  1 : 2 : 3 but perceived about 1 : 1.6 : 2.2, assuming perceived size goes as area to the power
  0.7 (an assumption from memory, not a sourced figure). The shipped mark under-separated 1 from 3.
- A true cone needs radii linear in position and an equal pitch. A steep one (2 / 3.7 / 5.4) turns
  out 1 : 4 : 9 in ink and level 1 shrinks to a speck (10 px² against 52). Area-honest sizing
  (radius as the square root of the value) curves the flanks.
- **Chosen: radii 3.8 / 4.6 / 5.4, pitch 11.5** (the gentle cone). Perceived steps 1 : 1.8 : 2.7,
  level 1 33 px² (WebKit 1x), and the middle radius is the mean of the outer two, so the tangents
  are straight. Unreached circles stay as a faint ghost (22% opacity, filled) so the ceiling
  shows; the full ones are 80%. Half values fill the left half of the next circle.
- Drawn from the left edge of the 46 x 12 box for the chart (`m`) and the right edge for the
  paragraph (`s`, radii 5% smaller), so the paragraph's mark stays flush top right. The box does
  not grow. Built in `frontend/src/components/IntensityDots.tsx`; no CSS changed.

Not taken: signal bars and rating glyphs (say "good"), a single bubble sized by value (reads as a
radio button), an unghosted cone (level 1 a lone speck), steeper cones (overstate the top).
