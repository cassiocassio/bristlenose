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

describe("Toast anatomy", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("draws a kind as an icon, not a character, in the kind's colour class", () => {
    const { getByTestId } = render(<Toast message="Export failed" kind="error" onDismiss={vi.fn()} />);
    const el = getByTestId("bn-toast");
    expect(el.querySelector(".toast-glyph--error svg")).not.toBeNull();
    expect(el.textContent).toBe("Export failed"); // no ✗ character in the text
    expect(el.classList.contains("has-kind")).toBe(true);
  });

  it("draws skipped as info: a toast has four of the five kinds", () => {
    const { getByTestId } = render(<Toast message="Not needed" kind="skipped" onDismiss={vi.fn()} />);
    const el = getByTestId("bn-toast");
    expect(el.querySelector(".toast-glyph--info svg")).not.toBeNull();
    expect(el.querySelector(".toast-glyph--skipped")).toBeNull();
    expect(el.getAttribute("data-kind")).toBe("skipped");
  });

  it("a title sits over a quieter body; a message alone is one regular line", () => {
    const withTitle = render(
      <Toast title="No quotes yet" message="Analyse your sessions first." onDismiss={vi.fn()} />,
    );
    expect(withTitle.getByText("No quotes yet").className).toBe("toast-title");
    expect(withTitle.getByText("Analyse your sessions first.").className).toBe("toast-body");
    withTitle.unmount();

    const alone = render(<Toast message="Copied" onDismiss={vi.fn()} />);
    expect(alone.getByText("Copied").className).toBe("toast-message");
    expect(alone.container.querySelector(".toast-title")).toBeNull();
  });

  it("a plain toast has no icon", () => {
    const { getByTestId } = render(<Toast message="Copied" onDismiss={vi.fn()} />);
    expect(getByTestId("bn-toast").querySelector(".toast-glyph")).toBeNull();
    expect(getByTestId("bn-toast").classList.contains("has-kind")).toBe(false);
  });
});
