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

Phases **0** (seam), **2** (rail), **3** (codebook page), **4** (browse grid)
and **5** (destructive edges) built; phase 1
collapsed into the B6 fix because the data audit had already answered what it
was going to discover. Suites green throughout: **4286 pytest, 1630 vitest,
ruff and tsc clean**.

**Phase 3 is the read surface.** The floor's authoring apparatus — add and
delete a group, add, rename and delete a tag, drag between groups — is lifted
from the shipped panel in a later step, deliberately: it is ~400 lines of
drag-and-drop whose entire value is that it already works, and re-deriving it at
the end of a long session is how it acquires new bugs.

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

**Scoping, and reuse over reimplementation.** A script confirms **zero** v2
selectors clash with `codebook-panel.css`, and the page emits **17 shipped
classes against 19 of its own** — `Badge`, `MicroBar` and the colour helpers are
the shipped components, so the histogram alignment this repo has already paid
for is inherited rather than approximated.

**The orphan check earned its keep immediately.** It found `bn-btn-sm` emitted
and styled nowhere — the Review button would have rendered at the default size,
corrupting the exact comparison it exists for — and `contentinner`, a
prototype-only wrapper (`AppLayout` provides `.bn-main`).

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
4. **The Review door leads nowhere yet.** Q15 says it opens the *existing*
   modal, and phase 5 wires it. Opening a half-built one would be worse than not
   opening it, and rebuilding it is explicitly ruled out — so the handler is
   empty and says why.
5. **Install and Uninstall are inert.** Phase 5 owns them, because that is the
   phase where a bug loses work: install-is-apply spends money, and D20's
   uninstall stops preserving. Wiring them early, cheaply, is the worst option.
6. **The size axis is scoped to v2, not promoted.** `.bn-btn-sm` / `-lg` live in
   `codebook-v2.css` so the QA comparison renders truthfully without a
   design-system decision being taken by accident. If v2 ships, they move up.
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


### Phase 4 — what it found

**Two defects the tests caught, both mine and both invisible to reading.** The
sentiment card said *"On by default"* **twice** — once as provenance, once where
the button would be — and `bn-v2-browse` was a testid on both the Browse Library
button and the grid it opens. The first is the more interesting: that slot is now
empty on purpose, because the provenance line is where *what is this* belongs,
and a second copy in the button's place is **the absence of a control pretending
to be one**.

**And `tsc` caught what Vitest could not.** The test's handler overrides were
typed `Record<string, Mock>`, which the suite accepted and `tsc -b` refused —
exactly the split `sharedFormatContract.test.ts` warns about in its own comment.
Vitest passing is not the gate.

**D12 needed one qualification against a later decision.** It says the card's
author line reads *"Built in"* for the three with none; **D23 supersedes that**
with *On by default* / *Available by default*, which distinguishes sentiment
(arrives applied) from UXR (ships with the product, commonly installed **and
disabled**). The later, more precise decision wins.

**Still inert, and deliberately.** Install and uninstall on both the card and the
page call empty handlers. Phase 5 owns them because that is the phase where a bug
loses work: install-is-apply spends money, and D20's option A makes uninstall
stop preserving. A cheap early wiring is the worst available option.


### Phase 5 — the destructive edges, and three bugs found on the way

**D20 option A is implemented.** Uninstall keeps nothing: this project's
QuoteTags, links, enable opinion, AutoCode job and proposals all go. The
instance-scoped `CodebookGroup` / `TagDefinition` rows go **only when no other
project still links them** — without that guard this would be A1 one level up,
and a worse bug than the one it replaced.

**Three real defects surfaced, none of them the thing I set out to change.**

1. **A1** — `remove_framework` deleted `QuoteTag` by `tag_definition_id` with no
   project filter, and those are instance-scoped. Uninstalling from one study
   stripped the framework from every other study in the instance. The impact
   endpoint had the same hole in its *counting*, which is worse in a quiet way:
   it overstated the loss, and that number is the one the researcher decides on.
2. **The import branch's proposal reset** filtered on `tag_definition_id` too,
   so re-importing here rewrote **another project's** accepted proposals back to
   pending. Same shape as A1, one table over. Removed — since option A there is
   nothing of ours to reset, so the only rows it could reach belong to someone
   else.
3. **`restorable` was computed instance-wide** (register **A3**), so a framework
   installed in any project read as restorable in every project. Retired with
   the thing it described.

**And the parity check found the one that would have shipped silently:**
`onInstall` called `importCodebookTemplate` and nothing else, so installing put
the tags in the codebook and **coded nothing** — the separate Apply step v2
exists to remove, left half-implemented and invisible. Install is now import +
job + activity-chip registration.

**Q14 closed.** `/codebook/templates` is `SERVER_ONLY` while `/codebook` is
embedded, so a bare `Promise.all` would have blanked the whole lens in an
exported report. Tolerated separately; Browse Library and the install controls
are hidden offline, not disabled.

### What phase 6 is waiting on

**The floor's authoring apparatus is the single remaining functional gap** — add
and delete a group, add, rename and delete a tag, drag between groups, drop to
merge. Seven API calls, **15 drag handlers** and the inline-edit machinery,
inside a 1,545-line component.

The user's instruction was *"all of that we take **directly** from the existing
implementation"*, and the faithful reading is **extraction into a component both
lenses use** — not a rewrite in v2, which would be two implementations of one
behaviour. That is a refactor of the **shipped** lens, so it carries real risk to
the thing D29 exists to protect, and it wants its own session with the shipped
lens under test rather than the tail of a long one.

Phase 6's other gates are unchanged: the four Indicative items still want your
eye on the parallel surface, and the flag defaults on only after that.

### Phase 6a — the authoring extraction

**Done 30 Aug 2026.** The floor's authoring apparatus is now one implementation
that both lenses render, which was phase 6's blocker. The instruction was that
v2 take it *directly* from the shipped implementation; the faithful reading is
extraction, not reimplementation, because two implementations of one behaviour
drift from the day they ship.

#### What moved

| From | To | What |
|---|---|---|
| `islands/CodebookPanel.tsx` L55–521 | `components/CodebookAuthoring.tsx` | `TagRow`, `GroupSubtitle`, `CodebookGroupColumn` — **verbatim**, three `export` keywords and the props split aside |
| same file, the 12-handler cluster | `hooks/useCodebookAuthoring.ts` | seven API calls, the drag ref, the pending merge |
| the container's render | `NewGroupPlaceholder`, `MergeConfirm` | the new-group card and the centred merge dialog, each now a component both lenses call |

The move is provable rather than asserted: `git show 901d0586:…/CodebookPanel.tsx
| sed -n '55,521p'` diffs against the new file in **24 lines**, all of them the
three exports and the interface split. Nothing else was touched, and the CSS
was not touched at all — `git diff bristlenose/theme/` is empty.

v2's page had its own read-only `Group`/`TagRow`. Both are deleted. There is no
second renderer left.

#### The props contract

```ts
interface CodebookGroupHandlers {          // components/CodebookAuthoring.tsx
  onUpdateGroup, onDeleteGroup,
  onCreateTag, onDeleteTag, onRenameTag,
  onDragStart, onDragEnd, onDropTag, onMergeDrop
}

interface CodebookAuthoring {              // hooks/useCodebookAuthoring.ts
  groupProps: CodebookGroupHandlers        // spread onto CodebookGroupColumn
  onCreateGroup, onDropNewGroup            // the new-group card
  pendingMerge, onConfirmMerge, onCancelMerge   // feed to MergeConfirm
}

useCodebookAuthoring({ groups, onChanged })
```

**The bundle is the load-bearing part.** Ten separately-named props listed at
three call sites is precisely how the two implementations this extraction
removes would grow back, one prop at a time. `groupProps` is typed as the exact
shape the hook returns, so a lens cannot wire nine of ten and still compile.

`groups` is **every** group including the frameworks', not the ones on screen: a
new group's colour set is chosen by what is unused, and asking only the visible
groups would hand out one a framework already holds. `onChanged` is each lens's
own refetch — v1's `fetchData`, v2's `reload`.

**Read-only is decided by the group, not by the lens.** `CodebookGroupColumn`
reads `is_default` / `framework_id` / `isExportMode()` and gates itself, so both
lenses inherit one rule instead of each remembering it. That is why v2 passes
the handlers on a framework page too and gets a read-only card anyway. The one
thing the *page* decides is the new-group card, gated on `book.floor` — only the
floor grows groups.

#### The one behaviour that changed, and why

**D26 now exempts the floor.** The bleak "This codebook has no tags." governs *a
codebook you installed*; the floor is not one — it is the surface you author.
Answering an empty floor with a sentence instead of controls would leave a
researcher with no way to begin, which the shipped lens never does. A framework
with no tags still gets the sentence, pinned by a test either way.

#### What the extraction could not preserve — and did not try to

Four of these are **defects it found in the shipped lens**. None is fixed here:
this was a refactor, and a fix smuggled into a move is invisible to review.

1. **`.tag-row.dragging` never fires in either lens.** The reduced-opacity drag
   state is applied only by `theme/js/codebook.js` — the frozen vanilla
   renderer. React's `TagRow` composes `["tag-row", isMergeTarget && "merge-target"]`
   and has done since the migration. So the CSS rule is live and unreachable in
   the SPA. Preserved exactly; the parity tests assert `.merge-target`, which
   React does own, and deliberately assert nothing about `.dragging`.
2. **`.codebook-panel .tag-row:hover` is likewise dead.** Nothing in the React
   tree carries `.codebook-panel` — it is a vanilla-renderer ancestor. The row
   hover background does not exist in the SPA, in either lens.
3. **The group title and subtitle have no keyboard route.** `EditableText` with
   `trigger="click"` renders no `tabIndex`, no `role`, and no key handler until
   it is already editing. Not brought to parity: `EditableText` is used across
   the app, so an a11y change there is a different piece of work with a
   different blast radius. **The badge, however, already had parity** — `Badge`
   emits `role="button"` + `tabIndex={0}` + Enter/Space whenever `onClick` is
   present, so inline rename has been keyboard-reachable all along. Half the
   gap named in the brief was already closed.
4. **A researcher's tag can be dropped onto a *framework's* group card and it
   moves there.** The `.codebook-group` drop handler is not gated by
   `isFramework`, so the card is read-only for every control except this one.
   Shipped behaviour, preserved verbatim. In v2 it is unreachable — the floor
   and a framework are different pages — which means the deletion step of D29
   would close it as a side effect.
5. **Failures `console.error` and stop.** No toast, no revert, no retry: a
   rename that fails leaves the old name on screen with nothing said. Carried
   over unchanged, and it is the same class as the optimistic toggle already
   listed under Doubts.

Two cosmetic consequences in v2, both intended: its group cards gain the header,
the close button and the total row they never had, and the per-tag number is
`.tag-count` rather than `.group-total-count`. Its old `TagRow` also drew a bar
at count 0, where the shipped one draws none. v2 now looks like v1 because it
*is* v1.

#### Do they genuinely share one implementation?

Yes, and it is asserted rather than believed.
`islands/CodebookAuthoringParity.test.tsx` runs **thirteen** assertions against
both lenses from one `describe.each` — 26 tests — mounting `CodebookPanel` and
`CodebookV2` against the same fixture. It covers the details a reasonable test
would not think to ask for, because those are the ones a move loses: the
confirmation that is **skipped** for a zero-count tag, the delete button that is
**absent** on the floor group, and the delete dialog's **position** inside the
card rather than over the lens. A behaviour holding in only one lens fails the
table.

What that table cannot reach is visual: jsdom loads none of
`bristlenose/theme/`, so `cursor: grab → grabbing` and the `.merge-target` ring
are asserted as classes, never as computed style. Those want the Tier-1
two-lens comparison, which is now genuinely two-lens.

One harness note worth keeping: `TagRow`'s drag-start clones the badge into
`document.body` as `.drag-ghost` and removes it on the next animation frame.
Testing-library's cleanup unmounts its own container, not a node the component
appended beside it, so a ghost outlives the assertion after a drag and
`getByText` finds two. The fix is to filter ghosts when querying — **not** to
sweep them in `afterEach`, which makes the component's own `removeChild` throw
`NotFoundError` out of a callback nothing awaits.

#### Two things phase 6 inherits from this

- **Chunking.** Exported through the `components` barrel, the apparatus landed
  in the always-loaded chunk and charged the landing route ~9.7 kB for markup no
  first paint renders. Both lenses now import it by path, and it sits in a lazy
  chunk they share. Confirmed against `index.html`'s modulepreload list, which
  names `components-*.js` and not `useCodebookAuthoring-*.js`.
- **The size glob excludes `CodebookPanel-*.js` by name and does not exclude
  `CodebookV2-*.js`,** so the budget already counts the whole v2 lens while
  discounting v1's. Harmless today (204.61 kB against 220) and worth tidying at
  the deletion step, when one of those two filenames stops existing.

#### And one hole this closed by accident

Phase 6's owed i18n item is smaller than it was. v2's group cards now render
through the shipped component, so `+ tag`, `Total`, `New group`, `Add subtitle…`
and the delete-confirm strings are `t()` calls in all 21 locales rather than the
English literals v2's own `Group` emitted. The page **head** — "Review",
"Install", "Uninstall", "This codebook has no tags." — is still untranslated,
and the check the plan asks for (grep the v2 files for `t(` and expect zero)
must now be read as *the v2-specific chrome*, not the whole lens.
