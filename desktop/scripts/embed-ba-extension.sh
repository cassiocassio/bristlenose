#!/bin/bash
# Run Script phase of the app target ("Background Assets Host Keys"): the store build's other half of
# embedding the Background Assets extension.
#
# The extension itself is embedded by a real Xcode Copy Files phase ("Embed ExtensionKit Extensions",
# into Contents/Extensions), because Xcode must embed and sign it: a hand-copied, re-signed extension
# was measured never to start (spike, 17 Nov 2026). That phase is skipped unless BN_EMBED_BA=YES
# (EXCLUDED_SOURCE_FILE_NAMES), and only the "Bristlenose Store" scheme builds the extension, so the
# .dmg lane, IDE builds and the other schemes never embed, build, sign or register it.
#
# This script does the part Xcode has no setting for. With BN_EMBED_BA=YES (set only by build-all.sh) it
# verifies the extension really is in the bundle and adds the host's Background Assets keys to the built
# Info.plist: BAAppGroupID (the team-prefixed group the extension shares, which needs no portal
# registration), BAHasManagedAssetPacks and BAUsesAppleHosting. Custom keys cannot be set through
# INFOPLIST_KEY_ build settings, and the Developer-ID .dmg must not carry them (check-dmg-shippable.sh
# refuses them). Script phases run before the app is signed, so the plist edit is inside the seal.
# Without the flag it removes a stale extension and the keys an earlier store build may have left.
#
# Refuses (rather than skipping) when asked to embed but it cannot: a store build that quietly lacks the
# extension is the failure this exists to prevent.
set -euo pipefail

if [ "${BN_EMBED_BA:-NO}" != "YES" ]; then
    removed=""
    for dir in Extensions PlugIns; do
        STALE="${TARGET_BUILD_DIR:-/nonexistent}/${CONTENTS_FOLDER_PATH:-x}/$dir/BAExtension.appex"
        if [ -e "$STALE" ]; then rm -rf "$STALE"; removed="${removed:+$removed, }a stale extension in $dir"; fi
    done
    PLIST="${TARGET_BUILD_DIR:-}/${INFOPLIST_PATH:-}"
    if [ -n "${TARGET_BUILD_DIR:-}" ] && [ -f "$PLIST" ]; then
        for key in BAAppGroupID BAHasManagedAssetPacks BAUsesAppleHosting; do
            if /usr/libexec/PlistBuddy -c "Delete :$key" "$PLIST" >/dev/null 2>&1; then
                removed="${removed:+$removed, }stale key $key"
            fi
        done
    fi
    echo "embed-ba-extension: BN_EMBED_BA is not YES; nothing embedded${removed:+ (removed: $removed)}"
    exit 0
fi
case " ${SWIFT_ACTIVE_COMPILATION_CONDITIONS:-} " in
    *" DEVELOPER_ID_BETA "*)
        echo "error: embed-ba-extension: BN_EMBED_BA=YES in a DEVELOPER_ID_BETA build; the .dmg never carries the extension" >&2
        exit 1 ;;
esac

APPEX="$TARGET_BUILD_DIR/$CONTENTS_FOLDER_PATH/Extensions/BAExtension.appex"
if [ ! -d "$APPEX" ]; then
    echo "error: embed-ba-extension: BN_EMBED_BA=YES but $APPEX is not in the bundle." >&2
    echo "       Build the \"Bristlenose Store\" scheme (it lists BAExtension before the app), and check the" >&2
    echo "       \"Embed ExtensionKit Extensions\" phase was not excluded (BN_EMBED_BA must reach the build as YES)." >&2
    exit 1
fi
PLIST="$TARGET_BUILD_DIR/$INFOPLIST_PATH"
[ -f "$PLIST" ] || { echo "error: embed-ba-extension: no Info.plist at $PLIST" >&2; exit 1; }
GROUP="${DEVELOPMENT_TEAM:?DEVELOPMENT_TEAM is not set}.app.bristlenose"
PB=/usr/libexec/PlistBuddy
for kv in "BAAppGroupID:string:$GROUP" "BAHasManagedAssetPacks:bool:true" "BAUsesAppleHosting:bool:true"; do
    key="${kv%%:*}"; rest="${kv#*:}"; type="${rest%%:*}"; val="${rest#*:}"
    "$PB" -c "Delete :$key" "$PLIST" >/dev/null 2>&1 || true
    "$PB" -c "Add :$key $type $val" "$PLIST"
done
echo "embed-ba-extension: extension present; Info.plist carries BAAppGroupID=$GROUP, BAHasManagedAssetPacks, BAUsesAppleHosting"
