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

  it("refuses a relative path, whose first component would read as a host", () => {
    expect(() => fileUri("bristlenose-output/clips")).toThrow();
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

  it("in a browser fails when the server could not show the folder", async () => {
    vi.mocked(revealClips).mockResolvedValueOnce({ revealed: false, path: "/s/clips" });
    await expect(revealExport("clips")).rejects.toThrow("could not show");
  });

  it("in the app shows nothing for an export that did not finish", async () => {
    embed();
    vi.mocked(getScreensExportStatus).mockResolvedValue({
      ...screensStatus("/s/screens", ["p1-01.jpg"]), status: "cancelled",
    });
    await expect(revealExport("screens")).rejects.toThrow("no finished screens export");
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

  it("in the app posts nothing, and fails, when the latest clips export did not finish", async () => {
    // A newer export replaced the chip's: cancelled, with the partial folder it left.
    embed();
    vi.mocked(getClipExtractionStatus).mockResolvedValue({
      status: "cancelled", progress: 1, total: 3, completed_count: 1, skipped_count: 0,
      current_clip: "", output_dir: "/s/clips",
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
