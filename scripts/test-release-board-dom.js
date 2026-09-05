#!/usr/bin/env node
// test-release-board-dom.js — the page's live half, executed, not grepped.
//
//     node scripts/test-release-board-dom.js
//
// Renders board.html and board-replay.html for a synthetic run in jsdom and
// drives the parts no Python test can reach: every pane exists, a live patch
// swaps only the pane whose slice moved, the tick counts ages and elapsed from
// stamps, freshness expires with the heartbeat, a fault reaches the band, and a
// replay frame keeps its own clock. fetch/EventSource are stubbed — jsdom has
// neither — so what is proven is the page's reaction to a model, not the wire
// (test-release-board.py's Server suite proves the wire).
//
// Needs frontend/node_modules/jsdom (a devDependency). Exits 3, and says so,
// when it is absent: skipped is not passed (docs/design-test-philosophy.md).
"use strict";
const fs = require("fs"), path = require("path"), os = require("os"), { execFileSync } = require("child_process");
const ROOT = path.resolve(__dirname, "..");
let JSDOM, VirtualConsole;
try { ({ JSDOM, VirtualConsole } = require(path.join(ROOT, "frontend", "node_modules", "jsdom"))); }
catch (e) { console.error("SKIPPED, NOT PASSED: frontend/node_modules/jsdom is absent — run `npm ci` in frontend/"); process.exit(3); }

const PY = fs.existsSync(path.join(ROOT, ".venv", "bin", "python")) ? path.join(ROOT, ".venv", "bin", "python") : "python3";
const GEN = path.join(ROOT, "scripts", "release-board.py");
let fails = 0, passes = 0;
const ok = (m) => { passes++; console.log("  ✓ " + m); };
const bad = (m) => { fails++; console.log("  ✗ " + m); };
const eq = (m, want, got) => (JSON.stringify(want) === JSON.stringify(got) ? ok(m) : bad(`${m} — expected ${JSON.stringify(want)}, got ${JSON.stringify(got)}`));

// ── a synthetic run: one running step, a heartbeat, a sink with one lane ──
const work = fs.mkdtempSync(path.join(os.tmpdir(), "rb-dom-"));
fs.mkdirSync(path.join(work, "scripts"), { recursive: true }); fs.mkdirSync(path.join(work, "docs", "testing"), { recursive: true });
fs.writeFileSync(path.join(work, "scripts", "project.conf"), 'PROJECT_NAME="bristlenose"\nCHANNELS="pypi github"\nCHANNELS_UNPROBEABLE=""\nGH_REPO="o/r"\n');
fs.writeFileSync(path.join(work, "docs", "testing", "ratchet.json"), "{}");
const run = path.join(work, ".release", "1.0.0"); fs.mkdirSync(run, { recursive: true });
const ev = (ts, step, status, detail) => JSON.stringify({ ts, run: "1.0.0", step, status, detail: detail || "" });
fs.writeFileSync(path.join(run, "steps.tbl"), "# steps.tbl v1\npreflight|preflight|gate|1m|||./scripts/check-release-ready.sh\nbump|bump|plain|1m|||x\nbuild-all|build|plain|11m|||desktop/scripts/build-all.sh\ntag|tag|hard|2m||HARD|x\n");
const T0 = Date.now() - 90 * 1000;   // the run started 90 s ago
const iso = (ms) => new Date(ms).toISOString().replace(/\.\d{3}Z$/, "Z");
fs.writeFileSync(path.join(run, "events.jsonl"), [ev(iso(T0), "run", "started"), ev(iso(T0 + 1000), "preflight", "ok", "1s"), ev(iso(T0 + 2000), "bump", "ok", "1s"), ev(iso(T0 + 3000), "build-all", "running", "attempt 1")].join("\n") + "\n");
fs.mkdirSync(path.join(run, ".lock")); fs.writeFileSync(path.join(run, ".lock", "pid"), String(process.pid));
fs.writeFileSync(path.join(run, "heartbeat"), `${Math.floor((Date.now() - 20000) / 1000)}\tbuild-all\t60\tsigning\n`);

const model = (extraArgs) => JSON.parse(execFileSync(PY, [GEN, "1.0.0", "--json", "--root", work, ...(extraArgs || [])], { encoding: "utf8" }));
const htmlFor = (m) => {
  // the generator's own inlining, via a tiny wrapper: keeps the escaping rule in one place
  const out = path.join(work, "out"); fs.mkdirSync(out, { recursive: true });
  execFileSync(PY, [GEN, "1.0.0", "--root", work, "--out", out], { stdio: "ignore" });
  const html = fs.readFileSync(path.join(out, "board.html"), "utf8");
  return m ? html.replace(/<script type="application\/json" id="board-data">[\s\S]*?<\/script>/, () => `<script type="application/json" id="board-data">${JSON.stringify(m).replace(/</g, "\\u003c").replace(/>/g, "\\u003e").replace(/&/g, "\\u0026")}</script>`) : html;
};
const load = (html, url) => {
  const errors = [];
  const vc = new VirtualConsole().on("jsdomError", (e) => errors.push(String(e.message || e)));
  const dom = new JSDOM(html, { runScripts: "dangerously", url: url || "http://127.0.0.1:8151/?k=t", virtualConsole: vc, pretendToBeVisual: true });
  return { dom, d: dom.window.document, w: dom.window, errors };
};

console.log("1 · a live page renders every pane, and the tick counts from stamps");
{
  const m = model(); m.live = { generation: 1, poll_ms: 1000, served_at: iso(Date.now()), changed_at: iso(Date.now()), error: null, token: "t", with_logs: false };
  const { d, w, errors } = load(htmlFor(m));
  eq("no renderer error", 0, errors.filter(e => /Uncaught/.test(e)).length);
  eq("no fault band", null, d.getElementById("fault"));
  for (const id of ["top", "line", "main", "pane-activity", "pane-preflight", "pane-build-build-all", "pane-ci", "pane-tag", "pane-channels", "pane-clocks", "pane-confounded", "pane-log", "pane-events", "gutter-tag", "gutter-stream", "live-pill"]) if (!d.getElementById(id)) bad("missing #" + id);
  ok("every pane, gutter and the live pill exist");
  const running = d.querySelector(".station.running");
  eq("the running station pulses while the heartbeat is fresh (20 s old, cadence 300)", true, running.classList.contains("fresh"));
  const since = running.querySelector("[data-since]");
  eq("elapsed counts from the ledger stamp (~87 s)", true, /running · (1m|8\ds)/.test(since.textContent));
  // the tick, fast-forwarded: a heartbeat 20 minutes old is stale
  m.liveness.heartbeat.epoch = Math.floor(Date.now() / 1000) - 1200;
  const { d: d2 } = load(htmlFor(m));
  eq("a heartbeat older than 3× cadence turns the running station stale", true, d2.querySelector(".station.running").classList.contains("stale"));
}

async function section2() {
  console.log("2 · a live patch swaps only the pane whose slice moved");
  const m = model(); m.live = { generation: 1, poll_ms: 1000, served_at: iso(Date.now()), changed_at: iso(Date.now()), error: null, token: "t", with_logs: false };
  const { d, w } = load(htmlFor(m));
  const before = { pre: d.getElementById("pane-preflight"), ci: d.getElementById("pane-ci"), line: d.getElementById("line") };
  // next model: build-all finished, nothing else moved
  fs.appendFileSync(path.join(run, "events.jsonl"), ev(iso(T0 + 60000), "build-all", "ok", "57s") + "\n");
  const next = model(); next.live = { ...m.live, generation: 2, served_at: iso(Date.now()) };
  let fetched = 0;
  // jsdom has no EventSource, so the page installed only the safety poll (every 2 s); stub fetch and wait for it
  w.fetch = () => { fetched++; return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(next), text: () => Promise.resolve("") }); };
  await sleep(2400);
  eq("the safety poll fetched board.json", true, fetched >= 1);
  eq("the line pane was swapped (its slice moved)", false, d.getElementById("line") === before.line);
  eq("…and carries the glisten class", true, d.getElementById("line").classList.contains("changed"));
  eq("the preflight pane is the same node (its slice did not move)", true, d.getElementById("pane-preflight") === before.pre);
  eq("the CI pane is the same node", true, d.getElementById("pane-ci") === before.ci);
  const ba = [...d.querySelectorAll(".station")].find(s => s.querySelector("b").textContent === "build-all");
  eq("the swapped line shows build-all ok", true, /^ok/.test(ba.querySelector("small").textContent));
  // an older generation landing after a newer one is ignored
  const stale = { ...next, live: { ...next.live, generation: 1 }, phase: "stranded" };
  w.fetch = () => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(stale), text: () => Promise.resolve("") });
  await sleep(2400);
  eq("an older generation does not regress the page", false, /stranded/.test(d.getElementById("top").textContent));
  // a failing pull is a state, not silence
  w.fetch = () => Promise.resolve({ ok: false, status: 503, json: () => Promise.reject(new Error("x")), text: () => Promise.resolve("no model yet — boom") });
  await sleep(2400);
  const pill = d.getElementById("live-pill");
  eq("a 503 pull marks the pill unreachable with the server's reason", true, /unreachable/.test(pill.textContent) && /boom/.test(pill.textContent));
  // a renderer fault during a patch reaches the band
  w.fetch = () => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ ...next, live: { ...next.live, generation: 3 }, line: null }), text: () => Promise.resolve("") });
  await sleep(2400);
  eq("a renderer fault on live data reaches the fault band", true, !!d.getElementById("fault"));
  w.close();
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function section3() {
  console.log("3 · a replay frame keeps its own clock and its assumed liveness");
  const out = path.join(work, "replay"); fs.mkdirSync(out, { recursive: true });
  execFileSync(PY, [GEN, "1.0.0", "--replay", "--root", work, "--out", out], { stdio: "ignore" });
  const { d, errors } = load(fs.readFileSync(path.join(out, "board-replay.html"), "utf8"), "file:///board-replay.html");
  eq("no renderer error on the replay", 0, errors.filter(e => /Uncaught/.test(e)).length);
  eq("the scrubber is present", true, !!d.getElementById("replay"));
  // step back to the frame where build-all is running (frame 4 of 5)
  const prev = d.getElementById("replay").querySelectorAll("button")[0];
  prev.click();
  const running = d.querySelector(".station.running");
  eq("a replayed running station is fresh (liveness assumed), not stale", true, running && running.classList.contains("fresh"));
  eq("its elapsed counts from the frame's clock, not today's", true, running && /running · \d+s/.test(running.querySelector("small").textContent) && !/\d+m/.test(running.querySelector("small").textContent));
}

(async () => {
  try { await section2(); section3(); }
  catch (e) { bad("suite threw: " + (e && e.stack || e)); }
  fs.rmSync(work, { recursive: true, force: true });
  console.log(`\n${passes} passed, ${fails} failed`);
  process.exit(fails ? 1 : 0);
})();
