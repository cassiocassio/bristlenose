/**
 * The person picker's model (docs/design-people.md § UX iteration 3): which
 * names a speaker slot's picker offers, and what choosing one means. Shared by
 * the browser's `PersonPicker` and the Mac app's native picker (through
 * `personPickerBridge`), so the two cannot disagree. Kept out of the component
 * so the Sessions grid, which loads before first paint, can use it without
 * pulling the picker in: the component is loaded only when someone opens it.
 */

import type { TFunction } from "i18next";

export type PickerRole = "moderator" | "participant" | "observer";

/** One speaker slot: this session's speaker, its name, and whether a person
 *  has said yes to it. */
export interface PersonPickerSlot {
  code: string;
  role: PickerRole;
  name: string;
  confirmed: boolean;
}

/** What the picker hands back. `confirm` keeps the name and says yes to it. */
export type PersonPickerChoice = { kind: "confirm" } | { kind: "name"; name: string };

/** The names a slot's picker offers, in order. Shared with the native picker. */
export function personPickerRows(slot: PersonPickerSlot, knownNames: string[]): string[] {
  if (slot.role === "participant") return slot.name ? [slot.name] : [];
  const names = [...new Set(knownNames.filter(Boolean))];
  if (slot.name && !names.includes(slot.name)) names.unshift(slot.name);
  return names;
}

/** What choosing a name means for this slot: the slot's own proposed name is a
 *  yes; its own confirmed name changes nothing; any other name renames it. */
export function personPickerChoice(slot: PersonPickerSlot, name: string): PersonPickerChoice | null {
  const trimmed = name.trim();
  if (!trimmed) return null;
  if (trimmed === slot.name) return slot.confirmed ? null : { kind: "confirm" };
  return { kind: "name", name: trimmed };
}

/** The speaker roles in their segment order. */
export const PICKER_ROLES: PickerRole[] = ["moderator", "participant", "observer"];

/** Every string either picker shows, localised once by the caller — the web
 *  picker takes them as a prop and the Mac app receives the same object over
 *  the bridge, so the two read one source. */
export interface PersonPickerLabels {
  roles: Record<PickerRole, string>;
  /** The role toggle's accessible name. */
  roleGroup: string;
  /** The new-person field's hint, which follows the role. */
  newPrompt: string;
  /** "That’s Me ({{name}})" — native fills the account's name; null where the
   *  role has no That's Me row (a participant), and unused in the browser. */
  thatsMe: string | null;
  /** The menu's accessible name. */
  menu: string;
  /** The accessible name of the slot's own name while it is proposed
   *  ("m1, proposed name Sarah"): the dotted ring and the grey say it only
   *  to the eye. Null when there is no proposed name. */
  proposed: string | null;
}

/** The picker's strings for one slot. */
export function personPickerLabels(slot: PersonPickerSlot, t: TFunction): PersonPickerLabels {
  const roles = Object.fromEntries(
    PICKER_ROLES.map((r) => [r, t(`sessions.speakerPlaceholder.${r}`)]),
  ) as Record<PickerRole, string>;
  const newPrompt =
    slot.role === "moderator" ? t("sessions.picker.newModerator")
    : slot.role === "observer" ? t("sessions.picker.newObserver")
    : t("sessions.picker.newNameFor", { code: slot.code });
  return {
    roles,
    roleGroup: t("sessions.picker.role"),
    newPrompt,
    // i18next would fill {{name}}; it is left for native, which knows it.
    thatsMe:
      slot.role === "participant"
        ? null
        : t("sessions.picker.thatsMe", { name: "{{name}}", interpolation: { escapeValue: false } }),
    menu: t("sessions.editName", { code: slot.code }),
    proposed: personPickerProposedLabel(slot, t),
  };
}

/** "m1, proposed name Sarah" for a proposed slot, null otherwise. The grid's
 *  badge and both pickers' rows use it, so all three read the same. */
export function personPickerProposedLabel(slot: PersonPickerSlot, t: TFunction): string | null {
  if (!slot.name || slot.confirmed) return null;
  return t("sessions.picker.proposedName", {
    code: slot.code,
    name: slot.name,
    interpolation: { escapeValue: false },
  });
}
