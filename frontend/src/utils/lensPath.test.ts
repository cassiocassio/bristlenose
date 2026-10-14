import { describe, expect, it } from "vitest";
import { activeTabForPath, navigationLabel } from "./lensPath";

describe("lensPath", () => {
  it("reports the Screens lens to the Mac as its own tab", () => {
    expect(activeTabForPath("/report/screens/")).toBe("screens");
    expect(activeTabForPath("/report/discussion/")).toBe("discussion");
    expect(activeTabForPath("/report/")).toBe("project");
  });

  it("announces the Screens lens by name, not as the Project lens", () => {
    expect(navigationLabel("/report/screens/")).toBe("Screens");
    expect(navigationLabel("/report/")).not.toBe("Screens");
    expect(navigationLabel("/report/quotes/")).toBe(navigationLabel("/report/quotes"));
  });
});
