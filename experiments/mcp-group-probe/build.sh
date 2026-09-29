#!/bin/zsh
# Build the two group-route probes from 29 Sep 2026 (docs/design-mcp-native-proxy.md §6.2).
#   probe          C file probe: LIST/WRITE/READ/UNLINK paths, prints its responsible pid.
#   group-probe    Swift stdio MCP server with one tool, `group_probe`, packaged as .mcpb.
# Needs SIGN_IDENTITY on team Z56GZVA2QB (e.g. "Developer ID Application: … (Z56GZVA2QB)").
# Output goes to $OUT (default: a fresh temp dir). Nothing is installed.
set -euo pipefail
: "${SIGN_IDENTITY:?set SIGN_IDENTITY to a Z56GZVA2QB signing identity}"
HERE=${0:A:h}; OUT=${OUT:-$(mktemp -d)}; GROUP=${GROUP:-Z56GZVA2QB.app.bristlenose.probe}
plist() { # $1 bundle id → Info.plist; a sandboxed bare Mach-O traps (exit 133) without one
  print -r -- "<?xml version=\"1.0\" encoding=\"UTF-8\"?><plist version=\"1.0\"><dict><key>CFBundleIdentifier</key><string>$1</string></dict></plist>"; }
ents() { # $1 = "sandbox" or "" → entitlements with the group
  local sb=""; [[ $1 == sandbox ]] && sb='<key>com.apple.security.app-sandbox</key><true/>'
  print -r -- "<?xml version=\"1.0\" encoding=\"UTF-8\"?><plist version=\"1.0\"><dict>$sb<key>com.apple.security.application-groups</key><array><string>$GROUP</string></array></dict></plist>"; }
for v in sandbox control; do
  id=app.bristlenose.group-probe; [[ $v == control ]] && id=$id-control
  mode=sandbox; [[ $v == control ]] && mode=""
  plist $id > $OUT/info-$v.plist; ents "$mode" > $OUT/ent-$v.plist
  clang -O2 -o $OUT/probe-$v $HERE/probe.c -sectcreate __TEXT __info_plist $OUT/info-$v.plist
  codesign -f -s "$SIGN_IDENTITY" -o runtime -i $id --entitlements $OUT/ent-$v.plist $OUT/probe-$v
  mkdir -p $OUT/mcpb-$v/server
  xcrun swiftc -O $HERE/group-probe-mcp.swift -o $OUT/mcpb-$v/server/group-probe \
    -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker $OUT/info-$v.plist
  codesign -f -s "$SIGN_IDENTITY" -o runtime -i $id --entitlements $OUT/ent-$v.plist $OUT/mcpb-$v/server/group-probe
  cat > $OUT/mcpb-$v/manifest.json <<JSON
{"manifest_version":"0.3","name":"bristlenose-group-probe-$v","display_name":"Bristlenose group probe ($v)",
 "version":"0.0.1","description":"Diagnostic probe for the app-group route (not Bristlenose).","author":{"name":"Bristlenose"},
 "server":{"type":"binary","entry_point":"server/group-probe","mcp_config":{"command":"\${__dirname}/server/group-probe","args":[]}},
 "compatibility":{"claude_desktop":">=1.13576.0","platforms":["darwin"]}}
JSON
  (cd $OUT/mcpb-$v && zip -qr ../bristlenose-group-probe-$v.mcpb manifest.json server)
done
print "built in $OUT"
