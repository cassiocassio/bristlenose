/**
 * The person picker across the Mac bridge (docs/design-people.md § UX
 * iteration 3). In the Mac app a click on a speaker in the Sessions grid does
 * not open the web picker: it sends `person-picker` with everything the native
 * popover draws — the slot, the rows (`personPickerRows`, so both pickers offer
 * the same names), where the badge is, and every string already localised —
 * and the native side sends back `personPickerChoose`. Native holds no locale
 * key and no rule about what a choice means; the shapes are pinned on both
 * sides by tests/fixtures/person-picker-bridge-contract.json.
 */

import type { TFunction } from "i18next";

import {
  personPickerCanClear,
  personPickerChoice,
  personPickerLabels,
  personPickerNameTaken,
  personPickerNewCode,
  personPickerRenamed,
  personPickerRows,
  personPickerTyped,
  type PersonPickerChoice,
  type PersonPickerLabels,
  type PersonPickerRow,
  type PersonPickerSlot,
} from "./personPicker";

export interface WirePersonPicker {
  sessionId: string;
  slot: PersonPickerSlot;
  /** The rows' names, in order — the slot's own name among them when it has
   *  one. Unique within a role (§J8.11), so a name names one person. */
  names: string[];
  /** Each row's own code, parallel to `names` (§J8.8). */
  codes: string[];
  /** The code someone new would get. */
  newCode: string;
  /** The badge, in CSS pixels from the web view's top-left. */
  anchor: { x: number; y: number; width: number; height: number };
  labels: PersonPickerLabels;
}

/** What native picked: a listed row, a typed name, That's Me, the ✕, or the
 *  current row renamed in place. */
export type WireNativeChoice =
  | { kind: "confirm" }
  | { kind: "clear" }
  | { kind: "name" | "new" | "me" | "rename"; name: string };

/** What `personPickerChoose` carries back. */
export interface WirePersonPickerReply {
  sessionId: string;
  code: string;
  choice: WireNativeChoice;
}

/** A reply as the grid applies it: a choice, or a typed name another person
 *  already goes by, which the grid refuses aloud (§J8.11). */
export type ResolvedPersonPick =
  | { sessionId: string; code: string; choice: PersonPickerChoice }
  | { sessionId: string; code: string; taken: string };

export function buildPersonPickerMessage(
  sessionId: string,
  slot: PersonPickerSlot,
  known: PersonPickerRow[],
  anchor: { x: number; y: number; width: number; height: number },
  t: TFunction,
): WirePersonPicker {
  const rows = personPickerRows(slot, known);
  return {
    sessionId,
    slot,
    names: rows.map((r) => r.name),
    codes: rows.map((r) => r.code),
    newCode: personPickerNewCode(slot, rows),
    anchor: {
      x: Math.round(anchor.x),
      y: Math.round(anchor.y),
      width: Math.round(anchor.width),
      height: Math.round(anchor.height),
    },
    labels: personPickerLabels(slot, t),
  };
}

/** Read a `personPickerChoose` payload; anything malformed is null. */
export function parsePersonPickerChoice(payload: unknown): WirePersonPickerReply | null {
  if (!payload || typeof payload !== "object") return null;
  const p = payload as Record<string, unknown>;
  const choice = p.choice as Record<string, unknown> | undefined;
  if (typeof p.sessionId !== "string" || typeof p.code !== "string" || !choice) return null;
  if (choice.kind === "confirm") return { sessionId: p.sessionId, code: p.code, choice: { kind: "confirm" } };
  if (choice.kind === "clear") return { sessionId: p.sessionId, code: p.code, choice: { kind: "clear" } };
  const kind = choice.kind;
  if (
    (kind === "name" || kind === "new" || kind === "me" || kind === "rename") &&
    typeof choice.name === "string" &&
    choice.name.trim()
  ) {
    return { sessionId: p.sessionId, code: p.code, choice: { kind, name: choice.name.trim() } };
  }
  return null;
}

/**
 * Native's pick as the grid applies it. Native sends a name and which row it
 * came from; what it means is decided here, by the web picker's own rules,
 * against the slot and rows as the grid holds them now:
 * - `name`: the listed person by that name (a yes, if it is the slot's own);
 * - `new`: someone new — refused if another person already goes by it;
 * - `me`: the listed person by the account's name, else someone new;
 * - `clear`: not this person, where the slot has someone to refuse;
 * - `rename`: a new spelling for the current person, refused if taken.
 */
export function resolvePersonPickerChoice(
  payload: unknown,
  slotFor: (sessionId: string, code: string) => { slot: PersonPickerSlot; known: PersonPickerRow[] } | null,
): ResolvedPersonPick | null {
  const pick = parsePersonPickerChoice(payload);
  if (!pick) return null;
  const { sessionId, code } = pick;
  if (pick.choice.kind === "confirm") return { sessionId, code, choice: { kind: "confirm" } };
  const found = slotFor(sessionId, code);
  if (!found) return null;
  const { slot } = found;
  if (pick.choice.kind === "clear") {
    return personPickerCanClear(slot) ? { sessionId, code, choice: { kind: "clear" } } : null;
  }
  const rows = personPickerRows(slot, found.known);
  const { kind, name } = pick.choice;
  if (kind === "rename") {
    const clash = personPickerNameTaken(slot, rows, name);
    if (clash) return { sessionId, code, taken: clash };
    const choice = personPickerRenamed(slot, name);
    return choice ? { sessionId, code, choice } : null;
  }
  const listed = rows.find((r) => r.name === name);
  if (kind === "name" || (kind === "me" && listed)) {
    const choice = listed ? personPickerChoice(slot, listed) : null;
    return choice ? { sessionId, code, choice } : null;
  }
  const clash = personPickerNameTaken(slot, rows, name);
  if (clash) return { sessionId, code, taken: clash };
  const choice = personPickerTyped(slot, name);
  return choice ? { sessionId, code, choice } : null;
}
