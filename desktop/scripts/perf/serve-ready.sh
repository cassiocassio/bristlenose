#!/bin/bash
# How long the bundled sidecar takes to serve a study: the app's own `serve-ready` signpost
# (spawn -> port answering), cold and warm, with the app's sidecar swapped for A/B.
#
#   serve-ready.sh <template.app> <label> [cold=5] [warm=5] [outdir=/tmp/bn-perf]
#
# <template.app> is a Debug-signed Bristlenose.app whose Contents/Resources/bristlenose-sidecar
# is the one under test. COLD = a fresh copy of the template per run (the kernel has never
# validated those files: the first-exec code-signature cost the desktop notes describe);
# WARM = relaunches of the last copy. Each run launches the copy WITHOUT the dev-server flag, so
# it starts its own sidecar, selects a study with a report (BN_STUDY, default Talismanic), waits
# for the web area, and reads the signposts back with `log stream --signpost`.
# Never run two at once: it launches app copies and presses their sidebar through Accessibility.
set -u
TEMPLATE=${1:?template app}; LABEL=${2:?label}; COLD=${3:-5}; WARM=${4:-5}; OUT=${5:-/tmp/bn-perf}
HERE=$(cd "$(dirname "$0")" && pwd); STUDY=${BN_STUDY:-Talismanic}
mkdir -p "$OUT/bin"; BIN="$OUT/bin"
[ -x "$BIN/select-study" ] && [ "$BIN/select-study" -nt "$HERE/select-study.swift" ] \
  || swiftc -O "$HERE/select-study.swift" -o "$BIN/select-study" || { echo "cannot build select-study" >&2; exit 1; }
RUN=/tmp/bn-ab-run.app
: > "$OUT/$LABEL.runs"

one() { # kind index
  local kind=$1 i=$2 exe pid slog
  slog="$OUT/$LABEL.$kind$i.log"
  exe=$(cd "$RUN" && pwd -P)/Contents/MacOS/Bristlenose
  [ -z "$(pgrep -f "$exe")" ] || { echo "a copy is already running" >&2; return 1; }
  /usr/bin/log stream --predicate 'subsystem == "app.bristlenose" AND category == "perf"' --signpost --level debug --style compact > "$slog" 2>&1 &
  local lp=$!; sleep 2
  open -n "$RUN"
  for _ in $(seq 1 40); do pid=$(pgrep -f "$exe" | head -1); [ -n "$pid" ] && break; sleep 0.5; done
  sleep 6
  "$BIN/select-study" "$pid" "$STUDY" --wait-web=180 > /dev/null
  for _ in $(seq 1 60); do grep -q "end\] serve-ready" "$slog" && break; sleep 1; done
  sleep 2; pkill -f "$exe" 2>/dev/null; sleep 2; kill "$lp" 2>/dev/null
  python3 - "$slog" "$kind" "$OUT/$LABEL.runs" <<'PY'
import re, sys
log, kind, out = sys.argv[1:4]
t = lambda s: sum(float(x) * m for x, m in zip(s.split(":"), (3600, 60, 1)))
begins, ends = {}, {}
for l in open(log):
    m = re.match(r"\S+ ([\d:.]+) +Sp .*\[spid (0x[0-9a-f]+), process, +(begin|end)\] ([a-z-]+)", l)
    if m: (begins if m[3] == "begin" else ends)[(m[2], m[4])] = t(m[1])
def dur(name):
    for (sp, n), b in begins.items():
        if n == name and (sp, n) in ends: return round((ends[(sp, n)] - b) * 1000)
open(out, "a").write(f'{kind} {dur("serve-ready")} {dur("project-select")}\n')
print(kind, "serve-ready", dur("serve-ready"), "ms; project-select", dur("project-select"), "ms")
PY
}

for i in $(seq 1 "$COLD"); do rm -rf "$RUN"; ditto "$TEMPLATE" "$RUN"; one cold "$i"; done
for i in $(seq 1 "$WARM"); do one warm "$i"; done
rm -rf "$RUN"
python3 - "$OUT/$LABEL.runs" "$LABEL" <<'PY'
import statistics as st, sys
rows = [l.split() for l in open(sys.argv[1]) if l.strip()]
for kind in ("cold", "warm"):
    v = [int(r[1]) for r in rows if r[0] == kind and r[1] != "None"]
    p = [int(r[2]) for r in rows if r[0] == kind and r[2] != "None"]
    if v: print(f'{sys.argv[2]:>8} {kind}: serve-ready median {st.median(v)} ms (n={len(v)}, min {min(v)}, max {max(v)}); project-select median {st.median(p) if p else "-"} ms')
PY
