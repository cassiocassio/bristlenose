import { renderHook, act } from "@testing-library/react";
import { vi } from "vitest";
import {
  addJob,
  removeJob,
  settleJob,
  getJobs,
  useActivityJobs,
  resetActivityStore,
  rehydrateActivityJobs,
} from "./ActivityStore";
import { getClipExtractionStatus, getScreensExportStatus, listAutoCodeJobs } from "../utils/api";
import { isExportMode } from "../utils/exportData";

vi.mock("../utils/api", () => ({
  getClipExtractionStatus: vi.fn(),
  getScreensExportStatus: vi.fn(),
  listAutoCodeJobs: vi.fn(),
}));
vi.mock("../utils/exportData", () => ({ isExportMode: vi.fn(() => false) }));

/** A chip id without its page-load stamp: `clips:restored:k3f9-2` → `clips:restored`. */
const kind = (id: string) => id.replace(/:[0-9a-z]+-\d+$/, "");
const kinds = () => [...getJobs().keys()].map(kind);
const byKind = (k: string) => [...getJobs()].find(([id]) => kind(id) === k)?.[1];

describe("ActivityStore", () => {
  beforeEach(() => {
    resetActivityStore();
  });

  it("starts empty", () => {
    expect(getJobs().size).toBe(0);
  });

  it("addJob adds an entry", () => {
    addJob("autocode:garrett", { type: "autocode", frameworkId: "garrett", frameworkTitle: "Garrett" });
    expect(getJobs().size).toBe(1);
    expect(getJobs().get("autocode:garrett")).toEqual({
      type: "autocode",
      frameworkId: "garrett",
      frameworkTitle: "Garrett",
    });
  });

  it("removeJob removes an entry", () => {
    addJob("autocode:garrett", { type: "autocode", frameworkId: "garrett", frameworkTitle: "Garrett" });
    removeJob("autocode:garrett");
    expect(getJobs().size).toBe(0);
  });

  it("removeJob is a no-op for unknown id", () => {
    addJob("autocode:garrett", { type: "autocode", frameworkId: "garrett", frameworkTitle: "Garrett" });
    removeJob("autocode:unknown");
    expect(getJobs().size).toBe(1);
  });

  it("addJob overwrites existing entry with same id", () => {
    addJob("autocode:garrett", { type: "autocode", frameworkId: "garrett", frameworkTitle: "Garrett" });
    addJob("autocode:garrett", { type: "autocode", frameworkId: "garrett", frameworkTitle: "Garrett v2" });
    expect(getJobs().size).toBe(1);
    expect(getJobs().get("autocode:garrett")!.frameworkTitle).toBe("Garrett v2");
  });

  it("resetActivityStore clears all jobs", () => {
    addJob("autocode:garrett", { type: "autocode", frameworkId: "garrett", frameworkTitle: "Garrett" });
    addJob("autocode:norman", { type: "autocode", frameworkId: "norman", frameworkTitle: "Norman" });
    resetActivityStore();
    expect(getJobs().size).toBe(0);
  });

  it("useActivityJobs hook tracks mutations", () => {
    const { result } = renderHook(() => useActivityJobs());
    expect(result.current.size).toBe(0);

    act(() => {
      addJob("autocode:garrett", { type: "autocode", frameworkId: "garrett", frameworkTitle: "Garrett" });
    });
    expect(result.current.size).toBe(1);

    act(() => {
      removeJob("autocode:garrett");
    });
    expect(result.current.size).toBe(0);
  });

  it("produces a new snapshot ref on each mutation", () => {
    const snap1 = getJobs();
    addJob("autocode:garrett", { type: "autocode", frameworkId: "garrett", frameworkTitle: "Garrett" });
    const snap2 = getJobs();
    expect(snap1).not.toBe(snap2);
  });
});

// R14: a reload lost every chip, and the job's result was never shown. On load the store asks the
// server what is still running and puts those chips back.
describe("rehydrateActivityJobs", () => {
  const clips = vi.mocked(getClipExtractionStatus);
  const screens = vi.mocked(getScreensExportStatus);
  const autocode = vi.mocked(listAutoCodeJobs);
  const idle = { status: "idle", total: 0 } as never;

  beforeEach(() => {
    resetActivityStore();
    vi.mocked(isExportMode).mockReturnValue(false);
    clips.mockReset().mockResolvedValue(idle);
    screens.mockReset().mockResolvedValue(idle);
    autocode.mockReset().mockResolvedValue({ jobs: [] });
  });

  it("puts back a running clip export's chip, with its count", async () => {
    clips.mockResolvedValue({ status: "running", total: 7 } as never);
    await rehydrateActivityJobs("1");
    expect(kinds()).toEqual(["clips:restored"]);
    expect(byKind("clips:restored")).toEqual({ type: "clips", frameworkId: "", frameworkTitle: "", total: 7 });
  });

  it("puts back a running screens export as a plain export", async () => {
    screens.mockResolvedValue({ status: "running", total: 3 } as never);
    await rehydrateActivityJobs("1");
    expect(byKind("screens:restored")).toEqual({
      type: "screens", frameworkId: "", frameworkTitle: "", total: 3, copyWhenDone: false,
    });
  });

  it("puts back each AutoCode run in flight under its codebook's title, and a catch-up as one", async () => {
    // A running job that finished once is the on-enable catch-up (the only path
    // that sets a finished job running again), so it comes back as the chip it
    // was given when the switch went on (R12), not as an AutoCode run.
    autocode.mockResolvedValue({
      jobs: [
        { framework_id: "garrett", title: "Garrett", status: "running", completed_at: null },
        { framework_id: "norman", title: "Norman", status: "pending", completed_at: null },
        { framework_id: "morville", title: "Morville", status: "running", completed_at: "2026-10-20T10:00:00" },
      ],
    });
    await rehydrateActivityJobs("1");
    expect(kinds()).toEqual([
      "autocode:garrett:restored", "autocode:norman:restored", "catchup:morville:restored",
    ]);
    expect(byKind("autocode:garrett:restored")).toEqual({
      type: "autocode", frameworkId: "garrett", frameworkTitle: "Garrett", originRoute: "/report/codebook/",
    });
    expect(byKind("catchup:morville:restored")).toEqual({
      type: "catchup", frameworkId: "morville", frameworkTitle: "Morville",
    });
  });

  it("does not double a catch-up whose chip the page already has", async () => {
    addJob("catchup:morville:3", { type: "catchup", frameworkId: "morville", frameworkTitle: "Morville" });
    autocode.mockResolvedValue({
      jobs: [{ framework_id: "morville", title: "Morville", status: "running", completed_at: "2026-10-20T10:00:00" }],
    });
    await rehydrateActivityJobs("1");
    expect([...getJobs().keys()]).toEqual(["catchup:morville:3"]);
  });

  it("adds nothing for a job that is idle, finished, failed or cancelled", async () => {
    for (const status of ["idle", "completed", "failed", "cancelled"]) {
      resetActivityStore();
      clips.mockResolvedValue({ status, total: 2 } as never);
      screens.mockResolvedValue({ status, total: 2 } as never);
      await rehydrateActivityJobs("1");
      expect(getJobs().size).toBe(0);
    }
  });

  it("a read that fails adds nothing, says so, and does not stop the others", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    clips.mockRejectedValue(new Error("GET /export/clips/status → 500"));
    screens.mockImplementation(() => { throw new Error("thrown, not rejected"); });
    autocode.mockResolvedValue({
      jobs: [{ framework_id: "garrett", title: "Garrett", status: "running", completed_at: null }],
    });
    await expect(rehydrateActivityJobs("1")).resolves.toBeUndefined();
    expect(kinds()).toEqual(["autocode:garrett:restored"]);
    expect(warn).toHaveBeenCalledTimes(2);
    warn.mockRestore();
  });

  it("a body of another shape adds nothing", async () => {
    clips.mockResolvedValue({ quotes: [] } as never);
    screens.mockResolvedValue(null as never);
    autocode.mockResolvedValue({ quotes: [] } as never);
    await rehydrateActivityJobs("1");
    expect(getJobs().size).toBe(0);
  });

  it("a job list with a hole in it restores the rest and does not reject", async () => {
    autocode.mockResolvedValue({
      jobs: [null, { framework_id: "garrett", title: "Garrett", status: "running", completed_at: null }],
    } as never);
    await expect(rehydrateActivityJobs("1")).resolves.toBeUndefined();
    expect(kinds()).toEqual(["autocode:garrett:restored"]);
  });

  it("reads once more after a failed read, and keeps what it restored the first time", async () => {
    vi.useFakeTimers();
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    try {
      clips.mockRejectedValueOnce(new Error("GET /export/clips/status → timeout"));
      clips.mockResolvedValue({ status: "running", total: 6 } as never);
      screens.mockResolvedValue({ status: "running", total: 2 } as never);
      await rehydrateActivityJobs("1");
      expect(kinds()).toEqual(["screens:restored"]);
      await vi.advanceTimersByTimeAsync(5_000);
      expect(kinds()).toEqual(["screens:restored", "clips:restored"]);
      expect(clips).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
      warn.mockRestore();
    }
  });

  it("reads once more only: a server still failing is not asked again and again", async () => {
    vi.useFakeTimers();
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    try {
      clips.mockRejectedValue(new Error("down"));
      await rehydrateActivityJobs("1");
      await vi.advanceTimersByTimeAsync(30_000);
      expect(clips).toHaveBeenCalledTimes(2);
      expect(getJobs().size).toBe(0);
    } finally {
      vi.useRealTimers();
      warn.mockRestore();
    }
  });

  it("asks once per project", async () => {
    await rehydrateActivityJobs("1");
    await rehydrateActivityJobs("1");
    expect(clips).toHaveBeenCalledTimes(1);
    expect(autocode).toHaveBeenCalledTimes(1);
  });

  it("does not double a job started while the reads were out", async () => {
    clips.mockResolvedValue({ status: "running", total: 4 } as never);
    screens.mockResolvedValue({ status: "running", total: 2 } as never);
    autocode.mockResolvedValue({
      jobs: [{ framework_id: "garrett", title: "Garrett", status: "running", completed_at: null }],
    });
    const pending = rehydrateActivityJobs("1");
    addJob("clips:1", { type: "clips", frameworkId: "", frameworkTitle: "", total: 4 });
    addJob("screens:1", { type: "screens", frameworkId: "", frameworkTitle: "", total: 2, copyWhenDone: true });
    addJob("autocode:garrett:1", { type: "autocode", frameworkId: "garrett", frameworkTitle: "Garrett" });
    await pending;
    expect([...getJobs().keys()]).toEqual(["clips:1", "screens:1", "autocode:garrett:1"]);
  });

  it("makes no read in an exported report", async () => {
    vi.mocked(isExportMode).mockReturnValue(true);
    await rehydrateActivityJobs("1");
    expect(clips).not.toHaveBeenCalled();
    expect(screens).not.toHaveBeenCalled();
    expect(autocode).not.toHaveBeenCalled();
    expect(getJobs().size).toBe(0);
  });
});

// RE#38 (decisions #35, #36): a window keeps its own chip list across a reload, in session storage.
// The server's read above sees only what is still running, so a job that finished during the reload
// was missed, and a Copy Screens came back as a plain export that never copied.
describe("a window's chips across a reload", () => {
  const clips = vi.mocked(getClipExtractionStatus);
  const screens = vi.mocked(getScreensExportStatus);
  const autocode = vi.mocked(listAutoCodeJobs);
  const idle = { status: "idle", total: 0, job_id: null } as never;
  const done = {
    status: "completed", progressLabel: null, durationLabel: null, errorMessage: null, partialMessage: null,
  } as const;

  /** The page goes away and comes back: the module's memory is gone, the tab's session storage is not. */
  async function reload(projectId = "1") {
    resetActivityStore({ keepSession: true });
    await rehydrateActivityJobs(projectId);
  }

  beforeEach(() => {
    resetActivityStore();
    vi.mocked(isExportMode).mockReturnValue(false);
    clips.mockReset().mockResolvedValue(idle);
    screens.mockReset().mockResolvedValue(idle);
    autocode.mockReset().mockResolvedValue({ jobs: [] });
  });

  afterEach(() => {
    resetActivityStore();
  });

  it("puts back the chips the window had, in order, as they were", async () => {
    await rehydrateActivityJobs("1");
    addJob("clips:1", { type: "clips", frameworkId: "", frameworkTitle: "", total: 4, jobId: "c1" });
    addJob("screens:1", {
      type: "screens", frameworkId: "", frameworkTitle: "", total: 2, copyWhenDone: true, jobId: "s1",
    });
    addJob("autocode:garrett:1", { type: "autocode", frameworkId: "garrett", frameworkTitle: "Garrett" });
    const before = [...getJobs()];
    await reload();
    expect([...getJobs()]).toEqual(before);
  });

  it("puts back an export that finished during the reload, which the server's read cannot see", async () => {
    await rehydrateActivityJobs("1");
    addJob("clips:1", { type: "clips", frameworkId: "", frameworkTitle: "", total: 4, jobId: "c1" });
    clips.mockResolvedValue({ status: "completed", total: 4, job_id: "c1" } as never);
    await reload();
    expect([...getJobs().keys()]).toEqual(["clips:1"]);
  });

  it("keeps a Copy Screens a copy", async () => {
    await rehydrateActivityJobs("1");
    addJob("screens:1", {
      type: "screens", frameworkId: "", frameworkTitle: "", total: 2, copyWhenDone: true, jobId: "s1",
    });
    screens.mockResolvedValue({ status: "running", total: 2, job_id: "s1" } as never);
    await reload();
    expect([...getJobs()]).toEqual([
      ["screens:1", { type: "screens", frameworkId: "", frameworkTitle: "", total: 2, copyWhenDone: true, jobId: "s1" }],
    ]);
  });

  it("a dismissed chip stays dismissed", async () => {
    await rehydrateActivityJobs("1");
    addJob("clips:1", { type: "clips", frameworkId: "", frameworkTitle: "", total: 4, jobId: "c1" });
    removeJob("clips:1");
    await reload();
    expect(getJobs().size).toBe(0);
  });

  it("a finished chip comes back with how it ended", async () => {
    await rehydrateActivityJobs("1");
    addJob("clips:1", { type: "clips", frameworkId: "", frameworkTitle: "", total: 4, jobId: "c1" });
    settleJob("clips:1", done);
    await reload();
    expect(getJobs().get("clips:1")?.outcome).toEqual(done);
  });

  it("a finished chip whose export was replaced gives way to the newer run's chip", async () => {
    await rehydrateActivityJobs("1");
    addJob("clips:1", { type: "clips", frameworkId: "", frameworkTitle: "", total: 4, jobId: "c1" });
    settleJob("clips:1", done);
    clips.mockResolvedValue({ status: "running", total: 9, job_id: "c2" } as never);
    await reload();
    expect(kinds()).toEqual(["clips:restored"]);
    expect(byKind("clips:restored")?.jobId).toBe("c2");
  });

  it("a finished chip still holding the server's export comes back beside nothing new", async () => {
    await rehydrateActivityJobs("1");
    addJob("clips:1", { type: "clips", frameworkId: "", frameworkTitle: "", total: 4, jobId: "c1" });
    settleJob("clips:1", done);
    clips.mockResolvedValue({ status: "completed", total: 4, job_id: "c1" } as never);
    await reload();
    expect([...getJobs().keys()]).toEqual(["clips:1"]);
  });

  it("a chip restored from the server's read takes the export's id", async () => {
    screens.mockResolvedValue({ status: "running", total: 3, job_id: "s9" } as never);
    await rehydrateActivityJobs("1");
    expect(byKind("screens:restored")?.jobId).toBe("s9");
  });

  it("a reload onto another serve starts empty", async () => {
    // Every serve says project 1 and the CLI's share a port, so a tab reloaded after
    // `serve studyB` must not show study A's chips. Each serve mints its own token.
    const w = window as unknown as Record<string, unknown>;
    try {
      w.__BRISTLENOSE_AUTH_TOKEN__ = "serve-a";
      await rehydrateActivityJobs("1");
      addJob("clips:1", { type: "clips", frameworkId: "", frameworkTitle: "", total: 4, jobId: "c1" });
      w.__BRISTLENOSE_AUTH_TOKEN__ = "serve-b";
      await reload();
      expect(getJobs().size).toBe(0);
      w.__BRISTLENOSE_AUTH_TOKEN__ = "serve-a";
      await reload();
      expect([...getJobs().keys()]).toEqual(["clips:1"]);
    } finally {
      delete w.__BRISTLENOSE_AUTH_TOKEN__;
    }
  });

  it("drops a carried finished chip whose export the server has replaced", async () => {
    // Its Reveal reads the server's export, which would be the newer one.
    await rehydrateActivityJobs("1");
    addJob("screens:1", { type: "screens", frameworkId: "", frameworkTitle: "", total: 2, jobId: "s1" });
    settleJob("screens:1", done);
    addJob("clips:1", { type: "clips", frameworkId: "", frameworkTitle: "", total: 4, jobId: "c1" });
    settleJob("clips:1", done);
    screens.mockResolvedValue({ status: "completed", total: 9, job_id: "s2" } as never);
    clips.mockResolvedValue({ status: "completed", total: 4, job_id: "c1" } as never);
    await reload();
    expect([...getJobs().keys()]).toEqual(["clips:1"]);
  });

  it("keeps an export started while the reads were out, though they name the one before", async () => {
    let answer!: (v: unknown) => void;
    clips.mockReturnValue(new Promise((r) => (answer = r)) as never);
    const pending = rehydrateActivityJobs("1");
    addJob("clips:7", { type: "clips", frameworkId: "", frameworkTitle: "", total: 4, jobId: "c-new" });
    answer({ status: "completed", total: 2, job_id: "c-old" });
    await pending;
    expect([...getJobs().keys()]).toEqual(["clips:7"]);
  });

  it("a stale carried chip does not keep a newer running export from its chip", async () => {
    await rehydrateActivityJobs("1");
    addJob("clips:1", { type: "clips", frameworkId: "", frameworkTitle: "", total: 4, jobId: "c1" });
    clips.mockResolvedValue({ status: "running", total: 9, job_id: "c2" } as never);
    await reload();
    expect(kinds()).toEqual(["clips:restored"]);
    expect(byKind("clips:restored")?.jobId).toBe("c2");
  });

  it("a finished restored chip is not overwritten by the next run's restored chip", async () => {
    clips.mockResolvedValue({ status: "running", total: 4, job_id: "c1" } as never);
    await rehydrateActivityJobs("1");
    const [first] = [...getJobs().keys()];
    settleJob(first, done);
    clips.mockResolvedValue({ status: "running", total: 9, job_id: "c2" } as never);
    // c1 finished and c2 began during the reload: the server names c2, so c1's chip goes; the
    // point here is that the new chip has an id of its own.
    await reload();
    expect([...getJobs().keys()]).not.toContain(first);
    expect(kinds()).toEqual(["clips:restored"]);
  });

  it("does not take a carried chip that claims to have ended running", async () => {
    sessionStorage.setItem("bristlenose-activity:1:", JSON.stringify([
      ["clips:1", { type: "clips", frameworkId: "", frameworkTitle: "", outcome: { ...done, status: "running" } }],
    ]));
    await rehydrateActivityJobs("1");
    expect(getJobs().get("clips:1")?.outcome).toBeUndefined();
  });

  it("a write that fails after one that worked leaves no old list behind, and says so once", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    await rehydrateActivityJobs("1");
    addJob("screens:1", { type: "screens", frameworkId: "", frameworkTitle: "", total: 2, copyWhenDone: true, jobId: "s1" });
    const set = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("full"); });
    try {
      settleJob("screens:1", done);
      removeJob("screens:1");
      expect(sessionStorage.getItem("bristlenose-activity:1:")).toBeNull();
      expect(warn).toHaveBeenCalledTimes(1);
    } finally {
      set.mockRestore();
      warn.mockRestore();
    }
  });

  it("an exported report neither reads nor writes session storage", async () => {
    vi.mocked(isExportMode).mockReturnValue(true);
    const get = vi.spyOn(Storage.prototype, "getItem");
    const set = vi.spyOn(Storage.prototype, "setItem");
    try {
      await rehydrateActivityJobs("1");
      addJob("clips:1", { type: "clips", frameworkId: "", frameworkTitle: "", total: 4 });
      removeJob("clips:1");
      expect(get).not.toHaveBeenCalled();
      expect(set).not.toHaveBeenCalled();
    } finally {
      get.mockRestore();
      set.mockRestore();
    }
  });

  it("works as before when session storage cannot be used", async () => {
    const get = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("denied"); });
    const set = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("denied"); });
    try {
      screens.mockResolvedValue({ status: "running", total: 3, job_id: "s9" } as never);
      await expect(rehydrateActivityJobs("1")).resolves.toBeUndefined();
      addJob("clips:1", { type: "clips", frameworkId: "", frameworkTitle: "", total: 4 });
      expect(kinds()).toEqual(["screens:restored", "clips:1"]);
    } finally {
      get.mockRestore();
      set.mockRestore();
    }
  });

  it("never gives a new run the id of a chip carried from the last page load", async () => {
    // The page's counters start again at every load; a new export under a carried chip's id
    // would inherit that chip's finished state in the stack.
    const now = vi.spyOn(Date, "now");
    try {
      vi.resetModules();
      now.mockReturnValue(1_000_000);
      const before = (await import("./ActivityStore")).newJobId("clips");
      vi.resetModules();
      now.mockReturnValue(2_000_000);
      const after = (await import("./ActivityStore")).newJobId("clips");
      expect(after).not.toBe(before);
      expect(after.startsWith("clips:")).toBe(true);
    } finally {
      now.mockRestore();
    }
  });

  it("ignores a carried list it cannot read", async () => {
    sessionStorage.setItem("bristlenose-activity:1:", "{not json");
    await rehydrateActivityJobs("1");
    expect(getJobs().size).toBe(0);
    sessionStorage.setItem("bristlenose-activity:1:", JSON.stringify([
      ["x", { type: "rocket", frameworkId: "", frameworkTitle: "" }],
      ["y", { type: "clips" }],
      7,
    ]));
    await reload();
    expect(getJobs().size).toBe(0);
  });
});
