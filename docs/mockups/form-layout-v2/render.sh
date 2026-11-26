#!/bin/bash
# Builds render.swift into a throwaway app bundle (so its window can become key and draw the
# accent colour), runs it, and leaves the PNGs and manifest.txt beside this script.
# Run from anywhere:  docs/mockups/form-layout-v2/render.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
TMP="$(mktemp -d)"
APP="$TMP/FormRender.app"
mkdir -p "$APP/Contents/MacOS"
swiftc -O "$HERE/render.swift" -o "$APP/Contents/MacOS/FormRender"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>FormRender</string>
<key>CFBundleIdentifier</key><string>local.bristlenose.form-render</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleName</key><string>FormRender</string>
</dict></plist>
PLIST
codesign -s - --force "$APP" >/dev/null 2>&1
open -W "$APP" --args "$ROOT"
rm -rf "$TMP"
cat "$HERE/manifest.txt"
