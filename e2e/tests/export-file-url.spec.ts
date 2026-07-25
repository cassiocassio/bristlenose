/**
 * The self-contained HTML export as a leave-behind artifact.
 *
 * Two things this file asserts:
 *
 *  1. (PASSING) The export endpoint returns a self-contained artifact with the
 *     path-keyed data embed inlined — the anti-drift contract's client half.
 *
 *  2. (FIXME — known limitation) Opening that artifact from `file://` — the way a
 *     stakeholder double-clicks it on a corporate laptop — does NOT currently
 *     render. The bundle is code-split ESM loaded via `blob:` URLs; browsers
 *     block `blob:` module scripts from an opaque (file://) origin, and the
 *     obvious data:-URL alternative can't resolve a module's own bare/relative
 *     sub-imports (import maps only resolve the top-level document module). The
 *     blob bootstrap works when the export is *served* (WKWebView/http origin —
 *     how it's consumed today); making a raw file:// double-click work needs a
 *     dedicated single-file inline build of the SPA, not a bootstrap tweak.
 *     Tracked as the "file:// export" work; flip these `fixme`s to `test` once
 *     the single-file build lands, and it becomes the real acceptance gate.
 *
 * Runs on Chromium + WebKit (Edge/Chrome are Chromium; WebKit covers Safari).
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

test.describe("self-contained export artifact", () => {
  test("endpoint returns a self-contained artifact with the data embed", async ({
    baseURL,
  }) => {
    const html = await fetchExportHtml(baseURL!);
    // Path-keyed data embed present (the anti-drift contract's payload).
    expect(html).toContain("window.BRISTLENOSE_EXPORT=");
    expect(html).toContain('"endpoints"');
    expect(html).toContain('"/dashboard"');
    expect(html).toContain('id="bn-app-root"');
    // Fully inlined — no external asset references to a server.
    expect(html).not.toContain('src="/assets/');
    expect(html).not.toContain('href="/assets/');
    // Non-trivial (bundle + data inlined).
    expect(html.length).toBeGreaterThan(500_000);
  });
});

// ---------------------------------------------------------------------------
// KNOWN LIMITATION — export does not yet render from file:// (see file header).
// These are the real acceptance gate once a single-file build lands.
// ---------------------------------------------------------------------------

const EXPORT_ROUTES: Array<{ label: string; hash: string }> = [
  { label: "dashboard", hash: "" },
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

function isBenign(text: string): boolean {
  return (
    /fonts\.(googleapis|gstatic)\.com/.test(text) ||
    /Failed to load resource/.test(text) ||
    /net::ERR_/.test(text)
  );
}

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
    test.fixme(`renders cleanly at ${route.label}`, async ({ page }) => {
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
    });
  }
});
