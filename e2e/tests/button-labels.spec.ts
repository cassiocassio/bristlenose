/**
 * No button label is ever truncated.
 *
 * Owner rule, 9 Nov 2026: a button that reads "Show Det…" is a defect, in any
 * language. Review never caught it, because a label fits in English and is cut
 * in German, and nobody reviews the German. So this walks every lens in English
 * and in the four locales whose strings run longest (de, fr, pl, ru: measured
 * across all locale files, ~10% over English on average and far more on single
 * labels), and fails on any visible button whose text overflows the box it is
 * drawn in.
 *
 * "Button" means anything a researcher clicks that carries a label: <button>,
 * role=button / tab / menuitem / switch, <summary>, and <a> styled as a button
 * (.bn-btn*). An icon-only control has no text to cut and is skipped.
 *
 * "Truncated" is measured, not inferred from CSS: the control or a descendant
 * that clips (overflow other than visible, or text-overflow: ellipsis) is
 * narrower than its content (scrollWidth > clientWidth). That catches an
 * ellipsis, a hard clip and a fixed width alike.
 *
 * Also opened: the Feedback and Settings dialogs, and the tag sidebar at the
 * narrow end of its drag. Still unseen: menus, popovers and any dialog not
 * opened here — covered by the review rule in .claude/agents/ux-critique.md;
 * add each new one to this walk.
 *
 * The one exemption: an element marked data-truncates="user-content" shows
 * the researcher's own words (a tag, file or speaker name), which may
 * ellipsize. Our own words never may. See docs/design-control-labels.md.
 */
import { test, expect, Page } from '@playwright/test';

test.describe.configure({ mode: 'serial' });

const LOCALES = ['en', 'de', 'fr', 'pl', 'ru'];

const LENSES = [
  '/report/',
  '/report/sessions/',
  '/report/quotes/',
  '/report/codebook/',
  '/report/signals/',
];

async function waitForPageReady(page: Page): Promise<void> {
  await page.waitForLoadState('networkidle');
  await page.waitForFunction(
    () => {
      const root = document.querySelector('#bn-app-root');
      return !!(root && root.children.length > 0);
    },
    { timeout: 5_000 },
  );
  await page.waitForFunction(
    () => {
      const current = document.querySelectorAll('*').length;
      const w = window as unknown as { __prevDomCount?: number };
      const prev = w.__prevDomCount;
      w.__prevDomCount = current;
      return prev !== undefined && prev === current;
    },
    { timeout: 5_000, polling: 200 },
  );
}

interface Cut {
  label: string;
  tag: string;
  cls: string;
  clipper: string;
  scroll: number;
  client: number;
}

/** Every visible labelled control whose text is cut, with where it is cut. */
async function truncatedControls(page: Page): Promise<Cut[]> {
  return page.evaluate(() => {
    const SELECTOR = [
      'button',
      '[role="button"]',
      '[role="tab"]',
      '[role="menuitem"]',
      '[role="switch"]',
      'summary',
      'a[class*="bn-btn"]',
    ].join(',');
    const clips = (el: Element): boolean => {
      const s = getComputedStyle(el);
      return s.overflowX !== 'visible' || s.textOverflow === 'ellipsis';
    };
    const visible = (el: Element): boolean => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
    };
    const out: Cut[] = [];
    for (const control of Array.from(document.querySelectorAll(SELECTOR))) {
      const label = (control.textContent ?? '').replace(/\s+/g, ' ').trim();
      if (!label || !visible(control)) continue;
      // Only the researcher's own words may truncate (a tag, file or speaker
      // name), and only where the element says so. Our own labels never.
      if (control.closest('[data-truncates="user-content"]')) continue;
      const candidates = [control, ...Array.from(control.querySelectorAll('*'))];
      for (const el of candidates) {
        if (!(el instanceof HTMLElement) || !visible(el) || !clips(el)) continue;
        if (!(el.textContent ?? '').trim()) continue;
        // One CSS pixel of slack: sub-pixel layout rounds scrollWidth up.
        if (el.scrollWidth > el.clientWidth + 1) {
          out.push({
            label: label.slice(0, 80),
            tag: control.tagName.toLowerCase(),
            cls: (control.getAttribute('class') ?? '').slice(0, 80),
            clipper: `${el.tagName.toLowerCase()}.${(el.getAttribute('class') ?? '').split(/\s+/)[0]}`,
            scroll: el.scrollWidth,
            client: el.clientWidth,
          });
          break;
        }
      }
      if (out.length && out[out.length - 1].label === label.slice(0, 80)) continue;
      // The whole control can be cut too: a row that will not wrap pushes it
      // past the box that clips it (an overflow other than visible) or past
      // the dialog card it belongs to. Only a PARTIAL horizontal cut counts —
      // a control scrolled wholly out of a list is not cut, it is elsewhere.
      let box: Element | null = control.parentElement;
      while (box && box !== document.body) {
        const s = getComputedStyle(box);
        if (s.overflowX !== 'visible' || box.matches('.bn-modal, [role="dialog"]')) break;
        box = box.parentElement;
      }
      if (!box || box === document.body) continue;
      const r = control.getBoundingClientRect();
      const b = box.getBoundingClientRect();
      const cutLeft = r.left < b.left - 1 && r.right > b.left;
      const cutRight = r.right > b.right + 1 && r.left < b.right;
      if (cutLeft || cutRight) {
        out.push({
          label: label.slice(0, 80),
          tag: control.tagName.toLowerCase(),
          cls: (control.getAttribute('class') ?? '').slice(0, 80),
          clipper: `${box.tagName.toLowerCase()}.${(box.getAttribute('class') ?? '').split(/\s+/)[0]} (edge)`,
          scroll: Math.round(r.width),
          client: Math.round(Math.min(r.right, b.right) - Math.max(r.left, b.left)),
        });
      }
    }
    return out;
  });
}

// The walk can fail: cut one real button the way a stylesheet would, and it
// must be reported. Without this a selector typo or a page that never mounted
// would pass every case below.
test('the walk reports a button that is cut', async ({ page }) => {
  await page.goto('/report/quotes/?locale=de');
  await waitForPageReady(page);
  expect(await truncatedControls(page)).toEqual([]);
  const marked = await page.evaluate(() => {
    const b = Array.from(document.querySelectorAll('button'))
      .find((el) => (el.textContent ?? '').trim().length > 6
        && el.getBoundingClientRect().width > 0
        && getComputedStyle(el).visibility !== 'hidden');
    if (!b) return false;
    Object.assign(b.style, {
      maxWidth: '24px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
    });
    return true;
  });
  expect(marked, 'no labelled button on Quotes to cut').toBe(true);
  expect((await truncatedControls(page)).length).toBeGreaterThanOrEqual(1);
});

test('the walk reports a control pushed past its box', async ({ page }) => {
  await page.goto('/report/quotes/?locale=de');
  await waitForPageReady(page);
  const marked = await page.evaluate(() => {
    const b = Array.from(document.querySelectorAll('button'))
      .find((el) => (el.textContent ?? '').trim().length > 6
        && el.getBoundingClientRect().width > 0
        && getComputedStyle(el).visibility !== 'hidden');
    if (!b || !b.parentElement) return false;
    // A clipping box half the button's width, with the button inside it.
    const box = document.createElement('div');
    Object.assign(box.style, {
      overflow: 'hidden', width: `${Math.floor(b.getBoundingClientRect().width / 2)}px`,
      display: 'flex', flexWrap: 'nowrap',
    });
    b.parentElement.insertBefore(box, b);
    box.appendChild(b);
    b.style.flexShrink = '0';
    return true;
  });
  expect(marked, 'no labelled button on Quotes to cut').toBe(true);
  expect((await truncatedControls(page)).some((c) => c.clipper.endsWith('(edge)'))).toBe(true);
});

// Dialogs are not on the page until they are opened, so the lens walk cannot
// see them. Feedback is reachable from every lens's footer: open it in each
// locale (it overflowed its card in Danish, German, Polish and Russian until
// 9 Nov 2026).
for (const locale of [...LOCALES, 'da']) {
  test(`no truncated button label — Feedback dialog in ${locale}`, async ({ page }) => {
    await page.goto(`/report/?locale=${locale}`);
    await waitForPageReady(page);
    // Fail, never skip, when the trigger is missing: a gate that skips on a
    // build with feedback off passes without having looked.
    const trigger = page.locator('.feedback-trigger');
    await expect(trigger.first(), 'no Feedback trigger in the footer').toBeVisible();
    await trigger.first().click();
    await expect(page.locator('.feedback-modal')).toBeVisible();
    const cuts = await truncatedControls(page);
    expect(
      cuts,
      cuts.map((c) => `"${c.label}" <${c.tag} class="${c.cls}"> cut by ${c.clipper} `
        + `(${c.scroll}px wide, ${c.client}px shown)`).join('\n'),
    ).toEqual([]);
  });
}

function describeCuts(cuts: Cut[]): string {
  return cuts.map((c) => `"${c.label}" <${c.tag} class="${c.cls}"> cut by ${c.clipper} `
    + `(${c.scroll} vs ${c.client}px)`).join('\n');
}

// Settings: its nav column held "Конфиденциальность" and Finnish
// "LLM-palveluntarjoaja" at the edge of a fixed 11rem until 9 Nov 2026.
for (const locale of [...LOCALES, 'fi']) {
  test(`no truncated button label — Settings dialog in ${locale}`, async ({ page }) => {
    await page.goto(`/report/?locale=${locale}`);
    await waitForPageReady(page);
    await page.keyboard.press('Control+Comma');
    await expect(page.locator('.modal-nav-sidebar')).toBeVisible();
    const cuts = await truncatedControls(page);
    expect(cuts, describeCuts(cuts)).toEqual([]);
  });
}

// The tag sidebar at the narrow end of its drag: its Select all / Clear / Used
// row was clipped by the sidebar's overflow-x: hidden at 200px in Russian,
// Catalan and Polish until 9 Nov 2026. Narrowed with the handle's own Home key
// (useDragResize: Home = minimum width), so this is the researcher's gesture.
for (const locale of ['en', 'ru', 'ca', 'pl']) {
  test(`no truncated button label — tag sidebar at its narrowest in ${locale}`, async ({ page }) => {
    await page.goto(`/report/quotes/?locale=${locale}`);
    await waitForPageReady(page);
    if (!(await page.locator('.tag-drag-handle').isVisible())) {
      await page.locator('.tag-rail .rail-btn').click();
    }
    const handle = page.locator('.tag-drag-handle');
    await expect(handle).toBeVisible();
    await handle.focus();
    await page.keyboard.press('Home');
    await expect.poll(async () => page.locator('.tag-sidebar-actions').evaluate(
      (el) => Math.round(el.closest('aside, [class*="sidebar"]')!.getBoundingClientRect().width),
    )).toBeLessThanOrEqual(210);
    const cuts = await truncatedControls(page);
    expect(cuts, describeCuts(cuts)).toEqual([]);
  });
}

for (const locale of LOCALES) {
  for (const lens of LENSES) {
    test(`no truncated button label — ${lens} in ${locale}`, async ({ page }) => {
      await page.goto(`${lens}?locale=${locale}`);
      await waitForPageReady(page);
      // The locale actually took: a walk that silently fell back to English
      // would pass every locale for the price of one.
      expect(await page.evaluate(() => document.documentElement.lang)).toContain(locale);
      const cuts = await truncatedControls(page);
      expect(
        cuts,
        cuts.map((c) => `"${c.label}" <${c.tag} class="${c.cls}"> cut by ${c.clipper} `
          + `(${c.scroll}px of text in ${c.client}px)`).join('\n'),
      ).toEqual([]);
    });
  }
}
