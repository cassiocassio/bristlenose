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
    });
  }
});
