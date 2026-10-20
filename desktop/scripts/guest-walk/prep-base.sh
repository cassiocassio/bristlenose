#!/bin/bash
# prep-base.sh <vm> — turn a Cirrus *vanilla* guest into the walk's base image.
#
# Vanilla is the cleanest image Cirrus publishes: SIP on, no Homebrew, no Xcode.
# It has no tart guest agent, so `tart exec` cannot reach it. This installs only
# that agent (the Cirrus-signed binary copied out of the tahoe guest, team
# 9M2P8L4D89) under /usr/local/bin, and nothing else, then sets the few prefs
# a walk needs. After it: a person grants Accessibility and Screen Recording to
# tart-guest-agent once, in the guest window (SIP is on, so TCC cannot be
# pre-written), and the result is cloned as the base every night starts from.
set -uo pipefail
VM="${1:?vm name}"
export TART_HOME=/Volumes/Iona/tart
TART=${TART_BIN:-$HOME/Applications/tart.app/Contents/MacOS/tart}
KEY=$HOME/.ssh/id_ed25519_tartvm
AGENT=/Volumes/Iona/tart/share/bn-walk27/agent
SSHO=(-i "$KEY" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o IdentitiesOnly=yes -o LogLevel=ERROR)

ip=""
for i in $(seq 1 120); do ip=$($TART ip "$VM" 2>/dev/null) && [ -n "$ip" ] && break; sleep 2; done
[ -n "$ip" ] || { echo "no IP for $VM"; exit 1; }
for i in $(seq 1 60); do nc -z -w 2 "$ip" 22 2>/dev/null && break; sleep 2; done
echo "guest $VM at $ip"

# Key auth, using the image's published default password (admin/admin), once.
if ! ssh "${SSHO[@]}" -o BatchMode=yes admin@"$ip" true 2>/dev/null; then
  # Multi-line on purpose: expect's one-line `expect { … }` form did not match.
  # IdentitiesOnly, or ssh offers every agent key first and the guest cuts it off.
  expect -c "
    set timeout 60
    spawn ssh-copy-id -i $KEY.pub -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o IdentitiesOnly=yes admin@$ip
    expect {
      -re {[Pp]assword:} { send \"admin\r\"; exp_continue }
      eof
    }" >/dev/null
fi
ssh "${SSHO[@]}" -o BatchMode=yes admin@"$ip" true || { echo "key auth failed"; exit 1; }

scp -q "${SSHO[@]}" "$AGENT/tart-guest-agent" "$AGENT/org.cirruslabs.tart-guest-agent.plist" \
  "$AGENT/org.cirruslabs.tart-guest-daemon.plist" admin@"$ip":/tmp/ || exit 1
ssh "${SSHO[@]}" admin@"$ip" 'set -e
  S() { echo admin | sudo -S -p "" "$@"; }
  S mkdir -p /usr/local/bin
  S install -m 755 /tmp/tart-guest-agent /usr/local/bin/tart-guest-agent
  for p in agent daemon; do
    sed "s#/opt/homebrew/bin/tart-guest-agent#/usr/local/bin/tart-guest-agent#" /tmp/org.cirruslabs.tart-guest-$p.plist > /tmp/$p.plist
  done
  S install -m 644 -o root -g wheel /tmp/agent.plist /Library/LaunchAgents/org.cirruslabs.tart-guest-agent.plist
  S install -m 644 -o root -g wheel /tmp/daemon.plist /Library/LaunchDaemons/org.cirruslabs.tart-guest-daemon.plist
  S launchctl bootstrap system /Library/LaunchDaemons/org.cirruslabs.tart-guest-daemon.plist 2>/dev/null || true
  launchctl bootstrap gui/$(id -u) /Library/LaunchAgents/org.cirruslabs.tart-guest-agent.plist 2>/dev/null || true
  # A walk wants a quiet, repeatable desktop: no reopened windows at login, no
  # screen saver or display sleep mid-walk.
  defaults write com.apple.loginwindow TALLogoutSavesState -bool false
  defaults -currentHost write com.apple.screensaver idleTime -int 0
  S pmset -a displaysleep 0 sleep 0
  sw_vers -productVersion; csrutil status; spctl --status 2>&1
  which brew xcodebuild python3 2>&1 | sed "s/^/which: /"
'
for i in $(seq 1 20); do $TART exec "$VM" true 2>/dev/null && { echo "tart exec: works"; exit 0; }; sleep 2; done
echo "tart exec: not answering yet"; exit 1
