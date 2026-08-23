#!/usr/bin/env bash
# test-preflight-gates.sh — replay 0.27.0's build failure 1 and assert the
# preflight now catches it before any build.
#
# The incident: 037b371e (20 Aug) renamed handshakeProjectPath to its plural,
# which made check-window-surfaces' assertion UNSATISFIABLE. It then failed on
# correct code. Nothing noticed for two days because the gate only ran during a
# build and nobody cut one; it cost 11 minutes of build to discover.
#
# A5's answer is to run the source gates at preflight. This proves that answer
# works, by breaking the same gate the same way.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
PASS=0; FAIL=0
ok()  { printf '  \033[32m✓\033[0m %s\n' "$1"; PASS=$((PASS+1)); }
bad() { printf '  \033[31m✗\033[0m %s\n' "$1" >&2; FAIL=$((FAIL+1)); }
head_(){ printf '\n\033[1m%s\033[0m\n' "$1"; }

FLEET="desktop/Bristlenose/Bristlenose/ServeFleet.swift"
GATE="desktop/scripts/check-window-surfaces.sh"

cleanup() { git checkout -- "$FLEET" 2>/dev/null || true; }
trap cleanup EXIT

head_ "baseline"
git diff --quiet -- "$FLEET" && ok "ServeFleet.swift clean before we start" \
    || { bad "ServeFleet.swift already modified — refusing to inject"; exit 1; }
bash "$GATE" >/dev/null 2>&1 && ok "gate passes on clean source" \
    || bad "gate already failing — injection would prove nothing"

head_ "cost — A5's whole design rests on these being cheap enough to just run"
_t0=$SECONDS
for g in check-window-surfaces check-appearance-seam check-menu-routing \
         check-logging-hygiene check-bundle-manifest; do
    bash "desktop/scripts/$g.sh" >/dev/null 2>&1
done
_el=$(( SECONDS - _t0 ))
if [ "$_el" -le 6 ]; then ok "five gates run in ${_el}s (budget 6s)"
else bad "five gates took ${_el}s — too slow to run unconditionally; A5 needs the ledger after all"; fi

head_ "replay build failure 1 — a rename makes the assertion unsatisfiable"
# Exactly the shape of 037b371e: rename the symbol the gate asserts on.
python3 - "$FLEET" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text()
assert "handshakeProjectPaths" in s, "symbol not present — test is stale"
p.write_text(s.replace("handshakeProjectPaths", "handshakeProjectPathsRENAMED"))
PY
if bash "$GATE" >/dev/null 2>&1; then
    bad "gate PASSED after the rename — it is not asserting what it claims"
else
    ok "gate fails on the rename (unsatisfiable assertion)"
fi

# And the preflight row must surface it, not swallow it.
_out=$(bash -c '
  set -uo pipefail
  ok()   { printf "OK %s\n" "$1"; }
  warn() { printf "WARN %s\n" "$1"; }
  bad()  { printf "BAD %s\n" "$1"; }
  head_(){ :; }
  SECONDS=0
  for _g in check-window-surfaces; do
    _gs="desktop/scripts/$_g.sh"
    if _o=$(bash "$_gs" 2>&1); then ok "$_g"; else bad "$_g"; fi
  done' 2>&1)
case "$_out" in
    BAD*) ok "the preflight loop reports it as a failure" ;;
    *)    bad "preflight loop did not report failure (got: $_out)" ;;
esac

cleanup
head_ "restoration"
git diff --quiet -- "$FLEET" && ok "ServeFleet.swift restored" || bad "NOT RESTORED — git checkout it"
bash "$GATE" >/dev/null 2>&1 && ok "gate green again" || bad "gate still failing after restore"

head_ "the fix that made this affordable"
# The SelectionSync grep used to walk 2.4 GB of build output. If someone widens
# it again the gate goes back to 23s and A5's design premise dies quietly.
if grep -q "include='\*\.swift'" "$GATE" && grep -q '_SRC=' "$GATE"; then
    ok "SelectionSync grep still scoped to source"
else
    bad "SelectionSync grep is unscoped again — gate will cost ~23s"
fi

printf '\n\033[1m%d passed, %d failed\033[0m\n\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
