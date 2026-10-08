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
fs.mkdirSync(path.join(run, "logs")); for (const f of ["preflight.1.log", "bump.1.log"]) fs.writeFileSync(path.join(run, "logs", f), "done\n");
fs.writeFileSync(path.join(run, "logs", "build-all.1.log"), Array.from({ length: 30 }, (_, i) => `building line ${i}`).join("\n") + "\n");

const model = (extraArgs) => JSON.parse(execFileSync(PY, [GEN, "1.0.0", "--json", "--with-logs", "--root", work, ...(extraArgs || [])], { encoding: "utf8" }));
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
  const sel = d.querySelector("#pane-log select"), pre = d.querySelector("#pane-log pre.logtail");
  eq("the log pane offers every step that has a log", 3, sel ? sel.options.length : 0);
  eq("…and focuses the running step", "build-all", sel ? sel.value : null);
  eq("…whose tail is in the pre", true, !!pre && /building|line/.test(pre.textContent));
  const running = d.querySelector(".station.running");
  eq("the running station pulses while the heartbeat is fresh (20 s old, cadence 300)", true, running.classList.contains("fresh"));
  const since = running.querySelector("[data-since]");
  // ~87 s plus however long the two generator runs above took: a cold CI runner
  // spent over 3 s there and read "9Xs" (0.35.0 push run), so the band is 87 s to 2 min.
  eq("elapsed counts from the ledger stamp (~87 s)", true, /running · (1m|8[7-9]s|9\ds)/.test(since.textContent));
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
  // a pull that changed nothing still moves the pill's stamp (it read "20m ago" on the first rehearsal)
  const pillTs0 = d.getElementById("live-pill").querySelector("[data-ts]").getAttribute("data-ts");
  const same = { ...next, live: { ...next.live, served_at: iso(Date.now() + 5000) } };
  w.fetch = () => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(same), text: () => Promise.resolve("") });
  await sleep(2400);
  eq("the live pill's stamp refreshes on a pull that moved no pane", true, d.getElementById("live-pill").querySelector("[data-ts]").getAttribute("data-ts") !== pillTs0);
  eq("channel card ages tick", true, d.querySelectorAll("#pane-channels [data-ts]").length >= 0);
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

function section4() {
  console.log("4 · the History tab: a toggle that sticks, every invocation drawn, a bad read is a state");
  const m = model();
  const { d, w, errors } = load(htmlFor(m));
  eq("no renderer error with the history in the model", 0, errors.filter(e => /Uncaught/.test(e)).length);
  const screen = d.getElementById("screen");
  eq("the board opens on This run", "run", screen.getAttribute("data-view"));
  eq("the History pane is in the DOM", true, !!d.getElementById("pane-history"));
  d.getElementById("view-history").click();
  eq("clicking History switches the view", "history", screen.getAttribute("data-view"));
  eq("…and presses its button", "true", d.getElementById("view-history").getAttribute("aria-pressed"));
  eq("the run's panes stay in the DOM, so a live patch still lands", true, !!d.getElementById("main") && !!d.getElementById("pane-preflight"));
  eq("the choice is remembered", "history", w.localStorage.getItem("rb-view"));
  const svg = d.querySelector("#pane-history .hist-scroll svg.hist-svg");
  eq("one release label for the one release in .release/", 1, svg ? svg.querySelectorAll("g.rel").length : 0);
  // the synthetic run holds a live lock (this process's pid) with a fresh heartbeat: it is the run in progress
  const liveMark = svg && svg.querySelector(".hist-live");
  eq("the run in progress is drawn live, not as a stop", "hist-live running", liveMark && liveMark.getAttribute("class").replace(/ (fresh|stale)/g, ""));
  eq("…pulsing on the run board's own freshness rule (the tick)", true, !!liveMark && liveMark.classList.contains("fresh"));
  eq("…its release label says so", true, /running/.test(svg.querySelector("g.rel").textContent));
  eq("…and the funnel does not count the undecided step as a stop", true, ![...d.querySelectorAll("#pane-history table.hist-t tbody tr")].some(tr => tr.cells[2].textContent.trim().startsWith("1")));
  // sortable table with in-cell bars
  const ths = [...d.querySelectorAll("#pane-history table.hist-t th button.sort")];
  eq("every heading sorts", 4, ths.length);
  ths[1].click();
  eq("attempts opens largest-first", "descending", d.querySelectorAll("#pane-history table.hist-t th")[1].getAttribute("aria-sort"));
  ths[1].click();
  eq("…and reverses on a second click", "ascending", d.querySelectorAll("#pane-history table.hist-t th")[1].getAttribute("aria-sort"));
  eq("the stopped column carries a data bar per row", d.querySelectorAll("#pane-history table.hist-t tbody tr").length, d.querySelectorAll("#pane-history .cellbar i").length);
  {
    // the same run, stranded: the generator's fold said so, and the history agrees
    const st = JSON.parse(JSON.stringify(m));
    st.line.stations.forEach(x => { if (x.id === "build-all") x.state = "stranded"; });
    st.liveness.alive = false;
    const { d: d6 } = load(htmlFor(st));
    const mk = d6.querySelector("#pane-history .hist-live");
    eq("a stranded run is drawn stranded, never pulsing", "hist-live stranded", mk && mk.getAttribute("class").replace(/ (fresh|stale)/g, ""));
    // and finished: no live mark at all
    const done = JSON.parse(JSON.stringify(m));
    done.line.stations.forEach(x => { if (x.state === "running") x.state = "ok"; });
    done.liveness.lock = false; done.liveness.alive = false;
    const { d: d7 } = load(htmlFor(done));
    eq("a run with no lock and nothing running has no live mark", null, d7.querySelector("#pane-history .hist-live"));
  }
  eq("there is a table view of the same numbers", true, !!d.querySelector("#pane-history table.hist-t"));
  eq("every SVG title is text, never markup", true, [...svg.querySelectorAll("title")].every(t => t.children.length === 0));
  // (a reload restoring the view is not asserted: each JSDOM gets its own storage)
  // machine versions: the synthetic tree has no git, so there are none to split by — the control says so
  const slider = d.getElementById("hist-era");
  eq("the machine-version slider exists", true, !!slider);
  d.getElementById("hist-mode-era").click();
  eq("By machine version with no named changes says there is nothing to split by", true, /no named release-machine changes to split by/.test(d.querySelector(".hist-ver").textContent));
  eq("…and draws no fault", null, d.getElementById("fault"));
  {
    const h = JSON.parse(JSON.stringify(m.history)), inv0 = h.releases[0].invocations[0];
    const later = JSON.parse(JSON.stringify(inv0)); later.id = "1.0.0#2"; later.start = "2999-01-01T00:00:00Z";
    later.exit = { kind: "completed", step: "snap" }; later.steps = [{ step: "preflight", status: "ok" }, { step: "snap", status: "ok" }];
    h.releases[0].invocations.push(later);
    h.machine_commits = [{ sha: "abcdef12", ts: "2998-01-01T00:00:00Z", subject: "x", milestone: "a named change" }];
    const { d: d5, errors: e5 } = load(htmlFor({ ...m, history: h }));
    eq("two versions: no renderer error", 0, e5.filter(e => /Uncaught/.test(e)).length);
    d5.getElementById("view-history").click();
    const s5 = d5.getElementById("hist-era");
    eq("the slider has one stop per version an attempt ran under", "1", s5.max);
    s5.value = "0"; s5.dispatchEvent(new d5.defaultView.Event("input"));
    eq("sliding switches to By machine version", "true", d5.getElementById("hist-mode-era").getAttribute("aria-pressed"));
    const groups = [...d5.querySelectorAll("#pane-history g.inv")];
    eq("…and dims the attempts outside the selected version", ["1", "0.1"], groups.map(g => g.getAttribute("opacity")));
    eq("…and names the version in words", true, /version 1 of 2 · before #1/.test(d5.querySelector(".hist-ver").textContent));
    s5.value = "1"; s5.dispatchEvent(new d5.defaultView.Event("input"));
    eq("the newest version names the change that began it", true, /after #1 .*a named change/.test(d5.querySelector(".hist-ver").textContent));
    eq("…and its one clean attempt is a 100% yield", true, /100% yield/.test(d5.querySelector(".hist-ver").textContent));
    d5.getElementById("hist-mode-all").click();
    eq("All releases undims every attempt", ["1", "1"], [...d5.querySelectorAll("#pane-history g.inv")].map(g => g.getAttribute("opacity")));
  }
  // a history that could not be read is a nodata line, not a fault band
  const broken = { ...m, history: { schema: 1, error: "ValueError: boom", releases: [] } };
  const { d: d4, errors: e4 } = load(htmlFor(broken));
  eq("a bad history read renders no fault band", null, d4.getElementById("fault"));
  eq("…and says what went wrong in the pane", true, /boom/.test(d4.getElementById("pane-history").textContent));
  eq("…with no renderer error", 0, e4.filter(e => /Uncaught/.test(e)).length);
  w.close();
}

async function section5() {
  console.log("5 · THE LINE replays in place on a live board, and only the line");
  // the generator's own frames, as /replay.json serves them
  const frames = JSON.parse(execFileSync(PY, ["-c", "import importlib.util,json,sys;from pathlib import Path\ns=importlib.util.spec_from_file_location('rb',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\nprint(json.dumps(m.line_frames(Path(sys.argv[2]),'1.0.0')))", GEN, work], { encoding: "utf8" }));
  // a failure for the scrubber to mark: the client reads a frame's caption, so one rewritten caption is enough
  frames[2].caption = frames[2].caption.replace(/ ok\b/, " fail");
  const m = model(); m.live = { generation: 1, poll_ms: 1000, served_at: iso(Date.now()), changed_at: iso(Date.now()), error: null, token: "t", with_logs: false };
  {
    const { d } = load(htmlFor(model()), "file:///board.html");
    eq("a snapshot has no replay control (no server to ask)", null, d.getElementById("line-replay"));
  }
  {
    const { d } = load(fs.readFileSync(path.join(work, "replay", "board-replay.html"), "utf8"), "file:///board-replay.html");
    eq("the --replay design page has no line replay control", null, d.getElementById("line-replay"));
  }
  const { d, w, errors } = load(htmlFor(m));
  // reduced motion: the replay opens paused on the first frame
  w.matchMedia = (q) => ({ matches: /reduce/.test(q), addEventListener() {} });
  const asked = [];
  const board = () => ({ ok: true, status: 200, json: () => Promise.resolve(m), text: () => Promise.resolve("") });
  w.fetch = (u) => { asked.push(u); return Promise.resolve(/replay\.json/.test(u) ? { ok: true, status: 200, json: () => Promise.resolve({ version: "1.0.0", frames }), text: () => Promise.resolve("") } : board()); };
  const btn = d.getElementById("line-replay");
  eq("the live line carries a replay control, top right of its heading", true, !!btn && btn.parentNode === d.querySelector("#line h2"));
  eq("…drawn with createElementNS, not markup", "svg", btn && btn.firstChild && btn.firstChild.localName);
  const lineNode = d.getElementById("line"), pre = d.getElementById("pane-preflight");
  btn.click(); await sleep(50);
  eq("it asks the server for the frames, with the token", true, asked.some(u => /^\/replay\.json\?k=t$/.test(u)));
  eq("the line enters replay, in place (same node)", true, d.getElementById("line") === lineNode && lineNode.classList.contains("replaying"));
  eq("…with a labelled control bar", true, /REPLAY/.test(d.getElementById("line-replay-ctl").textContent));
  eq("reduced motion: it opens paused on frame 0", ["0", "false"], [d.getElementById("rp-range").value, d.getElementById("rp-play").getAttribute("aria-pressed")]);
  const st = () => Object.fromEntries([...d.querySelectorAll("#line .station")].map(s => [s.querySelector("b").textContent, s.className.split(" ")[1]]));
  eq("frame 0 is before the first event", "pending", st()["preflight"]);
  d.getElementById("rp-fwd").click(); d.getElementById("rp-fwd").click();
  eq("step forward twice: frame 2, preflight decided", ["2", "ok"], [d.getElementById("rp-range").value, st()["preflight"]]);
  eq("a fail frame's caption is marked", true, d.querySelector("#line .rpcap").classList.contains("fail"));
  eq("the scrubber marks the fail frame", 1, d.querySelectorAll("#line .rpmarks i.fail").length);
  d.getElementById("rp-back").click();
  eq("step back: frame 1", "1", d.getElementById("rp-range").value);
  { const r = d.getElementById("rp-range"); r.value = "3"; r.dispatchEvent(new w.Event("input")); }
  eq("dragging the scrubber jumps to its frame", ["3", true], [d.getElementById("rp-range").value, d.querySelector("#line .rpcount").textContent.startsWith("frame 3 of ")]);
  d.getElementById("rp-back").click(); d.getElementById("rp-back").click();
  w.document.dispatchEvent(new w.KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
  w.document.dispatchEvent(new w.KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
  w.document.dispatchEvent(new w.KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
  const run = d.querySelector("#line .station.running");
  eq("→ steps too; the frame where build-all runs pulses (liveness assumed)", true, !!run && run.classList.contains("fresh"));
  eq("…and counts elapsed from the frame's clock, not today's", true, !!run && /running · \d+s/.test(run.querySelector("small").textContent));
  // a live patch while replaying: every pane may move, the line may not
  fs.appendFileSync(path.join(run_dir(), "events.jsonl"), ev(iso(T0 + 70000), "tag", "running", "attempt 1") + "\n");
  const next = model(); next.live = { ...m.live, generation: 9, served_at: iso(Date.now()) };
  w.fetch = (u) => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(next), text: () => Promise.resolve("") });
  await sleep(2400);
  eq("a live patch leaves the replaying line alone", true, d.getElementById("line") === lineNode && lineNode.classList.contains("replaying") && d.getElementById("rp-range").value === "4");
  eq("…while the rest of the board stays live", true, /tag/.test(d.getElementById("pane-events").textContent));
  eq("…and preflight, unmoved, is the same node", true, d.getElementById("pane-preflight") === pre);
  // play from a mid frame, under no reduced motion: it advances on its own
  w.matchMedia = () => ({ matches: false, addEventListener() {} });
  d.getElementById("rp-play").click();
  eq("play presses the button", "true", d.getElementById("rp-play").getAttribute("aria-pressed"));
  await sleep(2700);
  eq("…and advances a frame on its own (evenly spaced, ~10 s end to end) to the last", String(frames.length - 1), d.getElementById("rp-range").value);
  eq("the last frame holds: play stops there", "false", d.getElementById("rp-play").getAttribute("aria-pressed"));
  eq("…labelled as the line as it stands", true, /last frame/.test(d.querySelector("#line .rpcap").textContent));
  w.document.dispatchEvent(new w.KeyboardEvent("keydown", { key: " ", bubbles: true }));
  eq("space at the end replays from the start", ["0", "true"], [d.getElementById("rp-range").value, d.getElementById("rp-play").getAttribute("aria-pressed")]);
  w.document.dispatchEvent(new w.KeyboardEvent("keydown", { key: " ", bubbles: true }));
  eq("space pauses", "false", d.getElementById("rp-play").getAttribute("aria-pressed"));
  d.getElementById("rp-live").click();
  eq("back to live: the line is redrawn from the newest model", true, !d.getElementById("line").classList.contains("replaying") && st()["tag"] === "running");
  eq("…the control bar is gone", null, d.getElementById("line-replay-ctl"));
  eq("…and focus returns to the replay control", "line-replay", d.activeElement && d.activeElement.id);
  // a failing fetch is the control's state, never the board's
  w.fetch = () => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({ error: "boom" }), text: () => Promise.resolve("") });
  d.getElementById("line-replay").click(); await sleep(50);
  eq("a failed replay fetch marks the control and says why", true, d.getElementById("line-replay").classList.contains("err") && /boom/.test(d.getElementById("line-replay").title));
  eq("…and draws no fault band", null, d.getElementById("fault"));
  eq("no renderer error across the replay", 0, errors.filter(e => /Uncaught/.test(e)).length);
  w.close();
}
const run_dir = () => run;

(async () => {
  try { await section2(); section3(); section4(); await section5(); }
  catch (e) { bad("suite threw: " + (e && e.stack || e)); }
  fs.rmSync(work, { recursive: true, force: true });
  console.log(`\n${passes} passed, ${fails} failed`);
  process.exit(fails ? 1 : 0);
})();
