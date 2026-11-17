#!/bin/bash
# Run Script phase of the app target: put the Background Assets extension into the STORE build.
#
# Does nothing unless BN_EMBED_BA=YES (set only by the store lane, `build-all.sh`, on the
# command line). The .dmg lane, IDE builds and the other schemes never set it, and the
# extension target is built only by the "Bristlenose Store" scheme, so nothing else ever builds,
# signs or registers it (the Background Assets plan, release lanes section).
#
# With BN_EMBED_BA=YES it (1) copies BAExtension.appex into Contents/PlugIns, (2) adds the
# host's Background Assets keys to the built Info.plist: BAAppGroupID (the team-prefixed group
# the extension shares, which needs no portal registration), BAHasManagedAssetPacks and
# BAUsesAppleHosting. Custom keys cannot be set through INFOPLIST_KEY_ build settings, and
# the Developer-ID .dmg must not carry them (check-dmg-shippable.sh refuses them). Script
# phases run before the app is signed, so the plist edit is inside the seal.
#
# Refuses (rather than skipping) when asked to embed but it cannot: a store build that quietly
# lacks the extension is the failure this exists to prevent.
set -euo pipefail

if [ "${BN_EMBED_BA:-NO}" != "YES" ]; then
    # Not a store build. An earlier store build in the same derived data may have left the
    # extension and the host's BA keys behind (an incremental build does not always rebuild
    # Info.plist): remove them, so this build can never carry them by accident.
    removed=""
    STALE="${TARGET_BUILD_DIR:-/nonexistent}/${CONTENTS_FOLDER_PATH:-x}/PlugIns/BAExtension.appex"
    if [ -e "$STALE" ]; then rm -rf "$STALE"; removed="a stale extension"; fi
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

# Where the product is: BUILT_PRODUCTS_DIR in both a plain build and an archive (measured 17 Nov
# 2026: during an archive that is the ArchiveIntermediates products path, and the app, which is
# built after the extension, finds it there). The other two are fallbacks for a layout change.
SRC=""
for cand in "$BUILT_PRODUCTS_DIR/BAExtension.appex" \
            "$BUILD_DIR/UninstalledProducts/macosx/BAExtension.appex" \
            "$(dirname "$BUILT_PRODUCTS_DIR")/UninstalledProducts/macosx/BAExtension.appex"; do
    if [ -d "$cand" ]; then SRC="$cand"; break; fi
done
if [ -z "$SRC" ]; then
    echo "error: embed-ba-extension: BAExtension.appex not found under BUILT_PRODUCTS_DIR or UninstalledProducts." >&2
    echo "       Build the \"Bristlenose Store\" scheme (it lists BAExtension before the app)." >&2
    exit 1
fi

# Check everything the plist step needs BEFORE copying anything, so a refusal leaves nothing behind.
PLIST="$TARGET_BUILD_DIR/$INFOPLIST_PATH"
[ -f "$PLIST" ] || { echo "error: embed-ba-extension: no Info.plist at $PLIST" >&2; exit 1; }
GROUP="${DEVELOPMENT_TEAM:?DEVELOPMENT_TEAM is not set}.app.bristlenose"

DEST="$TARGET_BUILD_DIR/$CONTENTS_FOLDER_PATH/PlugIns"
mkdir -p "$DEST"
rm -rf "$DEST/BAExtension.appex"
ditto "$SRC" "$DEST/BAExtension.appex"
echo "embed-ba-extension: embedded $SRC"

PB=/usr/libexec/PlistBuddy
for kv in "BAAppGroupID:string:$GROUP" "BAHasManagedAssetPacks:bool:true" "BAUsesAppleHosting:bool:true"; do
    key="${kv%%:*}"; rest="${kv#*:}"; type="${rest%%:*}"; val="${rest#*:}"
    "$PB" -c "Delete :$key" "$PLIST" >/dev/null 2>&1 || true
    "$PB" -c "Add :$key $type $val" "$PLIST"
done
echo "embed-ba-extension: Info.plist carries BAAppGroupID=$GROUP, BAHasManagedAssetPacks, BAUsesAppleHosting"
