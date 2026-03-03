/**
 * Layer 2: Link crawler.
 *
 * Walks every <a> on every page. Asserts all links with visible text
 * have an href, and internal links resolve (no 404).
 * Catches: Dead links, broken internal navigation, orphaned routes.
 */
import { test, expect } from '@playwright/test';
import { getAllRoutes } from '../fixtures/routes';

test('all links have href and internal links resolve', async ({
  page,
  baseURL,
}) => {
  const deadLinks: string[] = [];
  const brokenLinks: string[] = [];

  const routes = await getAllRoutes(baseURL!);

  for (const path of routes) {
    await page.goto(path);
    await page.waitForLoadState('networkidle');

    const links = await page.locator('a').all();

    for (const link of links) {
      const href = await link.getAttribute('href');
      const text = (await link.textContent())?.trim() ?? '';
      const role = await link.getAttribute('role');

      // Skip <a role="button"> — these are interactive elements (modals,
      // toggles) intentionally without href
      if (role === 'button') continue;

      // Links with visible text should have an href
      if (!href && text) {
        deadLinks.push(`${path}: "${text.slice(0, 60)}" has no href`);
        continue;
      }

      // Skip hash-only links, external links, and empty hrefs
      if (!href || href.startsWith('#') || href.startsWith('//')) continue;
      if (href.startsWith('http://') || href.startsWith('https://')) continue;
      if (href.startsWith('javascript:')) continue;

      // Internal links should resolve (no 404)
      if (href.startsWith('/')) {
        const res = await page.request.get(`${baseURL}${href}`);
        if (res.status() >= 400) {
          brokenLinks.push(
            `${path}: "${text.slice(0, 40)}" -> ${href} (${res.status()})`,
          );
        }
      }
    }
  }

  expect(deadLinks).toEqual([]);
  expect(brokenLinks).toEqual([]);
});

// Known bug: 12 "Show all N quotes" links on Analysis page have no
// href and no click handler. Only reproducible with analysis data
// (project-ikea fixture).
test.fixme(
  'KNOWN BUG: dead "Show all N quotes" links on Analysis page',
  async () => {
    // Promote when analysis page fixture data produces signal cards
    // with "Show all" links.
  },
);
