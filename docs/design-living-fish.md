# Living Fish — Animated Logo for Serve Mode

Subtly animated "living portrait" pleco logo: breathing gills, slight fin sway, otherwise perfectly still. Serve mode only — static render keeps the transparent PNG.

## Current status

**Code: done.** All 11 files committed on `living-fish` branch, tested (1811 Python, 590 Vitest).

**Blocked on assets.** Drop these into `bristlenose/theme/images/` and serve mode picks them up automatically:

| File | Format | Purpose |
|------|--------|---------|
| `bristlenose-transparent.png` | PNG with alpha | Base logo for all themes (light + dark) |
| `bristlenose-alive.webm` | VP9 with alpha | Animated logo (Chrome, Firefox, Edge) |
| `bristlenose-alive.mov` | HEVC with alpha | Animated logo (Safari) |

---

## Asset creation pipeline

### Step 1: Remove background from source photo

Take the source pleco photo and remove the background.

**Tools:** remove.bg, Adobe Express, Canva, or any AI background removal tool.

**Output:** `bristlenose-transparent.png` — PNG with alpha transparency. Save to `bristlenose/theme/images/`.

This transparent PNG also fixes the dark-mode logo problem. It replaces the old dual-logo system (`bristlenose.png` + `bristlenose-dark.png` + `mix-blend-mode: lighten` hack) with a single image that composites cleanly on any background.

### Step 2: Generate AI video

Upload the transparent-background fish to an image-to-video AI tool.

**Recommended: Runway Gen-3 Alpha**
- Supports Motion Brush — paint specific regions to animate
- Paint gills, pectoral fins, dorsal fin, tail
- Leave body, head, eyes static

**Prompt:**
> subtle breathing, gentle gill pulsing, slight dorsal fin sway, barely perceptible tail beat, otherwise perfectly still, aquarium ambient light

**Settings:**
- Duration: 3-4 seconds (will loop)
- Generate several variations and pick the most natural

**Alternatives if Runway doesn't nail fish anatomy:**
- **Kling 2.0** — competitive quality, sometimes better on non-human subjects
- **Hailuoai MiniMax** — free tier available
- **Wan-Alpha v2.0** — open-source, can generate with alpha channel directly (skip Step 3)

### Step 3: Remove background from video

If the AI video output has a background (most tools add one), remove it.

**Tools:**
- videobgremover.com
- Adobe Express
- CapCut AI background remover

**Export as:** video with alpha channel (ProRes 4444, or any format ffmpeg can read).

**Skip this step** if using Wan-Alpha v2.0 (generates RGBA natively).

### Step 4: Convert to web formats

Run the conversion script from the repo root:

```bash
./scripts/prep-logo-assets.sh <your-video-with-alpha.mov>
```

This produces:
- `bristlenose/theme/images/bristlenose-alive.webm` — VP9 alpha, 160px wide (2x retina)
- `bristlenose/theme/images/bristlenose-alive.mov` — HEVC alpha, 160px wide (2x retina)

**Note:** The HEVC conversion uses `hevc_videotoolbox` (macOS hardware encoder). Only works on Mac. If building on Linux, pre-convert the MOV on a Mac and commit it.

**Target file size:** WebM under 200KB for a 3s loop. If larger, increase CRF (lower quality) or reduce duration.

---

## Iteration workflow

The script overwrites previous output each time. To try a different video:

1. Generate a new AI video (repeat Steps 2-3)
2. Run `./scripts/prep-logo-assets.sh <new-video.mov>`
3. Re-render: `bristlenose render <your-test-folder>`
4. Evaluate: `bristlenose serve <your-test-folder>`
5. Check Chrome, Safari, dark mode, light mode
6. Repeat until the fish feels alive but calm

No code changes needed between iterations — just swap the asset files.

---

## Art direction

**How still is still?** The goal is "AI living portrait energy" — a fish that's alive and chilling in the corner. Not a screensaver, not a GIF. Think:

- Gills pulsing gently (breathing rhythm)
- Pectoral fins with barely perceptible sway
- Dorsal fin with very slight undulation
- Tail with the smallest possible beat
- Body, head, eyes: completely still

The prompt tuning and Motion Brush region selection is where the personality lives. Err on the side of too subtle — you can always increase movement in the next iteration.

**Loop seam:** The 3-4 second clip loops via `<video loop>`. A visible seam (jump cut) breaks the illusion. Look for this when evaluating — the start and end frames should blend smoothly. Some AI tools handle this better than others.

---

## Architecture

### Comment-marker injection

The same pattern used for React islands. Static render writes:

```html
<!-- bn-logo -->
<a href="#project" class="report-logo-link" ...>
<img class="report-logo" src="assets/bristlenose-logo-transparent.png" alt="Bristlenose logo">
</a>
<!-- /bn-logo -->
```

Serve mode's `_transform_report_html()` in `app.py` swaps the markers for:

```html
<!-- bn-logo -->
<a href="#project" class="report-logo-link" ...>
<video class="report-logo" autoplay loop muted playsinline
       poster="assets/bristlenose-logo-transparent.png">
  <source src="assets/bristlenose-alive.webm" type="video/webm">
  <source src="assets/bristlenose-alive.mov" type="video/quicktime">
  <img class="report-logo" src="assets/bristlenose-logo-transparent.png" alt="Bristlenose logo">
</video>
</a>
<!-- /bn-logo -->
```

**Conditional:** Only injects `<video>` if `bristlenose-alive.webm` exists on disk. No video file = static `<img>` stays.

### Browser fallback chain

1. Browser supports WebM VP9 alpha → plays `.webm`
2. Browser supports HEVC alpha (Safari) → plays `.mov`
3. Browser supports `<video>` but neither codec → shows `poster` (transparent PNG)
4. Browser doesn't support `<video>` → shows `<img>` fallback inside `<video>` tag

### Accessibility

- **`prefers-reduced-motion: reduce`**: JS listener pauses the video on page load. `matchMedia("change")` handler resumes if preference changes. Implemented in both `settings.js` (vanilla JS path) and `SettingsPanel.tsx` (React island)
- **Print**: `video.report-logo { display: none }` in `@media print` — static render is the print path anyway

### Dark mode

Transparent PNG composites cleanly on both light and dark backgrounds. The old system is eliminated:
- ~~`bristlenose-dark.png`~~ — kept for backward compat but unused by new templates
- ~~`<picture><source media="(prefers-color-scheme: dark)">`~~ — replaced by plain `<img>`
- ~~`mix-blend-mode: lighten`~~ — removed from `logo.css`
- ~~`_updateLogo()` DOM manipulation~~ — gutted to reduced-motion only

---

## File map

| File | Role |
|------|------|
| `bristlenose/theme/images/bristlenose-transparent.png` | Source transparent logo (committed) |
| `bristlenose/theme/images/bristlenose-alive.webm` | Source animated logo, WebM (committed) |
| `bristlenose/theme/images/bristlenose-alive.mov` | Source animated logo, MOV (committed) |
| `bristlenose/output_paths.py` | `logo_transparent_file`, `logo_video_webm`, `logo_video_mov` properties |
| `bristlenose/stages/render_html.py` | Constants, copy logic, `has_transparent_logo` template var |
| `bristlenose/theme/templates/report_header.html` | `<!-- bn-logo -->` markers, transparent PNG preferred |
| `bristlenose/theme/templates/footer.html` | Plain `<img>` with transparent PNG (no video) |
| `bristlenose/server/app.py` | `_video_logo_html()`, `re.sub` in both transform functions |
| `bristlenose/theme/atoms/logo.css` | `video.report-logo` styles, print hide, no mix-blend-mode |
| `bristlenose/theme/js/settings.js` | Simplified `_updateLogo()`, reduced-motion listener |
| `frontend/src/islands/SettingsPanel.tsx` | Simplified `updateLogo()`, reduced-motion `useEffect` |
| `scripts/prep-logo-assets.sh` | ffmpeg WebM VP9 alpha + MOV HEVC alpha conversion |
| `tests/test_dark_mode.py` | Logo marker, transparent PNG, no mix-blend-mode tests |

---

## Verification checklist

1. `pytest tests/` — all pass
2. `ruff check .` — clean
3. `bristlenose serve <folder>` — logo animates in Chrome, Firefox, Safari
4. Toggle dark mode in Settings — fish composites cleanly on dark background
5. `bristlenose render <folder>` — logo is static transparent PNG (no `<video>`)
6. Open rendered HTML from disk (`file://`) — transparent PNG on both light and dark
7. DevTools → Rendering → `prefers-reduced-motion: reduce` — video paused, poster frame shown
8. Print from serve mode — video hidden (acceptable, static export is the print path)
9. Open a pre-existing report in serve mode — old logo still works (no markers = no injection)
10. File size: WebM should be under 200KB

---

## Future

- **Full 3D fish behaviour**: This animated portrait is a stepping stone. Commissioning proper 3D modelling + rigging would give interactive behaviour (follows cursor, reacts to scroll, idles differently). That's a separate project
- **APNG for static render**: Extract frames from video → assemble as APNG (~300-800KB). Would bring animation to the offline HTML report too. Not planned yet
- **Manual keyframe override**: Let the user scrub to a specific frame as the poster image. Like Dovetail's thumbnail picker
