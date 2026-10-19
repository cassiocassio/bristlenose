/**
 * What the Miro panel SENDS, not what it renders.
 *
 * This repo has already paid for the difference: the v2 codebook navigator's
 * tests asserted that the switch *renders* and never what it *put*, so a
 * single-key patch to a replacement endpoint shipped to nine channels (root
 * CLAUDE.md, "Deleting a UI surface can orphan the test that was pinning a wire
 * contract"). `locale` on the Miro request is the same shape of contract: drop
 * it and every board silently reverts to English, with every suite green,
 * because the server's default is `"en"` by design.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MiroExportPanel } from "../MiroExportPanel";
import i18n from "../../i18n";

const startMiroBoard = vi.fn().mockResolvedValue({ status: "started" });
const board = (status: string, extra: object = {}) => ({
  status, board_url: "https://miro.com/app/board/b1/", stickies: 3, reason: null, vars: {},
  build: null, ...extra,
});
const getMiroBoardStatus = vi.fn();

vi.mock("../../utils/api", () => ({
  getMiroStatus: vi.fn().mockResolvedValue({ connected: true }),
  postMiroConnect: vi.fn(),
  postMiroDisconnect: vi.fn(),
  startMiroBoard: (...args: unknown[]) => startMiroBoard(...args),
  getMiroBoardStatus: (...args: unknown[]) => getMiroBoardStatus(...args),
  cancelMiroBoard: vi.fn().mockResolvedValue({ cancelled: true }),
  apiGet: vi.fn().mockResolvedValue({ project_name: "Kitchen study" }),
}));
vi.mock("../../utils/announce", () => ({ announce: vi.fn() }));
vi.mock("../../utils/exportData", () => ({ isExportMode: vi.fn(() => false) }));
vi.mock("../../shims/bridge", () => ({ postStoreMiroToken: vi.fn() }));

async function exportOnce(language: string): Promise<Record<string, unknown>> {
  await i18n.changeLanguage(language);
  render(<MiroExportPanel open onClose={() => {}} />);
  const button = await screen.findByText(i18n.t("miro.createBoard"));
  fireEvent.click(button);
  await waitFor(() => expect(startMiroBoard).toHaveBeenCalled());
  // Index arithmetic, not `.at(-1)`: the build's tsconfig is `lib: ES2020`
  // and `Array.prototype.at` is ES2022, so `tsc -b` refuses it.
  const calls = startMiroBoard.mock.calls;
  return calls[calls.length - 1][0] as Record<string, unknown>;
}

describe("MiroExportPanel — the board's language travels with the request", () => {
  beforeEach(() => {
    startMiroBoard.mockClear();
    getMiroBoardStatus.mockReset().mockResolvedValue(board("completed"));
  });

  it("sends the researcher's UI language", async () => {
    expect(await exportOnce("es")).toMatchObject({ locale: "es" });
  });

  it("normalises a region tag the server would reject", async () => {
    // `i18n.language` can be `zh-TW`, which is not in SUPPORTED_LOCALES — sent
    // raw it falls back to English server-side and the board is silently wrong,
    // which is the exact failure this field exists to end. Same normalisation
    // the HTML export does (AppLayout.triggerReportDownload).
    expect(await exportOnce("zh-TW")).toMatchObject({ locale: "zh-Hant" });
  });

  it("still sends the other fields it always sent, flat colour by default", async () => {
    const body = await exportOnce("en");
    // Flat on every board unless the researcher picks sentiment (owner, 19 Oct 2026).
    expect(body).toMatchObject({ colour_by: "none", clips_base: "", locale: "en" });
  });

  it("offers no clip links while they are parked, and sends no folder", async () => {
    const body = await exportOnce("en");
    expect(screen.queryByText(i18n.t("miro.linkClipsLabel"))).toBeNull();
    expect(body).toMatchObject({ clips_base: "" });
  });
});

describe("MiroExportPanel — a partial board keeps its address", () => {
  it("shows the localised sentence AND the url the server sent in vars", async () => {
    // A half-built board's job ends failed, naming its reason and carrying the
    // board's address. The localised sentence tells the researcher to open it;
    // without the address that is an instruction nobody can follow.
    getMiroBoardStatus.mockReset().mockResolvedValueOnce(board("idle")).mockResolvedValue(
      board("failed", {
        board_url: "https://miro.com/app/board/x9/",
        reason: "board_incomplete",
        vars: { url: "https://miro.com/app/board/x9/" },
      }));
    await i18n.changeLanguage("es");
    render(<MiroExportPanel open onClose={() => {}} />);
    fireEvent.click(await screen.findByText(i18n.t("miro.createBoard")));
    const sentence = i18n.t("miro.errBoardIncomplete");
    // Match on the element's OWN text, not textContent: every ancestor of the
    // error line contains it too, and a textContent matcher finds them all.
    const shown = await screen.findByText((content) => content.includes(sentence));
    expect(shown.textContent).toContain(sentence);
    expect(shown.textContent).toContain("https://miro.com/app/board/x9/");
    expect(shown.textContent).not.toContain("Board created but incomplete");
  });
});
