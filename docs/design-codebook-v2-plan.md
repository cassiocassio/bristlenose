# Codebook v2 — delivery plan

Companion to `docs/design-codebook-v2.md`, which holds the decisions. This holds
the sequence. Written 30 Aug 2026.

## The rule for "uncontentious"

A change is uncontentious when it is **settled by a recorded decision (D1–D30)
or is a measured defect**, and is **not listed as Indicative** in the fidelity
map. Everything else waits for pixels on real data — which is what D29's
parallel surface is for.

That rule is why the four Indicative items (button treatments, the `-sm`/`-lg`
size axis, the Review door's split) do **not** block the build: they get judged
on the parallel surface beside the shipped one, which is strictly better than
ratifying them from a mockup on fixture data.

## Phase order, and why this order

**The constraint that sets it:** D29 says v2 is a parallel flagged surface. Any
component built before that scaffolding exists is a rewrite-in-place by
accident, because it has nowhere else to live.

### Phase 0 — the seam (no UI)

The flag, the route, the mount point, and an empty v2 lens that renders
"nothing here yet". Following the `codebook-lab` / chat-lens pattern
(`app.py:254`, `:261`): a settings flag, **not** `--dev`, so it ships in the
bundled sidecar where the cohort can reach it.

*Done when:* both lenses reachable, flag toggles, suites green.
*Risk:* low. No design content, so nothing to get wrong except the wiring.

### Phase 1 — data, not chrome

The v2 lens fetches the real codebook + templates and renders an unstyled list.
Proves the data shape carries every field the design needs **before** any pixel
is spent on it. This is where **Q6** (`version` on `TemplateOut`) and **Q8**
(framework-level distinct quote count) surface as real gaps rather than notes.

*Done when:* every field the fidelity map calls Definitive is on the wire.
*Risk:* medium — this is where owed plumbing becomes visible.

### Phase 2 — the rail

Three sections, installed-only, unconditional headings (**D25**), the platform
switch trailing at 26×15 (**D15**, **D16**), the count badge, `.partial` states.
Wholly Definitive; no judgement calls.

*Done when:* the rail matches the prototype and keyboard works.
*Risk:* low. The most-decided part of the design.

### Phase 3 — the codebook page

Zone title + Browse Library, the two-column geometry, the graphic gutter
(**D13**), provenance (**D23**), the three shapes (**D20**), the bleak empty
state (**D26**), the Review door opening the **existing modal** (**Q15**).
Reuses the floor's authoring apparatus from the shipped panel rather than
reimplementing it.

*Done when:* a codebook page is complete for floor, sentiment and framework.
*Risk:* **highest.** It is the largest surface and it carries three of the four
Indicative items. Expect to change the buttons after seeing them.

### Phase 4 — the browse grid

Cards (**D12**), navigation (**D22**), the shared disabled treatment (**D27**,
**D27a**), install/uninstall.

*Done when:* both routes to a codebook work, both directions.
*Risk:* low-medium.

### Phase 5 — the destructive edges

Uninstall confirmation at real fidelity (currently a stub), **D20 option A**
(uninstall stops preserving) with the restore path deleted in the *same* change,
and export mode's fourth state (**Q14**).

*Done when:* nothing can destroy data without saying what it will cost.
*Risk:* **highest for the user**, lowest for the code. This is the phase where a
bug loses work.

### Phase 6 — parity and deletion

The coverage audit's inventory re-run against v2; the flag defaults on; then the
sequence **D29** names — flag visibly off while v2 carries real work, then
delete v1.

## What this plan does not cover

- **The Mac half.** Blocked on **Q17**'s channel decision; the SPA work above is
  independent of it.
- **Q17c's extension model.** A wire change, not a database one, and not on this
  path.
- **The label-vs-host link vector.** Presentational, open, needs drawing.

## Session report — 30 Aug

Phases **0** (seam) and **2** (rail) built; phase 1 collapsed into the B6 fix
because the data audit had already answered what it was going to discover.
Suites green throughout: **4286 pytest, 1617 vitest, ruff and tsc clean**.

### What worked

**The mechanical gates caught my own defects, within minutes, twice.**
`test_theme_token_resolution.py` — written this morning for someone else's bug —
failed on `--bn-off-track` in a CSS file I had *just* written, because the
mockup skill documents a token that does not exist. And the self-review script
found `BUILTIN_IDS` hardcoding three ids in the frontend. Reading found neither.
That is now four defects this session caught by scripts and none by inspection.

**Seam before components.** Phase 0 has no design content on purpose, and its
most valuable test asserts that `/report/codebook` still resolves. Without that,
"parallel surface" quietly becomes "rewrite in place" and nobody notices until
the lens is broken.

**Deriving over declaring.** `isBuiltIn` reads the absence of an author — exact
across all nine codebooks and already on the wire — rather than restating
knowledge the server has. The provenance line keyed on the same fact, so the two
now agree by construction instead of by coincidence.

**Scoping.** Every v2 rule sits under `.v2-rail`; a script confirms none of its
seven classes collides with anything the shipped panel owns. The two lenses
cannot fight.

### Doubts — things that work and that I am not sure about

1. **The `@ts-expect-error` on the platform switch.** `switch` is a real
   attribute in Safari 17.4+ and absent from React's DOM typings, so rendering
   the platform control needs an escape hatch. It will **break loudly when the
   typings catch up**, which is the good failure — but it is still a suppression.
2. **`isBuiltIn = !author` is exact today and wrong later.** A community
   submission with no author lands under Default. Stated in the code, and the
   real fix is a field on `TemplateOut`.
3. **The optimistic toggle is silent on failure.** It re-reads the server state,
   so the switch corrects itself — but the researcher sees a switch move and
   move back with no explanation. That is the "fake success feedback" class in
   reverse and it wants a message.
4. **The rail navigates nowhere.** Phase 3 does not exist, so selecting a row
   changes only the highlight. Correct for the phase; deeply unsatisfying to
   click.
5. **No i18n on any v2 string.** "Manual tags", "Default", "Frameworks", "Your
   tags" are English literals. Deliberate while dev-gated — Specimen sets that
   precedent — but it is *exactly* the hole `CLAUDE.md` warns about: a new
   surface with zero `t()` call sites, invisible to `check-locales.py` because
   English never had the keys either. **Phase 6 must not be the first time
   anyone asks.**

### Judgement calls owed

| | what | why it is not mine |
|---|---|---|
| **1** | The four Indicative items — buttons, the `-sm`/`-lg` size axis, the Review split | Now judgeable side-by-side on real data, which is what D29 was for |
| **2** | **Q17's channel** — and note my recommendation *moved* from the activity endpoint to the events log after the extension framing dissolved two of its three objections | A reversal after arguing the other way is not one to act on quietly |
| **3** | The label-vs-host link vector | The fix is presentational and the shipped labels are editorial |
| **4** | Whether `TemplateOut` carries `builtin` explicitly | A wire change to remove an inference |
| **5** | **Q7** — nine short descriptions | Content, not plumbing |
| **6** | **Q10** — where the Codebook lab button lives | A placement, which is a design choice |

## QA plan

**The principle, and it is this repo's own scar tissue.** On 20 Aug a corpus was
run through the acceptance harness repeatedly and reported clean; one screenshot
of the same corpus in the `.app` produced three defects, none visible to 4,037
passing tests, *"because a test asserts what someone thought to ask, and nobody
had thought to ask what the pane said."* Everything below is therefore **looking
at rendered surfaces**, not running more assertions.

### What is already mechanical — do not re-check by hand

Token resolution (`test_theme_token_resolution.py`), the export-CSS selectors,
the URL-safety contract in both languages, the prototype render sweep
(`scripts/check-prototype-render.py`), the message-kind mirror, locale parity
(`check-locales.py`), and 10 rail tests each named for the decision it pins.

### Tier 1 — the two-lens comparison (the point of D29)

```bash
.venv/bin/bristlenose serve --dev trial-runs/project-ikea
```

Open `http://localhost:8150/report/`, then **Codebook** and **Codebook v2** in
two tabs on the same project. The four Indicative items are decidable here and
nowhere else:

1. **Button hierarchy** — Browse Library quiet and larger against Install
   primary. Does the destination read as findable without shouting?
2. **`.bn-btn-sm` / `-lg`** — does the size axis look like it belongs in the
   atom, or like a mockup?
3. **The Review door** — verb button plus counts on its baseline. Subordinate to
   Install, as intended?
4. **Provenance weight** — *Jakob Nielsen* against *Available by default* in the
   same rail. Does the system fact recede enough?

### Tier 2 — the states a test cannot judge

- **Toggle a codebook off in the rail.** The row knocks back; watch whether the
  switch reads as *off* rather than *broken*, and that the row is still clearly
  clickable.
- **Both switch renderings.** Safari gives the platform control, Chrome the
  fallback. **Compare them side by side** — the fallback is 26×15 by
  measurement, and the test cannot tell you it looks wrong.
- **The empty Frameworks heading.** Uninstall every framework. Does the bare
  heading plus Browse Library explain itself, or read as a bug? This is D25's
  whole claim.
- **Dark mode and the edo palette.** `--bn-colour-border-hover` as the off track
  was chosen from the shipped switch; it has never been seen at rail scale.

### Tier 3 — the app, once, with your eyes

The corpus lesson again: run it in the `.app`, not the browser. The rail is
chrome-adjacent, the WKWebView is not Chrome, and *"a feature whose whole point
is the native context"* wants the real one.

### What QA cannot yet reach, and why

**Phase 3 does not exist**, so selecting a rail row changes only the highlight.
Nothing beyond the rail is testable by hand, and the temptation to judge the
button treatments from the *prototype* instead should be resisted — that is
fixture data in a mockup, which is what D29 exists to stop.

### The check I would add before phase 6

**Grep the v2 files for `t(` and expect zero.** That is true today and
deliberate; it must stop being true before the flag defaults on. Nothing
mechanical will ask — `check-locales.py` is blind to a surface English never
enrolled — so it belongs on a human's list.
