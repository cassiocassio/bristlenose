/**
 * On the Screens lens the Miro panel builds the screens board (docs/design-screens-export.md §6):
 * it starts the job, reads its progress until it ends, and never calls the quotes export.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MiroExportPanel } from "../MiroExportPanel";
import i18n from "../../i18n";

const startMiroBoard = vi.fn();
const getMiroBoardStatus = vi.fn();
const startScreensMiro = vi.fn();
const getScreensMiroStatus = vi.fn();
const cancelScreensMiro = vi.fn().mockResolvedValue({ cancelled: true });

vi.mock("../../utils/api", () => ({
  getMiroStatus: vi.fn().mockResolvedValue({ connected: true }),
  postMiroConnect: vi.fn(),
  postMiroDisconnect: vi.fn(),
  startMiroBoard: (...a: unknown[]) => startMiroBoard(...a),
  getMiroBoardStatus: (...a: unknown[]) => getMiroBoardStatus(...a),
  cancelMiroBoard: vi.fn().mockResolvedValue({ cancelled: true }),
  startScreensMiro: (...a: unknown[]) => startScreensMiro(...a),
  getScreensMiroStatus: (...a: unknown[]) => getScreensMiroStatus(...a),
  cancelScreensMiro: (...a: unknown[]) => cancelScreensMiro(...a),
  apiGet: vi.fn().mockResolvedValue({ project_name: "Kitchen study" }),
}));
vi.mock("../../utils/announce", () => ({ announce: vi.fn() }));
vi.mock("../../utils/exportData", () => ({ isExportMode: vi.fn(() => false) }));
vi.mock("../../shims/bridge", () => ({ postStoreMiroToken: vi.fn() }));

const status = (s: string, extra: object = {}) => ({
  status: s, progress: 0, total: 9, completed_count: 9, skipped_count: 0, current: "",
  board_url: "https://miro.com/app/board/s1/", reason: null, ...extra,
});

describe("MiroExportPanel — the screens board", () => {
  beforeEach(async () => {
    vi.useRealTimers();
    startMiroBoard.mockReset();
    startScreensMiro.mockReset().mockResolvedValue({ status: "started", total: 9 });
    // Opening the panel asks whether a build is already running; nothing is, by default.
    getScreensMiroStatus.mockReset().mockResolvedValue(status("idle"));
    await i18n.changeLanguage("en");
  });

  /** Open the panel, wait for its form, then queue what the build's status reads say. */
  async function openThen(...reads: object[]): Promise<void> {
    render(<MiroExportPanel open screens onClose={() => {}} />);
    await screen.findByText(i18n.t("miro.createBoard"));
    await waitFor(() => expect(getScreensMiroStatus).toHaveBeenCalledTimes(1));
    for (const r of reads) getScreensMiroStatus.mockResolvedValueOnce(r);
  }

  it("builds the screens board, not the quotes one, and offers no clip links", async () => {
    await openThen(status("completed"));
    expect(screen.queryByText(i18n.t("miro.linkClipsLabel"))).toBeNull();
    fireEvent.click(screen.getByText(i18n.t("miro.createBoard")));
    await screen.findByText(i18n.t("export.screens.done", { count: 9 }));
    expect(startScreensMiro).toHaveBeenCalledWith(expect.objectContaining({ locale: "en", colour_by: "none" }));
    expect(startMiroBoard).not.toHaveBeenCalled();
    expect(screen.getByText(i18n.t("miro.openInMiro")).closest("a")).toHaveAttribute(
      "href", "https://miro.com/app/board/s1/");
  });

  it("a board left part-built names its reason and its address", async () => {
    await openThen(status("failed", { reason: "board_incomplete" }));
    fireEvent.click(screen.getByText(i18n.t("miro.createBoard")));
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toBe(
        `${i18n.t("miro.errBoardIncomplete")} https://miro.com/app/board/s1/`));
  });

  it("nothing to export says so, and never shows the last build's board", async () => {
    startScreensMiro.mockResolvedValueOnce({ status: "no_screens", total: 0 });
    await openThen();
    getScreensMiroStatus.mockResolvedValue(status("completed"));  // the previous build's
    fireEvent.click(screen.getByText(i18n.t("miro.createBoard")));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe(i18n.t("export.screens.none")));
    expect(getScreensMiroStatus).toHaveBeenCalledTimes(1);  // only the check on opening
    expect(screen.queryByText(i18n.t("miro.openInMiro"))).toBeNull();
  });

  it("says how many screens could not be shown", async () => {
    await openThen(status("completed", { completed_count: 7, skipped_count: 2 }));
    fireEvent.click(screen.getByText(i18n.t("miro.createBoard")));
    await screen.findByText(i18n.t("export.screens.partial", { written: 7, total: 9 }));
  });

  it("Cancel stops the build on the server and the wait in the panel", async () => {
    await openThen();
    getScreensMiroStatus.mockResolvedValue(status("running", {
      progress: 2,
      build: { phase: "screens", done: 12, total: 40, count_done: 2, count_total: 9, waiting: false,
               fraction: 0.3, eta_seconds: null },
    }));
    fireEvent.click(screen.getByText(i18n.t("miro.createBoard")));
    await screen.findByText(i18n.t("miro.progressScreens", { done: 2, total: 9 }));
    fireEvent.click(screen.getByText(i18n.t("miro.cancel")));
    expect(cancelScreensMiro).toHaveBeenCalledTimes(1);
    await screen.findByText(i18n.t("miro.createBoard"));
  });
});

describe("MiroExportPanel — breaking long quotes", () => {
  it("is offered ticked, and unticking it reaches the board", async () => {
    await i18n.changeLanguage("en");
    startScreensMiro.mockReset().mockResolvedValue({ status: "started", total: 9 });
    getScreensMiroStatus.mockReset().mockResolvedValueOnce(status("idle")).mockResolvedValue(status("completed"));
    render(<MiroExportPanel open screens onClose={() => {}} />);
    const box = (await screen.findByTestId("bn-miro-split-long")) as HTMLInputElement;
    expect(box.checked).toBe(true);
    fireEvent.click(box);
    fireEvent.click(screen.getByText(i18n.t("miro.createBoard")));
    await waitFor(() =>
      expect(startScreensMiro).toHaveBeenCalledWith(expect.objectContaining({ split_long_quotes: false })));
  });
});

describe("MiroExportPanel — sticky shape", () => {
  it("offers rectangle, chosen, and square reaches the board when picked", async () => {
    await i18n.changeLanguage("en");
    startScreensMiro.mockReset().mockResolvedValue({ status: "started", total: 9 });
    getScreensMiroStatus.mockReset().mockResolvedValueOnce(status("idle")).mockResolvedValue(status("completed"));
    render(<MiroExportPanel open screens onClose={() => {}} />);
    const rect = await screen.findByLabelText(i18n.t("miro.stickyShapeRectangle"));
    expect((rect as HTMLInputElement).checked).toBe(true);
    fireEvent.click(screen.getByLabelText(i18n.t("miro.stickyShapeSquare")));
    fireEvent.click(screen.getByText(i18n.t("miro.createBoard")));
    await waitFor(() =>
      expect(startScreensMiro).toHaveBeenCalledWith(expect.objectContaining({ sticky_shape: "square" })));
  });
});

describe("MiroExportPanel — the board name", () => {
  beforeEach(async () => {
    vi.useRealTimers();
    startMiroBoard.mockReset().mockResolvedValue({ status: "started" });
    getMiroBoardStatus.mockReset().mockResolvedValue({
      status: "idle", board_url: null, stickies: 0, reason: null, vars: {}, build: null });
    startScreensMiro.mockReset().mockResolvedValue({ status: "started", total: 9 });
    await i18n.changeLanguage("en");
  });

  it("arrives filled with the name the board would get anyway", async () => {
    const { unmount } = render(<MiroExportPanel open onClose={() => {}} />);
    await waitFor(() => expect(screen.getByLabelText(i18n.t("miro.boardNameLabel"))).toHaveValue("Kitchen study"));
    unmount();
    render(<MiroExportPanel open screens onClose={() => {}} />);
    await waitFor(() =>
      expect(screen.getByLabelText(i18n.t("miro.boardNameLabel"))).toHaveValue(
        `Kitchen study · ${i18n.t("screens.title")}`));
  });

  it("keeps a name the researcher typed", async () => {
    render(<MiroExportPanel open onClose={() => {}} />);
    const field = await screen.findByLabelText(i18n.t("miro.boardNameLabel"));
    await waitFor(() => expect(field).toHaveValue("Kitchen study"));
    fireEvent.change(field, { target: { value: "Workshop" } });
    fireEvent.click(screen.getByText(i18n.t("miro.createBoard")));
    await waitFor(() =>
      expect(startMiroBoard).toHaveBeenCalledWith(expect.objectContaining({ board_name: "Workshop" })));
  });
});
