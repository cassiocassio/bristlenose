import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));
vi.mock("../hooks/useProjectId", () => ({ useProjectId: () => "1" }));
vi.mock("../contexts/FocusContext", () => ({ useFocus: () => ({ selectedIds: new Set() }) }));
vi.mock("../contexts/QuotesContext", () => ({
  useQuotesStore: () => ({
    searchQuery: "",
    viewMode: "all",
    tagFilter: null,
    hidden: {},
    starred: {},
    tags: {},
    quotes: [],
  }),
}));
vi.mock("../utils/filter", () => ({ filterQuotes: () => [] }));
vi.mock("../utils/exportActions", () => ({
  copyQuotesToClipboard: vi.fn(),
  saveQuotesSpreadsheet: vi.fn(),
  extractVideoClips: vi.fn(),
}));

import { ExportDropdown } from "./ExportDropdown";
import { _resetSubtitlePrefsForTests, getSubtitlePrefs } from "../utils/subtitlePrefs";

function openMenu() {
  render(
    <MemoryRouter initialEntries={["/report/quotes"]}>
      <ExportDropdown onExportReport={vi.fn()} onSendToMiro={vi.fn()} />
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByRole("button", { name: "buttons.export" }));
  return screen.getByTestId("export-clips-burn");
}

beforeEach(() => {
  localStorage.clear();
  _resetSubtitlePrefsForTests();
});

describe("ExportDropdown — burn subtitles checkbox", () => {
  it("is an unchecked menu checkbox by default", () => {
    const row = openMenu();
    expect(row).toHaveAttribute("role", "menuitemcheckbox");
    expect(row).toHaveAttribute("aria-checked", "false");
  });

  it("toggles on click and leaves the menu open", () => {
    const row = openMenu();
    fireEvent.click(row);
    expect(getSubtitlePrefs().burnSubtitles).toBe(true);
    expect(screen.getByTestId("export-clips-burn")).toHaveAttribute("aria-checked", "true");
    expect(screen.getByTestId("export-dropdown-menu")).toBeInTheDocument();
  });

  it("toggles exactly once from the keyboard", () => {
    const row = openMenu();
    act(() => row.focus());
    fireEvent.keyDown(row, { key: "Enter" });
    expect(getSubtitlePrefs().burnSubtitles).toBe(true);
    fireEvent.keyDown(screen.getByTestId("export-clips-burn"), { key: " " });
    expect(getSubtitlePrefs().burnSubtitles).toBe(false);
  });
});
