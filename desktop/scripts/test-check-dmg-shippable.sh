#!/usr/bin/env bash
# Negative fixtures for check-dmg-shippable.sh.
#
# This is the publish gate. On 4 Aug 2026 a complete, correctly named .dmg sat on disk for 14 hours
# looking finished while spctl said "Unnotarized Developer ID", because a failure printed nothing and
# fell through to the success banner. A gate that cannot fail would reproduce that, so every check
# is driven red here on its own, and a tree where everything holds must pass.
#
# The gate reaches macOS only through codesign, xcrun stapler, spctl and hdiutil (and the real
# PlistBuddy), and runs three sibling gates by its own path. So each case copies the gate into a
# scratch directory beside stub siblings, puts stub tools first on PATH, and lets an environment
# variable decide each stub's verdict; "mounting" copies a prepared tree. No signing, no network,
# no image. Needs macOS (PlistBuddy); skipped elsewhere.
#
# BN_REPORT=0 turns off the report renderer, which would otherwise swallow the gate's own lines.
#
# Usage: test-check-dmg-shippable.sh
# Exit:  0 all cases behaved (or skipped) · 1 at least one gate failed to fail (or failed a clean tree)
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ "$(uname)" != Darwin ] || [ ! -x /usr/libexec/PlistBuddy ]; then
    echo "check-dmg-shippable: skipped — needs macOS (PlistBuddy)"; exit 0
fi
[ -f "$SCRIPT_DIR/check-dmg-shippable.sh" ] || { echo "gate not found" >&2; exit 2; }

TMP=$(mktemp -d "${TMPDIR:-/tmp}/bn-dmg-test.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0

# --- the scratch scripts directory: the real gate + report.sh, and stub sibling gates ----------------
S="$TMP/scripts"; mkdir -p "$S" "$TMP/bin"
cp "$SCRIPT_DIR/check-dmg-shippable.sh" "$SCRIPT_DIR/report.sh" "$S/"
[ -f "$SCRIPT_DIR/sink.sh" ] && cp "$SCRIPT_DIR/sink.sh" "$S/"
for sib in check-mcp-helper:STUB_MCP check-speech-helper:STUB_SPEECH check-sidecar-mlx-floor:STUB_MLX; do
    name="${sib%%:*}"; var="${sib##*:}"
    printf '#!/bin/sh\nif [ "${%s:-ok}" = ok ]; then echo ok; exit 0; fi\necho "FAIL: %s said no"; exit 1\n' "$var" "$name" > "$S/$name.sh"
    chmod +x "$S/$name.sh"
done

# --- the stub tools -------------------------------------------------------------------------------
cat > "$TMP/bin/codesign" <<'STUB'
#!/bin/sh
case "$*" in
  *"--verify --verbose=2"*)   [ "${STUB_SIG_IMG:-ok}" = ok ] ;;
  *"--verify --deep --strict"*) [ "${STUB_SIG_APP:-ok}" = ok ] ;;
  *"--entitlements"*)         [ -n "${STUB_ENTS_FILE:-}" ] && cat "$STUB_ENTS_FILE"; exit 0 ;;
  *"-dvvv"*)                  echo "Timestamp=$STUB_TS" >&2 ;;
esac
STUB
cat > "$TMP/bin/xcrun" <<'STUB'
#!/bin/sh
[ "${STUB_STAPLE:-ok}" = ok ]
STUB
cat > "$TMP/bin/spctl" <<'STUB'
#!/bin/sh
case "$*" in
  *"--type open"*) v="${STUB_GK_IMG:-ok}" ;;
  *)               v="${STUB_GK_APP:-ok}" ;;
esac
if [ "$v" = ok ]; then echo "accepted"; echo "source=Notarized Developer ID"; else echo "rejected"; echo "source=Unnotarized Developer ID"; fi
STUB
cat > "$TMP/bin/hdiutil" <<'STUB'
#!/bin/sh
case "$1" in
  attach) [ "${STUB_MOUNT:-ok}" = ok ] || exit 1
          mp=""; while [ $# -gt 0 ]; do [ "$1" = "-mountpoint" ] && mp="$2"; shift; done
          cp -R "$FIX_TREE"/. "$mp"/ ;;
  *) exit 0 ;;
esac
STUB
chmod +x "$TMP/bin/"*

# --- fixtures ---------------------------------------------------------------------------------------
ENTS_GOOD="$TMP/ents-good.plist"
printf '%s\n' '<plist><dict><key>com.apple.security.application-groups</key><array><string>Z56GZVA2QB.app.bristlenose</string></array></dict></plist>' > "$ENTS_GOOD"
ENTS_NOGROUP="$TMP/ents-nogroup.plist"; printf '%s\n' '<plist><dict></dict></plist>' > "$ENTS_NOGROUP"
ENTS_MAS="$TMP/ents-mas.plist"
printf '%s\n' '<plist><dict><key>com.apple.security.application-groups</key><array><string>group.app.bristlenose</string></array></dict></plist>' > "$ENTS_MAS"
ENTS_OTHER="$TMP/ents-other.plist"
printf '%s\n' '<plist><dict><key>com.apple.security.application-groups</key><array><string>ZZZZZZZZZZ.app.bristlenose</string></array></dict></plist>' > "$ENTS_OTHER"
ENTS_PRINT="$TMP/ents-print.plist"
printf '%s\n' '<plist><dict><key>com.apple.security.application-groups</key><array><string>Z56GZVA2QB.app.bristlenose</string></array><key>com.apple.security.print</key><true/></dict></plist>' > "$ENTS_PRINT"

TS="$(date -u '+%d %b %Y at %H:%M:%S UTC')"

# A "mounted image" tree. <name> <version> [omit-key] ; echoes its path.
tree() {
    local t="$TMP/tree-$1" v="${2:-1.2.3}" omit="${3:-}"
    mkdir -p "$t/Bristlenose.app/Contents/MacOS" "$t/Bristlenose.app/Contents/Helpers" "$t/Bristlenose.app/Contents/Resources/bristlenose-sidecar"
    printf 'binary-%s\n' "$1" > "$t/Bristlenose.app/Contents/MacOS/Bristlenose"
    printf 'speech\n' > "$t/Bristlenose.app/Contents/Helpers/bristlenose-speech"
    {
        echo '<?xml version="1.0" encoding="UTF-8"?><plist version="1.0"><dict>'
        echo "<key>CFBundleShortVersionString</key><string>$v</string>"
        for k in MicrosoftOAuthClientID MicrosoftOAuthRedirectURI GoogleOAuthClientID ZoomOAuthPublicClientID ZoomOAuthRedirectURI; do
            [ "$k" = "$omit" ] && continue
            echo "<key>$k</key><string>real-value-$k</string>"
        done
        echo '</dict></plist>'
    } > "$t/Bristlenose.app/Contents/Info.plist"
    echo "$t"
}

# A sibling manifest agreeing with a tree's binary.
manifest() {  # <dmg> <tree> [tree-line]
    local sha; sha=$(shasum -a 256 "$2/Bristlenose.app/Contents/MacOS/Bristlenose" | cut -d' ' -f1)
    { echo "commit: 0123456789abcdef"; echo "tree: ${3:-clean}"; echo "  $sha  Bristlenose.app/Contents/MacOS/Bristlenose"; } > "${1%.dmg}.manifest.txt"
}

# run <label> <want-exit> <needle> <dmg> <tree> [ENV=value ...]
run() {
    local label="$1" want="$2" needle="$3" dmg="$4" tr="$5"; shift 5
    local out rc
    out=$(env BN_REPORT=0 STUB_TS="$TS" STUB_ENTS_FILE="$ENTS_GOOD" FIX_TREE="$tr" PATH="$TMP/bin:$PATH" "$@" \
            bash "$S/check-dmg-shippable.sh" "$dmg" 2>&1); rc=$?
    if [ "$rc" -ne "$want" ]; then
        echo "  ✗ $label: exit $rc, wanted $want"; echo "$out" | sed 's/^/      /' | rg "✗|FAIL|fail" | head -4; FAIL=$((FAIL+1)); return
    fi
    if [ -n "$needle" ] && ! printf '%s' "$out" | grep -qF -- "$needle"; then
        echo "  ✗ $label: exit $rc but no \"$needle\""; echo "$out" | sed 's/^/      /' | head -6; FAIL=$((FAIL+1)); return
    fi
    echo "  ✓ $label"; PASS=$((PASS+1))
}

DMG="$TMP/Bristlenose-1.2.3.dmg"; : > "$DMG"
GOOD=$(tree good); manifest "$DMG" "$GOOD"

echo "check-dmg-shippable negative fixtures"

run "a tree where every check holds is shippable" 0 "signed · notarised" "$DMG" "$GOOD"

UNV="$TMP/Bristlenose.dmg"; : > "$UNV"
run "an unversioned artefact is refused" 1 "refusing an unversioned artefact" "$UNV" "$GOOD"
run "an image whose signature does not verify is refused" 1 "codesign --verify failed on the .dmg" "$DMG" "$GOOD" STUB_SIG_IMG=bad
run "an image with no stapled ticket is refused" 1 "no ticket stapled" "$DMG" "$GOOD" STUB_STAPLE=bad
run "an image Gatekeeper rejects is refused (the 4 Aug incident)" 1 "image Gatekeeper" "$DMG" "$GOOD" STUB_GK_IMG=bad
run "an image that will not mount is refused" 1 "hdiutil could not attach" "$DMG" "$GOOD" STUB_MOUNT=bad

EMPTY="$TMP/tree-empty"; mkdir -p "$EMPTY"
run "an image with no app at its root is refused" 1 "no .app found" "$DMG" "$EMPTY"

SKEW=$(tree skew 9.9.9); manifest "$DMG" "$GOOD"
run "a filename and an app that disagree on the version are refused" 1 "filename says 1.2.3" "$DMG" "$SKEW"

for key in MicrosoftOAuthClientID MicrosoftOAuthRedirectURI GoogleOAuthClientID ZoomOAuthPublicClientID ZoomOAuthRedirectURI; do
    T=$(tree "no-$key" 1.2.3 "$key"); manifest "$DMG" "$T"
    run "a missing $key is refused" 1 "missing or placeholder" "$DMG" "$T"
done
PH=$(tree placeholder); sed -i '' 's/real-value-GoogleOAuthClientID/__GOOGLE_ID__/' "$PH/Bristlenose.app/Contents/Info.plist"; manifest "$DMG" "$PH"
run "a placeholder client ID is refused" 1 "missing or placeholder" "$DMG" "$PH"

manifest "$DMG" "$GOOD"
run "an inner app that fails codesign --deep --strict is refused" 1 "fails codesign --deep --strict" "$DMG" "$GOOD" STUB_SIG_APP=bad
run "an inner app Gatekeeper rejects is refused" 1 "inner app Gatekeeper" "$DMG" "$GOOD" STUB_GK_APP=bad

MCP=$(tree mcp); printf 'x\n' > "$MCP/Bristlenose.app/Contents/Helpers/bristlenose-mcp"; manifest "$DMG" "$MCP"
run "a native MCP helper that fails its gate is refused" 1 "native MCP helper" "$DMG" "$MCP" STUB_MCP=bad
run "a native MCP helper that passes its gate is fine" 0 "signed · notarised" "$DMG" "$MCP"

NOSP=$(tree nospeech); rm "$NOSP/Bristlenose.app/Contents/Helpers/bristlenose-speech"; manifest "$DMG" "$NOSP"
run "a missing Apple speech helper is refused" 1 "missing from the image" "$DMG" "$NOSP"
manifest "$DMG" "$GOOD"
run "an Apple speech helper that fails its gate is refused" 1 "Apple speech helper" "$DMG" "$GOOD" STUB_SPEECH=bad
run "a sidecar whose MLX is built for the wrong floor is refused" 1 "sidecar MLX floor" "$DMG" "$GOOD" STUB_MLX=bad

rm -f "${DMG%.dmg}.manifest.txt"
run "no sibling manifest only warns" 0 "signed · notarised" "$DMG" "$GOOD"
manifest "$DMG" "$SKEW"; sed -i '' '/^commit/!b' "${DMG%.dmg}.manifest.txt"
STALE=$(tree stale); printf 'a different build\n' > "$STALE/Bristlenose.app/Contents/MacOS/Bristlenose"
manifest "$DMG" "$GOOD"
run "a manifest describing a different build is refused" 1 "manifest describes a DIFFERENT build" "$DMG" "$STALE"
printf 'commit: 0123\ntree: clean\n' > "${DMG%.dmg}.manifest.txt"
run "a manifest whose hash cannot be read is refused" 1 "could not read both hashes" "$DMG" "$GOOD"
manifest "$DMG" "$GOOD" "dirty (3 files)"
run "a dirty-tree manifest only warns" 0 "signed · notarised" "$DMG" "$GOOD"
manifest "$DMG" "$GOOD"

run "no app group at all is refused" 1 "ABSENT" "$DMG" "$GOOD" STUB_ENTS_FILE="$ENTS_NOGROUP"
run "the Mac App Store group in a Developer-ID image is refused" 1 "group.app.bristlenose PRESENT" "$DMG" "$GOOD" STUB_ENTS_FILE="$ENTS_MAS"
run "a different team's group is refused" 1 "team group" "$DMG" "$GOOD" STUB_ENTS_FILE="$ENTS_OTHER"
run "the print entitlement is refused (printing is post-v1)" 1 "PRESENT — printing is post-v1" "$DMG" "$GOOD" STUB_ENTS_FILE="$ENTS_PRINT"
run "entitlements that cannot be read only warn" 0 "signed · notarised" "$DMG" "$GOOD" STUB_ENTS_FILE=

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
