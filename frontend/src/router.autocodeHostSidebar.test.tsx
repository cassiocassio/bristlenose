import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { routes } from "./router";
import { _resetEmbeddedCache } from "./utils/embedded";
import { resetSidebarStore } from "./contexts/SidebarStore";
import { addJob, getJobs, resetActivityStore } from "./contexts/ActivityStore";
import { resetConditionStore } from "./contexts/ConditionStore";
import { resetLastRunStore } from "./contexts/LastRunStore";
import { _resetToast } from "./utils/toast";
import { beginHandover, whenPlayedOut } from "./contexts/AutoCodePlaybackView";

// Landing plan D38, D40, D51 (Phase 5b): in a Mac app whose sidebar shows AutoCode, the first-run
// and catch-up pop-ups are not drawn, and the work they did unseen still runs: the job ends, the
// shell hears of a credit or key failure, the run hands over from the playback and refreshes the
// lenses, once. A Mac whose sidebar does not show AutoCode, and the browser, keep the pop-up.
// Every other job's pop-up is drawn everywhere.

vi.mock("./contexts/AutoCodePlaybackView", async (importOriginal) => {
  const m = await importOriginal<typeof import("./contexts/AutoCodePlaybackView")>();
  return { ...m, beginHandover: vi.fn(m.beginHandover), whenPlayedOut: vi.fn(m.whenPlayedOut) };
});

type W = Record<string, unknown>;
const w = window as unknown as W;

/** What the next AutoCode status read answers. */
let autocode: Record<string, unknown>;
/** Whether the server has a clip export running (otherwise a load restores its chip everywhere). */
let clipsRunning = false;
const posted: { type: string }[] = [];

const FINISHED = {
  status: "completed", processed_quotes: 4, total_quotes: 4, proposed_count: 3,
  catch_up_total: 1, catch_up_processed: 1,
  started_at: "2026-10-20T10:00:00Z", completed_at: "2026-10-20T10:01:00Z",
};
const OUT_OF_CREDIT = {
  ...FINISHED, status: "failed", processed_quotes: 0, proposed_count: 0,
  failure_kind: "out_of_credit", llm_provider: "anthropic", completed_at: null,
};

function host(kind: "mac-sidebar-autocode" | "mac" | "browser"): void {
  if (kind !== "browser") w.__BRISTLENOSE_EMBEDDED__ = true;
  if (kind === "mac-sidebar-autocode") w.__BRISTLENOSE_SIDEBAR_AUTOCODE__ = true;
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  autocode = FINISHED;
  clipsRunning = false;
  posted.length = 0;
  w.BRISTLENOSE_API_BASE = "/api/projects/1";
  w.webkit = { messageHandlers: { navigation: { postMessage: (m: { type: string }) => posted.push(m) } } };
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
  vi.mocked(beginHandover).mockClear();
  vi.mocked(whenPlayedOut).mockClear();
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const body = url.includes("/autocode/norman/status")
      ? autocode
      : url.includes("/export/clips/status")
        ? { status: clipsRunning ? "running" : "idle", progress: 1, total: 3 }
        : url.includes("/autocode/norman/proposals")
          ? { proposals: [], total: 0 }
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
  for (const k of ["BRISTLENOSE_API_BASE", "__BRISTLENOSE_EMBEDDED__", "__BRISTLENOSE_SIDEBAR_AUTOCODE__", "webkit"]) delete w[k];
  _resetEmbeddedCache();
  document.getElementById("bn-app-root")?.remove();
});

function renderAt(path: string) {
  render(<RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />);
}

/** Listen for the run's one reload, on both channels. */
function listen() {
  const heard = { codebook: 0, tags: 0 };
  const onCodebook = () => heard.codebook++;
  const onTags = () => heard.tags++;
  window.addEventListener("codebook-changed", onCodebook);
  document.addEventListener("bn:tags-changed", onTags);
  return {
    heard,
    stop: () => {
      window.removeEventListener("codebook-changed", onCodebook);
      document.removeEventListener("bn:tags-changed", onTags);
    },
  };
}

/** Long enough for several more polls, so a second reload or a second signal would have come. */
async function letItRun() {
  await act(async () => { await vi.advanceTimersByTimeAsync(7_000); });
}

describe("AutoCode pop-ups in a Mac app whose sidebar shows AutoCode", () => {
  beforeEach(() => host("mac-sidebar-autocode"));

  it.each([
    ["a first run", "autocode"],
    ["a catch-up", "catchup"],
  ] as const)("%s draws no chip, ends, hands over and refreshes the lenses once", async (_name, type) => {
    const ears = listen();
    try {
      renderAt("/report/sessions/");
      act(() => addJob(`${type}:norman:1`, { type, frameworkId: "norman", frameworkTitle: "Norman" }));
      await waitFor(() => expect(ears.heard.tags).toBe(1));
      await letItRun();
      expect(ears.heard).toEqual({ codebook: 1, tags: 1 });
      expect(vi.mocked(beginHandover)).toHaveBeenCalledOnce();
      expect(vi.mocked(beginHandover)).toHaveBeenCalledWith("norman", `${type}:norman:1`);
      // The job is in the store, and ended, as with a chip drawn.
      expect(getJobs().get(`${type}:norman:1`)?.outcome?.status).toBe("completed");
      expect(screen.queryByTestId("bn-activity-chip")).not.toBeInTheDocument();
    } finally {
      ears.stop();
    }
  });

  it("still tells the shell, once, that the account is out of credit", async () => {
    autocode = OUT_OF_CREDIT;
    renderAt("/report/sessions/");
    act(() => addJob("autocode:norman:1", { type: "autocode", frameworkId: "norman", frameworkTitle: "Norman" }));
    await waitFor(() => expect(posted.filter((m) => m.type === "llm-failure")).toHaveLength(1));
    await letItRun();
    expect(posted.filter((m) => m.type === "llm-failure")).toEqual([
      { type: "llm-failure", kind: "out_of_credit", provider: "anthropic" },
    ]);
    expect(getJobs().get("autocode:norman:1")?.outcome?.status).toBe("failed");
    expect(screen.queryByTestId("bn-activity-chip")).not.toBeInTheDocument();
  });

  it("draws every other job's pop-up", async () => {
    clipsRunning = true;
    renderAt("/report/sessions/");
    act(() => {
      addJob("autocode:norman:1", { type: "autocode", frameworkId: "norman", frameworkTitle: "Norman" });
      addJob("clips:1", { type: "clips", frameworkId: "", frameworkTitle: "", total: 3 });
    });
    const chip = await screen.findByTestId("bn-activity-chip");
    await waitFor(() => expect(chip).toHaveAttribute("data-status", "running"));
    expect(screen.getAllByTestId("bn-activity-chip")).toHaveLength(1);
    expect(chip).not.toHaveTextContent("Norman");
  });
});

describe.each([
  ["a Mac app whose sidebar does not show AutoCode", "mac"],
  ["the browser", "browser"],
] as const)("AutoCode pop-ups in %s", (_name, kind) => {
  beforeEach(() => host(kind));

  it.each([
    ["a first run", "autocode"],
    ["a catch-up", "catchup"],
  ] as const)("%s keeps its chip", async (_job, type) => {
    autocode = { ...FINISHED, status: "running", completed_at: null };
    renderAt("/report/sessions/");
    act(() => addJob(`${type}:norman:1`, { type, frameworkId: "norman", frameworkTitle: "Norman" }));
    expect(await screen.findByTestId("bn-activity-chip")).toHaveAttribute("data-status", "running");
  });
});
