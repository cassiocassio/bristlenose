/**
 * Tests for desktop-aware translation helper.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { _resetPlatformCache } from "./platform";

// Mock i18n module — must be before import of dt()
vi.mock("../i18n", () => ({
  default: {
    exists: vi.fn(),
  },
}));

import i18n from "../i18n";
import { dt } from "./desktopTranslation";

const mockExists = vi.mocked(i18n.exists);

/** Stub TFunction that returns the key (or desktop key) as the "translation". */
const stubT = ((key: string) => `translated:${key}`) as any;

beforeEach(() => {
  _resetPlatformCache();
  vi.clearAllMocks();
  // Default: not desktop
  delete document.documentElement.dataset.platform;
});

describe("dt", () => {
  it("returns base translation when not on desktop", () => {
    const result = dt(stubT, "help.privacy.redactionIntro");
    expect(result).toBe("translated:help.privacy.redactionIntro");
    expect(mockExists).not.toHaveBeenCalled();
  });

  it("returns desktop translation when on desktop and key exists", () => {
    document.documentElement.dataset.platform = "desktop";
    _resetPlatformCache();
    mockExists.mockReturnValue(true);

    // When desktop key exists, dt() calls t() with the desktop-namespaced key
    const t = vi.fn().mockImplementation((key: string) => `translated:${key}`);
    const result = dt(t as any, "help.privacy.redactionIntro");

    expect(mockExists).toHaveBeenCalledWith("desktop:help.privacy.redactionIntro");
    expect(result).toBe("translated:desktop:help.privacy.redactionIntro");
  });

  it("falls back to base translation when on desktop but key missing", () => {
    document.documentElement.dataset.platform = "desktop";
    _resetPlatformCache();
    mockExists.mockReturnValue(false);

    const result = dt(stubT, "help.privacy.redactionIntro");

    expect(mockExists).toHaveBeenCalledWith("desktop:help.privacy.redactionIntro");
    expect(result).toBe("translated:help.privacy.redactionIntro");
  });

  it("works with settings namespace keys", () => {
    document.documentElement.dataset.platform = "desktop";
    _resetPlatformCache();
    mockExists.mockReturnValue(true);

    const t = vi.fn().mockImplementation((key: string) => `translated:${key}`);
    const result = dt(t as any, "configReference.intro");

    expect(mockExists).toHaveBeenCalledWith("desktop:configReference.intro");
    expect(result).toBe("translated:desktop:configReference.intro");
  });
});
