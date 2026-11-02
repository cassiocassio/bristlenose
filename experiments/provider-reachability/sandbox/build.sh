#!/usr/bin/env bash
# Build the probe twice as a SANDBOXED bare executable (app-sandbox + network.client, the same
# two entitlements the app's network access rests on), differing only in the embedded Info.plist:
#   probe-sbx      no App Transport Security keys   (what the app has today)
#   probe-sbx-ats  ATS exception for captive.apple.com allowing plain HTTP
# A sandboxed bare Mach-O needs the embedded Info.plist or it traps with exit 133.
# Ad-hoc signed; no Developer ID needed. The first run creates a container under
# ~/Library/Containers/app.bristlenose.reachprobe* (delete those folders to clean up).
set -eu
here="$(cd "$(dirname "$0")" && pwd)"; out="$here/../.build"; mkdir -p "$out"
for v in "" "-ats"; do
  plist="$here/Info${v}.plist"; bin="$out/probe-sbx${v}"
  swiftc -O -swift-version 5 "$here/../probe.swift" -o "$bin" \
    -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker "$plist"
  codesign --force --sign - --entitlements "$here/sandbox.entitlements" --identifier "$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$plist")" "$bin"
  echo "built $bin"
done
