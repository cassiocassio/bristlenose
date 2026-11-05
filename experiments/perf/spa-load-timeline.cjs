// usage: node spa-load-timeline.cjs <report-url> [runs]   (run from anywhere; finds Playwright in ../../e2e)
const { chromium } = require(require('path').join(__dirname, '..', '..', 'e2e', 'node_modules', 'playwright'));
if (!process.argv[2]) { console.error('usage: node spa-load-timeline.cjs <report-url> [runs]'); process.exit(2); }
(async () => {
  const runs = +process.argv[3] || 5, url = process.argv[2];
  const out = [];
  const browser = await chromium.launch();
  for (let i = 0; i < runs; i++) {
    const ctx = await browser.newContext();            // fresh context = cold cache, like a new web view
    const page = await ctx.newPage();
    await page.addInitScript(() => {
      window.__BRISTLENOSE_EMBEDDED__ = true;
      window.__bn = { ready: null, posts: [] };
      window.webkit = { messageHandlers: { navigation: { postMessage: (m) => {
        window.__bn.posts.push([m && m.type, performance.now()]);
        if (m && m.type === 'ready' && window.__bn.ready === null) window.__bn.ready = performance.now();
      } } } };
    });
    await page.goto(url, { waitUntil: 'load' });
    await page.waitForFunction(() => window.__bn.ready !== null, null, { timeout: 20000 });
    const m = await page.evaluate(() => {
      const nav = performance.getEntriesByType('navigation')[0];
      const res = performance.getEntriesByType('resource');
      const js = res.filter(r => r.name.endsWith('.js')), css = res.filter(r => r.name.endsWith('.css'));
      const api = res.filter(r => r.name.includes('/api/'));
      const sum = (a, k) => a.reduce((s, r) => s + (r[k] || 0), 0);
      const fcp = (performance.getEntriesByName('first-contentful-paint')[0] || {}).startTime;
      return {
        domInteractive: nav.domInteractive, dcl: nav.domContentLoadedEventEnd, load: nav.loadEventEnd,
        fcp, ready: window.__bn.ready,
        nJs: js.length, jsBytes: sum(js, 'decodedBodySize'), jsTransfer: sum(js, 'transferSize'),
        nCss: css.length, nApi: api.length,
        lastJsEnd: js.length ? Math.max(...js.map(r => r.responseEnd)) : null,
        firstApiStart: api.length ? Math.min(...api.map(r => r.startTime)) : null, lastApiEnd: api.length ? Math.max(...api.map(r => r.responseEnd)) : null,
        apis: api.map(r => [r.name.replace(/^.*\/api\//, '/api/'), Math.round(r.startTime), Math.round(r.responseEnd)]),
      };
    });
    out.push(m); await ctx.close();
  }
  await browser.close();
  const med = k => { const v = out.map(o => o[k]).filter(x => x != null).sort((a, b) => a - b); return Math.round(v[v.length >> 1]); };
  const keys = ['domInteractive','dcl','load','fcp','ready','lastJsEnd','firstApiStart','lastApiEnd','nJs','jsBytes','jsTransfer','nCss','nApi'];
  const sum = {}; keys.forEach(k => sum[k] = med(k));
  console.log(JSON.stringify(sum));
  console.log(JSON.stringify(out[out.length - 1].apis));
})();
