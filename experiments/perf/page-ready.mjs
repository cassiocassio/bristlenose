// Time from navigation to the page telling the Mac app it is ready (the `ready` bridge message),
// with a cold cache each rep, as the app's per-study web view has.
//   BN_URL=http://127.0.0.1:<port> node page-ready.mjs [--reps=10] [--browser=chromium]
// ?embedded makes the page behave as embedded; a stand-in for the WKWebView message handler
// records the moment `ready` is posted. Reports what was fetched before it.
import { args, requireServer, pw, BASE } from './lib.mjs';

const a = args();
const reps = Number(a.reps ?? 10);
await requireServer();
const browser = await pw[a.browser ?? 'chromium'].launch();
const rows = [];
for (let i = 0; i < reps + 1; i++) {
  const context = await browser.newContext({ viewport: { width: 1500, height: 900 } });
  const page = await context.newPage();
  await page.addInitScript(() => {
    window.__BRISTLENOSE_EMBEDDED__ = true;
    window.__msgs = [];
    window.webkit = { messageHandlers: { navigation: { postMessage: (m) => { window.__msgs.push({ t: performance.now(), type: m.type }); } } } };
  });
  const reqs = [];
  page.on('requestfinished', async (r) => { const t = r.timing(); reqs.push({ url: new URL(r.url()).pathname, end: t.responseEnd, bytes: (await r.sizes().catch(() => ({ responseBodySize: 0 }))).responseBodySize }); });
  await page.goto(`${BASE}/report/`, { waitUntil: 'commit' });
  await page.waitForFunction(() => window.__msgs.some((m) => m.type === 'ready'), null, { timeout: 30000 });
  const m = await page.evaluate(() => {
    const ready = window.__msgs.find((x) => x.type === 'ready').t;
    const nav = performance.getEntriesByType('navigation')[0];
    const res = performance.getEntriesByType('resource');
    const before = res.filter((r) => r.responseEnd <= ready);
    const js = before.filter((r) => /\.js(\?|$)/.test(r.name));
    const fcp = performance.getEntriesByType('paint').find((p) => p.name === 'first-contentful-paint');
    return { ready, dcl: nav.domContentLoadedEventEnd, fcp: fcp ? fcp.startTime : null, js: js.length, jsKB: js.reduce((n, r) => n + (r.transferSize || r.encodedBodySize || 0), 0) / 1024, api: before.filter((r) => r.name.includes('/api/')).map((r) => new URL(r.name).pathname) };
  });
  await context.close();
  if (i > 0) rows.push(m);
}
await browser.close();
const med = (k) => rows.map((r) => r[k]).filter((v) => v != null).sort((x, y) => x - y)[Math.floor(rows.length / 2)];
console.log(`${a.browser ?? 'chromium'}, cold cache, ${reps} reps (median / min / max, ms)`);
for (const k of ['dcl', 'fcp', 'ready']) {
  const v = rows.map((r) => r[k]).filter((x) => x != null).sort((x, y) => x - y);
  if (!v.length) { console.log(`  ${k.padEnd(6)} (not reported by this browser)`); continue; }
  console.log(`  ${k.padEnd(6)} ${v[Math.floor(v.length / 2)].toFixed(0).padStart(5)} / ${v[0].toFixed(0)} / ${v[v.length - 1].toFixed(0)}`);
}
console.log(`  JS files before ready: ${med('js')} (${(med('jsKB') ?? 0).toFixed(0)} KB on the wire); API calls before ready: ${rows[0].api.join(', ') || 'none'}`);
