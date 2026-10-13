# Screens lens

Can the screen-text index tell which screens participants visited, in what order, and which quotes
were said on each? Measured 13 Oct 2026 on the two real sessions the screen-text spike used. The
proposal is [`docs/design-screens-lens.md`](../../docs/design-screens-lens.md); the prior-art survey
is [`prior-art.md`](prior-art.md); this file is the method and the numbers.

Everything these scripts write (visits, contact sheets, labels) goes in the gitignored private
trial-data folder beside the screen-text spike's outputs, because it holds participants' screens and
speech. This README holds aggregates only, plus URL templates of a public website.

## Files

| File | What it does |
|---|---|
| `visits.py` | Reads the screen-text spike's dense sweep (Vision accurate every 2 s) and cuts each session into **visits**: runs of share frames whose content lines stay within Jaccard 0.6 of the visit's first frame. Per visit: the address-bar URL (whole-line URL in the top 15% of the share area; scheme and query dropped, `#route` kept), a template (product slugs and ids masked), the browser's link-hover URL if any, line and token sets after word-at-position stickiness, the tallest line, dHash of the share area, and the first and last frames' lines with positions. `--sheets` draws numbered contact sheets for hand-labelling. Needs Pillow (a scratch venv) |
| `identity.py` | Scores eight "same page?" signals and the URL-else-text combination against hand labels: ROC AUC, best F1, and average-linkage clustering at the best threshold (cluster count, adjusted Rand index). Also the same signals on same-page pairs for the **state** question (dialogs, panels) |
| `states.py` | An overlay rule for states: the page underneath stays put (≥ 35% of the previous frame's lines retained at the same place), and new lines arrive in a compact box (≤ 45% of the frame) |
| `flows.py` | Page sequences (repeats merged, revisits, back-steps), cross-session alignment by URL template with the locale prefix dropped, quotes against page intervals, report-section purity against the page on screen, and speech `screen_change` boundaries against observed transitions |

Labels (`screens/labels.json`, private) were written by looking at every visit's middle frame on the
contact sheets, before scoring: a **page** for each visit (what a sitemap node would be) and a
**state** (the page plus any dialog, panel or drop-down over it). One labeller.

## Material

The screen-text spike's two sessions: a 38-minute German IKEA session (share from 16:06, Chrome) and
an 18-minute UK IKEA session (share from 7:10, Safari), both Teams at 1080p, both browser shares, both
already run through Bristlenose (quotes, sections, topic boundaries). Dense OCR from that spike's
`coverage.py` pass.

## Results

### Visits and pages

| | German | UK |
|---|---|---|
| share frames / with an address-bar URL | 649 / 638 | 330 / 326 |
| visits / median length / ≥ 6 s | 91 / 6 s / 54 | 73 / 2 s / 29 |
| distinct URL (path + #route) | 10 | 12 |
| hand-labelled pages / states | 9 / 21 | 11 / 17 |
| visits with a link-hover URL | 12 | 0 |

### Same page? (`identity.py`)

All pairs of visits within a session (4,095 and 2,628 pairs).

| signal | AUC DE / UK | F1 DE / UK | clusters DE / UK (9 / 11) | ARI DE / UK |
|---|---|---|---|---|
| URL, else TF-IDF | 0.98 / 0.97 | 0.98 / 0.95 | 11 / 12 | 0.98 / 0.96 |
| URL (path + #route) | 0.98 / 0.97 | 0.98 / 0.91 | 14 / 14 | 0.97 / 0.90 |
| URL template | 0.98 / 0.97 | 0.98 / 0.91 | 14 / 14 | 0.97 / 0.90 |
| TF-IDF cosine (IDF over the session's visits) | 0.90 / 0.89 | 0.72 / 0.73 | 11 / 18 | 0.86 / 0.76 |
| token Jaccard | 0.91 / 0.90 | 0.78 / 0.76 | 13 / 19 | 0.77 / 0.77 |
| token overlap (∩ / min) | 0.91 / 0.88 | 0.76 / 0.68 | 13 / 17 | 0.81 / 0.73 |
| line-set Jaccard | 0.88 / 0.89 | 0.77 / 0.75 | 15 / 19 | 0.81 / 0.72 |
| dHash, min over first/middle/last | 0.83 / 0.89 | 0.66 / 0.71 | 29 / 23 | 0.62 / 0.71 |
| tallest line equal | 0.61 / 0.63 | 0.37 / 0.40 | 45 / 39 | 0.33 / 0.35 |

Best thresholds: TF-IDF 0.09 / 0.21, URL-else-TF-IDF 0.25 / 0.30, dHash 0.73.

Two URL-reading traps, both fixed in `visits.py` before these numbers: Safari's bookmark bar has a
title naming a host, which a longest-match rule took for the address (require the whole line to be a
URL); and the link-hover URL starts with `https://`, which an anchored match missed (strip the scheme
first).

### Same state, given the same page?

| | AUC DE / UK |
|---|---|
| every visit-level signal above | 0.45–0.69 / 0.45–0.67 |
| TF-IDF with IDF within the page, tokens | 0.79 / 0.67 (ARI 0.69 / 0.72; page labels alone 0.68 / 0.72) |
| overlay rule (`states.py`) | found 9 of 21 / 4 of 14 overlay visits, flagged 23 / 19 |

When a dialog opened, the page underneath kept 6–64% (German, median 37%) and 45–75% (UK, median
63%) of the previous frame's lines at the same place; every other change within a page ranged 0–100%
(medians 25% and 26%). The ranges overlap, so retention alone cannot separate "a dialog opened" from
"scrolled": the scrim dims text unevenly, and a scrolled list inside a dialog reads as new lines.

### Sequences, quotes, sections (`flows.py`)

| | German | UK |
|---|---|---|
| steps (repeats merged) / revisits / A→B→A | 9 / 0 / 0 | 18 / 7 / 5 |
| URL templates | 9 | 8 |
| quotes extracted / during the share / on a page | 25 / 18 / 18 | 28 / 16 / 16 |
| pages with a quote | 6 of 9 | 8 of 11 |
| report sections / their quotes on the section's top page | 6 / 14 of 17 | 8 / 12 of 15 |
| speech `screen_change` boundaries in the share / near a transition (±30 s) | 4 / 2 | 8 / 6 |
| observed transitions / with a boundary within ±30 s | 8 / 2 | 17 / 16 (8 of the 17 in 44 s) |

Template paths, locale prefix dropped:

- German: `/ → /cat/* → /p/* → /planner-app#/spr → #/planner → #/summary → /shoppingcart → /order/continue → /order/delivery`
- UK: `/ → /cat/* → / → /search → / → /search → /cat/* → /p/* → /shoppingcart → /order/delivery → /shoppingcart → /order/continue → /order/delivery → /order/shipping`
- Shared: 6 templates (`/`, `/cat/*`, `/p/*`, `/shoppingcart`, `/order/continue`, `/order/delivery`),
  4 transitions.

Time on page, top three: German delivery 306 s, cart 296 s, planner 256 s; UK cart 184 s, product
page 130 s, home 106 s.

## Not measured

Window and app shares (no address bar) beyond the text-only rows above; Zoom and Meet layouts; mobile
shares; Figma prototypes; more than two sessions of one study, so whether a "typical order" across
participants is stable is untested; a second labeller; the quote-to-screen lag (no published
measurement either, per the survey).
