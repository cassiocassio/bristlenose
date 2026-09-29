import { describe, it, expect, beforeEach, vi } from "vitest";

vi.mock("./api", () => ({ startClipExtraction: vi.fn() }));
vi.mock("./toast", () => ({ toast: vi.fn() }));
vi.mock("./announce", () => ({ announce: vi.fn() }));
vi.mock("../contexts/ActivityStore", () => ({ addJob: vi.fn() }));

import { startClipExtraction } from "./api";
import { toast } from "./toast";
import { extractVideoClips } from "./exportActions";
import { _resetSubtitlePrefsForTests, setSubtitlePref } from "./subtitlePrefs";

const t = ((key: string) => key) as unknown as Parameters<typeof extractVideoClips>[1];
const start = vi.mocked(startClipExtraction);

beforeEach(() => {
  localStorage.clear();
  _resetSubtitlePrefsForTests();
  start.mockReset();
  vi.mocked(toast).mockReset();
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
    expect(toast).toHaveBeenCalledWith("export.clips.burnUnavailable");
  });
});
