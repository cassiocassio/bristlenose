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
# BN_APP_ENV="BRISTLENOSE_STARTUP_TRACE=1" also reports the sidecar's own start stages (Debug builds).
# Never run two at once: it launches app copies and presses their sidebar through Accessibility.
set -u
TEMPLATE=${1:?template app}; LABEL=${2:?label}; COLD=${3:-5}; WARM=${4:-5}; OUT=${5:-/tmp/bn-perf}
HERE=$(cd "$(dirname "$0")" && pwd); STUDY=${BN_STUDY:-Talismanic}
mkdir -p "$OUT/bin"; BIN="$OUT/bin"
[ -x "$BIN/select-study" ] && [ "$BIN/select-study" -nt "$HERE/select-study.swift" ] \
  || swiftc -O "$HERE/select-study.swift" -o "$BIN/select-study" || { echo "cannot build select-study" >&2; exit 1; }
RUN=/tmp/bn-ab-run.app
: > "$OUT/$LABEL.runs"; : > "$OUT/$LABEL.steps.jsonl"

one() { # kind index
  local kind=$1 i=$2 exe pid slog
  slog="$OUT/$LABEL.$kind$i.log"
  exe=$(cd "$RUN" && pwd -P)/Contents/MacOS/Bristlenose
  [ -z "$(pgrep -f "$exe")" ] || { echo "a copy is already running" >&2; return 1; }
  /usr/bin/log stream --predicate 'subsystem == "app.bristlenose" AND category == "perf"' --signpost --level debug --style compact > "$slog" 2>&1 &
  local lp=$!; sleep 2
  local extra=(); [ -n "${BN_APP_ENV:-}" ] && extra=(--env "$BN_APP_ENV")
  open -n ${extra[@]+"${extra[@]}"} "$RUN"
  for _ in $(seq 1 40); do pid=$(pgrep -f "$exe" | head -1); [ -n "$pid" ] && break; sleep 0.5; done
  sleep 6
  "$BIN/select-study" "$pid" "$STUDY" --wait-web=180 > /dev/null
  for _ in $(seq 1 60); do grep -q "end\] serve-ready" "$slog" && break; sleep 1; done
  sleep 2; pkill -f "$exe" 2>/dev/null; sleep 2; kill "$lp" 2>/dev/null
  python3 - "$slog" "$kind" "$OUT/$LABEL.runs" "$OUT/$LABEL.steps.jsonl" <<'PY'
import json, re, sys, time
log, kind, out, steps_out = sys.argv[1:5]
t = lambda s: sum(float(x) * m for x, m in zip(s.split(":"), (3600, 60, 1)))
begins, ends, events, stages, epoch_of = {}, {}, {}, {}, {}
for l in open(log):
    m = re.match(r"(\d{4}-\d\d-\d\d) ([\d:.]+) +Sp .*\[spid (0x[0-9a-f]+|excl), process, +(begin|end|event)\] ([a-z-]+)(?:: (.*))?", l)
    if not m: continue
    when = t(m[2])
    day = time.mktime(time.strptime(m[1], "%Y-%m-%d"))
    if m[4] == "event" and m[5] == "sidecar-stage":
        name, ms = m[6].split()[:2]; stages.setdefault(name, int(ms) / 1000.0)   # sidecar's own clock, epoch seconds
    elif m[4] == "event":
        events.setdefault(m[6], when); epoch_of.setdefault(m[6], day + when)
    else: (begins if m[4] == "begin" else ends)[(m[3], m[5])] = when
def span(name):
    for (sp, n), b in begins.items():
        if n == name and (sp, n) in ends: return b, ends[(sp, n)]
    return None, None
ps_b, ps_e = span("project-select"); sr_b, sr_e = span("serve-ready")
pts = [("click", ps_b), ("spawn requested", sr_b), ("process spawned", events.get("serve-spawned")),
       ("sidecar port line", events.get("serve-port-parsed")), ("port answering", sr_e),
       ("health answered", events.get("serve-health-answered")), ("web view load started", events.get("webview-load-started")),
       ("web view did finish", events.get("webview-did-finish")), ("report ready", ps_e)]
seg = {}
for (a, ta), (b, tb) in zip(pts, pts[1:]):
    seg[f"{a} -> {b}"] = round((tb - ta) * 1000) if ta is not None and tb is not None else None
total = round((ps_e - ps_b) * 1000) if ps_b and ps_e else None
spawn = epoch_of.get("serve-spawned")
stage_ms = {k: round((v - spawn) * 1000) for k, v in stages.items()} if spawn else {}
open(out, "a").write(f"{kind} {round((sr_e - sr_b) * 1000) if sr_b and sr_e else None} {total}\n")
open(steps_out, "a").write(json.dumps({"kind": kind, "segments": seg, "total": total, "stages": stage_ms}) + "\n")
print(kind, "project-select", total, "ms:", seg)
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
python3 - "$OUT/$LABEL.steps.jsonl" "$LABEL" <<'PY'
import json, statistics as st, sys
rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
if rows:
    names = list(rows[0]["segments"])
    print(f"\n{sys.argv[2]}: median ms per part of project-select, over {len(rows)} runs")
    for n in names:
        v = [r["segments"][n] for r in rows if r["segments"][n] is not None]
        if v: print(f"  {n:46} {int(st.median(v)):>6}   (min {min(v)}, max {max(v)})")
    v = [r["total"] for r in rows if r["total"]]
    print(f'  {"TOTAL click -> report ready":46} {int(st.median(v)):>6}')
    order = []
    for r in rows:
        for k in r.get("stages", {}):
            if k not in order: order.append(k)
    if order:
        print(f"\n{sys.argv[2]}: the sidecar's own stages, ms after the app spawned it (median over runs that reported)")
        for k in order:
            v = [r["stages"][k] for r in rows if k in r.get("stages", {})]
            print(f"  {k:46} {int(st.median(v)):>6}   (n={len(v)}, min {min(v)}, max {max(v)})")
PY
