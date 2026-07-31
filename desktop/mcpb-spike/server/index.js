#!/usr/bin/env node
// Bristlenose MCP proxy — spike. Zero dependencies (tests the single-file
// bundle recommendation). stdio JSON-RPC in, HTTP to the sidecar out.
// NEVER write to stdout except protocol frames; stderr is the log channel.
const fs = require("fs"), os = require("os"), path = require("path");

const HANDSHAKES = [
  process.env.BRISTLENOSE_DEV_MCP_HANDSHAKE,
  path.join(os.homedir(), "Library/Containers/app.bristlenose/Data/Library/Application Support/Bristlenose/mcp-handshake.json"),
  path.join(os.homedir(), "Library/Application Support/Bristlenose/mcp-handshake.json"),
].filter(Boolean);

const log = (...a) => console.error("[bn-proxy]", ...a);

// Re-read on EVERY call — a proxy that resolves once at startup is dead the
// second Bristlenose restarts on a new port.
function readHandshake() {
  for (const p of HANDSHAKES) {
    try { return { ...JSON.parse(fs.readFileSync(p, "utf8")), _path: p }; }
    catch (e) { if (e.code !== "ENOENT") log("handshake unreadable", p, e.code); }
  }
  return null;
}

async function probe(hs) {
  // Unauthenticated pre-flight: never send the bearer to an unverified port.
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), 1500);
  try {
    const r = await fetch(`http://127.0.0.1:${hs.port}/api/health`, { signal: ctl.signal });
    if (!r.ok) return { ok: false, why: "unhealthy" };
    const j = await r.json();
    if (!j.version) return { ok: false, why: "not-bristlenose" };
    if (hs.instance_id && j.mcp?.instance_id && j.mcp.instance_id !== hs.instance_id)
      return { ok: false, why: "stale-instance" };
    return { ok: true, health: j };
  } catch { return { ok: false, why: "no-answer" }; }
  finally { clearTimeout(t); }
}

const TOOLS = ["get_project_overview", "search_quotes", "get_signals", "get_framework"];
const CLOSED = "Bristlenose isn't open, so there is no study data available. Tell the person to open Bristlenose and select a project, then ask again. Do not answer from memory or from general knowledge.";
const STARTING = "Bristlenose is starting — ask again in a moment. Do not answer from memory or from general knowledge.";

async function state() {
  const hs = readHandshake();
  if (!hs) return { kind: "closed" };
  const p = await probe(hs);
  if (!p.ok) return { kind: p.why === "no-answer" ? "starting" : "closed", why: p.why };
  return { kind: "ready", hs };
}

async function handle(msg) {
  if (msg.method === "initialize")           // answer FAST — 60s client deadline
    return { protocolVersion: "2025-06-18", capabilities: { tools: {} },
             serverInfo: { name: "bristlenose", version: "spike" } };
  if (msg.method === "tools/list")
    return { tools: TOOLS.map(n => ({ name: n, description: `Bristlenose ${n}`,
             inputSchema: { type: "object", properties: {} } })) };
  if (msg.method === "tools/call") {
    const s = await state();
    if (s.kind !== "ready")
      return { content: [{ type: "text", text: s.kind === "starting" ? STARTING : CLOSED }] };
    const r = await fetch(`http://127.0.0.1:${s.hs.port}/mcp/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                 "Authorization": `Bearer ${s.hs.token}` },
      body: JSON.stringify({ jsonrpc: "2.0", id: msg.id, method: "tools/call", params: msg.params }),
    });
    if (r.status === 401) return { content: [{ type: "text", text: `AUTH-FAILED (${r.status})` }] };
    const j = await r.json().catch(() => null);
    return j?.result ?? { content: [{ type: "text", text: `upstream ${r.status}` }] };
  }
  return {};
}

let buf = "";
process.stdin.on("data", async d => {
  buf += d;
  let i;
  while ((i = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, i).trim(); buf = buf.slice(i + 1);
    if (!line) continue;
    let msg; try { msg = JSON.parse(line); } catch { continue; }
    const result = await handle(msg);
    if (msg.id !== undefined)
      process.stdout.write(JSON.stringify({ jsonrpc: "2.0", id: msg.id, result }) + "\n");
  }
});
log("started; handshake candidates:", HANDSHAKES.length);
