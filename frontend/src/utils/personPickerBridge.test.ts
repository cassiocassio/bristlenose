/**
 * The person picker bridge, SPA side, against the shared contract fixture
 * (`tests/fixtures/person-picker-bridge-contract.json`). Swift's
 * PersonPickerContractTests decode the same `wire` and build the same
 * `payload`, so a field added on one side only fails one of the two suites.
 */
import contractJson from "../../../tests/fixtures/person-picker-bridge-contract.json";
import i18n from "../i18n";
import type { PersonPickerRow, PersonPickerSlot, PersonPickerSwap, PickerRole } from "./personPicker";
import { buildPersonPickerMessage, resolvePersonPickerChoice } from "./personPickerBridge";

interface WebToNativeCase {
  name: string;
  input: {
    sessionId: string;
    slot: PersonPickerSlot;
    known: PersonPickerRow[];
    knownByRole?: Record<PickerRole, PersonPickerRow[]>;
    swap?: PersonPickerSwap;
    anchor: { x: number; y: number; width: number; height: number };
  };
  wire: unknown;
}

interface NativeToWebCase {
  name: string;
  payload: unknown;
  slot: PersonPickerSlot;
  known: PersonPickerRow[];
  knownByRole?: Record<PickerRole, PersonPickerRow[]>;
  swap?: PersonPickerSwap;
  effect: unknown;
}

const contract = contractJson as unknown as {
  web_to_native: WebToNativeCase[];
  native_to_web: NativeToWebCase[];
};

describe("person picker bridge contract", () => {
  beforeAll(async () => {
    await i18n.changeLanguage("en");
  });

  for (const c of contract.web_to_native) {
    it(`builds: ${c.name}`, () => {
      const { sessionId, slot, known, anchor, knownByRole, swap } = c.input;
      expect(buildPersonPickerMessage(sessionId, slot, known, anchor, i18n.t, knownByRole, swap)).toEqual(c.wire);
    });
  }

  for (const c of contract.native_to_web) {
    it(`resolves: ${c.name}`, () => {
      const pick = resolvePersonPickerChoice(c.payload, () => ({
        slot: c.slot,
        known: c.known,
        knownByRole: c.knownByRole,
        swap: c.swap,
      }));
      const effect = pick === null ? null : "taken" in pick ? { taken: pick.taken } : pick.choice;
      expect(effect).toEqual(c.effect);
    });
  }

  it("a pick for a speaker the grid no longer has is dropped", () => {
    const [c] = contract.native_to_web;
    expect(resolvePersonPickerChoice(c.payload, () => null)).toBeNull();
  });

  it("a role reply with no people by role to read is dropped, never read as a pick in the speaker's own role", () => {
    const slot: PersonPickerSlot = { code: "p3", role: "participant", name: "Mary", confirmed: true };
    const payload = { sessionId: "s3", code: "p3", choice: { kind: "new", name: "Jo Bloggs", role: "observer" } };
    expect(resolvePersonPickerChoice(payload, () => ({ slot, known: [] }))).toBeNull();
  });

  it("a malformed payload is dropped", () => {
    expect(resolvePersonPickerChoice({ sessionId: "s1", choice: { kind: "name", name: "x" } }, () => null)).toBeNull();
    expect(resolvePersonPickerChoice({ sessionId: "s1", code: "m1", choice: { kind: "name", name: "  " } }, () => null)).toBeNull();
  });
});
