#!/usr/bin/env bash
# test-dmg-lane.sh — the .dmg lane skips only what build-all already proved.
#
#     bash scripts/test-dmg-lane.sh
#
# The Swift suite's green receipt (desktop/scripts/test-swift.sh, 8 Oct 2026):
# inside a release run a green verdict writes run + commit + a whole-tree
# fingerprint, and build-dmg.sh skips its own second run of the suite only when
# `test-swift.sh --green-here` matches. A receipt that matches when it should not
# would ship a .dmg on a suite nobody ran against its tree, so every way it must
# NOT match is a case here, driven end to end: the real script, copied into a
# throwaway git repo, with a fake `xcodebuild` on PATH that passes, fails, or
# edits the tree while "the suite" runs. No Xcode needed, so it runs on Linux CI.
#
# Every assertion is proven to fail on its own violation — see meta_check in
# test-lib.sh (docs/design-test-philosophy.md).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
. "$(dirname "$0")/test-lib.sh"

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
REPO="$WORK/repo"
mkdir -p "$REPO/desktop/scripts" "$REPO/desktop/Bristlenose" "$WORK/bin"
cp "$ROOT/desktop/scripts/test-swift.sh" "$REPO/desktop/scripts/"
printf 'desktop/build/\n' > "$REPO/.gitignore"
printf 'one\n' > "$REPO/desktop/Bristlenose/App.swift"
git -C "$REPO" init -q && git -C "$REPO" add -A \
    && git -C "$REPO" -c user.email=t@t -c user.name=t commit -qm init || { bad "could not build the fixture repo"; finish; }

# The fake xcodebuild. MODE=pass prints two verdicts and exits 0; MODE=fail prints
# a failing verdict and exits 65; MODE=edit passes but edits a tracked file while
# the "suite" runs — the tree the suite finished on is not the one it started on.
cat > "$WORK/bin/xcodebuild" <<'EOF'
#!/usr/bin/env bash
case " $* " in *" build-for-testing "*) exit 0 ;; esac
case "${MODE:-pass}" in
  pass) printf "Test case 'A.a()' passed on 'Mac' (0.1 seconds)\nTest case 'A.b()' passed on 'Mac' (0.1 seconds)\n"; exit 0 ;;
  fail) printf "Test case 'A.a()' failed on 'Mac' (0.1 seconds)\n"; exit 65 ;;
  edit) printf 'edited\n' >> "$EDIT_FILE"; printf "Test case 'A.a()' passed on 'Mac' (0.1 seconds)\n"; exit 0 ;;
esac
EOF
chmod +x "$WORK/bin/xcodebuild"

TS="$REPO/desktop/scripts/test-swift.sh"
STAMP="$REPO/desktop/build/swift-green.stamp"
suite() { env PATH="$WORK/bin:$PATH" "$@" bash "$TS" --quiet >/dev/null 2>&1; echo $?; }
here()  { env PATH="$WORK/bin:$PATH" "$@" bash "$TS" --green-here >/dev/null 2>&1; echo $?; }

head_ "outside a release: no receipt"
eq "a green suite exits 0"                      0 "$(suite env -u BN_RELEASE_RUN MODE=pass)"
eq "…and writes no receipt"                     no "$([ -f "$STAMP" ] && echo yes || echo no)"
eq "--green-here without BN_RELEASE_RUN says no" 1 "$(here env -u BN_RELEASE_RUN)"

head_ "inside a release: a green run on this tree is honoured"
eq "a green suite in run 9.9.0 exits 0"          0 "$(suite env BN_RELEASE_RUN=9.9.0 MODE=pass)"
eq "…and writes the receipt"                     yes "$([ -f "$STAMP" ] && echo yes || echo no)"
eq "--green-here in the same run, same tree: yes" 0 "$(here env BN_RELEASE_RUN=9.9.0)"
eq "--green-here in a different run: no"          1 "$(here env BN_RELEASE_RUN=9.9.1)"

head_ "anything the suite did not see: no"
printf 'two\n' >> "$REPO/desktop/Bristlenose/App.swift"
eq "an uncommitted edit to a tracked file"       1 "$(here env BN_RELEASE_RUN=9.9.0)"
git -C "$REPO" checkout -q -- desktop/Bristlenose/App.swift
eq "…reverted: the same tree again"              0 "$(here env BN_RELEASE_RUN=9.9.0)"
mkdir -p "$REPO/bristlenose/locales/en" && printf '{}\n' > "$REPO/bristlenose/locales/en/common.json"
eq "a new untracked file OUTSIDE desktop/ (the test bundle copies locales in)" 1 "$(here env BN_RELEASE_RUN=9.9.0)"
rm -rf "$REPO/bristlenose"
printf 'x\n' > "$REPO/desktop/build/ignored.log"
eq "an ignored build product changes nothing"    0 "$(here env BN_RELEASE_RUN=9.9.0)"
printf 'three\n' >> "$REPO/desktop/Bristlenose/App.swift"
git -C "$REPO" -c user.email=t@t -c user.name=t commit -qam "a new commit"
eq "a new commit (HEAD moved)"                   1 "$(here env BN_RELEASE_RUN=9.9.0)"

head_ "a red run, or a tree that moved mid-suite, leaves no receipt"
eq "green again at the new commit"               0 "$(suite env BN_RELEASE_RUN=9.9.0 MODE=pass)"
eq "…honoured"                                   0 "$(here env BN_RELEASE_RUN=9.9.0)"
eq "a red suite exits 1"                         1 "$(suite env BN_RELEASE_RUN=9.9.0 MODE=fail)"
eq "…and removes the earlier receipt"            no "$([ -f "$STAMP" ] && echo yes || echo no)"
eq "--green-here after a red run: no"            1 "$(here env BN_RELEASE_RUN=9.9.0)"
eq "a suite whose tree moves while it runs exits 0 (the verdict is still green)" 0 \
    "$(suite env BN_RELEASE_RUN=9.9.0 MODE=edit EDIT_FILE="$REPO/desktop/Bristlenose/App.swift")"
eq "…but writes no receipt"                      no "$([ -f "$STAMP" ] && echo yes || echo no)"
git -C "$REPO" checkout -q -- desktop/Bristlenose/App.swift

head_ "build-dmg.sh asks the receipt, and only skips on a yes"
# The real step-1b block, cut from build-dmg.sh and run with a stub test-swift.sh,
# so what is asserted is the branch the release takes, not a string in the file.
blk="$(awk '/^say "Swift unit suite \(BristlenoseTests\)"$/{f=1} f{print} f&&/^fi$/{exit}' "$ROOT/desktop/scripts/build-dmg.sh")"
case "$blk" in *"--green-here"*) ok "step 1b consults --green-here" ;; *) bad "step 1b no longer consults --green-here" ;; esac
mkdir -p "$WORK/stub"
cat > "$WORK/stub/test-swift.sh" <<'EOF'
#!/usr/bin/env bash
if [ "${1:-}" = "--green-here" ]; then [ "${STUB_GREEN:-0}" = 1 ] && { echo "green at deadbeef"; exit 0; }; exit 1; fi
echo RAN-THE-SUITE; exit 0
EOF
chmod +x "$WORK/stub/test-swift.sh"
step1b() { env "$@" bash -c "say(){ :; }; ok(){ printf '%s\n' \"\$*\"; }; die(){ echo DIED; exit 1; }; SCRIPT_DIR='$WORK/stub'
$blk" 2>&1; }
out="$(step1b STUB_GREEN=1)"
case "$out" in *"not re-run — green at deadbeef"*) ok "a matching receipt: skipped, and it says why" ;; *) bad "matching receipt: $out" ;; esac
case "$out" in *RAN-THE-SUITE*) bad "…but the suite ran anyway" ;; *) ok "…and the suite did not run" ;; esac
out="$(step1b STUB_GREEN=0)"
case "$out" in *RAN-THE-SUITE*) ok "no receipt: the suite runs" ;; *) bad "no receipt, yet the suite did not run: $out" ;; esac
out="$(step1b STUB_GREEN=1 SKIP_SWIFT_TESTS=1)"
case "$out" in *"SKIP_SWIFT_TESTS=1"*) ok "SKIP_SWIFT_TESTS still wins, and still says so" ;; *) bad "SKIP_SWIFT_TESTS: $out" ;; esac

meta_check
finish
