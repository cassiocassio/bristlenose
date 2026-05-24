---
status: exploration
last-trued: 2026-05-23
trued-against: not yet implemented — research + options capture only
---

# Status bar (optional bottom strip)

> **Status: exploration.** Nothing shipped. This doc captures the idea, the
> macOS convention research behind it, the full inventory of Bristlenose
> surfaces that *could* live in a bottom strip, and a tiered shortlist with
> trade-offs — enough to resume cold and make a call. No design is chosen
> yet. The one decision that gates everything else (always-on vs conditional)
> is called out in §6.

## The idea

Move the pipeline status pill out of the window **toolbar** and into an
**optionally-visible status bar at the bottom of the window**. Rationale from
the owner: *"less at the top eye level."* The bottom strip could also carry
secondary chrome (zoom level, view state) that doesn't earn a toolbar slot.

The pill currently lives at `ToolbarItem(placement: .status)` in
`desktop/Bristlenose/Bristlenose/ContentView.swift` (`PipelineActivityItem`),
competing with Export, Tags, Heatmap, Search, Back/Forward, and the tab picker
for the top strip.

## Context research — macOS conventions

> **Method caveat.** The local Apple HIG mirror (scraped via
> `scripts/scrape-apple-corpus.py`, from the `hig-corpus` merge) was **not
> reachable** in the cloud session this was researched from, and
> `developer.apple.com` / `daringfireball.net` returned 403/empty to WebFetch.
> Citations below are from web-search result summaries, not verbatim HIG
> quotes. **Before committing to a design, re-run a HIG-corpus pass from the
> Mac** for chapter-and-verse, and inspect the named apps' actual pixels.

### What Apple says

- The HIG **Toolbars** page frames toolbar items as commands / controls /
  navigation. **"Status" is not a named first-class toolbar citizen.** The
  trailing toolbar end is "preferred for important items that need to be
  visible at all window sizes."
- There is **no HIG page prescribing where in-window status belongs.**
  `NSStatusBar` is the *system menu bar*, not an in-window strip.
- The framework anticipates a bottom strip without editorialising:
  `NSTitlebarAccessoryViewController` lays out views "at the bottom of the
  title bar or toolbar"; SwiftUI has `ToolbarItemPlacement.bottomBar`.
- **Net: the question is settled by idiom, not policy.** Apple ships optional
  bottom status bars in its own file/web/dev apps — that's the strongest
  implicit signal.

### First-party apps split by app type

| App | Bottom strip | Carries | Optional |
|---|---|---|---|
| Finder | Yes (Status + Path, two strips) | item count + free disk; breadcrumb | both opt-in (View menu) |
| Safari | Yes | URL preview on hover | off by default (⌘/) |
| Xcode | Yes (debug bar) | breakpoint/step controls, view debugging | toggles with debug area |
| Preview (macOS 26) | Yes | page indicator + view-mode buttons + zoom | always-on |
| Pages / Numbers / Keynote | No (zoom in toolbar pop-up) | — | — |
| Mail / Notes / Music / Photos | No (counts in sidebar/title) | — | — |

Pattern: **document apps keep status in the toolbar; file/web/dev/media apps
use a bottom strip, often opt-in.**

### Indie apps (the DF / Sweet Setup / ATP audience)

- **Persistent bottom strip is the default** for editor/dev/file-transfer
  apps: Tower (remote activity + progress + abort), Nova (lines, language,
  indentation), Transmit (opt-in Activity Bar: speed, queue, connection),
  Sublime/VS Code/Zed (line:col, language, encoding, line-endings, git branch
  + ahead/behind, problems count).
- **Writing apps split:** iA Writer commits to a bottom toolbar (word/char/
  sentence count, click-to-cycle); Ulysses puts the counter top-right of the
  editor instead; Bear/Drafts use a corner count.
- **Strongest counter-argument to "make it hideable":** Zed's docs say hiding
  the bottom bar "causes major usability problems but is provided for those
  who value screen real-estate." Bottom status reads as load-bearing.

### Zoom level placement (owner asked specifically)

Two coexisting Apple conventions: **toolbar pop-up** (iWork) and
**bottom-right corner** (Preview-26, Pixelmator Pro). Apple has shipped both;
bottom-right zoom is mainstream when it co-locates with other view-state
controls. Caveat: research-analysis is not a zoom-heavy workflow, so a
permanent zoom slot may sit unused.

### Recent commentary (2025–2026)

- macOS Tahoe / Liquid Glass (WWDC 2025) concentrated visual weight at the
  **top** of windows (translucent menu bar, redesigned toolbars).
- Gruber (Daring Fireball, 22 Jan 2026) called the new Finder toolbar a
  *"free-floating monstrosity."* The post-Tahoe critique is about top-strip
  **density** — circumstantial support for moving secondary chrome down, but
  **no commentator explicitly prescribes the bottom** as the destination.

## Bristlenose inventory — everything that could go in the bar

Grouped; not all are good ideas (see shortlist). Sourced from
`ContentView.swift` toolbar + `frontend/src/components/`.

**Currently in toolbar:** sidebar toggle · back/forward · tab picker
(Contents/Codes/Signals) · Export menu · Tags toggle · Heatmap toggle ·
Search · **pipeline pill** · Settings.

**Titlebar (redesign pending):** app icon · project name · subtitle
("3 sessions · April 2026").

**Pipeline / sidecar status:** activity state (idle / in-flight / completed /
completedPartial / failed / failedWithDiagnostic) · stage progress
("Step 4 of 12 · extract quotes") · stage ETA · current LLM latency · sidecar
health · last-analysed time · project availability (ready / cantFind:moved /
:unmountedVolume / :network / cloudEvicted) · folder-watcher new-file pulse ·
provider chip ("Claude · sonnet-4") · Whisper backend.

**Project / corpus info:** quote / session / participant / tag / theme /
signal counts · output-dir breadcrumb · free disk on volume · cost estimate ·
token usage.

**View state (SPA):** zoom · density · theme · view switcher · filtered count
("Showing 5 of 42") · active filter chips · active search query · selected
count · hidden-quote count · codebook/autocode threshold.

**In-flight actions:** Cancel run · Show Log · open diagnostic popover · reveal
output in Finder · Refetch/Refresh · switch project · (speculative) pause/
resume · open telemetry.

**Conditional / transient:** cohort/TestFlight notice banner · update-available
· connection-lost / sidecar-down · last-action toast echo · background
re-analysis progress (post-cohort incremental).

## Shortlist with pros & cons

Ranked by the owner's stated priorities: **concise info + quick in-flight
actions, low real-estate cost.**

### Tier 1 — strongest fit

**1. Pipeline activity pill + stage progress**
- Pro: canonical precedent (Tower, Transmit, Xcode); removes top distraction;
  click-to-expand popover already wired.
- Con: **failure visibility risk** if the bar is opt-in-hidden — the
  no-surprises cohort gate means a buried `.failed` state is a fake-success
  regression. Mitigation: auto-show on non-idle state (OmniFocus notice-bar
  pattern).

**2. Cancel + Show Log**
- Pro: pairs with the activity row (Tower's abort sits beside activity); Show
  Log is already verb-first `.bordered .small` chrome.
- Con: both *just* landed inside the unified failure popover (`unify-failure-
  popover`, 20 May). Promoting them back to a strip reverses that unless the
  bar *is* the popover anchor. If the bar is hidden they're unreachable —
  can't be the only path.

**3. Project availability (when non-ready)**
- Pro: window-level surface for cantFind/cloudEvicted when the sidebar is
  collapsed.
- Con: sidebar row already shows it; only justified if sidebar can hide.

### Tier 2 — defensible, each loses to a competing surface

| Candidate | Pro | Con |
|---|---|---|
| Last-analysed time | always-on confirmation; cohort-call moment | titlebar subtitle redesign is taking this slot — pick one |
| Output-path breadcrumb | Finder Path Bar precedent; click-to-reveal one-liner | project name already in titlebar; long strings truncate |
| Zoom level | owner-raised; Preview-26 precedent | low-frequency action here; slot sits unused |
| Density mode | pairs with zoom | one toggle — belongs in View menu |
| Provider chip | reinforces "known to work with Claude, try anything else" | rarely changes; becomes wallpaper |
| Free disk | Finder precedent; big media drops | not Bristlenose-specific; reads as mimicry |

### Tier 3 — keep out

Primary commands and navigation: view switcher, Search, Export, Tags/Heatmap
toggles, tab picker, Settings → HIG keeps these in the toolbar (trailing /
principal). Inline-already counts (filtered count, tag chips, selected count)
→ second surface = noise. Notice banners → deserve their own *conditional*
sub-strip, not the persistent status bar. Token/cost telemetry → debug pane,
not cohort chrome.

## The gating decision

**Is the bar always-on or conditional?** Everything else falls out of this.

- **Conditional (OmniFocus notice-bar pattern):** appears only when there's
  something to say (in-flight, partial, failed, cantFind). Preserves the
  no-surprises rule for free; idle windows stay clean. Best fit for the
  failure-visibility risk in Tier 1.
- **Always-on, opt-in (Finder Status Bar pattern):** user toggles via View
  menu; blank/minimal when idle. Risks burying failures if the user hides it.
  Zed's "hiding causes usability problems" warning applies.
- **Hybrid:** always-on but auto-expands/tints on non-idle state (Xcode debug
  bar appears only while running; VS Code tints the whole bar on git conflict).

Recommendation to *evaluate first*, not a decision: the **conditional /
hybrid** path squares the no-surprises gate with the "less at the top" goal.
Pick the policy, then the inventory shortlist resolves.

## The coherent unit that falls out

The cleanest "moves to bottom together" cluster is **Tier 1 as one unit** —
activity pill + stage progress + Cancel + Show Log + (conditional)
availability state: *what's running, how to interrupt it, what to do when it
breaks.* Tier 2 items are each defensible alone but each loses to a competing
surface. Tier 3 is the trap (the VS-Code-density failure mode — primary
controls migrating downward).

## Open questions / next steps

1. **Re-run the HIG research from the Mac** against the local corpus for
   verbatim citations; inspect Tower / Nova / Preview-26 / iA Writer pixels.
2. **Decide the visibility policy** (§6) — this gates the rest.
3. **Map pill states → bar behaviour:** what shows when, what disappears when,
   what auto-expands. Start from the `PipelineActivityState` /
   `ProjectAvailability` enums.
4. **Resolve the Show Log / Cancel ownership** with `unify-failure-popover` —
   bar vs popover, not both.
5. **Decide titlebar vs status-bar** for last-analysed + project name (they
   collide; the titlebar redesign claims both).
6. Mock options (HTML in `docs/mockups/`) before any Swift.

## References

- Code: `desktop/Bristlenose/Bristlenose/ContentView.swift` (toolbar),
  `PipelineActivityItem.swift`, `PipelineSummary.swift`,
  `ProjectAvailability.swift`, `ProjectRow.swift`.
- SPA chrome: `frontend/src/components/` — `NavBar`, `ViewSwitcher`,
  `SearchBox`, `TagFilterDropdown`, `Footer`, `MicroBar`, `RefreshButton`.
- Related docs: `docs/design-pipeline-diagnostic-popover.md` (pill states,
  MessageKind taxonomy, failure popover — **the sibling surface**),
  `docs/design-badge-action-pill.md` (pill UI idiom),
  `docs/design-responsive-layout.md` (density), `docs/design-dashboard-
  navigation.md`, the titlebar-redesign entry in the launch plan.
