/**
 * English `desktop` is fetched, not bundled — see `desktopEnReady` in ./index.
 *
 * The budget gate pins the bytes staying off first paint; this pins the other
 * half of the contract: on the Mac the namespace is registered by the time
 * main.tsx mounts, and in a browser there is nothing to wait for.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  delete document.documentElement.dataset.platform;
  vi.resetModules();
});

describe("desktopEnReady", () => {
  it("is null in a browser, and the desktop namespace stays unregistered", async () => {
    vi.resetModules();
    const { default: i18n, desktopEnReady } = await import("./index");
    expect(desktopEnReady).toBeNull();
    expect(i18n.hasResourceBundle("en", "desktop")).toBe(false);
  });

  it("registers English desktop on the Mac before it resolves", async () => {
    document.documentElement.dataset.platform = "desktop";
    vi.resetModules();
    const { default: i18n, desktopEnReady } = await import("./index");
    expect(desktopEnReady).not.toBeNull();
    await desktopEnReady;
    expect(i18n.hasResourceBundle("en", "desktop")).toBe(true);
    expect(i18n.exists("desktop:configReference.intro")).toBe(true);
  });
});
