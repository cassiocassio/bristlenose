#!/bin/bash
# tunnel.sh up|down — the guest's localhost:11434 becomes the host's Ollama.
#
# The Mac app hardwires Ollama at localhost:11434 (LLMSettingsView.swift), so a
# reverse ssh forward is the only route that needs no change to the app, and it
# keeps the guest clean: no Ollama, no model download, the model runs on the
# host's GPU. Same mechanism as guest-run.sh's harness mode.
# `up` proves the forward answers INSIDE the guest on both loopback families
# (the app asks 127.0.0.1 for /api/tags and localhost for /v1), or fails.
set -uo pipefail
export TART_HOME=/Volumes/Iona/tart
VM="${GUEST:-bn-walk}"
PIDF="/tmp/bn-walk-tunnel-$VM.pid"
case "${1:-}" in
  up)
    curl -s -m 3 http://127.0.0.1:11434/api/tags >/dev/null || { echo "host Ollama is not answering"; exit 1; }
    IP=$(${TART_BIN:-$HOME/Applications/tart.app/Contents/MacOS/tart} ip "$VM") || exit 1
    [ -f "$PIDF" ] && kill "$(cat "$PIDF")" 2>/dev/null
    ssh -i "$HOME/.ssh/id_ed25519_tartvm" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        -o IdentitiesOnly=yes -o LogLevel=ERROR -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 \
        -N -R 127.0.0.1:11434:127.0.0.1:11434 -R "[::1]:11434:127.0.0.1:11434" admin@"$IP" &
    echo $! > "$PIDF"
    for i in $(seq 1 20); do
      if "$(dirname "$0")/g.sh" sh -c 'curl -s -m 3 http://127.0.0.1:11434/api/tags >/dev/null && curl -s -m 3 "http://localhost:11434/v1/models" >/dev/null'; then
        echo "tunnel up (pid $(cat "$PIDF")): guest localhost:11434 -> host Ollama"; exit 0
      fi
      sleep 1
    done
    echo "tunnel did not answer inside the guest"; exit 1 ;;
  down)
    [ -f "$PIDF" ] && kill "$(cat "$PIDF")" 2>/dev/null; rm -f "$PIDF"; echo "tunnel down" ;;
  *) echo "usage: tunnel.sh up|down"; exit 2 ;;
esac
