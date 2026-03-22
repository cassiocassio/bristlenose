# Plan: Diverge Desktop & Browser Visuals

## Context

Bristlenose currently has zero visual divergence between the macOS desktop app and the CLI-driven browser version — both render the identical React SPA with the same CSS. As we approach App Store release, three layers need to separate:

1. **Typography & Icons** — SF Pro + SF Symbols feel on macOS, Google Fonts (Inter) on web
2. **Chrome & Functionality** — web needs explicit toolbars/export/nav; macOS gets these from the native shell
3. **Color themes** — the current blue-links/red-cancel palette was "good enough for alpha." We need a pluggable color theme system so we can ship an Edo palette for macOS and evolve the web palette independently, swappable with a single token file change

## Architecture: Platform Detection

**How the frontend knows which mode it's in:**

1. Desktop launcher already passes env vars to the sidecar (`ContentView.swift` lines 174–190). Add `BRISTLENOSE_PLATFORM=desktop`.
2. Server reads this and exposes it via the existing `/api/config` or a new lightweight endpoint, and also injects `data-platform="desktop"` on the `<html>` element (same injection point as `data-theme`).
3. Frontend gets a `usePlatform()` hook (backed by `platform.ts`) that reads the attribute. CSS uses `[data-platform="desktop"]` selectors.

**Files to modify:**
- `desktop/Bristlenose/Bristlenose/ContentView.swift` — add env var
- `bristlenose/server/app.py` — read env var, inject `data-platform` attribute
- `frontend/src/utils/platform.ts` — add `isDesktop()` based on `document.documentElement.dataset.platform`

## Layer I: Typography & Icons

### Fonts

**Strategy:** A platform token override file loaded after the base tokens.

```
bristlenose/theme/
  tokens.css              ← shared (spacing, radii, layout, transitions)
  tokens-typography.css   ← web defaults (Inter, current scale)
  tokens-desktop.css      ← desktop overrides (SF Pro, Apple HIG scale)
```

`tokens-desktop.css` overrides under `[data-platform="desktop"]`:
- `--bn-font-body: -apple-system, "SF Pro Text", "SF Pro", system-ui, sans-serif`
- `--bn-font-heading: -apple-system, "SF Pro Display", system-ui, sans-serif` (new token — Display variant for ≥20pt)
- Type scale adjusted to match Apple HIG defaults (body 13pt, subhead 15pt, etc. — slightly different progression than current)
- Weight scale remapped for SF Pro's optical weight axis

**Files to create:**
- `bristlenose/theme/tokens-typography.css` — extract current font/type tokens from `tokens.css`
- `bristlenose/theme/tokens-desktop.css` — SF Pro overrides

**Files to modify:**
- `bristlenose/theme/tokens.css` — remove font/type tokens (moved to `tokens-typography.css`)
- `bristlenose/theme/index.css` — import order: `tokens.css` → `tokens-typography.css` → `tokens-desktop.css`
- `bristlenose/stages/s12_render/theme_assets.py` — add new files to `_THEME_FILES` list
- `frontend/index.html` — keep Google Fonts `<link>` (web only; desktop doesn't need it)

### Icons

**Strategy:** An `<Icon>` React component with a platform-aware registry.

Current state: ~12 inline SVGs scattered across NavBar, SidebarLayout, SearchBox, EyeToggle, TagInput, InspectorPanel, ToolbarButton, ExportDialog.

Plan:
1. Create `frontend/src/components/Icon.tsx` — takes `name` prop, renders from registry
2. Create `frontend/src/icons/web/` — current SVGs extracted as named exports
3. Create `frontend/src/icons/desktop/` — SF Symbols-matching SVGs (same names, same viewBox, matching stroke weights 1.2–1.5 for SF Symbols Ultralight/Regular feel)
4. `Icon.tsx` picks registry based on `isDesktop()`
5. Refactor existing components to use `<Icon name="export" />` etc.

**Files to create:**
- `frontend/src/components/Icon.tsx`
- `frontend/src/icons/web.ts` (barrel export of current SVGs)
- `frontend/src/icons/desktop.ts` (SF Symbols-style SVGs)

**Files to modify:**
- `frontend/src/components/NavBar.tsx` — replace inline SVGs with `<Icon>`
- `frontend/src/components/SidebarLayout.tsx` — same
- `frontend/src/components/SearchBox.tsx` — same
- `frontend/src/components/EyeToggle.tsx` — same
- `frontend/src/components/ToolbarButton.tsx` — same
- Other components with inline SVGs

## Layer II: Chrome Divergence

**What macOS provides natively (SwiftUI shell):**
- Window title bar with traffic lights
- Native toolbar (can host buttons)
- Share sheet (system-level)
- Menu bar (File → Export, etc.)

**What web must keep providing:**
- `.bn-global-nav` tab bar (Project/Sessions/Quotes/Codebook/Analysis)
- Export button + ExportDialog
- Settings + Help modals
- Toolbar with view switcher, density, sort

**What desktop should hide/simplify:**
- Export button in nav bar (move to native menu bar / toolbar)
- Possibly simplify the sticky `.toolbar` if native toolbar hosts some controls
- Share functionality → native share sheet

**Strategy:** CSS hiding via `[data-platform="desktop"]` for simple cases, React conditional rendering for structural differences.

```css
/* organisms/global-nav.css */
[data-platform="desktop"] .bn-nav-export,
[data-platform="desktop"] .bn-nav-share {
  display: none;
}
```

For structural differences (e.g., desktop gets a slimmer nav without the icon cluster on the right):
```tsx
// NavBar.tsx
const { isDesktop } = usePlatform();
// ... conditionally render icon buttons
```

**Files to modify:**
- `bristlenose/theme/organisms/global-nav.css` — desktop overrides
- `bristlenose/theme/organisms/toolbar.css` — desktop overrides
- `frontend/src/components/NavBar.tsx` — conditional rendering
- `frontend/src/components/ExportDialog.tsx` — desktop might trigger native share instead

**Files to create (SwiftUI side, future):**
- Desktop toolbar items in `desktop/Bristlenose/` that communicate with the React app via URL scheme or JS bridge

## Layer III: Pluggable Color Themes (Edo + future themes)

### Making colors modular

**Current state:** ~40 color tokens hardcoded in `tokens.css` using `light-dark()`. Not swappable.

**Target state:** Color palettes live in standalone files. Switching theme = changing one attribute. Users can pick themes (like terminal color schemes — Solarized, Dracula, Nord, etc. are beloved in the CLI world). The font scale and grid system stay fixed (users won't reinvent those), but swapping colors is a one-line config change.

**Strategy:**

```
bristlenose/theme/
  tokens.css                    ← layout, spacing, radii, transitions (color-free)
  tokens-typography.css         ← font stacks, type scale
  colors/
    _contract.css               ← documents required color tokens (reference, not loaded)
    palette-default.css         ← current blue/grey (web default)
    palette-edo.css             ← Edo palette (desktop default)
    palette-solarized.css       ← community theme (example/future)
    palette-edo-swiftui.json    ← Edo colors exported for SwiftUI Asset Catalog
```

Each palette file defines all `--bn-colour-*` tokens under a scoped selector:

```css
/* palette-default.css — loaded for everyone, provides :root fallback */
:root,
[data-color-theme="default"] {
  --bn-colour-bg: light-dark(#ffffff, #111111);
  --bn-colour-accent: light-dark(#2563eb, #60a5fa);
  /* ... all ~40 color tokens ... */
}

/* palette-edo.css — overrides when active */
[data-color-theme="edo"] {
  --bn-colour-bg: light-dark(#faf8f5, #1a1816);
  --bn-colour-accent: light-dark(#8b4513, #d4a574);
  /* ... Edo palette ... */
}
```

**Contract file (`_contract.css`):** Lists every `--bn-colour-*` token a palette must define, with comments explaining each. Not loaded by the browser — it's documentation for theme authors. A test validates that every palette file defines all tokens in the contract.

**Loading:**
- `palette-default.css` always loaded first (provides `:root` fallback)
- Additional palette files loaded after (override via specificity of `[data-color-theme]`)
- Server sets `data-color-theme` from config: `color_theme` setting in project config, or `BRISTLENOSE_COLOR_THEME` env var
- Desktop defaults to `"edo"`, web defaults to `"default"`
- Settings modal gets a theme picker dropdown (future — shows palette names)

**User-facing config:**
- `bristlenose.toml` or project config: `color_theme = "edo"`
- CLI: `bristlenose serve --color-theme edo`
- Env: `BRISTLENOSE_COLOR_THEME=edo`
- Same pattern as existing `color_scheme` (auto/light/dark) — orthogonal: scheme picks light vs dark, theme picks the palette

**Adding a new theme:** Drop a `palette-<name>.css` in `colors/`, define all contract tokens, add to `_THEME_FILES` — done. No React changes needed.

**SwiftUI color sharing:**
- `palette-edo-swiftui.json` generated from `palette-edo.css` via `scripts/export-palette-swiftui.py`
- CSS is the source of truth; JSON is a checked-in build artifact
- SwiftUI reads from Asset Catalog (`.xcassets`) generated from the JSON
- A CI check verifies CSS and JSON stay in sync

**Sentiment colors stay shared** — they're analytical, not brand. Keep in `tokens.css` (or a `tokens-sentiment.css` if we want to split further). Themes don't override sentiment hues.

**Files to create:**
- `bristlenose/theme/colors/palette-default.css` — extract current colors from tokens.css
- `bristlenose/theme/colors/palette-edo.css` — new Edo palette (to be designed)
- `bristlenose/theme/colors/_contract.css` — token contract documentation
- `bristlenose/theme/colors/palette-edo-swiftui.json` — SwiftUI export
- `scripts/export-palette-swiftui.py` — CSS → JSON converter
- `tests/test_color_contract.py` — validates all palettes define all contract tokens

**Files to modify:**
- `bristlenose/theme/tokens.css` — remove color tokens (moved to palette files)
- `bristlenose/theme/index.css` — import palette files
- `bristlenose/stages/s12_render/theme_assets.py` — add palette files to `_THEME_FILES`
- `bristlenose/server/app.py` — set `data-color-theme` attribute based on platform/config
- `bristlenose/server/app.py` — accept `--color-theme` CLI flag / env var

## Phased Rollout

### Phase A: Infrastructure — DONE (Mar 2026)
1. ~~Platform detection plumbing (env var → server → HTML attribute → React hook)~~
2. ~~Extract color tokens from `tokens.css` into `colors/palette-default.css`~~
3. ~~Extract font/type tokens into `tokens-typography.css`~~
4. ~~Create `tokens-desktop.css` with SF Pro overrides~~
5. ~~Create `colors/palette-edo.css` with Edo palette (light + dark)~~
6. ~~Create `colors/_contract.css` + `tests/test_color_contract.py`~~
7. ~~Update `index.css` imports and `theme_assets.py` file list~~
8. ~~Verify: everything looks identical — pure refactor, no visual change~~

### Phase B: Typography fork
1. Test SF Pro type scale on macOS with the desktop app
2. Iterate sizes/weights until it feels native (currently Apple HIG defaults)
3. Iterate sizes/weights until it feels native

### Phase C: Icon system
1. Create `Icon.tsx` component and extract existing SVGs into `icons/web.ts`
2. Refactor components to use `<Icon>`
3. Design and add `icons/desktop.ts` with SF Symbols-weight SVGs

### Phase D: Chrome divergence
1. Add `[data-platform="desktop"]` CSS overrides to hide web-only chrome
2. Conditional rendering in NavBar for desktop mode
3. (Future) Wire native SwiftUI toolbar to trigger React actions via JS bridge

### Phase E: Edo color theme + theme picker
1. Create `_contract.css` documenting all required color tokens
2. Write `test_color_contract.py` — validates every palette defines all tokens
3. Map the Edo palette to tokens — **already designed** in `docs/mockups/edo-colour-palette.html` (15 sampled colors from 3 Edo-period artworks, British Museum visit 1 Mar 2026). Token mapping table is in the mockup. Key decision: accent = Prussian Blue (`#1E3A5F`) or Verdigris (`#7BA8A0`). Dark mode variants need deriving from the same source hues
4. Create `palette-edo.css`
5. Add `--color-theme` CLI flag and `BRISTLENOSE_COLOR_THEME` env var
6. Generate SwiftUI color export via `scripts/export-palette-swiftui.py`
7. Apply Edo to desktop by default, test both themes
8. (Future) Add theme picker to Settings modal

## Verification

After each phase:
1. `cd frontend && npx vitest run` — unit tests pass
2. `.venv/bin/python -m pytest tests/` — Python tests pass
3. `.venv/bin/ruff check .` — lint clean
4. Manual QA: run `bristlenose serve --dev` and check both with and without `data-platform="desktop"` attribute (toggle in browser DevTools)
5. Phase E additionally: verify Edo colors render correctly in SwiftUI prototype

## Key Files Summary

| File | Change |
|------|--------|
| `bristlenose/theme/tokens.css` | Remove font + color tokens (keep layout/spacing/sentiment) |
| `bristlenose/theme/tokens-typography.css` | **New** — web font stack + type scale |
| `bristlenose/theme/tokens-desktop.css` | **New** — SF Pro overrides under `[data-platform="desktop"]` |
| `bristlenose/theme/colors/_contract.css` | **New** — documents required tokens for theme authors |
| `bristlenose/theme/colors/palette-default.css` | **New** — current blue/grey palette |
| `bristlenose/theme/colors/palette-edo.css` | **New** — Edo palette |
| `tests/test_color_contract.py` | **New** — validates all palettes define all contract tokens |
| `bristlenose/theme/index.css` | Updated import order |
| `bristlenose/stages/s12_render/theme_assets.py` | Add new CSS files to `_THEME_FILES` |
| `bristlenose/server/app.py` | Inject `data-platform` + `data-color-theme` attributes |
| `frontend/src/utils/platform.ts` | Add `isDesktop()`, `usePlatform()` hook |
| `frontend/src/components/Icon.tsx` | **New** — platform-aware icon component |
| `frontend/src/icons/web.ts` | **New** — extracted current SVGs |
| `frontend/src/icons/desktop.ts` | **New** — SF Symbols-style SVGs |
| `frontend/src/components/NavBar.tsx` | Use `<Icon>`, conditional desktop rendering |
| `desktop/.../ContentView.swift` | Add `BRISTLENOSE_PLATFORM=desktop` env var |
| `scripts/export-palette-swiftui.py` | **New** — CSS palette → SwiftUI JSON |
