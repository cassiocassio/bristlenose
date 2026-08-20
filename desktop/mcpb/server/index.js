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
  ambiguous: (entries) =>
    "Bristlenose has more than one project open, so this question needs one " +
    "named. Ask the person which they mean, then pass its `project` key: " +
    entries.map((e) => `${e.name || "(unnamed)"} = ${e.key}`).join(", ") + ". " +
    GROUNDING,
  // Not "reinstall the app" — the app is fine and newer. The extension is
  // the stale half, and Settings is where it is replaced.
  outdated: "This Bristlenose extension is older than the Bristlenose app and " +
    "can no longer read it correctly. Tell the person to open Bristlenose \u25b8 " +
    "Settings \u25b8 MCP Agents and install the extension again — it takes a " +
    "moment and keeps every setting. " + GROUNDING,
  unknownProject: (entries) =>
    "That project is not open in Bristlenose right now — its window may have " +
    "been closed. Currently readable: " +
    (entries.length
      ? entries.map((e) => `${e.name || "(unnamed)"} = ${e.key}`).join(", ")
      : "none") + ". " + GROUNDING,
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
      "name": "list_projects",
      "description": "The projects Bristlenose currently has open with Agent Access on \u2014 each with a stable key to pass as `project`. Call this first when a question might span studies, or whenever the scope fingerprint on a result changes.",
      "inputSchema": {
        "type": "object",
        "properties": {}
      }
    },
    {
      "name": "get_project_overview",
      "description": "Cheap orientation: sessions, participants, sections, themes, codebook summary, counts, top signals, and last-run status. Call this first; it also lists valid framework ids.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "project_id": {
            "type": "integer",
            "default": 1
          },
          "project": {
            "type": "string",
            "description": "Which project to read, by the key from list_projects. Required when more than one project is open; optional when only one is."
          }
        }
      }
    },
    {
      "name": "search_quotes",
      "description": "Search the curated quotes (hidden quotes excluded, researcher edits applied). Filters combine with AND; limit is capped at 50 - page with offset/next_offset.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "project_id": {
            "type": "integer",
            "default": 1
          },
          "query": {
            "type": "string"
          },
          "tag": {
            "type": "string"
          },
          "sentiment": {
            "type": "string"
          },
          "participant": {
            "type": "string"
          },
          "section": {
            "type": "string"
          },
          "theme": {
            "type": "string"
          },
          "starred_only": {
            "type": "boolean",
            "default": false
          },
          "limit": {
            "type": "integer",
            "default": 20
          },
          "offset": {
            "type": "integer",
            "default": 0
          },
          "project": {
            "type": "string",
            "description": "Which project to read, by the key from list_projects. Required when more than one project is open; optional when only one is."
          }
        }
      }
    },
    {
      "name": "get_signals",
      "description": "Concentration/agreement/intensity signals over the curated corpus. lens=\"sentiment\" or \"tags\" (accepted tags only). Never calls an LLM.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "project_id": {
            "type": "integer",
            "default": 1
          },
          "lens": {
            "type": "string",
            "default": "sentiment"
          },
          "limit": {
            "type": "integer",
            "default": 10
          },
          "project": {
            "type": "string",
            "description": "Which project to read, by the key from list_projects. Required when more than one project is open; optional when only one is."
          }
        }
      }
    },
    {
      "name": "get_framework",
      "description": "One framework in full - the stance, not just the tag list. framework_id is a published template id, or \"codebook\" for this project's live codebook.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "framework_id": {
            "type": "string"
          },
          "project_id": {
            "type": "integer",
            "default": 1
          },
          "project": {
            "type": "string",
            "description": "Which project to read, by the key from list_projects. Required when more than one project is open; optional when only one is."
          }
        },
        "required": [
          "framework_id"
        ]
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

// The agent-surface contract THIS proxy speaks. An installed extension never
// auto-updates and cannot rewrite itself, so the only honest thing it can do
// when the app moves ahead is notice and say so — in a tool result, which is
// the one channel we have into the other app. See MSG.outdated.
const CONTRACT = 2;

// Re-read on EVERY call — see the header. A stat+read of a sub-1KB file per
// call is free; nothing is cached across calls.
function readHandshake() {
  let denied = false;
  for (const p of HANDSHAKES) {
    try {
      const hs = { ...JSON.parse(fs.readFileSync(p, "utf8")), _path: p };
      tccBlocked = false;
      return normalise(hs);
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

// One shape for both schemas. Schema 2 carries `projects: [...]`; schema 1
// carried the single project's port/token/instance_id at the top level. A
// proxy is installed once and never auto-updates, so it has to read whichever
// the host happens to write — a newer proxy against an older app is exactly
// as likely as the reverse.
function normalise(hs) {
  if (Array.isArray(hs.projects)) return hs;
  if (hs.port) {
    return { ...hs, projects: [{
      key: hs.key || "", name: hs.name || "", port: hs.port,
      token: hs.token, instance_id: hs.instance_id,
    }] };
  }
  return { ...hs, projects: [] };
}

// A short, stable fingerprint of the in-scope set.
//
// The count phrases the warning ("three now, you had two"); the fingerprint
// catches the case a count cannot — a SWAP, where one window closes and
// another opens, n stays 2, and the agent answers about a different study
// believing nothing changed. Same bug class as a project_id that silently
// re-points, which is what this whole design exists to end.
function scopeOf(entries) {
  const keys = entries.map((e) => e.key).sort().join("|");
  let h = 5381;
  for (let i = 0; i < keys.length; i++) h = ((h * 33) ^ keys.charCodeAt(i)) >>> 0;
  return { n: entries.length, fp: h.toString(16).padStart(8, "0") };
}

// Unauthenticated pre-flight: never send the bearer to an unverified port.
// /api/health is auth-exempt and records no activity (a probe that called a
// real tool would light the sidebar antenna with no researcher present).
async function probe(entry) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), 1500);
  try {
    const r = await fetch(`http://127.0.0.1:${entry.port}/api/health`, { signal: ctl.signal });
    if (!r.ok) return { ok: false, why: "unhealthy" };
    const j = await r.json();
    if (!j.version) return { ok: false, why: "not-bristlenose" };
    // FAIL CLOSED on a missing mcp.instance_id: any host that writes a
    // handshake ships a serve that emits one, so an answer without it is a
    // squatter mimicking the health shape, not an old Bristlenose. A
    // `j.mcp?.instance_id &&` conjunct here would skip the comparison and
    // transmit the bearer — the exact hole the check exists to close.
    if (entry.instance_id && j.mcp?.instance_id !== entry.instance_id)
      return { ok: false, why: "stale-instance" };
    // Health says the build has no /mcp mount: report it before the bearer
    // is ever transmitted. Absent mcp block = older build; let the call's
    // own 404 speak instead.
    if (j.mcp && j.mcp.mounted === false) return { ok: false, why: "no-mcp" };
    // Absent = an older app that predates the field, which by definition
    // speaks contract 1 and is fine. Only a HIGHER number means this
    // extension is behind.
    if ((j.mcp?.contract ?? 1) > CONTRACT) return { ok: false, why: "outdated" };
    return { ok: true, health: j };
  } catch { return { ok: false, why: "no-answer" }; }
  finally { clearTimeout(t); }
}

// Three states, not two (design §5b): "no handshake" and "handshake present
// but port silent" have different remedies, and the researcher's own click
// is what creates the second — collapsing them tells someone who just
// opened Bristlenose to open Bristlenose.
async function state(wantedKey) {
  const hs = readHandshake();
  if (hs && hs._tccBlocked) return { kind: "no-permission" };
  if (!hs || hs.projects.length === 0) return { kind: "closed" };

  const scope = scopeOf(hs.projects);

  // Which project? The agent names one by key. With exactly one in scope
  // there is nothing to disambiguate, so it may say nothing — but with
  // several, guessing would be the re-pointing bug wearing a new hat, so we
  // refuse and teach instead.
  let entry;
  if (wantedKey) {
    entry = hs.projects.find((e) => e.key === wantedKey);
    if (!entry) return { kind: "unknown-project", hs, scope };
  } else if (hs.projects.length === 1) {
    entry = hs.projects[0];
  } else {
    return { kind: "ambiguous", hs, scope };
  }

  const p = await probe(entry);
  if (!p.ok) {
    if (p.why === "no-answer") return { kind: "starting" };
    if (p.why === "no-mcp") return { kind: "no-mcp" };
    if (p.why === "outdated") return { kind: "outdated" };
    return { kind: "closed", why: p.why };
  }
  return { kind: "ready", entry, hs, scope };
}

const text = (t) => ({ content: [{ type: "text", text: t }] });

const stripProject = (args) => {
  if (!args || typeof args !== "object") return args;
  const { project, ...rest } = args;
  return rest;
};

// Every result carries the scope it was answered against, so a widening is
// detectable rather than something the agent has to remember. What this
// guarantees is DETECTABILITY, not compliance — a client that ignores it is
// free to; the enforceable control is app-side, in the antenna and the window.
function withScope(result, scope) {
  if (!scope || !result || typeof result !== "object") return result;
  return { ...result, scope };
}

const projectList = (entries) =>
  entries.map((e) => ({ key: e.key, name: e.name })).filter((e) => e.key);

async function callUpstream(entry, msg, scope) {
  let r;
  try {
    r = await fetch(`http://127.0.0.1:${hs.port}/mcp/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": `Bearer ${entry.token}`,
        // So the app can say "your extension is out of date" in its own UI
        // rather than only the agent hearing about it.
        "X-Bristlenose-Proxy-Contract": String(CONTRACT),
        "X-Bristlenose-Proxy-Version": VERSION,
      },
      // `project` is OURS — it names which serve to reach. The server is
      // single-project and would reject it as an unknown argument.
      body: JSON.stringify({
        jsonrpc: "2.0", id: msg.id, method: "tools/call",
        params: { ...msg.params, arguments: stripProject(msg.params?.arguments) },
      }),
    });
  } catch {
    // Died between probe and call — the next call re-reads and recovers.
    return text(MSG.starting);
  }
  if (r.status === 401) return text(MSG.authFailed);
  if (r.status === 404) return text(MSG.noAgentSupport);
  const j = await r.json().catch(() => null);
  if (j?.result) return withScope(j.result, scope);
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
    // list_projects is answered HERE, from the handshake, with no upstream
    // call and no bearer transmitted. The proxy is the only party that knows
    // the whole set — each serve knows only itself — so this is its job, not
    // a tool the server could implement.
    if (msg.params?.name === "list_projects") {
      const hs = readHandshake();
      if (hs?._tccBlocked) return text(MSG.permission);
      const entries = hs ? projectList(hs.projects) : [];
      noteReady(entries.length > 0);
      if (!entries.length) return text(MSG.closed);
      return withScope(
        { content: [{ type: "text", text: JSON.stringify({ projects: entries }, null, 2) }] },
        scopeOf(hs.projects));
    }

    const s = await state(msg.params?.arguments?.project);
    noteReady(s.kind === "ready");
    if (s.kind === "no-permission") return text(MSG.permission);
    if (s.kind === "starting") return text(MSG.starting);
    if (s.kind === "no-mcp") return text(MSG.noAgentSupport);
    if (s.kind === "outdated") return text(MSG.outdated);
    if (s.kind === "ambiguous")
      return withScope(text(MSG.ambiguous(projectList(s.hs.projects))), s.scope);
    if (s.kind === "unknown-project")
      return withScope(text(MSG.unknownProject(projectList(s.hs.projects))), s.scope);
    if (s.kind !== "ready") return text(MSG.closed);
    return callUpstream(s.entry, msg, s.scope);
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
