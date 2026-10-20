import { renderHook, act } from "@testing-library/react";
import { vi } from "vitest";
import {
  addJob,
  removeJob,
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
    expect([...getJobs()]).toEqual([
      ["clips:restored", { type: "clips", frameworkId: "", frameworkTitle: "", total: 7 }],
    ]);
  });

  it("puts back a running screens export as a plain export", async () => {
    screens.mockResolvedValue({ status: "running", total: 3 } as never);
    await rehydrateActivityJobs("1");
    expect(getJobs().get("screens:restored")).toEqual({
      type: "screens", frameworkId: "", frameworkTitle: "", total: 3, copyWhenDone: false,
    });
  });

  it("puts back each AutoCode run in flight under its codebook's title, but not a catch-up", async () => {
    autocode.mockResolvedValue({
      jobs: [
        { framework_id: "garrett", title: "Garrett", status: "running", completed_at: null },
        { framework_id: "norman", title: "Norman", status: "pending", completed_at: null },
        { framework_id: "morville", title: "Morville", status: "running", completed_at: "2026-10-20T10:00:00" },
      ],
    });
    await rehydrateActivityJobs("1");
    expect([...getJobs().keys()]).toEqual(["autocode:garrett:restored", "autocode:norman:restored"]);
    expect(getJobs().get("autocode:garrett:restored")).toEqual({
      type: "autocode", frameworkId: "garrett", frameworkTitle: "Garrett", originRoute: "/report/codebook/",
    });
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
    expect([...getJobs().keys()]).toEqual(["autocode:garrett:restored"]);
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
    expect([...getJobs().keys()]).toEqual(["autocode:garrett:restored"]);
  });

  it("reads once more after a failed read, and keeps what it restored the first time", async () => {
    vi.useFakeTimers();
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    try {
      clips.mockRejectedValueOnce(new Error("GET /export/clips/status → timeout"));
      clips.mockResolvedValue({ status: "running", total: 6 } as never);
      screens.mockResolvedValue({ status: "running", total: 2 } as never);
      await rehydrateActivityJobs("1");
      expect([...getJobs().keys()]).toEqual(["screens:restored"]);
      await vi.advanceTimersByTimeAsync(5_000);
      expect([...getJobs().keys()]).toEqual(["screens:restored", "clips:restored"]);
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
