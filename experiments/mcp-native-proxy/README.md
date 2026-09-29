# Native MCP proxy — spike (29 Sep 2026)

Throwaway research code. The write-up, measurements and open questions are in
[`docs/design-mcp-native-proxy.md`](../../docs/design-mcp-native-proxy.md).
Read that first; this file only says what is here and how to run it.

## What is here

| File | What it is |
|---|---|
| `main.swift` | A 128 KB native port of the essentials of `desktop/mcpb/server/index.js`. On first start it re-launches itself with responsibility disclaimed, then serves stdio MCP: handshake → `/api/health` probe → `/mcp/`. No Node. |
| `probes/reader.c` | Opens a path and prints `READ ok` or `DENIED errno=…`. Built twice: ad-hoc and team-signed. |
| `probes/disclaim.c` | `posix_spawn` with `responsibility_spawnattrs_setdisclaim(1)`: runs its argument as its own responsible process. |
| `build.sh` | Builds all of the above into `build/` (ignored) and generates `tools.json` from the Node proxy's `BN-TOOLS-JSON` block, marking each tool `readOnlyHint`. |

```bash
SIGN_IDENTITY="Developer ID Application: <name> (<TEAM>)" experiments/mcp-native-proxy/build.sh
```

The team must be the one that signs Bristlenose. The whole effect depends on
the read being same-team.

## Reproducing the key result

Run the probes from a **fresh** Terminal. Terminal has no Files & Folders grant
for Bristlenose, and macOS caches a denial per responsible process, so the
first read in a session is the only clean one. Quit Terminal between cases.

```bash
H="$HOME/Library/Containers/app.bristlenose/Data/Library/Application Support/Bristlenose/mcp-handshake.json"
build/reader "$H" team-signed                     # DENIED — Terminal is responsible
build/disclaim build/reader-adhoc "$H" adhoc      # DENIED — its own identity, cross-team
build/disclaim build/reader "$H" team-disclaimed  # READ ok — same team, never reaches TCC
```

A running Bristlenose with Agent Access on for a project is what writes the
handshake. Read the decision with
`/usr/bin/log show --last 2m --predicate 'process == "tccd"' --style compact`
(never bare `log`, which is a zsh builtin).

## Not production code

The spike leaves out the Node proxy's scope fingerprint, `tools/list_changed`,
the contract/outdated check and the 404 branch. `responsibility_spawnattrs_setdisclaim`
is private SPI; see the doc's App Store section before shipping any of it.
