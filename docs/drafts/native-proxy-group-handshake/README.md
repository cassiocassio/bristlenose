# Draft patch: the MCP handshake in the team-prefixed app group

**Not applied.** A ready-to-apply patch for the host half of the recommended
architecture in [`docs/design-mcp-native-proxy.md`](../../design-mcp-native-proxy.md)
§6.4. The proxy half is the spike in `experiments/mcp-native-proxy/`
(`GROUP_VARIANT`). Drafted 29 Sep 2026 for the maintainer's decision.

```bash
git am docs/drafts/native-proxy-group-handshake/0001-*.patch
```

## What it changes

| File | Change |
|---|---|
| `desktop/Bristlenose/Bristlenose/MCPHandshake.swift` | `write`/`remove` with no directory now also write/remove a copy in `<team group container>/Bristlenose/`. The group identifier is read from the process's own entitlements (`SecTaskCopyValueForEntitlement`), so no team ID is hard-coded and a build without the entitlement skips the copy. The return value is still the data-container result. |
| `Bristlenose.entitlements` (MAS) | adds `$(TeamIdentifierPrefix)app.bristlenose` beside `group.app.bristlenose` |
| `BristlenoseDeveloperID.entitlements` (`.dmg`) | adds the team group only (never the Background Assets group) |
| `tests/test_entitlements_split.py` | the split is now "differ by exactly the Background Assets group", and both carry the team group |
| `BristlenoseTests/MCPHandshakeTests.swift` | three tests for picking the team group out of an entitlement list |

It keeps writing the data-container copy, because today's Node `.mcpb` reads
only that, and Files & Folders can rescue only a data-container read.

## Verified

- `tests/test_entitlements_split.py`: 13 passed (on a commit carrying the patch;
  the committed-file tests read `HEAD`).
- Swift: `build-for-testing` succeeds in a clean worktree (isolated
  DerivedData), and `MCPHandshakeTests` passes 10 of 10, including the three
  new ones.
- The mechanism itself is measured in the design doc: a sandboxed, team-signed
  proxy carrying the group reads it under ChatGPT, Claude Desktop, Claude Code
  and Terminal. Apple's validator accepts the MAS app with the group and the
  nested proxy (§6.5).

## Not verified

- **A Release archive with this patch.** `$(TeamIdentifierPrefix)` expansion in
  the entitlements was not checked on a real archive. The validator run used a
  hand-edited entitlements plist with the literal `Z56GZVA2QB.app.bristlenose`.
- **The Developer-ID profile.** Today's "Mac Team Direct" profile lists only
  `keychain-access-groups`. With it embedded, a Developer-ID app claiming the
  team group ran and used the group on macOS 27, but taskgated logged
  *"Unsatisfied entitlements: com.apple.security.application-groups …
  Disallowing"*. Re-export so Xcode mints a profile that authorises the group
  before relying on that, and test on macOS 15 and 26 too.
- **Debug builds.** `BristlenoseDebug.entitlements` (`skip-worktree`) is
  untouched, so Debug skips the group copy. Adding it would change automatic
  signing's capabilities.
- **The sidecar's own cleanup** (`lifecycle.install_handshake_cleanup`) deletes
  only the data-container copy on a graceful exit. A group copy left behind
  fails closed: the proxy's `/api/health` probe rejects the stale
  `instance_id`. The host's own `remove()` clears both.
- **The Swift suite as a whole** was not run for this draft; only
  `MCPHandshakeTests`.

## Not in this patch: bundling the proxy

This patch is the host half only. When the sandboxed proxy is bundled, give it
**a different bundle identifier per channel**, for example
`app.bristlenose.mcp-proxy` for the App Store and
`app.bristlenose.mcp-proxy.devid` for the `.dmg`. A sandboxed helper's own
container remembers the signer that created it, and one launch by a different
signer hung it, and for a few minutes every later launch too, including the
trusted build's (design doc §6.6).
