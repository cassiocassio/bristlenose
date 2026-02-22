import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Badge } from "./Badge";

describe("Badge", () => {
  it("renders text for readonly variant", () => {
    render(<Badge text="frustration" variant="readonly" />);
    expect(screen.getByText("frustration")).toBeInTheDocument();
  });

  it("renders text for ai variant", () => {
    render(<Badge text="delight" variant="ai" />);
    expect(screen.getByText("delight")).toBeInTheDocument();
  });

  it("renders text for user variant", () => {
    render(<Badge text="my-tag" variant="user" />);
    expect(screen.getByText("my-tag")).toBeInTheDocument();
  });

  it("ai badge: click fires onDelete", async () => {
    const onDelete = vi.fn();
    render(<Badge text="delight" variant="ai" onDelete={onDelete} />);
    await userEvent.click(screen.getByText("delight"));
    expect(onDelete).toHaveBeenCalledOnce();
  });

  it("user badge: x button appears and click fires onDelete", async () => {
    const onDelete = vi.fn();
    render(<Badge text="my-tag" variant="user" onDelete={onDelete} />);
    const btn = screen.getByRole("button", { name: /delete my-tag/i });
    expect(btn).toBeInTheDocument();
    await userEvent.click(btn);
    expect(onDelete).toHaveBeenCalledOnce();
  });

  it("readonly: no delete affordance", () => {
    const onDelete = vi.fn();
    render(<Badge text="info" variant="readonly" onDelete={onDelete} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("applies sentiment class", () => {
    render(<Badge text="test" variant="readonly" sentiment="frustration" data-testid="b" />);
    expect(screen.getByTestId("b")).toHaveClass("badge-frustration");
  });

  it("forwards data-testid", () => {
    render(<Badge text="x" variant="readonly" data-testid="my-badge" />);
    expect(screen.getByTestId("my-badge")).toBeInTheDocument();
  });

  // ── Proposed variant ──────────────────────────────────────────────────

  it("proposed: renders badge with dashed-border class", () => {
    render(<Badge text="Frustration" variant="proposed" data-testid="p" />);
    expect(screen.getByTestId("p")).toHaveClass("badge-proposed");
  });

  it("proposed: shows accept and deny actions", () => {
    render(
      <Badge text="Frustration" variant="proposed" data-testid="p" />,
    );
    expect(screen.getByTitle("Accept (a)")).toBeInTheDocument();
    expect(screen.getByTitle("Deny (d)")).toBeInTheDocument();
  });

  it("proposed: accept click fires onAccept", async () => {
    const onAccept = vi.fn();
    render(
      <Badge text="Frustration" variant="proposed" onAccept={onAccept} data-testid="p" />,
    );
    await userEvent.click(screen.getByTestId("p-accept"));
    expect(onAccept).toHaveBeenCalledOnce();
  });

  it("proposed: deny click fires onDeny", async () => {
    const onDeny = vi.fn();
    render(
      <Badge text="Frustration" variant="proposed" onDeny={onDeny} data-testid="p" />,
    );
    await userEvent.click(screen.getByTestId("p-deny"));
    expect(onDeny).toHaveBeenCalledOnce();
  });

  it("proposed: shows rationale tooltip", () => {
    render(
      <Badge
        text="Frustration"
        variant="proposed"
        rationale="Speaker expressed dissatisfaction"
        data-testid="p"
      />,
    );
    expect(screen.getByText("Speaker expressed dissatisfaction")).toBeInTheDocument();
  });

  it("proposed: has tooltip class for hover", () => {
    render(<Badge text="Frustration" variant="proposed" data-testid="p" />);
    expect(screen.getByTestId("p")).toHaveClass("has-tooltip");
  });

  // ── Keyboard shortcuts (A to accept, D to deny while hovered) ──────

  it("proposed: A key fires onAccept when hovered", () => {
    const onAccept = vi.fn();
    render(<Badge text="Tag" variant="proposed" onAccept={onAccept} data-testid="p" />);
    fireEvent.mouseEnter(screen.getByTestId("p"));
    fireEvent.keyDown(document, { key: "a" });
    expect(onAccept).toHaveBeenCalledOnce();
  });

  it("proposed: D key fires onDeny when hovered", () => {
    const onDeny = vi.fn();
    render(<Badge text="Tag" variant="proposed" onDeny={onDeny} data-testid="p" />);
    fireEvent.mouseEnter(screen.getByTestId("p"));
    fireEvent.keyDown(document, { key: "d" });
    expect(onDeny).toHaveBeenCalledOnce();
  });

  it("proposed: A/D keys do nothing when not hovered", () => {
    const onAccept = vi.fn();
    const onDeny = vi.fn();
    render(<Badge text="Tag" variant="proposed" onAccept={onAccept} onDeny={onDeny} data-testid="p" />);
    // No mouseEnter — badge is not hovered.
    fireEvent.keyDown(document, { key: "a" });
    fireEvent.keyDown(document, { key: "d" });
    expect(onAccept).not.toHaveBeenCalled();
    expect(onDeny).not.toHaveBeenCalled();
  });

  it("proposed: A/D keys do nothing when focus is in an input", () => {
    const onAccept = vi.fn();
    const onDeny = vi.fn();
    render(
      <div>
        <Badge text="Tag" variant="proposed" onAccept={onAccept} onDeny={onDeny} data-testid="p" />
        <input data-testid="text-input" />
      </div>,
    );
    fireEvent.mouseEnter(screen.getByTestId("p"));
    const input = screen.getByTestId("text-input");
    input.focus();
    // Dispatch keydown on the input (simulates typing in a text field).
    fireEvent.keyDown(input, { key: "a" });
    fireEvent.keyDown(input, { key: "d" });
    expect(onAccept).not.toHaveBeenCalled();
    expect(onDeny).not.toHaveBeenCalled();
  });
});
