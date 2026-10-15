# Leader styles for the Screens lens

_15 Oct 2026. Research and mockup only; the lens code is unchanged. Mockup:
[`docs/mockups/screens-leader-styles.html`](../../docs/mockups/screens-leader-styles.html).
Context: `docs/design-screens.md` §2 S5 (placement, the owner's decisions)._

**The problem, in the owner's words:** the Discussion lens's connectors are "just right, but there
they are over more clear space and here they have to compete with the visuals of the screen."

**The short answer** (revised the same day, §6a). Keep the line and its geometry, and **case** it,
in the *screengrab's* paper colour, clipped to the screengrab; over the screengrab the line takes the
screengrab's accent. A casing in the board's colour, the first answer, drew heavy dark tracks in dark
mode. There is no casing over the gutter, and over paper the casing is the paper, so a leader looks
exactly like a Discussion wire except where it crosses ink. Then, on selection only, add a quiet
spotlight that dims towards the paper. §6 gives the first ranking; §6a revises #1.

## 1. What we have, measured

- **Discussion wires** (`frontend/src/islands/discussion/discussion.css`, `model.ts wirePath`).
  - Shape: a 1px accent line at opacity 0.5, drawn as `M0,y1 h8 L(w-8),y2 h8`: a stub, a slant
    across the gutter, a stub.
  - On focus, the lit wire goes to opacity 1 at 1.5px and the others to `--bn-focus-ghost-opacity`
    (0.14).
  - They live entirely in a gutter of plain `--bn-colour-bg`. The only thing a wire has to separate
    itself from is the background, and the accent does that at 4.0:1 (default light) to 6.7:1 (Edo
    light).
- **Screens leaders** (`layout.ts leaderPath`, `screens.css svg.screens-leaders`).
  - Shape: a 1px accent line at full opacity (raised from 0.6, which measured 2.3:1), ending in an
    r=2.5 accent dot. The target line on the screengrab gets a 1.5px accent box with a 6% accent
    fill (15% when lit).
  - Geometry: straight when the card is level with its line, otherwise a 12px drafting shoulder off
    the card and then one straight run. The run crosses the gutter, then the screengrab, to the
    line.
- **Contrast of the 1px accent core against what is under it.** These are WCAG ratios, computed for
  the colours in the mockup's synthetic page, which are typical of retail UI:

  | Accent | White page | Grey panel | Blue button | Link blue | Blue product photo | Dark text |
  |---|---|---|---|---|---|---|
  | default light `#007aff` | 4.0 | 3.7 | **1.4** | **1.4** | **1.0** | 4.0 |
  | default dark `#0a84ff` | 3.6 | 3.3 | **1.6** | **1.6** | **1.1** | 4.4 |
  | Edo light `#0f5c9e` | 6.9 | 6.3 | **1.2** | **1.2** | **1.7** | **2.3** |
  | Edo dark `#4d9fe0` | **2.9** | **2.6** | **2.0** | **2.0** | **1.4** | 5.6 |

  Bold cells fail WCAG 1.4.11's 3:1 for a graphical object that carries meaning ([W3C, Understanding
  1.4.11](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast)). The rule is measured
  against *adjacent colours*, and over a screengrab the adjacent colour is the page. A blue line
  cannot reliably pass over a page that is itself blue, and most commercial pages are. Note one
  row: **in dark mode the screengrab usually stays light**, so Edo's dark accent fails even on
  white.
- **The highlight box has the same problem.** A 1.5px accent border around a blue button is 1.0–1.6:1
  against the button. On a busy page the box disappears first, so the line may still be visible
  while its target is not.

## 2. Technical illustration, cartography and annotation

- **The drafting leader.** ASME Y14.2 / ISO 128 leaders are a thin continuous line, usually
  straight, at a clear angle to the feature, with a short horizontal shoulder at the note. Today's
  shoulder-plus-run is the same. **Termination encodes the target's kind.** An arrowhead touches a
  line or edge; a dot sits *within the outline* of a surface it refers to (ASME Y14.2 §"Termination
  of leaders", [TOC](https://webstore.ansi.org/preview-pages/ASME/preview_Y14-2_2014_w_CPRT.pdf);
  restated with the Y14.5 citation in the [GD&T study
  guide](https://open-exam-prep.com/study-guides/asme-gdtp-technologist/ch1/application-and-location-of-dimensions)).
  A line of text on a screen is an area, so a **dot is the right terminator**, and drafting would
  put it inside the box rather than 3px outside it. Secondary sources disagree on the allowed
  angles (≥30° to the feature vs. 15–75° from horizontal), so treat those as convention, not
  standard.
- **Richards's rules for leaders on technical drawings** (Richards, "Technical and scientific
  illustration", in *Information Design: Research and Practice*, 2017, ch. 5, as summarised by
  Bekos, Niedermann and Nöllenburg).
  - Leaders should be straight where possible.
  - A leader is **a dark line with a thin white line beside it, which separates it from the
    background**. This is the drafting form of casing.
  - Terminate with a dot for a large feature and an arrowhead for a small one.
  - Staircase polylines are acceptable in small numbers, but avoid them where safety or efficiency
    matters ([Bekos et al., "External Labeling Techniques: A Taxonomy and Survey", CGF/EuroVis STAR
    2019, §3.1](https://arxiv.org/pdf/1902.01454)).
- **Differentiate leaders from the background's own lines** (same survey, citing Wu et al. 2012).
  - In illustrations of irregular shapes (maps, anatomy), straight and polyline leaders are best.
  - In illustrations full of straight, regularly sloped lines (the example is **floorplans**), use
    curved leaders or polylines at non-aligned slopes.
  - **A web page is a floorplan in this sense**: rules, borders, underlines, table lines, all
    horizontal or vertical. Two consequences follow. A horizontal leader over a page can read as an
    underline or a strike-through. Today's diagonal run is the more distinct shape, so the geometry
    should not be made more orthogonal inside the screengrab.
- **Boundary labelling** (Bekos, Kaufmann, Symvonis, Wolff 2004–07; the survey above).
  - The S5 layout *is* this model: labels outside a rectangle, sides ordered by their sites' order,
    no crossings.
  - Leader types:
    - *s*: straight.
    - *po*: a segment parallel to the side, then one orthogonal to it.
    - *do*: diagonal, then orthogonal.
    - *opo*: three segments, the middle in a routing track beside the image.
  - **The only readability study** (Barth, Gemsa, Niedermann, Nöllenburg, [GD 2015, arXiv
    1509.00379](https://arxiv.org/pdf/1509.00379); journal version *Information Visualization*
    18(1), 2019, [doi 10.1177/1473871618799500](https://doi.org/10.1177/1473871618799500)). It ran
    31 subjects on an assignment task (find a label's site and vice versa).
    - **po** was fastest, with the same error rate as s and do.
    - Preference ran **do > po > s > opo**.
    - **opo** was worst on every measure: "confusing, because leaders closely pass by each other".
    - s-leaders were legible but "chaotic and unstructured".
    - Their own caveat is the one that matters here: the study "judged all leader types on an empty
      background, where the leaders receive the entire visual attention … In reality, the labeled
      figure itself is the main visual element and the leaders should be as unobtrusive as
      possible." **No study measures leaders over busy imagery.** What follows is practice, not
      evidence.
  - Today's leader is a do-leader read from the card: a short orthogonal shoulder, then a slant.
    That is the type subjects liked best, so the geometry is not the problem.
- **Excentric labelling** (Fekete & Plaisant, [UMIACS-TR-98-59 /
  CHI 1999](https://drum.lib.umd.edu/items/13064c68-5887-47c3-9035-acd4b89b7dcb/full)). Labels
  appear only for the neighbourhood under a stationary cursor, stacked left and right with straight
  leaders. Two lessons transfer. **Leaders on demand** are a legitimate answer to clutter, and the
  original gates them on a one-second dwell, which keeps them from flickering. S5 has already ruled
  out hover for cards; the same reasoning rules out hover-only leaders, so demand would mean
  selection.
- **Cartographic casing and halos.**
  - Esri's basemap team describe casing as "a visually protective wrapper around our symbol": a
    contrasting tone either side of the core that keeps a line visible "over most any background"
    and sets it in the hierarchy (John Nelson, ArcGIS Blog, ["Make lines legible and pop with
    casing"](https://www.esri.com/arcgis-blog/products/arcgis-pro/mapping/make-lines-legible-and-pop-with-casing);
    the page refuses automated fetches, so this is quoted from search summaries).
  - Halos are the text equivalent. They are disliked when heavy and blocky, and favoured when thin.
    Print cartographers *masked* (knocked out) the background around a label instead (Andy Skinner,
    ["Polishing your halo"](https://www.esri.com/about/newsroom/arcuser/polishing-your-halo); the
    restrained-halo argument from QGIS Planet is
    [here](https://plugins.qgis.org/planet/user/13/tag/cartography)).
  - Takeaway: make the casing **thin**, and in a tone that belongs to the annotation layer, not the
    map.
- **Areas of disinterest.** Cartographers lighten everything outside the subject instead of making
  the subject louder (Esri, ["Light, shadow and areas of disinterest"](https://www.esri.com/arcgis-blog/products/arcgis-pro/mapping/light-shadow-and-areas-of-disinterest),
  title and gist only, as the page refused a fetch; the "reverse AOI" in the Imhof
  style). The risk they name is a washed-out map, so do it lightly, and only while there is a
  subject.
- **Perception.** Thin lines are seen through *luminance* contrast. Chromatic (hue) contrast is weak
  at high spatial frequency, and a 1px line is about as high as it gets (Ware, *Information
  Visualization: Perception for Design*, 4th ed., ch. 3–4, after Mullen 1985). The point for this
  lens: **a blue line on a blue button differs in hue and hardly at all in luminance, so it
  vanishes.** A light/dark casing adds the luminance edge the hue cannot.

## 3. Product prior art

- **Skitch** (Evernote). Coloured arrows with "a fat white outline and a dark drop shadow, making
  them easily visible in any screenshot, regardless of background colour" ([user account,
  KDE Discuss](https://discuss.kde.org/t/configurable-shadow-outline-options/35765)). It is the
  canonical screenshot-annotation style: casing plus lift. It is loud by design, because Skitch's
  marks are the message; ours are the route to the message (the card).
- **Apple Preview / Markup.** Shapes and arrows have an optional shadow, the same lift idea with no
  casing. **CleanShot X** offers four arrow styles including curved ([features](https://cleanshot.com/features)).
  No official source states their outline treatment, so they are not cited for it.
- **Figma.** Comment pins are numbered markers that need a click to read. Users report that
  stakeholders ignore them for exactly that reason. Dev Mode annotations sit with the element and
  stay visible, and are preferred for it ([Figma forum
  thread](https://forum.figma.com/suggest-a-feature-11/allow-us-to-expose-annotations-and-measurements-to-view-seat-users-39110/index7.html)).
  Lesson: **a pin with the text elsewhere is read less than text joined to its place.** That argues
  for keeping visible leaders at rest, not only on demand.
- **Zeplin / Avocode redlines.** Measurement overlays in a saturated colour foreign to the design
  (magenta or red), so a spec line cannot be mistaken for UI. The colour choice is the general
  redlining convention; no vendor source explains it ([redlining
  definition](https://uiuxjobsboard.com/terms/ux-design/redlining)). It is the alternative to casing:
  pick a hue no page uses. It conflicts with BN's rule that colour is content's and the accent is the
  one interactive colour, and no hue is guaranteed absent from a client's page.
- **Hotjar / Maze heatmaps.** The data overlays a snapshot of the page, with no leaders and no
  dimming ([Hotjar](https://help.hotjar.com/hc/de/articles/36819988774545),
  [Maze](https://help.maze.co/hc/en-us/articles/360052722953)). Spotlight-and-dim is a capture-tool
  idiom (e.g. [Spotlit](https://addons.mozilla.org/tr/firefox/addon/spotlit/)), not an analysis-tool
  one.
- **Dovetail.** Highlights text and transcripts and has no region annotation on images ([help:
  highlights](https://docs.dovetail.com/help/projects/highlights)). There is no prior art for "quote
  joined to a screen region" in a research repository; Bristlenose would be first.
- **Miro connectors.** Straight, elbow (rounded or sharp) and curved. Users asked for rounded elbows
  because they are easier to trace where lines converge, and some later asked for sharp elbows back
  ([community](https://community.miro.com/ideas/connection-lines-with-rounded-elbows-6116)). Taste
  varies, and there is no evidence either way.
- **Numbered hotspots with a legend, not lines.** These win when labels are long or many, when a
  parts list already exists, or when lines would run through the subject (assembly manuals; PTC Creo
  Illustrate offers [numbered callouts](https://support.ptc.com/help/creo/creoillustrate/en/creo_illustrate/gxy1580.html)
  as a peer of text callouts). They lose on split attention: the eye goes target → number → legend →
  text. No controlled study compares the two for figures; the argument is Mayer's spatial-contiguity
  principle. **S5 already has half a hotspot system**: each card carries a per-person sequence badge
  (p1 ①). Putting the same badge on the target box gives redundancy for a leader that is momentarily
  lost, without giving up the line.

## 4. Legibility techniques over a busy image

| Technique | What it does | For us |
|---|---|---|
| **Casing** (a wider stroke under the core, in the annotation layer's background colour) | Gives the core a guaranteed adjacent colour: 4.0:1 default light, 5.2:1 default dark, 6.7:1 Edo light, 6.2:1 Edo dark | **Yes.** In the board's bg colour it is invisible over the gutter, so a leader is unchanged where it is already fine. One extra path per leader. |
| Drop shadow on the line | Lifts it onto the cards' plane | Pairs with casing (Skitch). Alone it does nothing on a dark region. Optional. |
| `mix-blend-mode: difference` | Inverts what is under the line | **No.** Fails on midtones (which a product photo is), changes the hue unpredictably, can't be themed, and its 1.4.11 contrast can't be stated. Shown in the mockup to make the failure visible. |
| A foreign hue (magenta redline) | Picks a colour the page won't have | No: breaks accent = link, and nothing guarantees absence. |
| Neutral ink core (`--bn-colour-text`) + casing | Richards's black-and-white | Works with casing (17:1 against white) but fails 1.7:1 on a dark photo without it. Drops the accent's meaning. Second best. |
| Heavier weight (1.5–2px) | More ink | Helps a little; reads chunky (Discussion moved 1.3/2px → 1px for exactly that, 3 Oct 2026). Selected leader only. |
| Dashes | Distinct texture | No: dashes break up over texture, and dashed rules are common in page UI. |
| End marker: dot / ring / arrow / none | Says where the line stops | **Dot**, cased, inside the box edge (ASME: area target). A ring is a fair alternative over a dark target. Arrows add direction we don't need. |
| Highlight-box casing (1px bg ring outside the accent border) | Same fix for the target | **Yes.** On a busy page the target is lost before the line. |
| Spotlight: dim the screengrab outside the lit line | Area of disinterest | **On selection only**, lightly (a 35–45% scrim of the board bg), never at rest, never on hover. It changes the artefact's look temporarily, which the owner's "don't disrespect the screengrab" allows only while the researcher asks for it. |
| Show only the selected leader; others faint or hidden | Removes clutter | Already done at 0.25 on focus. Hiding at rest loses the join (Figma pins) and is not recommended. |

**Accessibility.**
- **1.4.11.** Casing is what makes a defensible 3:1 claim possible. The meaning-bearing part (the
  core) is always adjacent to the casing. This is the same reading as the Understanding doc's
  example of an input border, where the adjacent colour is the one immediately beside the mark.
- **Meaning, and screen readers.** At rest the leader is the only visual join between a card and
  its line: the badges give person and order, not position. So 1.4.11 applies, and `aria-hidden`
  does not change that. _Corrected 15 Oct 2026, in review: this said the leader was "redundant for a
  screen reader". It is not. Nothing tells a screen-reader user which line a quote points at: the
  highlight boxes have no text, and the card doesn't name its target. That is a 1.3.1 follow-up
  (e.g. "On screen: <line text>" on each linked card), separate from the leader style._
- **Reduced motion.** A spotlight fade must snap under `prefers-reduced-motion`, as the board's other
  transitions already do.
- **Dark mode.** The casing takes the *board's* bg (`--bn-colour-bg`), not the page's, so a dark board
  over a light screengrab puts dark casings on the page. Measured legible in the mockup; the
  alternative, a white casing in dark mode, glows.
- **The selected-state gate.** `tests/test_screens_css.py` allows only "can't move anything"
  properties on selected or focused selectors (`stroke`, `opacity`, `box-shadow`…), and
  `stroke-width` is not on the list. A thicker lit leader must therefore hang off `path.on` (which
  the gate does not treat as a state), not `.screens-stage.focus`, or `stroke-width` joins `SAFE`
  with a reason.

## 5. Routing

- **Straight / drafting shoulder (today).** do-type. The best-liked shape in Barth et al., and its
  slant separates it from a page's axis-aligned rules. Its weakness is only length: a card far from
  its line sends a long diagonal across the page.
- **Orthogonal (po/opo, staircases).** Over a web page, horizontal and vertical segments read as page
  rules (the floorplan finding). opo is the worst-measured type, because parallel tracks run close
  together. **Not inside the screengrab.**
- **Discussion wire shape (stub, slant across the gutter, stub).** Its slant lives in clear space,
  which is why it looks right there. Transplanted here, the slant stays in a 32px gutter and the run
  *into* the screengrab becomes horizontal: the underline problem again.
- **Gutter-run.** Do the vertical travel in the gutter, then enter the screengrab with one short
  slant. This minimises ink on the page and keeps the in-image segment non-orthogonal. Its cost is
  opo's failure mode: several leaders travelling down one 32px gutter overlap unless each gets its
  own track by rank. Worth it only for long leaders (|Δy| beyond ~1.5× the in-image distance, a guess to tune), which
  the S5 layout makes rare, because a column places each card near its line.
- **Curved (Bézier).** The survey's answer for floorplan-like backgrounds, and the most distinct shape
  over UI. But it is the least drafting-like, BN's whole S5 vocabulary is the architect's drawing,
  and there is no readability evidence for it. Park it.
- **Stop at the edge.** The leader ends at the screengrab's border with a small cased chevron. The
  target carries the card's p1 ① badge; the line continues inward only when the card is selected.
  This is the cleanest screengrab, at the cost of a scan across the page to match a badge. It suits
  a dense screen (eight or more linked quotes) more than a typical one. S5 says "every quote linked
  has a leader", so this would be a mode, not the default.

Which routings survive a busy page: **a short slant survives best**, orthogonal worst. The
difference matters much less than rendering: a cased slant and a cased horizontal both read, and an
uncased one of either does not.

## 6. Comparison and recommendation

Scores: ● good, ◐ mixed, ○ poor. Build cost is against today's `leaderPath`, `ScreensLens.tsx` and
`screens.css`.

| | Busy-image legibility | Clutter on the screengrab | Accessibility (1.4.11, dark, motion) | Family with Discussion | Build cost |
|---|---|---|---|---|---|
| A. Today (1px accent, dot, 1.5px box) | ○ 1.0–1.6:1 on blue | ● | ○ fails on blue; Edo dark fails on white | ● | — |
| **B. Cased** (bg casing on line, dot, box) | ● | ● (casing invisible off-page) | ● 4.0–6.7:1 in all four | ● identical over clear space | **S**: CSS + one path per leader |
| C. Cased + lifted (shadow, 1.25px) | ● | ◐ heavier | ● | ◐ | S |
| D. Gutter-run (cased) | ● | ● least ink on the page | ● | ◐ | **M**: `leaderPath` + track assignment + tests |
| E. Edge port + badge on target | ● (nothing to see) | ● cleanest | ◐ join is by badge, not line, at rest | ○ | M |
| F. Spotlight on selection (with B) | ● when selected | ● at rest, ◐ selected | ● (snap under reduced motion) | ● Discussion lights the hot wire too | **S**: CSS on `.screens-hl.on` |
| G. Neutral ink, cased | ● | ◐ reads heavier | ● | ○ loses the accent | S |
| H. `mix-blend-mode: difference` | ◐ fails on midtones | ● | ○ unprovable | ○ | S |

**Recommendation** (first pass; #1 revised in §6a to B′, paper-coloured casing)

1. **B. Cased leaders, dots and boxes.**
   - The direct fix for the failure the owner named, and the only option that makes 1.4.11 hold on
     any page in every palette.
   - It changes nothing over clear space, so the Discussion look is kept exactly. Cartography (casing),
     drafting (Richards's white line) and screenshot tools (Skitch) all converge on it.
   - Cheapest of all: `leaderPath` is untouched.
2. **F. Selection spotlight, on top of B.** When a card is selected (press, focus, J/K), lift its
   leader to 1.5px and lay a light board-bg scrim over the screengrab outside the lit line. This is
   the cartographer's area of disinterest, applied only while the researcher has asked about one
   line. It answers "which of these lines is mine" on a crowded screen without hiding anything at
   rest. It is CSS only.
3. **D. Gutter-run for long leaders only.**
   - Move the vertical travel into the gutter and keep one short slant into the screengrab. This
     reduces the leader's run across the page, which is the owner's second complaint.
   - Ranked third because it needs per-leader gutter tracks to avoid opo's close parallels, new
     `leaderPath` tests, and a threshold.
   - The S5 layout already keeps most leaders short, so measure first: count leaders whose in-image
     length exceeds ~200px (an unmeasured guess at "long") on the real sessions before building it.

**Considered and not recommended:**

- **E, edge port,** as a default. It breaks "a linked quote has a visible leader", and Figma's pins
  show that joined-to-place is read more. Keep it as the dense-screen idea if a screen ever carries
  12+ links.
- **G, ink** (loses the accent's meaning), **H, difference blend** (fails on midtones), dashes, a
  foreign hue, hover-only.

## 6a. Iteration: the casing follows the screengrab, not the board (15 Oct 2026)

**What the owner saw.** B is right in light mode and wrong in dark: its casing takes the *board's*
background, near-black in dark mode, and a screengrab is almost always a white page. Every leader
gained two dark tracks, which read as heavy dark lines. The mirror case follows: a light board over
a screengrab of a **dark-mode site** puts white tracks on a dark page.

**The fix is the print cartographer's mask rather than a halo.** Paint the casing in the screengrab's
own *paper* colour, and clip it to the screengrab. On paper the casing is the paper, so it can't be
seen; it shows only where the line crosses ink (a button, a photo, text). In the gutter there is no
casing at all. The line is then a bare Discussion wire everywhere except where the page needs it to
be more.

**The line's colour has to follow the screengrab too, at least in Edo.** Contrast of the accent
against the paper:

| Accent | White site | Dark site `#121212` | Dark site panel `#1e1f22` |
|---|---|---|---|
| default light `#007aff` | 4.0 | 4.7 | 4.1 |
| default dark `#0a84ff` | 3.6 | 5.1 | 4.5 |
| Edo light `#0f5c9e` | 6.9 | **2.7** | **2.4** |
| Edo dark `#4d9fe0` | **2.9** | 6.6 | 5.8 |

So over the screengrab the line takes the accent of the **screengrab's** scheme, not the board's:
- **The rule:** light-mode accent on a light site, dark-mode accent on a dark site.
- **Paper contrast** under that rule is 4.0 / 5.1:1 in the default palette and 6.9 / 6.6:1 in Edo.
- **Where the change shows:** in the default palette the two halves barely differ. In Edo the line
  changes tone where it enters the screengrab, which reads as crossing onto another surface.
- **The rest of the annotation follows the same rule:** the target box, the end dot and the
  selection spotlight. The spotlight now dims **towards the paper**, the cartographers' direction,
  so it no longer greys a white page on a dark board.

**Variants mocked** (B′ in the mockup, in four frames: board light/dark × site light/dark):

| | What | Verdict |
|---|---|---|
| R0 | B as was: casing in the board's colour | Dark tracks on a dark board; white tracks over a dark site. |
| R4 | R0 at half width and half opacity | Softer tracks, still tracks. Also loses the measurable contrast guarantee. |
| R1 | Paper casing, clipped; board's accent | Clean in the default palette. Edo fails (2.7 and 2.9:1). |
| R2 | R1 + the screengrab's accent over the screengrab | Clean in all four frames and both palettes. The hard-edged form of R3. |
| **R3** | **R2 with the casing softened into a halo** | **Chosen by the owner, 15 Oct 2026.** Gentler over the photo. Built opaque, blurred only at its edge (below). |

**Paper is one colour per slide, and the assumption has limits.**
- **One colour per slide.** Carousel versions can differ: one participant browses in dark mode,
  another doesn't. Paper is sampled from each still. The page's dominant background is what the
  outer ring of the image mostly is, and a 24×16 downscale is enough to find it.
- **Where one colour is wrong:** a full-bleed photo or a mid-grey page (#8a8a8a is 1.1–2.0:1
  against every accent). There, fall back to whichever of the two accent halves, cased with the
  paper or with the opposite, clears 3:1. That fallback is a rule the product has to own, and no
  frame shows it.
- **Untested:** sampling under each segment rather than once per slide.

**Chosen: R3** (the owner, 15 Oct 2026). A soft halo in the paper colour around the line, dot and box,
clipped to the screengrab, with the screengrab's accent over it.

**The softness must come from blur, never from opacity.** With σ 0.7px on a 4px casing, the paper's
share is 98% at the exact edge of the core but about 91% averaged over the first pixel beside it.
The worst pairing (default light accent, white site, over dark text) therefore holds at about
**3.3:1 at 1×** (3.7:1 at 2×). That passes, but costs about 18% against a hard casing's 4.0:1.
_Corrected in review: the first figure here, 3.9:1, used the edge value._ Partial opacity is worse,
because it lets ink through right next to the core: the same pairing is 3.0:1 at 85% opacity and
2.4:1 at 75%. The first R3 mock used 85% and has been corrected. Because of the blur's cost, a paper
counts as **midtone** below about **3.65:1** (3 ÷ 0.82), not 3:1. A light grey `#e0e0e0` passes a
naive 3:1 test and fails under the blur.

The rest of the ranking stands: #2 is the spotlight, now dimming towards the paper, and #3 is
gutter-run.

## 7. Fold-in plan for R3 (reviewed 15 Oct 2026; handed to the session reworking the lens)

**As built: `72f80bd1` (15 Oct 2026), with one measured departure.**

- **Where the build differs from the plan below:** the blur applies only at
  `(min-resolution: 2dppx)` (`ScreensLens.tsx`, `HIDPI`). At 1× the halo is the hard casing: R2,
  4.0:1.
- **Why, measured by the lens session in Playwright WebKit and Chromium:**
  - **WebKit at 1×:** σ 0.35 and σ 0.7 render identically, as a 3px smear whose brightest row is
    214/255 over `#222` ink. That is about 81% paper, under the 3:1 floor, not the 91% this plan
    assumed.
  - **WebKit at 2×:** the device rows beside the core stay 96–100% paper, better than assumed.
  - **Chromium at 1×:** no blur is drawn at all for σ < 1.
  - **The lesson:** the 91% here came from a continuous Gaussian, and the renderers quantise blur
    to device pixels. Measure the rendered pixels, not the formula.
- **Step 0(a) holds in WebKit:** `color-scheme` on the `<g>` resolves the accent to its dark half.
- **Step 0(c):** drag and resize frame times in headless WebKit showed no measurable difference with
  the filter on or off (p95 17–19 ms either way).
- **On real data:** the IKEA board's paper samples as `rgb(247,247,247)`, and the light half is
  chosen on both board themes.
- **Not done:**
  - Step 5, the `.app` look, which needs a sidecar rebuild and the owner's eyes.
  - The screen-reader follow-up.
- **A probe trap for anyone re-measuring:** a page loaded with `page.setContent` (`about:blank`) does
  not resolve `url(#id)` for `clip-path` or `filter`, so a clip probe draws nothing. Serve the probe
  from a real http origin.

_The plan below is as handed over. Its blur figures (91%, 3.3:1 at 1×) are superseded by the
measurements above._

Three reviewers checked this plan against the lens at `46819910`: correctness, accessibility and
performance. It has been revised to match. The mockup's section B′ shows R3.

### What R3 is

- **The line itself is unchanged:** today's 1px accent core, with `leaderPath` untouched. It gains a
  soft, **opaque** halo in the **screengrab's own paper colour**, **clipped to the screengrab**.
  - Over plain page background the halo is the paper and can't be seen. It shows only where the line
    crosses ink.
  - In the gutter there is no halo, so the line is a bare Discussion wire.
- **Over the screengrab the line uses the accent half that contrasts best with that paper,** whatever
  the board's theme. The end dot and the target box follow the same rule.
- **Why not the board-coloured casing:** it drew heavy dark tracks on a dark board over the usual
  white screengrab, and white tracks over a dark-mode site.
- **The softening is blur, never opacity.** The halo is core + 3px wide with an SVG `feGaussianBlur`
  of σ 0.7.
  - **What the blur costs:** about 91% paper survives across the first pixel beside the core, so the
    worst pairing is about **3.3:1 at 1×** and 3.7:1 at 2×. That is roughly 18% less than a hard
    casing gives (4.0:1).
  - **What opacity would cost:** partial opacity lets ink through right beside the core, giving 3.0:1
    at 85% and 2.4:1 at 75%.

### Steps

0. **Measure in WebKit first** (Safari, or the `.app`'s WKWebView).
   - **(a)** Check that `<g style="color-scheme: dark">` resolves `var(--bn-colour-accent)` to the
     dark half (`#0a84ff` in the default palette). This is measured in Chromium only.
   - **(b)** Check that `feGaussianBlur` on a clipped group renders.
   - **(c)** Time a card drag and a live resize with the filter on and off. WebKit rasterises SVG
     filters on the CPU.
   - **If the blur costs visibly, or can't be told from antialiasing,** ship it unblurred: that is
     R2, at 4.0:1 worst. Tell the owner, since R3 was their pick.
   - **If (a) fails,** use the explicit accent halves from step 1's probe as stroke values. That needs
     no new token either.
1. **Paper sample: `screens/paper.ts`, sampled off the DOM when a still arrives.**
   - **Where:** in `fetchStill`'s `.then` (~line 299). Load the data URI into `new Image()`,
     `await img.decode()`, draw it into a canvas, and read **thin strips at full resolution** along the
     left, right and bottom edges, inset ~4px. **Skip the top edge,** which may be a browser tab bar
     after the crop.
     - Thin strips rather than a 24×16 downscale, because downscaling aliases.
     - Stills are data URIs, so the canvas is never tainted. Screens is server-only and never in an
       export.
   - **Cache** the raw paper rgb per still URL in a module `Lru` sized like `boardStills` (24). Set it
     **before** `stills.set(...)`, so the still and its paper arrive in one commit.
   - **Every** fetched still is sampled, so neighbour slides have their paper before a turn. That
     prevents a flicker where the halo vanishes and the accent jumps tone on a turn, which is visible
     in Edo.
   - **Force alpha to 1.**
   - **The decision is a pure function, unit-tested:**
     `choosePaper(paperRgb, accents: { light, dark }) → { casing, scheme, midtone }`.
     - `accents` is read once from a probe element under forced `color-scheme: light` and `dark`, then
       re-read when the palette changes.
     - Take the accent half with the higher ratio against the paper. If that ratio is **≥ 3.65:1**
       (3:1 ÷ the blur's 0.82), use `casing = paper` and that half's scheme.
     - Otherwise it is a **midtone**: try the 4 pairs (each accent half × a white or `#111111`
       casing), pick the best, and take `scheme` from the chosen accent half, never from the paper.
     - Return the casing as a **literal** rgb. Inside a forced-scheme group, `--bn-colour-bg` would
       resolve to the paper's own scheme and stop being a choice.
     - Test cases: a white page, `#121212`, `#e0e0e0` (which passes a naive 3:1 test but fails under
       the blur), and a mid-grey photo, in both palettes.
2. **`ScreensLens.tsx`, the leaders `<svg className="screens-leaders">` (~line 2086).**
   - **`<defs>`**, with ids from `useId()`:
     - A `<clipPath>` rect = the showing still's picture in board space, **padded 3px** so an end dot
       at the image edge is not halved: `geo.sx + geo.ix`, `geo.sy + geo.iy`, `geo.iw`, `geo.ih`
       (the same terms as `elem` at ~line 1551).
     - A `<filter filterUnits="userSpaceOnUse">` whose region is **that same rect plus ~3px**, not the
       whole board. A board-sized region forces a full-board raster on every drag, glide and resize.
   - **Paths:** keep today's paths in the board layer. Add a clipped `<g class="lead-shot">` holding:
     - a casing pass `<g class="lead-casing" filter=url(#…)>`, with no `opacity` attribute;
     - a core pass of the same `d`s;
     - the end dots, which move into it.
   - **Styling the group:** it carries the current slide's choice (`tabIdx`, ~line 531):
     `style={{ colorScheme: choice.scheme, "--screens-paper": choice.casing } as React.CSSProperties}`.
     Memoise it. The name follows the local `--screens-*` pattern.
   - **Do not put the scheme on `.screens-slides`.** That would recolour the image's border and the
     wait and error states. Put the same two properties on **each `.screens-hl`** instead.
   - **No paper yet** (still loading or failed): no clipped group, so today's line stands.
   - **Accepted:** while the slow cross-fade runs on a turn, the halo can briefly sit over the outgoing
     still. Reduced motion already stops the fade (`screens.css` ~310).
3. **`screens.css` (~line 271).** Keep your `path.on { stroke-width: 2 }`.
   ```css
   svg.screens-leaders .lead-casing path { stroke: var(--screens-paper); stroke-width: 4; stroke-linecap: round; stroke-linejoin: round; }
   svg.screens-leaders .lead-casing path.on { stroke-width: 5; }
   svg.screens-leaders .lead-shot circle { stroke: var(--screens-paper); stroke-width: 2; paint-order: stroke; }
   .screens-hl { box-shadow: 0 0 0 1px var(--screens-paper, transparent); }
   @media (forced-colors: active) {
     svg.screens-leaders .lead-casing { display: none; }
     svg.screens-leaders path { stroke: CanvasText; }
     svg.screens-leaders circle { fill: CanvasText; }
     .screens-hl { border-color: Highlight; }
   }
   ```
   - Core and dot fills keep `var(--bn-colour-accent)`, which resolves in the group's scheme.
   - **No new tokens** (S5).
   - **Optional:** under `prefers-contrast: more`, a 1.5px core and casing + 4px.
4. **Gates.**
   - **`tests/test_screens_css.py`:** fail if any selector naming `lead-casing` sets `opacity`,
     `stroke-opacity`, `fill-opacity` or `filter: opacity(…)`.
   - **Lens test**, with a stubbed paper because jsdom has no canvas: the clipped group renders with
     `color-scheme` and both passes, and **no `opacity` attribute** on the casing. The CSS gate can't
     see an attribute in the TSX.
   - **Prove each new test fails** against a reverted fix.
5. **Look at it in the `.app`.** Use a light site and a dark-mode site, in both palettes, both
   themes, at rest and selected. Do a drag and a resize, which also covers step 0(c). Nothing earlier
   sees the pixels.
6. **`docs/design-screens.md` S5:** one bullet. The leaders' halo and accent follow the screengrab's
   paper, with the reason. "No new tokens" still holds.

### Not in this change, but named

- **Screen readers learn nothing about where a quote points.** The highlight boxes have no text, and
  a card doesn't name its target line. A follow-up would give each linked card a description such as
  "On screen: <line text>" (WCAG 1.3.1). The leader itself does carry meaning (1.4.11 applies, and
  `aria-hidden` doesn't change that).
- **The selection spotlight (#2)** and **gutter-run routing (#3)**, as in the note.
- **Considered and not chosen: the server returning `{src, paper}`.**
  - For: it would be testable in pytest, with nothing to stub.
  - Against: the server has no image library (no Pillow), so it would take a second ffmpeg rawvideo
    pass and a change to the still cache.
  - Revisit if the client sampler proves fragile.
