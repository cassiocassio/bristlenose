#!/bin/bash
# vbox-uv-walk.sh — the Windows one-liner and the uv route on native x64 Windows,
# in benbecula's VirtualBox VMs, with real media. Companion to
# packaging/windows/vbox-test.sh, whose VMs, test user and password file it uses.
#
#   vbox-uv-walk.sh <vm> <kit-dir>
#     kit-dir holds: install.ps1 (scripts/windows), post.ps1 (this folder's
#     windows-post.ps1), kit.zip (project/, a bristlenose wheel, probe.py)
#
# Restores the VM's "clean" snapshot first and again at the end. Written for
# /bin/bash 3.2 (Big Sur).
set -uo pipefail
vm="$1" kit="$2"
BN_WINTEST="${BN_WINTEST:-$HOME/bn-wintest}"
PWFILE="$BN_WINTEST/guest-password"
GUSER="bn"
VBM="${VBM:-/usr/local/bin/VBoxManage}"
W='C:\Users\bn\bnwalk'
say_() { printf '%s  %s\n' "$(date +%H:%M:%S)" "$*"; }
vbm() { "$VBM" "$@"; }
state() { vbm showvminfo "$1" --machinereadable 2>/dev/null | sed -n 's/^VMState="\(.*\)"/\1/p'; }
grun() {  # as the test user, profile loaded; extra --putenv args before --
    vbm guestcontrol "$vm" run --username "$GUSER" --passwordfile "$PWFILE" --profile \
        --timeout 3600000 --wait-stdout --wait-stderr "$@"
}
restore_clean() {
    [ "$(state "$vm")" = poweroff ] || vbm controlvm "$vm" poweroff >/dev/null 2>&1
    local i=0; while [ "$(state "$vm")" != poweroff ] && [ $i -lt 120 ]; do sleep 5; i=$((i+5)); done
    vbm snapshot "$vm" restore clean >/dev/null || { say_ "no clean snapshot for $vm"; exit 1; }
}
reset_clock() {
    vbm setextradata "$vm" "VBoxInternal/Devices/VMMDev/0/Config/GetHostTimeDisabled" >/dev/null 2>&1
    vbm modifyvm "$vm" --bios-system-time-offset 0 >/dev/null 2>&1
}
restore_clean
# BN_GUEST_CLOCK=YYYY-MM-DD boots the guest on that date: the clean snapshots'
# test user was made on 9 Oct 2026, and Windows' 42-day password age expires it,
# so guest control cannot log in on today's date. Reset at the end.
if [ -n "${BN_GUEST_CLOCK:-}" ]; then
    off=$(( ($(date -j -f "%Y-%m-%d %H:%M:%S" "$BN_GUEST_CLOCK 12:00:00" +%s) - $(date +%s)) * 1000 ))
    vbm setextradata "$vm" "VBoxInternal/Devices/VMMDev/0/Config/GetHostTimeDisabled" 1
    vbm modifyvm "$vm" --bios-system-time-offset "$off"
    say_ "[$vm] guest clock set to $BN_GUEST_CLOCK (offset ${off} ms), host time sync off"
fi
say_ "[$vm] booting the clean snapshot"
vbm startvm "$vm" --type headless >/dev/null || exit 1
i=0; until grun --exe 'C:\Windows\System32\cmd.exe' -- /d /c ver >/dev/null 2>&1; do
    [ $i -ge 1500 ] && { say_ "guest never answered"; restore_clean; reset_clock; exit 1; }; sleep 15; i=$((i+15)); done
say_ "[$vm] guest control answered after ${i} s"
vbm guestcontrol "$vm" mkdir --username "$GUSER" --passwordfile "$PWFILE" --parents "$W"
for f in install.ps1 post.ps1 "${BN_POST:-post.ps1}" waitclock.ps1 kit.zip; do
    vbm guestcontrol "$vm" copyto --username "$GUSER" --passwordfile "$PWFILE" --target-directory "$W\\" "$kit/$f" || say_ "copy $f failed"
done
whl=$(cd "$kit" && unzip -Z1 kit.zip | grep '\.whl$' | head -1)
say_ "[$vm] the one-liner (install.ps1), FFmpeg from its pinned zip, Bristlenose from $whl"
# One guest logon for everything: the guest's own time service corrects a
# set-back clock once it has network, and a second logon then meets the expired
# password ("account is restricted"). post.ps1 reads PATH from the registry, as
# a new terminal would, so running it in the same session loses nothing.
grun --putenv "BRISTLENOSE_INSTALL_SPEC=$W\\kit\\$whl" --putenv "BRISTLENOSE_INSTALL_FFMPEG=zip" --putenv "BN_REAL_EPOCH=$(date +%s)" \
     --exe 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -- \
     -NoProfile -ExecutionPolicy Bypass -Command \
     "& powershell -NoProfile -ExecutionPolicy Bypass -File '$W\\waitclock.ps1'; Expand-Archive -Force '$W\\kit.zip' '$W\\kit'; & powershell -NoProfile -ExecutionPolicy Bypass -File '$W\\install.ps1'; '== install.ps1 exit: ' + \$LASTEXITCODE; & powershell -NoProfile -ExecutionPolicy Bypass -File '$W\\${BN_POST:-post.ps1}'" 2>&1 | tr -d '\r'
echo "== session exit: $?"
restore_clean
reset_clock
say_ "[$vm] restored to clean, clock settings reset"
