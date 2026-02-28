import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SessionsTable } from "./SessionsTable";

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

  it("enters edit mode on name text click", async () => {
    mockFetchResponses();
    render(<SessionsTable projectId="1" />);
    await screen.findByText("#1");
    // Click the wrapper span around EditableText
    const nameEl = screen.getByTestId("bn-name-p1");
    fireEvent.click(nameEl.parentElement!);
    expect(nameEl.getAttribute("contenteditable")).toBe("true");
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

    // PUT should have been called
    const putCalls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.filter(
      (call: unknown[]) => {
        const opts = call[1] as { method?: string } | undefined;
        return opts?.method === "PUT";
      },
    );
    expect(putCalls.length).toBe(1);
    const putBody = JSON.parse((putCalls[0][1] as { body: string }).body);
    expect(putBody.p1.short_name).toBe("Alicia");
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
