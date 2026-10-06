/**
 * Naming a speaker, undoably (docs/design-people.md §B10).
 *
 * Every way a researcher names a speaker slot — a pick or a confirm in the
 * person picker (web or native), a typed new name, the Sessions grid's inline
 * rename — goes through `nameSpeaker`, which writes the slot and records one
 * entry on the report's undo stack. Undo puts the slot back to exactly what it
 * held: both stored names and the confirmed state, so undoing a confirm
 * returns the name to proposed.
 *
 * Two write paths, because the server has two:
 * - a moderator or observer is named per session, and one
 *   `PUT …/sessions/{sid}/speakers/{code}` carries the whole state;
 * - a participant is named through `PUT /people`, which is written through to
 *   `people.yaml` so a re-run keeps the name. That route can only confirm, so
 *   the flag follows on the per-session route.
 *
 * Writes go through one queue, so an undo pressed while the act it reverses is
 * still in flight lands after it rather than racing it.
 */

import { getPeople, isSessionScopedCode, sendPut } from "./api";
import { isExportMode } from "./exportData";
import { pushUndo } from "../contexts/UndoStore";
import {
  PEOPLE_CHANGED_EVENT,
  type PeopleChangedDetail,
  type SpeakerNameState,
} from "./peopleChanged";

export { PEOPLE_CHANGED_EVENT, type PeopleChangedDetail, type SpeakerNameState };

/** The act, as Edit ▸ Undo names it (`undo.undo.<action>`). */
export function actionFor(code: string, before: SpeakerNameState, after: SpeakerNameState): string {
  if (isSessionScopedCode(code) && before.person && !after.person) return "clearName";
  if (before.kind && after.kind && before.kind !== after.kind) return "changeRole";
  const renamed =
    before.full_name !== after.full_name || before.short_name !== after.short_name;
  if (!renamed) return "confirmName";
  if (code.startsWith("m")) return "renameModerator";
  if (code.startsWith("o")) return "renameObserver";
  return "renameParticipant";
}

function sameState(a: SpeakerNameState, b: SpeakerNameState): boolean {
  return (
    a.full_name === b.full_name &&
    a.short_name === b.short_name &&
    a.confirmed === b.confirmed &&
    a.person === b.person &&
    a.kind === b.kind
  );
}

let queue: Promise<void> = Promise.resolve();

function enqueue(write: () => Promise<void>): Promise<void> {
  const next = queue.then(write);
  // A failed write has already told the researcher (sendPut toasts); the
  // queue must outlive it or every later write would be skipped.
  queue = next.catch(() => undefined);
  return next;
}

function slotPath(sessionId: string, code: string): string {
  return `/sessions/${encodeURIComponent(sessionId)}/speakers/${encodeURIComponent(code)}`;
}

/** Whether a write goes through the slot's own route: every moderator or
 *  observer, every speaker whose role a recode changes or changed (§J7), and
 *  never a plain participant, whose name is written through to people.yaml. */
function viaSlot(code: string, state: SpeakerNameState, other: SpeakerNameState): boolean {
  return (
    isSessionScopedCode(code) ||
    (state.kind !== undefined && state.kind !== "participant") ||
    state.kind !== other.kind
  );
}

async function writeSlot(
  sessionId: string,
  code: string,
  state: SpeakerNameState,
  other: SpeakerNameState,
): Promise<void> {
  if (viaSlot(code, state, other)) {
    // One request carries the whole state: the person, their names (a
    // spelling fix wherever they appear) and the flag; nobody is `clear`.
    // A participant carries no uuid, so back to participant names the role
    // alone, and the server points the slot at the participant it held.
    const kind = state.kind ? { kind: state.kind } : {};
    await sendPut(
      slotPath(sessionId, code),
      state.person
        ? {
            person: state.person,
            ...(state.create ? { create: true } : {}),
            ...kind,
            full_name: state.full_name,
            short_name: state.short_name,
            confirmed: state.confirmed,
          }
        : state.kind === "participant"
          ? { kind: "participant", full_name: state.full_name, short_name: state.short_name, confirmed: state.confirmed }
          : { clear: true, ...kind },
    );
    return;
  }
  // Fresh, not the caller's copy: by the time an undo runs, other
  // participants may have been renamed, and only this one is going back.
  const people = await getPeople();
  const entry = people[code] ?? { full_name: "", short_name: "", role: "" };
  const full_name = state.full_name ?? entry.full_name;
  if (entry.full_name !== full_name || entry.short_name !== state.short_name) {
    await sendPut("/people", {
      ...people,
      [code]: { ...entry, full_name, short_name: state.short_name },
    });
  }
  await sendPut(slotPath(sessionId, code), { confirmed: state.confirmed });
}

function announce(sessionId: string, code: string, state: SpeakerNameState): void {
  window.dispatchEvent(
    new CustomEvent<PeopleChangedDetail>(PEOPLE_CHANGED_EVENT, {
      detail: { sessionId, code, state },
    }),
  );
}

export interface NameSpeakerArgs {
  sessionId: string;
  code: string;
  before: SpeakerNameState;
  after: SpeakerNameState;
}

/**
 * Write a speaker slot and make the write undoable. A no-op when nothing
 * changes. Resolves when the forward write has landed (callers may ignore it).
 */
export function nameSpeaker({ sessionId, code, before, after }: NameSpeakerArgs): Promise<void> {
  if (isExportMode() || sameState(before, after)) return Promise.resolve();
  const done = enqueue(() => writeSlot(sessionId, code, after, before));
  pushUndo({
    action: actionFor(code, before, after),
    undo: () => {
      announce(sessionId, code, before);
      return enqueue(() => writeSlot(sessionId, code, before, after));
    },
    redo: () => {
      announce(sessionId, code, after);
      return enqueue(() => writeSlot(sessionId, code, after, before));
    },
  });
  return done;
}

/**
 * Swap two of one session's speakers (§J7 call 4): their roles and people
 * change places in one write, and the undo is the same write again. Views
 * re-read afterwards (`bn:speakers-written`): two slots changed, and only the
 * server knows the codes they now show.
 */
export function swapSpeakers(sessionId: string, code: string, other: string): Promise<void> {
  if (isExportMode()) return Promise.resolve();
  const write = () =>
    enqueue(() => sendPut(slotPath(sessionId, code), { swap_with: other })).then(written);
  // Recorded once the swap has landed: its undo is the same write, so an
  // entry for a refused swap would perform it on ⌘Z.
  return write().then(() => pushUndo({ action: "swapRoles", undo: write, redo: write }));
}

function written(): void {
  window.dispatchEvent(new CustomEvent("bn:speakers-written"));
}

/** Resolves when every queued write has landed (or failed), so a view can
 *  re-read what the server renumbered. */
export function speakerWritesSettled(): Promise<void> {
  return queue;
}

/** Test seam: drop any queued writes' ordering. */
export function resetSpeakerNameQueue(): void {
  queue = Promise.resolve();
}
