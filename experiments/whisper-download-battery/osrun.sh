#!/bin/zsh
# osrun.sh <base-image> <vm-name> <label> [tests…] — clone a Tart image, boot it, install the CURRENT sidecar
# bundle, run the battery, leave the guest running (stop it yourself) and the results in results/<label>.txt.
#   NETDOWN=<s> STALL=<s> FREEZE=<s> HUBMODE=<m> HUBWAIT=<s>  tune the detached/network tests.
# Images used on 30 Oct 2026: ghcr.io/cirruslabs/macos-sequoia-vanilla:latest (15), a local macOS 26 image,
# a local macOS 27 base. macOS allows TWO guests at a time on one host.
BASE=$1; VM=$2; LABEL=$3; shift 3
TESTS=${@:-info cold fetch orphan orphan_fresh sigint concurrent tls badcert proxy unwritable lowdisk boundary enospc net}
HERE="${0:A:h}"; ROOT="${HERE:h:h}"
KEY=${BATTERY_KEY:-$HOME/.ssh/id_ed25519_tartvm}
mkdir -p $HERE/results; RES=$HERE/results/$LABEL.txt; : > $RES
tart stop $VM >/dev/null 2>&1; tart delete $VM >/dev/null 2>&1
tart clone $BASE $VM || exit 1
(tart run $VM --no-graphics --no-clipboard > $HERE/results/$VM.log 2>&1 &)
ip=""; for i in $(seq 1 90); do ip=$(tart ip $VM 2>/dev/null) && [ -n "$ip" ] && nc -z -w2 $ip 22 2>/dev/null && break; sleep 2; done
# A fresh clone takes minutes before password login works, so keep trying. The expect block MUST be
# multi-line: the one-line `expect { … }` form never matches (desktop/scripts/guest-walk/prep-base.sh says so).
for t in $(seq 1 8); do
  expect -c "
set timeout 60
spawn ssh-copy-id -i $KEY.pub -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o IdentitiesOnly=yes admin@$ip
expect {
  -re {[Pp]assword:} { send \"admin\r\"; exp_continue }
  eof
}" >/dev/null 2>&1
  $HERE/sshg $VM true 2>/dev/null && break; sleep 12; done
$HERE/sshg $VM true || { echo "NO SSH" | tee -a $RES; exit 1; }
$HERE/rs $VM $ROOT/desktop/Bristlenose/Resources/bristlenose-sidecar/ sc-new/
scp -q -i $KEY -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o IdentitiesOnly=yes $HERE/bat.sh admin@$ip:bat.sh
# The sidecar is signed sandbox+inherit and traps when run from a shell: re-sign the main binary without entitlements.
$HERE/sshg $VM 'chmod +x ~/bat.sh; cd ~/sc-new && xattr -cr . && codesign --force -s - bristlenose-sidecar 2>&1 | tail -1'
for t in ${=TESTS}; do
  echo "--- $t" >> $RES
  if [ $t = net ] || [ $t = netblip ] || [ $t = stall ]; then
    # these cut the network, so the ssh channel dies: run detached, then poll for DONE
    $HERE/sshg $VM 'rm -f ~/net.out; NETDOWN='${NETDOWN:-25}' STALL='${STALL:-60}' nohup ~/bat.sh '$t' > ~/net.out 2>&1 &' ; sleep 20
    for i in $(seq 1 120); do $HERE/sshg $VM 'grep -q DONE ~/net.out' 2>/dev/null && break; sleep 5; done
    $HERE/sshg $VM 'cat ~/net.out' >> $RES 2>&1
  else
    $HERE/sshg $VM "HUBMODE='${HUBMODE:-}' HUBWAIT='${HUBWAIT:-420}' FREEZE='${FREEZE:-150}' ~/bat.sh $t" >> $RES 2>&1
  fi
done
echo "=== $LABEL done" >> $RES
