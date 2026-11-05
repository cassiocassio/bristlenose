#!/bin/bash
# Interleaved app A/B of the standby sidecar: OFF (BRISTLENOSE_STANDBY=0) against ON, one cold and one
# warm launch per arm per rep, the order alternating each rep. Reads the app's own signposts through
# serve-ready.sh. Needs a Debug app with a fresh sidecar inside, Accessibility trust, and an otherwise
# idle Mac (README). Stops itself if the study's llm-calls.jsonl grows: a study with no Signals
# snapshot builds one on every launch with the app's real provider, and BN_APP_ENV cannot override it.
#
#   APP=<Bristlenose.app> STUDY_DIR=<study folder> BN_STUDY=<sidebar name> REPS=6 standby-app-ab.sh
set -u
APP=${APP:?path to the Debug Bristlenose.app}
STUDY_DIR=${STUDY_DIR:?the study folder the sidebar row points at}
SR=$(cd "$(dirname "$0")" && pwd)/serve-ready.sh
L=$STUDY_DIR/bristlenose-output/.bristlenose
OUT=${OUT:-/tmp/bn-perf/ab}; mkdir -p $OUT; : > $OUT/loadlog.txt
base=$(wc -l < $L/llm-calls.jsonl | tr -d ' ')
REPS=${REPS:-6}
arm() { # name envvalue rep
  d=$OUT/$1-$3; mkdir -p $d
  echo "$(date +%H:%M:%S) $1 rep$3 load=$(uptime | sed 's/.*averages: //' | awk '{print $1}') calls_spent=$(( $(wc -l < $L/llm-calls.jsonl | tr -d ' ') - base ))" >> $OUT/loadlog.txt
  BN_STUDY=${BN_STUDY:?sidebar row name} BN_APP_ENV="$2" $SR $APP $1 1 1 $d > $d/stdout.txt 2>&1
  now=$(wc -l < $L/llm-calls.jsonl | tr -d ' ')
  if [ "$now" -gt "$base" ]; then echo "SPEND DETECTED after $1 rep$3: $((now-base)) new calls; stopping" >> $OUT/loadlog.txt; echo STOP > $OUT/STOP; fi
}
for r in $(seq 1 $REPS); do
  if [ $((r % 2)) -eq 1 ]; then A=off; B=on; else A=on; B=off; fi
  for a in $A $B; do
    [ -f $OUT/STOP ] && break 2
    if [ $a = off ]; then arm off "BRISTLENOSE_STANDBY=0" $r; else arm on "BRISTLENOSE_STANDBY=1" $r; fi
  done
done
echo ALLDONE >> $OUT/loadlog.txt
