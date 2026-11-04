#!/usr/bin/env node
// Compare two result files.  node summarise.mjs [--baseline=before.json] after.json
// With one file, just prints it. Positive delta = slower/more work.
import { readFileSync } from 'fs';
import { args } from './lib.mjs';

const a = args();
const files = a._;
const base = a.baseline ? JSON.parse(readFileSync(a.baseline, 'utf8')) : null;
const cur = files.length ? JSON.parse(readFileSync(files.at(-1), 'utf8')) : null;
if (!cur) { console.error('usage: summarise.mjs [--baseline=old.json] new.json'); process.exit(2); }

const metrics = (r) => ({
  'step mean ms': r.steps?.mean, 'step p90 ms': r.steps?.p90, 'step max ms': r.steps?.max,
  'layouts': r.cdp?.LayoutCount, 'layout ms': r.cdp?.LayoutMs, 'style ms': r.cdp?.RecalcStyleMs,
  'script ms': r.cdp?.ScriptMs, 'task ms': r.cdp?.TaskMs,
  'RO calls': r.roTotal?.calls, 'RO ms': r.roTotal?.ms, 'RO loop err': r.page?.loopErrors,
  'long tasks': r.page?.longTasks, 'LoAF': r.page?.loafCount, 'CLS': r.page?.cls,
});
const f = (v) => (v == null ? '-' : Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(Math.abs(v) < 1 && v !== 0 ? 3 : 1));
const pad = (s, n) => String(s).padStart(n);

console.log(`${base ? 'baseline' : 'run'}: ${(base ?? cur).browser} @${(base ?? cur).sha} ${(base ?? cur).tag ?? ''}`);
if (base) console.log(`current : ${cur.browser} @${cur.sha} ${cur.tag ?? ''}`);
for (const r of cur.results) {
  if (r.error) { console.log(`\n${r.label}: ERROR ${r.error}`); continue; }
  const b = base?.results.find((x) => x.label === r.label && x.route === r.route && !x.error);
  console.log(`\n${r.label}  ${r.route ?? ''}`);
  const m = metrics(r), bm = b ? metrics(b) : null;
  console.log(`  ${'metric'.padEnd(14)}${bm ? pad('before', 10) + pad('after', 10) + pad('delta', 9) : pad('value', 10)}`);
  for (const [k, v] of Object.entries(m)) {
    if (v == null) continue;
    if (!bm) { console.log(`  ${k.padEnd(14)}${pad(f(v), 10)}`); continue; }
    const o = bm[k], pct = o ? `${(((v - o) / o) * 100).toFixed(0)}%` : (v === 0 ? '0%' : 'n/a');
    console.log(`  ${k.padEnd(14)}${pad(f(o), 10)}${pad(f(v), 10)}${pad(pct, 9)}`);
  }
  if (base && !b) console.log('  (no matching baseline row)');
}
