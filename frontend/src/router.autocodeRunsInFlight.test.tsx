import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { routes } from "./router";
import { _resetEmbeddedCache } from "./utils/embedded";
import { resetSidebarStore } from "./contexts/SidebarStore";
import { getJobs, resetActivityStore } from "./contexts/ActivityStore";
import { resetConditionStore } from "./contexts/ConditionStore";
import { bumpRefreshKey, resetLastRunStore } from "./contexts/LastRunStore";
import { followAutoCode } from "./contexts/AutoCodePlayback";
import { _resetToast } from "./utils/toast";

// A run that starts after the report loaded, which this page did not start (the server's house
// default after a pipeline run, another window), gets its chip and is followed by the playback,
// as one there at load is (docs/design-autocode-landing-plan.md Phase 4, the gap the 24 Nov
// measurement found). The shell reads the runs in flight again every 12 s and when the data moves.

vi.mock("./contexts/AutoCodePlayback", async (importOriginal) => {
  const m = await importOriginal<typeof import("./contexts/AutoCodePlayback")>();
  return { ...m, followAutoCode: vi.fn() };
});

type W = Record<string, unknown>;
const w = window as unknown as W;

/** What the server's list of runs in flight answers. */
let inFlight: object[];
let jobListReads = 0;

const RUNNING = {
  status: "running", processed_quotes: 1, total_quotes: 4, proposed_count: 0,
  started_at: "2026-11-24T10:00:00Z", completed_at: null,
};

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  inFlight = [];
  jobListReads = 0;
  w.BRISTLENOSE_API_BASE = "/api/projects/1";
  const root = document.createElement("div");
  root.id = "bn-app-root";
  root.setAttribute("data-project-id", "1");
  document.body.appendChild(root);
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    })),
  });
  resetSidebarStore();
  resetActivityStore();
  vi.mocked(followAutoCode).mockClear();
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.includes("/autocode/jobs")) jobListReads++;
    const body = url.includes("/autocode/jobs")
      ? { jobs: inFlight }
      : url.includes("/autocode/uxr/status")
        ? RUNNING
        : url.includes("/export/clips/status") || url.includes("/export/screens/status")
          ? { status: "idle", progress: 0, total: 0 }
          : url.includes("/quotes")
            ? { sections: [], themes: [], total_quotes: 0, total_hidden: 0, total_starred: 0, has_moderator: false }
            : url.includes("/sessions")
              ? { sessions: [] }
              : url.includes("/codebook")
                ? { groups: [], ungrouped: [], all_tag_names: [] }
                : {};
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  });
});

afterEach(() => {
  act(() => _resetToast());
  resetActivityStore();
  resetConditionStore();
  resetLastRunStore();
  vi.restoreAllMocks();
  vi.useRealTimers();
  for (const k of ["BRISTLENOSE_API_BASE", "__BRISTLENOSE_EMBEDDED__", "__BRISTLENOSE_SIDEBAR_AUTOCODE__"]) delete w[k];
  _resetEmbeddedCache();
  document.getElementById("bn-app-root")?.remove();
});

/** The report opens with nothing running, and its own read on load has answered. */
async function open() {
  render(<RouterProvider router={createMemoryRouter(routes, { initialEntries: ["/report/sessions/"] })} />);
  await act(async () => { await vi.advanceTimersByTimeAsync(500); });
  expect(jobListReads).toBe(1);
  expect(getJobs().size).toBe(0);
}

async function wait(ms: number) {
  await act(async () => { await vi.advanceTimersByTimeAsync(ms); });
}

const uxr = { framework_id: "uxr", title: "UXR", status: "running", completed_at: null };
const followed = () => vi.mocked(followAutoCode).mock.calls.filter(([fid]) => fid === "uxr");

describe("a first apply that starts after the report loaded", () => {
  it("gets its chip at the next read and is followed, once", async () => {
    await open();
    inFlight = [uxr];
    await wait(12_500);
    const chip = await screen.findByTestId("bn-activity-chip");
    expect(chip).toHaveTextContent("UXR");
    const [id] = [...getJobs().keys()];
    expect(followed()).toEqual([["uxr", "first", id]]);
    await wait(25_000);
    expect(screen.getAllByTestId("bn-activity-chip")).toHaveLength(1);
    expect(followed()).toHaveLength(1);
  });

  it("is read again as soon as the report's data moves", async () => {
    await open();
    inFlight = [uxr];
    act(() => bumpRefreshKey());
    await wait(500);
    expect(jobListReads).toBe(2);
    expect(await screen.findByTestId("bn-activity-chip")).toHaveTextContent("UXR");
  });

  it("is not drawn in a Mac app whose sidebar shows AutoCode, and is still followed", async () => {
    w.__BRISTLENOSE_EMBEDDED__ = true;
    w.__BRISTLENOSE_SIDEBAR_AUTOCODE__ = true;
    await open();
    inFlight = [uxr];
    await wait(12_500);
    expect([...getJobs().values()].map((j) => j.frameworkId)).toEqual(["uxr"]);
    expect(followed()).toHaveLength(1);
    expect(screen.queryByTestId("bn-activity-chip")).not.toBeInTheDocument();
  });
});
