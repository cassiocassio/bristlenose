import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfirmDialog } from "./ConfirmDialog";

describe("ConfirmDialog", () => {
  it("renders title", () => {
    render(<ConfirmDialog title="Delete tag?" onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByText("Delete tag?")).toBeInTheDocument();
  });

  it("renders body when provided", () => {
    render(
      <ConfirmDialog
        title="Merge?"
        body={<span>This cannot be undone.</span>}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByText("This cannot be undone.")).toBeInTheDocument();
  });

  it("does not render body container when body is omitted", () => {
    const { container } = render(
      <ConfirmDialog title="Delete?" onConfirm={vi.fn()} onCancel={vi.fn()} />,
    );
    expect(container.querySelector(".confirm-dialog-body")).not.toBeInTheDocument();
  });

  it("uses 'Delete' as default confirm label", () => {
    render(<ConfirmDialog title="x" onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
  });

  it("uses custom confirm label", () => {
    render(
      <ConfirmDialog title="x" confirmLabel="Merge" onConfirm={vi.fn()} onCancel={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: "Merge" })).toBeInTheDocument();
  });

  it("clicking confirm button fires onConfirm", async () => {
    const onConfirm = vi.fn();
    render(<ConfirmDialog title="x" onConfirm={onConfirm} onCancel={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("clicking cancel button fires onCancel", async () => {
    const onCancel = vi.fn();
    render(<ConfirmDialog title="x" onConfirm={vi.fn()} onCancel={onCancel} />);
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("Escape fires onCancel", async () => {
    const onCancel = vi.fn();
    render(<ConfirmDialog title="x" onConfirm={vi.fn()} onCancel={onCancel} />);
    await userEvent.keyboard("{Escape}");
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("Enter on focused button fires onConfirm", async () => {
    const onConfirm = vi.fn();
    render(<ConfirmDialog title="x" onConfirm={onConfirm} onCancel={vi.fn()} />);
    // Button should be auto-focused
    await userEvent.keyboard("{Enter}");
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("auto-focuses the confirm button on mount", () => {
    render(<ConfirmDialog title="x" onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Delete" })).toHaveFocus();
  });

  it("applies danger variant class by default", () => {
    render(<ConfirmDialog title="x" onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Delete" })).toHaveClass("confirm-dialog-btn--danger");
  });

  it("applies primary variant class", () => {
    render(
      <ConfirmDialog title="x" variant="primary" onConfirm={vi.fn()} onCancel={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: "Delete" })).toHaveClass("confirm-dialog-btn--primary");
  });

  it("applies accent colour as background tint", () => {
    render(
      <ConfirmDialog
        title="x"
        accentColour="var(--bn-bar-emo)"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
        data-testid="dlg"
      />,
    );
    const el = screen.getByTestId("dlg");
    expect(el.style.backgroundColor).toContain("color-mix");
  });

  it("forwards data-testid", () => {
    render(
      <ConfirmDialog title="x" onConfirm={vi.fn()} onCancel={vi.fn()} data-testid="my-dlg" />,
    );
    expect(screen.getByTestId("my-dlg")).toBeInTheDocument();
  });
});
