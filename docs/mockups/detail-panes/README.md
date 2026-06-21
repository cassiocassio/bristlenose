# Detail-pane mockups

Synthetic mockups of every macOS detail-pane state. **The catalogue, audit tables,
and design synthesis live in [`docs/design-detail-panes-catalogue.md`](../../design-detail-panes-catalogue.md)** —
start there.

- `generate.py` — emits `svg/*.svg` (one frame per state). Pure stdlib. Edit the
  `build()` catalogue to add/change frames.
- `render-png.sh` — rasterises `svg/` → `png/` via macOS Quick Look.
- `svg/` — vector source (Figma-importable).
- `png/` — rasterised "screenshots" (embedded by the catalogue).

These are *synthetic* — drawn from the real code paths and copy, not live screen
captures (the SwiftUI panes need the signed sidecar + sandbox stack). Source of
truth for behaviour is the code; these are a design aid for seeing the whole set at
once. Throwaway design artifact — tracked, never shipped.

Regenerate everything:

```sh
./render-png.sh          # runs generate.py then qlmanage
```
