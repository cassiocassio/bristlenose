import { describe, it, expect, beforeEach } from "vitest";
import {
  DEFAULTS, LADDER, PAD_STEPS, getTapestryTuning, resetTapestryTuning, setTapestryTuning, tuningChanges,
} from "./tapestryTuning";

describe("tapestry tuning", () => {
  beforeEach(() => resetTapestryTuning());

  it("defaults are steps that exist on the ladders, so the shipped design is on-token", () => {
    for (const step of Object.values(DEFAULTS.type)) expect(LADDER).toContain(step);
    for (const [k, list] of Object.entries(PAD_STEPS)) {
      expect(list).toContain(DEFAULTS.pad[k as keyof typeof PAD_STEPS]);
    }
  });

  it("lists nothing to commit at the defaults, and each move it makes", () => {
    expect(tuningChanges(getTapestryTuning())).toEqual([]);
    setTapestryTuning({ ...DEFAULTS, type: { ...DEFAULTS.type, theme: "caption" }, pad: { ...DEFAULTS.pad, themeH: 20 } });
    expect(tuningChanges(getTapestryTuning())).toEqual([
      "type.theme: --bn-text-label → --bn-text-caption",
      "pad.themeH: 18px → 20px",
    ]);
  });
});
