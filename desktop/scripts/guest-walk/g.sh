#!/bin/bash
# g.sh <cmd…> — run a command inside the walk guest (tart exec), from the host.
# GUEST overrides the guest name (default bn-walk).
export TART_HOME="${TART_HOME:-/Volumes/Iona/tart}"
exec ${TART_BIN:-$HOME/Applications/tart.app/Contents/MacOS/tart} exec "${GUEST:-bn-walk}" "$@"
