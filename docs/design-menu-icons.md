---
status: partial
last-trued: 2026-07-28
trued-against: HEAD@main on 2026-07-28
---

# Menu icons — audit & dial-back exploration

## Changelog

- _2026-07-28_ — created, then corrected the same day. The first draft **invented
  lens glyphs that contradicted `LensItem.all`**, which declares itself the single
  source of the lens→Tab→icon mapping. Rows corrected to the settled set; a
  "Reuse before you propose" section added naming the two shipped vocabularies
  (`LensItem.all`, the export popover) that outrank any proposal here. Status
  rewritten — Tier 1 + 2 are implemented, not exploration.

Companion to [fix-the-menus.md](fix-the-menus.md). Where that doc tracks *wiring*
gaps, this one explores *iconography* for the native menu bar
(`desktop/Bristlenose/Bristlenose/MenuCommands.swift`).

## The design context

macOS 26 (Tahoe) pushed icons into menu items aggressively — nearly every
command got a leading SF Symbol. macOS 27 dialled that back as a recognised
over-correction: a glyph on *every* line produces a ransom-note wall, and
abstract commands ("Use Selection for Find", "Toggle Selection") have no honest
glyph, so forcing one adds noise without aiding recognition.

Bristlenose today sits at the **opposite** extreme: **zero** menu icons (every
item is a bare `Button(text)`). That's clean but leaves two real benefits on the
table:

1. **Toolbar↔menu association.** When a command's menu icon matches its toolbar
   button (Export = share glyph, Find = magnifier), the icon reinforces muscle
   memory across both surfaces.
2. **Scan-ability for high-frequency, visually-distinct commands** — Star,
   Trash, Print, Play read faster with their canonical glyph.

The goal here is the **middle ground**: iconify where a glyph earns its keep,
stay bare where it doesn't. Not "all or nothing."

### Principles for "earns its keep"

An item should carry an icon only if it clears **all** of:

- **Unambiguous, Apple-precedented glyph** — the symbol Apple itself uses for
  this action (or its obvious sibling). If we'd be inventing the association,
  skip it.
- **Recognition, not decoration** — the icon speeds scanning or signals
  category/consequence (destructive = trash). If it's just "a picture of the
  words", skip it.
- **No abstract-command forcing** — navigation/selection/meta commands
  (Use Selection for Find, Jump to Selection, Actual Size, Toggle Selection)
  stay bare; their glyphs would be arbitrary.
- **Toggles let the checkmark work** — a menu Toggle already shows a leading
  checkmark for "on". Don't stack a second leading glyph (Apple's own pattern).
  Exception: where the glyph *is* the meaning (Starred → `star`).

## Tiers

Four named points on the spectrum, so we can choose a scheme rather than argue
item-by-item:

- **Tier 0 — Sparse (today):** no icons. Baseline.
- **Tier 1 — Anchored (recommended middle):** icons *only* on commands with a
  strong Apple-precedented glyph that also mirror a toolbar/affordance the user
  already associates with it. ~18 items. Zero ransom-note, all upside.
- **Tier 2 — Structured:** Tier 1 **+** the lens tabs (match the toolbar
  segmented control) **+** the Video transport cluster (reads like a remote)
  **+** Codes CRUD. Abstract/navigation commands still bare.
- **Tier 3 — Tahoe-max (the ceiling to avoid):** a glyph on nearly everything,
  including Find Next, Use Selection for Find, Toggle Selection, Actual Size.
  Documented as the over-reach, not a ship candidate.

The column **"First tier"** in the audit below = the lowest tier at which the
item gets an icon.

---

## Full audit

> All SF Symbol names are **candidates — verify in SF Symbols.app and confirm
> availability ≥ macOS 15** (our deployment target) before use. `(alt)` = a
> second plausible match. "—" in the symbol column = leave bare at every tier.

### Bristlenose (app menu)

| Item | Candidate SF Symbol | Apple precedent / note | First tier |
|---|---|---|---|
| About Bristlenose | — | Apple's own About item is iconless | never |
| AI & Privacy | `hand.raised` (alt `lock.shield`) | Privacy panes use `hand.raised` | 2 |

### File

| Item | Candidate SF Symbol | Apple precedent / note | First tier |
|---|---|---|---|
| New Project (⌘N) | `plus` (alt `doc.badge.plus`) | Finder New Folder trend | 2 |
| New Folder (⇧⌘N) | `folder.badge.plus` | Finder | 2 |
| Add Files… (⇧⌘A) | `plus.rectangle.on.folder` (alt `doc.badge.plus`) | Mail Attach | 2 |
| Open in New Window (⇧⌘O) | `macwindow.badge.plus` | — | 2 |
| Export Report… (⇧⌘E) | `square.and.arrow.up` | Share/Export everywhere; **matches toolbar** | **1** |
| Export Anonymised… | `square.and.arrow.up` + note | same family as Export; distinguish by label not glyph | 2 |
| Page Setup… | — | Apple leaves iconless | never |
| Print… (⌘P) | `printer` | universal | **1** |

### Edit

| Item | Candidate SF Symbol | Apple precedent / note | First tier |
|---|---|---|---|
| Undo (⌘Z) | `arrow.uturn.backward` | universal | **1** |
| Redo (⇧⌘Z) | `arrow.uturn.forward` | universal | **1** |
| Find (⌘F) | `magnifyingglass` | **matches Search toolbar item** | **1** |
| Find Next (⌘G) | — (alt `chevron.down`) | Apple leaves bare | 3 |
| Find Previous (⇧⌘G) | — (alt `chevron.up`) | Apple leaves bare | 3 |
| Use Selection for Find (⌘E) | — | abstract; no honest glyph | never |
| Jump to Selection (⌘J) | — (alt `scope`) | abstract | 3 |

### View

| Item | Candidate SF Symbol | Apple precedent / note | First tier |
|---|---|---|---|
| Project tab (⌘1) | `target` | **from `LensItem.all` — the settled set** | 2 |
| Sessions tab (⌘2) | `person.2` | from `LensItem.all` | 2 |
| Quotes tab (⌘3) | `text.quote` | from `LensItem.all` | 2 |
| Codebook tab (⌘4) | `tag` | from `LensItem.all` | 2 |
| Analysis tab (⌘5) | `square.grid.3x3` | from `LensItem.all` | 2 |
| Move Focus to Projects (⌘0) | — | abstract focus move | never |
| Hide/Show Projects (⌥⌘S) | `sidebar.left` | Finder/Mail sidebar toggle | 2 |
| Show Contents/Sessions/… (⌥⌘L) | `list.bullet` | **matches the toolbar's own left-panel button** | 2 |
| Show Tags (⌥⌘T) | `sidebar.right` (alt `tag`) | right panel toggle | 2 |
| Show Heatmap | `square.grid.2x2` | **matches Analysis toolbar item** | 2 |
| ✓ All Quotes (toggle) | — | let the checkmark work | never |
| ✓ Starred Quotes Only (toggle) | `star` | glyph *is* the meaning | **1** |
| Zoom In (⌘=) | `plus.magnifyingglass` | universal | 2 |
| Zoom Out (⌘-) | `minus.magnifyingglass` | universal | 2 |
| Actual Size | — (alt `1.magnifyingglass`) | abstract | 3 |
| Switch to Light/Dark Mode | `sun.max` / `moon` (dynamic) | Control Center | 2 |

### Project

Folder-selected variant:

| Item | Candidate SF Symbol | Note | First tier |
|---|---|---|---|
| Rename | `pencil` | universal edit | 2 |
| Archive (disabled) | `archivebox` | Mail | 2 |
| Delete (⌘⌫, destructive) | `trash` | **consequence signal** | **1** |

Project variant:

| Item | Candidate SF Symbol | Note | First tier |
|---|---|---|---|
| Show in Finder (⇧⌘R) | `folder` (alt `arrow.up.forward.app`) | reveal-in-Finder idiom | **1** |
| Locate | `location.magnifyingglass` (alt `magnifyingglass`) | find-missing | 2 |
| Rename | `pencil` | universal | 2 |
| Move to ▸ | `folder` (alt `arrow.right`) | move-to-folder | 2 |
| Stop Analysis (⌘.) | `stop.circle` (alt `xmark.circle`) | transport stop | 2 |
| Re-analyse (disabled) | `arrow.clockwise` | refresh idiom | 2 |
| Archive (disabled) | `archivebox` | Mail | 2 |
| Remove from Sidebar (⌘⌫) | `minus.circle` | **remove ≠ delete** — not `trash` | **1** |

### Codes

| Item | Candidate SF Symbol | Note | First tier |
|---|---|---|---|
| Create Code Group | `folder.badge.plus` (alt `plus.rectangle.on.folder`) | new-container | 2 |
| Rename Code Group | `pencil` | — | 2 |
| Delete Code Group | `trash` | destructive | 2 |
| Show/Hide Code Group | `eye` / `eye.slash` | visibility | 2 |
| Create Code | `tag` (alt `plus`) | new-code | 2 |
| Rename Code | `pencil` | — | 2 |
| Delete Code | `trash` | destructive | 2 |
| Merge Codes | `arrow.triangle.merge` | merge idiom | 2 |
| Browse Codebooks | `books.vertical` (alt `list.bullet.rectangle`) | library | 2 |
| Import Framework | `square.and.arrow.down` | import | 2 |
| Remove Framework | `minus.circle` (alt `trash`) | remove | 2 |

### Quotes

| Item | Candidate SF Symbol | Note | First tier |
|---|---|---|---|
| Star / Unstar (dynamic) | `star.fill` / `star` | **the glyph previews the result**, not its negation — `star.slash` reads as "starring is disabled" | **1** |
| Hide | `eye.slash` | **matches quote-card hide** | **1** |
| Add Tag | `tag` | **matches tag affordance** | **1** |
| Apply "name" / Apply Last Tag | `tag.fill` (alt `tag`) | repeat-tag; fill = "again" | 2 |
| Reveal in Transcript | `doc.text.magnifyingglass` (alt `text.magnifyingglass`) | reveal-in-source | 2 |
| Play/Pause | `play` / `pause` (dynamic) | transport | 2 |
| Next Quote | — (alt `chevron.down`) | navigation | 3 |
| Previous Quote | — (alt `chevron.up`) | navigation | 3 |
| Extend Selection Down/Up | — | abstract selection | never |
| Toggle Selection | — | abstract selection | never |
| Clear Selection | `xmark.circle` | clear idiom | 3 |
| Copy Quotes ▸ | `doc.on.clipboard` | **matches the shipped export popover** | 2 |
| Save as Spreadsheet ▸ | `tablecells` (alt `square.and.arrow.down`) | spreadsheet | 2 |
| Extract Clips | `film` | **matches the shipped export popover** (code currently ships `scissors` — mismatch, see Status) | 2 |
| Send to Miro | — | **stays bare, stays in the Quotes menu.** Miro exports *quotes*; the File menu carries the whole-report export. The popover's `square.grid.2x2` is deliberately **not** adopted here — it already means Show Heatmap, and one glyph for two commands in one menu bar is worse than a bare row. |
| Copy as CSV | `doc.on.doc` (alt `tablecells`) | copy idiom | 2 |

### Video (the coherent transport cluster)

| Item | Candidate SF Symbol | Note | First tier |
|---|---|---|---|
| Play/Pause (dynamic) | `play` / `pause` | transport | **2** |
| Skip Forward 5 | `goforward.5` | native skip glyph | 2 |
| Skip Back 5 | `gobackward.5` | native skip glyph | 2 |
| Skip Forward 30 | `goforward.30` | native skip glyph | 2 |
| Skip Back 30 | `gobackward.30` | native skip glyph | 2 |
| Speed Up | `forward` | — | 2 |
| Slow Down | `backward` | — | 2 |
| Normal Speed | `gauge.medium` (alt `1.circle`) | reset-rate | 2 |
| Volume Up | `speaker.wave.3` | — | 2 |
| Volume Down | `speaker.wave.1` | — | 2 |
| Mute | `speaker.slash` | — | 2 |
| Picture in Picture | `pip.enter` (alt `pip`) | native PiP glyph | 2 |
| Fullscreen | `arrow.up.left.and.arrow.down.right` | native fullscreen | 2 |

### Window

| Item | Candidate SF Symbol | Note | First tier |
|---|---|---|---|
| Bristlenose (reopen main) | — | brand/reopen; Apple leaves bare | never |

### Help

| Item | Candidate SF Symbol | Note | First tier |
|---|---|---|---|
| Bristlenose Help (⌘?) | `questionmark.circle` | universal help | 2 |
| Welcome to Bristlenose | `house` (alt `hand.wave`) | home | 3 |
| Keyboard Shortcuts | `keyboard` | — | 3 |
| Release Notes | `sparkles` (alt `doc.text`) | what's-new | 3 |
| Send Feedback | `envelope` (alt `bubble.left`) | feedback | 3 |
| Blog | `safari` (alt `text.book.closed`) | external link | 3 |
| Acknowledgements | `heart` (alt `person.2`) | thanks | 3 |

### Diagnostics (tester-facing; English-only)

| Item | Candidate SF Symbol | Note | First tier |
|---|---|---|---|
| Check Health | `stethoscope` (alt `heart.text.square`, `waveform.path.ecg`) | doctor — a genuinely nice glyph here | 2 |
| Reveal .bristlenose/ in Finder | `folder` | reveal | 2 |
| Open Log in Console | `terminal` (alt `doc.text.below.ecg`) | log/console | 2 |
| Copy Build Provenance | `doc.on.doc` (alt `info.circle`) | copy | 2 |
| Shoal Screensaver | `fish` (alt `sparkles`) | playful | 2 |

---

## The few interesting possibilities

Beyond "pick a tier", four ideas stand out as *design wins* worth prototyping:

1. **Lens↔toolbar unity (Tier 2's best idea).** The five View-menu tabs already
   have visual identities in the toolbar segmented control. Giving the menu items
   the *same* five glyphs makes the segmented control legible as a legend and the
   menu legible as its expansion — the two surfaces teach each other. This is the
   single most defensible fuller-than-Tier-1 move.

2. **Video menu as a remote control.** Transport commands (play/skip/speed/
   volume/PiP/fullscreen) are the one cluster where a *fully* iconified menu reads
   *better*, not worse — it looks like a remote, because that vocabulary is
   universally iconic (`goforward.30` et al. are purpose-built). Consider
   iconifying Video **as a block** even under an otherwise-Anchored scheme.

3. **Consequence as a consistent glyph convention.** Reserve `trash` for
   irreversible deletes and `minus.circle` for reversible removes (Remove from
   Sidebar, Remove Framework), applied *consistently* across menus. The glyph
   then carries a safety signal, not just a label — a Mac-native "this bites"
   cue. This is worth doing even in a minimal scheme.

4. **Restraint as a feature: the toggle checkmark.** Explicitly *not* iconifying
   the "All Quotes / Starred Only" and panel toggles (beyond Starred's `star`)
   keeps the menu honest — the checkmark is the state, and a second glyph would
   compete. Documenting this restraint stops a future "iconify everything" drift.

### Recommendation

Ship **Tier 1 (Anchored)** as the baseline — it's pure upside (toolbar
association + consequence signalling, ~18 items, no noise) — and prototype the
two *cluster* ideas (**lens tabs**, **video-as-remote**) as opt-in Tier-2
additions to see them in situ. Hold Tier 3 as the documented ceiling.

The Tier-1 set (the ~18): Export Report, Print, Undo, Redo, Find, Starred Only,
Star/Unstar, Hide, Add Tag, Delete (project + folder), Show in Finder, Remove
from Sidebar — plus the two consequence-convention removes.

## Implementation notes (for the later build pass)

- **`Label`, not `Button(text)`.** A menu icon is
  `Button { … } label: { Label(i18n.t(key), systemImage: "name") }`. SwiftUI
  renders the leading symbol in the menu bar on macOS. This is a per-item edit,
  no new infrastructure.
- **Dynamic-glyph items** (Star/Unstar, Play/Pause, Light/Dark) swap
  `systemImage` off the same `bridgeHandler` state that already swaps their
  label.
- **Don't add `systemImage` to a `Toggle`** — the checkmark is the affordance
  (see possibility 4).
- **Verify every name + min-OS ≥ 15** in SF Symbols.app before wiring. Several
  candidates above (`arrow.triangle.merge`, `location.magnifyingglass`,
  `pip.enter`, `gauge.medium`) are the highest-risk for availability/naming.
- **i18n:** icons don't touch locale keys — labels stay translated, glyph is
  language-neutral. Diagnostics stays English-only literals regardless.
- **Reuse the `MessageKind` glyph discipline where relevant** — the project
  already forbids minting new *status* glyphs
  ([MessageKind.swift](desktop/Bristlenose/Bristlenose/MessageKind.swift)); menu
  *command* icons are a separate vocabulary but the same "don't invent
  associations" instinct applies.

## Reuse before you propose (added 28 Jul 2026)

The first draft of this doc invented lens glyphs (`doc.text`, `waveform`,
`chart.bar`) that contradicted **`LensItem.all`, which declares itself "the single
source of the lens→Tab→icon mapping"** with a settled set. Two shipped vocabularies
already exist and outrank any proposal here:

1. **`LensItem.all`** (`desktop/…/LensItem.swift`) — the five lens glyphs. The View
   menu now reads them via `LensItem.systemImage(for:)`, so the menu, the sidebar
   rail and the toolbar cannot drift.
2. **The export popover** (`ExportMenuButton`, `ContentView.swift`) — `square.and.arrow.up`,
   `doc.on.clipboard`, `tablecells`, `film`, `folder`, `square.grid.2x2`. It shipped
   first; the menu bar should follow it, not the reverse.

Check both before proposing a glyph.

## Status

**Tier 1 + Tier 2 implemented 28 Jul 2026** (~65 icons across `MenuCommands.swift`).
Deviations from the tables above, all deliberate:

- **Diagnostics takes no icons** — tester-facing, stays plain text.
- **View ▸ dark-mode toggle removed entirely** — appearance is owned by
  Settings ▸ Appearance; a second control that toggled only the *web* theme could
  desync from it. Locale keys `desktop.menu.view.switchTo{Light,Dark}Mode` are now
  orphaned in all 20 locales (cleanup pending).
- **Codes ▸ Merge Codes withdrawn** (commented out) — needs codebook multi-select.

Open, from the 28 Jul popover-vs-menu audit:

- Menu ships `scissors` for Extract Clips; popover ships `film`. **Align to `film`.**
- Menu ships `doc.on.doc` for Copy Quotes; popover ships `doc.on.clipboard`. **Align.**
- ~~Send to Miro / Show Heatmap glyph collision~~ — **resolved 28 Jul 2026** by not
  adopting the popover's glyph: Miro stays bare in the Quotes menu, `square.grid.2x2`
  keeps meaning Show Heatmap. A deliberate, documented departure from
  "follow the popover" — the popover and the menu bar don't share a glyph namespace,
  so the same symbol in both is fine; the same symbol twice *within the menu bar*
  is not.
- **File ▸ Export Anonymised… removed** (28 Jul) — anonymise is a checkbox on the
  export save panel. File's export group is now Export Report… alone.
- Repetition to watch when thinning: `pencil` ×4, `trash` ×3, then ×2 each for
  `folder`, `tag`, `doc.on.doc`, `minus.circle`, `archivebox`, `folder.badge.plus`,
  `square.and.arrow.up`.

Tracked alongside the rest of the menu work in [fix-the-menus.md](fix-the-menus.md).
