// What does an open, untouched report cost? Requests per minute, and CPU in the page and the server.
//   BN_URL=http://127.0.0.1:<port> BN_PID=<serve pid> node idle.mjs [--lens=Quotes] [--secs=120] [--hidden]
// --hidden emulates a backgrounded tab (visibilityState hidden) to see whether polling stops.
// Page CPU is the Chromium task time over the window (CDP Performance.getMetrics); server CPU is
// ps cputime over the same window. Serve a COPY of a project with serve-fixture.py.
import { execSync } from 'child_process';
import { args, requireServer, pw, BASE } from './lib.mjs';

const a = args();
const secs = Number(a.secs ?? 120);
const pid = process.env.BN_PID;
await requireServer();

const cpuSeconds = (p) => {
  const t = execSync(`ps -o cputime= -p ${p}`).toString().trim(); // [[dd-]hh:]mm:ss.cc
  const parts = t.split(':').map(parseFloat);
  return parts.reduce((acc, v) => acc * 60 + v, 0);
};

const browser = await pw.chromium.launch();
const context = await browser.newContext({ viewport: { width: 1500, height: 900 } });
const page = await context.newPage();
const cdp = await context.newCDPSession(page);
await cdp.send('Performance.enable');
await page.goto(`${BASE}/report/`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('a.bn-tab, button.bn-tab', { timeout: 20000 });
if (a.lens) await page.locator('a.bn-tab, button.bn-tab', { hasText: new RegExp(`^\\s*${a.lens}`, 'i') }).first().click();
await page.waitForLoadState('networkidle').catch(() => {});
await page.waitForTimeout(3000);
if (a.hidden) {
  await cdp.send('Emulation.setFocusEmulationEnabled', { enabled: false }).catch(() => {});
  await page.evaluate(() => {
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' });
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
    document.dispatchEvent(new Event('visibilitychange'));
  });
}
const metric = async (name) => (await cdp.send('Performance.getMetrics')).metrics.find((m) => m.name === name)?.value ?? 0;
const reqs = [];
page.on('request', (r) => { const u = new URL(r.url()); if (u.pathname.startsWith('/api/')) reqs.push(u.pathname.replace('/api/projects/1', '').replace('/api', '')); });

const t0 = { task: await metric('TaskDuration'), script: await metric('ScriptDuration'), srv: pid ? cpuSeconds(pid) : null };
await page.waitForTimeout(secs * 1000);
const t1 = { task: await metric('TaskDuration'), script: await metric('ScriptDuration'), srv: pid ? cpuSeconds(pid) : null };
await browser.close();

const counts = {};
for (const r of reqs) counts[r] = (counts[r] ?? 0) + 1;
const perMin = (n) => (n * 60 / secs).toFixed(1);
console.log(`window ${secs}s${a.hidden ? ', page emulated hidden' : ''}, lens ${a.lens ?? 'landing'}`);
console.log(`requests: ${reqs.length} total = ${perMin(reqs.length)} / min`);
for (const [p, n] of Object.entries(counts).sort((x, y) => y[1] - x[1])) console.log(`  ${p.padEnd(28)} ${String(n).padStart(4)}  (${perMin(n)} / min)`);
console.log(`page main-thread task time: ${((t1.task - t0.task) * 1000).toFixed(0)} ms over ${secs}s = ${((t1.task - t0.task) / secs * 100).toFixed(2)} % of one core (script ${((t1.script - t0.script) * 1000).toFixed(0)} ms)`);
if (pid) console.log(`server CPU: ${((t1.srv - t0.srv) * 1000).toFixed(0)} ms over ${secs}s = ${((t1.srv - t0.srv) / secs * 100).toFixed(2)} % of one core`);
