#!/usr/bin/env node
// Bristlenose MCP proxy — the .mcpb extension's server half.
// stdio JSON-RPC in (Claude Desktop), HTTP to the local Bristlenose serve out.
//
// Zero dependencies, deliberately: extensions run under hardened-runtime
// library validation, so any native module dies in dlopen before our JS runs
// (mcpb #229), and a dependency-free tree sidesteps the npm supply-chain
// obligations entirely (design §5c). NEVER write to stdout except protocol
// frames; stderr is the log channel.
//
// The one behavioural requirement that matters most (design §3.2): the
// handshake is re-read and the server re-probed ON EVERY TOOL CALL — a proxy
// that resolves once at startup is dead the second Bristlenose restarts on a
// new port, which is the ordinary case, not an edge. No sticky fallback.
//
// Hardened from the validated spike (desktop/mcpb-spike/, 31 Jul 2026).
const fs = require("fs"), os = require("os"), path = require("path");

const HANDSHAKES = [
  process.env.BRISTLENOSE_DEV_MCP_HANDSHAKE, // mcpb-dev-only
  path.join(os.homedir(), "Library/Containers/app.bristlenose/Data/Library/Application Support/Bristlenose/mcp-handshake.json"),
  path.join(os.homedir(), "Library/Application Support/Bristlenose/mcp-handshake.json"),
].filter(Boolean);

const VERSION = "0.1.0";
const log = (...a) => console.error("[bn-proxy]", ...a);

// Every failure sentence ends with this. A model handed "no data" will
// otherwise apologise and then answer from general knowledge anyway, and a
// confidently fabricated finding lands in research deliverables — the worst
// failure this feature has. Same family as INVARIANTS in grounding.py.
const GROUNDING = "Do not answer from memory or from general knowledge.";

// These are TOOL RESULTS, not dialogs: Claude reads them and the model
// relays them, paraphrased, into the conversation. Facts must survive
// rewording; destinations can be named but not linked. Vocabulary: the app
// "isn't open" (never "isn't serving"), and Settings names the APP, because
// this text is read inside Claude Desktop where "Settings" means Claude's.
const MSG = {
  closed: "Bristlenose isn't open, so there is no study data available. " +
    "Tell the person to open Bristlenose and select a project, then ask again. " + GROUNDING,
  starting: "Bristlenose is starting — ask again in a moment. " + GROUNDING,
  // 404 ≠ 401, and each names its own remedy (design §5c). 404: the build
  // has no agent support and no setting will enable it — say so rather
  // than pointing at a pane that cannot fix it.
  noAgentSupport: "This copy of Bristlenose was built without agent support. " +
    "No setting will enable it. " + GROUNDING,
  // 401: a stale/rotated credential. Unsharing deletes the handshake and
  // yields the "isn't open" sentence instead, so do NOT send the person
  // reinstalling — Settings is the place to check.
  authFailed: "Bristlenose refused this connection's stored credential. " +
    "Tell the person to open Bristlenose ▸ Settings ▸ MCP Agents (⌘,) and check " +
    "this project's agent access is turned on, then ask again. " + GROUNDING,
  upstream: (status) => "Bristlenose answered with an unexpected error (HTTP " + status +
    "), so there is no study data for this question. " + GROUNDING,
  // TCC denied/unanswered: name the macOS prompt in ITS words, and the
  // recovery. Deliberately not "reinstall" — the extension is fine.
  permission: "macOS is asking whether Claude may access data from other apps — " +
    "that permission is how this extension finds Bristlenose. Tell the person to " +
    "click Allow on the macOS dialog (or grant it in System Settings ▸ Privacy & " +
    "Security), then ask again. " + GROUNDING,
};

// Static tool list — served even when Bristlenose is closed (the fallback is
// what makes the ordinary failure a sentence instead of a missing tool).
// Mirrors the four §9a tools' signatures in bristlenose/server/mcp_server.py;
// tests/test_mcpb_proxy.py extracts the JSON between the markers below and
// compares it against the live server's tools/list, so drift fails CI
// rather than shipping (review Finding 25's mechanical gate).
/* BN-TOOLS-JSON-BEGIN */
const TOOLS = [
  {
    "name": "get_project_overview",
    "description": "Cheap orientation: sessions, participants, sections, themes, codebook summary, counts, top signals, and last-run status. Call this first; it also lists valid framework ids.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "project_id": { "type": "integer", "default": 1 }
      }
    }
  },
  {
    "name": "search_quotes",
    "description": "Search the curated quotes (hidden quotes excluded, researcher edits applied). Filters combine with AND; limit is capped at 50 - page with offset/next_offset.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "project_id": { "type": "integer", "default": 1 },
        "query": { "type": "string" },
        "tag": { "type": "string" },
        "sentiment": { "type": "string" },
        "participant": { "type": "string" },
        "section": { "type": "string" },
        "theme": { "type": "string" },
        "starred_only": { "type": "boolean", "default": false },
        "limit": { "type": "integer", "default": 20 },
        "offset": { "type": "integer", "default": 0 }
      }
    }
  },
  {
    "name": "get_signals",
    "description": "Concentration/agreement/intensity signals over the curated corpus. lens=\"sentiment\" or \"tags\" (accepted tags only). Never calls an LLM.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "project_id": { "type": "integer", "default": 1 },
        "lens": { "type": "string", "default": "sentiment" },
        "limit": { "type": "integer", "default": 10 }
      }
    }
  },
  {
    "name": "get_framework",
    "description": "One framework in full - the stance, not just the tag list. framework_id is a published template id, or \"codebook\" for this project's live codebook.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "framework_id": { "type": "string" },
        "project_id": { "type": "integer", "default": 1 }
      },
      "required": ["framework_id"]
    }
  }
];
/* BN-TOOLS-JSON-END */

// TCC: the handshake lives in Bristlenose's app container, and when the
// reader is Claude Desktop's Node process macOS attributes the read to
// "Claude" and fires the SystemPolicyAppData prompt ("would like to access
// data from other apps"). Measured 1 Aug 2026 — the spike's shell-read
// evidence did NOT transfer to Claude-spawned processes (design §5c's
// recorded caveat, resolved the bad way). One prompt is fine and sticky;
// an unthrottled reader is a DIALOG STORM: every unanswered attempt spawns
// another dialog. So: a permission failure (EPERM/EACCES) parks the
// background watcher entirely, and only explicit tool calls — researcher-
// initiated, one prompt at most — retry. A successful read un-parks it.
let tccBlocked = false;

// Re-read on EVERY call — see the header. A stat+read of a sub-1KB file per
// call is free; nothing is cached across calls.
function readHandshake() {
  let denied = false;
  for (const p of HANDSHAKES) {
    try {
      const hs = { ...JSON.parse(fs.readFileSync(p, "utf8")), _path: p };
      tccBlocked = false;
      return hs;
    } catch (e) {
      if (e.code === "EPERM" || e.code === "EACCES") {
        denied = true;
        if (!tccBlocked) log("handshake read permission-blocked (TCC)", p, e.code);
      } else if (e.code !== "ENOENT") {
        log("handshake unreadable", p, e.code);
      }
    }
  }
  if (denied) {
    tccBlocked = true;
    return { _tccBlocked: true };
  }
  return null;
}

// Unauthenticated pre-flight: never send the bearer to an unverified port.
// /api/health is auth-exempt and records no activity (a probe that called a
// real tool would light the sidebar antenna with no researcher present).
async function probe(hs) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), 1500);
  try {
    const r = await fetch(`http://127.0.0.1:${hs.port}/api/health`, { signal: ctl.signal });
    if (!r.ok) return { ok: false, why: "unhealthy" };
    const j = await r.json();
    if (!j.version) return { ok: false, why: "not-bristlenose" };
    // FAIL CLOSED on a missing mcp.instance_id: any host that writes a
    // handshake ships a serve that emits one, so an answer without it is a
    // squatter mimicking the health shape, not an old Bristlenose. A
    // `j.mcp?.instance_id &&` conjunct here would skip the comparison and
    // transmit the bearer — the exact hole the check exists to close.
    if (hs.instance_id && j.mcp?.instance_id !== hs.instance_id)
      return { ok: false, why: "stale-instance" };
    // Health says the build has no /mcp mount: report it before the bearer
    // is ever transmitted. Absent mcp block = older build; let the call's
    // own 404 speak instead.
    if (j.mcp && j.mcp.mounted === false) return { ok: false, why: "no-mcp" };
    return { ok: true, health: j };
  } catch { return { ok: false, why: "no-answer" }; }
  finally { clearTimeout(t); }
}

// Three states, not two (design §5b): "no handshake" and "handshake present
// but port silent" have different remedies, and the researcher's own click
// is what creates the second — collapsing them tells someone who just
// opened Bristlenose to open Bristlenose.
async function state() {
  const hs = readHandshake();
  if (hs && hs._tccBlocked) return { kind: "no-permission" };
  if (!hs) return { kind: "closed" };
  const p = await probe(hs);
  if (!p.ok) {
    if (p.why === "no-answer") return { kind: "starting" };
    if (p.why === "no-mcp") return { kind: "no-mcp" };
    return { kind: "closed", why: p.why };
  }
  return { kind: "ready", hs };
}

const text = (t) => ({ content: [{ type: "text", text: t }] });

async function callUpstream(hs, msg) {
  let r;
  try {
    r = await fetch(`http://127.0.0.1:${hs.port}/mcp/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": `Bearer ${hs.token}`,
      },
      body: JSON.stringify({ jsonrpc: "2.0", id: msg.id, method: "tools/call", params: msg.params }),
    });
  } catch {
    // Died between probe and call — the next call re-reads and recovers.
    return text(MSG.starting);
  }
  if (r.status === 401) return text(MSG.authFailed);
  if (r.status === 404) return text(MSG.noAgentSupport);
  const j = await r.json().catch(() => null);
  if (j?.result) return j.result;
  if (j?.error?.message) return text(j.error.message + " " + GROUNDING);
  return text(MSG.upstream(r.status));
}

// --- Self-heal notification -------------------------------------------------
// notifications/tools/list_changed fires on the offline→ready edge so a
// client that cached a dead state refreshes. CRUCIALLY there is NO
// background watcher any more: the handshake lives in a TCC-protected
// container, macOS prompts PER ACCESS when the grant fails to persist
// (measured 1 Aug 2026 — Claude's built-in Node has no stable identity
// for TCC to key a durable grant to, so Allow lands for one read and the
// next one re-prompts), and any timer therefore becomes a dialog storm
// no matter how it backs off on errors. Reads happen ONLY inside tool
// calls — researcher-initiated, one prompt per question at worst — and
// the edge detection rides those same reads for free.
let clientInitialized = false;
let lastReady = null;
function noteReady(ready) {
  if (clientInitialized && lastReady === false && ready) {
    process.stdout.write(JSON.stringify(
      { jsonrpc: "2.0", method: "notifications/tools/list_changed" }
    ) + "\n");
    log("server appeared — sent tools/list_changed");
  }
  lastReady = ready;
}

async function handle(msg) {
  // Answer initialize IMMEDIATELY — 60s client deadline, servers start in
  // parallel at app launch, and a blocking connect during startup has been
  // reported to break the entire host client, not just one connector
  // (design §3.2b). Everything slow lives inside tool calls.
  if (msg.method === "initialize") {
    return {
      protocolVersion: "2025-06-18",
      capabilities: { tools: { listChanged: true } },
      serverInfo: { name: "bristlenose", version: VERSION },
    };
  }
  // Server→client notifications are only legal after the client confirms —
  // gate list_changed on this, not on our initialize answer.
  if (msg.method === "notifications/initialized") {
    clientInitialized = true;
    return {};
  }
  if (msg.method === "tools/list") return { tools: TOOLS };
  if (msg.method === "tools/call") {
    const s = await state();
    noteReady(s.kind === "ready");
    if (s.kind === "no-permission") return text(MSG.permission);
    if (s.kind === "starting") return text(MSG.starting);
    if (s.kind === "no-mcp") return text(MSG.noAgentSupport);
    if (s.kind !== "ready") return text(MSG.closed);
    return callUpstream(s.hs, msg);
  }
  return {};
}

let buf = "";
// Without an encoding, each chunk is a Buffer decoded independently — a
// multi-byte UTF-8 character split across a 64KB pipe boundary would decode
// to U+FFFD and silently corrupt the frame. setEncoding runs a StringDecoder
// that holds partial sequences across chunks.
process.stdin.setEncoding("utf8");
process.stdin.on("data", async (d) => {
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
process.stdin.on("end", () => process.exit(0));
log("started; handshake candidates:", HANDSHAKES.length);
