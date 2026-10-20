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
});
