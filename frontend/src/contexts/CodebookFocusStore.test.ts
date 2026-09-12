/**
 * CodebookFocusStore — the codebook detail pane's cursor.
 *
 * These pin the three things that are decisions rather than plumbing: the
 * cursor is *one* cursor, it does not survive its target being deleted, and a
 * command fires once for the components that were mounted when it was issued.
 */

import { renderHook, act } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearCodebookFocus,
  focusCodebookGroup,
  focusCodebookTag,
  getCodebookFocus,
  reconcileCodebookFocus,
  resetCodebookFocus,
  sendCodebookCommand,
  useCodebookCommand,
  useCodebookFocus,
} from "./CodebookFocusStore";

const EDITABLE = { editable: true, acceptsTags: true };
const FLOOR_DEFAULT = { editable: false, acceptsTags: true };

beforeEach(() => {
  resetCodebookFocus();
});

describe("one cursor, not two", () => {
  it("focusing a group clears a focused code", () => {
    focusCodebookTag(7, 1, EDITABLE);
    expect(getCodebookFocus().focusedTagId).toBe(7);

    focusCodebookGroup(2, EDITABLE);

    expect(getCodebookFocus().focusedGroupId).toBe(2);
    // Without this, moving the cursor to a group would leave a chip from the
    // group you just left reporting as focused, and Delete Code would be lit
    // over it.
    expect(getCodebookFocus().focusedTagId).toBeNull();
  });

  it("focusing a code also focuses its group", () => {
    focusCodebookTag(7, 3, EDITABLE);
    expect(getCodebookFocus().focusedGroupId).toBe(3);
    expect(getCodebookFocus().focusedTagId).toBe(7);
  });

  it("clearing drops both and every capability", () => {
    focusCodebookTag(7, 3, EDITABLE);
    clearCodebookFocus();
    const s = getCodebookFocus();
    expect(s.focusedGroupId).toBeNull();
    expect(s.focusedTagId).toBeNull();
    expect(s.focusedGroupEditable).toBe(false);
    expect(s.focusedGroupAcceptsTags).toBe(false);
  });
});

describe("capabilities are two flags, not one", () => {
  it("carries a group that takes codes but cannot be renamed", () => {
    // `Uncategorised`: read-only as a group, still the bucket unfiled codes
    // land in. One flag here would dim New Code over a card that offers it.
    focusCodebookGroup(1, FLOOR_DEFAULT);
    expect(getCodebookFocus().focusedGroupEditable).toBe(false);
    expect(getCodebookFocus().focusedGroupAcceptsTags).toBe(true);
  });
});

describe("reconcile — absence is the one thing a cursor cannot notice", () => {
  it("drops a group that is gone, and the code inside it", () => {
    focusCodebookTag(7, 3, EDITABLE);
    reconcileCodebookFocus(new Set([1, 2]), new Set([7]));
    const s = getCodebookFocus();
    expect(s.focusedGroupId).toBeNull();
    expect(s.focusedTagId).toBeNull();
    expect(s.focusedGroupEditable).toBe(false);
  });

  it("drops a code that is gone but keeps its group", () => {
    focusCodebookTag(7, 3, EDITABLE);
    reconcileCodebookFocus(new Set([3]), new Set([8, 9]));
    expect(getCodebookFocus().focusedGroupId).toBe(3);
    expect(getCodebookFocus().focusedTagId).toBeNull();
  });

  it("leaves a live cursor alone", () => {
    focusCodebookTag(7, 3, EDITABLE);
    reconcileCodebookFocus(new Set([3]), new Set([7]));
    expect(getCodebookFocus().focusedGroupId).toBe(3);
    expect(getCodebookFocus().focusedTagId).toBe(7);
  });
});

describe("useCodebookCommand", () => {
  it("fires for a matching command, once", () => {
    const spy = vi.fn();
    renderHook(() =>
      useCodebookCommand("renameGroup", (c) => c.kind === "renameGroup" && c.groupId === 3, spy),
    );

    act(() => sendCodebookCommand({ kind: "renameGroup", groupId: 3 }));
    expect(spy).toHaveBeenCalledTimes(1);

    // An unrelated focus change re-renders every subscriber; the seq guard is
    // what stops that re-opening the editor.
    act(() => focusCodebookGroup(9, EDITABLE));
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("fires again for a second identical command", () => {
    const spy = vi.fn();
    renderHook(() =>
      useCodebookCommand("renameGroup", (c) => c.kind === "renameGroup" && c.groupId === 3, spy),
    );
    act(() => sendCodebookCommand({ kind: "renameGroup", groupId: 3 }));
    act(() => sendCodebookCommand({ kind: "renameGroup", groupId: 3 }));
    // "Rename this group" twice is two instructions. A boolean flag would have
    // swallowed the second.
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it("ignores another group's command, and another kind", () => {
    const spy = vi.fn();
    renderHook(() =>
      useCodebookCommand("renameGroup", (c) => c.kind === "renameGroup" && c.groupId === 3, spy),
    );
    act(() => sendCodebookCommand({ kind: "renameGroup", groupId: 4 }));
    act(() => sendCodebookCommand({ kind: "addTag", groupId: 3 }));
    expect(spy).not.toHaveBeenCalled();
  });

  it("does NOT fire for a command issued before it mounted", () => {
    // The refetch that follows a rename remounts every group card. Seeded from
    // 0 instead of the current seq, each fresh card would treat the spent
    // command as new and re-open its editor — a rename you cannot dismiss.
    act(() => sendCodebookCommand({ kind: "renameGroup", groupId: 3 }));

    const spy = vi.fn();
    renderHook(() =>
      useCodebookCommand("renameGroup", (c) => c.kind === "renameGroup" && c.groupId === 3, spy),
    );

    expect(spy).not.toHaveBeenCalled();
  });

  it("still fires for the next command after mounting late", () => {
    act(() => sendCodebookCommand({ kind: "renameGroup", groupId: 3 }));
    const spy = vi.fn();
    renderHook(() =>
      useCodebookCommand("renameGroup", (c) => c.kind === "renameGroup" && c.groupId === 3, spy),
    );
    act(() => sendCodebookCommand({ kind: "renameGroup", groupId: 3 }));
    expect(spy).toHaveBeenCalledTimes(1);
  });
});

describe("useCodebookFocus", () => {
  it("re-renders subscribers on a focus change", () => {
    const { result } = renderHook(() => useCodebookFocus());
    expect(result.current.focusedGroupId).toBeNull();
    act(() => focusCodebookGroup(5, EDITABLE));
    expect(result.current.focusedGroupId).toBe(5);
  });

  it("does not notify when nothing actually changed", () => {
    let renders = 0;
    renderHook(() => {
      renders += 1;
      return useCodebookFocus();
    });
    const baseline = renders;
    act(() => focusCodebookGroup(5, EDITABLE));
    const afterFirst = renders;
    act(() => focusCodebookGroup(5, EDITABLE));
    expect(renders).toBe(afterFirst);
    expect(afterFirst).toBeGreaterThan(baseline);
  });
});
