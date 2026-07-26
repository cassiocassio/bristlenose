import { describe, expect, it } from "vitest";
import { codebookDotState } from "./codebookDot";

describe("codebookDotState", () => {
  it("imported + enabled → on (blue, echoes the switch)", () => {
    expect(codebookDotState(true, "garrett", new Set())).toBe("on");
  });

  it("imported + disabled → off (grey, echoes the switch)", () => {
    expect(codebookDotState(true, "garrett", new Set(["garrett"]))).toBe("off");
  });

  it("not imported → available (transparent slot), regardless of disabled set", () => {
    expect(codebookDotState(false, "norman", new Set())).toBe("available");
    // A stale disabled entry for a not-imported codebook must not colour the dot.
    expect(codebookDotState(false, "norman", new Set(["norman"]))).toBe("available");
  });

  it("only the row's own id in the disabled set flips it off", () => {
    const disabled = new Set(["norman", "plato"]);
    expect(codebookDotState(true, "garrett", disabled)).toBe("on");
    expect(codebookDotState(true, "norman", disabled)).toBe("off");
  });
});
