// What does following a recording cost? Synthetic player time-updates into the transcript page.
//   BN_URL=http://127.0.0.1:<port> node playback.mjs [--session=s3] [--ticks=120] [--step=0.25]
// The player pops out and posts {type:"bristlenose-timeupdate", pid, seconds, playing} about four
// times a second; the page toggles word spans and sets a progress variable. This posts the same
// messages at the same pace and reads Chromium's counters (CDP) across the window.
import { args, requireServer, pw, BASE } from './lib.mjs';

const a = args();
const session = a.session ?? 's3';
const ticks = Number(a.ticks ?? 120);
const playing = a.playing !== 'false';
const step = Number(a.step ?? 0.25);
await requireServer();
const browser = await pw.chromium.launch();
const context = await browser.newContext({ viewport: { width: 1500, height: 900 } });
const page = await context.newPage();
const cdp = await context.newCDPSession(page);
await cdp.send('Performance.enable');
await page.goto(`${BASE}/report/sessions/${session}`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('.transcript-segment', { timeout: 30000 });
await page.waitForLoadState('networkidle').catch(() => {});
await page.waitForTimeout(1500);

const info = await page.evaluate(() => {
  const words = document.querySelectorAll('.transcript-word[data-start]');
  const segs = document.querySelectorAll('.transcript-segment');
  // the segment with the most words, and where its first word starts
  let best = null, n = 0;
  segs.forEach((s) => { const c = s.querySelectorAll('.transcript-word').length; if (c > n) { n = c; best = s; } });
  const first = best?.querySelector('.transcript-word[data-start]');
  return { words: words.length, segments: segs.length, biggest: n, start: first ? parseFloat(first.getAttribute('data-start')) : 0 };
});
console.log(`transcript ${session}: ${info.words} words in ${info.segments} segments, biggest paragraph ${info.biggest} words, start ${info.start.toFixed(1)}s`);

const m = async () => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
await page.evaluate(() => {
  window.__loaf = [];
  new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__loaf.push({ start: e.startTime, d: e.duration, queue: e.renderStart - e.startTime, render: e.startTime + e.duration - e.renderStart, scripts: e.scripts.reduce((n, x) => n + x.duration, 0) }); }).observe({ type: 'long-animation-frame', buffered: true });
});
if (a.prop) await page.addStyleTag({ content: '@property --bn-segment-progress { syntax: "<number>"; inherits: false; initial-value: 0; }' });
const windowStart = await page.evaluate(() => performance.now());
const t0 = await m();
await page.evaluate(async ({ pid, start, ticks, step, playing }) => {
  for (let i = 0; i < ticks; i++) {
    window.postMessage({ type: 'bristlenose-timeupdate', pid, seconds: start + i * step, playing }, '*');
    await new Promise((r) => setTimeout(r, 250)); // the player's own pace
  }
}, { pid: session, start: info.start, ticks, step, playing });
if (ticks === 0) await page.waitForTimeout(30000);
if (ticks) await page.waitForTimeout(300);
const t1 = await m();
const loaf = (await page.evaluate(() => window.__loaf)).filter((e) => e.start >= windowStart);
const activeWords = await page.evaluate(() => document.querySelectorAll('.transcript-word.bn-word-active').length);
await browser.close();

const d = (k) => (t1[k] - t0[k]);
const n = ticks || 120;
const per = (k) => ((d(k) * 1000) / n).toFixed(2);
console.log(`${ticks} ticks at 250 ms (${(n * 0.25).toFixed(0)} s), playing=${playing}, ${activeWords} word(s) active at the end`);
console.log(`main thread busy: ${(d('TaskDuration') / (n * 0.25) * 100).toFixed(0)} % of the window`);
console.log(`per tick: task ${per('TaskDuration')} ms | script ${per('ScriptDuration')} ms | style recalc ${per('RecalcStyleDuration')} ms (${(d('RecalcStyleCount') / n).toFixed(1)} per tick) | layout ${per('LayoutDuration')} ms (${(d('LayoutCount') / n).toFixed(1)} per tick)`);
console.log(`long animation frames inside the window: ${loaf.length}`);
const worst = loaf.sort((x, y) => y.d - x.d)[0];
if (worst) console.log(`  worst: ${worst.d.toFixed(0)} ms = ${worst.queue.toFixed(0)} ms before render (script ${worst.scripts.toFixed(0)}) + ${worst.render.toFixed(0)} ms render`);
