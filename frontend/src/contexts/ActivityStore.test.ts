import { renderHook, act } from "@testing-library/react";
import {
  addJob,
  removeJob,
  getJobs,
  useActivityJobs,
  resetActivityStore,
} from "./ActivityStore";

describe("ActivityStore", () => {
  beforeEach(() => {
    resetActivityStore();
  });

  it("starts empty", () => {
    expect(getJobs().size).toBe(0);
  });

  it("addJob adds an entry", () => {
    addJob("autocode:garrett", { frameworkId: "garrett", frameworkTitle: "Garrett" });
    expect(getJobs().size).toBe(1);
    expect(getJobs().get("autocode:garrett")).toEqual({
      frameworkId: "garrett",
      frameworkTitle: "Garrett",
    });
  });

  it("removeJob removes an entry", () => {
    addJob("autocode:garrett", { frameworkId: "garrett", frameworkTitle: "Garrett" });
    removeJob("autocode:garrett");
    expect(getJobs().size).toBe(0);
  });

  it("removeJob is a no-op for unknown id", () => {
    addJob("autocode:garrett", { frameworkId: "garrett", frameworkTitle: "Garrett" });
    removeJob("autocode:unknown");
    expect(getJobs().size).toBe(1);
  });

  it("addJob overwrites existing entry with same id", () => {
    addJob("autocode:garrett", { frameworkId: "garrett", frameworkTitle: "Garrett" });
    addJob("autocode:garrett", { frameworkId: "garrett", frameworkTitle: "Garrett v2" });
    expect(getJobs().size).toBe(1);
    expect(getJobs().get("autocode:garrett")!.frameworkTitle).toBe("Garrett v2");
  });

  it("resetActivityStore clears all jobs", () => {
    addJob("autocode:garrett", { frameworkId: "garrett", frameworkTitle: "Garrett" });
    addJob("autocode:norman", { frameworkId: "norman", frameworkTitle: "Norman" });
    resetActivityStore();
    expect(getJobs().size).toBe(0);
  });

  it("useActivityJobs hook tracks mutations", () => {
    const { result } = renderHook(() => useActivityJobs());
    expect(result.current.size).toBe(0);

    act(() => {
      addJob("autocode:garrett", { frameworkId: "garrett", frameworkTitle: "Garrett" });
    });
    expect(result.current.size).toBe(1);

    act(() => {
      removeJob("autocode:garrett");
    });
    expect(result.current.size).toBe(0);
  });

  it("produces a new snapshot ref on each mutation", () => {
    const snap1 = getJobs();
    addJob("autocode:garrett", { frameworkId: "garrett", frameworkTitle: "Garrett" });
    const snap2 = getJobs();
    expect(snap1).not.toBe(snap2);
  });
});
