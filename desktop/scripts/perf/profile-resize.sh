#!/bin/bash
# Records a Time Profiler trace of a real, scripted window drag and summarises it.
#
#   profile-resize.sh <path/to/Bristlenose.app> <label> [seconds=10] [outdir=/tmp/bn-perf]
#   BN_STUDY="ikea research" BN_LENS=Quotes   which sidebar row and lens to show (substring)
#   the study must be one with a report; the script stops if no web area renders
#
# Launches a NEW copy of the app against an already-running `bristlenose serve --dev` on
# BRISTLENOSE_DEV_EXTERNAL_PORT (default 8484; Debug builds only), so every run shows the
# same report and no sidecar is spawned. Drags the window edge with a real mouse
# (resize-drag.swift) while `xctrace` is attached, quits the copy, and writes
# <outdir>/<label>.json. Compare runs with: summarise-trace.py --compare a.json b.json
#
# It moves the real pointer for `seconds` and needs Accessibility trust: run it when nobody
# is at the Mac. Never run two at once. Debug numbers are inflated: compare Debug to Debug.
set -u
APP=${1:?app path}; LABEL=${2:?label}; SECS=${3:-10}; OUT=${4:-/tmp/bn-perf}
HERE=$(cd "$(dirname "$0")" && pwd); PORT=${BRISTLENOSE_DEV_EXTERNAL_PORT:-8484}
mkdir -p "$OUT"; BIN="$OUT/bin"; mkdir -p "$BIN"
die() { echo "profile-resize: $*" >&2; exit 1; }
curl -fsS -o /dev/null "http://127.0.0.1:$PORT/report/" || die "no serve on :$PORT (start: bristlenose serve --dev <project>)"
for t in resize-drag select-study; do
  [ -x "$BIN/$t" ] && [ "$BIN/$t" -nt "$HERE/$t.swift" ] || swiftc -O "$HERE/$t.swift" -o "$BIN/$t" || die "could not build $t"
done
STUDY=${BN_STUDY:-Talismanic}; LENS=${BN_LENS:-Quotes}
APP=$(cd "$APP" 2>/dev/null && pwd -P) || die "no such app"   # /tmp is /private/tmp to the process list
EXE="$APP/Contents/MacOS/Bristlenose"; [ -x "$EXE" ] || die "no executable at $EXE"
[ -z "$(pgrep -f "$EXE")" ] || die "a copy of $APP is already running"

open -n --env BRISTLENOSE_DEV_EXTERNAL_PORT="$PORT" "$APP" || die "open failed"
PID=""; for _ in $(seq 1 60); do
  PID=$(pgrep -f "$EXE" | head -1); [ -n "$PID" ] && break; sleep 0.5; done
[ -n "$PID" ] || die "app did not start"
trap 'pkill -f "$EXE" 2>/dev/null' EXIT
sleep 6   # window up
# A copy opens on Welcome with no report: a profile of that measures a sidebar and no page.
SEL=$("$BIN/select-study" "$PID" "$STUDY" --wait-web); echo "$LABEL study: $SEL"
echo "$SEL" | grep -q '"ok":true' || die "could not select a study ($SEL)"
sleep 3; "$BIN/select-study" "$PID" "$LENS" --wait-web >/dev/null || die "no report after choosing lens $LENS"
sleep 6   # report loaded, startup work settled

rm -rf "$OUT/$LABEL.trace"
xcrun xctrace record --attach "$PID" --template 'Time Profiler' --time-limit "$((SECS + 4))s" \
  --output "$OUT/$LABEL.trace" --no-prompt > "$OUT/$LABEL.xctrace.log" 2>&1 &
XT=$!; sleep 2
DRAG=$("$BIN/resize-drag" "$PID" "$SECS" 900 1500 120)
echo "$LABEL drag: $DRAG"
wait "$XT"
pkill -f "$EXE" 2>/dev/null; trap - EXIT
[ -d "$OUT/$LABEL.trace" ] || die "no trace written (see $OUT/$LABEL.xctrace.log)"
python3 "$HERE/summarise-trace.py" "$OUT/$LABEL.trace" --json "$OUT/$LABEL.json" > /dev/null || die "summarise failed"
python3 - "$OUT/$LABEL.json" "$LABEL" "$DRAG" <<'PY'
import json, sys
p, label, drag = sys.argv[1:4]
d = json.load(open(p)); d["label"] = label
try: d["drag"] = json.loads(drag)
except Exception: d["drag"] = {"raw": drag}
json.dump(d, open(p, "w"), indent=1)
k = d["drag"]
print(f'{label}: {k.get("updates_per_s","?")} size updates/s (gap p95 {k.get("gap_p95_ms","?")} ms), main busy {d["main_busy_ms"]} ms, WebKit frames {d["frames_ms"].get("WebKit frames (any)","?")} ms')
PY
