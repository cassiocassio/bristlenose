# Codebook audits — the framework YAMLs against their authors' texts

Read-only findings, one file per authored codebook, produced 22 Sep 2026 by
research agents given the YAML and told to read it against the author's own
book, article or site. **Nothing here is implemented.** Each report ends with
a proposed patch and a version string; the decision to apply any of it is the
owner's, and when one is applied it gets a decision register like
`docs/design-codebook-norman.md` and a `renamed_from:` on every renamed tag so
`codebook_sync` migrates installed rows.

Why these exist: the Norman audit (same day, `design-codebook-norman.md`)
found that the February 2026 codebooks had been padded to a fixed number of
tags per group, with the padding invented where the book ran out, and that
some terms were not the author's at all. Garrett and Morville had the same
4-per-group symmetry. The question put to each audit was the one a reader of
the author's table of contents or index would ask: *would they recognise
this?*

| Codebook | Report | Headline | Proposed version |
|---|---|---|---|
| Garrett | [2026-09-22-garrett.md](2026-09-22-garrett.md) | 8 of 20 tags his words, 7 his concepts under our labels (two on the wrong plane), 5 not from the book; description says "mutually exclusive" and "top-down", both the reverse of chapter 2; `jjg.net` link dead | 2.0 |
| Nielsen | [2026-09-22-nielsen.md](2026-09-22-nielsen.md) | 31 of 36 trace to NN/g text; 7 group names silently compressed; 2 tags not his (`mode confusion` is Norman's, `context loss` nobody's); one misfiled, one misnamed; five `not_this` pointers dangling after the Norman rewording; bio says ten heuristics in 1990, there were nine | 2.0 (1.1 if wording-only) |
| Yablonski | [2026-09-22-yablonski.md](2026-09-22-yablonski.md) | bio places him at Google (never); "21 laws from the book" is wrong on both counts (book has 10, site has 30); Hick's Law defined as Choice Overload; `Thaler` tag not on the site; six groups are ours; four `not_this` name tags that do not exist | 2.0 |
| Morville | [2026-09-22-morville.md](2026-09-22-morville.md) | the essay has seven facets and no sub-facets, so 17 of 28 tags are not his (Nielsen's usability attributes, Fogg, Microsoft inclusive design, Cialdini, Tristan Harris); the Valuable facet is inverted from sponsor-side to user-side; proposed 15-tag shape | 2.0 |
| Plato | not audited | the owner's call: it was for fun | — |

Sentiment, UXR and CLI-UX are Bristlenose's own and have no author to be
faithful to; UXR is where useful tags retired from the authored codebooks are
rescued (`exploration`, `first-time use` arrived 22 Sep 2026).
