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

const postMiroExport = vi.fn().mockResolvedValue({
  board_id: "b1",
  board_url: "https://miro.com/app/board/b1/",
  stickies: 3,
});

vi.mock("../../utils/api", () => ({
  getMiroStatus: vi.fn().mockResolvedValue({ connected: true }),
  postMiroConnect: vi.fn(),
  postMiroDisconnect: vi.fn(),
  postMiroExport: (...args: unknown[]) => postMiroExport(...args),
}));
vi.mock("../../utils/announce", () => ({ announce: vi.fn() }));
vi.mock("../../utils/exportData", () => ({ isExportMode: vi.fn(() => false) }));
vi.mock("../../shims/bridge", () => ({ postStoreMiroToken: vi.fn() }));

async function exportOnce(language: string): Promise<Record<string, unknown>> {
  await i18n.changeLanguage(language);
  render(<MiroExportPanel open onClose={() => {}} />);
  const button = await screen.findByText(i18n.t("miro.createBoard"));
  fireEvent.click(button);
  await waitFor(() => expect(postMiroExport).toHaveBeenCalled());
  // Index arithmetic, not `.at(-1)`: the build's tsconfig is `lib: ES2020`
  // and `Array.prototype.at` is ES2022, so `tsc -b` refuses it.
  const calls = postMiroExport.mock.calls;
  return calls[calls.length - 1][0] as Record<string, unknown>;
}

describe("MiroExportPanel — the board's language travels with the request", () => {
  beforeEach(() => {
    postMiroExport.mockClear();
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

  it("still sends the other fields it always sent", async () => {
    const body = await exportOnce("en");
    expect(body).toMatchObject({ colour_by: "sentiment", clips_base: "", locale: "en" });
  });
});
