/**
 * Every lens is enrolled in the flush-to-datum system.
 *
 * The contract is one rule in bristlenose/theme/templates/report.css:
 *
 *   .center > main > section:first-of-type > .section-heading,
 *   .analysis-center > .section-heading:first-of-type { margin-top: 0 }
 *
 * A lens enrols by rendering its zone title as the direct child of a <section>
 * that is the direct child of <main> (Analysis uses the scroll-pane variant).
 * Nothing needs inventing per lens — SessionsTable.tsx states the contract in a
 * source comment, and Quotes has always followed it.
 *
 * Codebook did not. It rendered a bare fragment, so the selector never matched,
 * `.section-heading`'s own 2.5rem stood, and the lens opened 40px below the
 * others for the entire life of the rule. Nothing caught it: no unit test can
 * see a CSS selector failing to match, and every other E2E spec asserts a lens
 * *mounts*, not *where* it starts.
 *
 * WHY margin-top AND NOT "all four tops are equal": the lenses legitimately
 * differ in what sits above the title — Quotes carries a web toolbar in browser
 * mode (native chrome in the app), Analysis an intro paragraph inside a padded
 * scroll pane. Asserting equal tops would encode that incidental chrome and go
 * red on a legitimate change. `margin-top: 0` is the contract itself, is
 * surface-independent, and catches both ways a lens falls out of the system:
 *
 *   - not enrolled at all (a fragment, no <section>)      -> 40px
 *   - enrolled but the title re-wrapped in a per-lens box -> 40px
 *
 * Those are the same defect, and they are the two that shipped: the second one
 * also truncated Codebook's keyline to the width of the column it was wrapped
 * in, which is why one assertion covers both.
 */
import { test, expect, Page } from '@playwright/test';

test.describe.configure({ mode: 'serial' });

/** Every lens that carries a zone title. Project is a dashboard — no h1 by design.
 *
 * `codebook-v2` joined 31 Aug 2026, and joining is the point: it had shipped
 * with its content in a wrapper `<div>`, which made its `<section>` a
 * GRANDCHILD of `<main>` and so unreachable by the datum selector. The heading
 * kept its default top margin and the lens sat visibly lower than the other
 * four — caught by eye, in a screenshot, because nothing enumerated it here.
 * A gate that lists its subjects by hand only covers the ones somebody
 * remembered; adding a lens means adding a row. */
const TITLED_LENSES = [
  { name: 'sessions', route: '/report/sessions/' },
  { name: 'quotes', route: '/report/quotes/' },
  { name: 'codebook', route: '/report/codebook/' },
  { name: 'codebook-v2', route: '/report/codebook-v2/' },
  { name: 'analysis', route: '/report/analysis/' },
];

function authToken(): string {
  return process.env._BRISTLENOSE_AUTH_TOKEN ?? 'test-token';
}

async function waitForZoneTitle(page: Page): Promise<void> {
  await page.waitForLoadState('networkidle');
  await page.waitForFunction(
    () => !!document.querySelector('#bn-app-root')?.children.length,
    { timeout: 8_000 },
  );
  // The islands are lazy — without this the probe reads an empty pane and a
  // missing heading looks like a passing "nothing to check".
  await page.waitForSelector('.section-heading', { timeout: 8_000 });
}

// A stale `bristlenose serve` on :8150 is reused outside CI (reuseExistingServer),
// so without this the file could measure a different project and report a
// confident green. Same guard lenses-load-clean.spec.ts carries.
test('server identity guard — smoke-test fixture', async ({ page, baseURL }) => {
  const res = await page.request.get(`${baseURL}/api/projects/1/info`, {
    headers: { Authorization: `Bearer ${authToken()}` },
  });
  expect(res.ok()).toBe(true);
  expect((await res.json()).project_name).toBe('Smoke Test');
});

for (const lens of TITLED_LENSES) {
  test(`${lens.name}: first zone title flushes to the datum`, async ({ page }) => {
    await page.goto(lens.route);
    await waitForZoneTitle(page);

    const probe = await page.evaluate(() => {
      const h = document.querySelector('.section-heading') as HTMLElement | null;
      if (!h) return null;
      return {
        marginTop: getComputedStyle(h).marginTop,
        // Reported on failure so the diagnosis is in the message rather than a
        // debugging session: which selector was meant to reach this heading.
        enrolledViaMain: h.matches('.center > main > section:first-of-type > .section-heading'),
        enrolledViaPane: h.matches('.analysis-center > .section-heading:first-of-type'),
        parent: `${h.parentElement?.tagName.toLowerCase()}.${String(h.parentElement?.className ?? '').split(' ')[0]}`,
      };
    });

    expect(probe, `${lens.name} renders no .section-heading`).not.toBeNull();
    expect(
      probe!.marginTop,
      `${lens.name} is not enrolled in the datum system: parent=${probe!.parent} ` +
        `mainSelector=${probe!.enrolledViaMain} paneSelector=${probe!.enrolledViaPane}`,
    ).toBe('0px');
  });
}
