/**
 * Tests for HelpModal — render, keyboard toggle, close behavior.
 */

import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { HelpModal } from "./HelpModal";

describe("HelpModal", () => {
  afterEach(() => {
    // Let React unmount portals cleanly before any manual DOM cleanup.
    cleanup();
  });

  it("renders nothing when open is false", () => {
    render(<HelpModal open={false} onClose={vi.fn()} />);
    expect(screen.queryByTestId("bn-help-overlay")).toBeNull();
  });

  it("renders overlay when open is true", () => {
    render(<HelpModal open={true} onClose={vi.fn()} />);
    expect(screen.getByTestId("bn-help-overlay")).toBeTruthy();
    expect(screen.getByTestId("bn-help-modal")).toBeTruthy();
  });

  it("renders all four shortcut sections", () => {
    render(<HelpModal open={true} onClose={vi.fn()} />);
    const modal = screen.getByTestId("bn-help-modal");
    expect(modal.textContent).toContain("Navigation");
    expect(modal.textContent).toContain("Selection");
    expect(modal.textContent).toContain("Actions");
    expect(modal.textContent).toContain("Global");
  });

  it("renders keyboard shortcuts content", () => {
    render(<HelpModal open={true} onClose={vi.fn()} />);
    const modal = screen.getByTestId("bn-help-modal");
    expect(modal.textContent).toContain("Next quote");
    expect(modal.textContent).toContain("Previous quote");
    expect(modal.textContent).toContain("Star quote(s)");
    expect(modal.textContent).toContain("Hide quote(s)");
    expect(modal.textContent).toContain("Add tag(s)");
    expect(modal.textContent).toContain("Play in video");
    expect(modal.textContent).toContain("Search");
  });

  it("calls onClose when clicking overlay background", () => {
    const onClose = vi.fn();
    render(<HelpModal open={true} onClose={onClose} />);
    const overlay = screen.getByTestId("bn-help-overlay");
    fireEvent.click(overlay);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("does not call onClose when clicking inside modal", () => {
    const onClose = vi.fn();
    render(<HelpModal open={true} onClose={onClose} />);
    const modal = screen.getByTestId("bn-help-modal");
    fireEvent.click(modal);
    expect(onClose).not.toHaveBeenCalled();
  });

  it("calls onClose on Escape key", () => {
    const onClose = vi.fn();
    render(<HelpModal open={true} onClose={onClose} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("renders via portal into document.body", () => {
    render(<HelpModal open={true} onClose={vi.fn()} />);
    const overlay = document.body.querySelector(".help-overlay");
    expect(overlay).toBeTruthy();
    expect(overlay!.parentElement).toBe(document.body);
  });

  it("uses the heading 'Keyboard Shortcuts'", () => {
    render(<HelpModal open={true} onClose={vi.fn()} />);
    expect(screen.getByText("Keyboard Shortcuts")).toBeTruthy();
  });

  it("includes footer text", () => {
    render(<HelpModal open={true} onClose={vi.fn()} />);
    const modal = screen.getByTestId("bn-help-modal");
    expect(modal.textContent).toContain("Press");
    expect(modal.textContent).toContain("to open this help");
  });
});
