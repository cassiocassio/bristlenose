#!/usr/bin/env bash
# Run `bristlenose doctor` on a fresh install and fail on anything except the
# one failure a fresh install is supposed to have: no API key.
#
# Used by .github/workflows/install-test.yml. Those jobs install from source on
# runners that carry no provider key, so doctor's API-key row is ✗ and doctor
# exits 1 (since 9 Oct 2026; before that it exited 0 whatever it found, and the
# jobs ran it as `doctor || true`, which checked nothing). What the jobs want to
# know is that FFmpeg, the transcription backend and the Python dependencies
# were found — so every OTHER ✗ row is a failure here.
#
# Exit 0: doctor ran, and the API key is the only failing check (or none fail).
# Exit 1: another check failed, or doctor's exit code disagrees with its rows.
set -uo pipefail

out=$(bristlenose doctor 2>&1)
rc=$?
printf '%s\n' "$out"

fail_rows=$(printf '%s\n' "$out" | grep -E '^[[:space:]]*✗' || true)
other_fails=$(printf '%s\n' "$fail_rows" | grep -v 'API key' | grep -v '^$' || true)

if [ -n "$other_fails" ]; then
  echo "::error::bristlenose doctor reported failures besides the API key:"
  printf '%s\n' "$other_fails"
  exit 1
fi
if [ -n "$fail_rows" ] && [ "$rc" -ne 1 ]; then
  echo "::error::doctor showed a failed check but exited $rc (expected 1)"
  exit 1
fi
if [ -z "$fail_rows" ] && [ "$rc" -ne 0 ]; then
  echo "::error::doctor showed no failed check but exited $rc (expected 0)"
  exit 1
fi
echo "doctor: exit $rc; no failures besides the API key"
