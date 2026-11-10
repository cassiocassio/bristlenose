// Three perceived-wait moments from the perf ledger (docs/design-perf-ledger.md, "Reviewed targets" rows 1 and 2, and
// the 0.1 s tier of "Click-to-visible: the budget"). Run through interaction-profile.mjs:
//   node interaction-profile.mjs --cases=lens-content,search,direct [--browser=webkit]
//
//   lens-content  click a lens tab; the step ENDS at a double rAF after that lens's own content selector
//                 appears. No sleep inside the timed region. Pass 1 on a fresh page is first visit (lazy chunk +
//                 read); later passes on the same page are revisits (read only). Each step is split from the
//                 browser's resource timing into chunk / mount / fetch / render along the critical path.
//   search        type a 6-letter word into the toolbar field (the BROWSER field, SearchBox.tsx; the Mac app's
//                 field is native and is not measured here). Field echo per character, and last keystroke to
//                 results settled MINUS the 150 ms debounce, at three typing speeds.
//   direct        star / unstar a card and toggle both sidebars; each step ENDS at a double rAF after the new
//                 state is on the DOM. Against the 0.1 s direct-manipulation budget.
//
// Serve with the PROD bundle and your own port (see serve-fixture.py), never `--dev`: unbundled Vite modules make
// the chunk cost a dev artefact.
import { pw, BASE, INIT, measure, saveResult } from './lib.mjs';

const VIEWPORT = { width: 1500, height: 900 };
const DEBOUNCE_MS = 150; // SearchBox.tsx default

const pct = (arr, p) => {
  if (!arr.length) return null;
  const s = [...arr].sort((x, y) => x - y);
  return s[Math.min(s.length - 1, Math.max(0, Math.ceil(p * s.length) - 1))];
};
const summ = (arr) => ({ n: arr.length, p50: pct(arr, 0.5), p90: pct(arr, 0.9), max: pct(arr, 1), min: pct(arr, 0) });
const f1 = (x) => (x == null ? '   -' : x.toFixed(1).padStart(6));

async function freshPage(browser, url, { warm = false } = {}) {
  const context = await browser.newContext({ viewport: VIEWPORT });
  if (warm) { // a throwaway load first, so the HTTP cache is warm for the measured page
    const w = await context.newPage();
    await w.goto(url, { waitUntil: 'networkidle' }).catch(() => {});
    await w.close();
  }
  const page = await context.newPage();
  await page.addInitScript(INIT);
  await page.addInitScript(() => { try { performance.setResourceTimingBufferSize(10000); } catch {} });
  const resp = await page.goto(url, { waitUntil: 'domcontentloaded' });
  if (!resp || !resp.ok()) throw new Error(`HTTP ${resp && resp.status()} for ${url}`);
  await page.waitForSelector('a.bn-tab, button.bn-tab', { timeout: 20000 });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(1500);
  return { context, page };
}

// ───────────────────────────── moment 1: click a lens ─────────────────────────────

// Order: the landing lens is last (it is already loaded, so its pass-1 step is not a first visit).
const LENSES = [
  { name: 'Project', tab: 'Project', sel: '.bn-dashboard-pane', read: /\/dashboard$/ },
  { name: 'Sessions', tab: 'Sessions', sel: '.bn-sessions-row', read: /\/sessions$/ },
  { name: 'Transcript', link: '.bn-sessions-row[data-session] .bn-session-duration', sel: '.transcript-segment', read: /\/transcripts\// },
  { name: 'Quotes', tab: 'Quotes', sel: '.quote-card', read: /\/quotes$/ },
  { name: 'Codebooks', tab: 'Codebooks', sel: '.codebook-group', read: /\/codebook$/ },
  { name: 'Signals', tab: 'Signals', sel: '.signal-card', read: /\/signals/ },
  { name: 'Discussion', tab: 'Discussion', sel: '.bn-empty-state, [class*="discussion-"]', landing: true },
];

// Runs in the page. Clicks in-page (no Playwright actionability wait inside the timed region).
const STEP = async ({ tab, link, sel }) => {
  const nav = (txt) => [...document.querySelectorAll('.bn-global-nav > .bn-tab')].find((e) => e.textContent.trim() === txt);
  const target = tab ? nav(tab) : document.querySelector(link);
  if (!target) return { error: 'no click target' };
  if (tab && target.getAttribute('aria-disabled')) return { unavailable: true };
  const pre = document.querySelectorAll(sel).length;
  const res = await new Promise((resolve) => {
    const t0 = performance.now();
    let tContent = null;
    const done = () => {
      requestAnimationFrame(() => requestAnimationFrame(() => {
        const tPaint = performance.now();
        // After the timed region: keep watching the card count (a lens may draw in batches) until it is quiet for 300 ms.
        let n = document.querySelectorAll(sel).length, nPaint = n, tLast = tPaint;
        const mo2 = new MutationObserver(() => {
          const m = document.querySelectorAll(sel).length;
          if (m !== n) { n = m; tLast = performance.now(); }
        });
        mo2.observe(document.body, { childList: true, subtree: true });
        const quiet = () => (performance.now() - tLast > 300 || performance.now() - tPaint > 4000)
          ? (mo2.disconnect(), resolve({ t0, tContent, tPaint, nPaint, nFinal: n, tFull: tLast }))
          : setTimeout(quiet, 50);
        setTimeout(quiet, 350);
      }));
    };
    const mo = new MutationObserver(() => {
      if (tContent == null && document.querySelector(sel)) { tContent = performance.now(); mo.disconnect(); done(); }
    });
    mo.observe(document.body, { childList: true, subtree: true });
    target.click();
    if (document.querySelector(sel)) { tContent = performance.now(); mo.disconnect(); done(); } // synchronous arrival
    setTimeout(() => { if (tContent == null) { mo.disconnect(); resolve({ t0, tContent: null, tPaint: null, timeout: true }); } }, 15000);
  });
  if (res.timeout) return { error: 'content never appeared', pre };
  const { t0, tContent, tPaint, nPaint, nFinal, tFull } = res;
  const poll = /\/(condition|last-run)$|\/autocode\/|\/export\/\w+\/status|\/tapestry|\/health/;
  const rs = performance.getEntriesByType('resource')
    .filter((e) => e.startTime >= t0 - 1)
    .map((e) => {
      const u = new URL(e.name);
      const kind = /\.css$/.test(u.pathname) ? 'css' : /\.js$/.test(u.pathname) ? 'js' : u.pathname.startsWith('/api/') ? 'api' : 'other';
      return { url: u.pathname.replace(/^.*\/assets\//, 'assets/'), kind, s: e.startTime - t0, e: e.responseEnd - t0,
        size: e.transferSize, cached: e.transferSize === 0 && e.decodedBodySize > 0, poll: kind === 'api' && poll.test(u.pathname),
        ttfb: e.responseStart ? e.responseStart - e.requestStart : null,
        srv: (e.serverTiming || []).find((x) => x.name === 'bn')?.duration ?? null, db: (e.serverTiming || []).find((x) => x.name === 'db')?.duration ?? null };
    });
  return { pre, toContent: tContent - t0, toPaint: tPaint - t0, toFull: tFull - t0, nPaint, nFinal, resources: rs };
};

function split(step, readRe) {
  // Critical path, in order: the lens chunk(s) -> mount until the read starts -> the read -> render and paint.
  const total = step.toPaint, content = step.toContent;
  const used = step.resources.filter((r) => !r.poll && r.e <= content + 1);
  const js = used.filter((r) => r.kind === 'js' || r.kind === 'css');
  // The lens's own read (primary endpoint) decides when the fetch starts and ends; the other calls ride along.
  const own = used.filter((r) => r.kind === 'api' && readRe && readRe.test(r.url));
  const api = own.length ? own : used.filter((r) => r.kind === 'api');
  const chunkEnd = Math.min(content, Math.max(0, ...js.map((r) => r.e)));
  const apiStart = api.length ? Math.min(content, Math.max(chunkEnd, Math.min(...api.map((r) => r.s)))) : chunkEnd;
  const apiEnd = api.length ? Math.min(content, Math.max(apiStart, ...api.map((r) => r.e))) : apiStart;
  const lastApi = [...api].sort((x, y) => y.e - x.e)[0];
  return { total, content, chunk: chunkEnd, mount: apiStart - chunkEnd, fetch: apiEnd - apiStart, render: total - apiEnd,
    jsN: js.length, jsBytes: js.reduce((x, r) => x + (r.size || 0), 0), apiN: api.length, apiBytes: api.reduce((x, r) => x + (r.size || 0), 0),
    lastApiSrv: lastApi?.srv ?? null, lastApiTtfb: lastApi?.ttfb ?? null, lastApiUrl: lastApi?.url ?? null };
}

export async function lensContent(a, browserName) {
  const reps = +(a.reps ?? 5), revisits = +(a.revisits ?? 6), settle = +(a.settle ?? 350);
  const warm = a.cache === 'warm';
  const browser = await pw[browserName].launch();
  const rows = []; // one per step
  for (let rep = 0; rep < reps; rep++) {
    const { context, page } = await freshPage(browser, `${BASE}/report/discussion/`, { warm });
    for (let pass = 1; pass <= 1 + revisits; pass++) {
      for (const L of LENSES) {
                const s = await page.evaluate(STEP, { tab: L.tab, link: L.link, sel: L.sel });
        const row = { rep, pass, lens: L.name, first: pass === 1 && !L.landing, ...s };
        if (s.toPaint != null) Object.assign(row, { split: split(s, L.read) });
        if (s.pre) row.preNonZero = true;
        rows.push(row);
        await page.waitForTimeout(settle); // outside the timed region
      }
    }
    await context.close();
  }
  await browser.close();
  return rows;
}

export function lensTable(rows, label) {
  const lines = [`lens-content ${label}`,
    'lens        | first visit: n  p50  p90  max | chunk mount fetch render (medians) | full | revisit: n  p50  p90  max | chunk mount fetch render | full'];
  const med = (xs) => pct(xs, 0.5);
  for (const L of LENSES) {
    const mine = rows.filter((r) => r.lens === L.name);
    if (mine.every((r) => r.unavailable)) { lines.push(`${L.name.padEnd(11)} | unavailable on this project (tab disabled)`); continue; }
    const ok = mine.filter((r) => r.split);
    const fv = ok.filter((r) => r.first), rv = ok.filter((r) => r.pass > 1);
    const cell = (xs) => {
      if (!xs.length) return '  n/a';
      const t = summ(xs.map((r) => r.split.total));
      const m = (k) => f1(med(xs.map((r) => r.split[k])));
      return `${String(t.n).padStart(2)} ${f1(t.p50)} ${f1(t.p90)} ${f1(t.max)} |${m('chunk')}${m('mount')}${m('fetch')}${m('render')} |${f1(med(xs.map((r) => r.toFull)))}`;
    };
    lines.push(`${L.name.padEnd(11)} | ${L.landing ? '(landing lens, not a first visit)'.padEnd(80) : cell(fv)} | ${cell(rv)}`);
  }
  return lines.join('\n');
}

// ───────────────────────────── moment 2: type in search ─────────────────────────────

// Runs in the page: choose a 6-letter word whose last character changes the result set (so there is a settle to time).
const PICK_WORDS = () => {
  // Candidate 6-letter words, most common first. Which of them changes the result set on the LAST character depends on
  // the matcher (it folds plurals, for one), so the caller probes them rather than guessing.
  const texts = [...document.querySelectorAll('.quote-text')].map((e) => e.textContent.toLowerCase());
  const df = new Map();
  texts.forEach((x) => new Set(x.match(/[a-z]{6}/g) || []).forEach((w) => df.set(w, (df.get(w) || 0) + 1)));
  return { quotes: texts.length, words: [...df.entries()].filter(([, n]) => n >= 8 && n <= texts.length * 0.5)
    .sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1)).slice(0, 12).map(([w, n]) => ({ w, n })) };
};

// Installs the recorder. Echo: keydown -> second rAF after the field's input event. Settle: the last change of the
// .quote-card count after a key, to the second rAF after it.
const RECORDER = () => {
  const S = (window.__search = { keys: [], changes: [] });
  let lastN = document.querySelectorAll('.quote-card').length;
  S.n0 = lastN;
  document.addEventListener('keydown', (e) => { if (e.key.length === 1) S.keys.push({ t: e.timeStamp, key: e.key, echo: null, frame1: null }); }, true);
  document.addEventListener('input', () => {
    const k = S.keys[S.keys.length - 1];
    requestAnimationFrame(() => {
      const f1 = performance.now();
      requestAnimationFrame(() => { if (k && k.echo == null) { k.frame1 = f1 - k.t; k.echo = performance.now() - k.t; } });
    });
  }, true);
  new MutationObserver(() => {
    const n = document.querySelectorAll('.quote-card').length;
    if (n === lastN) return;
    lastN = n;
    const c = { at: performance.now(), n, painted: null };
    S.changes.push(c);
    requestAnimationFrame(() => requestAnimationFrame(() => { c.painted = performance.now(); }));
  }).observe(document.body, { childList: true, subtree: true });
};

const TYPING = [
  { mode: 'slow', gap: 700, note: 'each character settles alone: clean echo and per-character results' },
  { mode: 'typical', gap: 170, note: 'gap just over the 150 ms debounce: the previous character\'s filter lands before the next key' },
  { mode: 'burst', gap: 60, note: 'faster than the debounce: one filter after the last key' },
];

export async function search(a, browserName) {
  const reps = +(a.reps ?? 8);
  const browser = await pw[browserName].launch();
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  await page.addInitScript(INIT);
  const resp = await page.goto(`${BASE}/report/quotes/`, { waitUntil: 'domcontentloaded' });
  if (!resp || !resp.ok()) throw new Error(`HTTP ${resp && resp.status()}`);
  await page.waitForSelector('.quote-card', { timeout: 20000 });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(1500);
  const cands = await page.evaluate(PICK_WORDS);
  await page.click('.search-toggle');
  await page.waitForFunction(() => document.activeElement && document.activeElement.classList.contains('search-input'));
  const clear = async () => {
    // Escape closes the suggestions list first, then clears the field (handleClear); a third would collapse the field.
    for (let i = 0; i < 3; i++) {
      if (!(await page.evaluate(() => document.querySelector('input.search-input')?.value))) break;
      await page.keyboard.press('Escape');
      await page.waitForTimeout(120);
    }
    await page.waitForTimeout(900);
    await page.evaluate(() => { document.querySelector('input.search-input')?.focus(); });
  };
  // Probe: type each candidate slowly, read the card count after every character, keep the first word whose sixth
  // character still changes the result set.
  let pick = null;
  for (const { w } of cands.words) {
    const counts = [];
    for (const ch of w) { await page.keyboard.press(ch); await page.waitForTimeout(450); counts.push(await page.evaluate(() => document.querySelectorAll('.quote-card').length)); }
    await clear();
    if (counts[5] !== counts[4] && counts[5] > 0) { pick = { word: w, counts, quotes: cands.quotes }; break; }
  }
  if (!pick) pick = { word: cands.words[0].w, weak: true, quotes: cands.quotes };
  const word = pick.word;
  await page.evaluate(RECORDER);
  const ctx = { browserName, browser, context, page };
  const out = { word, pick, modes: [] };
  for (const T of TYPING) {
    const trials = [];
    const work = async () => {
      for (let r = 0; r < reps; r++) {
        await page.evaluate(() => { window.__search.keys.length = 0; window.__search.changes.length = 0; });
        for (const ch of word) { await page.keyboard.press(ch); await page.waitForTimeout(T.gap); }
        await page.waitForTimeout(900); // let the last debounce + render land
        trials.push(await page.evaluate(() => ({ keys: window.__search.keys.map((k) => ({ ...k })), changes: window.__search.changes.map((c) => ({ ...c })) })));
        await clear();
      }
      return trials.flatMap((t) => t.keys.map((k) => k.echo ?? 0));
    };
    const m = await measure(ctx, page, `search-${T.mode}`, work);
    // Derive: echo per character position; results after each key that is the last key before a change.
    const echo = trials.flatMap((t) => t.keys.map((k) => k.echo)).filter((x) => x != null);
    const echoByPos = word.split('').map((_, i) => trials.map((t) => t.keys[i]?.echo).filter((x) => x != null));
    const afterLast = [], afterAny = [], noChange = [];
    for (const t of trials) {
      const last = t.keys[t.keys.length - 1];
      const ch = t.changes.filter((c) => c.at >= last.t + DEBOUNCE_MS - 5 && c.painted != null); // a commit cannot precede the debounce
      if (ch.length) afterLast.push(ch[ch.length - 1].painted - last.t - DEBOUNCE_MS); else noChange.push(1);
      t.keys.forEach((k, i) => {
        if (i === 0) return;
        const next = t.keys[i + 1]?.t ?? Infinity;
        const c2 = t.changes.filter((c) => c.at >= k.t + DEBOUNCE_MS - 5 && c.at < next && c.painted != null);
        if (c2.length) afterAny.push(c2[c2.length - 1].painted - k.t - DEBOUNCE_MS);
      });
    }
    out.modes.push({ raw: trials, mode: T.mode, gap: T.gap, note: T.note, reps, echo: summ(echo), echoByPos: echoByPos.map(summ),
      resultsAfterLastKey: summ(afterLast), resultsPerCharSlowOnly: T.mode === 'slow' ? summ(afterAny) : undefined,
      noChangeTrials: noChange.length, cdp: m.cdp, loaf: m.page, wallMs: m.wallMs,
      cdpPerTrial: m.cdp && Object.fromEntries(Object.entries(m.cdp).map(([k, v]) => [k, v / reps])) });
  }
  await browser.close();
  return out;
}

export function searchTable(r, label) {
  const lines = [`search ${label}  word="${r.word}" (${JSON.stringify(r.pick)})`,
    'mode    gap |  echo p50  p90  max (n) | results-after-last-key (debounce excluded) p50 p90 max (n, nochange) | CDP per trial: script layout style task ms'];
  for (const m of r.modes) {
    const c = m.cdpPerTrial;
    lines.push(`${m.mode.padEnd(8)}${String(m.gap).padStart(3)} | ${f1(m.echo.p50)}${f1(m.echo.p90)}${f1(m.echo.max)} (${m.echo.n}) | ${f1(m.resultsAfterLastKey.p50)}${f1(m.resultsAfterLastKey.p90)}${f1(m.resultsAfterLastKey.max)} (${m.resultsAfterLastKey.n}, ${m.noChangeTrials}) | ` +
      (c ? `${c.ScriptMs.toFixed(0)} ${c.LayoutMs.toFixed(0)} ${c.RecalcStyleMs.toFixed(0)} ${c.TaskMs.toFixed(0)}` : 'n/a (no CDP)'));
    if (m.resultsPerCharSlowOnly) lines.push(`        per-character results (slow, chars 2..6): p50 ${f1(m.resultsPerCharSlowOnly.p50)} p90 ${f1(m.resultsPerCharSlowOnly.p90)} max ${f1(m.resultsPerCharSlowOnly.max)} (n=${m.resultsPerCharSlowOnly.n})`);
    lines.push(`        echo by character position p50: ${m.echoByPos.map((s) => f1(s.p50).trim()).join(' ')}`);
  }
  return lines.join('\n');
}

// ───────────────────────────── moment 3: direct manipulation (the 0.1 s tier) ─────────────────────────────

// Each action flips one state; the step ends at the second rAF after the DOM shows the new state (the same end as
// STEP). Star and unstar the first quote card (a click on `.star-btn`); open and close the tag sidebar (`]`) and the
// contents sidebar (`[`), the keys the report binds on Quotes. A sidebar step ends when `.layout` carries the new
// open class; `toSettled` is when its 75 ms width slide ended (`transitionend` on `.layout`), after the step, or null
// if no slide ran (reduced motion, overlay mode; before 10 Nov 2026 it never ran: docs/design-perf-ledger.md).
// Hide and tag are not timed here: a hide leaves the card (the next rep has a different first card) and a tag needs
// the TagInput flow; both are recorded as not covered in docs/design-perf-ledger.md.
const DIRECT = [
  { name: 'star', state: 'starred', want: true, click: '.quote-card .star-btn' },
  { name: 'unstar', state: 'starred', want: false, click: '.quote-card .star-btn' },
  { name: 'tags-open', state: 'tags', want: true, key: ']' },
  { name: 'tags-close', state: 'tags', want: false, key: ']' },
  { name: 'toc-open', state: 'toc', want: true, key: '[' },
  { name: 'toc-close', state: 'toc', want: false, key: '[' },
];

// Runs in the page. The event is dispatched in-page, as STEP clicks in-page, so no Playwright wait sits inside the
// timed region. A key is a synthetic keydown on document, which is where useKeyboardShortcuts listens.
const FLIP = async ({ state, want, click, key }) => {
  const layout = () => document.querySelector('.layout');
  const read = {
    starred: () => document.querySelector('.quote-card')?.classList.contains('starred') ?? null,
    tags: () => layout()?.classList.contains('tags-open') ?? null,
    toc: () => { const l = layout(); return l ? l.classList.contains('toc-open') || l.classList.contains('toc-overlay') : null; },
  }[state];
  const before = read();
  if (before == null) return { error: `no element for ${state}` };
  if (before === want) return { error: `${state} already ${want} before the step` };
  const target = click ? document.querySelector(click) : document;
  if (!target) return { error: `no click target ${click}` };
  return new Promise((resolve) => {
    const t0 = performance.now();
    let tState = null, tSettled = null;
    const L = key ? layout() : null;
    const onEnd = (e) => { if (e.target === L && tSettled == null) tSettled = performance.now(); };
    L?.addEventListener('transitionend', onEnd);
    const hit = () => {
      tState = performance.now();
      mo.disconnect();
      requestAnimationFrame(() => requestAnimationFrame(() => {
        const out = { toState: tState - t0, toPaint: performance.now() - t0 };
        if (!L) return resolve(out);
        // Outside the timed region: wait up to 500 ms for the slide to end.
        const wait = () => (tSettled != null || performance.now() - t0 > 500)
          ? (L.removeEventListener('transitionend', onEnd), resolve({ ...out, toSettled: tSettled == null ? null : tSettled - t0 }))
          : setTimeout(wait, 10);
        wait();
      }));
    };
    const mo = new MutationObserver(() => { if (tState == null && read() === want) hit(); });
    mo.observe(document.body, { attributes: true, attributeFilter: ['class'], subtree: true });
    if (click) target.click();
    else document.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }));
    if (tState == null && read() === want) hit(); // the state was written in the same task
    setTimeout(() => { if (tState == null) { mo.disconnect(); resolve({ error: `${state} never became ${want}` }); } }, 15000);
  });
};

export async function direct(a, browserName) {
  const reps = +(a.reps ?? 10), settle = +(a.settle ?? 400);
  const browser = await pw[browserName].launch();
  // --reduced-motion turns the sidebar slide off (theme/organisms/sidebar.css), to A/B what the slide costs.
  const context = await browser.newContext({ viewport: VIEWPORT, reducedMotion: a['reduced-motion'] ? 'reduce' : 'no-preference' });
  const page = await context.newPage();
  await page.addInitScript(INIT);
  const resp = await page.goto(`${BASE}/report/quotes/`, { waitUntil: 'domcontentloaded' });
  if (!resp || !resp.ok()) throw new Error(`HTTP ${resp && resp.status()}`);
  await page.waitForSelector('.quote-card', { timeout: 20000 });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(1500);
  const quotes = await page.evaluate(() => document.querySelectorAll('.quote-card').length);
  // A sidebar that starts open would make the "open" step fail its precondition: close it first, outside timing.
  for (const [k, cls] of [[']', 'tags-open'], ['[', 'toc-open']]) {
    if (await page.evaluate((c) => document.querySelector('.layout')?.classList.contains(c), cls)) {
      await page.keyboard.press(k); await page.waitForTimeout(settle);
    }
  }
  // A first card that starts starred (a real study's copy) would fail the "star" step: run the pair the other way.
  const startsStarred = await page.evaluate(() => document.querySelector('.quote-card')?.classList.contains('starred'));
  const order = startsStarred ? [DIRECT[1], DIRECT[0], ...DIRECT.slice(2)] : DIRECT;
  const rows = [];
  for (let rep = 0; rep < reps; rep++) {
    for (const D of order) {
      const s = await page.evaluate(FLIP, { state: D.state, want: D.want, click: D.click ?? null, key: D.key ?? null });
      rows.push({ rep, action: D.name, ...s });
      await page.waitForTimeout(settle); // outside the timed region: the write and the next frame
    }
  }
  await browser.close();
  return { quotes, startsStarred, reps, reducedMotion: !!a['reduced-motion'], rows };
}

export function directTable(r, label, budget = 100) {
  const lines = [`direct ${label}  quotes=${r.quotes}${r.reducedMotion ? ' reduced-motion' : ''}${r.startsStarred ? ' (first card started starred: unstar ran first)' : ''}`,
    `action      | to state p50 | to paint: n  p50  p90  max | over ${budget} ms | slide settled p50 (n)`];
  for (const D of DIRECT) {
    const ok = r.rows.filter((x) => x.action === D.name && x.toPaint != null);
    const t = summ(ok.map((x) => x.toPaint));
    const over = ok.filter((x) => x.toPaint > budget).length;
    const st = ok.map((x) => x.toSettled).filter((x) => x != null);
    lines.push(`${D.name.padEnd(11)} | ${f1(pct(ok.map((x) => x.toState), 0.5))}       | ${String(t.n).padStart(2)} ${f1(t.p50)} ${f1(t.p90)} ${f1(t.max)} | ${String(over).padStart(4)}        | ${D.key ? `${f1(pct(st, 0.5))} (${st.length})` : '     -'}`);
  }
  return lines.join('\n');
}

export { saveResult };
