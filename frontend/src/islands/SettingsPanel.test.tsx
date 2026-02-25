import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SettingsPanel } from "./SettingsPanel";

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  localStorage.clear();
  // Reset <html> attributes
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.style.colorScheme = "";
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SettingsPanel", () => {
  it("renders three radio buttons", () => {
    render(<SettingsPanel />);
    const radios = screen.getAllByRole("radio");
    expect(radios).toHaveLength(3);
  });

  it("defaults to auto when no saved preference", () => {
    render(<SettingsPanel />);
    const auto = screen.getByRole("radio", { name: /system appearance/i });
    expect(auto).toBeChecked();
  });

  it("restores saved preference from localStorage", () => {
    localStorage.setItem("bristlenose-appearance", "dark");
    render(<SettingsPanel />);
    const dark = screen.getByRole("radio", { name: /dark/i });
    expect(dark).toBeChecked();
  });

  it("applies data-theme and colorScheme for dark mode", async () => {
    const user = userEvent.setup();
    render(<SettingsPanel />);
    const dark = screen.getByRole("radio", { name: /dark/i });
    await user.click(dark);

    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(document.documentElement.style.colorScheme).toBe("dark");
  });

  it("applies data-theme and colorScheme for light mode", async () => {
    const user = userEvent.setup();
    render(<SettingsPanel />);
    const light = screen.getByRole("radio", { name: /^light$/i });
    await user.click(light);

    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(document.documentElement.style.colorScheme).toBe("light");
  });

  it("removes data-theme for auto mode", async () => {
    const user = userEvent.setup();
    render(<SettingsPanel />);

    // First set to dark
    await user.click(screen.getByRole("radio", { name: /dark/i }));
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");

    // Then back to auto
    await user.click(screen.getByRole("radio", { name: /system appearance/i }));
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
    expect(document.documentElement.style.colorScheme).toBe("light dark");
  });

  it("persists choice to localStorage", async () => {
    const user = userEvent.setup();
    render(<SettingsPanel />);
    await user.click(screen.getByRole("radio", { name: /dark/i }));

    expect(localStorage.getItem("bristlenose-appearance")).toBe("dark");
  });

  it("falls back to auto for invalid localStorage value", () => {
    localStorage.setItem("bristlenose-appearance", "banana");
    render(<SettingsPanel />);
    const auto = screen.getByRole("radio", { name: /system appearance/i });
    expect(auto).toBeChecked();
  });
});
