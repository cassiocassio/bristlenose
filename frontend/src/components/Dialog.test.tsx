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

  it("can leave the × to a dialog that draws its own", () => {
    render(
      <Dialog open onClose={vi.fn()} label="Own" closeButton={false}>
        <p>content</p>
      </Dialog>,
    );
    expect(screen.queryByRole("button", { name: "Close" })).toBeNull();
  });
});
