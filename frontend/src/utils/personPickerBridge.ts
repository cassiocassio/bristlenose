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
  personPickerChoice,
  personPickerLabels,
  personPickerRows,
  type PersonPickerChoice,
  type PersonPickerLabels,
  type PersonPickerSlot,
} from "./personPicker";

export interface WirePersonPicker {
  sessionId: string;
  slot: PersonPickerSlot;
  /** The rows, in order — the slot's own name among them when it has one. */
  names: string[];
  /** The badge, in CSS pixels from the web view's top-left. */
  anchor: { x: number; y: number; width: number; height: number };
  labels: PersonPickerLabels;
}

/** What `personPickerChoose` carries back. */
export interface WirePersonPickerChoice {
  sessionId: string;
  code: string;
  choice: PersonPickerChoice;
}

export function buildPersonPickerMessage(
  sessionId: string,
  slot: PersonPickerSlot,
  knownNames: string[],
  anchor: { x: number; y: number; width: number; height: number },
  t: TFunction,
): WirePersonPicker {
  return {
    sessionId,
    slot,
    names: personPickerRows(slot, knownNames),
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
export function parsePersonPickerChoice(payload: unknown): WirePersonPickerChoice | null {
  if (!payload || typeof payload !== "object") return null;
  const p = payload as Record<string, unknown>;
  const choice = p.choice as Record<string, unknown> | undefined;
  if (typeof p.sessionId !== "string" || typeof p.code !== "string" || !choice) return null;
  if (choice.kind === "confirm") return { sessionId: p.sessionId, code: p.code, choice: { kind: "confirm" } };
  if (choice.kind === "name" && typeof choice.name === "string" && choice.name.trim()) {
    return { sessionId: p.sessionId, code: p.code, choice: { kind: "name", name: choice.name.trim() } };
  }
  return null;
}

/**
 * Native's pick as the grid applies it. The native picker sends the name that
 * was picked; what it means — a yes to the slot's own proposed name, a rename,
 * or nothing — is decided here with `personPickerChoice`, the rule the web
 * picker uses, against the slot as the grid holds it now.
 */
export function resolvePersonPickerChoice(
  payload: unknown,
  slotFor: (sessionId: string, code: string) => PersonPickerSlot | null,
): WirePersonPickerChoice | null {
  const pick = parsePersonPickerChoice(payload);
  if (!pick || pick.choice.kind === "confirm") return pick;
  const slot = slotFor(pick.sessionId, pick.code);
  if (!slot) return null;
  const choice = personPickerChoice(slot, pick.choice.name);
  return choice ? { sessionId: pick.sessionId, code: pick.code, choice } : null;
}
