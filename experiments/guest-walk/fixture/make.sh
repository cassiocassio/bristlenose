#!/bin/bash
# make.sh <out-dir> — the walk's screens fixture: a 36 s screen-share-style video of
# three web pages (12 s each, 1 fps) with a silent audio track, plus its Zoom-style
# transcript of the same name, so the pipeline pairs them and skips Whisper.
# Small enough to stage nightly (about 100 KB); regenerated, never committed as video.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:?out dir}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$OUT"
swiftc -O "$HERE/render_screens.swift" -o "$TMP/render" 2>/dev/null
"$TMP/render" "$TMP" >/dev/null
printf "file '%s'\nduration 12\n" "$TMP/screen-1.png" "$TMP/screen-2.png" "$TMP/screen-3.png" > "$TMP/list.txt"
printf "file '%s'\n" "$TMP/screen-3.png" >> "$TMP/list.txt"   # concat needs the last frame twice
ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i "$TMP/list.txt" \
  -f lavfi -i anullsrc=channel_layout=mono:sample_rate=16000 -t 36 \
  -vf "fps=1,format=yuv420p" -c:v libx264 -preset veryslow -crf 30 -c:a aac -b:a 16k -shortest \
  "$OUT/Session 1.mp4"
cp "$HERE/Session 1.vtt" "$OUT/Session 1.vtt"
ls -la "$OUT"
