# Thematic Analysis Spike

Sibling exploration of options A–E (plus baseline) for thematic
analysis, run side-by-side over two corpora drawn from existing
trial-run output:

- **fossda-opensource** (oral histories, 100-quote random sample, all quote types pooled)
- a second private think-aloud corpus (UX, 67 quotes, all types pooled)

Output is `output/<corpus>/compare.html` for human reading.

## Boundary

This is **throwaway research code**. It does not modify the shipping
product. It reads `extracted_quotes.json` from existing trial-run
output read-only and writes only into `output/`. It does not import
from `bristlenose/`.

It does install two extra packages into the dev venv
(`scikit-learn`, `sentence-transformers`); this is venv-only and the
venv is gitignored, so the shipping wheel is unaffected.

## Run

```sh
cd /Users/cassio/Code/bristlenose
.venv/bin/python experiments/thematic-spike/run_all.py
```

Cost (Sonnet 4.5 at $3 in / $15 out per MTok): ~$3.80 for both corpora.

## Layout

```
experiments/thematic-spike/
├── README.md           — this file
├── lib.py              — shared: Quote, ThemeSet, LLM wrapper, embeddings
├── corpus.py           — load + sample quotes from existing run output
├── prompts.py          — all prompts for the prototypes
├── prototypes/
│   ├── baseline.py     — current s11-style single call (control)
│   ├── option_a.py     — embed → agglomerative cluster → LLM-name per cluster
│   ├── option_b.py     — per-quote codes → cluster codes → name per code-cluster
│   ├── option_c.py     — map-reduce: per-participant themes → merge → reassign
│   ├── option_d.py     — iterative two-pass: draft → review/refine
│   └── option_e.py     — self-consistency: 5× baseline → stable-theme reconciliation
├── render.py           — build compare.html from saved theme JSONs
├── run_all.py          — driver: corpus → all 6 prototypes → render → both corpora
└── output/
    └── <corpus>/{corpus.json, themes_*.json, compare.html, run.log}
```

## Read

`compare.html` shows six columns side by side. Each theme card shows
the label, description, participant count, quote count, and the
assigned quotes. Below the columns: a 6×6 overlap matrix (cosine
similarity of theme labels) and grain metrics (theme count, mean
quotes/theme, distribution).

The accompanying survey + option discussion is parked outside the
repo with the rest of the planning notes.
