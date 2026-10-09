#!/usr/bin/env bash
# Proof for scripts/check-doctor-install.sh: it passes a fresh install whose
# only failure is the API key, and fails everything else — including a doctor
# whose exit code disagrees with its own rows. Each case puts a fake
# `bristlenose` first on PATH that prints a doctor table and exits a set code.
#
# Run in install-test.yml (linux-pip) just before the real doctor step, so the
# checker is re-proven wherever it gates. Pure bash, no network.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
CHECK="$HERE/check-doctor-install.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fails=0
case_() {  # name, doctor exit code, expected checker exit code, doctor rows...
  local name=$1 code=$2 want=$3; shift 3
  {
    printf '#!/bin/sh\n'
    for row in "$@"; do printf 'printf "%%s\\n" "%s"\n' "$row"; done
    printf 'exit %s\n' "$code"
  } > "$TMP/bristlenose"
  chmod +x "$TMP/bristlenose"
  PATH="$TMP:$PATH" bash "$CHECK" >/dev/null 2>&1
  local got=$?
  if [ "$got" -eq "$want" ]; then
    echo "ok   $name (exit $got)"
  else
    echo "FAIL $name: checker exited $got, expected $want"
    fails=$((fails + 1))
  fi
}

case_ "only the API key fails"   1 0 " ✓ FFmpeg ok" " ✗ API key         No Anthropic API key"
case_ "nothing fails"            0 0 " ✓ FFmpeg ok" " ✓ API key ok"
case_ "FFmpeg fails too"         1 1 " ✗ FFmpeg not found" " ✗ API key none"
case_ "backend fails, key fine"  1 1 " ✗ Transcription  faster-whisper missing" " ✓ API key ok"
case_ "a fail row but exit 0"    0 1 " ✗ API key none"
case_ "no fail row but exit 1"   1 1 " ✓ FFmpeg ok"
case_ "doctor crashed (exit 2)"  2 1 "Traceback (most recent call last):"

if [ "$fails" -ne 0 ]; then
  echo "$fails case(s) failed"
  exit 1
fi
echo "all cases passed"
