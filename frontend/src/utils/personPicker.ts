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
  /** False when nobody has ever said yes to this person in any session: a
   *  pipeline guess. Such a person is offered only on their own speaker
   *  (§J8.10). Absent reads as confirmed. */
  confirmed?: boolean;
}

/**
 * What the picker hands back (docs/design-people.md §J8, answer 2). Three
 * acts, never inferred from a name, because two people may share one:
 * - `confirm`: yes to the name the slot holds;
 * - `person`: this slot is that person;
 * - `new`: someone new for this slot, by this name;
 * - `name`: a new spelling for the slot's own person, wherever they appear —
 *   a participant's typed name, or a rename in place on the current row;
 * - `clear`: not this person — the slot returns to unknown (§J8.8).
 */
export type PersonPickerChoice =
  | { kind: "confirm" }
  | { kind: "clear" }
  | { kind: "person"; row: PersonPickerRow; role?: PickerRole }
  | { kind: "new"; name: string; role?: PickerRole }
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
    // Another session's guess is not offered here (§J8.10): one wrong guess
    // must not spread. The slot's own guess is added below.
    if (row.confirmed === false && !isOwnRow(slot, row)) continue;
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
export function personPickerChoice(
  slot: PersonPickerSlot,
  row: PersonPickerRow,
  role: PickerRole = slot.role,
): PersonPickerChoice | null {
  // Under another role, every row — the speaker's own person included — is a
  // recode to that role (§J7 R1).
  if (role !== slot.role) return { kind: "person", row, role };
  if (isOwnRow(slot, row)) return slot.confirmed ? null : { kind: "confirm" };
  if (slot.role === "participant") return null;
  return { kind: "person", row };
}

/** The name another person already goes by, if `name` is theirs
 *  (case-insensitive). Someone new may not take it (§J8.11): there are two
 *  Martins, who need telling apart, or the researcher meant to pick Martin.
 *  Pass every person known for the role — not only the offered rows — since
 *  an unoffered guess still holds its name, and the server refuses it too. */
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
export function personPickerTyped(
  slot: PersonPickerSlot,
  name: string,
  role: PickerRole = slot.role,
): PersonPickerChoice | null {
  const trimmed = name.trim();
  if (!trimmed) return null;
  if (role !== slot.role) return { kind: "new", name: trimmed, role };
  if (trimmed === slot.name) return slot.confirmed ? null : { kind: "confirm" };
  return slot.role === "participant" ? { kind: "name", name: trimmed } : { kind: "new", name: trimmed };
}

/** A picker label with its `{{name}}` filled — the labels leave it open
 *  because the Mac picker fills it too. */
export function withName(template: string, name: string): string {
  return template.replace("{{name}}", name);
}

/** The roles a slot's picker lets the researcher switch between (§J7): a
 *  moderator and an observer can be recoded as each other (R1); a
 *  participant, and recoding into participant, is R2 and not built. */
export function personPickerRolesOpen(slot: PersonPickerSlot): PickerRole[] {
  return slot.role === "participant" ? ["participant"] : ["moderator", "observer"];
}

/** What the picker offers under another role (§J7): the speaker's own person
 *  first — the same person, recoded — then that role's people, each by the
 *  code they would carry in it. */
export function personPickerRowsForRole(
  slot: PersonPickerSlot,
  role: PickerRole,
  known: PersonPickerRow[],
): PersonPickerRow[] {
  if (role === slot.role) return personPickerRows(slot, known);
  const others = personPickerRows({ ...slot, role, name: "", person: undefined }, known)
    .filter((r) => !(slot.person && r.person === slot.person));
  if (!slot.person || !slot.name) return others;
  const code = personPickerNewCode({ ...slot, role }, others);
  return [{ name: slot.name, code, person: slot.person }, ...others];
}

/** Whether a row can be renamed in place: the slot's own confirmed answer
 *  (§J8.8). A proposed one is confirmed first, by its own click or Return. */
export function personPickerCanRename(slot: PersonPickerSlot, row: PersonPickerRow): boolean {
  return slot.confirmed && !!slot.name && isOwnRow(slot, row);
}

/** What a rename in place means: a new spelling for that person everywhere,
 *  or nothing when empty or unchanged. A taken name is the caller's to refuse
 *  first. */
export function personPickerRenamed(slot: PersonPickerSlot, name: string): PersonPickerChoice | null {
  const trimmed = name.trim();
  if (!trimmed || trimmed === slot.name) return null;
  return { kind: "name", name: trimmed };
}

/** Whether the slot's current answer can be refused with the ✕: a moderator
 *  or observer the slot points at. A participant's code is never unknown. */
export function personPickerCanClear(slot: PersonPickerSlot): boolean {
  return slot.role !== "participant" && !!slot.person && !!slot.name;
}

/** The letter an unknown moderator or observer goes by (`mA?` → "A"), or null
 *  for `m?` and every known code (design-people.md §J8.9). */
export function unknownLetter(code: string): string | null {
  const m = /^[mo]([A-Z]+)\?$/.exec(code);
  return m ? m[1] : null;
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
  /** The hint under each role a recode can browse to (§J7 R1). */
  newPromptFor?: Partial<Record<PickerRole, string>>;
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
  /** "Not {{name}}" — the ✕ on the current row, with `{{name}}` left for the
   *  caller. */
  notThisPerson: string;
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
    newPromptFor: {
      moderator: t("sessions.picker.newModerator"),
      observer: t("sessions.picker.newObserver"),
    },
    // i18next would fill {{name}}; it is left for native, which knows it.
    thatsMe:
      slot.role === "participant"
        ? null
        : t("sessions.picker.thatsMe", { name: "{{name}}", interpolation: { escapeValue: false } }),
    menu: t("sessions.editName", { code: slot.code }),
    proposed: personPickerProposedLabel(slot, t),
    nameTaken: t("sessions.picker.nameTaken", { name: "{{name}}", interpolation: { escapeValue: false } }),
    notThisPerson: t("sessions.picker.notThisPerson", { name: "{{name}}", interpolation: { escapeValue: false } }),
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
