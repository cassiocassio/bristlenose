/**
 * deriveTagVisibility — the hide/disable split (design-codebook-state-model.md §5).
 * "Same badge-hide, opposite reachability." These tests pin that opposition.
 */

import { describe, expect, it } from "vitest";

import { deriveTagVisibility, type TagGroupMeta } from "./tagVisibility";

const map: Record<string, TagGroupMeta> = {
  // eye-hideable floor tag (no framework)
  "onboarding-friction": { group: "Behaviour", frameworkId: null },
  // framework tag (Laws of UX / garrett)
  "law-of-proximity": { group: "Laws of UX", frameworkId: "garrett" },
  // another framework tag (uxr)
  "signal-strength": { group: "Signals", frameworkId: "uxr" },
};

describe("deriveTagVisibility", () => {
  it("hide (eye) keeps the tag suggestable but decorated", () => {
    const v = deriveTagVisibility(map, new Set(["Behaviour"]), new Set());
    expect(v.decoratedTagNames.has("onboarding-friction")).toBe(true);
    expect(v.suppressedTagNames.has("onboarding-friction")).toBe(false);
    expect(v.hiddenGroups.has("Behaviour")).toBe(true); // badge hidden
  });

  it("disable suppresses the tag from autocomplete entirely", () => {
    const v = deriveTagVisibility(map, new Set(), new Set(["garrett"]));
    expect(v.suppressedTagNames.has("law-of-proximity")).toBe(true);
    expect(v.decoratedTagNames.has("law-of-proximity")).toBe(false);
    expect(v.hiddenGroups.has("Laws of UX")).toBe(true); // badge hidden too
  });

  it("disable wins when a group is both eye-hidden AND disabled", () => {
    const v = deriveTagVisibility(
      map,
      new Set(["Laws of UX"]),
      new Set(["garrett"]),
    );
    // off means off — suppressed, not merely decorated.
    expect(v.suppressedTagNames.has("law-of-proximity")).toBe(true);
    expect(v.decoratedTagNames.has("law-of-proximity")).toBe(false);
  });

  it("the floor (no framework) can be hidden but never suppressed", () => {
    // Even if a framework id coincidentally matches, a null-framework tag is never
    // disabled — the floor is permanent (§2).
    const v = deriveTagVisibility(
      map,
      new Set(["Behaviour"]),
      new Set(["garrett", "uxr"]),
    );
    expect(v.decoratedTagNames.has("onboarding-friction")).toBe(true);
    expect(v.suppressedTagNames.has("onboarding-friction")).toBe(false);
  });

  it("only the disabled framework's tags are suppressed", () => {
    const v = deriveTagVisibility(map, new Set(), new Set(["garrett"]));
    expect(v.suppressedTagNames.has("law-of-proximity")).toBe(true);
    expect(v.suppressedTagNames.has("signal-strength")).toBe(false); // uxr enabled
  });

  it("no hide, no disable → everything empty (all reachable, all shown)", () => {
    const v = deriveTagVisibility(map, new Set(), new Set());
    expect(v.hiddenGroups.size).toBe(0);
    expect(v.decoratedTagNames.size).toBe(0);
    expect(v.suppressedTagNames.size).toBe(0);
  });

  it("an eye-hidden group with no mapped tags still hides its badges", () => {
    // hiddenGroups seeds from hiddenTagGroups directly, so a group whose tags aren't
    // in the map still filters its badges on the card.
    const v = deriveTagVisibility(map, new Set(["Empty Group"]), new Set());
    expect(v.hiddenGroups.has("Empty Group")).toBe(true);
    expect(v.decoratedTagNames.size).toBe(0);
  });
});
