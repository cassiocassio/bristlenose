#!/bin/bash
# Usage: edge-check.sh [vm]   (on the Mac that runs the VirtualBox VMs; see docs/release-winget.md)
# Boot the VM, render a font probe in headless Edge (Chromium font lookup), bring back DOM + PNG, restore "clean".
set -u
VM=${1:-win11-26h2}; VBM=/usr/local/bin/VBoxManage; PW=$HOME/bn-wintest/guest-password; D=${BN_FONTCHECK_DIR:-$HOME/bn-wintest/font-7c2e}   # holds fontcheck.html; receives shot.png
ts() { printf '%s  %s\n' "$(date +%H:%M:%S)" "$*"; }
[ "$($VBM showvminfo $VM --machinereadable | sed -n 's/^VMState="\(.*\)"/\1/p')" = poweroff ] || { ts "VM not powered off; refusing"; exit 2; }
ts "starting $VM"; $VBM startvm $VM --type headless || exit 3
i=0; until $VBM guestcontrol $VM run --username bn --passwordfile $PW --exe 'C:\Windows\System32\cmd.exe' -- /d /c ver >/dev/null 2>&1; do
  [ $i -ge 1800 ] && { ts "guest never answered"; break; }; sleep 20; i=$((i+20)); done
ts "guest up after ${i}s"
G='C:\Users\bn\fontcheck'
$VBM guestcontrol $VM mkdir --username bn --passwordfile $PW --parents "$G"
$VBM guestcontrol $VM copyto --username bn --passwordfile $PW "$D/fontcheck.html" "$G\\fontcheck.html"
EDGE='C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
common=(--headless=new --disable-gpu --no-first-run --user-data-dir="$G\\profile" --force-device-scale-factor=2 --window-size=900,1000)
ts "dump-dom"
$VBM guestcontrol $VM run --username bn --passwordfile $PW --profile --timeout 180000 --wait-stdout --wait-stderr --exe "$EDGE" -- \
  "${common[@]}" --dump-dom "file:///C:/Users/bn/fontcheck/fontcheck.html" 2>/dev/null | grep -o 'RESULT .*' | sed 's/<.*//'
ts "screenshot"
$VBM guestcontrol $VM run --username bn --passwordfile $PW --profile --timeout 180000 --wait-stdout --wait-stderr --exe "$EDGE" -- \
  "${common[@]}" --screenshot="$G\\shot.png" "file:///C:/Users/bn/fontcheck/fontcheck.html" >/dev/null 2>&1
$VBM guestcontrol $VM copyfrom --username bn --passwordfile $PW "$G\\shot.png" "$D/shot.png" && ls -la "$D/shot.png"
$VBM guestcontrol $VM run --username bn --passwordfile $PW --profile --wait-stdout --exe 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -- -NoProfile -Command '"Edge " + (Get-Item "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe").VersionInfo.ProductVersion'
ts "powering off and restoring snapshot clean"
$VBM controlvm $VM poweroff; sleep 10; $VBM snapshot $VM restore clean
$VBM showvminfo $VM --machinereadable | grep -E '^VMState=|^CurrentSnapshotName'
ts done
