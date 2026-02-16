import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Toggle } from "./Toggle";

describe("Toggle", () => {
  it("renders children content", () => {
    render(
      <Toggle active={false} onToggle={() => {}}>
        ★
      </Toggle>,
    );
    expect(screen.getByRole("button")).toHaveTextContent("★");
  });

  it("renders as a button element", () => {
    render(
      <Toggle active={false} onToggle={() => {}} data-testid="t">
        x
      </Toggle>,
    );
    expect(screen.getByTestId("t").tagName).toBe("BUTTON");
  });

  it("applies className", () => {
    render(
      <Toggle active={false} onToggle={() => {}} className="star-btn" data-testid="t">
        ★
      </Toggle>,
    );
    expect(screen.getByTestId("t")).toHaveClass("star-btn");
  });

  it("fires onToggle with true when currently inactive", async () => {
    const onToggle = vi.fn();
    render(
      <Toggle active={false} onToggle={onToggle}>
        ★
      </Toggle>,
    );
    await userEvent.click(screen.getByRole("button"));
    expect(onToggle).toHaveBeenCalledWith(true);
  });

  it("fires onToggle with false when currently active", async () => {
    const onToggle = vi.fn();
    render(
      <Toggle active={true} onToggle={onToggle}>
        ★
      </Toggle>,
    );
    await userEvent.click(screen.getByRole("button"));
    expect(onToggle).toHaveBeenCalledWith(false);
  });

  it("applies activeClassName when active", () => {
    render(
      <Toggle
        active={true}
        onToggle={() => {}}
        className="toolbar-btn toolbar-btn-toggle"
        activeClassName="active"
        data-testid="t"
      >
        AI
      </Toggle>,
    );
    expect(screen.getByTestId("t")).toHaveClass("active");
  });

  it("does not apply activeClassName when inactive", () => {
    render(
      <Toggle
        active={false}
        onToggle={() => {}}
        className="toolbar-btn toolbar-btn-toggle"
        activeClassName="active"
        data-testid="t"
      >
        AI
      </Toggle>,
    );
    expect(screen.getByTestId("t")).not.toHaveClass("active");
  });

  it("sets aria-pressed to reflect active state", () => {
    const { rerender } = render(
      <Toggle active={true} onToggle={() => {}} data-testid="t">
        ★
      </Toggle>,
    );
    expect(screen.getByTestId("t")).toHaveAttribute("aria-pressed", "true");

    rerender(
      <Toggle active={false} onToggle={() => {}} data-testid="t">
        ★
      </Toggle>,
    );
    expect(screen.getByTestId("t")).toHaveAttribute("aria-pressed", "false");
  });

  it("forwards data-testid", () => {
    render(
      <Toggle active={false} onToggle={() => {}} data-testid="my-toggle">
        x
      </Toggle>,
    );
    expect(screen.getByTestId("my-toggle")).toBeInTheDocument();
  });
});
