/**
 * While a board builds, the panel says how far it has got: what is being counted, a bar only when
 * there is an honest fraction, a time left only when the server has earned one, and a Stop that
 * reaches the server. A board still building when the panel was closed is picked up on reopening.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MiroExportPanel } from "../MiroExportPanel";
import i18n from "../../i18n";
import type { MiroBoardBuild } from "../../utils/types";

const startMiroBoard = vi.fn();
const getMiroBoardStatus = vi.fn();
const cancelMiroBoard = vi.fn();

vi.mock("../../utils/api", () => ({
  getMiroStatus: vi.fn().mockResolvedValue({ connected: true }),
  postMiroConnect: vi.fn(),
  postMiroDisconnect: vi.fn(),
  startMiroBoard: (...a: unknown[]) => startMiroBoard(...a),
  getMiroBoardStatus: (...a: unknown[]) => getMiroBoardStatus(...a),
  cancelMiroBoard: (...a: unknown[]) => cancelMiroBoard(...a),
  apiGet: vi.fn().mockResolvedValue({ project_name: "Kitchen study" }),
}));
vi.mock("../../utils/announce", () => ({ announce: vi.fn() }));
vi.mock("../../utils/exportData", () => ({ isExportMode: vi.fn(() => false) }));
vi.mock("../../shims/bridge", () => ({ postStoreMiroToken: vi.fn() }));

const build = (b: Partial<MiroBoardBuild>): MiroBoardBuild => ({
  phase: "quotes", done: 0, total: 20, count_done: 0, count_total: 0, waiting: false,
  fraction: null, eta_seconds: null, ...b,
});
const status = (s: string, b: MiroBoardBuild | null = null) => ({
  status: s, board_url: "https://miro.com/app/board/b1/", stickies: 40, reason: null, vars: {},
  build: b,
});

/** Open the panel, then start a build whose status reads `running` with `b`, for ever. */
async function building(b: MiroBoardBuild): Promise<void> {
  render(<MiroExportPanel open onClose={() => {}} />);
  fireEvent.click(await screen.findByText(i18n.t("miro.createBoard")));
  getMiroBoardStatus.mockResolvedValue(status("running", b));
  await waitFor(() => expect(startMiroBoard).toHaveBeenCalled());
}

describe("MiroExportPanel — a board's progress", () => {
  beforeEach(async () => {
    startMiroBoard.mockReset().mockResolvedValue({ status: "started" });
    cancelMiroBoard.mockReset().mockResolvedValue({ cancelled: true });
    getMiroBoardStatus.mockReset().mockResolvedValue(status("idle"));
    await i18n.changeLanguage("en");
  });

  it("while the board opens: says so, and the bar claims no fraction", async () => {
    await building(build({ phase: "opening", done: 1 }));
    await screen.findByText(i18n.t("miro.progressOpening"));
    const bar = screen.getByTestId("bn-miro-build-bar") as HTMLProgressElement;
    expect(bar.hasAttribute("value")).toBe(false);  // the browser's indeterminate bar
    expect(screen.queryByTestId("bn-miro-build-eta")).toBeNull();
  });

  it("placing quotes: counts quotes, fills the bar by calls made, and says the time once earned", async () => {
    await building(build({ phase: "quotes", done: 6, count_done: 40, count_total: 120, fraction: 0.3,
                           eta_seconds: 150 }));
    await screen.findByText(i18n.t("miro.progressQuotes", { done: 40, total: 120 }));
    expect((screen.getByTestId("bn-miro-build-bar") as HTMLProgressElement).value).toBeCloseTo(0.3);
    expect(screen.getByTestId("bn-miro-build-eta").textContent).toBe(i18n.t("miro.etaMinutes", { count: 3 }));
  });

  it("under a minute left reads '<1 min', and no estimate reads nothing", async () => {
    await building(build({ phase: "groups", count_done: 2, count_total: 9, fraction: 0.9, eta_seconds: 12 }));
    await screen.findByText(i18n.t("miro.progressGroups", { done: 2, total: 9 }));
    expect(screen.getByTestId("bn-miro-build-eta").textContent).toBe(i18n.t("miro.etaUnderMinute"));
  });

  it("a wait for Miro is said as waiting, the count kept on the bar", async () => {
    await building(build({ phase: "quotes", count_done: 40, count_total: 120, fraction: 0.3, waiting: true }));
    await screen.findByText(i18n.t("miro.progressWaiting"));
    expect((screen.getByTestId("bn-miro-build-bar") as HTMLProgressElement).value).toBeCloseTo(0.3);
  });

  it("Stop reaches the server and hands the form back at once", async () => {
    await building(build({ phase: "quotes", count_done: 1, count_total: 9, fraction: 0.1 }));
    await screen.findByText(i18n.t("miro.progressQuotes", { done: 1, total: 9 }));
    fireEvent.click(screen.getByText(i18n.t("miro.cancel")));
    expect(cancelMiroBoard).toHaveBeenCalledTimes(1);
    await screen.findByText(i18n.t("miro.createBoard"));
  });

  it("a finished board says how many quotes it placed and links to it", async () => {
    render(<MiroExportPanel open onClose={() => {}} />);
    fireEvent.click(await screen.findByText(i18n.t("miro.createBoard")));
    getMiroBoardStatus.mockResolvedValue(status("completed"));
    await screen.findByText(i18n.t("miro.boardReady", { count: 40 }));
    expect(screen.getByText(i18n.t("miro.openInMiro")).closest("a")).toHaveAttribute(
      "href", "https://miro.com/app/board/b1/");
  });

  it("a board still building when the panel reopens is shown, not lost", async () => {
    getMiroBoardStatus.mockResolvedValue(status("running", build({
      phase: "quotes", count_done: 20, count_total: 120, fraction: 0.2 })));
    render(<MiroExportPanel open onClose={() => {}} />);
    await screen.findByText(i18n.t("miro.progressQuotes", { done: 20, total: 120 }));
    expect(startMiroBoard).not.toHaveBeenCalled();
  });
});
