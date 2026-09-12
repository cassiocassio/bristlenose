/**
 * CodebookFocusStore — the focus cursor for the codebook detail pane.
 *
 * Modelled on `AnalysisSignalStore`: a module-level store over
 * `useSyncExternalStore`, holding one nullable id per focusable kind. Read by
 * the group card and the tag chip (for the `bn-selected` wash) and by
 * `AppLayout` (to tell the native menu what to dim).
 *
 * **Focus is not selection.** `design-codebook-v2.md` pins selection as single,
 * living in the master list, which selects a *codebook*; the detail pane is a
 * pure function of it. That pin is about selection and does not forbid a cursor
 * inside the pane — the app already ships two (`FocusContext.focusedId` for
 * quotes, `AnalysisSignalStore.focusedKey` for signal cards), and
 * `FocusContext`'s own docstring separates the axes in its first three lines.
 * See `design-codebook-focus.md`.
 *
 * @module CodebookFocusStore
 */

import { useEffect, useRef, useSyncExternalStore } from "react";

// ── Types ────────────────────────────────────────────────────────────────

/**
 * A one-shot instruction to the component that owns a focused thing.
 *
 * Every one of these has to be executed by the component that owns the target,
 * because what they do is *open* something the card owns: Rename opens the
 * inline field, New Code opens the group's own TagInput, and **Delete opens the
 * confirmation** — `handleRequestDeleteGroup` skips the dialog only when the
 * group is empty, and `handleRequestDeleteTag` only when the tag is on no
 * quotes and carries no pending proposals. Calling `onDeleteGroup` straight
 * from the menu would therefore delete a full group without asking, which is
 * the one difference between the menu and its on-card twin that would actually
 * cost a researcher something. So commands ride the store as a value with a
 * monotonic `seq`, and `useCodebookCommand` fires a callback once per new one.
 *
 * A plain boolean would not work: "rename the focused group" twice in a row is
 * two instructions, and the second must still fire after the first has been
 * consumed and the flag reset.
 *
 * New Code Group is absent on purpose — `onCreateGroup` mints a group with a
 * generated name and opens no editor, so the menu calls it directly.
 */
export type CodebookCommand =
  | { kind: "renameGroup"; groupId: number }
  | { kind: "deleteGroup"; groupId: number }
  | { kind: "renameTag"; tagId: number }
  | { kind: "deleteTag"; tagId: number }
  | { kind: "addTag"; groupId: number };

/**
 * What the focused group permits. Passed in by the card rather than derived
 * here: the card already computes these from the group's own shape, and a
 * second derivation is a second thing to drift.
 */
export interface GroupCapabilities {
  /** Rename / delete the group itself — the card's `!isReadOnly`. */
  editable: boolean;
  /** Add a code to it — the card's `!isFramework && !isExportMode()`. */
  acceptsTags: boolean;
}

export interface CodebookFocusState {
  /** Focused group, or null. Set by clicking a group card's background. */
  focusedGroupId: number | null;
  /** Focused code, or null. Set by clicking a chip. */
  focusedTagId: number | null;
  /**
   * Whether the focused group's own structure can be renamed or deleted.
   * Mirrors `isReadOnly` in `CodebookGroupColumn` — false for a framework
   * group, the floor's `Uncategorised`, sentiment, and an exported report.
   */
  focusedGroupEditable: boolean;
  /**
   * Whether the focused group accepts new codes. **Deliberately not the same
   * flag**: the card gates its add-tag row on `!isFramework` while gating
   * rename/delete on `isReadOnly`, so `Uncategorised` — read-only as a group —
   * still takes tags, which is right, since it is the bucket everything
   * unfiled lands in. Mirroring one flag onto both menu items would have
   * dimmed New Code over a group whose own card offers it.
   */
  focusedGroupAcceptsTags: boolean;
  /** The pending one-shot command, or null. */
  command: (CodebookCommand & { seq: number }) | null;
}

// ── Module-level store ──────────────────────────────────────────────────

const INITIAL: CodebookFocusState = {
  focusedGroupId: null,
  focusedTagId: null,
  focusedGroupEditable: false,
  focusedGroupAcceptsTags: false,
  command: null,
};

let state: CodebookFocusState = { ...INITIAL };
let seq = 0;
const listeners = new Set<() => void>();

function getSnapshot(): CodebookFocusState {
  return state;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function setState(updater: (prev: CodebookFocusState) => CodebookFocusState): void {
  const next = updater(state);
  if (next === state) return;
  state = next;
  listeners.forEach((l) => l());
}

// ── Actions ─────────────────────────────────────────────────────────────

/**
 * Focus a group. Clears any focused code — the two are one cursor, not two,
 * so focusing a group and then reading `focusedTagId` must not return a chip
 * from the group you just left.
 */
export function focusCodebookGroup(groupId: number, caps: GroupCapabilities): void {
  setState((prev) =>
    prev.focusedGroupId === groupId
      && prev.focusedTagId === null
      && prev.focusedGroupEditable === caps.editable
      && prev.focusedGroupAcceptsTags === caps.acceptsTags
      ? prev
      : {
          ...prev,
          focusedGroupId: groupId,
          focusedTagId: null,
          focusedGroupEditable: caps.editable,
          focusedGroupAcceptsTags: caps.acceptsTags,
        },
  );
}

/** Focus a code, and the group that holds it. */
export function focusCodebookTag(
  tagId: number,
  groupId: number,
  caps: GroupCapabilities,
): void {
  setState((prev) =>
    prev.focusedTagId === tagId
      && prev.focusedGroupId === groupId
      && prev.focusedGroupEditable === caps.editable
      && prev.focusedGroupAcceptsTags === caps.acceptsTags
      ? prev
      : {
          ...prev,
          focusedTagId: tagId,
          focusedGroupId: groupId,
          focusedGroupEditable: caps.editable,
          focusedGroupAcceptsTags: caps.acceptsTags,
        },
  );
}

/** Clear the cursor — a click on empty pane, or Escape. */
export function clearCodebookFocus(): void {
  setState((prev) =>
    prev.focusedGroupId === null && prev.focusedTagId === null
      ? prev
      : {
          ...prev,
          focusedGroupId: null,
          focusedTagId: null,
          focusedGroupEditable: false,
          focusedGroupAcceptsTags: false,
        },
  );
}

/** Issue a one-shot command. See `CodebookCommand`. */
export function sendCodebookCommand(command: CodebookCommand): void {
  seq += 1;
  const stamped = { ...command, seq };
  setState((prev) => ({ ...prev, command: stamped }));
}

/**
 * Drop focus on a group that no longer exists.
 *
 * Called after a delete, and after a refetch: absence is the one thing the
 * cursor cannot notice on its own, and a cursor pointing at a deleted group
 * leaves the menu lit over nothing — the exact shape of the dead commands this
 * whole feature replaces.
 */
export function reconcileCodebookFocus(
  liveGroupIds: ReadonlySet<number>,
  liveTagIds: ReadonlySet<number>,
): void {
  setState((prev) => {
    const groupGone = prev.focusedGroupId !== null && !liveGroupIds.has(prev.focusedGroupId);
    const tagGone = prev.focusedTagId !== null && !liveTagIds.has(prev.focusedTagId);
    if (!groupGone && !tagGone) return prev;
    return {
      ...prev,
      focusedGroupId: groupGone ? null : prev.focusedGroupId,
      focusedTagId: groupGone || tagGone ? null : prev.focusedTagId,
      focusedGroupEditable: groupGone ? false : prev.focusedGroupEditable,
      focusedGroupAcceptsTags: groupGone ? false : prev.focusedGroupAcceptsTags,
    };
  });
}

/**
 * Test-only reset — module state outlives a test otherwise.
 *
 * **Deliberately does NOT rewind `seq`.** Rewinding it to 0 while mounted
 * consumers still hold a high `lastSeq` makes every subsequent command fail
 * the `seq <= lastSeq` guard — so the menu silently stops working until the
 * counter climbs back, with no error and no log. That is the exact failure
 * `useCodebookCommand`'s guard exists to prevent, reintroduced by the escape
 * hatch meant to help test it. The counter is monotonic for the life of the
 * module; nothing reads its absolute value.
 */
export function resetCodebookFocus(): void {
  state = { ...INITIAL };
  listeners.forEach((l) => l());
}

// ── Hooks ───────────────────────────────────────────────────────────────

export function useCodebookFocus(): CodebookFocusState {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

/**
 * Run `handler` once for each command of `kind` that `match` accepts.
 *
 * The `seq` guard is what makes it once-per-command rather than once-per-render:
 * the effect re-runs on every store change, and without the ref it would
 * re-open an editor each time an unrelated group took focus.
 *
 * `handler` is deliberately read from a ref rather than listed as a dependency.
 * Callers pass an inline closure (`() => setIsAddingTag(true)`), which is a new
 * function every render; as a dependency it would re-run the effect on every
 * render, and the `seq` guard would then be the only thing standing between
 * this and an infinite open/close loop. Guarding on `seq` alone, and reading
 * the latest handler through a ref, means the two are independent.
 */
export function useCodebookCommand(
  kind: CodebookCommand["kind"],
  match: (command: CodebookCommand) => boolean,
  handler: () => void,
): void {
  const { command } = useCodebookFocus();
  // Seeded from the CURRENT seq, not 0. A group card that mounts after a
  // command was issued — every card does, on the refetch that follows a
  // rename — would otherwise treat that spent command as new and re-open its
  // editor. Seeding means a component only answers commands issued while it
  // was on screen. Pinned by "does NOT fire for a command issued before it
  // mounted", which goes red against `useRef(0)`.
  const lastSeq = useRef(getCodebookFocus().command?.seq ?? 0);

  // `handler` and `match` are listed as dependencies even though callers pass
  // inline closures, so the effect re-runs on every render. That is harmless
  // and deliberate: the `seq` guard returns early for a command already
  // consumed, so a re-run costs one comparison. The alternative — holding them
  // in refs written during render — is what `react-hooks/refs` forbids, and
  // the ref version only *looked* cheaper.
  useEffect(() => {
    if (!command || command.seq <= lastSeq.current) return;
    if (command.kind !== kind) return;
    if (!match(command)) return;
    lastSeq.current = command.seq;
    handler();
  }, [command, kind, match, handler]);
}

/** Non-reactive read, for event handlers and the bridge. */
export function getCodebookFocus(): CodebookFocusState {
  return state;
}
