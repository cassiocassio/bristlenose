#!/usr/bin/env bash
# Rasterise the synthetic detail-pane SVG mockups to PNG "screenshots".
#
# macOS-only: uses qlmanage (Quick Look) — the only rasteriser guaranteed present
# on a dev Mac (no rsvg-convert / cairosvg / ImageMagick assumed). The generator
# emits a *square* canvas on purpose so Quick Look's square thumbnail doesn't crop
# the landscape window. Re-run after editing generate.py.
set -euo pipefail
cd "$(dirname "$0")"

python3 generate.py

SIZE="${1:-1600}"          # long-edge px; override: ./render-png.sh 2000
mkdir -p png
rm -f png/*.png
for f in svg/*.svg; do
  qlmanage -t -s "$SIZE" -o png "$f" >/dev/null 2>&1 || true
done
# qlmanage writes "<name>.svg.png" — normalise to "<name>.png"
for p in png/*.svg.png; do
  [ -e "$p" ] && mv -f "$p" "${p%.svg.png}.png"
done

# qlmanage forces a square thumbnail, so the landscape window sits in a tall
# square with gradient letterbox top/bottom. Crop centred back to landscape
# (the window content is centred in the square) — leaves a thin desktop margin.
CH=$(python3 -c "print(round($SIZE * 0.74375))")
for p in png/*.png; do
  sips -c "$CH" "$SIZE" "$p" >/dev/null 2>&1 || true
done
echo "rendered $(ls png/*.png 2>/dev/null | wc -l | tr -d ' ') PNGs at ${SIZE}x${CH}px"
