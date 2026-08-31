import { describe, expect, it } from "vitest";
import { tabFromPath } from "./LensSubtitleSync";

/**
 * The tag this returns is matched against the Swift `Tab` rawValue before the
 * window subtitle is honoured:
 *
 *     guard bridgeHandler.lensSubtitleTab == bridgeHandler.activeTab?.rawValue
 *
 * So a wrong tag does not render a wrong subtitle — it renders NO subtitle, and
 * the window silently falls back to the session count. That is what shipped on
 * the v2 lens: "/report/codebook-v2" starts with "/report/codebook", the
 * shorter test matched first, and a codebook lens reported "3 Sessions · 9m".
 */
describe("tabFromPath — longest prefix first", () => {
  it("resolves the codebook lens, library view included", () => {
    // Was "resolves the v2 route to its own tab". That route retired on
    // 31 Aug 2026 when the lens took `/report/codebook`; the library is now a
    // query param on it, which must not change the tag.
    expect(tabFromPath("/report/codebook")).toBe("codebook");
    expect(tabFromPath("/report/codebook?view=library")).toBe("codebook");
  });

  it("still resolves the shipped codebook lens", () => {
    expect(tabFromPath("/report/codebook")).toBe("codebook");
    expect(tabFromPath("/report/codebook/")).toBe("codebook");
  });

  it("returns the Swift rawValue spelling, not a route slug", () => {
    // The tag is matched against `Tab.rawValue`; a slug would fail the guard
    // silently and the window would fall back to the session count.
    expect(tabFromPath("/report/codebook")).toBe("codebook");
  });

  it("resolves the other lenses unchanged", () => {
    expect(tabFromPath("/report/quotes")).toBe("quotes");
    expect(tabFromPath("/report/analysis")).toBe("analysis");
    expect(tabFromPath("/report/sessions")).toBe("sessions");
  });
});
