/**
 * "Send to FigJam": the dialog checks the board file, downloads it, and says
 * what to do in FigJam (docs/design-board-integrations.md). The download is a
 * file the plugin opens, so a refusal must be said here, never saved as a file.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { FigJamExportPanel } from "../FigJamExportPanel";
import i18n from "../../i18n";
import { featureFlags, resetFeatureFlags } from "../../utils/featureFlags";

const apiGet = vi.fn();
const getFigJamBoard = vi.fn();
const figjamBoardDownloadUrl = vi.fn(() => "/api/projects/1/export/figjam-board.json?x=1");

vi.mock("../../utils/api", () => ({
  apiGet: (...a: unknown[]) => apiGet(...a),
  getFigJamBoard: (...a: unknown[]) => getFigJamBoard(...a),
  figjamBoardDownloadUrl: (...a: unknown[]) => figjamBoardDownloadUrl(...(a as [])),
}));
vi.mock("../../utils/announce", () => ({ announce: vi.fn() }));
vi.mock("../../utils/exportData", () => ({ isExportMode: vi.fn(() => false) }));

const refusal = (reason: string) => Object.assign(new Error("GET 404"), { reason, status: 404 });

let clicked: string[] = [];

describe("FigJamExportPanel", () => {
  beforeEach(async () => {
    apiGet.mockReset().mockResolvedValue({ project_name: "Renfe kiosks" });
    getFigJamBoard.mockReset().mockResolvedValue({ totals: { quotes: 30 } });
    figjamBoardDownloadUrl.mockClear();
    clicked = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      clicked.push(this.getAttribute("href") ?? "");
    });
    resetFeatureFlags();
    await i18n.changeLanguage("en");
  });

  it("offers no clip links while they are parked", async () => {
    render(<FigJamExportPanel open onClose={() => {}} />);
    await waitFor(() => expect(apiGet).toHaveBeenCalled());
    expect(screen.queryByText(i18n.t("miro.linkClipsLabel"))).toBeNull();
  });

  it("sends a clip folder once the parked choice is on and ticked", async () => {
    featureFlags.boardClipLinks = true;
    render(<FigJamExportPanel open onClose={() => {}} />);
    await waitFor(() => expect(apiGet).toHaveBeenCalled());
    fireEvent.click(screen.getByText(i18n.t("miro.linkClipsLabel")));
    fireEvent.change(screen.getByLabelText(i18n.t("miro.linkClipsLabel")),
      { target: { value: " https://x.example/c " } });
    fireEvent.click(screen.getByTestId("bn-figjam-download"));
    await waitFor(() => expect(getFigJamBoard).toHaveBeenCalled());
    expect(getFigJamBoard.mock.calls[0][0]).toMatchObject({ clips_base: "https://x.example/c" });
  });

  it("arrives with the project's name in the board name, not a hint", async () => {
    render(<FigJamExportPanel open onClose={() => {}} />);
    const field = screen.getByLabelText(i18n.t("miro.boardNameLabel")) as HTMLInputElement;
    await waitFor(() => expect(field.value).toBe("Renfe kiosks"));
    expect(field.placeholder).toBe("");
  });

  it("keeps a name the researcher typed", async () => {
    const { rerender } = render(<FigJamExportPanel open onClose={() => {}} />);
    const field = screen.getByLabelText(i18n.t("miro.boardNameLabel")) as HTMLInputElement;
    fireEvent.change(field, { target: { value: "Round 2" } });
    rerender(<FigJamExportPanel open={false} onClose={() => {}} />);
    rerender(<FigJamExportPanel open onClose={() => {}} />);
    await waitFor(() => expect(apiGet).toHaveBeenCalled());
    expect(field.value).toBe("Round 2");
  });

  it("defaults to breaking long quotes and square stickies", async () => {
    render(<FigJamExportPanel open onClose={() => {}} />);
    await waitFor(() => expect(apiGet).toHaveBeenCalled());
    fireEvent.click(screen.getByTestId("bn-figjam-download"));
    await waitFor(() => expect(getFigJamBoard).toHaveBeenCalled());
    expect(getFigJamBoard.mock.calls[0][0]).toMatchObject({
      split_long_quotes: true, sticky_shape: "square", clips_base: "", locale: "en",
    });
  });

  it("checks the file, downloads it, then says how to finish in FigJam", async () => {
    render(<FigJamExportPanel open onClose={() => {}} />);
    await waitFor(() => expect(apiGet).toHaveBeenCalled());
    fireEvent.click(screen.getByLabelText(i18n.t("miro.stickyShapeRectangle")));
    fireEvent.click(screen.getByTestId("bn-figjam-download"));
    await screen.findByTestId("bn-figjam-steps");
    expect(getFigJamBoard.mock.calls[0][0]).toMatchObject({ sticky_shape: "rectangle" });
    expect(clicked).toEqual(["/api/projects/1/export/figjam-board.json?x=1"]);
    expect(screen.getByText(i18n.t("figjam.downloading", { count: 30 }))).toBeInTheDocument();
  });

  it.each([
    ["no_quotes_selected", "miro.errNoQuotesSelected"],
    ["clips_base_not_http", "figjam.errClipsBase"],
  ])("says a %s refusal in words and downloads nothing", async (reason, key) => {
    getFigJamBoard.mockRejectedValueOnce(refusal(reason));
    render(<FigJamExportPanel open onClose={() => {}} />);
    await waitFor(() => expect(apiGet).toHaveBeenCalled());
    fireEvent.click(screen.getByTestId("bn-figjam-download"));
    expect(await screen.findByRole("alert")).toHaveTextContent(i18n.t(key));
    expect(clicked).toEqual([]);
    expect(screen.queryByTestId("bn-figjam-steps")).toBeNull();
  });
});
