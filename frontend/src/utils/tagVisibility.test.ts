/**
 * deriveTagVisibility — the hide/disable split (design-codebook-state-model.md §5).
 * "Same badge-hide, opposite reachability." These tests pin that opposition.
 */

import { describe, expect, it } from "vitest";

import { deriveTagVisibility, isBadgeHidden, type TagGroupMeta } from "./tagVisibility";

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
    expect(isBadgeHidden(v, "Law-of-Proximity", "Laws of UX")).toBe(true); // badge hidden too
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

  it("a null-framework tag is treated as floor even if its group name collides", () => {
    // Defensive: suppression keys on frameworkId, not group name. A tag with
    // frameworkId=null is the floor and can never be suppressed — even if some other
    // (disabled) framework happens to share the group name. Documents the invariant
    // the §5 "invisible add" prevention rests on.
    const collide: Record<string, TagGroupMeta> = {
      "floor-tag": { group: "Shared Name", frameworkId: null },
      "fw-tag": { group: "Shared Name", frameworkId: "garrett" },
    };
    const v = deriveTagVisibility(collide, new Set(), new Set(["garrett"]));
    expect(v.suppressedTagNames.has("fw-tag")).toBe(true); // disabled fw → gone
    expect(v.suppressedTagNames.has("floor-tag")).toBe(false); // floor → stays
    expect(v.decoratedTagNames.has("floor-tag")).toBe(false); // not hidden either
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

  // N186: badges were filtered by group NAME, and the disabled framework's group
  // names were added to the hidden set, so switching off one codebook hid the
  // badges of any other codebook's same-named group (Norman's and CLI UX's
  // "Discoverability"). The disabled half is keyed by tag now.
  describe("two codebooks with a group of the same name", () => {
    const same: Record<string, TagGroupMeta> = {
      "affordance cues": { group: "Discoverability", frameworkId: "norman" },
      "flag discovery": { group: "Discoverability", frameworkId: "cli-ux" },
    };

    it("disabling one does not hide the other's badges", () => {
      const v = deriveTagVisibility(same, new Set(), new Set(["cli-ux"]));
      expect(v.hiddenGroups.has("Discoverability")).toBe(false);
      expect(isBadgeHidden(v, "Affordance cues", "Discoverability")).toBe(false);
      expect(isBadgeHidden(v, "Flag discovery", "Discoverability")).toBe(true);
    });

    // The eye is stored by group NAME, so hiding one same-named group hides both. That
    // is the current behaviour, not a settled one: it waits on a ruling (the key would
    // have to change in the stored data). Do not read this test as the spec.
    it("an eye-hidden group still hides every badge of that name (the eye is stored by name)", () => {
      const v = deriveTagVisibility(same, new Set(["Discoverability"]), new Set());
      expect(isBadgeHidden(v, "Affordance cues", "Discoverability")).toBe(true);
      expect(isBadgeHidden(v, "Flag discovery", "Discoverability")).toBe(true);
    });

    it("a floor tag that shares a framework tag's name keeps its badge when the framework is off", () => {
      const clash: Record<string, TagGroupMeta> = {
        // the map holds one entry per tag name, so the framework's wins the key
        "pricing": { group: "Money", frameworkId: "cli-ux" },
      };
      const v = deriveTagVisibility(clash, new Set(), new Set(["cli-ux"]));
      expect(isBadgeHidden(v, "Pricing", "Money")).toBe(true);
      expect(isBadgeHidden(v, "Pricing", "Uncategorised")).toBe(false);
    });

    it("a tag the map does not know is shown unless its group is eye-hidden", () => {
      const v = deriveTagVisibility(same, new Set(), new Set(["cli-ux", "norman"]));
      expect(isBadgeHidden(v, "Someone's own tag", "Discoverability")).toBe(false);
    });
  });
});
