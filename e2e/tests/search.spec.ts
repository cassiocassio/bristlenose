/**
 * Quotes search in a real browser against a real server (docs/design-search.md
 * §3–§6): a phrase filters and is offered in the suggestions list, a typed
 * speaker code becomes a chip, and Esc empties the field. The unit tests drive
 * SearchBox in jsdom; this proves the same flow through the served SPA, its
 * CSS and its store.
 */
import { test, expect, Page } from '@playwright/test';

test.describe.configure({ mode: 'serial' });

function authToken(): string {
  return process.env._BRISTLENOSE_AUTH_TOKEN ?? 'test-token';
}

async function waitForPageReady(page: Page): Promise<void> {
  await page.waitForLoadState('networkidle');
  await page.waitForFunction(
    () => {
      const root = document.querySelector('#bn-app-root');
      return !!(root && root.children.length > 0);
    },
    { timeout: 5_000 },
  );
}

test('server identity guard — smoke-test fixture', async ({ page, baseURL }) => {
  const res = await page.request.get(`${baseURL}/api/projects/1/info`, {
    headers: { Authorization: `Bearer ${authToken()}` },
  });
  expect(res.ok()).toBe(true);
  expect((await res.json()).project_name).toBe('Smoke Test');
});

test('a phrase is offered, filters, and a typed code becomes a chip', async ({ page }) => {
  await page.goto('/report/quotes/');
  await waitForPageReady(page);
  const quotes = page.locator('.quote-text');
  const total = await quotes.count();
  expect(total).toBeGreaterThan(1);

  await page.getByRole('button', { name: 'Search quotes' }).click();
  const field = page.getByRole('combobox');
  await field.fill('navigation was');

  // The list under the field offers the free text, with its count.
  const list = page.getByRole('listbox');
  await expect(list).toBeVisible();
  // Past the 150 ms debounce the store echoes the query back; that echo must
  // not close the list the typing opened (a bug the unit tests first missed).
  await page.waitForTimeout(400);
  await expect(list).toBeVisible();
  const first = list.getByRole('option').first();
  await expect(first).toContainText('navigation was');
  await expect(first).toContainText('1');

  // ↩ commits it: only the quote that says those words, in that order.
  await field.press('Enter');
  await expect(list).toBeHidden();
  await expect(quotes).toHaveCount(1);
  await expect(quotes.first()).toContainText('navigation was');

  // Words out of order are not what anybody said.
  await field.fill('was navigation');
  await expect(quotes).toHaveCount(0);

  // A speaker code and a space become a "said by" chip, and leave the text.
  await field.fill('p1 ');
  const chip = page.locator('.search-token');
  await expect(chip).toHaveCount(1);
  await expect(chip).toContainText('said by');
  await expect(field).toHaveValue('');
  await expect(quotes).toHaveCount(total); // every quote in the fixture is p1's

  // Esc empties the field, the chip included.
  await field.press('Escape');
  await expect(chip).toHaveCount(0);
});
