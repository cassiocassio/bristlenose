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
 *  has said yes to it. `code` is the code its badge shows. */
export interface PersonPickerSlot {
  code: string;
  role: PickerRole;
  name: string;
  confirmed: boolean;
  /** The person a moderator or observer slot points at (their uuid); absent on
   *  `m?` and on participants. */
  person?: string;
}

/** One row the picker offers: a person, by the code and name they go by. */
export interface PersonPickerRow {
  name: string;
  code: string;
  /** Moderators and observers only: the person's uuid. */
  person?: string;
  /** The stored names behind `name`, so a pick writes them back unchanged. */
  full_name?: string;
  short_name?: string;
}

/**
 * What the picker hands back (docs/design-people.md §J8, answer 2). Three
 * acts, never inferred from a name, because two people may share one:
 * - `confirm`: yes to the name the slot holds;
 * - `person`: this slot is that person;
 * - `new`: someone new for this slot, by this name;
 * - `name`: a participant's name (a participant is never picked).
 */
export type PersonPickerChoice =
  | { kind: "confirm" }
  | { kind: "person"; row: PersonPickerRow }
  | { kind: "new"; name: string }
  | { kind: "name"; name: string };

function isOwnRow(slot: PersonPickerSlot, row: PersonPickerRow): boolean {
  return slot.person ? row.person === slot.person : row.name === slot.name;
}

/** The rows a slot's picker offers, in order. Shared with the native picker. */
export function personPickerRows(slot: PersonPickerSlot, known: PersonPickerRow[]): PersonPickerRow[] {
  if (slot.role === "participant") {
    return slot.name ? [{ name: slot.name, code: slot.code, person: slot.person }] : [];
  }
  const rows: PersonPickerRow[] = [];
  const seen = new Set<string>();
  for (const row of known) {
    if (!row.name) continue;
    const key = row.person ?? `name:${row.name}`;
    if (seen.has(key)) continue;
    seen.add(key);
    rows.push(row);
  }
  if (slot.name && !rows.some((r) => isOwnRow(slot, r))) {
    rows.unshift({ name: slot.name, code: slot.code, person: slot.person });
  }
  return rows;
}

/** The code someone new would get: the next free number for this role
 *  (§J8.8), or a participant's own code, which never changes. */
export function personPickerNewCode(slot: PersonPickerSlot, rows: PersonPickerRow[]): string {
  if (slot.role === "participant") return slot.code;
  const prefix = slot.role === "moderator" ? "m" : "o";
  const taken = rows
    .map((r) => /^([mo])(\d+)$/.exec(r.code))
    .filter((m): m is RegExpExecArray => m !== null && m[1] === prefix)
    .map((m) => Number(m[2]));
  return `${prefix}${taken.length ? Math.max(...taken) + 1 : 1}`;
}

/** What choosing a row means: the slot's own proposed answer is a yes, its own
 *  confirmed answer changes nothing, any other row is that person. */
export function personPickerChoice(slot: PersonPickerSlot, row: PersonPickerRow): PersonPickerChoice | null {
  if (isOwnRow(slot, row)) return slot.confirmed ? null : { kind: "confirm" };
  if (slot.role === "participant") return null;
  return { kind: "person", row };
}

/** The name another person in the list already goes by, if `name` is theirs
 *  (case-insensitive). Someone new may not take it (§J8.11): there are two
 *  Martins, who need telling apart, or the researcher meant to pick Martin. */
export function personPickerNameTaken(
  slot: PersonPickerSlot,
  rows: PersonPickerRow[],
  name: string,
): string | null {
  if (slot.role === "participant") return null;
  const wanted = name.trim().toLocaleLowerCase();
  const hit = rows.find(
    (r) =>
      !isOwnRow(slot, r) &&
      [r.name, r.full_name, r.short_name].some((n) => n && n.trim().toLocaleLowerCase() === wanted),
  );
  return hit ? hit.name : null;
}

/** What a typed name means: someone new for a moderator or observer (unless
 *  it is the slot's own name), a participant's name otherwise. Null when empty
 *  or unchanged. A taken name is the caller's to refuse first. */
export function personPickerTyped(slot: PersonPickerSlot, name: string): PersonPickerChoice | null {
  const trimmed = name.trim();
  if (!trimmed) return null;
  if (trimmed === slot.name) return slot.confirmed ? null : { kind: "confirm" };
  return slot.role === "participant" ? { kind: "name", name: trimmed } : { kind: "new", name: trimmed };
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
  /** "There's already a {{name}}…" — the web picker's refusal of a taken name
   *  (§J8.11), with `{{name}}` left for the caller. */
  nameTaken: string;
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
    nameTaken: t("sessions.picker.nameTaken", { name: "{{name}}", interpolation: { escapeValue: false } }),
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
