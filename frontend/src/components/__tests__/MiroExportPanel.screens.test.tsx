/**
 * On the Screens lens the Miro panel builds the screens board (docs/design-screens-export.md §6):
 * it starts the job, reads its progress until it ends, and never calls the quotes export.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MiroExportPanel } from "../MiroExportPanel";
import i18n from "../../i18n";

const postMiroExport = vi.fn();
const startScreensMiro = vi.fn();
const getScreensMiroStatus = vi.fn();

vi.mock("../../utils/api", () => ({
  getMiroStatus: vi.fn().mockResolvedValue({ connected: true }),
  postMiroConnect: vi.fn(),
  postMiroDisconnect: vi.fn(),
  postMiroExport: (...a: unknown[]) => postMiroExport(...a),
  startScreensMiro: (...a: unknown[]) => startScreensMiro(...a),
  getScreensMiroStatus: (...a: unknown[]) => getScreensMiroStatus(...a),
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
    postMiroExport.mockReset();
    startScreensMiro.mockReset().mockResolvedValue({ status: "started", total: 9 });
    getScreensMiroStatus.mockReset();
    await i18n.changeLanguage("en");
  });

  it("builds the screens board, not the quotes one, and offers no clip links", async () => {
    getScreensMiroStatus.mockResolvedValueOnce(status("completed"));
    render(<MiroExportPanel open screens onClose={() => {}} />);
    fireEvent.click(await screen.findByText(i18n.t("miro.createBoard")));
    expect(screen.queryByText(i18n.t("miro.linkClipsLabel"))).toBeNull();
    await screen.findByText(i18n.t("export.screens.done", { count: 9 }));
    expect(startScreensMiro).toHaveBeenCalledWith(expect.objectContaining({ locale: "en", colour_by: "sentiment" }));
    expect(postMiroExport).not.toHaveBeenCalled();
    expect(screen.getByText(i18n.t("miro.openInMiro")).closest("a")).toHaveAttribute(
      "href", "https://miro.com/app/board/s1/");
  });

  it("a board left part-built names its reason and its address", async () => {
    getScreensMiroStatus.mockResolvedValueOnce(status("failed", { reason: "board_incomplete" }));
    render(<MiroExportPanel open screens onClose={() => {}} />);
    fireEvent.click(await screen.findByText(i18n.t("miro.createBoard")));
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toBe(
        `${i18n.t("miro.errBoardIncomplete")} https://miro.com/app/board/s1/`));
  });
});
