import { act, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { Dialog } from "./Dialog";
import { resetInertCount } from "../hooks/useInert";

function Harness({ initiallyOpen = false, onClose = vi.fn() }: { initiallyOpen?: boolean; onClose?: () => void }) {
  const [open, setOpen] = useState(initiallyOpen);
  return (
    <div id="bn-app-root">
      <button onClick={() => setOpen(true)}>Open it</button>
      <Dialog
        open={open}
        onClose={() => {
          onClose();
          setOpen(false);
        }}
        testId="overlay"
        labelledBy="t"
      >
        <h2 id="t">Title</h2>
        <button>First</button>
        <button>Last</button>
      </Dialog>
    </div>
  );
}

beforeEach(() => {
  resetInertCount();
});

describe("Dialog", () => {
  it("is a named modal dialog, shown only while open", () => {
    render(<Harness />);
    const overlay = screen.getByTestId("overlay");
    expect(overlay).not.toHaveClass("visible");
    expect(overlay).toHaveAttribute("aria-hidden", "true");

    fireEvent.click(screen.getByRole("button", { name: "Open it" }));
    expect(overlay).toHaveClass("visible");
    const dialog = screen.getByRole("dialog", { name: "Title" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
  });

  it("never closes on a click on the backdrop", () => {
    const onClose = vi.fn();
    render(<Harness initiallyOpen onClose={onClose} />);
    fireEvent.click(screen.getByTestId("overlay"));
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByTestId("overlay")).toHaveClass("visible");
  });

  it("closes on Escape and on its ×", () => {
    const onClose = vi.fn();
    render(<Harness initiallyOpen onClose={onClose} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Open it", hidden: true }));
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("answers Escape only when it is the topmost dialog", () => {
    const under = vi.fn();
    const over = vi.fn();
    render(
      <>
        <Dialog open onClose={under} label="Under">
          <p>under</p>
        </Dialog>
        <Dialog open onClose={over} label="Over">
          <p>over</p>
        </Dialog>
      </>,
    );
    fireEvent.keyDown(document, { key: "Escape" });
    expect(over).toHaveBeenCalledTimes(1);
    expect(under).not.toHaveBeenCalled();
  });

  it("makes the page behind inert while open", () => {
    render(<Harness initiallyOpen />);
    expect(document.getElementById("bn-app-root")).toHaveAttribute("inert");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(document.getElementById("bn-app-root")).not.toHaveAttribute("inert");
  });

  it("gives focus back to what opened it", () => {
    render(<Harness />);
    const opener = screen.getByRole("button", { name: "Open it" });
    opener.focus();
    fireEvent.click(opener);
    screen.getByRole("button", { name: "First" }).focus();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(opener).toHaveFocus();
  });

  it("moves focus to the card when nothing inside asks for it", async () => {
    render(<Harness initiallyOpen />);
    await act(() => new Promise((r) => requestAnimationFrame(() => r(undefined))));
    expect(screen.getByRole("dialog")).toHaveFocus();
  });

  it("keeps Tab inside the dialog", () => {
    render(<Harness initiallyOpen />);
    const close = screen.getByRole("button", { name: "Close" });
    const last = screen.getByRole("button", { name: "Last" });
    last.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(close).toHaveFocus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(last).toHaveFocus();
  });

  describe("Return presses the primary button", () => {
    function ReturnHarness({ onPrimary, disabled = false }: { onPrimary: () => void; disabled?: boolean }) {
      return (
        <Dialog open onClose={vi.fn()} label="Form">
          <input type="text" aria-label="Name" />
          <textarea aria-label="Notes" />
          <input
            type="text"
            aria-label="Tag"
            onKeyDown={(e) => {
              if (e.key === "Enter") e.preventDefault(); // commits the tag itself
            }}
          />
          <form onSubmit={(e) => e.preventDefault()}>
            <input type="text" aria-label="In a form" />
          </form>
          <div className="bn-modal-actions">
            <button className="bn-btn bn-btn-secondary">Cancel</button>
            <button className="bn-btn bn-btn-primary" onClick={onPrimary} disabled={disabled}>
              Go
            </button>
          </div>
        </Dialog>
      );
    }

    it("clicks the primary button on Enter in the dialog or a plain field", () => {
      const onPrimary = vi.fn();
      render(<ReturnHarness onPrimary={onPrimary} />);
      fireEvent.keyDown(screen.getByRole("dialog"), { key: "Enter" });
      expect(onPrimary).toHaveBeenCalledTimes(1);
      fireEvent.keyDown(screen.getByLabelText("Name"), { key: "Enter" });
      expect(onPrimary).toHaveBeenCalledTimes(2);
    });

    it("leaves Return to a control that needs it", () => {
      const onPrimary = vi.fn();
      render(<ReturnHarness onPrimary={onPrimary} />);
      fireEvent.keyDown(screen.getByLabelText("Notes"), { key: "Enter" });
      fireEvent.keyDown(screen.getByLabelText("Tag"), { key: "Enter" });
      fireEvent.keyDown(screen.getByLabelText("In a form"), { key: "Enter" });
      fireEvent.keyDown(screen.getByRole("button", { name: "Cancel" }), { key: "Enter" });
      fireEvent.keyDown(screen.getByRole("dialog"), { key: "Enter", metaKey: true });
      expect(onPrimary).not.toHaveBeenCalled();
    });

    it("does nothing while the primary button is disabled", () => {
      const onPrimary = vi.fn();
      render(<ReturnHarness onPrimary={onPrimary} disabled />);
      fireEvent.keyDown(screen.getByRole("dialog"), { key: "Enter" });
      expect(onPrimary).not.toHaveBeenCalled();
    });

    it("answers only in the topmost dialog", () => {
      const under = vi.fn();
      const over = vi.fn();
      render(
        <>
          <Dialog open onClose={vi.fn()} label="Under">
            <button className="bn-btn bn-btn-primary" onClick={under}>Under</button>
          </Dialog>
          <Dialog open onClose={vi.fn()} label="Over">
            <p>over</p>
            <button className="bn-btn bn-btn-primary" onClick={over}>Over</button>
          </Dialog>
        </>,
      );
      fireEvent.keyDown(screen.getByRole("dialog", { name: "Over" }), { key: "Enter" });
      expect(over).toHaveBeenCalledTimes(1);
      fireEvent.keyDown(screen.getByRole("dialog", { name: "Under", hidden: true }), { key: "Enter" });
      expect(under).not.toHaveBeenCalled();
    });
  });

  it("can leave the × to a dialog that draws its own", () => {
    render(
      <Dialog open onClose={vi.fn()} label="Own" closeButton={false}>
        <p>content</p>
      </Dialog>,
    );
    expect(screen.queryByRole("button", { name: "Close" })).toBeNull();
  });
});
