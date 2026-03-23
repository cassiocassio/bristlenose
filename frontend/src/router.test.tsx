import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { routes } from "./router";
import { _resetEmbeddedCache } from "./utils/embedded";

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

  // Mock matchMedia (used by SettingsPanel's updateLogo when Header renders a logo)
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

  it("/report/codebook/ activates Codebook tab", () => {
    renderRoute("/report/codebook/");
    const tab = screen.getByRole("link", { name: "Codebook" });
    expect(tab.className).toContain("active");
  });

  it("/report/analysis/ activates Analysis tab", () => {
    renderRoute("/report/analysis/");
    const tab = screen.getByRole("link", { name: "Analysis" });
    expect(tab.className).toContain("active");
  });

  it("/report/settings/ redirects to project tab (settings is now a modal)", () => {
    renderRoute("/report/settings/");
    // The catch-all route redirects unknown paths to /report/
    const tab = screen.getByRole("link", { name: "Project" });
    expect(tab.className).toContain("active");
  });

  it("/report/about/ redirects to project tab", () => {
    renderRoute("/report/about/");
    const tab = screen.getByRole("link", { name: "Project" });
    expect(tab.className).toContain("active");
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
