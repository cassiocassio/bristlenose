---
status: partial
last-trued: 2026-08-31
trued-against: HEAD@main 994d822c on 2026-08-31
---

> **Trued 31 Aug 2026.** The previous header read `last-trued: 2026-08-29`
> against `3802f2af` — *"true the copr reference line…"*, a **28 Aug** commit
> about Fedora packaging that predates every commit which built this lens. The
> header read fresh and the body predated the entire build, so a pointer sweep
> passed this doc. Five decisions below were **revised in code** between 30 and
> 31 Aug and each revision is annotated inline; where a decision now differs per
> surface, the doc says so rather than restating the superseded form.

# Codebook v2 — presentation, layout, flow

**The mockup is the spec.** [`docs/mockups/codebook-v2.html`](mockups/codebook-v2.html)
is the working surface; we iterate there and this file records what it settles.
Read the mockup first. This doc is the record, not the driver.

> Naming collision, so nobody trips on it: `docs/mockups/mockup-codebook-panel.html`
> is titled "CODEBOOK PANEL MOCKUP v2" but is the **Feb 2026 Phase-2 prototype**,
> unrelated to this work. Likewise `design-codebook-ecosystem.md`'s "UXR codebook
> v2" is a *content* version of `uxr.yaml`. This is the only doc about a v2 **UX**.

## Scope

Agreed at the outset, and worth not re-litigating:

- **Presentation, layout and flow.** Not the data model, not the two axes
  (install / enable), not the state machines. Those shipped and they hold.
- **The underlying primitives are mostly fine.** Badge, switch, status dot,
  micro-bar, confirm dialog, the token set — inherit them.
- **Inherit as much as possible.** Anything genuinely new wears `.is-new` in the
  mockup so invention stays visible and countable. A mockup that fills up with
  dashes is a signal we over-invented.
- **Migration is deferred** and is deliberately not being designed yet.
  Presentation-only scope should keep it cheap — no schema change, no data move.

## Issues

Raised in no particular order. Recorded in the raiser's words, with whatever
mechanical substrate is already known underneath — the substrate is context, not
a proposed fix.

### I1 — a very long scrolling page of all the codes, rapidly unmanageable

**Substrate.** Everything renders flat and at once. `.codebook-grid` is
`repeat(auto-fill, minmax(240px, 1fr))`, every researcher group is a column,
every *enabled* framework contributes all of its groups as more columns, and
each column is full-height with all its tags. There is no pagination, no
virtualisation, no per-group collapse, and no density control. The only thing
that removes height is the framework **disable** switch, which folds a whole
codebook away — a lifecycle control being used as a layout one, because it is
the only lever there is.

The page therefore grows without bound in the one direction it cannot afford to:
a project with the floor plus three frameworks is already past a screen before
any of the researcher's own work is on it.

### I2 — enabled/disabled, installed/not-installed, applied/not-applied: too many concepts for turning on and off

**Substrate.** Three lifecycle axes, plus a fourth that lives at a different
grain, and all four are reachable from the same header row:

| Axis | States | Grain |
|---|---|---|
| **Install** | not installed &middot; installed &middot; *restorable* | per codebook |
| **Enable** | enabled &middot; disabled | per codebook |
| **Apply** | not applied &middot; coding &middot; proposals pending &middot; applied | per codebook |
| ~~**Hide**~~ | ~~shown &middot; hidden~~ | ~~per group~~ |

> **Correction, 29 Aug 2026 — the Hide row does not belong in this table, and the
> error was mine.** The first draft said four axes were "all reachable from the
> same header row". Verified against the code: `CodebookPanel.tsx` contains
> **zero** references to `EyeToggle`, `hiddenTagGroups`, or any hide affordance.
> Hide lives only in `TagSidebar.tsx` and `TagGroupCard.tsx` — both **Quotes**-lens
> surfaces. `design-codebook-state-model.md` §5 had this right all along: its
> Codebook-lens row reads `(n/a)` under Hide. I misread the doc into the issue.
>
> **The codebook lens therefore carried three axes, not four** — and after D4,
> **two**. See D7.

So one framework had roughly seven reachable presented states, across three axes
on this lens.

**Two tells that this is the real problem and not a labelling one.** First, the
canonical spec opens with a *glossary* — `design-codebook-state-model.md` §1,
"Precise words, because loose ones (mixing 'hide' with 'disable') caused the
churn". A design that needs a dictionary before it can be discussed is telling
you something. Second, the browser-extension model it borrows from separates the
axes **by surface** — install lives in the store, enable lives in the extensions
page — while here Uninstall and the enable switch sit on the same row, inches
apart, in a design whose own stated principle is *"no control does two jobs; no
surface does two jobs."*

And the distinction the axes are supposed to encode is not even true: uninstall
is documented as reversible and retained, but it deletes every `QuoteTag` and
resets accepted proposals to pending (register A1, B2). So "reversible toggle"
versus "done with it" does not survive contact with what the buttons do.

### I3 — near-full-screen modals with their own scrolling, for content that just wants the screen

**Substrate.** `.codebook-modal` is `max-width: 56rem`, `max-height: 85vh`,
`overflow: hidden`, and its `.codebook-modal-body` is `overflow-y: auto` — an
inner scroll container, over a page that is itself scrolling (I1). Two of the
lens's surfaces are built this way:

- **Codebook Library** — a catalogue of nine tiles plus section headers. A page.
- **AutoCode Review** — a histogram, a dual slider, three zone counters and three
  zone lists that can run to hundreds of proposals. Emphatically a page.

Both take ~85% of the viewport to say "I am temporarily over something", then
immediately need their own scrollbar because they are not temporary at all. The
lens they cover is a route (`/report/codebook`); neither of these is.

The Library additionally takes the screen without taking a modal's
responsibilities: no focus trap, no `useInert`, no Escape handler (register C4).
`ThresholdReviewModal` has all three, so the two full-screen surfaces do not even
agree with each other about what being modal obliges.

### I4 — a framework is described by different pages before and after it is installed

**Substrate.** The same taxonomy renders **three** times, in three different
compositions:

| Where | What it shows |
|---|---|
| **Library tile** | title, author, description, six sample badges (2 tags &times; 3 groups), Install |
| **Library preview** | title, author, description, *every* group as a column, **author bio, author links** |
| **Lens section** | title, author, groups as columns *with* counts and micro-bars, Apply / Uninstall / switch |

The asymmetry is not just three layouts — it is **loss on adoption**. `author_bio`
and `author_links` render only in the preview (`CodebookPanel.tsx:1510–1517`); the
installed section renders `title` and `author` and nothing else. So the richest
description of a framework — who wrote it, why, where to read more — is reachable
only *before* you commit to it, and disappears at the moment it becomes yours.
To read Garrett's bio again you must uninstall, or open the Library and find the
tile you already own.

The group column itself is also three-ways forked: read-only-no-counts in the
preview, read-only-with-counts in an installed framework section, and fully
editable in the floor.

<!-- I5 … append below as they land -->

## Prior art — extension and connector mechanisms

Studied 29 Aug 2026 from screenshots of Safari Extensions, Chrome
`chrome://extensions` + Chrome Web Store, Edge `edge://extensions` + Edge
Add-ons, the Claude connectors directory, and the Mac App Store's editorial
"best Safari extensions" page.

The install/enable mental model is the right comparison — it is the same problem,
solved four times, by teams with far more usage data than we have. **They agree
with each other much more than any of them agrees with us.**

### 1. How many axes, and how each is expressed

| | Axes | Enable expressed as | Install expressed as |
|---|---|---|---|
| **Safari** | 2 | checkbox, in the master list | **button**, in the detail pane only |
| **Chrome** | 2 | toggle, on the card | button (Remove) on the card + confirm |
| **Edge** | 2 | toggle, on the card | button (Remove) on the card |
| **Claude connectors** | 1 (visible) | — | `+` / green check on the card |
| **Bristlenose** | **4** | switch, in the section header | **button, in the same header** |

**Learning.** Nobody ships more than two axes. And in every case **enable is a
toggle or checkbox and install is a button** — the two axes never share a control
idiom, so you can tell them apart without reading. Our header puts Apply and
Uninstall side by side as two identical `.bn-btn` siblings, then a switch: the
destructive control looks exactly like the routine one.

**Safari's asymmetry is the sharpest idea in the set.** The reversible act
(enable) is one click from the overview. The irreversible act (uninstall)
requires selecting the row *and* is only available one level deeper. Given our
uninstall deletes `QuoteTag` rows (register A1), that gradient is worth stealing
outright.

### 2. Where each job lives

| | Catalogue | Manager | Detail | Modal anywhere? |
|---|---|---|---|---|
| **Safari** | Mac App Store (separate app) | Settings pane | right pane, master&ndash;detail | no |
| **Chrome** | Web Store (a website) | `chrome://extensions` (a page) | own page | no |
| **Edge** | Edge Add-ons (a website) | `edge://extensions` (a page) | own page | no |
| **Claude** | directory | same surface | &mdash; | **yes** |
| **Bristlenose** | Library | the lens | preview, inside the Library | **yes** |

> **Corrected 29 Aug 2026.** The first draft of this row read the separation as a
> design lesson — "putting the catalogue somewhere else is what makes install
> legible as its own axis." **That was wrong, and it is worth recording why.**
> Apple, Google and Microsoft each already operate a store for reasons that have
> nothing to do with extensions; the separation is Conway's law showing up in the
> UI, not an insight about install semantics. Nobody built the Mac App Store to
> disambiguate a checkbox. Reading an org artefact as a principle would have sent
> v2 chasing a structure we have no reason to want.

**Learning, restated.** Location is not the lesson; **presentation is.**

- **The catalogue stays inside the app**, and that is settled (D2). We have no
  store to maintain and no reason to acquire one. The entire corpus is nine
  bundled YAML files — no download, no update channel, no signing, no versioning.
  An external catalogue at this size would be pure overhead.
- **The relevant comparator is therefore Claude's directory, not Safari's** — the
  one that keeps catalogue and manager on the same surface, and carries 2,252
  items there with search and a filter. In-app scales fine.
- **What survives from the native three is the presentation of the manager**, and
  it survives independently of where their catalogue lives: Safari's manager is
  master&ndash;detail *in one window*, with no overlay, no scrim and no second
  scrollbar. That is a straight answer to I3 and it costs us nothing to adopt.

So the modal criticism stands, and the separation argument does not.

### 3. What the manager shows

| | Per-item content in the manager |
|---|---|
| **Safari** | name + icon in the rail; detail on selection |
| **Chrome / Edge** | icon, name, ~2 lines of description, controls |
| **Claude** | icon, name, one line, one control |
| **Bristlenose** | **every group, and every tag in every group, always** |

**Learning, and this is the answer to I1.** No comparable manager renders the
item's *payload*. They render identity and state; contents are one level down.
The codebook lens is the only one of the five that puts the entire contents of
every installed item on the overview, which is precisely why it grows without
bound. The fix is not smaller cards — it is that a manager is a list.

### 4. What survives installation

| | Description after install | Author / provenance after install |
|---|---|---|
| **Safari** | kept, in the detail pane | kept — "1.11 from Lingopie" |
| **Chrome / Edge** | kept on the card | kept, via Details |
| **Claude** | kept on the card | kept |
| **Bristlenose** | replaced by tag columns | **`author_bio` and `author_links` are lost** |

**Learning.** Ours is the only one that *loses* information at the moment of
adoption (I4). Everywhere else the detail view is the same object before and
after; installing changes its state, not its description.

### 5. Grouping, search, and the editorial layer

- **Grouping is by provenance, not by state.** Edge groups "From other sources";
  Safari "Installed"; Chrome "My extensions". Our sidebar's three headings mix
  provenance (Manual tags, Default) with availability (Library) — two different
  kinds of thing in one column.
- **Search lives in the catalogue, never the manager** — Claude's directory has
  search, a filter and "Show all 2252"; the Chrome and Edge stores have search
  and category rails. Their managers have search only once you have dozens of
  items. **Our inversion is instructive**: at nine templates our catalogue does
  not need search, while our manager — which shows every tag — needs it badly.
  That is a symptom of §3, not an argument for a search box.
- **There is a separate editorial surface** teaching the concept: the App Store's
  illustrated "best Safari extensions" page, Edge's "Editor's pick", the Web
  Store's category rail. We have nothing equivalent, so the Library modal has to
  be catalogue, teacher and manager at once.

### 6. The axis extensions do not have

Extensions have install and enable. They have no **Apply** — because an extension
does not cost money each time it runs. Our third axis has no analogue in the set,
and copying a two-axis idiom while carrying four is part of why the vocabulary
needs a glossary (I2).

The nearest shape in the prior art is **Safari's Permissions block** — "Web Page
Contents and Browsing History &hellip; Edit Websites&hellip;", the place where you
say *what this thing is allowed to act on*. That is much closer to what Apply
actually is (a scope grant over a corpus, with a cost) than to a lifecycle state.
Worth testing in the mockup: **Apply as scope, presented like permissions, rather
than Apply as a button that sits beside Uninstall.**

And the fourth axis, per-group hide, has no analogue at all — no extension
manager lets you hide *part* of an extension.

## Possible solutions

**The mapping is many-to-many.** An issue may have several candidate solutions;
a solution may resolve several issues, or dissolve one and only dent another.
So solutions are numbered independently of issues, and each carries an
`Addresses:` line. The coverage matrix at the end is **derived from those lines**,
never maintained by hand — so it cannot drift, and a blank column is a real
signal that an issue has no candidate yet.

Each entry:

```
### S<n> — <the move, in one line>
Addresses: I<n>, I<n> (partial)
Inherits:  <what existing component/pattern it reuses>
Invents:   <anything genuinely new, or "nothing">
<the reasoning; what it costs; what it forecloses>
```

`Invents: nothing` is the target for most of them — the mockup marks anything new
with `.is-new` so the count stays honest.

### S1 — the codebook sidebar is permanent, and one codebook always has focus

Addresses: **I1** (fully), **I4** (substantially), **I3** (partially), **I2** (partially)
Inherits:  `SidebarLayout` left-panel push mode &middot; `CodebookSidebar` rows, dots and `activeId` &middot; `TagSidebar`'s precedent
Invents:   nothing structural — see the open question about the detail pane

Master&ndash;detail. The sidebar stops being a table of contents and becomes the
**master list**; the pane beside it shows exactly one codebook at a time.

**Why it is cheap.** `SidebarLayout` is already a six-column grid
(`toc-rail | toc-sidebar | center | minimap | tag-sidebar | tag-rail`) whose left
panel already has a **push mode** — pinning it open on this lens is
configuration, not new structure. `CodebookSidebar` already tracks a single
`activeId`, already defaults it to the floor, and already renders installed and
not-installed rows with a status dot. Most of this solution is *already built and
being used as navigation*; S1 promotes it to being the primary control.

**And there is in-house precedent.** `TagSidebar`, on the Quotes lens, already
renders the whole codebook as a compact tree — frameworks, groups, tags — with
per-tag controls. So "the codebook is a list" is not an import from Safari; we
already ship it one lens over, on the same data. That makes this the strongest
*inherit* argument available, and it means the two lenses would stop disagreeing
about what a codebook looks like.

**What it does to each issue.**

- **I1 — dissolved. Measured 29 Aug, after an over-hedge.** One codebook renders
  at a time, so the concatenated page is gone.

  _I first graded this "substantially", reasoning that a large single codebook
  would still scroll — sixty tags across six groups. **That was wrong, and the
  error was in the unit.** The grid is `repeat(auto-fill, minmax(240px, 1fr))`,
  three columns at the 832px content width, and tags flow **inside** a group card.
  Page length therefore scales with **group count**, not tag count._

  Counted across the nine shipped codebooks:

  | | groups | grid rows at 3-up |
  |---|---|---|
  | worst single codebook (nielsen) | 10 | **4** |
  | median single codebook | 6 | 2 |
  | **all nine concatenated — what ships today** | **56** | **19** |

  Nineteen rows plus nine section headers plus the floor is the long scrolling
  page. Four rows is not, by any reading. The concatenation *was* the issue, and
  S1 removes it outright.

- **I4 — substantially, conditional.** _Graded down 29 Aug, see the master-list
  clarification below._ An **installed** codebook gets one detail view, so the
  section-versus-preview fork narrows. But if not-installed codebooks live on a
  separate browse surface, a codebook is still described in two places. **I4
  closes only if that surface reuses the same detail component**, differing in
  which controls it offers rather than in what it renders. That is a cheap
  condition to meet and an easy one to miss.
- **I3 — partially.** _Graded down 29 Aug from "substantially"._ The first draft
  reasoned that if not-installed rows sat in the master list, the picker would
  have nothing left to do and the Library modal would dissolve — closing register
  C4 by deletion rather than by repair. **The master list is installed-only, so
  that does not happen.** Browsing still needs a home, and S1 does not supply one — _S2 does_.
  What S1 does contribute is removing the installed-codebook content *from* the
  modal; what remains inside it is the genuine catalogue. The AutoCode Review
  modal is untouched throughout — different kind of content.
- **I2 — partially.** It does not reduce the four axes. It gives each one a
  *place*, which is what makes them legible: Safari's asymmetry becomes available
  — enable as a control in the list (reversible, one click from the overview),
  install/uninstall in the detail pane (irreversible, a level deeper). D1 gets a
  home rather than just a rule.

**Selection semantics, confirmed 29 Aug.** Stated from the content side: *stop
showing a long scrolling page, show the item with focus — the single selected
left-hand choice.* So selection is **single**, it **lives in the master list**,
and the detail pane is a **pure function of it** — no independent state, no
multi-select, no second place a thing can be "current". That is worth pinning
because it is what makes the pane cheap: it renders one id, and the sidebar owns
which.

**Open questions this raises, none of them blocking.**

1. ~~**Does "always open" mean un-hideable?**~~ **Answered by D9:** open by
   default, closable, and traversable by next/prev when closed. It cannot be
   un-hideable — `hideAllSidebars()` sets `tocMode: "closed"` and Focus Mode calls
   it, so the rail *will* be closed by shipped features.
2. **What is the detail pane made of?** Reusing `.codebook-grid` scoped to one
   codebook inherits everything and invents nothing. A purpose-built pane would
   be the first thing in the mockup to wear `.is-new`.
3. **What does it foreclose?** The cross-codebook overview — seeing every
   codebook's tags at once. Worth asking whether that is a real job; if it is, it
   already belongs to `TagSidebar` on Quotes, not here.
4. ~~**Do not-installed codebooks live in the same list?**~~ **Answered 29 Aug:
   no. The master list is what you have installed.** I had speculated yes, from
   Safari's "Add Extensions" row — wrong, and it cost two gradings above.

   This lands us on the **Chrome/Edge shape**: the manager lists installed items
   only, the catalogue is elsewhere. Held together with D2 (the catalogue stays
   in the app), that means *an in-app browse surface that is not the master list*
   — which is now the open decision, and the thing standing between us and I3.

   It also makes the sidebar honest. Today it renders installed and not-installed
   in one column, so a row is navigation for some codebooks and a Library door for
   others — one affordance doing two jobs. Installed-only removes that, and the
   three headings collapse to pure provenance (the floor, then what you have
   added), which is exactly how every comparator groups.

### S2 — three surfaces, no modals: sidebar, browse page, codebook page

Addresses: **I3** (fully), **I4** (fully), **I1** (via S1, unchanged), **I2** (partially)
Inherits:  the preview's existing full-detail layout, promoted to a route &middot; `.picker-card` &middot; the router
Invents:   nothing — every piece exists; two of them stop being modal

| Surface | Contains | Reached from |
|---|---|---|
| **Content sidebar** | installed, manual and built-in codebooks **only** | always present (S1) |
| **Browse page** | **all** codebooks as cards — summary detail, an install affordance, a learn-more affordance (the title, or anywhere on the card) | a door from the sidebar |
| **Codebook page** | the **full, maximal** detail and layout we already have — currently the modal preview | a card's title from browse; a row from the sidebar |

**No modal versions of any of it.** Just a card view and a full page view.

**What it removes.** Today: open the Library modal, scan a list nested inside it,
click a tile, read the preview *in the same modal*, install. That is a click and
an entire layer of listing — a list inside a modal inside a page — and the modal
brought an 85vh ceiling and its own scrollbar with it. S2 deletes the layer
rather than tidying it.

- **I3 — dissolved.** There is no Library modal to criticise. Register **C4**
  (the modal has no focus trap, no `useInert`, no Escape) closes by deletion
  rather than repair, which is the cheapest possible fix for it.
- **I4 — dissolved**, and this is the condition I named when grading S1 down:
  *"I4 closes only if the browse surface reuses the same detail component."*
  S2 specifies exactly that. One page per codebook, reached two ways, with
  install/enable state shown on it. `author_bio` and `author_links` stop being
  pre-purchase-only, because there is no longer a before-page and an after-page —
  there is one page whose **state** differs.

**Interpretation flagged, because it is load-bearing.** Three surfaces are named,
but an installed codebook's detail has to live somewhere. I read *"the installed,
not installed, enabled, disabled state should be clear on the cards and whole
page view"* — **whole page view, singular** — as meaning the learn-more page **is**
the codebook page, for installed and not-installed alike, varying only by state
and by which controls it offers. That reading is what closes I4; the alternative
(sidebar gets its own detail pane, separate from learn-more) would reopen it by
reintroducing two descriptions. **Confirm before building.**

**Open: does "no modals" reach the AutoCode Review?** The rule is stated over the
codebook browsing surfaces. The Review modal is a different kind of content —
proposals across quotes, not codebook identity — and I have not assumed it is
included. It is the last modal standing either way.

<!-- S3 … append below as they land -->

### Coverage

| | I1 | I2 | I3 | I4 |
|---|---|---|---|---|
| **S1** | ● | ◑ | ◑ | ◕ |
| **S2** | ◑ | ◑ | ● | ● |

● dissolves it &middot; ◕ substantially &middot; ◑ partially &middot; · untouched

**I1, I3 and I4 are closed** — I1 by S1, I3 and I4 by S2. I2 is closed by the
decisions rather than by a solution (D4 removed an axis, D7 established hide was
never on this lens). The remaining opens are all newly raised, not carried over.


## Settled by iteration

### D1 — enable is a toggle or a checkbox; install is a button. Never two buttons.

Confirmed 29 Aug 2026 from the prior art, where it holds without exception across
Safari, Chrome, Edge and the Claude directory. The two axes never share a control
idiom, so they are separable at a glance, before reading a label.

**What it settles immediately.** The switch is already right — enable is a
toggle. Uninstall is already right — install is a button. The problem is that
**Apply is also a button, sitting next to it**, so the routine act and the
destructive one are the same shape, the same weight and the same colour.

**What follows, combined with Safari's asymmetry** (reversible act one click from
the overview; irreversible act only in the detail, a level deeper): **Uninstall
leaves the section header.** That is not a new idea — `design-codebook-library.md`
already specified it and it was never executed (register C3). The rule and the
prior art now agree with the spec, so it stops being a preference.

That leaves exactly one button and one toggle in the header, which is the shape
every one of the four comparators uses.

**What it does not settle:** what Apply becomes. It stays a button here for now,
and §6's "Apply as scope, presented like permissions" is the live alternative.
Nor does it settle where Uninstall goes — the Library tile already has one
(shipped), so it may need no new home at all.

Frame: **V1** in [`mockups/codebook-v2.html`](mockups/codebook-v2.html).

### D2 — the catalogue stays inside the app

Settled 29 Aug 2026. We are small, we maintain no store, and the whole corpus is
nine bundled YAML files — the size argument that pushes other products to an
external catalogue does not exist here. Whatever v2 does with the Library, it
does in the app.

This is a v1 decision, not a permanent one. The far-future shape — a public
codebook library as a website you browse, with community submission — is parked
in the maintainer's private planning notes, kept outside the public tree. It
would change the catalogue's *location*; it would not change anything D1 or the
prior art settled about its controls.

### D3 — the enable toggle moves to the sidebar row, Safari-style

Settled 29 Aug 2026. D1 fixed the *idiom* (enable is a toggle or checkbox,
install is a button). This fixes the **placement**, and adopts Safari's gradient
whole: the reversible act sits in the master list, one click from the overview;
the irreversible act sits in the detail pane, a level deeper.

**This reverses a settled decision, deliberately.** `design-codebook-state-model.md`
§8 says the codebook-lens sidebar is *"state + navigation only — a blue/grey
status dot echoing the switch, **never a control**."* That rule was written for a
sidebar that was a **table of contents**. Under S1 it is a **master list**, which
is a different object, and a master list carrying a per-row toggle is exactly
what every comparator ships. The old rule is not being broken so much as
outlived — but it is a reversal and the state-model doc will need truing.

**The status dot goes.** It existed to *echo* the switch. With the switch in the
row, the echo is duplication. Pure deletion — nothing invented.

**Superseded again by D15** — the enable control is now the platform switch where one exists; the mini toggle is deleted, and the switch-or-checkbox question is moot.

**Superseded in part by D11** — the page no longer carries a copy of this toggle; the rail owns it alone.

**Open: switch or checkbox.** Both satisfy D1. `.sw` is 38&times;22 and already
the codebook's idiom; `.bn-checkbox` is 14&times;14, already shipped in
`atoms/checkbox.css`, and is what Safari uses in a dense list — rows are the one
place the switch's bulk actually costs something. Drawn both ways in the mockup
rather than argued.

### D4 — installing *is* applying. There is no separate Apply step.

Settled 29 Aug 2026. Choosing to install a codebook runs it, and that costs
tokens. The third axis is removed from the UX.

**This reverses `design-codebook-library.md` Principle 1** — *"Cost-safe play.
Getting a codebook onto your workbench is free. **Apply** (AutoCode) is the *one*
deliberate spend."* Now install is the one deliberate spend. The doc will need
truing.

**The reasoning, in the raiser's words.**

1. **It is relatively cheap.** Applying a codebook is not the kind of spend that
   earns its own confirmation step.
2. **There is not much you can learn from the installed state that you cannot
   learn from the browse surface.** This is the sharpest of the three: the
   installed-but-unapplied state renders the codebook's groups and tags with
   every count at zero — which is precisely what the catalogue already showed
   before you installed. The state is not merely confusing, it is
   **informationally empty**. It costs a decision and returns nothing.
3. **A layer of complexity has to come out of the UX**, and this is the layer.

**What it buys.**

- **An axis, gone.** Four become three: install-and-run, enable/disable, hide.
  The first real structural hit on I2 — everything before this gave the axes
  better *places*; this deletes one.
- **A state, gone.** "Installed, not applied" — the limbo that renders a full
  section with zero counts and an unspent button — cannot occur. That was one of
  the seven states counted in I2.
- **One moment where money leaves**, and it is the moment you say yes. The old
  model asked twice, which is precisely the surprise-spend the Library doc was
  trying to avoid, and it paid for that with a confusing intermediate state.
- **The section header empties of controls.** Enable left for the sidebar (D3);
  Apply no longer exists. What remains is Uninstall — one button, irreversible,
  a level deeper. Exactly Safari, and it frees the header to be a *description*,
  which is where `author_bio` and `author_links` can finally live (I4).

**The step goes; the states stay.** Clarified 29 Aug: internally there is still
unapplied, applying-in-progress, applied. D4 removes the **exposed step**, not
the machinery — `AutoCodeJob`, the watermark and the catch-up delta are all
untouched. The difference is what those states *are* to the researcher:

| | Before | After |
|---|---|---|
| unapplied | a state you must **act on** — a button waiting | a moment you never see; install started the job |
| in progress | — | **transitional feedback** you watch |
| applied | the result of your second decision | the result of your only one |

So the states become progress, not homework. And the surface that shows progress
is **already built**: the floating activity chip, deliberately engineered to stay
visible across every lens. Install fires the job, the chip carries it, the chip's
completion is the door to review. Nothing new is needed to expose any of it.

**What it obliges.**

- **The count moves, and now it matters more.** Register B1 (Apply lost its
  `{{count}}`) does not get fixed on Apply — Apply is gone. The number moves to
  the install control, which is now the spending one. An install button that does
  not say what it will cost is worse than an Apply button that didn't.
- **"Reinstall instantly" becomes actively false.** Register B2 already flagged
  that copy as wrong because uninstall deletes `QuoteTag` rows. Under D4 a
  reinstall also **re-spends**. The copy has to say so; the fix is now obvious
  rather than fiddly.
- **Nothing in the data model moves**, which keeps the presentation-only scope
  intact. The watermark and catch-up machinery are keyed on `enabled`, untouched.
- **The AutoCode Review modal survives.** Proposals still need reviewing; only
  the entry point changes, from post-Apply to post-install. I3 is unaffected.

### D5 — disable retains the run; re-enabling is free and fast

Settled 29 Aug 2026. Under D4 a codebook in the list has nearly always already
been applied, so disable has to answer "what happens to my results?" — and the
answer is **nothing happens to them**. Switching off keeps every `QuoteTag`,
every `ProposedTag` and the `AutoCodeJob`; switching back on re-reveals them
without re-spending.

**This needs no code change — it is already true.** Verified 29 Aug:
`set_framework_state` in `server/routes/data.py` touches `ProjectFrameworkState`
rows and nothing else; no path from the toggle deletes a tag or a proposal.
D5 is therefore a **presentation obligation**, not a behaviour change, which
keeps the presentation-only scope intact.

**The one qualification, and it is not a footnote.** Re-enable is free for the
corpus the codebook already covered. If sessions arrived *while it was off*, the
watermark froze and re-enable fires a one-shot **catch-up delta** over exactly
those — which spends. Existing results are never re-billed; the cost is only ever
the genuinely new quotes. Today that arrives as a numberless activity chip, which
is the same "does not say what it costs" fault as register B1, one surface along.

**What it buys: the three verbs finally form a legible gradient.** Under the
shipped design this was the thing that needed a 300-line glossary. Under D4 + D5
it fits in a line each:

| Verb | Costs | Keeps your results | Getting back |
|---|---|---|---|
| **Install** | **yes — this is the spend** | — | — |
| **Disable** | no | **everything** | free, instant (delta only for sessions added while off) |
| **Uninstall** | no | **no** — deletes `QuoteTag`s, resets proposals to pending | **re-spends**, because reinstall re-runs (D4) |

Three verbs, three costs, monotonically increasing in consequence — and it maps
straight onto D3's placement: the free, reversible act sits in the master list;
the destructive one sits a level deeper in the detail pane. The gradient and the
geography now agree, which is what the shipped design never managed.

**The wrinkle in "nearly always".** An installed codebook is *usually* applied,
but a run can fail, be cancelled, or be mid-flight. D4 said the internal states
become progress rather than homework — a **failed** run is neither. It is an error
that needs a route back to retry, and that is the one exposure D4 leaves owed.

### D6 — no modals in the codebook browsing surfaces

Settled 29 Aug 2026 as part of S2, recorded separately because it governs
choices that have not been made yet. A codebook is presented as **a card or a
page**. Not a modal, not a drawer, not a sheet.

The rule earns its keep going forward: the next time something needs "just a
quick overlay", this says no, and points at the page that already exists.

### D7 — hide and enable are different axes, on different lenses

Settled 29 Aug 2026, and this is the one that closes I2.

| | **Hide** | **Enable / disable** |
|---|---|---|
| Grain | per **group** | per **codebook** |
| Lives on | **Quotes** lens sidebar | **Codebook** lens |
| Control | the eye icon | the toggle in the master row (D3) |
| Nature | **visual only** | **functional** — off means off |
| Duration | tactical, in-the-moment | *"I don't want to work with this framework for the foreseeable future"* |
| Undo | free, and **auto-unhides** when you reach for a hidden tag | free, retained (D5) |

**They never appear on the same surface.** That is what makes them
unconfusable — not a better label, but the fact that you are never looking at
both at once.

**This needs no work: it is already how the code behaves.** Verified 29 Aug —
`CodebookPanel.tsx` has no hide affordance of any kind; the eye exists only in
`TagSidebar` and `TagGroupCard`. What was missing was never the separation, only
the **statement** of it. The vocabulary churn that made `design-codebook-state-model.md`
open with a glossary — *"precise words, because loose ones (mixing 'hide' with
'disable') caused the churn"* — was a naming failure on top of an architecture
that had already got it right.

**What it does to I2.** Counting only what the codebook lens actually exposes:

| | axes on the codebook lens |
|---|---|
| shipped | three — install, enable, apply |
| after **D4** | two — install, enable |
| after **D7** | two, and confirmed that hide was never a third here |

**Two axes is exactly the prior art** — Safari, Chrome, Edge all ship precisely
two, expressed as a button and a toggle (D1), placed one level apart (D3).
I2 is dissolved on this lens; what remains is a documentation job, not a design
one.

### D8 — one idiom per axis: eye, toggle, button

Settled 29 Aug 2026. D1 fixed two of the three; this completes the set.

| Axis | Control | Grain | Lens |
|---|---|---|---|
| **Hide / show** | the **eye icon** | group | Quotes |
| **Enable / disable** | the **toggle** | codebook | Codebook (sidebar row, D3) |
| **Install / uninstall** | a **button** | codebook | Codebook (detail page, D1) |

Three axes, three idioms, no overlap — so the control's *shape* names the axis
before its label is read. Combined with D7 (hide is on a different lens), a
researcher never sees more than two of these at once.

All three already exist and are already shipped: `EyeToggle`, `.framework-toggle`
and `.bn-btn`. Nothing to invent.

### Open — sentiment does not fit the two-axis model

Surfaced 29 Aug while confirming which codebooks are toggleable. Verified:

- **The floor has no enable/disable** — correct, and by design. The
  `framework-section-header` that carries the switch is rendered only for entries
  with a non-null `framework_id`.
- **Sentiment *does* have one.** `isSentimentFramework` gates exactly one thing —
  the Apply button (`CodebookPanel.tsx:1194`). The toggle renders for every
  framework including sentiment, and the state model intends this (§2 lists
  sentiment under "toggleable — every auto-generated codebook").
- **Sentiment is also *uninstallable*** — it is a template with `enabled: true`,
  so it gets a Library tile with an Install/Uninstall button. See register **A4**:
  that path deletes data nothing can restore.

**The v2 question.** Under D4 install *is* apply — but sentiment is applied by the
**pipeline**, not by installing. So installing sentiment means nothing, and
uninstalling it is purely destructive. It has one meaningful axis (enable) where
frameworks have two, giving the lens **three shapes**, not two:

| | install | enable | hide |
|---|---|---|---|
| **floor** | — | — | ✓ |
| **sentiment** | *meaningless* | ✓ | ✓ |
| **framework** | ✓ | ✓ | ✓ |

**Settled 29 Aug — sentiment is floor-like on install, framework-like on enable.**
No install or uninstall control anywhere: not on the codebook page, not on the
browse card, which reads *Always on* where the button would sit. The rail toggle
stays.

This **closes A4 by deletion rather than by repair** — a control that does not
exist cannot destroy tags nothing can restore. Note the limit of that: it removes
the affordance, not the endpoint. `remove_framework` would still accept the call
if anything else made it, so A4 stays on the register as a server-side fix, at
much lower priority now that nothing in the UI can reach it.

### D9 — the rail is open by default, closable, and traversable when closed

Proposed 29 Aug as two competing stances: *always keep the sidebar open*, or
*offer next/previous on a full-screen view*. **They are not alternatives.** One is
the default, the other is what makes the default closable without stranding you.

**"Always open" cannot be absolute, and the reason is shipped code.**
`hideAllSidebars()` sets `tocMode: "closed"` (`SidebarStore.ts:205`), and the
codebook sidebar occupies that toc slot. **Focus Mode calls it** — `z` /
&#x2318;&#x2325;F, shipped 0.24.0, whose entire purpose is hiding chrome. So does
&#x2318;&#x2325;L, the per-lens panel toggle. Making the rail un-hideable would
mean carving the codebook lens out of a global affordance, on the one lens where
the rail is load-bearing — the worst place to make an exception, because that is
exactly where a user reaching for Focus Mode is most likely to be reading.

So the rail **will** be closed sometimes, by features that already exist. The
design has to survive that rather than forbid it.

**The shape, and it is Mail's.** The message list is present by default, can be
hidden, and when hidden you still move with &#x2318;] / &#x2318;[ or the toolbar
arrows. Nobody experiences that as two competing designs.

1. **Open by default** — opinionated, and it is what makes this a master&ndash;detail
   lens rather than a page with a table of contents beside it.
2. **Closable** — &#x2318;&#x2325;L and Focus Mode keep working, unchanged.
3. ~~**Next / previous when closed**~~ — **dropped 29 Aug.** The chevrons were a
   complexity that did not earn its keep. They existed for one case, the rail
   being closed, and that case is **Focus Mode — a *reading* mode, not a
   navigating one**. Wanting a different codebook while in it is rare, and
   reopening the rail is one keystroke *and* shows you where you are going, which
   a blind next/prev never does. **Arrow-key traversal stays**, because it costs
   no chrome and no discovery burden.

   Consequence: D9 reduces to two clauses — open by default, closable — and the
   set gains no new control at all. The Welcome-rotator port is recorded below as
   history; the frames are marked rejected in the mockup.

**A precision worth fixing now.** Next/prev traverses **installed** codebooks —
the rail's contents — not the catalogue. Moving through everything available is
the browse page's job, and conflating the two would put the whole library behind
an arrow key. *"Move through all the codebooks"* means all the ones you have.

**A benefit that falls out.** It gives this lens keyboard traversal, which it does
not currently have, and there is house precedent — spatial arrow navigation
shipped on the Sessions grid in 0.25.0.

**Prior art in-house: the Welcome slot rotator** (`WelcomeHomeView.swift:482`,
chevrons at `:707`). Worth raiding, but not wholesale.

**Take the chevron treatment.** Hover-revealed edge chevrons on a frosted disk,
hairline stroke, soft shadow — and critically `allowsHitTesting(revealed)`, so an
invisible edge column never shadows the content beneath it. That last part is a
trap already paid for; the CSS equivalent is `pointer-events: none` while hidden,
and forgetting it would reintroduce exactly the bug they designed out.

**Leave the rotator.** It is built for *ambient* content — tips you page through
casually, with a curriculum mode and a random tail. Codebook traversal is
*navigational*: an ordered list, a known destination. Two parts actively do not
transfer:

- **The page dots.** Dots say "small unordered set". The rail already shows
  position far better, and next/prev only exists *when the rail is closed* — so
  dots would be re-implementing the rail, badly, in the one situation the rail is
  absent. A title is the better position cue there.
- **The cross-fade-in-place.** Right for a slot; wrong for a whole codebook page,
  where it would read as a slideshow rather than as navigation.

**The port is not free, and two things do not survive it.** `.regularMaterial` has
no true CSS equivalent — `backdrop-filter: blur()` approximates it without
vibrancy or dynamic tint, and needs a `prefers-reduced-transparency` guard.
And **SF Symbols are unavailable to CSS**; `chevron.left` becomes a Lucide chevron
(the settled web-interior icon set), so the glyph will not match pixel-for-pixel.
That is acceptable here — CLAUDE.md's rule is *don't fake a symbol at the seam*,
and the codebook lens is fully web content, not a seam.

**Open:** whether next/prev is *always* present or only when the rail is closed.
Always-present is simpler to build and to explain; only-when-closed is less
chrome but means an affordance that appears and disappears, which is its own
cost. Worth drawing both.

## Q2 — D4 against the restore path

Discussed 29 Aug. Three options; one is disqualified by a finding on the Quotes
lens, and the other two are a now/later pair rather than alternatives.

### The collision, restated

`remove_framework` deletes `QuoteTag` rows but **preserves** groups, tag
definitions, jobs and proposals — stated reason, `codebook.py:887`: *"enables
instant restore on re-import without re-running the LLM."* `import_template`
then has a restore branch that relinks the orphaned groups and resets `accepted`
proposals to `pending`.

Under **D4**, installing fires a job. So a reinstall takes the restore branch
*and* runs: resurrected proposals plus fresh ones, both `pending`, for the same
(quote, tag). `UniqueConstraint(job_id, quote_id)` permits it — different job.
The reviewer sees every quote twice.

### Option A — delete the restore path

Uninstall stops preserving; reinstall is a fresh import and a fresh run. One
code path, collision impossible, and **both endpoints get markedly simpler**.

The preservation existed *only* to make restore instant, and **D4 already killed
instant restore** — reinstall re-spends either way. So it now buys nothing. The
one thing lost is the denial history, and nothing reads it today: the accept
guard is blind to denials (state-model **Q-C**).

### Option B — reinstall does not fire a job

Keeps preservation by making install-is-apply conditional. Rejected: it
reintroduces exactly the "sometimes it spends, sometimes it doesn't"
ambiguity D4 removed, and the restored proposals may be stale against a changed
`prompt_version` or a corpus that has grown since.

### Option D — non-destructive uninstall

The most attractive on paper. Uninstall drops only the link; nothing is deleted;
reinstall relinks and everything returns genuinely instantly. It would **restore
the intended contract** — the state model says *"Remove = done, no preservation
promise"* and the Library doc's deferred Forget says *"uninstall keeps results by
default; opt-in to purge"* — so the shipped delete contradicts both. It would
also **fix A1**, since a delete that does not happen cannot cross projects.

**Disqualified today by the Quotes lens.** `TagSidebar` folds *"tag names that
live on quotes but not yet in the fetched codebook"* into **the floor's default
group** — an optimistic fallback for the fire-and-forget `PUT /tags`. So an
uninstalled framework's retained tags would surface in **Uncategorised, as the
researcher's own work**. Machine-authored tags masquerading as hand-coding is
precisely the confusion the four-value `QuoteTag.source` exists to prevent.

Option D needs that fold to become **source-aware** first. That is real work on
another lens.

### D20 — A now, D later. Settled 29 Aug.

**A** is small, safe, and net-deletes code. Take it with D4.

**D** is the better end state: it is what both design docs intended, and it fixes
A1. But it is gated on the pending-tag fold learning about `source`, and that is
a Quotes-lens change with its own blast radius.

Sequenced, A is not thrown away — it removes a restore path that never worked,
and D later reintroduces restore on a foundation where it can.

**The v1 contract, in the user's words: click uninstall and you say byebye; if
you are not sure, you disable.** That is a clean thing to explain and a clean
thing to confirm against — and it is the honest reading of what the code will do
once A lands. The disable path is the one that preserves, and it already does.

**D goes to the 100-day inventory**, not because it is optional but because the
prize is real: restoring is computationally and financially free if we get it
right, which makes a permanent uninstall a worse deal than it needs to be. The
blocker is named and specific — `TagSidebar`'s pending-tag fold must learn about
`QuoteTag.source` before retained tags can sit in the database unlinked.

## Open questions — consolidated

As of 30 Aug, after 23 decisions.

**Closed since this list was written:** **Q1** by D20's prelude (sentiment is
floor-like on install, framework-like on enable) &middot; **Q2** by **D20** (A now,
D later) &middot; **Q5** by **D21** (neutral and larger, not primary) &middot;
**Q15** by the user's call on 30 Aug — **the threshold review stays a modal**,
which *reverses* what the prototype had answered by construction, and qualifies
D6 to the browsing surfaces only &middot; the rail-closed navigation question by
**D22** (Browse Library carries it; no arrows).

**Q3 closed 30 Aug by D24** — the run never belonged on the codebook surface;
it reports where runs already report. **What remains is no longer a product hole.**
Everything else is either deliberately deferred (**Q4**), small mechanical
plumbing (**Q6&ndash;Q11**, **Q16**), or a question a build can start without
settling (**Q12**, **Q13**). **Q14** is small but must not be forgotten: it is a
shipping surface.

### Product calls — yours, and nothing proceeds without them

| | Question | Why it blocks |
|---|---|---|
| **Q1** | **The sentiment shape.** Install is meaningless (the pipeline applies it), uninstall is purely destructive (**A4**), and it has one axis where frameworks have two. Floor-like? Framework with an odd install? Or off the codebook surface entirely as a report-wide display setting? | It is the only codebook that does not fit the model. Every surface has to special-case it until this is answered |
| **Q2** | **D4 × the restore path — must be decided together.** If install-is-apply ships while `import_template`'s restore branch stays, a reinstall resurrects old proposals *and* fires a new job: two proposals per quote, and `UniqueConstraint(job_id, quote_id)` does not stop it | Shipping one without the other is a data defect, not a rough edge |
| **Q3** | **Failed install.** D4 merges two failures into one act — *install succeeded, the run failed*. Today each has an obvious retry; coupled, the retry has to be invented | The only exposure D4 leaves owed |
| **Q4** | **The graphic fill.** D13 reserved the slot and deferred the fill. Jacket for the two that have one, initials, headshot, or nothing — per codebook, no systematic obligation | Deferred deliberately; the slot ships without it |
| **Q5** | **Browse Library: primary or neutral?** The shipped button is plain `.bn-btn`; the prototype promotes it to `.bn-btn-primary`. It is now the only accent-filled control on a page about a codebook you already have | Small, but it is an unmarked divergence either way |

### Plumbing owed — decided in principle, needs a field or a string

| | Owed | Size |
|---|---|---|
| **Q6** | `version` on `TemplateOut` — the YAML already parses it for three codebooks | one field |
| **Q7** | A **short description** field. All nine descriptions run 44&ndash;75 words against a 9&ndash;18 budget; first-sentence-only fits just 5 of 9 | one field + nine hand-written lines |
| **Q8** | **B6** — a framework-level *distinct* quote count. `summariseFramework` sums per-group distinct counts, so a quote tagged in two groups counts twice. D12's status line puts that number in front of the researcher | one query |
| **Q9** | **B7** — the author's **fourth home**, `.codebook-author` in the Quotes tag sidebar. Any author treatment must reach it | one rule |
| **Q10** | **G3** — the **Codebook lab** button is homeless. It lived in the `<project> tags` header action, which v2 does not have. It ships to the cohort behind a default-on flag | one placement |
| **Q11** | **G7** — `showHideCodeGroup` sits in the desktop **Codes** menu while D7 puts hide on the **Quotes** lens | move it, or except it |
| **Q17** | **A failed autocode job cannot reach the Mac.** `routes/autocode.py` returns `error_message` over HTTP — enough for the SPA toast — but nothing under `bristlenose/server/` writes to the events log, which is what feeds the sidebar glyph and popover. **Not one field:** the events log is per pipeline *run* and autocode is a job, so whether it appends there or needs a second channel is a design call | design + plumbing |

### Navigation — sketched, not settled

| | Question |
|---|---|
| **Q12** | **Breadcrumb or not.** With the rail as the hierarchy, only browse&rarr;page lacks a return. A single "Back to browse" that appears only when you arrived from there may be enough |
| **Q13** | **One page, two provenances.** Reached from the rail (installed) and from a card (not installed). History-aware chrome is the usual answer and the usual source of bugs |
| **Q14** | **Export mode's fourth state** — read-only, installed, offline. Browse must be stripped; the same `isExportMode()` gate already hides the Library button and the lab |

### Answered in the prototype but never explicitly decided

| | |
|---|---|
| **Q15** | **Does D6's no-modals rule reach the AutoCode Review?** The prototype builds it as a **route**, which answers the question by construction. Worth ratifying or reversing rather than leaving as an accident of implementation |
| **Q16** | `.picker-card-actions` gains `align-items` and `gap` for the card footrow. That should be a **new class**, not an override on a shipped rule |

### Closed since the coverage audit

**G1** the review badge (D10, D18) &middot; **G2** tentative counts (the micro-bar stack now renders them) &middot;
**G4** the instructional copy (floor page) &middot; **G5** cross-codebook drag (dissolved &mdash; one codebook at a time).

## Status rollup — where each issue stands

Per **issue**, accounting for every decision and solution, not just the
solution-by-solution matrix above. As of 29 Aug 2026.

### Addressed

**I1 — a very long scrolling page of all the codes.** Closed by S1. One codebook
in the content pane at a time; the concatenated page does not exist. Measured:
the worst single codebook is **4 grid rows** (nielsen, 10 groups), against **19
rows** for all nine concatenated. My earlier "partial" grading counted tags when
the layout counts groups — corrected 29 Aug.

**I2 — too many concepts for turning on and off.** Closed on this lens.
D4 merged apply into install, removing an axis. D7 established that hide was
never a codebook-lens concept at all — my counting error, corrected against the
code. D1 and D8 gave each remaining axis its own idiom (button, toggle, eye);
D3 gave them separate places (list vs detail). The lens now exposes **two axes**,
which is exactly what Safari, Chrome and Edge each ship.
_Residual: the sentiment shape — see Not addressed._

**I4 — a framework described differently before and after install.** Closed by
S2: one codebook page, reached from the rail or from a browse card, differing
only in state and controls. `author_bio` and `author_links` stop being
pre-purchase-only. The author also now appears in the rail, so provenance is
visible one surface earlier than before.
_Residual: export adds a fourth page state (read-only, installed, offline)._

### Partially addressed

**I3 — near-full-screen modals with their own scrolling.** S2 and D6 delete the
Library modal outright — the picker becomes the browse page, the preview becomes
the codebook page. Register **C4** (no focus trap, no `useInert`, no Escape)
closes by deletion rather than repair.
**Not closed:** the **AutoCode Review modal** is untouched and is the last modal
standing. D6 is stated over the browsing surfaces; whether it reaches Review has
not been decided.

### Not addressed

These are *newly raised* rather than carried over — the work surfaced them.

| Open | Why it matters |
|---|---|
| **The sentiment shape** | Three shapes, not two: floor (no install, no enable), sentiment (install *meaningless*, enable yes), framework (both). Under D4, installing sentiment means nothing because the pipeline applies it |
| **AutoCode Review's fate** | The last modal; D6 does not obviously reach it |
| **D4 × the restore path** | Must be decided **together**. `ProposedTag` is unique on `(job_id, quote_id)`, so a reinstall that both resurrects old proposals and fires a new job yields two proposals per quote |
| **Failed-install retry** | Coupling install and apply merges two failures into one act; the retry affordance has to be invented |
| **Navigation** | Breadcrumb or not; one page with two provenances; the export state |
| **The slot aspect ratio** | 2:3 versus 1:1 pre-decides which fills are possible; cannot be deferred with the fill |
| **`version` plumbing** | One field on `TemplateOut` — the YAML already parses it |

### Register defects v2 moves

| | Effect |
|---|---|
| **C1** Apply never morphs into the switch | **dissolved** — Apply no longer exists (D4) |
| **C3** Uninstall still on the lens | **resolved** — D1 + D3 |
| **C4** Library modal has no focus trap | **closed by deletion** — S2 |
| **B1** Apply lost its `{{count}}` | **relocated** to the install control, and drawn |
| **B2** "reinstall instantly" is false | **made worse** — under D4 reinstall also re-spends; copy must change |
| **A1 A2 A3** cross-project data loss | **untouched** — v2 is presentation; these are server bugs |
| **A4** sentiment uninstall is unrecoverable | **untouched**, newly found |
| **D1 D2 D3** dead code, unreachable states, denied-is-terminal | **untouched** |

## Open — navigation, across three contexts

Raised 29 Aug from Claude's connector detail (a modal: breadcrumb
*Connectors / Directory / Gmail*, Copy link, an X, a prominent CTA). Ours is a
page, not a modal (D6), so dismissal is not the gesture &mdash; **return** is.

**Back and breadcrumb are different affordances and do not duplicate each other.**
Back is *history* ("undo my last move"); a breadcrumb is *hierarchy* ("where am I,
jump up"). Claude's modal carries both: the X dismisses, the breadcrumb locates.
Worth keeping that distinction, because the answer differs per context.

### What each context already provides

| Context | Router | History back | Notes |
|---|---|---|---|
| **Browser** (`serve`) | `createBrowserRouter` | browser chrome | URL bar visible; Copy link is free once these are real routes |
| **Desktop** (WKWebView) | same | **already native** | `ContentView.swift:2148` renders a toolbar Back button calling `bridgeHandler.goBack()`, enabled off `canGoBack`, observed by KVO in `WebView.swift:155` |
| **Export** (`file://`) | `createHashRouter` | browser back over hashes | browse cannot exist offline &mdash; no server to install from &mdash; so the only path is sidebar &rarr; codebook page |

**The desktop finding settles most of it: do not add an in-page back button.** The
native toolbar already has one, wired to real WebView history. An in-page twin
would duplicate native chrome &mdash; exactly the situation `ct()` already exists for,
and exactly what it already does to the Codebook Library button, which is
suppressed in-pane on desktop because the native toolbar carries it. Same
mechanism, same reasoning, no new pattern.

### D22 — Browse Library *is* the navigation. Settled 30 Aug.

**When the rail is closed, the user gets to another codebook by clicking Browse
Library.** There is no next/previous, no arrow pair, no traversal affordance of
any kind. Two routes to a codebook, and only two: a rail row when the rail is
open, a card when it is not.

This kills the arrow idea raised on 29 Aug — reusing the Welcome screen's
left/right arrows, which are SwiftUI and would have had to be re-implemented in
CSS for the embedded surface. **An innovation avoided rather than justified**,
and the second one this pass has removed rather than added.

It also settles, retroactively, why Browse Library had to be *obvious and in
clear space at the top*: it is not merely a catalogue door. With the rail closed
it is the **only** way to reach another codebook, so its prominence is
load-bearing rather than decorative. The requirement that it be findable without
hunting was the right instinct before the reason for it existed.

One consequence worth stating so it is not rediscovered: Browse Library sits on
the codebook page's zone-title row, which renders in every rail state. Nothing
needs to be added for the closed case — the affordance is already unconditional.
The build must simply not gate it on the rail.

### What was still open before D22

1. **Does a breadcrumb earn its place at all?** With S1's permanent sidebar, the
   rail *is* the hierarchy for installed codebooks &mdash; you can always see where
   you are and jump anywhere. A breadcrumb would only do work on the
   **browse &rarr; codebook page** path, where the origin is not in the rail. So
   possibly: no breadcrumb, and browse gets a single "Back to browse" that appears
   only when you arrived from it.
2. **One page, two provenances.** The codebook page is reached from the rail
   (installed) and from a browse card (not installed). Only the second needs a
   return. History-aware chrome is the usual answer and the usual source of bugs.
3. **Export mode.** Browse must be stripped (no server), and the not-installed
   half of the codebook page with it &mdash; the same `isExportMode()` gate that
   already hides the Library button and the lab. Cheap, but it means the page has
   a fourth state: *read-only, installed, offline*.
4. **Copy link.** Real routes make a shareable URL free. Whether we want one is a
   separate question &mdash; it is only meaningful in `serve`, and it points at a
   project-scoped surface.

None of these blocks the mockup; all of them want deciding before the router work.

### D10 — the review count gets two homes: a rail badge and a page button

Closes **G1**, settled 29 Aug. D4 fired the job on install and handed progress to
the activity chip, but a chip is *transient* — dismiss it, return tomorrow, and
v1's persistent "View Report &middot; 12" was gone with nothing behind it. Pending
proposals became unreachable. Function lost, not chrome.

**A chip is progress; a badge is a door.** They are different objects and v2
needed both.

| Home | Answers | Idiom |
|---|---|---|
| **Rail row badge** | *where is there work?* — scannable across every installed codebook without navigating | `.proposed-count` pill, right-aligned, first-line aligned |
| **Page button** | *take me to it* | accent-filled `Review 12`, beside the neutral Uninstall |

This is Mail's split exactly: unread counts in the sidebar, the door in the
content pane.

**It does not reintroduce D1's problem.** D1 objected to a *routine* and a
*destructive* control sharing shape, weight and colour. Review is accent-filled
and Uninstall is neutral — the shipped `.apply-btn` / `.add-btn` pair. Primary
beside secondary reads correctly; twin neutrals did not.

**Nothing invented** — `.proposed-count` already ships. **But it carries a defect
to fix in the same pass:** the rule hardcodes `rgba(37, 99, 235, 0.08)`, the
*light-mode* accent. Dark mode uses `#0a84ff` and `palette-edo` uses `#0f5c9e`,
so the tint is wrong on **two of the four theme combinations**. `color-mix()`
against `--bn-colour-accent` fixes it, exactly as island-doc decision 6 did for
`.merge-target`. Registered as **B5**.

**Still open, deliberately:** whether Review opens a modal or a route. The door
works either way; the last-modal-standing question is untouched.

Frame: **V8** in [`mockups/codebook-v2.html`](mockups/codebook-v2.html).

### D11 — each control appears exactly once; installed state is shown, not re-offered

Settled 29 Aug, **reversing part of D3 and D10.** D3 put the enable toggle in the
rail *and* a full-size copy on the page; V4's installed card carried a toggle
too. That was over-provisioned, and the argument for it was weak.

**The reasoning that was wrong.** I justified repeating the toggle by citing
Chrome, which does show it on both the card and the details page. **But Chrome is
a card grid with no rail.** Safari is our analogue — master list plus detail pane
— and **Safari's detail pane has no enable checkbox at all**: it lives in the
list, once. Claude's directory goes further still: an already-added connector
shows a green **check**, not a plus. State, not a control.

**Each control now appears exactly once.**

| Surface | Control it owns | What it shows of the others |
|---|---|---|
| **Rail row** | enable toggle | the review count, as a badge |
| **Browse card** | the install/uninstall button — **one footprint, swapping verb** | installed / installed-but-off, as state |
| **Codebook page** | Uninstall &middot; Review | enable state, greyed when off |

This also lands D1's gradient properly: **Uninstall becomes the only button on the
page**, a level deeper than everything reversible, which is exactly Safari's
asymmetry.

**Corrected 29 Aug, same day.** The first draft of this decision said an installed
card should show *state only* — a green check, no control — reading Claude's
directory too literally. **Claude can do that because its directory has no
uninstall on the card at all**; removal lives on another surface. Ours must be
reachable, so an installed card carries **Uninstall**. One button, swapping verb,
on the shipped `.picker-card-toggle` with its `min-width` — the "one footprint"
rule the Library doc already settled.

What survives, and it was the actual complaint: **no enable toggle** on the card
or the page. That part stands.

**Still open:** if the card carries Uninstall, does the *page* keep one too? Both
would undercut D1's gradient (irreversible act a level deeper). The cleaner split
is **card owns lifecycle, page owns content**, which would leave Review as the
page's only button. Not decided.

**Future enhancement, noted not built:** a transition as Install becomes
Uninstall. It is the one moment on this surface worth animating — the only
feedback that a *paid* install actually took.

**Why enable and review sit the opposite way round, and why that is not
inconsistent.** Enable's control is in the rail and its state on the page; the
review's state is in the rail and its control on the page. The mirror is
principled:

- **Enable is a *property* of the codebook.** Its control belongs with the
  codebook's identity — the rail row — and the page reflects it.
- **Review is a *task*.** Its control belongs where the task happens — the page —
  and the rail's job is to advertise that work exists.

Property lives with identity; task lives with the work.

**Disabled reads as deselected, not unavailable.** Muted text, desaturated
identity slot — deliberately lighter than the shipped `.picker-card.disabled`
(`opacity: .45`), which means *coming soon, you cannot have this*. An
installed-but-off codebook is yours and one click from returning; it should not
carry the weight of something you are barred from.

**Net effect: a control removed, not added.** Eight page-header toggles came out
of the mockup, including V3's and V8's.

Frame: **V9** in [`mockups/codebook-v2.html`](mockups/codebook-v2.html).

### D12 — the browse card, specified

Settled 29 Aug. Title, author, version, a short description, a status line, one
button. No enable toggle (D11), no "New" badge, grey when disabled.

| Element | Rule |
|---|---|
| Title | always |
| Author | always — "Built in" for the three with none |
| **Version** | render **only if present**; nothing otherwise (no dash, no placeholder) |
| **Description** | **9&ndash;18 words**, one to two sentences or clauses |
| **Status** (installed) | *"14 tags on 34 quotes"* — scoped to the current project |
| **Action** | one button that swaps verb: **Install** out, **Uninstall** in — one footprint |
| Disabled | grey / low contrast, deselected |
| Whole card | navigates to the full page. **The button is the only region that does not** |

**No "New" badge**, deliberately, though Claude's directory has one. It is a
store-merchandising device for a catalogue that turns over; ours is nine bundled
codebooks that change rarely. It would be noise pretending to be news.

**Two things the spec needs that do not exist yet.**

1. **A short description field.** All nine shipped descriptions run **44&ndash;75
   words** against a 9&ndash;18 word budget. First-sentence-only lands in budget for
   **5 of 9** — sentiment (7w) and uxr (8w) are too short, cli-ux (19w) and Plato
   (25w) too long — so it is a useful starting draft, not a rule. Nine
   hand-written lines plus one model field. Truncating prose written for a full
   page will read as truncated.
2. **A framework-level distinct quote count.** Registered as **B6**: `total_quotes`
   is distinct *within a group*, but `summariseFramework` sums across groups, so a
   quote tagged in two groups of one framework counts twice. The shipped
   `foldedSummary` already overstates for the same reason — an existing bug, not
   one v2 introduces, but "on 34 quotes" makes it visible and wrong.

Frame: **V10** in [`mockups/codebook-v2.html`](mockups/codebook-v2.html).

### D13 — the graphic is a fixed-width gutter, not a fixed box

Settled 29 Aug, and it **retires an objection I raised wrongly.** I had argued the
aspect ratio could not be deferred with the fill: a 2:3 slot would strand a circle
in dead space, a 1:1 slot would shrink the jacket. Both consequences follow from
assuming a fixed **box**. They do not survive fixing the **width** instead.

| Fill | Size | Notes |
|---|---|---|
| **Nothing** | 44 &times; 0 | width still reserved |
| **Initials circle** | 44 &times; 44 (1:1) | |
| **Book jacket** | 44 &times; 66 (2:3) | happens to be 2:3; nothing depends on it |

All three are **top-aligned**, and the text column starts at the same x in every
case.

**The invariant is the text's left edge, not the graphic's silhouette.** That is
what makes a grid read as coherent. Cards do not need matching graphic shapes;
they need matching text alignment, and a reserved width delivers it whatever the
fill turns out to be.

**"Nothing" is a first-class option, not a fallback.** Reserving the width when
there is no graphic is precisely what stops a bookless codebook looking broken
beside one with a jacket. No colour has to be invented and no artwork
commissioned for the grid to hold — which is what the earlier assigned-palette
attempt was reaching for and overshot.

**What this frees.** Jackets can arrive for the two codebooks that have them
(Norman, Nielsen) without waiting for the other seven; a headshot can arrive for
one author and not the rest; and none of it disturbs the layout. The fill becomes
per-codebook data with no systematic obligation.

Frame: **V11** in [`mockups/codebook-v2.html`](mockups/codebook-v2.html).

### D14 — the codebook page occupies the content area; the rail is not touched

Settled 29 Aug. Enable/disable lives on the **sidebar only** — confirmed, and
already D11. The live question was what opening a full details page does to the
layout, and the two options were not equal:

- **(a)** the page takes the whole window, snapping the rail shut — **which forces
  enable/disable back onto the page**, since the surface that owns it is gone
- **(b)** the page occupies the content area; the rail stays exactly as the user
  left it, open or closed

**(b), and the arithmetic decides it.** Measured 29 Aug on the primary target, a
14-inch MacBook Pro at 1512pt:

| | |
|---|---|
| window | 1512 |
| project sidebar (`navigationSplitViewColumnWidth` ideal) | −220 |
| codebook rail | −320 |
| **available to content** | **972** |
| `--bn-max-width` (52rem) | **832** |

**972 > 832, with 140pt of slack.** At full screen on the target device, opening
the rail costs the content column **nothing** — the max-width binds first. So
option (a) buys no width at all in the case that matters, while paying three
prices: it changes a state the user did not ask to change, it undoes D11 by
forcing the toggle back onto the page, and it stops the lens being
master&ndash;detail at exactly the moment you are using the master list.

**Where the rail does cost width:** below a window of **220 + 320 + 832 = 1372pt**
the content column starts being squeezed (1332 at the sidebar's 180 minimum). A
windowed-small app is a real case — and it is already handled, by the user. D9
makes the rail closable and next/prev covers traversal once it is shut. **Closing
it is the researcher's call, not something the page does to them.**

That is the whole argument against auto-snapping: an app that rearranges the
window on navigation feels possessed, and here it would be rearranging it to gain
space that the content column cannot use.

Frame: **V12** in [`mockups/codebook-v2.html`](mockups/codebook-v2.html).

### D15 — the enable control is the platform switch, with ours as the fallback

Settled 29 Aug, and it **deletes an innovation rather than justifying one.**

`design-codebook-library.md` chose the custom switch on an explicit premise:
*"the exact `NSSwitch` spring curve and focus ring are not reproducible in
CSS/WKWebView — that ~5% is the accepted gap."* **That premise expired.** Safari
17.4 added `<input type="checkbox" switch>`, which renders the platform switch
with its real spring, its real focus ring, and correct behaviour under Increase
Contrast and Reduce Motion — none of which our CSS gets.

| Host | Control |
|---|---|
| Desktop app (WKWebView) &middot; Safari | **the platform switch** |
| Chrome &middot; Firefox — the CLI-served SPA's likely hosts | **ours** (`.sw`), unchanged |

**Detection is by capability, not channel** — `'switch' in document.createElement('input')`.
Stated as *"ours for the CLI-driven SPA"*, but the intent reads as *"ours where
the platform has nothing to offer"*: someone running `bristlenose serve` in
Safari should get the native control too, and a UA or `isEmbedded()` check would
deny it to them for no reason. Capability detection also ages correctly — if
Chrome ships the attribute, we inherit it without touching this code.

**Consequences.**

- **The mini toggle is deleted.** D3's open question ("switch or checkbox at rail
  size?") is answered by not needing an answer. Innovations drop from 8 to 7.
- **The fallback is not a downgrade** — `.sw` is the shipped, measured,
  macOS-matched control. It stays exactly as it is.
- **This is the house pattern**, one layer down from where it usually operates:
  shared taxonomy, rendered native per surface. `dt()` and `ct()` already fork
  *text* by platform; this forks a *control* by capability.

**Measured 29 Aug in Safari, and it settles the sizing question too.**

| Lever | Rendered |
|---|---|
| default, no CSS | **38.0 × 22.0** |
| `font-size` 1rem / .85 / .7 | 38.0 × 22.0 — **ignored entirely** |
| `width/height: 38×22` | 38.0 × 22.0 |
| `width/height: 30×18` | 30.0 × 18.0 |
| `width/height: 26×15` | 26.0 × 15.0 |
| `transform: scale(.7)` | 26.6 × 15.4 |

Three things fall out of that.

1. **The platform default is *exactly* 38×22** — the same numbers
   `design-codebook-library.md` recorded from measuring a real `NSSwitch`. The
   original metric work was right to the pixel; what has changed is only that we
   no longer have to reproduce it by hand.
2. **`font-size` is ignored**, so there is no implicit control-size hook. Only
   `width`/`height` moves it.
3. **`width`/`height` is honoured and re-lays the control cleanly** — so
   **rail size is available from the platform control itself**. My earlier "not
   resized" caution was wrong: I assumed scaling would distort it, and it does
   not.

**So the rail uses the platform switch at 26×15** — the exact metric our dropped
mini used. We keep the native spring, focus ring, Increase Contrast and Reduce
Motion behaviour *and* the density, with no custom CSS at all.

**One caveat that stays open and needs an eye, not a measurement.** AppKit's
`controlSize: .mini` is a *redrawn* control — different corner-radius ratio,
different knob inset — whereas CSS `width`/`height` re-lays the *regular*
drawing. The probe proves the geometry is clean; whether it reads as a proper
small switch or as a shrunk large one is a judgement to make at 1× on a real
display, which is exactly what the parity doc means by squinting at arm's length.

The prototype has a **Platform / Ours** toggle so both can be judged in place, and
it disables the platform option with a note when the host cannot render it.

### D16 — the enable switch is trailing, at 26×15

Settled 29 Aug, **against my recommendation, and the ordering dissolves my
objection.**

I argued for a *leading* control on the grounds that the pending-proposal count
(D10) already owns the trailing edge, so putting the switch there would mean two
competing things on one edge and *"a switch whose x-position moves depending on
whether a row has proposals."*

**That is only true if the switch is not last.** With the order
**label → count → switch**, the switch is flush right on every row, so its column
is perfectly aligned and still scannable — and the **count** becomes the thing
that shifts. Which is fine, because the count is *information, not a control*: a
ragged column costs it nothing, while a ragged control column costs a lot.

So the trailing layout wins on its own merits once ordered correctly, and it
brings back what our own doc argued for in the first place: *"title flush left,
control on the right"* — no indent, nothing between the reader and the codebook's
name. The 57px indent the leading layout imposed on every title is gone.

**At 26×15**, the platform switch resized — see D15's measurements. Full size in
a two-line rail row is taller than the title line and starts to dominate a row
whose author line is already muted.

**The floor row carries no switch at all**, and under a trailing layout that
costs nothing: its label simply runs the full width. Under a leading layout it
needed a 26px spacer to keep the text aligned. One less thing.

### D18 — one Review door, and what the number on it may honestly say

Settled 29 Aug: **the primary "Review N proposals" button is dropped.** The
coverage line becomes the single door and opens the **threshold histogram** —
the run as it was, with the sliders where the researcher left them.

**Three different kinds of thing were being averaged into one number.** Keeping
them apart is what makes the restatement possible:

| | What it is | Does it change? |
|---|---|---|
| **The histogram** | the confidence distribution the model produced | **never** — it is history |
| **The thresholds** | `applied_lower_threshold` / `applied_upper_threshold`, stored on the job | only when the researcher moves them |
| **Individual accept/deny** | per-`ProposedTag` overrides made afterwards | continuously |

The histogram is a *record*, the thresholds are a *setting*, the overrides are a
*delta*. One number cannot describe all three, and trying to is what made
"12 pending" and "142 proposed" both feel wrong.

**So the button states the outcome, not the pipeline.**

- **Applied** — the `QuoteTag` rows that exist. *"36 tags on 72 quotes."* This is
  the truth of the report right now, and it is the primary figure.
- **Undecided** — `ProposedTag(status='pending')`, appended as a quiet modifier
  only when non-zero: *"· 12 undecided."* It is **work outstanding**, not a state
  anyone chose.
- **Denied** — retained, never surfaced on the page. It belongs inside the review
  surface, where it is a filter, not a headline.

One primary number, one honest caveat, nothing about proposals-as-issued.

**Why the threshold cannot be restated as a rule.** Once a researcher has hand-
denied something at 0.9 confidence, *"accepted above 0.70"* is false. The slider
position is still worth restoring — it is where they left the instrument — but it
must be presented as **the slider's position**, not as a description of the
outcome. The counts describe the outcome; the histogram and sliders describe how
it was arrived at.

**The pitfall, and it is already a known open item.** Re-entering this surface
and moving a threshold could **clobber manual decisions** — re-applying at a
lower cutoff would resurrect a hand-denied tag, because the accept guard is blind
to the denial ledger. That is `design-codebook-state-model.md`'s open **Q-C**,
arriving here as a UX consequence rather than a theoretical one. **A surface that
re-opens the sliders after hand-editing needs that question answered first.**

**Sentiment has no door at all.** It is pipeline-applied: no `AutoCodeJob`, no
proposals, no confidence distribution, so no histogram to open. Its coverage
figure is real but its Review button would lead nowhere. Another instance of the
sentiment-shape problem — it wants a different answer, not a disabled button.

### The RAW analogy, and the one column that is missing

Raised 29 Aug: *"all the original tag proposals are there and you should be able
to go back and recover the shadows — but if you have added manual layers over the
top, you should be able to change the levels and retain them."* **The analogy is
more exact than it was offered as.** Three of the four pieces already exist.

| Photography | Bristlenose | Status |
|---|---|---|
| the RAW negative | `ProposedTag` rows + `confidence` — every proposal the model made, **denied ones retained** | ✅ already stored |
| develop settings | `applied_lower_threshold` / `applied_upper_threshold` on the job | ✅ stored *separately*, non-destructive |
| adjustment layers | individual accept / deny | ⚠️ **stored destructively** |
| the exported JPEG | `QuoteTag` rows — what the report renders | ✅ re-derivable |

**The break is in one column.** `ProposedTag.status` carries two different
provenances with no way to tell them apart:

- `denied` because it fell below the threshold — a **derived** value
- `denied` because the researcher looked at it and said no — an **override**

That is the moment the adjustment gets baked into the pixels. Move the slider and
you must recompute the derived ones — but you cannot, because you cannot see
which they are, so you either clobber the overrides or refuse to move.

**`reviewed_at` does not rescue it.** All four write sites set it identically —
single accept (`autocode.py:484`), single deny (`:519`), accept-all (`:597`),
deny-all (`:664`). It records *when* a decision was made, never *by what*.
Timestamps could be inferred against the job's `completed_at`, but two hand
decisions in the same second are indistinguishable from a batch, and a re-apply
rewrites them. Inference, not fact.

**The fix is one column, and the schema already has the pattern.** `QuoteTag`
records `source` with four values — `human`, `autocode`, `pipeline`,
`codebook-builder`. **The system knows how a *tag* was applied but not how a
*decision* was made.** A `decided_by` on `ProposedTag` closes it: moving the
slider recomputes only `threshold` rows, `human` rows survive untouched, and the
histogram can *mark* the overrides — which is the "see the layers over the levels"
half of the analogy.

**Where the analogy breaks, and it breaks in our favour.** In Lightroom the
layers are ordered and re-composited. Here an override does not sit *over* the
threshold's verdict, it *replaces* it for that one item — closer to a per-item
mask than a layer stack. No compositing order, no blend modes. **Simpler than
RAW, not harder.**

**What today's surface can honestly do without that column.** Show the histogram
(immutable), restore the sliders where they were left (stored), show the current
decisions — but treat the sliders as **read-only on re-entry**. You are looking
at the negative, not re-developing it. That ships the Review door now with no
clobber risk, and leaves the non-destructive re-cast as the v2-future work it was
called.

### D19 — the author gets the person treatment the house already uses

Settled 29 Aug. The byline moves from `--bn-colour-muted` at normal weight to
**`--bn-weight-emphasis` in full text colour**, in all three places it appears:
rail row, browse card, page header.

**This is not a new treatment — it is the one already in the codebase.** Three
shipped rules render a person exactly this way:

| Rule | Where |
|---|---|
| `.preview-author-name` | **the author card on this very page** |
| `.bn-speaker-editable-name` | speaker names, `person-badge.css` |
| `.rewatch-participant` | `blockquote.css` |

Only the codebook *byline* was muted — `.picker-card-author`,
`.framework-section-author`, `.codebook-author` — so **the same name rendered two
ways on one screen**: strong in the author card, greyed beside the title. The
muted version is the outlier, not the standard.

**Why it matters beyond consistency.** These are the best-known names in the
field, and *"Jakob Nielsen"* is more recognisable than *"10 Usability Heuristics
for User Interface Design"*. Rendering the person in the same treatment as a
timestamp or a file path is a claim about what matters on that row, and it is
the wrong one.

**Rejected, with reasons.** *Accent colour* (the App Store developer, the Music
artist) is the stronger signal but carries an obligation — blue means navigable,
so it must be taken together with browse-by-author, never for looks.
*Inversion* (Mail's sender-first: author leads, title follows) is the most
faithful reading of the observation, but the three authorless built-ins would
then lead with a title while the rest lead with a name, making the rail a mixed
list. *Uppercase byline* reads as a **credit**, which is closer to the apologetic
register being escaped.

**Marked as a deliberate divergence.** These three rules now differ from
`organisms/codebook-panel.css` on purpose, and the prototype says so at the rule:
*do not "restore" them*. The CSS sweep that restored 27 rules to their shipped
form would otherwise revert this on its next pass — the correction and the drift
look identical to a diff.

Specimen: [`mockups/codebook-v2-author.html`](mockups/codebook-v2-author.html).

**Correction, 29 Aug — I overstated the evidence for this decision.**

My first census said "nine person-name rules in three treatments, no settled
rule". That conflated three genuinely different objects:

| Object | What it is | Example |
|---|---|---|
| **Codebook author** | a public figure, externally credited | Nielsen, Norman |
| **Participant / speaker** | the researcher's own subject, pseudonymised | `.session-entry-name`, `.report-speaker` |
| **Editable speaker name** | an editing affordance over a participant | `.bn-speaker-editable-name` |

A participant is **research data under a consent gradient**; an author is a
**credit**. They should not share a treatment, and Sessions rendering names at
`--bn-weight-light` in a dense list is a reasonable answer to a different
question. Counting them together made the system look inconsistent when it was
mostly answering separate questions separately.

**The real picture, narrowed to the codebook author — four sites:**

| Rule | Surface | Treatment |
|---|---|---|
| `.codebook-author` | **Tag sidebar, Quotes lens** (`TagSidebar.tsx:619`) | badge, muted |
| `.picker-card-author` | Library tile | label, muted |
| `.framework-section-author` | codebook section header | label, muted |
| `.preview-author-name` | preview author **card** | label, **emphasis** |

**Three of four agree.** And the fourth is arguably not a byline at all — it is
the *heading of a bio card*, a title for the block beneath it, which is a
different typographic job. So calling it "the house person treatment I am merely
adopting" was a stretch.

**D19 stands, but as a design change rather than a consistency fix.** The
argument that carries it is the original observation — *Jakob Nielsen is better
known than "10 Usability Heuristics for User Interface Design"*, and rendering
him like a timestamp makes a claim about what matters on that row. That is
enough on its own. The "it is already in the codebase" framing was evidence that
flattered the conclusion, and it does not hold.

**The genuinely useful finding is the fourth surface.** `.codebook-author`
renders on the **Quotes lens**, outside the codebook lens entirely — the one site
any change to the author treatment will forget. Registered as **B7** for that
reason, not as a defect in the treatment itself.

**Until then the divergence is marked, not silent** — which is the actual answer
to the question. An unmarked difference between a mockup and the system is drift;
a marked one with its reasoning attached is a proposal waiting to be taken or
rejected.

### D17 — the rail keeps the shipped three-section IA, filtered to installed

Corrected 29 Aug. The prototype had collapsed the rail to two sections — *Your
codebook* / *Installed* — which is an **IA regression**: the shipped
`CodebookSidebar` has **three**, split on `author === ""`
(`CodebookSidebar.tsx:100`).

| Section | Shipped string | Contains | v2 |
|---|---|---|---|
| floor | `yourTags` — **"Manual tags"** | the project's own | kept |
| built-in | `builtIn` — **"Default"** | `sentiment`, `uxr`, `cli-ux` | kept |
| authored | `frameworks` — ~~"Library"~~ | garrett, morville, nielsen, norman, plato, yablonski | **"Frameworks"** |

**Only one string changes, and for a reason v2 created.** "Library" meant
*available to install* in v1, where the rail listed both installed and
not-installed codebooks. v2 gives that word to the browse page and makes the rail
installed-only, so "Library" as a heading over *installed* frameworks would name
the wrong thing. **"Frameworks"** is not invented either — `frameworksHeader`
("Codebook frameworks") is already the browse page's own word for the same set.

**Empty sections are omitted**, not shown empty. A researcher who has installed
no frameworks sees two headings, not three with a gap.

**The author line is suppressed under "Default".** All three built-ins have the
author `""`, rendered as "Built in" — under a heading that already says *Default*,
repeating it on every row is noise. Framework rows keep their author, which is
where the byline does work: *Norman* lands faster than *The Design of Everyday
Things*.

### The one page, and what each state shows

v1 had **two pages**: a *storefront* (the modal preview, for something you had
not taken) and an *installed view* (the lens section, for something you had).
That split is I4, and it is why `author_bio` and `author_links` vanished the
moment you adopted a codebook — they only ever lived in the storefront.

**v2 has one page and three states.** Nothing is a different page; only the
state differs.

| | not installed | installed &amp; enabled | installed &amp; disabled |
|---|---|---|---|
| Title, author, version | ✓ | ✓ | ✓ muted |
| **Description** | ✓ | ✓ | ✓ muted |
| **Author bio + links** | ✓ | ✓ | ✓ muted |
| Group titles + **subtitles** | ✓ | ✓ | ✓ muted |
| Tags | badges | **rows** | **rows**, muted |
| **Bar charts + counts** | — | **✓** | **✓**, muted |
| Group totals | — | ✓ | ✓ muted |
| Action | Install | Uninstall &middot; Review | Uninstall &middot; Review, **not muted** |

**Counts follow *installed*, not *enabled*.** Under D4 installing is applying, so
an installed codebook has results by definition. Disabling does not remove them
(D5) — it stops them being live. Hiding the counts when a codebook is switched
off would contradict the retention promise the switch is supposed to make
legible; knocking them back says *kept, not active*, which is the truth.

**Description and bio show in every state.** They are what the codebook *is*, not
what it is currently doing.

### Data completeness — what the full page must carry

Measured 29 Aug from the nine YAMLs, after the prototype was found to be
rendering less than the shipped preview already does.

| Field | Present in |
|---|---|
| `title`, `author`, `description` | 9 / 9 |
| **group `subtitle`** | **59 groups, 9 / 9 codebooks — every single one** |
| `author_bio` | **9 / 9** — including all three built-ins |
| `author_links` | 6 / 9 (morville 6, nielsen 4, yablonski 4, garrett 3, norman 3, plato 2) |
| `version` | 3 / 9 — `cli-ux` 1.0, `sentiment` 1.0, `uxr` 2.0 |
| `preamble` | in the YAML, **absent from `TemplateOut`** — surfaced nowhere |

**Two corrections to earlier claims in this doc.** Versions are on **three**
codebooks, not two — `uxr` is at 2.0. And the built-ins are **not** bio-less: I
had assumed sentiment, uxr and cli-ux carried no author material because they
have no byline. They all have bios.

**And the tag row is not a badge.** The shipped *preview* renders tags as bare
badges; an **installed** codebook renders `.tag-row` — name left, micro-bar and
count right, the bar split when tentative proposals exist. Rendering badges in
both states silently drops every count and the whole tentative band, which is
audit gap **G2** arriving as a rendering choice rather than a missing feature.
One page, two states: badges before install, rows with counts after.

## Coverage audit — every control and every datum, v1 against v2

Asked 29 Aug: traverse the shipped surface exhaustively and find anything the
researcher loses that is **not** a deliberate choice. Built mechanically from the
55 `t()` keys and 19 `onClick` handlers in `CodebookPanel.tsx` +
`CodebookSidebar.tsx`, not from recall.

### Gaps — not yet decided either way

**These are the answer to the question. Nothing below has been deliberately
removed; each is something v2 has simply not placed.**

| # | v1 has | v2 has | Why it matters |
|---|---|---|---|
| ~~**G1**~~ | ~~`viewReport` + `proposed_count` badge~~ | **rail badge + page button** | **CLOSED by D10.** A chip is progress, a badge is a door — v2 now has both, split Mail-style: count in the rail for *where is there work*, accent button on the page for *take me to it* |
| **G2** | **`tag.tentative_count`** — a two-tone `MicroBar` and the title *"N tentative + M accepted"* | not drawn anywhere | The whole *tentative* zone of the threshold review lands here. Losing the split bar means the mid-confidence band becomes invisible on the codebook page |
| **G3** | **`codebook.codebookLab`** — the lab button, in the `<project> tags` header action | no `<project> tags` header exists in v2 | The floor is a rail row now. The lab button is homeless. It ships to the cohort behind a default-on flag, so it is live, not hypothetical |
| **G4** | **`codebook.description`** — *"Drag tags between groups to reorganise. Click a tag or title to rename it. Drop a tag on another to merge."* | not placed | Instructional copy, and it is **floor-specific** — framework tags are not draggable. Probably belongs on the floor's page only, but it has not been said |
| **G5** | **Cross-codebook drag.** All groups render together today, and `handleDropTag` has **no guard** against dropping a floor tag onto a framework column | impossible — one codebook at a time | Likely an improvement (it may even be an unnoticed bug today), but it is a capability **removed by side effect**, not by decision |
| **G6** | **`autoCodeStartFailed`** toast — 409 already-running, 503 no key, 400 no quotes | — | Already flagged as the owed failed-install retry, but the toast is a concrete existing thing that needs a new trigger point |
| **G7** | Desktop **`showHideCodeGroup`** sits in the **Codes** menu | D7 puts hide on the **Quotes** lens | A pre-existing inconsistency that D7 makes sharp. Either the menu item moves or D7 has an exception |

### Deliberate removals — recorded, not forgotten

| v1 has | Fate | Decision |
|---|---|---|
| `autoCodeQuotes` — the Apply button | **removed** | D4: installing *is* applying |
| `restoreCodebook` / `restoringCodebook` / `restoreHelp` / `previouslyImported` | **removed** | D4 makes reinstall re-spend, so "restore instantly" is no longer true |
| The Library **modal** (`codebook-modal-*`, picker + preview) | **removed** | S2 + D6: browse page and codebook page, no modals |
| The **status dot** | **removed** | D3: promoted into the toggle it used to echo |
| Sidebar **`builtIn` / `frameworks`** headings, and not-installed rows | **removed** | Rail is installed-only; grouping is provenance |
| `comingSoon` | **unreachable today** (all nine ship `enabled: true`) | Browse page may keep the state; no user has seen it |

### Mapped — same capability, new address

| v1 | v2 |
|---|---|
| `heading` + `browseCodebooks` action | browse page, reached from the rail |
| `browseTitle` / `browseSubtitle` / `frameworksHeader` | browse page chrome |
| `importCodebook` / `importingCodebook` / `importHelp` | the card's Install button, now carrying the cost |
| picker card title / author / desc / tags | browse card, density ladder V4–V5 |
| `preview-author` / `-bio` / `-links` | codebook page — **and no longer lost on install** (I4) |
| framework title / author / `foldedSummary` | codebook page header |
| `framework-toggle` | rail row (mini) **and** page header (full) — D3 |
| `removeFromCodebook` / `hideTitle` / `tagsRemovedFromQuotes` / `noQuotesTagged` / `loadingImpact` / `autoCodePreserved` / `restoreAnytime` | uninstall confirm, unchanged |
| Group CRUD — title, `addSubtitle`, `group-close`, `addTag`, `newGroup`, `deleteGroupTitle`, `deleteTagTitle`, `tagOnQuotes`, `tagsWillMove`, `mergeTitle`/`mergeBody`/`merge` | the floor's codebook page, unchanged |
| `total` / `group-total-row` | group card, unchanged |
| `uncategorised` / `uncategorisedSubtitle` | floor page |
| `sentimentTitle` / `analysis.sentiment*` | sentiment's page — **but see the sentiment-shape open question** |
| `projectTagsHeading` / `yourTags` | rail row + page title |
| anchor scroll `#codebook-fw-{id}` | replaced by selection |
| `all_tag_names` duplicate guard | unchanged — still passed whole, so it still sees every tag |
| Desktop Codes menu: `browseCodebooks`, `importFramework`, `removeFramework` | re-point from modal-open to route navigation |

### One thing that quietly changes

Cross-codebook **colour** comparison. Today every codebook's groups render in one
grid, so Garrett-blue sits beside Norman-green and the palette does work as a
distinguisher. One codebook at a time, colour only distinguishes groups *within*
a codebook. Not a loss of function, and arguably a gain in focus — but the six
colour sets do less work than they did.

## State-engine audit — what v2 breaks, changes, or renders purposeless

Asked 29 Aug 2026: does any of D1&ndash;D6 / S1 / S2 break the shipped state
machines or the data model? Audited against the code, not the docs.

**Headline: nothing is broken. Six engines are untouched. D4 renders a
substantial amount of existing machinery *purposeless*, and introduces one real
collision.**

### The six engines, and their status

| Engine | Where | Status under v2 |
|---|---|---|
| **Tag instance FSM** — `QuoteTag.source` &times; `ProposedTag.status` | `models.py` | **untouched.** D4 changes what *triggers* a job, never how a tag gets applied or reviewed |
| **Codebook lifecycle** — link, `ProjectFrameworkState.enabled` | `codebook.py`, `data.py` | **states intact; one transition merged.** Install and apply become one user action. Neither state disappears |
| **AutoCodeJob status** — pending / running / completed / failed / cancelled, plus `reconcile_orphaned_jobs` | `autocode.py` | **untouched, and more load-bearing than before.** It stops being homework and becomes the progress feedback (D4) |
| **The watermark** — `first_imported_at` vs `completed_at`, catch-up delta | `autocode.py` | **untouched.** D5 confirms it rather than changing it |
| **`hidden_tag_groups`** — per-group hide | `data.py` | **untouched** |
| **Re-apply gate** — ever-applied &cap; linked &cap; enabled | `reapply_active_frameworks` | **untouched** |

So the data model does not move, and the presentation-only scope holds — with one
caveat under "scope" below.

### What D4 renders purposeless

This is the real finding, and it is a *simplification available*, not a break.

`remove_framework` deliberately preserves `CodebookGroup`, `TagDefinition`,
`AutoCodeJob` and `ProposedTag` on uninstall. The stated reason is at
`routes/codebook.py:887`: **"enables instant restore on re-import without
re-running the LLM."** `import_template` then carries a whole second branch — the
restore path — that relinks orphaned groups and resets accepted proposals to
`pending`.

**Under D4, reinstall re-runs. So restore is not instant, and the preserved data
is not reused.** The machinery's entire stated purpose is gone:

- the restore branch in `import_template`
- the preservation in `remove_framework`
- `restorable` / `previouslyImported` / *"Previously installed — reinstall
  instantly"* (register **B2** said the copy was wrong; D4 makes the **concept**
  wrong)

None of it breaks. It simply stops buying anything, and could be deleted — which
would make both endpoints markedly simpler than they are today. **That is a
decision to take deliberately, not a consequence to discover in the build.**

### The one real collision

`ProposedTag` is constrained `UniqueConstraint("job_id", "quote_id")` — **scoped
to the job**. So a second job over the same quotes does not violate it.

Combine that with the restore branch: reinstall relinks the old groups **and**
resets their accepted proposals to `pending`, and under D4 also fires a fresh
job producing new proposals for the same quotes. The reviewer then sees **two
proposals per quote** — resurrected old ones and new ones — with nothing in the
schema forbidding it.

The collision disappears if the restore branch is deleted per the section above.
It bites only if D4 ships while restore stays. **These two must be decided
together.**

### The one complexity increase

Install and apply are **fully independent today** — no path in `codebook.py`
fires a job. Coupling them merges two failures into one action: *install
succeeded, the run failed.* Today each has an obvious retry; coupled, that
retry has to be invented. Already flagged as owed under D5's "nearly always";
recording it here as the concrete cost of D4, set against the axis it removes.

### Scope

**D4 has a presentation-only implementation and a behavioural one, and they are
not equivalent.**

- **Presentation-only (in scope):** the install control calls install, then
  autocode — two existing API calls behind one user action. The server is
  untouched, and "we removed the exposed step" is literally true.
- **Behavioural (out of the stated scope):** the install endpoint itself fires
  the job. Tidier, but it is a server change, and the moment it lands, "presentation,
  layout and flow" stops describing this work.

Recommend the first until there is a reason for the second.

### S1 and S2 cost

- **S1** — render change only. `CodebookSidebar` stops fetching and listing
  not-installed templates.
- **S2** — **new routes**, so the codebook lens gains sub-paths (browse, and a
  per-codebook page). Router work, not state work. It also *deletes* code: the
  modal, and with it register **C4**.

## Grounding

Already measured, so v2 does not re-derive it:

- **[codebook-defects.md](codebook-defects.md)** — the eighteen spec-vs-shipped
  gaps. Several are layout-adjacent (C1 the un-morphed Apply, C3 the duplicated
  Uninstall) and may dissolve into v2 rather than needing separate fixes.
- **The flow** — five FigJam diagrams, the routes between every element:
  [figma.com/board/2H7rrbqAP5J1ic5Zmkyo32](https://www.figma.com/board/2H7rrbqAP5J1ic5Zmkyo32)
  (access-controlled).
- **[design-codebook-state-model.md](design-codebook-state-model.md)** —
  canonical on behaviour. v2 must not contradict it.
- **[design-codebook-library.md](design-codebook-library.md)** — canonical on
  layout *only*; its disable-semantics half was reversed the day after writing.

## Migration

Deferred by agreement. Not designed here yet.

**Superseded by D28 — there is no migration before GA; trial projects get
reprocessed.** Kept for the reasoning, which still holds if a path is ever
needed.

One note so it is not a surprise later: because the scope is presentation, the
expensive half of a migration — schema, stored state, the `ProjectFrameworkState`
and `hidden_tag_groups` rows — should not move at all. What will need thought is
anything that changes a *route* people have learned, and the export, which bakes
a per-project CSS copy and so lags a theme change by one render.


### D21 — the button hierarchy: size carries the destination, fill carries the action

Settled 29 Aug, and it adds the one innovation this pass could not avoid.

**Browse Library is a destination, not an action.** It wants presence — clear
space at the top of the zone-title row, and enough size to be found without
hunting — but not contrast, because it competes with nothing and commits to
nothing. So it goes **up a size and stays neutral**: `.bn-btn .bn-btn-secondary
.bn-btn-lg`. It had been `.bn-btn-primary`, which was the promotion Q5 flagged as
unmarked; this replaces it rather than justifying it.

**Install is the main call to action on the codebook page**, so on that page it
takes the shipped primary fill at **normal size** — `.add-btn .bn-btn-primary`.
Size does the work on the destination, fill does the work on the action, and
neither borrows the other's device.

> **Revised 31 Aug 2026 — the card pair is now Install `bn-btn-primary`,
> Uninstall `bn-btn-secondary`** (`frontend/src/islands/CodebookV2Browse.tsx`,
> commit *"install leads, uninstall recedes — the card pair is ranked by intent,
> not by danger"*). The paragraph below argued the opposite and is preserved so
> the reversal is legible. What changed the answer: until the button atom gained
> a background (commit *"the button atom had no background…"*), a "neutral"
> `.bn-btn` was not neutral — it fell through to the user agent's `buttonface`,
> so this paragraph was comparing a chosen restraint against an unstyled
> control. With a real resting state to compare against, ranking by *what you
> came to do* beat ranking by danger; the confirmation sheet is where cost is
> stated. Chosen from `docs/mockups/button-catalogue.html` §5, option D.

**The browse card's Install stays neutral and normal.** On a grid of cards no
single install is *the* action; a wall of accent-filled buttons would make the
grid shout and would misrepresent a catalogue as a decision. Primary belongs to
the page, where there is exactly one codebook and exactly one thing to do with it.

**The innovation, declared.** `.bn-btn-lg` is new. The shipped atom
(`theme/atoms/modal.css`) carries four *colour* variants — `-primary`,
`-secondary`, `-cancel`, `-danger` — and **no size axis at all**, because every
existing call site is a dialog action row where one size is correct. A zone-title
destination is the first call site that wants a second size. The new class is
purely dimensional (`font-size`, `padding`); it introduces no colour and no new
token, and `.add-btn.bn-btn-primary` restates the shipped primary's three
declarations verbatim rather than inventing a fill. **This is a genuine gap in
the atom, not a local workaround** — if v2 ships, the size axis belongs in
`modal.css`, not in the mockup.
## Fidelity map — what the prototype is, part by part

Asked for on 30 Aug, and it is the thing a prototype most needs and least often
has. Without it the artefact reads as a spec in every part, including the parts
that are one afternoon old. Tiers are the house ones (sketch / system-true /
native-true).

### Definitive — Tier 2, build production code from this

These are real markup, real tokens, and settled by a decision above. A build
that disagrees with one of them is wrong, not different.

| Part | Settled by | Note |
|---|---|---|
| Rail IA — three sections, installed-only | **D17** | Mirrors the shipped panel's IA, filtered |
| The enable switch — platform control, our fallback, trailing, 26×15 | **D15, D16** | **Measured**, not designed. Receipts in `codebook-v2-parity.html` and `-rail.html` |
| Zone-title row and the datum | *lifted* | `.section-heading` verbatim; the first-child `margin-top:0` rule is the cross-lens datum |
| Codebook-page two-column geometry | user direction, 29 Aug | Description's right edge aligns to the graphic's; Install trails |
| The graphic as a fixed-width gutter | **D13** | Definitive that the space is reserved and fixed-width. **Contents deliberately deferred** |
| Author treatment | **D19** | Specimen B of six, chosen |
| Browse-card structure | **D12** | |
| Three shapes — floor / sentiment / framework | **D20** | Including: sentiment has no install control anywhere |
| Navigation between codebooks | **D22** | Rail row, or Browse Library. No arrows, no traversal — Browse Library carries it when the rail is closed |
| The provenance line | **D23** | Settled 30 Aug. The author slot carries provenance: a person for a framework, and for a built-in the fact that it shipped with us. *On by default* for sentiment, *Available by default* for the rest. See below |
| Lifted shipped components | CSS sweep, 29 Aug | `.tag-micro-bar`, `.badge`, group backgrounds, the floor's authoring apparatus. **Definitive as pointers to shipped code, not as re-specifications** — read the component, not the mockup |

### Indicative — a direction, not a drawing to match

| Part | Why it is only indicative |
|---|---|
| Button treatments | Changed **twice on 30 Aug**. The *hierarchy* is the direction — destination quiet and larger, page action primary, card action neutral. The classes are a proposal |
| `.bn-btn-sm` / `.bn-btn-lg` | A **declared gap** in the atom, not an accepted addition. Per the fidelity contract a missing atom is a finding; this one is filed, not granted |
| The Review door's split — verb button, counts on its baseline | Minutes old at the time of writing |
| All interaction wiring | Tier 1 stubs — install flow, confirm dialog, drag gestures |
| Fixture data | Throwaway, though shaped like the real payload |
| The native chrome stand-in | A **labelled** static placeholder. Deliberately not a proposal |

### Rejected — do not build from this at all

**The threshold review page.** The user's call, 30 Aug: it stays a **modal, as it
currently is**, and its detailed UX is not being reinvented. The prototype's
version is a parody and is now banner-marked in the artefact and comment-marked
in the source, rather than deleted, so the route still shows where the door goes.

What survives from it is narrow and worth stating exactly: **that the door
exists, where it sits, and that what it opens is read-only** (D18). The
destination is the shipped `ThresholdReviewModal`.

This also **qualifies D6** — "no modals in the codebook browsing surfaces". The
threshold review is not a browsing surface; it is a focused task on one
codebook's results, which is the case modals are for. D6 governs the rail, the
browse page and the codebook page. It does not reach this.

### Not drawn at all — coverage holes, named so they are not mistaken for decisions

~~Empty states (no codebooks installed)~~ — **settled by D25**: the heading
stays, the list is empty. ~~Error and failed-job states~~ — **settled by D24**:
they are not on this surface at all.

~~A codebook with no tags~~ — **settled by D26**: a bleak one-line statement,
and no Review door.

Still owed as drawings: **a codebook page whose counts are zero** (tags defined,
but the run failed or has not finished — D24 settles that this is a *zero* state
and not an error, and D26 distinguishes it from a tagless codebook, but neither
says what it looks like), and the uninstall confirmation at Tier 2 rather than as
a stub. ~~The knocked-back disabled card~~ — **settled by D27**: identical to
the page, with the uninstall control exempt on both.

**Long-content overflow on titles, author names and group subtitles is
explicitly good enough for v2** (user, 30 Aug) — deferred by decision, not by
oversight.


### D23 — the author slot carries provenance, and built-ins have provenance too

> **Revised 31 Aug 2026 — D23 is now PER SURFACE.** The navigator shows a
> **person or nothing**; the system fact ("On by default", "Available by
> default") was dropped from it entirely
> (`frontend/src/components/CodebookV2Sidebar.tsx`, commit *"…the rail's second
> line is a person or nothing"*). **The page and the browse card keep it.**
>
> Why the split, since the decision below assumed one slot could carry both if
> they differed in weight: in a **list** the eye reads the second line as one
> slot with one meaning, and two rows apart it said "who made this" and "how
> this is configured" — a false parallel however lightly the second is set.
> Weight was answering the wrong question. It also cannot help *choose*, which
> is all the rail is for: everything listed there is already installed, so
> "Available by default" is not actionable. In the **catalogue** the same string
> is decision-relevant — it separates a codebook that ships with Bristlenose
> from a third party's framework — and the **page** shows one codebook, so no
> comparison is invited. The list compares, the page explains, the catalogue
> distinguishes.
>
> Also revised in the same pass: provenance moved `--bn-text-micro` →
> `--bn-text-badge` (the sidebar's own subtitle stop, matching
> `.tag-sidebar-subtitle` under a `.tag-sidebar-header .sidebar-title`), and the
> two-line stack gained `gap: 1px` to match `.session-entry-speakers`.

Settled 30 Aug, in two passes, and the second corrected an error in the first.

**The string on sentiment was wrong, not merely provisional.** *Always on* denies
the enable toggle sitting in the rail beside it — it would have told a researcher
that a codebook they can switch off cannot be switched off. **On by default**
states both true things at once: it arrives on, and it can be turned off.

**And it does not generalise to the other built-ins.** The Bristlenose UXR
Codebook and Command-Line UX ship with the product but are **not** applied on
arrival — the user installs and enables them like any framework. Their truth is
**Available by default**: you did not have to go and find it, and it is still
yours to turn on. In the fixture, UXR is installed and *disabled*, which is
precisely the state *On by default* would misdescribe.

**Where it renders, and why that slot.** A framework's provenance is a person, so
D19 gave the author its own line under the title. A built-in has no author, and
that line sat empty. It is the right home for this: same slot, one question
answered — *where did this come from?*

**Same slot, different treatment.** D19's weight was chosen for a **name**:
Jakob Nielsen is better known than his heuristics, and the typography was
supposed to say so — emphasis weight, full text colour. *On by default* is a
system fact, and it must not borrow the celebrity treatment; dressing a
configuration state as a cultural figure is a category error the eye catches
immediately. The system answers revert to the pre-B rendering — **normal weight,
muted colour** — so the slot reads as one question with two kinds of answer,
which is what it is.

This also closes a hole opened on 29 Aug. **Built in** was dropped from cards and
pages on the reasoning that the rail's **Default** heading already says it — true
in the rail, and false on the browse page, **which is a flat grid with no
headings at all**. A built-in's card had no way to say what it was. The
provenance line restores that without bringing back a badge.

### D24 — installed is the state; the run reports where runs already report

Settled 30 Aug, and it closes **Q3**, the one hole the fidelity review called a
genuine product gap rather than a missing drawing.

**The framing that dissolves it.** Under the hood install and run are different
things, and D4 never claimed otherwise. What D4 merged was the *researcher's*
act: **install means "get and do"**. So the durable state the codebook surface
owns is **Installed** — it survives a failed run, and the Uninstall button is
there the whole time, because what you installed is still installed.

**The run is not that state, and it does not belong on this surface.**
Autotagging is not instant, it needs progress, and it can fail — all of which is
already true today and already has a home. It keeps that home:

- **macOS** — the **glyph, the status line, and the popover for detail**, all of
  which already exist on the project sidebar row (`ProjectRow.swift`,
  `ProjectRowActivityIndicator.swift`, and the Schema E rule that a clean row
  shows no status line at all). A failed autocode job is a **message in the
  existing five-kind taxonomy** — `MessageKind.ERROR` from
  `bristlenose/ui_kinds.py` — not a new glyph, a new colour, or a new surface.
  `docs/design-pipeline-diagnostic-popover.md` holds the flowchart for fitting a
  new message into that vocabulary, and it is required reading before adding
  one.
- **CLI SPA** — the **activity chip stack** in `AppLayout`, plus a floating
  toast. Both already exist: `CodebookPanel` registers a running job in the
  activity store, and the failure paths already toast a real reason rather than
  swallowing it — 409 already-running, 503 no API key.

**Nothing needs inventing, which is the point.** The retry the fidelity review
said "has to be invented" does not, because the run's progress and failure never
moved onto the codebook page in the first place. Q3 read as a hole because the
codebook surface was assumed to own the whole merged act. It owns the half that
is durable; the event stream stays where event streams live.

**Two things fall out, both worth stating so the build does not rediscover them.**

1. **An installed codebook with a failed or pending run renders a zero state**,
   not an error. It is installed, its counts are zero, and the *reason* is in the
   status line or the toast — not restated on the page. That zero rendering is
   still owed as a drawing; what is settled is that it is a **zero state, not an
   error state**.
2. **The completion toast already opens the review modal.** `CodebookPanel`
   dispatches `bn:autocode-report` from the toast's *View Report*, which opens
   `ThresholdReviewModal` — the same destination as the codebook page's Review
   door. Today's call that the review stays a modal is not a constraint on this;
   the two doors already converge on it, and keeping the modal is what lets them.

**The Mac half is not wired, and this is the one build-blocking finding in
D24.** Measured 30 Aug: `routes/autocode.py` records `error_message` on the job
and returns it over HTTP (`:122`), which is how the SPA toasts a real reason
today. But **no path under `bristlenose/server/` calls `append_event` at all**,
and the Mac's sidebar glyph and popover read the events log
(`PipelineRunner.swift`, `EventLogReader.swift`). So a failed autocode job
reaches the SPA and **cannot currently reach the Mac's glyph or popover** — the
surface the requirement names exists, and autocode is not connected to the
channel that feeds it. Recorded as **Q17**.

Note this is not merely a missing wire: the events log is written **per pipeline
run**, and autocode is a server-side job rather than a run. Appending to it may
be right, or may be a category error that wants a second channel. That is a
design question and it is open — see Q17.

**Platform fork, deliberate.** A status line on the Mac and a toast in the SPA is
not an inconsistency — it is the house rule that a shared taxonomy renders native
per surface. The desktop's chrome vocabulary rules out transient toasts; the web
surface has no sidebar row to write to.

### D25 — an empty section keeps its heading

Settled 30 Aug. With no frameworks installed the rail still shows the
**Frameworks** heading, with nothing under it.

The prototype had the opposite — `sect()` returned `''` for an empty array, so
the section vanished. That teaches the researcher nothing: a heading that is
absent does not read as *empty*, it reads as *this category does not exist*. The
heading is the thing that says frameworks are a concept and this is where yours
will appear. Same reason Mail keeps a mailbox in the sidebar when it has no
messages.

Only **Frameworks** can actually be empty — the floor is always exactly one row,
and Default always holds sentiment, which D20 made uninstallable. All three
headings are nonetheless unconditional, so the rule has no exception to remember
and no special case to get wrong later.

**It pairs with D22 rather than needing anything added.** The empty heading says
*frameworks go here*; Browse Library, which D22 made the unconditional route to
the catalogue, says *and here is where you get one*. The first-run rail is
therefore self-explaining without a single line of instructional copy.

**On the name.** Raised as a question — *Library? FRAMEWORKS?* — and the answer
is **Frameworks**, per D17. The rail lists what you **have**; the Library is
where you **get** things, and it is already the name of the browse page
(*Codebook Library*). Calling the rail section Library would make an empty one
look like a broken catalogue rather than an empty shelf, and would leave the
browse page needing a different name.

Verified by rendering: with every framework uninstalled the rail emits
`["Manual tags", "Default", "Frameworks"]` and three rows.

### D26 — a codebook with no tags says so, bleakly

Settled 30 Aug. **"This codebook has no tags."** Muted label text where the
groups would be, and nothing else: no illustration, no call to action, no
cheerful reframing of the absence as an opportunity. The fact is the whole
message.

That is the house position on empty states rather than a one-off — an absence is
information, and dressing it up costs the researcher a beat to decode something
they already understood from the void. It is also the same instinct as D25's
empty heading one level up: state the truth, add no chrome.

**One consequence, forced rather than chosen: the Review door is suppressed.**
`hasJob()` is true for every framework, so without a gate a tagless codebook
would render *Review 0 tags on 0 quotes* — a door onto nothing, which is worse
than no door. It now requires a non-zero tag count.

**Not to be confused with the other zero, which D24 governs.** A codebook that
*defines* no tags is empty in itself, and that is this message. A codebook that
defines tags but whose run produced nothing is **installed with a zero result**,
and its explanation belongs in the sidebar status line or the SPA toast, never
restated on the page. The two look similar and mean different things; only the
first gets this sentence.

Verified by rendering: with a framework's groups emptied, the page emits the
line and omits `#coveragebtn`.

### D27 — one disabled treatment, two surfaces, and the uninstall stays reachable

Settled 30 Aug. **The disabled card knocks back exactly as the disabled full page
does, and it is still uninstallable.**

Straightforward as a decision; the interesting part is what it found. The two
treatments were **three** separate declarations that did not agree:

| | text | knock-back |
|---|---|---|
| `.pageoff` (page) | muted | `opacity:.55; saturate(.4)` |
| `.picker-card.off2` (card) | muted | `opacity:.45; saturate(.35)` |
| `.picker-card.off` | muted | `opacity:.45; saturate(.35)` — **dead** |

The page and card differed by a tenth in both values — visible when you put them
on one screen, invisible when you look at either alone. And `.picker-card.off`
was unreachable: the markup only ever emits `off2`. Editing it would have
changed nothing while looking exactly like a fix.

Now **one rule lists both surfaces**, on the page's numbers, because the page is
the full treatment the card is meant to match. Two surfaces that must agree
should not be able to disagree, which means one declaration and not two tidy
ones.

**The uninstall control is exempt on both.** The page already exempted
`.pg-actions`; the card exempted nothing, so its toggle greyed with everything
else. That contradicted the 29 Aug call that uninstall stays normal and active
on a disabled codebook — the one control that must stay reachable is precisely
the one a blanket knock-back takes away. Both surfaces now hold it at full
opacity with its live hover.

This is the same shape as the `.add-btn` and missing-`.bn-btn` findings earlier
today: **the defect was never in the rule anyone was reading.**

#### D27a — and unifying two inventions is not the same as removing them

Corrected within the hour, on the right question: *does the design system already
have a disabled treatment, and is it tokenised?* Measured — **it does not, and it
is not.**

| opacity | sites |
|---|---|
| **0.5** | `.bn-btn:disabled`, `.toolbar-btn:disabled`, `.autocode-btn:disabled` |
| 0.45 | `.picker-card.disabled` |
| 0.4 | `.feedback-btn-send:disabled` |
| 0.3 | `.expand-arrow:disabled` |

**Seven declarations, five values, no token.** So picking `.55` over `.45` was
choosing between two local guesses while a third question went unasked. The
knock-back is now `--bn-opacity-off`, set to **0.5** — the plurality *and* the
base atom's own value, so the token adopts the de-facto system value rather than
adding a sixth.

**Named `-off`, not `-disabled`, deliberately.** A disabled control cannot be
used — `.picker-card.disabled` even sets `pointer-events: none`. A switched-off
codebook is fully interactive: you open it, you read it, you uninstall it. Same
visual weight, different state, and borrowing the shipped class would have
silently killed the interaction D27 exists to preserve.

**And `filter: saturate()` is gone.** It appeared on both surfaces here and
**nowhere in `bristlenose/theme`** — grep returns prose about colour and not one
declaration. It was invented, on both, and D27 unified the two inventions
without noticing that neither belonged. That is the subtler failure of the two:
a consistency fix reads as diligence, and it made an invented device look
house-standard by applying it twice.

**Filed for the real design system, out of scope here:** the seven sites want to
converge on one token. That is a theme-wide change with its own blast radius,
and naming it is the deliverable — not doing it inside a codebook mockup.

## The message inventory — `docs/mockups/codebook-v2-messages.html`

Built 30 Aug. Every message the install-and-autotag path can produce, drawn in
both renderings that carry it: the SPA toast and the macOS project-sidebar row
with its popover. **Nineteen messages, no new UX** — the five kinds from
`bristlenose/ui_kinds.py`, the shipped `.autocode-toast`, the existing sidebar
status line, and the seven failure kinds the classifier already distinguishes.

Three groups, because they fail differently:

- **Pre-flight (7)** — the install is refused and nothing is spent. All seven are
  real HTTP paths in `routes/autocode.py`.
- **Lifecycle (5)** — running, completed, completed-with-nothing,
  completed-partial, cancelled. Running is rendered as a **status, not a kind**,
  which is what `ui_kinds.py`'s own docstring instructs.
- **Runtime failure (7)** — one per `LLMFailureKind`, each already mapped to an
  existing `CauseCategoryEnum` case. **No new category is proposed.**

Every toast string is inside the 60-character budget, checked mechanically rather
than by eye. The kinds split on one rule: **`WARNING` when waiting fixes it,
`ERROR` when the researcher must change something** — which is why rate-limited
is a warning despite stopping the run.

### What building it found

**0. The palette can colour one of the five kinds.** `--bn-colour-success`,
`--bn-colour-danger` and `--bn-colour-warning` are used **sixteen times across
`bristlenose/theme` and `frontend/src` and defined nowhere**. Eleven uses carry a
hard-coded fallback and work. **Five do not** — and two of the five are the very
surfaces this page draws: `.toast-check` and `.toast-error`
(`autocode-toast.css:32,37`), plus both activity-chip states and the autocode
report. An undefined custom property makes `color` invalid at computed-value
time, so it inherits: **the tick and the cross on the shipped autocode toast have
no colour at all.**

`--bn-colour-danger` is a **misspelling of `--bn-colour-negative`**, which exists
as `light-dark(#dc2626, #ef4444)` — and the eleven fallbacks pin its *light* hex,
so all eleven are wrong in dark mode. Success and warning have no counterpart
token whatsoever, and the loose greens disagree with each other (`#22c55e`
against `#16a34a`).

**1. The SPA toast has two kinds, not five.** `.toast-check` and `.toast-error`
exist; warning, info and skipped have no treatment, and `toast()` itself takes
`(message, duration)` with **no kind parameter**. Completing that finishes an
existing pattern rather than inventing one.

**2. The autocode path never classifies.** `autocode.py:458` catches bare
`Exception` and stores `str(exc)`, so `error_message` is raw exception text.
`classify_exception()` exists and is called from nowhere in that path. Wiring it
is the prerequisite for all seven runtime rows.

**3. `L4` is a state the code already produces and nothing reports.**
`autocode.py:425` logs `"Batch failed: %s"` and continues, so a job can complete
having tagged a subset — and today reports that as unqualified success with a
number that is quietly short.

**4. The HTTP details are developer copy and are being shown to researchers.**
`CodebookPanel` renders `err.detail` straight into the toast. Those strings quote
internal framework ids, and one tells the researcher to run
`bristlenose use <provider>` — a shell command, inside a Mac app. All nineteen
sentences here replace one.

**5. Pre-flight configuration refusals want a durable home.** A missing API key
is still true tomorrow; a four-second toast is the wrong container for it. Named,
not solved — and deliberately not invented here.

## Build log — what landed on 30 Aug

The message inventory turned out to rest on three things that did not work, so
the build started there rather than at the UI.

**The semantic palette (finding 0).** `--bn-colour-positive` and
`--bn-colour-warning` join the colour contract in both palettes — edo taking
Pine Green and Gold Ochre — and all eighteen uses of the three undefined names
now read a real token. `--bn-colour-danger` was a misspelling of
`--bn-colour-negative`. **`tests/test_theme_token_resolution.py`** fails on any
no-fallback use of an undefined custom property, and found two more the moment
it existed: About-tab citation links rendering as plain text, and a playground
button with no background.

**The five kinds on the web.** `frontend/src/utils/messageKind.ts` is the third
mirror of the glyph table, pinned to Python by
`tests/test_message_kind_mirrors.py` — asserted from pytest, because a Vitest
test would need `readFileSync`, which type-checks under Vitest and then fails
`tsc -b`. `toast()` and `Toast` take an optional kind.

**Refusals name themselves.** AutoCode's seven pre-flight refusals raise
`RefusalError`, serialised as `{detail, reason}` — `detail` unchanged for every
existing reader, `reason` the stable code the UI localises from. The seven
sentences from the inventory replace the HTTP details, which quoted framework
ids and told Mac users to run a shell command.

**A failed job says why it died.** `autocode_jobs.failure_kind` (migration 009)
carries the `LLMFailureKind`, populated by `classify_exception()` — which
already existed and was called from nowhere in that path. Both the toast and the
activity chip stopped interpolating `str(exc)`, which had been reaching
researchers as stringified JSON bodies.

**A partial run stops claiming success.** No column needed:
`processed_quotes` only increments after a batch succeeds, so `processed <
total` on a *completed* job is exactly the partial that `return_exceptions=True`
produces. Rendered as WARNING with both numbers.

Fifteen strings across all 21 full locales; `check-locales.py` clean.

**Still owed on this path:** the Mac half (**Q17** — nothing under
`bristlenose/server/` writes to the events log, so none of this reaches the
sidebar glyph or popover), and a durable home for configuration refusals, which
a four-second toast is not.

## Q17 in detail — which channel carries a job's state to the Mac

Measured 30 Aug. I had said the events log "isn't a missing wire, it's a
decision". That is right, but I understated the log: **three of its four readers
tolerate a new event type by construction**, so option A is more viable than I
implied. The objections to it are elsewhere.

### Option A — append a job event to `pipeline-events.jsonl`

**Safer than expected.** Every reader that derives run *state* is type-filtered,
not tail-based:

- `app.py:1022` scans backwards **for a terminus type** and skips anything else.
- `event_watcher.py` dispatches only on `RUN_COMPLETED`.
- Swift `EventLogReader`'s `default:` arm logs and returns `nil`, annotated
  *"Unknown event type — likely forward-compat"*.
- `read_events` "skips malformed", so even an unparseable line is inert.

**One real trap.** `tail_run_state` (`events.py:708`) walks the tail for the most
recent *lifecycle* event, skipping only `RunProgressEvent`. A new type would
become `last_event` and **mask the real terminus** — which is precisely the bug
its own comment records as *"Finding 1"*. Adding to that skip list is one line;
noticing it is the whole problem, and this would be the second recurrence.

**Two objections that are not mechanical.**

1. **The schema would have to lie.** Every event carries a `run_id`. AutoCode has
   no run. Either mint a synthetic one — a lie every reader inherits, including
   `PipelineRunner.swift:621`, which reads `tailEvent(at:)?.runId` — or make it
   nullable, weakening it for all five existing event types to serve a sixth.
2. **Governance.** `pipeline-events.jsonl` is a **named re-identification
   surface**, in `.bristlenose/` beside `pii_summary.txt`, with retention
   obligations and a 64 KB Swift read window. Job telemetry is new content in a
   file whose contents are deliberately constrained.

**Cost:** a new event type is the popover doc's **five-site change**, plus the
Swift mirror, plus a `pipeline-summary-contract.json` bump, plus the skip-list
fix.

### Option B — the Mac polls the per-framework status route

`failure_kind` already ships on `/autocode/{framework_id}/status`, so the server
work is **done**. But the Mac would have to know *which* frameworks to poll, at N
requests per project, and then synthesise a project-level rollup the server
already holds. Discovery and lifecycle are exactly what the events log gives for
free, and this option gives neither.

### Option C — a project-level activity endpoint — RECOMMENDED

One authed `GET /api/projects/{id}/activity`: the jobs currently running or
recently failed, each with its `failure_kind`. The Mac polls **one URL per
project** and renders; the server owns the rollup.

**Precedented, not invented.** `ServeManager.swift:1119` already polls
`http://127.0.0.1:<port>/api/agent-activity` behind the bearer and drives the
sidebar antenna from it — same transport, same authentication, same surface,
same "server computes, host renders" split. `health.py:146` even records *why*
that route sits behind the bearer rather than on auth-exempt `/api/health`,
which is the same reasoning a job-activity route needs.

No new event type, no weakened schema, nothing added to a re-identification
surface. And it generalises: clip export and Miro are jobs too.

### The question that actually decides it

**Is a failed AutoCode job a *record* or a *status*?**

The events log is a record — append-only, reconstructible from disk, survives a
restart, and is what a support bundle would carry. If a researcher needs to know
next week that a job failed, it belongs there and option A is right despite the
cost.

If it is live status — something they need *now*, on screen, while it is true —
then the job row in SQLite already persists it and the log adds nothing but
obligations. **That is the reading I would take**, which is why C is the
recommendation.

The two are not exclusive. C can ship now against work already done; A remains
open if the record turns out to matter.

### Q17a — there is no sixth event *type*. There is a sixth `kind`.

The question "what are the semantics of a sixth event type for the user?"
has an answer the schema already gives, and it is the one thing my Q17 write-up
missed.

**The five types are lifecycle positions, not subjects.** `run_started`,
`run_progress`, `run_completed`, `run_cancelled`, `run_failed` say *where in its
life* a piece of work is. They say nothing about which work.

**Which work is a separate axis that already exists.** Every event carries
`kind`, and `KindEnum` is already **three** values — `run`, `analyze`,
`transcribe-only`. So the log is not, and never was, about one thing. A full
pipeline run and an `analyze` are different acts with different durations, costs
and failure modes, and they share the same five verbs.

So the semantics of the five, stated plainly: **"a unit of work the researcher
asked for, and what became of it."** The type is the lifecycle position; the
kind is the work.

**Autocode is therefore a sixth `kind`, not a sixth type** — and it passes the
admission test the design doc already wrote, in the place it turned one down:

> **Should `kind: render` exist?** → **No.** Render is a read-only re-emission,
> doesn't change project state, and the static-render path is being actively
> phased out. — `docs/design-pipeline-resilience.md` §Open decisions

Render failed on *doesn't change project state*. Autocode **creates
`ProposedTag` rows and, on accept, `QuoteTag` rows** — it changes project state,
it costs money, and under **D4** the researcher explicitly asked for it by
installing. It is the same shape as `analyze`: a smaller, separately-invoked act
on the project.

**What this fixes in the Q17 analysis above.** Two of the three objections to
Option A dissolve:

- **The schema no longer has to lie.** An autocode job is a unit of work and
  gets its own `run_id` honestly. Nothing goes nullable.
- **No five-site new-type change.** `KindEnum` gains a value — the doc's own
  note says *"New kinds require code change + migration"*, which is smaller than
  minting a type, and no reader's type-filter is touched.

**What survives.** The `tail_run_state` trap is unchanged and arguably worse: it
walks the tail for the most recent lifecycle event, and an autocode terminus
would now legitimately *be* one — masking the run's. And the governance point
stands: the file remains a named re-identification surface, so an autocode
`run_progress` inherits the counts-and-timings-only rule.

**And the question this exposes is the real one, independent of channel.**
A project can hold a **completed run and a failed job at once**. The sidebar row
renders one glyph. A failed codebook does not mean the analysis is broken — the
report exists, the quotes are there, one optional enhancement did not apply — so
rendering it as `.failed` would tell the researcher their project died. The row
already has the vocabulary for this: **`.partial(kind:stagesComplete:)`**, which
is what `transcribe-only` resolves to. That is where a failed job belongs, and
it needs deciding whichever channel carries it.

### Q17b — an extension is downstream-only, and that decides the precedence

Settled framing, 30 Aug (user): **autocode is an optional modular extension to
the run — "you've already got your burger, do you want fries with that?"**
Sentiment is *part of* the run; a Library codebook is not. And an extension has
its own full mini-lifecycle: started, progress, completed, cancelled, failed.

**The asymmetry is the load-bearing part.** A run can succeed and its extension
fail. **The reverse is impossible** — no extended analysis can run without a
working vanilla project underneath it.

That is not a detail; it **decides the precedence question** the previous section
called channel-independent and open:

| run | extension | row |
|---|---|---|
| failed | *cannot have run* | `.failed` — the run's own cause |
| succeeded | failed | **`.partial`, never `.failed`** |
| succeeded | succeeded | `.ready` |

There is no ambiguous cell, because the dependency forbids it. A failed
codebook can never mean "you have no project", so it can never outrank a run
failure and can never present as one.

**And it corrects `kind`.** `run`, `analyze` and `transcribe-only` are three
*alternative* entry points — you pick one. Autocode is not a fourth alternative;
it is a **successor**. Listing it beside them would put a dependent act in a menu
of mutually exclusive ones.

**The synthesis of the two options the user named.** An extension emits its own
mini-lifecycle *and* reuses the stage-rollup machinery rather than inventing a
parallel one: a terminus whose `PipelineSummary` carries a **`codebooks` slot**
and nothing else, exactly as `transcripts` is `None` for `analyze` and
`quotes`/`themes` are `None` for `transcribe-only`. The summary is already
shaped for "this kind of work populates these slots".

Two things make that fit rather than force:

1. **`PipelineSummary` already states the semantics we need.** From its own
   comment: *"A non-empty `failed` here does NOT mean the run failed."* That is
   precisely the extension contract.
2. **Adding a slot has direct precedent, for this exact reason.** The `ingest`
   slot "did not exist until Aug 2026, which is why refusals reached no surface
   at all: `StageFailure.source_file` had been added in Jul 2026 for exactly this
   case, and three consumers already keyed on it, but there was nowhere in the
   summary to put one." A slot was added to give an existing failure somewhere to
   live. This is the same move.

**Why it cannot simply be a stage of the main run.** `PipelineSummary` attaches
to a **terminus**, and the log is append-only. Autocode is invoked later, from
the UI, after that line is written — there is nothing to amend. Hence the
mini-lifecycle: the extension is its own event sequence, whose *internal*
structure borrows the stage vocabulary.

**What this leaves as real work, now well-specified rather than vague:**
`tail_run_state` must derive state **per lifecycle**, not from the tail — an
extension terminus is legitimately the most recent lifecycle event and would
otherwise mask the run's. That is the trap named twice above, and this framing
turns it from "a thing to remember" into "the function takes a kind".

**One open shape.** Sentiment is in the run, so autocode is the only extension
today. Whether the slot is `codebooks` or a general `extensions` map is worth
deferring until a second extension exists — a fixed named slot is clearer, and
generalising for one case is how a schema acquires a dictionary nobody needs.

### Q17c — the schema must not learn the names of extensions

The previous section deferred "one `codebooks` slot or a general map?" on the
grounds that generalising for a single case is how a schema acquires a dictionary
nobody needs. That deferral was wrong, because there are **two** plurals and only
one of them is hypothetical.

**Plural instances — real today.** Nine codebooks in the Library. Install three
and there are three autocode jobs, three lifecycles, three ways to fail. Even
with one extension *type*, the state is already a set.

**Plural types — speculative but named.** A researcher's own, or a corporate,
processing of tags, adding a lens, with its own flow and its own states.

The two want different answers, and conflating them is what a single `codebooks`
slot would do.

**The instance plural already fits.** `StageOutcome` is `{attempted, succeeded,
failed[], duration_ms}` — three codebooks attempted, two succeeded, one failed is
exactly that shape, unchanged. **One gap:** `StageFailure` can carry
`session_id` or `source_file`, and an autocode failure is neither
session-scoped nor file-scoped. Nothing in it can say *"Nielsen"*.

That is precisely the gap `source_file` was added to close for files, and its
docstring records the reasoning: it exists "because `session_id` alone cannot
identify the file for failures that happen *before* a session exists… every
downstream surface was left unable to name it." An extension failure is the same
problem one level out.

**The type plural argues against named slots — and the mini-lifecycle removes the
need for them.** If each extension is its own event sequence with its own
`run_id` and its own terminus, then **each extension carries its own summary**.
There is no single rollup that has to enumerate extensions, so `PipelineSummary`
never grows a `codebooks` field, never grows a `corporate_tagger` field, and
never grows a map. The plurality is carried by *multiple sequences*, not by
multiple slots.

**Which gives the design rule: an extension names itself in the data, never in
the schema.** A second extension type is then a new *value*, not a new *field* —
no migration, no Swift mirror, no fixture bump, no five-site change. Compare the
cost of the alternative: under named slots, every extension anyone ever writes
taxes `events.py`, `PipelineSummary.swift`, the contract fixture and
`EventLogReader` — which is an odd toll to charge a thing whose whole selling
point is being modular.

**Two constraints that ride along, so they are not rediscovered:**

1. **The re-identification rule is inherited, not re-litigated.**
   `RunProgressEvent` carries counts and timings *only* — never an id, filename,
   speaker label or transcript-derived string. An extension's progress is bound
   by the same rule: a corporate tag processor may report *how many*, never
   *which tags*. The file is a named re-identification surface and an extension
   does not get an exemption for being new.
2. **The rollup stays trivial because of the dependency.** However many
   extensions and instances exist, the sidebar row needs one question answered —
   *did any extension fail?* — and the answer can only ever produce `.partial`,
   never `.failed`, because every extension is downstream of a working project.
   N extensions do not make the precedence N-way; the asymmetry collapses it.

### Q17d — consequences, played back

What the Q17 thread commits to, separated into what a researcher sees and what
the schema has to become. Nothing here is built; the SPA half shipped on 30 Aug
and reaches the browser only.

#### UX and flow

**The sidebar row gains a third outcome, and it is the important one.** Today a
project row is broadly working / working-on-it / broken. An extension makes
**"finished, with one part missing"** a first-class state — and the dependency
guarantees it can never be mistaken for the second:

| run | extension | row | what the researcher reads |
|---|---|---|---|
| failed | *cannot have run* | `.failed` | the run's own cause — "Claude is out of credit" |
| succeeded | failed | **`.partial`** | the project is fine; a codebook did not apply |
| succeeded | succeeded | `.ready` | nothing — Schema E shows no status line on a clean row |

**A failed codebook must never present as a failed project.** The report exists,
the quotes are there, one optional enhancement did not apply. That is the whole
UX consequence of the burger/fries framing, and it is why `.partial` — which
already exists for `transcribe-only` — is the right home rather than a new state.

**The popover has to name which codebook.** "A codebook failed" is not
actionable when three are installed. This is the one place the extension model
demands new information rather than reusing existing shape.

**The flow the researcher experiences is unchanged.** They install; it runs; the
row shows progress; it finishes or it doesn't. What changes is that the row stops
lying in the one case where the run succeeded and the extension did not —
today that case is invisible on the Mac entirely.

**Cancelled stays distinct from failed**, per the run's own vocabulary: an
extension the researcher stopped reads "stopped", not "failed". The five
lifecycle verbs carry over whole; that is the point of reusing them.

#### Schema

**Settled by the thread:**

- **No new event *type*.** The five verbs are lifecycle positions and cover an
  extension unchanged.
- **No per-extension slot on `PipelineSummary`.** Each extension sequence carries
  its own summary, so the schema never enumerates extensions.
- **`tail_run_state` derives state per lifecycle, not from the tail.** An
  extension terminus is legitimately the most recent lifecycle event and would
  otherwise mask the run's. Currently a trap; becomes a signature change.
- **Extension progress inherits the counts-and-timings-only rule.** No ids, no
  filenames, no tag names — the file is a named re-identification surface.

**My synthesis of the two constraints, not stated outright above and worth
ratifying or rejecting:** `KindEnum` gains exactly **one** value — `extension` —
permanently, however many extensions ever exist. `kind` then answers "entry point
or extension?", which is a real category distinction, rather than listing a
successor beside three alternatives (the Q17b objection). *Which* extension is a
separate field the schema does not enumerate (the Q17c rule). One value, once.

**Genuinely open:**

- **Does one extension sequence cover one codebook or several?** Under D4,
  install-is-apply is per codebook, so one job = one codebook = one sequence,
  and the sequence names it — no change to `StageFailure` needed. But
  `reapply_active_frameworks` codes **every active framework** for newly-added
  sessions, which is one act over N codebooks. If that emits one sequence,
  `StageFailure` needs to name a codebook after all — the gap Q17c identified,
  and the same shape as `source_file`.
- **Whether the extension identifier is one field or two** (type, and instance).

**Unchanged and still blocking, from Q17:** nothing under
`bristlenose/server/` writes to the events log at all. Every word above
presumes a writer that does not exist yet, and autocode runs in the server.

### Q17e — "out of the schema" was the wrong phrase

Q17c said *"an extension names itself in the data, never in the schema"*, and
Q17d compressed that to *"which extension stays out of the schema"*. That reads
as though the researcher would not be told which extension failed, which would
be useless. The opposite is intended, and the distinction is **field name against
field value**.

- **Out of the schema:** a field *called* `codebooks`, or `plato`, or
  `corporate_lens_c`. The structure never enumerates extensions, because then
  every new one is a migration in two languages.
- **Very much in the data:** *which* extension and *which* instance, as values
  in generic fields. This is what every surface reads and renders.

So `"Plato autocode succeeded"` is `extension="autocode"`, `instance="plato"`,
`outcome=completed`. Same shape as `kind="analyze"` today: the *field* is
`kind`, and `analyze` is a value in it, not a column.

**The three worked examples, against the existing vocabulary:**

| what the researcher reads | outcome | cause | shape |
|---|---|---|---|
| *Plato autocode succeeded* | `completed` | — | `failed[]` empty |
| *Corporate lens C failed authentication* | `failed` | `category=auth` | existing category, no new one |
| *CLI analysis tool incomplete* | `completed` | — | `failed[]` **non-empty** |

The third is the interesting one and it needs no new outcome: **`PipelineSummary`
already states that "a non-empty `failed` here does NOT mean the run failed."**
Incomplete is `completed` with losses, which is exactly the L4 partial the
AutoCode toast now renders in the SPA.

**And the sentence templates already parameterise the subject.**
`PipelineRunner.swift:1828` is `let subject = provider?.displayName ?? "LLM
provider"`, feeding *"Your \(subject) key isn't working."* An extension that
authenticates against something other than the LLM provider — the corporate lens
— supplies its own subject and the existing string renders correctly. That is
the payoff of an extension naming itself in the data: the *rendering* needs no
extension-specific code either, only a value.

**What this does add, and it is the one real addition:** the row and popover need
the extension and instance in the sentence — *"Plato"*, not *"a codebook"* —
which is the naming gap Q17c identified. It is one or two values on the event,
not a slot per extension.

### Q17f — one sequence or several: the UX consequences

The question only arises because **two different acts produce autocode work**,
and they are not alike.

| | **Install** | **Reapply** |
|---|---|---|
| trigger | researcher clicks | automatic, on `run_completed` |
| scope | one codebook | every applied ∩ linked ∩ enabled framework |
| review | proposals to review | **none** — accepts at the job's stored cutoff |
| cost | knowingly spent | spent without being asked |
| today | toast + chip in the SPA | **completely silent** |

In the burger framing: install is ordering fries. Reapply is the refill that
arrives with the meal — you did not order it, and it exists to keep what you
already have true.

**The real UX problem is not granularity, it is that reapply is invisible.**
`app.py:963` guards it — *"a re-apply failure never breaks the import/publish
contract"* — so a failure is logged and nothing else. And a silent reapply
failure is **worse than a failed install**, because a failed install is
self-evident (the codebook has no tags at all) whereas a failed reapply leaves a
codebook **partially applied across sessions**: sessions 1–12 coded, sessions
13–18 not, nothing on screen distinguishing them. The researcher reads a
codebook as complete when it has a hole in it. That is a data-integrity problem
wearing the clothes of a background chore, and it is the thing worth fixing
whatever the sequence shape.

#### Option A — one sequence per codebook

Three frameworks reapplied = three lifecycles.

- **Against:** the researcher performed *one* act — they added sessions — and
  would watch three things happen that they never asked for. Progress becomes
  three streams the single row has to roll up anyway.
- **For:** failure and retry are natively per codebook, which is where the money
  is.

#### Option B — one sequence covering the reapply

One act, one lifecycle: *"keeping 3 codebooks current on 12 new sessions."*

- **For:** matches what the researcher did. Per-codebook detail lives in
  `failed[]`, exactly as a run's summary carries per-session failures.
- **Cost:** `StageFailure` must name the codebook — the gap Q17c found.

#### The money settles it, and it closes the gap as *required*

If three reapply and one fails on a rate limit, retrying the sequence re-spends
on the two that worked. **So per-codebook identity is mandatory either way** —
which turns the `StageFailure` naming gap from an open question into a
requirement, and removes A's only advantage. **B, with the codebook named in
`failed[]`.**

That is also the shape the run already uses: one sequence, a summary naming
per-session failures, and recovery aimed at the named entries rather than at the
whole.

#### And one option the trigger rules out

Reapply cannot be folded into the run's own sequence. It fires **from**
`_on_run_completed`, after the terminus is written, and the log is append-only.
Deferring the terminus until reapply finished would be worse than the problem:
**the SPA mounts on `run_completed`**, so the researcher's report would be held
hostage to a maintenance pass they did not ask for.

#### The UX that falls out

- **Install failure** — as now: toast in the SPA, and (when the Mac half lands)
  the row goes `.partial` with the codebook named.
- **Reapply failure** — the same `.partial`, but the sentence has to carry what
  is actually wrong: not *"tagging failed"* but *"Nielsen is missing from 6
  sessions."* The consequence is a hole in a codebook, and naming the codebook
  without naming the hole would still leave the researcher unable to trust it.
- **Reapply success stays silent.** Maintenance that worked is not news, and
  Schema E's clean row already says so by showing nothing.

### D28 — no migration for v2. Reprocess the trial projects.

Settled 30 Aug. **Legacy trial projects get reprocessed; migration machinery is
for V1 → V2 when we leave beta.** So nothing in this design is constrained by
having to carry existing project data forward, and no migration path is owed
before v2 ships.

The blast radius is genuinely small: the TestFlight cohort was never enrolled,
so the projects in question are the maintainer's own trial runs.

**What that unblocks.** **D20's option A** — uninstall stops preserving groups,
definitions, jobs and proposals — stops being a live-data change needing a
backfill. It becomes a behaviour change on projects that will be rebuilt anyway.
Same for any other breaking change to codebook state: free until GA.

**Two caveats, so "just reprocess" is not heard as more than it is.**

1. **Reprocessing regenerates the analysis, not the database.** The SQLite file
   is per project at `<output_dir>/.bristlenose/bristlenose.db`, and nothing in
   the re-run path unlinks or drops it — so **Alembic still has to migrate a
   real user's DB**, and a guarded additive migration (like 009) is still the
   only safe shape. Only deleting the output directory gives a fresh schema, and
   that is a separate manual act.
2. **Re-analyse is still destructive.** Reprocessing a trial project discards
   hand-curation on it — accepted and denied proposals, manual tags, edited
   names. For the maintainer's own trial runs that is a fine trade; it is worth
   naming once so it is a choice rather than a surprise.

**What stays owed at GA**, and is now explicitly out of scope here: a real V1 →
V2 path for projects someone else owns.

### D29 — v2 lands as a parallel surface behind a flag, not a rewrite in place

> **Closed 31 Aug 2026.** The parallel period ran its course: v2 became the only
> codebook lens, took `/report/codebook`, and v1 was deleted. See
> `design-codebook-v2-plan.md` § Phase 7 for what moved. One part of this
> decision was **never satisfied** and is worth naming rather than quietly
> dropping — D29 argued for a *settings* flag rather than `--dev` so the cohort
> could reach the lens, and what shipped was `IS_DEV`. The lens went straight
> from dev-gated to default-on; the intermediate step stopped being needed once
> the swap arrived, but no cohort member ever saw v2 behind a flag.

Settled 30 Aug. `CodebookPanel.tsx` is **1,545 lines** and ten files reference it
(`QuoteThemes`, `QuoteSections`, `TagSidebar`, `SidebarStore`, `main.tsx`,
`codebookDot`, `colours`, and three test files). Rewriting that in place means
the lens is broken for the whole of the build.

**The mounting pattern already exists, twice.** `codebook-lab` and the chat lens
are each *"one route plus one lab page"* behind a **settings flag rather than
`--dev`** — `app.py:254` and `:261` — deliberately, *"so it ships in the bundled
desktop sidecar and plain `serve`"*. The cohort can reach a flagged surface; a
`--dev` one they cannot.

**But v2 is not a lab, and should not borrow that framing.** The chat-lens module
says its page is *"deliberately ugly (codebook-lab precedent)"* because what a lab
tests is a hypothesis. v2 is the **replacement**, built to production fidelity.
Same mounting, opposite fidelity expectation — worth saying out loud so nobody
reads "flagged surface" as "rough".

**Why parallel beats a branch.** A branch gives isolation; it does not give
**comparison**, and comparison is the thing actually needed. The house default is
trunk anyway — *"a branch is free; a worktree costs an env"* — and the two worst
recorded incidents in this repo came from the multi-worktree pattern.

**Side-by-side is not a convenience, it is the mechanism that enforces the
no-invention rule.** Every prototype defect this session came from not looking at
the original: `.add-btn` invented and described as a lift; `.bn-btn`'s base rule
never carried across; `filter: saturate()` used on two surfaces and present in
none; a "consistency fix" that unified two inventions. All four are *failures to
look*, and all four are prevented by the shipped lens being one click away on the
same project with the same data.

**And it makes the four Indicative items decidable.** A button treatment cannot
be ratified from a static mockup on fixture data. It can be ratified from the
real control beside the shipped one.

**The risk, and why the flag disarms it.** A parallel implementation becomes
permanent — the repo carries that scar, and the rule *"actively remove static
render, don't find clever uses"* exists because of it.

**But the flag is not only the shipping vehicle; it is the deletion
instrument.** Turn it off, work exclusively on v2, and nothing breaking *is* the
evidence that v1 is dead weight. That is a moment you can schedule and observe,
and it is exactly what static render never had — no flag, so there was never a
day on which switching it off proved anything, which is how it survived long
enough to need a rule.

So the sequence is: flag on and both live → flag defaults on → **flag visibly
off while v2 carries real work** → delete. The deletion trigger is that third
step passing quietly, not a judgement that we are happy.

### D28a — what "guarded additive migration" means here, measured

Across the nine migrations in `bristlenose/server/alembic/versions/`:

| | |
|---|---|
| upgrades that are **purely additive** | **7 of 9** — `add_column` / `create_table` / `create_index` |
| upgrades that **drop** anything | **none.** The single `drop_column` (008) is in `downgrade()` |
| `downgrade()` raising `NotImplementedError` | **8 of 9** — forward-only by house rule |
| migrations carrying a **backfill** | 3 (003, 004, 005) — in the *same* migration, not a later release |
| structural changes | 1 (004), via `batch_alter_table` |

So: **add, then move to it — and you do not get to move back.** The safety comes
from additive-first, not from reversibility.

**"Guarded" has a specific cause, not general caution.** `init_db` runs
`create_all()` **then** `run_migrations`, which stamps 001 and upgrades to head —
so `upgrade()` *does* run on a brand-new database where the model has already
made the column. `_has_column` makes it inert there. Every migration carries that
helper because of the boot order, not out of defensiveness.

**004 is the template for anything harder than a new column**, and its two moves
are the ones worth copying:

- **`batch_alter_table`**, because SQLite cannot drop a constraint in place —
  Alembic rebuilds the table. Still conditional (`if "uq_…" in
  _unique_constraint_names(...)`), guarded exactly like the additive ones.
- **It decides in advance what it will lose.** `heading_edits` has
  `UNIQUE(project_id, heading_key)`, so a colliding re-key would raise
  `IntegrityError` and abort the *whole* migration. It builds a `live_keys` set,
  skips the collisions, and leaves those rows un-rekeyed — *"a one-time loss,
  documented in the plan"*. **A migration that can partially fail must choose its
  loss up front and write it down**, or it takes the whole upgrade with it.

**And the distinction that matters most for the extension work:** almost none of
it is a database change at all.

| change | discipline |
|---|---|
| `autocode_jobs.failure_kind` | **DB** — migration 009, guarded, additive. Shipped |
| naming the codebook in `StageFailure` | **wire** — a Pydantic model in `events.py` |
| `KindEnum` gaining `extension` | **wire** |
| an extension's own summary | **wire** |

The events log is NDJSON on disk, versioned by `schema_version`, and
`read_events` *"skips malformed"* lines. So a wire change is `events.py` + the
Swift mirror + a `pipeline-summary-contract.json` bump — no Alembic, no
`ALTER TABLE`, and old lines stay readable. Different discipline, much cheaper,
and easy to conflate with the DB work because both are called "schema".

## Gap analysis + prototype QA — 30 Aug, measured

Two questions: **is v2 about to remove something we ship?** and **does any
control in the prototype lead somewhere undesigned?** Both answered
mechanically against `CodebookPanel.tsx` (1,545 lines) and the prototype, not by
reading.

### A. Shipped behaviour v2 drops

| | shipped today | v2 | verdict |
|---|---|---|---|
| **1** | **`restorable`** — the card's verb becomes **"Restore codebook"**, a **"Previously imported"** note appears, and the page promises *"AutoCode results are preserved — reinstall any time from the Codebook Library."* | all three gone | **D20 option A. Deliberate — but it retires a promise, not just a label. Worth confirming explicitly** |
| **2** | **`imported`** — an **"Installed"** badge in the card's top-right (`.picker-card.imported::after`) | the button reads Uninstall instead | D11 says state is *shown*, not re-offered. The badge was the showing; the button is the control. **Confirm the button alone carries it** |
| **3** | The separate **Apply** button (`autocode-btn`) | gone | **D4** — deliberate |
| **4** | Near-fullscreen **modal** + close (`codebook-modal*`) | full-page routes | **D6** — deliberate |
| **5** | **"Coming soon"** on `!enabled` templates | not rendered | **Dead today: 0 of 9 templates ship `enabled: false`.** Dropping an unreachable affordance, not a regression — but v2 loses the *capability* to mark one |
| **6** | **Keyboard access** on `tag-add-row` (`role="button"` + `tabIndex`) and `new-group-placeholder` (`role="button"` + `onKeyDown` + `tabIndex`) | neither in the prototype | **REGRESSION. Not a decision — an omission** |

### B. What v2 shows that has no data yet

- **`ver`** — the version chip. **Q6**, one field on `TemplateOut`; the YAML
  already parses it.
- **`jacket`** — the graphic. **Q4**, deferred by decision.
- **The provenance line** — **D23**, new; `author_bio` / `author_links` already
  ship (`CodebookPanel.tsx:1518`), so only the built-in case is new.

### C. QA — every control, and where it leads

**No dead controls.** Every interactive element resolves to a handler: seven ids
and seven `data-*` hooks in the delegated listener, plus separate handlers for
the palette switch, the switch-fallback toggle and the confirm dialog. The
"Create new codebook" class of defect — a live control that no-ops — does not
recur.

**One control whose real destination is undesigned.** The author's external links
render as `<a href="#" onclick="return false">`. Inert is right for a prototype,
but the shipped behaviour is unspecified: **opening an external URL from an
embedded WKWebView needs a decision** (hand to the default browser, almost
certainly — never navigate the app's own web view away from the report).

**Six clickable non-buttons with no keyboard path** — `sb-row`, `tag-del`,
`tag-add-row`, `new-group-placeholder`, `picker-card`, and one more. Only the
switch carries a `role`. Two of these are the **A6 regression** above; the rest
are new surfaces that never had it. One `keydown` listener exists in the whole
prototype.

### The one thing to confirm before building

**A1 — retiring "Restore".** Everything else is either deliberate and recorded,
dead already, or an omission to fix. The restore promise is the only place v2
takes away something a researcher can currently rely on: today, uninstalling is
reversible and the UI says so in three places. After D20 option A it is not, and
saying so is D20's *"click uninstall and you say byebye"*. That is the intended
change — this is the note that it has a visible surface today, not just a code
path.

### A1 confirmed — retire "Restore", and put it back later with less verbiage

Confirmed 30 Aug (user): *"new UX is better, less fiddly — functionality we're
losing is mostly confusing… put back later with more care and less verbiage."*

So **D20 option A stands**, and the three shipped surfaces go with it: the
*"Restore codebook"* verb, the *"Previously imported"* card note, and the
*"AutoCode results are preserved — reinstall any time from the Codebook
Library"* line.

**That last string is the argument for removing it.** Twenty-two words to
explain a state the researcher has to hold in their head — that an uninstalled
codebook is secretly still there — and the state it described **did not work**:
the restore branch reset accepted proposals to pending, and under D4 a reinstall
re-spends anyway. It was verbiage explaining a promise the code did not keep.

**The 100-day item inherits a constraint, not just a task.** When
non-destructive uninstall returns it must be *shown, not explained* — no
sentence telling the researcher what is preserved. If the state needs a
paragraph, it is the wrong state.

### A6 fixed — keyboard parity restored, and extended

The regression is closed and the new surfaces got the same treatment: `sb-row`,
`tag-del`, `tag-add-row`, `new-group-placeholder`, `picker-card` and the
fallback switch now all carry `role` + `tabindex`, with one delegated `keydown`
listener handling Enter and Space (preventDefault'd, or Space scrolls the page
under the control). The platform `<input type="checkbox" switch>` was already
focusable. Verified: **no element carries a `role` without a tab stop.**

## External links — author websites and book links

Raised by the 30 Aug QA pass as the one control in the prototype whose real
destination is undesigned. Drawn in parallel as
[`docs/mockups/codebook-v2-external-links.html`](mockups/codebook-v2-external-links.html),
which reaches the same verdict from the frames; this is the record. Answered
here mechanically, against `WebView.swift`, `CodebookPanel.tsx`,
`routes/export.py` and the nine YAML files — not by reading the prototype.

**The headline is that there is no bug to fix.** The prototype's links are inert
stubs (`<a href="#" onclick="return false">`), but the *shipped* renderer is not:
`CodebookPanel.tsx:1526` already emits a real anchor, and every context already
resolves it correctly. The work this section identifies is a **parse-time scheme
allowlist** that costs nothing today and is the difference between safe and
unsafe the moment the codebook corpus stops being maintainer-curated.

### What a click does today, per context

| Context | Path | Verdict |
|---|---|---|
| **Desktop** (WKWebView) | `target="_blank"` → `createWebViewWith` (`WebView.swift:601`) → `isAllowedServeURL` fails → `openExternal(url)` → `NSWorkspace.shared.open` | **Already correct.** Opens the default browser; returns `nil`, so no popout window is created |
| **Browser** (`serve`) | new tab, `rel="noopener noreferrer"` | Standard, matches 12 sibling sites |
| **Export** (`file://`) | **the links never render** — see below | No decision to make today; one to make for D23 |

**The desktop answer needed no design, because SECURITY #8 already made it.** The
concern in the QA note — that an unhandled `_blank` silently does nothing in
WKWebView unless `WKUIDelegate.createWebViewWith` is implemented — does not apply:
it *is* implemented (`WebView.swift:599-614`), and it hands non-serve URLs to
`openExternal`. The app is safe two ways, because a same-frame click without
`target="_blank"` would hit `decidePolicyFor` (`WebView.swift:251`), fall past
`isAllowedServeURL`, and take the same `openExternal` + `.cancel` pair. The web
view cannot be navigated away from the report by an author link, with or without
the `_blank`.

`openExternal` (`WebView.swift:317`) is itself scheme-gated to `http` / `https` /
`mailto`, and logs a warning otherwise. That gate was added because the
pre-existing fallthrough called `NSWorkspace.shared.open` on anything — which
happily launches `file://` and renders `data:`.

**Export mode does not render `author_links` at all.**
`/projects/{project_id}/codebook/templates` sits in `SERVER_ONLY_PATH_TEMPLATES`
(`routes/export.py:79`), so `apiGet` throws for it offline (`utils/api.ts:92-97`).
Both fetch sites swallow the throw — `.catch(() => {})` at `CodebookPanel.tsx:654`
and a `console.error` at `:812` — so `templates` stays `null`, `selectedTemplate`
stays `null`, and the author sidebar is behind `selectedTemplate &&` at `:1451`.
Belt as well as braces: `.codebook-picker-btn` is hidden by `export.css:64`, so
the door is shut too.

**That is the one thing to carry forward.** It holds only because the links live
in the *browse preview*, which is server-only. **D23 puts the provenance line on
the codebook page**, which does ship offline — so D23 moves `author_links` into
the export for the first time. When it lands, the links become live anchors in a
file a researcher hands to a client, and the export's read-only story has to
cover them. Nothing about that is hard; it is only invisible.

### Precedent — the pattern ships, do not invent one

Fourteen `target="_blank"` anchor sites in `frontend/src`. Twelve carry
`rel="noopener noreferrer"`; `author_links` is one of the twelve. Two carry a
bare `rel="noreferrer"` (`ProposalZoneList.tsx:127`, `AutoCodeReportModal.tsx:227`)
— equivalent in modern browsers, since `noreferrer` implies `noopener`, but
inconsistent. Two `window.open` calls pass no `noopener`
(`Dashboard.tsx:389`, same-origin; `AppLayout.tsx:560`, the first-party blog);
neither destination is data-driven.

The About tab's citation links (`.bn-about-citation a`, `report.css:158`) use the
same anchor form with no glyph. **`author_links` already conforms to the house
majority. No new pattern is needed, and none should be added.**

### App Sandbox — nothing required

`NSWorkspace.open` on an `http`/`https` URL is a LaunchServices-delegated action;
the sandbox permits it with no entitlement, and it does not need
`com.apple.security.network.client` — the browser makes the connection, not us.
The host entitlements file carries only `keychain-access-groups`; sandbox and
Hardened Runtime come from build settings, not from it. Both entitlements files
are `skip-worktree` (`git ls-files -v` → `S`), and the working copy matches HEAD
today — nothing is riding. **No entitlement change, and no new row for
`design-desktop-security-audit.md`:** row 6 (SECURITY #8) already closed this
class.

### Security — three gates today, one of them not ours

The shipped corpus is 22 links across all nine YAML files, every one `https`,
loaded with `yaml.safe_load` (`codebook/__init__.py:161`). The live risk is nil.
The question is what happens when the corpus stops being curated — the public
codebook library with community submission, parked in the maintainer's private
planning notes, kept outside the public tree.

| Vector | Mitigated by | Whose gate |
|---|---|---|
| `javascript:` | React 19's `sanitizeURL` rewrites the href to a throwing stub; the regex tolerates leading control characters and `\r\n\t` interleaved through the scheme | **React's** |
| `javascript:` reaching navigation | `openExternal`'s scheme gate | ours (desktop only) |
| `data:text/html` | browsers block top-level `data:` navigation; `openExternal` blocks it on the Mac | browsers' + ours |
| **label names one host, href points at another** | **nothing** | — |

**Two of the three gates are not ours, and the strongest one is a framework
behaviour we do not control.** React's sanitiser protects this render site and
nothing else: it evaporates if the links are ever rendered through
`dangerouslySetInnerHTML`, through a vanilla template, through the frozen
modules in `theme/js/`, or natively in SwiftUI. The MCP endpoint reads the same
templates and is not React at all.

**Recommendation: allowlist the scheme at parse time, in the YAML loader.**
`_parse_template` (`codebook/__init__.py:129-134`) currently appends every
`(label, url)` pair unvalidated. Reject anything that is not `https` there, the
way `_parse_group` already refuses an unknown `colour_set` at `:107` — raising
with the filename, at load, before any surface sees it. Three reasons to put it
there rather than at render:

1. **One gate serves every surface** — React, the export embed, the MCP
   endpoint, and any future native renderer. A render-time gate has to be
   re-implemented per surface, and this codebase has already paid for what
   happens to per-surface and CSS-only gates: they stop matching silently.
2. **It fails loudly and early**, with a filename, which is the whole contract
   for a submitted file.
3. **It is a no-op on today's corpus.** All 22 URLs are already `https`. Adding
   a constraint while it costs nothing is the cheap moment; adding it once
   submissions exist means rejecting other people's files.

Two smaller things in the same function, worth fixing in the same pass: `_str()`
coerces *any* YAML value to a string, so a nested dict arrives as
`"{'a': 1}"`; and a missing `url` becomes `""`, which renders `<a href="">` — a
page reload.

**The label/href mismatch has no validation answer**, and it is the one an
attacker would actually use. `label: nngroup.com` with
`url: https://evil.example` is well-formed `https` and passes any allowlist. It
needs a presentation answer, below.

### Presentation

**The ↗ glyph is not a house pattern.** It ships in exactly one place —
`CodebookPanel.tsx:1527` — and the prototype mirrors it. Nothing in
`docs/glossary.md` or `bristlenose/theme/` establishes it. **Keep it anyway:** it
is the product's only external-link marker, the prototype and the shipped
renderer already agree, and removing it would make these links read as internal.
A sample of one that two surfaces already share is not drift.

**The raw-domain labels are a data problem, not a renderer problem.** The
glossary's rule is *"No 'click here' link text — describe the destination."* A
bare `nngroup.com` names a host, not a destination. The corpus is already
inconsistent about this without anyone deciding it should be:

- `nielsen.yaml` — `nngroup.com — 10 Usability Heuristics` (host **and**
  destination)
- `garrett.yaml` — `jjg.net` (host only)
- `plato.yaml` — `plato.stanford.edu` entries, host only

The nielsen form is the one that satisfies the glossary. Truing the other eight
files to it is a YAML pass, no code.

**And that same change is the mitigation for the mismatch attack.** Rather than
revealing the destination on hover — `title` is not keyboard-reachable and is
read inconsistently by screen readers — render the **host** as part of the link,
always. Curated links then read as they do now, and a submitted link claiming to
be Nielsen's site while pointing elsewhere shows its real host in the label by
construction, with nothing to hover and nothing to notice. It replaces a
security question with a typographic one.

Out of scope here, flagged because readers will ask: the `Amazon US` / `Amazon UK`
pairs are a per-locale question, not a link-handling one.

### Recommendation, in order

1. **Ship nothing for the desktop or browser cases.** Both are already correct,
   and the desktop case was settled by SECURITY #8 before this question was asked.
2. **Add the `https`-only allowlist to `_parse_template`**, with a test that a
   `javascript:` URL in a template file fails the load. No-op on the current
   corpus; the whole point is to add it while it is free.
3. **True the eight non-nielsen YAML files to the `host — destination` label
   form**, which satisfies the glossary and pre-empts the mismatch case.
4. **When D23 lands, revisit the export.** It is the change that first puts these
   links in a file that leaves the researcher's machine.

### D30 — URLs from config are distrusted at parse time, https only

Settled 30 Aug, after a parallel research session converged on the same problem
from the other end. Its findings corrected two things here and are worth keeping.

**The gate is at parse time, not at each render site.** `_parse_template`
(`server/codebook/__init__.py`) drops any `author_links` entry whose URL fails
the check, and logs which label it dropped. One gate serves the React render,
the HTML export, the MCP surface and anything added later; a per-renderer gate
is one grep away from being incomplete. The render site keeps its filter as
defence in depth, where it is now a no-op.

**Two scheme sets, because there are two questions.** `ALLOWED_SCHEMES`
(http/https/mailto) answers *"may this be an href at all"* — the right question
for a URL the researcher reached, and it matches Swift's `openExternal`.
**`CONFIG_SCHEMES` is https-only** and answers *"may a stranger put this in our
corpus"*. All 22 shipped author links are already https; plain http from a
submitted codebook is a downgrade buying nothing. Inheriting one policy for the
other would have been the lazy read.

**No dependency.** `bleach` was deprecated in 2023; DOMPurify sanitises *HTML*
at ~20 KB for a check that is one function. The rule is borrowed — allowlist,
never denylist, per OWASP — and the parsing is the platform's (`urlparse`,
`new URL()`), which is the half that gets `JaVaScRiPt:` and a tab-split scheme
right. Only the policy is ours. Pinned across languages by
`tests/fixtures/safe-url-contract.json`, 18 adversarial cases, asserted from
both pytest and vitest.

**Two corrections from the other session, both recorded rather than argued:**

1. **Export mode does not render these links today** — `/codebook/templates` is
   `SERVER_ONLY`, so the fetch throws offline and both call sites swallow it.
   The third frame of `codebook-v2-external-links.html` is therefore drawn for a
   case that does not yet exist. **But v2 creates it:** the links live in the
   browse *preview* today, and v2 puts the bio on the **codebook page**, which
   does ship offline. **v2 moves `author_links` into an exported file for the
   first time** — a new exposure created by a layout decision, which is exactly
   the kind of consequence a layout decision does not announce.
2. **The unmitigated vector is presentational, not schematic.** A well-formed
   `https` URL whose *label* names a different host — `nngroup.com` pointing at
   somewhere else — passes every allowlist there is. No scheme check touches it.
   The fix is to render the host rather than trust the label, and it is **open**:
   the shipped labels are editorial (*"Original 1994 CHI paper (DOI)"*), so
   replacing them with bare hosts costs something real. Worth drawing before
   deciding.

### D31 — the catalogue's title is one `SectionHeading` switched on content, not a second one

Recorded 31 Aug 2026, from a parallel session's durable-artefact audit. It was
deferred there rather than written, because this doc was being edited at the
time — the decision lived only in a commit body, which is exactly the burial the
audit exists to catch.

The catalogue view needs a different title from the codebook page, and the
obvious shape is a second `SectionHeading` rendered in the browse branch. That
is wrong here, and the reason is the shared datum rather than taste.

`report.css` flushes the first zone title to the content datum with

    .center > main > section:first-of-type > .section-heading

so the rule reaches the heading of the **first** `<section>` in `<main>`, and
only that one. Two `SectionHeading`s in two branches means the browse view's
title is a *different element* from the page view's — and whether it is enrolled
in the datum then depends on which branch rendered, which is a geometry bug that
only appears on one of two routes and looks like a rendering glitch rather than
a selector miss. One heading whose *text* switches on `view` keeps a single
element in a single position, so the datum rule matches unconditionally.

The general form is worth keeping: **when a lens has two views, vary the
content of one heading rather than rendering one heading per view.** The
page-geometry rules in `design-lens-template.md` are positional, and a
conditionally-rendered element cannot satisfy a positional rule reliably.

Related: the same lens's Library is `?view=library` URL state rather than
component state, which is what makes "two views, one route" coherent in the
first place — see the Back-button note in `design-codebook-v2-plan.md`.
