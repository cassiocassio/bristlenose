// Shared helpers for the page-side perf harness. No dependencies beyond e2e's playwright-core.
import { createRequire } from 'module';
import { execSync } from 'child_process';
import { mkdirSync, writeFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
export const pw = require(join(here, '../../e2e/node_modules/playwright-core'));
export const BASE = (process.env.BN_URL ?? 'http://127.0.0.1:8484').replace(/\/$/, '');
export const RESULTS = join(here, 'results');

export function args(argv = process.argv.slice(2)) {
  const o = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const [k, v] = a.slice(2).split('=');
      o[k] = v ?? (argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : true);
    } else o._.push(a);
  }
  return o;
}

export async function requireServer() {
  try {
    const r = await fetch(`${BASE}/report/`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
  } catch (e) {
    console.error(`ERROR: Bristlenose server not reachable at ${BASE}/report/ (${e.message}).\n` +
      'Start one with `bristlenose serve --dev <project>` or set BN_URL.');
    process.exit(2);
  }
}

export const gitSha = () => {
  try {
    const d = execSync('git status --porcelain', { cwd: here }).toString().trim() ? '+dirty' : '';
    return execSync('git rev-parse --short HEAD', { cwd: here }).toString().trim() + d;
  } catch { return 'unknown'; }
};

// Wraps ResizeObserver and records long tasks / LoAF / layout shifts. Runs before page scripts.
export const INIT = () => {
  const S = (window.__perf = { ro: new Map(), loopErrors: 0, longtask: [], loaf: [], cls: 0, shifts: 0 });
  const Orig = window.ResizeObserver;
  window.ResizeObserver = class extends Orig {
    constructor(cb) {
      const key = String(cb).replace(/\s+/g, ' ').slice(0, 90);
      super((entries, obs) => {
        const t0 = performance.now();
        try { return cb(entries, obs); } finally {
          const r = S.ro.get(key) ?? { calls: 0, entries: 0, ms: 0 };
          r.calls++; r.entries += entries.length; r.ms += performance.now() - t0;
          S.ro.set(key, r);
        }
      });
    }
  };
  addEventListener('error', (e) => { if (String(e.message).includes('ResizeObserver loop')) S.loopErrors++; });
  const obs = (type, fn) => { try { new PerformanceObserver((l) => l.getEntries().forEach(fn)).observe({ type, buffered: false }); } catch {} };
  obs('longtask', (e) => S.longtask.push(e.duration));
  obs('long-animation-frame', (e) => S.loaf.push({ d: e.duration, block: e.blockingDuration ?? 0 }));
  obs('layout-shift', (e) => { if (!e.hadRecentInput) { S.cls += e.value; S.shifts++; } });
};

export const resetPage = (page) => page.evaluate(() => {
  const S = window.__perf; S.ro.clear(); S.loopErrors = 0; S.longtask = []; S.loaf = []; S.cls = 0; S.shifts = 0;
});

export const frame = (page) => page.evaluate(() => new Promise((res) => {
  const t0 = performance.now();
  requestAnimationFrame(() => requestAnimationFrame(() => res(performance.now() - t0)));
}));

const stats = (a) => {
  if (!a.length) return { n: 0, mean: 0, p50: 0, p90: 0, max: 0, sum: 0 };
  const s = [...a].sort((x, y) => x - y), sum = a.reduce((x, y) => x + y, 0);
  return { n: a.length, mean: sum / a.length, p50: s[s.length >> 1], p90: s[Math.floor(s.length * 0.9)], max: s.at(-1), sum };
};

/** Run `work(page)` (returns array of per-step ms) with metrics + optional trace. */
export async function measure(ctx, page, label, work, { traceFile } = {}) {
  const { browserName } = ctx;
  let cdp, before, trace = [];
  if (browserName === 'chromium') {
    cdp = await ctx.context.newCDPSession(page);
    await cdp.send('Performance.enable');
    before = Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((m) => [m.name, m.value]));
    if (traceFile) {
      cdp.on('Tracing.dataCollected', (d) => trace.push(...d.value));
      await cdp.send('Tracing.start', { transferMode: 'ReportEvents',
        categories: 'devtools.timeline,disabled-by-default-devtools.timeline,blink.user_timing,v8.execute,loading' });
    }
  }
  await resetPage(page);
  const t0 = Date.now();
  const steps = await work(page);
  const wall = Date.now() - t0;
  const out = { label, wallMs: wall, steps: stats(steps) };
  if (cdp) {
    const done = traceFile ? new Promise((r) => cdp.once('Tracing.tracingComplete', r)) : null;
    if (traceFile) { await cdp.send('Tracing.end'); await done; writeFileSync(traceFile, JSON.stringify({ traceEvents: trace })); out.trace = traceFile; }
    const after = Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((m) => [m.name, m.value]));
    const d = (k) => (after[k] ?? 0) - (before[k] ?? 0);
    out.cdp = { LayoutCount: d('LayoutCount'), RecalcStyleCount: d('RecalcStyleCount'),
      LayoutMs: d('LayoutDuration') * 1e3, RecalcStyleMs: d('RecalcStyleDuration') * 1e3,
      ScriptMs: d('ScriptDuration') * 1e3, TaskMs: d('TaskDuration') * 1e3 };
    await cdp.detach();
  }
  const p = await page.evaluate(() => {
    const S = window.__perf;
    return { loopErrors: S.loopErrors, longtask: S.longtask, loaf: S.loaf, cls: S.cls, shifts: S.shifts,
      ro: [...S.ro.entries()].map(([k, v]) => ({ k, ...v })) };
  });
  out.page = { loopErrors: p.loopErrors, longTasks: p.longtask.length, longTaskMs: p.longtask.reduce((a, b) => a + b, 0),
    loafCount: p.loaf.length, loafMs: p.loaf.reduce((a, b) => a + b.d, 0), cls: p.cls, shifts: p.shifts };
  out.resizeObservers = p.ro.sort((a, b) => b.ms - a.ms);
  out.roTotal = { calls: p.ro.reduce((a, r) => a + r.calls, 0), ms: p.ro.reduce((a, r) => a + r.ms, 0) };
  return out;
}

export async function openPage(browserName, url, viewport = { width: 1500, height: 900 }) {
  const browser = await pw[browserName].launch();
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  await page.addInitScript(INIT);
  const resp = await page.goto(url, { waitUntil: 'domcontentloaded' });
  if (!resp || !resp.ok()) throw new Error(`HTTP ${resp && resp.status()} for ${url}`);
  await page.waitForSelector('a.bn-tab, button.bn-tab', { timeout: 20000 });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(1500);
  return { browser, context, page, browserName };
}

export function saveResult(kind, browserName, results, meta) {
  mkdirSync(RESULTS, { recursive: true });
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const file = join(RESULTS, `${kind}-${browserName}-${stamp}.json`);
  writeFileSync(file, JSON.stringify({ kind, browser: browserName, sha: gitSha(), base: BASE, date: new Date().toISOString(), ...meta, results }, null, 2));
  console.log(`\nwrote ${file}`);
  return file;
}

export function printRow(r) {
  const s = r.steps, c = r.cdp, p = r.page;
  console.log(`  ${r.label.padEnd(26)} steps=${s.n} mean=${s.mean.toFixed(1)} p90=${s.p90.toFixed(1)} max=${s.max.toFixed(1)}ms` +
    (c ? ` layout=${c.LayoutCount}/${c.LayoutMs.toFixed(0)}ms style=${c.RecalcStyleCount}/${c.RecalcStyleMs.toFixed(0)}ms script=${c.ScriptMs.toFixed(0)}ms task=${c.TaskMs.toFixed(0)}ms` : '') +
    ` RO=${r.roTotal.calls}/${r.roTotal.ms.toFixed(0)}ms loopErr=${p.loopErrors} long=${p.longTasks} loaf=${p.loafCount} cls=${p.cls.toFixed(3)}`);
}
