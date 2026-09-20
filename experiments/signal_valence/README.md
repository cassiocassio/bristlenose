# Signal-card valence — mockup source

Generates `docs/mockups/signal-card-valence.html` (13 Sep 2026).

    .venv/bin/python -c "from bristlenose.stages.s12_render.theme_assets import load_default_css; \
        open('experiments/signal_valence/theme.css','w').write(load_default_css())"
    .venv/bin/python experiments/signal_valence/build.py     # run from the repo root

- `cards.json` — 34 elaborated cards harvested from `trial-runs/*/…/bristlenose.db`
  (`elaboration_caches` joined back to each card's own quotes). The page's *measurements*
  are over all 91 elaborated cards in those databases; the 34 are the ones that could also
  be resolved to quotes, and so are what gets drawn.
- `page.css` — mockup chrome plus the eleven candidate valence treatments.
- `theme.css` — baked from `bristlenose/theme`; regenerate as above, not by hand.

`trial-runs/` is gitignored, so `cards.json` is kept here to make the page rebuildable
without the source projects. It contains participant quotes from trial studies — do not
copy it anywhere shareable.
