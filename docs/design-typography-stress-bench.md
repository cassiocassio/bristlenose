# Typography Stress-Test Bench — design

**Status:** Built (Jun 2026). Tool: [`docs/design-system/typography-stress-bench.html`](design-system/typography-stress-bench.html). Auto-discovered by `bristlenose serve --dev`; open directly with `open docs/design-system/typography-stress-bench.html`. **Not** shipped in the wheel, **not** part of the React SPA — a personal design tool.

## Purpose

The tuning instrument for Phase 1 (type-snap) of the native-typography effort (see `docs/design-native-typography-grid.md`). You bump a desktop SF-Pro type token and need to **catch the ripple across every component, by eye**: a bump that fixes quotes can quietly wreck signal cards three screens down. No other surface shows the whole system reacting to a single token change.

The proofing-bench and side-by-side-type-comparison parts have prior art (Pattern Lab, Storybook, font proofers, the 8-pt grid); the novel bit is the cross-component **ripple-on-token-bump**, which is why the *eye* — not pixel-diffing — is the judge (cross-engine antialiasing never matches anyway).

## Architecture

- **Real cascade, not a mock.** The page `<link>`s the live `bristlenose/theme/*.css` (in `_THEME_FILES` order) and renders real-class components, so a token edit ripples for real. (Re-sync the link list if `_THEME_FILES` is reordered.)
- **A CSS grid, config columns × component rows.** Each component is one grid row spanning both columns — read *across* = same component in each config, *down* = one config through all components. Because the left and right cells share a grid row, they stay top-aligned: **no scroll drift** (this is why it's a grid, not two scrollers).
- **Left = Reference (known-good), Right = Editing (judge this).** Each column has its own type-theme / colour-scheme / light-dark pickers. Per-cell config is applied via `data-platform` / `data-color-theme` / `data-theme` attributes + an inline `color-scheme`. **Verified**: the theme's palette selectors are plain attribute selectors (`[data-color-theme="edo"]`, not `:root`-compound) and dark mode is `light-dark()` + `color-scheme`, so per-cell theming resolves correctly — no iframe isolation needed.
- **Value-set model.** Editing-column sizes are inline `--bn-text-*` vars driven by a JS value-set; the live token editor mutates it. Two sets are held — `editBaseline` (before) and `editValues` (after) — and the flick swaps between them. The cell is given the report's body base (`font-family: var(--bn-font-body); font-size: var(--bn-text-label)`) so inherited-size components (e.g. nav tabs) render correctly and ripple.
- **Chrome on `system-ui`, deliberately.** The toolbar/editor must be a stable reference frame while the content moves, so it never consumes the theme tokens it's editing.

## Controls

| Control | Behaviour |
|---|---|
| **Edit: before ↔ after** | Flips the *editing* column between baseline and your edits, scroll-anchored to the component under focus. |
| **Hold Space** | Peek the original (baseline) while held; release returns to your edits. Louder cue: the editing cells get a tinted inset border while showing baseline. |
| **Edit tokens** | Collapsible drawer — size + line-height per stop (tracking omitted; see limits). Undo snapshots once per field-edit session, not per keystroke. |
| **Undo / Reset / ⌘Z** | Single-step undo; Reset returns the editing column to baseline (itself undoable). |
| **Grid** | 4/8-pt spacing overlay (spacing rhythm, *not* a baseline grid — the leadings aren't 8-pt multiples by design). |
| **Highlight token** | Outlines every element using a `--bn-text-*` stop (annotated via `data-token`); shows a hit count, and says "no … on screen" instead of silently dimming everything. |
| **Export** | Paste-ready `[data-platform="desktop"]` (or `:root` for web) CSS block + JSON; clipboard with an honest success/fallback message; persistence = paste to Claude → "save as version 3" (same loop as the Type Parity Inspector). |

## Content

Climbing-study sample (real, from the mockups — IKEA content isn't in the worktree), **frozen** so a visual change is your bump not different content, and **weighted to extremes**: a 60+-word quote, a long tag (`risk management and safety`), a long name (`Lena Hoffmann-Bergström`), a three-card cluster for margins-in-context.

## Review (usual-suspects, Jun 2026)

Four agents (code-review, ux-critique, a11y-review, silent-failure-hunter). The load-bearing catches, all fixed: the cells didn't set `font-family`/base `font-size`, so the Inter-vs-SF axis was inert and inherited-size components didn't ripple (the single most important defect); the tracking control was theatre (no component consumes `--bn-track-*`) — removed; clipboard claimed "Copied" unconditionally — now honest; the dependency-highlight dimmed everything on a no-match — now guarded; plus focus rings, Escape-to-close, export-selector-per-platform, undo granularity, degenerate-value clamp. One contradiction (ux-critique wanted an iframe rebuild for per-cell theming) was resolved against the actual CSS — per-cell theming works, no rebuild.

## Known limitations / deferred

- **Tracking is unwired.** `--bn-track-*` exists in `tokens-desktop.css` but no component consumes `letter-spacing` yet, so the bench omits the knob rather than fake it. Export still emits the tokens (≈0; only `micro` is non-zero) for file fidelity.
- **`[data-theme]`-*ancestor*-selector components** (toast, logo, tag-suggest dropdown) won't dark-theme per-cell — not in the current specimen set; would need iframes if added.
- **Narrow-breakpoint coverage** (500/1100px) isn't exercised — cells are wide. A per-column width control is the obvious next add if a bump breaks wrapping at the narrow end.
- **Content is the climbing study, not IKEA.** Swap in the public-safe IKEA demo subset when it's available (same content the website screenshots need).
- **Generalisation deferred:** loading arbitrary saved variants into either column (SF-v1 vs SF-v2) is phase 2 — variants are real versioned CSS files (`tokens-desktop-v*.css`) Claude writes from exports; v1 compares the two real themes.
