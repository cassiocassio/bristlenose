import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));
vi.mock("../hooks/useProjectId", () => ({ useProjectId: () => "1" }));
vi.mock("../contexts/FocusContext", () => ({ useFocus: () => ({ selectedIds: new Set() }) }));
vi.mock("../contexts/QuotesContext", () => ({
  useQuotesStore: () => ({ hidden: {}, starred: {}, tags: {}, quotes: [] }),
  filterStateOf: () => ({}),
}));
vi.mock("../utils/filter", () => ({ filterQuotes: (qs: unknown[]) => qs }));
vi.mock("../utils/exportActions", () => ({
  copyQuotesToClipboard: vi.fn(),
  saveQuotesSpreadsheet: vi.fn(),
  extractVideoClips: vi.fn(),
  exportScreens: vi.fn(),
}));

import { ExportDropdown } from "./ExportDropdown";
import { exportScreens } from "../utils/exportActions";

function openAt(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <ExportDropdown onExportReport={vi.fn()} onSendToMiro={vi.fn()} />
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByRole("button", { name: "buttons.export" }));
}

describe("ExportDropdown — the Screens lens's export", () => {
  it("is offered on the Screens lens and starts the folder export", () => {
    openAt("/report/screens/");
    fireEvent.click(screen.getByTestId("export-screens"));
    expect(exportScreens).toHaveBeenCalledTimes(1);
  });

  it("is not offered on another lens: the menu morphs with the lens", () => {
    openAt("/report/quotes/");
    expect(screen.queryByTestId("export-screens")).toBeNull();
  });
});
