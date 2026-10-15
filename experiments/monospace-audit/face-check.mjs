// Which face does each stack reach? Large-glyph ink at 100px tells Menlo, Courier and SF Mono apart
// (metrics-based labels proved unreliable). Run in a lang="en" page, as the report is: WebKit's
// generic `monospace` is Courier without a lang attribute and Menlo with one.
import { createRequire } from 'node:module';
const { chromium, webkit } = createRequire(new URL('../../e2e/package.json', import.meta.url))('playwright');
const fams = ["'SF Mono'", 'ui-monospace', 'Menlo', 'Courier', 'monospace',
  '"SF Mono", "Fira Code", "Consolas", monospace', '"Fira Code", "Consolas", monospace',
  '"SF Mono", ui-monospace, monospace', 'ui-monospace, monospace',
  "ui-monospace, Menlo, Consolas, 'DejaVu Sans Mono', monospace"];
for (const [en, eng] of [['webkit', webkit], ['chromium', chromium]]) {
  const b = await eng.launch(); const pg = await b.newPage({ viewport: { width: 900, height: 1600 } }); // tall enough for every row: Chromium's fullPage capture resizes the viewport and swaps its generic monospace from Courier to Menlo
  for (const lang of ['', 'lang="en"']) {
    await pg.setContent(`<!doctype html><html ${lang}><body style="margin:0;background:#fff">${fams.map(f => `<div style="height:150px;font:400 100px/150px ${f.replace(/"/g, "'")};color:#000;white-space:nowrap">gaR0</div>`).join('')}</body></html>`);
    const buf = await pg.screenshot();
    const inks = await pg.evaluate(async (b64) => { const img = new Image(); img.src = 'data:image/png;base64,' + b64; await img.decode();
      const c = document.createElement('canvas'); c.width = img.width; c.height = img.height; const x = c.getContext('2d'); x.drawImage(img, 0, 0);
      return [...Array(10).keys()].map(r => { const d = x.getImageData(0, r * 150, img.width, 150).data; let s = 0; for (let i = 0; i < d.length; i += 4) s += 255 - d[i]; return Math.round(s / 255); }); }, buf.toString('base64'));
    console.log(`${en} ${lang || 'no lang'}`); fams.forEach((f, i) => console.log(`  ${String(inks[i]).padStart(6)}  ${f}`));
  }
  await b.close();
}
