---
name: bn-mockup
description: Build a Bristlenose UI mockup. Two modes — bn-accurate (the shipped design system, real --bn-* tokens + real component classes, artefact walled off from commentary) and quick/loose (hand-rolled tokens, fast). Use bn-accurate when the user asks for a "bn accurate" / "design-system-true" / "real pixels" mockup of a Bristlenose surface, or is reviewing a design to build; use quick for a fast sketch. Either beats a long text-only back-and-forth.
user-invocable: true
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

Make an HTML mockup of a Bristlenose surface. Save to **`docs/mockups/<name>.html`** (repo convention — `serve --dev` auto-discovers them in the About → Design section; also openable as `file://`). Pick the mode from the ask.

## Two modes

- **bn-accurate** — the user says "bn accurate", "design-system-true", "real pixels", or is reviewing a spec to *build*. Use the shipped design system exactly. Full recipe below.
- **quick / loose** — "just a rough mockup", exploring an idea. Hand-rolled tokens are fine; move fast. Still save to `docs/mockups/`. Skip the rest of this file.

The point of bn-accurate: **we do not reinvent what the design system means.** The tokens, the switch, the badge, the sidebar already exist — reference them, don't approximate them.

## bn-accurate recipe

### 1. Lift the real tokens + components — don't hand-roll them

The shipped tokens live in `bristlenose/theme/tokens.css` + `bristlenose/theme/colors/palette-default.css` / `palette-edo.css` (atoms/molecules/organisms alongside). **The fastest true-to-pixel path is to copy the inlined `<style>` block from an existing mockup that already did this** — the canonical one is **`docs/mockups/codebook-library-states.html`** (its `:root` blocks inline the shipped tokens verbatim, and it defines the real `.badge`, `.sw` switch, `.sec`/`.fold`, `.sb-row`/`.dot`, `.apply-btn`). Start from that stylesheet, then add only what your surface needs.

Set `<html data-color-theme="default">`, `color-scheme: light dark`, and theme every colour with `light-dark(<light>, <dark>)`. The `[data-color-theme="edo"]` block gives the warm-palette swap — keep it so the mockup can be checked in both palettes.

### 2. Token cheat-sheet (the ones you'll reach for)

- Type: `--bn-font-body` (Inter/system), `--bn-font-mono`. Scale: `--bn-text-micro/badge/caption/label/body/heading/title/display`. Weights: `--bn-weight-normal:420 / -emphasis:490 / -strong:700` (**490 is "bold" here, not 600/700**).
- Space: `--bn-space-xs/sm/md/lg/xl`. Radii: `--bn-radius-sm/md/lg/pill`.
- Colour: `--bn-colour-bg / text / muted / border / accent / hover / quote-bg / badge-bg / badge-text / border-hover / shadow`. State: `--bn-off-track` (switch/dot off), `--bn-positive`.
- Group tints (tag-pill fills): `--bn-emo-1-bg`, `--bn-task-1-bg`, `--bn-ux-1-bg`, `--bn-trust-1-bg`, `--bn-opp-1-bg`.

### 3. Real component recipes

- **Tag badge**: `.badge` = `font-family:var(--bn-font-mono); font-size:var(--bn-text-badge); background:var(--bn-colour-badge-bg)` (grey default). A **coloured** tag pill is `.badge` + inline `style="background:var(--bn-emo-1-bg)"` (or another group tint).
- **Switch** (enable/disable, macOS-matched): `.sw` = 38×22, `border-radius:11px`, `background:var(--bn-colour-accent)`; off → `background:var(--bn-off-track)`; 18px white knob via `::after` (left:18px on / left:2px off).
- **Status dot** (sidebar, status-only never a control): 7px, `--bn-colour-accent` on / `--bn-off-track` off / `transparent` available. Aligned to the **first** line (bullet), not the block centre.
- **Apply button**: `.apply-btn` = `color:#fff; background:var(--bn-colour-accent); border-radius:var(--bn-radius-md)`.
- **Section fold** (codebook page disable): `.sec` + `.fold` (`grid-template-rows:1fr` → `0fr` on `.off`), meta crossfades `on-m`/`off-m`.
- **Eye toggle** icons (the app's own paths):
  - open: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`
  - closed: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`
- `prefers-reduced-motion: reduce` → kill the fold/switch transitions.

### 4. Wall the artefact off from the commentary

**Non-negotiable when reviewing a design:** the reader must tell "what ships" from "why it works" at a glance.

- **Artefact zone** = the real pixels, in a clean frame (a light "screenshot" chrome bar is fine). **No prose, no callouts, no labels that wouldn't appear in the product.** If a caption explains the pixel, it does not belong here.
- **Commentary zone** = a *visually distinct* block (hatched/tinted background, a mono "Commentary" label, a left rule) placed below/beside — deliberately not-the-product.
- Put a small **key** at the top naming the two zones. For before/after comparisons, label the frame chrome ("before"/"after"), never the UI inside it.

### 5. Don't reinvent — check first

Before drawing a control, confirm it exists: components in `frontend/src/components/` (`Badge`, `EyeToggle`, `TagInput`, `Toggle`, `ConfirmDialog`, `ThresholdReviewModal`, `TagSidebar`) and `frontend/src/islands/` (`CodebookPanel`, `QuoteGroup`); CSS in `bristlenose/theme/{atoms,molecules,organisms}`; existing mockups in `docs/mockups/`; design intent in `docs/design-*.md`. A mockup should surface *existing* components in new states — flag any genuinely new element to the user before inventing it (per `feedback_shared_taxonomy_render_native_per_surface` and the no-bespoke-CSS rule).

## Self-contained + viewable

Full standalone HTML doc (DOCTYPE/html/head/body) so it opens as `file://` and in `serve --dev`. No external font/CSS CDNs (inline everything). After writing, the file shows in the Browser pane; tell the user the path.

## Reference

The worked example this skill generalises: `docs/mockups/codebook-disable-old-vs-new.html` (real tokens + framed artefacts + separated commentary) and `docs/mockups/codebook-library-states.html` (the canonical inlined-token stylesheet to copy from).
