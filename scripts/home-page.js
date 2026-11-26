/* home-page.js: draws the home page from the JSON block and keeps its ages true.
 * Inlined by scripts/home.py. Needs window.HomeFreshness (home-freshness.js) loaded first.
 * RENDER RULE: strings from the data go in through textContent on created nodes only.
 */
(function () {
  "use strict";
  var DATA = JSON.parse(document.getElementById("home-data").textContent);
  var H = window.HomeFreshness;
  var SVGNS = "http://www.w3.org/2000/svg";
  var panelEls = [];

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = String(text);
    return n;
  }
  function svg(tag, attrs) {
    var n = document.createElementNS(SVGNS, tag);
    for (var k in attrs) { if (Object.prototype.hasOwnProperty.call(attrs, k)) n.setAttribute(k, String(attrs[k])); }
    return n;
  }
  function svgText(x, y, text, anchor) {
    var t = svg("text", { x: x, y: y });
    if (anchor) t.setAttribute("text-anchor", anchor);
    t.textContent = String(text);
    return t;
  }
  function num(x, d) { return typeof x === "number" && isFinite(x) ? x : (d || 0); }

  /* A link is made only for file: and localhost URLs. Anything else is shown as plain text. */
  function safeHref(u) {
    try {
      var x = new URL(String(u));
      if (x.protocol === "file:") return x.href;
      if (x.protocol === "http:" && (x.hostname === "localhost" || x.hostname === "127.0.0.1")) return x.href;
    } catch (e) { /* not a URL */ }
    return null;
  }

  var LONDON_DATE = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", day: "numeric", month: "short", year: "numeric" });
  var LONDON_TIME = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

  /* ---- body renderers: one per kind the panels use ---- */
  var BODY = {
    kpis: function (b) {
      var d = el("div", "kpis");
      (b.items || []).forEach(function (k) {
        var kp = el("div", "kpi"), n = el("div", "n");
        var href = k.link ? safeHref(k.link) : null;
        if (href) { var a = el("a", null, k.n); a.href = href; n.appendChild(a); } else { n.textContent = String(k.n); }
        if (k.of !== undefined) { var o = el("span", null, " / " + k.of); o.style.cssText = "font-size:12px;color:var(--mute)"; n.appendChild(o); }
        kp.appendChild(n); kp.appendChild(el("div", "l", k.l)); d.appendChild(kp);
      });
      return d;
    },
    split: function (b) {
      var w = el("div");
      w.appendChild(el("div", "cap", b.title));
      var bar = el("div", "bar"); bar.setAttribute("role", "img"); bar.setAttribute("aria-label", b.aria || "");
      var total = (b.parts || []).reduce(function (s, p) { return s + num(p.n); }, 0) || 1;
      (b.parts || []).forEach(function (p) {
        var i = document.createElement("i"); i.style.width = (100 * num(p.n) / total) + "%"; i.style.background = "var(" + (p.color || "--skip") + ")"; bar.appendChild(i);
      });
      w.appendChild(bar);
      w.appendChild(el("div", "m", (b.parts || []).map(function (p) { return p.l + " " + p.n; }).join(" · ") + (b.note ? " " + b.note : "")));
      return w;
    },
    area: function (b) {          /* two stacked series: lower (opted in) under upper (not opted in); the edge is all */
      var W = 400, Hh = 110, L = 26, R = 4, T = 8, B = 20, pts = b.points || [];
      var top = Math.max.apply(null, [1].concat(pts.map(function (p) { return num(p.all); })));
      var x = function (i) { return L + i * (W - L - R) / Math.max(1, pts.length - 1); };
      var y = function (v) { return T + (Hh - T - B) * (1 - v / top); };
      var s = svg("svg", { viewBox: "0 0 " + W + " " + Hh, role: "img", "aria-label": b.aria || "" });
      [0, 0.5, 1].forEach(function (f) { s.appendChild(svg("line", { "class": "gl", x1: L, x2: W - R, y1: y(top * f), y2: y(top * f) })); });
      function path(vals, base) {
        if (!vals.length) return "";
        var up = vals.map(function (v, i) { return x(i).toFixed(1) + " " + y(v).toFixed(1); });
        var lo = vals.map(function (v, i) { return x(i).toFixed(1) + " " + y(base ? base[i] : 0).toFixed(1); }).reverse();
        return "M" + up.join(" L") + " L" + lo.join(" L") + " Z";
      }
      var all = pts.map(function (p) { return num(p.all); }), opt = pts.map(function (p) { return num(p.opt); });
      s.appendChild(svg("path", { d: path(all, opt), fill: "var(--s-a)", "fill-opacity": ".55" }));
      s.appendChild(svg("path", { d: path(opt, null), fill: "var(--s-b)", "fill-opacity": ".85" }));
      s.appendChild(svg("path", { d: "M" + opt.map(function (v, i) { return x(i).toFixed(1) + " " + y(v).toFixed(1); }).join(" L"), fill: "none", stroke: "var(--ink)", "stroke-width": "1.5" }));
      s.appendChild(svgText(0, y(top) + 3, Math.round(top))); s.appendChild(svgText(0, y(0) + 3, "0"));
      s.appendChild(svgText(L, Hh - 4, b.first_label || "")); s.appendChild(svgText(W - R, Hh - 4, b.last_label || "", "end"));
      var w = el("div"); w.appendChild(s);
      w.appendChild(el("div", "m", "■ opted in (lower)  ■ not opted in (upper) · the line is the opted-in edge"));
      return w;
    },
    line: function (b) {          /* one series, optional straight-line plan */
      var W = 400, Hh = 120, L = 26, R = 6, T = 8, B = 22, pts = b.points || [], top = Math.max(1, num(b.top, 1));
      var x = function (i) { return L + i * (W - L - R) / Math.max(1, pts.length - 1); };
      var y = function (v) { return T + (Hh - T - B) * (1 - v / top); };
      var s = svg("svg", { viewBox: "0 0 " + W + " " + Hh, role: "img", "aria-label": b.aria || "" });
      [0, 0.5, 1].forEach(function (f) { s.appendChild(svg("line", { "class": "gl", x1: L, x2: W - R, y1: y(top * f), y2: y(top * f) })); });
      if (b.plan && pts.length > 1) s.appendChild(svg("path", { d: "M" + x(0) + " " + y(top) + " L" + x(pts.length - 1) + " " + y(0), stroke: "var(--mute)", "stroke-dasharray": "3 4", fill: "none" }));
      if (pts.length) s.appendChild(svg("path", { d: "M" + pts.map(function (v, i) { return x(i).toFixed(1) + " " + y(num(v)).toFixed(1); }).join(" L"), stroke: "var(--s-open)", "stroke-width": "2", fill: "none" }));
      s.appendChild(svgText(0, y(top) + 3, top)); s.appendChild(svgText(0, y(0) + 3, "0"));
      s.appendChild(svgText(L, Hh - 4, b.first_label || "")); s.appendChild(svgText(W - R, Hh - 4, b.last_label || "", "end"));
      return s;
    },
    bars: function (b) {          /* a histogram with the counts printed on the bars */
      var items = b.items || [], W = 300, Hh = 120, top = Math.max.apply(null, [1].concat(items.map(function (i) { return num(i.n); })));
      var s = svg("svg", { viewBox: "0 0 " + W + " " + Hh, role: "img", "aria-label": b.aria || "" });
      s.appendChild(svg("line", { "class": "gl", x1: 10, x2: W - 10, y1: 94, y2: 94 }));
      var bw = 40, gap = (W - 20 - items.length * bw) / Math.max(1, items.length - 1);
      items.forEach(function (it, i) {
        var h = 76 * num(it.n) / top, x = 10 + i * (bw + gap);
        s.appendChild(svg("rect", { x: x, y: 94 - h, width: bw, height: h, fill: "var(--s-a)" }));
        s.appendChild(svgText(x + bw / 2, 94 - h - 4, it.n, "middle"));
        s.appendChild(svgText(x + bw / 2, 108, it.l, "middle"));
      });
      return s;
    },
    stations: function (b) {
      var d = el("div", "line"); d.setAttribute("role", "img"); d.setAttribute("aria-label", b.aria || "");
      (b.items || []).forEach(function (st) {
        var s = el("div", "st " + (st.state === "ok" ? "ok" : st.state === "bad" ? "bad" : ""));
        s.appendChild(document.createElement("i")); s.appendChild(el("b", null, st.name));
        if (st.note) s.appendChild(el("small", null, st.note));
        d.appendChild(s);
      });
      return d;
    },
    pills: function (b) {
      var d = el("div");
      (b.items || []).forEach(function (p) { d.appendChild(el("span", "pill " + (p.tone || ""), p.text)); d.appendChild(document.createTextNode(" ")); });
      return d;
    },
    progress: function (b) {
      var w = el("div"), bar = el("div", "bar"); bar.setAttribute("role", "img"); bar.setAttribute("aria-label", b.aria || "");
      var i = document.createElement("i"); i.style.width = (100 * num(b.done) / Math.max(1, num(b.total, 1))) + "%"; i.style.background = "var(--ok)"; bar.appendChild(i);
      w.appendChild(bar);
      if (b.items && b.items.length) { var ul = el("ul", "plain"); b.items.forEach(function (t) { ul.appendChild(el("li", null, t)); }); w.appendChild(ul); }
      return w;
    },
    expiries: function (b) {      /* rows carry their own epoch; days left is worked out in the page, from the clock */
      var t = document.createElement("table"), hr = document.createElement("tr");
      ["What", "Date", "Days"].forEach(function (h) { var th = el("th", null, h); th.scope = "col"; hr.appendChild(th); });
      t.appendChild(hr);
      (b.rows || []).forEach(function (r) {
        var tr = document.createElement("tr"), what = el("td", null, r.what), date = el("td"), days = el("td", "n");
        if (typeof r.epoch === "number" && isFinite(r.epoch)) {
          date.textContent = LONDON_DATE.format(new Date(r.epoch * 1000));
          days.setAttribute("data-epoch", String(r.epoch));
        } else { date.textContent = "unknown"; days.textContent = "? unknown"; }
        tr.appendChild(what); tr.appendChild(date); tr.appendChild(days); t.appendChild(tr);
      });
      return t;
    },
    text: function (b) { return el("div", null, b.text); }
  };

  function paintExpiries(nowMs) {
    document.querySelectorAll("td[data-epoch]").forEach(function (td) {
      var left = Math.floor((Number(td.getAttribute("data-epoch")) * 1000 - nowMs) / 86400000);
      td.textContent = left < 0 ? "▲ expired" : left < 60 ? "▲ " + left : String(left);
    });
  }

  function build() {
    var grid = document.getElementById("grid");
    DATA.panels.forEach(function (p) {
      var sec = el("section", "panel" + (p.span === 2 ? " span2" : ""));
      sec.setAttribute("data-id", String(p.id));
      var ph = el("div", "ph"), h = el("h2", "cap");
      var href = p.link ? safeHref(p.link) : null;
      if (href) { var a = el("a", null, p.title); a.href = href; if (p.link_note) a.title = p.link_note; h.appendChild(a); } else { h.textContent = p.title; }
      ph.appendChild(h);
      var fr = el("span", "fresh"); ph.appendChild(fr); sec.appendChild(ph);
      (p.body || []).forEach(function (b) { var f = BODY[b.kind]; if (f) sec.appendChild(f(b)); });
      (p.facts || []).forEach(function (t) { sec.appendChild(el("div", "m", t)); });
      var why = el("div", "why"); why.hidden = true; sec.appendChild(why);
      if (p.src) sec.appendChild(el("div", "src", p.src));
      grid.appendChild(sec);
      panelEls.push({ p: p, sec: sec, fr: fr, why: why });
    });
  }

  /* Recomputed from the clock on load and whenever the page is looked at again; no ticking interval. */
  function paint() {
    var now = Date.now();
    panelEls.forEach(function (e) {
      var f = H.freshness(e.p, now);
      e.sec.setAttribute("data-state", f.state);
      e.fr.textContent = f.words;
      e.fr.title = typeof e.p.as_of === "number" && isFinite(e.p.as_of) ? LONDON_TIME.format(new Date(e.p.as_of * 1000)) + " London" : "";
      var msg = f.note || (e.p.error ? String(e.p.error) : "");
      if (f.state === "unknown" && e.p.error) msg = String(e.p.error);
      e.why.hidden = !msg; e.why.textContent = msg;
      e.why.className = "why" + (f.state === "unknown" ? " unknown" : "");
    });
    var c = H.summary(DATA.panels, now), parts = [c.fresh + " fresh"];
    if (c.old) parts.push(c.old + " old");
    if (c.unknown) parts.push(c.unknown + " unknown");
    if (c.nodata) parts.push(c.nodata + " no data");
    var s = document.getElementById("sum");
    s.textContent = parts.join(" · ");
    s.className = "pill " + (c.unknown ? "unknown" : c.old ? "warn" : c.nodata ? "" : "ok");
    document.getElementById("again").hidden = !c.runAgain;
    var pa = H.pageAge(DATA.built_at, now);
    document.getElementById("built").textContent = pa.words;
    document.getElementById("stale24").hidden = !pa.stale;
    paintExpiries(now);
  }

  build();
  paint();
  document.addEventListener("visibilitychange", function () { if (!document.hidden) paint(); });
  window.addEventListener("focus", paint);
})();
