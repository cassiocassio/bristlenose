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
    a.person === b.person
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

async function writeSlot(sessionId: string, code: string, state: SpeakerNameState): Promise<void> {
  if (isSessionScopedCode(code)) {
    // One request carries the whole state: the person, their names (a
    // spelling fix wherever they appear) and the flag; nobody is `clear`.
    await sendPut(
      slotPath(sessionId, code),
      state.person
        ? {
            person: state.person,
            ...(state.create ? { create: true } : {}),
            full_name: state.full_name,
            short_name: state.short_name,
            confirmed: state.confirmed,
          }
        : { clear: true },
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
  const done = enqueue(() => writeSlot(sessionId, code, after));
  pushUndo({
    action: actionFor(code, before, after),
    undo: () => {
      announce(sessionId, code, before);
      return enqueue(() => writeSlot(sessionId, code, before));
    },
    redo: () => {
      announce(sessionId, code, after);
      return enqueue(() => writeSlot(sessionId, code, after));
    },
  });
  return done;
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
