import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { NavBar } from "./NavBar";

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
          { path: "analysis", element: <div>analysis</div> },
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
  it("renders all 7 tabs", () => {
    renderNavBar();
    expect(screen.getByText("Project")).toBeInTheDocument();
    expect(screen.getByText("Sessions")).toBeInTheDocument();
    expect(screen.getByText("Quotes")).toBeInTheDocument();
    expect(screen.getByText("Codebook")).toBeInTheDocument();
    expect(screen.getByText("Analysis")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "About" })).toBeInTheDocument();
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

  it("all tabs have role=tab", () => {
    renderNavBar();
    const tabs = screen.getAllByRole("tab");
    expect(tabs).toHaveLength(7);
  });

  it("nav has role=tablist", () => {
    renderNavBar();
    expect(screen.getByRole("tablist")).toBeInTheDocument();
  });

  it("tabs are links with correct hrefs", () => {
    renderNavBar();
    expect(screen.getByText("Project").closest("a")).toHaveAttribute("href", "/report/");
    expect(screen.getByText("Sessions").closest("a")).toHaveAttribute("href", "/report/sessions/");
    expect(screen.getByText("Quotes").closest("a")).toHaveAttribute("href", "/report/quotes/");
    expect(screen.getByText("Codebook").closest("a")).toHaveAttribute("href", "/report/codebook/");
    expect(screen.getByText("Analysis").closest("a")).toHaveAttribute("href", "/report/analysis/");
  });

  it("Settings and About have aria-label", () => {
    renderNavBar();
    expect(screen.getByRole("tab", { name: "Settings" })).toHaveAttribute("aria-label", "Settings");
    expect(screen.getByRole("tab", { name: "About" })).toHaveAttribute("aria-label", "About");
  });
});
