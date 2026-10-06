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
  | { kind: "name"; name: string }
  /** §J7 call 4: this speaker and `slot` (the other's slot code) were the
   *  other way round — one write that exchanges their roles and people. */
  | { kind: "swap"; slot: string };

/** The speaker a swap would exchange with: in a session of exactly one
 *  participant and one moderator, each is the other's (§J7 call 4) — the
 *  common inversion, where the pipeline called the moderator `p3`. */
export interface PersonPickerSwap {
  /** The code the other speaker shows (`m1`). */
  code: string;
  /** Their slot code, which a write addresses. */
  slot: string;
}

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
 *  (§J8.8), or a participant's own code, which never changes. A speaker
 *  recoded into participant (§J7 R2) has none of their own, and is numbered
 *  after every participant in the study, as the server numbers them. */
export function personPickerNewCode(
  slot: PersonPickerSlot,
  rows: PersonPickerRow[],
  known: PersonPickerRow[] = rows,
): string {
  if (slot.role === "participant") {
    if (slot.code.startsWith("p") && !slot.code.endsWith("?")) return slot.code;
    const numbers = known
      .map((r) => /^p(\d+)$/.exec(r.code))
      .filter((m): m is RegExpExecArray => m !== null)
      .map((m) => Number(m[1]));
    return `p${numbers.length ? Math.max(...numbers) + 1 : 1}`;
  }
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
  role: PickerRole = slot.role,
): string | null {
  // Participants may share a name: the check is for the team (§J8.11).
  if (role === "participant") return null;
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

/** The new-person field's hint under the role being browsed. */
export function newPromptUnder(labels: PersonPickerLabels, role: PickerRole, recoding: boolean, code: string): string {
  const under = recoding ? labels.newPromptFor?.[role] : undefined;
  return (under ?? labels.newPrompt).replace("{{code}}", code);
}

/** A picker label with its `{{name}}` filled — the labels leave it open
 *  because the Mac picker fills it too. */
export function withName(template: string, name: string): string {
  return template.replace("{{name}}", name);
}

/** The roles a slot's picker lets the researcher switch between (§J7): every
 *  one — moderator and observer as each other (R1), into and out of
 *  participant (R2). A segment click only browses; a pick under it recodes. */
export function personPickerRolesOpen(_slot: PersonPickerSlot): PickerRole[] {
  return [...PICKER_ROLES];
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
  if (role === "participant") {
    // Into participant (§J7 R2): only this speaker, under the number they
    // would take. Another participant is never offered — picking one would
    // join two people.
    if (!slot.person || !slot.name) return [];
    const code = personPickerNewCode({ ...slot, role, code: "p?" }, [], known);
    return [{ name: slot.name, code, person: slot.person }];
  }
  // Out of participant, the speaker's own row is not offered: a participant
  // carries no uuid to the client, so it is the team's people, or someone new.
  const others = personPickerRows({ ...slot, role, name: "", person: undefined }, known)
    .filter((r) => !(slot.person && r.person === slot.person));
  if (!slot.person || !slot.name) return others;
  const code = personPickerNewCode({ ...slot, role }, others);
  return [{ name: slot.name, code, person: slot.person }, ...others];
}

/** Whether a row can be renamed in place: the slot's own confirmed answer
 *  (§J8.8). A proposed one is confirmed first, by its own click or Return. */
export function personPickerCanRename(slot: PersonPickerSlot, row: PersonPickerRow): boolean {
  // Proposed or confirmed: a click on the name always edits it (owner, 6 Oct
  // 2026), and Return on a proposed name left as it is says yes to it.
  return !!slot.name && isOwnRow(slot, row);
}

/** What a rename in place means: a new spelling for that person everywhere;
 *  a yes, when a proposed name is left as it is; nothing when empty or
 *  unchanged. A taken name is the caller's to refuse first. */
export function personPickerRenamed(slot: PersonPickerSlot, name: string): PersonPickerChoice | null {
  const trimmed = name.trim();
  if (!trimmed) return null;
  if (trimmed === slot.name) return slot.confirmed ? null : { kind: "confirm" };
  return { kind: "name", name: trimmed };
}

/** Whether the picker shows a field for someone new. A named participant's
 *  record belongs to that one speaker, so typing a different name over theirs
 *  is the same act as renaming: no second field (owner, 6 Oct 2026). A
 *  moderator or observer keeps it — renaming Martin changes him everywhere,
 *  "someone else" must not. */
export function personPickerOffersNew(slot: PersonPickerSlot, role: PickerRole = slot.role): boolean {
  return !(role === slot.role && slot.role === "participant" && !!slot.name);
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
  /** The hint under each role a recode can browse to (§J7); the
   *  participant's carries `{{code}}`, filled by `newPromptUnder`. */
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
  /** "Swap with {{code}}" — the swap row (§J7 call 4), `{{code}}` left for
   *  the caller. */
  swapWith: string;
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
      // `{{code}}` is left for the caller, which knows the number (§J7 R2).
      participant: t("sessions.picker.newNameFor", {
        code: "{{code}}",
        interpolation: { escapeValue: false },
      }),
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
    swapWith: t("sessions.picker.swapWith", { code: "{{code}}", interpolation: { escapeValue: false } }),
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
