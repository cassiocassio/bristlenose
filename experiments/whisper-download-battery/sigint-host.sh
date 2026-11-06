#!/bin/bash
# sigint-host.sh <label> <cmd…> — start a fetch into a throwaway cache, SIGINT the TOP pid at 300 MB, time the stop.
# `set -m` matters: without job control a background job starts with SIGINT ignored and nothing stops.
set -m
label=$1; shift
T=$(mktemp -d "${TMPDIR:-/tmp}/hfi.XXXX"); export HF_HOME=$T HF_HUB_DISABLE_PROGRESS_BARS=1
"$@" >$T.log 2>&1 & p=$!
for i in $(seq 1 400); do s=$(du -sm $T | cut -f1); [ "$s" -ge 300 ] && break; kill -0 $p 2>/dev/null || break; sleep 0.25; done
t0=$(date +%s); kill -INT $p
for i in $(seq 1 360); do kill -0 $p 2>/dev/null || break; sleep 0.5; done
echo "[$label] stopped_in=$(( $(date +%s)-t0 ))s cache_after=$(du -sm $T | cut -f1)MB partials=$(find $T -name '*.incomplete' | wc -l | tr -d ' ')"
pkill -9 -P $p 2>/dev/null; kill -9 $p 2>/dev/null; rm -rf $T $T.log
