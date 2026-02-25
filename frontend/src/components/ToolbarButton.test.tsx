import { render } from "@testing-library/react";
import { ToolbarButton } from "./ToolbarButton";

describe("ToolbarButton", () => {
  it("renders the label", () => {
    const { getByText } = render(<ToolbarButton label="Copy CSV" />);
    expect(getByText("Copy CSV")).toBeDefined();
  });

  it("applies toolbar-btn class", () => {
    const { getByRole } = render(<ToolbarButton label="Test" />);
    expect(getByRole("button").classList.contains("toolbar-btn")).toBe(true);
  });

  it("appends custom className", () => {
    const { getByRole } = render(<ToolbarButton label="Test" className="tag-filter-btn" />);
    const btn = getByRole("button");
    expect(btn.classList.contains("toolbar-btn")).toBe(true);
    expect(btn.classList.contains("tag-filter-btn")).toBe(true);
  });

  it("renders icon when provided", () => {
    const icon = <svg data-testid="icon" />;
    const { getByTestId } = render(<ToolbarButton label="Test" icon={icon} />);
    expect(getByTestId("icon")).toBeDefined();
  });

  it("wraps icon in toolbar-icon-svg span", () => {
    const icon = <svg data-testid="icon" />;
    const { getByTestId } = render(<ToolbarButton label="Test" icon={icon} />);
    expect(getByTestId("icon").parentElement?.classList.contains("toolbar-icon-svg")).toBe(true);
  });

  it("does not render icon wrapper when no icon", () => {
    const { container } = render(<ToolbarButton label="Test" />);
    expect(container.querySelector(".toolbar-icon-svg")).toBeNull();
  });

  it("renders arrow when arrow=true", () => {
    const { container } = render(<ToolbarButton label="Test" arrow />);
    expect(container.querySelector(".toolbar-arrow")).not.toBeNull();
  });

  it("does not render arrow when arrow is not set", () => {
    const { container } = render(<ToolbarButton label="Test" />);
    expect(container.querySelector(".toolbar-arrow")).toBeNull();
  });

  it("sets aria-expanded when expanded is provided", () => {
    const { getByRole } = render(<ToolbarButton label="Test" arrow expanded={true} />);
    expect(getByRole("button").getAttribute("aria-expanded")).toBe("true");
  });

  it("sets aria-haspopup when arrow is true", () => {
    const { getByRole } = render(<ToolbarButton label="Test" arrow />);
    expect(getByRole("button").getAttribute("aria-haspopup")).toBe("true");
  });

  it("does not set aria-haspopup when arrow is false", () => {
    const { getByRole } = render(<ToolbarButton label="Test" />);
    expect(getByRole("button").getAttribute("aria-haspopup")).toBeNull();
  });

  it("passes through onClick", () => {
    const onClick = vi.fn();
    const { getByRole } = render(<ToolbarButton label="Test" onClick={onClick} />);
    getByRole("button").click();
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("forwards data-testid", () => {
    const { getByTestId } = render(<ToolbarButton label="Test" data-testid="btn" />);
    expect(getByTestId("btn")).toBeDefined();
  });
});
