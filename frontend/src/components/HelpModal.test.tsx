/**
 * Tests for HelpModal — ModalNav-based sidebar-nav help modal.
 *
 * Tests cover: open/close lifecycle, section navigation, disclosure group,
 * initialSection prop, keyboard shortcuts rendering, and platform-aware
 * kbd badge display.
 */

import { render, screen, fireEvent, cleanup, within } from "@testing-library/react";
import { HelpModal } from "./HelpModal";
import { DEFAULT_HEALTH_RESPONSE } from "../utils/health";
import { isMac } from "../utils/platform";

vi.mock("../utils/platform", () => ({
  isMac: vi.fn(() => true),
  isDesktop: vi.fn(() => false),
  _resetPlatformCache: vi.fn(),
}));

vi.mock("../utils/exportData", () => ({
  isExportMode: vi.fn(() => false),
  getExportData: vi.fn(() => null),
}));

const mockIsMac = vi.mocked(isMac);

const defaultProps = {
  open: true,
  onClose: vi.fn(),
  health: DEFAULT_HEALTH_RESPONSE,
};

describe("HelpModal — lifecycle", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders overlay without visible class when open is false", () => {
    render(<HelpModal {...defaultProps} open={false} />);
    const overlay = screen.getByTestId("bn-help-overlay");
    expect(overlay.classList.contains("visible")).toBe(false);
    expect(overlay.getAttribute("aria-hidden")).toBe("true");
  });

  it("renders overlay with visible class when open is true", () => {
    render(<HelpModal {...defaultProps} />);
    const overlay = screen.getByTestId("bn-help-overlay");
    expect(overlay.classList.contains("visible")).toBe(true);
    expect(overlay.getAttribute("aria-hidden")).toBe("false");
  });

  it("renders via portal into document.body", () => {
    render(<HelpModal {...defaultProps} />);
    const overlay = document.body.querySelector(".modal-nav-overlay");
    expect(overlay).toBeTruthy();
    expect(overlay!.parentElement).toBe(document.body);
  });

  it("has role=dialog and aria-modal on modal element", () => {
    render(<HelpModal {...defaultProps} />);
    const dialog = screen.getByRole("dialog");
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(dialog.getAttribute("aria-labelledby")).toBe("help-modal-title");
  });

  it("has unique titleId (help-modal-title)", () => {
    render(<HelpModal {...defaultProps} />);
    const heading = document.getElementById("help-modal-title");
    expect(heading).toBeTruthy();
    expect(heading!.textContent).toBe("Help");
  });

  it("calls onClose when clicking overlay background", () => {
    const onClose = vi.fn();
    render(<HelpModal {...defaultProps} onClose={onClose} />);
    const overlay = screen.getByTestId("bn-help-overlay");
    fireEvent.click(overlay);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("does not call onClose when clicking inside modal", () => {
    const onClose = vi.fn();
    render(<HelpModal {...defaultProps} onClose={onClose} />);
    const dialog = screen.getByRole("dialog");
    fireEvent.click(dialog);
    expect(onClose).not.toHaveBeenCalled();
  });

  it("calls onClose on Escape key", () => {
    const onClose = vi.fn();
    render(<HelpModal {...defaultProps} onClose={onClose} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("renders close button", () => {
    const onClose = vi.fn();
    render(<HelpModal {...defaultProps} onClose={onClose} />);
    const btn = screen.getByRole("button", { name: "Close" });
    expect(btn).toBeTruthy();
    fireEvent.click(btn);
    expect(onClose).toHaveBeenCalledOnce();
  });
});

describe("HelpModal — navigation", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows 5 top-level nav items", () => {
    render(<HelpModal {...defaultProps} />);
    const nav = screen.getByRole("navigation", { name: "Help sections" });
    const buttons = within(nav).getAllByRole("button");
    // Help, Shortcuts, Signals, Codebook, Privacy, About (disclosure)
    expect(buttons.length).toBe(6);
  });

  it("defaults to Help section", () => {
    render(<HelpModal {...defaultProps} />);
    // The content heading shows the active section label
    expect(screen.getByText("Sections and themes")).toBeTruthy();
  });

  it("switches to Shortcuts section on click", () => {
    render(<HelpModal {...defaultProps} />);
    fireEvent.click(screen.getByRole("button", { name: "Shortcuts" }));
    // Shortcuts section has the keyboard grid
    expect(screen.getByText("Next quote")).toBeTruthy();
    expect(screen.getByText("Star quote(s)")).toBeTruthy();
  });

  it("switches to Signals section on click", () => {
    render(<HelpModal {...defaultProps} />);
    fireEvent.click(screen.getByRole("button", { name: "Signals" }));
    expect(screen.getByText("Sentiment signals")).toBeTruthy();
  });

  it("switches to Codebook section on click", () => {
    render(<HelpModal {...defaultProps} />);
    fireEvent.click(screen.getByRole("button", { name: "Codebook" }));
    expect(screen.getByText("Sections and themes")).toBeTruthy();
  });

  it("opens to Shortcuts section via initialSection prop", () => {
    render(<HelpModal {...defaultProps} initialSection="shortcuts" />);
    expect(screen.getByText("Next quote")).toBeTruthy();
    expect(screen.getByText("Star quote(s)")).toBeTruthy();
  });

  it("resets to initialSection on reopen", () => {
    const { rerender } = render(<HelpModal {...defaultProps} initialSection="help" />);
    // Navigate away from Help
    fireEvent.click(screen.getByRole("button", { name: "Shortcuts" }));
    expect(screen.getByText("Next quote")).toBeTruthy();
    // Close and reopen
    rerender(<HelpModal {...defaultProps} open={false} initialSection="help" />);
    rerender(<HelpModal {...defaultProps} open={true} initialSection="help" />);
    // Should be back on Help landing
    expect(screen.getByText("Sections and themes")).toBeTruthy();
  });
});

describe("HelpModal — disclosure group", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders About as a disclosure button", () => {
    render(<HelpModal {...defaultProps} />);
    const aboutBtn = screen.getByRole("button", { name: /About/ });
    expect(aboutBtn.getAttribute("aria-expanded")).toBe("false");
  });

  it("expands About to show Developer, Design, Contributing", () => {
    render(<HelpModal {...defaultProps} />);
    const aboutBtn = screen.getByRole("button", { name: /About/ });
    fireEvent.click(aboutBtn);
    expect(aboutBtn.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByRole("button", { name: "Developer" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Design" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Contributing" })).toBeTruthy();
  });

  it("navigates to Contributing sub-section", () => {
    render(<HelpModal {...defaultProps} />);
    // Expand About
    fireEvent.click(screen.getByRole("button", { name: /About/ }));
    // Click Contributing
    fireEvent.click(screen.getByRole("button", { name: "Contributing" }));
    expect(screen.getByText(/AGPL-3\.0/)).toBeTruthy();
  });
});

describe("HelpModal — shortcuts platform display (Mac)", () => {
  beforeEach(() => {
    mockIsMac.mockReturnValue(true);
  });

  afterEach(() => {
    cleanup();
  });

  it("renders ⌘. as a single <kbd> on Mac", () => {
    render(<HelpModal {...defaultProps} initialSection="shortcuts" />);
    const dialog = screen.getByRole("dialog");
    const kbds = Array.from(dialog.querySelectorAll("kbd")).map((k) => k.textContent);
    // ⌘. for "Toggle both sidebars" — ⌘, is commented out (browser intercepts)
    expect(kbds).toContain("\u2318.");
  });

  it("renders ⇧J and ⇧K for extend selection", () => {
    render(<HelpModal {...defaultProps} initialSection="shortcuts" />);
    const dialog = screen.getByRole("dialog");
    const kbds = Array.from(dialog.querySelectorAll("kbd")).map((k) => k.textContent);
    expect(kbds).toContain("\u21E7J");
    expect(kbds).toContain("\u21E7K");
  });
});

describe("HelpModal — shortcuts platform display (non-Mac)", () => {
  beforeEach(() => {
    mockIsMac.mockReturnValue(false);
  });

  afterEach(() => {
    cleanup();
  });

  it("renders Ctrl and Shift as text labels", () => {
    render(<HelpModal {...defaultProps} initialSection="shortcuts" />);
    const dialog = screen.getByRole("dialog");
    const kbds = Array.from(dialog.querySelectorAll("kbd")).map((k) => k.textContent);
    expect(kbds).toContain("Ctrl");
    expect(kbds).toContain("Shift");
  });

  it("does not render Mac glyph symbols", () => {
    render(<HelpModal {...defaultProps} initialSection="shortcuts" />);
    const dialog = screen.getByRole("dialog");
    const allKbdText = Array.from(dialog.querySelectorAll("kbd"))
      .map((k) => k.textContent)
      .join("");
    expect(allKbdText).not.toContain("\u2318");
    expect(allKbdText).not.toContain("\u21E7");
  });
});

describe("HelpModal — responsive dropdown", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders a dropdown select with all sections", () => {
    render(<HelpModal {...defaultProps} />);
    const select = screen.getByRole("combobox", { name: "Help section" });
    expect(select).toBeTruthy();
    const options = within(select).getAllByRole("option");
    // Help, Shortcuts, Signals, Codebook, Privacy + About children (Developer, Design, Contributing, Acknowledgements) = 9
    expect(options.length).toBe(9);
  });
});
