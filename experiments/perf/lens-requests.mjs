// Count the API requests a lens makes when it opens, and how many of them are the same URL.
//   BN_URL=http://127.0.0.1:<port> node lens-requests.mjs [--browser=chromium] [--lenses=Quotes,Codebooks,Sessions]
// Serve a COPY of a project with serve-fixture.py first. A mount that asks for the same GET
// three times in a few milliseconds queues behind itself on one server: this is what shows it.
import { args, requireServer, pw, BASE } from './lib.mjs';

const a = args();
const browserName = a.browser ?? 'chromium';
const lenses = (a.lenses ?? 'Quotes,Codebooks,Sessions').split(',');
await requireServer();

const browser = await pw[browserName].launch();
const out = [];
for (const lens of lenses) {
  const context = await browser.newContext({ viewport: { width: 1500, height: 900 } });
  const page = await context.newPage();
  await page.goto(`${BASE}/report/`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('a.bn-tab, button.bn-tab', { timeout: 20000 });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(1500);
  const seen = [];
  page.on('request', (r) => {
    const u = new URL(r.url());
    if (u.pathname.startsWith('/api/') && r.method() === 'GET') seen.push(u.pathname.replace('/api/projects/1', ''));
  });
  await page.locator('a.bn-tab, button.bn-tab', { hasText: new RegExp(`^\\s*${lens}`, 'i') }).first().click();
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(800);
  const counts = {};
  for (const p of seen) counts[p] = (counts[p] ?? 0) + 1;
  const dup = Object.entries(counts).filter(([, n]) => n > 1);
  out.push({ lens, total: seen.length, unique: Object.keys(counts).length, duplicates: dup });
  await context.close();
}
await browser.close();
for (const r of out) {
  console.log(`${r.lens.padEnd(10)} ${String(r.total).padStart(2)} requests, ${r.unique} distinct` +
    (r.duplicates.length ? `  repeated: ${r.duplicates.map(([p, n]) => `${p} x${n}`).join(', ')}` : ''));
}
