# Design: Breathing Logotype

**Status:** Mockup complete, implementation deferred
**Mockup:** `docs/mockups/mockup-header-redesign.html`
**Target branch:** Merge into `react-router` worktree once that branch stabilises
**Related:** `living-fish` branch (animated fish video — separate concern, but same header region)

---

## What it is

The "Bristlenose" logotype text and its background block slowly drift through colours sampled from the fish logo — warm browns, olive greens, cream/gold spots, dark umber. The animation is almost imperceptible at production speed, like very slow breathing.

### Type spec

- Font: Inter Semi Bold (600)
- Size: 12px
- Line height: 15px
- Letter spacing: 2% (0.02em)
- Display: inline-block with padding (0.15rem 0.45rem), border-radius 3px
- Position: flush to top-left of content area, left-aligned with toolbar and main content

### Colour animation

- **Fish palette (HSL):** H 25–55 (umber brown → olive green), S 18–40%, L 28–88%
- **Both text and background** use the same full lightness range on independent sine waves — they cross over periodically (text becomes light on dark bg, then back)
- **Bias:** light mode = dark text ~70% of the time; dark mode = light text ~70% (power-curve skew on the lightness sine)
- **Speed modulation:** the speed itself breathes on a ~67s sine, oscillating between 1.5x and 4x of base rate
- **Base periods:** H ~37s, S ~23s, text-L ~29s, bg-L ~43s, bg-H ~41s — coprime for organic feel
- **Implementation:** `requestAnimationFrame` loop, virtual time accumulator (speed-independent), HSL colour strings applied via `el.style.color` / `el.style.background`

---

## Implementation plan

### Shape: React component

In the `react-router` branch, the header is still Jinja2 (`report_header.html`) — it's not yet a React component. The NavBar *is* React (`NavBar.tsx`), and `AppLayout.tsx` renders `<NavBar /> <Outlet />`.

**Step 9** of the React migration plan is "app shell cleanup" — that's when the header becomes React. The breathing logotype should ship as part of that step, or as a small addition after it.

### Target component structure

```
frontend/src/components/BreathingLogotype.tsx   — the animated text + bg
frontend/src/components/ReportHeader.tsx        — header layout (logo, logotype, project info)
frontend/src/hooks/useBreathingColour.ts        — sine-wave colour engine (reusable)
```

### `useBreathingColour` hook

Extracted from the mockup JS. Returns `{ textColor: string, bgColor: string }` that update on each animation frame. Uses `useRef` for virtual time accumulator, `useEffect` with `requestAnimationFrame` loop, `useState` for the two colour strings.

Parameters (with defaults matching the mockup):
- `palette: { hMin, hMax, sMin, sMax, lMin, lMax }` — fish colours
- `periods: { hue, saturation, textLightness, bgLightness, bgHue }` — sine periods
- `bias: { textL, bgL }` — power-curve lightness skew
- `speedRange: { min, max, period }` — speed modulation envelope

Dark mode detection via `window.matchMedia('(prefers-color-scheme: dark)')` or reading `document.documentElement.dataset.theme` (the existing Bristlenose pattern).

### `BreathingLogotype` component

```tsx
export function BreathingLogotype() {
  const { textColor, bgColor } = useBreathingColour();
  return (
    <span
      className="header-logotype-new"
      style={{ color: textColor, background: bgColor }}
    >
      Bristlenose
    </span>
  );
}
```

CSS class `header-logotype-new` provides the type spec (12px, 600, 0.02em letter-spacing, padding, border-radius). Add this to `atoms/logo.css` alongside the existing `.header-logotype`.

### `ReportHeader` component

Replaces the Jinja2 `report_header.html` in serve mode. Layout:

```tsx
export function ReportHeader({ projectName, meta }: Props) {
  return (
    <div className="report-header-new">
      <div className="header-left">
        <BreathingLogotype />
        <a href="/report/" className="report-logo-link">
          <img className="report-logo" src="/assets/bristlenose-logo.png" alt="" />
        </a>
      </div>
      <div className="header-right">
        <span className="header-project-title">{projectName}</span>
        <span className="header-meta">{meta}</span>
      </div>
    </div>
  );
}
```

Mounted in `AppLayout.tsx` above `<NavBar />`:

```tsx
export function AppLayout() {
  return (
    <PlayerProvider>
      <FocusProvider>
        <KeyboardShortcutsManager>
          <ReportHeader projectName={...} meta={...} />
          <NavBar />
          <Outlet />
        </KeyboardShortcutsManager>
      </FocusProvider>
    </PlayerProvider>
  );
}
```

Project name and meta come from the existing `/api/projects/1` endpoint (already fetched by Dashboard).

### CSS changes

In `atoms/logo.css`, add:

```css
.header-logotype-new {
    font-size: 12px;
    font-weight: 600;
    line-height: 15px;
    letter-spacing: 0.02em;
    display: inline-block;
    padding: 0.15rem 0.45rem;
    border-radius: var(--bn-radius-sm);
    /* Fallback colour before JS hydrates */
    color: hsl(35, 25%, 45%);
    background: hsl(35, 18%, 90%);
}
```

### Static render path

The static render path (`bristlenose render`) keeps the existing Jinja2 header with the current logotype style. The breathing animation is serve-mode only — no JS in static HTML reports. This is consistent with the rule: "new features target React serve version only."

### Coordination with `living-fish` branch

The `living-fish` branch replaces the fish `<img>` with a `<video>` loop. That's orthogonal to the logotype text animation — they occupy different DOM elements. But they'll both modify `atoms/logo.css` and the header layout. **Merge order:** whichever is ready first goes in; the second rebases. Low conflict risk since they touch different CSS selectors (`.report-logo` vs `.header-logotype-new`).

### Tests

- `useBreathingColour.test.ts` — unit test the hook with fake `requestAnimationFrame` (vi.useFakeTimers). Verify colour values are within palette range. Verify bias skew produces expected distribution over N frames.
- `BreathingLogotype.test.tsx` — renders, applies inline style, has correct class.
- `ReportHeader.test.tsx` — renders project name, meta, logo, logotype.

### Verification

1. `npm run build` (tsc type-check)
2. `npm test` (Vitest)
3. `bristlenose serve <folder> --dev` — visual check: logotype breathes, colours drift, crossovers happen
4. Toggle dark mode — bias inverts (light text on dark bg ~70%)
5. Check static render (`bristlenose render`) — logotype uses fallback CSS colours, no animation, no errors

---

## Open questions

1. **Should the breathing be pauseable?** e.g. `prefers-reduced-motion` media query → static fallback colours. Probably yes for accessibility.
2. **Should the logotype link anywhere?** Currently the fish links to Project tab. Should the text also link, or is it purely decorative?
3. **Hook reuse:** Could `useBreathingColour` be used elsewhere (e.g. subtle tinting on section dividers, loading states)? Design the API generically but don't over-engineer.
