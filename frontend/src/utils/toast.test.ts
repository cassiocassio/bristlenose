import { act } from "@testing-library/react";
import { announce } from "./announce";
import { _resetToast, toast } from "./toast";

vi.mock("./announce", () => ({ announce: vi.fn() }));

const mockAnnounce = vi.mocked(announce);

describe("toast", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    act(() => _resetToast());
  });

  it("speaks its message, since a toast is often the only sign an action happened", () => {
    act(() => toast("Copied"));
    expect(mockAnnounce).toHaveBeenCalledTimes(1);
    expect(mockAnnounce).toHaveBeenCalledWith("Copied");
  });

  it("speaks the bare message, never the kind's glyph", () => {
    act(() => toast("Couldn't save", 4000, "error"));
    expect(mockAnnounce).toHaveBeenCalledWith("Couldn't save");
  });
});

describe("toast, what stays on screen", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    act(() => _resetToast());
    vi.clearAllMocks();
  });
  afterEach(() => {
    act(() => _resetToast());
    vi.useRealTimers();
  });

  const shown = () => document.querySelector('[data-testid="bn-toast"]');

  it("a failure is not erased by a confirmation fired while it is up", () => {
    act(() => toast("Couldn't save your change", undefined, "error"));
    act(() => vi.advanceTimersByTime(1500));
    act(() => toast("47 quotes copied"));
    expect(shown()?.textContent).toContain("Couldn't save your change");
    expect(shown()?.getAttribute("data-kind")).toBe("error");
  });

  it("nor is a warning, and the confirmation is still spoken", () => {
    act(() => toast("Clips contain original audio.", undefined, "warning"));
    act(() => toast("Copied", undefined, "success"));
    expect(shown()?.textContent).toContain("Clips contain original audio.");
    expect(mockAnnounce).toHaveBeenCalledWith("Copied");
  });

  it("but a newer answer that carries information does replace a failure", () => {
    act(() => toast("Export failed", undefined, "error"));
    act(() => toast("No quotes match current filters", undefined, "info"));
    expect(shown()?.textContent).toContain("No quotes match current filters");
  });

  it("a failure replaces a confirmation, and one failure replaces another", () => {
    act(() => toast("Copied"));
    act(() => toast("Export failed", undefined, "error"));
    expect(shown()?.textContent).toContain("Export failed");
    act(() => toast("Couldn't show the folder.", undefined, "error"));
    expect(shown()?.textContent).toContain("Couldn't show the folder.");
  });

  it("a confirmation shows once the failure has gone", () => {
    act(() => toast("Export failed", undefined, "error")); // 6 s, then a 300 ms fade
    act(() => vi.advanceTimersByTime(6000 + 300 + 50));
    expect(shown()).toBeNull();
    act(() => toast("Copied"));
    expect(shown()?.textContent).toContain("Copied");
  });

  it("a toast fired while the last one fades out is not taken down by the last one's timer", () => {
    act(() => toast("Copied")); // 2 s
    act(() => vi.advanceTimersByTime(2100)); // fading out
    act(() => toast("Couldn't save your change", undefined, "error"));
    act(() => vi.advanceTimersByTime(400)); // past the old fade's 300 ms
    expect(shown()?.textContent).toContain("Couldn't save your change");
    expect(shown()?.classList.contains("show")).toBe(true);
  });

  it("holds each kind for its own time when the caller names none", () => {
    act(() => toast("a", undefined, "info")); // 4 s
    act(() => vi.advanceTimersByTime(3900));
    expect(shown()?.classList.contains("show")).toBe(true);
    act(() => vi.advanceTimersByTime(300 + 100));
    expect(shown()).toBeNull();

    act(() => toast("b", undefined, "error")); // 6 s
    act(() => vi.advanceTimersByTime(5900));
    expect(shown()?.classList.contains("show")).toBe(true);
    act(() => vi.advanceTimersByTime(300 + 100));
    expect(shown()).toBeNull();
  });

  it("a caller's own duration still wins", () => {
    act(() => toast("c", 500, "error"));
    act(() => vi.advanceTimersByTime(500 + 300));
    expect(shown()).toBeNull();
  });

  it("a replacing toast gets its own timer, not what was left of the last one's", () => {
    act(() => toast("first", 2000));
    act(() => vi.advanceTimersByTime(1900));
    act(() => toast("second", 2000));
    act(() => vi.advanceTimersByTime(300)); // 2200 ms in: the first's 2 s would have faded it
    expect(shown()?.textContent).toContain("second");
    expect(shown()?.classList.contains("show")).toBe(true);
  });

  it("an identical repeat restarts the timer without replaying the fade-in", () => {
    act(() => toast("Couldn't save your change", undefined, "error"));
    act(() => vi.advanceTimersByTime(100)); // faded in
    act(() => toast("Couldn't save your change", undefined, "error"));
    // No frame has run since the repeat, so a toast that replayed the fade would not be shown yet.
    expect(shown()?.classList.contains("show")).toBe(true);
    act(() => toast("A different failure", undefined, "error"));
    expect(shown()?.classList.contains("show")).toBe(false);
  });

  it("speaks a title and its body together, in the title's own punctuation", () => {
    act(() => toast("Check your connection.", undefined, "error", { title: "Couldn’t save your change" }));
    expect(mockAnnounce).toHaveBeenLastCalledWith("Couldn’t save your change. Check your connection.");
    act(() => toast("接続を確認してください。", undefined, "error", { title: "変更を保存できませんでした" }));
    expect(mockAnnounce).toHaveBeenLastCalledWith("変更を保存できませんでした。接続を確認してください。");
    act(() => toast("Is it saved?", undefined, undefined, { title: "Done!" }));
    expect(mockAnnounce).toHaveBeenLastCalledWith("Done! Is it saved?");
    act(() => toast("One.\nTwo."));
    expect(mockAnnounce).toHaveBeenLastCalledWith("One. Two.");
  });
});
