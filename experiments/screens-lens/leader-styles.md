# Leader styles for the Screens lens

_15 Oct 2026. Research and mockup only; the lens code is unchanged. Mockup:
[`docs/mockups/screens-leader-styles.html`](../../docs/mockups/screens-leader-styles.html).
Context: `docs/design-screens.md` §2 S5 (placement, the owner's decisions)._

**The problem, in the owner's words:** the Discussion lens's connectors are "just right, but there
they are over more clear space and here they have to compete with the visuals of the screen."

**The short answer.** Keep the line and its geometry, and **case** it: draw the 1px accent core over a
3px stroke in the board's own background colour, and case the end dot and the highlight box the same
way. Over clear space the casing matches the board and is invisible, so a leader in the gutter looks
exactly like a Discussion wire. Over the screengrab the casing separates the line from whatever is
under it. Then, on selection only, add a quiet spotlight. Section 6 gives the ranking.

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
- **Without colour.** The leader is `aria-hidden`; the join is also carried by the card's
  person/sequence badge and the card's accessible text. The leader is redundant for a screen reader,
  so it only needs to be visible.
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

**Recommendation**

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

## 7. What implementing #1 and #2 would touch (not done)

- **`layout.ts leaderPath`: no change** for #1 and #2. One optional tweak: end the leader *inside*
  the box edge (`- 3` → `+ 1`), so the dot sits within the outline as ASME has it. That is a
  two-character edit per branch, plus the expected strings in `layout.test.ts` (`describe("leaderPath")`,
  about seven assertions).
- **`ScreensLens.tsx`, the `<svg className="screens-leaders">` block (~line 1745).** Render each
  leader twice: a `<g className="casing">` pass first, then the core pass, each path carrying the same
  `on` / `is-muted` classes so fading and lighting apply to both. The end circles get the casing as
  a stroke, so no second circle is needed. About 8 changed lines. No change to the measuring effect
  (~line 1262).
- **`screens.css`, `svg.screens-leaders` rules (~line 284).** Roughly:
  ```css
  svg.screens-leaders .casing path { stroke: var(--bn-colour-bg); stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; }
  svg.screens-leaders circle { stroke: var(--bn-colour-bg); stroke-width: 1.5; paint-order: stroke; }
  svg.screens-leaders path.on { stroke-width: 1.5; }
  svg.screens-leaders .casing path.on { stroke-width: 3.5; }
  .screens-hl { box-shadow: 0 0 0 1px var(--bn-colour-bg); }
  ```
  For #2, add:
  ```css
  .screens-stage.focus .screens-hl.on { box-shadow: 0 0 0 1px var(--bn-colour-bg), 0 0 0 100vmax color-mix(in srgb, var(--bn-colour-bg) 40%, transparent); }
  ```
  The scrim must be clipped to the slide, so `.screens-slide` (or the `.screens-slides` grid) needs
  `overflow: clip` — check that nothing there relies on overflow before adding it. And with two lit
  boxes (a shared line), the second scrim doubles; use `:first-of-type` or a single scrim element.
  About 6–8 lines in total. Everything new on a selected selector is `box-shadow` or `stroke`, which
  `tests/test_screens_css.py` already allows. The 1.5px weight goes on `path.on`, outside the gate's
  state pattern. Reduced motion: `.screens-hl` is already in the transition-off list.
- **Tests.** The CSS gate needs nothing. A lens test could assert that each leader renders a casing
  path (jsdom can count paths, not pixels). Prove the contrast claim once by eye in both palettes and
  both themes over a real busy session, as the S5 measurements were.
