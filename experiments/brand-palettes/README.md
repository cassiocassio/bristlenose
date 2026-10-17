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
