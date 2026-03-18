/**
 * Tests for SettingsModal — open/close, nav switching, disclosure toggle,
 * appearance persistence, language selector, focus management.
 */

import { render, screen, fireEvent, cleanup, within } from "@testing-library/react";
import { SettingsModal } from "./SettingsModal";

// Mock the locale store.
const mockLocale = { locale: "en" as const };
const mockSetLocale = vi.fn();
vi.mock("../i18n/LocaleStore", () => ({
  useLocaleStore: () => mockLocale,
  setLocale: (...args: unknown[]) => mockSetLocale(...args),
}));

vi.mock("../i18n", () => ({
  SUPPORTED_LOCALES: ["en", "es", "ja", "fr", "de", "ko"] as const,
}));

describe("SettingsModal", () => {
  afterEach(() => {
    cleanup();
    localStorage.clear();
  });

  // ── Open / close ──────────────────────────────────────────────────────

  it("renders overlay without visible class when closed", () => {
    render(<SettingsModal open={false} onClose={vi.fn()} />);
    const overlay = screen.getByTestId("bn-settings-overlay");
    expect(overlay.classList.contains("visible")).toBe(false);
    expect(overlay.getAttribute("aria-hidden")).toBe("true");
  });

  it("renders overlay with visible class when open", () => {
    render(<SettingsModal open={true} onClose={vi.fn()} />);
    const overlay = screen.getByTestId("bn-settings-overlay");
    expect(overlay.classList.contains("visible")).toBe(true);
    expect(overlay.getAttribute("aria-hidden")).toBe("false");
  });

  it("renders via portal into document.body", () => {
    render(<SettingsModal open={true} onClose={vi.fn()} />);
    const overlay = document.body.querySelector(".settings-overlay");
    expect(overlay).toBeTruthy();
    expect(overlay!.parentElement).toBe(document.body);
  });

  it("renders dialog with correct ARIA attributes", () => {
    render(<SettingsModal open={true} onClose={vi.fn()} />);
    const dialog = screen.getByRole("dialog");
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(dialog.getAttribute("aria-labelledby")).toBe("modal-nav-title");
  });

  it("calls onClose when clicking close button", () => {
    const onClose = vi.fn();
    render(<SettingsModal open={true} onClose={onClose} />);
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when clicking overlay background", () => {
    const onClose = vi.fn();
    render(<SettingsModal open={true} onClose={onClose} />);
    fireEvent.click(screen.getByTestId("bn-settings-overlay"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("does not call onClose when clicking inside modal", () => {
    const onClose = vi.fn();
    render(<SettingsModal open={true} onClose={onClose} />);
    fireEvent.click(screen.getByRole("dialog"));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("calls onClose on Escape key", () => {
    const onClose = vi.fn();
    render(<SettingsModal open={true} onClose={onClose} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });

  // ── Title and heading ─────────────────────────────────────────────────

  it("renders Settings title", () => {
    render(<SettingsModal open={true} onClose={vi.fn()} />);
    expect(screen.getByText("Settings")).toBeTruthy();
  });

  // ── Navigation ────────────────────────────────────────────────────────

  it("shows General section by default with content heading", () => {
    render(<SettingsModal open={true} onClose={vi.fn()} />);
    // Content heading should say "General"
    const headings = screen.getAllByText("General");
    expect(headings.length).toBeGreaterThanOrEqual(2); // nav item + content heading
  });

  it("shows all 5 nav items", () => {
    render(<SettingsModal open={true} onClose={vi.fn()} />);
    const nav = screen.getByRole("navigation", { name: /sections/i });
    expect(within(nav).getByText("General")).toBeTruthy();
    expect(within(nav).getByText("Project")).toBeTruthy();
    expect(within(nav).getByText("Profile")).toBeTruthy();
    expect(within(nav).getByText("API Keys")).toBeTruthy();
    expect(within(nav).getByText("Config")).toBeTruthy();
  });

  it("switches to Project section on nav click", () => {
    render(<SettingsModal open={true} onClose={vi.fn()} />);
    const nav = screen.getByRole("navigation", { name: /sections/i });
    fireEvent.click(within(nav).getByText("Project"));
    expect(screen.getByText("Per-project settings will appear here. Coming soon.")).toBeTruthy();
  });

  it("switches to Profile section on nav click", () => {
    render(<SettingsModal open={true} onClose={vi.fn()} />);
    const nav = screen.getByRole("navigation", { name: /sections/i });
    fireEvent.click(within(nav).getByText("Profile"));
    expect(screen.getByText(/Profile settings/)).toBeTruthy();
  });

  it("switches to API Keys section on nav click", () => {
    render(<SettingsModal open={true} onClose={vi.fn()} />);
    const nav = screen.getByRole("navigation", { name: /sections/i });
    fireEvent.click(within(nav).getByText("API Keys"));
    expect(screen.getByText(/API key management/)).toBeTruthy();
  });

  // ── Disclosure (Config sub-items) ─────────────────────────────────────

  it("expands Config disclosure on click", () => {
    render(<SettingsModal open={true} onClose={vi.fn()} />);
    const nav = screen.getByRole("navigation", { name: /sections/i });
    const configBtn = within(nav).getByRole("button", { name: /Config/ });
    expect(configBtn.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(configBtn);
    expect(configBtn.getAttribute("aria-expanded")).toBe("true");

    // Sub-items should now be visible in the sidebar
    expect(within(nav).getByText("LLM Provider & Model")).toBeTruthy();
    expect(within(nav).getByText("Transcription")).toBeTruthy();
    expect(within(nav).getByText("Privacy")).toBeTruthy();
  });

  it("shows config reference content when clicking a sub-category", () => {
    render(<SettingsModal open={true} onClose={vi.fn()} />);
    const nav = screen.getByRole("navigation", { name: /sections/i });
    // Expand Config
    fireEvent.click(within(nav).getByRole("button", { name: /Config/ }));
    // Click LLM sub-category
    fireEvent.click(within(nav).getByText("LLM Provider & Model"));
    // Should show config reference rows
    expect(screen.getByText("Provider")).toBeTruthy();
    expect(screen.getByText("BRISTLENOSE_LLM_PROVIDER")).toBeTruthy();
  });

  it("collapses Config disclosure on second click", () => {
    render(<SettingsModal open={true} onClose={vi.fn()} />);
    const configBtn = screen.getByRole("button", { name: /Config/ });
    fireEvent.click(configBtn);
    expect(configBtn.getAttribute("aria-expanded")).toBe("true");

    fireEvent.click(configBtn);
    expect(configBtn.getAttribute("aria-expanded")).toBe("false");
  });

  // ── General section: Appearance ───────────────────────────────────────

  it("renders appearance radio buttons", () => {
    render(<SettingsModal open={true} onClose={vi.fn()} />);
    expect(screen.getByLabelText(/Use system appearance/)).toBeTruthy();
    expect(screen.getByLabelText("Light")).toBeTruthy();
    expect(screen.getByLabelText("Dark")).toBeTruthy();
  });

  it("auto radio is checked by default", () => {
    render(<SettingsModal open={true} onClose={vi.fn()} />);
    const auto = screen.getByLabelText(/Use system appearance/) as HTMLInputElement;
    expect(auto.checked).toBe(true);
  });

  it("persists appearance to localStorage", () => {
    render(<SettingsModal open={true} onClose={vi.fn()} />);
    fireEvent.click(screen.getByLabelText("Dark"));
    const stored = localStorage.getItem("bristlenose-appearance");
    expect(stored).toBe('"dark"');
  });

  it("reads saved appearance from localStorage", () => {
    localStorage.setItem("bristlenose-appearance", '"light"');
    render(<SettingsModal open={true} onClose={vi.fn()} />);
    const light = screen.getByLabelText("Light") as HTMLInputElement;
    expect(light.checked).toBe(true);
  });

  // ── General section: Language ──────────────────────────────────────────

  it("renders language selector with locales", () => {
    render(<SettingsModal open={true} onClose={vi.fn()} />);
    // Two comboboxes: nav dropdown (hidden on desktop) + language selector
    const selects = screen.getAllByRole("combobox") as HTMLSelectElement[];
    const langSelect = selects.find((s) => s.classList.contains("bn-locale-select") && s.options.length === 6);
    expect(langSelect).toBeTruthy();
    expect(langSelect!.value).toBe("en");
  });

  it("calls setLocale on language change", () => {
    render(<SettingsModal open={true} onClose={vi.fn()} />);
    const selects = screen.getAllByRole("combobox") as HTMLSelectElement[];
    const langSelect = selects.find((s) => s.classList.contains("bn-locale-select") && s.options.length === 6)!;
    fireEvent.change(langSelect, { target: { value: "es" } });
    expect(mockSetLocale).toHaveBeenCalledWith("es");
  });

  // ── Resets to General on reopen ───────────────────────────────────────

  it("resets to General section when reopened", () => {
    const { rerender } = render(<SettingsModal open={true} onClose={vi.fn()} />);
    // Navigate to API Keys
    const nav = screen.getByRole("navigation", { name: /sections/i });
    fireEvent.click(within(nav).getByText("API Keys"));
    expect(screen.getByText(/API key management/)).toBeTruthy();

    // Close and reopen
    rerender(<SettingsModal open={false} onClose={vi.fn()} />);
    rerender(<SettingsModal open={true} onClose={vi.fn()} />);

    // Should be back on General
    expect(screen.getByLabelText(/Use system appearance/)).toBeTruthy();
  });

  // ── Responsive dropdown ───────────────────────────────────────────────

  it("renders a dropdown select for narrow viewports", () => {
    render(<SettingsModal open={true} onClose={vi.fn()} />);
    // The dropdown is always rendered (CSS hides it on wide viewports)
    const selects = screen.getAllByRole("combobox");
    // One is the nav dropdown, one is the language selector
    expect(selects.length).toBe(2);
  });
});
