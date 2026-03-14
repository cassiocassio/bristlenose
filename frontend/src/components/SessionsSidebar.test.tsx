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

// ── Text measurement mock ────────────────────────────────────────
// jsdom's offsetWidth is always 0. We mock it to return ~7px/char
// so content-adaptive breakpoints produce realistic thresholds.

const CHAR_WIDTH = 7;
let origOffsetWidth: PropertyDescriptor | undefined;

function installOffsetWidthMock() {
  origOffsetWidth = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "offsetWidth");
  Object.defineProperty(HTMLElement.prototype, "offsetWidth", {
    configurable: true,
    get() {
      // Return approximate pixel width based on text content
      const text = (this as HTMLElement).textContent ?? "";
      return text.length * CHAR_WIDTH;
    },
  });
}

function restoreOffsetWidthMock() {
  if (origOffsetWidth) {
    Object.defineProperty(HTMLElement.prototype, "offsetWidth", origOffsetWidth);
  }
}

// Also mock getComputedStyle to return a font string
const origGetComputedStyle = globalThis.getComputedStyle;

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

// Short names for breakpoint calculation reference:
// "Rachel" = 6 chars × 7px = 42px, "David" = 5 chars × 7px = 35px
// Longest short name "Rachel" → 42px
// Full names: "Rachel Chen" = 11 chars × 7px = 77px, "David Kim" = 9 chars × 7px = 63px
// Longest full name "Rachel Chen" → 77px
//
// Computed breakpoints (from computeBreakpoints):
// baseShort = 24 + 6 + 42 + 6 + 16 = 94
// baseFull  = 24 + 6 + 77 + 6 + 16 = 129
// durationAt = 94 + 42 + 36 + 10 = 182
// dowAt      = 94 + 70 + 36 + 10 = 210
// fullNameAt = 129 + 42 + 36 + 10 = 217
// thumbAt    = Infinity (no video)
//
// So for this data set:
// - 180px: date only, short names
// - 185px: + duration
// - 215px: + day-of-week
// - 220px: + full names

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
    installOffsetWidthMock();
    // Mock getComputedStyle to return a font string
    globalThis.getComputedStyle = ((el: Element) => {
      const real = origGetComputedStyle(el);
      return {
        ...real,
        fontWeight: "400",
        fontSize: "14px",
        fontFamily: "sans-serif",
      } as CSSStyleDeclaration;
    }) as typeof getComputedStyle;
  });

  afterEach(() => {
    restoreOffsetWidthMock();
    globalThis.getComputedStyle = origGetComputedStyle;
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
    // With "Rachel Chen" (11 chars) → durationAt ~182px
    // At 150px, duration should be hidden
    initialWidth = 150;
    mockApiGet.mockResolvedValue(ONE_TO_ONE);
    renderInRouter("/report/sessions");

    await waitFor(() => {
      // Short name "Rachel" shown at narrow width
      expect(screen.getByText("Rachel")).toBeDefined();
    });

    // Duration should not be shown
    expect(screen.queryByText("47m")).toBeNull();
    // Date should still be shown
    expect(screen.getByText("12 Feb")).toBeDefined();
  });

  it("shows duration when wide enough for content", async () => {
    // durationAt ~182px, so 200px should show it
    initialWidth = 200;
    mockApiGet.mockResolvedValue(ONE_TO_ONE);
    renderInRouter("/report/sessions");

    await waitFor(() => {
      expect(screen.getByText("47m")).toBeDefined();
    });
  });

  it("shows short names at narrow width, full names when wide enough", async () => {
    // fullNameAt ~217px for "Rachel Chen"
    initialWidth = 150;
    mockApiGet.mockResolvedValue(ONE_TO_ONE);
    renderInRouter("/report/sessions");

    await waitFor(() => {
      expect(screen.getByText("Rachel")).toBeDefined();
    });
    // Full name should not be shown
    expect(screen.queryByText("Rachel Chen")).toBeNull();

    // Widen past fullNameAt — full names appear
    fireResize(400);
    await waitFor(() => {
      expect(screen.getByText("Rachel Chen")).toBeDefined();
    });
  });

  it("updates breakpoints live during resize", async () => {
    initialWidth = 150;
    mockApiGet.mockResolvedValue(ONE_TO_ONE);
    renderInRouter("/report/sessions");

    await waitFor(() => {
      expect(screen.getByText("Rachel")).toBeDefined();
    });

    // No duration at 150px
    expect(screen.queryByText("47m")).toBeNull();

    // Widen to 200 — duration appears (durationAt ~182)
    fireResize(200);
    await waitFor(() => {
      expect(screen.getByText("47m")).toBeDefined();
    });

    // Widen to 250 — day-of-week appears (dowAt ~210)
    fireResize(250);
    await waitFor(() => {
      expect(screen.getByText("Thu 12 Feb")).toBeDefined();
    });

    // Widen to 400 — full names (fullNameAt ~217)
    fireResize(400);
    await waitFor(() => {
      expect(screen.getByText("Rachel Chen")).toBeDefined();
    });
  });
});
