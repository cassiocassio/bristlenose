import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("./api", () => ({
  getClipExtractionStatus: vi.fn(),
  getScreensExportStatus: vi.fn(),
  revealClips: vi.fn(() => Promise.resolve({ revealed: true, path: "" })),
  revealScreens: vi.fn(() => Promise.resolve({ revealed: true, path: "" })),
}));

import { fileUri, revealExport } from "./revealExport";
import { _resetEmbeddedCache } from "./embedded";
import {
  getClipExtractionStatus,
  getScreensExportStatus,
  revealClips,
  revealScreens,
} from "./api";

const win = window as unknown as Record<string, unknown>;
let postMessage: ReturnType<typeof vi.fn>;

function screensStatus(output_dir: string | null, files: string[]) {
  return {
    status: "completed" as const, progress: 0, total: 0, completed_count: 0, skipped_count: 0,
    current: "", output_dir, files,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  postMessage = vi.fn();
  win.webkit = { messageHandlers: { navigation: { postMessage } } };
});

afterEach(() => {
  delete win.webkit;
  delete win.__BRISTLENOSE_EMBEDDED__;
  _resetEmbeddedCache();
});

function embed() {
  win.__BRISTLENOSE_EMBEDDED__ = true;
  _resetEmbeddedCache();
}

describe("fileUri", () => {
  it("percent-encodes each component and keeps the slashes", () => {
    expect(fileUri("/Users/r/Étude #2 ? 50%/clips")).toBe(
      "file:///Users/r/%C3%89tude%20%232%20%3F%2050%25/clips",
    );
  });
});

describe("revealExport", () => {
  it("in a browser asks the server, which can reveal there", async () => {
    await revealExport("clips");
    await revealExport("screens");
    expect(revealClips).toHaveBeenCalledOnce();
    expect(revealScreens).toHaveBeenCalledOnce();
    expect(postMessage).not.toHaveBeenCalled();
  });

  it("in the app shows the screens folder when the export wrote no files", async () => {
    embed();
    vi.mocked(getScreensExportStatus).mockResolvedValue(screensStatus("/s/screens/", []));
    await revealExport("screens");
    expect(postMessage).toHaveBeenCalledWith({
      type: "project-action", action: "reveal-in-finder", data: { uri: "file:///s/screens/" },
    });
    expect(revealScreens).not.toHaveBeenCalled();
  });

  it("in the app posts nothing, and fails, when there is no export folder to show", async () => {
    embed();
    vi.mocked(getClipExtractionStatus).mockResolvedValue({
      status: "idle", progress: 0, total: 0, completed_count: 0, skipped_count: 0,
      current_clip: "", output_dir: null,
    });
    await expect(revealExport("clips")).rejects.toThrow("no finished clips export");
    expect(postMessage).not.toHaveBeenCalled();
    expect(revealClips).not.toHaveBeenCalled();
  });

  it("in the app posts nothing when the status read fails", async () => {
    embed();
    vi.mocked(getScreensExportStatus).mockRejectedValue(new Error("timed out"));
    await expect(revealExport("screens")).rejects.toThrow("timed out");
    expect(postMessage).not.toHaveBeenCalled();
  });
});
