# App-group route probes — 29 Sep 2026

These probes are the evidence for `docs/design-mcp-native-proxy.md` §6.2. They check
whether a sandboxed binary, signed by our team and carrying a Team-ID-prefixed app group,
can use that group's container when another team's app (Claude, ChatGPT, Terminal) is
the responsible process on macOS 27.

- `probe.c` is a file probe. Its arguments are `D:<dir>` (list), `W:<file>` (write),
  `U:<file>` (unlink), or a bare `<file>` (read). It prints its pid, its ppid and its
  responsible pid. It calls `responsibility_get_pid_responsible_for_pid`, which is
  **private SPI, for diagnosis only**. Never copy it into a shipping target.
- `group-probe-mcp.swift` is a stdio MCP server with one tool, `group_probe`. It reports
  the responsible process and runs mkdir, write, read and unlink in the group container.
- `build.sh` builds a sandboxed variant and an unsandboxed control of each, and packages
  the MCP one as `.mcpb`.

To reproduce:

```
SIGN_IDENTITY="Developer ID Application: … (Z56GZVA2QB)" OUT=/tmp/gp ./build.sh
/tmp/gp/probe-sandbox "D:$HOME/Library/Group Containers/Z56GZVA2QB.app.bristlenose.probe"
```

Run each case in a fresh responsible process, for example
`open -n -a Terminal case.command`, because sandboxd caches denials per process. Read
tccd with `/usr/bin/log show --predicate 'process == "tccd"'`. A result from a
SIP-disabled VM (the Cirrus tart `-base` and `-xcode` images) proves nothing.
