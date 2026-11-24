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
/** What the run's status read answers. */
let uxrStatus: object;
/** Holds the load's clip export read until the test lets it answer. */
let clipsHeld: Promise<void> | null = null;

const RUNNING = {
  status: "running", processed_quotes: 1, total_quotes: 4, proposed_count: 0,
  started_at: "2026-11-24T10:00:00Z", completed_at: null,
};

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  inFlight = [];
  jobListReads = 0;
  uxrStatus = RUNNING;
  clipsHeld = null;
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
    if (url.includes("/export/clips/status") && clipsHeld) await clipsHeld;
    const body = url.includes("/autocode/jobs")
      ? { jobs: inFlight }
      : url.includes("/autocode/uxr/status")
        ? uxrStatus
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

describe("the load's own read", () => {
  it("answered after a recheck gave the run its chip and the run ended, adds no second chip", async () => {
    // Review of 7c6c12293: the load's AutoCode read says "running", a sibling read is slow, a
    // recheck gives the run its chip, the run ends, then the load's reads land.
    let release!: () => void;
    clipsHeld = new Promise((r) => (release = r));
    inFlight = [uxr];
    // The chip's completion is the run's one lens refresh (`codebook-changed` with it).
    let reloads = 0;
    const onReload = () => reloads++;
    window.addEventListener("codebook-changed", onReload);
    try {
      render(<RouterProvider router={createMemoryRouter(routes, { initialEntries: ["/report/sessions/"] })} />);
      await wait(12_500);
      expect(getJobs().size).toBe(1);
      uxrStatus = { ...RUNNING, status: "completed", processed_quotes: 4, completed_at: "2026-11-24T10:02:00Z" };
      inFlight = []; // the load's AutoCode read answered before this
      await wait(5_000);
      expect([...getJobs().values()][0].outcome?.status).toBe("completed");
      expect(reloads).toBe(1);
      release();
      await wait(25_000);
      expect(getJobs().size).toBe(1);
      expect(screen.getAllByTestId("bn-activity-chip")).toHaveLength(1);
      expect(reloads).toBe(1);
    } finally {
      window.removeEventListener("codebook-changed", onReload);
    }
  });
});
