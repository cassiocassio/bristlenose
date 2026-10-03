/**
 * The Export menu's "all" scope is the quotes the researcher can see, so it
 * must narrow with the search, tokens included. Uses the real store and the
 * real filter (ExportDropdown.subtitles.test.tsx stubs both).
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { addSearchToken, initFromQuotes, resetStore, setSearchQuery } from "../contexts/QuotesContext";
import { personToken } from "../utils/searchTokens";
import type { QuoteResponse } from "../utils/types";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));
vi.mock("../hooks/useProjectId", () => ({ useProjectId: () => "1" }));
vi.mock("../contexts/FocusContext", () => ({ useFocus: () => ({ selectedIds: new Set() }) }));
vi.mock("../utils/api", () => ({
  putHidden: vi.fn(),
  putStarred: vi.fn(),
  putEdits: vi.fn(),
  putTags: vi.fn(),
  putDeletedBadges: vi.fn(),
}));
vi.mock("../utils/exportActions", () => ({
  copyQuotesToClipboard: vi.fn(),
  saveQuotesSpreadsheet: vi.fn(),
  extractVideoClips: vi.fn(),
}));

import { ExportDropdown } from "./ExportDropdown";
import { saveQuotesSpreadsheet } from "../utils/exportActions";

const q = (dom_id: string, participant_id: string, text: string) =>
  ({
    dom_id, participant_id, text, verbatim_excerpt: text, session_id: "s1", speaker_name: participant_id,
    start_timecode: 0, end_timecode: 1, sentiment: null, intensity: 1, researcher_context: null,
    quote_type: "section", topic_label: "", is_starred: false, is_hidden: false, edited_text: null,
    tags: [], deleted_badges: [], proposed_tags: [], segment_index: 0,
  }) as QuoteResponse;

function exportAllAsSpreadsheet(): string[] {
  render(
    <MemoryRouter initialEntries={["/report/quotes"]}>
      <ExportDropdown onExportReport={vi.fn()} onSendToMiro={vi.fn()} />
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByRole("button", { name: "buttons.export" }));
  fireEvent.click(screen.getByTestId("export-spreadsheet-all"));
  const calls = vi.mocked(saveQuotesSpreadsheet).mock.calls;
  return calls[calls.length - 1][1] as string[];
}

beforeEach(() => {
  resetStore();
  vi.clearAllMocks();
  initFromQuotes([q("a", "p1", "the delivery was late"), q("b", "p2", "the delivery was fine"), q("c", "p2", "ok")]);
});

describe("ExportDropdown — the 'all' scope follows the search", () => {
  it("exports every quote when nothing narrows", () => {
    expect(exportAllAsSpreadsheet()).toEqual(["a", "b", "c"]);
  });

  it("narrows with a search token", () => {
    act(() => addSearchToken(personToken("p2")));
    expect(exportAllAsSpreadsheet()).toEqual(["b", "c"]);
  });

  it("narrows with a token and typed text together", () => {
    act(() => addSearchToken(personToken("p2")));
    act(() => setSearchQuery("delivery"));
    expect(exportAllAsSpreadsheet()).toEqual(["b"]);
  });
});
