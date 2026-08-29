---
status: draft
last-trued: 2026-08-29
trued-against: HEAD@main 3802f2af on 2026-08-29
---

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

Options, none chosen: treat sentiment as floor-like (permanent, enable-only,
off the browse page); keep it a framework and accept the odd install; or drop it
from the codebook surface entirely and make sentiment a report-wide display
setting. **Needs a call**, and A4 should be fixed either way.

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

### What is genuinely still open

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

One note so it is not a surprise later: because the scope is presentation, the
expensive half of a migration — schema, stored state, the `ProjectFrameworkState`
and `hidden_tag_groups` rows — should not move at all. What will need thought is
anything that changes a *route* people have learned, and the export, which bakes
a per-project CSS copy and so lags a theme change by one render.
