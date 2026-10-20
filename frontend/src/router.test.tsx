import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { routes } from "./router";
import { _resetEmbeddedCache } from "./utils/embedded";
import { closeToc, openTocPush, resetSidebarStore } from "./contexts/SidebarStore";
import { resetQuoteGroupingSlot } from "./contexts/QuoteGroupingSlot";
import { addJob, resetActivityStore } from "./contexts/ActivityStore";
import { act } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  (window as unknown as Record<string, unknown>).BRISTLENOSE_API_BASE = "/api/projects/1";

  // Mock the app root element for useProjectId
  const root = document.createElement("div");
  root.id = "bn-app-root";
  root.setAttribute("data-project-id", "1");
  document.body.appendChild(root);

  // Mock matchMedia — jsdom ships none, and `useIsDarkAppearance` calls it
  // whenever no `data-theme` override is set (see its own header comment).
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });

  // Suppress fetch calls from islands — return empty JSON for all endpoints
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ quotes: [], sessions: [], tags: [] }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
});

afterEach(() => {
  vi.restoreAllMocks();
  delete (window as unknown as Record<string, unknown>).BRISTLENOSE_API_BASE;
  delete (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__;
  _resetEmbeddedCache();
  document.getElementById("bn-app-root")?.remove();
});

function renderRoute(initialEntry: string) {
  const router = createMemoryRouter(routes, {
    initialEntries: [initialEntry],
  });
  return render(<RouterProvider router={router} />);
}

// ---------------------------------------------------------------------------
// Tests — route → NavBar active state
// ---------------------------------------------------------------------------

describe("Router", () => {
  it("renders NavBar on /report/", () => {
    renderRoute("/report/");
    expect(screen.getByRole("navigation")).toBeInTheDocument();
  });

  it("/report/ activates Project tab", () => {
    renderRoute("/report/");
    const tab = screen.getByRole("link", { name: "Project" });
    expect(tab.className).toContain("active");
  });

  it("/report/sessions/ activates Sessions tab", () => {
    renderRoute("/report/sessions/");
    const tab = screen.getByRole("link", { name: "Sessions" });
    expect(tab.className).toContain("active");
  });

  it("/report/quotes/ activates Quotes tab", () => {
    renderRoute("/report/quotes/");
    const tab = screen.getByRole("link", { name: "Quotes" });
    expect(tab.className).toContain("active");
  });

  it("/report/codebook/ activates Codebooks tab", () => {
    renderRoute("/report/codebook/");
    const tab = screen.getByRole("link", { name: "Codebooks" });
    expect(tab.className).toContain("active");
  });

  it("/report/signals/ activates Signals lens", () => {
    renderRoute("/report/signals/");
    const tab = screen.getByRole("link", { name: "Signals" });
    expect(tab.className).toContain("active");
  });

  it("/report/settings/ redirects to project tab (settings is now a modal)", async () => {
    renderRoute("/report/settings/");
    // The catch-all route redirects unknown paths to /report/. The redirect is a
    // router transition; the lazy ProjectTab island holds it pending until the
    // chunk resolves, so await the active state rather than asserting synchronously.
    await waitFor(() => {
      const tab = screen.getByRole("link", { name: "Project" });
      expect(tab.className).toContain("active");
    });
  });

  it("/report/about/ redirects to project tab", async () => {
    renderRoute("/report/about/");
    await waitFor(() => {
      const tab = screen.getByRole("link", { name: "Project" });
      expect(tab.className).toContain("active");
    });
  });

  it("/report/sessions/s1 activates Sessions tab (prefix match)", () => {
    renderRoute("/report/sessions/s1");
    const tab = screen.getByRole("link", { name: "Sessions" });
    expect(tab.className).toContain("active");
  });

  it("unknown sub-path redirects to project tab", async () => {
    renderRoute("/report/nonexistent");
    await waitFor(() => {
      const tab = screen.getByRole("link", { name: "Project" });
      expect(tab.className).toContain("active");
    });
  });
});

// ---------------------------------------------------------------------------
// Embedded mode — chrome suppression
// ---------------------------------------------------------------------------

describe("Embedded mode", () => {
  it("suppresses NavBar, Header, and Footer when embedded", () => {
    (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__ = true;
    _resetEmbeddedCache();
    renderRoute("/report/");
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
  });

  it("renders NavBar when not embedded", () => {
    renderRoute("/report/");
    expect(screen.getByRole("navigation")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// The Quotes lens's grouping control: at the top of the content sidebar while
// it shows, never there otherwise (QuotesTab takes it into the heading then).
// ---------------------------------------------------------------------------

describe("Quotes grouping control placement", () => {
  beforeEach(() => {
    resetSidebarStore();
    resetQuoteGroupingSlot();
    // Real-shaped answers: the catch-all stub above has no `sections`, and the
    // sidebar reads them once its fetch lands.
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      const body = url.includes("/quotes")
        ? { sections: [], themes: [], total_quotes: 0, total_hidden: 0, total_starred: 0, has_moderator: false }
        : url.includes("/sessions")
          ? { sessions: [] }
          : url.includes("/codebook")
            ? { groups: [], ungrouped: [], all_tag_names: [] }
            : {};
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
  });

  it("sits at the top of the content sidebar while it is open, and leaves with it", async () => {
    openTocPush();
    const { container } = renderRoute("/report/quotes/");
    await waitFor(() =>
      expect(
        container.querySelector(".toc-sidebar-header [data-testid='bn-quote-grouping-sections']"),
      ).not.toBeNull(),
    );
    act(() => closeToc());
    expect(container.querySelector(".toc-sidebar-header .bn-quote-grouping")).toBeNull();
  });

  it("is not offered in the sidebar of another lens", async () => {
    openTocPush();
    const { container } = renderRoute("/report/signals/");
    await waitFor(() => expect(container.querySelector(".toc-sidebar")).not.toBeNull());
    expect(container.querySelector(".bn-quote-grouping")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// An AutoCode run that finishes tells the lenses that draw quotes, not only the
// codebook: the proposals live on the quotes, which reload on `bn:tags-changed`.
// ---------------------------------------------------------------------------

describe("AutoCode chip completion", () => {
  beforeEach(() => {
    resetSidebarStore();
    resetActivityStore();
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      const body = url.includes("/autocode/norman/status")
        ? {
            status: "completed",
            processed_quotes: 4,
            total_quotes: 4,
            started_at: "2026-10-20T10:00:00Z",
            completed_at: "2026-10-20T10:01:00Z",
          }
        : url.includes("/quotes")
          ? { sections: [], themes: [], total_quotes: 0, total_hidden: 0, total_starred: 0, has_moderator: false }
          : url.includes("/sessions")
            ? { sessions: [] }
            : url.includes("/codebook")
              ? { groups: [], ungrouped: [], all_tag_names: [] }
              : {};
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
  });

  afterEach(() => {
    resetActivityStore();
  });

  it("announces bn:tags-changed when the run completes", async () => {
    const heard = vi.fn();
    document.addEventListener("bn:tags-changed", heard);
    try {
      renderRoute("/report/sessions/");
      act(() => {
        addJob("autocode-norman", { type: "autocode", frameworkId: "norman", frameworkTitle: "Norman" });
      });
      await waitFor(() => expect(heard).toHaveBeenCalled());
    } finally {
      document.removeEventListener("bn:tags-changed", heard);
    }
  });
});

// ---------------------------------------------------------------------------
// R12: switching a codebook back on re-codes its new sessions, and the chip for
// it is numberless by design — the job's counts are the codebook's cumulative
// totals, not the sessions being coded — so it must not draw them while it runs.
// ---------------------------------------------------------------------------

describe("Catch-up chip", () => {
  beforeEach(() => {
    resetSidebarStore();
    resetActivityStore();
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      const body = url.includes("/autocode/norman/status")
        ? { status: "running", processed_quotes: 40, total_quotes: 40, proposed_count: 12 }
        : url.includes("/sessions")
          ? { sessions: [] }
          : {};
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    });
  });

  afterEach(() => {
    resetActivityStore();
  });

  it("says what it is doing and draws no counts while it runs", async () => {
    renderRoute("/report/sessions/");
    act(() => {
      addJob("catchup:norman:1", { type: "catchup", frameworkId: "norman", frameworkTitle: "Norman" });
    });
    const chip = await screen.findByTestId("bn-activity-chip");
    await waitFor(() => expect(chip).toHaveTextContent("Re-coding new sessions for Norman"));
    expect(chip).toHaveAttribute("data-status", "running");
    expect(chip).not.toHaveTextContent("40/40");
  });
});

// R12 wave 6: the chip read the job's cumulative counts, which keep an earlier
// apply's shortfall for good, so every later catch-up that worked said "some
// batches failed". A catch-up's own counts decide its chip.
describe("Catch-up chip outcome", () => {
  function serve(status: Record<string, unknown>) {
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      const body = url.includes("/autocode/norman/status")
        ? status
        : url.includes("/sessions")
          ? { sessions: [] }
          : {};
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    });
  }

  beforeEach(() => {
    resetSidebarStore();
    resetActivityStore();
  });

  afterEach(() => {
    resetActivityStore();
  });

  it("says done when the catch-up coded everything, whatever an earlier apply missed", async () => {
    serve({
      status: "completed", processed_quotes: 38, total_quotes: 43,
      catch_up_processed: 3, catch_up_total: 3, proposed_count: 12, failure_kind: "",
    });
    renderRoute("/report/sessions/");
    act(() => {
      addJob("catchup:norman:1", { type: "catchup", frameworkId: "norman", frameworkTitle: "Norman" });
    });
    const chip = await screen.findByTestId("bn-activity-chip");
    await waitFor(() => expect(chip).toHaveAttribute("data-status", "completed"));
    expect(chip).not.toHaveTextContent("some batches failed");
  });

  it("names its own shortfall when the catch-up came up short", async () => {
    serve({
      status: "completed", processed_quotes: 40, total_quotes: 44,
      catch_up_processed: 2, catch_up_total: 4, proposed_count: 12, failure_kind: "",
    });
    renderRoute("/report/sessions/");
    act(() => {
      addJob("catchup:norman:1", { type: "catchup", frameworkId: "norman", frameworkTitle: "Norman" });
    });
    const chip = await screen.findByTestId("bn-activity-chip");
    await waitFor(() => expect(chip).toHaveTextContent("Tagged 2 of 4 quotes"));
  });
});

// ---------------------------------------------------------------------------
// R13: a clip export the server no longer holds (it restarted; its jobs live in
// memory) answers "idle", which the chip read as still running, for ever.
// ---------------------------------------------------------------------------

describe("Clip export chip after a server restart", () => {
  beforeEach(() => {
    resetSidebarStore();
    resetActivityStore();
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      const body = url.includes("/export/clips/status")
        ? { status: "idle", progress: 0, total: 0, completed_count: 0, skipped_count: 0, current_clip: "", output_dir: null }
        : url.includes("/quotes")
          ? { sections: [], themes: [], total_quotes: 0, total_hidden: 0, total_starred: 0, has_moderator: false }
          : url.includes("/sessions")
            ? { sessions: [] }
            : url.includes("/codebook")
              ? { groups: [], ungrouped: [], all_tag_names: [] }
              : {};
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
  });

  afterEach(() => {
    resetActivityStore();
  });

  it("ends as failed rather than spinning", async () => {
    renderRoute("/report/sessions/");
    act(() => {
      addJob("clips", { type: "clips", frameworkId: "", frameworkTitle: "", total: 3 });
    });
    await waitFor(() =>
      expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "failed"),
    );
  });

  it("a screens export the server no longer holds ends the same way", async () => {
    // Restarted between the export's start and its first read: "idle" from the first answer.
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      const body = url.includes("/export/screens/status")
        ? { status: "idle", progress: 0, total: 0, completed_count: 0, skipped_count: 0, current: "", output_dir: null, files: [] }
        : url.includes("/sessions")
          ? { sessions: [] }
          : {};
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    });
    renderRoute("/report/sessions/");
    act(() => {
      addJob("screens:r13", { type: "screens", frameworkId: "", frameworkTitle: "", total: 3 });
    });
    await waitFor(() =>
      expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "failed"),
    );
  });
});

// ---------------------------------------------------------------------------
// R14: a reload during a job lost its chip, and the job's end was never shown. The report asks the
// server on load what is still running and puts the chip back.
// ---------------------------------------------------------------------------

describe("Activity chips after a reload", () => {
  let clipsStatus = "running";
  beforeEach(() => {
    resetSidebarStore();
    resetActivityStore();
    clipsStatus = "running";
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      const body = url.includes("/export/clips/status")
        ? { status: clipsStatus, progress: 2, total: 5, completed_count: 2, skipped_count: 0, current_clip: "", output_dir: null }
        : url.includes("/sessions")
          ? { sessions: [] }
          : {};
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    });
  });

  afterEach(() => {
    resetActivityStore();
  });

  it("a clip export still running comes back as its chip, and its end is shown", async () => {
    renderRoute("/report/sessions/");
    await waitFor(() =>
      expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "running"),
    );
    clipsStatus = "completed";
    await waitFor(
      () => expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "completed"),
      // The next poll is up to 2 s away; a wide budget, since CI runners are slow on real timers.
      { timeout: 10_000 },
    );
  }, 15_000);
});

// ---------------------------------------------------------------------------
// R72: in the Mac app the chip's Reveal asked the sandboxed sidecar to run `open -R`, which does
// nothing there (and the clips route said it had). The app reveals through its own bridge.
// ---------------------------------------------------------------------------

describe("Reveal in Finder on a finished export", () => {
  let postMessage: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    resetSidebarStore();
    resetActivityStore();
    postMessage = vi.fn();
    (window as unknown as Record<string, unknown>).webkit = {
      messageHandlers: { navigation: { postMessage } },
    };
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      const body = url.includes("/export/clips/status")
        ? { status: "completed", progress: 3, total: 3, completed_count: 3, skipped_count: 0, current_clip: "", output_dir: "/Users/r/Study A/bristlenose-output/clips" }
        : url.includes("/export/screens/status")
          ? { status: "completed", progress: 2, total: 2, completed_count: 2, skipped_count: 0, current: "", output_dir: "/Users/r/Study A/bristlenose-output/screens", files: ["p1-01.jpg", "p1-02.jpg"] }
          : url.includes("/sessions")
            ? { sessions: [] }
            : {};
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    });
  });

  afterEach(() => {
    resetActivityStore();
    delete (window as unknown as Record<string, unknown>).webkit;
  });

  const reveals = () =>
    postMessage.mock.calls.map((c) => c[0]).filter((m) => m?.action === "reveal-in-finder");
  const serverReveals = () =>
    vi.mocked(globalThis.fetch).mock.calls.filter((c) => String(c[0]).includes("/reveal"));

  async function revealFinished(id: string, type: "clips" | "screens") {
    (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__ = true;
    _resetEmbeddedCache();
    renderRoute("/report/sessions/");
    act(() => {
      addJob(id, { type, frameworkId: "", frameworkTitle: "", total: 2 });
    });
    const action = await screen.findByTestId("bn-activity-chip-action", {}, { timeout: 5000 });
    act(() => action.click());
  }

  it("a clips export is shown in Finder by the app, not the sidecar", async () => {
    await revealFinished("clips", "clips");
    await waitFor(() => expect(reveals()).toHaveLength(1));
    expect(reveals()[0].data).toEqual({ uri: "file:///Users/r/Study%20A/bristlenose-output/clips" });
    expect(serverReveals()).toHaveLength(0);
  });

  it("a screens export is shown with its first still selected", async () => {
    await revealFinished("screens:r72", "screens");
    await waitFor(() => expect(reveals()).toHaveLength(1));
    expect(reveals()[0].data).toEqual({
      uri: "file:///Users/r/Study%20A/bristlenose-output/screens/p1-01.jpg",
    });
    expect(serverReveals()).toHaveLength(0);
  });
});
