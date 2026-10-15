import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";

// The Screens entry asks GET …/screens/status; everything else in the bar keeps the real helpers.
vi.mock("../utils/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../utils/api")>()),
  apiGet: vi.fn(() => Promise.reject(new Error("no status"))),
}));

import { NavBar } from "./NavBar";
import { resetConditionStore, startConditionPolling } from "../contexts/ConditionStore";
import { apiGet } from "../utils/api";
import { resetScreensAvailability } from "../islands/screens/availability";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderNavBar(initialEntry = "/report/") {
  const router = createMemoryRouter(
    [
      {
        path: "/report",
        element: <NavBar />,
        children: [
          { index: true, element: <div>project</div> },
          { path: "sessions", element: <div>sessions</div> },
          { path: "quotes", element: <div>quotes</div> },
          { path: "codebook", element: <div>codebook</div> },
          { path: "signals", element: <div>signals</div> },
          { path: "screens", element: <div>screens</div> },
          { path: "settings", element: <div>settings</div> },
          { path: "about", element: <div>about</div> },
        ],
      },
    ],
    { initialEntries: [initialEntry] },
  );
  return render(<RouterProvider router={router} />);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("NavBar", () => {
  it("renders all tabs and icon buttons", () => {
    renderNavBar();
    expect(screen.getByText("Project")).toBeInTheDocument();
    expect(screen.getByText("Sessions")).toBeInTheDocument();
    expect(screen.getByText("Quotes")).toBeInTheDocument();
    expect(screen.getByText("Codebooks")).toBeInTheDocument();
    expect(screen.getByText("Signals")).toBeInTheDocument();
    // Settings and Help are buttons (open modals), not tabs/links
    expect(screen.getByRole("button", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Help" })).toBeInTheDocument();
  });

  it("applies active class to current route", () => {
    renderNavBar("/report/quotes/");
    const quotesTab = screen.getByText("Quotes");
    expect(quotesTab.className).toContain("active");
    const projectTab = screen.getByText("Project");
    expect(projectTab.className).not.toContain("active");
  });

  it("marks Project active on /report/", () => {
    renderNavBar("/report/");
    const projectTab = screen.getByText("Project");
    expect(projectTab.className).toContain("active");
  });

  it("Sessions tab is active for /report/sessions/", () => {
    renderNavBar("/report/sessions/");
    const sessionsTab = screen.getByText("Sessions");
    expect(sessionsTab.className).toContain("active");
  });

  it("nav links are <a> elements (not role=tab)", () => {
    renderNavBar();
    // 5 text nav links (Settings and Help are buttons). Dev-gated lenses are
    // invisible in a shipped report but present here, because vitest runs with
    // DEV=true — so exclude them as a *class* rather than by name. Naming one
    // meant the second dev lens (Codebook v2) broke a test about how nav links
    // are marked up, which is not what it is asserting.
    const DEV_ONLY = ["Specimen", "Codebook v2"];
    const links = screen
      .getAllByRole("link")
      .filter((a) => !DEV_ONLY.includes(a.textContent ?? ""));
    expect(links).toHaveLength(6);
  });

  it("nav is a <nav> element (not role=tablist)", () => {
    renderNavBar();
    expect(screen.getByRole("navigation")).toBeInTheDocument();
  });

  it("tabs are links with correct hrefs", () => {
    renderNavBar();
    expect(screen.getByText("Project").closest("a")).toHaveAttribute("href", "/report/");
    expect(screen.getByText("Sessions").closest("a")).toHaveAttribute("href", "/report/sessions/");
    expect(screen.getByText("Quotes").closest("a")).toHaveAttribute("href", "/report/quotes/");
    // Label pluralised 14 Aug 2026; the route deliberately did NOT follow —
    // it's baked into exported reports, deep links and the native bridge.
    expect(screen.getByText("Codebooks").closest("a")).toHaveAttribute("href", "/report/codebook/");
    expect(screen.getByText("Signals").closest("a")).toHaveAttribute("href", "/report/signals/");
  });

  it("Settings and Help have aria-label", () => {
    renderNavBar();
    expect(screen.getByRole("button", { name: "Settings" })).toHaveAttribute("aria-label", "Settings");
    expect(screen.getByRole("button", { name: "Help" })).toHaveAttribute("aria-label", "Help");
  });

  it("Settings and Help buttons have aria-haspopup=dialog", () => {
    renderNavBar();
    expect(screen.getByRole("button", { name: "Settings" })).toHaveAttribute("aria-haspopup", "dialog");
    expect(screen.getByRole("button", { name: "Help" })).toHaveAttribute("aria-haspopup", "dialog");
  });
});

describe("NavBar — lenses with nothing to show yet", () => {
  const realFetch = globalThis.fetch;
  afterEach(() => {
    resetConditionStore();
    globalThis.fetch = realFetch;
  });

  it("renders a disabled lens as text, not a link, and keeps it visible", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({
        data_version: 0,
        lenses: { project: false, sessions: true, quotes: false, codebook: false, signals: false, discussion: false },
      }),
    }) as unknown as typeof globalThis.fetch;
    renderNavBar("/report/sessions/");
    act(() => startConditionPolling("1"));
    const quotes = await screen.findByText("Quotes", { selector: "span" });
    expect(screen.getByRole("link", { name: "Sessions" })).toHaveAttribute("href", "/report/sessions/");
    expect(quotes.tagName).toBe("SPAN");
    expect(quotes).toHaveAttribute("aria-disabled", "true");
    expect(quotes).not.toHaveAttribute("href");
  });

  it("leaves a withheld lens for Sessions, where the status page handed over", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({
        data_version: 0,
        lenses: { project: false, sessions: true, quotes: false, codebook: false, signals: false, discussion: false },
      }),
    }) as unknown as typeof globalThis.fetch;
    const router = createMemoryRouter(
      [{ path: "/report/*", element: <NavBar /> }],
      { initialEntries: ["/report/"] },
    );
    render(<RouterProvider router={router} />);
    act(() => startConditionPolling("1"));
    await screen.findByText("Project", { selector: "span" });
    expect(router.state.location.pathname).toBe("/report/sessions/");
  });

  it("stays on a lens that is there", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({
        data_version: 0,
        lenses: { project: false, sessions: true, quotes: true, codebook: false, signals: false, discussion: false },
      }),
    }) as unknown as typeof globalThis.fetch;
    const router = createMemoryRouter(
      [{ path: "/report/*", element: <NavBar /> }],
      { initialEntries: ["/report/quotes/"] },
    );
    render(<RouterProvider router={router} />);
    act(() => startConditionPolling("1"));
    await screen.findByText("Project", { selector: "span" });
    expect(router.state.location.pathname).toBe("/report/quotes/");
  });
});

describe("NavBar — the Screens lens", () => {
  const status = (over: Record<string, unknown>) => ({
    enabled: true, unavailable: null, running: false, done: 2, total: 2,
    seconds_done: 0, seconds_total: 0, rate: null, has_screens: false, ...over,
  });
  beforeEach(() => {
    resetScreensAvailability();
  });
  afterEach(() => {
    vi.mocked(apiGet).mockImplementation(() => Promise.reject(new Error("no status")));
  });

  it("is a lens link when the project has screens, active on its route", async () => {
    vi.mocked(apiGet).mockResolvedValue(status({ has_screens: true, available: true }));
    renderNavBar("/report/screens/");
    const link = await screen.findByRole("link", { name: "Screens" });
    expect(link).toHaveAttribute("href", "/report/screens/");
    expect(link.className).toContain("active");
    expect(apiGet).toHaveBeenCalledWith("/screens/status");
  });

  it("is a lens link while recordings are still being read", async () => {
    vi.mocked(apiGet).mockResolvedValue(status({ running: true, done: 0, available: true }));
    renderNavBar();
    expect(await screen.findByRole("link", { name: "Screens" })).toBeInTheDocument();
  });

  it("is absent when nothing was found and nothing is left to read, Diagnostics or not", async () => {
    const w = window as unknown as Record<string, unknown>;
    w.__BRISTLENOSE_DIAGNOSTICS__ = true;
    try {
      vi.mocked(apiGet).mockResolvedValue(status({}));
      renderNavBar();
      await act(async () => {});
      expect(screen.queryByText("Screens")).toBeNull();
    } finally {
      delete w.__BRISTLENOSE_DIAGNOSTICS__;
    }
  });

  it("is absent when screens cannot be read here", async () => {
    vi.mocked(apiGet).mockResolvedValue(status({ has_screens: true, unavailable: "not_macos", available: false }));
    renderNavBar();
    await act(async () => {});
    expect(screen.queryByText("Screens")).toBeNull();
  });
});
