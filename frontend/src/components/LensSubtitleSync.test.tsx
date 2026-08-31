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
  it("resolves the v2 route to its own tab, not the shipped lens", () => {
    expect(tabFromPath("/report/codebook-v2")).toBe("codebookV2");
    expect(tabFromPath("/report/codebook-v2/")).toBe("codebookV2");
    expect(tabFromPath("/report/codebook-v2?view=library")).toBe("codebookV2");
  });

  it("still resolves the shipped codebook lens", () => {
    expect(tabFromPath("/report/codebook")).toBe("codebook");
    expect(tabFromPath("/report/codebook/")).toBe("codebook");
  });

  it("returns the Swift rawValue spelling, not the route slug", () => {
    // `case codebookV2` in Tab.swift has rawValue "codebookV2". Posting the
    // route's "codebook-v2" would fail the guard exactly as the prefix bug did
    // — same silent fallback, different cause.
    expect(tabFromPath("/report/codebook-v2")).not.toBe("codebook-v2");
  });

  it("resolves the other lenses unchanged", () => {
    expect(tabFromPath("/report/quotes")).toBe("quotes");
    expect(tabFromPath("/report/analysis")).toBe("analysis");
    expect(tabFromPath("/report/sessions")).toBe("sessions");
  });
});
