#!/bin/bash
# vbox-linux-walk.sh — native x86_64 Linux for the uv walk: Ubuntu 24.04's
# official cloud image as a throwaway VirtualBox VM on an Intel Mac (benbecula).
#
#   vbox-linux-walk.sh <work-dir>
#     work-dir holds: project/ (media), bristlenose-*.whl, probe.py
#
# Everything lives under <work-dir>: the image, the VM, a key made for this VM
# only. The VM is unregistered and deleted at the end. Written for /bin/bash 3.2.
set -uo pipefail
D="$1"
VBM="${VBM:-/usr/local/bin/VBoxManage}"
VM=bn-linux-walk
PORT=2299
say_() { printf '%s  %s\n' "$(date +%H:%M:%S)" "$*"; }
cleanup() {
    "$VBM" controlvm "$VM" poweroff >/dev/null 2>&1; sleep 5
    "$VBM" unregistervm "$VM" --delete >/dev/null 2>&1
    say_ "VM deleted"
}
trap cleanup EXIT
cd "$D" || exit 1

[ -f ubuntu.ova ] || curl -sfL -o ubuntu.ova https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.ova || { say_ "download failed"; exit 1; }
rm -f key key.pub; ssh-keygen -q -t ed25519 -N "" -f key -C bn-linux-walk
mkdir -p seed
cat > seed/user-data <<EOF
#cloud-config
users:
  - name: walker
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    ssh_authorized_keys: [$(cat key.pub)]
ssh_pwauth: false
EOF
printf 'instance-id: bn-linux-walk\nlocal-hostname: bnlinux\n' > seed/meta-data
rm -f seed.iso; hdiutil makehybrid -quiet -iso -joliet -default-volume-name cidata -o seed.iso seed

"$VBM" unregistervm "$VM" --delete >/dev/null 2>&1
"$VBM" import ubuntu.ova --vsys 0 --vmname "$VM" --basefolder "$D/vm" >/dev/null || { say_ "import failed"; exit 1; }
disk=$(find "$D/vm" -name '*.vmdk' | head -1)
ctl=$("$VBM" showvminfo "$VM" --machinereadable | sed -n 's/^storagecontrollername0="\(.*\)"/\1/p')
"$VBM" clonemedium disk "$disk" "$D/vm/disk.vdi" --format VDI >/dev/null
"$VBM" modifymedium disk "$D/vm/disk.vdi" --resize 20480
"$VBM" storageattach "$VM" --storagectl "$ctl" --port 0 --device 0 --type hdd --medium "$D/vm/disk.vdi"
"$VBM" storageattach "$VM" --storagectl "$ctl" --port 1 --device 0 --type dvddrive --medium "$D/seed.iso" 2>/dev/null \
  || { "$VBM" storagectl "$VM" --name IDE --add ide >/dev/null; "$VBM" storageattach "$VM" --storagectl IDE --port 0 --device 0 --type dvddrive --medium "$D/seed.iso"; }
"$VBM" modifyvm "$VM" --memory 6144 --cpus 4 --nic1 nat --natpf1 "ssh,tcp,127.0.0.1,$PORT,,22" --uart1 off --audio-enabled off
"$VBM" startvm "$VM" --type headless >/dev/null || { say_ "start failed"; exit 1; }
say_ "booting Ubuntu 24.04 (x86_64, native)"

S="ssh -q -i $D/key -p $PORT -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 walker@127.0.0.1"
i=0; until $S true 2>/dev/null; do [ $i -ge 900 ] && { say_ "ssh never answered"; exit 1; }; sleep 10; i=$((i+10)); done
say_ "ssh up after ${i} s"
$S 'cloud-init status --wait >/dev/null 2>&1; uname -m; grep PRETTY /etc/os-release; grep -o -m1 "avx2" /proc/cpuinfo'
scp -q -i "$D/key" -P $PORT -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -r "$D/project" "$D"/bristlenose-*.whl "$D/probe.py" walker@127.0.0.1:
step() { echo "== STEP: $1"; $S "bash -lc $(printf %q "$1")"; echo "== EXIT: $?"; }
# The website's uv section, word for word (wget: Ubuntu's cloud image has curl too).
step "sudo apt-get update -q >/dev/null && sudo apt install -y -q ffmpeg >/dev/null; ffmpeg -version | head -1"
step "curl -LsSf https://astral.sh/uv/install.sh | sh"
step "uv tool install --python 3.14 bristlenose 2>&1 | tail -2"
step "bristlenose --version && bristlenose doctor 2>&1 | grep -E 'FFmpeg|Transcription|API'"
step 'py=$(uv tool dir)/bristlenose/bin/python; $py -m spacy download en_core_web_lg 2>&1 | tail -1'
step 'uv tool install --force ~/bristlenose-*.whl --python 3.14 2>&1 | tail -1'
step 'bristlenose transcribe ~/project -w tiny 2>&1 | grep -E "Transcribed|Done|✗"'
step 'py=$(uv tool dir)/bristlenose/bin/python; $py ~/probe.py ~/project pii'
step 'cmd=$($(uv tool dir)/bristlenose/bin/python -c "from bristlenose.utils.install_channel import add_extra_command as a; print(a(\"voice\"))"); echo "$cmd"; eval "$cmd" >/dev/null 2>&1; $(uv tool dir)/bristlenose/bin/python -c "import kaldi_native_fbank, sys; print(\"voice on\", sys.version.split()[0])"'
say_ "done"
