---
status: partial
updated: 16 Oct 2026
---

# Icon system: Lucide on the web, SF Symbols on the Mac

**Status: phases 1–3 shipped on `main` overnight 15–16 Oct 2026** (a8333739, 5696bb52, 450e3cee;
unreleased). Every chrome icon the SPA drew for itself, as an SVG or a character, now
goes through `components/Icon.tsx` and Lucide, with a stroke taken from the text's stem,
and `tests/test_no_improvised_icons.py` holds it there. What is deferred, and why, is
§ What's left. The review artefacts: `docs/mockups/icon-system-side-by-side.html` (built
by `experiments/icon-system/build_mockup.py`, which lifts icons from source) and a local,
gitignored before/now catalogue of every icon in the running app
(`experiments/icon-system/capture_icons.mjs`, `build_catalogue.py`).

## The decision, and where it came from

Two sets, one per rendering technology:

- **Anything a browser engine draws uses Lucide** ([lucide.dev](https://lucide.dev), ISC).
  That covers the SPA in a browser, the SPA inside the Mac app's WKWebView, the HTML
  export, the website and docs, and the HTML welcome illustrations in the Mac app.
- **Anything AppKit or SwiftUI draws uses SF Symbols.** That covers the sidebar,
  toolbar, menus, Settings, sheets and popovers.

Nothing is improvised. A glyph Lucide lacks is a decision recorded here, not a
fresh SVG in a component.

This was already decided and not done:

| When | What | Where |
|---|---|---|
| 9 Jul 2026 | Lucide over Phosphor for the web interior, so the docs and the app share one set. Keep the Unicode ★ for the star; accept Lucide's search magnifier. | `docs/design-docs-system.md` §A3; project memory |
| 15 Jul 2026 | "No freelancing": new icons come from Lucide. A mark in running text is a typographic glyph and stays one; only chrome becomes an icon. | `docs/design-dashboard-widgets/design-police.md` § Icon policy |
| 20 Sep 2026 | Phase 3 of the lens campaign: install `lucide-react`, build an `Icon` atom, migrate. | `docs/design-lens-system-audit.md` § Phase 3 |
| 6 Oct 2026 | `frontend/src/components/Icon.tsx` was started as a registry of **improvised** paths (16-unit grid, stroke 1.4, `check` and `x`). It contradicts the decision, but its *shape* is right: one component, one place. | `ebcd2cbc` |

`lucide-react` was never installed. The website went the other way: its 27 icons
in `assets/site.js` are Lucide's exact paths, so it is the reference.

Reviewed 15 Oct 2026 for scope, bundle cost and Mac taste; their findings are folded
in below. This doc supersedes the migration plan in `docs/design-system/icon-catalog.html`
(Feb 2026, written against the removed `render_html.py`), `design-theme-divergence.md`
Phase C's `icons/desktop.ts` ("SF Symbols-weight SVGs", which is replaced by the
stem rule, below), and folds in `design-lens-system-audit.md` Phase 3.

## Who gets which fonts and icons

| Surface | Text | Icons | Shipped how | Licence |
|---|---|---|---|---|
| Browser, any OS | Inter 400–700 | Lucide | Inter from Google Fonts (`frontend/index.html:39`); Lucide in the JS bundle | Inter OFL; Lucide ISC — both redistributable |
| Mac app, web interior | SF Pro (`tokens-desktop.css`) | Lucide | SF Pro is on every Mac | SF Pro: Apple platforms |
| Mac app, native chrome | SF Pro | SF Symbols | Ship with macOS | Apple platforms only, never redistributed |
| HTML export | Inter when online, else system font | Lucide, inlined | One file | as browser |
| Website + docs | site fonts | Lucide (27, `site.js`) | Inlined | ISC |

Consequences. **SF Symbols can never appear in anything a browser engine draws**, even
on a Mac, so the web needs its own set. **Lucide meets two typefaces**, Inter in a
browser and SF Pro in the app. Their stems turn out to be the same (§ Weight), so one
rule serves both. **The only thing we redistribute is Lucide**, whose ISC notice
`lucide-react` carries in the bundle.

## Where we are (audit, 15 Oct 2026)

Counted from the tree, not carried over from July.

**What "improvised" means.** No designer drew these and no library file supplied them:
the path coordinates were written into each component by a model during a session
(every one checked arrived in a Claude co-authored commit). Some are *recalled*: the
eye-off is Feather's path verbatim and the moon an older Lucide's, both unattributed
(MIT / ISC). The rest were composed on the spot, each session choosing its own grid and
stroke, with nothing telling it what the last session had chosen. That is the cause of
the spread below.

**SPA (`frontend/src`).** 37 `<svg` in 22 non-test files: 2 in `Icon.tsx` and 35 sites
elsewhere, of which **29 are chrome icons** and 6 charts or diagrams (signal intensity
dots in `SignalsPage` and `Metric`, transcription diagnostic lanes, session tapestry,
Screens leader lines, Discussion wires). The 29 use **8 viewBox grids** (8, 10, 12, 14,
14×12, 16, 18, 24) and **6 stroke widths** (1.3–2). `x` is drawn 4 times, chevrons 6,
`eye-off` 3. Six take their stroke from CSS in `bristlenose/theme/`. Only three
components use `Icon.tsx`. A further **52 Unicode characters do an icon's job** in
26 files (9 of them dev-only): × ✕ ✗ for close/deny, ▸ ▾ ▶ ▼ ▴ ⌃ for disclosure and
carets, ✓ for accept/done, ↩ for revert, ✎ for edit, ✦ as a title ornament, ⊘ for deny.

**Theme CSS shared with the SPA.** 4 live `content:` glyphs (`badge.css:54` ×,
`settings.css:189` ✓, `coverage.css:165/171` ▶/▼ on the Dashboard) and 13 selectors
that size glyphs the SPA emits (`.bn-play-icon`, `.bn-hidden-chevron`, `.modal-nav-arrow`,
`.expand-arrow`, `.menu-icon`, …). Every item of July's known debt is still there.

**Frozen static renderer** (`theme/templates`, `theme/js`, `s12_render`). 13 improvised
SVGs and 27 Unicode chrome glyphs. Out of scope: vanilla JS is frozen to data-integrity
fixes (`CLAUDE.md` § Key conventions).

**Mac app.** No improvised native glyphs: every native icon is an SF Symbol: about 240
distinct names, 100 of them the project-icon palette. All exist and none needs more than macOS 14, under the 15.0 floor.
Debt is consistency, not drawing (§ Mac consistency). The exceptions are the five LLM
provider logos (brand assets, correct) and the welcome illustrations, which are HTML and
copy the web's improvised icons (a pointer copied three times, an eye-off, a chevron,
plus ★ ✓ ✕ ⌄ as Unicode).

## The rules

1. **Icon or glyph.** A mark that sits *in running text* and should take the font's
   weight, baseline and colour is a typographic glyph and stays a character: the ★
   rating, → in a journey, ↔ in a continua label, ⌘⇧⌥↩ in keycaps, the ✓✗⚠●○ pipeline
   matrix in Settings, × meaning "times". A mark that is a **control or affordance** —
   a button, toggle, disclosure, caret or dismiss — is an icon.
2. **One source per surface.** Web icons come from Lucide through `Icon.tsx` and
   nowhere else. Native icons come from SF Symbols. No component draws a `<path>` of
   its own; charts and diagrams are not icons and are exempt by name.
3. **One concept, one icon, on each side.** The concept map below is the vocabulary.
   It is shared across the seam and rendered natively on each side
   (`Undo` = `undo-2` / `arrow.uturn.backward`). A new concept gets a row before it
   gets a glyph.
4. **Stroke follows text.** An icon's stroke is the stem of the text beside it, so it
   carries the same ink, as an SF Symbol does beside SF Pro (§ Weight).
5. **Exceptions are rows, not drawings.** A Lucide glyph we refuse is overridden once,
   in `Icon.tsx`, with the reason in a comment and a row here.

## Concept map

The settled vocabulary. "Today" names the drawings and characters being replaced.
The seven open picks were settled by the owner on 15 Oct 2026 by taking the reviewers'
recommendations; each is a one-line change in `Icon.tsx` if the side-by-side sheet says
otherwise.

| Concept | Lucide | SF Symbol (Mac) | Today on the web |
|---|---|---|---|
| Close / dismiss / delete chip | `x` | `xmark` | 4 SVGs, 18× × ✕ ✗, `badge.css` × |
| Accept / done / menu tick | `check` | `checkmark` | `Icon` check, 7× ✓, `settings.css` ✓ |
| Disclosure (closed → open) | `chevron-right`, rotated 90° | the system control | 2 SVGs, ▶ ▸ (×6), `coverage.css` ▶/▼. TagSidebar's *filled* triangle goes too: the chevron is what the Tahoe sidebar draws |
| Caret on a menu button | `chevron-down` | `chevron.down` | 2 SVGs, ▾ ×5 |
| Collapse | `chevron-up` | `chevron.up` | ▴, ⌃ |
| Previous / next | `chevron-left` / `chevron-right` | `chevron.backward` / `chevron.forward` | 4 SVGs (Screens, tapestry) |
| Show / hide | `eye` / `eye-off` | `eye` / `eye.slash` | 4 SVGs, three of them `eye-off` |
| Search | `search` | `magnifyingglass` | SVG (SearchBox) |
| Zoom in / out | `zoom-in` / `zoom-out` | `plus.magnifyingglass` / `minus.magnifyingglass` | 2 SVGs |
| Edit | `pencil` | `pencil` | SVG, ✎ |
| Revert / restore | `undo-2` | `arrow.uturn.backward` | ↩ ×2 |
| Refresh / re-analyse | `rotate-cw` | `arrow.clockwise` | SVG |
| Download / export | `download` (picked over `share`) | `square.and.arrow.up` | SVG |
| Copy | `copy` | `doc.on.doc` | — (static report only) |
| Folder | `folder` | `folder` | SVG |
| Tag | `tag` | `tag` | SVG |
| Contents (list rail) | `list` | `list.bullet` | SVG |
| Heatmap grid | `layout-grid` | `square.grid.2x2` | SVG |
| Quotes lens | `text-quote` | `text.quote` | SVG traced from the SF Symbol |
| Focus mode | `moon` | `moon` | SVG (an older Lucide `moon`) |
| Session timeline | `gallery-horizontal` | `timeline.selection` | — (new, 17 Oct 2026). SF has no Gantt; `timeline.selection` is Apple's own timeline glyph (a frame between trim handles) and `gallery-horizontal` its silhouette twin. Rejected: `chart-gantt` ↔ `calendar.day.timeline.left` (a calendar day view), `align-start-vertical` ↔ `align.horizontal.left` (both mean align). `docs/mockups/transcript-timeline-toggle.html` |
| Settings | `settings` (picked over `settings-2`) | `gearshape` | SVG drawn as a sun |
| Help | `circle-help` (picked over `info`) | `questionmark.circle` | SVG |
| Star (control) | ★ kept, by decision | `star` / `star.fill` | ★ |
| Play | `play` | `play` | ▶ (`.bn-play-icon`) |
| AI ornament | `sparkle` (picked over keeping ✦) | `sparkles` | ✦ ×2 |
| Deny proposal | `x` (picked over `ban`) | `xmark` (`nosign` means *forbidden*) | ⊘ |
| Warning | `triangle-alert` | `exclamationmark.triangle` | ⚠ |
| Failed | `circle-x` | `xmark.circle` | ✗ |
| Broken part (couldn't be shown) | `image-off` | `photo.slash` | — (new, 20 Oct 2026). A crashed header, nav or dialog shows this mark alone, muted, with no words and no button (`PanelErrorBoundary` `part`). Not a missing image: the mark is chosen for what everyone already does about one, which is reload (⌘R; View ▸ Reload Report and right-click in the Mac app, which use Refresh's `arrow.clockwise`). The slash is shared with Hide's `eye-off`; the picture keeps them apart. `docs/mockups/error-patterns-and-chrome-crash.html` |
| Add | `plus` | `plus` | + (codebook) |
| External link | `external-link` | `arrow.up.forward.square` | ↗ |
| Close a side panel | `x` (picked over `panel-left-close`) | `sidebar.left` | × ×2 |
| Dev playground | `sliders-horizontal` | — | SVG, ◆ |

**Kept as characters.** The Toast and ActivityChip kind glyphs (✓ ℹ ⚠ ✗ —) are bound to
the CLI's `CLI_GLYPH` (`utils/messageKind.ts`, `ui_kinds.py`) and stay Unicode until that
parity is deliberately broken. The rest of the "kept" list is rule 1.

## Weight: the stroke is the stem of the text

**Decided 15 Oct 2026.** An icon's stroke equals the stem thickness of the text beside it,
with a 1 px floor.
The type does not move to suit the icon; the icon follows the type, as SF Symbols follow
SF Pro. Lucide has no named weights, so there is nothing to choose from a set. Its stroke
is a continuous number, and the text supplies it.

**Measured.** Stem of a lowercase "l", as a fraction of the font size:
- Inter (the variable font the SPA loads) measured in the browser;
- SF Pro on its `wght` axis (1–1000, CSS weights map directly) through Core Text,
  `experiments/icon-system/measure_stems.swift`.

| House weight | Token | Inter | SF Pro | Inter at 13 px | Inter at 15 px |
|---|---|---|---|---|---|
| 370 | `light` | *renders 400* | 0.082 | — | — |
| **420** | **`normal`** | **0.092** | **0.090** | **1.19 px** | **1.38 px** |
| 490 | `emphasis` | 0.106 | 0.104 | 1.37 px | 1.58 px |
| 520 | `starred` | 0.111 | 0.110 | 1.45 px | 1.67 px |
| 600 | `semibold` | 0.127 | 0.125 | 1.65 px | 1.90 px |
| 700 | `strong` | 0.146 | 0.144 | 1.90 px | 2.20 px |

From 420 to 700 the two typefaces agree to within 2% (0.03 px at 13 px, below what anyone
can see), so **one table serves both platforms**. Three things follow from it:
- **`light` (370) does not exist in a browser.** The SPA loads Inter as `wght@400..700`
  (`frontend/index.html:39`), so 370 is clamped to 400 wherever it is used. That is a
  type finding, not an icon one; icons beside light text take 0.092.
- **Lucide's own default is close to Inter 420 and a little light:** 1.08 px against
  1.19 px at 13 px.
- **Today's house 1.4 px (`Icon.tsx`) is the stem of emphasis text.** So the web's icons
  have been reading a notch heavier than the body text beside them.

**Mechanism.** One custom property, beside the weight tokens in
`tokens-typography.css`:

```css
--bn-icon-stem: 0.092;                       /* the default: normal text */
.bn-icon   { stroke-width: max(1px, calc(var(--bn-icon-stem) * 1em)); }
```

`vector-effect` is not inherited, so it must sit on each path, not on the `<svg>`.
`lucide-react` 1.49 does this for us: its `nonScalingStroke` prop puts `vector-effect`
on every child, and the facade passes it on every icon. The CSS rule then beats Lucide's
`stroke-width="2"` attribute, because a CSS declaration outranks a presentation
attribute. One WebKit caveat, harmless here: a `transform: scale()` on an ancestor does
not thicken a non-scaling stroke.

- **Size is automatic.** `em` resolves against the text the icon sits in, so a 15 px
  label gets a thicker line than a 13 px one, with no second token.
- **Weight is set in the few places that set it.** A context that sets emphasis or
  strong text sets `--bn-icon-stem` beside its `font-weight` (0.106, 0.146). Phase 1
  lists those contexts. Most icons sit beside 13 px normal labels in toolbars, menus
  and buttons, and need nothing.
- **The Mac needs no override.** SF Pro's stems are Inter's, and its optical-size axis
  (17–96) leaves the stem unchanged, so the text cut WebKit picks at 13 px reads the same.
- **What the catalogue measured in place (15 Oct 2026).** The weights icons actually sit
  beside are not mostly 420:
  - the nav icon tabs: 13 px / 490 → 1.38 px;
  - badge delete ×, AutoCode deny × and accept ✓: 9.6 px / 700 → 1.40 px;
  - sidebar and quote toolbar controls: 13 px / 400 → 1.20 px;
  - signal-card carets: 9.6 px / 460;
  - the settings modal's ▶: 7.8 px / 400.

  The first two were the ones the owner flagged as too thin when the catalogue wrongly
  used 420 everywhere. They are where the rule earns its keep: delete and action glyphs
  are `--bn-weight-strong` by the token's own comment.
- **A 1 px floor (decided 15 Oct 2026).** Below about 11 px of normal text the stem falls
  under a pixel (0.72 px beside the settings modal's 7.8 px ▶). The stroke never goes
  below 1 px; `max()` in the rule above does it.
- **Not `absoluteStrokeWidth`.** That is computed in JS and cannot read a CSS variable.

The mockup's green "stem-matched" row in each frame is this rule. The fixed-pixel rows
around it are there to show what it beat.

Ink is not only stroke. Two more settings come with it:
- **Colour.** On the Mac, icon colour follows the system semantic colours
  (`-apple-system-secondary-label`, `-apple-system-control-accent`) under
  `[data-platform="desktop"]`, so accent colour, dark mode and Increase Contrast move
  the web icons and the native ones together. Colour will show the seam sooner than
  stroke will.
- **Baseline.** SF Symbols sit on the text baseline at cap height; a 1 em box sits low.
  `.bn-icon`'s `vertical-align` becomes a token, tuned in the mockup.

## Implementation

**`Icon.tsx` stays the only door.** It becomes a facade over `lucide-react`:
`<Icon name="close" label="…" />` maps a **house name** (the Concept column) to a
Lucide component, imported **statically by name**. A Lucide rename then fails `tsc`
rather than rendering nothing, so it needs no test of its own. Call sites never import
Lucide directly, so:
- a concept changes glyph in one line;
- an override (the ★) lives in one file;
- stroke comes from the token.

Sizes: `inline` (1 em, the default), `menu` (the check gutter), or a `px` box where a
control was built around one (as built; the planned `toolbar` size was not needed). The facade returns the Lucide element directly, with no wrapper, and takes
only primitive props (`name`, `size`, `className`, and one of `label` / `decorative`), so
a long quote list pays no more than it must.

**Every icon is labelled or declared decorative.** The props type is a union, so a call
with neither does not compile: `label` (becomes `aria-label`, `role="img"`) or
`decorative` (`aria-hidden`). This matters because Lucide adds `aria-hidden` by itself
whenever no accessibility prop is passed, so a forgotten label would fail silently. A button whose only
content was "×" loses its accessible name when the × becomes a hidden SVG, so a migrated
control needs an `aria-label`. Where none exists today, that is **a new locale key in 21
files** (Phase 3's real cost).

**Dependency and budget.**
- `lucide-react`, pinned to an exact version at least two weeks old (1.49.0 is the
  current candidate).
- Named imports tree-shake: about 1.5 kB gzip of shared runtime plus about 200 B per
  icon, so roughly +4–7 kB net once the inline SVGs leave.
- The web budget (`scripts/check-bundle-budget.py`) stands at 208.5 of 222 kB, so this
  takes a third to half of the headroom. Measure after Phase 1. The facade imports every
  mapped icon into one module, so whichever chunk imports `Icon` carries them all. If
  that is too much, split the name map (core icons in `Icon`, lens-only ones beside their
  lens); moving `Icon` out of the barrel would change nothing.
- The export build inlines everything; about 1% of its size, and it needs no network,
  so an offline report keeps every icon. Spot-check once.
- If vitest start-up slows (it loads the package barrel), switch to deep imports.
- No icon font, no sprite.

**One gate, landed at zero.** A test counts `<svg` in `frontend/src/**/*.tsx` outside
`Icon.tsx` and an allowlist of chart files (`Metric`, `SignalsPage` intensity dots,
`TranscriptionDiagnostics`, `SessionTapestry`, the Screens leader lines, the Discussion
wires). It lands in Phase 2's last commit, at zero. No ratchet: the debt is a few commits
deep, not a standing one. The rule was written in July and broken in October, which is
why it needs a gate at all.

## Phases, as built

1. **Foundation — a8333739.** `lucide-react` 1.49.0, pinned exactly. `Icon.tsx` is the facade:
   a house name per concept, a props union that will not compile without `label` or
   `decorative`, `nonScalingStroke`, `className`, a `px` box. `--bn-icon-stem-*` in
   `tokens-typography.css` (normal, emphasis, starred, semibold, strong; no light, since
   370 renders 400), the stem rule with its 1 px floor in `atoms/icon.css`. Two fallbacks
   for a project whose baked theme CSS predates the rule: a `stroke-width="1.25"` and a
   `1em` size attribute on every icon. The menu tick box grew to 1em so Lucide's check
   keeps its ~9 px.
2. **The 29 SVGs — 5696bb52.** Each keeps its box: a `px` prop where the markup set one, or
   the contextual rule that already sized it (`.bn-tp-nav svg { width: 6px }`), which
   wins because the default 1em box sits in `:where()` at zero specificity. The rules
   that stroked the old paths are deleted. The three smallest boxes grew (timeline
   chevron 9 → 12 px, search-token caret 8 → 11, search clear 12 → 14): Lucide pads its
   glyphs, and at those sizes they had become specks. The gate landed at zero.
3. **The characters — 450e3cee.** 45 glyphs in 22 components. No new locale keys were needed:
   every glyph-only control already had an `aria-label`, or a `title`, which a browser
   uses as the name once the content is an `aria-hidden` icon. Stems are set beside the
   `font-weight` of the strong and emphasis controls (badge delete, accept/deny pill,
   activity chips, moderator dismiss, AutoCode title). The play triangle is filled; the
   modal nav's chevron got room a solid ▶ did not need; the starred view shows ★.

**The gate** (`tests/test_no_improvised_icons.py`, each rule mutation-checked): no `<svg`
in a component outside six named charts; the chart allowlist cannot go stale; no
`lucide-react` import outside `Icon.tsx`; no glyph standing alone as an element's
content; no quoted glyph in a JSX expression (the Settings pipeline key exempt by name).

**Phase 4** (the welcome illustrations' copied icons, in `WelcomeIllustrations.swift`) is
not started. The frozen static renderer is not migrated, by design.

## Mac consistency (separate work, same vocabulary)

It is not a phase of this plan: it is another codebase with its own gates, and the only
link is the concept map. It gets its own TODO item. One piece is free to land any time:
a test that every SF Symbol name in the source and in `IconPickerPopover.palette`
resolves (`NSImage(systemSymbolName:)` is non-nil). Today a bad name renders blank,
silently.

Same concept, different symbol today, with the pick:

| Concept | Today | Pick |
|---|---|---|
| Warning | `.fill` and outline; low-disk tinted **red** | `exclamationmark.triangle.fill` in yellow for status; outline in menus only; low disk yellow |
| Cancel a run | `stop.circle` (menu) vs `xmark.circle.fill` (ring) | `xmark.circle.fill` on the ring, `xmark.circle` in the menu; drop `stop.circle` (Xcode's "stop the build") |
| Copy | `doc.on.doc` vs `doc.on.clipboard` | `doc.on.doc`, as the system Edit menu (`doc.on.clipboard` reads as Paste) |
| Reveal Transcripts | `doc.text` (menu) vs `folder` (Export popover) | `folder` |
| Folder row | `folder` (AppKit) vs `folder.fill` (SwiftUI) | outline `folder`, as Finder's sidebar |
| Radio selected | `checkmark.circle.fill` vs `circle.inset.filled` | a real `Picker(.radioGroup)`; if a symbol is unavoidable, `circle.inset.filled` |
| Status dot | `Circle()` vs `circle.fill` | `circle.fill` |
| Direction | fixed `chevron.left/right` (carousel, a disclosure) vs RTL-aware | `.backward` / `.forward` everywhere |
| Drive / network unavailable | sidebar specific, detail pane generic | the sidebar's specific pair in both places |
| ~~In iCloud~~ | ~~`icloud.and.arrow.down` vs `icloud`~~ | resolved 22 Oct 2026: both uses deleted with the `.inCloud` state |
| Send to Miro | `square.grid.2x2` (also Heatmap, All Sessions) | `square.and.arrow.up`, since it is an export |
| `list.bullet`, `waveform` | each carries two or three meanings | one meaning each; pick when touched |
| Disclosure | rotated `chevron.forward` | the system control (`DisclosureGroup`, `NSOutlineView`), not a symbol |

The project-icon palette overlaps chrome (`hourglass`, `film`, `stethoscope`,
`ladybug.fill`), and the comment at `IconPickerPopover.swift:7` claims SF Symbols 6 /
macOS 15, when nothing in it needs more than 14.

## What's left

In the order worth doing.

1. **Decide whether serve and export keep preferring a project's baked theme CSS.** They
   do today with no version check (`server/app.py` `serve_theme_css_with_fallback`,
   `routes/export.py`), so every existing project keeps the CSS it was rendered with —
   for every theme change, not only icons — until it is re-run. Phases 1–3 were made to
   degrade (fallback stroke and size), but three glyphs could not be: see 2.
2. **Three glyphs drawn by theme CSS, deferred until 1 is decided**: the AI badge's
   delete × (`badge.css` `.badge-ai::after`), Settings' "copied" ✓ (`settings.css`), the
   Dashboard coverage ▶/▼ (`coverage.css`). Migrating them means rendering an element and
   removing the pseudo-element; under an old baked copy each would show twice. A
   reviewed implementation existed and was reverted (Badge `.badge-ai-delete` with a
   `:has()` guard that keeps the static report's × — reconstruct from the 16 Oct session).
3. **Look at the result.** The owner has not yet seen the migrated app. The local
   catalogue's `compare.html` shows every icon before and now, in place; the stroke at
   very small sizes and the three grown boxes are the judgement calls.
4. **The Mac app** shows none of this until the sidecar is rebuilt (`build-sidecar.sh`),
   and an existing project then still serves its baked CSS (1). Not verified in the
   WKWebView.
5. **Small leftovers**: the Discussion lens's ▾ is part of a badge's text
   (`DiscussionLens.tsx`, `code={`#${{n}} ▾`}`) and wants a real element; the dev
   playground's ◆ has no Lucide match; the signal-card caret and the hidden-quotes
   chevron read fainter than the old glyphs (opacity 0.4 and 0.7em).
6. **Phase 4**, the welcome illustrations.
7. **Mac consistency** (§ below), its own TODO item, plus the cheap test that every SF
   Symbol name resolves.
8. **Not built from § Weight:** the Mac colour nativisation (icons on
   `-apple-system-secondary-label` / `-apple-system-control-accent` under
   `[data-platform="desktop"]`) and the baseline token (`.bn-icon` still uses a fixed
   `vertical-align: -0.125em`). Both are tuning passes for after the owner has looked.
9. **Type, found on the way:** `--bn-weight-light: 370` never renders in a browser (Inter
   is served `wght@400..700`); and the frozen static report's `quote_card.html:4` writes
   `class=”speaker”` with curly quotes, so `.speaker` never matches.

## Open questions

- **Inter loads from Google Fonts.** Offline, or where Google is blocked, a report falls
  back to the system font, and opening it makes an outbound request. Owner's view
  (15 Oct 2026): an old report read offline in the system font is acceptable. The icons
  are what must survive, and they do, because Lucide is inlined in the bundle. Embedding
  Inter's Latin subset would add an estimated ~65 KB to a ~1.55 MB export (OFL permits
  it). Not measured, and not part of this work.
- **The Mac feedback sheet uses emoji faces** (😠…😊). The web's static footer does too.
  Lucide has `angry`…`laugh`; whether faces should be icons is a product question.
- **Brand marks.** LLM provider logos are assets; Teams / Meet / Zoom are letter symbols
  (`m.square`, `g.circle`, `z.square`). The licence boundary is already recorded in project
  memory; nothing here changes it.
