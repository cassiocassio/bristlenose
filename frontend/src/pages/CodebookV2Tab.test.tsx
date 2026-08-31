/**
 * The codebook lens, at the route it took over.
 *
 * This file began as "phase 0 — the seam", pinning that v2 was reachable at its
 * own route AND that it had not replaced v1, which was the whole point of D29:
 * the shipped lens had to keep working throughout the build. That parallel
 * period ended on 31 Aug 2026 — v2 became the only codebook lens, took
 * `/report/codebook`, and v1 was deleted. The assertions are inverted rather
 * than removed: what used to prove separation now proves the swap, and a
 * resurrected `codebook-v2` route would fail here.
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

const childPaths = () =>
  routes
    .flatMap((r) => ("children" in r && r.children ? r.children : []))
    .map((c) => (c as { path?: string }).path)
    .filter(Boolean);

describe("the codebook lens", () => {
  it("serves /report/codebook", async () => {
    renderAt("/report/codebook");
    await waitFor(() =>
      expect(screen.getByTestId("bn-codebook-v2")).toBeInTheDocument(),
    );
  });

  it("replaced v1 — there is exactly one codebook route", () => {
    // Inverted from "both routes exist". `/report/codebook-v2` is deliberately
    // NOT kept as an alias: it was dev-gated for its whole life, so nothing in
    // the wild holds that URL, and an alias would be a second door to maintain
    // for no reader.
    const paths = childPaths();
    expect(paths).toContain("codebook");
    expect(paths).not.toContain("codebook-v2");
  });

  it("is registered unconditionally, like specimen", () => {
    // A conditional route is a second thing to get wrong; the route costs
    // nothing until visited because the island is lazy.
    expect(childPaths().filter((p) => p === "codebook")).toHaveLength(1);
  });
});
