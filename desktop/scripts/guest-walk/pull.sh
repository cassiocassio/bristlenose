#!/bin/bash
# pull.sh <guest-dir> <host-dir> — copy a guest directory back to the host over ssh.
# The tart share is read-only by design (VirtioFS serves stale bytes for rewrites).
set -uo pipefail
export TART_HOME="${TART_HOME:-/Volumes/Iona/tart}"
IP=$(${TART_BIN:-$HOME/Applications/tart.app/Contents/MacOS/tart} ip "${GUEST:-bn-walk}") || exit 1
mkdir -p "$2"
rsync -a --delete --exclude walk.log --exclude verdict.txt --exclude run-end.json -e "ssh -i $HOME/.ssh/id_ed25519_tartvm -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o IdentitiesOnly=yes -o LogLevel=ERROR" \
  "admin@$IP:$1/" "$2/"
