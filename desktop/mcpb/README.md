# Bristlenose `.mcpb` extension

The shipping home of the Claude Desktop extension: a zero-dependency Node
proxy that connects an MCP client to whatever Bristlenose is currently
serving, via the handshake file the macOS host writes
(`…/Application Support/Bristlenose/mcp-handshake.json`). No token paste, no
port paste, no JSON editing.

- Design: `docs/design-mcp-extension.md` (§3.1 handshake, §3.2 proxy,
  §4 packaging, §5b three states, §5c spike results).
- Validated spike this grew from: `desktop/mcpb-spike/` (kept as the
  recorded artefact; don't develop there).

## Build

```sh
desktop/scripts/build-mcpb.sh        # → desktop/build/Bristlenose.mcpb
```

Plain `zip` of an explicit allowlist (`manifest.json`, `server/index.js`) —
the 8-month-stale `@anthropic-ai/mcpb` CLI is not a dependency. The release
pack strips every line marked `// mcpb-dev-only` (the
`BRISTLENOSE_DEV_MCP_HANDSHAKE` override is attacker-settable via
`launchctl setenv`, so it must never ship — design §3.1) and
`desktop/scripts/check-mcpb.sh` gates the artefact: manifest parses, no
Mach-O members, no `.env*`, no dev-override string.

## Dev loop

Claude Desktop ▸ Settings ▸ Extensions ▸ Advanced ▸ **Install Unpacked
Extension** pointed at this directory. The unpacked copy keeps the dev
handshake override for testing against a fixture serve. Local installs
never auto-update — uninstall/reinstall to pick up edits, and watch
`~/Library/Logs/Claude/mcp-server-Bristlenose.log` for the proxy's stderr.

## Not here yet (handoff 2 — surface work)

- `icon.png` (512×512) — needs real artwork, not placeholder art.
- Copying the packed `.mcpb` into `Contents/Resources/` + the container,
  and the Install button that `NSWorkspace.open`s it (design §3.4).
