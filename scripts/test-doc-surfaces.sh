#!/usr/bin/env bash
# test-doc-surfaces.sh — prove check-doc-surfaces.sh fires, and on what.
#
# A gate that reports 0 gaps on a clean tree is either correct or blind, and the
# two look identical from outside. This suite makes the difference visible:
# it injects each failure the gate exists to catch and asserts it is caught.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# The injection below edits a TRACKED file. Without a trap, anything that kills
# this script between injection and restore — a timeout, Ctrl-C, a failing
# assertion under `set -e` — leaves the man page damaged and the next run of
# check-doc-surfaces.sh reports a gap that does not exist. That happened: a
# 2-minute cap on a batch run killed this mid-injection and the tree carried a
# missing --llm until someone noticed. Restore from git, always, on every exit
# path. test-preflight-gates.sh already does this; this file did not.
#
# Restore from a snapshot of the PRE-TEST file, not from git. `git checkout --`
# discards whatever was in the working tree, which during a release is the
# version bump: bump-version.py writes the new version into this man page and
# leaves it unstaged, so running this suite mid-release silently reverted it to
# HEAD. Cost a confusing preflight failure on 27 Aug 2026 — "man page .TH says
# 0.27.0, expected 0.28.0" against a bump that had demonstrably succeeded.
# Falls back to git only if the snapshot was never taken (an abort before the
# cp below), which is the only case where HEAD is the best available answer.
_MAN_SRC="$ROOT/bristlenose/data/bristlenose.1"
_MAN_PRISTINE=$(mktemp "${TMPDIR:-/tmp}/bn-man-pristine.XXXXXX")
cp "$_MAN_SRC" "$_MAN_PRISTINE"
_restore() {
    if [ -s "$_MAN_PRISTINE" ]; then
        cp "$_MAN_PRISTINE" "$_MAN_SRC"
    else
        git -C "$ROOT" checkout -- bristlenose/data/bristlenose.1 2>/dev/null || true
    fi
    rm -f "$_MAN_PRISTINE"
}
trap _restore EXIT INT TERM

. "$(dirname "$0")/test-lib.sh"

DOC_SURFACES_LIB=1 . "$ROOT/scripts/check-doc-surfaces.sh"

head_ "normalise_roff — the trap that produced a whole audit pass of false positives"
eq "option name escaping"  "--whisper-model" "$(printf '\\-\\-whisper\\-model' | normalise_roff)"
eq "bold font escapes"     "--llm"           "$(printf '\\fB\\-\\-llm\\fR'     | normalise_roff)"
eq "italic font escapes"   "--output"        "$(printf '\\fI\\-\\-output\\fP'  | normalise_roff)"
eq "zero-width marker"     "--dev"           "$(printf '\\&\\-\\-dev'          | normalise_roff)"
eq "plain text untouched"  "already --fine"  "$(printf 'already --fine'        | normalise_roff)"
eq "combined"              "--no-fetch"      "$(printf '\\fB\\-\\-no\\-fetch\\fR' | normalise_roff)"

head_ "normalise_roff — proof the naive form fails (this is why the fn exists)"
_naive=$(printf '\\-\\-whisper\\-model' | grep -oE '\-\-[a-z-]+' || echo NONE)
eq "naive grep finds nothing usable" "NONE" "$_naive"

head_ "verdict_flag — README and cli.md are curated, man is complete"
eq "everywhere"                 ok      "$(verdict_flag --x 1 1 1)"
eq "man+readme, no website repo" ok     "$(verdict_flag --x 1 1 absent)"
eq "absent from both in-repo"   missing "$(verdict_flag --x 0 0 absent)"
eq "in man only"                partial "$(verdict_flag --x 0 1 absent)"
eq "in readme only"             partial "$(verdict_flag --x 1 0 absent)"
eq "missing from website only"  partial "$(verdict_flag --x 1 1 0)"

head_ "ANSI — a coloured CLI must still enumerate (the CI-only failure)"
# GitHub Actions sets FORCE_COLOR, so Rich colours --help even off a tty, and
# the escape lands BEFORE the leading spaces the enumeration anchors on. This
# returned 0 subcommands on the first Linux run while passing locally, where
# Rich renders plain. Asserted through the real gate, both ways round.
_plain=$(BN_BIN="" bash -c '. "$0" 2>/dev/null' "$ROOT/scripts/check-doc-surfaces.sh" 2>/dev/null; \
         "$ROOT/.venv/bin/bristlenose" --help 2>/dev/null | wc -l | tr -d ' ')
_n_colour=$(FORCE_COLOR=1 "$ROOT/.venv/bin/bristlenose" --help 2>/dev/null \
    | sed -e "s/$(printf '\033')\[[0-9;]*m//g" -e 's/[│┃┆┇┊┋|]/ /g' -e 's/[╭╮╰╯─━]//g' \
    | sed -n '/Commands/,$p' | grep -oE '^ +[a-z][a-z-]+' | tr -d ' ' | sort -u | wc -l | tr -d ' ')
[ "${_n_colour:-0}" -ge 5 ] \
    && ok "coloured help still enumerates ($_n_colour subcommands)" \
    || bad "coloured help enumerates only ${_n_colour:-0} — ANSI stripping regressed"
FORCE_COLOR=1 bash "$ROOT/scripts/check-doc-surfaces.sh" >/dev/null 2>&1
eq "the gate passes under FORCE_COLOR" 0 "$?"

head_ "end-to-end — inject each real failure and assert it is caught"

# Baseline must be clean, or the injections prove nothing.
bash "$ROOT/scripts/check-doc-surfaces.sh" >/tmp/ds-base.log 2>&1
if [ $? -eq 0 ]; then ok "clean tree passes"; else bad "clean tree already fails — injections meaningless"; fi

# 1 · a flag vanishes from the man page (the complete reference).
MAN_REAL="$ROOT/bristlenose/data/bristlenose.1"      # man/ is a symlink to this
cp "$MAN_REAL" /tmp/man.bak
python3 - "$MAN_REAL" <<'PY'
import sys,pathlib,re
p=pathlib.Path(sys.argv[1]); s=p.read_text()
# remove every mention of --llm, in its roff-escaped form
# The man page carries this flag in BOTH forms — escaped (\-\-llm) inside .TP
# option blocks and PLAIN (--llm) inside .EX example blocks, where roff does not
# escape. An injection that removes only the escaped form leaves the flag findable
# and the gate correctly reports it present — which reads as "the gate is blind"
# and is really "the test is."
s = s.replace(r"\-\-llm", r"\-\-XXGONEXX").replace("--llm", "--XXGONEXX")
p.write_text(s)
PY
bash "$ROOT/scripts/check-doc-surfaces.sh" >/tmp/ds-inj.log 2>&1
rc=$?
cp /tmp/man.bak "$MAN_REAL"
if [ "$rc" -ne 0 ] && grep -q 'absent from the man page' /tmp/ds-inj.log; then
    ok "removing --llm from the man page fails the gate"
else
    bad "man-page removal NOT caught (exit $rc) — gate is blind"
    tail -5 /tmp/ds-inj.log | sed 's/^/      /'
fi

# 2 · help parsing breaks → must refuse, not pass by seeing nothing.
_stub=$(mktemp); printf '#!/bin/sh\necho "no commands here"\n' > "$_stub"; chmod +x "$_stub"
_out=$(BN_BIN="$_stub" bash "$ROOT/scripts/check-doc-surfaces.sh" 2>&1); rc=$?
rm -f "$_stub"
if [ "$rc" -eq 2 ] && printf '%s' "$_out" | grep -q 'help parsing is broken'; then
    ok "broken help parsing refuses (exit 2) rather than passing on 0 flags"
else
    bad "trivial-pass guard did not fire (exit $rc)"
    printf '%s' "$_out" | tail -3 | sed 's/^/      /'
fi

# 3 · restoration actually happened.
if diff -q /tmp/man.bak "$MAN_REAL" >/dev/null; then ok "man page restored"
else bad "MAN PAGE NOT RESTORED — restore from git immediately"; fi

head_ "meta"
# Snapshot BEFORE the deliberate failure. Comparing against 0 made this fire
# spuriously whenever the suite had genuine failures — a meta-check that reports
# a harness bug every time a real bug exists is worse than none.
_before=$FAIL
_r=$(eq "deliberate" ok missing 2>&1)
case "$_r" in *"expected 'ok', got 'missing'"*) ok "eq() reports a real mismatch" ;;
             *) bad "eq() cannot fail" ;; esac
[ "$FAIL" -eq "$_before" ] || bad "harness leaked the deliberate failure into the count"

finish
