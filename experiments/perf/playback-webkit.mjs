// Playback in WebKit (the Mac app's engine), A/B on the progress variable: does a tick reach a painted frame sooner?
//   BN_URL=... node playback-webkit.mjs [--session=s3] [--ticks=60] [--reps=3]
// Per tick: time from the postMessage to a double rAF (the frame that carries it). A = shipped CSS (variable not
// inherited); B = the variable made inheriting again by a later @property rule. Interleaved A,B,A,B.
import { args, requireServer, pw, BASE } from './lib.mjs';
const a = args();
const session = a.session ?? 's3', ticks = +(a.ticks ?? 60), reps = +(a.reps ?? 3);
await requireServer();
const browser = await pw.webkit.launch();
async function run(inherit) {
  const ctx = await browser.newContext({ viewport: { width: 1500, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/report/sessions/${session}`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.transcript-segment', { timeout: 30000 });
  await page.waitForTimeout(1500);
  if (inherit) await page.addStyleTag({ content: '@property --bn-segment-progress { syntax: "<number>"; inherits: true; initial-value: 0; }' });
  const r = await page.evaluate(async ({ pid, ticks }) => {
    const first = document.querySelector('.transcript-word[data-start]');
    const start = parseFloat(first.getAttribute('data-start'));
    const out = [];
    for (let i = 0; i < ticks; i++) {
      const t = performance.now();
      window.postMessage({ type: 'bristlenose-timeupdate', pid, seconds: start + i * 0.25, playing: true }, '*');
      await new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res)));
      out.push(performance.now() - t);
      await new Promise((res) => setTimeout(res, 250));
    }
    return out;
  }, { pid: session, ticks });
  await ctx.close();
  r.sort((x, y) => x - y);
  const q = (p) => r[Math.min(r.length - 1, Math.floor(r.length * p))];
  return { p50: q(0.5), p90: q(0.9), max: r[r.length - 1] };
}
const res = { A: [], B: [] };
for (let i = 0; i < reps; i++) for (const [k, inh] of [['A', false], ['B', true]]) res[k].push(await run(inh));
await browser.close();
const f = (x) => x.toFixed(1);
for (const k of ['A', 'B']) console.log(`${k} ${k === 'A' ? 'shipped (not inherited)' : 'inherits'}: ` + res[k].map((x) => `p50 ${f(x.p50)} p90 ${f(x.p90)} max ${f(x.max)}`).join(' | '));
