/**
 * Send to Miro's Miro app tab: the board file, copied or downloaded, for the Bristlenose app in
 * Miro to draw (docs/mockups/miro-board-file-route.html, owner, 9 Nov 2026).
 *
 * What a researcher would notice: it opens on this tab even when a token is connected; the choices
 * come before the buttons; Copy puts a board the Miro panel can read on the clipboard and says
 * "Copied" in its own place, until a choice changes; Download says how many quotes; a refusal is
 * said in words; the "?" opens the help for the tab in front.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MiroExportPanel } from "../MiroExportPanel";
import i18n from "../../i18n";

const { getMiroStatus, getFigJamBoard, figjamBoardDownloadUrl } = vi.hoisted(() => ({
  getMiroStatus: vi.fn(),
  getFigJamBoard: vi.fn(),
  figjamBoardDownloadUrl: vi.fn(() => "/api/projects/1/export/figjam-board.json"),
}));

vi.mock("../../utils/api", () => ({
  getMiroStatus: (...a: unknown[]) => getMiroStatus(...a),
  getFigJamBoard: (...a: unknown[]) => getFigJamBoard(...a),
  figjamBoardDownloadUrl: (...a: unknown[]) => figjamBoardDownloadUrl(...(a as [])),
  postMiroConnect: vi.fn(),
  postMiroDisconnect: vi.fn(),
  startMiroBoard: vi.fn(),
  startScreensMiro: vi.fn(),
  getMiroBoardStatus: vi.fn().mockResolvedValue({ status: "idle" }),
  getScreensMiroStatus: vi.fn().mockResolvedValue({ status: "idle" }),
  cancelMiroBoard: vi.fn(),
  cancelScreensMiro: vi.fn(),
  apiGet: vi.fn().mockResolvedValue({ project_name: "Kitchen study" }),
}));
vi.mock("../../utils/announce", () => ({ announce: vi.fn() }));
vi.mock("../../utils/exportData", () => ({ isExportMode: vi.fn(() => false) }));
vi.mock("../../shims/bridge", () => ({ postStoreMiroToken: vi.fn() }));

const BOARD = { version: 1, title: "Kitchen study — Café", totals: { quotes: 112 }, columns: [] };

const copyButton = () => screen.getByTestId("bn-miro-copy-board");
/** What the Copy button says: the label not hidden from assistive tech. */
const copySays = () =>
  Array.from(copyButton().querySelectorAll("span"))
    .filter((s) => s.getAttribute("aria-hidden") !== "true")
    .map((s) => s.textContent)
    .join("");

/** The board inside the HTML flavour, read as the Miro and FigJam panels read it
 *  (figjam-plugin/src/clipboard.ts: base64 of the UTF-8 JSON in data-bristlenose-board). */
function boardInHtml(html: string): unknown {
  const m = /data-bristlenose-board\s*=\s*["']([A-Za-z0-9+/=\s]+)["']/.exec(html);
  if (!m) return null;
  const bytes = Uint8Array.from(atob(m[1]), (c) => c.charCodeAt(0));
  return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
}

/** jsdom's Blob has no text(): read it as a browser's FileReader would. */
function blobText(b: Blob): Promise<string> {
  return new Promise((resolve) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result));
    r.readAsText(b);
  });
}

let writeText: ReturnType<typeof vi.fn>;

beforeEach(async () => {
  await i18n.changeLanguage("en");
  getMiroStatus.mockReset().mockResolvedValue({ connected: false });
  getFigJamBoard.mockReset().mockResolvedValue(BOARD);
  figjamBoardDownloadUrl.mockClear();
  writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Send to Miro — the Miro app tab", () => {
  it("opens on the Miro app tab, even when a token is connected", async () => {
    getMiroStatus.mockResolvedValue({ connected: true });
    render(<MiroExportPanel open onClose={() => {}} />);
    expect(screen.getByRole("heading").textContent).toBe(i18n.t("miro.quotesTitle"));
    await waitFor(() => expect(getMiroStatus).toHaveBeenCalled());
    expect(screen.getByRole("tab", { name: i18n.t("miro.tabApp") })).toHaveAttribute("aria-selected", "true");
    expect(copyButton()).toBeInTheDocument();
    expect(screen.queryByText(i18n.t("miro.createBoard"))).toBeNull();
  });

  it("puts the choices before the buttons, so they are made first", () => {
    render(<MiroExportPanel open onClose={() => {}} />);
    const split = screen.getByTestId("bn-miro-app-split-long");
    expect(split.compareDocumentPosition(copyButton()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("copies the board with the chosen settings, then says Copied in the button's place", async () => {
    expect(i18n.t("miro.copied")).not.toBe("miro.copied");
    render(<MiroExportPanel open onClose={() => {}} />);
    fireEvent.click(screen.getByLabelText(i18n.t("miro.stickyShapeSquare")));
    fireEvent.click(screen.getByTestId("bn-miro-app-split-long"));
    expect(copySays()).toBe(i18n.t("miro.copyBoard"));
    fireEvent.click(copyButton());
    await waitFor(() => expect(copySays()).toBe(i18n.t("miro.copied")));
    expect(getFigJamBoard).toHaveBeenCalledWith(
      expect.objectContaining({ sticky_shape: "square", split_long_quotes: false, locale: "en" }));
    // No ClipboardItem here (jsdom): the bare board JSON, which both panels also read.
    expect(JSON.parse(writeText.mock.calls[0][0] as string)).toEqual(BOARD);
    // No status line: the button says it.
    expect(screen.queryByTestId("bn-miro-downloaded")).toBeNull();
  });

  it("forgets Copied when a choice changes, since the board would differ", async () => {
    render(<MiroExportPanel open onClose={() => {}} />);
    fireEvent.click(copyButton());
    await waitFor(() => expect(copySays()).toBe(i18n.t("miro.copied")));
    fireEvent.click(screen.getByLabelText(i18n.t("miro.stickyShapeSquare")));
    expect(copySays()).toBe(i18n.t("miro.copyBoard"));
  });

  it("writes to the clipboard inside the click, with the board as two flavours (Safari)", async () => {
    let resolveBoard: (b: unknown) => void = () => {};
    getFigJamBoard.mockReturnValue(new Promise((r) => { resolveBoard = r; }));
    const items: Array<Record<string, Promise<Blob>>> = [];
    const write = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("ClipboardItem", class {
      constructor(data: Record<string, Promise<Blob>>) { items.push(data); }
    });
    Object.defineProperty(navigator, "clipboard", { value: { write, writeText }, configurable: true });
    render(<MiroExportPanel open onClose={() => {}} />);
    fireEvent.click(copyButton());
    // Called before the board has arrived: after an await, Safari refuses the write.
    expect(write).toHaveBeenCalledTimes(1);
    resolveBoard(BOARD);
    const html = await blobText(await items[0]["text/html"]);
    expect(boardInHtml(html)).toEqual(BOARD);
    expect(await blobText(await items[0]["text/plain"])).toBe(BOARD.title);
    await waitFor(() => expect(copySays()).toBe(i18n.t("miro.copied")));
    expect(writeText).not.toHaveBeenCalled();
  });

  it("says why when the board can't be made, in the reader's words", async () => {
    getFigJamBoard.mockRejectedValue(Object.assign(new Error("GET 422"), { reason: "no_quotes_selected" }));
    render(<MiroExportPanel open onClose={() => {}} />);
    fireEvent.click(copyButton());
    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe(i18n.t("miro.errNoQuotesSelected")));
    expect(copySays()).toBe(i18n.t("miro.copyBoard"));
  });

  it("says the copy failed, and offers the download, when the clipboard refuses", async () => {
    writeText.mockRejectedValue(new DOMException("denied", "NotAllowedError"));
    render(<MiroExportPanel open onClose={() => {}} />);
    fireEvent.click(copyButton());
    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe(i18n.t("miro.copyFailed")));
  });

  it("downloads the board file and says how many quotes it holds", async () => {
    render(<MiroExportPanel open onClose={() => {}} />);
    fireEvent.click(screen.getByTestId("bn-miro-download-board"));
    await waitFor(() =>
      expect(screen.getByTestId("bn-miro-downloaded").textContent).toBe(
        i18n.t("figjam.downloading", { count: 112 })));
    expect(figjamBoardDownloadUrl).toHaveBeenCalledWith(
      expect.objectContaining({ sticky_shape: "rectangle", split_long_quotes: true, board_name: "" }));
  });

  it("offers the install page and each tab's own help", async () => {
    render(<MiroExportPanel open onClose={() => {}} />);
    expect(screen.getByText(i18n.t("miro.appAddLink")).closest("a")?.getAttribute("href")).toMatch(
      /^https:\/\/miro\.com\/app-install\/\?.*client_id=3458764676772092122/);
    expect(screen.getByTestId("bn-miro-help").getAttribute("href")).toBe(
      "https://bristlenose.app/docs/miro-app.html");
    fireEvent.click(screen.getByRole("tab", { name: i18n.t("miro.tabToken") }));
    expect((await screen.findByTestId("bn-miro-help")).getAttribute("href")).toBe(
      "https://bristlenose.app/docs/send-to-miro.html");
  });

  it("moves between the tabs with the arrow keys", () => {
    render(<MiroExportPanel open onClose={() => {}} />);
    const app = screen.getByRole("tab", { name: i18n.t("miro.tabApp") });
    fireEvent.keyDown(app, { key: "ArrowRight" });
    const token = screen.getByRole("tab", { name: i18n.t("miro.tabToken") });
    expect(token).toHaveAttribute("aria-selected", "true");
    expect(token).toHaveFocus();
    expect(screen.queryByTestId("bn-miro-copy-board")).toBeNull();
  });

  it("the screens board has no tabs: a board file carries no screengrabs", async () => {
    render(<MiroExportPanel open screens onClose={() => {}} />);
    expect(screen.queryByRole("tablist")).toBeNull();
    expect(screen.getByRole("heading").textContent).toBe(i18n.t("miro.title"));
    expect(screen.queryByTestId("bn-miro-copy-board")).toBeNull();
    await waitFor(() => expect(getMiroStatus).toHaveBeenCalled());
  });
});
