/**
 * A pasted token that connected but wasn't saved says where it couldn't be saved.
 *
 * `POST /connect` reports `persisted` and the kind of `store` it wrote to; in the
 * browser the panel words the notice in that store's own name (Keychain, the
 * desktop keyring, the Bristlenose settings file). The Mac app never shows it:
 * there Python's Keychain write is a sandboxed no-op by design and the native
 * sheet owns the warning, so `persisted: false` would be a false alarm.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MiroExportPanel } from "../MiroExportPanel";
import i18n from "../../i18n";
import { announce } from "../../utils/announce";
import type { MiroStatusResponse } from "../../utils/types";

const { postMiroConnect, desktop } = vi.hoisted(() => ({
  postMiroConnect: vi.fn(),
  desktop: { value: false },
}));

vi.mock("../../utils/api", () => ({
  getMiroStatus: vi.fn().mockResolvedValue({ connected: false }),
  postMiroConnect: (...args: unknown[]) => postMiroConnect(...args),
  postMiroDisconnect: vi.fn(),
  startMiroBoard: vi.fn(),
  getMiroBoardStatus: vi.fn().mockResolvedValue({ status: "idle" }),
  cancelMiroBoard: vi.fn(),
  apiGet: vi.fn().mockResolvedValue({ project_name: "Kitchen study" }),
}));
vi.mock("../../utils/announce", () => ({ announce: vi.fn() }));
vi.mock("../../utils/exportData", () => ({ isExportMode: vi.fn(() => false) }));
vi.mock("../../shims/bridge", () => ({ postStoreMiroToken: vi.fn() }));
vi.mock("../../utils/platform", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../utils/platform")>()),
  isDesktop: () => desktop.value,
}));

const WARNINGS = [
  "miro.persistWarningKeychain",
  "miro.persistWarningKeyring",
  "miro.persistWarningFile",
];

/** Paste a token and wait for the configure view. */
async function connectWith(reply: MiroStatusResponse): Promise<void> {
  postMiroConnect.mockResolvedValue(reply);
  render(<MiroExportPanel open onClose={() => {}} />);
  const field = await screen.findByLabelText(i18n.t("miro.tokenPlaceholder"));
  fireEvent.change(field, { target: { value: "tok-abc" } });
  fireEvent.click(screen.getByText(i18n.t("miro.connect")));
  await screen.findByText(i18n.t("miro.createBoard"));
}

function shownWarnings(): string[] {
  return WARNINGS.filter((k) => screen.queryByText(i18n.t(k)) !== null);
}

describe("MiroExportPanel — a token that connected but wasn't saved", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("en");
    postMiroConnect.mockReset();
    vi.mocked(announce).mockClear();
    desktop.value = false;
  });

  it.each([
    ["keychain", "miro.persistWarningKeychain"],
    ["secret_service", "miro.persistWarningKeyring"],
    ["file", "miro.persistWarningFile"],
  ] as const)("names the %s store in its own words", async (store, key) => {
    // The key must exist, or t() echoes it and the test passes on nothing.
    expect(i18n.t(key)).not.toBe(key);
    await connectWith({ connected: true, persisted: false, store });
    expect(screen.getByText(i18n.t(key))).toBeInTheDocument();
    expect(shownWarnings()).toEqual([key]);
    // State beside "Connected ✓", not an error: the connection works.
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByText(i18n.t("miro.createBoard"))).toBeInTheDocument();
  });

  it.each([
    ["keychain", "miro.persistWarningKeychain"],
    ["secret_service", "miro.persistWarningKeyring"],
    ["file", "miro.persistWarningFile"],
  ] as const)("speaks the %s notice through the shared live region", async (store, key) => {
    // The panel is a modal: useInert makes the app root inert, so a live region
    // inside it is silent. The notice goes through announce(), and the visible
    // paragraph carries no role of its own, so it is not spoken twice.
    await connectWith({ connected: true, persisted: false, store });
    expect(announce).toHaveBeenCalledWith(i18n.t(key));
    expect(screen.getByText(i18n.t(key))).not.toHaveAttribute("role");
  });

  it("says nothing when the token was saved", async () => {
    await connectWith({ connected: true, persisted: true, store: "keychain" });
    expect(shownWarnings()).toEqual([]);
    for (const k of WARNINGS) expect(announce).not.toHaveBeenCalledWith(i18n.t(k));
  });

  it("says nothing to an older server that doesn't report it", async () => {
    await connectWith({ connected: true });
    expect(shownWarnings()).toEqual([]);
  });

  it("says nothing in the Mac app, where the native sheet owns the warning", async () => {
    desktop.value = true;
    await connectWith({ connected: true, persisted: false, store: "keychain" });
    await waitFor(() => expect(postMiroConnect).toHaveBeenCalled());
    expect(shownWarnings()).toEqual([]);
  });
});
