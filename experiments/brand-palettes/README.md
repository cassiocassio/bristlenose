# Brand palettes

`gen.py` writes `bristlenose/theme/colors/palette-{catppuccin,gruvbox,rose-pine,solarized}.css`
and `docs/mockups/palette-gallery.html` from the official brand colours in `palettes.py`.

Colours a brand names are used verbatim. Every other token is a mix of those, following the
relationships in `palette-default.css`. A colour used as text that fails WCAG AA is darkened
(light) or lightened (dark) until it passes, keeping its hue; each palette file's header lists
the nudges.

Retune here, not in the CSS:

```bash
.venv/bin/python experiments/brand-palettes/gen.py
```

Then regenerate the welcome screen's copy (`scripts/gen-welcome-timeline.py`).

## The workbench: iterate on a palette without picking colours one at a time

`workbench.py` is for nudging a palette you already have (Edo) into one you can live with for
years. Nothing it makes touches the shipped palette until you `promote` it.

```bash
.venv/bin/python experiments/brand-palettes/workbench.py serve      # the live lab
```

The lab shows REAL rendered report pages (from `trial-runs/`, local only, never committed), light
and dark side by side, recoloured live. The sliders are *knobs*: each moves a whole family of
tokens together in OKLCH, relative to the base (paper hue and chroma, ground lightness, how far
cards sit off the page, ink, accent, signal colours), so the palette's own relationships survive.
Hold **Compare** to flash the base; the colour-vision menu simulates deuteranopia, protanopia and
tritanopia on the real page. A contrast guard keeps text pairs at their targets and says what it
moved. The side panel reads the type hierarchy: WCAG ratio, APCA Lc, and the body-to-muted step.

Other commands: `snapshot edo v1` (freeze what ships), `list`, `show`, `diff a b` (changed tokens
with OKLab distance), `lab a b ...` (static side-by-side page), `site <name>` (the website's colour
block, mapped from the same tokens), `check` (shipped file equals what it was promoted from),
`promote <name> --as edo` (writes the CSS and the native colorsets; refuses failing text pairs).

`knobs.mjs` is the single implementation, run in the browser by the lab and under node by the CLI.
`table.py` reads and writes the shipped CSS; `tests/test_palette_workbench.py` pins that both
round-trip and that neutral knobs change nothing. Still owed after a promote: regenerate the
welcome timeline and the hard-coded Edo hex listed in `docs/private/branding-scorecard.md` §3.
