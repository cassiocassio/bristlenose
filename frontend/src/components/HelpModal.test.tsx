/**
 * Tests for HelpModal — render, keyboard toggle, close behavior,
 * platform-aware shortcut display.
 */

import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { HelpModal } from "./HelpModal";
import { isMac } from "../utils/platform";

vi.mock("../utils/platform", () => ({
  isMac: vi.fn(() => true),
}));

const mockIsMac = vi.mocked(isMac);

describe("HelpModal", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders overlay without visible class when open is false", () => {
    render(<HelpModal open={false} onClose={vi.fn()} />);
    const overlay = screen.getByTestId("bn-help-overlay");
    expect(overlay.classList.contains("visible")).toBe(false);
    expect(overlay.getAttribute("aria-hidden")).toBe("true");
  });

  it("renders overlay with visible class when open is true", () => {
    render(<HelpModal open={true} onClose={vi.fn()} />);
    const overlay = screen.getByTestId("bn-help-overlay");
    expect(overlay.classList.contains("visible")).toBe(true);
    expect(overlay.getAttribute("aria-hidden")).toBe("false");
    expect(screen.getByTestId("bn-help-modal")).toBeTruthy();
  });

  it("renders all four shortcut sections", () => {
    render(<HelpModal open={true} onClose={vi.fn()} />);
    const modal = screen.getByTestId("bn-help-modal");
    expect(modal.textContent).toContain("Navigation");
    expect(modal.textContent).toContain("Selection");
    expect(modal.textContent).toContain("Actions");
    expect(modal.textContent).toContain("Global");
    // Sidebar shortcuts merged into Global
    expect(modal.textContent).toContain("Toggle contents");
    expect(modal.textContent).toContain("Toggle tags");
  });

  it("renders close button", () => {
    const onClose = vi.fn();
    render(<HelpModal open={true} onClose={onClose} />);
    const btn = screen.getByRole("button", { name: "Close" });
    expect(btn).toBeTruthy();
    fireEvent.click(btn);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("renders keyboard shortcuts content", () => {
    render(<HelpModal open={true} onClose={vi.fn()} />);
    const modal = screen.getByTestId("bn-help-modal");
    expect(modal.textContent).toContain("Next quote");
    expect(modal.textContent).toContain("Previous quote");
    expect(modal.textContent).toContain("Star quote(s)");
    expect(modal.textContent).toContain("Hide quote(s)");
    expect(modal.textContent).toContain("Add tag");
    expect(modal.textContent).toContain("Repeat last tag");
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

describe("HelpModal — Mac platform display", () => {
  beforeEach(() => {
    mockIsMac.mockReturnValue(true);
  });

  afterEach(() => {
    cleanup();
  });

  it("renders ⌘. as a single <kbd> element", () => {
    render(<HelpModal open={true} onClose={vi.fn()} />);
    const kbds = screen.getByTestId("bn-help-modal").querySelectorAll("kbd");
    const texts = Array.from(kbds).map((k) => k.textContent);
    expect(texts).toContain("\u2318.");
  });

  it("renders ⇧J and ⇧K for extend selection", () => {
    render(<HelpModal open={true} onClose={vi.fn()} />);
    const kbds = screen.getByTestId("bn-help-modal").querySelectorAll("kbd");
    const texts = Array.from(kbds).map((k) => k.textContent);
    expect(texts).toContain("\u21E7J");
    expect(texts).toContain("\u21E7K");
  });

  it("does not render 'Ctrl' or 'Shift' text labels", () => {
    render(<HelpModal open={true} onClose={vi.fn()} />);
    const modal = screen.getByTestId("bn-help-modal");
    const kbds = Array.from(modal.querySelectorAll("kbd")).map((k) => k.textContent);
    expect(kbds).not.toContain("Ctrl");
    expect(kbds).not.toContain("Shift");
  });
});

describe("HelpModal — non-Mac platform display", () => {
  beforeEach(() => {
    mockIsMac.mockReturnValue(false);
  });

  afterEach(() => {
    cleanup();
  });

  it("renders Ctrl+. with separate <kbd> elements and + separator", () => {
    render(<HelpModal open={true} onClose={vi.fn()} />);
    const modal = screen.getByTestId("bn-help-modal");
    const kbds = Array.from(modal.querySelectorAll("kbd")).map((k) => k.textContent);
    expect(kbds).toContain("Ctrl");
    expect(kbds).toContain(".");
    // The + separator is in a <span>, not <kbd>
    const seps = Array.from(modal.querySelectorAll(".help-key-sep")).map((s) => s.textContent);
    expect(seps).toContain("+");
  });

  it("renders Shift+J and Shift+K for extend selection", () => {
    render(<HelpModal open={true} onClose={vi.fn()} />);
    const modal = screen.getByTestId("bn-help-modal");
    const kbds = Array.from(modal.querySelectorAll("kbd")).map((k) => k.textContent);
    expect(kbds).toContain("Shift");
    expect(kbds).toContain("J");
    expect(kbds).toContain("K");
  });

  it("does not render Mac glyph symbols", () => {
    render(<HelpModal open={true} onClose={vi.fn()} />);
    const modal = screen.getByTestId("bn-help-modal");
    const allKbdText = Array.from(modal.querySelectorAll("kbd"))
      .map((k) => k.textContent)
      .join("");
    expect(allKbdText).not.toContain("\u2318");
    expect(allKbdText).not.toContain("\u21E7");
  });
});

describe("HelpModal — standalone keys identical on both platforms", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders j, k, Esc the same on Mac and non-Mac", () => {
    // Mac
    mockIsMac.mockReturnValue(true);
    const { unmount: unmountMac } = render(
      <HelpModal open={true} onClose={vi.fn()} />,
    );
    const macKbds = Array.from(
      screen.getByTestId("bn-help-modal").querySelectorAll("kbd"),
    ).map((k) => k.textContent);
    unmountMac();
    cleanup();

    // Non-Mac
    mockIsMac.mockReturnValue(false);
    render(<HelpModal open={true} onClose={vi.fn()} />);
    const nonMacKbds = Array.from(
      screen.getByTestId("bn-help-modal").querySelectorAll("kbd"),
    ).map((k) => k.textContent);

    // Standalone keys should appear in both
    for (const key of ["j", "k", "Esc", "?", "/", "s", "h", "t", "r", "Enter"]) {
      expect(macKbds).toContain(key);
      expect(nonMacKbds).toContain(key);
    }
  });
});
