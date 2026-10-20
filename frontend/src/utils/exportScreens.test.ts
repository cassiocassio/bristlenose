/**
 * Each screens export is its own chip job. A fixed id made the chip remember a finished job by
 * name, so a second Copy Screens looked finished at once and never reached the clipboard.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api", () => ({
  startClipExtraction: vi.fn().mockResolvedValue({ total: 2, pii_warning: false }),
  startScreensExport: vi.fn().mockResolvedValue({ status: "started", total: 3 }),
}));
vi.mock("./toast", () => ({ toast: vi.fn() }));
vi.mock("./announce", () => ({ announce: vi.fn() }));

import { getJobs, resetActivityStore } from "../contexts/ActivityStore";
import { exportScreens, extractVideoClips } from "./exportActions";

const t = ((k: string) => k) as unknown as Parameters<typeof exportScreens>[0];

describe("exportScreens", () => {
  beforeEach(() => resetActivityStore());

  it("gives every export its own job, and keeps only the latest", async () => {
    await exportScreens(t, true);
    const first = [...getJobs().keys()];
    await exportScreens(t, true);
    const second = [...getJobs().keys()];
    expect(first).toHaveLength(1);
    expect(second).toHaveLength(1);
    expect(second[0]).not.toBe(first[0]);
    expect(getJobs().get(second[0])).toMatchObject({ type: "screens", copyWhenDone: true, total: 3 });
  });
});

describe("extractVideoClips (R13)", () => {
  beforeEach(() => resetActivityStore());

  it("gives every export its own job too, so the last one's outcome cannot stand for it", async () => {
    await extractVideoClips(["q1"], t);
    const first = [...getJobs().keys()];
    await extractVideoClips(["q1"], t);
    const second = [...getJobs().keys()];
    expect(first).toHaveLength(1);
    expect(second).toHaveLength(1);
    expect(second[0]).not.toBe(first[0]);
    expect(getJobs().get(second[0])).toMatchObject({ type: "clips", total: 2 });
  });
});
