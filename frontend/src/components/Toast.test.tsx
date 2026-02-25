import { render, act } from "@testing-library/react";
import { Toast } from "./Toast";

describe("Toast", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the message", () => {
    const onDismiss = vi.fn();
    const { getByTestId } = render(<Toast message="Copied!" onDismiss={onDismiss} />);
    expect(getByTestId("bn-toast").textContent).toBe("Copied!");
  });

  it("adds .show class after mount (fade-in)", () => {
    const onDismiss = vi.fn();
    const { getByTestId } = render(<Toast message="Copied!" onDismiss={onDismiss} />);

    // Initially no .show (before rAF)
    const el = getByTestId("bn-toast");
    expect(el.classList.contains("show")).toBe(false);

    // After rAF fires
    act(() => {
      vi.advanceTimersByTime(16); // one frame
    });
    expect(el.classList.contains("show")).toBe(true);
  });

  it("calls onDismiss after duration + fade-out", () => {
    const onDismiss = vi.fn();
    render(<Toast message="Copied!" onDismiss={onDismiss} duration={2000} />);

    act(() => vi.advanceTimersByTime(2000));
    expect(onDismiss).not.toHaveBeenCalled(); // still in fade-out

    act(() => vi.advanceTimersByTime(300));
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it("removes .show class before fade-out", () => {
    const onDismiss = vi.fn();
    const { getByTestId } = render(<Toast message="Copied!" onDismiss={onDismiss} />);

    act(() => vi.advanceTimersByTime(16)); // rAF
    expect(getByTestId("bn-toast").classList.contains("show")).toBe(true);

    act(() => vi.advanceTimersByTime(2000)); // duration
    expect(getByTestId("bn-toast").classList.contains("show")).toBe(false);
  });

  it("uses clipboard-toast CSS class", () => {
    const onDismiss = vi.fn();
    const { getByTestId } = render(<Toast message="Copied!" onDismiss={onDismiss} />);
    expect(getByTestId("bn-toast").classList.contains("clipboard-toast")).toBe(true);
  });

  it("renders via portal to document.body", () => {
    const onDismiss = vi.fn();
    const { getByTestId } = render(
      <div data-testid="parent">
        <Toast message="Copied!" onDismiss={onDismiss} />
      </div>,
    );
    const toast = getByTestId("bn-toast");
    // Toast should be a child of body, not the parent div
    expect(toast.parentElement).toBe(document.body);
  });
});
