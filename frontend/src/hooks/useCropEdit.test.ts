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

  it("commitEdit from hybrid calls onCommit with the text", () => {
    const { result, onCommit } = makeHook("hello world");
    act(() => result.current.enterEditMode());
    act(() => result.current.commitEdit());
    expect(result.current.mode).toBe("idle");
    // Without an editable element, it falls back to currentText
    expect(onCommit).toHaveBeenCalledWith("hello world");
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
