import { resetNativePicker } from "../utils/speakerPicking";
import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from "vitest";
import {
  act,
  render as rtlRender,
  screen,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SessionsTable } from "./SessionsTable";
import { _resetEmbeddedCache } from "../utils/embedded";
import { _resetExportCache } from "../utils/exportData";
import { getUndoState, redo, resetUndoStore, undo } from "../contexts/UndoStore";
import { resetSpeakerNameQueue } from "../utils/speakerNames";
import { resetTapestryViews } from "../utils/tapestryScale";

// SessionsTable uses useNavigate (journey deep-links) — provide a Router.
const render = (ui: Parameters<typeof rtlRender>[0]) =>
  rtlRender(ui, { wrapper: MemoryRouter });

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const sessionsResponse = {
  sessions: [
    {
      session_id: "s1",
      session_number: 1,
      session_date: "2026-02-15",
      duration_seconds: 1800,
      has_media: false,
      has_video: false,
      thumbnail_url: null,
      speakers: [
        { speaker_code: "m1", name: "Sarah", role: "researcher" },
        { speaker_code: "p1", name: "Alice", role: "participant" },
      ],
      journey_labels: [],
      journey: [],
      sentiment_counts: {},
      source_files: [],
    },
    {
      session_id: "s2",
      session_number: 2,
      session_date: "2026-02-16",
      duration_seconds: 2400,
      has_media: false,
      has_video: false,
      thumbnail_url: null,
      speakers: [
        { speaker_code: "m1", name: "Sarah", role: "researcher" },
        { speaker_code: "p2", name: "Bob", role: "participant" },
      ],
      journey_labels: [],
      journey: [],
      sentiment_counts: {},
      source_files: [],
    },
  ],
  moderator_names: ["Sarah"],
  observer_names: [],
  source_folder_uri: "",
};

const peopleResponse: Record<string, { full_name: string; short_name: string; role: string }> = {
  m1: { full_name: "Sarah Chen", short_name: "Sarah", role: "UX Researcher" },
  p1: { full_name: "Alice Johnson", short_name: "Alice", role: "Product Manager" },
  p2: { full_name: "Bob", short_name: "Bob", role: "" },
};

// ---------------------------------------------------------------------------
// Fetch mock
// ---------------------------------------------------------------------------

function mockFetchResponses() {
  (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation(
    (url: string) => {
      if (url.includes("/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => sessionsResponse,
        });
      }
      if (url.includes("/people")) {
        return Promise.resolve({
          ok: true,
          json: async () => peopleResponse,
        });
      }
      return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
    },
  );
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
  // Module-level: an entry from one test must not be undone by the next.
  resetUndoStore();
  resetSpeakerNameQueue();
});

// ---------------------------------------------------------------------------
// Rendering tests
// ---------------------------------------------------------------------------

describe("SessionsTable", () => {
  it("renders session rows", async () => {
    mockFetchResponses();
    render(<SessionsTable projectId="1" />);
    expect(await screen.findByText("#1")).toBeTruthy();
    expect(screen.getByText("#2")).toBeTruthy();
  });

  it("renders durations as spans, never as clock times", async () => {
    // The defect this pins: the Duration column used to render MM:SS, so a
    // 30-minute session read "30:00" in a row that also carries a date and a
    // start time — a time of day at a glance. s1 is 1800s, s2 is 2400s.
    mockFetchResponses();
    render(<SessionsTable projectId="1" />);
    expect(await screen.findByText("30m")).toBeTruthy();
    expect(screen.getByText("40m")).toBeTruthy();
    // The invariant, not just the two examples: no duration cell may contain
    // a colon. Anchored on the cell class so a timecode elsewhere on the page
    // (quote positions legitimately use MM:SS) can never satisfy this.
    for (const cell of document.querySelectorAll(".bn-cell-duration")) {
      expect(cell.textContent).not.toContain(":");
    }
  });

  it("renders code-only badges (no name in badge)", async () => {
    mockFetchResponses();
    const { container } = render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    const badgeCodes = container.querySelectorAll(".bn-speaker-badge-code");
    expect(badgeCodes.length).toBeGreaterThanOrEqual(2);
    // Badge should not contain the name span — name is separate
    const badgeNames = container.querySelectorAll(
      ".bn-speaker-badge--split .bn-speaker-badge-name",
    );
    expect(badgeNames.length).toBe(0);
  });

  it("renders editable name text beside badges", async () => {
    mockFetchResponses();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    expect(screen.getByTestId("bn-name-p1")).toBeTruthy();
    expect(screen.getByTestId("bn-name-p1").textContent).toBe("Alice");
  });

  it("renders pencil buttons for each speaker", async () => {
    mockFetchResponses();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    expect(screen.getByTestId("bn-name-pencil-p1")).toBeTruthy();
    // m1 appears in both sessions
    expect(screen.getAllByTestId("bn-name-pencil-m1").length).toBe(2);
  });

  it("shows full_name as title when it differs from short_name", async () => {
    mockFetchResponses();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    // Alice Johnson (full) != Alice (short) → title should show full name
    const nameWrapper = screen.getByTestId("bn-name-p1").parentElement;
    expect(nameWrapper?.getAttribute("title")).toBe("Alice Johnson");
  });

  it("does not show title when full_name equals short_name", async () => {
    mockFetchResponses();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    // Bob (full) == Bob (short) → no title
    const nameWrapper = screen.getByTestId("bn-name-p2").parentElement;
    expect(nameWrapper?.getAttribute("title")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Editing tests
// ---------------------------------------------------------------------------

describe("SessionsTable name editing", () => {
  it("enters edit mode on pencil click", async () => {
    mockFetchResponses();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    const pencil = screen.getByTestId("bn-name-pencil-p1");
    fireEvent.click(pencil);
    const nameEl = screen.getByTestId("bn-name-p1");
    expect(nameEl.getAttribute("contenteditable")).toBe("true");
  });

  it("hides pencil during editing and restores it after commit", async () => {
    mockFetchResponses();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");

    // Pencil visible before editing
    expect(screen.getByTestId("bn-name-pencil-p1")).toBeTruthy();

    // Enter edit mode
    fireEvent.click(screen.getByTestId("bn-name-pencil-p1"));

    // Pencil gone during editing
    expect(screen.queryByTestId("bn-name-pencil-p1")).toBeNull();

    // Commit
    const nameEl = screen.getByTestId("bn-name-p1");
    nameEl.textContent = "Alicia";
    fireEvent.keyDown(nameEl, { key: "Enter" });

    // Pencil restored
    await waitFor(() => {
      expect(screen.getByTestId("bn-name-pencil-p1")).toBeTruthy();
    });
  });

  it("a click on the name opens the picker; the pencil is what edits in place", async () => {
    // Changed 4 Oct 2026 (design-people.md § UX iteration 3): the name and its
    // badge ask "who is this?" — the picker — and spelling fixes stay with the
    // pencil.
    mockFetchResponses();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    const nameEl = screen.getByTestId("bn-name-p1");
    fireEvent.click(nameEl.parentElement!);
    expect(nameEl.getAttribute("contenteditable")).not.toBe("true");
    // The picker is loaded on first open, so it arrives a tick after the click.
    await waitFor(() => expect(document.querySelector(".bn-person-picker")).not.toBeNull());
  });

  it("commits on Enter and updates display", async () => {
    mockFetchResponses();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");

    // Enter edit mode
    fireEvent.click(screen.getByTestId("bn-name-pencil-p1"));
    const nameEl = screen.getByTestId("bn-name-p1");

    // Simulate typing a new name
    nameEl.textContent = "Alicia";
    fireEvent.keyDown(nameEl, { key: "Enter" });

    // Name should be updated optimistically
    await waitFor(() => {
      expect(screen.getByTestId("bn-name-p1").textContent).toBe("Alicia");
    });

    // A participant is named through /people (written through to
    // people.yaml), then the slot says yes on the per-session route.
    const putCalls = () =>
      (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.filter(
        (call: unknown[]) => (call[1] as { method?: string } | undefined)?.method === "PUT",
      );
    await waitFor(() => expect(putCalls().length).toBe(2));
    expect(putCalls()[0][0]).toMatch(/\/people$/);
    expect(JSON.parse((putCalls()[0][1] as { body: string }).body).p1.short_name).toBe("Alicia");
    expect(putCalls()[1][0]).toMatch(/\/sessions\/s1\/speakers\/p1$/);
    expect(JSON.parse((putCalls()[1][1] as { body: string }).body)).toEqual({ confirmed: true });
  });

  it("cancels on Escape without changing name", async () => {
    mockFetchResponses();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");

    fireEvent.click(screen.getByTestId("bn-name-pencil-p1"));
    const nameEl = screen.getByTestId("bn-name-p1");

    // Type something but then Escape
    nameEl.textContent = "Changed";
    fireEvent.keyDown(nameEl, { key: "Escape" });

    // Should revert — no PUT fired
    await waitFor(() => {
      expect(nameEl.getAttribute("contenteditable")).not.toBe("true");
    });
    // No PUT calls
    const putCalls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.filter(
      (call: unknown[]) => {
        const opts = call[1] as { method?: string } | undefined;
        return opts?.method === "PUT";
      },
    );
    expect(putCalls.length).toBe(0);
  });

  it("commits on blur", async () => {
    mockFetchResponses();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");

    fireEvent.click(screen.getByTestId("bn-name-pencil-p1"));
    const nameEl = screen.getByTestId("bn-name-p1");

    nameEl.textContent = "Ali";
    fireEvent.blur(nameEl);

    await waitFor(() => {
      expect(screen.getByTestId("bn-name-p1").textContent).toBe("Ali");
    });
  });

  it("m1 appears in both sessions", async () => {
    mockFetchResponses();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");

    // m1 (Sarah) appears in session 1 and session 2
    const m1Names = screen.getAllByTestId("bn-name-m1");
    expect(m1Names.length).toBe(2);
    expect(m1Names[0].textContent).toBe("Sarah");
    expect(m1Names[1].textContent).toBe("Sarah");
  });

  it("renders moderator header", async () => {
    mockFetchResponses();
    render(<SessionsTable projectId="1" />);
    expect(await screen.findByText("Moderated by Sarah")).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// Folder proxy (Interviews header) — reveal-in-Finder vs copy-path fork
// ---------------------------------------------------------------------------

describe("SessionsTable folder proxy", () => {
  const FOLDER_URI = "file:///Users/x/Interviews";

  function mockFetchWithFolder() {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      (url: string) => {
        if (url.includes("/sessions")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({ ...sessionsResponse, source_folder_uri: FOLDER_URI }),
          });
        }
        if (url.includes("/people")) {
          return Promise.resolve({ ok: true, json: async () => peopleResponse });
        }
        return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
      },
    );
  }

  afterEach(() => {
    delete (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__;
    delete (window as unknown as Record<string, unknown>).webkit;
    _resetEmbeddedCache();
  });

  it("copies the folder path to the clipboard in the browser", async () => {
    _resetEmbeddedCache(); // ensure not embedded
    const writeText = vi.fn();
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    mockFetchWithFolder();
    const { container } = render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");

    const link = container.querySelector(".bn-interviews-link") as HTMLElement;
    expect(link).toBeTruthy();
    fireEvent.click(link);

    expect(writeText).toHaveBeenCalledWith(FOLDER_URI);
  });

  it("reveals the folder in Finder via the native bridge when embedded", async () => {
    (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__ = true;
    _resetEmbeddedCache();
    const postMessage = vi.fn();
    (window as unknown as Record<string, unknown>).webkit = {
      messageHandlers: { navigation: { postMessage } },
    };
    const writeText = vi.fn();
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    mockFetchWithFolder();
    const { container } = render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");

    const link = container.querySelector(".bn-interviews-link") as HTMLElement;
    fireEvent.click(link);

    expect(postMessage).toHaveBeenCalledWith({
      type: "project-action",
      action: "reveal-in-finder",
      data: { uri: FOLDER_URI },
    });
    expect(writeText).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Export mode (offline leave-behind) — read-only
// ---------------------------------------------------------------------------

describe("SessionsTable in export mode", () => {
  beforeEach(() => {
    // Export mode has no server: apiGet resolves reads from the embedded blob
    // and throws on a miss, so both endpoints the table fetches must be here.
    (window as unknown as Record<string, unknown>).BRISTLENOSE_EXPORT = {
      version: 1,
      exported_at: "2026-08-15T00:00:00Z",
      health: {},
      endpoints: { "/sessions": sessionsResponse, "/people": peopleResponse },
    };
    _resetExportCache();
  });

  afterEach(() => {
    delete (window as unknown as Record<string, unknown>).BRISTLENOSE_EXPORT;
    _resetExportCache();
  });

  it("does not render the name pencil (removed, not left dead)", async () => {
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");

    // Positive assertion first: without it, this test would also pass if the
    // table failed to render at all — and "nothing rendered" is exactly the
    // failure a queryBy(...).toBeNull() assertion cannot distinguish.
    expect(screen.getByTestId("bn-name-p1").textContent).toBe("Alice");

    expect(screen.queryByTestId("bn-name-pencil-p1")).toBeNull();
    expect(screen.queryByTestId("bn-name-pencil-m1")).toBeNull();
  });

  it("does not enter edit mode when the name text is clicked", async () => {
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");

    const nameEl = screen.getByTestId("bn-name-p1");
    fireEvent.click(nameEl.parentElement!);

    expect(nameEl.getAttribute("contenteditable")).not.toBe("true");
  });
});

// ---------------------------------------------------------------------------
// Degraded reads and assistive-tech exposure
// ---------------------------------------------------------------------------

describe("SessionsTable when /people fails", () => {
  it("still renders speaker names from /sessions, and says so", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      (url: string) => {
        if (url.includes("/people")) {
          return Promise.resolve({ ok: false, status: 500, json: async () => ({}) });
        }
        return Promise.resolve({ ok: true, json: async () => sessionsResponse });
      },
    );

    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");

    // The outcome that matters: a failed /people is a degraded read, not a
    // blank table. /sessions already carries a server-resolved display name,
    // so the names must survive it.
    expect(screen.getByTestId("bn-name-p1").textContent).toBe("Alice");
    // getAll, not get: m1 appears in both sessions and the test id is keyed by
    // speaker code, so two rows carry the same one. That duplication is the
    // per-session/global code split showing through into the DOM.
    const moderators = screen.getAllByTestId("bn-name-m1");
    expect(moderators).toHaveLength(2);
    moderators.forEach((el) => expect(el.textContent).toBe("Sarah"));

    // And it must not be silent. Before this, an empty catch made a broken
    // fetch indistinguishable from speakers who genuinely have no names.
    await waitFor(() => expect(warn).toHaveBeenCalled());
    warn.mockRestore();
  });
});

describe("SessionsTable speaker names and assistive tech", () => {
  beforeEach(mockFetchResponses);

  it("does not hide the narrow-width short name from assistive tech", async () => {
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");

    // Between 750px and 480px container width the CSS ladder hides
    // .bn-speaker-name-full and shows .bn-speaker-name-short. While the short
    // span carried aria-hidden, that band exposed NO speaker name at all — a
    // screen reader heard the badge code and nothing else.
    //
    // Honest about what this can and can't prove: jsdom applies no container
    // queries, so this pins the attribute rather than the announcement. The
    // announcement itself needs a real engine (axe-core in the e2e layer),
    // which does not exist yet. It still fails if the aria-hidden returns.
    const shortNames = document.querySelectorAll(".bn-speaker-name-short");
    expect(shortNames.length).toBeGreaterThan(0);
    shortNames.forEach((el) => {
      expect(el.getAttribute("aria-hidden")).toBeNull();
    });
  });
});

// ---------------------------------------------------------------------------
// Moderators are named per session
// ---------------------------------------------------------------------------
//
// Moderator codes restart in every session, so two sessions' `m1` are two
// people, and /people — keyed by code — holds only one of their names. The
// table must show each session's own (from /sessions), open one editor at a
// time, and rename one session's moderator without touching the other.

const twoModerators = {
  ...sessionsResponse,
  sessions: [
    {
      ...sessionsResponse.sessions[0],
      speakers: [
        { speaker_code: "m1", name: "Martin", role: "researcher", person: "id-martin" },
        { speaker_code: "p1", name: "Alice", role: "participant" },
      ],
    },
    {
      ...sessionsResponse.sessions[1],
      speakers: [
        { speaker_code: "m1", name: "Jo", role: "researcher", person: "id-jo" },
        { speaker_code: "p2", name: "Bob", role: "participant" },
      ],
    },
  ],
  moderator_names: ["Martin", "Jo"],
};

function mockTwoModerators() {
  (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation(
    (url: string) => {
      if (url.includes("/sessions")) {
        return Promise.resolve({ ok: true, json: async () => twoModerators });
      }
      if (url.includes("/people")) {
        // What the server sends: one m1, whichever session's came last.
        return Promise.resolve({
          ok: true,
          json: async () => ({ ...peopleResponse, m1: { full_name: "Jo Lee", short_name: "Jo", role: "" } }),
        });
      }
      return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
    },
  );
}

function putCalls(): Array<{ url: string; body: unknown }> {
  return (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls
    .filter((call: unknown[]) => (call[1] as { method?: string } | undefined)?.method === "PUT")
    .map((call: unknown[]) => ({
      url: call[0] as string,
      body: JSON.parse((call[1] as { body: string }).body),
    }));
}

// Route C Phase 1: the server shows each moderator under the identity's code
// (session 2's reads m2) and reports the transcript's own token as slot_code.
const identityCodes = {
  ...twoModerators,
  sessions: [
    {
      ...twoModerators.sessions[0],
      speakers: [
        { speaker_code: "m1", slot_code: "m1", name: "Martin", role: "researcher", person: "id-martin" },
        { speaker_code: "p1", slot_code: "p1", name: "Alice", role: "participant" },
      ],
    },
    {
      ...twoModerators.sessions[1],
      speakers: [
        { speaker_code: "m2", slot_code: "m1", name: "Jo", role: "researcher", person: "id-jo" },
        { speaker_code: "p2", slot_code: "p2", name: "Bob", role: "participant" },
      ],
    },
  ],
};

describe("SessionsTable addresses a slot by its slot code", () => {
  it("writes to the slot, not to the identity code the badge shows, and undo follows", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation((url: string) =>
      Promise.resolve(
        url.includes("/sessions")
          ? { ok: true, json: async () => identityCodes }
          : url.includes("/people")
            ? { ok: true, json: async () => peopleResponse }
            : { ok: false, status: 404, json: async () => ({}) },
      ),
    );
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    fireEvent.click(screen.getByTestId("bn-name-pencil-m2"));
    const editing = screen.getByTestId("bn-name-m2");
    editing.textContent = "Joanna";
    fireEvent.keyDown(editing, { key: "Enter" });

    // A pick can renumber identities, so m2 is never an address: the slot is.
    await waitFor(() => expect(putCalls()).toHaveLength(1));
    expect(putCalls()[0].url).toMatch(/\/sessions\/s2\/speakers\/m1$/);

    await act(async () => {
      await undo();
    });
    await waitFor(() => expect(putCalls()).toHaveLength(2));
    expect(putCalls()[1].url).toMatch(/\/sessions\/s2\/speakers\/m1$/);
    expect(screen.getByTestId("bn-name-m2").textContent).toBe("Jo");
  });
});

describe("SessionsTable moderators are named per session", () => {
  it("shows each session's own moderator, not /people's single m1", async () => {
    mockTwoModerators();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    await waitFor(() => {
      const [s1, s2] = screen.getAllByTestId("bn-name-m1");
      expect(s1.textContent).toBe("Martin");
      expect(s2.textContent).toBe("Jo");
    });
  });

  it("opens one editor, in the session clicked", async () => {
    mockTwoModerators();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    fireEvent.click(screen.getAllByTestId("bn-name-pencil-m1")[1]);
    const [s1, s2] = screen.getAllByTestId("bn-name-m1");
    expect(s2.getAttribute("contenteditable")).toBe("true");
    expect(s1.getAttribute("contenteditable")).not.toBe("true");
  });

  it("renames one session's moderator with one per-session PUT", async () => {
    mockTwoModerators();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    fireEvent.click(screen.getAllByTestId("bn-name-pencil-m1")[1]);
    const editing = screen.getAllByTestId("bn-name-m1")[1];
    editing.textContent = "Joanna";
    fireEvent.keyDown(editing, { key: "Enter" });

    await waitFor(() => {
      const [s1, s2] = screen.getAllByTestId("bn-name-m1");
      expect(s2.textContent).toBe("Joanna");
      expect(s1.textContent).toBe("Martin");
    });
    // The wire, not just the render: exactly one write, to this session,
    // carrying the slot's whole state (what an undo puts back). This fixture
    // predates /sessions reporting full_name, so none is sent — the stored
    // one is left alone rather than blanked.
    await waitFor(() => expect(putCalls()).toHaveLength(1));
    const puts = putCalls();
    expect(puts[0].url).toMatch(/\/sessions\/s2\/speakers\/m1$/);
    expect(puts[0].body).toEqual({ person: "id-jo", short_name: "Joanna", confirmed: true, kind: "moderator" });
  });

  it("Edit ▸ Undo puts the session's moderator back, name and flag", async () => {
    mockTwoModerators();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    fireEvent.click(screen.getAllByTestId("bn-name-pencil-m1")[1]);
    const editing = screen.getAllByTestId("bn-name-m1")[1];
    editing.textContent = "Joanna";
    fireEvent.keyDown(editing, { key: "Enter" });
    await waitFor(() => expect(putCalls()).toHaveLength(1));
    expect(getUndoState().undoAction).toBe("renameModerator");

    await act(async () => {
      await undo();
    });
    expect(screen.getAllByTestId("bn-name-m1").map((n) => n.textContent)).toEqual(["Martin", "Jo"]);
    expect(putCalls()[1].url).toMatch(/\/sessions\/s2\/speakers\/m1$/);
    // The fixture's slot carries no flag, which the grid reads as confirmed.
    expect(putCalls()[1].body).toEqual({ person: "id-jo", short_name: "Jo", confirmed: true, kind: "moderator" });

    await act(async () => {
      await redo();
    });
    expect(screen.getAllByTestId("bn-name-m1")[1].textContent).toBe("Joanna");
  });

  it("still renames a participant through /people", async () => {
    mockTwoModerators();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    fireEvent.click(screen.getByTestId("bn-name-pencil-p1"));
    const nameEl = screen.getByTestId("bn-name-p1");
    nameEl.textContent = "Alicia";
    fireEvent.keyDown(nameEl, { key: "Enter" });
    await waitFor(() => expect(putCalls()).toHaveLength(2));
    const [put] = putCalls();
    expect(put.url).toMatch(/\/people$/);
    expect((put.body as Record<string, { short_name: string }>).p1.short_name).toBe("Alicia");
  });
});

// ---------------------------------------------------------------------------
// Person picker — who is this speaker? (design-people.md § UX iteration 3)
// ---------------------------------------------------------------------------

describe("SessionsTable person picker", () => {
  // The native pick path lazy-loads the picker bridge on first use. On a cold CI
  // runner that first load can outlast waitFor's 1 s, so the first native-pick
  // test failed there while passing locally (5 Oct 2026). Load it once up front,
  // so each test measures the handler, not the module transform.
  beforeAll(async () => {
    await import("../utils/personPickerBridge");
  });

  // s1's moderator is a pipeline guess; s2's was confirmed by a person.
  const pickerSessions = {
    ...sessionsResponse,
    sessions: [
      {
        ...sessionsResponse.sessions[0],
        speakers: [
          { speaker_code: "m1", name: "Sarah", role: "researcher", name_confirmed: false, person: "id-sarah" },
          { speaker_code: "p1", name: "Alice", role: "participant", name_confirmed: true },
        ],
      },
      {
        ...sessionsResponse.sessions[1],
        speakers: [
          { speaker_code: "m1", name: "Kerri", role: "researcher", name_confirmed: true, person: "id-kerri" },
          { speaker_code: "p2", name: "Bob", role: "participant", name_confirmed: true },
        ],
      },
    ],
  };

  // A server that remembers what was written: a pick re-reads /sessions
  // (codes may renumber), so a frozen fixture would undo every pick.
  function mockPicker() {
    const server = structuredClone(pickerSessions) as typeof pickerSessions;
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      (url: string, init?: RequestInit) => {
        const slot = /\/sessions\/([^/]+)\/speakers\/([^/]+)$/.exec(url);
        if (slot && init?.method === "PUT") {
          const body = JSON.parse(init.body as string) as Record<string, unknown>;
          const sp = server.sessions
            .find((sess) => sess.session_id === slot[1])
            ?.speakers.find((x) => x.speaker_code === slot[2]) as Record<string, unknown> | undefined;
          if (sp && body.clear) Object.assign(sp, { person: "", name: "", name_confirmed: false });
          else if (sp) {
            const holder = server.sessions.flatMap((x) => x.speakers)
              .find((x) => (x as Record<string, unknown>).person === body.person) as Record<string, unknown> | undefined;
            const name = (body.short_name ?? body.full_name ?? holder?.name ?? sp.name) as string;
            Object.assign(sp, { person: body.person ?? sp.person, name, name_confirmed: body.confirmed ?? true });
          }
          return Promise.resolve({ ok: true, json: async () => ({ status: "ok" }) });
        }
        if (url.includes("/sessions") && !url.includes("/speakers/")) {
          return Promise.resolve({ ok: true, json: async () => structuredClone(server) });
        }
        if (url.includes("/people")) {
          return Promise.resolve({ ok: true, json: async () => peopleResponse });
        }
        return Promise.resolve({ ok: true, json: async () => ({ status: "ok" }) });
      },
    );
  }

  // The picker is loaded on first open, so it arrives a tick after the click.
  const pickerMenu = () =>
    waitFor(() => {
      const el = document.querySelector<HTMLElement>(".bn-person-picker");
      if (!el) throw new Error("picker not open yet");
      return el;
    });

  function puts(): { url: string; body: unknown }[] {
    return (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls
      .filter(([, init]) => (init as RequestInit | undefined)?.method === "PUT")
      .map(([url, init]) => ({ url: url as string, body: JSON.parse((init as RequestInit).body as string) }));
  }

  afterEach(() => {
    delete (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__;
    delete (window as unknown as Record<string, unknown>).__BRISTLENOSE_NATIVE_PERSON_PICKER__;
    delete (window as unknown as Record<string, unknown>).webkit;
    _resetEmbeddedCache();
    resetNativePicker();
  });

  /** Open the Mac app's picker on one speaker, as a click in the app does,
   *  then send what native would answer. A reply nobody asked for is ignored. */
  async function nativeReply(index: number, choice: Record<string, unknown>, sessionId: string) {
    (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__ = true;
    (window as unknown as Record<string, unknown>).__BRISTLENOSE_NATIVE_PERSON_PICKER__ = true;
    _resetEmbeddedCache();
    const postMessage = vi.fn();
    (window as unknown as Record<string, unknown>).webkit = { messageHandlers: { navigation: { postMessage } } };
    mockPicker();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    fireEvent.click(screen.getAllByTestId("bn-picker-trigger-m1")[index]);
    await waitFor(() => expect(postMessage.mock.calls.some(([m]) => m.type === "person-picker")).toBe(true));
    window.dispatchEvent(new CustomEvent("bn:menu-action", {
      detail: { action: "personPickerChoose", payload: { sessionId, code: "m1", choice } },
    }));
  }

  it("a native reply nobody asked for is ignored", async () => {
    mockPicker();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    window.dispatchEvent(new CustomEvent("bn:menu-action", {
      detail: { action: "personPickerChoose", payload: { sessionId: "s2", code: "m1", choice: { kind: "new", name: "Mike" } } },
    }));
    await new Promise((r) => setTimeout(r, 50));
    expect(puts()).toHaveLength(0);
  });

  it("draws a proposed name with the dotted ring and the grey name", async () => {
    mockPicker();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    const [s1Mod, s2Mod] = screen.getAllByTestId("bn-picker-trigger-m1");
    expect(s1Mod.classList.contains("bn-person-proposed")).toBe(true);
    expect(s2Mod.classList.contains("bn-person-proposed")).toBe(false);
    const [s1Name] = screen.getAllByTestId("bn-name-m1");
    expect(s1Name.classList.contains("proposed")).toBe(true);
    // The ring and the grey are visual; the badge says it in words too.
    expect(s1Mod.getAttribute("aria-label")).toMatch(/^m1, proposed name \S/);
    expect(s2Mod.getAttribute("aria-label")).toBeNull();
  });

  it("an exported report draws a proposed name plain, with no picker", async () => {
    (window as unknown as Record<string, unknown>).BRISTLENOSE_EXPORT = {
      version: 1,
      exported_at: "2026-10-04T00:00:00Z",
      health: {},
      endpoints: { "/sessions": pickerSessions, "/people": peopleResponse },
    };
    _resetExportCache();
    try {
      render(<SessionsTable projectId="1" />);
      await screen.findByText("#1");
      // The proposed name is there, just not drawn as proposed.
      expect(screen.getAllByTestId("bn-name-m1")[0].textContent).not.toBe("");
      expect(screen.queryByTestId("bn-picker-trigger-m1")).toBeNull();
      expect(document.querySelector(".bn-person-proposed")).toBeNull();
      expect(document.querySelector(".bn-speaker-editable-name.proposed")).toBeNull();
    } finally {
      delete (window as unknown as Record<string, unknown>).BRISTLENOSE_EXPORT;
      _resetExportCache();
    }
  });

  it("the badge opens the picker with every moderator name in the study", async () => {
    mockPicker();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    fireEvent.click(screen.getAllByTestId("bn-picker-trigger-m1")[0]);
    const picker = await pickerMenu();
    const names = Array.from(picker.querySelectorAll(".bn-speaker-badge-name")).map((n) => n.textContent);
    expect(names.slice(0, 2)).toEqual(["Sarah", "Kerri"]);
  });

  it("Enter on the proposed name confirms it, keeping the name", async () => {
    mockPicker();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    fireEvent.click(screen.getAllByTestId("bn-picker-trigger-m1")[0]);
    await pickerMenu();
    // The picker opens on the name as a field; Return on it unchanged is yes.
    fireEvent.keyDown(document.activeElement as HTMLElement, { key: "Enter" });
    await waitFor(() => expect(puts()).toHaveLength(1));
    expect(puts()[0].url).toContain("/sessions/s1/speakers/m1");
    expect(puts()[0].body).toEqual({ person: "id-sarah", short_name: "Sarah", confirmed: true, kind: "moderator" });
    expect(screen.getAllByTestId("bn-picker-trigger-m1")[0].classList.contains("bn-person-proposed")).toBe(false);
  });

  it("undoing a confirm returns the name to proposed", async () => {
    mockPicker();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    fireEvent.click(screen.getAllByTestId("bn-picker-trigger-m1")[0]);
    await pickerMenu();
    // The picker opens on the name as a field; Return on it unchanged is yes.
    fireEvent.keyDown(document.activeElement as HTMLElement, { key: "Enter" });
    await waitFor(() => expect(puts()).toHaveLength(1));
    expect(getUndoState().undoAction).toBe("confirmName");

    await act(async () => {
      await undo();
    });
    expect(puts()[1].url).toContain("/sessions/s1/speakers/m1");
    expect(puts()[1].body).toEqual({ person: "id-sarah", short_name: "Sarah", confirmed: false, kind: "moderator" });
    expect(screen.getAllByTestId("bn-picker-trigger-m1")[0].classList.contains("bn-person-proposed")).toBe(true);
    expect(screen.getAllByTestId("bn-name-m1")[0].textContent).toBe("Sarah");
  });

  it("'Moderated by' names the moderators the grid shows, and follows a rename", async () => {
    mockPicker(); // the payload's moderator_names says only "Sarah"
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    const header = () => document.querySelector(".bn-session-moderators")?.textContent;
    expect(header()).toBe("Moderated by Sarah and Kerri");
    fireEvent.click(screen.getAllByTestId("bn-picker-trigger-m1")[0]);
    const kerri = Array.from((await pickerMenu()).querySelectorAll<HTMLElement>(".export-dropdown-item"))[1];
    fireEvent.click(kerri);
    await waitFor(() => expect(header()).toBe("Moderated by Kerri"));
  });

  it("picking another moderator points this session's at them, by person (§J8)", async () => {
    mockPicker();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    fireEvent.click(screen.getAllByTestId("bn-picker-trigger-m1")[0]);
    const kerri = Array.from((await pickerMenu()).querySelectorAll<HTMLElement>(".export-dropdown-item"))[1];
    fireEvent.click(kerri);
    await waitFor(() => expect(puts()).toHaveLength(1));
    expect(puts()[0].url).toContain("/sessions/s1/speakers/m1");
    expect(puts()[0].body).toEqual({ person: "id-kerri", short_name: "Kerri", confirmed: true, kind: "moderator" });
    expect(screen.getAllByTestId("bn-name-m1").map((n) => n.textContent)).toEqual(["Kerri", "Kerri"]);
  });

  it("the pencil still edits the name in place", async () => {
    mockPicker();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    fireEvent.click(screen.getAllByTestId("bn-picker-trigger-m1")[0]);
    await pickerMenu();
    fireEvent.mouseDown(screen.getAllByTestId("bn-name-pencil-m1")[0]);
    fireEvent.click(screen.getAllByTestId("bn-name-pencil-m1")[0]);
    expect(document.querySelector(".bn-person-picker")).toBeNull();
  });

  it("in the Mac app the badge asks native for its picker instead", async () => {
    (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__ = true;
    (window as unknown as Record<string, unknown>).__BRISTLENOSE_NATIVE_PERSON_PICKER__ = true;
    _resetEmbeddedCache();
    const postMessage = vi.fn();
    (window as unknown as Record<string, unknown>).webkit = {
      messageHandlers: { navigation: { postMessage } },
    };
    mockPicker();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    fireEvent.click(screen.getAllByTestId("bn-picker-trigger-m1")[0]);
    expect(document.querySelector(".bn-person-picker")).toBeNull();
    // The bridge module loads on demand, so the message follows a tick later.
    await waitFor(() =>
      expect(postMessage.mock.calls.some(([m]) => m.type === "person-picker")).toBe(true),
    );
    const msg = postMessage.mock.calls.map(([m]) => m).find((m) => m.type === "person-picker");
    expect(msg).toMatchObject({
      sessionId: "s1",
      slot: { code: "m1", role: "moderator", name: "Sarah", confirmed: false },
      names: ["Sarah", "Kerri"],
    });
  });

  it("an app without a native picker opens the web one: no message goes unanswered", async () => {
    (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__ = true;
    _resetEmbeddedCache();
    const postMessage = vi.fn();
    (window as unknown as Record<string, unknown>).webkit = {
      messageHandlers: { navigation: { postMessage } },
    };
    mockPicker();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    fireEvent.click(screen.getAllByTestId("bn-picker-trigger-m1")[0]);
    await pickerMenu();
    expect(postMessage.mock.calls.some(([m]) => m.type === "person-picker")).toBe(false);
  });

  it("native picking the slot's own proposed name is a yes, not a rename", async () => {
    await nativeReply(0, { kind: "name", name: "Sarah" }, "s1");
    await waitFor(() => expect(puts()).toHaveLength(1));
    expect(puts()[0].url).toContain("/sessions/s1/speakers/m1");
    expect((puts()[0].body as { confirmed?: boolean }).confirmed).toBe(true);
    await waitFor(() =>
      expect(screen.getAllByTestId("bn-picker-trigger-m1")[0].classList.contains("bn-person-proposed")).toBe(false),
    );
  });

  it("native picking the slot's own confirmed name sends nothing", async () => {
    await nativeReply(1, { kind: "name", name: "Kerri" }, "s2");
    // Give the on-demand bridge module time to load and answer.
    await new Promise((r) => setTimeout(r, 50));
    expect(puts()).toHaveLength(0);
  });

  it("native's choice comes back as a menu action and is applied", async () => {
    await nativeReply(1, { kind: "new", name: "Mike" }, "s2");
    await waitFor(() => expect(puts()).toHaveLength(1));
    expect(puts()[0].url).toContain("/sessions/s2/speakers/m1");
    expect(puts()[0].body).toMatchObject({ create: true, full_name: "Mike", short_name: "Mike", confirmed: true });
    expect(typeof (puts()[0].body as { person?: unknown }).person).toBe("string");
    await waitFor(() =>
      expect(screen.getAllByTestId("bn-name-m1").map((n) => n.textContent)).toEqual(["Sarah", "Mike"]),
    );
  });

  it("native's typed name another moderator goes by is refused, and nothing is written (§J8.11)", async () => {
    await nativeReply(1, { kind: "new", name: "sarah" }, "s2");
    await new Promise((r) => setTimeout(r, 50));
    expect(puts()).toHaveLength(0);
    expect(screen.getAllByTestId("bn-name-m1").map((n) => n.textContent)).toEqual(["Sarah", "Kerri"]);
  });

  it("the ✕ clears this session's moderator, and undo points back (§J8.8)", async () => {
    mockPicker();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    fireEvent.click(screen.getAllByTestId("bn-picker-trigger-m1")[1]);
    const picker = await pickerMenu();
    fireEvent.click(picker.querySelector(".bn-picker-clear") as HTMLElement);
    await waitFor(() => expect(puts()).toHaveLength(1));
    expect(puts()[0].url).toContain("/sessions/s2/speakers/m1");
    expect(puts()[0].body).toEqual({ clear: true });
    expect(getUndoState().undoAction).toBe("clearName");
    await waitFor(() => expect(screen.getAllByTestId("bn-name-m1")[1].textContent).toBe("Moderator"));

    await act(async () => {
      await undo();
    });
    await waitFor(() => expect(puts()).toHaveLength(2));
    expect(puts()[1].body).toEqual({ person: "id-kerri", short_name: "Kerri", confirmed: true, kind: "moderator" });
  });

  it("two unknown moderators read Moderator A and Moderator B (§J8.9)", async () => {
    const lettered = {
      ...pickerSessions,
      sessions: [
        {
          ...pickerSessions.sessions[0],
          speakers: [
            { speaker_code: "mA?", slot_code: "m1", name: "", role: "researcher", name_confirmed: false },
            { speaker_code: "mB?", slot_code: "m2", name: "", role: "researcher", name_confirmed: false },
            { speaker_code: "p1", name: "Alice", role: "participant", name_confirmed: true },
          ],
        },
        pickerSessions.sessions[1],
      ],
    };
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation((url: string) =>
      Promise.resolve(
        url.includes("/sessions")
          ? { ok: true, json: async () => lettered }
          : { ok: true, json: async () => peopleResponse },
      ),
    );
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    expect(screen.getByTestId("bn-name-mA?").textContent).toBe("Moderator A");
    expect(screen.getByTestId("bn-name-mB?").textContent).toBe("Moderator B");
  });

  it("another session's guess is not offered, but still holds its name (§J8.10)", async () => {
    mockPicker(); // s1's Sarah is a pipeline guess; s2's Kerri was confirmed
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    fireEvent.click(screen.getAllByTestId("bn-picker-trigger-m1")[1]);
    const picker = await pickerMenu();
    const names = Array.from(picker.querySelectorAll(".export-dropdown-item .bn-speaker-badge-name"))
      .map((n) => n.textContent)
      .filter((n) => n !== "New moderator");
    expect(names).toEqual(["Kerri"]);
    const field = screen.getByPlaceholderText("New moderator");
    fireEvent.change(field, { target: { value: "Sarah" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(screen.getByRole("alert").textContent).toContain("Sarah");
    expect(puts()).toHaveLength(0);
  });

  it("renaming in the picker fixes that person's spelling everywhere (§J8.8)", async () => {
    mockPicker();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    fireEvent.click(screen.getAllByTestId("bn-picker-trigger-m1")[1]);
    const kerriRow = Array.from((await pickerMenu()).querySelectorAll<HTMLElement>(".export-dropdown-item"))
      .find((li) => li.textContent?.includes("Kerri")) as HTMLElement;
    fireEvent.click(kerriRow);
    const field = kerriRow.querySelector("input") as HTMLInputElement;
    fireEvent.change(field, { target: { value: "Keri" } });
    fireEvent.keyDown(field, { key: "Enter" });
    await waitFor(() => expect(puts()).toHaveLength(1));
    expect(puts()[0].url).toContain("/sessions/s2/speakers/m1");
    expect(puts()[0].body).toEqual({ person: "id-kerri", short_name: "Keri", confirmed: true, kind: "moderator" });
  });

  it("recoding a moderator as an observer is one write with the role, and undo puts it back (§J7 R1)", async () => {
    mockPicker();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    fireEvent.click(screen.getAllByTestId("bn-picker-trigger-m1")[1]);
    const picker = await pickerMenu();
    fireEvent.click(picker.querySelectorAll<HTMLButtonElement>(".dimension-btn")[2]);
    fireEvent.click(picker.querySelectorAll<HTMLElement>(".export-dropdown-item")[0]);
    await waitFor(() => expect(puts()).toHaveLength(1));
    expect(puts()[0].url).toContain("/sessions/s2/speakers/m1");
    expect(puts()[0].body).toEqual({ person: "id-kerri", short_name: "Kerri", confirmed: true, kind: "observer" });
    expect(getUndoState().undoAction).toBe("changeRole");
    await act(async () => {
      await undo();
    });
    await waitFor(() => expect(puts()).toHaveLength(2));
    expect(puts()[1].body).toMatchObject({ person: "id-kerri", kind: "moderator" });
  });

  it("the pencil cannot give a moderator someone else's name (§J8.11)", async () => {
    mockPicker();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    fireEvent.click(screen.getAllByTestId("bn-name-pencil-m1")[1]);
    const editing = screen.getAllByTestId("bn-name-m1")[1];
    editing.textContent = "Sarah";
    fireEvent.keyDown(editing, { key: "Enter" });
    await new Promise((r) => setTimeout(r, 20));
    expect(puts()).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// Session tapestry: the timeline slice under each row
// ---------------------------------------------------------------------------

describe("SessionsTable — session tapestry", () => {
  beforeEach(() => resetTapestryViews());

  const tapestryResponse = {
    sessions: [
      {
        session_id: "s1",
        duration_seconds: 1800,
        turns: [
          { t0: 0, t1: 60, speaker: "m1", colour: null },
          { t0: 60, t1: 1800, speaker: "p1", colour: "#c4a893" },
        ],
        sections: [{ t0: 120, label: "Checkout" }],
        quotes: [
          { t0: 120, t1: 140, text: "I can't find the basket", sentiment: "frustration", intensity: 2, section: "Checkout", theme: null },
        ],
      },
    ],
  };

  function mockWithTapestry(tapestry: unknown) {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation((url: string) => {
      if (url.includes("/tapestry")) {
        return tapestry
          ? Promise.resolve({ ok: true, json: async () => tapestry })
          : Promise.resolve({ ok: false, status: 500, json: async () => ({}) });
      }
      if (url.includes("/sessions")) return Promise.resolve({ ok: true, json: async () => sessionsResponse });
      if (url.includes("/people")) return Promise.resolve({ ok: true, json: async () => peopleResponse });
      return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
    });
  }

  it("offers a disclosure only for sessions the tapestry covers, closed by default", async () => {
    mockWithTapestry(tapestryResponse);
    render(<SessionsTable projectId="1" />);
    const toggle = await screen.findByRole("button", { name: "Timeline for session 1" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("button", { name: "Timeline for session 2" })).not.toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Session timeline" })).not.toBeInTheDocument();
  });

  it("opens the slice under its row and shows the zoom control", async () => {
    mockWithTapestry(tapestryResponse);
    render(<SessionsTable projectId="1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Timeline for session 1" }));
    // Lazy-loaded: the slice arrives a tick after the click.
    expect(await screen.findByRole("group", { name: "Session timeline" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Timeline for session 1" })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("slider", { name: "Timeline zoom" })).toBeInTheDocument();
    // The slice is a row of the grid, right after its session's row.
    const row = document.querySelector('[data-session="s1"]');
    expect(row?.nextElementSibling?.id).toBe("bn-tapestry-s1");
  });

  it("keeps a timeline open across a visit to a transcript and back", async () => {
    mockWithTapestry(tapestryResponse);
    const first = render(<SessionsTable projectId="1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Timeline for session 1" }));
    fireEvent.change(screen.getByRole("slider", { name: "Timeline zoom" }), { target: { value: "40" } });
    first.unmount(); // the lens unmounts when the router goes to the transcript
    render(<SessionsTable projectId="1" />);
    const toggle = await screen.findByRole("button", { name: "Timeline for session 1" });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(await screen.findByRole("group", { name: "Session timeline" })).toBeInTheDocument();
    expect(screen.getByRole("slider", { name: "Timeline zoom" })).toHaveValue("40");
  });

  it("scrolls each open timeline on its own", async () => {
    const two = { sessions: [tapestryResponse.sessions[0], { ...tapestryResponse.sessions[0], session_id: "s2" }] };
    mockWithTapestry(two);
    render(<SessionsTable projectId="1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Timeline for session 1" }));
    fireEvent.click(screen.getByRole("button", { name: "Timeline for session 2" }));
    await waitFor(() => expect(document.querySelectorAll(".bn-tapestry-scroll")).toHaveLength(2));
    const [a, b] = Array.from(document.querySelectorAll<HTMLElement>(".bn-tapestry-scroll"));
    a.scrollLeft = 300;
    fireEvent.scroll(a);
    expect(b.scrollLeft).toBe(0);
  });

  it("keeps each project's open timelines to itself", async () => {
    mockWithTapestry(tapestryResponse);
    const first = render(<SessionsTable projectId="1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Timeline for session 1" }));
    first.unmount();
    render(<SessionsTable projectId="2" />);
    expect(await screen.findByRole("button", { name: "Timeline for session 1" })).toHaveAttribute("aria-expanded", "false");
  });

  it("degrades to no timelines when /tapestry fails", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    mockWithTapestry(null);
    render(<SessionsTable projectId="1" />);
    await screen.findAllByText("Alice");
    await waitFor(() => expect(warn).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: /Timeline for session/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("slider", { name: "Timeline zoom" })).not.toBeInTheDocument();
    warn.mockRestore();
  });
});

describe("SessionsTable — re-analyse after a recode (§J7 R3)", () => {
  it("offers Re-analyse only on a session that needs it, and opens the sheet", async () => {
    const needs = {
      ...sessionsResponse,
      sessions: [{ ...sessionsResponse.sessions[0], needs_reanalysis: true }, sessionsResponse.sessions[1]],
    };
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation((url: string) => {
      if (url.includes("/reanalyse")) {
        return Promise.resolve({ ok: true, json: async () => ({ needed: true, cost_usd: null, running: false, command: "bristlenose run x" }) });
      }
      if (url.includes("/sessions")) return Promise.resolve({ ok: true, json: async () => needs });
      if (url.includes("/people")) return Promise.resolve({ ok: true, json: async () => peopleResponse });
      return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
    });
    render(<SessionsTable projectId="1" />);
    const button = await screen.findByTestId("bn-reanalyse-s1");
    expect(screen.queryByTestId("bn-reanalyse-s2")).toBeNull();
    fireEvent.click(button);
    expect(await screen.findByTestId("bn-reanalyse-sheet")).toBeInTheDocument();
  });
});
