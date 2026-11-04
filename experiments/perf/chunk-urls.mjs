// How many times is each JS chunk fetched on a first visit, and under how many URL prefixes?
//   BN_URL=http://127.0.0.1:<port> node chunk-urls.mjs [--browser=chromium] [--lens=Sessions]
// A chunk requested as both /assets/X.js and /static/assets/X.js is two module instances: it is
// downloaded and evaluated twice, and module-level state in it exists twice.
import { args, requireServer, pw, BASE } from './lib.mjs';

const a = args();
await requireServer();
const browser = await pw[a.browser ?? 'chromium'].launch();
const page = await (await browser.newContext({ viewport: { width: 1500, height: 900 } })).newPage();
const seen = [];
page.on('request', (r) => {
  const p = new URL(r.url()).pathname;
  if (/\.(js|css)$/.test(p) && /\/assets\//.test(p)) seen.push(p);
});
await page.goto(`${BASE}/report/`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('a.bn-tab, button.bn-tab', { timeout: 20000 });
await page.waitForLoadState('networkidle').catch(() => {});
await page.waitForTimeout(1200);
for (const lens of (a.lens ?? 'Sessions,Quotes,Codebooks').split(',')) {
  await page.locator('a.bn-tab, button.bn-tab', { hasText: new RegExp(`^\\s*${lens}`, 'i') }).first().click();
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(600);
}
await browser.close();
const byName = new Map();
for (const p of seen) {
  const name = p.replace(/^\/(static\/)?assets\//, '');
  byName.set(name, [...(byName.get(name) ?? []), p.startsWith('/static/') ? '/static/assets' : '/assets']);
}
const twice = [...byName].filter(([, v]) => new Set(v).size > 1);
console.log(`${seen.length} script/style requests, ${byName.size} distinct files, ${twice.length} fetched under both prefixes`);
for (const [n] of twice.slice(0, 8)) console.log('  both:', n);
