import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Counter } from "./Counter";
import type { CounterItem } from "./Counter";

const makeItem = (overrides: Partial<CounterItem> = {}): CounterItem => ({
  domId: "q-p1-42",
  timecode: "00:42",
  seconds: 42,
  participantId: "p1",
  previewText: "I found the checkout process really confusing",
  hasMedia: true,
  ...overrides,
});

describe("Counter", () => {
  it("renders nothing when count is 0", () => {
    const { container } = render(
      <Counter
        count={0}
        items={[]}
        isOpen={false}
        onToggle={() => {}}
        onUnhide={() => {}}
        onUnhideAll={() => {}}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders singular label for count of 1", () => {
    render(
      <Counter
        count={1}
        items={[makeItem()]}
        isOpen={false}
        onToggle={() => {}}
        onUnhide={() => {}}
        onUnhideAll={() => {}}
        data-testid="bn-counter"
      />,
    );
    expect(screen.getByTestId("bn-counter-toggle")).toHaveTextContent("1 hidden quote");
    expect(screen.getByTestId("bn-counter-toggle")).not.toHaveTextContent("quotes");
  });

  it("renders plural label for count > 1", () => {
    render(
      <Counter
        count={3}
        items={[
          makeItem({ domId: "q-p1-10" }),
          makeItem({ domId: "q-p1-20" }),
          makeItem({ domId: "q-p1-30" }),
        ]}
        isOpen={false}
        onToggle={() => {}}
        onUnhide={() => {}}
        onUnhideAll={() => {}}
        data-testid="bn-counter"
      />,
    );
    expect(screen.getByTestId("bn-counter-toggle")).toHaveTextContent("3 hidden quotes");
  });

  it("does not show dropdown when closed", () => {
    render(
      <Counter
        count={1}
        items={[makeItem()]}
        isOpen={false}
        onToggle={() => {}}
        onUnhide={() => {}}
        onUnhideAll={() => {}}
        data-testid="bn-counter"
      />,
    );
    expect(screen.queryByTestId("bn-counter-dropdown")).not.toBeInTheDocument();
  });

  it("shows dropdown when open", () => {
    render(
      <Counter
        count={1}
        items={[makeItem()]}
        isOpen={true}
        onToggle={() => {}}
        onUnhide={() => {}}
        onUnhideAll={() => {}}
        data-testid="bn-counter"
      />,
    );
    expect(screen.getByTestId("bn-counter-dropdown")).toBeInTheDocument();
  });

  it("fires onToggle when toggle button is clicked", async () => {
    const onToggle = vi.fn();
    render(
      <Counter
        count={1}
        items={[makeItem()]}
        isOpen={false}
        onToggle={onToggle}
        onUnhide={() => {}}
        onUnhideAll={() => {}}
        data-testid="bn-counter"
      />,
    );
    await userEvent.click(screen.getByTestId("bn-counter-toggle"));
    expect(onToggle).toHaveBeenCalledOnce();
  });

  it("fires onUnhide when preview text is clicked", async () => {
    const onUnhide = vi.fn();
    render(
      <Counter
        count={1}
        items={[makeItem({ domId: "q-p1-42" })]}
        isOpen={true}
        onToggle={() => {}}
        onUnhide={onUnhide}
        onUnhideAll={() => {}}
        data-testid="bn-counter"
      />,
    );
    await userEvent.click(screen.getByTestId("bn-counter-preview-q-p1-42"));
    expect(onUnhide).toHaveBeenCalledWith("q-p1-42");
  });

  it("fires onUnhideAll when 'Unhide all' is clicked", async () => {
    const onUnhideAll = vi.fn();
    render(
      <Counter
        count={2}
        items={[makeItem({ domId: "q-p1-10" }), makeItem({ domId: "q-p1-20" })]}
        isOpen={true}
        onToggle={() => {}}
        onUnhide={() => {}}
        onUnhideAll={onUnhideAll}
        data-testid="bn-counter"
      />,
    );
    await userEvent.click(screen.getByTestId("bn-counter-unhide-all"));
    expect(onUnhideAll).toHaveBeenCalledOnce();
  });

  it("does not show 'Unhide all' link for count of 1", () => {
    render(
      <Counter
        count={1}
        items={[makeItem()]}
        isOpen={true}
        onToggle={() => {}}
        onUnhide={() => {}}
        onUnhideAll={() => {}}
        data-testid="bn-counter"
      />,
    );
    expect(screen.queryByTestId("bn-counter-unhide-all")).not.toBeInTheDocument();
  });

  it("sets aria-expanded on toggle button", () => {
    const { rerender } = render(
      <Counter
        count={1}
        items={[makeItem()]}
        isOpen={false}
        onToggle={() => {}}
        onUnhide={() => {}}
        onUnhideAll={() => {}}
        data-testid="bn-counter"
      />,
    );
    expect(screen.getByTestId("bn-counter-toggle")).toHaveAttribute("aria-expanded", "false");

    rerender(
      <Counter
        count={1}
        items={[makeItem()]}
        isOpen={true}
        onToggle={() => {}}
        onUnhide={() => {}}
        onUnhideAll={() => {}}
        data-testid="bn-counter"
      />,
    );
    expect(screen.getByTestId("bn-counter-toggle")).toHaveAttribute("aria-expanded", "true");
  });

  it("truncates long preview text with ellipsis", () => {
    const longText =
      "This is a very long quote that should be truncated because it exceeds fifty characters easily";
    render(
      <Counter
        count={1}
        items={[makeItem({ previewText: longText })]}
        isOpen={true}
        onToggle={() => {}}
        onUnhide={() => {}}
        onUnhideAll={() => {}}
        data-testid="bn-counter"
      />,
    );
    const preview = screen.getByTestId("bn-counter-preview-q-p1-42");
    expect(preview.textContent!.length).toBeLessThan(longText.length);
    expect(preview.textContent).toContain("\u2026");
  });

  it("renders timecode as link when hasMedia is true", () => {
    render(
      <Counter
        count={1}
        items={[makeItem({ hasMedia: true })]}
        isOpen={true}
        onToggle={() => {}}
        onUnhide={() => {}}
        onUnhideAll={() => {}}
      />,
    );
    const tc = screen.getByText("[00:42]");
    expect(tc.tagName).toBe("A");
    expect(tc).toHaveAttribute("data-seconds", "42");
  });

  it("renders timecode as span when hasMedia is false", () => {
    render(
      <Counter
        count={1}
        items={[makeItem({ hasMedia: false })]}
        isOpen={true}
        onToggle={() => {}}
        onUnhide={() => {}}
        onUnhideAll={() => {}}
      />,
    );
    const tc = screen.getByText("[00:42]");
    expect(tc.tagName).toBe("SPAN");
  });

  it("renders data-end-seconds when provided", () => {
    render(
      <Counter
        count={1}
        items={[makeItem({ hasMedia: true, endSeconds: 55 })]}
        isOpen={true}
        onToggle={() => {}}
        onUnhide={() => {}}
        onUnhideAll={() => {}}
      />,
    );
    const tc = screen.getByText("[00:42]");
    expect(tc).toHaveAttribute("data-end-seconds", "55");
  });
});
