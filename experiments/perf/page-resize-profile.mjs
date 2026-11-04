#!/usr/bin/env node
// Viewport-width sweep per route. Usage:
//   node page-resize-profile.mjs [--browser=chromium|webkit] [--routes=quotes,sessions,...] [--mode=sweep|drag]
//                                [--trace] [--tag=name]
import { args, requireServer, openPage, measure, frame, saveResult, printRow, BASE, RESULTS } from './lib.mjs';
import { mkdirSync } from 'fs';
import { join } from 'path';

const a = args();
const browserName = a.browser ?? 'chromium';
const mode = a.mode ?? 'sweep';
const ROUTES = { quotes: '/report/quotes/', sessions: '/report/sessions/', dashboard: '/report/',
  transcript: '@transcript', signals: '/report/signals/' };
const wanted = (a.routes ?? Object.keys(ROUTES).join(',')).split(',');
const step = mode === 'drag' ? 4 : 20;
const widths = [];
for (let w = 1500; w >= 760; w -= step) widths.push(w);
for (let w = 760 + step; w <= 1500; w += step) widths.push(w);

async function discoverTranscript() {
  const html = await (await fetch(`${BASE}/report/sessions/`)).text().catch(() => '');
  const m = html.match(/\/report\/sessions\/[a-z0-9_-]+/i);
  if (m) return m[0];
  const o = await openPage(browserName, `${BASE}/report/sessions/`);
  const href = await o.page.evaluate(() => [...document.querySelectorAll('a[href]')]
    .map((x) => x.getAttribute('href')).find((h) => /^\/report\/sessions\/[^/#]+$/.test(h)));
  await o.browser.close();
  return href;
}

await requireServer();
const out = [];
let failed = 0;
for (const name of wanted) {
  let path = ROUTES[name];
  if (!path) { console.error(`unknown route ${name}`); failed++; continue; }
  try {
    if (path === '@transcript') path = await discoverTranscript();
    if (!path) throw new Error('no transcript link found on sessions page');
    const ctx = await openPage(browserName, BASE + path);
    const dom = await ctx.page.evaluate(() => document.querySelectorAll('*').length);
    mkdirSync(join(RESULTS, 'traces'), { recursive: true });
    const traceFile = a.trace && browserName === 'chromium'
      ? join(RESULTS, 'traces', `resize-${name}-${Date.now()}.json`) : null;
    const r = await measure(ctx, ctx.page, `${name} (${mode})`, async (page) => {
      const steps = [];
      for (const w of widths) {
        await page.setViewportSize({ width: w, height: 900 });
        steps.push(await frame(page));
      }
      return steps;
    }, { traceFile });
    r.route = path; r.domNodes = dom; r.sweep = { from: 1500, to: 760, step, height: 900, widths: widths.length };
    out.push(r);
    console.log(`${name} ${path} dom=${dom}`);
    printRow(r);
    if (a.verbose) r.resizeObservers.slice(0, 5).forEach((c) => console.log(`    RO ${c.calls}x ${c.ms.toFixed(1)}ms ${c.k}`));
    await ctx.browser.close();
  } catch (e) {
    failed++; console.error(`FAILED ${name}: ${e.message}`);
    out.push({ label: `${name} (${mode})`, route: path, error: e.message });
  }
}
saveResult('resize', browserName, out, { mode, tag: a.tag ?? null, viewportSweep: `1500->760->1500 step ${step} h900` });
process.exit(failed && failed === wanted.length ? 1 : 0);
