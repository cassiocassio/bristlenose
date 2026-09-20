# Signal-card valence — mockup source

**PARKED, not superseded.** A side branch off generation 3 (13 Sep 2026).
Generation 4 (19–20 Sep) fixed the card's own problems first and deferred
valence; `signal.pattern` still arrives on the wire, so nothing has to be
regenerated when it is picked up. Lineage: `docs/design-signal-card.md` §0
("One side branch"). Register: `docs/mockups/STATUS.md`.

Two of its sections have since been overtaken and are kept as the 13 Sep
record, not as advice — the ribbon on the page says which, and why.

## Build

    .venv/bin/python -c "from bristlenose.stages.s12_render.theme_assets import load_default_css; \
        open('experiments/signal_valence/theme.css','w').write(load_default_css())"
    .venv/bin/python experiments/signal_valence/build.py     # the full page
    .venv/bin/python experiments/signal_valence/wall.py      # the density wall alone

Both run from the repo root.

## What is here, and what is deliberately not

| file | tracked | |
|---|---|---|
| `build.py` | yes | the full page — 11 treatments, the density wall, §9's vocabulary and glyph exploration |
| `wall.py` | yes | the wall on its own, ~15 KB, every mark at the real 11.5px |
| `words.py` | yes | §9's six vocabulary frames and eight glyph families |
| `page.css` | yes | mockup chrome plus the candidate treatments |
| `cards.json` | **no** | 34 elaborated cards harvested from `trial-runs/*/…/bristlenose.db` |
| `theme.css` | **no** | baked from `bristlenose/theme`; regenerate with the command above |

`cards.json` and `theme.css` are gitignored (`.gitignore:195-196`), as are both
output pages (`:203-204`) — they carry verbatim participant quotes from trial
studies, and every signal-card mockup of 19–20 Sep is handled the same way. **So
the repo keeps the recipe, not the artefact:** a fresh clone can read this and
rebuild nothing until it has the trial projects. That is the intended trade, not
a gap. Do not commit `cards.json`, and do not copy it anywhere shareable.

The page's measurements are over all **91** elaborated cards in those databases
(92 by 20 Sep); the 34 in `cards.json` are the ones that could also be resolved
back to their own quotes, and so are what gets drawn.
