import { render, screen, waitFor, act } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SessionsSidebar } from "./SessionsSidebar";
import type { SessionsListResponse } from "../utils/types";

// Mock apiGet
vi.mock("../utils/api", () => ({
  apiGet: vi.fn(),
}));

import { apiGet } from "../utils/api";

const mockApiGet = vi.mocked(apiGet);

// ── ResizeObserver mock ──────────────────────────────────────────

type ROCallback = (entries: Array<{ contentRect: { width: number } }>) => void;
let roCallback: ROCallback | null = null;
let initialWidth = 280;

function fireResize(width: number) {
  act(() => {
    roCallback?.([{ contentRect: { width } }]);
  });
}

class MockResizeObserver {
  constructor(cb: ROCallback) {
    roCallback = cb;
  }
  observe() {
    // Fire immediately with the configured initial width so the
    // component picks it up on first render after data loads.
    roCallback?.([{ contentRect: { width: initialWidth } }]);
  }
  unobserve() {}
  disconnect() {
    roCallback = null;
  }
}

// ── Fixtures ──────────────────────────────────────────────────────

const ONE_TO_ONE: SessionsListResponse = {
  sessions: [
    {
      session_id: "s1",
      session_number: 1,
      session_date: "2026-02-12T10:00:00",
      duration_seconds: 2820,
      has_media: false,
      has_video: false,
      thumbnail_url: null,
      speakers: [
        { speaker_code: "m1", name: "Sarah", role: "moderator" },
        { speaker_code: "p1", name: "Rachel Chen", role: "participant" },
      ],
      journey_labels: [],
      sentiment_counts: {},
      source_files: [],
    },
    {
      session_id: "s2",
      session_number: 2,
      session_date: "2026-02-13T10:00:00",
      duration_seconds: 3780,
      has_media: false,
      has_video: false,
      thumbnail_url: null,
      speakers: [
        { speaker_code: "m1", name: "Sarah", role: "moderator" },
        { speaker_code: "p2", name: "David Kim", role: "participant" },
      ],
      journey_labels: [],
      sentiment_counts: {},
      source_files: [],
    },
  ],
  moderator_names: ["Sarah"],
  observer_names: [],
  source_folder_uri: "file:///input",
};

const MULTI_PARTICIPANT: SessionsListResponse = {
  sessions: [
    {
      session_id: "s1",
      session_number: 1,
      session_date: "2026-02-15T10:00:00",
      duration_seconds: 3600,
      has_media: true,
      has_video: true,
      thumbnail_url: "/thumb/s1.jpg",
      speakers: [
        { speaker_code: "m1", name: "Sarah", role: "moderator" },
        { speaker_code: "p1", name: "Rachel", role: "participant" },
        { speaker_code: "p2", name: "David", role: "participant" },
      ],
      journey_labels: [],
      sentiment_counts: {},
      source_files: [],
    },
  ],
  moderator_names: ["Sarah"],
  observer_names: [],
  source_folder_uri: "file:///input",
};

// ── Helpers ───────────────────────────────────────────────────────

function renderInRouter(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/report/sessions" element={<SessionsSidebar />} />
        <Route path="/report/sessions/:sessionId" element={<SessionsSidebar />} />
      </Routes>
    </MemoryRouter>,
  );
}

// ── Tests ─────────────────────────────────────────────────────────

describe("SessionsSidebar", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    roCallback = null;
    initialWidth = 400; // default: wide enough to show everything
    globalThis.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver;
  });

  it("renders nothing while loading", () => {
    mockApiGet.mockReturnValue(new Promise(() => {})); // never resolves
    const { container } = renderInRouter("/report/sessions");
    expect(container.innerHTML).toBe("");
  });

  it("renders 1:1 sessions with participant badges", async () => {
    mockApiGet.mockResolvedValue(ONE_TO_ONE);
    renderInRouter("/report/sessions");

    await waitFor(() => {
      expect(screen.getByText("Rachel Chen")).toBeDefined();
    });

    expect(screen.getByText("p1")).toBeDefined();
    expect(screen.getByText("David Kim")).toBeDefined();
    expect(screen.getByText("p2")).toBeDefined();
    // No #N session IDs in 1:1 mode
    expect(screen.queryByText("#1")).toBeNull();
  });

  it("renders multi-participant sessions with session IDs", async () => {
    mockApiGet.mockResolvedValue(MULTI_PARTICIPANT);
    renderInRouter("/report/sessions");

    await waitFor(() => {
      expect(screen.getByText("#1")).toBeDefined();
    });

    expect(screen.getByText("Rachel")).toBeDefined();
    expect(screen.getByText("David")).toBeDefined();
  });

  it("highlights active session on transcript route", async () => {
    mockApiGet.mockResolvedValue(ONE_TO_ONE);
    renderInRouter("/report/sessions/s1");

    await waitFor(() => {
      expect(screen.getByText("Rachel Chen")).toBeDefined();
    });

    const links = screen.getAllByRole("link");
    const activeLink = links.find((l) => l.classList.contains("active"));
    expect(activeLink).toBeDefined();
    expect(activeLink!.getAttribute("href")).toBe("/report/sessions/s1");
  });

  it("hides duration at narrow widths", async () => {
    initialWidth = 200;
    mockApiGet.mockResolvedValue(ONE_TO_ONE);
    renderInRouter("/report/sessions");

    await waitFor(() => {
      // At 200px, short names are shown (full names require 360px+)
      expect(screen.getByText("Rachel")).toBeDefined();
    });

    // Duration should not be shown at 200px
    expect(screen.queryByText("47m")).toBeNull();
    // Date should still be shown
    expect(screen.getByText("12 Feb")).toBeDefined();
  });

  it("shows duration at 260px+", async () => {
    initialWidth = 260;
    mockApiGet.mockResolvedValue(ONE_TO_ONE);
    renderInRouter("/report/sessions");

    await waitFor(() => {
      expect(screen.getByText("47m")).toBeDefined();
    });
  });

  it("shows short names at narrow width, full names at 360px+", async () => {
    initialWidth = 200;
    mockApiGet.mockResolvedValue(ONE_TO_ONE);
    renderInRouter("/report/sessions");

    await waitFor(() => {
      expect(screen.getByText("Rachel")).toBeDefined();
    });
    // Full name should not be shown
    expect(screen.queryByText("Rachel Chen")).toBeNull();

    // Widen — full names appear
    fireResize(400);
    await waitFor(() => {
      expect(screen.getByText("Rachel Chen")).toBeDefined();
    });
  });

  it("updates breakpoints live during resize", async () => {
    initialWidth = 200;
    mockApiGet.mockResolvedValue(ONE_TO_ONE);
    renderInRouter("/report/sessions");

    await waitFor(() => {
      expect(screen.getByText("Rachel")).toBeDefined();
    });

    // No duration at 200px
    expect(screen.queryByText("47m")).toBeNull();

    // Widen to 260 — duration appears
    fireResize(260);
    await waitFor(() => {
      expect(screen.getByText("47m")).toBeDefined();
    });

    // Widen to 320 — day-of-week appears
    fireResize(320);
    await waitFor(() => {
      expect(screen.getByText("Thu 12 Feb")).toBeDefined();
    });

    // Widen to 400 — full names
    fireResize(400);
    await waitFor(() => {
      expect(screen.getByText("Rachel Chen")).toBeDefined();
    });
  });
});
