/**
 * Phase 0 — the seam. Pins that v2 is reachable and that it is *parallel*,
 * which is the whole point of D29: v1 must keep working throughout the build.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { routes } from "../router";
import { _resetEmbeddedCache } from "../utils/embedded";

// Same setup as router.test.tsx — AppLayout renders the NavBar and the islands
// fetch on mount, so a route test without these renders the error boundary and
// tells you nothing about the route.
beforeEach(() => {
  (window as unknown as Record<string, unknown>).BRISTLENOSE_API_BASE =
    "/api/projects/1";
  const root = document.createElement("div");
  root.id = "bn-app-root";
  root.setAttribute("data-project-id", "1");
  document.body.appendChild(root);
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
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ quotes: [], sessions: [], tags: [], groups: [] }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
});

afterEach(() => {
  vi.restoreAllMocks();
  delete (window as unknown as Record<string, unknown>).BRISTLENOSE_API_BASE;
  _resetEmbeddedCache();
  document.getElementById("bn-app-root")?.remove();
});

function renderAt(path: string) {
  return render(
    <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />,
  );
}

describe("codebook v2 seam", () => {
  it("is reachable at its own route", async () => {
    renderAt("/report/codebook-v2");
    await waitFor(() =>
      expect(screen.getByTestId("bn-codebook-v2")).toBeInTheDocument(),
    );
  });

  it("does not replace v1 — both routes exist", () => {
    // The failure this guards against is a rewrite in place by accident. If
    // /report/codebook ever stops resolving while v2 is incomplete, the lens is
    // broken for the whole build, which is exactly what D29 rules out.
    const paths = routes
      .flatMap((r) => ("children" in r && r.children ? r.children : []))
      .map((c) => (c as { path?: string }).path)
      .filter(Boolean);
    expect(paths).toContain("codebook");
    expect(paths).toContain("codebook-v2");
  });

  it("registers the route unconditionally, like specimen", () => {
    // A conditional route is a second thing to get wrong; the route costs
    // nothing until visited because the island is lazy. Only the link is gated.
    const children = routes.flatMap((r) =>
      "children" in r && r.children ? r.children : [],
    );
    const v2 = children.find((c) => (c as { path?: string }).path === "codebook-v2");
    expect(v2).toBeDefined();
  });
});
