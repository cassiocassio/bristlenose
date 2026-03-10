/**
 * Tests for PlaygroundFab — floating quick-open button for the playground.
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PlaygroundFab } from "./PlaygroundFab";

// ── Mocks ────────────────────────────────────────────────────────────────

const mockTogglePlayground = vi.fn();
let mockOpen = false;

vi.mock("../contexts/PlaygroundStore", () => ({
  usePlaygroundStore: () => ({ open: mockOpen }),
  togglePlayground: (...args: unknown[]) => mockTogglePlayground(...args),
}));

// ── Setup ────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();
  mockOpen = false;
});

// ── Tests ────────────────────────────────────────────────────────────────

describe("PlaygroundFab", () => {
  it("renders when playground is closed", () => {
    render(<PlaygroundFab />);
    expect(screen.getByTestId("pg-fab")).toBeTruthy();
  });

  it("is hidden when playground is open", () => {
    mockOpen = true;
    render(<PlaygroundFab />);
    expect(screen.queryByTestId("pg-fab")).toBeNull();
  });

  it("calls togglePlayground on click", () => {
    render(<PlaygroundFab />);
    fireEvent.click(screen.getByTestId("pg-fab"));
    expect(mockTogglePlayground).toHaveBeenCalledOnce();
  });

  it("has accessible label", () => {
    render(<PlaygroundFab />);
    expect(screen.getByLabelText("Open responsive playground")).toBeTruthy();
  });

  it("includes keyboard shortcut in title", () => {
    render(<PlaygroundFab />);
    const btn = screen.getByTestId("pg-fab");
    expect(btn.getAttribute("title")).toContain("Ctrl+Shift+P");
  });
});
