#!/usr/bin/env node
// Interaction metrics on the quotes page. Usage:
//   node interaction-profile.mjs [--browser=chromium|webkit] [--trace] [--tag=name] [--verbose]
// Each interaction is one "case"; every step inside is timed to a double rAF.
import { args, requireServer, openPage, measure, frame, saveResult, printRow, BASE, RESULTS } from './lib.mjs';
import { mkdirSync } from 'fs';
import { join } from 'path';

const a = args();
const browserName = a.browser ?? 'chromium';

const CASES = {
  // Wheel-scroll the quotes page top to bottom in 500px notches, then back to the top.
  async scroll(page) {
    await page.mouse.move(750, 500);
    const steps = [];
    let last = -1;
    for (let i = 0; i < 80; i++) {
      await page.mouse.wheel(0, 500);
      steps.push(await frame(page));
      const y = await page.evaluate(() => Math.max(window.scrollY,
        ...[...document.querySelectorAll('*')].filter((e) => e.scrollTop > 0).map((e) => e.scrollTop)));
      if (y === last) break;
      last = y;
    }
    await page.evaluate(() => { window.scrollTo(0, 0); document.querySelectorAll('*').forEach((e) => { e.scrollTop = 0; }); });
    return steps;
  },
  // Toggle the tag sidebar (']') and the contents sidebar ('[') open/closed, 3 times each.
  async sidebars(page) {
    const steps = [];
    for (const key of [']', '[']) {
      for (let i = 0; i < 6; i++) {
        await page.keyboard.press(key);
        await page.waitForTimeout(40);
        steps.push(await frame(page));
        await page.waitForTimeout(250); // let the width transition settle
      }
    }
    return steps;
  },
  // Click through every lens tab and back to Quotes.
  async lenses(page) {
    const steps = [];
    const names = ['Sessions', 'Codebooks', 'Signals', 'Discussion', 'Project', 'Quotes'];
    for (const n of names) {
      const t0 = Date.now();
      await page.locator('a.bn-tab, button.bn-tab', { hasText: new RegExp(`^${n}$`) }).first().click();
      await page.waitForTimeout(50);
      await frame(page);
      steps.push(Date.now() - t0);
      await page.waitForTimeout(400);
    }
    return steps;
  },
};

await requireServer();
const ctx = await openPage(browserName, `${BASE}/report/quotes/`);
await ctx.page.waitForSelector('.quote-card', { timeout: 20000 });
const out = [];
mkdirSync(join(RESULTS, 'traces'), { recursive: true });
for (const [name, fn] of Object.entries(CASES)) {
  try {
    const traceFile = a.trace && browserName === 'chromium' ? join(RESULTS, 'traces', `interaction-${name}-${Date.now()}.json`) : null;
    const r = await measure(ctx, ctx.page, name, fn, { traceFile });
    r.route = '/report/quotes/';
    out.push(r); printRow(r);
    if (a.verbose) r.resizeObservers.slice(0, 4).forEach((c) => console.log(`    RO ${c.calls}x ${c.ms.toFixed(1)}ms ${c.k}`));
  } catch (e) {
    console.error(`FAILED ${name}: ${e.message}`);
    out.push({ label: name, error: e.message });
  }
  await ctx.page.goto(`${BASE}/report/quotes/`, { waitUntil: 'domcontentloaded' });
  await ctx.page.waitForSelector('.quote-card', { timeout: 20000 });
  await ctx.page.waitForTimeout(1000);
}
await ctx.browser.close();
saveResult('interaction', browserName, out, { tag: a.tag ?? null });
process.exit(out.some((r) => r.error) ? 1 : 0);
