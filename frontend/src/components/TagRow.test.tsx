import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TagRow } from "./TagRow";

const BASE_PROPS = {
  name: "Frustration",
  checked: true,
  count: 5,
  maxCount: 10,
  badgeBg: "#f00",
  barColour: "#c00",
  onToggle: vi.fn(),
};

describe("TagRow", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders checkbox and badge", () => {
    render(<TagRow {...BASE_PROPS} />);
    expect(screen.getByRole("checkbox")).toBeChecked();
    expect(screen.getByText("Frustration")).toBeInTheDocument();
  });

  it("checkbox click calls onToggle", async () => {
    const onToggle = vi.fn();
    render(<TagRow {...BASE_PROPS} onToggle={onToggle} />);
    await userEvent.click(screen.getByRole("checkbox"));
    expect(onToggle).toHaveBeenCalledWith("Frustration", false);
  });

  it("badge click calls onAssign when assignActive", async () => {
    const onAssign = vi.fn();
    const onToggle = vi.fn();
    render(
      <TagRow {...BASE_PROPS} onToggle={onToggle} onAssign={onAssign} assignActive={true} />,
    );
    await userEvent.click(screen.getByText("Frustration"));
    expect(onAssign).toHaveBeenCalledWith("Frustration");
    expect(onToggle).not.toHaveBeenCalled();
  });

  it("badge click does NOT call onAssign when assignActive is false", async () => {
    const onAssign = vi.fn();
    render(
      <TagRow {...BASE_PROPS} onAssign={onAssign} assignActive={false} />,
    );
    await userEvent.click(screen.getByText("Frustration"));
    expect(onAssign).not.toHaveBeenCalled();
  });

  it("badge click does nothing without onAssign prop", async () => {
    const onToggle = vi.fn();
    render(<TagRow {...BASE_PROPS} onToggle={onToggle} />);
    await userEvent.click(screen.getByText("Frustration"));
    // No onAssign means badge click is inert (no toggle either — row is a div now)
    expect(onToggle).not.toHaveBeenCalled();
  });

  it("badge has role=button when onAssign is provided", () => {
    render(<TagRow {...BASE_PROPS} onAssign={vi.fn()} assignActive={true} />);
    expect(screen.getByRole("button", { name: /assign frustration/i })).toBeInTheDocument();
  });

  it("badge has tabIndex=0 only when assignActive", () => {
    const { rerender } = render(
      <TagRow {...BASE_PROPS} onAssign={vi.fn()} assignActive={false} />,
    );
    const badge = screen.getByText("Frustration");
    expect(badge).toHaveAttribute("tabindex", "-1");

    rerender(<TagRow {...BASE_PROPS} onAssign={vi.fn()} assignActive={true} />);
    expect(badge).toHaveAttribute("tabindex", "0");
  });

  it("Enter key on badge calls onAssign when assignActive", async () => {
    const onAssign = vi.fn();
    render(
      <TagRow {...BASE_PROPS} onAssign={onAssign} assignActive={true} />,
    );
    const badge = screen.getByRole("button", { name: /assign frustration/i });
    badge.focus();
    await userEvent.keyboard("{Enter}");
    expect(onAssign).toHaveBeenCalledWith("Frustration");
  });

  it("Space key on badge calls onAssign when assignActive", async () => {
    const onAssign = vi.fn();
    render(
      <TagRow {...BASE_PROPS} onAssign={onAssign} assignActive={true} />,
    );
    const badge = screen.getByRole("button", { name: /assign frustration/i });
    badge.focus();
    await userEvent.keyboard(" ");
    expect(onAssign).toHaveBeenCalledWith("Frustration");
  });

  it("applies badge-assignable class when assignActive", () => {
    render(<TagRow {...BASE_PROPS} onAssign={vi.fn()} assignActive={true} />);
    expect(screen.getByText("Frustration")).toHaveClass("badge-assignable");
  });

  it("applies badge-accept-flash class when flashing", () => {
    render(<TagRow {...BASE_PROPS} flashing={true} />);
    expect(screen.getByText("Frustration")).toHaveClass("badge-accept-flash");
  });

  it("renders micro-bar and count", () => {
    render(<TagRow {...BASE_PROPS} />);
    expect(screen.getByText("5")).toBeInTheDocument();
  });
});
