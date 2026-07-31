# `.mcpb` spike — 31 Jul 2026

**Spike artefact, not shipping code.** Validated the mechanism in
[`docs/design-mcp-extension.md`](../../docs/design-mcp-extension.md) before
committing to it. Kept because 90 working lines are worth more than a
description of them. **The shipping extension grew from this and lives in
[`desktop/mcpb/`](../mcpb/)** — develop there, not here.

What it proved, end to end against a real `bristlenose serve`:

- client → stdio proxy → HTTP → real MCP tools → **real data** (smoke fixture:
  1 session, 4 quotes)
- **zero dependencies** — no `node_modules`, ~90 lines, packs to 4 KB
- the **three states** (no handshake / port not answering / ready), each with
  its own message, and **self-heal** without restarting anything
- the bearer is genuinely enforced through this path (wrong token → 401)
- `initialize` answers immediately; nothing slow happens before it

What it did NOT test: installing into Claude Desktop (needs a click, and the
relaunch would end the session that built this).

**Update, same day:** Bristlenose now emits `mcp.instance_id` on
`/api/health`, so the proxy's staleness check is live rather than inert — a
handshake naming a recycled ephemeral port is now detected *before* the bearer
is transmitted.

To re-run: write a handshake to
`~/Library/Containers/app.bristlenose/Data/Library/Application Support/Bristlenose/mcp-handshake.json`
with `{schema, port, token, instance_id, updated_at}`, then pipe JSON-RPC
lines into `node server/index.js`.
