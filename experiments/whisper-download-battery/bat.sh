#!/bin/bash
# bat.sh <test>… — synthetic failure battery for the Whisper download, run INSIDE a clean Tart guest.
# Prints `RESULT <test> <key>=<value> …` lines (and NOTE lines); it asserts nothing, the host reads it.
# The sidecar under test sits in ~/sc-new (osrun.sh puts it there and re-signs it for ssh use).
SC=$HOME/sc-new/bristlenose-sidecar
CACHE=$HOME/.cache/huggingface
HUB=$CACHE/hub
export PATH=$HOME/bin:$PATH
OUT=$HOME/bat-logs; mkdir -p $OUT

mb()      { du -sm "$1" 2>/dev/null | cut -f1; }
free_mb() { df -m / | awk 'NR==2{print $4}'; }
status()  { $SC doctor --whisper-status 2>/dev/null | awk '/@whisper-status/{print $2}'; }
clean()   { pkill -9 -f bristlenose-sidecar 2>/dev/null; sleep 1; rm -rf "$CACHE" $HOME/fill*; }
partials(){ find "$HUB" -name '*.incomplete' 2>/dev/null | wc -l | tr -d ' '; }
wait_mb() { # wait_mb <mb> <pid> — until the cache holds that much or the pid is gone (max 180 s)
    local i=0; while [ $i -lt 360 ]; do
        [ "$(mb $CACHE)" -ge "$1" ] 2>/dev/null && return 0
        kill -0 "$2" 2>/dev/null || return 1
        sleep 0.5; i=$((i+1)); done; return 2; }
# run_for <secs> <outfile> <cmd…> — run, kill after secs; echo the exit code (or TIMEOUT)
run_for() { local s=$1 f=$2; shift 2; "$@" >"$f" 2>&1 & local p=$!; local i=0
    while kill -0 $p 2>/dev/null && [ $i -lt $((s*2)) ]; do sleep 0.5; i=$((i+1)); done
    if kill -0 $p 2>/dev/null; then pkill -9 -P $p 2>/dev/null; kill -9 $p 2>/dev/null; pkill -9 -f bristlenose-sidecar; echo TIMEOUT; else wait $p; echo $?; fi; }
last() { tail -${2:-2} "$1" | tr '\n' '|' | cut -c1-300; }
peak_watch() { # peak_watch <pid> <file> — samples the cache until the pid exits, writes the max MB
    local m=0 s; while kill -0 "$1" 2>/dev/null; do s=$(mb $CACHE); [ "${s:-0}" -gt "$m" ] && m=$s; sleep 0.3; done; echo $m > "$2"; }

t_info() {
    echo "RESULT info os=$(sw_vers -productVersion) chip=$(sysctl -n machdep.cpu.brand_string) free_mb=$(free_mb) mem_gb=$(( $(sysctl -n hw.memsize)/1073741824 ))"
}
t_cold() { # the first-ever sidecar start on this guest (Gatekeeper scans the onedir)
    local s=$(date +%s); local st=$(status); echo "RESULT cold status=$st secs=$(( $(date +%s)-s ))"
    s=$(date +%s); $SC doctor --mlx-probe >/dev/null 2>&1; echo "RESULT cold probe_exit=$? secs=$(( $(date +%s)-s ))"
}
t_fetch() {
    clean; ( $SC doctor --fetch --progress-lines >$OUT/fetch.log 2>&1; echo $? > $OUT/fetch.rc ) & local p=$!
    sleep 1; local fp=$(pgrep -f "doctor --fetch" | head -1)
    peak_watch ${fp:-$p} $OUT/peak.txt & wait $p
    sleep 1; echo "RESULT fetch rc=$(cat $OUT/fetch.rc) status=$(status) final_mb=$(mb $CACHE) peak_mb=$(cat $OUT/peak.txt) partials=$(partials) last=$(last $OUT/fetch.log 1)"
    $SC doctor --fetch --progress-lines >$OUT/fetch2.log 2>&1; echo "RESULT fetch_again rc=$? last=$(last $OUT/fetch2.log 2)"
}
t_orphan() { # kill -9 mid-download; backdate the partial; refetch
    clean; $SC doctor --fetch --progress-lines >$OUT/o1.log 2>&1 & local p=$!
    wait_mb 400 $p; pkill -9 -f bristlenose-sidecar; sleep 1
    echo "RESULT orphan after_kill partials=$(partials) mb=$(mb $CACHE) status=$(status)"
    find "$HUB" -name '*.incomplete' -exec touch -t 202601010000 {} \;
    $SC doctor --fetch --progress-lines >$OUT/o2.log 2>&1 & p=$!
    sleep 1; local fp=$(pgrep -f "doctor --fetch" | head -1); peak_watch ${fp:-$p} $OUT/peak2.txt & wait $p; local rc=$?
    sleep 1; echo "RESULT orphan refetch rc=$rc status=$(status) final_mb=$(mb $CACHE) peak_mb=$(cat $OUT/peak2.txt) partials=$(partials)"
}
t_orphan_fresh() { # a partial only seconds old is kept at the START of a fetch, then swept once it has SUCCEEDED
    clean; $SC doctor --fetch --progress-lines >$OUT/of1.log 2>&1 & local p=$!
    wait_mb 400 $p; pkill -9 -f bristlenose-sidecar; sleep 1
    local before=$(partials); $SC doctor --fetch --progress-lines >$OUT/of2.log 2>&1 & p=$!
    sleep 4; echo "RESULT orphan_fresh partials_before=$before partials_4s_into_refetch=$(partials) note=a young orphan is kept at the start"
    wait $p; echo "RESULT orphan_fresh refetch_rc=$? status=$(status) final_mb=$(mb $CACHE)   # 1543 = swept; ~1950 = the orphan stayed"
}
t_sigint() {
    set -m   # a non-interactive shell starts background jobs with SIGINT IGNORED; Python then never sees it
    clean; $SC doctor --fetch --progress-lines >$OUT/s1.log 2>&1 & local p=$!
    wait_mb 400 $p; local t0=$(date +%s); pkill -INT -f bristlenose-sidecar
    local i=0; while pgrep -f bristlenose-sidecar >/dev/null && [ $i -lt 120 ]; do sleep 0.5; i=$((i+1)); done
    echo "RESULT sigint stopped_in_s=$(( $(date +%s)-t0 )) partials=$(partials) status=$(status) mb=$(mb $CACHE) last=$(last $OUT/s1.log 1)"
}
t_concurrent() {
    clean; $SC doctor --fetch --progress-lines >$OUT/c1.log 2>&1 & local a=$!
    sleep 6; $SC doctor --fetch --progress-lines >$OUT/c2.log 2>&1 & local b=$!
    wait $a; local ra=$?; wait $b; local rb=$?
    echo "RESULT concurrent rcA=$ra rcB=$rb status=$(status) final_mb=$(mb $CACHE) partials=$(partials) lastA=$(last $OUT/c1.log 1) lastB=$(last $OUT/c2.log 1)"
}
t_tls() { # a missing CA bundle
    clean; export SSL_CERT_FILE=/dev/null REQUESTS_CA_BUNDLE=/dev/null
    local rc=$(run_for 90 $OUT/tls.log $SC doctor --fetch --progress-lines); unset SSL_CERT_FILE REQUESTS_CA_BUNDLE
    echo "RESULT tls rc=$rc status=$(status) mb=$(mb $CACHE) last=$(last $OUT/tls.log 3)"
}
t_badcert() { # an untrusted certificate chain, as behind a TLS-inspecting proxy
    clean; local rc=$(HF_ENDPOINT=https://untrusted-root.badssl.com run_for 90 $OUT/bc.log $SC doctor --fetch --progress-lines)
    echo "RESULT badcert rc=$rc last=$(last $OUT/bc.log 3)"
}
t_proxy() { # a dead proxy: must fail in seconds, not wait
    clean; export HTTPS_PROXY=http://127.0.0.1:9 https_proxy=http://127.0.0.1:9
    local t0=$(date +%s); local rc=$(run_for 120 $OUT/px.log $SC doctor --fetch --progress-lines); unset HTTPS_PROXY https_proxy
    echo "RESULT proxy rc=$rc secs=$(( $(date +%s)-t0 )) status=$(status) last=$(last $OUT/px.log 3)"
}
t_unwritable() {
    clean; mkdir -p $HOME/ro && chmod 555 $HOME/ro
    local rc=$(HF_HOME=$HOME/ro/hf run_for 90 $OUT/ro.log $SC doctor --fetch --progress-lines); chmod 755 $HOME/ro
    echo "RESULT unwritable rc=$rc last=$(last $OUT/ro.log 3)"
}
t_lowdisk() { # about 1.7 GB free: refused before a byte is written
    clean; local free=$(free_mb); dd if=/dev/zero of=$HOME/fill.bin bs=1m count=$((free-1700)) 2>/dev/null
    local n=0; while [ $(free_mb) -gt 1800 ] && [ $n -lt 6 ]; do dd if=/dev/zero of=$HOME/fill-x$n.bin bs=1m count=$(( $(free_mb)-1700 )) 2>/dev/null; n=$((n+1)); done
    local before=$(free_mb)
    local rc=$(run_for 60 $OUT/ld.log $SC doctor --fetch --progress-lines)
    echo "RESULT lowdisk free_before_mb=$before rc=$rc started=$(grep -c '@download-start' $OUT/ld.log) mb_written=$(mb $CACHE) last=$(last $OUT/ld.log 1)"
    rm -f $HOME/fill*
}
t_boundary() { # just over what the check asks (model + 1 GB = 2.614 GB): must pass. APFS free space drifts by ~200 MB, so leave 3.1 GB
    clean; local free=$(free_mb); dd if=/dev/zero of=$HOME/fill.bin bs=1m count=$((free-3100)) 2>/dev/null
    local before=$(free_mb)
    local rc=$(run_for 150 $OUT/bd.log $SC doctor --fetch --progress-lines)
    echo "RESULT boundary free_before_mb=$before rc=$rc status=$(status) free_after_mb=$(free_mb) last=$(last $OUT/bd.log 1)"
    rm -f $HOME/fill*
}
t_enospc() { # the check passes, then the disk fills DURING the download
    clean; local free=$(free_mb); dd if=/dev/zero of=$HOME/fill.bin bs=1m count=$((free-2800)) 2>/dev/null
    $SC doctor --fetch --progress-lines >$OUT/en.log 2>&1 & local p=$!
    wait_mb 400 $p; dd if=/dev/zero of=$HOME/fill2.bin bs=1m 2>/dev/null   # eats the rest of the disk
    wait $p; local rc=$?; sleep 1
    echo "RESULT enospc rc=$rc partials=$(partials) mb=$(mb $CACHE) status=$(status) last=$(last $OUT/en.log 3)"
    rm -f $HOME/fill2.bin; sleep 2
    find "$HUB" -name '*.incomplete' -exec touch -t 202601010000 {} \; 2>/dev/null
    local rc2=$(run_for 150 $OUT/en2.log $SC doctor --fetch --progress-lines)
    echo "RESULT enospc recovery rc=$rc2 status=$(status) final_mb=$(mb $CACHE) partials=$(partials) free_mb=$(free_mb)"
    rm -f $HOME/fill*
}
t_stall() { # a SILENT drop (no refusal, no DNS failure): the connection stays open and nothing arrives. STALL=<secs>
    clean; $SC doctor --fetch --progress-lines >$OUT/st.log 2>&1 & local p=$!
    wait_mb 400 $p
    printf 'block drop out quick proto tcp to any port 443\nblock drop out quick proto udp to any port 443\n' > /tmp/stall.rules
    echo admin | sudo -S pfctl -ef /tmp/stall.rules >/dev/null 2>&1; local t0=$(date +%s); sleep ${STALL:-60}
    echo admin | sudo -S pfctl -d >/dev/null 2>&1
    local i=0; while kill -0 $p 2>/dev/null && [ $i -lt 600 ]; do sleep 0.5; i=$((i+1)); done
    if kill -0 $p 2>/dev/null; then pkill -9 -f bristlenose-sidecar; echo "RESULT stall silent_s=${STALL:-60} outcome=HUNG_300s_after_unblock(killed) mb=$(mb $CACHE)"; else wait $p; echo "RESULT stall silent_s=${STALL:-60} outcome=exit_$? total_s=$(( $(date +%s)-t0 )) status=$(status) mb=$(mb $CACHE) last=$(last $OUT/st.log 2)"; fi
    echo DONE
}
t_sleepsim() { # a writer frozen for FREEZE s (sleep/wake, App Nap) while a SECOND fetch starts and sweeps. FREEZE=<secs>
    clean; $SC doctor --fetch --progress-lines >$OUT/ss1.log 2>&1 & local a=$!
    wait_mb 400 $a; pkill -STOP -f bristlenose-sidecar; local fr=${FREEZE:-150}
    sleep $((fr-15)); local age=$(( $(date +%s) - $(stat -f %m $(find "$HUB" -name '*.incomplete' | head -1)) ))
    $SC doctor --fetch --progress-lines >$OUT/ss2.log 2>&1 & local b=$!
    sleep 15; echo "NOTE sleepsim partial_age_s=$age partials_now=$(partials) mb=$(mb $CACHE)   # age past 120 s: only the HF lock protects it"
    pkill -CONT -f bristlenose-sidecar
    wait $a; local ra=$?; wait $b; local rb=$?; sleep 1
    echo "RESULT sleepsim frozen_s=$fr rcA=$ra rcB=$rb status=$(status) final_mb=$(mb $CACHE) partials=$(partials) lastA=$(last $OUT/ss1.log 1) lastB=$(last $OUT/ss2.log 1)"
}
t_hub() { # a fake endpoint: HUBMODE=429:4 | 5xx:4 | portal (the host runs fakehub.py on 192.168.64.1:8765)
    clean; local t0=$(date +%s); local rc=$(HF_ENDPOINT=http://192.168.64.1:8765 run_for ${HUBWAIT:-420} $OUT/hub.log $SC doctor --fetch --progress-lines)
    echo "RESULT hub mode=${HUBMODE} rc=$rc secs=$(( $(date +%s)-t0 )) status=$(status) mb=$(mb $CACHE) last=$(last $OUT/hub.log 2)"
}
t_netblip() { # detached (ssh dies with the interface): only the mid-download outage. NETDOWN=<secs>
    clean; local ifc=$(route -n get default 2>/dev/null | awk '/interface:/{print $2}')
    $SC doctor --fetch --progress-lines >$OUT/nb.log 2>&1 & local p=$!
    wait_mb 400 $p
    echo admin | sudo -S ifconfig $ifc down 2>/dev/null; sleep ${NETDOWN:-5}; echo admin | sudo -S ifconfig $ifc up 2>/dev/null
    local i=0; while kill -0 $p 2>/dev/null && [ $i -lt 400 ]; do sleep 0.5; i=$((i+1)); done
    if kill -0 $p 2>/dev/null; then pkill -9 -f bristlenose-sidecar; echo "RESULT netblip down_s=${NETDOWN:-5} outcome=HUNG(killed) mb=$(mb $CACHE)"; else wait $p; echo "RESULT netblip down_s=${NETDOWN:-5} outcome=exit_$? status=$(status) mb=$(mb $CACHE) last=$(last $OUT/nb.log 1)"; fi
    echo DONE
}
t_net() { # detached: an outage mid-download, then an outage at the START of a fetch. NETDOWN=<secs>
    clean; local ifc=$(route -n get default 2>/dev/null | awk '/interface:/{print $2}')
    echo "NOTE net iface=$ifc"
    $SC doctor --fetch --progress-lines >$OUT/n1.log 2>&1 & local p=$!
    wait_mb 400 $p
    echo admin | sudo -S ifconfig $ifc down 2>/dev/null; local t0=$(date +%s)
    sleep ${NETDOWN:-25}
    echo admin | sudo -S ifconfig $ifc up 2>/dev/null
    local i=0; while kill -0 $p 2>/dev/null && [ $i -lt 480 ]; do sleep 0.5; i=$((i+1)); done
    if kill -0 $p 2>/dev/null; then pkill -9 -f bristlenose-sidecar; echo "RESULT net down_s=${NETDOWN:-25} outcome=HUNG_after_reconnect(killed)"; else wait $p; echo "RESULT net down_s=${NETDOWN:-25} outcome=exit_$? total_s=$(( $(date +%s)-t0 )) status=$(status) mb=$(mb $CACHE) partials=$(partials) last=$(last $OUT/n1.log 3)"; fi
    # offline at the START of a fetch: the job must WAIT for the network, then finish
    clean; echo admin | sudo -S ifconfig $ifc down 2>/dev/null; local t1=$(date +%s)
    ( sleep ${NETDOWN:-25}; echo admin | sudo -S ifconfig $ifc up 2>/dev/null ) &
    local rc=$(run_for 330 $OUT/n2.log $SC doctor --fetch --progress-lines)
    echo admin | sudo -S ifconfig $ifc up 2>/dev/null
    echo "RESULT net offline_start rc=$rc total_s=$(( $(date +%s)-t1 )) status=$(status) final_mb=$(mb $CACHE) last=$(last $OUT/n2.log 2)"
    echo DONE
}
for t in "$@"; do "t_$t"; done
