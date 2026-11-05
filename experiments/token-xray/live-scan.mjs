#!/usr/bin/env node
// Live token X-ray: walk a rendered Bristlenose page and report every computed
// colour / font-size / radius / spacing value that is not a --bn-* token value.
//
//   cd e2e && node ../experiments/token-xray/live-scan.mjs <url> [--overlay] [--out file.json] [--shot file.png]
//
// Needs the full stack up (serve on :8484). Not a test: it never fails a build,
// it produces evidence. Declared exceptions are elements (or ancestors) carrying
// data-ds-deviation="reason" -> reported as "deliberate", not "freelance".
//
// Static twin: scripts/audit-css.py reads the CSS source; this reads the screen.

import { createRequire } from 'node:module';
import { writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const require = createRequire(resolve(process.cwd(), 'package.json'));
const { chromium } = require('@playwright/test');

const args = process.argv.slice(2);
const url = args.find((a) => !a.startsWith('--') && !args[args.indexOf(a) - 1]?.startsWith('--out') && !args[args.indexOf(a) - 1]?.startsWith('--shot'));
const flag = (n) => args.includes(n);
const opt = (n) => (args.includes(n) ? args[args.indexOf(n) + 1] : null);
if (!url) {
  console.error('usage: live-scan.mjs <url> [--overlay] [--out f.json] [--shot f.png] [--dark]');
  process.exit(2);
}

const browser = await chromium.launch();

const scan = (page, overlay) => page.evaluate((overlay) => {
  const probe = document.createElement('div');
  probe.style.cssText = 'position:absolute;visibility:hidden';
  document.body.appendChild(probe);
  const norm = (prop, v) => {
    probe.style[prop] = '';
    probe.style[prop] = v;
    return getComputedStyle(probe)[prop];
  };

  // 1. Token vocabulary: every --bn-* custom property on :root, normalised.
  const root = getComputedStyle(document.documentElement);
  const names = new Set();
  for (const sheet of document.styleSheets) {
    let rules;
    try { rules = sheet.cssRules; } catch { continue; }
    const walk = (rs) => {
      for (const r of rs) {
        if (r.style) for (const p of r.style) if (p.startsWith('--bn-')) names.add(p);
        if (r.cssRules) walk(r.cssRules);
      }
    };
    walk(rules);
  }
  const vocab = { color: new Set(), length: new Set() };
  for (const n of names) {
    const v = root.getPropertyValue(n).trim();
    if (!v) continue;
    vocab.color.add(norm('color', v));
    // paddingTop, not width: width is layout-snapped (0.15rem -> 2.39062px)
    // while padding keeps the specified value (2.4px), which is what elements report.
    vocab.length.add(norm('paddingTop', v));
  }
  const okLen = (v) => ['0px', 'auto', 'normal', '1px', '100%'].includes(v) || vocab.length.has(v);
  const okCol = (v) =>
    v === 'rgba(0, 0, 0, 0)' || v === 'transparent' || vocab.color.has(v) ||
    // tokens with alpha are normalised the same way, so a miss here is real
    false;

  const COLOUR = ['color', 'backgroundColor', 'borderTopColor', 'outlineColor'];
  const LENGTH = ['fontSize', 'borderTopLeftRadius', 'paddingTop', 'paddingLeft', 'marginTop', 'rowGap', 'columnGap'];

  const label = (el) => {
    const cls = [...el.classList].filter((c) => c.startsWith('bn-')).slice(0, 2).join('.');
    return el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (cls ? '.' + cls : '');
  };
  const deviation = (el) => el.closest('[data-ds-deviation]')?.getAttribute('data-ds-deviation') ?? null;

  const findings = [];
  for (const el of document.body.querySelectorAll('*')) {
    if (el === probe || !el.offsetParent && getComputedStyle(el).position !== 'fixed') continue;
    if (el.closest('svg') && el.tagName !== 'svg') continue;
    const cs = getComputedStyle(el);
    const bad = [];
    for (const p of COLOUR) {
      if (p === 'borderTopColor' && cs.borderTopWidth === '0px') continue;
      if (p === 'outlineColor' && cs.outlineStyle === 'none') continue;
      if (!okCol(cs[p])) bad.push({ prop: p, value: cs[p] });
    }
    for (const p of LENGTH) if (!okLen(cs[p])) bad.push({ prop: p, value: cs[p] });
    if (!bad.length) continue;
    const dev = deviation(el);
    findings.push({
      el: label(el),
      path: (() => { const parts = []; let n = el; while (n && n !== document.body && parts.length < 4) { parts.unshift(label(n)); n = n.parentElement; } return parts.join(' > '); })(),
      status: dev ? 'deliberate' : 'freelance',
      reason: dev,
      bad,
    });
    if (overlay) {
      el.style.outline = dev ? '2px dashed #00a3a3' : '2px solid #d100d1';
      el.style.outlineOffset = '-2px';
    }
  }
  probe.remove();
  return { tokens: names.size, findings };
}, overlay);

const summarise = (findings) => {
  const byValue = {};
  for (const f of findings) for (const b of f.bad) {
    const k = `${b.prop}=${b.value}`;
    byValue[k] = (byValue[k] ?? 0) + 1;
  }
  return Object.entries(byValue).sort((a, b) => b[1] - a[1]).slice(0, 15);
};

if (flag('--all')) {
  // Every tab, both colour schemes. Tabs come from the page's own tablist.
  const pages = [];
  for (const scheme of ['light', 'dark']) {
    const pg = await browser.newPage({ viewport: { width: 1280, height: 900 }, colorScheme: scheme });
    await pg.goto(url, { waitUntil: 'load' });
    await pg.waitForTimeout(1500);
    const tabs = await pg.evaluate(() =>
      // the top tab bar only: sidebar and in-page anchors sit below it
      [...document.querySelectorAll('[role=tab], [role=tablist] a, nav a')]
        .filter((e) => e.getBoundingClientRect().top < 230)
        .map((e) => ({ label: e.textContent.trim(), href: e.getAttribute('href') }))
        .filter((t) => t.label));
    const seen = new Set();
    for (const t of tabs) {
      if (seen.has(t.label)) continue;
      seen.add(t.label);
      if (t.href && t.href.startsWith('/')) await pg.goto(new URL(t.href, url).href, { waitUntil: 'load' });
      else await pg.getByRole('tab', { name: t.label, exact: true }).first().click().catch(() => {});
      await pg.waitForTimeout(1200);
      const r = await scan(pg, false);
      pages.push({ tab: t.label, scheme, url: pg.url(), tokens: r.tokens, total: r.findings.length,
        freelance: r.findings.filter((f) => f.status === 'freelance').length,
        deliberate: r.findings.filter((f) => f.status === 'deliberate').length,
        topValues: summarise(r.findings), findings: r.findings });
      console.log(`${scheme.padEnd(5)} ${t.label.padEnd(12)} off-token elements: ${r.findings.length}`);
    }
    await pg.close();
  }
  if (opt('--out')) writeFileSync(opt('--out'), JSON.stringify({ url, scannedAt: new Date().toISOString(), pages }, null, 2));
  await browser.close();
  process.exit(0);
}

const page = await browser.newPage({
  viewport: { width: 1280, height: 900 },
  colorScheme: flag('--dark') ? 'dark' : 'light',
});
await page.goto(url, { waitUntil: 'load' });
await page.waitForTimeout(1500); // SPA mount; networkidle is untrustworthy here
const result = await scan(page, flag('--overlay'));

const top = summarise(result.findings);

const out = { url, tokens: result.tokens, total: result.findings.length,
  freelance: result.findings.filter((f) => f.status === 'freelance').length,
  deliberate: result.findings.filter((f) => f.status === 'deliberate').length,
  topValues: top, findings: result.findings };
if (opt('--out')) writeFileSync(opt('--out'), JSON.stringify(out, null, 2));
if (opt('--shot')) await page.screenshot({ path: opt('--shot'), fullPage: false });

console.log(`${url}  tokens:${out.tokens}  off-token elements:${out.total} (freelance ${out.freelance}, deliberate ${out.deliberate})`);
for (const [k, n] of top) console.log(`  ${String(n).padStart(4)}  ${k}`);
await browser.close();
