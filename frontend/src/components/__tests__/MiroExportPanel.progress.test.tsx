/**
 * While a board builds, the panel says how far it has got: what is being counted, a bar only when
 * there is an honest fraction, a time left only when the server has earned one, and a Stop that
 * reaches the server. A board still building when the panel was closed is picked up on reopening.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MiroExportPanel } from "../MiroExportPanel";
import i18n from "../../i18n";
import { loadLocaleResources } from "../../i18n/localeLoader";
import type { MiroBoardBuild } from "../../utils/types";

const startMiroBoard = vi.fn();
const getMiroBoardStatus = vi.fn();
const cancelMiroBoard = vi.fn();
const getMiroStatus = vi.fn();

vi.mock("../../utils/api", () => ({
  getMiroStatus: (...a: unknown[]) => getMiroStatus(...a),
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
    getMiroStatus.mockReset().mockResolvedValue({ connected: true });
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

  it("one minute left agrees in number where the language needs it", async () => {
    // Non-English strings arrive as the app loads them, through the locale loader.
    const fr = await loadLocaleResources("fr", ["common"]);
    i18n.addResourceBundle("fr", "common", fr.common, true, true);
    await i18n.changeLanguage("fr");
    await building(build({ phase: "groups", count_done: 2, count_total: 90, fraction: 0.5, eta_seconds: 70 }));
    await waitFor(() => expect(screen.getByTestId("bn-miro-build-eta").textContent).toBe("~1 min restante"));
    getMiroBoardStatus.mockResolvedValue(status("running", build({
      phase: "groups", count_done: 2, count_total: 90, fraction: 0.5, eta_seconds: 180 })));
    // The panel reads the build every 1.5 s, longer than waitFor's default second.
    await waitFor(() => expect(screen.getByTestId("bn-miro-build-eta").textContent).toBe("~3 min restantes"),
      { timeout: 4000 });
    await i18n.changeLanguage("en");
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

  it("a second Create while the last board is still stopping says so", async () => {
    startMiroBoard.mockRejectedValueOnce(new Error("POST /miro/board 409"));
    render(<MiroExportPanel open onClose={() => {}} />);
    fireEvent.click(await screen.findByText(i18n.t("miro.createBoard")));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe(i18n.t("miro.stillStopping")));
  });

  it("starting a board while not connected says so, not the server's English (R94)", async () => {
    startMiroBoard.mockRejectedValueOnce(Object.assign(new Error("POST /miro/board 400: Not connected to Miro"),
      { reason: "not_connected", detail: "Not connected to Miro" }));
    render(<MiroExportPanel open onClose={() => {}} />);
    fireEvent.click(await screen.findByText(i18n.t("miro.createBoard")));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe(i18n.t("miro.errNotConnected")));
  });

  it("a build the server no longer knows is an error, not a quiet stop", async () => {
    render(<MiroExportPanel open onClose={() => {}} />);
    fireEvent.click(await screen.findByText(i18n.t("miro.createBoard")));
    getMiroBoardStatus.mockResolvedValue(status("idle"));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe(i18n.t("miro.exportError")));
  });

  it("a board that completes without a link is an error, not ready (R79)", async () => {
    render(<MiroExportPanel open onClose={() => {}} />);
    fireEvent.click(await screen.findByText(i18n.t("miro.createBoard")));
    getMiroBoardStatus.mockResolvedValue({ ...status("completed"), board_url: null });
    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe(i18n.t("miro.exportError")));
    expect(screen.getByText(i18n.t("miro.createBoard"))).toBeInTheDocument();
    expect(screen.queryByText(i18n.t("miro.boardReady", { count: 40 }))).toBeNull();
    expect(screen.queryByText(i18n.t("miro.openInMiro"))).toBeNull();
  });

  it("a Stop that misses (the board had just finished) shows the finished board", async () => {
    cancelMiroBoard.mockRejectedValueOnce(new Error("POST /miro/board/cancel 404"));
    await building(build({ phase: "groups", count_done: 8, count_total: 9, fraction: 0.95 }));
    await screen.findByText(i18n.t("miro.progressGroups", { done: 8, total: 9 }));
    getMiroBoardStatus.mockResolvedValue(status("completed"));
    fireEvent.click(screen.getByText(i18n.t("miro.cancel")));
    await screen.findByText(i18n.t("miro.boardReady", { count: 40 }));
  });

  it("closing while it is still loading starts no watching behind the shut panel", async () => {
    // Closed during "Checking connection…": the connection answers afterwards, a board is running.
    let connected: (v: unknown) => void = () => {};
    getMiroStatus.mockReset().mockImplementation(() => new Promise((r) => { connected = r; }));
    getMiroBoardStatus.mockResolvedValue(status("running", build({
      phase: "quotes", count_done: 1, count_total: 9, fraction: 0.1 })));
    const { rerender } = render(<MiroExportPanel open onClose={() => {}} />);
    await waitFor(() => expect(getMiroStatus).toHaveBeenCalledTimes(1));
    rerender(<MiroExportPanel open={false} onClose={() => {}} />);
    connected({ connected: true });
    await new Promise((r) => setTimeout(r, 2000));
    expect(getMiroBoardStatus).not.toHaveBeenCalled();  // nothing read, nothing polled
  });

  it("a language change does not take a finished board's link away", async () => {
    render(<MiroExportPanel open onClose={() => {}} />);
    fireEvent.click(await screen.findByText(i18n.t("miro.createBoard")));
    getMiroBoardStatus.mockResolvedValue(status("completed"));
    await screen.findByText(i18n.t("miro.openInMiro"));
    await i18n.changeLanguage("en-GB");
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.getByText(i18n.t("miro.openInMiro"))).toBeTruthy();
    await i18n.changeLanguage("en");
  });
});

describe("MiroExportPanel — a status check that fails (R78)", () => {
  beforeEach(async () => {
    getMiroStatus.mockReset();
    getMiroBoardStatus.mockReset().mockResolvedValue(status("idle"));
    await i18n.changeLanguage("en");
  });

  it("a server error says the request failed, beside the paste field", async () => {
    getMiroStatus.mockRejectedValue(Object.assign(new Error("GET /miro/status 500"), { status: 500 }));
    render(<MiroExportPanel open onClose={() => {}} />);
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toBe(i18n.t("miro.requestFailed", { status: 500 })));
    expect(screen.getByLabelText(i18n.t("miro.tokenPlaceholder"))).toBeTruthy();
  });

  it("a request that never reached the server says the server could not be reached", async () => {
    getMiroStatus.mockRejectedValue(new TypeError("Failed to fetch"));
    render(<MiroExportPanel open onClose={() => {}} />);
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toBe(i18n.t("miro.serverUnreachable")));
    expect(screen.getByLabelText(i18n.t("miro.tokenPlaceholder"))).toBeTruthy();
  });

  it("a connected status whose running-board read fails keeps the form, with no error", async () => {
    getMiroStatus.mockResolvedValue({ connected: true });
    getMiroBoardStatus.mockRejectedValue(new TypeError("Failed to fetch"));
    render(<MiroExportPanel open onClose={() => {}} />);
    await screen.findByText(i18n.t("miro.createBoard"));
    await waitFor(() => expect(getMiroBoardStatus).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
