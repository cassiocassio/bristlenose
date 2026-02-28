import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { useAppNavigate } from "./useAppNavigate";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderWithRouter(initialEntry = "/report/") {
  const resultRef: { current: ReturnType<typeof useAppNavigate> | null } = { current: null };

  function TestComponent() {
    resultRef.current = useAppNavigate();
    return null;
  }

  const router = createMemoryRouter(
    [
      {
        path: "/report",
        element: <TestComponent />,
        children: [
          { index: true, element: <div /> },
          { path: "sessions", element: <div /> },
          { path: "sessions/:sessionId", element: <div /> },
          { path: "quotes", element: <div /> },
          { path: "codebook", element: <div /> },
          { path: "analysis", element: <div /> },
          { path: "settings", element: <div /> },
          { path: "about", element: <div /> },
        ],
      },
    ],
    { initialEntries: [initialEntry] },
  );

  renderHook(() => null, {
    wrapper: () => <RouterProvider router={router} />,
  });

  return { router, getResult: () => resultRef.current! };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useAppNavigate", () => {
  it("navigateToTab navigates to correct path", () => {
    const { router, getResult } = renderWithRouter();
    const result = getResult();

    act(() => {
      result.navigateToTab("quotes");
    });

    expect(router.state.location.pathname).toBe("/report/quotes/");
  });

  it("navigateToTab defaults to /report/ for unknown tab", () => {
    const { router, getResult } = renderWithRouter("/report/quotes/");
    const result = getResult();

    act(() => {
      result.navigateToTab("nonexistent");
    });

    expect(router.state.location.pathname).toBe("/report/");
  });

  it("navigateToSession navigates to /report/sessions/:id", () => {
    const { router, getResult } = renderWithRouter();
    const result = getResult();

    act(() => {
      result.navigateToSession("s1");
    });

    expect(router.state.location.pathname).toBe("/report/sessions/s1");
  });

  it("navigateToTab maps all known tabs", () => {
    const { router, getResult } = renderWithRouter();
    const result = getResult();

    const expectedPaths: Record<string, string> = {
      project: "/report/",
      sessions: "/report/sessions/",
      quotes: "/report/quotes/",
      codebook: "/report/codebook/",
      analysis: "/report/analysis/",
      settings: "/report/settings/",
      about: "/report/about/",
    };

    for (const [tab, path] of Object.entries(expectedPaths)) {
      act(() => {
        result.navigateToTab(tab);
      });
      expect(router.state.location.pathname).toBe(path);
    }
  });
});
