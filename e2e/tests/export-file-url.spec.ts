/**
 * The self-contained HTML export as a leave-behind artifact, opened from file://.
 *
 * A stakeholder double-clicks the exported .html on a corporate (often Windows)
 * laptop — no Bristlenose, no server, opaque file:// origin. This asserts:
 *
 *  1. The export endpoint returns a self-contained artifact with the path-keyed
 *     data embed inlined (the anti-drift contract's client half).
 *  2. That artifact RENDERS from file:// — every tab mounts with zero console
 *     errors / unhandled rejections. The SPA ships as one inline module (see
 *     frontend/vite.export.config.ts + _build_export_html); the fail-loud apiGet
 *     turns any uncovered offline read into a thrown error that surfaces here.
 *
 * Runs on Chromium + WebKit (Edge/Chrome are Chromium; WebKit covers Safari).
 *
 * NOTE: requires the single-file export build (bristlenose/server/static-export/)
 * to exist — the serve fixture's export endpoint reads it.
 */

import { test, expect, type Page } from "@playwright/test";
import { mkdtempSync, writeFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { pathToFileURL } from "url";

const AUTH_TOKEN = process.env._BRISTLENOSE_AUTH_TOKEN;

function authHeaders(): Record<string, string> {
  return AUTH_TOKEN ? { Authorization: `Bearer ${AUTH_TOKEN}` } : {};
}

async function fetchExportHtml(baseURL: string): Promise<string> {
  const res = await fetch(`${baseURL}/api/projects/1/export`, {
    headers: authHeaders(),
  });
  expect(res.ok, "export endpoint should return 200").toBe(true);
  return res.text();
}

const EXPORT_ROUTES: Array<{ label: string; hash: string }> = [
  { label: "dashboard", hash: "" },
  { label: "sessions", hash: "#/report/sessions" },
  { label: "quotes", hash: "#/report/quotes" },
  { label: "codebook", hash: "#/report/codebook" },
  { label: "analysis", hash: "#/report/analysis" },
];

async function waitForMount(page: Page): Promise<void> {
  await page.waitForFunction(
    () => {
      const root = document.querySelector("#bn-app-root");
      return !!(root && root.children.length > 0);
    },
    undefined,
    { timeout: 10_000 },
  );
}

/** Offline resource-load noise (blocked fonts) we don't count as an app error. */
function isBenign(text: string): boolean {
  return (
    /fonts\.(googleapis|gstatic)\.com/.test(text) ||
    /Failed to load resource/.test(text) ||
    /net::ERR_/.test(text)
  );
}

test.describe("self-contained export artifact", () => {
  test("endpoint returns a self-contained artifact with the data embed", async ({
    baseURL,
  }) => {
    const html = await fetchExportHtml(baseURL!);
    expect(html).toContain("window.BRISTLENOSE_EXPORT=");
    expect(html).toContain('"endpoints"');
    expect(html).toContain('"/dashboard"');
    expect(html).toContain('id="bn-app-root"');
    // One inline module (no external/blob module scripts a file:// open can't reach).
    expect(html).toContain('<script type="module">');
    expect(html).not.toContain('src="/assets/');
    expect(html).not.toContain('href="/assets/');
    expect(html.length).toBeGreaterThan(1_000_000);
  });
});

test.describe("export renders offline from file://", () => {
  let fileUrl: string;

  test.beforeAll(async ({ baseURL }) => {
    const html = await fetchExportHtml(baseURL!);
    const dir = mkdtempSync(join(tmpdir(), "bn-export-"));
    const p = join(dir, "report.html");
    writeFileSync(p, html, "utf-8");
    fileUrl = pathToFileURL(p).href;
  });

  for (const route of EXPORT_ROUTES) {
    test(`renders cleanly at ${route.label}`, async ({ page }) => {
      const errors: string[] = [];
      page.on("console", (msg) => {
        if (msg.type() === "error" && !isBenign(msg.text())) errors.push(msg.text());
      });
      page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));

      await page.goto(fileUrl + route.hash);
      await waitForMount(page);
      const root = page.locator("#bn-app-root");
      await expect(root.locator("*").first()).toBeVisible();

      expect(
        errors,
        `console errors / unhandled rejections at ${route.label}:\n${errors.join("\n")}`,
      ).toEqual([]);

      // Intra-app links must be hash-routed (#/...), never browser-router paths
      // (/report/... or /api/...) — those navigate the browser off the file://
      // document to a non-existent path. Broken links throw no console error, so
      // this is the only guard for the Sessions-lens link class.
      const browserPathLinks = await page.evaluate(() =>
        Array.from(document.querySelectorAll("a[href]"))
          .map((a) => a.getAttribute("href") || "")
          .filter((h) => /^\/(report|api)\//.test(h)),
      );
      expect(
        browserPathLinks,
        `browser-router links break under hash routing at ${route.label}:\n${browserPathLinks.join("\n")}`,
      ).toEqual([]);
    });
  }
});

// ---------------------------------------------------------------------------
// Internal link integrity — the exported artifact must not contain a single
// dead-end. Crawl every tab, collect every <a href>, and FOLLOW each internal
// link asserting it lands on a real, mounted route (not the "Erreur"
// RouteError). Bare in-page anchors (#t=…, #section-…) must be onClick-
// intercepted so a click doesn't blow away the route hash. Broken links throw
// no console error, so this dynamic crawl is the only real guarantee.
// ---------------------------------------------------------------------------

test.describe("export link integrity", () => {
  let fileUrl: string;

  test.beforeAll(async ({ baseURL }) => {
    const html = await fetchExportHtml(baseURL!);
    const dir = mkdtempSync(join(tmpdir(), "bn-export-"));
    const p = join(dir, "report.html");
    writeFileSync(p, html, "utf-8");
    fileUrl = pathToFileURL(p).href;
  });

  test("every internal link resolves; no bare anchor breaks the route", async ({ page }) => {
    const collectHrefs = async (hash: string): Promise<string[]> => {
      await page.goto(fileUrl + hash);
      await waitForMount(page).catch(() => {});
      return page.evaluate(() =>
        Array.from(document.querySelectorAll("a[href]")).map((a) => a.getAttribute("href") || ""),
      );
    };

    // 1. Crawl every tab, plus any transcript route it links to.
    const hrefs = new Set<string>();
    for (const r of EXPORT_ROUTES) (await collectHrefs(r.hash)).forEach((h) => hrefs.add(h));
    const transcriptRoutes = [...hrefs].filter((h) => /^#\/report\/sessions\/[^/]+$/.test(h));
    for (const r of transcriptRoutes) (await collectHrefs(r)).forEach((h) => hrefs.add(h));

    // 2. No browser-router paths anywhere in the artifact.
    const browserPaths = [...hrefs].filter((h) => /^\/(report|api)\//.test(h));
    expect(browserPaths, `browser-router links:\n${browserPaths.join("\n")}`).toEqual([]);

    // 3. Follow every internal-route link — none may dead-end.
    const internal = [...hrefs].filter((h) => h.startsWith("#/report"));
    expect(internal.length, "expected at least one internal link to crawl").toBeGreaterThan(0);
    const deadEnds: string[] = [];
    for (const href of internal) {
      const errs: string[] = [];
      const onConsole = (m: import("@playwright/test").ConsoleMessage) => {
        if (m.type() === "error" && !isBenign(m.text())) errs.push(m.text());
      };
      page.on("console", onConsole);
      await page.goto(fileUrl + href);
      await waitForMount(page).catch(() => {});
      const broken = await page.evaluate(() => {
        const root = document.querySelector("#bn-app-root");
        const routeError = !!document.querySelector(".bn-route-error");
        return routeError || !root || root.children.length === 0;
      });
      page.off("console", onConsole);
      if (broken || errs.length) deadEnds.push(`${href} → ${errs[0] ?? "RouteError / empty"}`);
    }
    expect(deadEnds, `dead-end internal links:\n${deadEnds.join("\n")}`).toEqual([]);

    // 4. Bare in-page anchors (#t=…, #section-…) must be onClick-intercepted:
    // clicking one must NOT change the route hash (which would break the tab).
    for (const r of ["#/report/quotes", "#/report/sessions"]) {
      await page.goto(fileUrl + r);
      await waitForMount(page).catch(() => {});
      const anchor = page.locator('a[href^="#t="], a[href^="#section-"]').first();
      if ((await anchor.count()) === 0) continue;
      const before = await page.evaluate(() => location.hash);
      await anchor.click({ force: true }).catch(() => {});
      await page.waitForTimeout(400);
      const after = await page.evaluate(() => location.hash);
      const routeError = await page.evaluate(() => !!document.querySelector(".bn-route-error"));
      expect(
        { route: r, before, after, routeError },
        `bare anchor click broke the route at ${r}`,
      ).toMatchObject({ before, after: before, routeError: false });
    }
  });
});
