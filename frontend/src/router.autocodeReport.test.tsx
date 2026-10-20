import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { routes } from "./router";
import { _resetEmbeddedCache } from "./utils/embedded";
import { resetSidebarStore } from "./contexts/SidebarStore";
import { resetActivityStore } from "./contexts/ActivityStore";

// R15: View Report on an AutoCode chip, clicked from another lens before the
// Codebook lens was ever opened, went to Codebook and opened nothing. The lens is
// a lazy chunk, and the chip announced the report 100 ms after navigating, to a
// listener the chunk had not yet mounted. The chip that reaches this state is the
// one a reload puts back (R14): it is added on load, so no visit to Codebook
// precedes it. Its own file, so the chunk is cold here, and held back until the
// test lets it go, well after the 100 ms.

const chunk = vi.hoisted(() => {
  let release!: () => void;
  const loaded = new Promise<void>((r) => {
    release = r;
  });
  return { loaded, release };
});

vi.mock("./islands/CodebookV2", async (importOriginal) => {
  await chunk.loaded;
  return importOriginal();
});

beforeEach(() => {
  (window as unknown as Record<string, unknown>).BRISTLENOSE_API_BASE = "/api/projects/1";
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
  resetSidebarStore();
  resetActivityStore();
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const body = url.includes("/autocode/jobs")
      ? { jobs: [{ framework_id: "norman", title: "Norman", status: "running", completed_at: null }] }
      : url.includes("/autocode/norman/status")
        ? {
            status: "completed",
            processed_quotes: 4,
            total_quotes: 4,
            proposed_count: 3,
            started_at: "2026-10-20T10:00:00Z",
            completed_at: "2026-10-20T10:01:00Z",
          }
        : url.includes("/autocode/norman/proposals")
          ? { proposals: [], total: 0 }
          : url.includes("/sessions")
            ? { sessions: [] }
            : url.includes("/codebook/templates")
              ? { templates: [] }
              : url.includes("/codebook")
                ? { groups: [], ungrouped: [], all_tag_names: [], framework_quote_totals: {} }
                : {};
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  });
});

afterEach(() => {
  resetActivityStore();
  vi.restoreAllMocks();
  delete (window as unknown as Record<string, unknown>).BRISTLENOSE_API_BASE;
  _resetEmbeddedCache();
  document.getElementById("bn-app-root")?.remove();
});

describe("View Report on a restored AutoCode chip (R15)", () => {
  it("opens the report once the Codebook lens has loaded, however long that takes", async () => {
    const router = createMemoryRouter(routes, { initialEntries: ["/report/sessions/"] });
    render(<RouterProvider router={router} />);

    const link = await screen.findByTestId("bn-activity-chip-action", {}, { timeout: 10_000 });
    fireEvent.click(link);
    await waitFor(() => expect(router.state.location.pathname).toBe("/report/codebook/"));

    // The chunk arrives well after the chip's 100 ms.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 300));
      chunk.release();
    });

    await waitFor(() => {
      const overlay = document.querySelector(".codebook-modal-overlay.visible");
      expect(overlay).not.toBeNull();
      expect(overlay!.textContent).toContain("Norman");
    });
    // Spent once read: a reload or Back to this entry does not open it again.
    expect(router.state.location.state).toBeNull();
  }, 15_000);
});
