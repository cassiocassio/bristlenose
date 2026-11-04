// CDP sampling CPU profile of the SPA during a width sweep, aggregated by source location (dev server only: needs unminified source).
//   node cpu-profile.cjs   (BN_URL=http://127.0.0.1:8484/report/quotes/)  It found the whole-report re-render on 4 Nov 2026: read inclusive 'react-dom' time first.
// BN_MODE=search types a word into the toolbar field (BN_WORD, default "someth"; BN_GAP ms between keys, default 170) six times.
// BN_COUNT=1 (search mode) installs a React DevTools-style commit hook instead of the profiler and prints which components
// rendered, per commit: the profile says where the time went, the count says who re-rendered.
// BN_VITE=http://localhost:5199 serves the SPA's source from YOUR OWN Vite instead of a `serve --dev` page, so a prod-bundle
// `serve` on an ephemeral port can be profiled with unminified names (the document is rewritten in flight; start Vite with
// a port that is not 5173, a cacheDir of your own and no `server.origin`, and never point it at a shared dev stack).
const { chromium } = require('../../e2e/node_modules/playwright-core');
const URL = process.env.BN_URL ?? 'http://127.0.0.1:8484/report/quotes/';
(async () => {
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: 1500, height: 900 } })).newPage();
  const VITE = process.env.BN_VITE;
  if (VITE) {
    await page.route((u) => u.pathname.startsWith('/report/') && !/\.(js|css|json|svg|png|woff2?)$/.test(u.pathname), async (route) => {
      if (route.request().resourceType() !== 'document') return route.continue();
      const resp = await route.fetch();
      let html = await resp.text();
      html = html.replace(/<script type="module"[^>]*src="[^"]*assets\/main-[^"]*"[^>]*><\/script>/, '')
        .replace(/<link rel="modulepreload"[^>]*>/g, '');
      const dev = `<script type="module">import RefreshRuntime from '/@react-refresh'; RefreshRuntime.injectIntoGlobalHook(window); window.$RefreshReg$ = () => {}; window.$RefreshSig$ = () => (type) => type; window.__vite_plugin_react_preamble_installed__ = true</script>` +
        `<script type="module" src="/@vite/client"></script><script type="module" src="/src/main.tsx"></script>`;
      html = html.replace('</body>', dev + '</body>');
      await route.fulfill({ response: resp, body: html });
    });
  }
  if (VITE) {
    // The page's origin is the serve; Chromium refuses a cross-origin loopback script without a permission prompt, so the
    // module requests are answered from the Vite instance through the harness instead.
    await page.route((u) => /^\/(src\/|@|node_modules\/)/.test(u.pathname), async (route) => {
      const u = new globalThis.URL(route.request().url()); // the file's own `URL` is the page address
      await route.fulfill({ response: await route.fetch({ url: VITE + u.pathname + u.search }) });
    });
  }
  const COUNT = process.env.BN_COUNT === '1';
  if (COUNT) {
    await page.addInitScript(() => {
      const names = new Map(); let commits = 0, recording = false, perCommit = [];
      const nameOf = (f) => { const t = f.type; return t ? (t.displayName || t.name || (t.type && (t.type.displayName || t.type.name)) || (t.render && t.render.name) || '?') : '?'; };
      window.__renders = { start() { names.clear(); commits = 0; perCommit = []; recording = true; }, stop() { recording = false; return { commits, perCommit, names: [...names.entries()] }; } };
      window.__REACT_DEVTOOLS_GLOBAL_HOOK__ = {
        supportsFiber: true, isDisabled: false, renderers: new Map(), checkDCE() {}, onScheduleFiberRoot() {}, onPostCommitFiberRoot() {}, onCommitFiberUnmount() {},
        inject(r) { const id = this.renderers.size + 1; this.renderers.set(id, r); return id; },
        onCommitFiberRoot(id, root) {
          if (!recording) return;
          commits++;
          const here = {};
          (function walk(f) {
            while (f) {
              if ((f.tag === 0 || f.tag === 1 || f.tag === 11 || f.tag === 14 || f.tag === 15) && (f.flags & 1) && f.alternate) {
                const n = nameOf(f); names.set(n, (names.get(n) || 0) + 1); here[n] = (here[n] || 0) + 1;
              }
              if (f.child) walk(f.child);
              f = f.sibling;
            }
          })(root.current);
          perCommit.push(here);
        },
      };
    });
  }
  await page.goto(URL, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.quote-card', { timeout: 20000 });
  await page.waitForTimeout(2500);
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Profiler.enable'); await cdp.send('Profiler.setSamplingInterval', { interval: 200 });
  const mode = process.env.BN_MODE ?? 'resize';
  const widths = [];
  const profiles = [];
  const startProf = () => cdp.send('Profiler.start');
  const stopProf = async () => { const { profile } = await cdp.send('Profiler.stop'); profiles.push(profile); };
  if (mode !== 'search') await startProf();
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
  if (mode === 'search') {
    // BN_MODE=search: type the word six times; only the typing and the wait for its results are sampled, not the clearing.
    const word = process.env.BN_WORD ?? 'someth', gap = +(process.env.BN_GAP ?? 170);
    await page.click('.search-toggle'); await page.waitForTimeout(400);
    const counted = [];
    for (let r = 0; r < 6; r++) {
      widths.push(r);
      if (COUNT) await page.evaluate(() => window.__renders.start()); else await startProf();
      for (const ch of word) { await page.keyboard.press(ch); await page.waitForTimeout(gap); }
      await page.waitForTimeout(700);
      if (COUNT) counted.push(await page.evaluate(() => window.__renders.stop())); else await stopProf();
      for (let i = 0; i < 3; i++) {
        if (!(await page.evaluate(() => document.querySelector('input.search-input')?.value))) break;
        await page.keyboard.press('Escape'); await page.waitForTimeout(120);
      }
      await page.waitForTimeout(900);
      await page.evaluate(() => document.querySelector('input.search-input')?.focus());
    }
    if (COUNT) {
      const tot = new Map(); let commits = 0;
      counted.forEach((c) => { commits += c.commits; c.names.forEach(([n, k]) => tot.set(n, (tot.get(n) || 0) + k)); });
      console.log(`word=${word} gap=${gap} trials=${counted.length}: ${commits} commits (${(commits / counted.length).toFixed(1)} per typing of ${word.length} keys)`);
      console.log('components rendered (total over trials; per typing in parens), our source names first:');
      [...tot.entries()].sort((a, b) => b[1] - a[1]).slice(0, 40).forEach(([n, k]) => console.log(`${String(k).padStart(7)}  (${(k / counted.length).toFixed(1).padStart(7)})  ${n}`));
      console.log('commit shapes, trial 1 (components rendered in each commit, top 6 by count):');
      counted[0].perCommit.forEach((h, i) => console.log(`  commit ${i + 1}: ${Object.values(h).reduce((x, y) => x + y, 0)} renders; ` + Object.entries(h).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([n, k]) => `${n}x${k}`).join(' ')));
      await browser.close(); return;
    }
  }
  if (mode !== 'search') await stopProf();
  const incl = new Map(), selfBy = new Map(); let totalUs = 0;
  for (const profile of profiles) {
    const nodes = new Map(profile.nodes.map(n => [n.id, n]));
    const self = new Map(); const dt = profile.timeDeltas;
    profile.samples.forEach((id, i) => self.set(id, (self.get(id) ?? 0) + (dt[i] ?? 0)));
    const parent = new Map(); profile.nodes.forEach(n => (n.children ?? []).forEach(c => parent.set(c, n.id)));
    const key = n => `${n.callFrame.functionName || '(anon)'}  ${n.callFrame.url.replace(/^.*\/\/[^/]+/, '').replace(/\?.*$/, '')}:${n.callFrame.lineNumber + 1}`;
    for (const [id, t] of self) {
      totalUs += t;
      const seen = new Set(); let cur = id;
      while (cur !== undefined) { const k = key(nodes.get(cur)); if (!seen.has(k)) { seen.add(k); incl.set(k, (incl.get(k) ?? 0) + t); } cur = parent.get(cur); }
      const k = key(nodes.get(id)); selfBy.set(k, (selfBy.get(k) ?? 0) + t);
    }
  }
  const total = totalUs / 1000;
  console.log(`mode=${process.env.BN_MODE ?? "resize"} steps=${widths.length} sampled script+idle ms=${total.toFixed(0)}`);
  const show = (m, n, f) => [...m.entries()].filter(([k]) => f(k)).sort((a, b) => b[1] - a[1]).slice(0, n).forEach(([k, v]) => console.log(`${(v / 1000).toFixed(0).padStart(6)}ms  ${k}`));
  console.log('--- inclusive, our source (frontend/src)'); show(incl, 28, k => k.includes('/src/') && !k.includes('node_modules'));
  console.log('--- inclusive, react-dom'); show(incl, 8, k => /react-dom/.test(k));
  console.log('--- self, top'); show(selfBy, 8, k => !k.startsWith('(idle)') && !k.startsWith('(program)'));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
