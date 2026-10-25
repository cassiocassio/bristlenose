import { render, screen, waitFor } from "@testing-library/react";
import { QuoteSections } from "./QuoteSections";
import { PlayerContext, resetVideoMapForTests } from "../contexts/PlayerContext";
import type { QuotesListResponse } from "../utils/types";
import { resetStore } from "../contexts/QuotesContext";

vi.mock("../utils/api", () => ({
  apiGet: vi.fn(),
  getCodebook: vi.fn(),
  patchEdits: vi.fn(() => Promise.resolve()),
}));

import { apiGet, getCodebook } from "../utils/api";

// N187. A quote from a participant with no recording (a transcript-only study, or one session
// of several without media) drew its timecode as a link: the Quotes lens passes hasMedia as a
// constant true, so the card said "play" and the click found no recording and did nothing. The
// card already has the other draw (a plain [mm:ss], as Dashboard and the transcript give a
// session without media); what it lacked was the truth.

const quote = (id: string, pid: string, t: number) => ({
  dom_id: id,
  text: `text of ${id}`,
  verbatim_excerpt: "text",
  participant_id: pid,
  session_id: pid === "p1" ? "s1" : "s2",
  speaker_name: pid,
  start_timecode: t,
  end_timecode: t + 5,
  sentiment: "negative",
  intensity: 3,
  researcher_context: null,
  quote_type: "section",
  topic_label: "Login",
  is_starred: false,
  is_hidden: false,
  edited_text: null,
  tags: [],
  deleted_badges: [],
  proposed_tags: [],
  segment_index: 0,
});

const DATA: QuotesListResponse = {
  sections: [
    {
      cluster_id: 1,
      screen_label: "Login",
      description: "",
      display_order: 1,
      edited_label: null,
      edited_description: null,
      is_new: false,
      quotes: [quote("q-p1-120", "p1", 120), quote("q-p2-240", "p2", 240)],
    },
  ],
  themes: [],
  total_quotes: 2,
  total_hidden: 0,
  total_starred: 0,
  has_moderator: false,
} as never;

beforeEach(() => {
  resetStore();
  vi.mocked(apiGet).mockResolvedValue(DATA);
  vi.mocked(getCodebook).mockResolvedValue({ all_tag_names: [], groups: [], ungrouped: [] } as never);
});

afterEach(() => resetVideoMapForTests({}));

function renderLens() {
  return render(
    <PlayerContext.Provider value={{ seekTo: vi.fn(), sendCommand: vi.fn() }}>
      <QuoteSections projectId="1" />
    </PlayerContext.Provider>,
  );
}

describe("Quotes lens timecodes with and without a recording (N187)", () => {
  it("links the timecode of a participant whose recording the player has (control)", async () => {
    resetVideoMapForTests({ p1: "/media/a.mp4", p2: "/media/b.mp4" });
    renderLens();
    await waitFor(() => expect(screen.getByText("text of q-p1-120")).toBeInTheDocument());
    expect(document.querySelector('a.timecode[data-participant="p1"]')).not.toBeNull();
    expect(document.querySelector('a.timecode[data-participant="p2"]')).not.toBeNull();
  });

  // Strict pin, awaiting a ruling (decisions-pending): drop `.fails` when it is built.
  it.fails("draws a plain [mm:ss], not a link, for a participant the player has no recording of", async () => {
    resetVideoMapForTests({ p1: "/media/a.mp4" }); // p2: no recording
    renderLens();
    await waitFor(() => expect(screen.getByText("text of q-p2-240")).toBeInTheDocument());
    expect(document.querySelector('a.timecode[data-participant="p1"]')).not.toBeNull();
    expect(document.querySelector('a.timecode[data-participant="p2"]')).toBeNull();
    expect(screen.getByText("[04:00]")).toBeInTheDocument();
  });
});
