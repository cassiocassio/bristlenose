/* home-freshness.js: THE freshness rules for the home page. One copy.
 *
 * Inlined into the page by scripts/home.py (so a page opened a day later turns old by itself) and
 * run by node in tests/test_home_freshness.py against tests/fixtures/home-freshness-cases.json.
 * No DOM, no clock of its own: every function takes `nowMs`, so the tests pin the clock.
 *
 * A panel, as the readers write it (all times are UTC epoch SECONDS; display zones are the page's job):
 *   status        "ok" | "nodata" | "unknown"   unknown = could not ask; nodata = nothing exists to read
 *   as_of         when the DATA last changed or was last successfully fetched. Never the time the page
 *                 was built or the file was merely read. null when there is none.
 *   as_of_label   "pulled" | "changed" | "counted" | "run" ...: the verb in "pulled 4 min ago"
 *   max_age       seconds the data may be before it counts as old
 *   refreshable   can running `home` again make it fresher? false where a person must move the data
 *   stateless     true for a panel that is only a link (Visitors): it has no state at all
 *
 * Fail closed: anything that cannot be decided is `unknown`, never `fresh`. A missing or unparseable
 * as_of, a timestamp in the future, a missing age limit: all unknown. (In JS `NaN > max` is false,
 * so a careless comparison would call every such panel fresh.)
 *
 * Old and unknown carry a mark IN THE WORDS (\u25b2, ?): state is never colour alone (WCAG 1.4.1).
 */
(function (root) {
  "use strict";
  var FUTURE_TOLERANCE_S = 300;   // clocks differ by minutes between this Mac and the host

  function isNum(x) { return typeof x === "number" && isFinite(x); }

  /* "just now", "4 min ago", "22 h ago", "10 days ago". Under 48 h we count hours, so "1 day" never appears. */
  function ago(seconds) {
    var s = Math.max(0, seconds);
    if (s < 60) return "just now";
    if (s < 3600) return Math.floor(s / 60) + " min ago";
    if (s < 48 * 3600) return Math.floor(s / 3600) + " h ago";
    return Math.floor(s / 86400) + " days ago";
  }

  function words(label, seconds) {
    var a = ago(seconds);
    return a === "just now" ? label + " just now" : label + " " + a;
  }

  /* -> { state: "fresh"|"old"|"unknown"|"nodata"|"link", words: string, note: string|null } */
  function freshness(panel, nowMs) {
    var nowS = nowMs / 1000;
    if (panel.stateless) return { state: "link", words: "", note: null };
    if (!isNum(nowMs)) return { state: "unknown", words: "? clock unreadable", note: null };
    if (panel.status === "nodata") return { state: "nodata", words: "no data", note: null };
    if (panel.status !== "ok" && panel.status !== "unknown") return { state: "unknown", words: "? unrecognised status", note: null };
    var label = panel.as_of_label || "as of";
    var hasAsOf = isNum(panel.as_of);
    if (panel.status === "unknown") {
      if (hasAsOf && panel.as_of <= nowS + FUTURE_TOLERANCE_S) {
        return { state: "unknown", words: "? could not ask · data from " + ago(nowS - panel.as_of), note: null };
      }
      return { state: "unknown", words: "? could not ask", note: null };
    }
    if (!hasAsOf) return { state: "unknown", words: "? no timestamp", note: null };
    if (panel.as_of > nowS + FUTURE_TOLERANCE_S) {
      return { state: "unknown", words: "? timestamp is in the future", note: null };
    }
    if (!isNum(panel.max_age) || panel.max_age <= 0) {
      return { state: "unknown", words: "? no age limit set", note: null };
    }
    var age = nowS - panel.as_of;
    if (age > panel.max_age) {
      return { state: "old", words: "\u25b2 old \u00b7 " + words(label, age),
               note: panel.refreshable === false ? "Refreshing will not change this: the data itself has not changed." : null };
    }
    return { state: "fresh", words: words(label, age), note: null };
  }

  /* Counts for the top line. Link-only panels have no state and are left out; no-data panels are counted. */
  function summary(panels, nowMs) {
    var c = { fresh: 0, old: 0, unknown: 0, nodata: 0, runAgain: false };
    panels.forEach(function (p) {
      var f = freshness(p, nowMs);
      if (f.state === "link") return;
      c[f.state] += 1;
      if ((f.state === "old" || f.state === "unknown") && p.refreshable !== false) c.runAgain = true;
    });
    return c;
  }

  /* The page's own age, from the time it was built. Over a day old it says so, once, at the top. */
  function pageAge(builtAtS, nowMs) {
    var nowS = nowMs / 1000;
    if (!isNum(builtAtS)) return { words: "page age unknown", stale: true };
    var age = nowS - builtAtS;
    if (age < -FUTURE_TOLERANCE_S) return { words: "page age unknown", stale: true };
    return { words: "page built " + ago(age), stale: age > 24 * 3600 };
  }

  var api = { freshness: freshness, summary: summary, pageAge: pageAge, ago: ago };
  root.HomeFreshness = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : this);
