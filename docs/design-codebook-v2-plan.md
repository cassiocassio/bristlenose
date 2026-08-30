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
