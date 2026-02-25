import { render, fireEvent } from "@testing-library/react";
import { ViewSwitcher } from "./ViewSwitcher";

describe("ViewSwitcher", () => {
  it("renders the current view mode label", () => {
    const { getByTestId } = render(
      <ViewSwitcher
        viewMode="all"
        onViewModeChange={vi.fn()}
        data-testid="vs"
      />,
    );
    expect(getByTestId("vs-btn").textContent).toContain("All quotes");
  });

  it("shows 'Starred quotes' when viewMode is starred", () => {
    const { getByTestId } = render(
      <ViewSwitcher
        viewMode="starred"
        onViewModeChange={vi.fn()}
        data-testid="vs"
      />,
    );
    expect(getByTestId("vs-btn").textContent).toContain("Starred quotes");
  });

  it("shows labelOverride when provided", () => {
    const { getByTestId } = render(
      <ViewSwitcher
        viewMode="all"
        onViewModeChange={vi.fn()}
        labelOverride="7 matching quotes"
        data-testid="vs"
      />,
    );
    expect(getByTestId("vs-btn").textContent).toContain("7 matching quotes");
  });

  it("opens menu on button click", () => {
    const { getByTestId, queryByTestId } = render(
      <ViewSwitcher
        viewMode="all"
        onViewModeChange={vi.fn()}
        data-testid="vs"
      />,
    );
    expect(queryByTestId("vs-menu")).toBeNull();
    fireEvent.click(getByTestId("vs-btn"));
    expect(queryByTestId("vs-menu")).not.toBeNull();
  });

  it("calls onViewModeChange when an option is selected", () => {
    const onViewModeChange = vi.fn();
    const { getByTestId, getByText } = render(
      <ViewSwitcher
        viewMode="all"
        onViewModeChange={onViewModeChange}
        data-testid="vs"
      />,
    );
    fireEvent.click(getByTestId("vs-btn")); // open
    fireEvent.click(getByText("Starred quotes"));
    expect(onViewModeChange).toHaveBeenCalledWith("starred");
  });

  it("closes menu after selection (uncontrolled)", () => {
    const { getByTestId, getByText, queryByTestId } = render(
      <ViewSwitcher
        viewMode="all"
        onViewModeChange={vi.fn()}
        data-testid="vs"
      />,
    );
    fireEvent.click(getByTestId("vs-btn"));
    fireEvent.click(getByText("Starred quotes"));
    expect(queryByTestId("vs-menu")).toBeNull();
  });

  it("calls onToggle(false) after selection in controlled mode", () => {
    const onToggle = vi.fn();
    const { getByText } = render(
      <ViewSwitcher
        viewMode="all"
        onViewModeChange={vi.fn()}
        isOpen={true}
        onToggle={onToggle}
        data-testid="vs"
      />,
    );
    fireEvent.click(getByText("Starred quotes"));
    expect(onToggle).toHaveBeenCalledWith(false);
  });

  it("marks active item with .active class", () => {
    const { getByTestId } = render(
      <ViewSwitcher
        viewMode="starred"
        onViewModeChange={vi.fn()}
        isOpen={true}
        onToggle={vi.fn()}
        data-testid="vs"
      />,
    );
    const menu = getByTestId("vs-menu");
    const items = menu.querySelectorAll("li");
    expect(items[0].classList.contains("active")).toBe(false); // "All quotes"
    expect(items[1].classList.contains("active")).toBe(true); // "Starred quotes"
  });

  it("sets aria-expanded on trigger button", () => {
    const { getByTestId } = render(
      <ViewSwitcher
        viewMode="all"
        onViewModeChange={vi.fn()}
        isOpen={true}
        onToggle={vi.fn()}
        data-testid="vs"
      />,
    );
    expect(getByTestId("vs-btn").getAttribute("aria-expanded")).toBe("true");
  });
});
