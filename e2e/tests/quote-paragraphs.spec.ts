/**
 * A quote's own paragraphs, in a real browser against a real server
 * (docs/design-quote-editing.md §12a): Shift-Return while editing starts a
 * paragraph, Return saves it, and it is still there after a reload. The unit
 * tests drive the caret in jsdom, which lays nothing out and places a caret
 * as no browser does; this is the one path WebKit (the Mac app's engine) has
 * to prove (review 21 Nov 2026, finding 25).
 *
 * It writes to the fixture's database, so it puts the quote back as it found
 * it, and it refuses to run against a server that is not the smoke fixture.
 */
import { test, expect, Page } from '@playwright/test';

test.describe.configure({ mode: 'serial' });

function authToken(): string {
  return process.env._BRISTLENOSE_AUTH_TOKEN ?? 'test-token';
}

async function waitForPageReady(page: Page): Promise<void> {
  await page.waitForLoadState('load');
  await page.waitForFunction(() => document.querySelectorAll('.quote-text').length > 0, undefined, {
    timeout: 10_000,
  });
}

test('Shift-Return starts a paragraph that survives a reload', async ({ page, baseURL }) => {
  const headers = { Authorization: `Bearer ${authToken()}` };
  const info = await page.request.get(`${baseURL}/api/projects/1/info`, { headers });
  expect(info.ok()).toBe(true);
  expect((await info.json()).project_name).toBe('Smoke Test');

  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));

  await page.goto('/report/quotes/');
  await waitForPageReady(page);

  // A quote drawn as one paragraph, long enough to split in the middle.
  const domId = await page
    .locator('blockquote.quote-card')
    .filter({ has: page.locator('.quote-text') })
    .filter({ hasNot: page.locator('.bn-block + .bn-block') })
    .first()
    .getAttribute('id');
  expect(domId).toBeTruthy();
  // Pinned by id: the filter above stops matching once the quote has two paragraphs.
  const card = page.locator(`blockquote[id="${domId}"]`);
  const text = card.locator('.quote-text');
  const before = await text.locator('.bn-block').count();

  try {
    await text.click(); // the middle of the quote's words
    await expect(card).toHaveClass(/editing/);
    await page.keyboard.press('Shift+Enter');
    await expect(text.locator('.bn-block')).toHaveCount(Math.max(before, 1) + 1);
    await page.keyboard.press('Enter');
    await expect(card).not.toHaveClass(/editing/);
    // Return leaves the researcher on the card (finding 8).
    expect(await page.evaluate(() => document.activeElement?.id)).toBe(domId);

    await expect
      .poll(async () => {
        const res = await page.request.get(`${baseURL}/api/projects/1/quotes`, { headers });
        const data = await res.json();
        const all = [...data.sections, ...data.themes].flatMap((g: { quotes: unknown[] }) => g.quotes);
        const q = all.find((x) => (x as { dom_id: string }).dom_id === domId) as
          | { researcher_breaks: number[] | null }
          | undefined;
        return q?.researcher_breaks?.length ?? 0;
      })
      .toBe(1);

    await page.reload();
    await waitForPageReady(page);
    const again = page.locator(`blockquote[id="${domId}"] .quote-text .bn-block`);
    await expect(again).toHaveCount(Math.max(before, 1) + 1);
    expect(errors).toEqual([]);
  } finally {
    const res = await page.request.patch(`${baseURL}/api/projects/1/quote-breaks`, {
      headers,
      data: { [domId!]: null },
    });
    expect(res.ok()).toBe(true);
  }
});
