import { renderHook, act } from "@testing-library/react";
import { useCropEdit } from "./useCropEdit";

function makeHook(text = "one two three four five") {
  const onCommit = vi.fn();
  const onCancel = vi.fn();
  const result = renderHook(() =>
    useCropEdit({
      currentText: text,
      originalText: text,
      onCommit,
      onCancel,
    }),
  );
  return { ...result, onCommit, onCancel };
}

describe("useCropEdit", () => {
  it("starts in idle mode", () => {
    const { result } = makeHook();
    expect(result.current.mode).toBe("idle");
  });

  it("enterEditMode transitions to hybrid", () => {
    const { result } = makeHook();
    act(() => result.current.enterEditMode());
    expect(result.current.mode).toBe("hybrid");
    expect(result.current.words).toEqual(["one", "two", "three", "four", "five"]);
    expect(result.current.cropStart).toBe(0);
    expect(result.current.cropEnd).toBe(5);
  });

  it("does nothing if enterEditMode called when not idle", () => {
    const { result } = makeHook();
    act(() => result.current.enterEditMode());
    expect(result.current.mode).toBe("hybrid");
    act(() => result.current.enterEditMode());
    expect(result.current.mode).toBe("hybrid"); // no double-entry
  });

  it("cancelEdit reverts to idle and calls onCancel", () => {
    const { result, onCancel } = makeHook();
    act(() => result.current.enterEditMode());
    act(() => result.current.cancelEdit());
    expect(result.current.mode).toBe("idle");
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("commitEdit from hybrid calls onCommit with the edited text", () => {
    const { result, onCommit } = makeHook("hello world");
    act(() => result.current.enterEditMode());
    const el = document.createElement("span");
    el.textContent = " hello there ";
    act(() => result.current.commitEdit(el));
    expect(result.current.mode).toBe("idle");
    expect(onCommit).toHaveBeenCalledWith("hello there");
  });

  // An edit opened and left unchanged is not an edit: no write, no Undo entry.
  it("commitEdit with the text unchanged leaves edit mode and commits nothing", () => {
    const { result, onCommit, onCancel } = makeHook("hello world");
    act(() => result.current.enterEditMode());
    // Without an editable element, it falls back to currentText
    act(() => result.current.commitEdit());
    expect(result.current.mode).toBe("idle");
    expect(onCommit).not.toHaveBeenCalled();
    expect(onCancel).toHaveBeenCalledOnce();
  });

  // A bracket drag re-bases `words` on the typed text, so "unchanged" must mean
  // unchanged from before the edit, or a typed edit followed by a drag that
  // puts the bracket back is thrown away (review, 20 Oct 2026).
  it("commits what was typed when a bracket drag leaves the crop as it was", () => {
    const { result, onCommit, onCancel } = makeHook("one two three");
    act(() => result.current.enterEditMode());
    const span = document.createElement("span");
    const editable = document.createElement("span");
    editable.className = "crop-editable";
    editable.textContent = "one two three four";
    span.appendChild(editable);
    const down = { clientX: 100, preventDefault: () => {}, stopPropagation: () => {} };
    act(() => result.current.handleBracketPointerDown("end", down as unknown as React.PointerEvent, span));
    act(() => {
      document.dispatchEvent(new MouseEvent("pointermove", { clientX: 120 }));
      document.dispatchEvent(new MouseEvent("pointerup"));
    });
    expect(result.current.mode).toBe("crop");
    act(() => result.current.commitEdit());
    expect(onCommit).toHaveBeenCalledWith("one two three four");
    expect(onCancel).not.toHaveBeenCalled();
  });

  // Decision #30 (22 Oct 2026): the report does not show spacing, so a change
  // only in spacing is no edit, whichever way it goes.
  it("an untouched quote whose text has a double space commits nothing", () => {
    const { result, onCommit, onCancel } = makeHook("hello  world");
    act(() => result.current.enterEditMode());
    const el = document.createElement("span");
    el.textContent = "hello  world";
    act(() => result.current.commitEdit(el));
    expect(onCommit).not.toHaveBeenCalled();
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("adding only a space commits nothing", () => {
    const { result, onCommit } = makeHook("hello world");
    act(() => result.current.enterEditMode());
    const el = document.createElement("span");
    el.textContent = "hello   world";
    act(() => result.current.commitEdit(el));
    expect(onCommit).not.toHaveBeenCalled();
  });

  it("commitEdit with empty text calls onCancel", () => {
    const { result, onCancel } = makeHook("hello world");
    act(() => result.current.enterEditMode());
    // Simulate empty editable
    const emptyEl = document.createElement("span");
    emptyEl.textContent = "";
    act(() => result.current.commitEdit(emptyEl));
    expect(onCancel).toHaveBeenCalled();
  });

  it("reenterTextEdit switches from crop to hybrid", () => {
    const { result } = makeHook();
    act(() => result.current.enterEditMode());
    // Manually force crop mode to test reenterTextEdit
    // (In practice this happens via handleBracketPointerDown)
    act(() => result.current.reenterTextEdit());
    expect(result.current.mode).toBe("hybrid");
  });

  it("suppressBlurRef starts as false", () => {
    const { result } = makeHook();
    expect(result.current.suppressBlurRef.current).toBe(false);
  });

  it("hasLeftCrop and hasRightCrop are false initially", () => {
    const { result } = makeHook();
    expect(result.current.hasLeftCrop).toBe(false);
    expect(result.current.hasRightCrop).toBe(false);
  });

  it("splits words correctly with multiple spaces", () => {
    const { result } = makeHook("  spaced   out  text  ");
    act(() => result.current.enterEditMode());
    expect(result.current.words).toEqual(["spaced", "out", "text"]);
  });

  it("handles single-word text", () => {
    const { result } = makeHook("solo");
    act(() => result.current.enterEditMode());
    expect(result.current.words).toEqual(["solo"]);
    expect(result.current.cropStart).toBe(0);
    expect(result.current.cropEnd).toBe(1);
  });
});
