/**
 * Opening the person picker on a speaker, and applying what it chooses — for
 * every surface that shows one: the Sessions grid, the transcript and the
 * project dashboard (docs/design-people.md §J8.7). One copy of the rules, so
 * a pick means the same thing wherever it was made.
 *
 * Kept free of React and of the picker component: the dashboard is first
 * paint, and the picker itself is loaded only when someone opens it.
 */

import i18n from "../i18n";
import { apiGet } from "./api";
import { isExportMode } from "./exportData";
import type { SpeakerNameState } from "./peopleChanged";
import {
  personPickerNameTaken,
  type PersonPickerChoice,
  type PersonPickerRow,
  type PersonPickerSlot,
  type PersonPickerSwap,
  type PickerRole,
} from "./personPicker";
import { nameSpeaker, speakerWritesSettled, swapSpeakers } from "./speakerNames";
import { toast } from "./toast";
import type { SessionsListResponse, SpeakerResponse } from "./types";

/** Fired when a write from a picker (or its undo) has landed, so a surface
 *  that shows speakers re-reads them. */
export const SPEAKERS_WRITTEN_EVENT = "bn:speakers-written";

/** The picker's role for a speaker code (the code prefix is the role; the
 *  stored moderator role is "researcher", never "moderator"). */
export function pickerRoleOf(code: string): PickerRole {
  if (code.startsWith("m")) return "moderator";
  if (code.startsWith("o")) return "observer";
  return "participant";
}

/** How a write addresses a speaker: the slot code (`m1`, this session's
 *  first moderator), not the identity code the badge shows (`m2`). A pick
 *  can renumber identities, so a display code is never an address
 *  (docs/design-people.md §H H9, Phase 1). */
export function slotOf(sp: SpeakerResponse): string {
  return sp.slot_code ?? sp.speaker_code;
}

/** The people known for each role across the study, in first-seen order —
 *  what a picker offers (`personPickerRows`). A moderator or observer is one
 *  row per person; a participant per name. */
export function knownPeopleOf(data: SessionsListResponse | null): Record<PickerRole, PersonPickerRow[]> {
  const known: Record<PickerRole, PersonPickerRow[]> = { moderator: [], participant: [], observer: [] };
  for (const sess of data?.sessions ?? []) {
    for (const sp of sess.speakers) {
      if (!sp.name) continue;
      const list = known[pickerRoleOf(sp.speaker_code)];
      const key = sp.person || `name:${sp.name}`;
      // Confirmed if anyone said yes to this person in any session; a
      // missing flag reads as confirmed, as the grid draws it.
      const yes = sp.name_confirmed !== false;
      const seen = list.find((r) => (r.person || `name:${r.name}`) === key);
      if (seen) {
        if (yes) seen.confirmed = true;
        continue;
      }
      list.push({
        name: sp.name,
        code: sp.speaker_code,
        person: sp.person || undefined,
        full_name: sp.full_name,
        short_name: sp.short_name,
        confirmed: yes,
      });
    }
  }
  return known;
}

/** Who a speaker would swap with (§J7 call 4): in a session of exactly one
 *  participant and one moderator, the other one. Observers do not count. */
export function swapPartnerOf(
  speakers: SpeakerResponse[],
  sp: SpeakerResponse,
): PersonPickerSwap | undefined {
  const participants = speakers.filter((x) => pickerRoleOf(x.speaker_code) === "participant");
  const moderators = speakers.filter((x) => pickerRoleOf(x.speaker_code) === "moderator");
  if (participants.length !== 1 || moderators.length !== 1) return undefined;
  const other = sp === participants[0] ? moderators[0] : sp === moderators[0] ? participants[0] : undefined;
  return other ? { code: other.speaker_code, slot: slotOf(other) } : undefined;
}

/** A speaker as the picker sees it. */
export function pickerSlotOf(sp: SpeakerResponse): PersonPickerSlot {
  const name = sp.name || "";
  return {
    code: sp.speaker_code,
    role: pickerRoleOf(sp.speaker_code),
    name,
    confirmed: !(name && sp.name_confirmed === false),
    person: sp.person || undefined,
  };
}

/** What a speaker's slot holds, as an undo records it. A missing flag reads
 *  as confirmed, as the grid draws it. */
export function nameStateOf(sp: SpeakerResponse): SpeakerNameState {
  // What the speaker is now — the displayed code's role, which a recode
  // changes (§J7), not the slot's tag. A participant carries no uuid.
  const kind = pickerRoleOf(sp.speaker_code);
  return {
    full_name: sp.full_name,
    short_name: sp.short_name ?? sp.name,
    confirmed: sp.name_confirmed !== false,
    ...(kind !== "participant" ? { person: sp.person || undefined } : {}),
    // Always: an undo compares the role before and after, and a plain
    // participant's "participant" is what sends a recode's undo home.
    kind,
  };
}

/**
 * What a slot holds after a choice (§J8, answer 2). A pick writes the
 * person's own names back unchanged; someone new gets a client-made uuid,
 * so a redo finds the same person; not this person empties the slot.
 */
export function stateAfter(
  choice: PersonPickerChoice,
  before: SpeakerNameState,
  newPerson: () => string = () => crypto.randomUUID(),
): SpeakerNameState {
  switch (choice.kind) {
    case "confirm":
      return { ...before, confirmed: true };
    case "clear":
      return { full_name: "", short_name: "", confirmed: false };
    case "swap":
      // Two slots at once: the caller writes it (`swapSpeakers`).
      return before;
    case "name":
      return { ...before, short_name: choice.name, confirmed: true };
    case "person":
      return {
        person: choice.row.person,
        full_name: choice.row.full_name,
        short_name: choice.row.short_name ?? choice.row.name,
        confirmed: true,
        ...kindAfter(choice.role, before),
      };
    case "new":
      return {
        person: newPerson(),
        create: true,
        full_name: choice.name,
        short_name: choice.name,
        confirmed: true,
        ...kindAfter(choice.role, before),
      };
  }
}

/** The role a pick leaves the slot in: the one it was picked under, or the
 *  one it had (§J7). */
function kindAfter(role: PickerRole | undefined, before: SpeakerNameState): Pick<SpeakerNameState, "kind"> {
  if (role) return { kind: role };
  return before.kind ? { kind: before.kind } : {};
}

/** A name another person already goes by, refused aloud (§J8.11). */
export function refuseTakenName(name: string): void {
  toast(i18n.t("sessions.picker.nameTaken", { name }), 5000);
}

/** Whether the host draws its own picker. The Mac app says so by setting this
 *  flag in the web view; without it — the browser, or an app build from
 *  before the native picker — the web picker opens, so a click never sends a
 *  message nothing answers. */
export function hasNativePersonPicker(): boolean {
  return (window as unknown as Record<string, unknown>).__BRISTLENOSE_NATIVE_PERSON_PICKER__ === true;
}

// ---------------------------------------------------------------------------
// One speaker, read fresh, for a surface that does not hold /sessions itself
// ---------------------------------------------------------------------------

export interface SpeakerPickContext {
  sessionId: string;
  /** The slot code: how a write addresses the speaker. */
  slotCode: string;
  slot: PersonPickerSlot;
  before: SpeakerNameState;
  /** The people the picker offers for this speaker's role. */
  known: PersonPickerRow[];
  /** Everyone, by role: what a recode browses (§J7 R1). */
  knownByRole: Record<PickerRole, PersonPickerRow[]>;
  /** Who this speaker would swap with, if anyone (§J7 call 4). */
  swap?: PersonPickerSwap;
}

/** The speaker a badge shows, from /sessions as it is now: the transcript's
 *  and the dashboard's own payloads name a speaker but carry no slot address,
 *  person or flag. Null when the speaker is not (or no longer) there. */
export async function loadSpeakerContext(sessionId: string, code: string): Promise<SpeakerPickContext | null> {
  const data = await apiGet<SessionsListResponse>("/sessions");
  const speakers = data.sessions.find((s) => s.session_id === sessionId)?.speakers ?? [];
  const sp = speakers.find((x) => x.speaker_code === code);
  if (!sp) return null;
  const slot = pickerSlotOf(sp);
  const knownByRole = knownPeopleOf(data);
  return {
    sessionId, slotCode: slotOf(sp), slot, before: nameStateOf(sp), known: knownByRole[slot.role], knownByRole,
    swap: swapPartnerOf(speakers, sp),
  };
}

/** Apply a choice to a speaker read by `loadSpeakerContext`, undoably, and
 *  tell the page when it has landed. */
export function applySpeakerChoice(ctx: SpeakerPickContext, choice: PersonPickerChoice): void {
  if (isExportMode()) return;
  if (choice.kind === "swap") {
    void swapSpeakers(ctx.sessionId, ctx.slotCode, choice.slot).catch(() => undefined);
    return;
  }
  if (choice.kind === "new" || choice.kind === "name") {
    const everyone = [...ctx.knownByRole.moderator, ...ctx.knownByRole.observer];
    const role = (choice.kind === "new" && choice.role) || ctx.slot.role;
    const clash = personPickerNameTaken(ctx.slot, everyone, choice.name, role);
    if (clash) {
      refuseTakenName(clash);
      return;
    }
  }
  const after = stateAfter(choice, ctx.before);
  void nameSpeaker({ sessionId: ctx.sessionId, code: ctx.slotCode, before: ctx.before, after })
    .then(announceSpeakersWritten)
    .catch(() => undefined);
}

/** After every queued speaker write has landed, tell the page to re-read. */
export function announceSpeakersWritten(): void {
  void speakerWritesSettled().then(() => window.dispatchEvent(new CustomEvent(SPEAKERS_WRITTEN_EVENT)));
}

// ---------------------------------------------------------------------------
// The Mac app's picker: one open at a time, answered to whoever opened it
// ---------------------------------------------------------------------------

export interface NativePick {
  sessionId: string;
  /** The code the badge showed, which native echoes back. */
  code: string;
  slot: PersonPickerSlot;
  known: PersonPickerRow[];
  /** Everyone by role, so native can browse a recode (§J7 R1). */
  knownByRole?: Record<PickerRole, PersonPickerRow[]>;
  /** Who this speaker would swap with (§J7 call 4). */
  swap?: PersonPickerSwap;
  apply: (choice: PersonPickerChoice) => void;
  refuse: (name: string) => void;
}

let pending: NativePick | null = null;
let listening = false;

function onMenuAction(e: Event): void {
  const { action, payload } = (e as CustomEvent<{ action: string; payload?: unknown }>).detail;
  if (action !== "personPickerChoose" || !pending) return;
  const open = pending;
  void import("./personPickerBridge").then(({ resolvePersonPickerChoice }) => {
    const pick = resolvePersonPickerChoice(payload, (sessionId, code) =>
      sessionId === open.sessionId && code === open.code
        ? { slot: open.slot, known: open.known, knownByRole: open.knownByRole, swap: open.swap }
        : null,
    );
    if (!pick) return;
    if (pending === open) pending = null;
    if ("taken" in pick) open.refuse(pick.taken);
    else open.apply(pick.choice);
  });
}

/** Ask the Mac app for its picker over `anchor`. Its answer arrives as a
 *  menu action and is handed to the opener's `apply`; a newer open replaces
 *  an unanswered one. */
export function openNativePicker(pick: NativePick, anchor: HTMLElement): void {
  if (!listening) {
    window.addEventListener("bn:menu-action", onMenuAction);
    listening = true;
  }
  pending = pick;
  const rect = anchor.getBoundingClientRect();
  void Promise.all([import("./personPickerBridge"), import("../shims/bridge")]).then(
    ([{ buildPersonPickerMessage }, { postPersonPicker }]) =>
      postPersonPicker(
        buildPersonPickerMessage(pick.sessionId, pick.slot, pick.known, rect, i18n.t, pick.knownByRole, pick.swap),
      ),
  );
}

/** Test seam. */
export function resetNativePicker(): void {
  pending = null;
}
