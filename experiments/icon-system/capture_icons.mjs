// Walk the running SPA, find every chrome icon (small inline SVGs, single-glyph
// text, glyph pseudo-elements), and for each one shoot:
//   before.png — the icon in place, with its control around it (2× pixels)
//   zoom.png   — a tight crop of the icon alone (2× pixels, shown pixelated)
//   after.png  — the same place with the proposed Lucide icon swapped in,
//                stroke by the stem rule (calc(0.092 * 1em))
// and write catalogue.json for build_catalogue.py.
//
// Run from inside e2e/ (module resolution needs its node_modules):
//   cp experiments/icon-system/capture_icons.mjs e2e/ && cd e2e && \
//   node capture_icons.mjs <out-dir> <lucide-static/package/icons> [base-url]
// The out-dir holds participant text in the screenshots: keep it gitignored.
import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const [OUT, LUCIDE, BASE = "http://127.0.0.1:8150"] = process.argv.slice(2);
if (!OUT || !LUCIDE) { console.error("usage: node capture_icons.mjs <out> <lucide icons dir> [base]"); process.exit(2); }
const HERE = path.dirname(fileURLToPath(import.meta.url));
const mapPath = [path.join(HERE, "icon-map.json"), path.join(HERE, "../experiments/icon-system/icon-map.json")]
  .find((p) => fs.existsSync(p));
const MAP = JSON.parse(fs.readFileSync(mapPath, "utf8"));
fs.mkdirSync(path.join(OUT, "shots"), { recursive: true });

// Unicode chrome → proposed Lucide (the concept map's default reading).
const GLYPH = { "×": "x", "✕": "x", "✗": "x", "✓": "check", "▶": "chevron-right", "▸": "chevron-right",
  "▾": "chevron-down", "▼": "chevron-down", "▴": "chevron-up", "▲": "chevron-up", "⌃": "chevron-up",
  "↩": "undo-2", "✎": "pencil", "✦": "sparkle", "⊘": "x", "⚠": "triangle-alert", "↗": "external-link",
  "★": null, "✳": "star", "◆": null, "+": "plus", "−": "minus", "↺": "rotate-ccw" };
const lucideInner = (n) => {
  const raw = fs.readFileSync(path.join(LUCIDE, `${n}.svg`), "utf8");
  return raw.slice(raw.indexOf(">", raw.indexOf("<svg")) + 1, raw.lastIndexOf("</svg>")).trim()
    .replace(/<(path|circle|line|rect|polyline|polygon|ellipse)\b/g, '<$1 vector-effect="non-scaling-stroke"');
};

const STEPS = [
  { name: "dashboard", url: "/report/" },
  { name: "sessions", url: "/report/sessions/" },
  { name: "sessions-tapestry", url: "/report/sessions/", act: async (p) => {
      const b = p.locator(".bn-tapestry-toggle, button[aria-expanded='false'][class*='disclos']").first();
      if (await b.count()) await b.click(); } },
  { name: "transcript", url: "/report/sessions/", act: async (p) => {
      const href = await p.evaluate(() => [...document.querySelectorAll("a[href]")].map((a) => a.getAttribute("href"))
        .find((h) => /\/report\/sessions\/[^/]+\/?$/.test(h)));
      if (href) { await p.goto(new URL(href, BASE).href, { waitUntil: "domcontentloaded" }); await p.waitForTimeout(1500); } } },
  { name: "quotes", url: "/report/quotes/" },
  { name: "quotes-tags-panel", url: "/report/quotes/", act: async (p) => {
      await p.locator("button.rail-btn[aria-label='Tags']:visible").first().click(); } },
  { name: "quotes-contents-panel", url: "/report/quotes/", act: async (p) => {
      await p.locator("button.rail-btn:visible").first().click(); } },
  { name: "codebook", url: "/report/codebook/" },
  { name: "signals", url: "/report/signals/" },
  { name: "discussion", url: "/report/discussion/" },
  { name: "screens", url: "/report/screens/" },
  { name: "settings", url: "/report/", act: async (p) => {
      await p.locator("button.bn-tab-icon[aria-label='Settings']:visible").first().click(); } },
  { name: "help", url: "/report/", act: async (p) => {
      await p.locator("button.bn-tab-icon[aria-label='Help']:visible").first().click(); } },
  { name: "export-menu", url: "/report/quotes/", act: async (p) => {
      await p.locator(".export-dropdown-wrapper > button.bn-tab-icon:visible").first().click(); } },
  { name: "inspector", url: "/report/quotes/", act: async (p) => {
      const b = p.locator("[aria-label*='eatmap' i], [title*='eatmap' i]").first();
      if (await b.count()) await b.click(); } },
];

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2,
  colorScheme: "light" });
const page = await ctx.newPage();
const items = [];
const seen = new Map();

async function settle() {
  await page.waitForLoadState("networkidle", { timeout: 4000 }).catch(() => {});
  await page.waitForTimeout(600);
}

const ONLY = process.env.STEPS ? process.env.STEPS.split(",") : null;
for (const step of STEPS) {
  if (ONLY && !ONLY.includes(step.name)) continue;
  try {
    await page.goto(BASE + step.url, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForSelector("#bn-app-root *", { timeout: 15000 }).catch(() => {});
    await settle();
    if (step.act) { await step.act(page); await settle(); }
    if (process.env.DEBUG) await page.screenshot({ path: path.join(OUT, `debug-${step.name}.png`) });
  } catch (e) { console.log(`skip ${step.name}: ${e.message.split("\n")[0]}`); continue; }

  const found = await page.evaluate(({ glyphs, svgMap }) => {
    const out = [];
    let n = 0;
    const HOST = "button, a, summary, [role=button], [role=menuitem], [role=tab], [role=option], label, .badge, li";
    const hidden = (el) => {
      if (!el.checkVisibility({ visibilityProperty: true })) return true;
      // an ancestor above the icon's own control at opacity 0 = a closed dialog, not a hover reveal
      const host = el.closest(HOST) || el;
      const DIALOG = "[role=dialog], dialog, [class*=modal], [class*=overlay], [class*=popover], [aria-hidden=true]";
      for (let a = host.parentElement; a; a = a.parentElement)
        if (a.matches(DIALOG) && getComputedStyle(a).opacity === "0") return true;
      return false;
    };
    const tag = (el, kind, extra) => {
      if (hidden(el)) return;
      const id = `icat-${Date.now()}-${n++}`;
      el.setAttribute("data-icat", id);
      const c = el.closest("button, a, summary, [role=button], [role=menuitem], [role=tab], [role=option], label, .badge, li") || el.parentElement;
      const cls = (c.getAttribute("class") || "").split(/\s+/).filter(Boolean).slice(0, 3).join(".");
      out.push({ id, kind, ctx: `${c.tagName.toLowerCase()}${cls ? "." + cls : ""}`,
        aria: c.getAttribute("aria-label") || c.getAttribute("title") || "",
        text: (c.innerText || "").replace(/\s+/g, " ").trim().slice(0, 50), ...extra });
    };
    for (const s of document.querySelectorAll("svg")) {
      if (s.closest("symbol, defs")) continue;
      const r = s.getBoundingClientRect();
      if (r.width === 0 || r.height === 0 || r.width > 32 || r.height > 32) continue;
      const html = s.outerHTML;
      const hit = svgMap.find((m) => html.includes(m.needle));
      tag(s, "svg", { sig: html.replace(/\s(class|style|data-icat)="[^"]*"/g, ""),
        row: hit?.row || null, lucide: hit?.lucide || null });
    }
    const all = document.querySelectorAll("body *");
    for (const el of all) {
      if (el.closest("svg")) continue;
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      if (el.children.length === 0) {
        const t = (el.textContent || "").trim();
        if (t && [...t].length === 1 && t in glyphs) tag(el, "glyph", { glyph: t, sig: `glyph:${t}`, lucide: glyphs[t] });
      }
      for (const pseudo of ["::before", "::after"]) {
        const c = getComputedStyle(el, pseudo).content;
        if (!c || c === "none" || c === "normal") continue;
        const ch = [...c.replace(/^["']|["']$/g, "").trim()].find((x) => x in glyphs);
        if (ch) tag(el, "pseudo", { glyph: ch, pseudo, sig: `pseudo:${pseudo}:${ch}`, lucide: glyphs[ch] });
      }
    }
    return out;
  }, { glyphs: GLYPH, svgMap: MAP.svg });

  let shot = 0;
  const pending = [];
  for (const it of found) {
    const key = `${it.sig}|${it.ctx}`;
    const count = seen.get(key) || 0;
    if (count >= 1) continue;  // one instance per drawing-in-context
    seen.set(key, count + 1);
    const el = page.locator(`[data-icat="${it.id}"]`);
    try {
      await el.scrollIntoViewIfNeeded({ timeout: 2000 });
      const host = el.locator("xpath=ancestor-or-self::*[self::button or self::a or self::summary or @role='button' or @role='menuitem' or @role='tab' or contains(concat(' ',@class,' '),' badge ') or self::label or self::li][1]");
      const hov = (await host.count()) ? host : el;
      await hov.hover({ timeout: 1500, force: true }).catch(() => {});
      await page.waitForTimeout(200);
      const ib = await el.boundingBox();
      const hb = (await hov.boundingBox()) || ib;
      if (!ib || !hb) continue;
      const vp = page.viewportSize();
      const pad = (b, x, y) => {
        const left = Math.max(0, b.x - x), top = Math.max(0, b.y - y);
        return { x: left, y: top, width: Math.min(vp.width - left, b.width + 2 * x), height: Math.min(vp.height - top, b.height + 2 * y) };
      };
      const base = `${step.name}-${String(shot++).padStart(2, "0")}`;
      const ctxClip = pad({ x: Math.min(ib.x, hb.x), y: Math.min(ib.y, hb.y),
        width: Math.max(ib.x + ib.width, hb.x + hb.width) - Math.min(ib.x, hb.x),
        height: Math.max(ib.y + ib.height, hb.y + hb.height) - Math.min(ib.y, hb.y) }, 28, 12);
      if (ctxClip.width > 520) { ctxClip.x = Math.max(0, ib.x - 240); ctxClip.width = 500; }
      if (ctxClip.height > 110) { ctxClip.y = Math.max(0, ib.y - 45); ctxClip.height = Math.min(vp.height - ctxClip.y, ib.height + 90); }
      // a pseudo-element has no box of its own: crop to where its glyph sits on the
      // element (::before at the start, ::after at the end), about two ems wide
      let zb = ib;
      if (it.kind === "pseudo") {
        const em = await el.evaluate((n) => parseFloat(getComputedStyle(n).fontSize) || 13);
        const w = Math.min(ib.width, em * 2.2);
        zb = it.pseudo === "::before" ? { x: ib.x, y: ib.y, width: w, height: ib.height }
          : { x: ib.x + ib.width - w + em * 0.6, y: ib.y - em * 0.6, width: w, height: ib.height + em * 0.6 };
      }
      const zoomClip = pad(zb, 4, 4);
      await page.screenshot({ path: path.join(OUT, "shots", `${base}-before.png`), clip: ctxClip });
      await page.screenshot({ path: path.join(OUT, "shots", `${base}-zoom.png`), clip: zoomClip });
      const rec = { ...it, step: step.name, base, after: null, url: step.url,
        zrel: { dx: zb.x - ib.x, dy: zb.y - ib.y, w: zb.width, h: zb.height } };
      items.push(rec);
      // the crop relative to the icon, so pass 2 can find the same frame after scrolling
      pending.push({ it, rec, rel: { dx: ctxClip.x - ib.x, dy: ctxClip.y - ib.y, w: ctxClip.width, h: ctxClip.height } });
      process.stdout.write(".");
    } catch (e) { /* element went away (re-render); skip */ }
  }
  // second pass: swap every proposed icon in, then shoot each place again
  for (const { it, rec, rel } of pending) {
    try {
      const base = rec.base;
      const hostOf = () => page.locator(`[data-icat="${it.id}"]`).locator("xpath=ancestor-or-self::*[self::button or self::a or self::summary or @role='button' or @role='menuitem' or @role='tab' or contains(concat(' ',@class,' '),' badge ') or self::label or self::li][1]");
      const rehover = async () => { const h = hostOf(); if (await h.count()) await h.first().hover({ timeout: 1000, force: true }).catch(() => {}); };
      await rehover();
      if (it.lucide) {
        const inner = lucideInner(it.lucide);
        const swapped = await page.evaluate(({ id, inner, kind, stems, pseudo }) => {
          const el = document.querySelector(`[data-icat="${id}"]`);
          if (!el) return false;
          // the rule: stroke = stem of the text the icon sits in (its weight, its size).
          // Below 420 the browser renders 400 (Inter is served 400..700), so clamp there.
          const pts = Object.entries(stems).map(([w, v]) => [+w, v]).filter(([w]) => w >= 420).sort((a, b) => a[0] - b[0]);
          const stemFor = (w) => {
            if (w <= pts[0][0]) return pts[0][1];
            for (let i = 1; i < pts.length; i++) if (w <= pts[i][0]) {
              const [w0, v0] = pts[i - 1], [w1, v1] = pts[i]; return v0 + (v1 - v0) * (w - w0) / (w1 - w0); }
            return pts[pts.length - 1][1];
          };
          const textOf = kind === "pseudo" ? getComputedStyle(el, pseudo) : getComputedStyle(kind === "svg" ? el.parentElement : el);
          const stem = stemFor(parseFloat(textOf.fontWeight) || 420);
          window.__icatStem = { weight: textOf.fontWeight, size: textOf.fontSize, stem };
          const svg = `<svg class="bn-icat-swap" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;width:1em;height:1em;vertical-align:-0.125em;stroke-width:max(1px, calc(${stem} * 1em));flex:none">${inner}</svg>`;
          if (kind === "svg") {
            const r = el.getBoundingClientRect();
            const fs = parseFloat(getComputedStyle(el.parentElement).fontSize) || 13;
            const span = document.createElement("span");
            span.innerHTML = svg;
            const s = span.firstChild;
            // keep the original box, so layout doesn't move; stem follows the text around it
            s.style.width = `${r.width}px`; s.style.height = `${r.height}px`;
            s.style.strokeWidth = `${Math.max(1, stem * fs)}px`;
            el.replaceWith(s);
            s.setAttribute("data-icat", id);
          } else if (kind === "glyph") {
            el.innerHTML = svg;
          } else {
            // keep the pseudo-element's own box (a badge's delete circle, a summary's indent):
            // swap only its content, as an image in the glyph's colour and size
            const cs = getComputedStyle(el, pseudo);
            const px = parseFloat(cs.fontSize) || 12;
            const img = `<svg xmlns="http://www.w3.org/2000/svg" width="${px}" height="${px}" viewBox="0 0 24 24" fill="none" stroke="${cs.color}" stroke-width="${(Math.max(1, stem * px) * 24 / px).toFixed(2)}" stroke-linecap="round" stroke-linejoin="round">${inner.replace(/ vector-effect="non-scaling-stroke"/g, "")}</svg>`;
            const st = document.createElement("style");
            const url = `url("data:image/svg+xml,${encodeURIComponent(img)}")`;
            st.textContent = `[data-icat="${id}"]${pseudo}{color:transparent!important;background-image:${url}!important;` +
              `background-repeat:no-repeat!important;background-position:center!important;background-size:${px}px ${px}px!important}`;
            document.head.appendChild(st);
          }
          return true;
        }, { id: it.id, inner, kind: it.kind, stems: MAP.stems, pseudo: it.pseudo });
        rec.stemInfo = await page.evaluate(() => window.__icatStem || null);
        if (swapped) {
          const node = page.locator(`[data-icat="${it.id}"]`).first();
          await node.scrollIntoViewIfNeeded({ timeout: 1500 }).catch(() => {});
          await rehover();
          const nb0 = await node.boundingBox();
          if (!nb0) continue;
          const vp0 = page.viewportSize();
          const cx = Math.max(0, nb0.x + rel.dx), cy = Math.max(0, nb0.y + rel.dy);
          const ctxClip = { x: cx, y: cy, width: Math.min(vp0.width - cx, rel.w), height: Math.min(vp0.height - cy, rel.h) };
          await page.waitForTimeout(150);
          rec.after = `${base}-after.png`;
          await page.screenshot({ path: path.join(OUT, "shots", rec.after), clip: ctxClip });
          let nb = await page.locator(`[data-icat="${it.id}"]`).first().boundingBox().catch(() => null);
          if (nb && it.kind === "pseudo") nb = { x: nb.x + rec.zrel.dx, y: nb.y + rec.zrel.dy, width: rec.zrel.w, height: rec.zrel.h };
          if (nb) {
            const vp = page.viewportSize();
            const z = { x: Math.max(0, nb.x - 4), y: Math.max(0, nb.y - 4) };
            z.width = Math.min(vp.width - z.x, nb.width + 8); z.height = Math.min(vp.height - z.y, nb.height + 8);
            rec.afterZoom = `${base}-after-zoom.png`;
            await page.screenshot({ path: path.join(OUT, "shots", rec.afterZoom), clip: z });
          }
        }
      }
    } catch (e) { /* skip */ }
  }
  console.log(` ${step.name}: ${found.length} found, ${shot} shot`);
}

fs.writeFileSync(path.join(OUT, "catalogue.json"), JSON.stringify({ base: BASE, when: new Date().toISOString(), items }, null, 1));
await browser.close();
console.log(`${items.length} icons → ${OUT}`);
