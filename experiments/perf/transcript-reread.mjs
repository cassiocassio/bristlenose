// What does a transcript write cost the page? Every speaker pick, split, join or reassign ends in a
// re-read of the whole transcript. This fires the same event the page listens for after a speaker
// write (bn:speakers-written) and times it to the next double rAF after the new data is drawn.
//   BN_URL=http://127.0.0.1:<port> node transcript-reread.mjs [--session=s3] [--reps=8]
// Reports wall time, Chromium's script/style/layout across the window, and whether the word spans
// were REPLACED (a fresh DOM) or reused.
import { args, requireServer, pw, BASE } from './lib.mjs';

const a = args();
const session = a.session ?? 's3';
const reps = Number(a.reps ?? 8);
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

const m = async () => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((x) => [x.name, x.value]));
const rows = [];
let replaced = null;
for (let i = 0; i < reps + 1; i++) {
  const before = await m();
  const r = await page.evaluate(async () => {
    const word = document.querySelector('.transcript-word');
    word.__mark = 'kept';
    const words = document.querySelectorAll('.transcript-word').length;
    const t0 = performance.now();
    let drawn = 0;
    const done = new Promise((resolve) => {
      const obs = new MutationObserver(() => { drawn += 1; });
      obs.observe(document.body, { childList: true, subtree: true });
      // settled = no mutation for 150 ms after the request answers
      const check = () => {
        const last = performance.now();
        setTimeout(() => { if (drawn === 0 && performance.now() - t0 > 400) { obs.disconnect(); resolve(); } else if (performance.now() - t0 > 3000) { obs.disconnect(); resolve(); } else check(); }, 150);
        void last;
      };
      check();
    });
    window.dispatchEvent(new Event('bn:speakers-written'));
    await done;
    const still = document.querySelector('.transcript-word');
    return { words, ms: performance.now() - t0, kept: still && still.__mark === 'kept', mutations: drawn };
  });
  const after = await m();
  if (i === 0) continue; // warm-up
  rows.push({ ...r, script: (after.ScriptDuration - before.ScriptDuration) * 1000, style: (after.RecalcStyleDuration - before.RecalcStyleDuration) * 1000, layout: (after.LayoutDuration - before.LayoutDuration) * 1000, task: (after.TaskDuration - before.TaskDuration) * 1000 });
  replaced = !r.kept;
}
await browser.close();
const med = (k) => rows.map((r) => r[k]).sort((x, y) => x - y)[Math.floor(rows.length / 2)];
console.log(`${session}: ${rows[0].words} word spans, ${reps} rereads`);
console.log(`word spans ${replaced ? 'REPLACED (fresh DOM each time)' : 'kept (reused)'}; DOM mutation records per reread: ${med('mutations')}`);
console.log(`per reread (median, includes ~0.6 s observation window): task ${med('task').toFixed(0)} ms | script ${med('script').toFixed(0)} ms | style ${med('style').toFixed(0)} ms | layout ${med('layout').toFixed(0)} ms`);
