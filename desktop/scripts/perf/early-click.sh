#!/bin/bash
# The earliest possible click: poll for the sidebar from launch and select the study the instant it
# exists, standby off and on, interleaved. A restored window starts its sidecar about as soon as its
# window exists, so the time from the `launch-to-ready` signpost to `serve-ready` begin is a proxy
# for t_w (docs/design-standby-sidecar.md). It also shows whether an early spare slows an early start.
# Needs the compiled `select-study` (serve-ready.sh builds it into <outdir>/bin).
#
#   APP=<Bristlenose.app> STUDY_DIR=<study folder> BN_STUDY=<sidebar name> BIN=<dir with select-study> REPS=6 early-click.sh
set -u
APP=${APP:?path to the Debug Bristlenose.app}
STUDY_DIR=${STUDY_DIR:?the study folder the sidebar row points at}
BN_STUDY=${BN_STUDY:?sidebar row name}
BIN=${BIN:?directory holding the compiled select-study}
RUN=/tmp/bn-ab-run.app
OUT=${OUT:-/tmp/bn-perf/early}; rm -rf $OUT; mkdir -p $OUT
L=$STUDY_DIR/bristlenose-output/.bristlenose
base=$(wc -l < $L/llm-calls.jsonl | tr -d ' ')
exe="$(rm -rf $RUN; ditto $APP $RUN; cd $RUN && pwd -P)/Contents/MacOS/Bristlenose"
now_ms() { python3 -c 'import time;print(int(time.time()*1000))'; }
rep() { # arm env n
  local log=$OUT/$1-$3.log
  /usr/bin/log stream --predicate 'subsystem == "app.bristlenose" AND category == "perf"' --signpost --level debug --style compact > $log 2>&1 &
  local lp=$!; sleep 2
  local t0; t0=$(now_ms)
  open -n --env "$2" "$RUN"
  local pid=""; for _ in $(seq 1 100); do pid=$(pgrep -f "$exe" | head -1); [ -n "$pid" ] && break; sleep 0.05; done
  local tclick=""
  for _ in $(seq 1 300); do
    if "$BIN/select-study" "$pid" "$BN_STUDY" >/dev/null 2>&1; then tclick=$(now_ms); break; fi
    sleep 0.05
  done
  echo "$1 $3 click_after_open_ms=$(( ${tclick:-0} - t0 ))" >> $OUT/clicks.txt
  for _ in $(seq 1 40); do grep -q "end\] serve-ready" $log && break; sleep 1; done
  sleep 3; pkill -f "$exe" 2>/dev/null; sleep 2; kill $lp 2>/dev/null
  echo "$(date +%H:%M:%S) $1 rep$3 load=$(uptime | sed 's/.*averages: //' | awk '{print $1}') calls=$(( $(wc -l < $L/llm-calls.jsonl | tr -d ' ') - base ))" >> $OUT/loadlog.txt
}
: > $OUT/clicks.txt; : > $OUT/loadlog.txt
for r in $(seq 1 ${REPS:-6}); do
  if [ $((r % 2)) -eq 1 ]; then A=off; B=on; else A=on; B=off; fi
  for a in $A $B; do
    [ "$(( $(wc -l < $L/llm-calls.jsonl | tr -d ' ') - base ))" -gt 0 ] && { echo SPEND >> $OUT/loadlog.txt; echo STOP > $OUT/STOP; }
    [ -f $OUT/STOP ] && break 2
    if [ $a = off ]; then rep off BRISTLENOSE_STANDBY=0 $r; else rep on BRISTLENOSE_STANDBY=1 $r; fi
  done
done
rm -rf $RUN
echo ALLDONE >> $OUT/loadlog.txt
