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
  it("renders all tabs and icon buttons", () => {
    renderNavBar();
    expect(screen.getByText("Project")).toBeInTheDocument();
    expect(screen.getByText("Sessions")).toBeInTheDocument();
    expect(screen.getByText("Quotes")).toBeInTheDocument();
    expect(screen.getByText("Codebook")).toBeInTheDocument();
    expect(screen.getByText("Analysis")).toBeInTheDocument();
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
    const links = screen.getAllByRole("link");
    // 5 text nav links (Settings and Help are buttons)
    expect(links).toHaveLength(5);
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
    expect(screen.getByText("Codebook").closest("a")).toHaveAttribute("href", "/report/codebook/");
    expect(screen.getByText("Analysis").closest("a")).toHaveAttribute("href", "/report/analysis/");
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
