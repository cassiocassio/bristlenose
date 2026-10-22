import { describe, it, expect, beforeEach, vi } from "vitest";

vi.mock("./api", () => ({ startClipExtraction: vi.fn() }));
vi.mock("./toast", () => ({ toast: vi.fn() }));
vi.mock("./announce", () => ({ announce: vi.fn() }));
vi.mock("../contexts/ActivityStore", () => ({
  addJob: vi.fn(), getJobs: vi.fn(() => new Map()), removeJob: vi.fn(), newJobId: vi.fn((kind: string) => `${kind}:t-1`),
}));

import { startClipExtraction } from "./api";
import { toast } from "./toast";
import { announce } from "./announce";
import { extractVideoClips } from "./exportActions";
import { _resetSubtitlePrefsForTests, setSubtitlePref } from "./subtitlePrefs";

const t = ((key: string) => key) as unknown as Parameters<typeof extractVideoClips>[1];
const start = vi.mocked(startClipExtraction);

beforeEach(() => {
  localStorage.clear();
  _resetSubtitlePrefsForTests();
  start.mockReset();
  vi.mocked(toast).mockReset();
  vi.mocked(announce).mockReset();
});

describe("extractVideoClips — burn-in", () => {
  it("does not ask for burned copies by default", async () => {
    start.mockResolvedValue({ total: 2, pii_warning: false } as never);
    await extractVideoClips(["q1"], t);
    expect(start).toHaveBeenCalledWith(false, ["q1"], false);
  });

  it("asks for burned copies when the preference is on", async () => {
    setSubtitlePref("burnSubtitles", true);
    start.mockResolvedValue({ total: 2, pii_warning: false } as never);
    await extractVideoClips(["q1"], t);
    expect(start).toHaveBeenCalledWith(false, ["q1"], true);
  });

  it("tells the researcher when this ffmpeg cannot burn", async () => {
    setSubtitlePref("burnSubtitles", true);
    start.mockResolvedValue({ total: 2, pii_warning: false, burn_unavailable: true } as never);
    await extractVideoClips(["q1"], t);
    expect(toast).toHaveBeenCalledWith("export.clips.burnUnavailable", 6000);
  });

  it("keeps the privacy warning when both notices apply", async () => {
    setSubtitlePref("burnSubtitles", true);
    start.mockResolvedValue({ total: 2, pii_warning: true, burn_unavailable: true } as never);
    await extractVideoClips(["q1"], t, true);
    // One toast replaces the last, so a second call would erase the first.
    expect(toast).toHaveBeenCalledOnce();
    expect(vi.mocked(toast).mock.calls[0][0]).toContain("export.clips.piiWarning");
    expect(vi.mocked(toast).mock.calls[0][0]).toContain("export.clips.burnUnavailable");
  });

  it("speaks the notices as well as the progress, since the progress line replaces the toast's", async () => {
    start.mockResolvedValue({ total: 2, pii_warning: true } as never);
    await extractVideoClips(["q1"], t, true);
    expect(announce).toHaveBeenCalledOnce();
    const spoken = vi.mocked(announce).mock.calls[0][0];
    expect(spoken).toContain("export.clips.piiWarning");
    expect(spoken).toContain("export.clips.progress");
  });
});
