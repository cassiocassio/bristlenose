// CDP sampling CPU profile of the SPA during a width sweep, aggregated by source location (dev server only: needs unminified source).
//   node cpu-profile.cjs   (BN_URL=http://127.0.0.1:8484/report/quotes/)  It found the whole-report re-render on 4 Nov 2026: read inclusive 'react-dom' time first.
const { chromium } = require('../../e2e/node_modules/playwright-core');
const URL = process.env.BN_URL ?? 'http://127.0.0.1:8484/report/quotes/';
(async () => {
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: 1500, height: 900 } })).newPage();
  await page.goto(URL, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.quote-card', { timeout: 20000 });
  await page.waitForTimeout(2500);
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Profiler.enable'); await cdp.send('Profiler.setSamplingInterval', { interval: 200 });
  await cdp.send('Profiler.start');
  const mode = process.env.BN_MODE ?? 'resize';
  const widths = [];
  if (mode === 'resize') {
    for (let w = 1500; w >= 800; w -= 10) widths.push(w); for (let w = 800; w <= 1500; w += 10) widths.push(w);
    for (const w of widths) { await page.setViewportSize({ width: w, height: 900 }); await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))); }
  } else if (mode === 'sidebars') {
    // BN_MODE=sidebars: the contents panel ([) and the tag panel (]) opened and closed, six times each.
    await page.locator('.center').click({ position: { x: 5, y: 5 } }).catch(() => {});
    for (let i = 0; i < 12; i++) { widths.push(i); await page.keyboard.press(i % 2 ? '[' : ']'); await page.waitForTimeout(450); }
  }
  if (mode === 'lenses') {
    // BN_MODE=lenses: click through the lens tabs (Project, Sessions, Quotes, Signals, ...) three times.
    const tabs = page.locator('.bn-global-nav a');
    const n = await tabs.count();
    for (let r = 0; r < 3; r++) for (let i = 0; i < n; i++) { widths.push(i); await tabs.nth(i).click().catch(() => {}); await page.waitForTimeout(700); }
  }
  const { profile } = await cdp.send('Profiler.stop');
  const nodes = new Map(profile.nodes.map(n => [n.id, n]));
  const self = new Map(); const dt = profile.timeDeltas;
  profile.samples.forEach((id, i) => self.set(id, (self.get(id) ?? 0) + (dt[i] ?? 0)));
  const parent = new Map(); profile.nodes.forEach(n => (n.children ?? []).forEach(c => parent.set(c, n.id)));
  const key = n => `${n.callFrame.functionName || '(anon)'}  ${n.callFrame.url.replace(/^.*\/\/[^/]+/, '').replace(/\?.*$/, '')}:${n.callFrame.lineNumber + 1}`;
  const incl = new Map(), selfBy = new Map();
  for (const [id, t] of self) {
    const seen = new Set(); let cur = id;
    while (cur !== undefined) { const k = key(nodes.get(cur)); if (!seen.has(k)) { seen.add(k); incl.set(k, (incl.get(k) ?? 0) + t); } cur = parent.get(cur); }
    const k = key(nodes.get(id)); selfBy.set(k, (selfBy.get(k) ?? 0) + t);
  }
  const total = [...self.values()].reduce((a, b) => a + b, 0) / 1000;
  console.log(`mode=${process.env.BN_MODE ?? "resize"} steps=${widths.length} sampled script+idle ms=${total.toFixed(0)}`);
  const show = (m, n, f) => [...m.entries()].filter(([k]) => f(k)).sort((a, b) => b[1] - a[1]).slice(0, n).forEach(([k, v]) => console.log(`${(v / 1000).toFixed(0).padStart(6)}ms  ${k}`));
  console.log('--- inclusive, our source (frontend/src)'); show(incl, 28, k => k.includes('/src/') && !k.includes('node_modules'));
  console.log('--- inclusive, react-dom'); show(incl, 8, k => /react-dom/.test(k));
  console.log('--- self, top'); show(selfBy, 8, k => !k.startsWith('(idle)') && !k.startsWith('(program)'));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
