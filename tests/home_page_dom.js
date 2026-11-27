// Runs a built home page in jsdom with a pinned, movable clock and checks what a person would see.
//   node tests/home_page_dom.js <page.html>   (env HOME_NOW_S = the pinned clock, epoch seconds)
// Needs frontend/node_modules/jsdom. Exits 3, saying so, when it is absent: skipped is not passed.
"use strict";
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, "..");
let JSDOM, VirtualConsole;
try { ({ JSDOM, VirtualConsole } = require(path.join(ROOT, "frontend", "node_modules", "jsdom"))); }
catch (e) { console.error("SKIPPED, NOT PASSED: frontend/node_modules/jsdom is absent"); process.exit(3); }
const html = fs.readFileSync(process.argv[2], "utf8");
const NOW = Number(process.env.HOME_NOW_S) * 1000;
let fails = 0, passes = 0;
const ok = (name, cond, extra) => { if (cond) passes++; else { fails++; console.log("FAIL " + name + (extra ? "\n  " + extra : "")); } };
const errors = [];
const vc = new VirtualConsole(); vc.on("jsdomError", e => errors.push(String(e.message || e)));
function open(offsetMs) {
  let t = NOW + (offsetMs || 0);
  const dom = new JSDOM(html, { runScripts: "dangerously", pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) { const RD = w.Date; w.__setNow = (v) => { t = v; };
      class FD extends RD { constructor(...a) { if (a.length === 0) super(t); else super(...a); } static now() { return t; } }
      w.Date = FD; } });
  return dom;
}
const dom = open(0), w = dom.window, d = w.document;
if (process.argv[3] === "--real") {
  // A page built from the real readers: it must run, draw all nine panels with a heading, and show no leaked JS values.
  ok("no script error", errors.length === 0, errors.join(" | "));
  ok("nine panels", d.querySelectorAll("section.panel").length === 9, String(d.querySelectorAll("section.panel").length));
  ok("each has an h2", d.querySelectorAll("section.panel > .ph > h2").length === 9);
  const visible = d.querySelector("header.top").textContent + d.getElementById("grid").textContent;   // not the inlined script text
  ok("nothing rendered as undefined or [object Object] or NaN", !/undefined|\[object Object\]|NaN/.test(visible), (visible.match(/.{0,30}(undefined|\[object Object\]|NaN).{0,30}/) || [""])[0]);
  ok("the summary says something", d.getElementById("sum").textContent.length > 0);
  console.log(passes + " passed, " + fails + " failed");
  process.exit(fails ? 1 : 0);
}
const panel = (id) => d.querySelector('section[data-id="' + id + '"]');
ok("no script error", errors.length === 0, errors.join(" | "));
ok("three scripts only (data, freshness, page): nothing the data typed became a script", d.scripts.length === 3, "scripts=" + d.scripts.length);
ok("every panel has an h2 title", d.querySelectorAll("section.panel").length === d.querySelectorAll("section.panel > .ph > h2").length);
ok("fresh", panel("fresh").getAttribute("data-state") === "fresh", panel("fresh").getAttribute("data-state"));
ok("old pull", panel("old").getAttribute("data-state") === "old");
ok("old words carry the mark as text", /^▲ old/.test(panel("old").querySelector(".fresh").textContent), panel("old").querySelector(".fresh").textContent);
ok("source-old says refreshing will not change it", /Refreshing will not change this/.test(panel("srcold").querySelector(".why").textContent));
ok("unknown carries ?", /^\? could not ask/.test(panel("unk").querySelector(".fresh").textContent));
ok("unknown shows only the fixed error string", panel("unk").querySelector(".why").textContent === "host unreachable");
ok("no data in words", panel("nod").querySelector(".fresh").textContent === "no data");
ok("link-only panel has no state words", panel("lnk").querySelector(".fresh").textContent === "" && panel("lnk").getAttribute("data-state") === "link");
ok("summary counts", d.getElementById("sum").textContent === "2 fresh · 2 old · 1 unknown · 1 no data", d.getElementById("sum").textContent);
ok("summary is a status region", d.getElementById("sum").getAttribute("role") === "status");
ok("run-again line shows when something refreshable is old", d.getElementById("again").hidden === false);
ok("a safe file link is a link", !!panel("fresh").querySelector("h2 a") && panel("fresh").querySelector("h2 a").href.startsWith("file:"));
ok("a javascript: link is plain text", !panel("evil").querySelector("h2 a") && /javascript/.test(panel("evil").querySelector("h2").textContent));
ok("a hostile title is text, not markup", panel("evil").querySelector("h2").textContent.includes("<img src=x onerror=alert(1)>") && !d.querySelector("img"));
ok("a hostile fact is text", /<\/script><script>alert\(2\)<\/script>/.test(panel("evil").textContent));
const exp = Array.from(d.querySelectorAll("td.n")).map(td => td.textContent);
ok("expiry rows: soon, later, expired, unknown", JSON.stringify(exp) === JSON.stringify(["▲ 30 · soon", "100", "▲ expired", "? unknown", "▲ expired"]), JSON.stringify(exp));
const dates = Array.from(d.querySelectorAll("table tr")).map(tr => tr.children[1] && tr.children[1].textContent);
ok("a date-only expiry reads as its own UTC date, not the next day in London summer time", dates.includes("19 Apr 2026"), JSON.stringify(dates));
ok("page age is fresh now", d.getElementById("stale24").hidden === true && /^page built/.test(d.getElementById("built").textContent), d.getElementById("built").textContent);
// the clock moves on: looked at again two hours later, the fresh panel (limit 1 h) is old, with no reload
w.__setNow(NOW + 2 * 3600 * 1000); d.dispatchEvent(new w.Event("visibilitychange"));
ok("a page left open turns old when looked at again", panel("fresh").getAttribute("data-state") === "old", panel("fresh").getAttribute("data-state"));
ok("and a 30-day-plus-an-hour expiry has lost a day after two hours (floor)", Array.from(d.querySelectorAll("td.n")).map(td => td.textContent)[0] === "▲ 29 · soon", Array.from(d.querySelectorAll("td.n")).map(td => td.textContent)[0]);
w.__setNow(NOW + 3 * 86400 * 1000); w.dispatchEvent(new w.Event("focus"));
ok("three days later the page itself is stale", d.getElementById("stale24").hidden === false);
ok("and a 30-day expiry has lost three days", Array.from(d.querySelectorAll("td.n")).map(td => td.textContent)[0] === "▲ 27 · soon", Array.from(d.querySelectorAll("td.n")).map(td => td.textContent)[0]);
console.log(passes + " passed, " + fails + " failed");
process.exit(fails ? 1 : 0);
