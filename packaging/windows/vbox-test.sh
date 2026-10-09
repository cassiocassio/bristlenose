#!/bin/bash
# vbox-test.sh — install the Windows installer in clean Windows 10 / 11 VMs and
# prove it works, on an Intel Mac running VirtualBox 7.0.
#
# The client-Windows check CI cannot make: GitHub's runner and aella are Windows
# Server. This builds one VM per Windows version from Microsoft's own ISO with
# VirtualBox's unattended install, snapshots it clean, then for each test reverts
# to that snapshot, installs bristlenose-<v>-setup-x64.exe silently, and checks
# what a user would: --version, doctor --self-test, a real transcription (ffmpeg
# and whisper), the user PATH entry, and an uninstall that leaves nothing behind.
# Plan and reasoning: docs/release-winget.md, "Testing the installer".
#
#   vbox-test.sh build <vm> <iso> [image-index]   create the VM, install Windows, snapshot "clean"
#   vbox-test.sh test  <vm> <setup.exe>           revert to clean, install, check, uninstall
#   vbox-test.sh detect <iso>                     list the editions in an ISO (for the index)
#   vbox-test.sh status                           the VMs and their state
#
# <vm> names its Windows: win10-* builds Windows 10, win11-* Windows 11.
# What it cannot see: SmartScreen and Smart App Control. A file copied in by
# the guest additions carries no Mark of the Web, so those stay a human check.
#
# Written for /bin/bash 3.2 (Big Sur). State lives under $BN_WINTEST.

set -uo pipefail

BN_WINTEST="${BN_WINTEST:-$HOME/bn-wintest}"
VMS="$BN_WINTEST/vms"
PWFILE="$BN_WINTEST/guest-password"   # generated once, 0600, never printed
GUSER="bn"
# A 2014 i7 takes most of an hour for an unattended install; three is a hang.
BUILD_TIMEOUT_S="${BUILD_TIMEOUT_S:-10800}"
BOOT_TIMEOUT_S="${BOOT_TIMEOUT_S:-900}"
# The first transcribe downloads the whisper model; generous on a slow line.
STEP_TIMEOUT_MS="${STEP_TIMEOUT_MS:-1800000}"
VBM="${VBM:-/usr/local/bin/VBoxManage}"

say_() { printf '%s  %s\n' "$(date +%H:%M:%S)" "$*"; }
die() { say_ "FAIL: $*"; exit 1; }
vbm() { "$VBM" "$@"; }

state() { vbm showvminfo "$1" --machinereadable 2>/dev/null | sed -n 's/^VMState="\(.*\)"/\1/p'; }

ensure_password() {
    [ -s "$PWFILE" ] && return
    mkdir -p "$BN_WINTEST"
    ( umask 077; LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 20 > "$PWFILE" )
}

# Run a program in the guest as the test user, with the user's profile loaded
# (HKCU and %LOCALAPPDATA% exist). Output streams back; exit status is the guest's.
# VirtualBox 7.0 supplies argv[0] from --exe itself: the words after -- are the
# arguments only (passing the path again made it argv[1], measured 9 Oct 2026).
# Each argument reaches Windows as one quoted word, so never route a path with a
# space through `cmd /c`: its quoting turns an error into a "not found".
grun() {
    local vm="$1" exe="$2"; shift 2
    vbm guestcontrol "$vm" run --username "$GUSER" --passwordfile "$PWFILE" --profile \
        --timeout "$STEP_TIMEOUT_MS" --wait-stdout --wait-stderr --exe "$exe" -- "$@"
}
# Does a guest path exist? VirtualBox's own stat: no guest shell, no quoting.
gexists() { vbm guestcontrol "$1" stat --username "$GUSER" --passwordfile "$PWFILE" "$2" >/dev/null 2>&1; }
gcmd() { local vm="$1"; shift; grun "$vm" 'C:\Windows\System32\cmd.exe' /d /c "$@"; }

wait_state() {  # $1 vm, $2 wanted state, $3 timeout seconds
    local i=0
    while [ "$(state "$1")" != "$2" ]; do
        [ "$i" -ge "$3" ] && return 1
        sleep 20; i=$((i + 20))
        if [ $((i % 600)) -eq 0 ]; then say_ "  still waiting for $1 to reach $2 ($((i / 60)) min)"; fi
    done
    return 0  # the loop's status is its last body command's, not "reached the state"
}

wait_guest() {  # until the guest additions answer a command as our user
    local i=0
    until gcmd "$1" ver >/dev/null 2>&1; do
        [ "$i" -ge "$BOOT_TIMEOUT_S" ] && return 1
        sleep 15; i=$((i + 15))
    done
}

cmd_detect() {
    [ -f "${1:-}" ] || die "usage: detect <iso>"
    vbm unattended detect --iso="$1" --machine-readable | grep -E 'ImageIndex|ImageName|OSVersion|OSFlavor|Languages'
}

cmd_build() {
    local vm="${1:-}" iso="${2:-}" index="${3:-1}" ostype key=""
    [ -n "$vm" ] && [ -f "$iso" ] || die "usage: build <vm> <iso> [image-index]"
    case "$vm" in
        win10-*) ostype=Windows10_64 ;;
        win11-*) ostype=Windows11_64 ;;
        *) die "a VM name starts win10- or win11-" ;;
    esac
    vbm showvminfo "$vm" >/dev/null 2>&1 && die "$vm exists; unregister it first (VBoxManage unregistervm $vm --delete)"
    # The consumer multi-edition Windows 10 ISO stops at a product-key prompt under
    # unattended setup. W269N-… is the published generic (KMS client) key for Pro
    # (learn.microsoft.com, "KMS client activation and product keys"): it picks the
    # edition and installs unactivated, which is all a test VM needs. The
    # Enterprise evaluation ISO needs no key.
    case "$vm" in win10-*) key="${BN_PRODUCT_KEY:-W269N-WFGWX-YVC9B-4J6C9-T83GX}" ;; esac
    ensure_password
    mkdir -p "$VMS"
    say_ "creating $vm ($ostype) from $(basename "$iso"), image $index"
    vbm createvm --name "$vm" --ostype "$ostype" --basefolder "$VMS" --register >/dev/null || die createvm
    vbm modifyvm "$vm" --memory 8192 --cpus 4 --vram 128 --graphicscontroller vboxsvga \
        --firmware efi --nic1 nat --audio-enabled off --clipboard-mode disabled \
        --drag-and-drop disabled --usb-ohci off || die modifyvm
    if [ "$ostype" = Windows11_64 ]; then
        vbm modifyvm "$vm" --tpm-type 2.0 || die "tpm"
        vbm modifynvram "$vm" inituefivarstore && vbm modifynvram "$vm" enrollmssignatures \
            && vbm modifynvram "$vm" enrollorclpk && vbm modifynvram "$vm" secureboot --enable \
            || say_ "  secure boot not enabled (installs anyway with the bypass below)"
    fi
    local disk="$VMS/$vm/$vm.vdi"
    vbm createmedium disk --filename "$disk" --size 65536 >/dev/null || die createmedium
    vbm storagectl "$vm" --name SATA --add sata --controller IntelAhci --portcount 4 || die storagectl
    vbm storageattach "$vm" --storagectl SATA --port 0 --type hdd --medium "$disk" || die storageattach

    local aux="$VMS/$vm/unattended"
    mkdir -p "$aux"
    vbm unattended install "$vm" --iso="$iso" --image-index="$index" \
        --user="$GUSER" --password-file="$PWFILE" --full-user-name="Bristlenose Test" \
        --install-additions --locale=en_GB --country=GB --time-zone="GMT Standard Time" \
        --hostname="$vm.local" --auxiliary-base-path="$aux/" ${key:+--key="$key"} \
        --post-install-command='shutdown /s /t 60 /f' || die "unattended install"

    # Windows 11 setup refuses a CPU older than 8th-gen Intel, inside a VM too.
    # The LabConfig keys are Microsoft's own documented-by-practice bypass.
    local xml; xml=$(ls "$aux"/autounattend.xml "$aux"/*utounattend.xml 2>/dev/null | head -1)
    [ -f "$xml" ] || die "no autounattend.xml under $aux"
    if [ "$ostype" = Windows11_64 ] && ! grep -q BypassCPUCheck "$xml"; then
        /usr/bin/python3 - "$xml" <<'PY' || die "could not add the LabConfig bypass"
import re, sys
p = sys.argv[1]; s = open(p, encoding="utf-8").read()
keys = ["BypassTPMCheck", "BypassSecureBootCheck", "BypassRAMCheck", "BypassCPUCheck"]
cmds = "".join(
    f'<RunSynchronousCommand wcm:action="add"><Order>{90 + i}</Order>'
    f'<Path>reg add HKLM\\SYSTEM\\Setup\\LabConfig /v {k} /t REG_DWORD /d 1 /f</Path></RunSynchronousCommand>'
    for i, k in enumerate(keys))
m = re.search(r'(<component[^>]*Microsoft-Windows-Setup[^>]*>)', s)
if not m: sys.exit("no Microsoft-Windows-Setup component in the windowsPE pass")
if "<RunSynchronous>" in s[m.end():s.find("</component>", m.end())]:
    i = s.find("<RunSynchronous>", m.end()) + len("<RunSynchronous>")
    s = s[:i] + cmds + s[i:]
else:
    s = s[:m.end()] + "<RunSynchronous>" + cmds + "</RunSynchronous>" + s[m.end():]
open(p, "w", encoding="utf-8").write(s)
PY
        say_ "  added the Windows 11 hardware-check bypass to $(basename "$xml")"
    fi

    say_ "installing Windows unattended (expect 45-90 min on this Mac)"
    vbm startvm "$vm" --type headless >/dev/null || die startvm
    # A UEFI Windows ISO waits a few seconds on "Press any key to boot from CD or
    # DVD" and then falls through to "No bootable device". Nothing presses a key
    # in a headless VM, so press Enter until Setup has surely taken over.
    local k=0
    while [ "$k" -lt 25 ]; do sleep 1; vbm controlvm "$vm" keyboardputscancode 1c 9c >/dev/null 2>&1; k=$((k + 1)); done
    local t0; t0=$(date +%s)
    wait_state "$vm" poweroff "$BUILD_TIMEOUT_S" || die "$vm did not finish installing within $((BUILD_TIMEOUT_S / 60)) min"
    # An install that "finishes" in minutes never ran Setup; never snapshot that as clean.
    [ $(( $(date +%s) - t0 )) -ge 900 ] || die "$vm powered off after $(( ($(date +%s) - t0) / 60 )) min, too soon for a Windows install; not snapshotting"
    vbm storageattach "$vm" --storagectl SATA --port 1 --medium none 2>/dev/null
    vbm storageattach "$vm" --storagectl SATA --port 2 --medium none 2>/dev/null
    vbm snapshot "$vm" take clean --description "fresh unattended install $(date +%F)" >/dev/null || die snapshot
    say_ "$vm built and snapshotted 'clean'"
}

cmd_test() {
    local vm="${1:-}" setup="${2:-}"
    [ -n "$vm" ] && [ -f "$setup" ] || die "usage: test <vm> <setup.exe>"
    ensure_password
    local dl='C:\Users\bn\Downloads' study='C:\Users\bn\Bristle Study' \
          app='C:\Users\bn\AppData\Local\Programs\Bristlenose'
    local exe="$app\\bristlenose.exe" name; name=$(basename "$setup")
    local wav="$BN_WINTEST/hello.wav"
    [ -f "$wav" ] || say -o "$wav" --file-format=WAVE --data-format=LEI16@16000 \
        "Honestly I found the dashboard pretty confusing the first time I opened it." || die "say"

    [ "$(state "$vm")" = poweroff ] || vbm controlvm "$vm" poweroff >/dev/null 2>&1
    wait_state "$vm" poweroff 120 || true
    vbm snapshot "$vm" restore clean >/dev/null || die "no clean snapshot for $vm"
    say_ "[$vm] booting the clean snapshot"
    vbm startvm "$vm" --type headless >/dev/null || die startvm
    local rc=0 failed=""
    step() {  # $1 label; the rest is the command. Records, never aborts, so uninstall still runs.
        local label="$1"; shift
        if "$@"; then say_ "[$vm] ok    $label"; else say_ "[$vm] FAIL  $label"; failed="$failed; $label"; rc=1; fi
    }
    check_version() { grun "$vm" "$exe" --version 2>&1 | tr -d '\r' | tee /dev/stderr | grep -q '^bristlenose '; }
    check_transcript() {  # copy the transcripts out and read them here: no guest shell
        local out="$BN_WINTEST/out/$vm"; rm -rf "$out"; mkdir -p "$out"
        vbm guestcontrol "$vm" copyfrom --username "$GUSER" --passwordfile "$PWFILE" --recursive \
            --target-directory "$out" "$study\\bristlenose-output\\transcripts-raw" || return 1
        find "$out" -name '*.txt' -exec cat {} + | tee /dev/stderr | grep -qi dashboard
    }
    user_path() { grun "$vm" 'C:\Windows\System32\reg.exe' query 'HKCU\Environment' /v Path 2>/dev/null | tr -d '\r'; }
    check_path_has() { user_path | grep -qi 'Programs\\Bristlenose'; }
    check_path_clean() { ! user_path | grep -qi 'Programs\\Bristlenose'; }
    check_folder_gone() { ! gexists "$vm" "$app"; }
    check_folder_there() { gexists "$vm" "$exe"; }
    wait_guest "$vm" || { vbm controlvm "$vm" poweroff >/dev/null 2>&1; die "[$vm] guest additions never answered"; }
    gcmd "$vm" ver | tr -d '\r' | grep -i version | sed "s/^/[$vm]       /"

    vbm guestcontrol "$vm" mkdir --username "$GUSER" --passwordfile "$PWFILE" --parents "$study" || die mkdir
    vbm guestcontrol "$vm" copyto --username "$GUSER" --passwordfile "$PWFILE" --target-directory "$dl\\" "$setup" || die "copy installer"
    vbm guestcontrol "$vm" copyto --username "$GUSER" --passwordfile "$PWFILE" --target-directory "$study\\" "$wav" || die "copy wav"

    step "silent install" grun "$vm" "$dl\\$name" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART "/LOG=$dl\\setup.log"
    step "bristlenose.exe where expected" check_folder_there
    step "--version" check_version
    step "doctor --self-test" grun "$vm" "$exe" doctor --self-test
    step "transcribe a spoken WAV" grun "$vm" "$exe" transcribe "$study"
    step "transcript has the words" check_transcript
    step "user PATH has the app" check_path_has
    # The uninstaller re-launches itself from %TEMP% and returns at once.
    step "silent uninstall" grun "$vm" "$app\\unins000.exe" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
    local i=0
    while gexists "$vm" "$app"; do
        [ "$i" -ge 120 ] && break; sleep 5; i=$((i + 5))
    done
    step "folder gone after uninstall" check_folder_gone
    step "PATH entry gone after uninstall" check_path_clean

    vbm controlvm "$vm" poweroff >/dev/null 2>&1
    if [ "$rc" -eq 0 ]; then say_ "[$vm] PASS  $name"; else say_ "[$vm] FAILED $name:${failed#;}"; fi
    return "$rc"
}

cmd_status() { vbm list vms; for vm in $(vbm list vms | sed -n 's/^"\([^"]*\)".*/\1/p'); do echo "$vm: $(state "$vm")"; done; }

case "${1:-}" in
    build)  shift; cmd_build "$@" ;;
    test)   shift; cmd_test "$@" ;;
    detect) shift; cmd_detect "$@" ;;
    status) cmd_status ;;
    *) sed -n '2,20p' "$0"; exit 2 ;;
esac
