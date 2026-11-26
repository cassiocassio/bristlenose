// Runs the case table through scripts/home-freshness.js. Prints one line per failure; exit 1 if any.
const fs = require("fs"), path = require("path");
const root = path.resolve(__dirname, "..");
const H = require(path.join(root, "scripts", "home-freshness.js"));
const T = JSON.parse(fs.readFileSync(path.join(root, "tests", "fixtures", "home-freshness-cases.json"), "utf8"));
const nowMs = T.now_s * 1000;
function build(p) {
  const q = Object.assign({}, p);
  if ("as_of_offset" in q) { q.as_of = q.as_of_offset === null ? null : T.now_s + q.as_of_offset; delete q.as_of_offset; }
  if ("as_of_raw" in q) { q.as_of = q.as_of_raw === "NaN" ? NaN : q.as_of_raw; delete q.as_of_raw; }
  if ("max_age" in q && q.max_age === null) delete q.max_age;
  return q;
}
let bad = 0;
function check(name, got, want) {
  const a = JSON.stringify(got), b = JSON.stringify(want);
  if (a !== b) { bad++; console.log("FAIL " + name + "\n  got  " + a + "\n  want " + b); }
}
T.freshness.forEach(c => check("freshness: " + c.name, H.freshness(build(c.panel), nowMs), c.expect));
T.summary.forEach(c => check("summary: " + c.name, H.summary(c.panels.map(build), nowMs), c.expect));
T.page.forEach(c => check("page: " + c.name, H.pageAge(c.built_at_offset === null ? null : T.now_s + c.built_at_offset, nowMs), c.expect));
console.log((T.freshness.length + T.summary.length + T.page.length - bad) + " passed, " + bad + " failed");
process.exit(bad ? 1 : 0);
